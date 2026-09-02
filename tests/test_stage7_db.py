"""7단계의 DB·파일시스템 경로 (D35–D41).

**여기는 D22 의 `--profile test` 에서만 돈다.** DB 가 필요하고, D36 의 걸음은
`O_NOFOLLOW`·`O_DIRECTORY` 가 있는 플랫폼을 전제한다 — 호스트(Windows)에서 skip 되는 것이 정상이다.

허용 목록은 `kb_documents` 이므로 행은 **실제 ingest 로** 만든다. 손으로 INSERT 하면
색인이 넣지 않는 모양의 행으로 검사가 통과할 수 있다.
"""

from __future__ import annotations

import psycopg
import pytest
from psycopg.rows import dict_row

from sillok import ingest as ingest_rules
from sillok import service, workspace

from dbcheck import DSN, needs_db

PROJECT = "t_step7"
FM = "---\ntitle: T\ndoc_type: other\nstatus: current\nmodule: null\n---\n\n"
ONE = FM + "# 하나\n\n본문 한 줄 가나다\n"

pytestmark = [
    needs_db,
    pytest.mark.skipif(
        not workspace.flags_supported(),
        reason="O_NOFOLLOW / O_DIRECTORY 가 없는 플랫폼이다 (D36). --profile test 에서 돈다",
    ),
]


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
def ws(tmp_path, clean):
    """작은 workspace 를 만들어 실제로 색인한다. 이 트리가 곧 뿌리다 (D37)."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "one.md").write_text(ONE, encoding="utf-8")
    (tmp_path / "docs" / "big.md").write_text(
        FM + "".join(f"{i}번째 줄 가나다\n" for i in range(900)), encoding="utf-8"
    )
    (tmp_path / "docs" / "crlf.md").write_bytes(
        (FM + "# 씨알엘에프\n\n줄 끝이 다르다\n").replace("\n", "\r\n").encode("utf-8")
    )
    service.ingest(DSN, PROJECT, str(tmp_path))
    return tmp_path


def read_file(ws, path, offset=0):
    return service.get_file(DSN, PROJECT, path, offset, str(ws))


def propose(ws, path, body, base_hash=None):
    request = {"project": PROJECT, "path": path, "body": body}
    if base_hash is not None:
        request["base_hash"] = base_hash
    return service.save_doc(DSN, request, str(ws))["proposal"]


# --- get_file (D36) ----------------------------------------------------------


def test_indexed_file_comes_back_whole(ws):
    got = read_file(ws, "docs/one.md")
    assert got["text"] == ONE
    assert got["project"] == PROJECT and got["path"] == "docs/one.md"
    assert got["offset"] == 0
    assert got["total_bytes"] == len(ONE.encode("utf-8"))
    assert got["next_offset"] == got["total_bytes"]
    assert got["truncated"] is False


def test_text_is_raw_bytes_not_normalized(ws):
    """`get_file` 의 창은 원본 바이트다 — 세 숫자가 바이트이므로 (D41)."""
    got = read_file(ws, "docs/crlf.md")
    assert "\r\n" in got["text"], "정규화하면 offset 이 무엇의 바이트인지 사라진다"
    assert got["total_bytes"] == (ws / "docs" / "crlf.md").stat().st_size


def test_unindexed_path_is_not_found(ws):
    """색인이 곧 허용 목록이다 (D36). 파일이 있어도 행이 없으면 없는 것이다."""
    (ws / "docs" / "ghost.txt").write_text("색인 밖", encoding="utf-8")
    (ws / ".env").write_text("SECRET=1", encoding="utf-8")
    for path in ("docs/ghost.txt", ".env", "docs/none.md"):
        with pytest.raises(service.NotFound):
            read_file(ws, path)


@pytest.mark.parametrize("path", ["", "docs/one.md/", "docs//one.md", "./docs/one.md", "DOCS/ONE.MD"])
def test_path_must_match_the_row_byte_for_byte(ws, path):
    """정규화 대상이 아니라 그냥 행이 없는 것이다 (D36 가장자리)."""
    with pytest.raises(service.NotFound):
        read_file(ws, path)


def test_offset_at_the_end_is_the_end(ws):
    total = read_file(ws, "docs/one.md")["total_bytes"]
    got = read_file(ws, "docs/one.md", total)
    assert got["text"] == ""
    assert got["next_offset"] == total
    assert got["truncated"] is False


def test_offset_past_the_end_is_validation(ws):
    total = read_file(ws, "docs/one.md")["total_bytes"]
    with pytest.raises(service.ValidationFailed):
        read_file(ws, "docs/one.md", total + 1)


def test_offset_off_a_character_boundary_is_validation(ws):
    raw = ONE.encode("utf-8")
    mid = next(i for i, byte in enumerate(raw) if byte & 0xC0 == 0x80)
    with pytest.raises(service.ValidationFailed):
        read_file(ws, "docs/one.md", mid)


def test_windows_tile_the_whole_file(ws):
    """창을 이어 붙이면 파일 전체다. 큰 문서를 읽지 못하게 만들지도 않는다 (D36)."""
    path, offset, parts = "docs/big.md", 0, []
    while True:
        window = read_file(ws, path, offset)
        parts.append(window["text"])
        if not window["truncated"]:
            break
        offset = window["next_offset"]
    assert "".join(parts) == (ws / "docs" / "big.md").read_text(encoding="utf-8")
    assert len(parts) > 1, "한 창에 다 들어가면 이 검사가 아무것도 보지 않는다"
    assert all(len(part) <= workspace.WINDOW_CHARS for part in parts)


def test_a_row_that_became_a_symlink_is_not_found(ws):
    """행은 낡을 수 있다 (D36). 걸음이 열지 못할 뿐 행은 남는다."""
    (ws / "secret.txt").write_text("비밀", encoding="utf-8")
    target = ws / "docs" / "one.md"
    target.unlink()
    target.symlink_to(ws / "secret.txt")
    with pytest.raises(service.NotFound):
        read_file(ws, "docs/one.md")


def test_a_symlinked_directory_component_is_not_found(ws):
    """**성분마다 내려가는 이유다.** 마지막만 막는 방어는 여기서 통과한다 (D36)."""
    (ws / "elsewhere").mkdir()
    (ws / "elsewhere" / "one.md").write_text("남의 본문", encoding="utf-8")
    real = ws / "docs"
    (ws / "docs_moved").mkdir()
    for item in real.iterdir():
        item.rename(ws / "docs_moved" / item.name)
    real.rmdir()
    real.symlink_to(ws / "elsewhere", target_is_directory=True)
    with pytest.raises(service.NotFound):
        read_file(ws, "docs/one.md")


def test_a_deleted_file_is_not_found_but_the_row_stays(ws, db):
    (ws / "docs" / "one.md").unlink()
    with pytest.raises(service.NotFound):
        read_file(ws, "docs/one.md")
    row = db.execute(
        "SELECT path FROM kb_documents WHERE project = %s AND path = %s",
        (PROJECT, "docs/one.md"),
    ).fetchone()
    assert row is not None, "get_file 의 404 와 행이 없는 것은 다르다 (D36)"


# --- save_doc (D38 · D40 · D41) ----------------------------------------------


def test_identical_body_is_an_empty_diff(ws):
    got = propose(ws, "docs/one.md", ONE)
    assert got["exists"] is True
    assert got["diff"] == ""
    assert got["body"] == ONE


def test_crlf_file_and_lf_body_are_the_same_content(ws):
    """해시와 diff 가 같은 텍스트를 본다 (D41). 아니면 응답이 자기모순이 된다."""
    raw = (ws / "docs" / "crlf.md").read_bytes()
    normalized = ingest_rules.normalize(raw, "docs/crlf.md")
    got = propose(ws, "docs/crlf.md", normalized, f"sha256:{ingest_rules.content_hash(normalized)}")
    assert got["diff"] == "", "정규화가 한쪽에만 걸리면 전 줄이 바뀐 것으로 보인다"


def test_changed_body_produces_a_unified_diff(ws):
    got = propose(ws, "docs/one.md", ONE.replace("본문 한 줄", "본문 두 줄"))
    assert got["diff"].startswith("--- a/docs/one.md\n+++ b/docs/one.md\n")
    assert "-본문 한 줄 가나다" in got["diff"]
    assert "+본문 두 줄 가나다" in got["diff"]


def test_save_doc_does_not_touch_the_file(ws):
    """v1 은 제안까지다. Git 에 쓰지 않는다 (D3·D38) — §9 의 완료 조건이다."""
    before = (ws / "docs" / "one.md").read_bytes()
    propose(ws, "docs/one.md", "완전히 다른 본문\n")
    assert (ws / "docs" / "one.md").read_bytes() == before


def test_matching_base_hash_passes(ws):
    digest = ingest_rules.content_hash(ONE)
    got = propose(ws, "docs/one.md", ONE + "덧붙임\n", f"sha256:{digest}")
    assert got["exists"] is True and got["diff"] != ""


def test_stale_base_hash_is_a_conflict(ws):
    (ws / "docs" / "one.md").write_text(ONE + "누군가 먼저 고쳤다\n", encoding="utf-8")
    with pytest.raises(service.BaseHashMismatch) as exc:
        propose(ws, "docs/one.md", ONE, f"sha256:{ingest_rules.content_hash(ONE)}")
    assert str(exc.value) == service.BASE_HASH_MESSAGE
    assert service.LOCKED_MESSAGE != service.BASE_HASH_MESSAGE


def test_base_hash_is_compared_against_the_file_not_the_row(ws, db):
    """행은 낡을 수 있다 (D36). 비교 상대는 **지금 파일**이다 (D41)."""
    changed = ONE + "색인 뒤에 바뀌었다\n"
    (ws / "docs" / "one.md").write_text(changed, encoding="utf-8")
    row = db.execute(
        "SELECT content_hash FROM kb_documents WHERE project = %s AND path = %s",
        (PROJECT, "docs/one.md"),
    ).fetchone()
    assert row["content_hash"] == ingest_rules.content_hash(ONE), "전제: 행은 옛 해시를 들고 있다"

    got = propose(ws, "docs/one.md", changed, f"sha256:{ingest_rules.content_hash(changed)}")
    assert got["diff"] == ""


def test_missing_file_is_absence_not_empty(ws):
    """행은 있는데 파일이 없다 — `exists: false` 이고 `/dev/null` 에서의 추가다 (D41)."""
    (ws / "docs" / "one.md").unlink()
    got = propose(ws, "docs/one.md", "새 본문\n")
    assert got["exists"] is False
    assert got["diff"].startswith("--- /dev/null\n+++ b/docs/one.md\n")


def test_missing_file_with_a_base_hash_is_a_conflict(ws):
    """사라진 것은 바뀐 것의 부분집합이다 (D41)."""
    (ws / "docs" / "one.md").unlink()
    with pytest.raises(service.BaseHashMismatch):
        propose(ws, "docs/one.md", "새 본문\n", f"sha256:{ingest_rules.content_hash(ONE)}")


def test_unindexed_path_cannot_be_proposed(ws):
    """새 문서 제안은 v1 비범위다 (D38). 색인된 경로만 고칠 수 있다."""
    (ws / "docs" / "fresh.md").write_text("아직 색인되지 않았다\n", encoding="utf-8")
    with pytest.raises(service.NotFound):
        propose(ws, "docs/fresh.md", "본문\n")


# --- get_event (D35 · D39) ---------------------------------------------------


@pytest.fixture
def event(clean):
    return service.save_event(
        DSN,
        {
            "project": PROJECT,
            "kind": "failure",
            "title": "제목",
            "summary": "요약",
            "occurred_at": "2026-08-31T09:00:00Z",
            "result": "failure",
            "module": "auth",
            "root_cause": "풀 고갈",
            "resolution": "상한을 올렸다",
            "severity": "high",
            "payload": {"k": "v"},
            "created_by": "claude",
        },
    )["id"]


def test_get_event_returns_the_row(event):
    got = service.get_event(DSN, event, PROJECT)
    assert set(got) == set(service.EVENT_FIELDS)
    assert got["id"] == event
    # search_events 가 싣지 않아 "원문에서 본다" 로 넘긴 둘이 여기 있다.
    assert got["root_cause"] == "풀 고갈" and got["resolution"] == "상한을 올렸다"
    assert got["payload"] == {"k": "v"}
    assert got["occurred_at"] == "2026-08-31T09:00:00+00:00"
    assert got["created_at"].startswith("20")
    assert got["resolved_at"] is None


def test_another_projects_event_reads_like_a_missing_one(event):
    """없는 id 와 남의 id 는 같은 응답이다 (D35). 존재를 흘리지 않는다."""
    with pytest.raises(service.NotFound) as other:
        service.get_event(DSN, event, "t_step7_other")
    with pytest.raises(service.NotFound) as missing:
        service.get_event(DSN, event + 10_000_000, PROJECT)
    assert str(other.value) == str(missing.value) == service.NOT_FOUND_EVENT


def test_get_event_requires_a_project(event):
    with pytest.raises(service.ValidationFailed):
        service.get_event(DSN, event, None)
