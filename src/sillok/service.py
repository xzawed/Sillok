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
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from . import ingest as ingest_rules
from . import search
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
    return psycopg.connect(
        dsn,
        row_factory=dict_row,
        connect_timeout=migrations.CONNECT_TIMEOUT_SECONDS,
        autocommit=autocommit,
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
            ORDER BY count DESC, root_cause ASC, module ASC NULLS LAST
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
              -- 실패한 run 은 세지 않는다 (D32) — 세면 실패가 마지막 색인으로 보고된다.
              (SELECT max(finished_at) FROM kb_ingest_runs
                 WHERE project = %(p)s AND status = ANY(%(counted)s)) AS last_ingest_at,
              -- 9단계 전까지 0.
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


def _embed(texts: list[str], api_key: str) -> list[list[float]]:
    """임베딩 클라이언트는 여기서만 부른다. import 도 여기서 한다.

    키가 없으면 이 함수가 아예 불리지 않으므로(D2·D31) 커밋된 구성에서
    의존성이 없어도 검사가 돈다. 키가 있는 상태의 검사 경로는 D31 이 남긴 자리다.
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    result = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in result.data]


def _clip(text: object) -> str:
    """error 는 첫 실패의 첫 줄이고 상한에서 자른다. run 하나가 로그가 되면 안 된다 (D32)."""
    lines = migrations.redact_dsn(str(text)).splitlines()
    return (lines[0] if lines else "")[:ERROR_MAX]


def _write_document(conn: psycopg.Connection, project: str, doc: dict[str, Any]) -> int:
    """문서 하나가 트랜잭션 하나다 (D32).

    kb_documents upsert + 그 문서의 청크 DELETE + INSERT 가 한 트랜잭션에 든다.
    나누면 그 사이에 들어온 검색이 문서를 0건으로 돌려준다 — 오류 없이 조용히.
    """
    with conn.transaction(), conn.cursor() as cur:
        row = cur.execute(
            """
            INSERT INTO kb_documents
              (project, repo, path, doc_type, module, status, title, content_hash, source_mtime)
            VALUES (%(project)s, '', %(path)s, %(doc_type)s, %(module)s, %(status)s, %(title)s,
                    %(content_hash)s, %(source_mtime)s)
            ON CONFLICT (project, repo, path) DO UPDATE SET
              doc_type = EXCLUDED.doc_type,
              module = EXCLUDED.module,
              status = EXCLUDED.status,
              title = EXCLUDED.title,
              content_hash = EXCLUDED.content_hash,
              source_mtime = EXCLUDED.source_mtime,
              indexed_at = now()
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
            return done, _clip(exc)
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
    """taxonomy 밖이면 서비스가 거절한다. DDL 에 CHECK 를 더하지 않는다 (D25)."""
    if meta["doc_type"] not in ingest_rules.DOC_TYPES:
        raise IngestFailed(path + ': doc_type "' + str(meta["doc_type"]) + '" is outside the taxonomy')
    if meta["status"] not in ingest_rules.STATUSES:
        raise IngestFailed(path + ': status "' + str(meta["status"]) + '" is outside the taxonomy')


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
        files, skips = ingest_rules.scan(root)
        skipped = [{"path": s.path, "reason": s.reason} for s in skips]
        counters["files_seen"] = len(files)
        # 잘못된 workspace 한 번이 인덱스를 통째로 지우는 것이 이 결정의 유일한 파국이다.
        if not files:
            raise IngestFailed("scan found no .md under the D9 paths")

        with conn.cursor() as cur:
            known = {
                r["path"]: r["content_hash"]
                for r in cur.execute(
                    "SELECT path, content_hash FROM kb_documents WHERE project = %s AND repo = ''",
                    (project,),
                ).fetchall()
            }

        for item in files:
            text = ingest_rules.normalize(item.absolute.read_bytes(), item.path)
            digest = ingest_rules.content_hash(text)
            if known.get(item.path) == digest:
                continue
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
                    "source_mtime": datetime.fromtimestamp(item.mtime, tz=timezone.utc),
                    "chunks": pieces,
                    **meta,
                },
            )
            counters["files_changed"] += 1
            counters["chunks_upserted"] += len(pieces)

        # 삭제는 백필 앞이다. 뒤에 두면 백필 첫 실패에서 멈추는 run 이
        # 삭제를 영구히 건너뛴다 — 텍스트 색인의 일부인데 벡터 때문에 빠지는 것이다.
        with conn.transaction(), conn.cursor() as cur:
            gone = cur.execute(
                "DELETE FROM kb_documents WHERE project = %s AND repo = ''"
                " AND NOT (path = ANY(%s)) RETURNING id",
                # 제외(skip)는 삭제 후보가 아니다 (D30 §1). 빼면 파일 하나를 심볼릭 링크로
                # 바꾸는 것만으로 그 문서가 인덱스에서 지워진다.
                (project, [f.path for f in files] + [s.path for s in skips]),
            ).fetchall()
            counters["files_deleted"] = len(gone)

        if api_key:
            embedded, failure = _backfill(conn, project, api_key)
            if failure is not None:
                status, error = "partial", failure
    except (IngestFailed, ingest_rules.DecodeFailed) as exc:
        status, error = "failed", _clip(exc)
    except Exception as exc:
        # run 행에 남기고 다시 올린다. api 가 INTERNAL 로 접는다 (D21).
        _finish(conn, run_id, "failed", _clip(exc), counters)
        raise

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


def _optional_text(body: dict[str, Any], field: str) -> str | None:
    """필드가 없거나 null 이면 거르지 않는다 (D33 §1)."""
    raw = body.get(field)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValidationFailed(f"{field} must be a string")
    value = raw.strip()
    return value or None


def _doc_filters(body: dict[str, Any], project: str) -> tuple[str, dict[str, Any]]:
    """필터는 **두 팔의 WHERE** 에 건다. 병합 뒤에 거르면 걸러질 행이 후보 칸을 먹는다."""
    where = ["d.project = %(project)s"]
    params: dict[str, Any] = {"project": project}
    for field in ("module", "doc_type", "status"):
        value = _optional_text(body, field)
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


def search_docs(dsn: str, body: dict[str, Any], api_key: str = "") -> dict[str, Any]:
    """문서 검색 (D33). 빈 결과는 오류가 아니다 — 200 에 `{"results": []}` 다 (D21)."""
    if not isinstance(body, dict):
        raise ValidationFailed("body must be an object")
    project = normalize_project(body.get("project"))
    # search_docs 에서 query 는 필수다 — 질의 말고 신호가 없어 필터만으로는
    # "관련 문서 전부" 가 되고 그것은 설계 위반이다 (D33 §6).
    raw_query = body.get("query")
    if not isinstance(raw_query, str) or not raw_query.strip():
        raise ValidationFailed("query required")
    query = raw_query.strip()
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

    return {"results": results}


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

    return [
        {
            "path": row["path"],
            "heading_path": by_id[row["id"]]["heading_path"],
            "excerpt": search.clip_excerpt(by_id[row["id"]]["excerpt"]),
            "commit_sha": by_id[row["id"]]["commit_sha"],
            "status": by_id[row["id"]]["status"],
            "score": row["score"],
        }
        for row in picked
    ]


def _event_search_filters(body: dict[str, Any], project: str) -> tuple[str, dict[str, Any]]:
    """필터가 먼저다 (D34 §3). 남은 집합에 키워드를 건다.

    **4단계의 `_event_filters` 와 이름이 겹치면 안 된다.** 파이썬은 나중 정의로 덮으므로
    `event_stats` 가 조용히 다른 함수를 부르게 된다 — 실제로 한 번 그렇게 났고,
    기존 4단계 검사가 잡았다. 이름을 나누는 것이 이 파일에서 지키는 방식이다.
    """
    where = ["project = %(project)s"]
    params: dict[str, Any] = {"project": project}
    for field in ("kind", "module"):
        value = _optional_text(body, field)
        if value is not None:
            where.append(f"{field} = %({field})s")
            params[field] = value
    for field, op in (("since", ">="), ("until", "<")):
        raw = body.get(field)
        if raw is not None:
            params[field] = parse_timestamp(raw, field)
            where.append(f"occurred_at {op} %({field})s")
    return " AND ".join(where), params


def search_events(dsn: str, body: dict[str, Any]) -> dict[str, Any]:
    """이벤트 검색 (D33 · D34). **v1 은 이벤트를 임베딩하지 않는다** — 키워드만이다."""
    if not isinstance(body, dict):
        raise ValidationFailed("body must be an object")
    project = normalize_project(body.get("project"))
    top_k = _top_k(body.get("top_k"))
    # search_events 에서 query 는 선택이다 — 필터만으로도 완결된 요청이 된다 (D33 §6).
    raw_query = body.get("query")
    if raw_query is not None and not isinstance(raw_query, str):
        raise ValidationFailed("query must be a string")
    query = (raw_query or "").strip() or None
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
                ORDER BY rk
                LIMIT %(top_k)s
                """,
                {**params, "query": query, "top_k": top_k},
            ).fetchall()

    results = []
    for row in rows:
        item = {k: row[k] for k in fields.split(", ")}
        item["occurred_at"] = item["occurred_at"].isoformat()
        # 목록이 하나뿐이라 RRF 는 그 순위의 단조 재표기다 (D33 §7).
        item["score"] = (
            None if query is None else round(1.0 / (search.RRF_K + row["rk"]), search.SCORE_DIGITS)
        )
        results.append(item)
    return {"results": results}
