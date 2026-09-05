"""담을 수 없는 클라이언트 입력이 `VALIDATION` 으로 거절되는가. **DB 가 필요 없다.**

D25 가 이름 붙인 부류다 — `클라이언트 입력 문제인데 서버 결함으로 보고된다`.
D25 는 `project` 에서, D36 은 `path` 에서 각각 막았지만 **둘 다 자리를 막았다.**
2026-09-04 실측에서 나머지 자리가 그대로 `INTERNAL 500` 을 냈다.

**DSN 이 죽어 있는 것이 이 파일의 판정 장치다.** 검증이 거절하면 `VALIDATION` 422 이고,
거절하지 못하면 연결까지 내려가 `INTERNAL` 500 이 된다 — 두 결과가 갈라지므로
이 검사들은 고치기 전에 실제로 붉은불이었다 (`INTERNAL != VALIDATION`).
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sillok import api, service
from sillok.config import Config

# 붙을 수 없는 DSN. 위 docstring 이 이유다.
DEAD_DSN = "postgresql://sillok:x@127.0.0.1:1/sillok"

NUL = "\x00"
# 짝 없는 서로게이트. JSON 의 `\ud800` 이 파이썬 str 로 오면 이 모양이다.
LONE = "\ud800"

# D43 의 이유로 MCP 는 Host 를 고쳐 보낸다.
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Host": "127.0.0.1:8080",
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
def client() -> TestClient:
    with TestClient(api.create_app(_config()), raise_server_exceptions=False) as c:
        yield c


def _event(**over) -> dict:
    body = {
        "project": "t_unstorable",
        "kind": "success",
        "title": "제목",
        "summary": "요약",
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "result": "success",
    }
    body.update(over)
    return body


# --- 가드 자체 ---------------------------------------------------------------


def test_require_text_rejects_nul():
    with pytest.raises(service.ValidationFailed) as exc:
        service.require_text("a" + NUL + "b", "title")
    assert str(exc.value) == "title must not contain NUL"


def test_require_text_rejects_an_unpaired_surrogate():
    with pytest.raises(service.ValidationFailed) as exc:
        service.require_text("a" + LONE + "b", "query")
    assert str(exc.value) == "query must not contain unpaired surrogates"


@pytest.mark.parametrize("value", ["한글", "😀", "plain ascii", "", "tab\tand\nnewline"])
def test_require_text_passes_everything_utf8_can_encode(value):
    """**거르는 것은 인코딩되지 않는 둘뿐이다.**

    이모지가 걸리면 가드가 계약보다 넓은 것이다 — `json` 이 `\\ud83d\\ude00` 같은 **짝**을
    이미 한 글자로 합쳐 주므로 남아 있는 서로게이트는 정의상 짝이 없다.
    """
    assert service.require_text(value, "f") == value
    value.encode("utf-8")  # 가드가 통과시킨 것은 실제로 인코딩된다


def test_json_pairs_surrogates_before_the_guard_sees_them():
    """가드가 이모지를 막지 않는 **이유**를 잠근다. 이 전제가 깨지면 위 검사가 공허해진다."""
    assert json.loads('"\\ud83d\\ude00"') == "😀"
    assert json.loads('"\\ud800"') == LONE


def test_payload_walk_reaches_keys_values_lists_and_depth():
    """**겉의 dict 만 보면 `payload` 하나로 부류가 되살아난다.** 네 자리를 다 걷는지 본다."""
    for payload in (
        {"x": "a" + NUL},
        {"a" + NUL: "x"},
        {"a": ["ok", "b" + NUL]},
        {"a": {"b": {"c": NUL}}},
        {"a": [{"b": ["c" + LONE]}]},
    ):
        with pytest.raises(service.ValidationFailed) as exc:
            service.require_payload_text(payload)
        assert str(exc.value).startswith("payload must not contain"), payload


def test_payload_walk_passes_an_ordinary_payload():
    """가드가 payload 를 통째로 막으면 D58 이 재는 대상이 사라진다."""
    service.require_payload_text({"module": "api", "count": 3, "tags": ["정상", "😀"], "nested": {"ok": True}})


@pytest.mark.parametrize("depth", [10, 200, 400, 5000, 20000])
def test_deep_payload_raises_no_recursion_error_in_either_step(depth):
    """**걷는 함수 앞에 재귀가 하나 더 있다** (Grok 재검토가 물은 것).

    `build_event` 는 `require_payload_text` 로 **먼저** 걷고, 그 다음에
    `_payload_text`(재귀적인 `json.dumps`)로 길이를 잰다. 순서가 이것인 이유가 여기다 —
    반대로 두면 깊은 payload 가 길이를 재다 RecursionError 를 내고, 걷는 쪽을
    스택으로 만든 보람이 없다. 둘 다 클라이언트가 만든 500 이다.

    **HTTP 로 재지 않는다.** 이 파일의 DSN 은 죽어 있어서 얕고 유효한 payload 는
    연결 실패로 500 이 되고, 그러면 깊이 때문에 난 500 과 구분되지 않는다.
    두 함수를 직접 부르는 것이 이 질문에 답하는 유일한 방법이다.
    (라이브 실측은 따로 했다: 깊이 10~200000 에서 500 이 하나도 없었다.)
    """
    node: Any = "ok"
    for _ in range(depth):
        node = {"a": node}

    # `build_event` 와 **같은 순서**로 부른다. 순서가 뒤집히면 이 검사가 붉은불이다.
    try:
        service.require_payload_text(node)
    except service.ValidationFailed as exc:
        # 너무 깊으면 여기서 걸린다 — 새 한계값이 아니라 길이 상한과 같은 문구다.
        assert str(exc) == f"payload longer than {service.PAYLOAD_MAX}"
        return
    service._payload_text(node)  # RecursionError 가 나면 여기서 죽는다


def test_payload_walk_does_not_recurse():
    """깊은 중첩에서 `RecursionError` 가 나면 그것도 클라이언트가 만든 500 이다.

    스택으로 걷는다는 것을 못 박는다 — 재귀로 바꾸면 이 검사가 붉은불이 된다.

    깊이는 **파이썬 재귀 한계(기본 1000)보다 깊고 `PAYLOAD_MAX` 보다 얕게** 고른다.
    상한을 넘기면 깊이 가드가 먼저 걸려 재귀 여부를 재지 못한다 — 그러면 공허해진다.
    """
    assert sys.getrecursionlimit() < 1500 < service.PAYLOAD_MAX  # 위 두 조건을 못 박는다
    deep: Any = "leaf"
    for _ in range(1500):
        deep = {"a": deep}
    service.require_payload_text(deep)


# --- 시각: UTC 로 옮기면 범위를 벗어나는 값 ------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["0001-01-01T00:00:00+23:59", "9999-12-31T23:59:59-23:59"],
)
def test_parse_timestamp_rejects_values_that_overflow_in_utc(raw):
    """ISO-8601 로도 datetime 으로도 멀쩡하고 **옮기는 순간** OverflowError 다."""
    with pytest.raises(service.ValidationFailed) as exc:
        service.parse_timestamp(raw, "occurred_at")
    assert "representable range" in str(exc.value)


def test_parse_timestamp_still_takes_an_extreme_offset_in_an_ordinary_year():
    """가드가 **오프셋 자체**를 막으면 안 된다 — 막힌 것은 범위를 벗어나는 결과다."""
    got = service.parse_timestamp("2026-01-01T00:00:00+23:59", "occurred_at")
    assert got.isoformat() == "2025-12-31T00:01:00+00:00"


# --- HTTP: 실측으로 500 을 냈던 자리 전부 --------------------------------------

# (이름, 메서드, 경로, 본문). 본문이 None 이면 질의 인자로만 민다.
# 2026-09-04 실측에서 이 목록이 전부 `INTERNAL 500` 이었다.
UNSTORABLE_CASES = [
    ("save_event title NUL", "POST", "/v1/events", _event(title="a" + NUL + "b")),
    ("save_event summary NUL", "POST", "/v1/events", _event(summary="a" + NUL + "b")),
    ("save_event module NUL", "POST", "/v1/events", _event(module=NUL)),
    ("save_event root_cause NUL", "POST", "/v1/events", _event(root_cause=NUL)),
    ("save_event title surrogate", "POST", "/v1/events", _event(title="a" + LONE + "b")),
    ("save_event summary surrogate", "POST", "/v1/events", _event(summary="a" + LONE + "b")),
    ("search_docs query NUL", "POST", "/v1/search/docs", {"project": "p", "query": "a" + NUL}),
    ("search_docs module NUL", "POST", "/v1/search/docs", {"project": "p", "query": "a", "module": NUL}),
    ("search_docs query surrogate", "POST", "/v1/search/docs", {"project": "p", "query": "a" + LONE}),
    ("search_docs module surrogate", "POST", "/v1/search/docs", {"project": "p", "query": "a", "module": LONE}),
    ("search_docs project surrogate", "POST", "/v1/search/docs", {"project": "p" + LONE, "query": "a"}),
    ("search_events query NUL", "POST", "/v1/search/events", {"project": "p", "query": "a" + NUL}),
    ("search_events module NUL", "POST", "/v1/search/events", {"project": "p", "query": "a", "module": NUL}),
    ("search_events kind NUL", "POST", "/v1/search/events", {"project": "p", "query": "a", "kind": NUL}),
    ("search_events query surrogate", "POST", "/v1/search/events", {"project": "p", "query": "a" + LONE}),
    ("stats module NUL", "GET", "/v1/stats/events?project=p&module=%00", None),
    ("ingest workspace NUL", "POST", "/v1/ingest", {"project": "p", "workspace": "/w" + NUL}),
    ("ingest workspace surrogate", "POST", "/v1/ingest", {"project": "p", "workspace": "/w" + LONE}),
    # payload 는 `jsonb` 로 들어간다 — **안쪽까지** 같은 규칙이다 (Grok 이 라이브에서 찾았다).
    ("payload value NUL", "POST", "/v1/events", _event(payload={"x": "a" + NUL})),
    ("payload value surrogate", "POST", "/v1/events", _event(payload={"x": "a" + LONE})),
    ("payload key NUL", "POST", "/v1/events", _event(payload={"a" + NUL: "x"})),
    ("payload key surrogate", "POST", "/v1/events", _event(payload={"a" + LONE: "x"})),
    ("payload inside a list", "POST", "/v1/events", _event(payload={"a": ["ok", "b" + NUL]})),
    ("payload nested three deep", "POST", "/v1/events", _event(payload={"a": {"b": {"c": NUL}}})),
    ("save_doc body surrogate", "POST", "/v1/docs/proposals", {"project": "p", "path": "docs/spec.md", "body": "a" + LONE, "base_hash": "sha256:" + "0" * 64}),
    ("save_event occurred_at overflows", "POST", "/v1/events", _event(occurred_at="0001-01-01T00:00:00+23:59")),
    # `parse_timestamp` 는 네 자리에서 불린다. 셋만 덮으면 네 번째가 조용히 열린다 —
    # 가드가 공유 함수에 있어 오늘은 맞지만, 잠그지 않으면 그 공유가 깨져도 모른다 (Grok 감사).
    ("save_event resolved_at overflows", "POST", "/v1/events", _event(resolved_at="9999-12-31T23:59:59-23:59")),
    ("stats since overflows", "GET", "/v1/stats/events?project=p&since=0001-01-01T00%3A00%3A00%2B23%3A59", None),
    ("search_events since overflows", "POST", "/v1/search/events", {"project": "p", "query": "a", "since": "0001-01-01T00:00:00+23:59"}),
    ("search_events until overflows", "POST", "/v1/search/events", {"project": "p", "query": "a", "until": "9999-12-31T23:59:59-23:59"}),
]


def _send(client: TestClient, method: str, path: str, body: dict | None):
    """**`json=` 을 쓰지 않는다.** httpx 가 짝 없는 서로게이트를 본문으로 인코딩하지 못해
    요청이 앱에 닿기도 전에 죽는다 — 그러면 검사가 서버가 아니라 클라이언트를 재는 것이 된다.

    실제 클라이언트가 보내는 것도 **JSON 이스케이프**(`\\ud800`)이지 raw 문자가 아니다.
    `json.dumps` 의 기본값(`ensure_ascii=True`)이 정확히 그 바이트를 만든다.
    """
    if body is None:
        return client.request(method, path)
    return client.request(
        method,
        path,
        content=json.dumps(body).encode("ascii"),
        headers={"content-type": "application/json"},
    )


@pytest.mark.parametrize(
    "name,method,path,body", UNSTORABLE_CASES, ids=[c[0] for c in UNSTORABLE_CASES]
)
def test_unstorable_input_is_validation_not_internal(client, name, method, path, body):
    """**`INTERNAL` 이면 실패다.** 500 은 이 부류가 고쳐지지 않았다는 신호다 (D21·D25)."""
    response = _send(client, method, path, body)
    envelope = response.json()
    assert envelope["ok"] is False, (name, envelope)
    assert envelope["error"]["code"] == "VALIDATION", (name, response.status_code, envelope)
    assert response.status_code == 422, (name, envelope)


def test_the_dead_dsn_really_would_have_produced_internal(client):
    """위 검사들이 **무엇과 갈라지는지** 못 박는다.

    같은 라우트에 담을 수 있는 값을 주면 연결까지 내려가 `INTERNAL` 이 된다.
    이 검사가 없으면 위 22 건이 `VALIDATION` 인 이유가 가드 때문인지
    라우트가 원래 못 도는 것인지 구분되지 않는다.
    """
    response = client.post("/v1/search/docs", json={"project": "p", "query": "정상"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL"


# --- 두 얼굴이 같은 답을 낸다 (D46) --------------------------------------------


MCP_PARITY_CASES = [
    ("save_event", _event(title="a" + NUL + "b"), "title must not contain NUL"),
    ("search_docs", {"project": "p", "query": "a" + NUL}, "query must not contain NUL"),
    ("event_stats", {"project": "p", "module": NUL}, "module must not contain NUL"),
]


@pytest.mark.parametrize("tool,arguments,message", MCP_PARITY_CASES, ids=[c[0] for c in MCP_PARITY_CASES])
def test_mcp_face_rejects_the_same_input_with_the_same_message(client, tool, arguments, message):
    """MCP 가 같은 Service 함수를 타므로 문구까지 같아야 한다 (D46).

    한쪽만 막히면 모델은 계약이 약속한 거절 대신 `internal error` 를 받고 재시도한다.
    """
    rpc = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": arguments}}
    response = client.post(
        "/mcp",
        content=json.dumps(rpc).encode("ascii"),  # `_send` 와 같은 이유다
        headers=MCP_HEADERS,
    )
    assert response.status_code == 200, response.text
    envelope = json.loads(response.json()["result"]["content"][0]["text"])
    assert envelope["ok"] is False, envelope
    assert envelope["error"] == {"code": "VALIDATION", "message": message}, envelope


def test_mcp_transport_rejects_a_lone_surrogate_before_the_service_sees_it(client):
    """**두 얼굴이 여기서만 갈라지고, 갈라지는 자리가 Service 밖이다.**

    HTTP 얼굴은 `\\ud800` 을 파이썬 str 로 받아 `require_text` 가 `VALIDATION` 으로 접는다.
    MCP 전송의 JSON 파서는 그 이스케이프를 **프로토콜 오류**로 먼저 거절한다 —
    JSON-RPC `-32700` 이고 도구는 불리지 않는다.

    D46 의 대조 대상은 **Service 봉투**이지 전송의 파서가 아니므로 이것은 위반이 아니다.
    다만 어느 쪽이 바뀌어도 알아야 하므로 관찰한 그대로 못 박는다 —
    적지 않으면 다음 사람이 위 파라미터에서 서로게이트가 빠진 것을 누락으로 읽는다.
    """
    rpc = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "search_docs", "arguments": {"project": "p", "query": "a" + LONE}},
    }
    response = client.post("/mcp", content=json.dumps(rpc).encode("ascii"), headers=MCP_HEADERS)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == -32700, response.text


# --- CLI: ok 가 아닌 run 이 KeyError 로 죽지 않는다 -----------------------------


@pytest.mark.parametrize("status", ["failed", "partial"])
def test_ingest_cli_prints_a_non_ok_run_without_crashing(capsys, monkeypatch, status):
    """`service.ingest` 가 돌려주는 dict 에는 **`error` 키가 없다.**

    실패 문구는 `kb_ingest_runs.error` **컬럼**에만 쓰인다 (`_finish`). 대괄호로 읽으면
    ok 가 아닌 모든 run 이 KeyError 로 죽는다 — `failed` 는 taxonomy 밖 문서 하나로 나므로
    키 없이도 닿는 자리다.
    """
    from sillok import cli

    run: dict = {
        "run_id": 1,
        "project": "t_cli",
        "status": status,
        "commit_sha": "",
        "files_seen": 1,
        "files_changed": 0,
        "files_deleted": 0,
        "chunks_upserted": 0,
        "chunks_embedded": 0,
        "chunks_pending": 0,
        "skipped": [],
    }
    # `cli` 는 `service` 를 함수 안에서 늦게 import 한다 (D19 의 이유). 모듈 속성을 민다.
    monkeypatch.setattr(service, "ingest", lambda *a, **k: run)
    monkeypatch.setenv("DATABASE_URL", DEAD_DSN)
    assert cli is not None  # import 가 실제로 되는지까지 본다

    assert cli.main(["ingest", "--project", "t_cli"]) == 1
    captured = capsys.readouterr()
    assert status in captured.err
    assert "KeyError" not in captured.err


def test_ingest_result_has_no_error_key():
    """위 검사의 전제. `_run` 의 반환 리터럴에 `error` 가 들어오면 그 검사는 공허해진다."""
    import inspect

    source = inspect.getsource(service._run)
    body = source.split("return {", 1)[1]
    assert '"error"' not in body
