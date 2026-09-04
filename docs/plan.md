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
| [operations.md](operations.md) | 백업·복구·재기동 절차 (D54) |
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

MCP에 노출하지 않는 HTTP: `POST /v1/ingest` 하나다 (D64 가 `GET /v1/docs` 를 뺐다).

추가로 CLI: `sillok ingest`, `sillok serve`. 인자 계약은 D19 — 색인 경로는 플래그가 아니라 항상 D9다.
`POST /v1/ingest`는 삭제 대상이 아니라 같은 함수의 HTTP 얼굴이다 (D20). 운영자 진입점은 CLI.
마이그레이션 러너 `sillok migrate`는 D17이 정한 별도 명령이고 D8이 정한 CLI 두 개에 포함되지 않는다.
stdio 표면 `sillok mcp` 도 마찬가지다 — D45가 정한 별도 명령이고 그 둘에 들어가지 않는다.

금지: 임의 SQL 도구, 전체 덤프, 기본 `top_k` > 8 (최대 12), 통계에 벡터.

빈 검색은 `{ "results": [] }`. 모델이 채울 문장을 API가 넣지 않음.
Service 기본 `http://127.0.0.1:8080`.

## 6. 데이터 (요약)

테이블: `kb_documents`, `kb_chunks`, `kb_events`, `kb_ingest_runs`, `kb_query_logs`.
DDL은 [data-model.md](data-model.md)를 그대로 쓴다. 단 **v1 은 HNSW 를 만들지 않는다 (D33)** —
행이 적어 이득이 없고,  쪽은 채울 값이 아예 없다 (D34).

- 문서 원본은 Git. DB는 해시·청크 인덱스
- 이벤트는 Git에 없는 원장. **백업 대상** — 절차는 [operations.md](operations.md)가 소유한다 (D54)
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
검증할 수 있다는 것은 **계약이 다 있다**는 뜻이다. 진행 상태는 §9가 소유하고,
**2026-09-03 현재 열 단계가 다 구현됐다.**
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
      그 순위의 단조 재표기이므로 순서는 키워드 순서와 같다.
      **2026-09-04 에 키를 넣고 같은 자리를 다시 쟀다** — 위 문장은 키가 없을 때의 것이고
      여전히 참이다. 두 팔이 다 찬 상태는 아래 `키가 있는 상태` 절이 적는다
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
- [x] 검색 0건이 `kb_query_logs`에 `hit_count=0`으로 남는다 — 2026-09-03 실측.
      살아 있는 8080 에 0건 확정 질의를 던지니 `{"results": []}` 였고 `zero_hit_queries` 가 0 에서 1 이 됐다.
      행은 `hit_count=0` · `hit_paths={}` · `filters={}` 였다. 히트 있는 질의에서는
      `hit_paths` 에 `README.md` 가 **두 번** 들어온다 — 문서당 상한이 2이고 중복을 접지 않기 때문이다 (D49).
      MCP 얼굴로 같은 인자를 보내면 `client` 만 `mcp` 로 다르고 `filters`·`hit_count` 는 같다

이 저장소 자신이 색인 경로 규칙을 따르므로, **첫 ingest 스모크는 이 레포를 대상으로 돌린다.**

### 키가 있는 상태 (2026-09-04 실측)

위 여덟 항목은 **키 없이** 통과한 것이고 그것이 D2 의 정상 상태다. 이 절은 그것을 뒤집지 않는다 —
`OPENAI_API_KEY` 를 넣고 **한 번 돌려** D31·D33 이 `사람이 한 번 돌려 확인한다` 로 남겨 둔 자리를 채운 기록이다.
커밋된 구성은 그대로다: `--profile test` 는 여전히 키를 갖지 않는다 (D33).

**점수는 run 번호에 매달아 적는다.** 이 파일 자신이 색인 대상이라 여기에 한 줄을 쓰면 그 문서의 청크가
다시 만들어지고 **벡터 순위가 움직인다.** 실제로 그렇게 됐다 — 아래 `run 11552` 의 값은 이 절을 쓴 뒤
`run 11686` 에서 달라졌다. 그러니 여기 있는 수는 현재값이 아니라 **그 run 에서 본 값**이다.
(그 흔들림 자체가 아래 네 번째 항목의 근거다.)

- **백필이 돈다 (D31).** `run 11552`: `본 11 · 바뀐 0 · 청크 0 · 임베딩 320 · 남은 벡터 0`.
  **`바뀐 0 · 청크 0` 인데 채워졌다** — 백필은 무엇이 바뀌었는지와 무관하게 그 project 전체를 본다는
  D31 의 요점이 그대로다. **`kb_documents` 를 건드리지 않았다**: 그 run 의 창 안에 `indexed_at` 이
  갱신된 행이 하나도 없다. 차원은 전 청크가 `1536` 이다.
  **이 절을 쓰면서 문서 둘이 바뀌어 경로가 한 번 더 확인됐다** — `run 11686`:
  `바뀐 2 · 청크 209 · 임베딩 209 · 남은 벡터 0`.
  새로 넣은 청크는 그 순간 `embedding IS NULL` 이고 **같은 패스가 그대로 집는다** (D31)
- **두 팔이 다 찬 RRF 가 처음 돌았다 (D33).** 최상위 점수가 `1/(60+1)` 하나로 고정되던 것이 끝났다.
  질의 `Sillok` 의 여덟 행이 **전부** `1/(60+a) + 1/(60+b)` 로 분해된다 — 병합 공식이 문서 그대로다.
  이 분해가 성립한다는 것은 run 이 바뀌어도 참이고, `a`·`b` 값만 움직인다
- **`RRF_K = 60` 이 이 색인에서 하는 일.** 점수를 납작하게 만든다 — `run 11552` 에서 1위와 8위의 비가
  `1.142` 였다 (`k=0` 이면 `6.2`). 그리고 **순서가 `k≈60` 에서 수렴한다**: `k` 를 60·200·1000 으로
  바꿔도 순서가 같고, 20 이하로 내리면 달라진다. 한 팔에서만 상위인 행이 올라오는 것을 `k=60` 이
  누른다는 뜻이다. (한계: 병합 뒤 **상위 여덟**으로만 다시 정렬한 것이라 후보 풀 60행 중 아래에서
  올라올 행은 보지 못한다)
- **1위 점수가 색인 상태만으로 움직인다.** `0.016393`(팔 하나) → `0.031545`(`run 11552`) →
  `0.031319`(`run 11686`). 마지막 두 사이에 바뀐 것은 **문서 둘의 문장뿐**이다 —
  `run 11686` 이 다시 읽은 것은 이 파일과 [adr/0001](../adr/0001-v1-stack-decisions.md) 이고,
  코드도 청크 규칙도 그대로다. `score` 를 임계값으로 쓸 수 없는 이유가 이것이고,
  D33 이 그렇게 될 것이라 적어 두었다
- **키가 있으면 `search_docs` 는 필터 없이 0건을 내지 않는다.** 벡터 팔에 거리 임계값이 없어
  뜻 없는 질의도 후보를 채운다. **필터가 집합을 비우면 0건이다** — `module`·`doc_type`·`status`·
  없는 `project` 로 실측했다. D33 은 낱말이 없는 질의에서 벡터 팔이 도는 것까지만 적었고,
  **이 상태가 D33 이 지정한 `hit_count=0` 신호를 죽인다는 것은 어디에도 없다** →
  [open-questions.md](open-questions.md) **Q33** 으로 연다
- **아직 안 본 것:** `키 없이 재색인하면 이미 있던 벡터가 사라진다` (D31). 문서를 고쳐야 만들 수 있는
  상태라 이번에 만들지 않았다

**v1이 끝났을 때** 판정에 쓰는 명령 (D18):

```bash
node scripts/check-layout.mjs
docker compose up -d --wait
docker compose exec api sillok ingest --project sillok
curl -sf "http://127.0.0.1:8080/v1/status?project=sillok"
node scripts/smoke.mjs
uv run pytest -q
```

> **여섯 줄을 2026-09-03 에 이 순서로 돌렸다.** 1번째는 `배치 검증 통과`, 2번째는 `db`·`api` 둘 다 `Healthy`,
> 3번째는 `ok` 로 끝난 run 하나, 4번째는 `{"ok":true,…}` 봉투,
> 5번째는 스모크 셋이 전부 `PASS`, 6번째는 호스트에서 DB 검사가 skip 된 채 통과였다.
> 수치는 여기 적지 않는다 — 위 체크박스가 같은 이유로 파일 수를 적지 않는다.
> `exec api` 는 처음 돌렸을 때 `sillok` 이 PATH 에 없어 `executable file not found` 로 죽었고(2026-09-02),
> `Dockerfile` 의 runtime 스테이지가 `/app/.venv/bin` 을 PATH 에 넣도록 고쳐 지금은 그 형태로 돈다.
> 5번째 줄이 10단계 스모크다 (D53). 6번째 줄을 전부 돌리려면 D22의 `--profile test`다.
> **이 블록은 이제 목표가 아니라 도는 명령이다.** 마이그레이션을 더한 뒤에는 `api` 이미지를 다시 굽는다 —
> `migrations/` 는 `test` 서비스에만 마운트돼 있고 `api` 에는 구워져 있다 (D28 이 예고한 자리).

`sillok ingest`는 `serve`가 떠 있지 않아도 도는 것이 D19의 요점이다.
위 명령이 `exec api`를 쓰는 것은 Compose 안에서 워크스페이스와 DSN이 이미 맞춰져 있기 때문이지, HTTP를 타서가 아니다.

## 10. 하지 말 것 (반복)

- 이벤트 본문을 `docs/`에 append
- Collections/외부 RAG로 DB를 대체
- 채팅 모델에게 임베딩을 숫자로 적어 달라고 하기
- 임베딩 모델 변경을 스키마 변경 없이 하기
- "관련 문서 전부" 반환
