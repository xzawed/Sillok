"""5단계 ingest 의 순수 로직 (D30).

**여기에는 DB 가 없다.** 스캔·정규화·해시·front matter·청크까지가 이 모듈이고,
쓰기는 `service.ingest` 가 한다 — DB 를 만지는 문은 하나여야 한다 (D19).

이 분리가 검사를 싸게 만든다. 아래 규칙은 대부분 순수 함수라 `tmp_path` 로 만든
최소 workspace 트리에서 확인할 수 있고, 그것이 D22 가 남긴 숙제(`test` 이미지에
`docs/`·`adr/` 가 없다)를 우회하는 방법이다 — 작업 트리를 마운트하면 검사가
저장소의 지금 내용에 묶여 문서를 고칠 때마다 깨진다.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

# --- D30 이 못 박은 값 ------------------------------------------------------
# 정본은 adr/0001-v1-stack-decisions.md §D30 이다. 여기서 바꾸지 않는다.

MD_SUFFIX = ".md"
CHUNK_SOFT_LIMIT = 1200
CHUNK_HARD_LIMIT = 4000
HEADING_SEPARATOR = " > "

# 색인 경로 (D9). 게이트의 INCLUDE 와 같은 집합을 봐야 한다 —
# 다르면 "게이트는 초록인데 색인은 비어 있는" 부류가 생긴다.
_ROOT_README = re.compile(r"^README[^/]*$", re.IGNORECASE)
# D47. 게이트의 walk 와 **같은 목록**이어야 한다 — 두 벌이 되면 갈라진다.
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}

# 게이트(scripts/check-layout.mjs)의 FRONT_MATTER 와 같은 것을 본다.
# GitHub 이 front matter 로 인정하는 것을 기준으로 잡는다 (D29).
_FRONT_MATTER = re.compile(r"^﻿?---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*\r?\n?")

# taxonomy 정본은 docs/data-model.md 다. 검증은 서비스에 두고 DDL 에 CHECK 를 넣지 않는다 (D25).
DOC_TYPES = frozenset({"adr", "api", "runbook", "readme", "schema", "other"})
STATUSES = frozenset({"current", "draft", "superseded", "stale"})

# front matter 에서 읽는 키는 넷뿐이다 (D30 §7). 나머지는 무시한다.
_META_KEYS = ("title", "doc_type", "status", "module")

_ATX = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


class DecodeFailed(Exception):
    """UTF-8 로 못 읽는 파일. 그 파일만 건너뛰지 않고 run 을 실패로 끝낸다 (D30 §2).

    조용히 빠진 문서는 검색 0건과 구분되지 않는다.
    """


@dataclass(frozen=True)
class Scanned:
    path: str          # workspace 루트 기준 상대 경로, 구분자는 슬래시
    absolute: Path
    mtime: float       # 초. UTC 변환은 service 가 한다


@dataclass(frozen=True)
class Skipped:
    path: str
    reason: str        # not-md | symlink


@dataclass(frozen=True)
class Chunk:
    chunk_idx: int
    heading_path: str | None
    content: str


# --- 스캔 ------------------------------------------------------------------


def in_index_paths(rel: str) -> bool:
    """D9. 경로 판정은 확장자·대소문자를 가리지 않는다 — 무엇을 먹는지는 D30 이 정한다."""
    return rel.startswith("docs/") or rel.startswith("adr/") or bool(_ROOT_README.match(rel))


def scan(workspace: Path) -> tuple[list[Scanned], list[Skipped]]:
    """D9 경로를 훑어 `.md` 만 돌려준다. 제외한 것은 조용히 사라지지 않는다 (D30 §1).

    순서는 `path` 의 UTF-8 바이트 오름차순이다. 파일시스템이 주는 순서에 기대지 않는다 —
    부분 run 이 남긴 상태가 실행마다 같아야 한다 (D23 선례).
    """
    files: list[Scanned] = []
    skipped: list[Skipped] = []

    for entry in sorted(_walk(workspace), key=lambda p: str(p)):
        rel = entry.relative_to(workspace).as_posix()
        if not in_index_paths(rel):
            continue
        # 심볼릭 링크는 따라가지 않는다. workspace 밖을 가리키는 링크 하나가
        # D9 경로를 무의미하게 만든다.
        if entry.is_symlink():
            skipped.append(Skipped(rel, "symlink"))
            continue
        if not rel.endswith(MD_SUFFIX):
            skipped.append(Skipped(rel, "not-md"))
            continue
        files.append(Scanned(rel, entry, entry.stat().st_mtime))

    files.sort(key=lambda f: f.path.encode("utf-8"))
    skipped.sort(key=lambda s: s.path.encode("utf-8"))
    return files, skipped


def _walk(root: Path) -> list[Path]:
    found: list[Path] = []
    for entry in root.iterdir():
        if entry.name in _SKIP_DIRS:
            continue
        # is_dir() 은 링크를 따라간다. 링크는 파일로 잡아 skipped 로 흘린다.
        if entry.is_dir() and not entry.is_symlink():
            found.extend(_walk(entry))
        else:
            found.append(entry)
    return found


# --- 정규화와 해시 ----------------------------------------------------------


def normalize(raw: bytes, path: str = "") -> str:
    """D30 §2. 정규화는 둘뿐이다 — 선행 BOM 제거, CRLF 와 홀로 있는 CR 을 LF 로.

    그 밖에는 아무것도 하지 않는다. 후행 공백을 다듬지 않고 마지막 개행을
    더하지도 빼지도 않는다. 손대는 만큼 해시가 무엇의 함수인지 흐려진다.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DecodeFailed(f"UTF-8 로 읽을 수 없다: {path or '<bytes>'}") from exc
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def content_hash(text: str) -> str:
    """정규화한 텍스트를 UTF-8 로 다시 인코드한 바이트의 SHA-256, 소문자 16진 64자.

    **본문만의 함수다.** `path`·`project`·`commit_sha` 를 섞지 않는다 —
    섞으면 체크아웃 한 번이 전 문서를 변경으로 만든다 (D30 §2).
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- front matter 와 메타 ---------------------------------------------------


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    """게이트와 같은 파서다 (D30 §7). YAML 파서가 아니다.

    첫 콜론 앞이 키, 뒤가 값이며 값은 주석 표시 이후를 떼고 앞뒤 공백을 벗긴다.
    따옴표를 벗기지 않는다.
    """
    m = _FRONT_MATTER.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = re.sub(r"\s+#.*$", "", value).strip()
    return meta, text[m.end() :]


def strip_inline(text: str) -> str:
    """제목에서 인라인 마크업을 벗긴다. 형식 정본은 docs/service-and-mcp.md 다.

    링크는 표시 텍스트만 남긴다. 강조·코드 스팬 표시는 지운다.
    """
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "")
    text = re.sub(r"\*{1,3}|_{1,3}", "", text)
    return text.strip()


def first_h1(text: str) -> str | None:
    """코드 펜스 밖 첫 `# ` 제목의 텍스트 (D29).

    HTML 블록은 CommonMark 6형이라 **빈 줄에서 끝난다** — `</div>` 를 기다리지 않는다.
    그래서 줄 단위로 훑으면 `<div align="center">` 다음의 H1 이 그대로 잡힌다.
    """
    for line in _outside_fences(text):
        m = _ATX.match(line)
        if m and len(m.group(1)) == 1:
            return strip_inline(m.group(2)) or None
    return None


def derive_meta(rel_path: str, text: str) -> dict[str, str | None]:
    """루트 `README*` 는 유도하고, 나머지는 front matter 를 읽는다 (D29·D30 §7)."""
    if _ROOT_README.match(rel_path):
        return {
            "title": first_h1(text),
            "doc_type": "readme",
            "status": "current",
            "module": None,
        }
    meta, _ = split_front_matter(text)
    out: dict[str, str | None] = {}
    for key in _META_KEYS:
        raw = meta.get(key, "")
        # 빈 값과 null 은 NULL 이다. 이 한 줄이 없으면 문자열 "null" 이 들어간다.
        out[key] = None if raw in ("", "null", "~") else raw
    if out["doc_type"] is None:
        out["doc_type"] = "other"
    if out["status"] is None:
        out["status"] = "current"
    if out["title"] is None:
        # front matter 가 없으면 title 은 D29 의 첫 H1 규칙으로 유도한다 (D30 §7).
        # 이 저장소에서는 게이트가 먼저 막지만, D5 가 말하는 다른 project 에서는
        # front matter 가 없는 것이 정상이다.
        out["title"] = first_h1(text)
    return out


# --- 청크 ------------------------------------------------------------------


def _outside_fences(text: str):
    """코드 펜스 안을 건너뛰며 줄을 돌려준다. 게이트의 stripCode 와 같은 규칙이다."""
    fence: tuple[str, int] | None = None
    for line in text.split("\n"):
        m = _FENCE.match(line)
        if m:
            marker, length = m.group(1)[0], len(m.group(1))
            if fence is None:
                fence = (marker, length)
            elif marker == fence[0] and length >= fence[1]:
                fence = None
            continue
        if fence is None:
            yield line


def chunk(body: str) -> list[Chunk]:
    """헤딩이 자르고 블록이 지킨다 (D30 §5).

    1차는 ATX 헤딩, 2차는 블록 채우기다. **블록은 쪼개지 않는다** —
    다만 하드 상한에서만 줄 경계로 나눈다. 문자 단위로 자르는 경로는 없다.
    setext 제목은 제목으로 보지 않는다.
    """
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    section: list[str] = []
    heading_path: str | None = None

    def flush() -> None:
        nonlocal section
        for text in _fill(section):
            chunks.append(Chunk(len(chunks), heading_path, text))
        section = []

    fence: tuple[str, int] | None = None
    for line in body.split("\n"):
        m = _FENCE.match(line)
        if m:
            marker, length = m.group(1)[0], len(m.group(1))
            if fence is None:
                fence = (marker, length)
            elif marker == fence[0] and length >= fence[1]:
                fence = None
            section.append(line)
            continue
        head = None if fence is not None else _ATX.match(line)
        if head is None:
            section.append(line)
            continue

        flush()
        level = len(head.group(1))
        # 레벨을 건너뛰면 빈 칸을 채우지 않고 스택에 그대로 쌓는다 — 없는 제목을 만들지 않는다.
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, strip_inline(head.group(2))))
        heading_path = HEADING_SEPARATOR.join(t for _, t in stack)

    flush()
    return chunks


def _blocks(lines: list[str]) -> list[str]:
    """빈 줄로 구분되는 연속 줄 뭉치. 코드 펜스는 안에 빈 줄이 있어도 한 블록이다."""
    out: list[str] = []
    buf: list[str] = []
    fence: tuple[str, int] | None = None
    for line in lines:
        m = _FENCE.match(line)
        if m:
            marker, length = m.group(1)[0], len(m.group(1))
            if fence is None:
                fence = (marker, length)
            elif marker == fence[0] and length >= fence[1]:
                fence = None
            buf.append(line)
            continue
        if fence is None and not line.strip():
            if buf:
                out.append("\n".join(buf))
                buf = []
            continue
        buf.append(line)
    if buf:
        out.append("\n".join(buf))
    return out


def _split_hard(block: str) -> list[str]:
    """하드 상한을 넘는 블록만 줄 경계로 나눈다.

    줄 하나가 그것마저 넘으면 **그 줄은 그대로 한 조각이다** —
    문자 단위로 자르는 경로는 만들지 않는다 (D30 §5).
    """
    if len(block) <= CHUNK_HARD_LIMIT:
        return [block]
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for line in block.split("\n"):
        add = len(line) + (1 if buf else 0)
        if buf and size + add > CHUNK_HARD_LIMIT:
            out.append("\n".join(buf))
            buf, size = [], 0
            add = len(line)
        buf.append(line)
        size += add
    if buf:
        out.append("\n".join(buf))
    return out


def _fill(lines: list[str]) -> list[str]:
    """블록을 순서대로 담다가 소프트 상한을 넘으면 새 청크를 시작한다.

    담은 것이 있는데 다음 블록을 더하면 상한을 넘을 때는 **그 블록 앞에서 끊는다.**
    본문이 비어 있는 절은 청크를 만들지 않는다.
    """
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for block in _blocks(lines):
        for piece in _split_hard(block):
            add = len(piece) + (2 if buf else 0)
            if buf and size + add > CHUNK_SOFT_LIMIT:
                out.append("\n\n".join(buf))
                buf, size = [], 0
                add = len(piece)
            buf.append(piece)
            size += add
    if buf:
        out.append("\n\n".join(buf))
    return out
