"""D16 환경변수 계약.

정본: adr/0001-v1-stack-decisions.md §D16. 사본: .env.example.
이름이나 기본값을 여기서 바꾸지 않는다 — 정본을 먼저 고친다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_DATABASE_URL = "postgresql://sillok:sillok@127.0.0.1:5432/sillok"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_WORKSPACE = "."


@dataclass(frozen=True)
class Config:
    database_url: str
    host: str
    port: int
    workspace: str
    bearer_token: str
    openai_api_key: str

    @property
    def auth_required(self) -> bool:
        """D7: 빈 값이면 로컬 무인증. 값이 있으면 Bearer 를 요구한다."""
        return bool(self.bearer_token)

    @property
    def embeddings_enabled(self) -> bool:
        """D2: 키가 없으면 embedding 은 NULL 이고 tsv 키워드 검색만 동작한다."""
        return bool(self.openai_api_key)


def _port_from_env(raw: str) -> int:
    try:
        port = int(raw)
    except ValueError:
        raise ValueError(f"SILLOK_PORT 가 정수가 아니다: {raw!r}") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"SILLOK_PORT 가 범위 밖이다: {port}")
    return port


def load(env: dict[str, str] | None = None) -> Config:
    src = os.environ if env is None else env
    return Config(
        database_url=src.get("DATABASE_URL") or DEFAULT_DATABASE_URL,
        host=src.get("SILLOK_HOST") or DEFAULT_HOST,
        port=_port_from_env(src.get("SILLOK_PORT") or str(DEFAULT_PORT)),
        workspace=src.get("SILLOK_WORKSPACE") or DEFAULT_WORKSPACE,
        # 빈 문자열이 의미를 갖는 값들이다. or 로 기본값을 덮지 않는다.
        bearer_token=src.get("SILLOK_BEARER_TOKEN", ""),
        openai_api_key=src.get("OPENAI_API_KEY", ""),
    )
