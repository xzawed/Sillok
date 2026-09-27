"""HTTP 어댑터 검증 — 무엇이 오든 공통 봉투로 답하는가 (D21) + 4단계 라우트.

핸들러 자체(검증 실패·없는 경로·예외)를 때리는 라우트는 테스트가 직접 붙인다.
앱에 스텁 라우트를 심으면 아직 안 만든 단계가 구현된 것처럼 보인다.
"""

from __future__ import annotations

import pytest
from starlette._utils import is_async_callable
from fastapi.testclient import TestClient
from pydantic import BaseModel

from sillok import api, service
from sillok.config import Config


def _config(**overrides) -> Config:
    base = dict(
        database_url="postgresql://sillok:sillok@127.0.0.1:5432/sillok",
        host="127.0.0.1",
        port=8080,
        workspace=".",
        bearer_token="",
        openai_api_key="",
    )
    base.update(overrides)
    return Config(**base)


# plan.md §5 의 업무 라우트 아홉. 경로로 고른다 — 함수 이름을 바꿔도 검사가 따라온다.
BUSINESS_ROUTES = [
    "/v1/events",
    "/v1/stats/events",
    "/v1/status",
    "/v1/search/docs",
    "/v1/search/events",
    "/v1/ingest",
    "/v1/events/{event_id}",
    "/v1/files",
    "/v1/docs/proposals",
]


def test_business_routes_are_not_coroutines():
    """업무 라우트는 `def` 여야 한다 — `async def` 면 모든 요청이 줄을 선다.

    본문이 동기 `service.*` 한 번이라 `await` 할 것이 없는데 `async def` 로 두면
    그 DB 왕복 동안 이벤트 루프가 잡힌다. 실측으로 동시 여덟 건이 이상적 병렬의
    여덟 배였다. `def` 면 Starlette 가 스레드풀에서 돌린다.

    **시간을 재지 않는다** — 느린 기계에서 거짓 실패가 난다. 바꾼 그 키워드를 본다.
    Starlette 가 디스패치에 쓰는 술어를 그대로 쓴다 — `iscoroutinefunction` 은
    `functools.partial(async_fn)` 을 놓친다.
    """
    app = api.create_app(_config())
    by_path = {r.path: r for r in app.routes if hasattr(r, "endpoint")}

    missing = [p for p in BUSINESS_ROUTES if p not in by_path]
    assert not missing, missing

    coroutines = [
        p for p in BUSINESS_ROUTES if is_async_callable(by_path[p].endpoint)
    ]
    assert coroutines == [], coroutines


class _Body(BaseModel):
    result: str


# 4단계 검증 케이스의 바탕. 유효한 최소 이벤트다.
_EVENT = {
    "project": "t_api",
    "kind": "failure",
    "title": "제목",
    "summary": "요약",
    "occurred_at": "2026-08-31T09:00:00Z",
    "result": "failure",
}


def _client(**overrides) -> TestClient:
    """핸들러를 때릴 수 있는 임시 라우트를 붙인 클라이언트."""
    app = api.create_app(_config(**overrides))

    @app.post("/t/validate")
    async def _validate(body: _Body):  # pragma: no cover - 검증에서 걸린다
        return api.ok({"result": body.result})

    @app.get("/t/boom")
    async def _boom():
        raise RuntimeError("암호는 hunter2 이고 DSN 은 postgresql://u:pw@h/db 다")

    # D67: 토큰 없는 앱은 루프백 Host 만 받는다. TestClient 기본값 `testserver` 는 막힌다.
    return TestClient(app, base_url="http://127.0.0.1:8080", raise_server_exceptions=False)


# --- 봉투 -----------------------------------------------------------------


def test_success_is_wrapped():
    r = _client().post("/t/validate", json={"result": "success"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "data": {"result": "success"}}


def test_unknown_path_is_envelope_not_fastapi_detail():
    """FastAPI 기본은 {"detail": "Not Found"} 다. 그것이 새어 나오면 계약 위반이다."""
    r = _client().get("/no/such/path")
    assert r.status_code == 404
    body = r.json()
    assert "detail" not in body
    assert body["ok"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_request_validation_is_envelope_not_detail_array():
    r = _client().post("/t/validate", json={})
    assert r.status_code == 422
    body = r.json()
    assert "detail" not in body
    assert body["ok"] is False
    assert body["error"]["code"] == "VALIDATION"
    # 무엇이 빠졌는지는 알려준다 — save_event 의 "메시지를 그대로" 규칙이 여기에 해당한다.
    assert "result" in body["error"]["message"]


def test_status_outside_the_contract_is_normalised():
    """405 는 계약 enum 에 없다.

    새 코드를 발명하지 않고 VALIDATION 으로 접는다. 그러면 D21 의 코드↔상태가
    1:1 로 유지되므로 나가는 상태는 405 가 아니라 422 다 — 405 는 살아남지 않는다.
    """
    r = _client().get("/t/validate")
    assert r.status_code == 422
    body = r.json()
    assert "detail" not in body
    assert body["error"]["code"] == "VALIDATION"


# --- INTERNAL 은 아무것도 흘리지 않는다 ------------------------------------


def test_unhandled_exception_leaks_nothing():
    r = _client().get("/t/boom")
    assert r.status_code == 500
    body = r.json()
    assert body == {"ok": False, "error": {"code": "INTERNAL", "message": "internal error"}}
    raw = r.text
    for secret in ("hunter2", "postgresql://", "RuntimeError", "Traceback"):
        assert secret not in raw


# --- D7 게이트 -------------------------------------------------------------


def test_no_bearer_gate_when_token_is_empty():
    """D7: 로컬은 무인증. 빈 토큰이면 Bearer 게이트가 없다 — 대신 D67 의 Host 게이트가 선다."""
    r = _client().post("/t/validate", json={"result": "success"})
    assert r.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong"},
        {"Authorization": "Basic secret-token"},
        {"Authorization": "secret-token"},
        {"Authorization": "Bearer "},
    ],
)
def test_gate_rejects_with_unauthorized(headers):
    r = _client(bearer_token="secret-token").post(
        "/t/validate", json={"result": "success"}, headers=headers
    )
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    # 기대 토큰을 되돌려 주지 않는다.
    assert "secret-token" not in r.text


def test_gate_accepts_the_token():
    r = _client(bearer_token="secret-token").post(
        "/t/validate",
        json={"result": "success"},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert r.status_code == 200


def test_gate_covers_unknown_paths_too():
    """라우트 의존성으로 두면 404 경로가 인증 없이 응답한다."""
    r = _client(bearer_token="secret-token").get("/no/such/path")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


# --- 계약 표면 -------------------------------------------------------------


def test_mapping_matches_d21():
    assert api.STATUS_FOR_CODE == {
        "VALIDATION": 422,
        "UNAUTHORIZED": 401,
        "NOT_FOUND": 404,
        "CONFLICT": 409,
        "INTERNAL": 500,
    }


def test_unknown_code_degrades_to_internal():
    r = api.error("TEAPOT", "postgresql://u:pw@h/db 와 hunter2")
    assert r.status_code == 500
    assert r.body == b'{"ok":false,"error":{"code":"INTERNAL","message":"internal error"}}'


@pytest.mark.parametrize(
    "message",
    ["postgresql://sillok:hunter2@db:5432/sillok", "Traceback (most recent call last)"],
)
def test_internal_message_is_pinned_regardless_of_caller(message):
    """호출자를 믿지 않는다.

    이 고정이 없으면 4단계에서 HTTPException(500, detail=...) 하나로 DSN 이 샌다.
    """
    r = api.error(api.ErrorCode.INTERNAL, message)
    assert r.status_code == 500
    assert b"hunter2" not in r.body
    assert b"Traceback" not in r.body
    assert b'"message":"internal error"' in r.body


def test_http_exception_5xx_does_not_leak_detail():
    app = api.create_app(_config())

    @app.get("/t/raise5xx")
    async def _raise():
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail="postgresql://u:hunter2@h/db")

    r = TestClient(
        app, base_url="http://127.0.0.1:8080", raise_server_exceptions=False
    ).get("/t/raise5xx")
    assert r.status_code == 500
    assert "hunter2" not in r.text
    assert r.json()["error"] == {"code": "INTERNAL", "message": "internal error"}


@pytest.mark.parametrize(
    "path",
    [
        # GET /v1/docs 는 만들지 않기로 정했다 (D64). 이 404 가 답의 전부다.
        "/v1/docs",
        # MCP 는 /mcp 하나다 (D43). 접두사를 붙인 자리는 없다.
        "/v1/mcp",
        # 마운트가 아니라 두 경로만 이었으므로 그 아래는 이 앱의 404 봉투다 (D43).
        "/mcp/nope",
    ],
)
def test_unbuilt_routes_stay_unbuilt(path):
    """뒤 단계의 계약 경로가 통과하는 것처럼 보이면 안 된다.

    `app.routes` 를 훑는 대신 **실제로 때린다.** 라우터를 mount 로 붙이면
    경로 비교는 조용히 통과하지만 요청은 통과하지 않는다.
    """
    client = _client()
    for method in ("GET", "POST"):
        r = client.request(method, path)
        assert r.status_code == 404, f"{method} {path} -> {r.status_code}"
        assert r.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/v1/events/1"), ("GET", "/v1/files"), ("POST", "/v1/docs/proposals")],
)
def test_step7_routes_exist(method, path):
    """7단계 경로는 이제 있어야 한다. 404 면 붙지 않은 것이다 (D35·D36·D38)."""
    r = _client().request(method, path)
    assert r.status_code != 404


def test_get_event_requires_project_and_an_integer_id():
    """D35: `project` 는 필수다. 정수가 아닌 id 도 같은 자리에서 걸린다 (D21)."""
    client = _client(database_url="postgresql://sillok:x@127.0.0.1:1/sillok")
    for path in ("/v1/events/1", "/v1/events/abc?project=sillok"):
        r = client.get(path)
        assert r.status_code == 422, path
        assert r.json()["error"]["code"] == "VALIDATION"


def test_get_file_requires_project_and_path():
    client = _client(database_url="postgresql://sillok:x@127.0.0.1:1/sillok")
    for path in ("/v1/files", "/v1/files?project=sillok", "/v1/files?path=docs/plan.md"):
        r = client.get(path)
        assert r.status_code == 422, path
        assert r.json()["error"]["code"] == "VALIDATION"


@pytest.mark.parametrize(
    ("query", "fragment"),
    [("&offset=-1", "negative"), ("&offset=x", "offset")],
)
def test_get_file_offset_validation_reaches_the_client(query, fragment):
    """DB 에 닿기 전에 걸린다 — 죽은 DSN 이어도 422 다 (D36)."""
    client = _client(database_url="postgresql://sillok:x@127.0.0.1:1/sillok")
    r = client.get(f"/v1/files?project=sillok&path=docs/plan.md{query}")
    assert r.status_code == 422
    assert fragment in r.json()["error"]["message"]


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        ({"project": "sillok", "path": "docs/plan.md"}, "body required"),
        ({"project": "sillok", "path": "docs/plan.md", "body": 7}, "body required"),
        (
            {"project": "sillok", "path": "docs/plan.md", "body": "새 본문", "base_hash": "a" * 64},
            "base_hash",
        ),
    ],
)
def test_save_doc_validation_reaches_the_client(payload, fragment):
    """D40: 접두사 없는 16진도 거절이다. 관대하게 벗기지 않는다."""
    client = _client(database_url="postgresql://sillok:x@127.0.0.1:1/sillok")
    r = client.post("/v1/docs/proposals", json=payload)
    assert r.status_code == 422
    assert fragment in r.json()["error"]["message"]


def test_nul_in_path_is_validation_over_http():
    """살아 있는 Service 에서 이것이 INTERNAL 500 이었다 (Grok 이 라이브에서 찾았다)."""
    client = _client(database_url="postgresql://sillok:x@127.0.0.1:1/sillok")
    r = client.get("/v1/files", params={"project": "sillok", "path": "docs/plan.md\x00.txt"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION"


def test_ingest_refuses_another_workspace_over_http(tmp_path):
    """D37: 같은 거절이 HTTP 얼굴에도 걸린다 — CLI 에만 걸면 이 문으로 우회된다."""
    client = _client(
        database_url="postgresql://sillok:x@127.0.0.1:1/sillok", workspace=str(tmp_path)
    )
    r = client.post("/v1/ingest", json={"project": "sillok", "workspace": str(tmp_path.parent)})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION"
    assert "SILLOK_WORKSPACE" in r.json()["error"]["message"]


@pytest.mark.parametrize(
    ("method", "path"),
    [("POST", "/v1/events"), ("GET", "/v1/stats/events"), ("GET", "/v1/status")],
)
def test_step4_routes_exist(method, path):
    """4단계 경로는 이제 있어야 한다. 404 면 붙지 않은 것이다."""
    r = _client().request(method, path)
    assert r.status_code != 404


def test_step4_routes_stay_in_the_envelope_without_a_db():
    """DB 가 없어도 봉투를 깨지 않는다 — INTERNAL 이지 스택 트레이스가 아니다."""
    client = _client(database_url="postgresql://sillok:x@127.0.0.1:1/sillok")
    r = client.get("/v1/status?project=sillok")
    assert r.status_code == 500
    assert r.json() == {"ok": False, "error": {"code": "INTERNAL", "message": "internal error"}}


def test_service_connect_always_passes_a_timeout(monkeypatch):
    """타임아웃이 없으면 DB 가 닿지 않을 때 요청이 매달린다 (실측 130초).

    경과 시간으로 재면 OS 마다 다르다 — 리눅스는 죽은 포트에 즉시 RST 를 보내므로
    타임아웃이 없어도 빨리 끝나 검사가 공허해진다(Grok 지적).
    그래서 시간이 아니라 **인자가 넘어가는지**를 본다.
    """
    seen = {}

    def _fake_connect(dsn, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("연결하지 않는다")

    monkeypatch.setattr(service.psycopg, "connect", _fake_connect)
    with pytest.raises(RuntimeError):
        service.connect("postgresql://x/y")

    assert seen.get("connect_timeout"), "connect_timeout 이 넘어가지 않는다"


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        ({}, "missing required field"),
        ({**_EVENT, "occurred_at": "2026-08-31T09:00:00"}, "offset"),
        ({**_EVENT, "resolved_at": "2026-08-31T08:00:00Z"}, "resolved_at"),
        ({**_EVENT, "title": "a" * 201}, "title"),
        ({**_EVENT, "project": "has/slash"}, "project"),
        ({**_EVENT, "kind": "typo"}, "kind"),
    ],
)
def test_save_event_validation_reaches_the_client(payload, fragment):
    """D21: VALIDATION 만 메시지를 그대로 돌려준다. 모델이 무엇을 고칠지 알아야 한다.

    DB 에 닿기 전에 걸리므로 DSN 이 죽어 있어도 422 다.
    """
    client = _client(database_url="postgresql://sillok:x@127.0.0.1:1/sillok")
    r = client.post("/v1/events", json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION"
    assert fragment in r.json()["error"]["message"]


def test_stats_and_status_require_project():
    """D5: project 필수. 없으면 FastAPI 요청 검증이 VALIDATION 으로 나간다."""
    client = _client()
    for path in ("/v1/stats/events", "/v1/status"):
        r = client.get(path)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALIDATION"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_human_facing_surface(path):
    """v1은 웹 페이지 비범위 (D12).

    docs_url 만 끄면 /openapi.json 이 살아남아 **봉투 밖 200**을 돌려준다.
    """
    r = _client().get(path)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize("path", ["/t/validate/", "/v1/nope/", "/openapi.json/"])
def test_trailing_slash_does_not_redirect(path):
    """라우터의 슬래시 리다이렉트는 핸들러보다 먼저 **빈 본문 307**을 낸다.

    계약 밖 상태에 봉투도 없는 응답이므로 꺼야 한다.
    """
    r = _client().get(path, follow_redirects=False)
    assert r.status_code != 307
    assert r.json()["ok"] is False


def test_duplicate_authorization_headers_are_rejected():
    """Headers.get 은 첫 번째만 본다.

    맞는 토큰 뒤에 아무 값이나 덧붙인 요청이 통과하면 안 된다.
    """
    app = api.create_app(_config(bearer_token="secret-token"))
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(
        "/v1/nope",
        headers=[
            ("authorization", "Bearer secret-token"),
            ("authorization", "Bearer wrong"),
        ],
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(
    ("token", "presented"),
    [
        # 헤더는 latin-1 이라 0x80~0xFF 가 비-ASCII str 로 들어온다.
        ("secret-token", b"Bearer \xe9\xff"),
        # 토큰 자체가 ASCII 밖인 구성.
        ("비밀토큰", b"Bearer wrong"),
        ("비밀토큰", "Bearer 다른토큰".encode()),
    ],
)
def test_non_ascii_never_degrades_to_internal(token, presented):
    """compare_digest 는 비-ASCII str 에 TypeError 를 낸다.

    그대로 두면 인증 실패가 INTERNAL 500 으로 새어 나간다 — 서버 결함이 아닌데도.
    """
    client = TestClient(
        api.create_app(_config(bearer_token=token)), raise_server_exceptions=False
    )
    r = client.get("/v1/nope", headers={"Authorization": presented})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_non_ascii_token_still_accepts_the_right_value():
    """양쪽 인코딩이 어긋나면 맞는 토큰도 영원히 불일치한다.

    Starlette 은 헤더를 latin-1 로 디코드하고 os.environ 은 UTF-8 로 디코드한다.
    """
    client = TestClient(
        api.create_app(_config(bearer_token="비밀토큰")), raise_server_exceptions=False
    )
    # 클라이언트가 실제로 보내는 것은 UTF-8 바이트다.
    r = client.get("/v1/nope", headers={"Authorization": "Bearer 비밀토큰".encode()})
    assert r.status_code == 404  # 게이트는 통과, 라우트가 없어 404


# --- 로컬 모드의 Host·Origin 게이트 (D67) -------------------------------------
#
# 토큰이 없으면 브라우저의 DNS 리바인딩이 경계를 넘는 길은 낯선 `Host` 다. D43 은 그것을 `/mcp` 에만
# 막았고 같은 Service 를 내는 `/v1` 이 열려 있었다(2026-09-26 감사 실측: 낯선 Host 의 POST 가 원장에 행을 남겼다).
# 검사는 **없는 경로와 `/mcp` 까지** 본다 — 라우트 의존성이면 없는 경로가 빠진다.

HOST_REJECTED = {"ok": False, "error": {"code": "VALIDATION", "message": "host not allowed"}}
ORIGIN_REJECTED = {"ok": False, "error": {"code": "VALIDATION", "message": "origin not allowed"}}
MCP_BODY = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
MCP_ACCEPT = "application/json, text/event-stream"


def _local_hit(path: str, headers, **overrides):
    """토큰 없는 앱에 요청 하나. `/mcp` 는 POST 로, 나머지는 GET 으로.

    `with` 로 연다 — lifespan 이 돌아야 `/mcp` 가 게이트 뒤에서 실제로 답한다.
    """
    with TestClient(
        api.create_app(_config(**overrides)),
        base_url="http://127.0.0.1:8080",
        raise_server_exceptions=False,
    ) as client:
        if path == "/mcp":
            extra = [("accept", MCP_ACCEPT)]
            return client.post(path, json=MCP_BODY, headers=list(headers) + extra)
        return client.get(path, headers=list(headers))


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "evil.example:8080",
        "127.0.0.1.evil.example",
        "localhost.",  # 끝의 점도 다른 이름이다
        "0.0.0.0:8080",
        "user@127.0.0.1",
        "testserver",  # TestClient 기본값 — 검사를 위해 코드에 예외를 두지 않는다
        "api:8080",  # compose 네트워크 안의 이름. 쓰려면 토큰을 켠다
        "127.0.0.1:8080.evil.example",  # 이름 뒤 찌꺼기 — fullmatch 가 아니면 통과한다
        "localhost:80@evil.example",
        "user:pass@127.0.0.1",
        "127.0.0.2",  # 다른 루프백도 D67 이 이름으로 든 셋이 아니다
        "host.docker.internal",
    ],
)
@pytest.mark.parametrize("path", ["/v1/status?project=t_api", "/v1/nope", "/mcp"])
def test_local_mode_rejects_a_foreign_host_on_every_path(path, host):
    r = _local_hit(path, [("host", host)])
    assert r.status_code == 422
    assert r.json() == HOST_REJECTED
    assert host not in r.text  # 받은 값을 되싣지 않는다


def test_local_mode_refuses_a_rebound_write_before_the_service(monkeypatch):
    """감사가 잰 그 요청이다 — 낯선 Host 의 `POST /v1/events` 가 원장에 행을 남겼다.

    Service 에 닿기 전에 끝나야 한다. 게이트를 GET 에만 걸면 여기서 붉어진다.
    """
    called = []
    monkeypatch.setattr(service, "save_event", lambda *a, **k: called.append(a) or {"id": 1})
    client = TestClient(
        api.create_app(_config()), base_url="http://127.0.0.1:8080", raise_server_exceptions=False
    )
    r = client.post(
        "/v1/events",
        json=_EVENT,
        headers={"Host": "rebind.evil:8080", "Origin": "http://rebind.evil:8080"},
    )
    assert r.json() == HOST_REJECTED
    assert called == []


def test_local_mode_rejects_two_host_headers():
    """하나가 루프백이어도 거절한다. 첫 값만 보는 우회를 막는다 (BearerGate 와 같은 이유)."""
    r = _local_hit("/v1/nope", [("host", "127.0.0.1:8080"), ("host", "evil.example")])
    assert r.json() == HOST_REJECTED


def _passed_the_gate(path: str, r) -> bool:
    """게이트를 지났는가. `/v1/nope` 는 라우트가 없어 404 봉투, `/mcp` 는 JSON-RPC 200 이다."""
    if path == "/mcp":
        return r.status_code == 200 and "result" in r.json()
    return r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


# `/mcp` 를 함께 때린다. SDK 의 루프백 목록은 게이트보다 좁아서(포트 필수·http 만),
# 켜 두면 게이트가 통과시킨 요청을 `/mcp` 만 평문 421·403 으로 거절했다 (2026-09-26 리뷰 실측).
@pytest.mark.parametrize(
    "host", ["127.0.0.1", "127.0.0.1:8080", "localhost", "LocalHost:1234", "[::1]", "[::1]:8090"]
)
@pytest.mark.parametrize("path", ["/v1/nope", "/mcp"])
def test_local_mode_lets_loopback_hosts_through(path, host):
    """포트는 어느 것이든 된다 — D66 복제 스택은 다른 포트로 뜬다. 두 얼굴이 같게 답한다."""
    assert _passed_the_gate(path, _local_hit(path, [("host", host)]))


@pytest.mark.parametrize(
    "origin",
    [
        "http://evil.example",
        "http://127.0.0.1.evil.example:8080",
        "http://evil.example@localhost",  # userinfo 뒤의 이름을 취하는 파서로 바뀌면 통과한다
        "null",  # 샌드박스 iframe·file: 이 보내는 값
        "http://localhost:8080/path",
        "ftp://localhost",
    ],
)
@pytest.mark.parametrize("path", ["/v1/nope", "/mcp"])
def test_local_mode_rejects_a_foreign_origin(path, origin):
    r = _local_hit(path, [("host", "127.0.0.1:8080"), ("origin", origin)])
    assert r.status_code == 422
    assert r.json() == ORIGIN_REJECTED


def test_local_mode_rejects_two_origin_headers():
    """첫 값만 보는 파서로 바뀌어도 막히게 — 루프백을 앞에 둔다."""
    r = _local_hit(
        "/v1/nope",
        [("host", "127.0.0.1:8080"), ("origin", "http://localhost"), ("origin", "http://evil.example")],
    )
    assert r.json() == ORIGIN_REJECTED


@pytest.mark.parametrize(
    "origin", ["http://localhost:5173", "https://127.0.0.1", "http://[::1]:3000", "HTTP://LOCALHOST"]
)
@pytest.mark.parametrize("path", ["/v1/nope", "/mcp"])
def test_local_mode_lets_a_loopback_origin_through(path, origin):
    """Origin 이 없으면 보지 않는다 — 브라우저가 아닌 클라이언트는 보내지 않는다."""
    assert _passed_the_gate(path, _local_hit(path, [("host", "127.0.0.1:8080"), ("origin", origin)]))


def test_exposure_mode_leaves_host_to_the_bearer_token():
    """토큰이 있으면(D7 노출) 게이트를 설치하지 않는다 — 진짜 호스트 이름 뒤에서도 돌아야 한다.

    브라우저는 Authorization 을 스스로 붙이지 않으므로 리바인딩된 페이지는 토큰을 넘지 못한다.
    """
    client = TestClient(
        api.create_app(_config(bearer_token="secret-token")),
        base_url="http://sillok.example.com",
        raise_server_exceptions=False,
    )
    passed = client.get(
        "/v1/nope",
        headers={"Authorization": "Bearer secret-token", "Origin": "https://agent.example.com"},
    )
    assert passed.status_code == 404
    refused = client.get("/v1/nope")
    assert refused.status_code == 401


# --- 7단계 라우트의 HTTP 층 (D21 · D35 · D38) --------------------------------
#
# service 층 검사는 `tests/test_stage7_db.py` 가 한다. **여기는 어댑터다** —
# 핸들러가 등록되지 않으면 저쪽은 초록인 채 여기서만 500 이 된다 (Grok 지적).

_STAGE7 = [
    ("GET", "/v1/events/1?project=sillok", "get_event", None),
    ("GET", "/v1/files?project=sillok&path=docs/plan.md", "get_file", None),
    ("POST", "/v1/docs/proposals", "save_doc", {"project": "sillok", "path": "docs/plan.md", "body": "x"}),
]
_NOT_FOUND_MESSAGE = {
    "get_event": service.NOT_FOUND_EVENT,
    "get_file": service.NOT_FOUND_FILE,
    "save_doc": service.NOT_FOUND_DOC,
}


def _hit(method, path, payload, **overrides):
    return _client(**overrides).request(method, path, json=payload)


def _raiser(exc):
    def _raise(*args, **kwargs):
        raise exc

    return _raise


@pytest.mark.parametrize(("method", "path", "func", "payload"), _STAGE7)
def test_service_not_found_becomes_404(monkeypatch, method, path, func, payload):
    """D35 의 404 는 **없는 경로**가 아니라 없는 행이다. 핸들러가 없으면 500 이 된다."""
    message = _NOT_FOUND_MESSAGE[func]
    monkeypatch.setattr(service, func, _raiser(service.NotFound(message)))
    r = _hit(method, path, payload)
    assert r.status_code == 404
    assert r.json() == {"ok": False, "error": {"code": "NOT_FOUND", "message": message}}


def test_not_found_text_outside_the_contract_is_dropped(monkeypatch):
    """이 핸들러만 `str(exc)` 를 흘린다 — 계약 밖 문구는 버린다 (D21 이 INTERNAL 에 건 이유)."""
    monkeypatch.setattr(
        service, "get_file", _raiser(service.NotFound("postgresql://u:hunter2@h/db 없다"))
    )
    r = _hit("GET", "/v1/files?project=sillok&path=docs/plan.md", None)
    assert r.status_code == 404
    assert "hunter2" not in r.text
    assert r.json()["error"]["message"] == api.NOT_FOUND_FALLBACK


def test_base_hash_mismatch_becomes_409_with_the_fixed_message(monkeypatch):
    """CONFLICT 의 둘째 발신자다 (D38). D32 의 문구를 쓰지 않고 예외 문구도 싣지 않는다."""
    monkeypatch.setattr(
        service,
        "save_doc",
        _raiser(service.BaseHashMismatch("postgresql://u:hunter2@h/db " + service.LOCKED_MESSAGE)),
    )
    r = _hit("POST", "/v1/docs/proposals", _STAGE7[2][3])
    assert r.status_code == 409
    assert r.json()["error"] == {"code": "CONFLICT", "message": service.BASE_HASH_MESSAGE}
    assert "hunter2" not in r.text
    assert service.LOCKED_MESSAGE not in r.text


@pytest.mark.parametrize(("method", "path", "func", "payload"), _STAGE7)
def test_stage7_routes_do_not_leak_exception_text(monkeypatch, method, path, func, payload):
    """psycopg 예외는 DSN 을 품는다. 라우트가 늘 때마다 이 자리가 새로 생긴다 (D21)."""
    monkeypatch.setattr(service, func, _raiser(RuntimeError("postgresql://u:hunter2@h/db")))
    r = _hit(method, path, payload)
    assert r.status_code == 500
    assert r.json() == {"ok": False, "error": {"code": "INTERNAL", "message": "internal error"}}
    assert "hunter2" not in r.text


@pytest.mark.parametrize(("method", "path", "func", "payload"), _STAGE7)
def test_stage7_routes_answer_through_the_envelope(monkeypatch, method, path, func, payload):
    """성공도 봉투다. 라우트가 dict 를 그대로 돌려주면 계약 밖으로 나간다 (D21)."""
    monkeypatch.setattr(service, func, lambda *a, **k: {"x": 1})
    r = _hit(method, path, payload)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "data": {"x": 1}}


@pytest.mark.parametrize(("method", "path", "func", "payload"), _STAGE7)
def test_stage7_routes_are_behind_the_bearer_gate(method, path, func, payload):
    """D7 게이트는 미들웨어라 모든 요청을 덮는다 — 라우트가 늘어도 그래야 한다.

    라우트 의존성으로 옮기면 이 검사만 붉어진다. 인자가 유효해도 401 이 먼저다.
    """
    r = _hit(method, path, payload, bearer_token="secret-token")
    assert r.status_code == 401
    assert r.json()["error"] == {"code": "UNAUTHORIZED", "message": "bearer required"}


@pytest.mark.parametrize(("method", "path", "func", "payload"), _STAGE7)
def test_stage7_failures_stay_inside_the_error_table(method, path, func, payload):
    """D21 의 코드 표는 닫혀 있다. 새 코드를 발명하면 여기서 걸린다 (D35 의 FORBIDDEN 도)."""
    # DSN 이 죽어 있으므로 이 셋은 전부 실패한다. 무엇으로 실패하든 표 안이어야 한다.
    r = _hit(method, path, payload, database_url="postgresql://sillok:x@127.0.0.1:1/sillok")
    body = r.json()
    assert body["ok"] is False
    code = body["error"]["code"]
    assert code in api.STATUS_FOR_CODE
    assert r.status_code == api.STATUS_FOR_CODE[code]
    assert isinstance(body["error"]["message"], str)


# --- 반복된 질의 인자 (D69) --------------------------------------------------
#
# 예전에는 계약에 문장이 없어 프레임워크 기본값(마지막 값이 이긴다)을 찾은 자리에서 잠가 두었다.
# D69 가 그것을 결정으로 뒤집었다 — 마지막 값이 `module=authx&module=` 의 필터를 조용히 지웠다.
# 되풀이된 키는 `duplicate field: <이름>` 이고 **Service 에 닿기 전에** 끝난다. 두 값이 실제로 다른
# 요청을 보내 가짜 Service 가 불리지 않는지 본다 — 검사가 빠지면 어느 값이든 함수까지 간다.


def _capture(seen):
    def _fake(*args, **kwargs):
        seen["args"] = args + tuple(kwargs.values())
        return {}

    return _fake


@pytest.mark.parametrize(
    ("path", "func"),
    [
        ("/v1/events/1?project=first&project=last", "get_event"),
        ("/v1/files?path=docs/a.md&project=first&project=last", "get_file"),
        ("/v1/status?project=first&project=last", "kb_status"),
        ("/v1/stats/events?project=first&project=last", "event_stats"),
    ],
)
def test_a_repeated_query_parameter_is_refused(monkeypatch, path, func):
    """D69 가 뒤집었다. 예전에는 마지막 값이 이겼다 — 결정이 아니라 프레임워크 기본값을 잠가 둔 것이었고
    (open-questions G절 주석), `module=authx&module=` 이 필터를 조용히 지웠다(2026-09-26 리뷰 실측).
    Service 에 닿기 전에 끝난다."""
    seen: dict[str, tuple] = {}
    monkeypatch.setattr(service, func, _capture(seen))
    r = _client().get(path)
    assert r.status_code == 422
    assert r.json()["error"] == {"code": "VALIDATION", "message": "duplicate field: project"}
    assert seen == {}


def test_a_repeated_offset_is_refused(monkeypatch):
    """숫자 인자도 같다. 두 번 붙여 보낸 창 번호 중 무엇을 뜻했는지 서버가 고르지 않는다 (D69)."""
    seen: dict[str, tuple] = {}
    monkeypatch.setattr(service, "get_file", _capture(seen))
    r = _client().get("/v1/files?project=p&path=docs/a.md&offset=1&offset=2")
    assert r.status_code == 422
    assert r.json()["error"]["message"] == "duplicate field: offset"
    assert seen == {}


# --- 질의 임베딩 실패 (D33 §4 가 약속한 검사) --------------------------------

# 예외 문구에 비밀을 싣는다. 봉투가 예외를 그대로 실어 나르면 이 문자열이 응답에 뜬다.
# **`sk-` 뒤를 16자 이상으로 늘리지 않는다** — 게이트의 키 모양 검사(D56)가 `tests/` 도 보고,
# 늘리는 순간 "비밀을 가리는지 보는 검사"가 "비밀이 있다"로 붉어진다.
EMBED_SECRET = "key=sk-live-hunter2 dsn=postgresql://u:pw@h/db"

# `connect` 에 닿았다는 **구별되는 신호**다. 일부러 VALIDATION 이라 422 로 나간다 —
# 닿지 않는 DSN 을 쓰면 연결 실패가 INTERNAL 500 이 되어 임베딩 실패와 구별되지 않는다.
# 그 구별이 없으면 갈음 구현을 주입해도 검사가 초록이다 (실측으로 확인했다).
DB_REACHED = "DB WAS REACHED"


def _embed_boom(texts, api_key):  # noqa: ARG001 - 서명만 같으면 된다
    raise RuntimeError(EMBED_SECRET)


def _connect_tripwire(dsn, **kwargs):  # noqa: ARG001
    raise service.ValidationFailed(DB_REACHED)


def _search_docs_with_a_broken_embedder(monkeypatch):
    """임베딩만 고장 낸 채 `search_docs` 를 때린다. DB 는 지뢰선이다."""
    monkeypatch.setattr(service, "_embed", _embed_boom)
    monkeypatch.setattr(service, "connect", _connect_tripwire)
    return _client(openai_api_key="sk-live-hunter2").post(
        "/v1/search/docs", json={"project": "sillok", "query": "검색"}
    )


def test_query_embedding_failure_is_internal_not_a_keyword_fallback(monkeypatch):
    """D33 §4 가 약속하고 트리에 없던 검사다 — `임베딩을 실패시키고 500과 고정 문구를 단언`.

    **`service.search_docs` 를 가로채면 이 고장을 잠그지 못한다.** 그 자리를 가로채면
    구현이 키워드 결과로 갈음해도 검사가 초록이다. `_embed` 를 실패시켜야
    D33 이 막으려던 것 — 고장이 D2 의 정상 상태와 같은 모양으로 200 에 나가는 것 — 을 본다.

    지뢰선이 무는 422 는 갈음이 일어났다는 뜻이다. 500 고정 문구만이 통과다.

    **누수 주사를 여기 함께 둔다** (`test_unhandled_exception_leaks_nothing` 의 모양).
    따로 떼면 그 검사가 지뢰선의 422 본문에도 통과한다 — 그 본문에도 비밀이 없어서다.
    상태와 봉투를 먼저 못 박은 뒤에 훑어야 훑는 대상이 정해진다 (Grok 지적).
    """
    r = _search_docs_with_a_broken_embedder(monkeypatch)

    assert r.status_code == 500, f"임베딩 실패가 삼켜졌다: {r.status_code} {r.text}"
    assert r.json() == {"ok": False, "error": {"code": "INTERNAL", "message": "internal error"}}
    raw = r.text
    for secret in ("sk-live-hunter2", "postgresql://", "hunter2", "Traceback", "RuntimeError"):
        assert secret not in raw, raw


# --- Content-Type (D67, 2026-09-27 감사 F105) ------------------------------------------

CT_REJECTED = {"ok": False, "error": {"code": "VALIDATION", "message": "content type must be application/json"}}
# 업무 POST 다섯. 목록을 여기 둔 것은 **검사의 대상**이지 구현의 사본이 아니다 — 구현은 라우터에서 읽는다.
JSON_POSTS = ["/v1/events", "/v1/search/docs", "/v1/search/events", "/v1/docs/proposals", "/v1/ingest"]
RAW_BODY = b'{"project": "t_api"}'


def _post(path: str, headers: dict | list, content: bytes = RAW_BODY, **overrides):
    """`content=` 로 보낸다 — `json=` 이면 httpx 가 Content-Type 을 붙여 검사할 것이 사라진다."""
    with TestClient(
        api.create_app(_config(**overrides)), base_url="http://127.0.0.1:8080", raise_server_exceptions=False
    ) as client:
        return client.post(path, content=content, headers=headers)


@pytest.mark.parametrize("path", JSON_POSTS)
@pytest.mark.parametrize(
    "content_type",
    [
        None,  # 브라우저의 타입 없는 Blob — FastAPI 0.132 기본값에만 기대던 자리다
        "text/plain",
        "application/x-www-form-urlencoded",
        "multipart/form-data; boundary=x",
        "application/jsonx",
        "application/vnd.api+json",
    ],
)
def test_v1_posts_refuse_a_body_that_is_not_declared_json(path, content_type, monkeypatch):
    """단순 요청 CSRF 의 경계를 프레임워크 기본값이 아니라 앱이 쥔다. Service 에 닿기 전에 끝난다."""
    touched = []
    monkeypatch.setattr(service, "connect", lambda *a, **k: touched.append(a))
    headers = {} if content_type is None else {"content-type": content_type}
    r = _post(path, headers)
    assert r.status_code == 422
    assert r.json() == CT_REJECTED
    assert touched == []


@pytest.mark.parametrize(
    "headers",
    [
        [("content-type", "application/json"), ("content-type", "application/json")],
        [("content-type", "application/json"), ("content-type", "text/plain")],
        [("content-type", "text/plain"), ("content-type", "application/json")],
        [("content-type", "application/json, text/plain")],
    ],
    ids=["json-twice", "json-then-text", "text-then-json", "joined"],
)
def test_a_content_type_that_is_not_exactly_one_json_is_refused(headers):
    """Content-Type 은 꼭 하나다 — 여럿 중 첫 값이나 끝 값을 고르면 어느 쪽을 믿을지가 구현마다 갈린다."""
    r = _post("/v1/events", headers)
    assert r.json() == CT_REJECTED


def test_a_route_with_a_path_parameter_is_checked_too():
    """대상은 라우터가 고른다 — 경로 문자열을 모아 비교하면 `{name}` 이 든 라우트를 놓친다 (2026-09-27 리뷰 실측)."""
    app = api.create_app(_config())

    @app.post("/v1/t_probe/{name}")
    def probe(name: str) -> dict:
        return {"reached": name}

    with TestClient(app, base_url="http://127.0.0.1:8080", raise_server_exceptions=False) as client:
        r = client.post("/v1/t_probe/x", content=b"x", headers={"content-type": "text/plain"})
    assert r.json() == CT_REJECTED


def test_the_check_holds_under_a_root_path():
    """프록시가 접두를 붙여 서빙하면 `path` 에 root_path 가 들어 있다. 라우터처럼 그것을 벗기고 봐야 한다."""
    with TestClient(
        api.create_app(_config()), base_url="http://127.0.0.1:8080", root_path="/sillok",
        raise_server_exceptions=False,
    ) as client:
        r = client.post("/sillok/v1/events", content=RAW_BODY, headers={"content-type": "text/plain"})
    assert r.json() == CT_REJECTED


@pytest.mark.parametrize("content_type", ["application/json", "application/json; charset=utf-8", "Application/JSON"])
def test_a_json_body_reaches_the_route(content_type):
    """매개변수와 대소문자는 된다 — 미디어 타입만 본다. 라우트까지 가서 Service 의 필드 검증에 걸린다."""
    r = _post("/v1/events", {"content-type": content_type})
    assert r.status_code == 422
    assert r.json()["error"]["message"] != CT_REJECTED["error"]["message"]
    assert "missing required field" in r.json()["error"]["message"]


def test_the_host_gate_answers_before_the_content_type():
    r = _post("/v1/events", {"host": "evil.example"})
    assert r.json() == HOST_REJECTED


def test_the_bearer_gate_answers_before_the_content_type():
    r = _post("/v1/events", {}, bearer_token="t0ken-for-tests")
    assert r.status_code == 401
    ok = _post("/v1/events", {"authorization": "Bearer t0ken-for-tests"}, bearer_token="t0ken-for-tests")
    assert ok.json() == CT_REJECTED


def test_an_unknown_path_is_still_404_without_a_content_type():
    """대상은 등록된 `/v1` POST 라우트다 — 경로 접두만 보면 없는 경로가 422 가 된다."""
    r = _post("/v1/nope", {})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_the_app_holds_only_routes_the_content_type_rule_can_see():
    """JsonBody 는 `APIRoute` 만 본다. FastAPI 0.141 의 `include_router` 는 라우트를 다른 형으로 싸서 넣고,
    그 안의 `/v1` POST 는 검사를 건너뛴 채 200 이었다 (2026-09-27 리뷰 실측). 라우터를 들이려면 JsonBody 를 먼저 고친다."""
    from fastapi.routing import APIRoute
    from starlette.routing import Route

    assert {type(r) for r in api.create_app(_config()).routes} == {APIRoute, Route}


@pytest.mark.parametrize("path", ["/v1/status", "/v1/files", "/v1/events/1"])
def test_a_post_to_a_get_route_is_still_the_routers_answer(path):
    """대상은 경로와 메서드가 **둘 다** 맞는 라우트다 (`Match.FULL`). 경로만 맞는 GET 라우트까지 넣으면
    메서드 거절이 본문 타입 거절로 바뀐다 — 고칠 것을 잘못 알려 준다."""
    r = _post(path, {})
    assert r.json() == {"ok": False, "error": {"code": "VALIDATION", "message": "Method Not Allowed"}}


@pytest.mark.parametrize("content_type", [None, "text/plain"])
def test_mcp_is_not_checked_by_the_v1_rule(content_type):
    """`/mcp` 의 본문은 SDK 의 전송 계층이 본다 (D43). **본다는 것도 잠근다** — 문서가 거기에 기대므로
    SDK 가 타입 없는 본문을 받기 시작하면 여기서 알아야 한다. 거절은 SDK 의 것이라 봉투가 아니다."""
    import json

    headers = {"accept": MCP_ACCEPT} | ({} if content_type is None else {"content-type": content_type})
    r = _post("/mcp", headers, content=json.dumps(MCP_BODY).encode())
    assert r.status_code == 400
    assert CT_REJECTED["error"]["message"] not in r.text
