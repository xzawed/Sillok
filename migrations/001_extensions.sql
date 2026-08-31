-- 001 확장 (D17)
--
-- 테이블보다 먼저 실행한다. vector 없이 vector(1536) 컬럼을 만들 수 없다.
-- 정본: docs/data-model.md §확장.
--
-- 이미지에 확장 파일이 들어 있어도(pgvector/pgvector:pg16) DB 마다 따로 필요하다.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
