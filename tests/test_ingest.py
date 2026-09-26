"""5단계 ingest 의 순수 로직 (D30).

DB 가 필요 없다. 그래서 이 파일은 호스트에서도 전부 돈다 —
D22 가 남긴 숙제(`test` 이미지에 `docs/`·`adr/` 가 없다)를 `tmp_path` 로 우회한다.
작업 트리를 마운트하지 않는 이유는 그러면 검사가 저장소의 지금 내용에 묶여
문서를 고칠 때마다 깨지기 때문이다.
"""

from __future__ import annotations

import hashlib
import os
import sys

import pytest

from sillok import ingest

FM = "---\ntitle: T\ndoc_type: other\nstatus: current\nmodule: null\n---\n\n"


def write(root, rel, text, encoding="utf-8"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode(encoding) if isinstance(text, str) else text)
    return path


# --- 정규화와 해시 (D30 §2) -------------------------------------------------


def test_line_endings_do_not_change_the_hash():
    """같은 커밋을 두 OS 에서 색인하면 전량 재색인이 되던 것을 막는 규칙이다.

    이 저장소의 마크다운은 인덱스가 LF 이고 작업 트리가 CRLF 다.
    """
    lf = ingest.normalize(b"# T\n\n\xea\xb0\x80\n")
    crlf = ingest.normalize(b"# T\r\n\r\n\xea\xb0\x80\r\n")
    cr = ingest.normalize(b"# T\r\r\xea\xb0\x80\r")
    assert lf == crlf == cr
    assert ingest.content_hash(lf) == ingest.content_hash(crlf)


def test_leading_bom_is_stripped():
    """게이트의 front matter 정규식이 선행 BOM 을 허용한다 (D29).

    벗기지 않으면 같은 문서를 게이트는 읽고 ingest 는 못 읽는다.
    """
    assert ingest.normalize("﻿# T\n".encode()) == "# T\n"


def test_hash_is_a_function_of_the_body_only():
    """path·project 를 섞으면 체크아웃 한 번이 전 문서를 변경으로 만든다.

    알려진 값을 못 박는다. 같은 입력이 같은 값을 낸다는 것만 보면
    해시를 상수로 바꿔도 이 검사가 초록으로 남는다.
    """
    known = "0b46e6c5da8bebfeae63a03e8ff0b3f1d0f8cf7d2ef1e37f9f8a6a3d2f0a5b09"
    assert ingest.content_hash("가나다\n") == hashlib.sha256("가나다\n".encode()).hexdigest()
    assert len(ingest.content_hash("x")) == 64
    assert ingest.content_hash("x").islower()
    # 본문이 다르면 값이 다르다.
    assert ingest.content_hash("a") != ingest.content_hash("b")
    assert known != ingest.content_hash("a")  # 상수가 아니다


def test_nothing_else_is_normalized():
    """후행 공백을 다듬지 않고 마지막 개행을 더하지도 빼지도 않는다."""
    assert ingest.normalize(b"a  \n\nb") == "a  \n\nb"


def test_undecodable_bytes_fail_the_run():
    """그 파일만 건너뛰지 않는다 — 조용히 빠진 문서는 검색 0건과 구분되지 않는다."""
    with pytest.raises(ingest.DecodeFailed):
        ingest.normalize(b"\xff\xfe\x00binary", "docs/x.md")


# --- 스캔 (D30 §1) ----------------------------------------------------------


def test_scan_takes_only_md_inside_the_d9_paths(tmp_path):
    write(tmp_path, "docs/a.md", FM)
    write(tmp_path, "adr/b.md", FM)
    write(tmp_path, "README.md", "# T\n")
    write(tmp_path, "README.ko.md", "# T\n")
    write(tmp_path, "docs/skills/example.json", "{}")
    write(tmp_path, "src/x.md", FM)        # D9 경로 밖
    write(tmp_path, "notes.md", "# T\n")   # 루트지만 README 가 아니다
    write(tmp_path, "docs/UPPER.MD", FM)   # 대소문자를 접지 않는다

    files, skipped = ingest.scan(tmp_path)
    assert [f.path for f in files] == ["README.ko.md", "README.md", "adr/b.md", "docs/a.md"]
    # 제외한 것은 조용히 사라지지 않는다. D9 경로 밖은 애초에 대상이 아니라 보고하지 않는다.
    assert skipped == [
        ingest.Skipped("docs/UPPER.MD", "not-md"),
        ingest.Skipped("docs/skills/example.json", "not-md"),
    ]


def test_scan_order_is_utf8_byte_ascending(tmp_path):
    """파일시스템이 주는 순서에 기대지 않는다 — 부분 run 이 재현돼야 한다 (D23 선례)."""
    for name in ("docs/z.md", "docs/a.md", "docs/가.md", "docs/M.md"):
        write(tmp_path, name, FM)
    files, _ = ingest.scan(tmp_path)
    paths = [f.path for f in files]
    assert paths == sorted(paths, key=lambda p: p.encode("utf-8"))


def test_scan_uses_posix_separators(tmp_path):
    """같은 레포가 OS 마다 다른 문서 정체성을 갖지 않게 한다 (UNIQUE (project, repo, path))."""
    write(tmp_path, "docs/skills/deep/x.md", FM)
    files, _ = ingest.scan(tmp_path)
    assert [f.path for f in files] == ["docs/skills/deep/x.md"]


def test_scan_skips_dot_git_and_node_modules(tmp_path):
    """주입은 **D9 경로 안**이어야 이 규칙을 문다.

    루트의 `.git/` 은 in_index_paths 가 이미 떨어뜨리므로 skip 규칙을 지워도 초록이다.
    """
    write(tmp_path, "docs/a.md", FM)
    write(tmp_path, "docs/.git/x.md", FM)
    write(tmp_path, "docs/node_modules/x.md", FM)
    files, skipped = ingest.scan(tmp_path)
    assert [f.path for f in files] == ["docs/a.md"]
    assert skipped == []


def test_symlinks_are_reported_not_followed(tmp_path):
    """workspace 밖을 가리키는 링크 하나가 D9 경로를 무의미하게 만든다."""
    outside = tmp_path.parent / "outside.md"
    outside.write_text("# out\n", encoding="utf-8")
    write(tmp_path, "docs/real.md", FM)
    link = tmp_path / "docs" / "link.md"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 수 없다")

    files, skipped = ingest.scan(tmp_path)
    assert [f.path for f in files] == ["docs/real.md"]
    assert skipped == [ingest.Skipped("docs/link.md", "symlink")]


def _link(link, target, *, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("이 환경에서는 심볼릭 링크를 만들 수 없다")


def test_a_linked_top_level_docs_is_reported_not_dropped(tmp_path):
    """`docs` 자체가 링크면 `docs/` 접두 판정에 걸리지 않아 **조용히 사라졌다** (2026-09-26 감사).
    그 아래 행이 전부 삭제 후보가 됐다 — D30 §1 의 `조용히 사라지지 않는다` 가 한 층 위에서 깨진 것이다."""
    real = tmp_path.parent / f"{tmp_path.name}-real"
    write(real, "a.md", FM)
    write(tmp_path, "adr/b.md", FM)
    _link(tmp_path / "docs", real, directory=True)

    files, skipped = ingest.scan(tmp_path)
    assert [f.path for f in files] == ["adr/b.md"]
    assert skipped == [ingest.Skipped("docs", "symlink")]


def test_a_top_level_link_outside_the_d9_paths_is_not_reported(tmp_path):
    """대조군. `docsx` 는 D9 경로가 아니다 — 판정은 `이름 + '/'` 가 D9 인가이지 접두 문자열이 아니다."""
    real = tmp_path.parent / f"{tmp_path.name}-real"
    write(real, "a.md", FM)
    write(tmp_path, "docs/a.md", FM)
    _link(tmp_path / "docsx", real, directory=True)

    _, skipped = ingest.scan(tmp_path)
    assert skipped == []


fifo_only = pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO 를 만들 수 없는 플랫폼이다")


@fifo_only
def test_a_fifo_named_md_is_skipped_as_not_regular(tmp_path):
    """FIFO 는 받아들인 내용이 아니다 (D70 ①). `.md` 가 아니면 확장자 판정 그대로 `not-md` 다."""
    write(tmp_path, "docs/a.md", FM)
    os.mkfifo(tmp_path / "docs" / "x.md")
    os.mkfifo(tmp_path / "docs" / "y.json")

    files, skipped = ingest.scan(tmp_path)
    assert [f.path for f in files] == ["docs/a.md"]
    assert skipped == [
        ingest.Skipped("docs/x.md", "not-regular"),
        ingest.Skipped("docs/y.json", "not-md"),
    ]


undecodable_names = pytest.mark.skipif(
    sys.platform == "win32" or os.fsencode("\udcff") != b"\xff",
    reason="이름에 비-UTF-8 바이트를 넣을 수 있는 파일시스템 인코딩이 아니다",
)


def _raw(root, rel: bytes) -> None:
    path = os.path.join(os.fsencode(root), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(FM.encode("utf-8"))


@undecodable_names
def test_an_undecodable_non_md_name_is_skipped_with_a_display_path(tmp_path):
    """예전에는 정렬 키 `encode("utf-8")` 가 터져 **이미지 하나로 매 run 이 사유 없이** `failed` 였다 (D70 ②).
    표시형은 삭제 키가 아니다 — `exact` 가 그것을 싣는다."""
    write(tmp_path, "docs/a.md", FM)
    _raw(tmp_path, b"docs/\xff.json")

    files, skipped = ingest.scan(tmp_path)
    assert [f.path for f in files] == ["docs/a.md"]
    assert skipped == [ingest.Skipped("docs/\\udcff.json", "not-md", exact=False)]


@undecodable_names
def test_an_undecodable_md_name_is_a_document_that_cannot_be_stored(tmp_path):
    """건너뛰면 옛 청크가 `ok` 인 채 남는다 — NUL 을 skip 으로 두지 않은 이유와 같다 (D30 §2 · D70 ②).
    스캔은 터뜨리지 않고 표시만 한다 — 실패는 정렬 순서의 제자리에서 service 가 낸다."""
    write(tmp_path, "docs/a.md", FM)
    _raw(tmp_path, b"docs/\xff.md")

    files, skipped = ingest.scan(tmp_path)
    assert [(f.path, f.storable) for f in files] == [("docs/a.md", True), ("docs/\udcff.md", False)]
    assert skipped == []
    assert "docs/\\udcff.md" in str(ingest.unstorable(files[1]))


def test_the_walk_does_not_descend_outside_the_d9_directories(tmp_path, monkeypatch):
    """색인 집합은 같고, 뿌리의 읽을 수 없는 디렉터리 하나가 run 을 실패시키지 않는다 (2026-09-26 리뷰).
    뿌리의 항목 자체는 본다 — 루트 README 와 최상위 `docs`·`adr` 링크가 거기 있다."""
    write(tmp_path, "docs/a.md", FM)
    write(tmp_path, "adr/b.md", FM)
    write(tmp_path, "README.md", "# r\n")
    write(tmp_path, "build/private/x.md", FM)
    write(tmp_path, "src/docs/y.md", FM)
    listed: list[str] = []
    real = os.scandir

    def recording(path):
        listed.append(os.path.relpath(path, tmp_path).replace(os.sep, "/"))
        return real(path)

    monkeypatch.setattr(ingest.os, "scandir", recording)
    files, _ = ingest.scan(tmp_path)
    assert [f.path for f in files] == ["README.md", "adr/b.md", "docs/a.md"]
    assert sorted(listed) == [".", "adr", "docs"]


@pytest.mark.skipif(sys.platform == "win32", reason="경로 길이 한도가 깊이보다 먼저 온다")
def test_a_deep_tree_does_not_hit_the_recursion_limit(tmp_path):
    """재귀 걸음은 깊은 나무에서 `RecursionError` 로 끝나고 그 사유에는 경로가 없다."""
    depth = sys.getrecursionlimit() + 50
    # `mkdir(parents=True)`·`os.makedirs` 도 재귀다 — 준비가 먼저 한도에 걸린다. 한 단씩 만든다.
    here = tmp_path / "docs"
    here.mkdir()
    for _ in range(depth):
        here = here / "d"
        here.mkdir()
    (here / "deep.md").write_text(FM, encoding="utf-8")
    rel = "docs/" + "d/" * depth + "deep.md"

    files, _ = ingest.scan(tmp_path)
    assert [f.path for f in files] == [rel]


# --- 진단 문자열의 표시형 (D32) ----------------------------------------------


def test_printable_escapes_what_can_forge_or_cut_a_line():
    """제어·줄 구분·양방향 서식·짝 없는 서로게이트. 경로의 줄바꿈이 첫 줄 규칙으로 사유를 잘랐고
    ESC 가 운영자 터미널에 그대로 닿았다 (2026-09-26 감사)."""
    raw = "docs/a\nb\x1b[1m\x7f\x85 ‮⁦\udcff.md"
    assert ingest.printable(raw) == (
        "docs/a\\x0ab\\x1b[1m\\x7f\\x85\\u2028\\u202e\\u2066\\udcff.md"
    )


def test_printable_leaves_ordinary_names_alone_and_is_idempotent():
    plain = "docs/한글 이름 (초안) — v2.md"
    assert ingest.printable(plain) == plain
    once = ingest.printable("docs/a\tb.md")
    assert ingest.printable(once) == once


# --- front matter 와 메타 (D30 §7 · D29) ------------------------------------


def test_front_matter_null_becomes_none():
    """색인 대상 문서가 전부 module: null 이다. 없으면 문자열 "null" 이 들어간다."""
    meta = ingest.derive_meta("docs/a.md", FM + "본문\n")
    assert meta == {"title": "T", "doc_type": "other", "status": "current", "module": None}


def test_front_matter_value_comment_is_stripped():
    text = "---\ntitle: T  # 주석\ndoc_type: api\nstatus: draft\nmodule: auth\n---\n\n본문\n"
    meta = ingest.derive_meta("docs/a.md", text)
    assert meta["title"] == "T"
    assert meta["module"] == "auth"


def test_missing_front_matter_falls_back_to_ddl_defaults():
    """D5 가 말하는 다른 project 에서는 front matter 가 없는 것이 정상이다."""
    meta = ingest.derive_meta("docs/a.md", "# 제목\n\n본문\n")
    assert meta["doc_type"] == "other"
    assert meta["status"] == "current"
    assert meta["module"] is None


def test_root_readme_meta_is_derived_from_the_path_and_first_h1():
    """D29. 루트 README* 는 front matter 를 갖지 않는다."""
    text = '<div align="center">\n\n# Sillok · 실록\n\n본문\n'
    assert ingest.derive_meta("README.md", text) == {
        "title": "Sillok · 실록",
        "doc_type": "readme",
        "status": "current",
        "module": None,
    }
    # 두 README 의 H1 이 같아 title 이 겹친다. 받아들인 대가다 — 구분은 path 가 한다.
    assert ingest.derive_meta("README.ko.md", text)["title"] == "Sillok · 실록"


def test_h1_inside_a_code_fence_is_not_a_title():
    assert ingest.first_h1("```\n# 가짜\n```\n\n# 진짜\n") == "진짜"


def test_h1_strips_inline_markup():
    assert ingest.first_h1("# **굵은** `코드` [링크](http://x)\n") == "굵은 코드 링크"


# --- 인라인 마크업 (D29 — 2026-09-26 감사 F099) ---------------------------------


@pytest.mark.parametrize(
    "raw, want",
    [
        # 코드 스팬 안은 글자 그대로다 — `event_stats` 가 `eventstats` 였다.
        ("`event_stats` 응답", "event_stats 응답"),
        ("루트 `README*`", "루트 README*"),
        ("`docs/**`·`adr/**`", "docs/**·adr/**"),
        ("``a`b_c``", "a`b_c"),
        ("`` a_b ``", "a_b"),
        ("`[not](url)`", "[not](url)"),
        # 링크·이미지는 표시 텍스트만, 그 텍스트도 같은 규칙을 탄다.
        ("[`a_b`](http://x) 끝", "a_b 끝"),
        ("![그림](a.png) 설명", "그림 설명"),
        # 강조는 짝이 맞는 구분자만 지운다.
        ("**검증하다**", "검증하다"),
        ("_이탤릭_", "이탤릭"),
        ("**굵은**다", "굵은다"),
        ("***a**", "*a"),
        # 단어 안의 `_` 는 글자다. 짝 없는 `*` 도 글자다.
        ("snake_case 이름", "snake_case 이름"),
        ("a_b_c 와 D30_x_y", "a_b_c 와 D30_x_y"),
        ("2*3", "2*3"),
        ("a ` b_c", "a ` b_c"),
        # 백슬래시 이스케이프는 그 글자다.
        (r"\*별\* 과 \_밑줄\_", "*별* 과 _밑줄_"),
    ],
)
def test_strip_inline_keeps_code_spans_and_strips_only_real_markup(raw, want):
    assert ingest.strip_inline(raw) == want


def test_heading_path_keeps_identifiers_inside_code_spans():
    pieces = ingest.chunk("## `event_stats` 응답\n\n본문\n")
    assert pieces[0].heading_path == "event_stats 응답"


# --- 메타 파서의 가장자리 (D29 · D30 §7 — 2026-09-26 감사 F020) --------------------


def test_tilde_is_not_null():
    """D30 §7 은 빈 값과 `null` 만 NULL 이다. 코드가 적힌 적 없는 `~` 까지 접고 있었다."""
    text = "---\ntitle: T\ndoc_type: other\nstatus: current\nmodule: ~\n---\n\n본문\n"
    assert ingest.derive_meta("docs/a.md", text)["module"] == "~"
    assert ingest.derive_meta("docs/a.md", FM + "본문\n")["module"] is None


def test_an_empty_title_with_front_matter_stays_null():
    """H1 유도는 front matter 가 **없을 때만**이다 (D30 §7). front matter 안의 `# 주석` 줄도 제목이 아니다."""
    for title in ("", "null"):
        text = f"---\ntitle: {title}\n# 주석\ndoc_type: other\nstatus: current\nmodule: null\n---\n\n# 본문 제목\n"
        assert ingest.derive_meta("docs/a.md", text)["title"] is None


def test_an_h1_inside_an_html_block_is_not_a_title():
    """D29: HTML 블록은 지나가고 빈 줄에서 끝난다. 빈 줄 없이 블록 안에 든 `# ` 를 제목으로 잡았다."""
    assert ingest.first_h1('<div align="center">\n# 가짜\n\n# 진짜\n') == "진짜"
    assert ingest.first_h1('<div align="center">\n\n# Sillok · 실록\n') == "Sillok · 실록"
    # 6형이 아닌 태그는 블록을 열지 않는다.
    assert ingest.first_h1("<span>x</span>\n# 제목\n") == "제목"
    # 청크는 D30 §5 그대로 HTML 블록을 보지 않는다.
    assert [c.heading_path for c in ingest.chunk("<div>\n# 안\n본문\n")] == [None, "안"]


# --- 선형 파서 (Sonar S8786) --------------------------------------------------


def test_atx_heading_recognition_is_unchanged():
    assert ingest.chunk("####### 일곱\n본문\n")[0].heading_path is None
    assert ingest.chunk("#\t탭\n본문\n")[0].heading_path == "탭"
    assert ingest.chunk("###### 여섯\n본문\n")[0].heading_path == "여섯"
    # 빈 `# ` 도 첫 H1 이다 — 텍스트가 비어 NULL 이 되고 다음 H1 으로 넘어가지 않는다 (지금 동작 그대로).
    assert ingest.first_h1("# \n# 두번째\n") is None
    assert ingest.first_h1("#붙음\n") is None


def test_front_matter_comment_cut_is_unchanged():
    def value(v):
        meta, _ = ingest.split_front_matter(f"---\ntitle: {v}\n---\n")
        return meta["title"]

    assert value("T  # 주석") == "T"
    assert value("C# 가이드") == "C# 가이드"
    assert value("foo  # a # b") == "foo"
    # 콜론 뒤의 공백 다음 `#` 은 주석이다 — 값이 빈다 (게이트와 같다, 지금 동작 그대로).
    assert value("#맨앞") == ""


def test_a_long_whitespace_value_is_parsed_in_linear_time():
    """`\\s+#.*$` 는 `#` 없는 긴 공백에서 자리마다 다시 시도해 제곱 시간이 걸렸다."""
    import time

    text = "---\ntitle: T" + " " * 50_000 + "x\n---\n"
    started = time.perf_counter()
    meta, _ = ingest.split_front_matter(text)
    assert time.perf_counter() - started < 0.5
    assert meta["title"].endswith("x")


# --- 유도 규칙의 판 (D71) --------------------------------------------------------

# 규칙이 닿는 가장자리를 담은 고정 표본이다. 규칙을 바꾸는 변경은 그 경우를 여기에 더한다 (D71).
_DERIVATION_SAMPLE = {
    "README.md": '<div align="center">\n# 가짜\n\n# 진짜 `a_b` **굵게**\n\n소개\n',
    "docs/a.md": (
        "---\ntitle: T  # 주석\ndoc_type: other\nstatus: current\nmodule: ~\n---\n\n"
        "서두\n\n# 하나 `event_stats`\n\n본문 가\n\n### `README*` [링크](x) _기울임_\n\n본문 나\n\n"
        "```\n# 펜스 안\n```\n\n## snake_case 2*3 \\*별\\*\n\n본문 다\n\n제목\n===\n\n<div>\n# 블록 안\n</div>\n"
    ),
    "docs/b.md": "---\ntitle:\n# 주석\ndoc_type: api\nstatus: draft\nmodule: null\n---\n\n# 본문 제목\n\n본문\n",
    "docs/c.md": "<p>\n# 가짜\n</p>\n\n# 제목 ***a** \n\n본문\n",
}

# 판마다 digest. 규칙을 바꾸면 `RULES_VERSION` 을 올리고 새 판의 줄을 더한다 — 옛 줄은 지우지 않는다.
_DERIVATION_DIGEST = {
    1: "0bc6ab415edf261958ef9de743aac6f2fffa63f599cbdddb1453f3cddd1cadab",
}


def _derivation_digest() -> str:
    import json

    h = hashlib.sha256()
    for path in sorted(_DERIVATION_SAMPLE):
        text = _DERIVATION_SAMPLE[path]
        meta = ingest.derive_meta(path, text)
        _, body = ingest.split_front_matter(text)
        pieces = [[c.chunk_idx, c.heading_path, c.content] for c in ingest.chunk(body)]
        h.update(json.dumps([path, meta, pieces], ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return h.hexdigest()


def test_derivation_rules_are_pinned_to_their_version():
    """유도 규칙이 바뀌면 본문이 같은 문서는 판이 올라야만 다시 만들어진다 (D71).
    올리지 않고 바꾸면 여기서 운다 — 사람이 기억하는 길을 두지 않는다 (D31 이 버린 모양)."""
    assert ingest.RULES_VERSION in _DERIVATION_DIGEST, (
        f"RULES_VERSION {ingest.RULES_VERSION} 의 digest 가 없다 — 새 판의 줄을 더한다: {_derivation_digest()}"
    )
    assert _derivation_digest() == _DERIVATION_DIGEST[ingest.RULES_VERSION], (
        f"유도 규칙이 바뀌었다 — RULES_VERSION 을 올리고 새 판의 digest 를 더한다: {_derivation_digest()}"
    )


# --- 청크 (D30 §5) ----------------------------------------------------------


def test_heading_path_joins_with_the_separator():
    body = "# A\n\n본문1\n\n## B\n\n본문2\n"
    got = ingest.chunk(body)
    assert [(c.heading_path, c.content) for c in got] == [("A", "본문1"), ("A > B", "본문2")]


def test_text_before_the_first_heading_has_no_heading_path():
    got = ingest.chunk("서두\n\n# A\n\n본문\n")
    assert got[0].heading_path is None
    assert got[0].content == "서두"


def test_heading_line_is_not_in_the_content():
    """넣으면 tsv 생성식이 heading_path 와 이어 붙여 제목 토큰이 두 번 들어간다."""
    got = ingest.chunk("# A\n\n본문\n")
    assert got[0].content == "본문"


def test_skipped_heading_level_does_not_invent_a_title():
    got = ingest.chunk("# A\n\n x\n\n### C\n\n y\n")
    assert [c.heading_path for c in got] == ["A", "A > C"]


def test_setext_underline_is_not_a_heading():
    """front matter 를 뗀 자리와 수평선이 줄 스캐너에서 제목처럼 보이는 것을 막는다."""
    got = ingest.chunk("제목처럼 보이는 줄\n---\n\n본문\n")
    assert all(c.heading_path is None for c in got)


def test_atx_inside_a_code_fence_does_not_split():
    body = "# A\n\n```bash\n# 주석이지 제목이 아니다\nls\n```\n"
    got = ingest.chunk(body)
    assert len(got) == 1
    assert "# 주석이지 제목이 아니다" in got[0].content


def test_empty_section_makes_no_chunk():
    got = ingest.chunk("# A\n\n# B\n\n본문\n")
    assert [(c.heading_path, c.content) for c in got] == [("B", "본문")]


def test_chunk_idx_is_document_order_from_zero():
    got = ingest.chunk("# A\n\nx\n\n# B\n\ny\n\n# C\n\nz\n")
    assert [c.chunk_idx for c in got] == [0, 1, 2]


def test_blocks_are_not_split_below_the_hard_limit():
    """코드 펜스와 표가 한가운데서 잘리지 않는다. 실측 최장 표가 1330자다."""
    fence = "```\n" + "\n".join("x" * 60 for _ in range(20)) + "\n```"
    body = "# A\n\n" + fence + "\n"
    got = ingest.chunk(body)
    assert len(got) == 1
    assert got[0].content.count("```") == 2


def test_soft_limit_breaks_before_the_block_that_would_exceed_it():
    block = "y" * 700
    got = ingest.chunk("# A\n\n" + block + "\n\n" + block + "\n")
    assert len(got) == 2
    assert all(len(c.content) <= ingest.CHUNK_SOFT_LIMIT for c in got)


def test_hard_limit_splits_a_huge_block_at_line_boundaries():
    """천장이 없으면 거대한 코드 펜스 하나가 임베딩 요청 하나를 그만큼 키운다."""
    body = "# A\n\n" + "\n".join("z" * 100 for _ in range(80)) + "\n"
    got = ingest.chunk(body)
    assert len(got) > 1
    assert all(len(c.content) <= ingest.CHUNK_HARD_LIMIT for c in got)
    assert all(line == "z" * 100 for c in got for line in c.content.split("\n"))


def test_a_single_line_over_the_hard_limit_becomes_its_own_chunk():
    """문자 단위로 자르는 경로는 만들지 않는다 — 규칙에 종점이 있어야 한다.

    천장이 실제로 있다는 것은 위의 여러 줄 검사가 문다. 이 검사가 잠그는 것은 종점이다.
    """
    long_line = "w" * (ingest.CHUNK_HARD_LIMIT + 500)
    got = ingest.chunk("# A\n\n" + long_line + "\n")
    assert [c.content for c in got] == [long_line]


def test_there_is_no_overlap():
    """같은 문단을 두 번 임베딩하면 비용만 늘고 Q8(6단계)을 키운다."""
    first, second = "a" * 700, "b" * 700
    got = ingest.chunk("# A\n\n" + first + "\n\n" + second + "\n")
    assert [c.content for c in got] == [first, second]


def test_missing_front_matter_derives_the_title_from_the_first_h1():
    """D30 §7. 다른 project 에서는 front matter 가 없는 것이 정상이다.

    이것이 없으면 그 문서들의 title 이 전부 NULL 로 들어간다.
    """
    assert ingest.derive_meta("docs/a.md", "# 제목\n\n본문\n")["title"] == "제목"
    # front matter 가 있으면 그 값이 이긴다 — H1 로 덮어쓰지 않는다.
    assert ingest.derive_meta("docs/a.md", FM + "# 다른 제목\n\n본문\n")["title"] == "T"
    # 제목이 하나도 없으면 NULL 이다.
    assert ingest.derive_meta("docs/a.md", "본문뿐이다\n")["title"] is None


# --- 문서 본문의 NUL (D30 §2 — 2026-09-26 감사) ---------------------------------------------


def test_a_nul_in_the_body_is_a_decode_failure_that_names_the_file():
    """UTF-8 로는 멀쩡하지만 `text` 가 담지 못한다. 넘기면 청크 INSERT 가 DataError 로 터져
    경로 없는 500 이 되고 다음 run 들도 같은 파일에서 멈췄다. skip 이 아니다 — skip 은 삭제 후보가 아니라
    옛 청크가 `ok` 인 채 검색에 남는다."""
    with pytest.raises(ingest.DecodeFailed) as exc:
        ingest.normalize(b"# A\n\na\x00b\n", "docs/x.md")
    assert "docs/x.md" in str(exc.value)
