"""D17 마이그레이션 러너 검증.

DB 가 필요 없는 검사(discover)와 필요한 검사(apply/스키마)를 나눈다.
DB 가 없으면 skip 하되 이유를 남긴다 — 조용한 skip 은 "통과했다" 는 착각을 만든다.
"""

from __future__ import annotations

import os

import pytest

from sillok import migrations

psycopg = pytest.importorskip("psycopg")

DSN = os.environ.get("DATABASE_URL", "postgresql://sillok:sillok@127.0.0.1:5432/sillok")

TABLES = [
    "kb_documents",
    "kb_chunks",
    "kb_events",
    "kb_ingest_runs",
    "kb_query_logs",
]


# --- DB 없이 --------------------------------------------------------------


def test_discover_orders_by_version():
    found = migrations.discover()
    assert [m.version for m in found] == sorted(m.version for m in found)
    assert [m.name for m in found] == ["001_extensions.sql", "002_schema.sql"]


def test_extensions_run_before_schema():
    """vector 확장 없이 vector(1536) 컬럼을 만들 수 없다. 순서가 계약이다."""
    names = [m.name for m in migrations.discover()]
    assert names.index("001_extensions.sql") < names.index("002_schema.sql")


def test_missing_directory_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        migrations.discover(tmp_path / "없음")


def test_empty_directory_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        migrations.discover(tmp_path)


def test_bad_filename_is_not_skipped_silently(tmp_path):
    (tmp_path / "001_ok.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "schema.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(ValueError, match="규약"):
        migrations.discover(tmp_path)


def test_duplicate_version_is_an_error(tmp_path):
    (tmp_path / "001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "001_b.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(ValueError, match="겹친다"):
        migrations.discover(tmp_path)


# --- DB 필요 --------------------------------------------------------------


def _db_available() -> bool:
    try:
        with psycopg.connect(DSN, connect_timeout=3):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not _db_available(),
    reason=f"Postgres 에 붙을 수 없다: {DSN} — docker compose up -d --wait 후 다시 돌린다",
)


@pytest.fixture(scope="module")
def applied():
    return migrations.apply(DSN)


@pytest.fixture
def conn():
    """데이터 단언용. 커밋하지 않고 롤백한다."""
    with psycopg.connect(DSN) as c:
        yield c
        c.rollback()


@needs_db
def test_apply_returns_what_it_applied(applied):
    assert [m.name for m in applied] == ["001_extensions.sql", "002_schema.sql"]


@needs_db
def test_apply_is_idempotent(applied):
    """D17: 재기동이 안전해야 한다. 두 번째 적용이 실패하면 안 된다."""
    again = migrations.apply(DSN)
    assert [m.name for m in again] == [m.name for m in applied]


@needs_db
def test_extensions_installed(applied, conn):
    rows = conn.execute(
        "SELECT extname FROM pg_extension WHERE extname = ANY(%s)",
        (["vector", "pg_trgm"],),
    ).fetchall()
    assert sorted(r[0] for r in rows) == ["pg_trgm", "vector"]


@needs_db
@pytest.mark.parametrize("table", TABLES)
def test_table_exists(applied, conn, table):
    row = conn.execute("SELECT to_regclass(%s)", (table,)).fetchone()
    assert row[0] is not None, f"{table} 이 없다"


@needs_db
def test_embedding_is_vector_1536(applied, conn):
    """D2 의 차원이 DDL 에 박혀 있다. 모델을 바꾸면 스키마가 따라온다."""
    for table in ("kb_chunks", "kb_events"):
        row = conn.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            WHERE a.attrelid = %s::regclass AND a.attname = 'embedding'
            """,
            (table,),
        ).fetchone()
        assert row[0] == "vector(1536)", f"{table}.embedding = {row[0]}"


@needs_db
def test_tsv_is_generated_and_populated(applied, conn):
    """키가 없어도 키워드 검색이 되려면 tsv 가 실제로 채워져야 한다 (D2)."""
    doc_id = conn.execute(
        """
        INSERT INTO kb_documents (project, path, content_hash)
        VALUES ('t_smoke', 'docs/plan.md', 'h1') RETURNING id
        """
    ).fetchone()[0]
    row = conn.execute(
        """
        INSERT INTO kb_chunks (document_id, chunk_idx, heading_path, content)
        VALUES (%s, 0, '작업 순서', 'Compose 로 Postgres 를 띄운다')
        RETURNING tsv::text, length(tsv::text)
        """,
        (doc_id,),
    ).fetchone()
    assert row[1] > 0, "tsv 가 비어 있다"
    # D14: 구성은 simple. 한국어 어절이 그대로 남는다.
    assert "compose" in row[0].lower()


@needs_db
def test_chunks_cascade_with_document(applied, conn):
    """재색인은 (project, repo, path) 단위로 청크를 지우고 다시 넣는다."""
    doc_id = conn.execute(
        """
        INSERT INTO kb_documents (project, path, content_hash)
        VALUES ('t_smoke', 'docs/spec.md', 'h2') RETURNING id
        """
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO kb_chunks (document_id, chunk_idx, content) VALUES (%s, 0, 'x')",
        (doc_id,),
    )
    conn.execute("DELETE FROM kb_documents WHERE id = %s", (doc_id,))
    left = conn.execute(
        "SELECT count(*) FROM kb_chunks WHERE document_id = %s", (doc_id,)
    ).fetchone()[0]
    assert left == 0


@needs_db
def test_tsv_gin_index_exists(applied, conn):
    row = conn.execute(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'kb_chunks_tsv'"
    ).fetchone()
    assert row is not None, "kb_chunks_tsv 가 없다"
    assert "gin" in row[0].lower()


@needs_db
def test_hnsw_is_absent_in_v1(applied, conn):
    """data-model.md 와 plan.md §6 이 v1 에서 생략을 명시적으로 허용한다.

    있다고 착각하면 검색 성능 판단이 틀어지므로 부재를 단언한다.
    """
    rows = conn.execute(
        "SELECT indexname FROM pg_indexes WHERE indexname LIKE %s", ("%hnsw%",)
    ).fetchall()
    assert rows == []
