"""검색·필터의 뜻과 모르는 키 (D69). **DB 가 필요 없다.**

2026-09-26 감사가 잰 것이다 — 두 얼굴 모두 모르는 키를 조용히 버렸다(`root_casue` 는 NULL 로 저장되고
`kindd` 는 필터 없는 검색이 됐다). 필터의 오타(`kind="error"`)는 200 빈 결과로 끝나
`zero_hit_queries` 를 부풀렸다. **DSN 이 죽어 있는 것이 판정 장치다** — 검증이 거절하면 422,
못 하면 연결까지 내려가 500 이다.
"""

from __future__ import annotations

import json

import psycopg
import pytest
from fastapi.testclient import TestClient

from sillok import api, service
from sillok.config import Config

DEAD_DSN = "postgresql://sillok:x@127.0.0.1:1/sillok"
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Host": "127.0.0.1:8080",
}


def _config(**overrides) -> Config:
    base = dict(
        database_url=DEAD_DSN, host="127.0.0.1", port=8080, workspace=".",
        bearer_token="", openai_api_key="",
    )
    base.update(overrides)
    return Config(**base)


@pytest.fixture
def client():
    with TestClient(
        api.create_app(_config()), base_url="http://127.0.0.1:8080", raise_server_exceptions=False
    ) as c:
        yield c


def _unknown(name: str) -> dict:
    return {"ok": False, "error": {"code": "VALIDATION", "message": f"unknown field: {name}"}}


EVENT = {
    "project": "t_semantics", "kind": "failure", "title": "t", "summary": "s",
    "occurred_at": "2026-01-01T00:00:00Z", "result": "failure",
}


# --- 문구 -------------------------------------------------------------------------------


def test_the_first_unknown_key_by_code_point_is_named():
    with pytest.raises(service.ValidationFailed) as exc:
        service.reject_unknown({"project", "zeta", "Alpha", "b"}, {"project"})
    assert str(exc.value) == "unknown field: Alpha"  # 'A' < 'b' < 'z'


@pytest.mark.parametrize("name", ["", "k" * (service.TITLE_MAX + 1), "a\x00b", "a\ud800b"])
def test_a_key_that_cannot_be_named_gets_the_fixed_message(name):
    """이름을 잘라 싣지 않는다 — D68 이 긴 질의를 잘라 기록하는 안을 버린 그 이유다."""
    with pytest.raises(service.ValidationFailed) as exc:
        service.reject_unknown({name}, {"project"})
    assert str(exc.value) == "unknown field"


# --- HTTP 얼굴: 업무 라우트 아홉 ------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "body", "extra"),
    [
        ("/v1/events", EVENT, "root_casue"),
        ("/v1/search/docs", {"project": "t_semantics", "query": "q"}, "kindd"),
        ("/v1/search/events", {"project": "t_semantics"}, "kindd"),
        ("/v1/docs/proposals", {"project": "t_semantics", "path": "docs/a.md", "body": "x"}, "base_hsah"),
        ("/v1/ingest", {"project": "t_semantics"}, "workspce"),
        ("/v1/search/events", {"project": "t_semantics"}, "client"),  # D49 — 호출자가 얼굴을 위장한다
    ],
)
def test_an_unknown_body_key_is_refused_on_every_post(client, path, body, extra):
    r = client.post(path, json={**body, extra: "x"})
    assert r.status_code == 422
    assert r.json() == _unknown(extra)


@pytest.mark.parametrize(
    ("path", "extra"),
    [
        ("/v1/stats/events?project=t_semantics&modul=auth", "modul"),
        ("/v1/status?project=t_semantics&verbose=1", "verbose"),
        ("/v1/files?project=t_semantics&path=docs/a.md&ofset=4", "ofset"),
        ("/v1/events/1?project=t_semantics&projct=x", "projct"),
    ],
)
def test_an_unknown_query_key_is_refused_on_every_get(client, path, extra):
    """GET 은 FastAPI 가 선언 밖 질의 인자를 함수에 넣지 않는다 — `?modul=` 이 필터 없는 집계였다."""
    r = client.get(path)
    assert r.status_code == 422
    assert r.json() == _unknown(extra)


def test_a_typo_in_save_event_does_not_store_a_null():
    """되돌릴 수 없는 쪽이다 — 원장은 append-only 이고(D24) 수정 경로가 없다(D59)."""
    with pytest.raises(service.ValidationFailed) as exc:
        service.build_event({**EVENT, "root_casue": "pool"})
    assert str(exc.value) == "unknown field: root_casue"


# --- MCP 얼굴 — SDK 가 선언 밖 인자를 Service 전에 떨어뜨린다 -------------------------------


def _call(client, name, arguments):
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    r = client.post("/mcp", json=body, headers=MCP_HEADERS)
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result.get("isError") is False, result  # D44 — 실패도 정상 결과다
    return json.loads(result["content"][0]["text"])


@pytest.mark.parametrize(
    ("tool", "arguments", "extra"),
    [
        ("save_event", {k: v for k, v in EVENT.items()}, "root_casue"),
        ("search_docs", {"project": "t_semantics", "query": "q"}, "kindd"),
        ("search_events", {"project": "t_semantics"}, "kindd"),
        ("get_event", {"project": "t_semantics", "event_id": 1}, "projct"),
        ("get_file", {"project": "t_semantics", "path": "docs/a.md"}, "ofset"),
        ("save_doc", {"project": "t_semantics", "path": "docs/a.md", "body": "x"}, "base_hsah"),
        ("event_stats", {"project": "t_semantics"}, "modul"),
        ("kb_status", {"project": "t_semantics"}, "verbose"),
    ],
)
def test_an_unknown_tool_argument_gets_the_same_envelope(client, tool, arguments, extra):
    """두 얼굴이 같은 인자에 같은 봉투를 낸다 (D46) — 여분 키도 그 인자다."""
    assert _call(client, tool, {**arguments, extra: "x"}) == _unknown(extra)


# --- 필터 enum --------------------------------------------------------------------------


def test_an_unknown_kind_filter_is_refused_not_logged_as_a_zero_hit():
    with pytest.raises(service.ValidationFailed) as exc:
        service.search_events(DEAD_DSN, {"project": "t_semantics", "kind": "error"}, client="http")
    assert str(exc.value).startswith("kind must be one of")


@pytest.mark.parametrize(("field", "bad"), [("doc_type", "bogus"), ("status", "live")])
def test_an_unknown_doc_filter_is_refused_before_embedding(monkeypatch, field, bad):
    embedded = []
    monkeypatch.setattr(service, "_embed", lambda *a, **k: embedded.append(a) or [[0.0] * 1536])
    with pytest.raises(service.ValidationFailed) as exc:
        service.search_docs(DEAD_DSN, {"project": "t_semantics", "query": "q", field: bad}, "sk-test")
    assert str(exc.value).startswith(f"{field} must be one of")
    assert embedded == []


@pytest.mark.parametrize("value", ["  failure  ", "   "])
def test_filters_are_stripped_before_the_enum_check(value):
    """벗긴 뒤에 본다 — `"  failure  "` 는 통과하고 공백뿐이면 필터가 아니다. 순서가 바뀌면 둘 다 거절된다."""
    with pytest.raises(psycopg.OperationalError):  # 검증을 지나 죽은 DSN 에서 멈춘다
        service.search_events(DEAD_DSN, {"project": "t_semantics", "kind": value}, client="http")


# --- 기간 -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("since", "until"),
    [("2026-02-01T00:00:00Z", "2026-01-01T00:00:00Z"), ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")],
)
def test_a_period_that_holds_no_instant_is_refused(since, until):
    """`[t, t)` 는 순간이 하나도 없는 창이다 — 0건으로 원장에 남기지 않는다."""
    body = {"project": "t_semantics", "since": since, "until": until}
    with pytest.raises(service.ValidationFailed) as exc:
        service.search_events(DEAD_DSN, body, client="http")
    assert str(exc.value) == "since is not before until"


def test_a_real_period_passes():
    body = {"project": "t_semantics", "since": "2026-01-01T00:00:00Z", "until": "2026-01-01T00:00:01Z"}
    with pytest.raises(psycopg.OperationalError):
        service.search_events(DEAD_DSN, body, client="http")
