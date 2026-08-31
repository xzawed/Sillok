"""Service 함수 — DB를 만지는 유일한 문 (D19).

여기 있는 함수만 SQL을 안다. HTTP 어댑터(`api.py`)와 CLI는 이 함수들을 부를 뿐이다.
4단계(plan §7)의 세 가지: `save_event` · `event_stats` · `kb_status`.

**검증은 여기서 한다 (D10·D25).** DDL에 CHECK를 두지 않는 이유는, CHECK 위반이
Postgres 예외가 되고 D21이 그것을 `INTERNAL 500`으로 접기 때문이다 —
클라이언트 입력 문제가 서버 결함으로 보고되면 안 된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from . import migrations

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
_PROJECT_FORBIDDEN = (" ", "\t", "\n", "\r", "/", "\\", "\x00")

# D23. Skill 의 "2회 이상" 이 임계값이고, 상한은 검색 최대치와 같은 값이다.
REPEAT_MIN_COUNT = 2
REPEAT_LIMIT = 12


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


def connect(dsn: str) -> psycopg.Connection:
    """psycopg 예외를 그대로 올린다. 감싸는 것은 호출자의 몫이다.

    **타임아웃을 반드시 준다.** 없으면 DB 가 닿지 않을 때 요청이 무한히 매달린다 —
    마이그레이션 러너에서 같은 결함을 이미 한 번 고쳤는데(D17 기동 경로) 여기서 되풀이했다.
    실측: 타임아웃 없이 죽은 호스트로 붙으면 한 요청이 130초를 먹었다.
    """
    return psycopg.connect(
        dsn, row_factory=dict_row, connect_timeout=migrations.CONNECT_TIMEOUT_SECONDS
    )


# --- 검증 (D25) ------------------------------------------------------------


def normalize_project(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValidationFailed("project must be a string")
    project = raw.strip()
    if not project:
        raise ValidationFailed("project required")
    if len(project) > PROJECT_MAX:
        raise ValidationFailed(f"project longer than {PROJECT_MAX}")
    for bad in _PROJECT_FORBIDDEN:
        if bad in project:
            raise ValidationFailed("project must not contain whitespace, slash or NUL")
    # 대소문자를 접지 않는다. 슬러그 알파벳을 여기서 발명하지 않는다 (D25).
    return project


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
    return parsed.astimezone(timezone.utc)


def _optional_text(body: dict[str, Any], field: str) -> str | None:
    value = body.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationFailed(f"{field} must be a string")
    return value


def _enum(body: dict[str, Any], field: str, allowed: frozenset[str]) -> str | None:
    value = _optional_text(body, field)
    if value is not None and value not in allowed:
        raise ValidationFailed(f"{field} must be one of {sorted(allowed)}")
    return value


def build_event(body: dict[str, Any]) -> Event:
    """요청 본문을 검증된 Event 로 만든다. 관대하게 채우지 않는다 (D10)."""
    if not isinstance(body, dict):
        raise ValidationFailed("body must be an object")

    missing = [f for f in REQUIRED_FIELDS if body.get(f) in (None, "")]
    if missing:
        raise ValidationFailed("missing required field: " + ", ".join(missing))

    project = normalize_project(body["project"])

    title = body["title"]
    summary = body["summary"]
    if not isinstance(title, str) or not isinstance(summary, str):
        raise ValidationFailed("title and summary must be strings")
    if len(title) > TITLE_MAX:
        raise ValidationFailed(f"title longer than {TITLE_MAX}")
    if len(summary) > SUMMARY_MAX:
        raise ValidationFailed(f"summary longer than {SUMMARY_MAX}")

    kind = body["kind"]
    result = body["result"]
    if kind not in KINDS:
        raise ValidationFailed(f"kind must be one of {sorted(KINDS)}")
    if result not in RESULTS:
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
        for field, key in (("kind", "by_kind"), ("result", "by_result"), ("module", "by_module")):
            cur.execute(
                f"SELECT {field} AS bucket, count(*) AS n FROM kb_events"
                f" WHERE {where} GROUP BY {field}",
                params,
            )
            # module 이 NULL 인 행의 키는 넣지 않는다 — JSON 키는 null 일 수 없고
            # "null" 은 실제 모듈명과 충돌한다. 그 행들은 total 에 그대로 남는다 (D23).
            buckets[key] = {
                row["bucket"]: row["n"] for row in cur.fetchall() if row["bucket"] is not None
            }

        cur.execute(
            f"""
            SELECT module, root_cause, count(*) AS count
            FROM kb_events
            WHERE {where} AND root_cause IS NOT NULL
            GROUP BY module, root_cause
            HAVING count(*) >= {REPEAT_MIN_COUNT}
            ORDER BY count DESC, root_cause ASC
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
              -- 5단계 전까지 null. 빈 값이 정상이지 스텁이 아니다.
              (SELECT max(finished_at) FROM kb_ingest_runs WHERE project = %(p)s) AS last_ingest_at,
              -- 9단계 전까지 0.
              (SELECT count(*) FROM kb_query_logs
                 WHERE project = %(p)s AND hit_count = 0) AS zero_hit_queries
            """,
            {"p": project},
        )
        row = cur.fetchone()

    last = row["last_ingest_at"]
    return {
        "documents": row["documents"],
        "chunks": row["chunks"],
        "events": row["events"],
        "last_ingest_at": last.isoformat() if last is not None else None,
        "zero_hit_queries": row["zero_hit_queries"],
    }
