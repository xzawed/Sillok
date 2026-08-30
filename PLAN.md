# Sillok — Claude / Grok 공동 구현 기준

이 파일이 **양쪽 에이전트가 먼저 읽는 문서**다.  
사람용 기획서가 아니다. 구현 계약이다.

상세 스키마는 `03-DATA-MODEL.md`, 도구 입출력은 `04-SERVICE-AND-MCP.md`, 분류 규칙은 `02-STORAGE-RULES.md`.  
이 파일과 충돌하면 이 파일과 `05-OPEN-DECISIONS.md`를 이긴다.

읽은 뒤 구현을 시작하면 `AGENTS.md`를 따른다.

---

## 0. 한 줄

Git에는 현재 진실만. Postgres에는 사건 원장과 문서 인덱스만.  
AI는 MCP로 행 몇 개만 읽고 쓴다. 문서를 대화에 통째로 넣지 않는다.

이름: **Sillok**. SCAManager는 범위 밖.

---

## 1. 푸는 문제

프로젝트 md에 규칙과 성공/실패 이력이 같이 쌓이면:

- 위키가 로그가 된다
- 모델이 큰 파일을 읽어 토큰을 쓰고 틀린다
- 건수·재발을 글에서 집계할 수 없다

만들지 않는 것: 범용 RAG SaaS, 전사 검색, 공개 라이브러리 문서 MCP, 지식그래프.

---

## 2. 확정 스택 (뒤집지 말 것)

날짜: 2026-08-30

| 항목 | 값 |
|---|---|
| 언어 | Python, FastAPI, MCP Python SDK |
| DB | PostgreSQL 16+, pgvector, `vector(1536)` |
| 임베딩 | `text-embedding-3-small`. 키 없으면 embedding NULL, `tsv`만 |
| Git 쓰기 | `save_doc`는 제안 본문만. 커밋 없음 |
| 원문 | workspace 경로에서 `get_file` |
| 프로젝트 | `project` 문자열 필수 |
| MCP | stdio + Streamable HTTP, 같은 앱 |
| 인증 | 로컬 없음. 외부 HTTP면 Bearer |
| 색인 | CLI `sillok ingest` |
| 색인 경로 | `docs/**`, 루트 `README*`, `adr/**` |
| 이벤트 | 필수 필드 없으면 거절 |
| 승격 | `repeat_causes` 통계만 |
| 사람 UI | `GET /v1/status` 등 JSON. 웹 페이지 없음 |
| 배포 | Docker Compose (db + api) |
| 언어 | 한·영 혼용, tsvector `simple` |
| 공개 | 비공개 |

---

## 3. 세 층

```text
Postgres          kb_documents, kb_chunks, kb_events, ingest/query logs
Knowledge Service FastAPI. DB의 유일한 문
출구              MCP 도구 + Skill(02) + JSON 현황
```

n8n은 v1에서 안 만든다. Plugin도 안 만든다.

---

## 4. 저장 규칙 (모델이 매 저장에 적용)

전문: `02-STORAGE-RULES.md`.

- 내일 구현이 달라지는 현재 규칙 → Git 후보 → `save_doc` (제안)
- 날짜·시도·성공실패가 핵심 → `save_event`
- 한 글에 둘 다 있으면 결론만 제안, 과정은 이벤트
- 레포에 md를 임의 append 하지 않음

이벤트 필수: `project`, `kind`, `title`, `summary`, `occurred_at`, `result`  
`kind`: success | failure | incident | decision  
`result`: success | failure | partial | unknown  
`summary` 2000자 초과 거절

---

## 5. 구현해야 하는 표면

도구 이름 고정. 바꾸지 않음.

| MCP | HTTP |
|---|---|
| search_docs | POST /v1/search/docs |
| search_events | POST /v1/search/events |
| get_event | GET /v1/events/{id} |
| get_file | GET /v1/files |
| save_event | POST /v1/events |
| save_doc | POST /v1/docs/proposals |
| event_stats | GET /v1/stats/events |
| kb_status | GET /v1/status |

추가로 CLI: `sillok ingest`, `sillok serve` (또는 FastAPI + MCP 엔트리).

금지: 임의 SQL 도구, 전체 덤프, 기본 top_k > 8, 통계에 벡터.

빈 검색은 `{ "results": [] }`. 모델이 채울 문장을 API가 넣지 않음.

Service 기본 `http://127.0.0.1:8080`.

계약 JSON은 `04-SERVICE-AND-MCP.md`.

---

## 6. 데이터 (요약)

테이블: `kb_documents`, `kb_chunks`, `kb_events`, `kb_ingest_runs`, `kb_query_logs`.  
DDL은 `03-DATA-MODEL.md`를 그대로 쓴다.

- 문서 원본은 Git. DB는 해시·청크 인덱스
- 이벤트는 Git에 없는 원장. 백업 대상
- 재색인: (project, repo, path) 단위로 청크 삭제 후 insert
- 검색: 벡터 + tsv. 식별자·날짜·건수는 필터/SQL
- 이벤트 임베딩은 summary만

---

## 7. 작업 순서 (이 순서를 어기지 말 것)

1. Compose: Postgres + pgvector
2. 마이그레이션 (03 DDL)
3. FastAPI 골격, 공통 `{ok, data|error}`
4. `save_event` / `event_stats` / `kb_status` (임베딩 없이도 동작)
5. ingest: 경로 스캔, 해시, 청크, tsv. 키 있으면 임베딩
6. `search_docs` / `search_events` (키 없으면 키워드만)
7. `get_file` (workspace), `get_event`, `save_doc` 제안
8. MCP 도구를 같은 함수에 연결 (stdio + HTTP)
9. query_log 기록
10. 스모크: 필드 없는 이벤트 거절, ingest 후 검색, stats

웹 UI, n8n, GitHub App, 자동 승격은 이 목록 밖이다.

---

## 8. 협업

- Grok: 명세 준수 여부, 스키마/계약, 리뷰
- Claude: 구현·테스트
- 코드가 이 문서와 다르면 코드가 틀린다
- 계약을 바꾸려면 `PLAN.md`와 `05-OPEN-DECISIONS.md`를 먼저 고친다
- 비밀키를 레포에 넣지 않는다. `OPENAI_API_KEY`는 env

---

## 9. v1 완료 조건

- [ ] Compose로 DB가 뜬다
- [ ] 필수 필드 없는 `save_event`가 422/VALIDATION
- [ ] ingest가 docs/README/adr만 먹는다
- [ ] search_docs, search_events, event_stats가 한 project에서 돈다
- [ ] get_file이 workspace의 해당 path를 돌려준다
- [ ] save_doc이 Git을 변경하지 않는다
- [ ] MCP 도구 8개가 Service와 동일 동작
- [ ] 검색 0건이 kb_query_logs에 남는다

---

## 10. 하지 말 것 (반복)

- 이벤트 본문을 `docs/`에 append
- Collections/외부 RAG로 DB를 대체
- 채팅 모델에게 임베딩을 숫자로 적어 달라고 하기
- 임베딩 모델 변경을 스키마 변경 없이 하기
- “관련 문서 전부” 반환
