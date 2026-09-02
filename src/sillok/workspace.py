"""workspace 의 파일을 여는 걸음과 창 (D36 · D41).

**여기에는 DB 가 없다.** *무엇을 열어도 되는가*는 `service` 가 `kb_documents` 로 판정하고
(색인이 곧 허용 목록이다, D36), 이 모듈은 그 판정을 통과한 경로를 **뿌리 fd 에서 한 성분씩**
내려가 연다. 두 일을 한 함수에 두면 허용 목록이 경로 문자열 검사로 슬금슬금 옮겨 간다.

**경로 문자열을 `stat` 하거나 `realpath` 하지 않는다.** 검사한 경로와 연 경로가 같다는
보장이 없다(TOCTOU). 신원은 **파일 서술자에서** 얻는다 — `fstat` 으로 정규 파일인지 본다.

`O_NOFOLLOW` 는 **마지막 성분만** 막는다. 그래서 성분마다 내려간다 —
`docs/` 자체가 심볼릭 링크면 마지막만 막는 방어는 통과하고 뿌리 아래 아무 파일이나 열린다.
`realpath` 가 뿌리 아래인지 보는 검사도 그것을 막지 못한다: **요구한 적 없는 뿌리 안의
다른 파일**을 돌려주게 되기 때문이다.

플랫폼에 `O_NOFOLLOW`·`O_DIRECTORY` 가 없으면 **읽지 않고 실패한다** (D36).
방어가 꺼진 채 도는 것보다 꺼진 줄 모르는 것이 나쁘다. 운영 경로는 `api` 이미지의 Linux 이고,
호스트(Windows)에서는 이 걸음이 돌지 않는다 — 그 검사는 D22 의 `test` 프로필에서 한다.
"""

from __future__ import annotations

import codecs
import os
import stat

# D36. D30 의 청크 하드 상한과 같은 값이다 — 응답은 파일이 아니라 창이다.
WINDOW_CHARS = 4000
# UTF-8 은 글자당 최대 4바이트. +3 은 창 끝에서 잘린 시퀀스를 알아보기 위한 여유다 (D36).
WINDOW_BYTES = WINDOW_CHARS * 4 + 3

_READ_BLOCK = 1 << 16


class OpenFailed(Exception):
    """열지 못했다 — 없거나, 심볼릭 링크이거나, 정규 파일이 아니다.

    호출자가 `NOT_FOUND` 로 접는다 (D36). **행이 없는 것과 다르다** — 행은 남아 있고
    파일 쪽이 바뀐 것이다. 그 구분은 로그에만 남기고 응답에서는 같은 답을 준다.
    """


class PlatformUnsupported(Exception):
    """`O_NOFOLLOW`·`O_DIRECTORY` 가 없다. 읽지 않고 실패한다 (D36).

    클라이언트 입력 문제가 아니므로 `INTERNAL` 로 나간다 (D21·D39–D41 가장자리).
    """


class OffsetInvalid(Exception):
    """`offset` 이 음수·파일 밖·문자 경계가 아니다. `VALIDATION` 으로 나간다 (D36)."""


def flags_supported() -> bool:
    """이 플랫폼에서 D36 의 걸음을 걸을 수 있는가."""
    return hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")


def _flags() -> tuple[int, int, int]:
    if not flags_supported():
        raise PlatformUnsupported(
            "O_NOFOLLOW / O_DIRECTORY 가 없는 플랫폼이다. 방어 없이 읽지 않는다 (D36)"
        )
    return os.O_NOFOLLOW, os.O_DIRECTORY, getattr(os, "O_CLOEXEC", 0)


def open_regular(root: str, rel_path: str) -> int:
    """뿌리에서 한 성분씩 내려가 마지막 성분을 연다. **호출자가 fd 를 닫는다.**

    뿌리 자체에는 `O_NOFOLLOW` 를 걸지 않는다 — `SILLOK_WORKSPACE` 가 심볼릭 링크인 배치는
    운영자가 정한 것이고, D36 이 막는 것은 그 아래에서 링크를 **따라 나가는** 걸음이다.
    """
    nofollow, directory, cloexec = _flags()

    parts = rel_path.split("/")
    # `.` `..` 빈 성분은 열지 않는다. 색인이 그런 경로를 넣지 않으므로 여기 오지 않지만,
    # `openat(dirfd, "..")` 는 커널이 허락하는 걸음이라 오면 뿌리 밖으로 나간다.
    # **허용 목록을 넓히는 검사가 아니다** — 좁히기만 하므로 D36 의 요지와 부딪히지 않는다.
    if not rel_path or any(part in ("", ".", "..") for part in parts):
        raise OpenFailed(f"열 수 없는 경로 성분: {rel_path!r}")

    # **닫는 순서가 소유권이다.** 새 fd 를 먼저 변수에 넣고 옛 것을 닫는다 —
    # 반대로 하면 close 가 실패하는 순간 finally 가 이미 닫힌 fd 를 또 닫고
    # (재사용된 남의 fd 를 닫을 수 있다) 방금 연 것은 아무도 닫지 않는다 (Grok 지적).
    dirfd = os.open(root, os.O_RDONLY | directory | cloexec)
    try:
        for name in parts[:-1]:
            nxt = os.open(name, os.O_RDONLY | directory | nofollow | cloexec, dir_fd=dirfd)
            dirfd, previous = nxt, dirfd
            _close_quietly(previous)
        fd = os.open(parts[-1], os.O_RDONLY | nofollow | cloexec, dir_fd=dirfd)
    except OSError as exc:
        # ENOENT(없다) · ELOOP(링크다) · ENOTDIR(성분이 디렉터리가 아니다) 를 구분하지 않는다.
        # 구분해 알려 주면 뿌리 안의 배치를 응답으로 훑을 수 있다.
        raise OpenFailed(f"{rel_path}: {exc.strerror}") from exc
    finally:
        _close_quietly(dirfd)

    try:
        # 경로가 아니라 **서술자**를 본다 (D36 4번).
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OpenFailed(f"{rel_path}: 정규 파일이 아니다")
    except BaseException:
        # fstat 이 터져도 연 파일은 여기서 닫는다. 이 자리를 비워 두면
        # 거절된 요청 하나가 서술자를 하나씩 남기고, 장수 프로세스에서 그것이 쌓인다.
        _close_quietly(fd)
        raise
    return fd


def _close_quietly(fd: int) -> None:
    """닫기 실패로 **다른 fd 를 잃지 않는다.** 읽기 전용 서술자라 close 실패가 알려 주는 것이 없다."""
    try:
        os.close(fd)
    except OSError:
        pass


def _check_offset(offset: int, total_bytes: int) -> None:
    if offset < 0:
        raise OffsetInvalid(f"offset must not be negative: {offset}")
    if offset > total_bytes:
        # 같은 값은 오류가 아니라 끝이다 (D36 가장자리 표).
        raise OffsetInvalid(f"offset {offset} is past the end of the file")


def decode_window(chunk: bytes, offset: int, total_bytes: int) -> dict[str, object]:
    """창 하나를 만든다. **순수 함수다** — 파일이 없어도 검사할 수 있다.

    디코드는 strict 다. 관대한 디코더는 경계가 아닌 바이트들을 조용히 먹어
    `next_offset` 이 영영 그것들을 지나치게 만든다 (D36).
    """
    _check_offset(offset, total_bytes)

    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    try:
        # final=False. 끝의 불완전한 시퀀스는 버린다 — 그 글자는 **다음 창**이다.
        text = decoder.decode(chunk, False)
    except UnicodeDecodeError as exc:
        if exc.start == 0 and offset > 0:
            raise OffsetInvalid("offset is not a character boundary") from None
        # offset 0 은 언제나 문자 경계다. 여기서 터졌으면 파일이 UTF-8 이 아니다 —
        # 색인 뒤에 바뀐 것이고, 계약에 답이 없으므로 D21 의 포괄 예외에 맡긴다 (INTERNAL).
        raise

    text = text[:WINDOW_CHARS]
    # 잘라 낸 글자는 건너뛴 것이 아니라 다음 창이다. 그래서 실제로 실은 글자만 센다.
    next_offset = offset + len(text.encode("utf-8"))
    return {
        "text": text,
        "offset": offset,
        "next_offset": next_offset,
        # truncated 는 별도로 판단하지 않는다 — 이 부등식과 같은 뜻이다 (D36).
        "total_bytes": total_bytes,
        "truncated": next_offset < total_bytes,
    }


def read_window(fd: int, offset: int) -> dict[str, object]:
    """서술자에서 창 하나를 읽는다. 크기 상한은 두지 않는다 — 큰 파일도 창으로 잘린다 (D36)."""
    total_bytes = os.fstat(fd).st_size
    _check_offset(offset, total_bytes)
    os.lseek(fd, offset, os.SEEK_SET)
    return decode_window(_read_upto(fd, WINDOW_BYTES), offset, total_bytes)


def _read_upto(fd: int, count: int) -> bytes:
    """짧은 읽기를 접는다. `os.read` 는 요청한 만큼 준다고 약속하지 않는다."""
    parts: list[bytes] = []
    remaining = count
    while remaining > 0:
        block = os.read(fd, remaining)
        if not block:
            break
        parts.append(block)
        remaining -= len(block)
    return b"".join(parts)


def read_all(fd: int) -> bytes:
    """파일 전체. `save_doc` 이 쓴다 — 창으로 diff 를 뜨면 창 밖의 줄이 전부 삭제로 보인다 (D38)."""
    os.lseek(fd, 0, os.SEEK_SET)
    parts: list[bytes] = []
    while True:
        block = os.read(fd, _READ_BLOCK)
        if not block:
            break
        parts.append(block)
    return b"".join(parts)
