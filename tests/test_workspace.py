"""D36 의 걸음과 창.

창 계산은 순수 함수라 어디서나 돈다. **걸음은 그렇지 않다** —
`O_NOFOLLOW`·`O_DIRECTORY` 가 없는 호스트(Windows)에서는 D36 이 읽기를 금지하므로,
그쪽에서는 "읽지 않고 실패하는가" 만 확인하고 나머지는 `--profile test` 에서 돈다 (D22).
"""

from __future__ import annotations

import os

import pytest

from sillok import workspace

posix_only = pytest.mark.skipif(
    not workspace.flags_supported(),
    reason="O_NOFOLLOW / O_DIRECTORY 가 없는 플랫폼이다 (D36). D22 의 --profile test 에서 돈다",
)
windows_only = pytest.mark.skipif(
    workspace.flags_supported(), reason="이 플랫폼은 D36 의 걸음을 지원한다"
)


# --- 창 (순수) --------------------------------------------------------------


def test_empty_file_is_the_end_not_an_error():
    got = workspace.decode_window(b"", 0, 0)
    assert got == {
        "text": "",
        "offset": 0,
        "next_offset": 0,
        "total_bytes": 0,
        "truncated": False,
    }


def test_offset_at_the_end_is_the_end_not_an_error():
    """D36 가장자리 표: `offset == total_bytes` 는 끝이다."""
    got = workspace.decode_window(b"", 9, 9)
    assert got["text"] == ""
    assert got["next_offset"] == 9
    assert got["truncated"] is False


def test_offset_past_the_end_is_validation():
    with pytest.raises(workspace.OffsetInvalid):
        workspace.decode_window(b"", 10, 9)


def test_negative_offset_is_validation():
    with pytest.raises(workspace.OffsetInvalid):
        workspace.decode_window(b"", -1, 9)


def test_offset_off_a_character_boundary_is_validation():
    """관대한 디코더는 그 바이트들을 조용히 먹어 `next_offset` 이 영영 지나치게 만든다 (D36)."""
    raw = "가나다".encode("utf-8")
    with pytest.raises(workspace.OffsetInvalid):
        workspace.decode_window(raw[1:], 1, len(raw))


def test_broken_utf8_at_offset_zero_is_not_an_offset_problem():
    """offset 0 은 언제나 문자 경계다. 여기서 터지면 파일이 UTF-8 이 아니다 —
    계약에 답이 없으므로 D21 의 포괄 예외(INTERNAL)로 간다."""
    with pytest.raises(UnicodeDecodeError):
        workspace.decode_window(b"\xff\xfe", 0, 2)


def test_incomplete_tail_sequence_is_dropped():
    """끝의 불완전한 시퀀스는 버린다 — 그 글자는 **다음 창**이지 건너뛴 것이 아니다."""
    raw = ("가" * 10).encode("utf-8")
    got = workspace.decode_window(raw[:29], 0, len(raw))
    assert got["text"] == "가" * 9
    assert got["next_offset"] == 27
    assert got["truncated"] is True


def test_window_cuts_at_the_character_limit():
    raw = ("가" * (workspace.WINDOW_CHARS + 100)).encode("utf-8")
    got = workspace.decode_window(raw[: workspace.WINDOW_BYTES], 0, len(raw))
    assert len(got["text"]) == workspace.WINDOW_CHARS
    # next_offset 은 **실제로 실은 글자**의 바이트 수다. 잘라 낸 글자는 다음 창이다.
    assert got["next_offset"] == len(got["text"].encode("utf-8"))
    assert got["truncated"] is True


def test_truncated_is_exactly_the_inequality():
    """`truncated` 를 따로 판단하지 않는다 — `next_offset < total_bytes` 와 같은 뜻이다 (D36)."""
    raw = "abc".encode("utf-8")
    for offset in (0, 1, 2, 3):
        got = workspace.decode_window(raw[offset:], offset, len(raw))
        assert got["truncated"] == (got["next_offset"] < got["total_bytes"])


def test_window_bytes_leaves_room_for_a_split_sequence():
    """`4000*4 + 3` 은 D36 이 못 박은 값이다."""
    assert workspace.WINDOW_BYTES == workspace.WINDOW_CHARS * 4 + 3


# --- 걸음 -------------------------------------------------------------------


@windows_only
def test_platform_without_the_flags_refuses_to_read(tmp_path):
    """방어가 꺼진 채 도는 것보다 꺼진 줄 모르는 것이 나쁘다 (D36)."""
    (tmp_path / "a.md").write_text("본문", encoding="utf-8")
    with pytest.raises(workspace.PlatformUnsupported):
        workspace.open_regular(str(tmp_path), "a.md")


@posix_only
def test_reads_a_regular_file_through_the_walk(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("본문 한 줄\n", encoding="utf-8")
    fd = workspace.open_regular(str(tmp_path), "docs/a.md")
    try:
        assert workspace.read_all(fd).decode("utf-8") == "본문 한 줄\n"
    finally:
        os.close(fd)


@posix_only
def test_missing_file_fails_to_open(tmp_path):
    with pytest.raises(workspace.OpenFailed):
        workspace.open_regular(str(tmp_path), "docs/none.md")


@posix_only
def test_symlink_as_the_last_component_is_refused(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "secret").write_text("비밀", encoding="utf-8")
    (tmp_path / "docs" / "a.md").symlink_to(tmp_path / "secret")
    with pytest.raises(workspace.OpenFailed):
        workspace.open_regular(str(tmp_path), "docs/a.md")


@posix_only
def test_symlink_as_an_inner_component_is_refused(tmp_path):
    """**이것이 성분마다 내려가는 이유다.** 마지막만 막는 방어는 여기서 통과한다 (D36)."""
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "a.md").write_text("본문", encoding="utf-8")
    (tmp_path / "docs").symlink_to(tmp_path / "real", target_is_directory=True)
    with pytest.raises(workspace.OpenFailed):
        workspace.open_regular(str(tmp_path), "docs/a.md")


@posix_only
def test_directory_is_not_a_regular_file(tmp_path):
    """신원은 경로가 아니라 **서술자**에서 얻는다 (D36 4번)."""
    (tmp_path / "docs").mkdir()
    with pytest.raises(workspace.OpenFailed):
        workspace.open_regular(str(tmp_path), "docs")


@posix_only
def test_dotdot_component_never_walks_up(tmp_path):
    """`openat(dirfd, "..")` 는 커널이 허락하는 걸음이다. 색인이 그런 행을 넣지 않아도 막는다."""
    (tmp_path / "docs").mkdir()
    outside = tmp_path.parent / "outside.md"
    outside.write_text("밖", encoding="utf-8")
    with pytest.raises(workspace.OpenFailed):
        workspace.open_regular(str(tmp_path), "docs/../../outside.md")


@posix_only
def test_absolute_path_is_refused(tmp_path):
    """앞의 빈 성분에서 걸린다 — 뿌리 밖 절대 경로가 들어올 자리가 없다."""
    with pytest.raises(workspace.OpenFailed):
        workspace.open_regular(str(tmp_path), "/etc/hostname")


@posix_only
def test_failed_opens_do_not_leak_descriptors(tmp_path):
    """거절된 요청 하나가 서술자를 남기면 장수 프로세스(`serve`)에서 그것이 쌓인다.

    Grok 이 짚은 자리다. 여기 오는 다섯 경로는 **fd 를 연 뒤 거절되는 것**을 포함한다 —
    디렉터리는 열리고 나서 `fstat` 에서 걸린다.
    """
    fd_dir = "/proc/self/fd"
    if not os.path.isdir(fd_dir):
        pytest.skip("/proc 가 없어 서술자를 셀 수 없다")

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "sub").mkdir()
    (tmp_path / "docs" / "link.md").symlink_to(tmp_path / "docs" / "sub")

    before = len(os.listdir(fd_dir))
    for path in ("docs/none.md", "docs/sub", "docs/link.md", "docs/../docs/sub", "/etc/hostname"):
        with pytest.raises(workspace.OpenFailed):
            workspace.open_regular(str(tmp_path), path)
    assert len(os.listdir(fd_dir)) == before, "거절 경로가 서술자를 남긴다"


@posix_only
def test_window_walks_the_whole_file_in_order(tmp_path):
    """창을 이어 붙이면 파일 전체다 — `next_offset` 이 건너뛰지 않는다는 증거다."""
    (tmp_path / "docs").mkdir()
    text = "".join(f"{i}번째 줄 가나다\n" for i in range(900))
    (tmp_path / "docs" / "big.md").write_text(text, encoding="utf-8")

    fd = workspace.open_regular(str(tmp_path), "docs/big.md")
    try:
        offset, parts = 0, []
        while True:
            window = workspace.read_window(fd, offset)
            parts.append(window["text"])
            if not window["truncated"]:
                break
            assert window["next_offset"] > offset, "창이 전진하지 않는다"
            offset = window["next_offset"]
    finally:
        os.close(fd)

    assert "".join(parts) == text
    assert len(parts) > 1, "한 창에 다 들어가면 이 검사가 아무것도 보지 않는다"
