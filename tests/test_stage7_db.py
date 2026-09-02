"""7단계의 DB·파일시스템 경로 (D35–D41).

**여기는 D22 의 `--profile test` 에서만 돈다.** DB 가 필요하고, D36 의 걸음은
`O_NOFOLLOW`·`O_DIRECTORY` 가 있는 플랫폼을 전제한다 — 호스트(Windows)에서 skip 되는 것이 정상이다.

허용 목록은 `kb_documents` 이므로 행은 **실제 ingest 로** 만든다. 손으로 INSERT 하면
색인이 넣지 않는 모양의 행으로 검사가 통과할 수 있다.
"""

from __future__ import annotations

from datetime import datetime

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
    """작은 workspace 를 만들어 실제로 색인한다. 이 트리가 곧 뿌리다 (D37).

    D9 의 세 갈래를 **전부** 담는다 — `docs/**` 만 두면 `docs/` 접두사를 요구하는
    구현이 통과한다. 줄 끝 셋(LF·CRLF·홀로 있는 CR)과 BOM, 0바이트도 여기서 만든다.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "adr").mkdir()
    (tmp_path / "docs" / "one.md").write_text(ONE, encoding="utf-8")
    (tmp_path / "docs" / "big.md").write_text(
        FM + "".join(f"{i}번째 줄 가나다\n" for i in range(900)), encoding="utf-8"
    )
    (tmp_path / "docs" / "crlf.md").write_bytes(
        (FM + "# 씨알엘에프\n\n줄 끝이 다르다\n").replace("\n", "\r\n").encode("utf-8")
    )
    # 선행 BOM 과 홀로 있는 CR — D30 정규화의 나머지 둘이다 (D41).
    (tmp_path / "docs" / "bom.md").write_bytes(
        "\ufeff".encode("utf-8") + (FM + "# 봄\n\n본문\n").encode("utf-8")
    )
    (tmp_path / "docs" / "cr.md").write_bytes(
        (FM + "# 시알\n\n본문\n").replace("\n", "\r").encode("utf-8")
    )
    (tmp_path / "adr" / "0001-t.md").write_text(FM + "# 결정\n\n본문\n", encoding="utf-8")
    # 루트 README* 는 front matter 를 갖지 않는다 (D29). 메타는 경로와 첫 H1 에서 나온다.
    (tmp_path / "README.md").write_text("# 루트 리드미\n\n본문\n", encoding="utf-8")
    (tmp_path / "README.empty.md").write_bytes(b"")
    run = service.ingest(DSN, PROJECT, str(tmp_path))
    assert run["status"] == "ok", run
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


def test_a_row_that_became_a_symlink_is_not_found(ws, db):
    """행은 낡을 수 있다 (D36). 걸음이 열지 못할 뿐 **행은 남는다**."""
    (ws / "secret.txt").write_text("비밀", encoding="utf-8")
    target = ws / "docs" / "one.md"
    target.unlink()
    target.symlink_to(ws / "secret.txt")
    with pytest.raises(service.NotFound):
        read_file(ws, "docs/one.md")
    row = db.execute(
        "SELECT path FROM kb_documents WHERE project = %s AND path = %s",
        (PROJECT, "docs/one.md"),
    ).fetchone()
    assert row is not None, "D36 이 말한 낡은 행이다 — 404 와 행이 없는 것은 다르다"


def test_a_valid_md_that_was_never_indexed_is_not_found(ws):
    """허용 목록은 경로 규칙이 아니라 **행**이다 (D36).

    D9 경로 아래의 `.md` 이고 파일도 실제로 있다 — 규칙을 요청 문자열 위에서 다시
    구현한 구현은 이것을 열어 준다. 색인이 곧 허용 목록이므로 없는 것이다.
    """
    (ws / "docs" / "fresh.md").write_text(FM + "# 새 문서\n\n색인 뒤에 생겼다\n", encoding="utf-8")
    with pytest.raises(service.NotFound):
        read_file(ws, "docs/fresh.md")


def test_another_projects_path_is_not_found(ws):
    """허용 목록은 `(project, path)` 쌍이다 (D36). path 하나로 남의 나무를 읽지 않는다."""
    with pytest.raises(service.NotFound):
        service.get_file(DSN, PROJECT + "_other", "docs/one.md", 0, str(ws))


def test_root_readme_and_adr_open_too(ws):
    """`docs/` 접두사를 요구하지 않는다 — D9 는 셋을 색인한다."""
    assert read_file(ws, "README.md")["text"].startswith("# 루트 리드미")
    assert read_file(ws, "adr/0001-t.md")["text"].endswith("# 결정\n\n본문\n")


def test_zero_byte_file_is_the_end_not_an_error(ws):
    """D36 가장자리 표의 0바이트 줄 — 허용 목록부터 창까지 전부 지나서 그렇게 나와야 한다."""
    assert read_file(ws, "README.empty.md") == {
        "project": PROJECT,
        "path": "README.empty.md",
        "text": "",
        "offset": 0,
        "next_offset": 0,
        "total_bytes": 0,
        "truncated": False,
    }


def test_an_indexed_path_that_became_a_directory_is_not_found(ws):
    """신원은 경로가 아니라 서술자다 (D36 4번) — 디렉터리는 열린 뒤 `fstat` 에서 걸린다."""
    target = ws / "docs" / "one.md"
    target.unlink()
    target.mkdir()
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


def test_the_body_is_normalized_too(ws):
    """한쪽만 정규화하면 자기모순이 방향만 바꿔 돌아온다 (D41).

    앞의 검사는 **이미 LF 인** 본문을 보냈다. 여기서는 파일도 본문도 CRLF 다 —
    파일만 정규화하는 구현은 여기서 전 줄이 바뀐 diff 를 낸다 (Grok 지적).
    """
    raw = (ws / "docs" / "crlf.md").read_bytes()
    normalized = ingest_rules.normalize(raw, "docs/crlf.md")
    got = propose(
        ws, "docs/crlf.md", raw.decode("utf-8"), f"sha256:{ingest_rules.content_hash(normalized)}"
    )
    assert got["diff"] == ""
    assert got["body"] == normalized, "응답의 body 는 정규화를 지난 제안이다"


@pytest.mark.parametrize("path", ["docs/bom.md", "docs/cr.md"])
def test_bom_and_lone_cr_are_the_same_content(ws, path):
    """D30 정규화는 셋이다 — 선행 BOM 제거, CRLF 와 **홀로 있는 CR** 을 LF 로 (D41)."""
    normalized = ingest_rules.normalize((ws / path).read_bytes(), path)
    got = propose(ws, path, normalized, f"sha256:{ingest_rules.content_hash(normalized)}")
    assert got["diff"] == "", path


def test_a_symlinked_file_is_absence_too(ws):
    """부재는 사라진 것만이 아니다 — 걸음이 열지 못하는 것도 부재다 (D41)."""
    (ws / "secret.txt").write_text("비밀", encoding="utf-8")
    target = ws / "docs" / "one.md"
    target.unlink()
    target.symlink_to(ws / "secret.txt")

    got = propose(ws, "docs/one.md", "새 본문\n")
    assert got["exists"] is False
    assert got["diff"].startswith("--- /dev/null\n")
    assert "비밀" not in got["diff"], "링크 너머의 내용이 제안에 실리면 안 된다"
    with pytest.raises(service.BaseHashMismatch):
        propose(ws, "docs/one.md", "새 본문\n", f"sha256:{ingest_rules.content_hash(ONE)}")


def test_the_skill_heuristic_is_not_a_rejection_rule(ws):
    """D38: 기계적으로 판정할 수 없는 것은 계약에서 뺐다.

    `날짜별 시도가 3건 이상` 은 Skill 의 **안내**이고 API 는 그것으로 거절하지 않는다.
    거절하면 그 임의가 곧 계약처럼 인용된다.
    """
    tries = "".join(f"- 2026-09-0{i} 시도 {i}: 실패\n" for i in (1, 2, 3))
    got = propose(ws, "docs/one.md", ONE + tries)
    assert got["exists"] is True
    assert "+- 2026-09-01 시도 1: 실패" in got["diff"]


def test_the_proposal_echoes_the_request_and_the_whole_body(ws):
    """`body` 는 문서 전체다 — 조각을 보내도 서버가 파일에 붙이지 않는다 (D38)."""
    fragment = "# 조각만 보낸다\n"
    got = propose(ws, "docs/one.md", fragment)
    assert got["project"] == PROJECT and got["path"] == "docs/one.md"
    assert got["body"] == fragment
    assert "-# 하나" in got["diff"], "서버가 조각을 붙이면 삭제가 보이지 않는다"


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


def test_an_empty_project_is_validation_not_a_miss(event):
    """빈 문자열은 라벨이 아니다 (D25). 404 로 접으면 **project 를 안 줬다**와
    **남의 것이다**가 같은 답이 되어 D35 가 지키려던 구분이 사라진다."""
    with pytest.raises(service.ValidationFailed):
        service.get_event(DSN, event, "")


def test_get_event_carries_every_saved_field(clean):
    """D39: 저장 계약의 필드 + `id` + `created_at`.

    기대 목록을 **구현 상수에서 가져오지 않는다** — 둘이 함께 빠지면 검사가
    아무것도 보지 않는다 (Grok 지적).
    """
    body = {
        "project": PROJECT,
        "module": "auth",
        "kind": "incident",
        "title": "제목",
        "summary": "요약",
        "root_cause": "원인",
        "resolution": "조치",
        "result": "partial",
        "severity": "critical",
        "occurred_at": "2026-08-31T09:00:00Z",
        "resolved_at": "2026-08-31T10:30:00Z",
        "source": "manual",
        "related_doc_path": "docs/one.md",
        "payload": {"k": [1, 2]},
        "created_by": "claude",
    }
    got = service.get_event(DSN, service.save_event(DSN, body)["id"], PROJECT)

    assert set(got) == set(body) | {"id", "created_at"}
    for field, value in body.items():
        if field in ("occurred_at", "resolved_at"):
            continue
        assert got[field] == value, field
    # 시각은 ISO-8601 문자열이고 UTC 로 정규화돼 있다 (D25 가 오프셋을 요구한다).
    assert got["occurred_at"] == "2026-08-31T09:00:00+00:00"
    assert got["resolved_at"] == "2026-08-31T10:30:00+00:00"
    assert datetime.fromisoformat(got["created_at"]).tzinfo is not None
