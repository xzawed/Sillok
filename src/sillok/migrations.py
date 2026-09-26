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

import psycopg

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
# D16 의 정식 DSN 만 가리면 나머지 형태에서 암호가 오류 메시지로 샌다.
# `sslpassword` 도 비밀이다. 질의 뒤의 `password=` 는 _QUERY_PASSWORD 가 맡는다(lookbehind).
# 큰따옴표는 libpq 의 인용이 아니지만 사람이 그렇게 쓰면 뒷조각이 샜다 — 같이 가린다 (2026-09-27 감사 F061).
_KEYWORD_PASSWORD = re.compile(
    r"""(?i)((?<![?&])\b(?:ssl)?password\s*=\s*)(?:'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|\S+)"""
)
_QUERY_PASSWORD = re.compile(r"(?i)([?&](?:ssl)?password=)[^&#]*")
# URI 는 libpq 의 접두사로만 찾는다. 아무 `scheme://` 나 시작으로 보면 암호에 든 `sec://` 가 새 URI 가 되어
# 그 뒤가 사용자 이름으로 나갔다(실측).
_URI_START = re.compile(r"(?i)postgres(?:ql)?://")


class ConnectionFailed(RuntimeError):
    """DB 에 붙지 못했다. 메시지에는 암호가 없다.

    CLI 가 psycopg 를 몰라도 되도록 러너가 드라이버 예외를 여기서 감싼다 (D19).
    """


def redact_dsn(dsn: str) -> str:
    """오류 메시지에 암호를 흘리지 않는다. DSN 이 아니라 산문을 받아도 된다 — `service._clip` 이 그렇게 쓴다.

    가리는 쪽으로 틀리는 것은 받아들인다 — `?user=a@b` 처럼 뒤에 `@` 가 더 있으면 host 까지 가려진다.
    """
    # 키워드·질의 비밀을 먼저 가린다 — 값에 든 '://' 나 '@' 가 아래 URI 규칙을 속이지 않게.
    text = _KEYWORD_PASSWORD.sub(r"\1***", _QUERY_PASSWORD.sub(r"\1***", dsn))
    # URI 는 **나올 때마다** 가린다. 한 URI 의 userinfo 끝은 다음 URI 전까지의 **마지막 '@'** 다 —
    # 첫 '/' 로 끊으면 암호에 날것으로 든 '/' 뒤가 그대로 나갔다 (2026-09-27 감사 F061).
    starts = [m.end() for m in _URI_START.finditer(text)]
    if not starts:
        return text
    out = [text[: starts[0]]]
    for begin in starts:
        following = _URI_START.search(text, begin)
        segment = text[begin : following.start() if following else len(text)]
        credentials, at, host = segment.rpartition("@")
        if at:
            user, has_password, _ = credentials.partition(":")
            segment = f"{user}{':***' if has_password else ''}@{host}"
        out.append(segment)
        if following:
            out.append(following.group(0))
    return "".join(out)


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
        raise ConnectionFailed(
            f"DB 에 붙을 수 없다 ({redact_dsn(dsn)}): DATABASE_URL 형식을 읽을 수 없다"
        ) from None
    except psycopg.OperationalError as exc:
        raise ConnectionFailed(
            f"DB 에 붙을 수 없다 ({redact_dsn(dsn)}): {redact_dsn(str(exc).strip())}"
        ) from exc

    with connection as conn:
        for migration in migrations:
            sql = migration.path.read_text(encoding="utf-8")
            log.info("실행 %s", migration.name)
            with conn.transaction():
                conn.execute(sql)
    return migrations
