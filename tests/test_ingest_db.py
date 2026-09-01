"""5단계 ingest 의 DB 경로 (D30 · D31 · D32).

workspace 는 `tmp_path` 로 만든다. 작업 트리를 마운트하지 않는 이유는
그러면 검사가 저장소의 지금 내용에 묶여 문서를 고칠 때마다 깨지기 때문이다 (D30).
"""

from __future__ import annotations

import psycopg
import pytest
from psycopg.rows import dict_row

from sillok import service

from dbcheck import DSN, needs_db

PROJECT = "t_step5"
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
        for table in ("kb_ingest_runs", "kb_documents"):
            db.execute(f"DELETE FROM {table} WHERE project = %s", (PROJECT,))

    wipe()
    yield PROJECT
    wipe()


@pytest.fixture
def write(tmp_path):
    """Path 에는 속성을 붙일 수 없다. 쓰기 헬퍼를 따로 둔다."""

    def _write(rel, text):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def workspace(tmp_path, write):
    write("docs/a.md", FM + "# 가\n\n본문 가\n")
    write("adr/b.md", FM + "# 나\n\n본문 나\n")
    write("README.md", "# 루트\n\n소개\n")
    return tmp_path


def run(workspace, project=PROJECT, key=""):
    return service.ingest(DSN, project, str(workspace), key)


def docs(db, project=PROJECT):
    return db.execute(
        "SELECT path, doc_type, title, module, content_hash, indexed_at, commit_sha"
        # 스캔 순서와 같은 바이트 순서로 본다. 기본 ORDER BY 는 DB 콜레이션 순서다.
        " FROM kb_documents WHERE project = %s ORDER BY path COLLATE \"C\"",
        (project,),
    ).fetchall()


def chunks(db, project=PROJECT):
    return db.execute(
        "SELECT d.path, c.chunk_idx, c.heading_path, c.content, c.embedding"
        " FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id"
        " WHERE d.project = %s ORDER BY d.path COLLATE \"C\", c.chunk_idx",
        (project,),
    ).fetchall()


# --- 첫 색인 ---------------------------------------------------------------


def test_first_run_indexes_the_d9_paths(db, clean, workspace):
    got = run(workspace)
    assert got["status"] == "ok"
    assert got["files_seen"] == 3
    assert got["files_changed"] == 3
    assert got["files_deleted"] == 0
    assert got["chunks_upserted"] == 3
    assert got["skipped"] == []
    # D30 §3: v1 은 채우지 않는다. 필드는 계약이라 지우지 않는다.
    assert got["commit_sha"] == ""

    rows = docs(db)
    assert [r["path"] for r in rows] == ["README.md", "adr/b.md", "docs/a.md"]
    readme = next(r for r in rows if r["path"] == "README.md")
    # D29: 루트 README 는 경로와 첫 H1 에서 유도한다.
    assert (readme["doc_type"], readme["title"], readme["module"]) == ("readme", "루트", None)
    # NOT NULL DEFAULT '' 라 빈 문자열이 곧 부재다.
    assert readme["commit_sha"] == ""


def test_chunks_carry_the_heading_path(db, clean, workspace):
    run(workspace)
    rows = [r for r in chunks(db) if r["path"] == "docs/a.md"]
    assert [(r["chunk_idx"], r["heading_path"], r["content"]) for r in rows] == [(0, "가", "본문 가")]


def test_tsv_is_generated_from_heading_and_content(db, clean, workspace):
    """백필 입력식과 tsv 생성식이 같은 것을 보는지 잠근다 (D31).

    파이썬에서 이어 붙이면 같은 규칙의 세 번째 사본이 생겨 이 검사가 물지 않는다.
    """
    run(workspace)
    bad = db.execute(
        "SELECT count(*) AS n FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id"
        " WHERE d.project = %s"
        " AND to_tsvector('simple', " + service.EMBED_INPUT_SQL + ") IS DISTINCT FROM c.tsv",
        (PROJECT,),
    ).fetchone()["n"]
    assert bad == 0


# --- 재실행과 재색인 --------------------------------------------------------


def test_second_run_changes_nothing(db, clean, workspace):
    """변경 판정의 근거는 content_hash 하나다 (D30 §2)."""
    run(workspace)
    before = {r["path"]: r["indexed_at"] for r in docs(db)}
    got = run(workspace)
    assert got["files_seen"] == 3
    assert got["files_changed"] == 0
    assert got["chunks_upserted"] == 0
    assert {r["path"]: r["indexed_at"] for r in docs(db)} == before


def test_line_ending_change_alone_is_not_a_change(db, clean, workspace):
    """같은 커밋을 두 OS 에서 색인해도 전량 재색인이 되지 않는다."""
    run(workspace)
    path = workspace / "docs" / "a.md"
    path.write_bytes(path.read_text(encoding="utf-8").replace("\n", "\r\n").encode())
    assert run(workspace)["files_changed"] == 0


def test_reindex_replaces_chunks_and_keeps_the_document_row(db, clean, workspace, write):
    """재색인은 문서 행을 유지한 채 청크만 지우고 다시 넣는다 (D30 §4)."""
    run(workspace)
    doc_id = db.execute(
        "SELECT id FROM kb_documents WHERE project = %s AND path = 'docs/a.md'", (PROJECT,)
    ).fetchone()["id"]

    write("docs/a.md", FM + "# 가\n\n바뀐 본문\n\n## 새 절\n\n둘\n")
    got = run(workspace)
    assert got["files_changed"] == 1
    assert got["chunks_upserted"] == 2

    same = db.execute(
        "SELECT id FROM kb_documents WHERE project = %s AND path = 'docs/a.md'", (PROJECT,)
    ).fetchone()["id"]
    assert same == doc_id
    rows = [r for r in chunks(db) if r["path"] == "docs/a.md"]
    assert [r["heading_path"] for r in rows] == ["가", "가 > 새 절"]


# --- 삭제 (D30 §4) ----------------------------------------------------------


def test_missing_file_is_deleted_with_its_chunks(db, clean, workspace):
    run(workspace)
    (workspace / "docs" / "a.md").unlink()
    got = run(workspace)
    assert got["files_deleted"] == 1
    # 삭제는 files_changed 에 접지 않는다 — 접으면 원장에서 사라진다.
    assert got["files_changed"] == 0
    assert [r["path"] for r in docs(db)] == ["README.md", "adr/b.md"]
    assert all(r["path"] != "docs/a.md" for r in chunks(db))


def test_empty_scan_deletes_nothing_and_fails(db, clean, workspace, tmp_path):
    """--workspace 를 잘못 준 한 번이 인덱스를 통째로 지우는 것이 유일한 파국이다."""
    run(workspace)
    empty = tmp_path / "empty"
    empty.mkdir()
    got = run(empty)
    assert got["status"] == "failed"
    assert got["files_deleted"] == 0
    assert len(docs(db)) == 3


def test_skipped_file_is_not_a_deletion_candidate(db, clean, workspace):
    """제외를 삭제 후보로 삼으면 링크로 바꾸는 것만으로 문서가 지워진다."""
    run(workspace)
    target = workspace / "docs" / "a.md"
    body = target.read_text(encoding="utf-8")
    target.unlink()
    outside = workspace.parent / "moved.md"
    outside.write_text(body, encoding="utf-8")
    try:
        target.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 수 없다")

    got = run(workspace)
    assert got["skipped"] == [{"path": "docs/a.md", "reason": "symlink"}]
    # 링크가 된 파일은 색인 대상이 아니지만 **지우지도 않는다.**
    assert got["files_deleted"] == 0
    assert "docs/a.md" in [r["path"] for r in docs(db)]


# --- run 행과 status (D32) --------------------------------------------------


def test_run_row_records_the_counters_and_status(db, clean, workspace):
    got = run(workspace)
    row = db.execute(
        "SELECT * FROM kb_ingest_runs WHERE id = %s", (got["run_id"],)
    ).fetchone()
    assert row["status"] == "ok"
    assert row["error"] is None
    assert row["finished_at"] is not None
    assert (row["files_seen"], row["files_changed"], row["files_deleted"]) == (3, 3, 0)


def test_failed_run_records_the_error(db, clean, tmp_path):
    empty = tmp_path / "none"
    empty.mkdir()
    got = run(empty)
    row = db.execute("SELECT * FROM kb_ingest_runs WHERE id = %s", (got["run_id"],)).fetchone()
    assert row["status"] == "failed"
    assert row["error"]
    assert len(row["error"]) <= service.ERROR_MAX


def test_decode_failure_fails_the_run_and_skips_deletion(db, clean, workspace):
    """못 읽은 파일과 사라진 파일을 구분할 수 없다 (D30 §2)."""
    run(workspace)
    (workspace / "docs" / "bad.md").write_bytes(b"\xff\xfe\x00\x01")
    got = run(workspace)
    assert got["status"] == "failed"
    assert got["files_deleted"] == 0
    assert len(docs(db)) == 3


def test_a_stale_running_row_is_reclaimed(db, clean, workspace):
    """락이 그 행이 죽었다는 증거다 — 살아 있었다면 락을 못 얻었다."""
    stale = db.execute(
        "INSERT INTO kb_ingest_runs (project, status) VALUES (%s, 'running') RETURNING id",
        (PROJECT,),
    ).fetchone()["id"]
    run(workspace)
    row = db.execute("SELECT * FROM kb_ingest_runs WHERE id = %s", (stale,)).fetchone()
    assert row["status"] == "failed"
    assert row["error"] == service.INTERRUPTED
    # 언제 죽었는지 모르는데 지금 시각을 넣으면 그것이 새 거짓말이다.
    assert row["finished_at"] is None


def test_taxonomy_violation_fails_the_run(db, clean, workspace, write):
    """검증은 서비스에 두고 DDL 에 CHECK 를 넣지 않는다 (D25)."""
    write(
        "docs/bad.md", "---\ntitle: T\ndoc_type: 발명\nstatus: current\nmodule: null\n---\n\nx\n"
    )
    got = run(workspace)
    assert got["status"] == "failed"
    assert "taxonomy" in (
        db.execute("SELECT error FROM kb_ingest_runs WHERE id = %s", (got["run_id"],))
        .fetchone()["error"]
    )


# --- 동시 실행 (D32) --------------------------------------------------------


def test_second_run_is_rejected_while_the_lock_is_held(db, clean, workspace):
    """블로킹 락은 매달린다 — 느린 색인과 구분되지 않는다. 그래서 즉시 거절한다."""
    with psycopg.connect(DSN, row_factory=dict_row) as holder:
        holder.autocommit = True
        got = holder.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s), hashtext(%s)) AS got",
            (service.LOCK_NAMESPACE, PROJECT),
        ).fetchone()["got"]
        assert got
        try:
            with pytest.raises(service.IngestLocked) as exc:
                run(workspace)
            assert str(exc.value) == service.LOCKED_MESSAGE
        finally:
            holder.execute(
                "SELECT pg_advisory_unlock(hashtext(%s), hashtext(%s))",
                (service.LOCK_NAMESPACE, PROJECT),
            )
    # 거절된 시도는 행을 만들지 않는다.
    assert db.execute(
        "SELECT count(*) AS n FROM kb_ingest_runs WHERE project = %s", (PROJECT,)
    ).fetchone()["n"] == 0


def test_a_different_project_is_not_blocked(db, clean, workspace):
    other = PROJECT + "_other"
    with psycopg.connect(DSN, row_factory=dict_row) as holder:
        holder.autocommit = True
        holder.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s), hashtext(%s))",
            (service.LOCK_NAMESPACE, other),
        )
        try:
            assert run(workspace)["status"] == "ok"
        finally:
            holder.execute(
                "SELECT pg_advisory_unlock(hashtext(%s), hashtext(%s))",
                (service.LOCK_NAMESPACE, other),
            )


def test_the_lock_is_released_when_the_run_ends(db, clean, workspace):
    """serve 는 장수 프로세스다. 안 풀면 세션 락이 남는다."""
    run(workspace)
    assert run(workspace)["status"] == "ok"


# --- 트랜잭션 경계 (D32) ----------------------------------------------------


def test_each_file_is_committed_on_its_own(db, clean, workspace, monkeypatch):
    """autocommit 을 안 켜면 파일 단위 커밋이 조용히 사라진다.

    블록 밖 문장 하나가 암묵 트랜잭션을 열면 이후 트랜잭션 블록이 전부
    세이브포인트가 되어 run 전체가 한 트랜잭션이 된다 — 실패가 아니라 통과로 나온다.
    그래서 **별도 연결에서** 그 행이 이미 보이는지 확인한다.
    """
    seen: list[int] = []
    real = service._write_document

    def spy(conn, project, doc):
        out = real(conn, project, doc)
        with psycopg.connect(DSN, row_factory=dict_row) as other:
            seen.append(
                other.execute(
                    "SELECT count(*) AS n FROM kb_documents WHERE project = %s", (project,)
                ).fetchone()["n"]
            )
        return out

    monkeypatch.setattr(service, "_write_document", spy)
    run(workspace)
    # 파일마다 커밋됐다면 밖에서 본 수가 1, 2, 3 으로 는다.
    assert seen == [1, 2, 3]


# --- 백필 (D31) -------------------------------------------------------------


def test_without_a_key_the_run_is_ok_and_vectors_stay_null(db, clean, workspace):
    """키가 없는 것은 오류가 아니라 정상 상태다 (D2). partial 로 부르면 정상이 경보가 된다."""
    got = run(workspace, key="")
    assert got["status"] == "ok"
    assert got["chunks_embedded"] == 0
    assert got["chunks_pending"] == 3
    assert all(r["embedding"] is None for r in chunks(db))
    assert service.kb_status(DSN, PROJECT)["chunks_without_embedding"] == 3


def test_backfill_stops_at_the_first_failure(db, clean, workspace, monkeypatch):
    """인증·한도 실패는 남은 청크에서도 똑같이 실패한다. 계속하면 실패 호출만 는다."""
    calls: list[int] = []

    def boom(texts, api_key):
        calls.append(1)
        raise RuntimeError("401 Unauthorized")

    monkeypatch.setattr(service, "_embed", boom)
    got = run(workspace, key="sk-not-real")
    assert got["status"] == "partial"
    assert got["chunks_embedded"] == 0
    assert len(calls) == 1
    row = db.execute("SELECT * FROM kb_ingest_runs WHERE id = %s", (got["run_id"],)).fetchone()
    assert row["status"] == "partial"
    assert "401" in row["error"]
    # 텍스트 색인 결과는 백필 실패로 되돌아가지 않는다 (D31 이 D32 에 건 제약).
    assert len(docs(db)) == 3


def test_backfill_fills_null_vectors_only(db, clean, workspace, monkeypatch):
    monkeypatch.setattr(service, "_embed", lambda texts, key: [[0.0] * 1536 for _ in texts])
    got = run(workspace, key="sk-not-real")
    assert got["status"] == "ok"
    assert got["chunks_embedded"] == 3
    assert got["chunks_pending"] == 0
    assert service.kb_status(DSN, PROJECT)["chunks_without_embedding"] == 0

    # 이미 값이 있는 벡터는 다시 계산하지 않는다.
    again = run(workspace, key="sk-not-real")
    assert again["chunks_embedded"] == 0


def test_partial_run_still_applies_deletions(db, clean, workspace, monkeypatch):
    """D32 가 삭제를 백필 앞에 둔 이유가 이 결과다 — partial 이어도 삭제는 반영된다.

    **이 검사가 잠그는 것은 순서가 아니라 결과다.** 지금 구현은 백필 실패에서
    파이프라인을 끊지 않으므로 두 순서가 관측상 같다 — 실제로 삭제 블록을 백필 뒤로
    옮겨 보니 이 검사가 그대로 통과했다. 순서를 어겨도 삭제를 건너뛰게 되는 것은
    누군가 백필 실패에서 일찍 빠져나가게 고칠 때이고, 그때 이 검사가 문다.
    """
    run(workspace)
    (workspace / "docs" / "a.md").unlink()
    monkeypatch.setattr(service, "_embed", lambda t, k: (_ for _ in ()).throw(RuntimeError("nope")))
    got = run(workspace, key="sk-not-real")
    assert got["status"] == "partial"
    assert got["files_deleted"] == 1
    assert "docs/a.md" not in [r["path"] for r in docs(db)]


def test_vector_literal_round_trips(db, clean, workspace, monkeypatch):
    """D31 개정. 어댑터를 버린 대가를 이 검사가 갚는다.

    손으로 만든 텍스트 형식은 아무도 검사하지 않는 두 번째 직렬화가 될 수 있다.
    알려진 벡터를 넣고 다시 읽어 값이 보존되는지 본다.
    """
    known = [0.5, -0.25, 0.125] + [0.0] * 1533
    monkeypatch.setattr(service, "_embed", lambda texts, key: [list(known) for _ in texts])
    run(workspace, key="sk-not-real")

    raw = db.execute(
        "SELECT c.embedding::text AS v FROM kb_chunks c"
        " JOIN kb_documents d ON d.id = c.document_id"
        " WHERE d.project = %s ORDER BY c.id LIMIT 1",
        (PROJECT,),
    ).fetchone()["v"]
    got = [float(x) for x in raw.strip("[]").split(",")]
    assert len(got) == service.EMBED_DIM
    # 컬럼이 float4 라 서버가 정밀도를 자르는 것은 어댑터를 써도 같다.
    assert got[:3] == [0.5, -0.25, 0.125]
    assert all(v == 0.0 for v in got[3:])


# --- HTTP 얼굴 (D32) --------------------------------------------------------


def _client(workspace):
    from fastapi.testclient import TestClient

    from sillok import api
    from sillok.config import Config

    return TestClient(
        api.create_app(
            Config(
                database_url=DSN,
                host="127.0.0.1",
                port=8080,
                workspace=str(workspace),
                bearer_token="",
                openai_api_key="",
            )
        ),
        raise_server_exceptions=False,
    )


def test_http_ingest_returns_the_same_envelope(db, clean, workspace):
    """같은 Service 함수의 HTTP 얼굴이고 인자까지 같다 (D20·D30)."""
    res = _client(workspace).post("/v1/ingest", json={"project": PROJECT})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["files_seen"] == 3
    # error 는 응답에 싣지 않는다 (D32).
    assert "error" not in body["data"]


def test_http_ingest_rejects_a_concurrent_run_with_conflict(db, clean, workspace):
    """**발신 경로를 잠근다.** 이 핸들러가 없으면 락 거절이 포괄 예외에 걸려

    409 가 아니라 500 으로 나간다 — 상태 매핑 표만 봐서는 드러나지 않는 자리다 (D32).
    """
    with psycopg.connect(DSN, row_factory=dict_row) as holder:
        holder.autocommit = True
        holder.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s), hashtext(%s))",
            (service.LOCK_NAMESPACE, PROJECT),
        )
        try:
            res = _client(workspace).post("/v1/ingest", json={"project": PROJECT})
        finally:
            holder.execute(
                "SELECT pg_advisory_unlock(hashtext(%s), hashtext(%s))",
                (service.LOCK_NAMESPACE, PROJECT),
            )

    assert res.status_code == 409
    assert res.json() == {
        "ok": False,
        "error": {"code": "CONFLICT", "message": service.LOCKED_MESSAGE},
    }


def test_http_ingest_rejects_a_missing_project(db, clean, workspace):
    """D25 의 검증은 HTTP 얼굴에서도 같은 코드로 나간다."""
    res = _client(workspace).post("/v1/ingest", json={})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION"
