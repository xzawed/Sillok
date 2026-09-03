---
title: Sillok 데이터 모델
doc_type: schema
status: current
module: null
---

# Sillok 데이터 모델

상위: [plan.md](plan.md) · [README](../README.md)

> 이 파일은 DDL과 컬럼 enum의 정본이다.
> `vector(1536)`·모델 ID·확장 목록의 정본은 [adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md)다.

PostgreSQL 16+ , 확장: `vector`, `pg_trgm`.  
임베딩: OpenAI `text-embedding-3-small`, **`vector(1536)` 확정**. 키 없으면 해당 행의 `embedding`은 NULL이고 키워드(`tsv`)만 검색한다.

문자셋: UTF-8. 검색 구성: 우선 `simple` (한국어·식별자 혼용).

## 확장

**테이블보다 먼저 실행한다.** `vector` 없이 `vector(1536)` 컬럼을 만들 수 없다.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

이미지에 확장 파일이 들어 있어도(`pgvector/pgvector:pg16` 등) `CREATE EXTENSION`은 DB마다 따로 필요하다.
적용 수단은 D17 — 버전 붙인 raw `.sql`을 `sillok serve` 기동 시 bind 전에 멱등 적용한다.
`001`이 확장, `002`가 아래 스키마다. **마이그레이션 파일은 이 문서의 SQL을 실행할 뿐 두 번째 스키마 정의가 아니다.**

## 문서 헤더

Git 현재 문서의 인덱스 헤더. 원문은 Git.

```sql
CREATE TABLE kb_documents (
  id            bigserial PRIMARY KEY,
  project       text NOT NULL,
  repo          text NOT NULL DEFAULT '',
  path          text NOT NULL,
  doc_type      text NOT NULL DEFAULT 'other',
  -- adr | api | runbook | readme | schema | other
  module        text,
  status        text NOT NULL DEFAULT 'current',
  -- current | draft | superseded | stale
  title         text,
  commit_sha    text NOT NULL DEFAULT '',
  content_hash  text NOT NULL,
  source_mtime  timestamptz,
  indexed_at    timestamptz NOT NULL DEFAULT now(),
  token_count   int,
  UNIQUE (project, repo, path)
);
```

## 청크

```sql
CREATE TABLE kb_chunks (
  id            bigserial PRIMARY KEY,
  document_id   bigint NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
  chunk_idx     int NOT NULL,
  heading_path  text,
  content       text NOT NULL,
  embedding     vector(1536),  -- text-embedding-3-small
  tsv           tsvector GENERATED ALWAYS AS
                  (to_tsvector('simple', coalesce(heading_path,'') || ' ' || content)) STORED,
  token_count   int,
  UNIQUE (document_id, chunk_idx)
);
```

청크 경계의 정본은 **D30**이다 — 헤딩 우선, 블록 채우기로 소프트 상한 1200자, 하드 상한 4000자, overlap 없음.  
파일 단위로 옛 청크를 지우고 다시 넣는다.

## 이벤트 원장

```sql
CREATE TABLE kb_events (
  id                bigserial PRIMARY KEY,
  project           text NOT NULL,
  module            text,
  kind              text NOT NULL,
  -- success | failure | incident | decision
  title             text NOT NULL,
  summary           text NOT NULL,
  root_cause        text,
  resolution        text,
  result            text NOT NULL,
  -- success | failure | partial | unknown
  severity          text,
  -- low | medium | high | critical
  occurred_at       timestamptz NOT NULL,
  resolved_at       timestamptz,
  source            text NOT NULL DEFAULT 'agent',
  related_doc_path  text,
  payload           jsonb NOT NULL DEFAULT '{}'::jsonb,
  embedding         vector(1536),  -- text-embedding-3-small, summary만. v1 은 채우지 않는다 (D34)
  created_at        timestamptz NOT NULL DEFAULT now(),
  created_by        text,
  tsv               tsvector GENERATED ALWAYS AS
                      (to_tsvector('simple',
                        coalesce(title,'')      || ' ' || coalesce(summary,'')    || ' ' ||
                        coalesce(root_cause,'') || ' ' || coalesce(resolution,''))) STORED
  -- D34. 네 필드를 전부 coalesce 로 감싼다 — 하나가 NULL 이면 tsv 가 통째로 NULL 이 된다.
);

CREATE INDEX kb_events_project_time ON kb_events (project, occurred_at DESC);
CREATE INDEX kb_events_filter ON kb_events (project, kind, result, module);
```

통계는 이 테이블의 필터 + `COUNT` / `AVG(resolved_at - occurred_at)` 로만 계산한다.

## 운영

```sql
CREATE TABLE kb_ingest_runs (
  id               bigserial PRIMARY KEY,
  project          text NOT NULL,
  started_at       timestamptz NOT NULL DEFAULT now(),
  finished_at      timestamptz,
  commit_sha       text,
  files_seen       int,
  files_changed    int,
  files_deleted    int,        -- D30. 삭제는 files_changed 에 접지 않는다
  chunks_upserted  int,
  status           text NOT NULL DEFAULT 'running',
  -- running | ok | partial | failed  (D32. CHECK 를 걸지 않는다 — D25)
  error            text
);

CREATE TABLE kb_query_logs (
  id          bigserial PRIMARY KEY,
  created_at  timestamptz NOT NULL DEFAULT now(),
  project     text,
  client      text,       -- http | mcp  (D49. 얼굴이다. 전송은 구분하지 않는다)
  tool        text NOT NULL,
  -- search_docs | search_events  (D48. 검색 둘만 남긴다)
  query       text,       -- D49. search_events 가 질의 없이 불리면 NULL
  filters     jsonb,      -- D49. 실제로 SQL 에 걸린 필터만. project·query·top_k 는 넣지 않는다
  hit_paths   text[],     -- D49. 문서는 결과 순서대로 중복을 접지 않고, 이벤트는 NULL
  hit_count   int,        -- D49. 돌려준 행 수. 고유 문서 수가 아니다
  latency_ms  int         -- D49. Service 진입부터 로그 쓰기 직전까지
);
```

## 인덱스

```sql
CREATE INDEX kb_chunks_hnsw
  ON kb_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX kb_chunks_tsv ON kb_chunks USING gin (tsv);
CREATE INDEX kb_docs_lookup ON kb_documents (project, doc_type, status, module);

CREATE INDEX kb_events_tsv ON kb_events USING gin (tsv);

CREATE INDEX kb_events_hnsw
  ON kb_events USING hnsw (embedding vector_cosine_ops);

CREATE INDEX kb_query_logs_project_time ON kb_query_logs (project, created_at DESC);
```

**v1 은 HNSW 를 만들지 않는다 (D33).** `kb_chunks_hnsw` 는 *행이 적어서* 미룬 것이고,
`kb_events_hnsw` 는 **채울 값이 없어서**다 — v1 은 이벤트를 임베딩하지 않는다 (D34).
이유가 다르므로 다르게 적는다. 빈 컬럼에 인덱스가 있으면 벡터 갈래가 있다는 증거로 읽힌다.

`kb_query_logs_project_time` 은 `005` 가 만든다 (D51). `kb_status` 가 부를 때마다
`project` 로 좁혀 `hit_count = 0` 을 세는데 이 표에는 PK 말고 인덱스가 없었다.

## 검색

문서: 벡터 유사도 + `tsv` 키워드를 **RRF(`k=60`)로 합친다.** 정의는 D33 이 소유한다.  
이벤트: 필터(project, kind, module, 기간)를 먼저 걸고, 남은 집합에 **키워드만** 건다 —
v1 은 이벤트를 임베딩하지 않는다 (D34).

식별자·에러코드·날짜·건수는 벡터만으로 풀지 않는다.

## 삭제·갱신

- 문서 재색인: `(project, repo, path)` 단위로 청크 삭제 후 insert.
- 이벤트: v1은 삭제보다 `payload`/`summary` 수정. 삭제가 필요하면 물리 삭제 대신 추후 `deleted_at`을 검토.
- Git이 원본이므로 문서 인덱스는 언제든 지우고 다시 만들 수 있다. 이벤트는 Git에 없는 원장이므로 백업 대상이다.
- `kb_query_logs` 는 v1 에서 지우지 않고 **백업 대상도 아니다** (D51). 지식이 아니라 v1 성공 조건의 측정이다.
- 무엇을 어떻게 뜨는지는 [operations.md](operations.md)가 소유한다 (D54).
