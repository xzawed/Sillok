"""D17 마이그레이션 러너.

**이 모듈은 Service 쪽에 있고 CLI 쪽에 있지 않다.** D19 가 금지하는 것은
CLI 가 자기 SQL 계층을 갖는 것이다. 러너는 하나이고 진입점이 둘이다 —
`sillok migrate`(지금)와 `sillok serve` 기동 시 bind 전(3단계).

DDL 정본은 docs/data-model.md 다. 여기서 SQL 을 만들지 않고 migrations/*.sql 을 읽어 실행한다.

버전 추적 테이블은 두지 않는다. D17 이 멱등(IF NOT EXISTS)을 재기동 안전의
수단으로 정했기 때문이다. 되돌릴 수 없는 변경이 필요해지면 그때 결정하고 ADR 에 기록한다.

**그 방식의 천장:** `IF NOT EXISTS` 는 같은 이름의 객체가 *다른 모양*으로 이미 있으면
고치지 않고 그냥 넘어간다. 예를 들어 `kb_chunks_tsv` 가 btree 로 이미 있으면 GIN 으로
바꿔 주지 않는다. 이 러너는 그때도 성공을 보고한다. 컬럼·인덱스 정의를 바꾸는 변경이
필요해지면 멱등만으로는 부족하므로 먼저 결정하고 ADR 에 기록한다. 추측으로 고치지 않는다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

import psycopg
import psycopg.conninfo

log = logging.getLogger(__name__)

# migrations/ 는 저장소 루트에 있다. src/sillok/migrations.py 기준 두 단계 위.
DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

# 붙을 수 없을 때 무한히 기다리지 않는다.
# D17 이 마이그레이션을 serve 기동 시 bind 전에 돌리므로, 타임아웃이 없으면
# DB 가 없을 때 서비스가 아무 메시지 없이 멈춘 것처럼 보인다 (실측으로 확인).
CONNECT_TIMEOUT_SECONDS = 10

# 001_extensions.sql 처럼 숫자로 시작하는 것만 마이그레이션으로 본다.
_NAME = re.compile(r"^(\d+)_[A-Za-z0-9_.-]+\.sql$")

# libpq 는 URI 말고도 "host=... password=..." 키워드 문자열과 ?password= 질의를 받는다.
# D16 의 정식 DSN 만 가리면 나머지 형태에서 암호가 오류 메시지로 샌다. `sslpassword` 도 비밀이다.
# 인용은 libpq 의 작은따옴표 규칙이다 — 닫히지 않았으면 끝까지 가린다. 큰따옴표는 libpq 의 인용이 아니다 —
# 닫히고 뒤가 공백·끝일 때만 한 덩어리로 보고, 아니면(`"ab"SeCrEt`) 인용 없는 값으로 통째로 가린다.
# 인용 없는 값의 `\ ` 는 libpq 가 공백으로 읽는다 (2026-09-27 감사 F061 · 리뷰 실측).
_KEYWORD_PASSWORD = re.compile(
    r"""(?i)((?<![?&])\b(?:ssl)?password\s*=\s*)"""
    r"""(?:'(?:[^'\\]|\\.)*(?:'|$)|"(?:[^"\\]|\\.)*"(?=\s|$)|(?:\\.|\S)+)"""
)
# 질의의 키는 퍼센트 인코딩될 수 있다(`%70assword`). 값은 `&`·공백까지다 — libpq 는 `#` 를 조각으로 보지 않는다.
_QUERY_PARAM = re.compile(r"([?&])([^=&\s]*)=([^&\s]*)")
_SECRET_KEYS = frozenset({"password", "sslpassword"})
# URI 의 시작은 아무 scheme 이나 본다 — `postgresql+psycopg://` 도 DSN 모양이다.
# 암호 안의 `sec://`·`postgres://` 는 경계가 되지 않는다: 한 URI 는 공백까지 한 덩어리이고 이미 삼킨 자리는 건너뛴다.
_URI_START = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://")
# 드라이버 문구에서 지울 조각의 최소 길이. 더 짧은 조각을 문구 전체에서 지우면 낱말이 망가진다.
_PIECE_MIN = 3


class ConnectionFailed(RuntimeError):
    """DB 에 붙지 못했다. 메시지에는 암호가 없다.

    CLI 가 psycopg 를 몰라도 되도록 러너가 드라이버 예외를 여기서 감싼다 (D19).
    """


def redact_dsn(dsn: str) -> str:
    """오류 메시지에 암호를 흘리지 않는다. DSN 이 아니라 산문을 받아도 된다 — `service._clip` 이 그렇게 쓴다.

    URI 를 먼저 가리고 질의·키워드를 가린다 — 반대로 하면 질의 규칙이 암호 뒤의 `@` 를 삼켜 URI 규칙이
    userinfo 를 찾지 못했다(암호 안에 `?password=` 가 든 URI, 리뷰 실측).
    가리는 쪽으로 틀리는 것은 받아들인다 — `?user=a@b` 처럼 뒤에 `@` 가 더 있으면 host 까지 가려진다.
    """
    text = _mask_userinfo(dsn)
    text = _QUERY_PARAM.sub(_mask_query, text)
    return _KEYWORD_PASSWORD.sub(r"\1***", text)


def _mask_query(m: re.Match[str]) -> str:
    if unquote(m.group(2)).lower() in _SECRET_KEYS:
        return f"{m.group(1)}{m.group(2)}=***"
    return m.group(0)


def _userinfo_spans(text: str):
    """`(시작, 끝, userinfo)` — URI 마다 공백 전까지의 **마지막 `@`** 앞이 userinfo 다.

    libpq 는 첫 `@` 에서 끊지만 가리기는 넓게 한다 — 첫 '/' 나 첫 '@' 로 끊으면 암호에 날것으로 든
    '/'·'@' 뒤가 그대로 나갔다 (2026-09-27 감사 F061).
    """
    consumed = 0
    for m in _URI_START.finditer(text):
        if m.start() < consumed:
            continue
        end = m.end()
        while end < len(text) and not text[end].isspace():
            end += 1
        consumed = end
        userinfo, at, _ = text[m.end() : end].rpartition("@")
        if at:
            yield m.end(), m.end() + len(userinfo), userinfo


def _mask_userinfo(text: str) -> str:
    out, pos = [], 0
    for start, stop, userinfo in _userinfo_spans(text):
        user, has_password, _ = userinfo.partition(":")
        out.append(text[pos:start])
        out.append(f"{user}{':***' if has_password else ''}")
        pos = stop
    out.append(text[pos:])
    return "".join(out)


def _password_pieces(dsn: str) -> list[str]:
    """DSN 에서 암호로 읽힐 수 있는 조각들 — 긴 것부터.

    libpq 는 userinfo 를 **첫 `@`** 에서 끊고 나머지를 host 로 읽는다. 그래서 `P@SeCrEt` 의 `SeCrEt` 이
    `failed to resolve host 'SeCrEt@db'` 로 드라이버 문구에 나온다 (2026-09-27 리뷰 실측). 문구는 DSN 모양이 아니라
    redact_dsn 이 못 찾으므로 조각을 직접 지운다. 사용자 이름과 같은 조각은 지우지 않는다 — D16 의 기본값처럼
    공개된 값이 모든 낱말을 지우게 된다.
    """
    pieces: set[str] = set()
    users: set[str] = set()
    for _, _, userinfo in _userinfo_spans(dsn):
        user, has_password, password = userinfo.partition(":")
        users.add(user)
        if has_password:
            pieces.add(password)
            for sep in "@/:":
                pieces.update(password.split(sep))
    for m in _KEYWORD_PASSWORD.finditer(dsn):
        pieces.add(m.group(0)[len(m.group(1)) :].strip("'\""))
    for m in _QUERY_PARAM.finditer(dsn):
        if unquote(m.group(2)).lower() in _SECRET_KEYS:
            pieces.add(unquote(m.group(3)))
    try:
        params = psycopg.conninfo.conninfo_to_dict(dsn)
    except Exception:  # noqa: BLE001 - 읽지 못하는 DSN 이면 위의 조각으로 충분하다
        params = {}
    users.add(str(params.get("user") or ""))
    for key in _SECRET_KEYS:
        if params.get(key):
            pieces.add(str(params[key]))
    return sorted((p for p in pieces if len(p) >= _PIECE_MIN and p not in users), key=len, reverse=True)


def scrub_driver_text(text: str, dsn: str) -> str:
    """드라이버 문구에서 이 DSN 의 암호 조각과 DSN 모양의 비밀을 지운다. 문구는 서버 로그·stderr 로 간다 (D21)."""
    for piece in _password_pieces(dsn):
        text = text.replace(piece, "***")
    return redact_dsn(text)


@dataclass(frozen=True)
class Migration:
    version: int
    path: Path

    @property
    def name(self) -> str:
        return self.path.name


def discover(directory: Path | None = None) -> list[Migration]:
    """버전 오름차순으로 마이그레이션을 찾는다.

    파일명이 규약에 안 맞으면 조용히 건너뛰지 않고 실패한다 — 조용한 누락은
    "적용됐다" 는 잘못된 확신을 만든다.
    """
    directory = directory or DEFAULT_MIGRATIONS_DIR
    if not directory.is_dir():
        raise FileNotFoundError(f"마이그레이션 디렉토리가 없다: {directory}")

    found: dict[int, Migration] = {}
    for path in sorted(directory.iterdir()):
        if path.is_dir() or path.suffix != ".sql":
            continue
        match = _NAME.match(path.name)
        if match is None:
            raise ValueError(
                f"마이그레이션 파일명이 규약에 맞지 않는다: {path.name} "
                "(NNN_이름.sql 이어야 한다)"
            )
        version = int(match.group(1))
        if version in found:
            raise ValueError(
                f"마이그레이션 번호가 겹친다: {version} "
                f"({found[version].name}, {path.name})"
            )
        found[version] = Migration(version=version, path=path)

    if not found:
        raise FileNotFoundError(f"마이그레이션 파일이 하나도 없다: {directory}")
    return [found[v] for v in sorted(found)]


def apply(dsn: str, directory: Path | None = None) -> list[Migration]:
    """모든 마이그레이션을 순서대로 적용하고 적용한 목록을 돌려준다.

    파일 하나가 트랜잭션 하나다. 중간에 실패하면 그 파일만 롤백되고 예외가 오른다.
    """
    migrations = discover(directory)
    try:
        connection = psycopg.connect(dsn, connect_timeout=CONNECT_TIMEOUT_SECONDS)
    except psycopg.ProgrammingError:
        # 형식이 틀린 DSN 의 구문 오류 문구는 DSN 조각(때로 URI 전체)을 따옴표로 되읊는다 — 싣지 않는다.
        # `from None` 으로 사슬도 끊는다 — 트레이스백을 찍는 로거가 원인을 다시 내보낸다 (2026-09-27 감사 F061).
        # DSN 도 싣지 않는다 — 형식이 틀린 입력이 바로 가리기가 libpq 와 갈라지는 자리다(닫히지 않은 따옴표,
        # `postgresql+psycopg://`, 리뷰 실측). 고정 문구가 전부다.
        raise ConnectionFailed("DB 에 붙을 수 없다: DATABASE_URL 형식을 읽을 수 없다") from None
    except psycopg.OperationalError as exc:
        raise ConnectionFailed(
            f"DB 에 붙을 수 없다 ({redact_dsn(dsn)}): {scrub_driver_text(str(exc).strip(), dsn)}"
        ) from None  # 원래 문구는 암호 조각을 되읊을 수 있다 — 사슬로도 남기지 않는다

    with connection as conn:
        for migration in migrations:
            sql = migration.path.read_text(encoding="utf-8")
            log.info("실행 %s", migration.name)
            with conn.transaction():
                conn.execute(sql)
    return migrations
