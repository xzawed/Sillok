"""검색·필터의 뜻 — DB 경로 (D69).

부정만 있는 질의, `repeat_causes` 의 동순 정렬, 통계 `module` 의 벗김, 기간의 경계.
"""

from __future__ import annotations

import psycopg
import pytest
from psycopg.rows import dict_row

from sillok import service

from dbcheck import DSN, needs_db

PROJECT = "t_semantics"

pytestmark = needs_db


@pytest.fixture
def db():
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        conn.autocommit = True
        yield conn


@pytest.fixture
def clean(db):
    def wipe():
        for table in ("kb_query_logs", "kb_events"):
            db.execute(f"DELETE FROM {table} WHERE project = %s", (PROJECT,))

    wipe()
    yield PROJECT
    wipe()


def _add(db, title, *, module=None, root_cause=None, occurred_at="2026-01-01T00:00:00Z"):
    return db.execute(
        "INSERT INTO kb_events (project, kind, title, summary, module, root_cause, result, occurred_at)"
        " VALUES (%s, 'failure', %s, 'summary', %s, %s, 'failure', %s) RETURNING id",
        (PROJECT, title, module, root_cause, occurred_at),
    ).fetchone()["id"]


def _events(body):
    return service.search_events(DSN, {"project": PROJECT, **body})["results"]


# --- ⑤ 부정만 있는 질의 --------------------------------------------------------------------


def test_a_negation_only_query_returns_nothing(clean, db):
    """감사 실측: `-없는낱말` 이 필터 집합 전체를 순위처럼 돌려줬다 — D33 이 websearch 를 버린 그 고장."""
    for i in range(3):
        _add(db, f"행{i} 평범한낱말")
    assert _events({"query": "-없는낱말"}) == []
    assert _events({"query": "평범한낱말 OR -없는낱말"}) == []  # 빈 tsvector 에도 참이다


def test_a_negation_with_a_positive_term_still_searches(clean, db):
    kept = _add(db, "남는낱말")
    _add(db, "남는낱말 빠질낱말")
    assert [r["id"] for r in _events({"query": "남는낱말 -빠질낱말"})] == [kept]


def test_the_negation_only_miss_is_logged(clean, db):
    """`VALIDATION` 이 아니라 술어를 적용한 미스다 — `???` 처럼 원장에 0건으로 남는다 (D50)."""
    _add(db, "무엇")
    _add(db, "다른것")  # 가드가 없으면 이 행이 `-무엇` 에 걸려 hit_count 가 1 이 된다
    assert _events({"query": "-무엇"}) == []
    row = db.execute(
        "SELECT hit_count FROM kb_query_logs WHERE project = %s ORDER BY id DESC LIMIT 1", (PROJECT,)
    ).fetchone()
    assert row["hit_count"] == 0


# --- ⑥ repeat_causes 의 동순 ------------------------------------------------------------------


def test_repeat_causes_ties_sort_bytewise(clean, db):
    """by_module 은 COLLATE "C" 였는데(D58) 여기만 DB 로케일을 따랐다 — `LIMIT 12` 가 자르는 대상이 갈린다."""
    locale_says_a_first = db.execute("SELECT 'a' < 'B' AS lt").fetchone()["lt"]
    if not locale_says_a_first:
        pytest.skip("DB 기본 콜레이션이 C 와 같은 순서라 두 정렬을 가를 수 없다")
    for cause in ("a", "a", "B", "B"):
        _add(db, "t", module="m", root_cause=cause)
    got = [r["root_cause"] for r in service.event_stats(DSN, PROJECT)["repeat_causes"]]
    assert got == ["B", "a"]


# --- ③ 통계 module 의 벗김 --------------------------------------------------------------------


def test_event_stats_module_is_stripped_like_the_search_filters(clean, db):
    _add(db, "t", module="auth")
    _add(db, "t", module="billing")
    assert service.event_stats(DSN, PROJECT, " auth ")["total"] == 1
    assert service.event_stats(DSN, PROJECT, "   ")["total"] == 2  # 공백뿐이면 필터가 아니다
    assert service.event_stats(DSN, PROJECT, "")["total"] == 2


# --- ④ 기간의 경계 ------------------------------------------------------------------------------


def test_the_period_is_half_open(clean, db):
    at = "2026-03-01T00:00:00Z"
    _add(db, "경계", occurred_at=at)
    assert len(_events({"since": at})) == 1  # since 는 포함
    assert _events({"until": at}) == []  # until 은 배제
    assert len(_events({"until": "2026-03-01T00:00:01Z"})) == 1
