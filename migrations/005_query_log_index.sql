-- 005: 질의 원장의 조회 인덱스 (D51)
--
-- DDL 정본은 docs/data-model.md 다. 이 파일은 그 SQL 을 실행할 뿐 두 번째 스키마 정의가 아니다.
--
-- `kb_status` 는 부를 때마다 `project` 로 좁혀 `hit_count = 0` 을 센다 (D31 응답의 zero_hit_queries).
-- 9단계가 이 표에 쓰기 시작하므로 그 집계가 처음으로 자란다 — 그런데 이 표에는 PK 말고 인덱스가 없었다.
--
-- 002 를 고치지 않는 이유는 003·004 와 같다: D17 러너는 적용 이력을 두지 않고 매 기동마다
-- 모든 .sql 을 다시 실행한다. 멱등의 유일한 출처가 IF NOT EXISTS 다.
--
-- `created_at DESC` 를 함께 넣는 것은 보존 규칙이 생기는 날(D51 이 닫지 않은 자리)
-- 기간으로 지우는 질의가 같은 인덱스를 타게 하려는 것이다. 오늘의 집계는 project 만으로 충분하다.

CREATE INDEX IF NOT EXISTS kb_query_logs_project_time
  ON kb_query_logs (project, created_at DESC);
