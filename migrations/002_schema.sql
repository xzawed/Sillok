-- 002 스키마 (D17)
--
-- DDL 정본은 docs/data-model.md 다. 이 파일은 그 SQL 을 실행할 뿐
-- 두 번째 스키마 정의가 아니다. 컬럼을 바꾸려면 data-model.md 를 먼저 고친다.
--
-- 재기동이 안전해야 하므로 전부 IF NOT EXISTS 다 (D17).
--
-- HNSW 인덱스는 여기 없다. data-model.md 와 plan.md §6 이
-- "행이 적을 때 이득이 없다. v1 에서 나중에 만들어도 된다" 로 명시적으로 허용한다.
-- 만들 때는 003 으로 붙인다.

-- 문서 헤더 — Git 현재 문서의 인덱스. 원문은 Git.
CREATE TABLE IF NOT EXISTS kb_documents (
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

-- 청크
CREATE TABLE IF NOT EXISTS kb_chunks (
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

-- 이벤트 원장 — Git 에 원본이 없는 유일한 데이터. 백업 대상.
CREATE TABLE IF NOT EXISTS kb_events (
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
  embedding         vector(1536),  -- text-embedding-3-small, summary 만
  created_at        timestamptz NOT NULL DEFAULT now(),
  created_by        text
);

CREATE INDEX IF NOT EXISTS kb_events_project_time ON kb_events (project, occurred_at DESC);
CREATE INDEX IF NOT EXISTS kb_events_filter ON kb_events (project, kind, result, module);

-- 운영
CREATE TABLE IF NOT EXISTS kb_ingest_runs (
  id               bigserial PRIMARY KEY,
  project          text NOT NULL,
  started_at       timestamptz NOT NULL DEFAULT now(),
  finished_at      timestamptz,
  commit_sha       text,
  files_seen       int,
  files_changed    int,
  chunks_upserted  int,
  status           text NOT NULL DEFAULT 'running',
  -- running | ok | partial | failed  (D32)
  error            text
);

CREATE TABLE IF NOT EXISTS kb_query_logs (
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

-- 인덱스 (HNSW 제외 — 위 주석 참조)
CREATE INDEX IF NOT EXISTS kb_chunks_tsv ON kb_chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS kb_docs_lookup ON kb_documents (project, doc_type, status, module);
