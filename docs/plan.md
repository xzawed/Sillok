---
title: Sillok 구현 계약
doc_type: other
status: current
module: null
---

# Sillok — 구현 계약

상위: [README](../README.md) · 협업 규칙: [AGENTS.md](../AGENTS.md)

이 파일이 **구현 에이전트가 먼저 읽는 문서**다. 사람용 기획서가 아니라 계약이다.

## 우선순위

```text
docs/plan.md = adr/0001-v1-stack-decisions.md   (이 둘이 이긴다)
        >  spec.md, data-model.md, service-and-mcp.md, conventions.md, skills/**
```

**충돌 판정은 두 단계다.**

1. **사실 소유권이 먼저다.** [conventions.md](conventions.md)의 문서 지도에서 그 사실을 정본으로 소유한 파일이 이긴다.
2. **소유자가 지도에 없으면** 위 서열로 판정하고 — 이 파일과 [adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md)가 이긴다 — 판정 후 **그 사실의 소유자를 문서 지도에 추가한다.**

서열만으로 판정하면 문서가 늘 때마다 서열을 다시 협상해야 한다.
계약을 바꾸려면 이 파일과 ADR을 먼저 고치고 나서 하위 문서와 구현을 맞춘다.

| 하위 문서 | 소유 |
|---|---|
| [conventions.md](conventions.md) | 문서 지도, 충돌 판정, 정본 표기, 자기 색인, 문서 게이트 |
| [spec.md](spec.md) | 문제, 목표, 비목표, 세 층 |
| [data-model.md](data-model.md) | 테이블, 인덱스, DDL, 컬럼 enum |
| [service-and-mcp.md](service-and-mcp.md) | HTTP·MCP 입출력 계약 |
| [skills/sillok-storage/SKILL.md](skills/sillok-storage/SKILL.md) | 저장 위치 분류 규칙 |
| [open-questions.md](open-questions.md) | 아직 답이 없는 것 |

---

## 0. 한 줄

Git에는 현재 진실만. Postgres에는 사건 원장과 문서 인덱스만.
AI는 MCP로 행 몇 개만 읽고 쓴다. 문서를 대화에 통째로 넣지 않는다.

이름: **Sillok**. SCAManager는 범위 밖.

## 1. 푸는 문제

프로젝트 md에 규칙과 성공/실패 이력이 같이 쌓이면:

- 위키가 로그가 된다
- 모델이 큰 파일을 읽어 토큰을 쓰고 틀린다
- 건수·재발을 글에서 집계할 수 없다

만들지 않는 것: 범용 RAG SaaS, 전사 검색, 공개 라이브러리 문서 MCP, 지식그래프.

## 2. 확정 스택 (뒤집지 말 것)

> 정본: [adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md) — 값이 다르면 정본이 이긴다.

| 항목 | 값 |
|---|---|
| 구현 언어 | Python, FastAPI, MCP Python SDK |
| DB | PostgreSQL 16+, 확장 `vector`(pgvector) · `pg_trgm` |
| 임베딩 | `text-embedding-3-small`, `vector(1536)`. 키 없으면 embedding NULL, `tsv`만 |
| Git 쓰기 | `save_doc`는 제안 본문만. 커밋 없음 |
| 원문 | workspace 경로에서 `get_file` |
| 프로젝트 | `project` 문자열 필수 |
| MCP | stdio + Streamable HTTP, 같은 앱 |
| 인증 | 로컬 없음. 외부 HTTP면 Bearer |
| 색인 | CLI `sillok ingest` |
| 색인 경로 | `docs/**`, 루트 `README*`, `adr/**` |
| 이벤트 | 필수 필드 없으면 거절 |
| 승격 | `repeat_causes` 통계와 제안까지만 |
| 사람 UI | `GET /v1/status` 등 JSON. **웹 페이지 없음** |
| 배포 | Docker Compose (db + api 2개). 테스트용 `test`는 `profiles` 게이트라 기본 `up`에 없다 (D22) |
| 본문 언어 | 한·영 혼용, tsvector `simple` |
| 공개 | 공개 저장소 (D26). `개인 도구`라는 성격은 그대로다 |
| 런타임 | CPython 3.12, uv, pytest (D18) |
| 환경변수 | `DATABASE_URL` 하나 + `SILLOK_*` 4개 + `OPENAI_API_KEY` (D16) → [.env.example](../.env.example) |
| 마이그레이션 | 버전 붙인 raw `.sql`, `serve` 기동 시 bind 전에 멱등 적용 (D17) |
| ingest 경로 | CLI가 Service 함수를 인프로세스 호출. **CLI는 자기 SQL을 갖지 않는다** (D19) |

## 3. 세 층

```text
Postgres          kb_documents, kb_chunks, kb_events, ingest/query logs
Knowledge Service FastAPI. DB의 유일한 문 — 단위는 함수지 HTTP가 아니다 (D19)
출구              MCP 도구 + Skill + JSON 현황
```

상세: [spec.md](spec.md). n8n은 v1에서 안 만든다. Plugin도 안 만든다.

## 4. 저장 규칙 (모델이 매 저장에 적용)

전문: [skills/sillok-storage/SKILL.md](skills/sillok-storage/SKILL.md).

- 내일 구현이 달라지는 현재 규칙 → Git 후보 → `save_doc` (제안)
- 날짜·시도·성공실패가 핵심 → `save_event`
- 한 글에 둘 다 있으면 결론만 제안, 과정은 이벤트
- 레포에 md를 임의 append 하지 않음

이벤트 필수: `project`, `kind`, `title`, `summary`, `occurred_at`, `result`
`kind`: success | failure | incident | decision
`result`: success | failure | partial | unknown
`summary` 2000자 초과 거절

## 5. 구현해야 하는 표면

도구 이름 고정. 바꾸지 않음. 입출력 계약은 [service-and-mcp.md](service-and-mcp.md).

| MCP | HTTP |
|---|---|
| `search_docs` | `POST /v1/search/docs` |
| `search_events` | `POST /v1/search/events` |
| `get_event` | `GET /v1/events/{id}` |
| `get_file` | `GET /v1/files` |
| `save_event` | `POST /v1/events` |
| `save_doc` | `POST /v1/docs/proposals` |
| `event_stats` | `GET /v1/stats/events` |
| `kb_status` | `GET /v1/status` |

MCP에 노출하지 않는 HTTP: `GET /v1/docs`, `POST /v1/ingest`.

추가로 CLI: `sillok ingest`, `sillok serve`. 인자 계약은 D19 — 색인 경로는 플래그가 아니라 항상 D9다.
`POST /v1/ingest`는 삭제 대상이 아니라 같은 함수의 HTTP 얼굴이다 (D20). 운영자 진입점은 CLI.
마이그레이션 러너 `sillok migrate`는 D17이 정한 별도 명령이고 D8이 정한 CLI 두 개에 포함되지 않는다.

금지: 임의 SQL 도구, 전체 덤프, 기본 `top_k` > 8 (최대 12), 통계에 벡터.

빈 검색은 `{ "results": [] }`. 모델이 채울 문장을 API가 넣지 않음.
Service 기본 `http://127.0.0.1:8080`.

## 6. 데이터 (요약)

테이블: `kb_documents`, `kb_chunks`, `kb_events`, `kb_ingest_runs`, `kb_query_logs`.
DDL은 [data-model.md](data-model.md)를 그대로 쓴다. 단 **v1 은 HNSW 를 만들지 않는다 (D33)** —
행이 적어 이득이 없고,  쪽은 채울 값이 아예 없다 (D34).

- 문서 원본은 Git. DB는 해시·청크 인덱스
- 이벤트는 Git에 없는 원장. **백업 대상**
- 재색인: `(project, repo, path)` 단위로 청크 삭제 후 insert
- 검색: 벡터 + tsv. 식별자·날짜·건수는 필터/SQL
- 이벤트 임베딩은 `summary`만 — 다만 **v1 은 이벤트를 임베딩하지 않는다** (D34)

## 7. 작업 순서 (이 순서를 어기지 말 것)

A절(Q1–Q5)은 **D16–D20**, Q11은 **D21**, Q26은 **D22**, Q16·Q18·Q21은 **D23–D25**로 마감됐다 (2026-08-31).
1–4단계를 그때 검증할 수 있게 됐다.
**B절의 Q6·Q7·Q10은 D30–D32로, Q8·Q9는 D33–D34로 마감됐다** (2026-09-01) —
5·6단계 계약이 생겼다.
**C절의 Q12·Q15와 D절의 Q19·Q20은 D35–D38로 마감됐다** (2026-09-02) —
7단계 계약이 생겼고, **Q17이 D42–D46으로 닫히면서 1–10단계를 이제 검증할 수 있다** (2026-09-02).
검증할 수 있다는 것은 **계약이 다 있다**는 뜻이지 구현이 다 됐다는 뜻이 아니다 — 진행 상태는 §9가 소유한다.
**H절의 Q32는 D48–D52로 마감됐다** (2026-09-03) — 9단계 계약이 생겼다.
다섯 결정이 `kb_query_logs` 를 이 자리로 미뤄 두고 있었다.
남은 공백은 단계별로 걸린다 — **4단계 전에 Q16·Q18·Q21**, 5단계 전에 Q6·Q7·Q10,
6단계 전에 Q8·Q9, 7단계 전에 Q12·Q15·Q19·Q20, 8단계 전에 Q17, 9단계 전에 Q32가 필요하다.
[open-questions.md](open-questions.md)를 참조하고, 답이 없는 항목을 추측으로 채우지 않는다.

> **위 문장은 `scripts/check-layout.mjs`가 읽어 강제한다.** Q가 다 풀려도 절을 지우지 않는다 —
> 해결 표시는 [open-questions.md](open-questions.md)가 하고, 여기서 절이 사라지면 그 단계가 무방비가 된다.
> 절이 없으면 검사가 실패한다.

1. Compose: Postgres + pgvector. `5432`는 호스트에 게시하지 않는다 (D16)
2. 마이그레이션 — `001` 확장 → `002` 스키마, 전부 멱등 ([data-model.md](data-model.md) DDL, D17)
3. FastAPI 골격, 공통 `{ok, data|error}`. 상태 매핑과 기본 응답 덮기는 D21.
   `serve`는 bind 전에 마이그레이션을 돌린다 (D17). 업무 라우트는 아직 붙이지 않는다
4. `save_event` / `event_stats` / `kb_status` (임베딩 없이도 동작)
5. ingest: 경로 스캔, 해시, 청크, tsv. 키 있으면 임베딩
6. `search_docs` / `search_events` (키 없으면 키워드만)
7. `get_file` (workspace), `get_event`, `save_doc` 제안
8. MCP 도구를 같은 함수에 연결 (stdio + HTTP)
9. `kb_query_logs` 기록
10. 스모크: 필드 없는 이벤트 거절, ingest 후 검색, stats

웹 UI, n8n, GitHub App, 자동 승격은 이 목록 밖이다.

## 8. 협업

규칙 전문: [AGENTS.md](../AGENTS.md).

- 코드가 이 문서와 다르면 코드가 틀린다
- 계약을 바꾸려면 이 파일과 [adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md)를 먼저 고친다
- 비밀키를 레포에 넣지 않는다. `OPENAI_API_KEY`는 env

## 9. v1 완료 조건

- [x] Compose로 DB가 뜬다 — 2026-08-31 실측. `pgvector/pgvector:pg16` healthy,
      `001`·`002` 적용 후 확장 `vector 0.8.2`·`pg_trgm 1.6`, 테이블 5개,
      `kb_chunks.embedding`·`kb_events.embedding` 모두 `vector(1536)`
- [x] 필수 필드 없는 `save_event`가 `VALIDATION`으로 거절된다 — 2026-08-31 실측.
      `POST /v1/events {}` → 422 `{"code":"VALIDATION","message":"missing required field: project, kind, …"}`.
      오프셋 없는 `occurred_at`도 같은 코드로 거절된다 (D25)
- [x] ingest가 `docs/**`, 루트 `README*`, `adr/**`만 먹는다 — 2026-09-01 실측.
      이 저장소를 대상으로 돌아 게이트의 색인 목록과 **같은 파일을 먹었고**,
      두 번째 run 은 아무것도 바꾸지 않았다(해시가 유일한 변경 판정이다).
      대조는 `scripts/check-index-parity.mjs` 가 매번 한다 — 파일 수를 여기 적지 않는다. 문서가 자라면 낡는다
- [x] `search_docs`, `search_events`, `event_stats`가 한 project에서 돈다 — 2026-09-01 실측.
      키가 없어 벡터 팔은 비어 있고 그것이 D2 의 정상 상태다. RRF 는 한 목록 위에서
      그 순위의 단조 재표기이므로 순서는 키워드 순서와 같다
- [x] `get_file`이 workspace의 해당 path를 돌려준다 — 2026-09-02 실측.
      살아 있는 Service 에 대고 `docs/plan.md`를 열었고 응답은 파일이 아니라 4000자 창이었다.
      창을 이어 붙이면 파일 전체이고, 색인 밖(`docker-compose.yml`·`.env`)과 `./`가 붙은 경로는 404다 —
      **색인이 곧 허용 목록이다** (D36)
- [x] `save_doc`이 Git을 변경하지 않는다 — 2026-09-02 실측.
      CRLF로 저장된 `docs/spec.md`에 LF 본문을 제안하니 `diff`가 빈 문자열이었고(D41),
      `base_hash` 불일치는 409, 접두사 없는 해시는 422였다. 응답이 전부이고 파일은 그대로다
- [x] MCP 도구 8개가 Service와 동일 동작 — 2026-09-03 실측.
      같은 인자로 두 얼굴을 태워 **봉투를 글자까지 대조**하는 검사가 판정한다 (D46).
      성공과 `VALIDATION`·`NOT_FOUND`·`CONFLICT`·`INTERNAL` 을 덮는다.
      `POST /mcp` 는 살아 있는 스택에서도 도구 여덟을 돌려주었다
- [ ] 검색 0건이 `kb_query_logs`에 `hit_count=0`으로 남는다

이 저장소 자신이 색인 경로 규칙을 따르므로, **첫 ingest 스모크는 이 레포를 대상으로 돌린다.**

**v1이 끝났을 때** 판정에 쓰는 명령 (D18):

```bash
node scripts/check-layout.mjs
docker compose up -d --wait
docker compose exec api sillok ingest --project sillok
curl -sf "http://127.0.0.1:8080/v1/status?project=sillok"
uv run pytest -q
```

> **3번째 줄의 `exec api` 는 2026-09-02 에 확인했다.** 처음 돌렸을 때는 `sillok` 이 PATH 에 없어
> `executable file not found` 로 죽었다 — `Dockerfile` 의 runtime 스테이지가 `/app/.venv/bin` 을
> PATH 에 넣도록 고쳤고, 지금은 그 형태로 돈다. 5단계 검증은 `--profile test` 안에서 같은 Service 함수를 불러 했다.
> `/v1/status`는 4단계에서 생겼으므로 4번째 줄은 돈다.
> 5번째 줄은 호스트에서 DB 검사가 skip된 채로 돈다 — 전부 돌리려면 D22의 `--profile test`다.
> 이 블록은 **v1 목표**이지 현재 상태가 아니다.

`sillok ingest`는 `serve`가 떠 있지 않아도 도는 것이 D19의 요점이다.
위 명령이 `exec api`를 쓰는 것은 Compose 안에서 워크스페이스와 DSN이 이미 맞춰져 있기 때문이지, HTTP를 타서가 아니다.

## 10. 하지 말 것 (반복)

- 이벤트 본문을 `docs/`에 append
- Collections/외부 RAG로 DB를 대체
- 채팅 모델에게 임베딩을 숫자로 적어 달라고 하기
- 임베딩 모델 변경을 스키마 변경 없이 하기
- "관련 문서 전부" 반환
