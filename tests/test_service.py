"""4단계 Service 함수 검증 (D23·D24·D25).

검증 규칙은 명세에 답이 있는 순수 로직이라 여기부터 쓴다 (AGENTS 테스트 방식).
DB 가 필요한 검사는 아래 `needs_db` 묶음에 있다.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import psycopg
import pytest

from sillok import service

from dbcheck import DSN, needs_db

VALID = {
    "project": "t_step4",
    "kind": "failure",
    "title": "배포 후 커넥션 풀 고갈",
    "summary": "요약",
    "occurred_at": "2026-08-31T09:00:00Z",
    "result": "failure",
}


def body(**overrides):
    return {**VALID, **overrides}


# --- D25 검증 (DB 불필요) --------------------------------------------------


@pytest.mark.parametrize("field", service.REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(field):
    """D10: 관대하게 채우지 않는다."""
    payload = body()
    del payload[field]
    with pytest.raises(service.ValidationFailed, match=field):
        service.build_event(payload)


@pytest.mark.parametrize("field", service.REQUIRED_FIELDS)
def test_empty_required_field_is_rejected(field):
    with pytest.raises(service.ValidationFailed, match=field):
        service.build_event(body(**{field: ""}))


@pytest.mark.parametrize(
    "raw",
    [
        "2026-08-31T09:00:00",  # 오프셋 없음
        "2026-08-31",  # 날짜만
        "31/08/2026",  # ISO 아님
        12345,  # 문자열 아님
    ],
)
def test_timestamp_without_offset_is_rejected(raw):
    """드라이버가 접속 TimeZone 으로 해석하게 두면 Compose 에서 우연히 UTC 가 된다."""
    with pytest.raises(service.ValidationFailed):
        service.build_event(body(occurred_at=raw))


@pytest.mark.parametrize("raw", ["2026-08-31T09:00:00Z", "2026-08-31T18:00:00+09:00"])
def test_timestamp_with_offset_is_accepted(raw):
    event = service.build_event(body(occurred_at=raw))
    assert event.occurred_at.tzinfo is timezone.utc


def test_resolved_before_occurred_is_rejected():
    with pytest.raises(service.ValidationFailed, match="resolved_at"):
        service.build_event(body(resolved_at="2026-08-31T08:00:00Z"))


def test_resolved_equal_to_occurred_is_allowed():
    event = service.build_event(body(resolved_at=VALID["occurred_at"]))
    assert event.resolved_at == event.occurred_at


@pytest.mark.parametrize(
    "project",
    ["", "   ", "a" * 65, "with space", "with/slash", "with\\backslash", "with\x00nul"],
)
def test_bad_project_is_rejected(project):
    with pytest.raises(service.ValidationFailed, match="project"):
        service.normalize_project(project)


def test_project_is_stripped_but_not_casefolded():
    """D25: 슬러그 알파벳을 발명하지 않는다. Sillok 과 sillok 은 다른 프로젝트다."""
    assert service.normalize_project("  Sillok  ") == "Sillok"


def test_title_and_summary_caps():
    with pytest.raises(service.ValidationFailed, match="title"):
        service.build_event(body(title="a" * (service.TITLE_MAX + 1)))
    with pytest.raises(service.ValidationFailed, match="summary"):
        service.build_event(body(summary="a" * (service.SUMMARY_MAX + 1)))


@pytest.mark.parametrize(
    ("field", "bad"),
    [("kind", "typo"), ("result", "typo"), ("severity", "typo"), ("source", "typo")],
)
def test_enum_values_are_checked_in_the_service(field, bad):
    """DDL 에 CHECK 를 두지 않는다 (D25) — 그래서 여기서 걸려야 한다."""
    with pytest.raises(service.ValidationFailed, match=field):
        service.build_event(body(**{field: bad}))


def test_source_defaults_to_agent():
    assert service.build_event(body()).source == "agent"


# --- DB 필요 ---------------------------------------------------------------


@pytest.fixture
def db():
    """단언·정리용 연결.

    **격리 장치가 아니다.** `save_event` 는 자기 연결에서 커밋하므로 여기서 롤백해도
    그 행은 남는다. 실제 정리는 아래 `clean_project` 의 커밋된 DELETE 다.
    """
    with psycopg.connect(DSN) as conn:
        try:
            yield conn
        finally:
            conn.rollback()


def _wipe(db, project):
    # kb_documents 는 청크를 ON DELETE CASCADE 로 끌고 간다.
    for table in ("kb_query_logs", "kb_events", "kb_ingest_runs", "kb_documents"):
        db.execute(f"DELETE FROM {table} WHERE project = %s", (project,))
    db.commit()


@pytest.fixture
def clean_project(db):
    """이 파일이 쓰는 project 의 잔여 행을 지운 상태로 시작하고, 끝나면 지운다."""
    _wipe(db, "t_step4")
    yield "t_step4"
    _wipe(db, "t_step4")


@needs_db
def test_save_event_returns_id(clean_project):
    assert service.save_event(DSN, body())["id"] > 0


@needs_db
def test_save_event_is_not_idempotent(clean_project, db):
    """D24: 재시도는 행을 하나 더 넣는다. 이것이 받아들인 대가다."""
    first = service.save_event(DSN, body())
    second = service.save_event(DSN, body())
    assert first["id"] != second["id"]
    n = db.execute(
        "SELECT count(*) FROM kb_events WHERE project = %s", (clean_project,)
    ).fetchone()[0]
    assert n == 2


@needs_db
def test_stats_groups_repeat_causes_by_module(clean_project):
    """D23 의 핵심. module 없이 묶으면 auth 와 billing 이 한 줄로 합쳐진다."""
    for module in ("auth", "auth", "billing", "billing"):
        service.save_event(DSN, body(module=module, root_cause="pool exhausted"))

    stats = service.event_stats(DSN, clean_project)
    causes = {(c["module"], c["root_cause"]): c["count"] for c in stats["repeat_causes"]}
    assert causes == {("auth", "pool exhausted"): 2, ("billing", "pool exhausted"): 2}


@needs_db
def test_repeat_causes_order_is_total(clean_project):
    """D23: count 와 root_cause 가 같아도 순서가 흔들리면 LIMIT 이 자르는 대상이 달라진다.

    module 까지 정렬 키에 넣어야 순서가 완전해진다. NULL module 은 마지막이다.
    """
    # NULL 그룹을 가운데 넣는다. 마지막에 넣으면 NULLS LAST 가 삽입 순서와 구분되지 않아
    # 그 절반이 검사되지 않는다.
    for module in ("zeta", "zeta", None, None, "alpha", "alpha"):
        service.save_event(DSN, body(module=module, root_cause="pool exhausted"))

    causes = service.event_stats(DSN, clean_project)["repeat_causes"]
    assert [c["module"] for c in causes] == ["alpha", "zeta", None]


@needs_db
def test_repeat_causes_needs_two(clean_project):
    """Skill 의 '2회 이상' 이 임계값이다."""
    service.save_event(DSN, body(module="auth", root_cause="once only"))
    assert service.event_stats(DSN, clean_project)["repeat_causes"] == []


@needs_db
def test_repeat_causes_skips_null_root_cause(clean_project):
    for _ in range(3):
        service.save_event(DSN, body(module="auth"))
    assert service.event_stats(DSN, clean_project)["repeat_causes"] == []


@needs_db
def test_by_module_omits_null_but_total_keeps_it(clean_project):
    """JSON 키는 null 일 수 없다. 그 행은 total 에 남는다 (D23)."""
    service.save_event(DSN, body(module="auth"))
    service.save_event(DSN, body())  # module 없음
    stats = service.event_stats(DSN, clean_project)
    assert stats["by_module"] == {"auth": 1}
    assert stats["total"] == 2
    assert sum(stats["by_module"].values()) < stats["total"]


@needs_db
def test_avg_resolution_is_null_when_nothing_resolved(clean_project):
    """전부 미해결이면 0 이 아니라 null 이다 — 0 이면 '즉시 해결' 로 읽힌다."""
    service.save_event(DSN, body())
    assert service.event_stats(DSN, clean_project)["avg_resolution_seconds"] is None


@needs_db
def test_avg_resolution_excludes_unresolved_rows(clean_project):
    service.save_event(DSN, body(resolved_at="2026-08-31T10:00:00Z"))  # 3600초
    service.save_event(DSN, body())  # 미해결 — 평균을 끌어내리면 안 된다
    assert service.event_stats(DSN, clean_project)["avg_resolution_seconds"] == 3600


@needs_db
def test_stats_filters_by_module_and_since(clean_project):
    service.save_event(DSN, body(module="auth", occurred_at="2026-01-01T00:00:00Z"))
    service.save_event(DSN, body(module="billing", occurred_at="2026-12-01T00:00:00Z"))

    assert service.event_stats(DSN, clean_project, module="auth")["total"] == 1
    since = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert service.event_stats(DSN, clean_project, since=since)["total"] == 1


# --- event_stats 는 벡터를 쓰지 않는다 (D23) -------------------------------
#
# CLAUDE.md `절대 금지` 와 AGENTS.md `통계는 SQL 집계` 가 같은 것을 말하고
# event_stats 의 docstring 도 그렇게 적는데, 그것을 무는 검사가 없었다.
#
# `inspect.getsource(event_stats)` 로 보지 않는다. 이 저장소의 선례는
# test_hnsw_is_absent_in_v1 의 `이름이 아니라 접근 방법(pg_am)으로 본다` 이고,
# 벡터 금지의 기전은 소스 텍스트가 아니라 **Postgres 에 가는 질의문**이다.
# 소스로 보면 셋을 놓친다: _event_filters 가 만드는 조각, 본문이
# `return _stats(...)` 로 바뀌는 순간, 그리고 연산자를 변수로 이어 붙이는 경우.

VECTOR_OPERATORS = ("<=>", "<->", "<#>", "::vector")


def vector_mechanism_in(sql: str) -> str | None:
    """질의문이 쓰는 벡터 기전을 돌려준다. 없으면 None.

    한글 `벡터` 는 찾지 않는다 — event_stats 의 docstring 이 그 말을 쓴다.
    """
    lowered = str(sql).lower()
    for operator in VECTOR_OPERATORS:
        if operator in lowered:
            return operator
    # `::vector` 만 보면 같은 캐스트의 다른 표기를 놓친다.
    if re.search(r"\bas\s+vector\b", lowered):
        return "cast as vector"
    if re.search(r"\bembedding\b", lowered):
        return "embedding"
    return None


def test_predicate_passes_the_shape_event_stats_actually_sends():
    assert (
        vector_mechanism_in(
            "SELECT count(*) AS total, ROUND(EXTRACT(EPOCH FROM"
            " AVG(resolved_at - occurred_at))) FROM kb_events WHERE project = %(project)s"
        )
        is None
    )
    assert vector_mechanism_in("SELECT kind, count(*) FROM kb_events GROUP BY kind") is None


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT id FROM kb_events ORDER BY embedding <=> %(q)s", "<=>"),
        ("SELECT id FROM kb_chunks ORDER BY embedding <-> %(q)s", "<->"),
        ("SELECT id FROM kb_chunks ORDER BY embedding <#> %(q)s", "<#>"),
        ("SELECT %(q)s::vector", "::vector"),
        ("SELECT CAST(%(q)s AS vector)", "cast as vector"),
        ("SELECT embedding FROM kb_events", "embedding"),
        ("select EMBEDDING from kb_events", "embedding"),
        # 점은 낱말 경계다. 한정 이름도 잡혀야 한다.
        ("SELECT kb_chunks.embedding FROM kb_chunks", "embedding"),
    ],
)
def test_predicate_catches_vector_mechanisms(sql, expected):
    """주입: 이 술어가 무는지 여기서 본다. 없으면 아래 캡처 검사가 공허해진다."""
    assert vector_mechanism_in(sql) == expected


def test_predicate_does_not_fire_on_a_similar_word():
    """`embedding` 은 낱말 경계로 본다. 아니면 컬럼 이름 하나가 못 지나간다."""
    assert vector_mechanism_in("SELECT embeddings_disabled FROM t") is None


@needs_db
def test_event_stats_never_sends_a_vector_query(clean_project, monkeypatch):
    """event_stats 가 실제로 execute 에 넘긴 질의문을 전부 모아 본다.

    감싸는 곳은 psycopg 의 Connection·Cursor 두 클래스다. 로컬 커서만 감싸면
    도우미가 connect() 를 새로 여는 순간 새어 나간다.
    """
    seen: list[str] = []

    # Connection 에는 executemany 가 없다. 클래스마다 있는 것만 감싼다 —
    # 없는 이름을 감싸려 들면 AttributeError 로 죽고, 있는데 빠뜨리면 조용히 샌다.
    # ClientCursor·ServerCursor 는 오늘 event_stats 가 타지 않는다. 그래도 감싼다 —
    # `conn.cursor(name=...)` 하나면 ServerCursor 로 새고, 그때 이 검사는 **초록으로** 샌다.
    for target, names in (
        (psycopg.Connection, ("execute",)),
        (psycopg.Cursor, ("execute", "executemany")),
        (psycopg.ClientCursor, ("execute", "executemany")),
        (psycopg.ServerCursor, ("execute", "executemany")),
    ):
        for name in names:
            original = getattr(target, name)

            def spy(self, query, *args, _original=original, **kwargs):
                seen.append(str(query))
                return _original(self, query, *args, **kwargs)

            monkeypatch.setattr(target, name, spy)

    service.save_event(DSN, body(module="auth"))
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    seen.clear()  # save_event 의 질의는 이 검사의 대상이 아니다
    service.event_stats(DSN, clean_project, module="auth", since=since)

    assert seen, "질의를 하나도 잡지 못했다 — 캡처가 비면 이 검사는 공허하다"
    offenders = {sql: found for sql in seen if (found := vector_mechanism_in(sql))}
    assert offenders == {}, f"event_stats 가 벡터 기전을 썼다: {offenders}"


@needs_db
def test_status_counts_and_nulls(clean_project):
    """성공한 run 이 없으면 빈 값이 정상이지 스텁이 아니다.

    `zero_hit_queries` 는 9단계가 붙어 이제 자란다 — 이 검사는 아무 질의도 하지 않은
    project 를 보므로 그래도 0 이다.
    """
    service.save_event(DSN, body())
    status = service.kb_status(DSN, clean_project)
    assert status["events"] == 1
    assert status["documents"] == 0
    assert status["chunks"] == 0
    assert status["last_ingest_at"] is None
    assert status["zero_hit_queries"] == 0
    # D31. 청크가 없으면 0 이다. 이 값이 chunks 와 같아지는 것이 "키 없이 색인했다" 는 신호다.
    assert status["chunks_without_embedding"] == 0


@needs_db
def test_status_keys_are_the_whole_contract(clean_project):
    """service-and-mcp.md 의 상태 응답이 이 여섯 키다. 늘거나 줄면 사본이 낡는다."""
    assert set(service.kb_status(DSN, clean_project)) == {
        "documents",
        "chunks",
        "events",
        "last_ingest_at",
        "zero_hit_queries",
        "chunks_without_embedding",
    }


def _add_run(db, project, status):
    """kb_status 는 자기 연결로 읽는다. 커밋하지 않으면 보이지 않는다."""
    db.execute(
        "INSERT INTO kb_ingest_runs (project, finished_at, status) VALUES (%s, now(), %s)",
        (project, status),
    )
    db.commit()


@needs_db
def test_status_ignores_failed_ingest_runs(db, clean_project):
    """D32. 실패한 run 을 세면 실패가 마지막 색인으로 보고된다."""
    _add_run(db, clean_project, "failed")
    assert service.kb_status(DSN, clean_project)["last_ingest_at"] is None
    # partial 은 텍스트 색인이 끝까지 간 run 이다. 세지 않으면 그것도 거짓말이 된다.
    _add_run(db, clean_project, "partial")
    assert service.kb_status(DSN, clean_project)["last_ingest_at"] is not None


@needs_db
def test_status_counts_chunks_without_embedding(db, clean_project):
    """D31. 빈 project 의 0 은 SQL 을 증명하지 못한다 — 틀린 FROM 도 0 을 준다."""
    doc = db.execute(
        "INSERT INTO kb_documents (project, path, content_hash)"
        " VALUES (%s, %s, %s) RETURNING id",
        (clean_project, "docs/x.md", "h"),
    ).fetchone()[0]  # db 픽스처는 dict_row 가 아니다
    db.execute(
        "INSERT INTO kb_chunks (document_id, chunk_idx, content) VALUES (%s, 0, %s), (%s, 1, %s)",
        (doc, "가", doc, "나"),
    )
    db.commit()

    status = service.kb_status(DSN, clean_project)
    assert status["chunks"] == 2
    assert status["chunks_without_embedding"] == 2

    db.execute(
        "UPDATE kb_chunks SET embedding = %s WHERE document_id = %s AND chunk_idx = 0",
        ("[" + ",".join(["0"] * 1536) + "]", doc),
    )
    db.commit()

    status = service.kb_status(DSN, clean_project)
    assert status["chunks"] == 2
    assert status["chunks_without_embedding"] == 1


@needs_db
def test_status_for_unknown_project_is_zeros_not_error():
    """404 대 빈 결과는 Q12(get_event)의 문제다. 여기서는 0 을 준다."""
    assert service.kb_status(DSN, "t_step4_never_used")["events"] == 0
