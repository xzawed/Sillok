"""FastAPI 어댑터 (plan.md §7 3–7단계, D21·D23–D25·D35–D41).

**여기에는 SQL이 없다.** 라우트는 인자를 읽어 `service.py`의 함수를 부를 뿐이다 (D19).
`api.py`가 직접 DB를 만지기 시작하면 데이터 접근 계층이 둘이 된다.

무엇이 오든 공통 봉투로 답한다 — FastAPI 기본 응답 `{"detail": ...}`은
service-and-mcp.md 계약 위반이므로 전부 덮는다.

붙어 있는 업무 라우트는 4단계의 셋, 5단계의 ingest, 6단계의 검색 둘, 7단계의 단건·제안 셋이고,
8단계의 MCP 전송이 `POST /mcp`·`POST /mcp/` 둘로 붙는다 (D43).
`GET /v1/docs`는 §7이 어느 단계에도 넣지 않았으므로 여기서 단계를 발명하지 않는다 (Q30).
뜨기만 하는 스텁을 §9 판정 대상에 올리지 않는다.
"""

from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.routing import Route

from . import service
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

# NOT_FOUND 의 문구는 service 가 소유한 세 상수뿐이다 (D35: 없는 것과 남의 것은 같은 답).
# 그 밖의 문구는 버린다 — 이 핸들러만 `str(exc)` 를 그대로 흘리므로, 나중에 누가
# `NotFound(f"...{exc}")` 를 쓰면 경로나 DSN 이 여기로 새어 나간다 (Grok 지적).
# D21 이 INTERNAL 에 건 이유와 같다: **호출자를 믿지 않는다.**
NOT_FOUND_FALLBACK = "not found"
NOT_FOUND_MESSAGES = frozenset(
    {service.NOT_FOUND_EVENT, service.NOT_FOUND_FILE, service.NOT_FOUND_DOC}
)


def envelope_ok(data: object = None) -> dict[str, Any]:
    """성공 봉투. **모양이 한 곳에만 있어야 두 얼굴이 같은 문자열을 낸다** (D46)."""
    return {"ok": True, "data": data if data is not None else {}}


def envelope_error(code: str, message: str) -> tuple[dict[str, Any], int]:
    """실패 봉투와 그 상태코드. **실패 응답은 반드시 이 함수를 지난다.**

    라우트나 MCP 도구가 봉투를 손으로 조립하면 여기의 고정 장치가 통째로 우회된다.
    """
    status = STATUS_FOR_CODE.get(code)
    if status is None:
        # 계약에 없는 코드를 내보내느니 INTERNAL 로 떨어뜨린다.
        log.error("계약에 없는 에러 코드: %s (message=%r)", code, message)
        code, status = ErrorCode.INTERNAL, 500

    if code == ErrorCode.INTERNAL:
        # **호출자를 믿지 않는다.** INTERNAL 의 본문은 여기서 무조건 고정한다 (D21).
        # 이 한 줄이 없으면 HTTPException(500, detail=...) 하나로 DSN 이 새어 나간다.
        # 넘어온 문구는 서버 로그에만 남긴다.
        if message != INTERNAL_MESSAGE:
            log.error("INTERNAL 메시지를 버렸다: %r", message)
        message = INTERNAL_MESSAGE

    return {"ok": False, "error": {"code": code, "message": message}}, status


def classify(exc: BaseException) -> tuple[str, str]:
    """예외를 계약의 코드와 문구로 접는다.

    **HTTP 핸들러와 MCP 도구가 같은 이것을 쓴다** (D46). 두 얼굴이 매핑을 따로 가지면
    한쪽만 고쳐지는 날이 온다 — 이 저장소의 재발 1위 부류다.
    """
    if isinstance(exc, service.ValidationFailed):
        # D21: VALIDATION 만 메시지를 그대로 돌려준다. 클라이언트가 고쳐야 하는 것이라서다.
        return ErrorCode.VALIDATION, str(exc)
    if isinstance(exc, service.NotFound):
        # D35: 없는 id 와 남의 id 는 같은 응답이다. 문구는 service 의 세 상수뿐이고,
        # **그 목록 밖이면 버린다** — 이 분기만 예외 문구를 그대로 흘리므로 나중에
        # NotFound(f"...{exc}") 가 하나 들어오면 경로나 DSN 이 그 길로 샌다.
        # **없는 경로**의 404 는 여기로 오지 않는다 (그쪽은 StarletteHTTPException 이다).
        message = str(exc)
        if message not in NOT_FOUND_MESSAGES:
            log.error("계약에 없는 NOT_FOUND 문구를 버렸다: %r", message)
            message = NOT_FOUND_FALLBACK
        return ErrorCode.NOT_FOUND, message
    if isinstance(exc, service.BaseHashMismatch):
        # CONFLICT 의 둘째 발신자다 (D38). D32 의 문구를 쓰지 않는다 — 원인이 다르다.
        return ErrorCode.CONFLICT, service.BASE_HASH_MESSAGE
    if isinstance(exc, service.IngestLocked):
        # D32 가 만든 첫 발신자. 이 분기가 없으면 락 거절이 409 가 아니라 500 이 된다.
        return ErrorCode.CONFLICT, service.LOCKED_MESSAGE
    return ErrorCode.INTERNAL, INTERNAL_MESSAGE


def ok(data: object = None) -> JSONResponse:
    return JSONResponse(envelope_ok(data))


def error(code: str, message: str) -> JSONResponse:
    body, status = envelope_error(code, message)
    return JSONResponse(body, status_code=status)


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

    # **여기서 부른다.** mcp_server 가 이 파일의 봉투와 매핑을 쓰므로 (D46) 모듈 층에서
    # 서로를 import 하면 순환이 된다. cli.py 가 uvicorn 을 늦게 부르는 것과 같은 이유다.
    from . import mcp_server as mcp_tools

    mcp = mcp_tools.build(cfg)
    mcp_transport = mcp_tools.transport(mcp)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # 이것을 돌리지 않으면 /mcp 가 "Task group is not initialized" 로 죽는다.
        # 마운트한 앱의 lifespan 은 Starlette 이 돌려 주지 않고, 우리는 마운트도 하지 않는다 (D43).
        async with mcp.session_manager.run():
            yield

    app = FastAPI(
        lifespan=lifespan,
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
        # 없는 **경로**의 404 가 여기로 온다. 없는 **행**의 404 는 service.NotFound 다 (D35).
        return error(_code_for_status(exc.status_code), str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # 서버 로그에는 전부 남기고 클라이언트에는 고정 문구만 준다.
        log.exception("처리되지 않은 예외: %s %s", request.method, request.url.path)
        return error(ErrorCode.INTERNAL, INTERNAL_MESSAGE)

    async def _service_failure(_: Request, exc: Exception) -> JSONResponse:
        # 매핑은 classify 하나뿐이다 — MCP 도구가 같은 것을 쓴다 (D46).
        return error(*classify(exc))

    for failure in (
        service.ValidationFailed,
        service.NotFound,
        service.BaseHashMismatch,
        service.IngestLocked,
    ):
        app.add_exception_handler(failure, _service_failure)

    _mount_v1(app, cfg)
    _mount_mcp(app, mcp_transport)
    return app


def since_filter(raw: str | None) -> datetime | None:
    """`since` 질의 인자를 시각으로 바꾼다. **두 얼굴이 같은 것을 쓴다** (D46)."""
    if raw is None:
        return None
    return service.parse_timestamp(raw, "since")


def _mount_v1(app: FastAPI, cfg: Config) -> None:
    """4–7단계의 라우트 (plan §7). 여기서 SQL 을 쓰지 않는다 — service 함수만 부른다."""

    @app.post("/v1/events")
    async def save_event(body: dict[str, Any]) -> JSONResponse:
        return ok(service.save_event(cfg.database_url, body))

    @app.get("/v1/stats/events")
    async def event_stats(
        project: str, module: str | None = None, since: str | None = None
    ) -> JSONResponse:
        return ok(service.event_stats(cfg.database_url, project, module, since_filter(since)))

    @app.get("/v1/status")
    async def kb_status(project: str) -> JSONResponse:
        return ok(service.kb_status(cfg.database_url, project))

    @app.post("/v1/search/docs")
    async def search_docs(body: dict[str, Any]) -> JSONResponse:
        # 빈 결과는 오류가 아니다 — 200 에 {"results": []} 다 (D21).
        # 모델이 채울 문장을 여기서 넣지 않는다.
        return ok(service.search_docs(cfg.database_url, body, cfg.openai_api_key))

    @app.post("/v1/search/events")
    async def search_events(body: dict[str, Any]) -> JSONResponse:
        # v1 은 이벤트를 임베딩하지 않는다 (D34) — 키가 필요 없다.
        return ok(service.search_events(cfg.database_url, body))

    @app.post("/v1/ingest")
    async def run_ingest(body: dict[str, Any]) -> JSONResponse:
        # 운영자 진입점은 CLI 다 (D20). 여기는 같은 Service 함수의 HTTP 얼굴이고
        # 인자까지 같다 — 변경 파일 목록을 받지 않는다 (D30).
        # run 행이 생긴 모든 경우에 ok: true 다. ok: false 는 락 거절과 D37 거절뿐이다.
        # **같은 거절이 이 얼굴에도 걸린다** — CLI 에만 걸면 이 문으로 우회된다 (D37).
        return ok(
            service.ingest(
                cfg.database_url,
                body.get("project"),
                service.resolve_workspace(body.get("workspace"), cfg.workspace),
                cfg.openai_api_key,
            )
        )

    @app.get("/v1/events/{event_id}")
    async def get_event(event_id: int, project: str) -> JSONResponse:
        # project 는 필수다 (D35). 없으면 FastAPI 요청 검증이 VALIDATION 으로 접는다.
        # 정수가 아닌 {id} 도 같은 자리에서 걸린다.
        return ok(service.get_event(cfg.database_url, event_id, project))

    @app.get("/v1/files")
    async def get_file(project: str, path: str, offset: int | None = None) -> JSONResponse:
        # 뿌리는 하나다 (D37). project 는 원장의 라벨이지 경로 성분이 아니다.
        # offset 의 기본값(0)은 **Service 한 곳에만** 둔다 — 두 얼굴이 같은 값을 쓰게 (D36·D46).
        return ok(service.get_file(cfg.database_url, project, path, offset, cfg.workspace))

    @app.post("/v1/docs/proposals")
    async def save_doc(body: dict[str, Any]) -> JSONResponse:
        # v1 은 제안 본문과 diff 만 돌려준다. Git 에 쓰지 않는다 (D3·D38).
        return ok(service.save_doc(cfg.database_url, body, cfg.workspace))


def _mount_mcp(app: FastAPI, transport: object) -> None:
    """8단계 (D43). **마운트하지 않는다** — 정확히 두 경로만 잇는다.

    뿌리에 마운트하면 라우트에 걸리지 않은 모든 경로가 MCP 앱으로 흘러 D21 의 봉투가 깨지고,
    `/mcp` 에 마운트하면 `redirect_slashes` 를 끈 탓에 맨 `/mcp` 가 잡히지 않는다 (둘 다 실측).
    두 경로만 이으면 `/mcp/아무거나` 는 이 앱의 404 봉투로 돌아온다.
    """
    from . import mcp_server as mcp_tools

    for path in (mcp_tools.MCP_PATH, mcp_tools.MCP_PATH + "/"):
        app.router.routes.append(
            Route(path, endpoint=transport, methods=["GET", "POST", "DELETE"])
        )
