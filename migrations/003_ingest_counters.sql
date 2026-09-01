-- 003: ingest 카운터 (D30)
--
-- DDL 정본은 docs/data-model.md 다. 이 파일은 그 SQL 을 실행할 뿐 두 번째 스키마 정의가 아니다.
--
-- 002 를 고치지 않고 새 파일을 만드는 이유: D17 러너는 적용 이력을 두지 않고 매 기동마다
-- 모든 .sql 을 다시 실행한다. 멱등의 유일한 출처가 IF NOT EXISTS 이므로, 이미 테이블이 있는
-- DB 에서는 002 의 CREATE TABLE 을 고쳐도 조용히 무시된다.
--
-- files_deleted 를 files_changed 에 접지 않는 이유는 D30 §4 다 — 삭제가 가장 파괴적인 동작인데
-- 다른 수에 섞이면 원장에서 사라진다.

ALTER TABLE kb_ingest_runs ADD COLUMN IF NOT EXISTS files_deleted int;
