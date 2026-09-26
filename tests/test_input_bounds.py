"""입력 경계 (D68). **DB 가 필요 없다.**

2026-09-26 감사가 잰 구멍들이다 — 클라이언트 값이 `INTERNAL 500` 이 되거나, 천장 없는 필드가
모델이 읽는 응답을 통째로 부풀렸다. D25·D58 이 이미 이름 붙인 부류를 **나머지 자리까지** 닫는다.

**DSN 이 죽어 있는 것이 HTTP 검사의 판정 장치다** (test_unstorable_input 과 같다).
검증이 거절하면 `VALIDATION` 422 이고, 거절하지 못하면 연결까지 내려가 `INTERNAL` 500 이 된다.
"""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from sillok import api, service
from sillok.config import Config

DEAD_DSN = "postgresql://sillok:x@127.0.0.1:1/sillok"
BODY_REJECTED = {
    "ok": False,
    "error": {"code": "VALIDATION", "message": f"body larger than {api.BODY_MAX} bytes"},
}


def _config(**overrides) -> Config:
    base = dict(
        database_url=DEAD_DSN,
        host="127.0.0.1",
        port=8080,
        workspace=".",
        bearer_token="",
        openai_api_key="",
    )
    base.update(overrides)
    return Config(**base)


@pytest.fixture
def client():
    # D67: 토큰 없는 앱은 루프백 Host 만 받는다.
    with TestClient(
        api.create_app(_config()), base_url="http://127.0.0.1:8080", raise_server_exceptions=False
    ) as c:
        yield c


def _event(**over) -> dict:
    body = {
        "project": "t_bounds",
        "kind": "success",
        "title": "제목",
        "summary": "요약",
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "result": "success",
    }
    body.update(over)
    return body


def _rejected(**over) -> str:
    with pytest.raises(service.ValidationFailed) as exc:
        service.build_event(_event(**over))
    return str(exc.value)


# --- 타입이 틀린 enum 이 500 이 되지 않는다 ------------------------------------


@pytest.mark.parametrize("field", ["kind", "result"])
@pytest.mark.parametrize("bad", [["success"], {"a": 1}])
def test_unhashable_enum_values_are_validation(field, bad):
    """`not in` 이 집합에 대해 TypeError 를 냈다 — 리스트·딕트는 해시되지 않는다."""
    assert _rejected(**{field: bad}).startswith(f"{field} must be one of")


@pytest.mark.parametrize("field", ["kind", "result"])
def test_unhashable_enum_over_http_is_422_not_500(client, field):
    r = client.post("/v1/events", json=_event(**{field: ["success"]}))
    assert r.status_code == 422
    assert r.json()["error"]["message"].startswith(f"{field} must be one of")


# --- payload 의 NaN·Infinity ---------------------------------------------------


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_payload_numbers_are_validation(value):
    """`json.dumps` 기본값은 NaN 을 내보내고 Postgres `jsonb` 가 그것을 거절했다 → 500."""
    assert _rejected(payload={"x": [1, {"y": value}]}) == "payload must not contain NaN or Infinity"


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_non_finite_payload_over_http_is_422_not_500(client, literal):
    """파이썬 `json` 은 이 넷을 받아들인다(`1e999` 는 inf 가 된다). 전선 위의 모양 그대로 보낸다."""
    raw = (
        '{"project":"t_bounds","kind":"success","title":"t","summary":"s",'
        '"occurred_at":"2026-01-01T00:00:00Z","result":"success","payload":{"x":' + literal + "}}"
    )
    r = client.post("/v1/events", content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["message"] == "payload must not contain NaN or Infinity"


# --- 천장 (D58 확장) ------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "cap"),
    [
        ("root_cause", service.SUMMARY_MAX),
        ("resolution", service.SUMMARY_MAX),
        ("module", service.TITLE_MAX),
        ("created_by", service.TITLE_MAX),
        ("related_doc_path", service.TITLE_MAX),
    ],
)
def test_optional_text_fields_have_a_ceiling(field, cap):
    """`get_event` 는 행을 통째로 돌려준다 (D39). 감사에서 한 번에 120,383자가 나왔다."""
    assert _rejected(**{field: "a" * (cap + 1)}) == f"{field} longer than {cap}"
    event = service.build_event(_event(**{field: "a" * cap}))
    assert getattr(event, field) == "a" * cap


def test_a_long_module_over_http_is_422_not_500(client):
    """btree 인덱스 행 한도(약 2.7KB)를 넘는 module 이 500 이었다."""
    r = client.post("/v1/events", json=_event(module="m" * 3000))
    assert r.status_code == 422
    assert r.json()["error"]["message"] == f"module longer than {service.TITLE_MAX}"


# --- project 의 공백 --------------------------------------------------------------


@pytest.mark.parametrize(
    "inner", ["　", " ", "\x0b", "\x0c", " ", "\u0085", "\x1c", " "]
)
def test_project_rejects_every_unicode_whitespace_inside(inner):
    """앞뒤는 `strip()` 이 유니코드 공백을 다 벗기는데 가운데는 넷만 봤다 — 겉보기에 같은 다른 project."""
    with pytest.raises(service.ValidationFailed) as exc:
        service.normalize_project("t" + inner + "x")
    assert str(exc.value) == "project must not contain whitespace, slash or NUL"


# --- 공백뿐인 필수 텍스트 ---------------------------------------------------------


@pytest.mark.parametrize("field", ["title", "summary"])
@pytest.mark.parametrize("blank", ["   ", "　", "\t\n"])
def test_blank_title_or_summary_counts_as_missing(field, blank):
    assert _rejected(**{field: blank}) == f"missing required field: {field}"


def test_required_text_is_stored_as_sent():
    """벗겨서 판정하지만 **벗겨서 저장하지 않는다** — D25 의 정규화는 project 만이다."""
    event = service.build_event(_event(title="  제목  ", summary=" 요약 "))
    assert (event.title, event.summary) == ("  제목  ", " 요약 ")


# --- 질의 길이 -----------------------------------------------------------------------


def test_search_docs_rejects_a_long_query_before_embedding(monkeypatch):
    """임베딩 호출 전이다 — 긴 질의가 제공자로 가거나 원장에 남지 않는다."""
    embedded = []
    monkeypatch.setattr(service, "_embed", lambda *a, **k: embedded.append(a) or [[0.0] * 1536])
    body = {"project": "t_bounds", "query": "가" * (service.QUERY_MAX + 1)}
    with pytest.raises(service.ValidationFailed) as exc:
        service.search_docs(DEAD_DSN, body, "sk-test", client="http")
    assert str(exc.value) == f"query longer than {service.QUERY_MAX}"
    assert embedded == []


def test_search_events_rejects_a_long_query_before_sql():
    body = {"project": "t_bounds", "query": "a " * service.QUERY_MAX}
    with pytest.raises(service.ValidationFailed) as exc:
        service.search_events(DEAD_DSN, body, client="http")
    assert str(exc.value) == f"query longer than {service.QUERY_MAX}"


def test_the_query_cap_counts_the_stripped_query():
    """공백만 늘린 질의는 길이가 아니라 **빈 질의**로 판정된다 — 두 도구의 기존 규칙 그대로다.

    search_docs 는 빈 질의를 거절하고(D33 §6), search_events 는 술어 없이 필터로만 돈다(D34 §3).
    """
    blank = " " * (service.QUERY_MAX * 3)
    with pytest.raises(service.ValidationFailed) as exc:
        service.search_docs(DEAD_DSN, {"project": "t_bounds", "query": blank}, "", client="http")
    assert "longer" not in str(exc.value)
    with pytest.raises(psycopg.OperationalError) as exc:  # 죽은 DSN 까지 내려간다 — 길이로 거절되지 않았다
        service.search_events(DEAD_DSN, {"project": "t_bounds", "query": blank}, client="http")
    assert not isinstance(exc.value, service.ValidationFailed)


@pytest.mark.parametrize("tool", ["search_docs", "search_events"])
def test_padding_does_not_count_toward_the_query_cap(tool):
    """앞뒤 공백으로 부풀린 짧은 질의는 통과한다 — 원문 길이를 재는 구현과 가르는 검사다.

    공백**뿐인** 질의는 빈 질의 규칙이 먼저 걸러 이 차이를 보지 못한다 (주입으로 확인).
    """
    body = {"project": "t_bounds", "query": "  a" + " " * (service.QUERY_MAX + 10)}
    call = (
        (lambda: service.search_docs(DEAD_DSN, body, "", client="http"))
        if tool == "search_docs"
        else (lambda: service.search_events(DEAD_DSN, body, client="http"))
    )
    with pytest.raises(psycopg.OperationalError) as exc:  # 검증을 지나 죽은 DSN 에서 멈춘다
        call()
    assert not isinstance(exc.value, service.ValidationFailed), exc.value


def test_a_query_at_the_cap_is_accepted():
    body = {"project": "t_bounds", "query": "a" * service.QUERY_MAX}
    with pytest.raises(psycopg.OperationalError) as exc:  # 검증을 지나 죽은 DSN 에서 멈춘다
        service.search_events(DEAD_DSN, body, client="http")
    assert not isinstance(exc.value, service.ValidationFailed)


# --- 요청 본문 상한 --------------------------------------------------------------------


def _big(n: int) -> bytes:
    return b"x" * n


@pytest.mark.parametrize("path", ["/v1/events", "/v1/search/events", "/v1/docs/proposals", "/mcp"])
def test_an_oversized_body_is_refused_before_it_is_read(client, monkeypatch, path):
    """`/mcp` 도 같은 문턱이다 — 한쪽만 평문 413 이면 D67 이 닫은 갈라짐이 되살아난다."""
    called = []
    monkeypatch.setattr(service, "save_event", lambda *a, **k: called.append(a))
    r = client.post(
        path,
        content=_big(api.BODY_MAX + 1),
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    assert r.status_code == 422
    assert r.json() == BODY_REJECTED
    assert called == []


def test_a_chunked_body_is_counted_not_trusted(client):
    """`Content-Length` 가 없는 청크 전송도 센다 — 헤더만 믿으면 이 길로 무제한이 된다."""

    def chunks():
        for _ in range(5):
            yield _big(api.BODY_MAX // 4)

    r = client.post("/v1/events", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json() == BODY_REJECTED


def test_a_body_at_the_limit_reaches_the_app(client):
    """문턱은 `>` 다 — SDK 의 `/mcp` 한도와 같은 비교라 두 얼굴이 같은 바이트에서 갈린다."""
    r = client.post(
        "/v1/events", content=_big(api.BODY_MAX), headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 422
    assert r.json()["error"]["message"] != BODY_REJECTED["error"]["message"]  # JSON 파싱에서 걸렸다


def test_an_ordinary_request_is_untouched(client):
    """상한이 본문을 다시 흘려보내는지 — 삼키면 평범한 요청이 빈 본문이 된다."""
    r = client.post("/v1/events", json=_event(kind="typo"))
    assert r.json()["error"]["message"].startswith("kind must be one of")
