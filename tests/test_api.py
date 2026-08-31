"""3단계 골격 검증 — 무엇이 오든 공통 봉투로 답하는가 (D21).

업무 라우트가 없으므로 핸들러를 때리는 라우트는 테스트가 직접 붙인다.
앱에 스텁 라우트를 심으면 4단계 전에 계약이 구현된 것처럼 보인다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from sillok import api
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

    return TestClient(app, raise_server_exceptions=False)


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


def test_no_gate_when_token_is_empty():
    """D7: 로컬은 무인증. 빈 토큰이면 게이트가 아예 없다."""
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

    r = TestClient(app, raise_server_exceptions=False).get("/t/raise5xx")
    assert r.status_code == 500
    assert "hunter2" not in r.text
    assert r.json()["error"] == {"code": "INTERNAL", "message": "internal error"}


@pytest.mark.parametrize(
    "path",
    [
        # 5~8단계. Q6·Q7·Q10 / Q8·Q9 / Q12·Q15·Q19·Q20 / Q17 이 아직 열려 있다.
        "/v1/events/1",
        "/v1/search/docs",
        "/v1/search/events",
        "/v1/files",
        "/v1/docs",
        "/v1/docs/proposals",
        "/v1/ingest",
    ],
)
def test_later_step_routes_do_not_exist_yet(path):
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
    [("POST", "/v1/events"), ("GET", "/v1/stats/events"), ("GET", "/v1/status")],
)
def test_step4_routes_exist(method, path):
    """4단계 경로는 이제 있어야 한다. 404 면 붙지 않은 것이다."""
    r = _client().request(method, path)
    assert r.status_code != 404


def test_step4_routes_stay_in_the_envelope_without_a_db():
    """DB 가 없어도 봉투를 깨지 않고, **무한히 매달리지 않는다.**

    타임아웃이 없으면 한 요청이 130초를 먹는다 (실측). 그건 서비스가 죽은 것과 같다.
    """
    import time

    client = _client(database_url="postgresql://sillok:x@127.0.0.1:1/sillok")
    started = time.monotonic()
    r = client.get("/v1/status?project=sillok")
    elapsed = time.monotonic() - started

    assert r.status_code == 500
    assert r.json() == {"ok": False, "error": {"code": "INTERNAL", "message": "internal error"}}
    assert elapsed < 30, f"연결 타임아웃이 없다: {elapsed:.0f}초"


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
