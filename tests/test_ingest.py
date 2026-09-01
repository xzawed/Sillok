"""5단계 ingest 의 순수 로직 (D30).

DB 가 필요 없다. 그래서 이 파일은 호스트에서도 전부 돈다 —
D22 가 남긴 숙제(`test` 이미지에 `docs/`·`adr/` 가 없다)를 `tmp_path` 로 우회한다.
작업 트리를 마운트하지 않는 이유는 그러면 검사가 저장소의 지금 내용에 묶여
문서를 고칠 때마다 깨지기 때문이다.
"""

from __future__ import annotations

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
    """path·project 를 섞으면 체크아웃 한 번이 전 문서를 변경으로 만든다."""
    assert ingest.content_hash("x") == ingest.content_hash("x")
    assert len(ingest.content_hash("x")) == 64
    assert ingest.content_hash("x").islower()


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

    files, skipped = ingest.scan(tmp_path)
    assert [f.path for f in files] == ["README.ko.md", "README.md", "adr/b.md", "docs/a.md"]
    # 제외한 것은 조용히 사라지지 않는다. D9 경로 밖은 애초에 대상이 아니라 보고하지 않는다.
    assert skipped == [ingest.Skipped("docs/skills/example.json", "not-md")]


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
    write(tmp_path, "docs/a.md", FM)
    write(tmp_path, ".git/docs/x.md", FM)
    write(tmp_path, "node_modules/docs/x.md", FM)
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
    """문자 단위로 자르는 경로는 만들지 않는다. 규칙에 종점이 있어야 한다."""
    long_line = "w" * (ingest.CHUNK_HARD_LIMIT + 500)
    got = ingest.chunk("# A\n\n" + long_line + "\n")
    assert [c.content for c in got] == [long_line]


def test_there_is_no_overlap():
    """같은 문단을 두 번 임베딩하면 비용만 늘고 Q8(6단계)을 키운다."""
    first, second = "a" * 700, "b" * 700
    got = ingest.chunk("# A\n\n" + first + "\n\n" + second + "\n")
    assert [c.content for c in got] == [first, second]
