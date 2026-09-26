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
import os
import re
import unicodedata
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

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")

# 유도 규칙(청크·`heading_path`·메타)의 판 (D71). 규칙이 바뀌면 올린다 — 본문이 같은 문서도 한 번 다시 만든다.
# 올리지 않고 바꾸면 tests/test_ingest.py 의 digest 검사가 운다.
RULES_VERSION = 1

# CommonMark 6형 HTML 블록을 여는 태그 (D29 — 빈 줄에서 끝난다). 제목 찾기만 쓴다; 청크는 보지 않는다 (D30 §5).
_HTML_BLOCK_TAGS = frozenset(
    "address article aside base basefont blockquote body caption center col colgroup dd details dialog"
    " dir div dl dt fieldset figcaption figure footer form frame frameset h1 h2 h3 h4 h5 h6 head header"
    " hr html iframe legend li link main menu menuitem nav noframes ol optgroup option p param search"
    " section source summary table tbody td tfoot th thead title tr track ul".split()
)
_HTML_BLOCK_START = re.compile(r" {0,3}</?([A-Za-z][A-Za-z0-9]*)(?:[ \t>]|/>|$)")


class DecodeFailed(Exception):
    """UTF-8 로 못 읽는 파일, 또는 이름을 담을 수 없는 문서. 그 파일만 건너뛰지 않고 run 을 실패로 끝낸다
    (D30 §2 · D70 ②).

    조용히 빠진 문서는 검색 0건과 구분되지 않는다.
    """


@dataclass(frozen=True)
class Scanned:
    path: str          # workspace 루트 기준 상대 경로, 구분자는 슬래시
    # 절대 경로와 mtime 을 싣지 않는다. 읽기는 D36 의 걸음이고 mtime 은 그 서술자의 것이다 (D70 ③) —
    # 스캔 때의 경로를 들고 가면 그 경로를 다시 따라가는 읽기가 돌아온다.
    # 이름이 유니코드로 담기지 않는 문서다 (D70 ②). 스캔에서 터뜨리지 않고 **정렬 순서의 제자리에서**
    # service 가 실패시킨다 — 스캔에서 터지면 앞 순서의 NUL·디코드 실패보다 먼저 나오고 앞 파일도 색인되지 않았다
    # (2026-09-26 리뷰 실측). 첫 실패는 순서대로다 (D30 §2).
    storable: bool = True


@dataclass(frozen=True)
class Skipped:
    path: str
    reason: str        # not-md | symlink | not-regular (D70 ①)
    # 이름이 유니코드로 담기지 않으면 `path` 는 표시형이고 **삭제 판정의 키가 아니다** (D70 ②).
    exact: bool = True


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
    부분 run 이 남긴 상태가 실행마다 같아야 한다 (D23 선례). 정렬 키는 이름의 **파일시스템 바이트**다 —
    UTF-8 로 담기는 이름에서는 같은 순서이고, 담기지 않는 이름에서 `encode("utf-8")` 처럼 터지지 않는다 (D70 ②).

    판정은 `lstat` 이고 **파일은 열지 않는다.** 읽기는 service 가 D36 의 걸음으로 한다 (D70 ③).
    디렉터리는 경로로 나열한다 — 나열과 진입 사이에 디렉터리가 링크로 바뀌는 경합은 닫지 않았다.
    그때 새는 것은 이름이고 내용은 읽기 걸음이 막는다 (D70 이 닫지 않는 것).
    """
    files: list[Scanned] = []
    skipped: list[Skipped] = []

    for rel, kind in sorted(_walk(workspace), key=lambda e: os.fsencode(e[0])):
        judged = _judge(rel, kind)
        if isinstance(judged, Scanned):
            files.append(judged)
        elif judged is not None:
            skipped.append(judged)
    return files, skipped


def _judge(rel: str, kind: str) -> Scanned | Skipped | None:
    """항목 하나. D9 경로 밖이면 None 이다."""
    exact = _storable(rel)
    shown = rel if exact else printable(rel)
    if kind == "link":
        # 심볼릭 링크는 따라가지 않는다. workspace 밖을 가리키는 링크 하나가
        # D9 경로를 무의미하게 만든다. 최상위 `docs`·`adr` 자체가 링크여도 싣는다 —
        # `docs/` 접두 판정에 걸리지 않아 조용히 사라졌고 그 아래 행이 전부 지워졌다 (D30 §1).
        indexed = in_index_paths(rel) or in_index_paths(rel + "/")
        return Skipped(shown, "symlink", exact) if indexed else None
    if not in_index_paths(rel):
        return None
    if not rel.endswith(MD_SUFFIX):
        return Skipped(shown, "not-md", exact)
    if kind != "file":
        # FIFO·소켓·장치. 읽으면 FIFO 는 쓰는 쪽을 영영 기다린다 (D70 ①).
        return Skipped(shown, "not-regular", exact)
    # `exact` 가 거짓이면 문서로 받을 것인데 `path` 가 `text` 컬럼과 JSON 에 담기지 않는다.
    # 건너뛰면 옛 청크가 `ok` 인 채 남는다 — NUL 과 같은 부류다 (D30 §2 · D70 ②). 실패는 service 가
    # 그 순서에서 낸다 (`unstorable`).
    return Scanned(rel, exact)


def unstorable(item: Scanned) -> DecodeFailed:
    """이름을 담을 수 없는 문서의 실패. 열기 전에 낸다 — 열 이유가 없다 (D70 ②)."""
    return DecodeFailed(f"경로를 UTF-8 로 담을 수 없다: {printable(item.path)}")


def _walk(root: Path) -> list[tuple[str, str]]:
    """`(상대 경로, 종류)` — 종류는 `file`·`link`·`other`. 디렉터리는 내려가고 링크는 따라가지 않는다.

    **재귀하지 않는다.** 깊은 나무가 `RecursionError` 로 끝나면 그 사유에 경로가 없다 (2026-09-26 감사).
    `DirEntry` 의 판정은 `follow_symlinks=False` 로 본다 — 기본값은 링크를 따라간다.
    **D9 디렉터리 밖으로는 내려가지 않는다.** 색인 집합은 같고, 뿌리의 `build/` 같은 읽을 수 없는
    디렉터리 하나가 run 을 실패시키지 않는다 (2026-09-26 리뷰). 뿌리의 항목 자체는 본다 — 루트 `README*` 와
    최상위 `docs`·`adr` 링크가 거기 있다.
    """
    found: list[tuple[str, str]] = []
    pending = [(os.fspath(root), "")]
    while pending:
        directory, prefix = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name in _SKIP_DIRS:
                    continue
                rel = prefix + entry.name
                kind = _kind(entry)
                if kind != "dir":
                    found.append((rel, kind))
                elif in_index_paths(rel + "/"):
                    pending.append((entry.path, rel + "/"))
    return found


def _kind(entry: os.DirEntry) -> str:
    """링크를 먼저 본다 — `is_dir()`·`is_file()` 의 기본값은 링크를 따라간다."""
    if entry.is_symlink():
        return "link"
    if entry.is_dir(follow_symlinks=False):
        return "dir"
    if entry.is_file(follow_symlinks=False):
        return "file"
    return "other"


def _storable(rel: str) -> bool:
    """이름이 유니코드로 담기는가 — 비-UTF-8 바이트(Linux 의 surrogateescape)·짝 없는 서로게이트가 없는가."""
    try:
        rel.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


# --- 진단 문자열의 표시형 (D32) ----------------------------------------------

# 양방향 서식 문자. 보이는 순서를 바꿔 진단 줄을 위조할 수 있다.
_BIDI = frozenset("؜‎‏‪‫‬‭‮⁦⁧⁨⁩")
# 제어(C0·DEL·C1)·줄 구분자·문단 구분자·짝 없는 서로게이트.
_UNPRINTABLE = frozenset({"Cc", "Zl", "Zp", "Cs"})


def printable(text: str) -> str:
    """run 오류·서버 로그·CLI 에 싣는 **표시형**이다 (D32 · D70 ②).

    경로에 든 줄바꿈이 첫 줄 규칙으로 사유를 경로 한가운데서 잘랐고, ESC 가 운영자 터미널에
    그대로 닿았다 (2026-09-26 감사). 그 글자들을 `\\xNN`·`\\uNNNN` 으로 적는다.
    **진단 전용이다** — 백슬래시가 든 진짜 이름과 같은 글자가 될 수 있어 키로 쓰지 않는다.
    응답의 `skipped[].path` 와 행의 `path` 는 원문이다 — JSON 이 이스케이프한다.
    """
    return "".join(_escape(ch) for ch in text)


def _escape(ch: str) -> str:
    if ch in _BIDI or unicodedata.category(ch) in _UNPRINTABLE:
        code = ord(ch)
        return f"\\x{code:02x}" if code < 0x100 else f"\\u{code:04x}"
    return ch


# --- 정규화와 해시 ----------------------------------------------------------


def normalize(raw: bytes, path: str = "") -> str:
    """D30 §2. 정규화는 둘뿐이다 — 선행 BOM 제거, CRLF 와 홀로 있는 CR 을 LF 로.

    그 밖에는 아무것도 하지 않는다. 후행 공백을 다듬지 않고 마지막 개행을
    더하지도 빼지도 않는다. 손대는 만큼 해시가 무엇의 함수인지 흐려진다.
    NUL 은 정규화가 아니라 **거절**이다 — 못 읽는 파일과 같은 `DecodeFailed` 다 (D30 §2).
    """
    # 사유에 싣는 경로는 표시형이다 (D32) — 이름의 줄바꿈이 첫 줄 규칙으로 사유를 자른다.
    shown = printable(path) if path else "<bytes>"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DecodeFailed(f"UTF-8 로 읽을 수 없다: {shown}") from exc
    # NUL 은 UTF-8 로는 멀쩡하지만 `text` 컬럼이 담지 못한다 — 못 읽는 파일과 같은 부류다 (D30 §2).
    # 넘기면 청크 INSERT 가 DataError 로 터져 경로 없는 실패가 됐다. 벗기지 않는다 — 해시가 바뀐다.
    if "\x00" in text:
        raise DecodeFailed(f"NUL 을 담을 수 없다: {shown}")
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
        meta[key.strip()] = _cut_comment(value).strip()
    return meta, text[m.end() :]


def _cut_comment(value: str) -> str:
    """`\\s+#.*$` 와 같은 자리를 자른다 — 공백 뒤에 오는 첫 `#` 앞의 공백 줄부터 끝까지.

    정규식은 `#` 없는 긴 공백에서 자리마다 다시 시도해 제곱 시간이었다 (Sonar S8786). 한 번 훑는다.
    게이트(scripts/check-layout.mjs)의 `cutComment` 와 같은 규칙이다 (D30 §7).
    """
    for i in range(1, len(value)):
        if value[i] == "#" and value[i - 1].isspace():
            start = i - 1
            while start > 0 and value[start - 1].isspace():
                start -= 1
            return value[:start]
    return value


def _atx(line: str) -> tuple[int, str] | None:
    """ATX 제목이면 `(레벨, 텍스트)`. `^(#{1,6})\\s+(.*)$` 와 같은 판정이다.

    정규식은 `\\s+` 와 `(.*)` 가 공백을 두고 겹쳐 Sonar 가 제곱 시간으로 봤다. 세어서 가른다.
    """
    level = len(line) - len(line.lstrip("#"))
    if not 1 <= level <= 6 or level == len(line) or not line[level].isspace():
        return None
    rest = line[level:]
    return level, rest[len(rest) - len(rest.lstrip()) :]


def strip_inline(text: str) -> str:
    """제목에서 인라인 마크업을 벗긴다 (D29 · D30 §5). 형식 정본은 docs/service-and-mcp.md 다.

    왼쪽에서 오른쪽으로 한 번 훑는다. **코드 스팬은 안의 글자를 그대로 둔다** — 예전에는 `_`·`*` 를 전부 지워
    `` `event_stats` `` 가 `eventstats` 였다 (2026-09-26 감사 F099). 링크·이미지는 표시 텍스트만 남기고 그 텍스트도
    같은 규칙을 탄다. 강조 `*`·`_` 는 **짝이 맞는 구분자만** 지운다 — CommonMark 의 flanking 이고, 단어 안의 `_` 는
    글자다. 백슬래시 이스케이프는 그 글자다. 참조 링크·HTML 태그는 벗기지 않는다.
    이 규칙이 바뀌면 `RULES_VERSION` 을 올린다 (D71).
    """
    return "".join(_emphasis(_inline_tokens(text))).strip()


_ASCII_PUNCT = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


@dataclass
class _Delim:
    """강조 구분자 한 줄기 (`*`·`**`·`_` …). 짝이 맞으면 `count` 가 줄어든다."""

    char: str
    count: int
    can_open: bool
    can_close: bool


def _inline_tokens(text: str) -> list[str | _Delim]:
    out: list[str | _Delim] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        link = _link_at(text, i) if ch in "![" else None
        if ch == "\\" and i + 1 < n and text[i + 1] in _ASCII_PUNCT:
            out.append(text[i + 1])
            i += 2
        elif ch == "`":
            i = _code_span(text, i, out)
        elif link is not None:
            # 링크 텍스트에는 `]` 가 없으므로 이 재귀는 한 겹이다.
            out.extend(_inline_tokens(link[0]))
            i = link[1]
        elif ch in "*_":
            j = i
            while j < n and text[j] == ch:
                j += 1
            out.append(_delim(text, i, j))
            i = j
        else:
            out.append(ch)
            i += 1
    return out


def _code_span(text: str, i: int, out: list[str | _Delim]) -> int:
    """`i` 의 백틱 줄기가 같은 길이의 줄기로 닫히면 안의 글자를 그대로 싣는다. 못 닫으면 백틱은 글자다."""
    n = len(text)
    j = i
    while j < n and text[j] == "`":
        j += 1
    run = j - i
    k = j
    while True:
        k = text.find("`", k)
        if k < 0:
            out.append(text[i:j])
            return j
        m = k
        while m < n and text[m] == "`":
            m += 1
        if m - k == run:
            inner = text[j:k]
            # CommonMark: 양끝이 모두 공백이고 공백뿐이 아니면 한 칸씩 벗긴다.
            if len(inner) >= 2 and inner[0] == " " and inner[-1] == " " and inner.strip(" "):
                inner = inner[1:-1]
            out.append(inner)
            return m
        k = m


def _link_at(text: str, i: int) -> tuple[str, int] | None:
    """`[텍스트](목적지)`·`![…](…)` 이면 `(텍스트, 끝)`.

    예전 정규식 `!?\\[([^\\]]*)\\]\\([^)]*\\)` 과 같은 모양을 본다 — 텍스트는 첫 `]` 까지, 목적지는 첫 `)` 까지.
    """
    start = i + 1 if text[i] == "!" else i
    if start >= len(text) or text[start] != "[":
        return None
    close = text.find("]", start + 1)
    if close < 0 or close + 1 >= len(text) or text[close + 1] != "(":
        return None
    end = text.find(")", close + 2)
    if end < 0:
        return None
    return text[start + 1 : close], end + 1


def _is_space(ch: str) -> bool:
    return ch.isspace()


def _is_punct(ch: str) -> bool:
    return unicodedata.category(ch)[0] in "PS"


def _delim(text: str, i: int, j: int) -> _Delim:
    """CommonMark 의 left/right-flanking. 줄의 처음과 끝은 공백으로 본다."""
    before = text[i - 1] if i > 0 else " "
    after = text[j] if j < len(text) else " "
    left = not _is_space(after) and (not _is_punct(after) or _is_space(before) or _is_punct(before))
    right = not _is_space(before) and (not _is_punct(before) or _is_space(after) or _is_punct(after))
    if text[i] == "*":
        return _Delim("*", j - i, left, right)
    # `_` 는 단어 안에서 열거나 닫지 않는다 — `snake_case` 는 글자다.
    return _Delim("_", j - i, left and (not right or _is_punct(before)), right and (not left or _is_punct(after)))


def _emphasis(tokens: list[str | _Delim]) -> list[str]:
    """닫는 구분자마다 같은 글자의 가장 가까운 여는 구분자와 짝짓고, 짝지은 만큼 지운다. 남은 것은 글자다."""
    openers: list[_Delim] = []
    for tok in tokens:
        if not isinstance(tok, _Delim):
            continue
        if tok.can_close:
            at = next((k for k in range(len(openers) - 1, -1, -1) if openers[k].char == tok.char), None)
            if at is not None:
                opener = openers[at]
                used = min(opener.count, tok.count)
                opener.count -= used
                tok.count -= used
                # 사이에 있던 여는 구분자는 더는 짝을 찾지 못한다 (CommonMark).
                del openers[at + 1 :]
                if opener.count == 0:
                    openers.pop()
        if tok.can_open and tok.count:
            openers.append(tok)
    return [tok if isinstance(tok, str) else tok.char * tok.count for tok in tokens]


def first_h1(text: str) -> str | None:
    """코드 펜스 밖 첫 `# ` 제목의 텍스트 (D29).

    HTML 블록은 CommonMark 6형이라 **빈 줄에서 끝난다** — `</div>` 를 기다리지 않는다.
    그래서 `<div align="center">` · 빈 줄 · H1 이면 그 H1 이 잡힌다. 빈 줄 없이 블록 **안에** 든 `# ` 는
    제목이 아니다 — 예전에는 그것을 잡았다 (2026-09-26 감사 F020). 청크는 HTML 블록을 보지 않는다 (D30 §5).
    """
    in_html = False
    for line in _outside_fences(text):
        if in_html:
            in_html = bool(line.strip(" \t"))
            continue
        start = _HTML_BLOCK_START.match(line)
        if start and start.group(1).lower() in _HTML_BLOCK_TAGS:
            in_html = True
            continue
        head = _atx(line)
        if head and head[0] == 1:
            return strip_inline(head[1]) or None
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
        # `~` 는 NULL 이 아니다 — D30 §7 에 없고 게이트도 접지 않는다 (2026-09-26 감사 F020).
        out[key] = None if raw in ("", "null") else raw
    if out["doc_type"] is None:
        out["doc_type"] = "other"
    if out["status"] is None:
        out["status"] = "current"
    if _FRONT_MATTER.match(text) is None:
        # front matter 가 **없을 때만** title 을 D29 의 첫 H1 규칙으로 유도한다 (D30 §7).
        # 있는데 title 이 비면 NULL 이다 — 예전에는 채웠고 front matter 안의 `# 주석` 줄까지 훑었다 (F020).
        # 이 저장소에서는 게이트가 먼저 막지만, D5 가 말하는 다른 project 에서는 없는 것이 정상이다.
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
        head = None if fence is not None else _atx(line)
        if head is None:
            section.append(line)
            continue

        flush()
        level, title = head
        # 레벨을 건너뛰면 빈 칸을 채우지 않고 스택에 그대로 쌓는다 — 없는 제목을 만들지 않는다.
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, strip_inline(title)))
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
