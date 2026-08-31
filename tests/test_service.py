"""4단계 Service 함수 검증 (D23·D24·D25).

검증 규칙은 명세에 답이 있는 순수 로직이라 여기부터 쓴다 (AGENTS 테스트 방식).
DB 가 필요한 검사는 아래 `needs_db` 묶음에 있다.
"""

from __future__ import annotations

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


@pytest.fixture
def clean_project(db):
    """이 파일이 쓰는 project 의 잔여 행을 지운 상태로 시작하고, 끝나면 지운다."""
    db.execute("DELETE FROM kb_events WHERE project = %s", ("t_step4",))
    db.commit()
    yield "t_step4"
    db.execute("DELETE FROM kb_events WHERE project = %s", ("t_step4",))
    db.commit()


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


@needs_db
def test_status_counts_and_nulls(clean_project):
    """5·9단계 전이라 빈 값이 정상이지 스텁이 아니다."""
    service.save_event(DSN, body())
    status = service.kb_status(DSN, clean_project)
    assert status["events"] == 1
    assert status["documents"] == 0
    assert status["chunks"] == 0
    assert status["last_ingest_at"] is None
    assert status["zero_hit_queries"] == 0


@needs_db
def test_status_for_unknown_project_is_zeros_not_error():
    """404 대 빈 결과는 Q12(get_event)의 문제다. 여기서는 0 을 준다."""
    assert service.kb_status(DSN, "t_step4_never_used")["events"] == 0
