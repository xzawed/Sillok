"""8단계 MCP 표면 (D42–D46). **DB 가 필요 없다.**

여기서 보는 것은 도구 목록·스키마·봉투·경로다. 실제 데이터로 두 얼굴을 대조하는 것은
`tests/test_mcp_db.py` 가 한다 (D46).

**클라이언트 SDK 를 쓰지 않고 JSON-RPC 를 그대로 때린다.** 전선 위의 모양이 계약이라서다.
`Host` 를 바꿔 보내는 이유는 D43 에 적혀 있다 — SDK 의 DNS 리바인딩 보호를 끄지 않는다.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from sillok import api, mcp_server, service
from sillok.config import Config

DEAD_DSN = "postgresql://sillok:x@127.0.0.1:1/sillok"

# D43: SDK 의 기본 허용 목록이 받는 주소다 (D16 의 주소이기도 하다).
# TestClient 의 기본 Host 는 `testserver` 라 막힌다 — 보호를 끄지 말고 헤더를 고친다.
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Host": "127.0.0.1:8080",
}

# plan.md §5 가 이름을 소유한다. 여기서 발명하지 않는다.
TOOL_NAMES = [
    "search_docs",
    "search_events",
    "get_event",
    "get_file",
    "save_event",
    "save_doc",
    "event_stats",
    "kb_status",
]


def _config(**overrides) -> Config:
    base = dict(
        database_url=DEAD_DSN,
        host="127.0.0.1",
        port=8080,
        workspace=".",
        bearer_token="",
        openai_api_key="",
    )
    base.update(overrides)
    return Config(**base)


@pytest.fixture
def client(request):
    overrides = getattr(request, "param", {})
    with TestClient(api.create_app(_config(**overrides))) as c:
        yield c


def rpc(client: TestClient, method: str, params: dict | None = None, path: str = "/mcp"):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post(path, json=body, headers=HEADERS)


def tools(client: TestClient) -> dict[str, dict]:
    result = rpc(client, "tools/list").json()["result"]
    return {t["name"]: t for t in result["tools"]}


def call(client: TestClient, name: str, arguments: dict | None = None) -> dict:
    """도구를 부르고 **봉투를 돌려준다.** 실패도 정상 결과여야 한다 (D44)."""
    response = rpc(client, "tools/call", {"name": name, "arguments": arguments or {}})
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result.get("isError") is False, result
    contents = result["content"]
    assert len(contents) == 1 and contents[0]["type"] == "text", contents
    return json.loads(contents[0]["text"])


# --- 목록과 스키마 (D42) -----------------------------------------------------


def test_exactly_eight_tools(client):
    """도구는 여덟뿐이다. resources·prompts 를 v1 에 만들지 않는다."""
    assert sorted(tools(client)) == sorted(TOOL_NAMES)


def test_no_tool_declares_a_required_argument(client):
    """**전부 선택이다** (D42).

    필수로 선언하면 SDK 가 도구를 부르기도 전에 거절하고, 모델은 계약이 약속한
    거절 문구 대신 pydantic 문구를 받는다.
    """
    for name, tool in tools(client).items():
        assert not tool["inputSchema"].get("required"), name


def test_save_event_offers_every_required_field(client):
    """스키마와 Service 가 갈라지지 않게 묶는다 — 필드 목록이 두 벌인 값을 치르는 자리다."""
    properties = tools(client)["save_event"]["inputSchema"]["properties"]
    for field in service.REQUIRED_FIELDS:
        assert field in properties, field


def test_descriptions_stay_short(client):
    """길면 모델이 도구를 안 고른다 (service-and-mcp.md)."""
    for name, tool in tools(client).items():
        assert 0 < len(tool.get("description", "")) <= 40, (name, tool.get("description"))


# --- 봉투 (D44) --------------------------------------------------------------


def test_missing_fields_come_back_as_the_service_message(client):
    """계약이 약속한 문장이다 — `필드 없으면 에러 메시지를 그대로 돌려줌`.

    스키마가 필수를 선언하면 이 검사가 붉어진다: 모델이 pydantic 문구를 받게 되기 때문이다.
    """
    body = call(client, "save_event")
    assert body["ok"] is False
    assert body["error"]["code"] == "VALIDATION"
    assert body["error"]["message"].startswith("missing required field")


def test_validation_failures_are_normal_results(client):
    """`VALIDATION`·`NOT_FOUND`·`CONFLICT` 를 프로토콜 오류로 접지 않는다 (D44)."""
    assert call(client, "get_event", {"project": "sillok"})["error"] == {
        "code": "VALIDATION",
        "message": "event_id must be an integer",
    }
    assert call(client, "get_file", {"project": "sillok", "path": "x", "offset": -1})["error"][
        "code"
    ] == "VALIDATION"


def test_a_dead_database_is_internal_with_the_fixed_message(client):
    """DSN 은 예외 문구를 품는다. MCP 얼굴에도 같은 고정 장치가 걸린다 (D21)."""
    body = call(client, "kb_status", {"project": "sillok"})
    assert body == {"ok": False, "error": {"code": "INTERNAL", "message": "internal error"}}


def test_the_envelope_is_the_only_shape(client):
    """`structuredContent` 를 함께 내보내지 않는다 — 두 모양은 두 계약이 된다 (D44)."""
    result = rpc(
        client, "tools/call", {"name": "kb_status", "arguments": {"project": "sillok"}}
    ).json()["result"]
    assert "structuredContent" not in result or result["structuredContent"] is None


# --- 경로와 게이트 (D43) ------------------------------------------------------


def test_both_paths_are_the_same_handler(client):
    for path in ("/mcp", "/mcp/"):
        response = rpc(client, "tools/list", path=path)
        assert response.status_code == 200, path
        assert len(response.json()["result"]["tools"]) == len(TOOL_NAMES)


def test_below_mcp_is_this_app_not_the_sdk(client):
    """마운트했다면 여기서 SDK 의 맨 `Not Found` 가 나온다 (D43)."""
    response = client.get("/mcp/nope", headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_v1_routes_keep_their_envelope(client):
    """뿌리에 마운트했다면 없는 경로가 SDK 로 흘러 봉투를 잃는다 (D43)."""
    response = client.get("/v1/nope", headers=HEADERS)
    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "error": {"code": "NOT_FOUND", "message": "Not Found"},
    }


@pytest.mark.parametrize("client", [{"bearer_token": "secret-token"}], indirect=True)
def test_the_bearer_gate_covers_mcp(client):
    """D7 게이트는 앱 미들웨어라 `/mcp` 도 덮는다. 라우트 의존성으로 옮기면 여기서 붉어진다."""
    response = rpc(client, "tools/list")
    assert response.status_code == 401
    assert response.json()["error"] == {"code": "UNAUTHORIZED", "message": "bearer required"}


def test_dns_rebinding_protection_stays_on():
    """보호를 끄지 않는다 (D43). 검사가 막히면 헤더를 고치는 것이 답이다."""
    with TestClient(api.create_app(_config())) as c:
        response = c.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={k: v for k, v in HEADERS.items() if k != "Host"},
        )
    assert response.status_code == 421


# --- 두 얼굴이 같은 것을 탄다 (D46) -------------------------------------------


def test_tools_call_the_service_in_process(monkeypatch, client):
    """HTTP 루프백을 만들면 `같은 함수를 탄다`는 D6·D19 의 문장이 거짓이 된다."""
    seen: dict[str, object] = {}

    def _fake_status(dsn, project):
        seen["args"] = (dsn, project)
        return {"documents": 1}

    monkeypatch.setattr(service, "kb_status", _fake_status)
    assert call(client, "kb_status", {"project": "sillok"}) == {
        "ok": True,
        "data": {"documents": 1},
    }
    assert seen["args"] == (DEAD_DSN, "sillok")


def test_both_faces_fold_failures_with_the_same_mapping(client):
    """매핑이 두 벌이면 한쪽만 고쳐지는 날이 온다 (D46)."""
    for exc, expected in (
        (service.ValidationFailed("나쁜 인자"), ("VALIDATION", "나쁜 인자")),
        (service.NotFound(service.NOT_FOUND_EVENT), ("NOT_FOUND", service.NOT_FOUND_EVENT)),
        (service.BaseHashMismatch("무시된다"), ("CONFLICT", service.BASE_HASH_MESSAGE)),
        (service.IngestLocked("무시된다"), ("CONFLICT", service.LOCKED_MESSAGE)),
        (RuntimeError("postgresql://u:hunter2@h/db"), ("INTERNAL", "internal error")),
    ):
        code, message = api.classify(exc)
        body, status = api.envelope_error(code, message)
        assert (code, body["error"]["message"]) == expected
        assert status == api.STATUS_FOR_CODE[code]


def test_the_mcp_path_is_one_place(client):
    """경로를 두 곳에 적지 않는다 — 라우트도 이 상수에서 나온다 (D43)."""
    assert mcp_server.MCP_PATH == "/mcp"
    paths = {getattr(route, "path", None) for route in client.app.router.routes}
    assert {"/mcp", "/mcp/"} <= paths
