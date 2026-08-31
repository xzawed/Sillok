"""D17 마이그레이션 러너.

**이 모듈은 Service 쪽에 있고 CLI 쪽에 있지 않다.** D19 가 금지하는 것은
CLI 가 자기 SQL 계층을 갖는 것이다. 러너는 하나이고 진입점이 둘이다 —
`sillok migrate`(지금)와 `sillok serve` 기동 시 bind 전(3단계).

DDL 정본은 docs/data-model.md 다. 여기서 SQL 을 만들지 않고 migrations/*.sql 을 읽어 실행한다.

버전 추적 테이블은 두지 않는다. D17 이 멱등(IF NOT EXISTS)을 재기동 안전의
수단으로 정했기 때문이다. 되돌릴 수 없는 변경이 필요해지면 그때 결정하고 ADR 에 기록한다.
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
    with psycopg.connect(dsn, connect_timeout=CONNECT_TIMEOUT_SECONDS) as conn:
        for migration in migrations:
            sql = migration.path.read_text(encoding="utf-8")
            log.info("적용 %s", migration.name)
            with conn.transaction():
                conn.execute(sql)
    return migrations
