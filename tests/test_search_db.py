"""6단계 검색의 DB 경로 (D33 · D34).

키가 없으므로 벡터 팔은 언제나 비어 있다 — 그것이 D2 가 정한 정상 상태다.
그 상태에서도 병합·상한·정렬·`excerpt` 는 전부 관측된다.
"""

from __future__ import annotations

import psycopg
import pytest
from psycopg.rows import dict_row

from sillok import search, service

from dbcheck import DSN, needs_db

PROJECT = "t_step6"
FM = "---\ntitle: T\ndoc_type: other\nstatus: current\nmodule: null\n---\n\n"

pytestmark = needs_db


@pytest.fixture
def db():
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        conn.autocommit = True
        yield conn


@pytest.fixture
def clean(db):
    def wipe():
        for table in ("kb_ingest_runs", "kb_documents", "kb_events"):
            db.execute(f"DELETE FROM {table} WHERE project = %s", (PROJECT,))

    wipe()
    yield PROJECT
    wipe()


@pytest.fixture
def indexed(tmp_path, clean):
    """작은 workspace 를 만들어 실제 ingest 로 색인한다."""

    def write(rel, text):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    write("docs/alpha.md", FM + "# 알파\n\n검색 낱말 하나\n")
    write("docs/beta.md", FM + "# 베타\n\n검색 낱말 둘\n\n## 다른 절\n\n검색 낱말 셋\n")
    write("adr/gamma.md", FM + "# 감마\n\n관계없는 본문\n")
    service.ingest(DSN, PROJECT, str(tmp_path))
    return tmp_path


def docs(body):
    return service.search_docs(DSN, {"project": PROJECT, **body})["results"]


def events(body):
    return service.search_events(DSN, {"project": PROJECT, **body})["results"]


# --- 요청 검증 (D33 §6) ------------------------------------------------------


def test_docs_query_is_required(clean):
    """문서 검색에는 질의 말고 신호가 없다 — 필터만으로는 "관련 문서 전부" 가 된다."""
    for bad in (None, "", "   "):
        with pytest.raises(service.ValidationFailed, match="query"):
            service.search_docs(DSN, {"project": PROJECT, "query": bad})


def test_events_query_is_optional(clean, db):
    """이벤트는 필터만으로도 완결된 요청이 된다 — "지난 달 auth 의 실패"."""
    _add_event(db, "락 경쟁", "요약")
    got = events({})
    assert len(got) == 1
    # 순위가 없는 것이지 0점이 아니다 (D23 의 avg_resolution_seconds 선례).
    assert got[0]["score"] is None


def test_top_k_out_of_range_is_rejected_not_clamped(indexed):
    """조용히 12 로 접으면 호출자가 자기 요청을 오해한다 (D25 선례)."""
    for bad in (0, -1, 13, 100):
        with pytest.raises(service.ValidationFailed, match="top_k"):
            docs({"query": "검색", "top_k": bad})
    assert docs({"query": "검색", "top_k": 12})


# --- 병합과 점수 (D33 §2·§5) -------------------------------------------------


def test_the_top_score_is_one_over_k_plus_one(indexed):
    """목록이 하나뿐인 오늘, 결과가 있는 모든 질의의 1위 점수가 같다.

    임계값을 걸려는 소비자는 즉시 그것이 불가능함을 본다 — 정규화의 정반대다.
    """
    got = docs({"query": "검색"})
    assert got[0]["score"] == round(1.0 / (search.RRF_K + 1), search.SCORE_DIGITS)


def test_empty_result_is_not_an_error(indexed):
    """빈 결과는 200 에 빈 배열이다 (D21). 모델이 채울 문장을 넣지 않는다."""
    assert docs({"query": "이런낱말은없다xyz"}) == []


def test_a_query_with_no_lexemes_returns_nothing(indexed):
    """그 갈래를 "질의 없음" 으로 접으면 필터 집합이 검색 결과로 나간다."""
    assert docs({"query": "???"}) == []


# --- 필터 (D33 §1) ----------------------------------------------------------


def test_filters_are_applied_in_the_arm_not_after_the_merge(indexed):
    """병합 뒤에 거르면 걸러질 행이 후보 칸을 먹는다."""
    assert docs({"query": "검색"})
    assert docs({"query": "검색", "doc_type": "adr"}) == []
    assert docs({"query": "검색", "status": "stale"}) == []


def test_a_null_filter_field_does_not_filter(indexed):
    assert len(docs({"query": "검색", "module": None})) == len(docs({"query": "검색"}))


# --- 문서당 상한 (D33 §6) ----------------------------------------------------


def test_one_document_takes_at_most_two_rows(indexed, tmp_path):
    """상한이 없으면 한 파일이 칸을 다 가져간다."""
    body = "\n\n".join(f"## 절 {i}\n\n검색 낱말 반복 {i}" for i in range(5))
    (tmp_path / "docs" / "many.md").write_text(FM + "# 많음\n\n" + body + "\n", encoding="utf-8")
    service.ingest(DSN, PROJECT, str(tmp_path))

    got = docs({"query": "반복", "top_k": 8})
    assert len(got) == 2
    assert {r["path"] for r in got} == {"docs/many.md"}


def test_the_cap_does_not_refill(indexed, tmp_path):
    """여덟을 요청해 적게 오는 것이 정상이다 — 메우면 상한이 도는지 아무도 모른다."""
    body = "\n\n".join(f"## 절 {i}\n\n유일낱말 {i}" for i in range(6))
    (tmp_path / "docs" / "many.md").write_text(FM + "# 많음\n\n" + body + "\n", encoding="utf-8")
    service.ingest(DSN, PROJECT, str(tmp_path))
    assert len(docs({"query": "유일낱말", "top_k": 8})) == 2


# --- 순서 (D33 §7) ----------------------------------------------------------


def test_the_same_query_returns_the_same_rows(indexed):
    """순서가 실행마다 달라지면 9단계의 원장이 무엇의 기록도 아니다."""
    first = [(r["path"], r["heading_path"]) for r in docs({"query": "검색"})]
    for _ in range(3):
        assert [(r["path"], r["heading_path"]) for r in docs({"query": "검색"})] == first


def test_results_are_sorted_by_score_then_key(indexed):
    got = docs({"query": "검색", "top_k": 12})
    keys = [(-r["score"], r["path"]) for r in got]
    assert keys == sorted(keys)


# --- excerpt (D33 §8) -------------------------------------------------------


def test_excerpt_shows_why_the_chunk_matched(indexed, tmp_path):
    """`content` 에만 걸면 제목으로 매칭된 청크가 강조 없는 앞머리를 돌려준다."""
    (tmp_path / "docs" / "title_only.md").write_text(
        FM + "# 제목에만있는낱말\n\n본문에는 그 말이 없다\n", encoding="utf-8"
    )
    service.ingest(DSN, PROJECT, str(tmp_path))
    got = docs({"query": "제목에만있는낱말"})
    assert got
    assert "제목에만있는낱말" in got[0]["excerpt"]


def test_excerpt_is_clipped_with_a_mark(indexed, tmp_path):
    (tmp_path / "docs" / "long.md").write_text(
        FM + "# 긺\n\n" + ("길다 " * 900) + "긴낱말표식\n", encoding="utf-8"
    )
    service.ingest(DSN, PROJECT, str(tmp_path))
    for row in docs({"query": "길다", "top_k": 12}):
        assert len(row["excerpt"]) <= search.EXCERPT_MAX


def test_commit_sha_is_empty_and_status_comes_from_the_document(indexed):
    got = docs({"query": "검색"})
    # D30: v1 내내 빈 문자열이다. 필드는 계약이라 지우지 않는다.
    assert all(r["commit_sha"] == "" for r in got)
    assert all(r["status"] == "current" for r in got)


# --- 이벤트 (D34) -----------------------------------------------------------


def _add_event(db, title, summary, root_cause=None, resolution=None, kind="failure"):
    return db.execute(
        "INSERT INTO kb_events (project, kind, title, summary, root_cause, resolution,"
        " result, occurred_at) VALUES (%s, %s, %s, %s, %s, %s, 'failure', now()) RETURNING id",
        (PROJECT, kind, title, summary, root_cause, resolution),
    ).fetchone()["id"]


def test_events_are_found_by_all_four_fields(clean, db):
    """D34 §2. `root_cause`·`resolution` 을 빼면 "왜 깨졌나" 를 묻는 질의를 놓친다."""
    _add_event(db, "제목낱말", "요약낱말", "원인낱말", "해결낱말")
    for word in ("제목낱말", "요약낱말", "원인낱말", "해결낱말"):
        assert len(events({"query": word})) == 1, f"{word} 로 못 찾았다"


def test_an_event_with_a_null_field_is_still_searchable(clean, db):
    """coalesce 를 하나만 빼도 그 행이 검색에서 통째로 사라진다. 오류는 없다."""
    _add_event(db, "널제목낱말", "요약", root_cause=None, resolution=None)
    assert len(events({"query": "널제목낱말"})) == 1


def test_events_with_a_value_but_no_lexemes_return_nothing(clean, db):
    """`"???"` 를 친 사람이 최근 이벤트를 검색 결과로 받으면 안 된다."""
    _add_event(db, "무엇", "요약")
    assert events({"query": "???"}) == []
    # 반대로 질의가 없으면 필터 집합이 결과다.
    assert len(events({})) == 1


def test_events_without_a_query_are_newest_first(clean, db):
    first = _add_event(db, "먼저", "요약")
    second = _add_event(db, "나중", "요약")
    got = events({})
    assert [r["id"] for r in got] == [second, first]


def test_event_filters_come_first(clean, db):
    _add_event(db, "필터낱말", "요약", kind="failure")
    _add_event(db, "필터낱말", "요약", kind="decision")
    assert len(events({"query": "필터낱말"})) == 2
    assert len(events({"query": "필터낱말", "kind": "decision"})) == 1


def test_event_score_is_the_single_list_rrf(clean, db):
    _add_event(db, "점수낱말", "요약")
    got = events({"query": "점수낱말"})
    assert got[0]["score"] == round(1.0 / (search.RRF_K + 1), search.SCORE_DIGITS)


def test_events_have_no_vector_arm(clean, db):
    """v1 은 이벤트를 임베딩하지 않는다 (D34 §5).

    전부 NULL 인 컬럼에 거리를 걸면 정렬이 물리 순서가 되고 오류는 없다.
    """
    _add_event(db, "벡터없음", "요약")
    left = db.execute(
        "SELECT count(*) AS n FROM kb_events WHERE project = %s AND embedding IS NOT NULL",
        (PROJECT,),
    ).fetchone()["n"]
    assert left == 0


def test_the_event_tsv_expression_matches_the_module_constant(clean, db):
    """D34 §2. 파일과 DB 가 갈라져도 러너는 성공을 보고한다 (ADD COLUMN IF NOT EXISTS).

    상수가 아무 데도 쓰이지 않으면 그것은 죽은 코드이고, 갈라짐을 아무도 못 본다.
    이 검사가 그 상수를 살아 있게 만든다 — D31 이 EMBED_INPUT_SQL 에 한 것과 같다.
    """
    import re

    actual = db.execute(
        """
        SELECT pg_get_expr(d.adbin, d.adrelid) AS e
        FROM pg_attrdef d JOIN pg_attribute a
          ON a.attrelid = d.adrelid AND a.attnum = d.adnum
        WHERE d.adrelid = 'kb_events'::regclass AND a.attname = 'tsv'
        """
    ).fetchone()["e"]

    fields = lambda s: re.findall(r"coalesce\(\s*(\w+)", s, re.IGNORECASE)  # noqa: E731
    assert fields(actual) == fields(service.EVENT_TSV_INPUT_SQL)
    assert fields(actual) == ["title", "summary", "root_cause", "resolution"]
    assert f"'{service.TS_CONFIG}'" in actual


# --- HTTP 얼굴 --------------------------------------------------------------


def _client():
    from fastapi.testclient import TestClient

    from sillok import api
    from sillok.config import Config

    return TestClient(
        api.create_app(
            Config(
                database_url=DSN,
                host="127.0.0.1",
                port=8080,
                workspace=".",
                bearer_token="",
                openai_api_key="",
            )
        ),
        raise_server_exceptions=False,
    )


def test_http_search_docs_returns_the_envelope(indexed):
    res = _client().post("/v1/search/docs", json={"project": PROJECT, "query": "검색"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["results"]
    assert set(body["data"]["results"][0]) == {
        "path", "heading_path", "excerpt", "commit_sha", "status", "score",
    }


def test_http_search_docs_rejects_a_missing_query(clean):
    res = _client().post("/v1/search/docs", json={"project": PROJECT})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION"


def test_http_search_events_returns_the_envelope(clean, db):
    _add_event(db, "HTTP 이벤트", "요약")
    res = _client().post("/v1/search/events", json={"project": PROJECT, "query": "이벤트"})
    assert res.status_code == 200
    body = res.json()
    assert set(body["data"]["results"][0]) == {
        "id", "title", "summary", "kind", "result", "module", "occurred_at", "score",
    }


def test_http_empty_result_is_two_hundred_with_an_empty_array(indexed):
    """빈 결과는 오류가 아니다 (D21). 모델이 채울 문장을 API 가 넣지 않는다."""
    res = _client().post("/v1/search/docs", json={"project": PROJECT, "query": "없는낱말zzz"})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "data": {"results": []}}
