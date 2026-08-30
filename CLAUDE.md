# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 이 저장소의 성격

**코드가 아직 없다.** 이 저장소는 Sillok 구현을 위한 명세 묶음이고, 문서 자체가 계약이다.
빌드·테스트·린트 명령이 존재하지 않는 것은 정상이다.

저장소 지도는 [README.md](README.md). **시작점은 [docs/plan.md](docs/plan.md)다.**
협업 규칙은 [AGENTS.md](AGENTS.md).

이 파일은 Claude Code 전용 컨텍스트다. **여기에 정본은 없다 — 전부 미러다.**

### 문서 우선 (가장 중요한 규칙)

```text
docs/plan.md = adr/0001-v1-stack-decisions.md   >   docs/ 나머지
```

- 동작이 명세와 다르면 **코드가 틀린 것으로 본다.**
- 계약을 바꾸려면 [docs/plan.md](docs/plan.md)와 [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md)를 **먼저** 고치고 나서 구현한다.
- ADR의 D1–D15는 2026-08-30 확정. 임의로 뒤집지 않는다.
- 같은 값이 여러 문서에 있으면 사본에 정본 위치가 적혀 있다. 어긋나면 정본이 이긴다.

### 아직 답이 없는 것

[docs/open-questions.md](docs/open-questions.md)의 Q1–Q24는 **아무 문서에도 답이 없다.**
추측으로 채우고 구현하지 않는다. 먼저 결정하고 ADR에 D16 이후로 기록한다.
특히 Q1–Q5(환경변수, 마이그레이션 실행, 실행 환경, CLI 계약)를 답하기 전에는 작업 순서 1–2단계를 검증할 수 없다.

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
| CLI | `sillok ingest`, `sillok serve` |
| 색인 경로 | `docs/**`, 루트 `README*`, `adr/**` — 이 셋만 |
| 사람 UI | JSON 현황 API만. **웹 페이지는 v1 비범위** |
| 비밀키 | `OPENAI_API_KEY`는 env. 레포에 넣지 않음 |

임베딩 모델을 바꾸면 스키마 변경 + 전체 재색인이 따라온다 (차원이 DDL에 박혀 있음).

## 아키텍처

```text
Postgres          kb_documents, kb_chunks, kb_events, kb_ingest_runs, kb_query_logs
Knowledge Service FastAPI — DB를 만지는 유일한 문
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
입출력 JSON 전문은 [docs/service-and-mcp.md](docs/service-and-mcp.md). MCP 도구 설명문은 짧게 — 길면 모델이 도구를 안 고른다.

공통 응답: `{ "ok": true, "data": {} }` / `{ "ok": false, "error": { "code": "...", "message": "..." } }`
에러 코드: `VALIDATION` | `NOT_FOUND` | `CONFLICT` | `INTERNAL` (HTTP 상태 매핑은 미정 — Q11)

## 구현 순서 (이 순서를 어기지 말 것)

[docs/plan.md](docs/plan.md) §7. 요지는 **임베딩 없이 도는 것부터** 세운다는 것:

1. Compose (Postgres + pgvector) → 2. 마이그레이션([docs/data-model.md](docs/data-model.md) DDL)
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

- 문서: 벡터 유사도 + `tsv` 키워드, 가능하면 RRF 병합 (병합 방식 미정 — Q8)
- 이벤트: **필터(project, kind, module, 기간)를 먼저** 걸고 남은 집합에 벡터/키워드
- 식별자·에러코드·날짜·건수는 벡터로 풀지 않는다 (필터/SQL)
- 이벤트 임베딩은 `summary`만
- 재색인은 `(project, repo, path)` 단위로 청크 삭제 후 insert
- 검색 0건도 `kb_query_logs`에 `hit_count=0`으로 남긴다 (v1 성공 조건)

## 이 저장소의 규약

- **문서 front matter**: `docs/**`, `adr/**`, 루트 `README.md`의 각 문서는 `title`·`doc_type`·`status`·`module`을 YAML front matter로 갖는다. 필드는 `kb_documents` 컬럼과 1:1이다. `AGENTS.md`/`CLAUDE.md`는 색인 대상이 아니므로 예외다.
- **자기 색인**: 이 저장소의 배치는 Sillok 자신의 색인 경로(D9)를 따른다. 첫 ingest 스모크는 이 레포를 대상으로 돌린다.
- **작업 단위**: 모든 변경은 브랜치 + PR. `main`에 직접 커밋하지 않는다.
- 이벤트는 Git에 원본이 없는 유일한 데이터 → **백업 대상**. 문서 인덱스는 언제든 재생성 가능.
