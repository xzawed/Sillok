# Sillok api (D13 의 두 서비스 중 하나, plan.md §7 3단계에서 붙었다)
#
# D18: CPython 3.12, uv. 이미지도 로컬도 3.12 다.

# 다단계다. runtime 이 제품 이미지이고 test 는 거기에 tests/ 와 dev 의존성을 더한 것이다.
# **compose 의 api 는 target: runtime 을 명시해야 한다** — build 는 마지막 스테이지를
# 기본으로 쓰므로 빠뜨리면 pytest 가 운영 이미지로 들어간다 (D22 가 피하려던 바로 그것).
FROM python:3.12-slim AS runtime

# PYTHONUTF8: cli 가 stdout 을 UTF-8 로 고정하지만 그 전에 죽는 경우까지 덮는다.
# PATH: plan.md §9 의 판정 명령이 `compose exec api sillok ingest` 다. 이것이 없으면
# 그 줄이 `executable file not found` 로 죽는다 (2026-09-02 실측). uv run 은 그대로 돈다.
ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

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


# D22: 커밋된 구성에서 DB 검사를 돌리는 스테이지.
# 내부 네트워크로 db:5432 에 붙으므로 5432 를 호스트에 게시할 필요가 없다.
FROM runtime AS test

COPY tests ./tests
RUN uv sync --frozen

CMD ["uv", "run", "--no-sync", "pytest", "-q"]


# 마지막 스테이지를 다시 runtime 으로 돌려놓는다.
# docker build 는 --target 이 없으면 **마지막** 스테이지를 만든다. test 로 끝내면
# `docker build .` 한 줄이 pytest 를 실은 이미지를 뱉는다 — compose 를 거치지 않는 경로다.
# compose 의 api 는 target: runtime 을 명시하므로 여기에 기대지 않지만,
# 기본값이 안전한 쪽이어야 한다.
FROM runtime AS default
