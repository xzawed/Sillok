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
    r = api.error("TEAPOT", "무엇이든")
    assert r.status_code == 500


def test_no_business_routes_yet():
    """4단계 전에 §9 판정 대상 경로가 통과하는 것처럼 보이면 안 된다."""
    paths = {route.path for route in api.create_app(_config()).routes}
    for contract_path in ("/v1/status", "/v1/events", "/v1/stats/events"):
        assert contract_path not in paths


def test_openapi_docs_are_off():
    """v1은 웹 페이지 비범위 (D12). 사람이 볼 UI 를 열지 않는다."""
    assert _client().get("/docs").status_code == 404
