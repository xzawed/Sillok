# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 이 저장소의 성격

**문서가 먼저이고 코드가 따라온다.** 문서 자체가 계약이다.
[docs/plan.md](docs/plan.md) §7의 **1–6단계까지 구현돼 있고 7단계부터는 아직 없다.**
(진행 상태 정본은 §7·§9다. 아래는 미러다.)
있는 것: `docker-compose.yml`+`Dockerfile`(db+api), `migrations/*.sql`,
`src/sillok/`(config · migrations 러너 · api · ingest·search 규칙 · CLI `migrate`/`serve`/`ingest`), `tests/`.
**업무 라우트는 여섯이다** — `POST /v1/events` · `GET /v1/stats/events` · `GET /v1/status` ·
`POST /v1/ingest`(5단계, MCP 에는 노출하지 않는다) · `POST /v1/search/docs` · `POST /v1/search/events`.
`get_file`·`save_doc`·MCP 경로는 정직하게 404다. 스텁을 만들지 않는다.
없는 것: MCP 도구 표면, `get_file`·`save_doc` — 순서대로 붙인다.

저장소 지도는 [docs/conventions.md](docs/conventions.md). **시작점은 [docs/plan.md](docs/plan.md)다.**
협업 규칙은 [AGENTS.md](AGENTS.md).

이 파일은 Claude Code 전용 컨텍스트다. **여기에 정본은 없다 — 전부 미러다.**

### 문서 우선 (가장 중요한 규칙)

```text
docs/plan.md = adr/0001-v1-stack-decisions.md   >   docs/ 나머지
```

- 동작이 명세와 다르면 **코드가 틀린 것으로 본다.**
- 계약을 바꾸려면 [docs/plan.md](docs/plan.md)와 [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md)를 **먼저** 고치고 나서 구현한다.
- ADR의 D1–D15는 2026-08-30, D16–D20은 2026-08-31 확정. 임의로 뒤집지 않는다.
- 같은 값이 여러 문서에 있으면 사본에 정본 위치가 적혀 있다. 어긋나면 정본이 이긴다.
- **충돌 판정은 파일 서열보다 사실 소유권이 먼저다.** [docs/conventions.md](docs/conventions.md)의 문서 지도에서 그 사실을 소유한 파일이 이긴다.
  소유자가 지도에 없으면 위 서열로 판정하고, 판정 후 소유자를 지도에 추가한다.

### 아직 답이 없는 것

[docs/open-questions.md](docs/open-questions.md)의 미해결 질문들은 **아무 문서에도 답이 없다.**
추측으로 채우고 구현하지 않는다. 먼저 결정하고 ADR에 D33 이후로 기록한다.

A절(Q1–Q5)은 **D16–D20**, Q11은 **D21**, Q26은 **D22**, Q16·Q18·Q21은 **D23–D25**,
B절은 Q6·Q7·Q10이 **D30–D32**로, Q8·Q9가 **D33–D34**로 마감돼 전부 닫혔다 —
작업 순서 1–6단계를 이제 검증할 수 있다.
남은 것이 단계별로 막는다:
7단계 전에 Q12·Q15·Q19·Q20, 8단계 전에 Q17.

## 핵심 불변식

Sillok은 RAG 플랫폼이 아니라 **저장 위치를 강제하는 지식 원장**이다. 모든 설계 판단이 여기서 나온다.

- **Git** = 현재 진실만 (현재형 규범, 최신본 하나)
- **Postgres** = 사건 원장(`kb_events`) + Git 문서의 검색 인덱스(`kb_documents`/`kb_chunks`)
- **AI**는 MCP 도구가 반환한 행 몇 개만 본다. 문서를 대화에 통째로 넣지 않는다.
- 적재량이 늘어도 질의당 토큰은 거의 고정 — "관련 문서 전부" 반환은 설계 위반.

분류 판단은 감으로 하지 않고 [docs/skills/sillok-storage/SKILL.md](docs/skills/sillok-storage/SKILL.md)의 결정 트리를 따른다.
이 파일은 동시에 **다른 프로젝트로 복사되는 배포 산출물**이다. 사본이 아니라 원본을 고친다.

## 확정 스택 (뒤집지 말 것)

> 정본: [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md) — 값이 다르면 정본이 이긴다.

| 항목 | 값 |
|---|---|
| 언어/프레임워크 | Python, FastAPI, MCP Python SDK |
| DB | PostgreSQL 16+, 확장 `vector`(pgvector) · `pg_trgm` |
| 임베딩 | `text-embedding-3-small`, **`vector(1536)`** 고정 |
| 키 없을 때 | `embedding`은 NULL, `tsv` 키워드 검색만 동작 |
| tsvector 구성 | `simple` (한·영 혼용) |
| MCP | stdio + Streamable HTTP, **같은 앱** |
| Service 주소 | `http://127.0.0.1:8080` |
| 인증 | 로컬 무인증. 외부 노출 시에만 `Authorization: Bearer` |
| 배포 | Docker Compose (db + api 2개) |
| 런타임 | CPython 3.12, uv, pytest (D18) |
| 환경변수 | `DATABASE_URL` + `SILLOK_HOST`·`SILLOK_PORT`·`SILLOK_WORKSPACE`·`SILLOK_BEARER_TOKEN` + `OPENAI_API_KEY` (D16) |
| 마이그레이션 | 버전 붙인 raw `.sql`, `serve` 기동 시 bind 전 멱등 적용 (D17) |
| CLI | `sillok ingest`, `sillok serve` (+ 마이그레이션 러너 `sillok migrate`) |
| ingest 경로 | CLI가 Service 함수를 인프로세스 호출. CLI는 자기 SQL을 갖지 않는다 (D19) |
| 색인 경로 | `docs/**`, 루트 `README*`, `adr/**` — 이 셋만 |
| 사람 UI | JSON 현황 API만. **웹 페이지는 v1 비범위** |
| 비밀키 | `OPENAI_API_KEY`는 env. 레포에 넣지 않음 |

임베딩 모델을 바꾸면 스키마 변경 + 전체 재색인이 따라온다 (차원이 DDL에 박혀 있음).

## 아키텍처

```text
Postgres          kb_documents, kb_chunks, kb_events, kb_ingest_runs, kb_query_logs
Knowledge Service FastAPI — DB를 만지는 유일한 문 (단위는 함수지 HTTP가 아니다, D19)
출구              MCP 도구 8개 + Skill + JSON 현황 API
```

**MCP와 사람용 UI는 DB에 직접 붙지 않는다.** 둘 다 Service의 HTTP API만 호출하고,
API와 MCP 도구는 **같은 Service 함수를 탄다** (도구별로 로직을 복제하지 않는다).

### 도구 ↔ 엔드포인트 (이름 고정)

| MCP 도구 | HTTP |
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
`POST /v1/ingest`는 삭제 대상이 아니라 CLI와 **같은 Service 함수의 HTTP 얼굴**이다. 운영자 진입점은 CLI (D20).
입출력 JSON 전문은 [docs/service-and-mcp.md](docs/service-and-mcp.md). MCP 도구 설명문은 짧게 — 길면 모델이 도구를 안 고른다.

공통 응답: `{ "ok": true, "data": {} }` / `{ "ok": false, "error": { "code": "...", "message": "..." } }`
에러 코드 → HTTP (D21): `VALIDATION` 422 · `UNAUTHORIZED` 401 · `NOT_FOUND` 404 · `CONFLICT` 409(D32: 같은 project 의 동시 ingest) · `INTERNAL` 500
`INTERNAL`의 `message`는 고정 문자열 `internal error`. 예외 문구를 싣지 않는다 — DSN·토큰·키가 새는 길이다.

## 구현 순서 (이 순서를 어기지 말 것)

[docs/plan.md](docs/plan.md) §7. 요지는 **임베딩 없이 도는 것부터** 세운다는 것:

1. Compose (Postgres + pgvector, `5432` 미게시) → 2. 마이그레이션 `001` 확장 → `002` 스키마, 멱등([docs/data-model.md](docs/data-model.md) DDL)
→ 3. FastAPI 골격 + 공통 응답 → 4. `save_event`/`event_stats`/`kb_status`
→ 5. ingest (스캔·해시·청크·tsv, 키 있으면 임베딩) → 6. `search_docs`/`search_events`
→ 7. `get_file`/`get_event`/`save_doc` 제안 → 8. MCP를 같은 함수에 연결
→ 9. `kb_query_logs` 기록 → 10. 스모크

## 절대 금지

- 이벤트 이력을 `docs/`에 append — 이 경로가 존재하면 프로젝트가 실패한 것
- `save_doc`이 Git에 직접 커밋 — v1은 **제안 본문/diff 반환만**
- MCP에 임의 SQL 도구, 전체 덤프, 이벤트 일괄 삭제 노출
- 통계에 벡터 검색 사용 — `event_stats`는 SQL 필터 + `COUNT`/`AVG`만
- 기본 `top_k > 8` (최대 12)
- 빈 결과에 모델이 채울 문장을 API가 넣기 — `{ "results": [] }` 그대로
- 반복 원인의 Git 자동 승격 — v1은 `repeat_causes` 통계와 *제안*까지만
- 범위 확장: SCAManager, 전사 검색, 공개 라이브러리 문서(Context7류), 지식그래프, 웹 UI, n8n, IDE Plugin

## 이벤트 검증 (거절 규칙)

`save_event`는 필수 필드가 없으면 **저장하지 않고 `VALIDATION`으로 거절**한다. 관대하게 채우지 않는다.

- 필수: `project`, `kind`, `title`, `summary`, `occurred_at`(ISO-8601), `result`
- `kind`: `success` | `failure` | `incident` | `decision`
- `result`: `success` | `failure` | `partial` | `unknown`
- `severity`(선택): `low` | `medium` | `high` | `critical`
- `summary` 2000자 초과 거절

## 검색 규칙

- 문서: 벡터 유사도 + `tsv` 키워드를 RRF(`k=60`)로 병합 (정의는 D33)
- 이벤트: **필터(project, kind, module, 기간)를 먼저** 걸고 남은 집합에 키워드만 (D34)
- 식별자·에러코드·날짜·건수는 벡터로 풀지 않는다 (필터/SQL)
- 이벤트 임베딩은 `summary`만 — 다만 **v1 은 이벤트를 임베딩하지 않는다** (D34)
- 재색인은 `(project, repo, path)` 단위로 청크 삭제 후 insert
- 검색 0건도 `kb_query_logs`에 `hit_count=0`으로 남긴다 (v1 성공 조건)

## 검증 명령

```bash
node scripts/evidence.mjs              # PR 증거를 한 번에 (AGENTS 가 요구하는 형태)
node scripts/check-layout.mjs          # 문서 게이트만
node scripts/check-layout.test.mjs     # 그 게이트가 실제로 무는지 (고장 주입 + 메타)
docker compose up -d --wait            # db + api (5432 미게시, 8080 만 게시)
curl -i http://127.0.0.1:8080/v1/nope  # 404 + 공통 봉투. detail 이 새면 계약 위반
uv run pytest -q                       # 호스트. DB 검사는 skip 된다
docker compose --profile test run --rm test   # DB 검사까지 (D22)
```

**호스트에서는 skip이 나오는 것이 정상이다.** `skip 0`은 D16이 막은 `5432`를
게시했다는 신호이지 더 나은 결과가 아니다 — 보고할 때 skip 개수를 빼지 않는다.
개수는 문서에 적지 않는다. 적으면 검사가 늘 때마다 낡는다.
DB 검사까지 돌리려면 `docker compose --profile test run --rm test` (D22, `5432`는 닫힌 채).
호스트에서 DB에 붙어야 하면(`pytest`의 DB 검사, `sillok migrate`)
`compose.override.example.yml`을 `compose.override.yml`로 복사한다.

문서 게이트다. 문서를 옮기거나 링크를 고친 뒤 반드시 돌린다.
D9 색인 대상 목록, 색인되면 안 되는 파일, front matter taxonomy(루트 `README*`는 **없어야** 한다, D29),
링크 해석, 진입점 도달성, 구 파일명 잔존,
존재하지 않는 `Q` 번호 참조, 머지 후 의미를 잃는 지시어(`이 PR` 등), 닫히지 않은 코드 펜스,
산문에 박힌 테스트 수치, 폐기된 문구,
**Q 게이트**(단계를 막는 Q가 열려 있는데 그 단계의 라우트·CLI·MCP가 `src/`에 있는가)를
검사하고 실패 시 종료 코드 1.

한 변경이 나가는 절차와 PR 하나의 증거는 [AGENTS.md](AGENTS.md)가 소유한다.

## 이 저장소의 규약

- **문서 front matter**: `docs/**`와 `adr/**`의 각 문서는 `title`·`doc_type`·`status`·`module`을 YAML front matter로 갖는다. 필드는 `kb_documents` 컬럼과 1:1이다. `AGENTS.md`/`CLAUDE.md`는 색인 대상이 아니므로 예외다.
- **루트 `README*`는 반대다 (D29)**: front matter를 **갖지 않는다** — GitHub가 최상단에 표로 렌더한다. 네 값은 ingest가 경로(`readme`·`current`·`null`)와 첫 H1(`title`)에서 유도한다. 게이트가 양방향으로 본다.
- **README 어조·개행**: [docs/conventions.md](docs/conventions.md)가 소유한다. 요지는 한국어 README의 산문은 합쇼체, 제목·표 셀은 개조식, 줄은 문장 경계에서 끊고 표시폭 100칸 이내.
- **자기 색인**: 이 저장소의 배치는 Sillok 자신의 색인 경로(D9)를 따른다. 첫 ingest 스모크는 이 레포를 대상으로 돌린다.
- **작업 단위**: 모든 변경은 브랜치 + PR. `main`에 직접 커밋하지 않는다.
- 이벤트는 Git에 원본이 없는 유일한 데이터 → **백업 대상**. 문서 인덱스는 언제든 재생성 가능.
