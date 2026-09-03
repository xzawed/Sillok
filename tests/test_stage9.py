"""9단계 질의 원장의 순수 부분 (D48–D52). **DB 가 필요 없다.**

여기서 보는 것은 계약에 문장으로 있는 것들이다 — `filters` 가 무엇을 담는지,
서명이 키워드 전용인지, 원장이 자기가 기록하는 것을 죽이지 않는지.
실제 행이 남는지는 `tests/test_stage9_db.py` 가 본다.
"""

from __future__ import annotations

import inspect
import logging
from datetime import datetime, timezone

import pytest

from sillok import service

# 죽은 DSN. 붙지 못하는 것이 이 파일에서는 **의도**다 (test_mcp.py 와 같은 값).
DEAD_DSN = "postgresql://sillok:x@127.0.0.1:1/sillok"


def test_log_filters_drops_project():
    """`project` 는 자기 컬럼이 있다 (D49). 같은 사실을 두 자리에 적지 않는다."""
    out = service._log_filters({"project": "p", "status": "current"})
    assert out == {"status": "current"}


def test_log_filters_isoformats_timestamps():
    """`Z` 와 `+00:00` 이 같은 순간인데 문자열이 다르면 원장이 같은 질의를 둘로 센다 (D49)."""
    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = service._log_filters({"project": "p", "since": when})
    assert out == {"since": "2026-01-01T00:00:00+00:00"}


def test_log_filters_keeps_only_what_the_builders_returned():
    """값이 없는 필터는 빌더가 애초에 키를 넣지 않는다 — 로그에도 없다 (D49).

    요청이 `null` 을 명시해도, MCP 얼굴이 `None` 으로 채워 넘겨도 같은 자리에서 사라진다.
    그래서 **같은 질의는 어느 얼굴로 들어와도 같은 `filters` 를 남긴다.**
    """
    body = {"project": "p", "module": None, "doc_type": None, "status": "current"}
    _where, params = service._doc_filters(body, "p")
    assert service._log_filters(params) == {"status": "current"}

    events = {"project": "p", "kind": None, "module": None}
    _w2, p2 = service._event_search_filters(events, "p")
    assert service._log_filters(p2) == {}


def test_client_is_keyword_only():
    """`api_key` 뒤에 위치 인자로 두면 HTTP 얼굴이 실수로 넘길 수 있다 (D49)."""
    for fn in (service.search_docs, service.search_events):
        param = inspect.signature(fn).parameters["client"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY, fn.__name__
        assert param.default == "http", fn.__name__


def test_client_is_not_in_the_request_body():
    """`body` 에서 읽으면 HTTP 호출자가 `mcp` 를 위장하고 D46 의 대조 기준이 깨진다 (D49)."""
    source = inspect.getsource(service.search_docs) + inspect.getsource(service.search_events)
    assert 'body.get("client")' not in source
    assert 'body["client"]' not in source


def test_log_write_failure_is_swallowed(caplog):
    """원장이 자기가 기록하는 것을 죽이면 안 된다 (D50).

    죽은 DSN 이므로 연결이 실패한다. 예외가 올라오면 검색이 500 이 된다.
    """
    with caplog.at_level(logging.WARNING):
        service._log_query(
            DEAD_DSN,
            client="http",
            tool="search_docs",
            project="p",
            query="q",
            params={"project": "p"},
            results=[],
            with_paths=True,
            started=0.0,
        )
    assert any("질의 로그를 남기지 못했다" in r.getMessage() for r in caplog.records)


def test_log_warning_does_not_carry_the_dsn(caplog):
    """경고에 DSN 을 싣지 않는다 (D21·D50). 이 저장소는 예외 경로로 한 번 흘린 적이 있다."""
    with caplog.at_level(logging.WARNING):
        service._log_query(
            DEAD_DSN,
            client="http",
            tool="search_docs",
            project="p",
            query="q",
            params={"project": "p"},
            results=[],
            with_paths=False,
            started=0.0,
        )
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "sillok:x@" not in text


def test_payload_bugs_are_swallowed_too(caplog, monkeypatch):
    """`try` 는 쓰기뿐 아니라 **값 만들기까지** 감싼다 (D50).

    `filters` 를 만들다 난 버그가 500 이 되면 안 된다. jsonb 어댑터를 터뜨려 그 자리를 민다.
    """

    def boom(_value):
        raise TypeError("주입한 고장")

    monkeypatch.setattr(service.psycopg.types.json, "Jsonb", boom)
    with caplog.at_level(logging.WARNING):
        service._log_query(
            DEAD_DSN,
            client="http",
            tool="search_events",
            project="p",
            query=None,
            params={"project": "p", "kind": "failure"},
            results=[],
            with_paths=False,
            started=0.0,
        )
    assert any("주입한 고장" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("tool", ["search_docs", "search_events"])
def test_only_the_two_search_functions_log(tool):
    """D48. `kb_status` 는 `hit_count = 0` 을 *세는* 쪽이라 쓰면 자기가 자기를 센다."""
    assert f'tool="{tool}"' in inspect.getsource(service)
    for fn in (service.kb_status, service.event_stats, service.get_event, service.save_event):
        assert "_log_query" not in inspect.getsource(fn), fn.__name__


def test_values_are_built_inside_the_try(caplog, monkeypatch):
    """`filters` 를 **만드는** 계산도 삼켜야 한다 (D50).

    처음 구현은 `filters=_log_filters(params)` 를 호출자가 만들어 넘겼는데, 키워드 인자는
    함수에 들어오기 **전에** 평가되므로 그 계산이 `try` 밖이었다 — 계약이 삼키라고 한
    바로 그 자리가 500 으로 새는 길이었다 (Grok 적대 리뷰). 재료를 넘기는 형태로 잠근다.
    """

    def boom(_params):
        raise RuntimeError("filters 를 만들다 터졌다")

    monkeypatch.setattr(service, "_log_filters", boom)
    with caplog.at_level(logging.WARNING):
        service._log_query(
            DEAD_DSN,
            client="http",
            tool="search_docs",
            project="p",
            query="q",
            params={"project": "p"},
            results=[],
            with_paths=True,
            started=0.0,
        )
    assert any("filters 를 만들다 터졌다" in r.getMessage() for r in caplog.records)


def test_hit_paths_are_built_inside_the_try(caplog):
    """`hit_paths` 도 같다 — `path` 가 없는 행이 와도 질의를 죽이지 않는다 (D50)."""
    with caplog.at_level(logging.WARNING):
        service._log_query(
            DEAD_DSN,
            client="http",
            tool="search_docs",
            project="p",
            query="q",
            params={"project": "p"},
            results=[{"경로가": "없다"}],
            with_paths=True,
            started=0.0,
        )
    # 죽은 DSN 도 같은 머리말로 경고한다. 그래서 **연결 실패가 낼 수 없는 문구**를 본다 (Grok 재검토).
    assert any("'path'" in r.getMessage() for r in caplog.records)


# --- D25 · D33 이 서로 다른 정규화를 요구하는 자리 ----------------------------


def test_event_fields_are_not_trimmed(monkeypatch):
    """D25 는 정규화를 `project` 에만 건다. 이벤트 필드는 받은 그대로다.

    같은 이름의 함수 둘 중 나중 것이 이겨 `build_event` 가 `module` 을 트리밍하고
    공백뿐인 `severity` 를 조용히 None 으로 삼키고 있었다 (Grok 적대 리뷰가 잡았다).
    """
    event = service.build_event(
        {
            "project": " sillok ",
            "kind": "failure",
            "title": "제목",
            "summary": "요약",
            "occurred_at": "2026-01-01T00:00:00Z",
            "result": "failure",
            "module": "  auth  ",
        }
    )
    assert event.project == "sillok"  # project 만 정규화한다 (D25)
    assert event.module == "  auth  "  # 나머지는 받은 그대로다


def test_blank_severity_is_rejected_not_swallowed():
    """`관대하게 채우지 않는다` (D10). 공백뿐인 enum 은 거절이지 None 이 아니다."""
    body = {
        "project": "sillok",
        "kind": "failure",
        "title": "제목",
        "summary": "요약",
        "occurred_at": "2026-01-01T00:00:00Z",
        "result": "failure",
        "severity": "   ",
    }
    with pytest.raises(service.ValidationFailed):
        service.build_event(body)


def test_search_filters_still_trim():
    """검색 필터는 반대다 — 공백뿐이면 거르지 않는다 (D33 §1). 두 규칙이 한 이름을 쓰면 안 된다."""
    _where, params = service._doc_filters({"project": "p", "status": "  current  "}, "p")
    assert params["status"] == "current"
    _w2, p2 = service._doc_filters({"project": "p", "status": "   "}, "p")
    assert "status" not in p2
