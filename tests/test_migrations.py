"""D17 마이그레이션 러너 검증.

DB 가 필요 없는 검사(discover)와 필요한 검사(apply/스키마)를 나눈다.
DB 가 없으면 skip 하되 이유를 남긴다 — 조용한 skip 은 "통과했다" 는 착각을 만든다.
"""

from __future__ import annotations


import psycopg
import pytest

from sillok import migrations

from dbcheck import DSN, needs_db

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
    assert [m.name for m in found] == ["001_extensions.sql", "002_schema.sql", "003_ingest_counters.sql"]


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


@pytest.mark.parametrize(
    ("dsn", "password"),
    [
        ("postgresql://sillok:secret@127.0.0.1:5432/sillok", "secret"),
        # 암호에 @ 나 : 가 들어간 경우. 검사 문자열도 그 암호여야 한다 —
        # 'secret' 을 찾으면 실제로 샜을 때도 통과한다.
        ("postgresql://sillok:p@ss@127.0.0.1:5432/sillok", "p@ss"),
        ("postgresql://sillok:pa:ss@127.0.0.1:5432/sillok", "pa:ss"),
        ("postgresql://sillok:secret@[::1]:5432/sillok", "secret"),
        ("postgresql://sillok:secret@127.0.0.1:5432/sillok?sslmode=require", "secret"),
        # libpq 는 URI 말고 아래 형태도 받는다. 여기서 새면 오류 로그에 암호가 남는다.
        ("postgresql://sillok@127.0.0.1:5432/sillok?password=secret", "secret"),
        ("postgresql://localhost/sillok?user=sillok&password=secret", "secret"),
        ("postgresql://h/db?password=one&password=two", "two"),
        ("postgresql://h/db?Password=MixedCase", "MixedCase"),
        ("host=127.0.0.1 port=5432 user=sillok password=secret dbname=sillok", "secret"),
        ("host=127.0.0.1 user=sillok password='se cret' dbname=sillok", "se cret"),
    ],
)
def test_redact_never_leaks_the_password(dsn, password):
    assert password in dsn, "테스트 입력이 그 암호를 실제로 담고 있어야 한다"
    assert password not in migrations.redact_dsn(dsn)


def test_redact_keeps_what_is_useful():
    out = migrations.redact_dsn("postgresql://sillok:secret@127.0.0.1:5432/sillok")
    assert out == "postgresql://sillok:***@127.0.0.1:5432/sillok"


def test_redact_leaves_passwordless_dsn_alone():
    dsn = "postgresql://db:5432/sillok"
    assert migrations.redact_dsn(dsn) == dsn


# --- DB 필요 --------------------------------------------------------------


# skip 장치는 tests/dbcheck.py 가 소유한다. 두 곳에 두면 사유 문구가 갈라진다.


@pytest.fixture(scope="module")
def applied():
    return migrations.apply(DSN)


@pytest.fixture
def conn():
    """데이터 단언용. 커밋하지 않고 롤백한다.

    psycopg 의 connect() 컨텍스트는 정상 종료 시 commit 한다. 그래서 rollback 이
    반드시 먼저 돌아야 한다 — 테스트가 실패해도 돌도록 finally 에 둔다.
    테스트가 스스로 commit 하면 이 장치는 막지 못한다. 테스트에서 commit 하지 않는다.
    """
    with psycopg.connect(DSN) as c:
        try:
            yield c
        finally:
            c.rollback()


@needs_db
def test_apply_returns_what_it_applied(applied):
    assert [m.name for m in applied] == ["001_extensions.sql", "002_schema.sql", "003_ingest_counters.sql"]


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
    tsv = row[0].lower()
    # D14: 구성은 simple. 영어는 소문자화만 되고 어간 추출은 없다.
    assert "compose" in tsv
    # simple 은 한국어를 형태소로 쪼개지 않으므로 어절이 그대로 남는다.
    # english 구성이었다면 'postgres' 로 어간이 잘려 아래가 깨진다.
    assert "postgres" in tsv
    assert "를" in tsv
    # heading_path 도 tsv 에 들어가야 한다 — 생성식에 coalesce(heading_path,'') 가 있다.
    assert "작업" in tsv


@needs_db
def test_chunks_cascade_with_document(applied, conn):
    """문서를 지우면 청크가 따라 지워진다 (FK ON DELETE CASCADE).

    재색인이 (project, repo, path) 단위로 도는 전제가 이 제약이다.
    """
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
@pytest.mark.parametrize(
    "index",
    [
        "kb_events_project_time",
        "kb_events_filter",
        "kb_docs_lookup",
        # UNIQUE 제약이 만드는 인덱스. 재색인 upsert 와 청크 교체가 이것에 기댄다.
        "kb_documents_project_repo_path_key",
        "kb_chunks_document_id_chunk_idx_key",
    ],
)
def test_declared_index_exists(applied, conn, index):
    row = conn.execute(
        "SELECT indexname FROM pg_indexes WHERE indexname = %s", (index,)
    ).fetchone()
    assert row is not None, f"{index} 가 없다"


@needs_db
def test_document_identity_is_project_repo_path(applied, conn):
    """재색인 단위가 (project, repo, path) 라는 계약을 DB 가 강제하는지 본다."""
    conn.execute(
        """
        INSERT INTO kb_documents (project, path, content_hash)
        VALUES ('t_smoke', 'docs/dup.md', 'h1')
        """
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            """
            INSERT INTO kb_documents (project, path, content_hash)
            VALUES ('t_smoke', 'docs/dup.md', 'h2')
            """
        )


@needs_db
def test_hnsw_is_absent_in_v1(applied, conn):
    """data-model.md 와 plan.md §6 이 v1 에서 생략을 명시적으로 허용한다.

    이름이 아니라 접근 방법(pg_am)으로 본다. 이름으로만 보면
    kb_chunks_embedding_idx 같은 이름의 HNSW 인덱스를 놓친다.
    """
    rows = conn.execute(
        """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_am am ON am.oid = c.relam
        WHERE c.relkind = 'i' AND am.amname = 'hnsw'
        """
    ).fetchall()
    assert rows == []


@needs_db
def test_ingest_run_counters_are_separate(applied, conn):
    """D30. 삭제를 files_changed 에 접으면 가장 파괴적인 동작이 원장에서 사라진다.

    003 이 더한 컬럼이다. 이 검사가 없으면 test 이미지의 구운 migrations/ 가
    낡아도 아무도 비명을 지르지 않는다 — D28 이 예고한 부류이고 실제로 한 번 났다.
    """
    rows = conn.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'kb_ingest_runs'
          AND column_name IN ('files_seen', 'files_changed', 'files_deleted')
        """
    ).fetchall()
    assert sorted(r[0] for r in rows) == ["files_changed", "files_deleted", "files_seen"]
