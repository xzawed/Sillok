"""D17 마이그레이션 러너 검증.

DB 가 필요 없는 검사(discover)와 필요한 검사(apply/스키마)를 나눈다.
DB 가 없으면 skip 하되 이유를 남긴다 — 조용한 skip 은 "통과했다" 는 착각을 만든다.
"""

from __future__ import annotations

import re

import psycopg
import pytest

from sillok import migrations

from dbcheck import DSN, needs_db


def _migration_text(name: str) -> str:
    """러너가 실제로 먹는 파일을 읽는다. 사본을 만들지 않는다."""
    return (migrations.DEFAULT_MIGRATIONS_DIR / name).read_text(encoding="utf-8")


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
    assert [m.name for m in found] == [
        "001_extensions.sql",
        "002_schema.sql",
        "003_ingest_counters.sql",
        "004_event_tsv.sql",
        "005_query_log_index.sql",
    ]


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


# --- 선언된 인덱스 파서 ----------------------------------------------------
#
# 왜 파서인가: 손으로 쓴 기대 목록은 **범위 밖이 조용히 썩는다.** 004 가
# kb_events_tsv 를 더했을 때 이 파일의 목록은 그대로였고, 그래서 그 인덱스가
# 사라져도 아무도 몰랐다. 기대 집합을 마이그레이션에서 유도하면 그 구멍이 닫힌다.
#
# 파싱하는 쪽은 **마이그레이션이지 docs/data-model.md 가 아니다.** 정본 DDL 은
# v1 이 만들지 않는 HNSW 를 CREATE INDEX 로 적어 두므로(D33), 그쪽을 기대 집합에
# 넣으면 test_hnsw_is_absent_in_v1 과 정면으로 부딪힌다. 이 검사가 묻는 것은
# "러너가 적용하는 파일이 선언한 인덱스가 살아 있는가" 하나다.
#
# 파서는 그 자체가 새 결함 표면이다 — 이 저장소는 검사 0개로 나간 게이트 파서에서
# 결함을 3건 냈다. 그래서 아래 파서 검사가 DB 검사보다 **먼저** 온다.

_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE = re.compile(r"--[^\n]*")

# CREATE [UNIQUE] INDEX [CONCURRENTLY] [IF NOT EXISTS] <이름> ON <표> [USING <방법>]
_CREATE_INDEX = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+"
    r"(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?P<name>[^\s(;]+)\s+ON\s+(?P<rest>[^;]*)",
    re.IGNORECASE,
)


def strip_sql_comments(sql: str) -> str:
    """`--` 줄 주석과 `/* */` 블록 주석을 지운다.

    이 단계가 없으면 산문이 인덱스가 된다. 004 는 본문에
    `CREATE INDEX CONCURRENTLY 를 쓸 수 없다` 를 주석으로 적어 두었다.
    """
    return _COMMENT_LINE.sub("", _COMMENT_BLOCK.sub("", sql))


def indexes_in_stripped_sql(sql: str) -> dict[str, str]:
    """주석이 **이미 벗겨진** SQL 에서 인덱스 이름 -> 접근 방법을 뽑는다.

    벗기는 단계를 분리해 두는 것은 그 단계가 실제로 일하는지 검사가 보기 위해서다.
    """
    found: dict[str, str] = {}
    for m in _CREATE_INDEX.finditer(sql):
        name = m.group("name")
        rest = m.group("rest")
        if name.startswith('"') or rest.lstrip().startswith('"'):
            raise AssertionError(f"따옴표 식별자는 v1 에 없다: {name}")
        if re.search(r"\bWHERE\b", rest, re.IGNORECASE):
            raise AssertionError(f"부분 인덱스는 v1 에 없다: {name}")
        using = re.search(r"\bUSING\s+(?P<am>\w+)", rest, re.IGNORECASE)
        method = using.group("am").lower() if using else "btree"
        if name in found:
            raise AssertionError(f"같은 인덱스 이름이 두 번 선언됐다: {name}")
        found[name] = method
    return found


def declared_indexes(sql: str) -> dict[str, str]:
    return indexes_in_stripped_sql(strip_sql_comments(sql))


def declared_indexes_in_dir(directory=None) -> dict[str, str]:
    """러너가 적용하는 파일 전체가 선언한 인덱스.

    discover() 를 쓰는 것은 러너가 실제로 먹는 목록과 갈라지지 않기 위해서다 —
    디렉터리를 따로 훑으면 그 순간 두 번째 목록이 생긴다.
    """
    merged: dict[str, str] = {}
    for m in migrations.discover(directory):
        for name, method in declared_indexes(m.path.read_text(encoding="utf-8")).items():
            if name in merged:
                raise AssertionError(f"같은 인덱스 이름이 두 파일에 있다: {name}")
            merged[name] = method
    return merged


def test_parser_reads_002():
    got = declared_indexes(_migration_text("002_schema.sql"))
    assert got == {
        "kb_events_project_time": "btree",
        "kb_events_filter": "btree",
        "kb_chunks_tsv": "gin",
        "kb_docs_lookup": "btree",
    }


def test_parser_reads_004():
    """004 는 본문 주석에 `CREATE INDEX CONCURRENTLY` 라는 산문을 갖는다."""
    assert declared_indexes(_migration_text("004_event_tsv.sql")) == {
        "kb_events_tsv": "gin"
    }


def test_parser_reads_005():
    assert declared_indexes(_migration_text("005_query_log_index.sql")) == {
        "kb_query_logs_project_time": "btree"
    }


@pytest.mark.parametrize(
    "sql",
    [
        "-- CREATE INDEX CONCURRENTLY 를 쓸 수 없다 — 러너는 한 트랜잭션이다 (D32).",
        "-- CREATE INDEX IF NOT EXISTS ghost ON t (c);",
        "/* CREATE INDEX ghost ON t (c); */",
    ],
)
def test_commented_out_index_is_not_declared(sql):
    assert declared_indexes(sql) == {}


def test_if_not_exists_is_not_part_of_the_name():
    assert declared_indexes("CREATE INDEX IF NOT EXISTS x ON t (c);") == {"x": "btree"}


def test_concurrently_is_not_part_of_the_name():
    assert declared_indexes("CREATE INDEX CONCURRENTLY x ON t (c);") == {"x": "btree"}


def test_the_comment_step_is_what_keeps_prose_out():
    """주입: 주석을 벗기는 단계를 끄면 주석 속 산문이 인덱스가 된다.

    이 케이스가 없으면 strip_sql_comments 를 지워도 위 검사들이 초록일 수 있다 —
    그 단계가 실제로 일하고 있음을 여기서만 볼 수 있다.
    """
    commented = "-- CREATE INDEX IF NOT EXISTS ghost ON t (c);"
    assert declared_indexes(commented) == {}
    assert indexes_in_stripped_sql(commented) == {"ghost": "btree"}


def test_partial_index_is_rejected_not_skipped():
    with pytest.raises(AssertionError, match="부분 인덱스"):
        declared_indexes("CREATE INDEX x ON t (c) WHERE c IS NOT NULL;")


def test_quoted_identifier_is_rejected_not_skipped():
    with pytest.raises(AssertionError, match="따옴표 식별자"):
        declared_indexes('CREATE INDEX "X" ON t (c);')


def test_duplicate_index_name_is_rejected():
    with pytest.raises(AssertionError, match="두 번 선언"):
        declared_indexes("CREATE INDEX x ON t (a); CREATE INDEX x ON t (b);")


def test_directory_walk_finds_every_declared_index():
    """러너가 먹는 파일 전체에서 여섯이 나온다. 하나라도 빠지면 대조가 공허해진다."""
    assert set(declared_indexes_in_dir()) == {
        "kb_events_project_time",
        "kb_events_filter",
        "kb_chunks_tsv",
        "kb_docs_lookup",
        "kb_events_tsv",
        "kb_query_logs_project_time",
    }


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
    assert [m.name for m in applied] == [
        "001_extensions.sql",
        "002_schema.sql",
        "003_ingest_counters.sql",
        "004_event_tsv.sql",
        "005_query_log_index.sql",
    ]


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


# UNIQUE 제약이 만드는 인덱스. 재색인 upsert 와 청크 교체가 이것에 기댄다.
# CREATE INDEX 가 아니라 CREATE TABLE 이 만들므로 파서가 유도하지 못한다 —
# 여기만 손으로 둔다. CREATE TABLE 까지 파싱하면 이번 구멍과 무관한 표면이 열린다.
# PRIMARY KEY 의 `_pkey` 는 넣지 않는다. 표가 있는 한 항상 있다.
CONSTRAINT_INDEXES = {
    "kb_documents_project_repo_path_key",
    "kb_chunks_document_id_chunk_idx_key",
}


@needs_db
def test_live_indexes_are_exactly_what_migrations_declare(applied, conn):
    """산 DB 와 마이그레이션이 **양쪽 다** 같은 집합인지 본다.

    존재만 보면 두 방향으로 썩는다.
      - 파일에만 있고 DB 에 없다 = 마이그레이션이 안 돌았다
      - DB 에만 있고 파일에 없다 = 손으로 만든 인덱스가 공유 볼륨(D55)에 남았다.
        이쪽은 CREATE INDEX 줄을 지워도 조용히 통과하게 만든다.

    접근 방법까지 보는 것은 test_hnsw_is_absent_in_v1 과 같은 이유다 — 이름만 보면
    gin 이어야 할 kb_events_tsv 가 btree 로 살아 있어도 초록이다.
    """
    declared = declared_indexes_in_dir()
    rows = conn.execute(
        """
        SELECT c.relname, am.amname
        FROM pg_class c
        JOIN pg_am am ON am.oid = c.relam
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_index i ON i.indexrelid = c.oid
        JOIN pg_class t ON t.oid = i.indrelid
        WHERE c.relkind = 'i'
          AND n.nspname = 'public'
          AND t.relname ~ '^kb_'
          AND c.relname !~ '_pkey$'
        """
    ).fetchall()
    live = {name: method for name, method in rows}

    assert set(live) == set(declared) | CONSTRAINT_INDEXES
    # 제약이 만드는 둘은 접근 방법을 단언하지 않는다. Postgres 가 정한다.
    assert {n: live[n] for n in declared} == declared


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

    003 이 더한 컬럼이다. 이 검사가 무는 것은 "003 이 돌았는데 컬럼이 없다" 하나다 —
    이미지가 낡아 003 을 못 본 것은 위의 discover·apply 이름 목록이 잡는다.
    공유 db_data 에 컬럼이 이미 있으면 이 단언만으로는 조용히 통과한다.
    """
    rows = conn.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'kb_ingest_runs'
          AND column_name IN ('files_seen', 'files_changed', 'files_deleted')
        """
    ).fetchall()
    assert sorted(r[0] for r in rows) == ["files_changed", "files_deleted", "files_seen"]


@needs_db
def test_event_tsv_is_generated_from_four_fields(applied, conn):
    """D34. 네 필드를 전부 coalesce 로 감싼다 — 하나가 NULL 이면 tsv 가 통째로 NULL 이 된다.

    그러면 그 행은 어떤 질의에도 걸리지 않고 오류는 어디에도 없다.
    """
    expr = conn.execute(
        """
        SELECT pg_get_expr(d.adbin, d.adrelid) AS e
        FROM pg_attrdef d JOIN pg_attribute a
          ON a.attrelid = d.adrelid AND a.attnum = d.adnum
        WHERE d.adrelid = 'kb_events'::regclass AND a.attname = 'tsv'
        """
    ).fetchone()[0]
    for field in ("title", "summary", "root_cause", "resolution"):
        assert f"COALESCE({field}" in expr, f"{field} 가 coalesce 로 감싸이지 않았다"
    assert "'simple'" in expr


@needs_db
def test_event_tsv_survives_a_null_field(applied, conn):
    """root_cause 가 NULL 인 이벤트도 title 의 낱말로 찾힌다."""
    conn.execute(
        "INSERT INTO kb_events (project, kind, title, summary, result, occurred_at)"
        " VALUES ('t_mig_tsv', 'failure', '락 경쟁', '요약', 'failure', now())"
    )
    got = conn.execute(
        "SELECT count(*) FROM kb_events"
        " WHERE project = 't_mig_tsv' AND tsv @@ websearch_to_tsquery('simple', '락')"
    ).fetchone()[0]
    assert got == 1


@needs_db
def test_no_trgm_index_exists(applied, conn):
    """D34. pg_trgm 은 v1 미사용이다. 확장 설치만 보는 검사의 짝이다."""
    rows = conn.execute(
        """
        SELECT c.relname FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_opclass o ON o.oid = ANY(i.indclass)
        WHERE o.opcname IN ('gin_trgm_ops', 'gist_trgm_ops')
        """
    ).fetchall()
    assert rows == []
