# Sillok api (D13 의 두 서비스 중 하나, plan.md §7 3단계에서 붙었다)
#
# D18: CPython 3.12, uv. 이미지도 로컬도 3.12 다.

FROM python:3.12-slim

# PYTHONUTF8: cli 가 stdout 을 UTF-8 로 고정하지만 그 전에 죽는 경우까지 덮는다.
ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

# 의존성 레이어를 소스와 분리한다. src 는 패키지 빌드에 필요해서 함께 온다.
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev

# D17 러너가 읽는다. DDL 정본은 docs/data-model.md 다.
COPY migrations ./migrations

# serve 는 bind 전에 마이그레이션을 돌린다 (D17). host/port 는 환경변수 (D16).
CMD ["uv", "run", "--no-sync", "sillok", "serve"]
