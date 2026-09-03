"""D46 — 두 얼굴이 같은 것을 내는가. **여기가 그 판정 기준이다.**

같은 인자로 Service 함수를 직접 부른 결과와 `tools/call` 이 돌려준 텍스트를
**글자까지 같은 봉투**로 대조한다. HTTP 상태코드와 JSON-RPC 껍데기는 대조에서 뺀다 —
전송이 다르니 당연히 다르다. `UNAUTHORIZED` 는 HTTP 전용이라 대상이 아니다.

DB 가 필요하므로 D22 의 `--profile test` 에서 돈다.
"""

from __future__ import annotations

import json

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from sillok import api, ingest as ingest_rules, service
from sillok.config import Config

from dbcheck import DSN, needs_db

PROJECT = "t_step8"
FM = "---\ntitle: T\ndoc_type: other\nstatus: current\nmodule: null\n---\n\n"
ONE = FM + "# 하나\n\n본문 한 줄 가나다\n"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Host": "127.0.0.1:8080",
}

pytestmark = needs_db


@pytest.fixture
def db():
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        conn.autocommit = True
        yield conn


@pytest.fixture
def ws(tmp_path, db):
    def wipe():
        for table in ("kb_query_logs", "kb_ingest_runs", "kb_documents", "kb_events"):
            db.execute(f"DELETE FROM {table} WHERE project = %s", (PROJECT,))

    wipe()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "one.md").write_text(ONE, encoding="utf-8")
    service.ingest(DSN, PROJECT, str(tmp_path))
    yield tmp_path
    wipe()


@pytest.fixture
def event(ws):
    return service.save_event(
        DSN,
        {
            "project": PROJECT,
            "kind": "failure",
            "title": "제목",
            "summary": "요약 가나다",
            "occurred_at": "2026-08-31T09:00:00Z",
            "result": "failure",
        },
    )["id"]


@pytest.fixture
def client(ws):
    cfg = Config(
        database_url=DSN,
        host="127.0.0.1",
        port=8080,
        workspace=str(ws),
        bearer_token="",
        openai_api_key="",
    )
    with TestClient(api.create_app(cfg)) as c:
        yield c


def call(client: TestClient, name: str, arguments: dict) -> dict:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result.get("isError") is False, result
    return json.loads(result["content"][0]["text"])


def direct(fn, *args, **kwargs) -> dict:
    """Service 를 직접 불러 **같은 봉투**를 만든다. 매핑은 api.classify 하나뿐이다."""
    try:
        return api.envelope_ok(fn(*args, **kwargs))
    except Exception as exc:  # noqa: BLE001
        body, _status = api.envelope_error(*api.classify(exc))
        return body


def compare(client: TestClient, name: str, arguments: dict, fn, *args) -> dict:
    mine = direct(fn, *args)
    theirs = call(client, name, arguments)
    assert theirs == mine, f"{name}: 두 얼굴이 다르다"
    return theirs


# --- 성공 (D46) --------------------------------------------------------------


def test_kb_status_matches(client):
    body = compare(client, "kb_status", {"project": PROJECT}, service.kb_status, DSN, PROJECT)
    assert body["ok"] is True and body["data"]["documents"] == 1


def test_the_two_faces_agree_byte_for_byte(client):
    """D44 는 `같은 문자열` 이라고 했다. 파싱해서 같은 것으로는 부족하다 —

    한쪽이 들여쓰기를 바꾸면 그 문장이 조용히 거짓이 된다 (Grok 지적).
    """
    http = client.get(f"/v1/status?project={PROJECT}", headers=HEADERS)
    rpc = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "kb_status", "arguments": {"project": PROJECT}},
        },
        headers=HEADERS,
    )
    text = rpc.json()["result"]["content"][0]["text"]
    assert text == http.text


def test_event_stats_matches(client, event):
    compare(
        client,
        "event_stats",
        {"project": PROJECT},
        service.event_stats,
        DSN,
        PROJECT,
        None,
        None,
    )


def test_search_docs_matches(client):
    body = compare(
        client,
        "search_docs",
        {"project": PROJECT, "query": "가나다"},
        service.search_docs,
        DSN,
        {"project": PROJECT, "query": "가나다"},
        "",
    )
    assert body["data"]["results"], "검색이 비면 이 대조가 아무것도 보지 않는다"


def test_search_events_matches(client, event):
    body = compare(
        client,
        "search_events",
        {"project": PROJECT, "query": "가나다"},
        service.search_events,
        DSN,
        {"project": PROJECT, "query": "가나다"},
    )
    assert body["data"]["results"]


def test_get_event_matches(client, event):
    body = compare(
        client,
        "get_event",
        {"event_id": event, "project": PROJECT},
        service.get_event,
        DSN,
        event,
        PROJECT,
    )
    assert body["data"]["id"] == event


def test_get_file_matches(client, ws):
    body = compare(
        client,
        "get_file",
        {"project": PROJECT, "path": "docs/one.md"},
        service.get_file,
        DSN,
        PROJECT,
        "docs/one.md",
        None,
        str(ws),
    )
    assert body["data"]["text"] == ONE


def test_save_doc_matches(client, ws):
    body = compare(
        client,
        "save_doc",
        {"project": PROJECT, "path": "docs/one.md", "body": ONE},
        service.save_doc,
        DSN,
        {"project": PROJECT, "path": "docs/one.md", "body": ONE},
        str(ws),
    )
    assert body["data"]["proposal"]["diff"] == ""


def test_save_event_writes_one_row(client, db, ws):
    """id 가 매번 달라 봉투를 대조할 수 없다. **행이 하나 생기는지**로 본다 (D24: 멱등이 아니다)."""
    before = db.execute(
        "SELECT count(*) AS n FROM kb_events WHERE project = %s", (PROJECT,)
    ).fetchone()["n"]
    body = call(
        client,
        "save_event",
        {
            "project": PROJECT,
            "kind": "decision",
            "title": "MCP 로 남긴다",
            "summary": "요약",
            "occurred_at": "2026-09-02T09:00:00Z",
            "result": "success",
        },
    )
    assert body["ok"] is True and isinstance(body["data"]["id"], int)
    after = db.execute(
        "SELECT count(*) AS n FROM kb_events WHERE project = %s", (PROJECT,)
    ).fetchone()["n"]
    assert after == before + 1

    # 저장한 것을 MCP 로 다시 읽어도 같은 행이다 — 두 도구가 같은 원장을 본다.
    got = call(client, "get_event", {"event_id": body["data"]["id"], "project": PROJECT})
    assert got["data"]["title"] == "MCP 로 남긴다"
    assert got["data"]["source"] == "agent", "source 를 비우면 Service 가 기본값을 넣는다 (D25)"


# --- 오류 (D46: 그 도구가 낼 수 있는 코드를 전부) -----------------------------


def test_not_found_matches(client, event):
    for name, arguments, fn, args in (
        (
            "get_event",
            {"event_id": event, "project": PROJECT + "_other"},
            service.get_event,
            (DSN, event, PROJECT + "_other"),
        ),
        (
            "get_file",
            {"project": PROJECT, "path": "docs/none.md"},
            service.get_file,
            (DSN, PROJECT, "docs/none.md", None, "."),
        ),
    ):
        body = compare(client, name, arguments, fn, *args)
        assert body["error"]["code"] == "NOT_FOUND"


def test_conflict_matches(client, ws):
    body = compare(
        client,
        "save_doc",
        {
            "project": PROJECT,
            "path": "docs/one.md",
            "body": ONE,
            "base_hash": "sha256:" + "0" * 64,
        },
        service.save_doc,
        DSN,
        {
            "project": PROJECT,
            "path": "docs/one.md",
            "body": ONE,
            "base_hash": "sha256:" + "0" * 64,
        },
        str(ws),
    )
    assert body["error"] == {"code": "CONFLICT", "message": service.BASE_HASH_MESSAGE}


def test_validation_matches(client):
    for name, arguments, fn, args in (
        (
            "search_docs",
            {"project": PROJECT},
            service.search_docs,
            (DSN, {"project": PROJECT}, ""),
        ),
        ("kb_status", {"project": "has/slash"}, service.kb_status, (DSN, "has/slash")),
        (
            "get_file",
            {"project": PROJECT, "path": "docs/one.md", "offset": -1},
            service.get_file,
            (DSN, PROJECT, "docs/one.md", -1, "."),
        ),
    ):
        body = compare(client, name, arguments, fn, *args)
        assert body["error"]["code"] == "VALIDATION"


def test_the_indexed_hash_is_what_save_doc_compares(client, ws):
    """MCP 로 들어온 제안도 **지금 파일**과 대조된다 (D41). 얼굴이 달라도 규칙은 하나다."""
    digest = ingest_rules.content_hash(ONE)
    body = call(
        client,
        "save_doc",
        {
            "project": PROJECT,
            "path": "docs/one.md",
            "body": ONE + "덧붙임\n",
            "base_hash": f"sha256:{digest}",
        },
    )
    assert body["ok"] is True
    assert body["data"]["proposal"]["diff"].startswith("--- a/docs/one.md")
