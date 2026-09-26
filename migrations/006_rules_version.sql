-- 006: 유도 규칙의 판 (D71)
--
-- DDL 정본은 docs/data-model.md 다. 이 파일은 그 SQL 을 실행할 뿐 두 번째 스키마 정의가 아니다.
--
-- ingest 는 해시가 같아도 이 판이 `RULES_VERSION` 보다 낮으면 메타와 청크를 다시 만든다.
-- 청크·heading_path·메타를 만드는 규칙이 바뀌어도 본문이 같으면 해시가 같아 낡은 청크가 영영 남았다
-- (2026-09-26 감사 F099 — `event_stats` 가 `eventstats` 였다). 기본값 0 이 옛 행을 한 번 다시 만들게 한다.
--
-- **UPDATE 를 두지 않는다.** D17 러너는 적용 이력 없이 매 기동 모든 .sql 을 다시 돌린다 —
-- 판을 되돌리는 문장이 있으면 `serve` 마다 전량 재색인이 된다. tests/test_migrations.py 가 이 한 문장을 잠근다.

ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS rules_version int NOT NULL DEFAULT 0;
