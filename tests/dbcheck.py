"""DB 가 필요한 검사의 공통 장치.

skip 사유가 거짓이면 안 된다 — `docker compose up -d --wait` 는 5432 를 게시하지 않으므로
호스트에서 다시 돌려도 똑같이 skip 된다 (D16). 두 경로를 정확히 안내한다.
"""

from __future__ import annotations

import os

import psycopg
import pytest

DSN = os.environ.get("DATABASE_URL", "postgresql://sillok:sillok@127.0.0.1:5432/sillok")

SKIP_REASON = (
    f"Postgres 에 붙을 수 없다: {DSN}. 호스트에서 돌리려면 5432 게시가 필요한데"
    " D16 이 그것을 막는다 — DB 검사까지 돌리려면"
    " `docker compose --profile test run --rm test` (D22)."
    " 호스트에서 그대로 돌리려면 compose.override.example.yml 을 복사한다."
)


def db_available() -> bool:
    try:
        with psycopg.connect(DSN, connect_timeout=3):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not db_available(), reason=SKIP_REASON)
