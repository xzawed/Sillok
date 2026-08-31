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

권장 청크: 헤딩 우선, 본문 800~1200자, overlap 120~200자.  
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
  embedding         vector(1536),  -- text-embedding-3-small, summary만
  created_at        timestamptz NOT NULL DEFAULT now(),
  created_by        text
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
  chunks_upserted  int,
  status           text NOT NULL DEFAULT 'running',
  error            text
);

CREATE TABLE kb_query_logs (
  id          bigserial PRIMARY KEY,
  created_at  timestamptz NOT NULL DEFAULT now(),
  project     text,
  client      text,
  tool        text NOT NULL,
  query       text,
  filters     jsonb,
  hit_paths   text[],
  hit_count   int,
  latency_ms  int
);
```

## 인덱스

```sql
CREATE INDEX kb_chunks_hnsw
  ON kb_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX kb_chunks_tsv ON kb_chunks USING gin (tsv);
CREATE INDEX kb_docs_lookup ON kb_documents (project, doc_type, status, module);

CREATE INDEX kb_events_hnsw
  ON kb_events USING hnsw (embedding vector_cosine_ops);
```

HNSW는 행이 적을 때 이득이 없다. v1에서 나중에 만들어도 된다.

## 검색

문서: 벡터 유사도 + `tsv` 키워드. 가능하면 RRF로 합친다.  
이벤트: 필터(project, kind, module, 기간)를 먼저 걸고, 남은 집합에 벡터/키워드.

식별자·에러코드·날짜·건수는 벡터만으로 풀지 않는다.

## 삭제·갱신

- 문서 재색인: `(project, repo, path)` 단위로 청크 삭제 후 insert.
- 이벤트: v1은 삭제보다 `payload`/`summary` 수정. 삭제가 필요하면 물리 삭제 대신 추후 `deleted_at`을 검토.
- Git이 원본이므로 문서 인덱스는 언제든 지우고 다시 만들 수 있다. 이벤트는 Git에 없는 원장이므로 백업 대상이다.
