---
title: v1 확정 결정 D1–D20
doc_type: adr
status: current
module: null
---

# ADR 0001 — v1 확정 결정 D1–D20

상위: [docs/plan.md](../docs/plan.md) · [README](../README.md)
상태: D1–D15 **2026-08-30 확정** (묶음 추천 수용) · D16–D20 **2026-08-31 확정** (부트스트랩 공백 마감)

이 파일은 **모든 확정값의 정본**이다. 확정값이 다른 문서와 어긋나면 이 파일이 이긴다.

소유자가 정해지지 않은 사실이면 서열로 판정한다 — [plan.md](../docs/plan.md)와 이 파일이 하위 문서를 이긴다.
판정 후 그 사실의 소유자를 [README](../README.md)의 문서 지도에 추가한다. 전체 규칙은 [plan.md](../docs/plan.md) §우선순위.

값을 바꾸려면 이 파일을 먼저 고친다.

> **선택지 라벨 주의.** 아래 `선택` 칸의 `A`/`B`/`C`는 2026-08-30 논의에서 쓰인 라벨이다.
> **그 선택지 목록 자체는 이 저장소에 남아 있지 않다.** `D6=C`, `D9=B`, `D14=C`처럼 비-A 선택이
> 있으므로 최소 3개 안이 있었으나 복원할 수 없다. 따라서 **`결정 내용` 칸만이 구속력을 가진다.**
> 라벨은 이력 표시일 뿐이다. → [open-questions.md](../docs/open-questions.md) Q24

| ID | 선택 | 결정 내용 |
|---|---|---|
| D1 | A | Python FastAPI + MCP Python SDK |
| D2 | A | OpenAI `text-embedding-3-small`, 차원 **1536**. 키 없으면 키워드만 (`embedding` NULL) |
| D3 | A | `save_doc`는 제안만. Git 직접 커밋 없음 |
| D4 | A | `get_file`은 설정된 workspace / 로컬 클론 경로를 읽음 |
| D5 | A | `project` 필수. 멀티 프로젝트 |
| D6 | C | MCP stdio + Streamable HTTP. **같은 Service 프로세스** |
| D7 | A (노출 시 B) | 로컬 무인증. HTTP를 외부에 열면 `Authorization: Bearer <token>` |
| D8 | A | 색인은 CLI `sillok ingest` |
| D9 | B | 색인 경로: `docs/**` + 루트 `README*` + `adr/**` |
| D10 | A | 이벤트 필수 필드 없으면 거절 |
| D11 | A | 반복 원인은 `repeat_causes` 통계와 승격 *제안*까지만. 자동 승격 없음 |
| D12 | A | 사람용은 JSON 현황 API. **웹 UI는 v1 이후** |
| D13 | A | 로컬 Docker Compose: **Postgres + Service 두 개.** MCP는 별도 컨테이너가 아니라 Service와 같은 앱이다 (D6) |
| D14 | C | 본문 한·영 혼용. tsvector 구성 `simple` |
| D15 | A | 비공개 개인 도구 |

## D16–D20 — 부트스트랩 (2026-08-31 확정)

[open-questions.md](../docs/open-questions.md) A절(Q1–Q5)을 마감한다. **D1–D15를 뒤집지 않는다.**
아래 `선택` 라벨은 [§D16–D20 선택지](#d16d20-선택지)에 실제 목록이 남아 있다 — Q24가 지적한 유실을 반복하지 않기 위해서다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D16 | A | 환경변수: 앱은 단일 DSN `DATABASE_URL`, 나머지는 `SILLOK_*` 접두, 키는 `OPENAI_API_KEY` 그대로 | Q1 |
| D17 | A | 마이그레이션: 버전 붙인 raw `.sql`을 `sillok serve` 기동 시 bind 전에 적용. **세 번째 컨테이너 없음** | Q2 |
| D18 | A | 실행 환경: CPython **3.12**, 의존성·실행은 **uv**, 테스트는 **pytest** | Q3 |
| D19 | C | `sillok ingest`는 **같은 앱의 Service 함수를 인프로세스 호출**. CLI는 독자 SQL 계층을 갖지 않는다 | Q4 |
| D20 | C | 색인 진입점은 **CLI**. `POST /v1/ingest`는 같은 함수의 HTTP 얼굴이고 MCP에 노출하지 않는다 | Q5 |

### D16 환경변수 계약

| 이름 | 기본값 | 역할 |
|---|---|---|
| `DATABASE_URL` | `postgresql://sillok:sillok@127.0.0.1:5432/sillok` | 앱 DSN. **분할하지 않는다** |
| `SILLOK_HOST` | `127.0.0.1` | bind 호스트. Compose의 `api`는 `0.0.0.0`으로 덮는다 |
| `SILLOK_PORT` | `8080` | bind 포트 |
| `SILLOK_WORKSPACE` | `.` | workspace 루트 (D4). **Q20의 project→경로 매핑은 닫지 않는다** |
| `SILLOK_BEARER_TOKEN` | 빈 값 | 빈 값이면 D7의 로컬 무인증. 값이 있으면 `Authorization: Bearer` 요구 |
| `OPENAI_API_KEY` | 빈 값 | 빈 값이면 D2대로 `embedding` NULL, `tsv`만. 레포에 넣지 않는다 |

Compose의 `db`는 앱 변수가 아니라 이미지 계약인 `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`를 쓴다.
`api`는 `DATABASE_URL`을 `@db:5432`로, `SILLOK_HOST`를 `0.0.0.0`으로 덮는다 — 그래야 호스트의 `127.0.0.1:8080`에 닿는다.

**`5432`를 호스트에 게시하지 않는다.** 다만 이것은 Compose 위생이지 D19가 강제하는 것이 아니다 —
D19가 금지하는 것은 CLI가 자기 SQL 계층을 갖는 것이고, 게시된 포트가 여는 것은 사람이 `psql`로 들어오는 길이다.
둘 다 막을 값어치가 있지만 근거가 다르다.

사본: [.env.example](../.env.example).

### D17 마이그레이션

```text
migrations/001_extensions.sql   CREATE EXTENSION IF NOT EXISTS vector; pg_trgm
migrations/002_schema.sql       data-model.md 의 DDL
```

DDL 정본은 [data-model.md](../docs/data-model.md)다. 마이그레이션 파일은 그 SQL을 실행할 뿐 **두 번째 스키마 정의가 아니다.**
확장을 먼저, 그다음 테이블·인덱스. 전부 멱등(`IF NOT EXISTS`)이어야 재기동이 안전하다.
Postgres 이미지는 확장 파일이 들어 있는 것(`pgvector/pgvector:pg16` 등)을 쓴다 — 이미지가 있어도 DB마다 `CREATE EXTENSION`은 따로 필요하다.
`sillok migrate`는 같은 러너를 돌리고 끝내는 명령이다. D8이 정한 CLI 두 개와 별개다.

### D18 실행 환경

```text
python   3.12          (이미지도 로컬도 3.12. 범위를 두지 않는다)
deps     uv lock · uv sync --frozen
tests    uv run pytest -q
문서 게이트  node scripts/check-layout.mjs
```

문서 게이트는 파이썬 툴체인과 무관하게 그대로 남는다.

### D19 CLI 계약

```text
sillok serve [--host HOST] [--port PORT]
    기본값은 SILLOK_HOST / SILLOK_PORT
    같은 프로세스에서 FastAPI + MCP Streamable HTTP (D6)

sillok ingest --project PROJECT [--workspace PATH]
    --project    필수 (D5). 기본값 없음
    --workspace  기본값 SILLOK_WORKSPACE
    색인 경로는 플래그가 아니다 — 항상 D9
```

**불변식의 정확한 뜻:** DB의 유일한 문은 *Service 함수*지 HTTP가 아니다.
`MCP와 사람용 UI는 HTTP만 호출한다`는 규칙은 그 둘에 대한 것이고, CLI는 둘 중 어느 쪽도 아니다.
**금지되는 것은 CLI가 자기 SQL을 갖는 것이다.**

D6과 혼동하지 않는다. D6은 *프로세스 동일성*이다 — MCP는 `serve`와 같은 프로세스의 다른 앞면이다.
`ingest`는 **별도 프로세스이고 같은 코드의 함수를 쓴다.** 공유되는 것은 데이터 접근 계층 하나뿐이지
프로세스가 아니다. `serve`와 `ingest`가 각자 DB 세션을 여는 문제는 Q10으로 남는다.

### D20 색인 진입점

운영자가 돌리는 것은 `sillok ingest`다. `POST /v1/ingest`는 이미 떠 있는 api에 같은 함수를 태우는 HTTP 얼굴이고,
MCP에는 노출하지 않는다. 두 문서 중 어느 쪽도 틀리지 않았다 — [plan.md](../docs/plan.md) §5의 MCP 표에 없는 것은 의도이고,
바로 다음 줄이 `MCP에 노출하지 않는 HTTP`로 그것을 명시한다. 아래 `나중에 바꿔도 되는 것`의 n8n webhook이 이 얼굴을 쓴다.

### D16–D20 선택지

Q24는 D1–D15의 선택지 목록이 유실돼 *왜 다른 안을 버렸는가*가 비었다고 지적한다. 아래는 그 반복을 막기 위한 기록이다.

| ID | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D16 | 단일 `DATABASE_URL` + `SILLOK_*` | `PGHOST`/`PGPORT`/… 분할 | 전부 `SILLOK_*` (키 포함) | B는 한 사실을 다섯 변수로 쪼개고 드라이버가 어차피 DSN으로 합친다. C는 이미 고정된 이름 `OPENAI_API_KEY`를 개명하는 계약 변경이다 |
| D17 | 버전 붙인 raw `.sql` | Alembic | 기동 시 파이썬 `create_all` | B는 이미 다 쓰인 DDL을 두 번째 스키마 정의로 복제한다. C는 실행 스키마가 DDL 정본에서 조용히 갈라진다. 마이그레이션 전용 컨테이너는 D13(2개)이 배제 |
| D18 | 3.12 + uv + pytest | 3.12 + pip + requirements | 3.13 + Poetry + pytest | B는 lock 신뢰도가 가장 약해 결국 별도 도구를 얹게 된다. C는 이미지에 Poetry 런타임이 들어가고 `poetry`와 `pip` 두 도구를 쓰게 된다 |
| D19 | CLI가 `POST /v1/ingest`의 HTTP 클라이언트 | CLI가 Postgres에 직접 접속 | 인프로세스로 Service 함수 호출 | **B는 불변식 위반** — 데이터 접근 계층이 둘이 되고 검증·쓰기가 복제된다. A는 색인 때마다 serve가 떠 있어야 하고 스캔+임베딩이 단일 긴 요청이 되어 타임아웃·진행률 문제를 부른다 |
| D20 | CLI만 남기고 엔드포인트 삭제 | HTTP가 진입점, CLI는 래퍼 | 같은 함수의 두 앞면 | A는 엔드포인트 소유자인 `service-and-mcp.md`를 틀리게 만들고 n8n webhook 확장을 막는다. B는 D19를 A로 되돌린다 |

### D16–D20이 닫지 않는 것

- **Q20** `project` → workspace 경로 매핑. D16은 workspace 루트 **하나**의 이름만 정했다
- **Q10** ingest 트랜잭션 경계와 동시 실행. `serve`와 `ingest`가 각자 세션을 여는 것까지만 정했다
- **Q17** MCP 도구 입력 스키마와 stdio 마운트 경로. D19는 `serve`가 둘을 같은 프로세스에서 연다는 것만 정했다
- **Q7 · Q9** 임베딩 백필과 `kb_events`의 `tsv`. D17이 `002` 다음 번호를 쓸 자리를 열어 둘 뿐이다

## 구현에 고정되는 값

- `vector(1536)` — 임베딩 모델 ID `text-embedding-3-small`
- Postgres 16+, 확장 `vector`, `pg_trgm`
- Git 쓰기는 proposal 응답만. 커밋 없음
- ingest include: `docs/`, 루트 `README*`, `adr/`
- MCP stdio 클라이언트 + HTTP 서버를 한 코드베이스에서
- Service 기본 `http://127.0.0.1:8080`
- 검색 기본 `top_k` 8, 최대 12
- CPython 3.12, uv, pytest (D18)
- 환경변수 이름 6개 — `DATABASE_URL`, `SILLOK_HOST`, `SILLOK_PORT`, `SILLOK_WORKSPACE`, `SILLOK_BEARER_TOKEN`, `OPENAI_API_KEY` (D16)
- 마이그레이션은 `serve` 기동 시 bind 전에 적용, 멱등 (D17)
- 색인 진입점은 `sillok ingest`. CLI는 자기 SQL을 갖지 않는다 (D19·D20)

## 이 값들이 복제된 위치

정본은 이 파일이다. 아래 사본이 어긋나면 **이 파일이 이긴다.** 값을 바꿀 때 함께 고친다.

| 사본 | 복제된 값 |
|---|---|
| [docs/plan.md](../docs/plan.md) §2 | 확정 스택 표 전체 |
| [CLAUDE.md](../CLAUDE.md) | 확정 스택 표 (도구 컨텍스트용 미러) |
| [docs/data-model.md](../docs/data-model.md) | `vector(1536)`, 모델 ID, 확장 목록 |
| [docs/service-and-mcp.md](../docs/service-and-mcp.md) | 서비스 주소, 인증, `top_k`, 색인 경로 |
| [AGENTS.md](../AGENTS.md) | 확정 전제 요약 블록 |
| [.env.example](../.env.example) | D16 환경변수 이름과 기본값 |

## 나중에 바꿔도 되는 것 (v1 비범위)

- D2를 Voyage / Gemini / Qwen3 / xAI로 교체 → **스키마 변경 + 전체 재색인**이 따라온다
- D7을 토큰으로 상향
- D8에 n8n webhook 추가
- D12 작은 웹 UI
- D13을 기존 Postgres에 붙이기

## 미기록

D21 이후로 기록해야 할 미해결 결정은 [docs/open-questions.md](../docs/open-questions.md)에 전부 모여 있다.
2026-08-31 기준 남은 것은 B절(색인·검색 결정성) · C절(API 계약) · D절(무결성·보안)과 Q24·Q25다.
