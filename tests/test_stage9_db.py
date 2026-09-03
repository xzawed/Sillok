"""9단계 질의 원장이 실제로 남는가 (D48–D52). **D22 의 `--profile test` 에서 돈다.**

`plan.md` §9 의 마지막 완료 조건이 여기 있다 — *검색 0건이 `kb_query_logs` 에
`hit_count=0` 으로 남는다*. 그 한 줄이 이 파일의 첫 검사다.

행은 **실제 검색으로** 만든다. 손으로 INSERT 하면 구현이 넣지 않는 모양으로 통과한다
(`test_stage7_db.py` 가 허용 목록에서 같은 이유로 그렇게 한다).
"""

from __future__ import annotations

import json

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from sillok import api, service
from sillok.config import Config

from dbcheck import DSN, needs_db

PROJECT = "t_step9"
FM = "---\ntitle: T\ndoc_type: other\nstatus: current\nmodule: null\n---\n\n"
# 한 문서에 절이 둘이라 청크가 둘이다 — 문서당 상한 2(D33)를 실제로 채운다.
TWO_CHUNKS = FM + "# 하나\n\n검색 낱말 가나다\n\n## 둘째 절\n\n검색 낱말 가나다 또\n"
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
    (tmp_path / "docs" / "one.md").write_text(TWO_CHUNKS, encoding="utf-8")
    service.ingest(DSN, PROJECT, str(tmp_path))
    yield tmp_path
    wipe()


def rows(db) -> list[dict]:
    return db.execute(
        "SELECT * FROM kb_query_logs WHERE project = %s ORDER BY id", (PROJECT,)
    ).fetchall()


def only(db) -> dict:
    got = rows(db)
    assert len(got) == 1, f"행이 하나여야 한다: {got}"
    return got[0]


# --- §9 의 마지막 완료 조건 ---------------------------------------------------


def test_zero_hit_query_leaves_a_row(ws, db):
    """*검색 0건이 `kb_query_logs` 에 `hit_count=0` 으로 남는다* — plan.md §9."""
    out = service.search_docs(DSN, {"project": PROJECT, "query": "이런낱말은없다xyz"})
    assert out == {"results": []}

    row = only(db)
    assert row["hit_count"] == 0
    assert row["tool"] == "search_docs"
    assert row["hit_paths"] == []


def test_zero_hit_query_shows_up_in_kb_status(ws, db):
    """`zero_hit_queries` 가 이제 자란다. 9단계 전까지 언제나 0 이었다."""
    before = service.kb_status(DSN, PROJECT)["zero_hit_queries"]
    service.search_docs(DSN, {"project": PROJECT, "query": "이런낱말은없다xyz"})
    after = service.kb_status(DSN, PROJECT)["zero_hit_queries"]
    assert after == before + 1


def test_kb_status_does_not_write_its_own_row(ws, db):
    """D48. 현황을 묻는 질의가 자기가 보고할 수를 늘리면 그 지표가 자기 자신을 센다."""
    service.kb_status(DSN, PROJECT)
    service.kb_status(DSN, PROJECT)
    assert rows(db) == []


# --- D49 여덟 컬럼 -----------------------------------------------------------


def test_hit_paths_keeps_duplicates_and_matches_hit_count(ws, db):
    """문서당 상한이 2라 같은 path 가 두 번 들어온다 — 접지 않는다 (D49)."""
    out = service.search_docs(DSN, {"project": PROJECT, "query": "검색 낱말 가나다"})
    assert len(out["results"]) == 2, out

    row = only(db)
    assert row["hit_count"] == 2
    assert row["hit_paths"] == [r["path"] for r in out["results"]]
    assert row["hit_paths"] == ["docs/one.md", "docs/one.md"]


def test_filters_hold_only_what_reached_sql(ws, db):
    """`project`·`query`·`top_k` 는 넣지 않는다. 값 없는 필터도 키가 없다 (D49)."""
    service.search_docs(
        DSN,
        {
            "project": PROJECT,
            "query": "가나다",
            "top_k": 5,
            "status": "current",
            "module": None,
        },
    )
    row = only(db)
    assert row["filters"] == {"status": "current"}
    assert row["query"] == "가나다"


def test_event_filters_are_isoformatted(ws, db):
    """시각은 `parse_timestamp` 를 통과한 UTC 의 `isoformat()` 이다 (D49)."""
    service.search_events(
        DSN, {"project": PROJECT, "kind": "failure", "since": "2026-01-01T00:00:00Z"}
    )
    row = only(db)
    assert row["filters"] == {"kind": "failure", "since": "2026-01-01T00:00:00+00:00"}


def test_events_leave_null_hit_paths(ws, db):
    """이벤트 히트는 경로가 아니라 id 다 — 한 `text[]` 에 두 종류를 섞지 않는다 (D49)."""
    out = service.search_events(DSN, {"project": PROJECT})
    row = only(db)
    assert row["tool"] == "search_events"
    assert row["hit_paths"] is None
    assert row["hit_count"] == len(out["results"])


def test_query_is_null_when_events_are_filtered_without_one(ws, db):
    """`search_events` 에서 query 는 선택이다 (D33 §6). 없으면 NULL 이다 (D49)."""
    service.search_events(DSN, {"project": PROJECT})
    assert only(db)["query"] is None


def test_latency_is_a_non_negative_int(ws, db):
    service.search_docs(DSN, {"project": PROJECT, "query": "가나다"})
    row = only(db)
    assert isinstance(row["latency_ms"], int)
    assert row["latency_ms"] >= 0


# --- D49 `client` ------------------------------------------------------------


def test_client_defaults_to_http(ws, db):
    service.search_docs(DSN, {"project": PROJECT, "query": "가나다"})
    assert only(db)["client"] == "http"


def test_mcp_face_records_itself(ws, db):
    """얼굴이 그대로 남는다 (D49). 같은 함수를 타지만 `client` 만 다르다."""
    cfg = Config(
        database_url=DSN,
        host="127.0.0.1",
        port=8080,
        workspace=str(ws),
        bearer_token="",
        openai_api_key="",
    )
    with TestClient(api.create_app(cfg)) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "search_docs",
                    "arguments": {"project": PROJECT, "query": "가나다"},
                },
            },
            headers=HEADERS,
        )
    assert response.status_code == 200, response.text
    body = json.loads(response.json()["result"]["content"][0]["text"])
    assert body["ok"] is True

    row = only(db)
    assert row["client"] == "mcp"
    assert row["tool"] == "search_docs"


def test_the_two_faces_leave_the_same_filters(ws, db):
    """D46 은 봉투를 대조한다. 원장도 갈라지면 안 된다 —
    MCP 얼굴은 부르지 않은 인자를 `None` 으로 채워 넘기는데(D42) 그것이 키를 만들면 안 된다.
    """
    cfg = Config(
        database_url=DSN,
        host="127.0.0.1",
        port=8080,
        workspace=str(ws),
        bearer_token="",
        openai_api_key="",
    )
    with TestClient(api.create_app(cfg)) as client:
        client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "search_docs",
                    "arguments": {"project": PROJECT, "query": "가나다"},
                },
            },
            headers=HEADERS,
        )
    service.search_docs(DSN, {"project": PROJECT, "query": "가나다"})

    got = rows(db)
    assert len(got) == 2
    assert got[0]["filters"] == got[1]["filters"] == {}
    assert got[0]["client"] == "mcp" and got[1]["client"] == "http"


# --- D50 남기지 않는 경우와 고장 -------------------------------------------


def test_rejected_requests_leave_nothing(ws, db):
    """`VALIDATION` 은 `project` 가 정해지기 전이라 적을 자리가 없다 (D50)."""
    with pytest.raises(service.ValidationFailed):
        service.search_docs(DSN, {"project": PROJECT})  # query 필수
    with pytest.raises(service.ValidationFailed):
        service.search_events(DSN, {"project": PROJECT, "top_k": 99})
    assert rows(db) == []


def test_a_broken_log_does_not_break_the_search(ws, db, monkeypatch):
    """원장이 자기가 기록하는 것을 죽이면 안 된다 (D50). **고장을 주입해 확인한다.**"""

    def boom(_value):
        raise TypeError("주입한 고장")

    monkeypatch.setattr(service.psycopg.types.json, "Jsonb", boom)
    out = service.search_docs(DSN, {"project": PROJECT, "query": "가나다"})
    assert len(out["results"]) == 2  # 검색은 그대로 답한다
    assert rows(db) == []  # 원장에는 남지 않았다


# --- D51 인덱스 --------------------------------------------------------------


def test_005_created_the_index(db):
    """`kb_status` 가 매번 `project` 로 좁혀 세는데 PK 말고 인덱스가 없었다 (D51)."""
    found = db.execute(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'kb_query_logs'"
        " AND indexname = 'kb_query_logs_project_time'"
    ).fetchone()
    assert found is not None
    assert "project" in found["indexdef"]


def test_a_broken_filters_builder_does_not_break_the_search(ws, db, monkeypatch):
    """호출부의 구멍을 잠근다 — 값 만들기가 `try` 밖이면 검색이 500 이 된다 (D50)."""

    def boom(_params):
        raise RuntimeError("주입한 고장")

    monkeypatch.setattr(service, "_log_filters", boom)
    out = service.search_docs(DSN, {"project": PROJECT, "query": "가나다"})
    assert len(out["results"]) == 2
    assert rows(db) == []


# --- D58 천장 (DB 경로) -------------------------------------------------------


def _event(db, module: str, title: str = "제목") -> None:
    service.save_event(
        DSN,
        {
            "project": PROJECT,
            "module": module,
            "kind": "failure",
            "title": title,
            "summary": "요약 가나다",
            "occurred_at": "2026-01-01T00:00:00Z",
            "result": "failure",
        },
    )


def test_by_module_is_capped_and_says_how_many_it_dropped(ws, db):
    """열린 축이라 천장이 필요하다 (D58). `by_module_omitted` 가 그 천장을 읽게 한다."""
    for i in range(15):
        _event(db, f"m{i:02d}")

    stats = service.event_stats(DSN, PROJECT)
    assert len(stats["by_module"]) == service.BY_MODULE_LIMIT
    assert stats["by_module_omitted"] == 15 - service.BY_MODULE_LIMIT
    assert stats["total"] == 15


def test_by_module_omitted_is_zero_under_the_cap(ws, db):
    """`0` 이면 `sum(by_module) <= total` 의 차이가 D23 의 뜻 그대로다."""
    _event(db, "auth")
    _event(db, "auth")
    _event(db, "billing")

    stats = service.event_stats(DSN, PROJECT)
    assert stats["by_module"] == {"auth": 2, "billing": 1}
    assert stats["by_module_omitted"] == 0


def test_module_less_rows_stay_out_of_by_module(ws, db):
    """D23 그대로다 — NULL 은 키가 되지 않고 `total` 에는 남는다. 천장과 섞이지 않는다."""
    _event(db, "auth")
    service.save_event(
        DSN,
        {
            "project": PROJECT,
            "kind": "failure",
            "title": "모듈 없음",
            "summary": "요약",
            "occurred_at": "2026-01-01T00:00:00Z",
            "result": "failure",
        },
    )
    stats = service.event_stats(DSN, PROJECT)
    assert stats["by_module"] == {"auth": 1}
    assert stats["by_module_omitted"] == 0
    assert stats["total"] == 2


def test_search_events_clips_summary_with_the_same_function(ws, db):
    """`excerpt` 와 **같은 함수**를 쓴다 — 799자 + `…` 로 합 800자다 (D33 §8 · D58)."""
    long_summary = "가" * 1500
    service.save_event(
        DSN,
        {
            "project": PROJECT,
            "kind": "failure",
            "title": "긴 요약",
            "summary": long_summary,
            "occurred_at": "2026-01-01T00:00:00Z",
            "result": "failure",
        },
    )
    found = service.search_events(DSN, {"project": PROJECT})["results"]
    assert len(found) == 1
    assert len(found[0]["summary"]) == 800
    assert found[0]["summary"].endswith("…")

    # 원문은 get_event 가 그대로 준다 (D39). 자르는 것은 검색뿐이다.
    whole = service.get_event(DSN, found[0]["id"], PROJECT)
    assert whole["summary"] == long_summary


# --- D60 `repo` 불변식 --------------------------------------------------------


def test_repo_is_always_empty(ws, db):
    """v1 은 repo 가 하나뿐이므로 `''` 로 고정한다 (D60).

    비워 두는 것이 **결정**이지 미정이 아니다. 다른 값이 들어오는 날은
    기존 행 이관이 따라오는 마이그레이션이고, 그때 이 검사가 먼저 운다.
    """
    rows = db.execute(
        "SELECT DISTINCT repo FROM kb_documents WHERE project = %s", (PROJECT,)
    ).fetchall()
    assert [r["repo"] for r in rows] == [""], rows
