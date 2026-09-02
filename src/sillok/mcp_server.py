"""MCP 도구 표면 (plan.md §7 8단계, D42–D46).

**여기에는 SQL 도 파일 접근도 없다.** 도구는 인자를 모아 `service` 함수를 인프로세스로 부르고
그 결과를 같은 봉투로 감싼다 — HTTP 얼굴과 **같은 함수, 같은 봉투**다 (D46).
HTTP 루프백을 만들지 않는다: 그 순간 "같은 함수를 탄다"는 D6·D19의 문장이 거짓이 된다.

**인자는 전부 선택이다 (D42).** 필수 판정은 Service 가 한다 — 스키마에 필수로 선언하면
SDK 가 도구를 부르기도 전에 거절하고, 모델은 계약이 약속한 거절 문구
(`필드 없으면 에러 메시지를 그대로 돌려줌`) 대신 pydantic 문구를 받는다.
기본값도 여기 복제하지 않는다. `top_k` 를 비우면 Service 가 D33 의 기본값을 쓴다.

설명문은 **짧게** 쓴다. 길면 모델이 도구를 안 고른다 (service-and-mcp.md).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer

from . import api, service
from .config import Config

log = logging.getLogger(__name__)

# D43. 표면은 이 경로와 여기에 슬래시를 붙인 것 둘뿐이다.
MCP_PATH = "/mcp"
SERVER_NAME = "sillok"


def _text(call: Callable[[], Any]) -> str:
    """Service 를 부르고 봉투 JSON 한 덩이를 만든다.

    **실패도 정상 결과다 (D44).** 프로토콜 오류로 접으면 `VALIDATION`·`NOT_FOUND`·`CONFLICT`
    셋이 "도구가 실패했다" 하나가 되고, 모델은 같은 인자로 재시도한다.
    코드와 문구는 `api.classify` 가 정한다 — HTTP 얼굴과 같은 매핑이어야 한다 (D46).
    """
    try:
        body: dict[str, Any] = api.envelope_ok(call())
    except Exception as exc:  # noqa: BLE001 - 계약의 코드로 접는 자리다
        code, message = api.classify(exc)
        if code == api.ErrorCode.INTERNAL:
            # 클라이언트에는 고정 문구만 가고, 무엇이 터졌는지는 서버 로그에 남는다 (D21).
            log.exception("MCP 도구에서 처리되지 않은 예외")
        body, _status = api.envelope_error(code, message)
    # **Starlette 의 JSONResponse 와 같은 인자다.** ensure_ascii=False 는 한국어를
    # \uXXXX 로 부풀리지 않기 위한 것이고, separators 는 두 얼굴의 문자열을
    # 바이트까지 같게 만든다 — D44 가 `같은 문자열` 이라고 했다 (Grok 지적).
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def build(cfg: Config) -> MCPServer:
    """도구 여덟을 단 서버. 이름은 plan.md §5 가 소유한다 — 여기서 바꾸지 않는다."""
    mcp = MCPServer(name=SERVER_NAME)

    # structured_output=False: 봉투 하나만 내보낸다 (D44). 켜 두면 같은 사실이
    # 텍스트와 structuredContent 두 모양으로 나가고, 두 모양은 곧 두 계약이 된다.
    @mcp.tool(name="search_docs", description="Git 문서 검색. query 필수", structured_output=False)
    def search_docs(
        project: str | None = None,
        query: str | None = None,
        top_k: int | None = None,
        doc_type: str | None = None,
        status: str | None = None,
        module: str | None = None,
    ) -> str:
        body = {
            "project": project,
            "query": query,
            "top_k": top_k,
            "doc_type": doc_type,
            "status": status,
            "module": module,
        }
        return _text(lambda: service.search_docs(cfg.database_url, body, cfg.openai_api_key))

    @mcp.tool(
        name="search_events",
        description="사건 원장 검색. 필터 먼저, query 는 선택",
        structured_output=False,
    )
    def search_events(
        project: str | None = None,
        query: str | None = None,
        kind: str | None = None,
        module: str | None = None,
        since: str | None = None,
        until: str | None = None,
        top_k: int | None = None,
    ) -> str:
        body = {
            "project": project,
            "query": query,
            "kind": kind,
            "module": module,
            "since": since,
            "until": until,
            "top_k": top_k,
        }
        return _text(lambda: service.search_events(cfg.database_url, body))

    @mcp.tool(name="get_event", description="이벤트 원문 하나", structured_output=False)
    def get_event(event_id: int | None = None, project: str | None = None) -> str:
        return _text(lambda: service.get_event(cfg.database_url, event_id, project))

    @mcp.tool(
        name="get_file", description="색인된 문서의 원문 창 (4000자)", structured_output=False
    )
    def get_file(
        project: str | None = None, path: str | None = None, offset: int | None = None
    ) -> str:
        return _text(
            lambda: service.get_file(cfg.database_url, project, path, offset, cfg.workspace)
        )

    @mcp.tool(
        name="save_event",
        description="사건을 원장에 남긴다. 필수 필드 없으면 거절",
        structured_output=False,
    )
    def save_event(
        project: str | None = None,
        kind: str | None = None,
        title: str | None = None,
        summary: str | None = None,
        occurred_at: str | None = None,
        result: str | None = None,
        module: str | None = None,
        root_cause: str | None = None,
        resolution: str | None = None,
        severity: str | None = None,
        resolved_at: str | None = None,
        source: str | None = None,
        related_doc_path: str | None = None,
        payload: dict[str, Any] | None = None,
        created_by: str | None = None,
    ) -> str:
        body = {
            "project": project,
            "kind": kind,
            "title": title,
            "summary": summary,
            "occurred_at": occurred_at,
            "result": result,
            "module": module,
            "root_cause": root_cause,
            "resolution": resolution,
            "severity": severity,
            "resolved_at": resolved_at,
            "source": source,
            "related_doc_path": related_doc_path,
            "payload": payload,
            "created_by": created_by,
        }
        # source 를 비우면 Service 가 기본값 agent 를 넣는다 (D25). 여기서 채우지 않는다.
        return _text(lambda: service.save_event(cfg.database_url, _without_none(body)))

    @mcp.tool(
        name="save_doc", description="문서 패치 제안. Git 에 쓰지 않는다", structured_output=False
    )
    def save_doc(
        project: str | None = None,
        path: str | None = None,
        body: str | None = None,
        base_hash: str | None = None,
    ) -> str:
        request = {"project": project, "path": path, "body": body, "base_hash": base_hash}
        return _text(lambda: service.save_doc(cfg.database_url, request, cfg.workspace))

    @mcp.tool(
        name="event_stats", description="사건 집계. 벡터를 쓰지 않는다", structured_output=False
    )
    def event_stats(
        project: str | None = None, module: str | None = None, since: str | None = None
    ) -> str:
        return _text(
            lambda: service.event_stats(
                cfg.database_url, project, module, api.since_filter(since)
            )
        )

    @mcp.tool(name="kb_status", description="색인·원장 현황", structured_output=False)
    def kb_status(project: str | None = None) -> str:
        return _text(lambda: service.kb_status(cfg.database_url, project))

    return mcp


def _without_none(body: dict[str, Any]) -> dict[str, Any]:
    """비운 인자를 아예 없는 것으로 만든다.

    `build_event` 는 `body.get(f) in (None, "")` 로 필수를 보므로 결과는 같지만,
    `source` 처럼 **없을 때 기본값이 붙는** 필드는 키가 없어야 그 규칙이 그대로 돈다.
    """
    return {k: v for k, v in body.items() if v is not None}


class Transport:
    """ASGI 핸들러. **마운트가 아니라 두 경로에만 붙는다** (D43).

    마운트하면 그 아래 아무 경로나 SDK 의 맨 `Not Found` 를 돌려주어 D21 의 봉투가 깨진다.
    """

    def __init__(self, server: MCPServer) -> None:
        self._server = server

    async def __call__(self, scope, receive, send) -> None:
        await self._server.session_manager.handle_request(scope, receive, send)


def transport(server: MCPServer) -> Transport:
    """전송을 만든다. **세션을 두지 않고 응답은 JSON 이다** (D43).

    `session_manager` 는 `streamable_http_app()` 을 한 번 부른 뒤에야 생긴다(실측).
    그래서 여기서 부르고 만들어진 앱은 쓰지 않는다 — 우리가 쓰는 것은 세션 관리자뿐이다.
    """
    server.streamable_http_app(
        streamable_http_path="/", json_response=True, stateless_http=True
    )
    return Transport(server)
