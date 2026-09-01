-- 004: 이벤트 키워드 검색 (D34)
--
-- DDL 정본은 docs/data-model.md 다. 이 파일은 그 SQL 을 실행할 뿐 두 번째 스키마 정의가 아니다.
--
-- 002 를 고치지 않는 이유는 003 과 같다: D17 러너는 적용 이력을 두지 않고 매 기동마다 모든 .sql 을
-- 다시 실행한다. 멱등의 유일한 출처가 IF NOT EXISTS 이므로, 이미 테이블이 있는 DB 에서는
-- 002 의 CREATE TABLE 을 고쳐도 조용히 무시된다.
--
-- 그 결과 003 과 마찬가지로 **정본 DDL 의 컬럼 순서와 실제 DB 의 컬럼 순서가 갈라진다.**
-- 코드가 컬럼 이름으로 읽으므로 동작에는 영향이 없다. 대조하다 발견하는 사람을 위해 적어 둔다.
--
-- 네 필드를 전부 coalesce 로 감싼다 (D34 §2). 하나라도 빼면 그 컬럼이 NULL 인 행의 tsv 가
-- 통째로 NULL 이 되어 **어떤 질의에도 걸리지 않는다** — 오류 없이 행 하나가 검색에서 사라진다.
--
-- 생성 컬럼이라 ALTER 가 기존 행을 전부 채운다. 백필 코드가 없는 이유다.
-- 비용은 테이블 재작성이고 잠금은 AccessExclusiveLock 이다. IF NOT EXISTS 라서 DB 당 한 번이다.
--
-- CREATE INDEX CONCURRENTLY 를 쓸 수 없다 — 러너는 파일 하나를 트랜잭션 하나로 돌린다 (D32).

ALTER TABLE kb_events ADD COLUMN IF NOT EXISTS tsv tsvector
  GENERATED ALWAYS AS (
    to_tsvector('simple',
      coalesce(title, '')      || ' ' || coalesce(summary, '')    || ' ' ||
      coalesce(root_cause, '') || ' ' || coalesce(resolution, ''))
  ) STORED;

CREATE INDEX IF NOT EXISTS kb_events_tsv ON kb_events USING gin (tsv);
