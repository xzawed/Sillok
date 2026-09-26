"""DB 가 필요한 검사의 공통 장치.

skip 사유가 거짓이면 안 된다 — `docker compose up -d --wait` 는 5432 를 게시하지 않으므로
호스트에서 다시 돌려도 똑같이 skip 된다 (D16). 두 경로를 정확히 안내한다.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from sillok import workspace
from sillok.migrations import redact_dsn

DSN = os.environ.get("DATABASE_URL", "postgresql://sillok:sillok@127.0.0.1:5432/sillok")


def skip_reason(dsn: str) -> str:
    """`pytest -rs` 가 검사마다 찍는 사유다. DSN 은 가려서 싣는다 — 예전에는 암호째 실었다 (2026-09-27 감사 F023).
    접두 `Postgres 에 붙을 수 없다` 는 scripts/evidence.mjs 가 찾는 판정 문자열이다 — 글자를 바꾸지 않는다."""
    return (
        f"Postgres 에 붙을 수 없다: {redact_dsn(dsn)}. 호스트에서 돌리려면 5432 게시가 필요한데"
        " D16 이 그것을 막는다 — DB 검사까지 돌리려면"
        " `docker compose --profile test run --rm test` (D22)."
        " 호스트에서 그대로 돌리려면 compose.override.example.yml 을 복사한다."
    )


SKIP_REASON = skip_reason(DSN)


def db_available() -> bool:
    try:
        with psycopg.connect(DSN, connect_timeout=3):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not db_available(), reason=SKIP_REASON)

# ingest 는 D36 의 걸음으로 읽는다 (D70 ③). 그 플래그가 없는 호스트(Windows)에서는 5432 를 게시해 DB 에 붙어도
# ingest 가 스캔 전에 `failed` 로 끝난다 — 실패가 아니라 skip 이 맞다. 이 검사들은 --profile test 에서 돈다.
WALK_SKIP_REASON = (
    "O_NOFOLLOW / O_DIRECTORY 가 없는 플랫폼이다 — ingest 는 D36 의 걸음으로 읽는다 (D70 ③)."
    " `docker compose --profile test run --rm test` 에서 돈다 (D22)."
)
needs_walk = pytest.mark.skipif(not workspace.flags_supported(), reason=WALK_SKIP_REASON)


def require_walk() -> None:
    """ingest 를 부르는 픽스처가 먼저 부른다. 모듈 전체를 막지 않아도 되는 자리다."""
    if not workspace.flags_supported():
        pytest.skip(WALK_SKIP_REASON)
