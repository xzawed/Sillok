"""FastAPI 골격과 공통 응답 (plan.md §7 3단계, D21).

**업무 라우트는 여기 없다.** `save_event`·`event_stats`·`kb_status`는 4단계이고,
그 전에 Q16·Q18·Q21이 답해져야 한다. 뜨기만 하는 스텁을 §9의 판정 대상 경로에
올려 두면 통과한 것처럼 보이므로 만들지 않는다.

지금 이 앱이 하는 일은 하나다: **무엇이 오든 공통 봉투로 답한다.**
FastAPI 기본 응답 `{"detail": ...}`은 service-and-mcp.md 계약 위반이므로 전부 덮는다.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .config import Config

log = logging.getLogger(__name__)


class ErrorCode:
    """정본: docs/service-and-mcp.md. 매핑 정본: adr/0001 §D21."""

    VALIDATION = "VALIDATION"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    INTERNAL = "INTERNAL"


STATUS_FOR_CODE = {
    ErrorCode.VALIDATION: 422,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.INTERNAL: 500,
}

# 역방향. 프레임워크가 상태코드만 들고 올 때 쓴다.
_CODE_FOR_STATUS = {status: code for code, status in STATUS_FOR_CODE.items()}

# INTERNAL 은 고정 문자열이다. 예외 문구를 실어 보내지 않는다 —
# psycopg 예외는 DSN 을 품는 일이 잦고 토큰·키도 같은 길로 샌다 (D21).
INTERNAL_MESSAGE = "internal error"


def ok(data: object = None) -> JSONResponse:
    return JSONResponse({"ok": True, "data": data if data is not None else {}})


def error(code: str, message: str) -> JSONResponse:
    status = STATUS_FOR_CODE.get(code)
    if status is None:
        # 계약에 없는 코드를 내보내느니 INTERNAL 로 떨어뜨린다.
        log.error("계약에 없는 에러 코드: %s", code)
        code, status, message = ErrorCode.INTERNAL, 500, INTERNAL_MESSAGE
    return JSONResponse(
        {"ok": False, "error": {"code": code, "message": message}}, status_code=status
    )


def _code_for_status(status: int) -> str:
    """상태코드만 있을 때 계약 안의 코드로 되돌린다.

    enum 에 없는 상태(405 등)는 새 코드를 발명하지 않고 4xx 는 VALIDATION,
    5xx 는 INTERNAL 로 둔다. 코드를 늘리는 것은 계약 변경이다.
    """
    known = _CODE_FOR_STATUS.get(status)
    if known is not None:
        return known
    return ErrorCode.INTERNAL if status >= 500 else ErrorCode.VALIDATION


def _flatten(exc: RequestValidationError) -> str:
    """Pydantic 의 오류 목록을 한 줄로 만든다.

    봉투의 message 는 문자열이다 (service-and-mcp.md 예: "result required").
    loc 배열을 그대로 실을 자리가 없다.
    """
    parts = []
    for err in exc.errors():
        location = ".".join(str(x) for x in err.get("loc", ()) if x != "body")
        parts.append(f"{location}: {err.get('msg', '')}".strip(": "))
    return "; ".join(parts) or "invalid request"


def _encode(value: str, encoding: str) -> bytes | None:
    """인코딩할 수 없으면 None. 인증 경로에서 예외를 올리지 않기 위해서다."""
    try:
        return value.encode(encoding)
    except UnicodeError:
        return None


class BearerGate(BaseHTTPMiddleware):
    """D7 게이트. 토큰이 설정됐을 때만 켜진다.

    미들웨어로 두는 이유는 없는 경로까지 포함해 **모든** 요청을 덮기 위해서다.
    라우트 의존성으로 두면 404 경로가 인증 없이 응답한다.

    기본 `fastapi.security.HTTPBearer`를 쓰지 않는다 — 그쪽은
    `{"detail": "Not authenticated"}`를 돌려주어 공통 봉투를 깬다.
    """

    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        # 헤더가 여러 개면 거절한다. Headers.get 은 첫 번째만 보므로,
        # 맞는 토큰 뒤에 아무 값이나 덧붙여 보내는 요청이 통과해 버린다.
        presented_headers = request.headers.getlist("authorization")
        if len(presented_headers) != 1:
            return error(ErrorCode.UNAUTHORIZED, "bearer required")

        scheme, _, presented = presented_headers[0].partition(" ")
        # 바이트로 비교한다. compare_digest 는 비-ASCII str 에 TypeError 를 내고,
        # 헤더는 latin-1 이라 0x80~0xFF 가 그대로 들어온다. str 로 비교하면
        # 인증 실패가 INTERNAL 500 으로 새어 나간다 (실측으로 확인).
        #
        # 인코딩이 양쪽에서 다르다는 점이 함정이다. Starlette 은 헤더를 latin-1 로
        # 디코드하므로 latin-1 로 되돌려야 클라이언트가 보낸 원래 바이트가 나온다.
        # 반면 self._token 은 os.environ 이 UTF-8 로 디코드한 값이다.
        # 둘을 맞추지 않으면 ASCII 밖 토큰이 영원히 불일치한다.
        presented_bytes = _encode(presented.strip(), "latin-1")
        expected_bytes = _encode(self._token, "utf-8")
        if (
            scheme.lower() != "bearer"
            or presented_bytes is None
            or expected_bytes is None
            or not secrets.compare_digest(presented_bytes, expected_bytes)
        ):
            # 무엇이 틀렸는지(헤더 없음/스킴 오류/토큰 불일치)를 구분해 알려주지 않는다.
            return error(ErrorCode.UNAUTHORIZED, "bearer required")
        return await call_next(request)


def create_app(config: Config | None = None) -> FastAPI:
    cfg = config or Config(
        database_url="", host="", port=0, workspace="", bearer_token="", openai_api_key=""
    )
    app = FastAPI(
        title="Sillok",
        version="0.0.1",
        # D12: 사람이 볼 웹 페이지는 v1 비범위. openapi_url 까지 꺼야 한다 —
        # docs_url 만 끄면 /openapi.json 이 살아남아 봉투 밖 200 을 돌려준다.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        # 슬래시 리다이렉트는 라우터가 **핸들러보다 먼저** 빈 본문 307 을 낸다.
        # 계약 밖 상태에 봉투도 없는 응답이라 끈다. 경로는 정확히 일치해야 한다.
        redirect_slashes=False,
    )

    if cfg.auth_required:
        app.add_middleware(BearerGate, token=cfg.bearer_token)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error(ErrorCode.VALIDATION, _flatten(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # 없는 경로의 404 가 여기로 온다. get_event 의 404 대 빈 결과는 Q12 로 열려 있다.
        return error(_code_for_status(exc.status_code), str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # 서버 로그에는 전부 남기고 클라이언트에는 고정 문구만 준다.
        log.exception("처리되지 않은 예외: %s %s", request.method, request.url.path)
        return error(ErrorCode.INTERNAL, INTERNAL_MESSAGE)

    return app
