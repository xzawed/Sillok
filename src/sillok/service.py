"""Service 함수 — DB를 만지는 유일한 문 (D19).

여기 있는 함수만 SQL을 안다. HTTP 어댑터(`api.py`)와 CLI는 이 함수들을 부를 뿐이다.
4단계(plan §7)의 세 가지(`save_event` · `event_stats` · `kb_status`)에서 시작해
5단계 `ingest`, 6단계 검색 둘, 7단계 단건·제안 셋까지 같은 자리에 있다.
9단계는 새 함수를 더하지 않는다 — 검색 둘이 돌아가는 길에 질의 원장을 남긴다 (D48–D52).

**파일을 여는 걸음은 여기 없다.** D36 의 `openat` 걸음은 `workspace.py` 가 갖고,
*무엇을 열어도 되는가*(= `kb_documents` 에 행이 있는가)만 이 파일이 판정한다.

**검증은 여기서 한다 (D10·D25).** DDL에 CHECK를 두지 않는 이유는, CHECK 위반이
Postgres 예외가 되고 D21이 그것을 `INTERNAL 500`으로 접기 때문이다 —
클라이언트 입력 문제가 서버 결함으로 보고되면 안 된다.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from . import ingest as ingest_rules
from . import search
from . import migrations
from . import workspace as workspace_rules

log = logging.getLogger(__name__)

# 정본: docs/skills/sillok-storage/SKILL.md · docs/service-and-mcp.md
REQUIRED_FIELDS = ("project", "kind", "title", "summary", "occurred_at", "result")
KINDS = frozenset({"success", "failure", "incident", "decision"})
RESULTS = frozenset({"success", "failure", "partial", "unknown"})
SEVERITIES = frozenset({"low", "medium", "high", "critical"})
SOURCES = frozenset({"manual", "github_issue", "markdown", "agent"})

# D25. project 는 앞뒤 공백을 제거한 뒤 검사한다.
PROJECT_MAX = 64
TITLE_MAX = 200
SUMMARY_MAX = 2000
# 공백은 `str.isspace()` 전부다 (D68) — 앞뒤를 벗기는 `strip()` 과 같은 정의라야 **공백 때문에**
# 겉보기에 같은 라벨이 다른 project 가 되지 않는다(폭 없는 문자 Cf 는 D68 이 닫지 않았다).
# 여기는 공백 밖의 셋이다.
_PROJECT_FORBIDDEN = ("/", "\\", "\x00")
# D68. 공백만 있으면 누락으로 본다. 판정만 벗기고 저장은 받은 그대로다 (D25 의 정규화는 project 만).
_BLANK_IS_MISSING = frozenset({"title", "summary"})

# D68 — D58 의 확장. `get_event` 가 행을 통째로 돌려주므로(D39) 나머지 자유 텍스트에도 천장을 둔다.
# 새 숫자를 만들지 않는다: 서술은 summary 의 수, 짧은 라벨은 title 의 수다.
_OPTIONAL_TEXT_MAX = {
    "root_cause": SUMMARY_MAX,
    "resolution": SUMMARY_MAX,
    "module": TITLE_MAX,
    "created_by": TITLE_MAX,
    "related_doc_path": TITLE_MAX,
}
# D68. 검색 질의 상한 — summary 와 같은 수. **벗긴** 질의를 잰다 (빈 질의 규칙이 먼저다).
QUERY_MAX = SUMMARY_MAX

# D69. Service 입력마다 받는 키. 그 밖의 키는 VALIDATION 이다 — 오타가 NULL 로 저장되거나
# (append-only 라 되살릴 원본이 없다, D24·D59) 필터 없는 검색이 되지 않게 한다.
# MCP 얼굴은 SDK 가 선언 밖 인자를 여기 오기 전에 떨어뜨리므로 `mcp_server` 가 같은 검사를 앞에서 한다.
SAVE_EVENT_KEYS = frozenset(REQUIRED_FIELDS) | frozenset(
    {"module", "root_cause", "resolution", "severity", "resolved_at", "source",
     "related_doc_path", "payload", "created_by"}
)
SEARCH_DOCS_KEYS = frozenset({"project", "query", "top_k", "doc_type", "status", "module"})
SEARCH_EVENTS_KEYS = frozenset({"project", "query", "top_k", "kind", "module", "since", "until"})
SAVE_DOC_KEYS = frozenset({"project", "path", "body", "base_hash"})
INGEST_KEYS = frozenset({"project", "workspace"})
EVENT_STATS_KEYS = frozenset({"project", "module", "since"})
KB_STATUS_KEYS = frozenset({"project"})
GET_FILE_KEYS = frozenset({"project", "path", "offset"})
GET_EVENT_KEYS = frozenset({"project"})


def reject_unknown(keys: Iterable[object], allowed: frozenset[str]) -> None:
    """모르는 키를 거절한다 (D69). 이름은 **키 하나**만 싣고 값은 싣지 않는다.

    여럿이면 코드점 순으로 첫 키다(결정적이다). 이름으로 실을 수 없는 키 — 비었거나,
    200자를 넘거나, 담을 수 없는 문자가 있는 키 — 는 잘라 싣지 않고 고정 문구만 낸다
    (D68 이 긴 질의를 잘라 기록하는 안을 버린 그 이유다).
    """
    unknown = sorted(str(k) for k in keys if k not in allowed)
    if unknown:
        raise ValidationFailed(_naming("unknown field", unknown[0]))


def reject_query(keys: list[str], allowed: frozenset[str]) -> None:
    """HTTP 질의 인자 (D69). 모르는 키를 먼저, 그다음 **되풀이된 키**를 거절한다.

    FastAPI 는 스칼라 인자에 마지막 값만 넘긴다 — `module=authx&module=` 이 필터 없는 집계가 되고
    `project=A&project=B` 가 B 로 읽혔다(2026-09-26 리뷰 실측). POST 라우트는 받는 질의 인자가 없으므로
    `allowed` 가 비어 있고, 키가 하나라도 있으면 거절된다 — `?root_cause=` 가 원인 없이 저장됐다.
    """
    reject_unknown(keys, allowed)
    repeated = sorted({k for k in keys if keys.count(k) > 1})
    if repeated:
        raise ValidationFailed(_naming("duplicate field", repeated[0]))


def _naming(message: str, name: str) -> str:
    """키 이름을 문구에 실어도 되는가 (D69). 실을 수 없으면 자르지 않고 고정 문구만 낸다."""
    if 0 < len(name) <= TITLE_MAX and "\x00" not in name and not _SURROGATE.search(name):
        return f"{message}: {name}"
    return message

# 짝 없는 서로게이트. `require_text` 가 쓴다 — 왜 거르는지는 그 함수의 docstring 이다.
_SURROGATE = re.compile("[\ud800-\udfff]")

# D23. Skill 의 "2회 이상" 이 임계값이고, 상한은 검색 최대치와 같은 값이다.
REPEAT_MIN_COUNT = 2
REPEAT_LIMIT = 12

# D58. 모델이 읽는 응답에만 천장을 준다. 경계는 MCP 노출이다 —
# `ingest` 의 `skipped[]` 에 천장이 없는 것은 그것이 도구가 아니기 때문이고, 그것도 결정이다.
BY_MODULE_LIMIT = 12
PAYLOAD_MAX = 2000


class ValidationFailed(Exception):
    """클라이언트 입력이 계약을 어겼다. D21의 `VALIDATION`으로 나간다."""


@dataclass(frozen=True)
class Event:
    """검증을 통과한 이벤트. DB에 넣을 수 있는 상태만 이 타입이 된다."""

    project: str
    kind: str
    title: str
    summary: str
    occurred_at: datetime
    result: str
    module: str | None = None
    root_cause: str | None = None
    resolution: str | None = None
    severity: str | None = None
    resolved_at: datetime | None = None
    source: str = "agent"
    related_doc_path: str | None = None
    payload: dict[str, Any] | None = None
    created_by: str | None = None


def connect(dsn: str, *, autocommit: bool = False) -> psycopg.Connection:
    """psycopg 예외를 그대로 올린다. 감싸는 것은 호출자의 몫이다.

    **타임아웃을 반드시 준다.** 없으면 DB 가 닿지 않을 때 요청이 무한히 매달린다 —
    마이그레이션 러너에서 같은 결함을 이미 한 번 고쳤는데(D17 기동 경로) 여기서 되풀이했다.
    실측: 타임아웃 없이 죽은 호스트로 붙으면 한 요청이 130초를 먹었다.

    autocommit 은 D32 가 ingest 를 위해 더한 것이다. 기본값이 꺼짐이라 4단계 세 함수의
    동작은 바뀌지 않는다. 켜지 않고 파일 단위 커밋을 하려 들면 블록 밖 문장 하나가
    암묵 트랜잭션을 열어 이후 트랜잭션 블록이 전부 세이브포인트가 된다 —
    run 전체가 한 트랜잭션이 되는데 **실패가 아니라 통과로 나온다.**
    """
    try:
        return psycopg.connect(
            dsn,
            row_factory=dict_row,
            connect_timeout=migrations.CONNECT_TIMEOUT_SECONDS,
            autocommit=autocommit,
        )
    except psycopg.ProgrammingError:
        # 형식이 틀린 DSN 의 구문 오류 문구는 DSN 을 되읊는다 — `sillok ingest` 는 러너를 거치지 않아
        # 그 문구가 트레이스백째 나갔다 (2026-09-27 감사 F061). 형은 두고(D21 이 INTERNAL 로 접는다) 문구를 버린다.
        raise psycopg.ProgrammingError("DATABASE_URL 형식을 읽을 수 없다") from None
    except psycopg.OperationalError as exc:
        # libpq 는 userinfo 를 첫 `@` 에서 끊어 암호의 나머지를 host 로 되읊는다(`failed to resolve host 'SeCrEt@db'`,
        # 리뷰 실측). 형은 두고 문구에서 암호 조각을 지운다.
        raise psycopg.OperationalError(migrations.scrub_driver_text(str(exc).strip(), dsn)) from None


# --- 검증 (D25) ------------------------------------------------------------


def normalize_project(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValidationFailed("project must be a string")
    project = raw.strip()
    if not project:
        raise ValidationFailed("project required")
    if len(project) > PROJECT_MAX:
        raise ValidationFailed(f"project longer than {PROJECT_MAX}")
    if any(ch.isspace() for ch in project) or any(bad in project for bad in _PROJECT_FORBIDDEN):
        raise ValidationFailed("project must not contain whitespace, slash or NUL")
    # NUL 은 위에서 D25 의 문구로 이미 걸렸다. 여기는 서로게이트를 받으러 온다 —
    # `_PROJECT_FORBIDDEN` 만 있던 동안 `project` 는 그 길로 500 을 냈다.
    require_text(project, "project")
    # 대소문자를 접지 않는다. 슬러그 알파벳을 여기서 발명하지 않는다 (D25).
    return project


def require_text(value: str, field: str) -> str:
    """`text` 컬럼에 담을 수 없는 문자열을 `VALIDATION` 으로 거절한다. **부류를 막는 한 자리다.**

    거르는 것은 둘이고 이유가 같다 — **그런 값을 담은 행은 존재할 수 없다.**

    - **NUL.** Postgres 의 `text` 가 담지 못한다.
    - **짝 없는 서로게이트.** UTF-8 로 인코딩되지 않는다 (`json` 은 `\\ud83d\\ude00` 같은
      **짝**은 이미 한 글자로 합쳐 주므로 이모지·한글은 여기 걸리지 않는다. 남아 있는
      서로게이트는 정의상 짝이 없는 것이다).

    그대로 SQL 에 넘기면 드라이버 예외(psycopg · `UnicodeEncodeError`)가 D21 의 포괄 예외에
    걸려 `INTERNAL 500` 이 되고, **클라이언트 입력 문제가 서버 결함으로 보고된다** —
    D25 가 `resolved_at` 에서 이미 이름 붙인 부류다
    (`CHECK 로 걸면 … 클라이언트 입력 문제인데 서버 결함으로 보고된다`).
    정규화가 아니라 **물어볼 수 없는 질문을 거절하는 것이다.**

    **왜 함수인가.** D25 가 `project` 에서, D36 이 `path` 에서 각각 NUL 을 막았지만
    둘 다 *자리*를 막았다. 2026-09-04 실측에서 나머지가 그대로 500 을 냈다 —
    `event_stats.module` · `search_docs` 의 `query`·`module` · `search_events` 의
    `query`·`module`·`kind` · `save_event` 의 `title`·`summary`·`module`·`root_cause` ·
    `ingest` 의 `workspace`, 그리고 서로게이트로는 **`project` 까지** 뚫렸다.
    **자리마다 고치면 다음 필드에서 또 난다.**
    """
    if "\x00" in value:
        raise ValidationFailed(f"{field} must not contain NUL")
    if _SURROGATE.search(value):
        raise ValidationFailed(f"{field} must not contain unpaired surrogates")
    return value


def parse_timestamp(raw: object, field: str) -> datetime:
    """오프셋이 없는 시각을 거절한다 (D25).

    드라이버가 접속 TimeZone 으로 해석하게 두면 Compose 에서 우연히 UTC 가 되는 것이지
    계약이 아니다. 날짜만 있는 값도 오프셋이 없으므로 여기서 함께 걸린다.
    """
    if not isinstance(raw, str):
        raise ValidationFailed(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise ValidationFailed(f"{field} is not ISO-8601: {raw!r}") from None
    if parsed.tzinfo is None:
        raise ValidationFailed(f"{field} needs a UTC offset (Z or ±HH:MM): {raw!r}")
    try:
        return parsed.astimezone(timezone.utc)
    except OverflowError:
        # `0001-01-01T00:00:00+23:59` 은 ISO-8601 로도 datetime 으로도 멀쩡하다.
        # **UTC 로 옮기는 순간** 연도가 1 아래(또는 9999 위)로 나가 OverflowError 가 난다.
        # 잡지 않으면 D21 의 포괄 예외가 INTERNAL 500 으로 접는다 — 클라이언트 입력인데도.
        # 실측 2026-09-04: `occurred_at` · `stats.since` · `search_events` 의 `since`·`until`.
        raise ValidationFailed(
            f"{field} is outside the representable range once shifted to UTC: {raw!r}"
        ) from None


def _optional_text(body: dict[str, Any], field: str) -> str | None:
    value = body.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationFailed(f"{field} must be a string")
    # `module`·`root_cause`·`resolution`·`related_doc_path`·`created_by` 와 `_enum` 의 둘이
    # 이 한 줄로 함께 막힌다. 자리마다 두지 않는 이유는 `require_text` 에 적었다.
    require_text(value, field)
    cap = _OPTIONAL_TEXT_MAX.get(field)
    if cap is not None and len(value) > cap:
        raise ValidationFailed(f"{field} longer than {cap}")
    return value


def require_payload_text(payload: dict[str, Any]) -> None:
    """`payload` 는 **안쪽 문자열까지** `require_text` 를 받는다.

    `jsonb` 로 저장되므로 키든 값이든 배열 안이든 담을 수 없는 문자열이 하나라도 있으면
    그 행은 존재할 수 없다. **겉의 dict 만 검사하면 `payload` 하나로 이 부류가 되살아난다** —
    실제로 그랬다 (2026-09-04, Grok 이 라이브에서 `{"x": "\\u0000"}` 로 찾았다).

    **재귀가 아니라 스택이다.** `PAYLOAD_MAX` 2000자 안에서도 수백 단 중첩이 되고,
    재귀로 걸으면 그 깊이에서 `RecursionError` 가 난다 — 그것 역시 클라이언트 입력이 만든
    500 이라 여기서 막으려던 것과 같은 부류다.

    문구는 필드명을 `payload` 로 고정한다. 안쪽 키 경로를 실어 보내면 error 봉투가
    요청 내용을 되비추는 자리가 된다.

    **깊이도 여기서 막는다.** 길이를 재는 `_payload_text` 는 `json.dumps` 라 재귀이고,
    깊은 payload 에서 `RecursionError` 를 낸다 — 실측 2026-09-04: 호스트에서 깊이 5000 이
    터졌고 **컨테이너에서는 요청 파서가 먼저 거절해 살아남았다.** 플랫폼이 가린 것이지
    닫힌 것이 아니다 (이 저장소의 재발 부류다). 그래서 이 함수가 `_payload_text` **앞에** 선다.

    한계값을 새로 만들지 않는다 — 중첩 한 단은 직렬화에 최소 한 바이트를 쓰므로
    `PAYLOAD_MAX` 단보다 깊은 payload 는 **이미 그 상한을 넘긴 것**이다. 문구도 같은 것을 쓴다.
    """
    stack: list[tuple[Any, int]] = [(payload, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > PAYLOAD_MAX:
            raise ValidationFailed(f"payload longer than {PAYLOAD_MAX}")
        if isinstance(node, str):
            require_text(node, "payload")
        elif isinstance(node, dict):
            for key, value in node.items():
                require_text(key, "payload")
                stack.append((value, depth + 1))
        elif isinstance(node, list):
            stack.extend((item, depth + 1) for item in node)


def _payload_text(payload: dict[str, Any]) -> str:
    """`payload` 의 길이를 재는 **한 가지** 방법 (D58).

    구분자를 적지 않으면 기본값이 공백을 넣어 **같은 객체가 재는 사람에 따라 갈린다.**
    저장된 `jsonb` 는 Postgres 가 정규화하므로 이 수는 *입력*을 재는 것이다.
    """
    # NaN·Infinity 는 JSON 이 아니다. 파이썬 `json` 은 받아들이고(`1e999` 는 inf 가 된다) 기본값으로
    # 도로 내보내는데, `jsonb` 가 그것을 거절해 INTERNAL 500 이 됐다 (D68, 2026-09-26 감사 실측).
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except ValueError:
        raise ValidationFailed("payload must not contain NaN or Infinity") from None


def _enum(body: dict[str, Any], field: str, allowed: frozenset[str]) -> str | None:
    value = _optional_text(body, field)
    if value is not None and value not in allowed:
        raise ValidationFailed(f"{field} must be one of {sorted(allowed)}")
    return value


def _is_missing(field: str, value: object) -> bool:
    """필수 필드가 없는가 (D10). `title`·`summary` 는 공백뿐이어도 없는 것이다 (D68)."""
    if value is None or value == "":
        return True
    return field in _BLANK_IS_MISSING and isinstance(value, str) and not value.strip()


def build_event(body: dict[str, Any]) -> Event:
    """요청 본문을 검증된 Event 로 만든다. 관대하게 채우지 않는다 (D10)."""
    if not isinstance(body, dict):
        raise ValidationFailed("body must be an object")
    # 누락보다 먼저다 — `root_casue` 는 "원인을 비웠다" 가 아니라 "철자를 틀렸다" 이다 (D69).
    reject_unknown(body, SAVE_EVENT_KEYS)

    missing = [f for f in REQUIRED_FIELDS if _is_missing(f, body.get(f))]
    if missing:
        raise ValidationFailed("missing required field: " + ", ".join(missing))

    project = normalize_project(body["project"])

    title = body["title"]
    summary = body["summary"]
    if not isinstance(title, str) or not isinstance(summary, str):
        raise ValidationFailed("title and summary must be strings")
    require_text(title, "title")
    require_text(summary, "summary")
    if len(title) > TITLE_MAX:
        raise ValidationFailed(f"title longer than {TITLE_MAX}")
    if len(summary) > SUMMARY_MAX:
        raise ValidationFailed(f"summary longer than {SUMMARY_MAX}")

    kind = body["kind"]
    result = body["result"]
    # 타입부터 본다 (D68). 리스트·딕트는 해시되지 않아 `not in` 이 TypeError 를 냈다 → 500.
    # 문구는 값이 틀렸을 때와 같다 — `_enum` 의 `must be a string` 으로 갈라 두지 않는다.
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValidationFailed(f"kind must be one of {sorted(KINDS)}")
    if not isinstance(result, str) or result not in RESULTS:
        raise ValidationFailed(f"result must be one of {sorted(RESULTS)}")

    occurred_at = parse_timestamp(body["occurred_at"], "occurred_at")
    resolved_at = None
    if body.get("resolved_at") is not None:
        resolved_at = parse_timestamp(body["resolved_at"], "resolved_at")
        if resolved_at < occurred_at:
            raise ValidationFailed("resolved_at is before occurred_at")

    payload = body.get("payload")
    if payload is not None and not isinstance(payload, dict):
        raise ValidationFailed("payload must be an object")
    if payload is not None:
        # **길이보다 먼저다.** 길이를 재는 `_payload_text` 가 재귀라 깊은 payload 에서
        # RecursionError 를 낸다 — 그 앞에서 깊이를 걸러야 이 부류가 닫힌다.
        require_payload_text(payload)
    if payload is not None and len(_payload_text(payload)) > PAYLOAD_MAX:
        raise ValidationFailed(f"payload longer than {PAYLOAD_MAX}")

    return Event(
        project=project,
        kind=kind,
        title=title,
        summary=summary,
        occurred_at=occurred_at,
        result=result,
        module=_optional_text(body, "module"),
        root_cause=_optional_text(body, "root_cause"),
        resolution=_optional_text(body, "resolution"),
        severity=_enum(body, "severity", SEVERITIES),
        resolved_at=resolved_at,
        source=_enum(body, "source", SOURCES) or "agent",
        related_doc_path=_optional_text(body, "related_doc_path"),
        payload=payload,
        created_by=_optional_text(body, "created_by"),
    )


# --- Service 함수 ----------------------------------------------------------


def save_event(dsn: str, body: dict[str, Any]) -> dict[str, int]:
    """이벤트를 넣고 `{"id": n}` 을 돌려준다.

    **멱등이 아니다 (D24).** 같은 요청을 두 번 보내면 행이 둘 생긴다.
    필수 필드로 만든 해시로 접으면 같은 project+module+root_cause 의 반복,
    즉 `repeat_causes` 가 탐지하려는 대상 자체가 사라진다.
    """
    event = build_event(body)
    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO kb_events (
              project, module, kind, title, summary, root_cause, resolution,
              result, severity, occurred_at, resolved_at, source,
              related_doc_path, payload, created_by
            ) VALUES (
              %(project)s, %(module)s, %(kind)s, %(title)s, %(summary)s,
              %(root_cause)s, %(resolution)s, %(result)s, %(severity)s,
              %(occurred_at)s, %(resolved_at)s, %(source)s,
              %(related_doc_path)s, COALESCE(%(payload)s, '{}'::jsonb), %(created_by)s
            ) RETURNING id
            """,
            {
                **event.__dict__,
                "payload": psycopg.types.json.Jsonb(event.payload)
                if event.payload is not None
                else None,
            },
        )
        return {"id": cur.fetchone()["id"]}


def _event_filters(project: str, module: str | None, since: datetime | None):
    where = ["project = %(project)s"]
    params: dict[str, Any] = {"project": project}
    if module is not None:
        where.append("module = %(module)s")
        params["module"] = module
    if since is not None:
        where.append("occurred_at >= %(since)s")
        params["since"] = since
    return " AND ".join(where), params


def event_stats(
    dsn: str, project: str, module: str | None = None, since: datetime | None = None
) -> dict[str, Any]:
    """D23. 필터 + COUNT/AVG 만 쓴다. 벡터를 쓰지 않는다."""
    project = normalize_project(project)
    # `module` 은 두 얼굴 다 **질의 인자**로 들어온다. 검색 필터와 같은 뜻이다 (D69) —
    # 벗기고, 공백뿐이거나 비면 거르지 않는다. 예전에는 원문 그대로 비교해 `''` 가 0행이었다.
    # NUL·서로게이트도 같은 자리에서 걸린다 (Grok 이 라이브에서 `module=%00` 으로 찾았던 구멍).
    module = _filter_text({"module": module}, "module")
    where, params = _event_filters(project, module, since)

    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT count(*) AS total,
                   ROUND(EXTRACT(EPOCH FROM AVG(resolved_at - occurred_at)))
                     AS avg_resolution_seconds
            FROM kb_events WHERE {where}
            """,
            params,
        )
        head = cur.fetchone()

        buckets: dict[str, dict[str, int]] = {}
        omitted = 0   # module 갈래가 채운다. 초기값을 두어 이름이 루프에 매이지 않게 한다
        for field, key in (("kind", "by_kind"), ("result", "by_result"), ("module", "by_module")):
            # `kind`·`result` 는 닫힌 enum 이라 천장이 필요 없다. `module` 만 열려 있다 (D58).
            # 정렬은 SQL 이 한다 — 파이썬에서 자르면 어느 열둘인지가 로케일에 따라 흔들린다.
            # 정렬만 SQL 이 한다. **LIMIT 을 걸지 않는다** — 걸면 몇 개가 떨어졌는지
            # 셀 수 없고, `by_module_omitted` 가 "천장이 걸렸다" 로만 줄어든다 (실측으로 드러났다).
            # module 수는 운영자가 고르는 값이지 요청이 부풀릴 수 있는 값이 아니다.
            order = (
                f' ORDER BY count(*) DESC, {field} COLLATE "C" ASC' if field == "module" else ""
            )
            cur.execute(
                f"SELECT {field} AS bucket, count(*) AS n FROM kb_events"
                f" WHERE {where} GROUP BY {field}{order}",
                params,
            )
            # module 이 NULL 인 행의 키는 넣지 않는다 — JSON 키는 null 일 수 없고
            # "null" 은 실제 모듈명과 충돌한다. 그 행들은 total 에 그대로 남는다 (D23).
            rows = [r for r in cur.fetchall() if r["bucket"] is not None]
            if field == "module":
                # 떨어진 **키 수**다. 떨어진 키들의 *행 수*는 알 수 없고, 그것까지 알려면
                # 목록 표면이 필요하다 — v1 은 만들지 않는다 (D58).
                omitted = max(0, len(rows) - BY_MODULE_LIMIT)
                rows = rows[:BY_MODULE_LIMIT]
            buckets[key] = {row["bucket"]: row["n"] for row in rows}

        cur.execute(
            f"""
            SELECT module, root_cause, count(*) AS count
            FROM kb_events
            WHERE {where} AND root_cause IS NOT NULL
            GROUP BY module, root_cause
            HAVING count(*) >= {REPEAT_MIN_COUNT}
            -- COLLATE "C" (D69) — by_module 과 같은 이유다 (D58). LIMIT 이 이 순서로 자른다.
            ORDER BY count DESC, root_cause COLLATE "C" ASC, module COLLATE "C" ASC NULLS LAST
            LIMIT {REPEAT_LIMIT}
            """,
            params,
        )
        repeat_causes = [
            {"module": r["module"], "root_cause": r["root_cause"], "count": r["count"]}
            for r in cur.fetchall()
        ]

    avg = head["avg_resolution_seconds"]
    return {
        "total": head["total"],
        **buckets,
        # D58. `0` 이면 `sum(by_module) <= total` 의 차이가 D23 의 뜻 그대로다.
        # `0` 이 아니면 천장이 걸린 것이고, **떨어진 키들의 행 수는 알 수 없다** —
        # 그것까지 알려면 목록 표면이 필요하고 v1 은 만들지 않는다.
        "by_module_omitted": omitted,
        "repeat_causes": repeat_causes,
        # 전부 미해결이면 0 이 아니라 null 이다 (D23).
        "avg_resolution_seconds": int(avg) if avg is not None else None,
    }


def kb_status(dsn: str, project: str) -> dict[str, Any]:
    """D23 옆의 새 사실. 모르는 project 도 같은 0 을 돌려준다 — NOT_FOUND 가 아니다."""
    project = normalize_project(project)
    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              (SELECT count(*) FROM kb_documents WHERE project = %(p)s) AS documents,
              (SELECT count(*) FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id
                 WHERE d.project = %(p)s) AS chunks,
              (SELECT count(*) FROM kb_events WHERE project = %(p)s) AS events,
              -- 성공한 run 이 한 번도 없으면 null. 빈 값이 정상이지 스텁이 아니다.
              -- 실패한 run 은 세지 않는다 (D32) — 세면 실패가 마지막 색인으로 보고된다.
              (SELECT max(finished_at) FROM kb_ingest_runs
                 WHERE project = %(p)s AND status = ANY(%(counted)s)) AS last_ingest_at,
              -- D48–D52. 검색 둘이 여기에 쓴다. 이 질의 자신은 쓰지 않는다 (D48).
              (SELECT count(*) FROM kb_query_logs
                 WHERE project = %(p)s AND hit_count = 0) AS zero_hit_queries,
              -- D31. 키 없이 색인한 상태가 오류가 아니라 정상이므로 현황에 드러낸다.
              (SELECT count(*) FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id
                 WHERE d.project = %(p)s AND c.embedding IS NULL) AS chunks_without_embedding
            """,
            {"p": project, "counted": sorted(INGEST_COUNTED_STATUSES)},
        )
        row = cur.fetchone()

    last = row["last_ingest_at"]
    return {
        "documents": row["documents"],
        "chunks": row["chunks"],
        "events": row["events"],
        "last_ingest_at": last.isoformat() if last is not None else None,
        "zero_hit_queries": row["zero_hit_queries"],
        "chunks_without_embedding": row["chunks_without_embedding"],
    }


# --- 5단계 ingest (D30 · D31 · D32) -----------------------------------------

INGEST_STATUSES = frozenset({"running", "ok", "partial", "failed"})
# kb_status 의 last_ingest_at 이 세는 것 (D32). 실패한 run 을 세면 실패가
# 마지막 색인으로 보고된다. 아무도 읽지 않는 값 집합은 틀려도 드러나지 않으므로
# 이 둘이 kb_status 의 SQL 과 _finish 의 가드에서 실제로 쓰인다.
INGEST_COUNTED_STATUSES = frozenset({"ok", "partial"})
LOCK_NAMESPACE = "sillok:ingest"
# 고정 문구다. project 값을 넣지 않는다 — 고정이어야 검사가 잠글 수 있다 (D32).
LOCKED_MESSAGE = "ingest already running for this project"
INTERRUPTED = "interrupted"
ERROR_MAX = 500
EMBED_MODEL = "text-embedding-3-small"
# D2 의 차원. DDL 이 이미 막지만 검사가 이름으로 부를 수 있어야 한다.
EMBED_DIM = 1536
# 백필의 입력식. tsv 생성식과 **같은 식**이어야 벡터와 키워드가 같은 것을 본다 (D31).
# 파이썬에서 이어 붙이지 않는다 — 그러면 같은 규칙의 세 번째 사본이 생겨 검사가 물지 않는다.
EMBED_INPUT_SQL = "coalesce(heading_path, '') || ' ' || content"


def vector_literal(values: list[float]) -> str:
    """pgvector 의 텍스트 형식. 어댑터를 쓰지 않는다 (D31 개정).

    손으로 만든 형식은 아무도 검사하지 않는 두 번째 직렬화가 될 수 있다 —
    그래서 DB 검사가 알려진 벡터를 넣고 다시 읽어 값이 보존되는지 단언한다.
    """
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


class IngestLocked(Exception):
    """같은 project 의 ingest 가 이미 돌고 있다 (D32).

    api 가 이것을 CONFLICT 409 로 접는다. 포괄 예외 핸들러에 걸리면
    락 거절이 500 으로 나간다 — 그래서 전용 예외가 있어야 한다.
    """


class IngestFailed(Exception):
    """run 을 끝까지 가지 못하게 하는 것. 이 예외가 status='failed' 를 만든다."""


# 임베딩 요청 하나의 한계 (D31 이 구현으로 둔 값). SDK 기본값이면 search_docs 요청 하나가 HTTP·MCP 가 나눠 쓰는
# 작업 스레드를 30분 넘게 잡았고 ingest 는 그동안 프로젝트 락을 쥐었다 (감사 F013). healthcheck 는 3초를 기다린다.
# 백필도 같은 값이다 — 첫 실패에서 멈추고 다음 run 이 잇는다 (D31).
EMBED_TIMEOUT_SECONDS = 10.0
EMBED_CONNECT_SECONDS = 3.0
EMBED_MAX_RETRIES = 1


def _embed(texts: list[str], api_key: str) -> list[list[float]]:
    """임베딩 클라이언트는 여기서만 부른다. import 도 여기서 한다.

    키가 없으면 이 함수가 아예 불리지 않으므로(D2·D31) 커밋된 구성에서
    의존성이 없어도 검사가 돈다. 키가 있는 상태의 검사 경로는 D31 이 남긴 자리다.
    """
    import httpx
    from openai import OpenAI

    # 한계를 명시한다 — SDK 기본값(읽기 600초·재시도 2)에 맡기지 않는다 (D31, 2026-09-27 감사 F013).
    client = OpenAI(
        api_key=api_key,
        timeout=httpx.Timeout(EMBED_TIMEOUT_SECONDS, connect=EMBED_CONNECT_SECONDS),
        max_retries=EMBED_MAX_RETRIES,
    )
    result = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in result.data]


# 게이트의 키 모양을 그대로 쓴다 (D56, `scripts/check-layout.mjs` 의 SECRETS 첫 줄).
# 새 모양을 발명하지 않는다 — `sk-proj-`·PEM·`ghp-` 는 이 컬럼으로 오는 길을 재지 않았다.
_OPENAI_KEY = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}")

# 직렬화가 **시작되는** 자리다 — 여는 중괄호 뒤에 바로 따옴표가 오는 모양.
# dict repr(`{'error': …`)과 JSON(`{"error": …`) 둘 다이고, 그 둘이 제공자가 보내는 것이다.
# **맨 `{` 로 끊지 않는다.** 그러면 중괄호가 든 도메인 요약이 통째로 날아간다 —
# `doc_type "{invented}" is outside the taxonomy` 가 `doc_type "` 만 남는 것을 실측했다.
# 그 값이야말로 이 컬럼이 있는 이유다.
_PAYLOAD_START = re.compile(r"\{\s*[\"']")


def _clip(text: object) -> str:
    """error 는 첫 실패의 첫 줄이고 상한에서 자른다. run 하나가 로그가 되면 안 된다 (D32).

    **D31 이 요구하는 것이 하나 더 있다 — `키·DSN·응답 본문을 싣지 않는다`.**
    D32 의 첫 줄 자르기는 그것을 못 한다: 제공자 예외는 본문을 *같은 줄에* 붙여 온다.
    2026-09-16 실측에서 이 컬럼이 OpenAI 응답 본문을 통째로 들고 있었다.

    그래서 **직렬화가 시작되는 자리에서 끊는다** — 여는 중괄호 뒤에 따옴표가 오는 모양.
    `[` 로는 끊지 않는다 — `[Errno 111]`·`[WinError …]` 가 직렬화가 아니라 실패 요약
    그 자체라서다. 맨 `{` 로도 끊지 않는다 — 중괄호가 든 도메인 요약이 날아간다
    (둘 다 Grok 이 짚었고 둘 다 실측했다). `Error code: 401` 은 본문이 아니라
    남겨야 하는 요약이고, 그 뒤의 dict 가 본문이다.

    이 함수는 DB 컬럼과 서버 로그 **둘 다** 먹인다. 갈라 두지 않는다 —
    표면 하나에만 세정기를 다는 것이 애초에 이 결함을 만든 부류다.
    """
    body = str(text)
    payload = _PAYLOAD_START.search(body)
    if payload:
        body = body[: payload.start()].rstrip()
    body = _OPENAI_KEY.sub("***", migrations.redact_dsn(body))
    lines = body.splitlines()
    return (lines[0] if lines else "")[:ERROR_MAX]


def _run_error(exc: BaseException) -> str:
    """run 행의 `error` — **비지 않는다** (D32 `partial`·`failed` 에서 반드시 있다).

    `_clip` 은 메시지가 없거나, 직렬화로 시작하거나, 첫 줄이 빈 예외에 빈 문자열을 낸다.
    그때는 예외 클래스 이름이다 — 본문을 싣지 않는 세정(D31)은 그대로다.
    """
    return _clip(exc) or type(exc).__name__


def ingest_run_error(dsn: str, run_id: int) -> str | None:
    """CLI 가 실패 사유를 stderr 에 싣는 문 (D32 · D19). **HTTP 에는 싣지 않는다** (D32).

    사유는 `kb_ingest_runs.error` 에만 있었고 5432 를 열지 않고는 읽을 수 없었다(2026-09-26 감사).
    CLI 는 자기 SQL 을 갖지 않으므로 여기서 읽는다.
    """
    with connect(dsn) as conn, conn.cursor() as cur:
        row = cur.execute("SELECT error FROM kb_ingest_runs WHERE id = %s", (run_id,)).fetchone()
    return row["error"] if row else None


def _write_document(conn: psycopg.Connection, project: str, doc: dict[str, Any]) -> int:
    """문서 하나가 트랜잭션 하나다 (D32).

    kb_documents upsert + 그 문서의 청크 DELETE + INSERT 가 한 트랜잭션에 든다.
    나누면 그 사이에 들어온 검색이 문서를 0건으로 돌려준다 — 오류 없이 조용히.
    """
    with conn.transaction(), conn.cursor() as cur:
        row = cur.execute(
            """
            INSERT INTO kb_documents
              (project, repo, path, doc_type, module, status, title, content_hash, source_mtime,
               rules_version)
            VALUES (%(project)s, '', %(path)s, %(doc_type)s, %(module)s, %(status)s, %(title)s,
                    %(content_hash)s, %(source_mtime)s, %(rules_version)s)
            ON CONFLICT (project, repo, path) DO UPDATE SET
              doc_type = EXCLUDED.doc_type,
              module = EXCLUDED.module,
              status = EXCLUDED.status,
              title = EXCLUDED.title,
              content_hash = EXCLUDED.content_hash,
              rules_version = EXCLUDED.rules_version,
              -- 판만 낡아 다시 만든 행은 내용이 바뀌지 않았다 (D71) — 두 시각을 그대로 둔다.
              source_mtime = CASE WHEN %(content_changed)s
                                  THEN EXCLUDED.source_mtime ELSE kb_documents.source_mtime END,
              indexed_at = CASE WHEN %(content_changed)s THEN now() ELSE kb_documents.indexed_at END
            RETURNING id
            """,
            {"project": project, **doc},
        ).fetchone()
        document_id = row["id"]
        # 재색인은 문서 행을 유지한 채 청크만 지우고 다시 넣는다.
        # ON DELETE CASCADE 는 문서 행이 지워질 때만 돈다 (D30).
        cur.execute("DELETE FROM kb_chunks WHERE document_id = %s", (document_id,))
        for piece in doc["chunks"]:
            # tsv 는 GENERATED ALWAYS 다. 컬럼 목록에 넣으면 오류다.
            cur.execute(
                "INSERT INTO kb_chunks (document_id, chunk_idx, heading_path, content)"
                " VALUES (%s, %s, %s, %s)",
                (document_id, piece.chunk_idx, piece.heading_path, piece.content),
            )
    return document_id


def _backfill(conn: psycopg.Connection, project: str, api_key: str) -> tuple[int, str | None]:
    """벡터가 빈 청크를 채운다. ingest 의 마지막 패스이고 경로는 이것 하나뿐이다 (D31).

    첫 실패에서 멈춘다. 인증·한도 같은 실패는 남은 청크에서도 똑같이 실패하고,
    계속하면 실패 호출만 수백 번 더 만든다. 정렬이 완결돼 있으므로 다시 돌리면 멈춘 자리부터다.
    """
    with conn.cursor() as cur:
        rows = cur.execute(
            "SELECT c.id, " + EMBED_INPUT_SQL + " AS text"
            " FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id"
            " WHERE d.project = %s AND c.embedding IS NULL"
            " ORDER BY c.document_id, c.chunk_idx",
            (project,),
        ).fetchall()
    if not rows:
        return 0, None

    done = 0
    for row in rows:
        try:
            vector = _embed([row["text"]], api_key)[0]
        except Exception as exc:
            return done, _run_error(exc)
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "UPDATE kb_chunks SET embedding = %s::vector WHERE id = %s",
                (vector_literal(vector), row["id"]),
            )
        done += 1
    return done, None


def ingest(dsn: str, project: object, workspace: str, api_key: str = "") -> dict[str, Any]:
    """5단계. 전체 스캔이 곧 삭제 판정이고 임베딩은 마지막 패스다 (D30·D31·D32).

    연결은 autocommit 으로 연다. 켜지 않으면 블록 밖 문장 하나가 암묵 트랜잭션을 열어
    이후 conn.transaction() 이 전부 세이브포인트가 되고 run 전체가 한 트랜잭션이 된다 —
    그 고장은 실패가 아니라 통과로 나온다.
    """
    project = normalize_project(project)
    root = Path(workspace)

    with connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            got = cur.execute(
                "SELECT pg_try_advisory_lock(hashtext(%s), hashtext(%s)) AS got",
                (LOCK_NAMESPACE, project),
            ).fetchone()["got"]
        if not got:
            raise IngestLocked(LOCKED_MESSAGE)
        try:
            return _run(conn, project, root, api_key)
        finally:
            # run 이 끝나면 명시적으로 푼다. serve 는 장수 프로세스라
            # 연결이 재사용되면 세션 락이 남는다 (D32).
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_unlock(hashtext(%s), hashtext(%s))",
                    (LOCK_NAMESPACE, project),
                )


def _validate_meta(path: str, meta: dict[str, Any]) -> None:
    """taxonomy 밖이면 서비스가 거절한다. DDL 에 CHECK 를 더하지 않는다 (D25). 경로는 표시형이다 (D32)."""
    # 값도 표시형이다 — front matter 의 ESC 가 행에 그대로 들어갔고 U+2028 이 사유를 잘랐다 (2026-09-26 리뷰).
    shown = ingest_rules.printable(path)
    for field, allowed in (("doc_type", ingest_rules.DOC_TYPES), ("status", ingest_rules.STATUSES)):
        if meta[field] not in allowed:
            value = ingest_rules.printable(str(meta[field]))
            raise IngestFailed(f'{shown}: {field} "{value}" is outside the taxonomy')


def _finish(
    conn: psycopg.Connection, run_id: int, status: str, error: str | None, counters: dict[str, int]
) -> None:
    """카운터는 종료 UPDATE 에서 상태와 같은 트랜잭션에 쓴다. 진행 중에는 NULL 이다 (D32).

    값 집합 밖의 상태를 쓰면 여기서 막는다. DDL 에 CHECK 를 넣지 않기로 했으므로(D25)
    그 자리를 지키는 것은 이 가드뿐이다.
    """
    if status not in INGEST_STATUSES:
        raise IngestFailed(f"unknown ingest status: {status!r}")
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "UPDATE kb_ingest_runs SET status = %(status)s, error = %(error)s, finished_at = now(),"
            " files_seen = %(files_seen)s, files_changed = %(files_changed)s,"
            " files_deleted = %(files_deleted)s, chunks_upserted = %(chunks_upserted)s"
            " WHERE id = %(id)s",
            {"id": run_id, "status": status, "error": error, **counters},
        )


def _index_file(
    conn: psycopg.Connection,
    project: str,
    root: str,
    item: ingest_rules.Scanned,
    known: dict[str, tuple[str, int]],
    counters: dict[str, int],
) -> None:
    """파일 하나를 읽고, 바뀌었으면 그 문서의 트랜잭션 하나로 쓴다 (D30 · D32).

    **읽기는 `get_file` 과 같은 걸음이다** (D36 · D70 ③). 스캔은 `lstat` 으로 링크를 걸렀지만
    예전 읽기는 경로를 다시 따라가 그 사이 링크로 바뀐 파일이나 중간 디렉터리의 밖을 색인했다.
    """
    if not item.storable:
        raise ingest_rules.unstorable(item)
    fd = workspace_rules.open_regular(root, item.path)
    try:
        raw = workspace_rules.read_all(fd)
        # 경로를 다시 stat 하지 않는다 — 읽은 서술자의 것이다.
        mtime = os.fstat(fd).st_mtime
    finally:
        os.close(fd)
    text = ingest_rules.normalize(raw, item.path)
    digest = ingest_rules.content_hash(text)
    stored_hash, stored_rules = known.get(item.path, (None, None))
    same_body = stored_hash == digest
    if same_body and stored_rules >= ingest_rules.RULES_VERSION:
        return
    meta = ingest_rules.derive_meta(item.path, text)
    _validate_meta(item.path, meta)
    _, body = ingest_rules.split_front_matter(text)
    pieces = ingest_rules.chunk(body)
    _write_document(
        conn,
        project,
        {
            "path": item.path,
            "content_hash": digest,
            "source_mtime": datetime.fromtimestamp(mtime, tz=timezone.utc),
            "chunks": pieces,
            "rules_version": ingest_rules.RULES_VERSION,
            # 판만 낡았으면 내용은 바뀌지 않았다 — `indexed_at`·`source_mtime` 을 건드리지 않고
            # `files_changed` 에 세지 않는다 (D71). 한 일은 `chunks_upserted` 가 센다.
            "content_changed": not same_body,
            **meta,
        },
    )
    if not same_body:
        counters["files_changed"] += 1
    counters["chunks_upserted"] += len(pieces)


def _run(conn: psycopg.Connection, project: str, root: Path, api_key: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        # 락이 그 행들이 죽었다는 증거다 — 살아 있는 run 이 있었다면 락을 못 얻었다.
        # finished_at 은 NULL 로 둔다. 언제 죽었는지 모르는데 지금 시각을 넣으면 새 거짓말이다.
        cur.execute(
            "UPDATE kb_ingest_runs SET status = 'failed', error = %s"
            " WHERE project = %s AND status = 'running'",
            (INTERRUPTED, project),
        )
        run_id = cur.execute(
            "INSERT INTO kb_ingest_runs (project, status) VALUES (%s, 'running') RETURNING id",
            (project,),
        ).fetchone()["id"]

    counters = {"files_seen": 0, "files_changed": 0, "files_deleted": 0, "chunks_upserted": 0}
    embedded = 0
    status = "ok"
    error: str | None = None
    skipped: list[dict[str, str]] = []

    try:
        # 걸음을 걸을 수 없으면 **스캔 전에** 실패한다 (D36 · D70 ③). 파일마다 실패하면
        # 첫 파일 이름이 붙어 사유가 플랫폼이 아니라 그 파일인 것처럼 읽힌다.
        workspace_rules.require_flags()
        files, skips = ingest_rules.scan(root)
        skipped = [{"path": s.path, "reason": s.reason} for s in skips]
        counters["files_seen"] = len(files)
        # 잘못된 workspace 한 번이 인덱스를 통째로 지우는 것이 이 결정의 유일한 파국이다.
        if not files:
            raise IngestFailed("scan found no .md under the D9 paths")

        with conn.cursor() as cur:
            known = {
                r["path"]: (r["content_hash"], r["rules_version"])
                for r in cur.execute(
                    "SELECT path, content_hash, rules_version FROM kb_documents"
                    " WHERE project = %s AND repo = ''",
                    (project,),
                ).fetchall()
            }

        workspace = os.fspath(root)
        for item in files:
            # 사유·서버 로그에 싣는 경로는 표시형이다 (D32).
            shown = ingest_rules.printable(item.path)
            try:
                _index_file(conn, project, workspace, item, known, counters)
            except (IngestFailed, ingest_rules.DecodeFailed):
                raise
            except workspace_rules.OpenFailed as exc:
                # 스캔 뒤에 링크로 바뀌었거나 사라졌다 (D70 ③). 예상한 실패라 트레이스백을 남기지 않는다.
                # 못 읽은 것과 사라진 것을 구분할 수 없으므로 삭제하지 않는다 (D32).
                raise IngestFailed(f"{shown}: {exc}") from exc
            except Exception as exc:
                # 예상 밖 실패에도 **경로를 붙인다** (2026-09-26 리뷰) — 청크가 tsvector 한도를 넘거나
                # 파일 읽기가 실패하면 사유에 어느 파일인지가 없어 운영자가 고칠 곳을 몰랐다.
                # 트레이스백은 서버 로그에 남는다 (D21). 사유 줄은 세정한다 (D31).
                log.error("ingest run %s failed on %s", run_id, shown, exc_info=exc)
                raise IngestFailed(f"{shown}: {_run_error(exc)}") from exc

        # 삭제는 백필 앞이다. 뒤에 두면 백필 첫 실패에서 멈추는 run 이
        # 삭제를 영구히 건너뛴다 — 텍스트 색인의 일부인데 벡터 때문에 빠지는 것이다.
        # 제외(skip)는 삭제 후보가 아니다 (D30 §1). 빼면 파일 하나를 심볼릭 링크로
        # 바꾸는 것만으로 그 문서가 인덱스에서 지워진다. **링크 아래**도 같다 — 디렉터리를 링크로
        # 바꾸면 그 아래가 지워졌다. 접두는 `링크 + '/'` 다 — 없으면 `docs/a` 가 `docs/ab.md` 를 살린다.
        # 표시형(`exact=False`)은 키가 아니다 — 글자 그대로 같은 진짜 이름의 행을 살린다 (D70 ②).
        keep = [f.path for f in files] + [s.path for s in skips if s.exact]
        links = [s.path for s in skips if s.exact and s.reason == "symlink"]
        with conn.transaction(), conn.cursor() as cur:
            gone = cur.execute(
                "DELETE FROM kb_documents WHERE project = %s AND repo = ''"
                " AND NOT (path = ANY(%s))"
                " AND NOT EXISTS (SELECT 1 FROM unnest(%s::text[]) AS link(p)"
                " WHERE starts_with(path, link.p || '/'))"
                " RETURNING id",
                (project, keep, links),
            ).fetchall()
            counters["files_deleted"] = len(gone)

        if api_key:
            embedded, failure = _backfill(conn, project, api_key)
            if failure is not None:
                status, error = "partial", failure
    except Exception as exc:
        # **run 행이 생긴 뒤의 실패는 한 길이다** (D32) — failed 로 적고 정상 반환한다.
        # 예전에는 IngestFailed·DecodeFailed 밖의 예외(파일 읽기 OSError, 문장 수준 DataError)를
        # 적고 다시 올려 HTTP 가 INTERNAL 500 이었고 CLI 는 요약 줄 없이 죽었다 (2026-09-26 감사).
        # 예상한 실패가 아니면 서버 로그에 트레이스백을 남긴다 (D21). 메시지 줄은 세정한다 (D31) —
        # 트레이스백 본문은 D21 이 서버 로그에 두기로 한 원문이다.
        # 플래그 없는 플랫폼(D70 ③)도 예상한 실패다 — 사유가 전부다.
        if not isinstance(exc, (IngestFailed, ingest_rules.DecodeFailed, workspace_rules.PlatformUnsupported)):
            log.error("ingest run %s failed: %s", run_id, _run_error(exc), exc_info=exc)
        status, error = "failed", _run_error(exc)

    # **연결이 끊기면** 여기부터 예외가 그대로 올라간다 — 종료 UPDATE, 아래 남은 벡터 조회,
    # `ingest()` 의 락 해제 모두 (D32). 종료 UPDATE 전이면 행은 running 으로 남고 다음 run 이 회수한다.
    # 응답을 만들 수 없는 경우이고, run 행이 생긴 뒤의 INTERNAL 은 이것뿐이다.
    _finish(conn, run_id, status, error, counters)
    with conn.cursor() as cur:
        pending = cur.execute(
            "SELECT count(*) AS n FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id"
            " WHERE d.project = %s AND c.embedding IS NULL",
            (project,),
        ).fetchone()["n"]

    return {
        "run_id": run_id,
        "project": project,
        "status": status,
        # v1 은 채우지 않는다 (D30). 필드는 계약이고 값이 생기면 채우는 자리다.
        "commit_sha": "",
        **counters,
        "chunks_embedded": embedded,
        "chunks_pending": pending,
        "skipped": skipped,
    }


# --- 6단계 검색 (D33 · D34) --------------------------------------------------

# 사전 이름은 상수 하나에서 나온다. 색인과 질의가 다른 구성을 보면 히트가 0 인데 오류가 아니다.
TS_CONFIG = "simple"
# 이벤트 tsv 의 입력식. DDL 의 생성식과 같은 것이어야 한다 (D34 §2).
EVENT_TSV_INPUT_SQL = (
    "coalesce(title, '')      || ' ' || coalesce(summary, '')    || ' ' || "
    "coalesce(root_cause, '') || ' ' || coalesce(resolution, '')"
)
HEADLINE_OPTS = 'StartSel="",StopSel="",MaxWords=60,MinWords=25,MaxFragments=1'


def _top_k(raw: object) -> int:
    """기본 8, 최대 12. 범위 밖은 거절한다 — 조용히 12 로 접지 않는다 (D33 §6 · D25 선례)."""
    if raw is None:
        return search.TOP_K_DEFAULT
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValidationFailed("top_k must be an integer")
    if not 1 <= raw <= search.TOP_K_MAX:
        raise ValidationFailed(f"top_k must be between 1 and {search.TOP_K_MAX}")
    return raw


def _filter_text(body: dict[str, Any], field: str) -> str | None:
    """검색 **필터**의 값을 읽는다. 없거나 null 이거나 공백뿐이면 거르지 않는다 (D33 §1).

    **`_optional_text` 와 이름이 겹치면 안 된다.** 파이썬은 나중 정의로 덮으므로
    이 파일에서 먼저 정의된 쪽을 쓰는 `build_event` 가 조용히 이 함수를 부르게 된다 —
    실제로 그렇게 나 있었고, `module`·`severity` 가 D25 에 없는 트리밍을 받고 있었다.
    같은 경고가 바로 아래 `_event_search_filters` 에 이미 적혀 있었는데 되풀이했다.
    """
    raw = body.get(field)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValidationFailed(f"{field} must be a string")
    # 검색 **필터** 도 `text` 컬럼과 비교되므로 같은 것을 거른다.
    value = require_text(raw, field).strip()
    return value or None


# D69. 닫힌 집합인 필터는 값도 본다 — 오타가 200 빈 결과로 `zero_hit_queries` 를 부풀리지 않게.
# 쓰기(ingest)가 이미 거절하는 집합과 같다. `module` 은 열린 값이라 여기 없다 (D25 레지스트리 금지).
_DOC_FILTER_ENUMS = {"doc_type": ingest_rules.DOC_TYPES, "status": ingest_rules.STATUSES}


def _enum_filter(value: str | None, field: str, allowed: frozenset[str] | None) -> str | None:
    """벗긴 **뒤에** 본다 — `"  failure  "` 는 통과하고 공백뿐이면 필터가 아니다 (D69)."""
    if value is not None and allowed is not None and value not in allowed:
        raise ValidationFailed(f"{field} must be one of {sorted(allowed)}")
    return value


def _doc_filters(body: dict[str, Any], project: str) -> tuple[str, dict[str, Any]]:
    """필터는 **두 팔의 WHERE** 에 건다. 병합 뒤에 거르면 걸러질 행이 후보 칸을 먹는다."""
    where = ["d.project = %(project)s"]
    params: dict[str, Any] = {"project": project}
    for field in ("module", "doc_type", "status"):
        value = _enum_filter(_filter_text(body, field), field, _DOC_FILTER_ENUMS.get(field))
        if value is not None:
            where.append(f"d.{field} = %({field})s")
            params[field] = value
    return " AND ".join(where), params


def _keyword_arm(cur, where: str, params: dict[str, Any], query: str) -> list[search.Ranked]:
    """정렬이 총순서가 아니면 순위가 실행마다 다르고, 그 순위가 곧 점수다 (D33 §2)."""
    rows = cur.execute(
        f"""
        SELECT c.id, d.repo, d.path, c.chunk_idx, d.id AS document_id,
               -- rank() 는 점수 식만 본다. 타이브레이크를 여기 넣으면 rank() 가
               -- row_number() 와 같아져 알파벳 순서가 그대로 점수가 된다 (D33 §2).
               rank() OVER (ORDER BY ts_rank(c.tsv, tq.q, 1) DESC) AS rk
        FROM kb_chunks c
        JOIN kb_documents d ON d.id = c.document_id,
             plainto_tsquery('{TS_CONFIG}', %(query)s) AS tq(q)
        WHERE {where} AND c.tsv @@ tq.q
        -- 풀에 들어갈 60행을 고르는 정렬은 총순서여야 한다.
        ORDER BY ts_rank(c.tsv, tq.q, 1) DESC,
                 d.repo COLLATE "C", d.path COLLATE "C", c.chunk_idx
        LIMIT {search.CANDIDATE_POOL}
        """,
        {**params, "query": query},
    ).fetchall()
    return [
        search.Ranked((r["repo"], r["path"], r["chunk_idx"]), r["document_id"], r["rk"], dict(r))
        for r in rows
    ]


def _vector_arm(cur, where: str, params: dict[str, Any], vector: str) -> list[search.Ranked]:
    """`IS NOT NULL` 을 **먼저** 건다 (D33 §2).

    최적화가 아니라 정확성이다 — 안 걸면 벡터가 하나도 없는 색인에서도 상위 행이 나온다.
    부분 임베딩은 정상 상태이므로(D31) 이것은 임시 방편이 아니라 영구 규칙이다.
    """
    rows = cur.execute(
        f"""
        SELECT c.id, d.repo, d.path, c.chunk_idx, d.id AS document_id,
               rank() OVER (ORDER BY c.embedding <=> %(v)s::vector ASC) AS rk
        FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id
        WHERE {where} AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> %(v)s::vector ASC,
                 d.repo COLLATE "C", d.path COLLATE "C", c.chunk_idx
        LIMIT {search.CANDIDATE_POOL}
        """,
        {**params, "v": vector},
    ).fetchall()
    return [
        search.Ranked((r["repo"], r["path"], r["chunk_idx"]), r["document_id"], r["rk"], dict(r))
        for r in rows
    ]


def _log_filters(params: dict[str, Any]) -> dict[str, Any]:
    """`filters` 는 **실제로 SQL 에 걸린 것만**이다 (D49).

    두 필터 빌더가 돌려준 `params` 가 곧 그 목록이다 — 값이 없는 필터는 애초에 키가 없다.
    요청의 `null` 도, MCP 얼굴이 채워 넘기는 `None` 도 `_filter_text` 에서 같이 사라지므로
    **같은 질의는 어느 얼굴로 들어와도 같은 `filters` 를 남긴다.**

    `project` 는 자기 컬럼이 있어 빼고, 시각은 `parse_timestamp` 를 통과한 UTC 의 `isoformat()` 이다 —
    `Z` 와 `+00:00` 이 같은 순간인데 문자열이 다르면 원장이 같은 질의를 둘로 센다.
    """
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in params.items()
        if key != "project"
    }


def _log_query(
    dsn: str,
    *,
    client: str,
    tool: str,
    project: str,
    query: str | None,
    params: dict[str, Any],
    results: list[dict[str, Any]],
    with_paths: bool,
    started: float,
) -> None:
    """질의 하나를 원장에 남긴다 (D48–D52).

    **검색 연결과 다른 연결이다.** 같은 연결에 쓰면 INSERT 실패가 검색 트랜잭션을 중단시키고
    psycopg 는 롤백 전까지 그 연결의 모든 문장을 거절한다 — 그러면 실패를 삼킬 수가 없다 (D50).

    **삼키는 범위는 값 만들기까지다.** `filters` 나 `hit_paths` 를 만들다 난 버그가
    500 이 되면 안 된다. 원장이 자기가 기록하는 것을 죽일 수 있으면 안 된다는 것이 규칙이고,
    그 규칙은 쓰기 한 줄이 아니라 이 함수 전체에 걸린다.

    **그래서 만들어진 값이 아니라 재료를 받는다.** 처음에는 `filters=_log_filters(params)` 처럼
    호출자가 만들어 넘겼는데, 키워드 인자는 함수에 들어오기 **전에** 평가되므로 그 계산이
    `try` 밖이었다 — 계약이 삼키라고 한 바로 그 자리가 500 으로 새는 길이었다 (Grok 적대 리뷰).

    경고에 DSN 을 싣지 않는다 (D21·D50). 이 저장소는 예외 경로로 DSN 을 흘린 적이 이미 있다.
    """
    try:
        # 로그 쓰기 자체는 재지 않는다 (D49). 벽시계가 아니라 단조 시계다.
        latency_ms = round((time.perf_counter() - started) * 1000)
        # **값을 여기서 만든다.** 연결을 열기 전이고 `try` 안이라, 값 만들다 난 버그가
        # 연결을 쓰지도 않고 질의를 죽이지도 않는다 (D50 의 `값 만들기까지 감싼다`).
        row = {
            "project": project,
            "client": client,
            "tool": tool,
            "query": query,
            "filters": psycopg.types.json.Jsonb(_log_filters(params)),
            # D49. 문서는 돌려준 행의 path 를 결과 순서대로 중복을 접지 않고,
            # 이벤트는 NULL 이다 — 히트가 경로가 아니라 id 이기 때문이다.
            "hit_paths": [item["path"] for item in results] if with_paths else None,
            "hit_count": len(results),
            "latency_ms": latency_ms,
        }
        with connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kb_query_logs
                    (project, client, tool, query, filters, hit_paths, hit_count, latency_ms)
                VALUES (%(project)s, %(client)s, %(tool)s, %(query)s, %(filters)s,
                        -- 빈 목록은 psycopg 가 타입 없는 `{}` 로 보낸다. 지금 컬럼에는 들어가지만
                        -- 추론에 기대지 않는다 — 0건 질의가 §9 의 완료 조건이 서 있는 행이다.
                        %(hit_paths)s::text[], %(hit_count)s, %(latency_ms)s)
                """,
                row,
            )
    except Exception as exc:  # noqa: BLE001 - 원장이 질의를 죽이면 안 된다 (D50)
        log.warning("질의 로그를 남기지 못했다 (tool=%s): %s", tool, _clip(exc))


def _bounded_query(query: str) -> str:
    """벗긴 질의의 길이를 본다 (D68). 임베딩·SQL·원장 기록보다 앞선다.

    `websearch_to_tsquery` 는 약 2만 낱말에서 `StatementTooComplex` 로 500 이었고(2026-09-26 감사),
    통과한 긴 질의는 `kb_query_logs` 에 영구히 남았다. 넘어진 지점을 상수로 베끼지 않는다 —
    summary 와 같은 수다. `VALIDATION` 이므로 D50 에 따라 원장에 남지 않는다.
    """
    if len(query) > QUERY_MAX:
        raise ValidationFailed(f"query longer than {QUERY_MAX}")
    return query


def search_docs(
    dsn: str, body: dict[str, Any], api_key: str = "", *, client: str = "http"
) -> dict[str, Any]:
    """문서 검색 (D33). 빈 결과는 오류가 아니다 — 200 에 `{"results": []}` 다 (D21).

    `client` 는 **키워드 전용**이다 (D49). `api_key` 뒤에 위치 인자로 두면 HTTP 얼굴이
    실수로 넘길 수 있다. 값은 `http`·`mcp` 둘뿐이고 검증하지 않는다 —
    클라이언트 입력이 아니라 호출자가 자기를 밝히는 값이다.
    """
    started = time.perf_counter()
    if not isinstance(body, dict):
        raise ValidationFailed("body must be an object")
    reject_unknown(body, SEARCH_DOCS_KEYS)  # D69
    project = normalize_project(body.get("project"))
    # search_docs 에서 query 는 필수다 — 질의 말고 신호가 없어 필터만으로는
    # "관련 문서 전부" 가 되고 그것은 설계 위반이다 (D33 §6).
    raw_query = body.get("query")
    if not isinstance(raw_query, str) or not raw_query.strip():
        raise ValidationFailed("query required")
    query = _bounded_query(require_text(raw_query, "query").strip())
    top_k = _top_k(body.get("top_k"))
    where, params = _doc_filters(body, project)

    # 질의 임베딩 실패는 INTERNAL 이다. 키워드 결과로 갈음하지 않는다 —
    # 갈음하면 고장이 D2 의 정상 상태와 같은 모양으로 200 에 나간다 (D33 §4).
    vector = vector_literal(_embed([query], api_key)[0]) if api_key else None

    with connect(dsn) as conn, conn.cursor() as cur:
        keyword = _keyword_arm(cur, where, params, query)
        vectors = _vector_arm(cur, where, params, vector) if vector is not None else []
        # 키워드 항을 먼저 더한다 (D33 §5).
        picked = search.order_and_cut(search.rrf(keyword, vectors), top_k)
        matched = {r.key for r in keyword}
        results = _decorate(cur, picked, query, matched)

    data = {"results": results}
    # D50. 쓰는 자리는 하나다 — `with` 가 닫히고 **돌려줄 dict 가 만들어진 뒤**다.
    # 둘 중 하나만 지키면 두 검색 함수 중 하나에서 어긋난다 (search_events 는 모양이 반대다).
    _log_query(
        dsn,
        client=client,
        tool="search_docs",
        project=project,
        query=query,
        # 재료를 넘긴다. 만들어 넘기면 그 계산이 try 밖이 된다 (D50).
        params=params,
        results=results,
        with_paths=True,
        started=started,
    )
    return data


def _decorate(cur, picked: list[dict], query: str, matched: set) -> list[dict[str, Any]]:
    """`excerpt` 는 `LIMIT` 뒤에만 만든다. 후보 풀에 걸면 원문을 그만큼 다시 파싱한다.

    **한 질의로 모아 온다.** 행마다 부르면 최대 열두 번이고, `WHERE c.id = ANY(…)` 는
    순서를 보존하지 않으므로 병합 순서대로 다시 늘어놓는다 (D33 §9).
    """
    if not picked:
        return []

    ids = [row["id"] for row in picked]
    # 키워드로 걸리지 않은 행에는 ts_headline 을 쓰지 않는다 — 매칭이 없으면
    # 출력 길이가 통제되지 않는다 (실측: 2자짜리 발췌). 그 행은 앞머리를 쓴다.
    keyword_ids = [
        row["id"] for row in picked if (row["repo"], row["path"], row["chunk_idx"]) in matched
    ]
    rows = cur.execute(
        f"""
        SELECT c.id, c.heading_path, d.commit_sha, d.status,
               CASE WHEN c.id = ANY(%(hit)s)
                    THEN ts_headline('{TS_CONFIG}', {EMBED_INPUT_SQL},
                           plainto_tsquery('{TS_CONFIG}', %(query)s), %(opts)s)
                    -- 상한보다 한 글자 더 가져온다. 그래야 clip_excerpt 가 잘렸는지 알고
                    -- 말줄임표를 붙인다 — left(…, 800) 이면 절단과 짧은 청크가 같아 보인다.
                    ELSE left(c.content, %(n)s)
               END AS excerpt
        FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id
        WHERE c.id = ANY(%(ids)s)
        """,
        {
            "ids": ids,
            "hit": keyword_ids,
            "query": query,
            "opts": HEADLINE_OPTS,
            "n": search.EXCERPT_MAX + 1,
        },
    ).fetchall()
    by_id = {r["id"]: r for r in rows}

    results: list[dict[str, Any]] = []
    for row in picked:
        # **팔 질의와 이 질의는 같은 스냅숏이 아니다.** `connect()` 가 격리 수준을 주지 않아
        # 서버 기본값(READ COMMITTED)이고, 그 사이 커밋된 동시 ingest 가 같은 문서를 다시
        # 색인하면 청크는 DELETE 후 INSERT 라 id 가 사라진다 (D32: 문서 하나가 트랜잭션 하나).
        #
        # 사라진 행은 **조용히 뺀다.** 대괄호로 읽으면 KeyError 가 D21 의 포괄 예외에 걸려
        # INTERNAL 500 이 되는데, 그것은 클라이언트 잘못도 서버 결함도 아니다.
        # 병합과 `score` 는 이 함수에 들어오기 전에 이미 정해졌으므로 남은 행의 순서도
        # 점수도 그대로다 (D33 §5) — 빼는 것이 순위를 바꾸지 않는다.
        extra = by_id.get(row["id"])
        if extra is None:
            continue
        results.append(
            {
                "path": row["path"],
                "heading_path": extra["heading_path"],
                "excerpt": search.clip_excerpt(extra["excerpt"]),
                "commit_sha": extra["commit_sha"],
                "status": extra["status"],
                "score": row["score"],
            }
        )
    return results


def _event_search_filters(body: dict[str, Any], project: str) -> tuple[str, dict[str, Any]]:
    """필터가 먼저다 (D34 §3). 남은 집합에 키워드를 건다.

    **4단계의 `_event_filters` 와 이름이 겹치면 안 된다.** 파이썬은 나중 정의로 덮으므로
    `event_stats` 가 조용히 다른 함수를 부르게 된다 — 실제로 한 번 그렇게 났고,
    기존 4단계 검사가 잡았다. 이름을 나누는 것이 이 파일에서 지키는 방식이다.
    """
    where = ["project = %(project)s"]
    params: dict[str, Any] = {"project": project}
    for field in ("kind", "module"):
        value = _enum_filter(_filter_text(body, field), field, KINDS if field == "kind" else None)
        if value is not None:
            where.append(f"{field} = %({field})s")
            params[field] = value
    # [since, until) — since 는 포함, until 은 배제다 (D69).
    for field, op in (("since", ">="), ("until", "<")):
        raw = body.get(field)
        if raw is not None:
            params[field] = parse_timestamp(raw, field)
            where.append(f"occurred_at {op} %({field})s")
    # 순간이 하나도 없는 창은 거절한다. `[t, t)` 를 0건으로 원장에 남기지 않는다 (D69).
    if "since" in params and "until" in params and params["since"] >= params["until"]:
        raise ValidationFailed("since is not before until")
    return " AND ".join(where), params


def search_events(dsn: str, body: dict[str, Any], *, client: str = "http") -> dict[str, Any]:
    """이벤트 검색 (D33 · D34). **v1 은 이벤트를 임베딩하지 않는다** — 키워드만이다.

    `client` 는 `search_docs` 와 같은 규칙이다 (D49).
    """
    started = time.perf_counter()
    if not isinstance(body, dict):
        raise ValidationFailed("body must be an object")
    reject_unknown(body, SEARCH_EVENTS_KEYS)  # D69
    project = normalize_project(body.get("project"))
    top_k = _top_k(body.get("top_k"))
    # search_events 에서 query 는 선택이다 — 필터만으로도 완결된 요청이 된다 (D33 §6).
    raw_query = body.get("query")
    if raw_query is not None and not isinstance(raw_query, str):
        raise ValidationFailed("query must be a string")
    query = require_text(raw_query or "", "query").strip() or None
    if query is not None:
        _bounded_query(query)
    where, params = _event_search_filters(body, project)

    fields = "id, title, summary, kind, result, module, occurred_at"
    with connect(dsn) as conn, conn.cursor() as cur:
        if query is None:
            rows = cur.execute(
                f"SELECT {fields}, NULL::float8 AS score FROM kb_events"
                f" WHERE {where} ORDER BY occurred_at DESC, id DESC LIMIT %(top_k)s",
                {**params, "top_k": top_k},
            ).fetchall()
        else:
            rows = cur.execute(
                f"""
                SELECT {fields},
                       rank() OVER (ORDER BY ts_rank(tsv, tq.q, 1) DESC,
                                    occurred_at DESC, id DESC) AS rk
                FROM kb_events, websearch_to_tsquery('{TS_CONFIG}', %(query)s) AS tq(q)
                WHERE {where} AND tsv @@ tq.q
                  -- 빈 tsvector 에도 참인 질의(부정만 있는 `-낱말`)는 0건이다 (D69).
                  -- 그런 질의는 코퍼스 거의 전체를 맞힌다 — D33 이 문서에서 websearch 를 버린 그 고장.
                  AND NOT (''::tsvector @@ tq.q)
                ORDER BY rk
                LIMIT %(top_k)s
                """,
                {**params, "query": query, "top_k": top_k},
            ).fetchall()

    results = []
    for row in rows:
        item = {k: row[k] for k in fields.split(", ")}
        item["occurred_at"] = item["occurred_at"].isoformat()
        # D58. `excerpt` 와 **같은 함수**를 쓴다 — 두 벌로 만들면 한쪽이 801자가 된다.
        # 원문은 `get_event` 가 그대로 준다 (D39).
        item["summary"] = search.clip_excerpt(item["summary"])
        # 목록이 하나뿐이라 RRF 는 그 순위의 단조 재표기다 (D33 §7).
        item["score"] = (
            None if query is None else round(1.0 / (search.RRF_K + row["rk"]), search.SCORE_DIGITS)
        )
        results.append(item)

    data = {"results": results}
    # 여기가 `with` 뒤이면서 dict 가 생긴 뒤다. 이 함수는 `with` 가 닫힌 **뒤에** 행을 변환하므로
    # `with 뒤`만 지키면 아직 결과가 없다 — D50 이 두 조건을 함께 적은 이유다.
    _log_query(
        dsn,
        client=client,
        tool="search_events",
        project=project,
        query=query,
        params=params,
        results=results,
        # D49. 이벤트 히트는 경로가 아니라 id 다. 한 text[] 에 두 종류의 식별자를 섞지 않는다.
        with_paths=False,
        started=started,
    )
    return data


# --- 7단계 단건·제안 (D35–D41) ----------------------------------------------

# D39. 행이 가진 사실을 전부 주되 파생 컬럼(`tsv`)과 v1 이 채우지 않는 벡터(`embedding`, D34)는 뺀다.
EVENT_FIELDS = (
    "id",
    "project",
    "module",
    "kind",
    "title",
    "summary",
    "root_cause",
    "resolution",
    "result",
    "severity",
    "occurred_at",
    "resolved_at",
    "source",
    "related_doc_path",
    "payload",
    "created_at",
    "created_by",
)
_EVENT_TIMESTAMPS = ("occurred_at", "resolved_at", "created_at")

# 없는 것과 남의 것은 같은 답이다 (D35). 무엇이 없는지도 구분해 알려 주지 않는다.
NOT_FOUND_EVENT = "event not found"
NOT_FOUND_FILE = "file not found"
NOT_FOUND_DOC = "document not found"

# D38. D32 의 문구를 쓰지 않는다 — 발신자가 둘이고 원인이 다르다.
BASE_HASH_MESSAGE = "document changed since base_hash"
# D40. 받아들이는 형식은 하나다. 접두사를 관대하게 벗기면 "무엇이 같은 해시인가" 규칙이 생긴다.
# **fullmatch 로 본다.** `$` 는 끝의 개행 **앞**에서도 맞으므로 `^…$` + match 는
# 뒤에 개행이 붙은 값을 통과시키고, 그 개행이 digest 에 남아 영원한 CONFLICT 가 된다 —
# 클라이언트 입력 문제가 VALIDATION 이 아니라 충돌로 보고되는 것이다 (Grok 지적).
_BASE_HASH = re.compile(r"sha256:[0-9a-f]{64}")


class NotFound(Exception):
    """지목한 조회에 답이 없다 (D35). 집합 질의는 빈 결과이지 이 예외가 아니다."""


class BaseHashMismatch(Exception):
    """`save_doc` 의 `base_hash` 가 현재 내용과 다르다. `CONFLICT` 의 둘째 발신자다 (D38)."""


def _require_path(raw: object) -> str:
    """**정규화하지 않는다** (D36). `kb_documents` 의 값과 바이트로 같아야 한다.

    빈 문자열·끝의 슬래시·겹친 슬래시·`./` 는 정규화 대상이 아니라 그냥 행이 없는 것이고 404 다.
    여기서 정규화하면 "무엇이 같은 경로인가" 라는 두 번째 규칙이 생기고,
    그 규칙이 곧 허용 목록을 느슨하게 만드는 손잡이가 된다.
    """
    if not isinstance(raw, str):
        raise ValidationFailed("path must be a string")
    # 담을 수 없는 문자만 예외다. **정규화가 아니라 물어볼 수 없는 질문을 거절하는 것이다.**
    # 실측: `path=docs/plan.md%00.txt` 가 500 을 냈다 (Grok 이 라이브에서 찾았다).
    # 이유 전문과 이 부류의 나머지 자리는 `require_text` 에 있다 — 여기서 되풀이하지 않는다.
    return require_text(raw, "path")


def _require_offset(raw: object) -> int:
    # 생략은 0 이다 (D36 가장자리 표). 기본값이 여기 하나뿐이어야 두 얼굴이 같은 값을 쓴다.
    if raw is None:
        return 0
    # bool 은 int 의 하위 타입이다. `offset=true` 를 0/1 로 받아들이지 않는다.
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValidationFailed("offset must be an integer")
    if raw < 0:
        raise ValidationFailed("offset must not be negative")
    return raw


def _require_event_id(raw: object) -> int:
    """HTTP 얼굴에서는 경로 인자라 늘 정수지만, MCP 도구에서는 비울 수 있다 (D42).

    비운 채로 SQL 에 넣으면 `id = NULL` 이 되어 **없는 것과 같은 404** 가 나간다 —
    인자를 안 준 것과 남의 것을 물은 것이 같은 답이 되어 D35 가 지키려던 구분이 사라진다.
    """
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValidationFailed("event_id must be an integer")
    return raw


def _require_base_hash(raw: object) -> str | None:
    """D40. `sha256:` + 소문자 16진 64자. 없으면 검사하지 않는다 (D38)."""
    if raw is None:
        return None
    if not isinstance(raw, str) or not _BASE_HASH.fullmatch(raw):
        raise ValidationFailed("base_hash must be sha256: followed by 64 lowercase hex digits")
    return raw.split(":", 1)[1]


def _indexed(dsn: str, project: str, path: str) -> bool:
    """허용 목록은 `kb_documents` 다 (D36). D9·D30 을 요청 문자열 위에 다시 구현하지 않는다.

    `repo = ''` 는 ingest 가 넣는 값이다 (D37). `repo` 를 두 번째 뿌리로 쓰면 Q20 이 되살아난다.
    """
    with connect(dsn) as conn, conn.cursor() as cur:
        row = cur.execute(
            "SELECT id FROM kb_documents WHERE project = %s AND repo = '' AND path = %s",
            (project, path),
        ).fetchone()
    return row is not None


def get_event(dsn: str, event_id: int, project: object) -> dict[str, Any]:
    """D35·D39. `project` 는 필수이고, 행의 `project` 와 다르면 없는 것과 같은 답이다.

    경계 검사를 SQL 에 둔다. 행을 읽어 와서 파이썬에서 비교하면 그 사이에 "읽었지만 안 준다" 는
    상태가 생기고, 로그·예외 문구 한 줄이 남의 이벤트 존재를 흘린다.
    """
    project = normalize_project(project)
    event_id = _require_event_id(event_id)
    with connect(dsn) as conn, conn.cursor() as cur:
        row = cur.execute(
            f"SELECT {', '.join(EVENT_FIELDS)} FROM kb_events"
            " WHERE id = %(id)s AND project = %(project)s",
            {"id": event_id, "project": project},
        ).fetchone()
    if row is None:
        raise NotFound(NOT_FOUND_EVENT)

    event = dict(row)
    for field in _EVENT_TIMESTAMPS:
        value = event[field]
        event[field] = value.isoformat() if value is not None else None
    return event


def _open_in_workspace(workspace: str, path: str) -> int:
    """D36 의 걸음. 호출자가 fd 를 닫는다."""
    return workspace_rules.open_regular(workspace, path)


def get_file(dsn: str, project: object, path: object, offset: object, workspace: str) -> dict[str, Any]:
    """D36·D37·D41. 색인된 행만 열고, 응답은 파일이 아니라 창이다.

    `text` 는 **원본 바이트를 그대로 푼 것이다.** 정규화하면 `offset` 세 개가 무엇의
    바이트인지 사라진다 — `save_doc` 이 정규화한 텍스트를 보는 것과 일부러 다르다 (D41).
    """
    project = normalize_project(project)
    path = _require_path(path)
    offset = _require_offset(offset)

    if not _indexed(dsn, project, path):
        raise NotFound(NOT_FOUND_FILE)

    try:
        fd = _open_in_workspace(workspace, path)
    except workspace_rules.OpenFailed as exc:
        # 행은 남아 있고 파일 쪽이 바뀐 것이다 (D36). 구분은 로그에만 남긴다.
        log.warning("색인된 행을 열지 못했다: %s (%s)", ingest_rules.printable(path), exc)
        raise NotFound(NOT_FOUND_FILE) from None

    try:
        window = workspace_rules.read_window(fd, offset)
    except workspace_rules.OffsetInvalid as exc:
        raise ValidationFailed(str(exc)) from None
    finally:
        os.close(fd)

    return {"project": project, "path": path, **window}


def _read_current(workspace: str, path: str) -> str | None:
    """`save_doc` 이 보는 현재 내용 — D36 의 걸음으로 열되 **끝까지 읽는다** (D38).

    D30 의 정규화를 거친다 (D41). 해시와 diff 가 같은 텍스트를 봐야 응답이 자기모순이 되지 않는다.
    열 수 없으면 빈 내용이 아니라 **부재**다 — None 이 그것이다.
    """
    try:
        fd = _open_in_workspace(workspace, path)
    except workspace_rules.OpenFailed as exc:
        log.warning("제안 대상 파일을 열지 못했다: %s (%s)", ingest_rules.printable(path), exc)
        return None
    try:
        raw = workspace_rules.read_all(fd)
    finally:
        os.close(fd)
    return ingest_rules.normalize(raw, path)


def _unified_diff(path: str, current: str | None, proposed: str) -> str:
    """현재 파일과 제안 본문의 unified diff. 같으면 빈 문자열이다 (D38).

    파일이 없으면 `/dev/null` 에서의 추가다 (D41). **새 문서 제안이 아니다** — 행은 있어야 한다.
    """
    before = current.splitlines(keepends=True) if current is not None else []
    return "".join(
        difflib.unified_diff(
            before,
            proposed.splitlines(keepends=True),
            fromfile=f"a/{path}" if current is not None else "/dev/null",
            tofile=f"b/{path}",
        )
    )


def save_doc(dsn: str, body: dict[str, Any], workspace: str) -> dict[str, Any]:
    """D38·D40·D41. **Git 에 쓰지 않는다** — 응답이 전부다 (D3).

    `body` 는 문서 전체다. 부분 패치를 받지 않는다 — 서버가 조각을 붙이기 시작하면
    붙이는 규칙이 두 번째 계약이 되고, 그 규칙은 아무 문서에도 없다.
    """
    if not isinstance(body, dict):
        raise ValidationFailed("body must be an object")
    reject_unknown(body, SAVE_DOC_KEYS)  # D69
    project = normalize_project(body.get("project"))
    path = _require_path(body.get("path"))
    proposed_raw = body.get("body")
    if not isinstance(proposed_raw, str):
        raise ValidationFailed("body required: the whole document as a string")
    # 이 자리의 싱크는 SQL 이 아니라 아래의 `.encode("utf-8")` 이다 — 짝 없는 서로게이트가
    # 거기서 UnicodeEncodeError 를 내고 D21 이 INTERNAL 500 으로 접었다 (실측 2026-09-04).
    # NUL 은 저장되지 않으므로 여기서는 무해하지만, **부류를 자리마다 쪼개지 않는다.**
    require_text(proposed_raw, "body")
    base_hash = _require_base_hash(body.get("base_hash"))

    # 경로 판정은 get_file 과 같다 (D38). 색인된 경로만 고칠 수 있다.
    if not _indexed(dsn, project, path):
        raise NotFound(NOT_FOUND_DOC)

    current = _read_current(workspace, path)
    if base_hash is not None:
        # 파일이 없으면 어떤 해시와도 다르다 — 사라진 것은 바뀐 것의 부분집합이다 (D41).
        digest = ingest_rules.content_hash(current) if current is not None else None
        if digest != base_hash:
            # 현재 해시를 응답에 싣지 않는다 (D38). error 봉투는 값을 나르는 자리가 아니다.
            raise BaseHashMismatch(BASE_HASH_MESSAGE)

    # body 도 같은 정규화를 거친다 (D41). 한쪽만 정규화하면 자기모순이 방향만 바꿔 돌아온다.
    proposed = ingest_rules.normalize(proposed_raw.encode("utf-8"), path)
    return {
        "proposal": {
            "project": project,
            "path": path,
            "exists": current is not None,
            "diff": _unified_diff(path, current, proposed),
            "body": proposed,
        }
    }


def resolve_workspace(requested: object, configured: str) -> str:
    """D37. ingest 는 `SILLOK_WORKSPACE` 와 다른 나무를 색인하지 않는다.

    저쪽 나무를 색인해 두면 `get_file` 은 **이 나무**를 저쪽의 `path` 로 연다 —
    같은 경로에 다른 내용이 있으면 조용히 남의 파일을 돌려준다.

    같은지는 **정규화한 절대 경로**로 본다. `.` 과 `/workspace` 가 같은 곳을 가리켜도
    문자열은 다르다. 기본값(`.`)이면 프로세스의 작업 디렉터리를 기준으로 푼다.
    거절 문구에 설정값을 싣지 않는다 — 요청자가 이미 아는 값만 돌려준다.
    """
    if requested is None or requested == "":
        return configured
    if not isinstance(requested, str):
        raise ValidationFailed("workspace must be a string")
    # `_real` 은 `Path(...).resolve()` 다. NUL·서로게이트가 들어오면 거기서 ValueError 가 나고
    # `api.classify` 에 분기가 없어 INTERNAL 500 이 된다 — 비교보다 **먼저** 거른다.
    require_text(requested, "workspace")
    if _real(requested) != _real(configured):
        raise ValidationFailed(
            f"workspace must be the configured SILLOK_WORKSPACE (D37): {requested!r} is a different tree"
        )
    return configured


def _real(path: str) -> str:
    # normcase 까지 간다. Windows 에서 대소문자만 다른 두 문자열이 같은 디렉터리다.
    return os.path.normcase(str(Path(path).resolve()))
