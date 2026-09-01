---
title: v1 확정 결정 D1–D32
doc_type: adr
status: current
module: null
---

# ADR 0001 — v1 확정 결정 D1–D32

상위: [docs/plan.md](../docs/plan.md) · [README](../README.md)
상태: D1–D15 **2026-08-30 확정** (묶음 추천 수용) · D16–D28 **2026-08-31 확정** (부트스트랩, HTTP 에러 표면, 테스트 경로, 4단계 계약, 공개 전환, 라이선스, 증거 신선도)
· D29–D32 **2026-09-01 확정** (README front matter, 5단계 ingest 계약)

이 파일은 **모든 확정값의 정본**이다. 확정값이 다른 문서와 어긋나면 이 파일이 이긴다.

소유자가 정해지지 않은 사실이면 서열로 판정한다 — [plan.md](../docs/plan.md)와 이 파일이 하위 문서를 이긴다.
판정 후 그 사실의 소유자를 [docs/conventions.md](../docs/conventions.md)의 문서 지도에 추가한다. 전체 규칙은 [plan.md](../docs/plan.md) §우선순위.

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
| D15 | A | 비공개 개인 도구 → **공개로 개정됨 (D26)**. `개인 도구`(제품이 아님)는 유효하다 |

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
tests    uv run pytest -q                             호스트. DB 검사는 skip 된다
         docker compose --profile test run --rm test  DB 검사까지 (D22)
문서 게이트  node scripts/check-layout.mjs
         node scripts/check-layout.test.mjs           그 게이트가 무는지
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
프로세스가 아니다. `serve`와 `ingest`가 각자 DB 세션을 여는 문제는 **D32가 세션 advisory 락으로 닫았다.**

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

## D21 — HTTP 어댑터의 에러 표면 (2026-08-31 확정)

[open-questions.md](../docs/open-questions.md) Q11을 마감한다. 3단계(FastAPI 골격)의 공통 응답이 여기에 걸려 있었다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D21 | A | 코드↔상태 매핑을 고정하고, 응답 본문은 **언제나** 공통 봉투다. `UNAUTHORIZED`를 코드에 추가한다 | Q11 |

| `error.code` | HTTP | 비고 |
|---|---|---|
| `VALIDATION` | 422 | FastAPI의 요청 모델 실패와 같은 부류다. v1에서 400과 나누지 않는다 |
| `UNAUTHORIZED` | 401 | **새 코드.** D7 게이트 전용. 권한 모델이 없으므로 403은 쓰지 않는다 |
| `NOT_FOUND` | 404 | 3단계에서는 **없는 경로**에만 쓴다. `get_event`의 404 대 빈 결과는 Q12로 남는다 |
| `CONFLICT` | 409 | **D32가 첫 발신자를 만들었다** — 같은 project 의 동시 ingest 거절. 아래 참조 |
| `INTERNAL` | 500 | 서버 결함. 클라이언트 입력 문제가 아니다 |

**상태코드는 어댑터의 것이고 애플리케이션 신호는 `ok:false`다.** D19가 정한 대로 단위는 Service 함수이고,
MCP를 통해 오는 모델은 함수 결과를 본다. 상태코드는 `curl`·나중의 n8n 같은 HTTP 클라이언트를 위한 것이다.

**전부 200으로 돌리지 않는다.** [plan.md](../docs/plan.md) §9의 판정 명령이 `curl -sf`이고,
모든 본문이 200이면 그 `-f`가 영원히 걸리지 않는다. 이미 적힌 검증을 무력화하는 선택은 택하지 않는다.

빈 검색 결과는 오류가 아니다. `{ "results": [] }` 그대로 200이다.

### FastAPI 기본 응답은 봉투를 깬다

FastAPI는 요청 검증 실패에 `{"detail": [...]}`를, 없는 경로에 `{"detail": "Not Found"}`를 돌려준다.
둘 다 [service-and-mcp.md](../docs/service-and-mcp.md)가 소유한 공통 응답 계약 위반이다. 핸들러로 덮는다.

```text
fastapi.exceptions.RequestValidationError   -> VALIDATION / 422
starlette.exceptions.HTTPException          -> 상태에 맞는 코드
Exception                                    -> INTERNAL / 500
```

`starlette` 쪽을 등록해야 한다. `fastapi.HTTPException`만 등록하면 프레임워크 내부에서 나는 것이 잡히지 않는다.
같은 이유로 기본 `fastapi.security.HTTPBearer`를 그대로 쓰지 않는다 — 그것도 `{"detail": ...}`를 돌려준다.

**계약 밖 상태는 살아남지 않는다.** 프레임워크가 405 같은 상태를 들고 오면 위 표의 코드로 접고,
나가는 상태는 **그 코드의 상태**다(405 → `VALIDATION` → 422). 코드↔상태를 1:1로 유지하기 위해서다.
5xx는 `INTERNAL`, 나머지 4xx는 `VALIDATION`으로 접는다. 코드를 늘리는 것은 계약 변경이다.

### `CONFLICT`에 v1 발신자가 없었다 — D32 가 만들었다

Q11이 이미 `발생 조건조차 없다`고 적었고, 실제로 없다.

| 표면 | 왜 CONFLICT가 아닌가 |
|---|---|
| `POST /v1/events` | `id`가 `bigserial`이고 payload에 유일성이 없다. 여기서 유일성을 발명하면 **Q18을 추측으로 닫는 것**이다 |
| `POST /v1/docs/proposals` | D3대로 쓰지 않는다. 충돌할 대상이 없다 |
| ingest의 `UNIQUE (project, repo, path)` | 재색인은 청크를 지우고 다시 넣는 upsert다 |
| 동시 ingest | **D32가 이 칸을 채웠다** — 세션 advisory 락을 못 얻으면 `CONFLICT` 409 다. 경쟁 상황의 UniqueViolation은 여전히 `INTERNAL` 이고, 락이 그 경쟁을 없애므로 발생하면 결함이다 |

**D21 시점에는 코드를 예약으로 남기고 매핑만 정했다.** 아무도 만들지 않는 코드를 지우는 것은 계약 변경이고,
쓰이는 것처럼 보이려고 발신 조건을 발명하는 것은 더 나쁘기 때문이다.
**D32 가 그 자리를 채웠다** — 발명한 것이 아니라 Q10 이 닫히면서 조건이 정해진 것이다.

### `INTERNAL`의 본문은 고정 문자열이다

```json
{ "ok": false, "error": { "code": "INTERNAL", "message": "internal error" } }
```

예외 문구·트레이스백·경로를 실어 보내지 않는다. `psycopg` 예외는 DSN을 품는 일이 잦고,
그 교훈은 이미 러너의 `redact_dsn`에 있다. `SILLOK_BEARER_TOKEN`·`OPENAI_API_KEY`도 마찬가지다.
서버 로그에 남기고 클라이언트에는 고정 문구만 준다.

`save_event`의 `에러 메시지를 그대로 돌려줌`은 **`VALIDATION`에 대한 것**이지 `INTERNAL`이 아니다.

### D21 선택지

| ID | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D21 매핑 | 코드별 상태 + 봉투 | 전부 200, 봉투만 | 상태만, 봉투 없음 | B는 plan §9의 `curl -sf`를 무력화하고 전송 성공과 처리 실패를 섞는다. C는 공통 응답 계약 자체를 버린다 |
| D21 인증 | `UNAUTHORIZED` 추가 | `VALIDATION`으로 통합 | 3단계에서 게이트 생략 | B는 모델에게 *인자가 틀렸다*고 말해 재시도를 유도한다 — 틀린 의미를 강제한다. C는 D7이 이미 정한 것을 미룬다 |
| D21 VALIDATION | 422 | 400 | 400/422 분리 | B·C는 FastAPI 자신의 요청 검증 실패와 부류가 갈라져 클라이언트가 두 형태를 구분해야 한다 |

### D21이 닫지 않는 것

- **Q12** `get_event`의 404 대 빈 결과, 프로젝트 경계 검사. D21은 *없는 경로*의 404만 정했다
- **Q13** 페이지네이션과 목록·타임라인 엔드포인트
- **Q16 · Q18 · Q21** 4단계(`save_event`·`event_stats`)가 필요로 하는 것들
- **Q17** MCP 입력 스키마와 마운트 경로. D7 게이트가 Streamable HTTP에 어떻게 걸리는지는 그때 확정한다
- ~~**Q10** 동시 실행~~ — **D32로 닫혔다.** 락 거절이 `CONFLICT` 의 첫 발신자다

## D22 — 커밋된 구성에서 DB 검사를 돌리는 방법 (2026-08-31 확정)

[open-questions.md](../docs/open-questions.md) Q26을 마감한다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D22 | A | `profiles: ["test"]`로 게이트된 compose `test` 서비스. 내부 네트워크만 쓰고 **호스트 포트를 열지 않는다** | Q26 |

```text
docker compose --profile test run --rm test
```

- 이미지는 다단계다. `runtime`은 지금까지의 api 이미지 그대로이고, `test`는 거기에 `tests/`와 dev 의존성을 더한다
- **`api`는 `target: runtime`을 명시해야 한다.** `build: .`은 *마지막* 스테이지를 쓰므로,
  빠뜨리면 pytest가 운영 이미지로 들어간다 — 이 결정이 피하려던 바로 그것이다
- 기본 `docker compose up`은 여전히 `db` + `api` 둘뿐이다. `profiles`가 붙은 서비스는 기본 `up`에 없다
- `5432`는 계속 게시하지 않는다 (D16). `test`는 `api`와 같은 방식으로 `db:5432`에 붙는다

### D13과 충돌하는가

D13은 `로컬 Docker Compose: Postgres + Service 두 개`다. **`두 개`는 기본 `up`이 세우는 제품 스택을 가리킨다.**
D17이 `세 번째 컨테이너 없음`으로 마이그레이션 전용 컨테이너를 배제한 것도 그 `up` 경로에 대한 것이다.
`profiles`로 가려진 테스트 러너는 제품 스택이 아니고 `up`에 나타나지 않는다. **D22는 D13을 해석할 뿐 고치지 않는다.**

**단, 게이트를 벗기면 곧바로 위반이다.** `test`에 `profiles`를 빼거나 `ports:`를 붙이면 D13 개정이 필요하다.

### D22 선택지

| A | B | C | D | 버린 이유 |
|---|---|---|---|---|
| profiles 게이트 `test` 서비스 | skip을 받아들이고 항상 드러낸다 | 운영 `api` 이미지에 테스트를 넣는다 | 별도 `compose.test.yml` | B는 19개가 커밋된 구성에서 **영원히 안 돌고** 4단계가 DB 검사를 더하면 구멍이 커진다. C는 런타임 이미지에 테스트 러너를 싣는다. D는 같은 효과지만 `-f` 두 개를 조합해야 해 잊기 쉽다 |

### D22가 닫지 않는 것

- 테스트가 제품 `db_data` 볼륨을 함께 쓴다. 격리는 정하지 않았다
- 5단계 ingest 검사는 workspace 파일이 필요한데 `test` 이미지에는 `docs/`·`adr/`가 없다. 그때 더한다
- **Q20 · Q10 · Q6–Q9 · Q12–Q19 · Q21 · Q23–Q25**는 그대로 열려 있다

## D23–D25 — 4단계(`save_event` · `event_stats` · `kb_status`) (2026-08-31 확정)

[open-questions.md](../docs/open-questions.md) Q16·Q18·Q21을 마감한다. 4단계 라우트를 막던 것들이다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D23 | B | `repeat_causes`는 `module`까지 묶고, 2회 이상만, 최대 12개. `avg_resolution_seconds` 추가 | Q16 |
| D24 | C | **`save_event`는 멱등이 아니다.** 재시도는 행을 하나 더 넣는다 | Q18 |
| D25 | A | 레지스트리 없음. 검증은 서비스에서. DDL에 CHECK를 넣지 않는다 | Q21 |

### D23 `event_stats` 응답

```json
{
  "total": 12,
  "by_kind": { "failure": 7, "success": 4, "incident": 1 },
  "by_result": { "failure": 6, "success": 5, "partial": 1 },
  "by_module": { "auth": 4, "billing": 2 },
  "repeat_causes": [{ "module": "auth", "root_cause": "pool exhausted", "count": 3 }],
  "avg_resolution_seconds": 3600
}
```

**`repeat_causes`에 `module`이 들어간다.** Skill의 결정 트리가 `project+module+root_cause`로 반복을 세는데
(`SKILL.md` 5번), 응답이 `root_cause`만 묶으면 `?module=` 없이 부른 결과가 그 트리와 어긋난다 —
`auth`의 `pool exhausted`와 `billing`의 그것이 한 줄로 합쳐진다. **D11의 승격 제안이 거짓말을 하게 된다.**
`project`는 질의 파라미터이므로 항목에 넣지 않는다.

- `root_cause IS NULL`은 제외한다. 원인이 아니다
- `HAVING count >= 2` — Skill의 *2회 이상*이 그대로 임계값이다
- `ORDER BY count DESC, root_cause ASC, module ASC NULLS LAST LIMIT 12` — 상한이 없으면 distinct 원인 전부가 나가
  토큰 불변식을 깬다. `12`는 검색 최대치와 같은 값이다. **동수면 `root_cause`, 그래도 같으면 `module`로 다시 정렬한다** —
  그렇지 않으면 `LIMIT`이 자르는 대상과 항목 순서가 실행마다 달라진다. `module`이 NULL 인 반복은 마지막에 온다
- `module`이 없는 반복도 항목으로 나간다(`"module": null`). `by_module`이 NULL **키**를 못 만드는 것과 다르다 —
  여기서는 필드라 `null`을 표현할 수 있고, 모듈 없는 반복도 승격 제안 대상이다
- `avg_resolution_seconds`는 `ROUND(EXTRACT(EPOCH FROM AVG(...)))` — 소수 첫째 자리에서 반올림한 정수 초다
- `by_module`은 `module IS NULL`인 행의 키를 **넣지 않는다.** JSON 키는 null일 수 없고 `"null"`은 실제 모듈명과 충돌한다.
  그 행들은 `total`에 그대로 있으므로 `sum(by_module) <= total`이 신호다. 0인 키도 넣지 않는다
- `avg_resolution_seconds`는 정수 초 또는 `null`. `resolved_at`이 NULL인 행은 `AVG`에서 빠지므로
  미해결 건이 평균을 0으로 끌지 않는다. **전부 미해결이면 `0`이 아니라 `null`이다**

벡터는 쓰지 않는다.

### D24 `save_event`는 멱등이 아니다

재시도는 행을 하나 더 넣는다. UNIQUE도, `CONFLICT`도, `003`도 없다.

**필수 필드로 만든 내용 해시로 접는 안(B)을 버린 이유:** 같은 `project+module+root_cause`가 반복되는 것이
바로 `repeat_causes`다. 그 행들을 하나로 합치면 **D11이 탐지하려는 대상 자체가 사라진다.**
"중복 제거"처럼 보이지만 실제로는 통계를 파괴한다.

- `id`는 `bigserial`이고 payload에 유일성이 없다. 이 결정은 그 사실을 **확정**하는 것이지 발견하는 것이 아니다
- D21의 `CONFLICT`를 `save_event`는 발신하지 않는다. v1의 유일한 발신자는 D32의 ingest 락 거절이다
- **대가는 남는다.** HTTP 재시도 한 번이 `total`과 `repeat_causes`를 부풀린다.
  Q18이 지적한 해가 해소된 것이 아니라 **받아들여진 것**이다. 문서에 그렇게 적는다

### D25 검증 세부

**`project`** — 레지스트리를 두지 않는다. D5는 문자열이고, `project`→경로 매핑(Q20)은 7단계에서 필요하다.
지금 레지스트리를 만들면 7단계를 4단계로 끌어오는 것이다.

```text
앞뒤 공백 제거 → 빈 값이면 VALIDATION
64자 초과 VALIDATION · 공백/슬래시/역슬래시/NUL 포함 VALIDATION
그 외에는 그대로 저장한다 (대소문자 구분)
```

케이스 폴딩을 하지 않는다. `sillok`과 `Sillok`이 다른 프로젝트가 되는 것은 못생겼지만,
슬러그 알파벳을 지금 발명하는 것이 더 나쁘다.

**시각** — `occurred_at`·`resolved_at`은 `timestamptz`다. **오프셋 없는 문자열을 거절한다**(`VALIDATION`).
`Z` 또는 `±HH:MM`이 있어야 하고 날짜만 있는 값도 거절한다. 드라이버가 접속 TimeZone으로 해석하게 두면
Compose에서 우연히 UTC가 되는 것이지 계약이 아니다.

**`resolved_at >= occurred_at`** — 서비스에서 검사하고 `VALIDATION`으로 거절한다.
CHECK로 걸면 Postgres 예외가 되고 D21이 그것을 `INTERNAL 500`으로 접는다 — 클라이언트 입력 문제인데 서버 결함으로 보고된다.

**`title` 상한 200자** — **새 사실이다.** 지금까지 어디에도 없었다. `summary` 2000자와 같은 자리에 적는다.

**`source`를 생략하면 `agent`다.** DDL의 컬럼 기본값과 같은 값이고, 서비스가 그 값을 채워 넣는다.

**DDL에 CHECK를 넣지 않는다.** enum은 서비스에만 둔다. Skill의 값이 바뀔 때 마이그레이션이 되지 않게 하려는 것이다.
넣기로 한다면 `002`를 고치면 안 된다 — 이미 적용된 `CREATE TABLE IF NOT EXISTS`는 제약을 추가하지 않는다.
그리고 Postgres에는 `ADD CONSTRAINT IF NOT EXISTS`가 없으므로 D17의 멱등을 지키려면 카탈로그를 직접 본다:

```sql
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'kb_events_kind_check') THEN
    ALTER TABLE kb_events ADD CONSTRAINT kb_events_kind_check
      CHECK (kind IN ('success','failure','incident','decision'));
  END IF;
END $$;
```

`DROP CONSTRAINT IF EXISTS` 후 재추가는 매 기동마다 배타 락과 재검증을 건다. 쓰지 않는다.

### D23–D25 선택지

| ID | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D23 | 예시 JSON 그대로 | `module`+임계값+`avg_resolution_seconds` | Skill 3종 키를 JSON 키로 | A는 `?module=` 없이 부르면 Skill 트리와 어긋나고 `AVG`가 죽은 근거로 남는다. C는 `project`를 매 행에 복제한다 |
| D24 | 클라이언트 `idempotency_key` + 재생 | 필수 필드 내용 해시 | 중복을 받아들인다 | **B는 D11을 파괴한다.** A는 `003`이 필요하고 MCP 모델이 안정된 키를 만들어야 효과가 있다 |
| D25 | 서비스 검증만 | 서비스 + DDL CHECK | 프로젝트 레지스트리 + FK | B는 CHECK 위반이 `INTERNAL`로 새고 enum 변경이 마이그레이션이 된다. C는 Q20이 열린 채 7단계를 끌어온다 |

## D26 — 저장소를 공개한다 (2026-08-31 확정)

| ID | 선택 | 결정 내용 | 개정 대상 |
|---|---|---|---|
| D26 | — | GitHub 저장소를 **공개**로 전환한다 | D15의 `비공개` |

**D15를 부분 개정하는 첫 결정이다.** D15의 두 축 중 `비공개`만 뒤집고 `개인 도구`(제품이 아니라
한 사람이 쓰는 도구)는 그대로 둔다. 로드맵·지원·하위호환 약속이 생기는 것이 아니다.

### 무엇이 바뀌지 않는가

- **D7 그대로.** 저장소 공개는 *서비스* 노출이 아니다. Service는 여전히 `127.0.0.1`에 붙고
  외부에 열 때만 Bearer를 요구한다. `5432`도 계속 게시하지 않는다 (D16)
- **D16 그대로.** 비밀은 env로만. `.env`는 `.gitignore`에 있고 `.env.example`은 빈 자리표시자다
- **D22 그대로.** `profiles` 게이트 test 서비스의 근거는 "기본 `up`의 제품 스택"이지 공개 여부가 아니다

### 공개 전에 확인한 것 (실측)

```text
히스토리에 커밋된 .env / *.pem / secrets  없음
sk- · ghp- · PRIVATE KEY 패턴            없음 (전 히스토리)
OPENAI_API_KEY                            .env.example 에 빈 값
POSTGRES_PASSWORD=sillok                  문서화된 로컬 자리표시자
```

**커밋 히스토리의 개인 이메일은 공개 전에 GitHub noreply 주소로 재작성했다.**
공개 후에는 클론·캐시가 남아 되돌릴 수 없으므로 순서를 지켰다.
그 결과 모든 커밋 해시가 바뀌었고, 이전 PR 본문이 인용한 해시는 더 이상 해석되지 않는다.

## D27 — MIT 라이선스와 영문 우선 README (2026-08-31 확정)

| ID | 선택 | 결정 내용 |
|---|---|---|
| D27 | A | **MIT.** README는 영문이 정본이고 [README.ko.md](../README.ko.md)가 한국어 사본이다 |

**라이선스가 없으면 공개돼 있어도 모든 권리가 유보된다** — 읽는 것 말고는 아무것도 할 수 없다.
D26이 열어 둔 자리를 채운다. 아무도 의존하기 전인 지금이 고르기 가장 쉬운 시점이다.

| A | B | C | 버린 이유 |
|---|---|---|---|
| MIT | Apache-2.0 | 라이선스 없음 유지 | B는 특허 조항이 필요할 때의 선택이다. 이 도구는 특허 표면이 없고 MIT가 더 짧고 널리 읽힌다. C는 D26의 "공개" 를 사실상 무의미하게 만든다 |

### README는 영문이 정본이다

방문자는 영문을 먼저 본다. 프로젝트의 나머지 문서는 전부 한국어이고 **그대로 둔다** —
번역본을 늘리면 감사에서 1위였던 재발 부류(사본이 낡는 것)를 문서 수만큼 복제하게 된다.

- [README.md](../README.md) — **정본.** 영문
- [README.ko.md](../README.ko.md) — 한국어 사본. 어긋나면 영문이 이긴다
- `docs/**`, `adr/**` — 한국어. 번역하지 않는다

### D27이 닫지 않는 것

- 기여 절차·이슈 템플릿·행동 강령은 여전히 없다. 필요해지면 그때 결정한다
- 두 README가 갈라지는 것을 막는 검사는 아직 없다. **사본이 낡는 것은 이 저장소의 알려진 실패 모드다**

### D26이 닫지 않는 것

- 공개했다고 **기여 절차·이슈 템플릿**이 생기는 것은 아니다. 필요해지면 그때 결정한다
- 라이선스는 **D27 이 MIT 로 채웠다**
- 남은 미해결 Q는 그대로다. 공개는 그 목록을 줄이지 않는다

### D23–D25가 닫지 않는 것

- **Q13** 목록·타임라인·페이지네이션. `GET /v1/events` 컬렉션을 만들지 않는다
- **Q14** 이벤트 수정 경로
- **Q12** `get_event`의 404 대 빈 결과, 프로젝트 경계 — 7단계
- **Q22 · Q23 · Q25** `repo` 의미, front matter 규칙(**절반은 D29 가 답했다**), Skill 사본 노후
- D24는 재시도 부풀림을 **해결하지 않고 받아들인다**

### D16–D20이 닫지 않는 것

- **Q20** `project` → workspace 경로 매핑. D16은 workspace 루트 **하나**의 이름만 정했다
- ~~**Q10** ingest 트랜잭션 경계와 동시 실행~~ — **D30–D32로 닫혔다**
- **Q17** MCP 도구 입력 스키마와 stdio 마운트 경로. D19는 `serve`가 둘을 같은 프로세스에서 연다는 것만 정했다
- **Q7 · Q9** 임베딩 백필과 `kb_events`의 `tsv`. D17이 `002` 다음 번호를 쓸 자리를 열어 둘 뿐이다

## D28 — `test` 서비스는 작업 트리를 마운트한다 (2026-08-31 확정)

| ID | 선택 | 결정 내용 |
|---|---|---|
| D28 | A | `test` 서비스가 `./src`·`./tests`를 읽기 전용으로 마운트한다. 이미지에 구워진 사본을 쓰지 않는다 |

**D22의 구멍이다.** `test` 스테이지는 `COPY tests ./tests`로 소스를 이미지에 굽는데
`docker compose run`은 이미지가 있으면 다시 만들지 않는다. 그래서 테스트를 새로 쓰고 돌려도
**옛 이미지가 옛 개수를 통과로 보고한다.** 실측으로 확인했다 — 검사를 하나 더한 뒤에도
`144 passed`가 그대로 나왔고, 마운트하고 나서야 `145 passed`가 됐다.

이것이 위험한 이유는 실패가 아니라 **통과**로 나오기 때문이다. 감사에서 1위였던 부류
(도구가 비명을 지르지 않는 결함)와 같고, 하필 `scripts/evidence.mjs`가 PR 증거로 인용하는 줄이다.

| A | B | C | 버린 이유 |
|---|---|---|---|
| `./src`·`./tests` 읽기 전용 마운트 | 명령에 `--build`를 붙인다 | 매번 손으로 다시 빌드한다 | B는 소스 한 줄에도 이미지를 다시 만들고 **빌드 샌드박스에 DNS가 없는 환경에서는 아예 못 돈다**(README 참조). C는 잊는 순간 같은 거짓 통과가 돌아온다 |

- 마운트는 **읽기 전용**이다. 테스트가 작업 트리를 고치지 못한다
- `.venv`는 이미지에 남는다. 의존성을 바꾸면 여전히 다시 빌드해야 하지만,
  그때는 `ImportError`로 **시끄럽게** 실패한다 — 조용한 통과가 아니다
- `api`는 마운트하지 않는다. 제품 이미지는 구워진 소스로 도는 것이 맞다

### D28이 닫지 않는 것

- **`migrations/` 도 마운트한다 (2026-09-01, D30 이 `003` 을 더하면서).** D28 이 예고한 자리가
  그대로 났다 — `003` 을 만들고 커밋된 명령을 돌렸더니 이미지 안에는 `001`·`002` 뿐이었고
  `files_deleted` 컬럼이 없는 채로 검사가 통과했다. `./migrations` 를 읽기 전용으로 더한다.
- **pytest 는 더 이상 `COPY src`·`COPY tests`·`COPY migrations` 를 목격하지 않는다.** 이미지가 소스를 제대로
  담았는지는 이제 검사가 아니라 재빌드로만 드러난다. 조용한 통과를 없애려고 치른 값이고,
  이 결정이 고른 쪽이다. `pyproject.toml`·`uv.lock` 은 마운트하지 않는다
- 의존성 변경 시 재빌드를 강제하는 검사는 없다. `uv.lock`이 바뀌면 사람이 다시 빌드한다
- 테스트가 제품 `db_data` 볼륨을 함께 쓰는 문제(D22)는 그대로다

## D29 — 루트 `README*`는 front matter 를 갖지 않는다 (2026-09-01 확정)

| ID | 선택 | 결정 내용 |
|---|---|---|
| D29 | A | 루트 `README*`에서 YAML front matter 를 **제거한다.** `kb_documents` 의 네 필드는 ingest 가 경로와 본문에서 유도한다. D9 색인 경로는 그대로다 |

**GitHub 은 front matter 를 숨기지 않고 표로 렌더한다.** 저장소 첫 화면에서 제목보다 위에 4행 표가 먼저 나온다 —
방문자 전원이 보고, 프로젝트에 대해 아무것도 말해 주지 않는다. D26 이 공개로 돌린 이유를 그 표가 스스로 깎는다.

값을 지키려고 치르는 비용도 아니다. **v1 에는 `title` 을 돌려주는 문서 API 가 없다** — `search_docs` 응답 항목은
`path`·`heading_path`·`excerpt`·`commit_sha`·`status`·`score` 이고([service-and-mcp.md](../docs/service-and-mcp.md)),
v1 이후 문서 목록도 `path`·`status`·`indexed_at` 이다. 그 표가 매일 보여 주는 네 값은 지금 어느 소비자에게도 닿지 않는다.

### 실측 — GitHub 이 무엇을 렌더하는가

```bash
gh api repos/xzawed/Sillok/readme -H "Accept: application/vnd.github.html+json"
```

```html
<div id="readme" class="md" data-path="README.md"><article class="markdown-body …">
<markdown-accessiblity-table><table><tbody>
  <tr><th>title</th><td>Sillok</td></tr>
  <tr><th>doc_type</th><td>readme</td></tr>
  <tr><th>status</th><td>current</td></tr>
  <tr><th>module</th><td></td></tr>
</tbody></table></markdown-accessiblity-table>
…
<h1 class="heading-element">Sillok · 실록</h1>
```

표가 `<h1>` **앞**에 있다. `module: null` 은 빈 칸으로 렌더돼 뜻 없는 행이 하나 더 붙는다. `README.ko.md` 도 같다.
**렌더러 설정으로 끄는 방법은 없다 — 파일에서 빼는 것이 유일한 수단이다.**

| A | B | C | D | 버린 이유 |
|---|---|---|---|---|
| 제거 + 유도 | 그대로 두고 감수한다 | README 를 색인에서 뺀다 (D9 개정) | HTML 주석으로 감싼다 | B는 **얻는 것 없이** 첫 화면을 낸다 — 네 값의 소비자가 v1 에 없다. C는 잡음을 없애려고 신호를 버린다. README 는 프로젝트를 한 화면으로 설명하는 문서이고, D9 경로 목록은 여러 곳에 복제돼 있으며, "이 저장소 자신을 첫 ingest 스모크 대상으로 쓴다"는 서약도 얇아진다. D는 `^---` 파서가 못 읽으므로 **더 이상 front matter 가 아니다** — 규약도 게이트도 그 값을 지키지 못한 채 눈에 안 보이는 곳에서 낡는다. 이 저장소의 1위 실패 모드를 하나 새로 만든다 |

### 왜 `docs/**`·`adr/**` 는 그대로 두는가

**그 문서들은 방문자가 처음 보는 얼굴이 아니다.** 저장소 첫 화면에 렌더되는 파일은 루트 `README*` 뿐이고,
그 아래 문서는 링크를 따라 들어간 사람만 본다 — 그 사람은 이미 문맥이 있어 상단 표를 잡음이 아니라 메타데이터로 읽는다.

게다가 그쪽 값은 **경로에서 유도되지 않는다.** `doc_type` 이 `api`·`schema`·`other` 로 갈리고 `status` 도 문서마다 달라질 수 있다.
파일이 스스로 선언하는 것이 맞는 자리다.

**front matter 규칙의 정본은 이제 이 파일이다.** 지금까지 이 규칙을 *요구*하는 문장은 [CLAUDE.md](../CLAUDE.md) 한 줄뿐이었는데
그 파일은 스스로 "여기에 정본은 없다"고 선언한다 — 소유자 없는 사실이었다. [plan.md](../docs/plan.md) §우선순위에 따라
서열로 판정하고, 소유자를 [docs/conventions.md](../docs/conventions.md) 문서 지도에 등록한다.

### 유도 규칙 (ingest 가 따른다)

색인 대상은 두 부류다. **루트 `README*` 는 유도하고, `docs/**`·`adr/**` 는 front matter 를 읽는다.**

| 필드 | 루트 `README*` 의 값 | 근거 |
|---|---|---|
| `doc_type` | `readme` | D9 패턴에 걸린 파일은 정의상 README 다. 경로만으로 결정된다 |
| `status` | `current` | **못 박는다.** 파일 안팎에 status 신호가 없다. DDL 기본값과 같고 지금 값과도 같다 |
| `module` | NULL | 컬럼이 nullable 이고 색인 문서 중 non-null `module` 은 하나도 없다. 잃는 정보가 0 이다 |
| `title` | **코드 펜스 밖 첫 `# ` 제목의 텍스트.** 없으면 NULL | 실측: 두 README 모두 `# Sillok · 실록` |

- **`title` 만은 지금 값을 재현하지 못한다.** 지금은 `Sillok` 과 `Sillok (한국어)` 인데 H1 이 글자까지 같아서
  **두 행이 같은 제목을 갖고 `(한국어)` 는 소멸한다.** 받아들인다 — 언어는 `path` 에 그대로 살아 있고,
  D27 이 정한 대로 둘은 같은 문서의 정본과 사본이다. 파일명 유도는 프로젝트 이름을 잃고,
  `.ko` 를 언어로 읽는 규칙은 어느 문서에도 없다. 경로→제목 대응표를 따로 두는 안은
  front matter 를 파일 밖으로 옮긴 것일 뿐이라 버렸다
- H1 은 **줄 단위로 찾는다.** `<div align="center">` 같은 HTML 블록은 지나가고, 코드 펜스 안의 `# ` 는 제목이 아니다.
  인라인 마크업은 벗기고 텍스트만 쓴다
- **HTML 블록은 빈 줄에서 끝난다** — `</div>` 를 기다리지 않는다 (CommonMark 6형). 두 README 가 정확히 그 모양이라
  `<div align="center">` · 빈 줄 · `# Sillok · 실록` 로 이어지고 그 H1 이 제목이다.
  `</div>` 까지 건너뛰는 구현은 제목을 놓쳐 NULL 을 넣는다 — 추측하지 않도록 여기 적는다
- `kb_documents.title` 에 길이 상한을 두지 않는다. D25 의 `title` 200자는 `kb_events` 의 것이지 여기가 아니다
- **`doc_type` enum 에서 `readme` 를 빼지 않는다.** enum 은 [data-model.md](../docs/data-model.md) 가 소유하고,
  ingest 가 루트 README 에 경로 기준으로 그 값을 부여한다. 선언하는 파일이 없어졌을 뿐 값은 살아 있다

### 문서 게이트는 반대 방향도 본다

검사 3(색인 대상은 front matter 를 갖는다)에 루트 `README*` 예외를 뚫는다. **예외만 뚫고 끝내지 않는다** —
새 검사가 **루트 `README*` 에 front matter 가 있으면 실패**시킨다.

**`AGENTS.md`·`CLAUDE.md` 를 색인하지 않는지 보는 기존 양방향 검사와 같은 이유다.** 한쪽만 보면 0건이 정상인지
버그인지 구분할 수 없다. 예외를 뚫어 놓고 반대 방향을 안 보면, 누군가 편의로 front matter 를 되살렸을 때
게이트가 초록불로 통과시키고 GitHub 첫 화면에 표가 돌아온다.

- 예외는 **루트 한정**이다. `docs/README.md` 같은 사본은 `docs/` 패턴에 걸리므로 여전히 front matter 가 필수다
- 색인 대상에 루트 `README*` 가 **하나도 없으면 실패**한다. 그렇지 않으면 D9 패턴이 깨졌을 때
  새 검사가 "볼 것이 없어서 통과"로 조용히 죽는다
- **고장 주입이 같은 변경에 따라온다.** 지금까지 검사 3 에 대한 주입은 하나도 없었다 —
  예외를 너무 넓게 뚫어도 아무도 비명을 지르지 않는 상태였다
- 게이트 출력의 `doc_type` 분포에서 `readme` 두 건이 빠진다. **게이트가 유도 규칙을 복제해서 채우지 않는다** —
  ingest 와 게이트에 같은 규칙이 두 벌 생기면 그것이 곧 낡는 사본이다. 대신 면제된 파일 목록을 그대로 출력해 드러낸다

### D9 는 바뀌지 않는다

**루트 `README*` 는 여전히 색인 대상이다.** 검색으로 찾히고, `kb_documents` 에 행을 갖고, 첫 ingest 스모크 대상에 그대로 들어간다.
바뀌는 것은 "색인 대상 문서는 front matter 를 갖는다"는 **등식**이지 색인 경로가 아니다.

### D29가 닫지 않는 것

- **Q23 은 닫히지 않는다.** D29 는 네 필드를 *어디서* 얻는지만 정했다. `draft`·`superseded`·`stale` 을 **언제** 붙이는지는
  여전히 어느 문서에도 없다. 그 결과 루트 README 는 이제 **영원히 `current`** 다 — 해결한 것이 아니라 받아들인 것이다 (D24 선례)
- **`title` 이 두 README 에서 같아진다.** v1 에는 소비자가 없어 지금 비용이 0 이지만, 문서 목록 UI 가 생기면
  같은 제목의 줄이 둘 나온다. 그때 `path` 를 함께 보여 주는 것으로 충분한지 다시 본다
- **다른 렌더러는 확인하지 않았다.** `gh api` 와 github.com 웹만 봤다. GitLab·Gitea·로컬 뷰어가 front matter 를
  어떻게 다루는지는 이 결정의 근거가 아니다
- **ingest 는 아직 없다 (5단계).** 유도 규칙은 계약일 뿐 한 번도 실행된 적이 없다 —
  5단계가 구현할 때까지 이 결정을 지키는 것은 문서 게이트뿐이다
- 두 README 가 갈라지는 것을 막는 검사는 여전히 없다. D27 이 남긴 그대로다
- **Q22** (`kb_documents.repo` 의 의미) 는 이 결정과 무관하게 열려 있다

## D30 — ingest 의 결정론(확장자 · 해시 · `commit_sha` · 삭제 · 청크) (2026-09-01 확정)

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D30 | A | `.md` 만 · 정규화한 텍스트의 SHA-256 · `commit_sha` 는 비운다 · 전체 스캔이 곧 삭제 판정 · 헤딩 다음 블록 경계로 청크 | Q6 |

**같은 커밋을 두 OS 에서 색인하면 문서 전부가 `변경`으로 판정된다.** 이 저장소의 마크다운은
인덱스가 LF 이고 작업 트리가 CRLF 다 — `.gitattributes` 가 `*.py`·`*.sql`·`*.yml` 은 LF 로 고정하는데
`*.md` 에는 규칙이 없다. 그런데 D9 색인 대상이 정확히 그 `*.md` 다.
`해시 비교 후 변경분만`([service-and-mcp.md](../docs/service-and-mcp.md) §색인)이라는 계약이
무엇의 해시인지 정하지 않은 채로 있으면, 리눅스 컨테이너에서 한 번 색인하고 Windows 호스트에서
한 번 돌리는 것만으로 매번 전량 재색인이 된다. 청크도 임베딩도 다시 만든다.

### 실측 — 줄끝과 git

```text
$ git ls-files --eol README.md docs/plan.md adr/0001-v1-stack-decisions.md
i/lf    w/crlf  attr/                   README.md
i/lf    w/crlf  attr/                   docs/plan.md
i/lf    w/crlf  attr/                   adr/0001-v1-stack-decisions.md

$ sha256sum README.md                 # 작업 트리 그대로
18ede5ad3e1d23666a5d621e707b3148351740ac89a12690036ece16936de4e7
$ tr -d CR < README.md | sha256sum    # CRLF -> LF
18be401ed7d53f95a85f145e62412a5bfcfa784a7a2800e0e8f076aa0f983f85

$ docker run --rm python:3.12-slim sh -c "command -v git || echo NO-git-binary"
NO-git-binary
```

같은 커밋의 같은 파일이 **두 해시**를 갖는다. 그리고 색인이 도는 이미지(`python:3.12-slim`)에는
git 이 없다 — `.dockerignore` 가 `.git` 을 이미지에서 빼고 `uv.lock` 에 git 라이브러리도 없다.

### 실측 — 이 규칙으로 이 저장소를 자른 결과

```text
파일                                    청크    최대   >1200   hp=NULL
adr/0001-v1-stack-decisions.md            49    1042       0         0
docs/conventions.md                        9    1330       1         0
docs/data-model.md                         9    1068       0         0
docs/open-questions.md                    10    1076       0         0
docs/plan.md                              14    1192       0         0
docs/service-and-mcp.md                   13    1030       0         0
docs/skills/sillok-storage/SKILL.md        8     556       0         0
docs/spec.md                              12     641       0         0
README.ko.md                              13    1116       0         1
README.md                                 14    1195       0         1
합계                                     151    1330       1         2

중앙값 408자 · 평균 489자 · 최소 20자 · 200자 미만 35
D9 경로 아래 비-.md 파일 0 · 최장 코드 펜스 999자 · 최장 표 1330자 · 최장 줄 357자
```

### D30 선택지

| ID | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D30 확장자 | `.md` 만 | D9 경로의 모든 파일 | 확장자 목록을 설정으로 | B는 이미지·잠금 파일까지 문서로 만들고 `to_tsvector` 에 이진 잡음을 넣는다. C는 D19 가 "색인 경로는 플래그가 아니다"로 이미 닫은 문을 확장자로 다시 연다 |
| D30 해시 | 정규화 후 SHA-256 | 원문 바이트 그대로 | git blob 해시(SHA-1) | B는 위 실측 그대로 OS 마다 다른 값을 낸다. C는 git 자신의 eol 정규화에 딸려 있어 체크아웃마다 달라지고, 재현하려면 `.gitattributes` 해석을 다시 구현해야 한다 |
| D30 `commit_sha` | 비운다 | HEAD 를 읽는다 | 파일별 마지막 커밋 | B·C 둘 다 이미지에 git 을 넣거나 의존성을 더해야 하고(D28 재빌드), **dirty 트리에서는 거짓말이다** — 해시하는 것은 디스크의 내용인데 붙이는 것은 커밋된 내용의 이름이다. C는 파일마다 git 을 한 번씩 더 돈다 |
| D30 삭제 | 전체 스캔 + 물리 삭제 | 소프트 삭제 컬럼 | 변경 목록만 받고 삭제하지 않는다 | B는 컬럼을 더해야 하고, 문서 인덱스는 Git 에서 언제든 다시 만들 수 있어 원장이 아니다. C는 사라진 파일이 인덱스에 영원히 남아 **검색이 조용히 옛것을 돌려준다** |
| D30 청크 | 헤딩 → 블록 채우기, 블록은 안 쪼갠다 | 고정 문자 수 + overlap | 토큰 수 기준 | B는 코드 펜스와 표를 한가운데서 자른다 — 실측 최장 표가 1330자라 실제로 잘린다. C는 토크나이저 의존성을 v1 에 들이고, D2 모델을 바꾸면 경계까지 바뀐다 |

### 1. 무엇을 먹는가 — `.md` 하나

- **D9 경로 안에서 이름이 `.md` 로 끝나는 파일만 먹는다.** 대소문자를 접지 않는다.
- `scripts/check-layout.mjs` 의 `endsWith` 검사와 **글자까지 같게** 둔다.
  게이트와 ingest 가 다른 집합을 보면 "게이트는 초록인데 색인은 비어 있는" 부류가 생긴다.
- **확장자 필터의 정본은 이 결정이고 그 파일이 사본이다.** 아래 `이 값들이 복제된 위치` 표에
  그 파일을 더한다. 규칙이 두 벌인 것보다 나쁜 것은 어느 쪽이 정본인지 안 적는 것이다.
- 그래서 `docs/skills/**` 아래 이미지·JSON·예제 파일, 확장자 없는 `README` 는 색인되지 않는다.
  `.env.example` 은 애초에 D9 경로 밖이다. `.markdown`·`.mdx` 를 더하지 않는다 —
  지금 0건이고, 더하는 순간 게이트와 갈라진다.
- **`.git` 과 `node_modules` 디렉토리에는 들어가지 않는다** — 게이트의 walk 와 같다.
- **심볼릭 링크는 따라가지 않는다.** workspace 밖을 가리키는 링크 하나가 D9 경로를 무의미하게 만든다.
- **파일 크기 상한을 두지 않는다.** 상한을 두면 "무엇이 잘리는가"를 다시 정해야 하고(D23),
  D9 경로가 이미 사람이 쓴 문서로 범위를 좁히고 있다.
- **먹지 않은 파일은 조용히 사라지지 않는다.** D9 경로 안에서 제외한 것은
  `skipped[]`(경로 + 이유)로 응답과 CLI 출력에 실린다. 이유는 `not-md` 와 `symlink` 둘뿐이다.
- **제외(skip)는 삭제 후보가 아니다.** 삭제 판정은 `.md` 인데 사라진 것만 본다.
  이 한 줄이 없으면 파일 하나를 심볼릭 링크로 바꾸는 것만으로 그 문서가 인덱스에서 지워진다.
- **`path` 는 workspace 루트 기준 상대 경로이고 구분자는 슬래시다.** 선행 `./` 를 붙이지 않고
  Windows 의 역슬래시를 슬래시로 바꾼다. 그러지 않으면 같은 레포가 OS 마다 다른 문서 정체성을 갖는다
  (`UNIQUE (project, repo, path)`).
- **스캔 순서는 `path` 의 UTF-8 바이트 오름차순이다.** 파일시스템이 주는 순서에 기대지 않는다.
- **`repo` 에는 값을 넣지 않는다** — DDL 기본값 그대로다. Q22 는 그대로 열려 있다.

### 2. `content_hash` — 정규화한 텍스트의 SHA-256

- 파일 바이트를 **UTF-8 로 디코드한다.** 실패하면 그 파일만 건너뛰지 않고 **run 을 실패로 끝낸다** —
  조용히 빠진 문서는 검색 0건과 구분되지 않는다.
- 정규화는 둘뿐이다: **선행 BOM(U+FEFF) 제거**, **CRLF 와 홀로 있는 CR 을 LF 로.**
  그 밖에는 아무것도 하지 않는다 — 후행 공백을 다듬지 않고 마지막 개행을 더하지도 빼지도 않는다.
- BOM 을 먼저 벗기는 것은 게이트의 front matter 정규식이 선행 BOM 을 허용하기 때문이다(D29).
  벗기지 않으면 같은 문서를 게이트는 읽고 ingest 는 못 읽는다.
- **`content_hash` = 그 텍스트를 UTF-8 로 다시 인코드한 바이트의 SHA-256, 소문자 16진 64자.**
- **해시는 본문만의 함수다.** `path`·`project`·`commit_sha` 를 섞지 않는다 —
  섞으면 체크아웃 한 번이 전 문서를 변경으로 만든다.
- 해시 대상은 **front matter 를 포함한 전문**이다. `doc_type` 이 바뀌면 헤더도 갱신돼야 한다.
- **변경 판정의 근거는 `content_hash` 하나다.** `source_mtime` 도 파일 크기도 쓰지 않는다 —
  mtime 은 클론할 때마다 새로 찍힌다.
- 해시가 같으면 그 문서에 아무 쓰기도 하지 않는다. 그래서 `indexed_at` 은 "마지막으로 스캔한 시각"이 아니라
  **"마지막으로 내용이 바뀌어 다시 색인한 시각"** 이다.
- 해시가 다르면 문서 행을 `INSERT … ON CONFLICT (project, repo, path) DO UPDATE` 로 갱신하면서
  **`indexed_at = now()` 를 명시한다.** `DEFAULT now()` 는 INSERT 에만 걸린다 —
  빠뜨리면 최초 색인 시각으로 굳는다. 이 upsert 형태 자체가 계약이다:
  D21 의 `CONFLICT` 표가 바로 그 upsert 를 근거로 이 표면을 `CONFLICT` 에서 뺐다.
- `source_mtime` 에는 스캔 시점의 파일 mtime 을 **UTC 로** 넣는다. 컬럼이 `timestamptz` 라
  naive datetime 을 넣으면 세션 시간대로 해석돼 환경마다 값이 달라진다(D23 결정성 선례).
  **판정에 쓰지 않는 진단값이다.**
- `token_count` 는 문서·청크 둘 다 **NULL 로 둔다.** 토크나이저를 v1 에 들이지 않는다.
- **디코드 실패의 시점.** 읽기·해시·청크는 파일 하나 안에서 끝나고 그 뒤에 트랜잭션이 열린다(D32).
  따라서 디코드 실패는 그 파일에 아무것도 쓰기 전에 일어나고, **앞선 파일은 이미 커밋돼 있다.**
  그 run 은 `failed` 로 끝나고 **삭제 반영을 하지 않는다** — 못 읽은 파일과 사라진 파일을 구분할 수 없다.

### 3. `commit_sha` — v1 은 채우지 않는다

- **ingest 는 `commit_sha` 를 채우지 않는다.** `kb_documents.commit_sha` 는 INSERT 컬럼 목록에 넣지 않아
  DDL 기본값인 빈 문자열로 남고, `kb_ingest_runs.commit_sha` 는 NULL 이다.
- `kb_documents.commit_sha` 는 `NOT NULL` 이라 **NULL 이 애초에 허용되지 않는다.** 빈 문자열이 곧 부재다.
  두 컬럼이 부재를 다르게 적는 것은 DDL 이 이미 그렇게 정한 것이고, 맞추려면 새 마이그레이션이다 — 하지 않는다.
- 바인드 마운트(`docker-compose.yml` 의 `.:/workspace:ro`)에는 `.git` 이 들어오지만 읽을 도구가 없다.
  `.git/HEAD` 를 손으로 파싱하는 것은 packed-refs·worktree·얕은 클론까지 git 을 다시 구현하는 일이다.
- **더 큰 이유는 정확성이다.** ingest 가 해시하는 것은 디스크의 내용이고 HEAD 가 가리키는 것은 커밋된 내용이다.
  둘이 다를 때 `commit_sha` 를 붙이면 "그 커밋에 이 내용이 있었다"는 **없는 사실**을 만든다.
- 소비자도 아직 없다. `search_docs` 응답의 `commit_sha` 는 6단계에서 생기고 **v1 내내 빈 문자열로 나간다.**
  필드를 지우지 않는다 — 계약이고, 값이 생기면 채우는 자리다.

### 4. 삭제된 파일 — 전체 스캔이 곧 삭제 판정이다

- **`sillok ingest` 는 언제나 전체 스캔이다.** 스캔이 만든 `path` 집합이 그 `(project, repo)` 의 전부다.
- DB 에 있고 스캔에 없는 행은 **물리 삭제**한다. 청크는 FK 의 `ON DELETE CASCADE` 가 따라 지운다.
  소프트 삭제를 쓰지 않는다 — 그 컬럼이 없고, 문서 인덱스는 Git 에서 언제든 다시 만들 수 있다.
- **스캔 결과가 0건이면 아무것도 지우지 않고 run 을 실패로 끝낸다.** `--workspace` 를 잘못 준 한 번이
  그 project 의 문서 인덱스를 통째로 지우는 것이 이 결정의 유일한 파국이고, 0건 가드가 그것을 막는다.
  게이트의 검사 1 과 같은 논리다 — 색인 대상 0건은 정상이 아니라 신호다.
- 문서를 정말 전부 지운 커밋을 색인해도 그때 실패한다. 받아들인다 — 사람이 판단할 자리다.
- **0건 가드는 전체 오지정만 막는다.** `.md` 가 하나라도 있는 잘못된 workspace 는 나머지를 전부 지운다.
  그래서 삭제 수를 다른 카운터에 접어 두지 않고 **`files_deleted` 로 따로 센다** — 아래 §6.
- 재색인(해시가 다른 문서)은 **문서 행을 유지한 채** 청크를 `DELETE FROM kb_chunks WHERE document_id = …`
  로 지우고 다시 넣는다. `ON DELETE CASCADE` 는 문서 행이 지워질 때만 발화한다 —
  재색인 경로에서는 발화하지 않는다. 이것이 `(project, repo, path)` 단위 재색인의 실제 모양이다.
- 순서를 못 박는다: **스캔 → `path` 오름차순으로 문서 upsert → 마지막에 삭제.**
- **`POST /v1/ingest` 는 변경 파일 목록을 받지 않는다.** 본문은 CLI 의 인자와 같다 —
  `project` 필수, `workspace` 선택. 부분 목록에서는 "목록에 없다"가 *안 바뀌었다*인지 *사라졌다*인지
  구분되지 않아 삭제 판정이 성립하지 않는다. [service-and-mcp.md](../docs/service-and-mcp.md) §색인의
  옛 한 줄을 이 결정이 좁힌다. **옛 문구는 게이트의 `RETIRED` 에 등록한다.**

### 5. 청크 경계 — 헤딩이 자르고 블록이 지킨다

- 단위는 **문자**다. 파이썬 `str` 의 길이, 즉 유니코드 코드포인트이고 한글 한 글자가 1 이다.
- **front matter 는 청크 본문에서 뺀다.** 네 값은 이미 `kb_documents` 컬럼이고(D29),
  남기면 모든 문서의 첫 청크가 같은 키워드를 갖는다. 해시는 전문이고 청크는 그 나머지다.
- **1차 분할은 ATX 헤딩이다.** 코드 펜스 밖의 `#` 로 시작하는 줄에서 자른다.
  setext 제목(밑줄식)은 제목으로 보지 않는다 — front matter 를 뗀 자리와 수평선이
  줄 스캐너에서 제목처럼 보이는 것을 막는다.
- 헤딩 줄 자체는 `content` 에 넣지 않는다 — `heading_path` 가 갖고, `tsv` 생성식이
  헤딩과 본문을 이어 붙이므로 검색에서 잃는 것이 없다. 넣으면 제목 토큰이 두 번 들어간다.
- `heading_path` 는 그 절까지의 헤딩을 상위부터 ` > ` 로 이은 것이다. 첫 헤딩 앞 서두는 NULL 이다.
  헤딩 텍스트에서 인라인 마크업을 벗기는 규칙은 D29 가 `title` 에 정한 것과 같다.
  **레벨을 건너뛰면 빈 칸을 채우지 않고 스택에 그대로 쌓는다** — 없는 제목을 만들지 않는다.
  길이 상한을 두지 않는다. 형식의 정본은 [service-and-mcp.md](../docs/service-and-mcp.md) 다.
- **2차 분할은 블록 채우기다.** 블록은 빈 줄로 구분되는 연속 줄 뭉치이고, 코드 펜스는 안에 빈 줄이 있어도
  한 블록이다. 절의 블록을 순서대로 담다가 **1200자**를 넘으면 새 청크를 시작한다.
  담은 것이 있는데 다음 블록을 더하면 상한을 넘을 때는 **그 블록 앞에서 끊는다.**
- **블록은 쪼개지 않는다. 다만 천장이 있다.** 블록 하나가 **4000자**를 넘으면 그 안에서 줄 경계로 나눈다.
  줄 하나가 그것마저 넘으면 **그 줄은 그대로 한 청크가 된다** — 문자 단위로 자르는 경로는 만들지 않는다.
  실측 최장 줄은 357자이고 최장 블록은 1330자라 오늘은 어느 쪽도 걸리지 않지만,
  천장이 없으면 거대한 코드 펜스 하나가 핵심 불변식("질의당 토큰은 거의 고정")을 깬다.
- **하한을 두지 않는다.** 헤딩 우선이면 짧은 절이 흔하다 — 위 실측에서 중앙값 408자, 200자 미만이 35 다.
  짧은 청크를 이웃과 합치면 `heading_path` 가 어느 절의 것인지 모호해진다.
- **overlap 을 두지 않는다.** 경계가 언제나 헤딩이거나 빈 줄이라 문장이 잘리지 않는다.
  overlap 은 문장 중간을 자를 때의 손실을 메우는 장치이고, 여기서는 같은 문단을 두 번 임베딩해
  비용만 늘리며 같은 문서의 인접 청크가 함께 걸리는 문제(Q8, 6단계)를 키운다.
- 앞의 두 줄이 [data-model.md](../docs/data-model.md) 의 권장 청크 줄을 좁힌다.
  그 줄은 권장이고 이 결정이 계약이다 — 하위 문서를 이 결정에 맞춘다.
- `chunk_idx` 는 문서 안 등장 순서로 0부터다. `UNIQUE (document_id, chunk_idx)` 를 그대로 쓴다.
- 본문이 비어 있는 절은 청크를 만들지 않는다. 문서 전체가 헤딩뿐이면 `kb_documents` 행만 남고 청크는 0 이다.
- **`tsv` 는 INSERT 컬럼 목록에 넣지 않는다.** `GENERATED ALWAYS … STORED` 라 쓰려 들면 오류다.

### 6. 응답과 카운터

[service-and-mcp.md](../docs/service-and-mcp.md) §색인은 8개 엔드포인트 중 **유일하게 응답 예시가 없는 자리**였다.
이 결정이 채운다. Service 함수는 같은 dict 를 돌려주고 CLI 는 그것을 한 줄로 찍는다.

```json
{ "ok": true, "data": {
  "run_id": 7, "project": "sillok", "status": "ok", "commit_sha": "",
  "files_seen": 10, "files_changed": 3, "files_deleted": 0, "chunks_upserted": 41,
  "chunks_embedded": 0, "chunks_pending": 151,
  "skipped": [{ "path": "docs/skills/sillok-storage/example.json", "reason": "not-md" }]
} }
```

- `files_seen` 은 스캔이 본 `.md` 수다. `skipped` 는 여기에 포함하지 않는다.
- `files_changed` 는 새로 넣은 것 + 해시가 다른 것이다. **삭제는 포함하지 않는다** — `files_deleted` 가 센다.
- `chunks_upserted` 는 이번 run 이 INSERT 한 청크 수다. 지운 청크는 세지 않는다.
- `chunks_embedded`·`chunks_pending` 은 D31 이 소유한다.
- `commit_sha` 는 v1 내내 빈 문자열이다 (§3).
- **`files_deleted` 는 `kb_ingest_runs` 의 새 컬럼이다.** `migrations/003_ingest_counters.sql` 에
  `ADD COLUMN IF NOT EXISTS` 로 더한다 (D17 멱등). [data-model.md](../docs/data-model.md) 를 먼저 고친다.
  `002` 를 고치지 않는 이유는 러너가 적용 이력을 갖지 않고 매 기동마다 전부 재실행하기 때문이다 —
  이미 테이블이 있는 DB 에서는 `002` 를 고쳐도 조용히 무시된다.
- `skipped[]` 는 응답에만 있다. 컬럼으로 만들지 않는다.

### 7. front matter 파싱 — D29 가 규칙만 정하고 파서를 정하지 않았다

- `docs/**`·`adr/**` 는 front matter 를 읽는다(D29). 파서는 게이트와 같은 것으로 못 박는다 —
  세 줄표로 여닫는 블록을 잡고, 그 안에서 **첫 콜론 앞이 키, 뒤가 값**이며 값은 주석 표시 이후를 떼고
  앞뒤 공백을 벗긴 문자열이다. 따옴표를 벗기지 않는다(실측: 0건).
- 읽는 키는 `title`·`doc_type`·`status`·`module` 넷뿐이다. 나머지 키는 무시한다.
  **빈 값과 `null` 은 NULL 로 넣는다** — 색인 대상 문서가 전부 `module: null` 이라 이 한 줄이 없으면
  문자열 `"null"` 이 들어간다.
- **`doc_type`·`status` 가 taxonomy 밖이면 서비스가 거절한다.** DDL CHECK 를 더하지 않는다 — D25 그대로다.
- front matter 가 없으면 DDL 기본값을 쓰고 `title` 은 D29 의 첫 H1 규칙으로 유도한다.
  이 저장소에서는 게이트가 먼저 막지만, D5 가 말하는 다른 project 에서는 없는 것이 정상이다.

### 어겨지면 무엇이 비명을 지르는가

| 규칙 | 어겨지면 | 무엇이 무는가 |
|---|---|---|
| 확장자 `.md` | 게이트와 다른 집합을 색인한다 | **없다** — 5단계가 게이트 목록과 대조하는 검사를 만든다 |
| 정규화 후 해시 | OS 마다 전량 재색인 | **없다** — 5단계가 두 줄끝의 해시가 같은지 단언한다 |
| 0건 스캔 가드 | 잘못된 workspace 한 번이 인덱스를 지운다 | 5단계 DB 검사 (빈 디렉터리로 부르면 `failed`) |
| `path` 구분자 | 같은 레포가 OS 마다 다른 문서가 된다 | 5단계 검사가 역슬래시를 넣고 결과를 본다 |
| skip 은 삭제 후보가 아니다 | 심볼릭 링크로 바꾸면 문서가 지워진다 | 5단계 DB 검사 |
| front matter `null` → NULL | `module` 에 문자열 `"null"` 이 들어간다 | 5단계 검사 |
| 청크 천장 4000자 | 임베딩 요청 하나가 무한히 커진다 | 5단계 검사 (합성 입력) |
| `heading_path` 구분자 | 6단계 응답이 형식을 잃는다 | **없다** — 소비자가 6단계에 생긴다 |

D28 이 정한 대로, **통과 출력만으로는 규칙이 살아 있는지 알 수 없다.** 위 표에서 "없다"로 남은 셋은
5단계 구현이 검사를 만들 자리이고, 만들지 않으면 그 자체가 결함이다.

### 기존 결정과 충돌하는가

- **D9 는 바뀌지 않는다.** 확장자 필터는 D9 경로 *안*에서 거르는 규칙이지 경로 목록이 아니다.
  다만 게이트의 "D9 는 확장자·대소문자를 가리지 않는다" 주석과 틈이 생긴다 —
  D9 **경로 판정**은 여전히 가리지 않고, 그 안에서 무엇을 먹는지를 이 결정이 정한다. 주석을 그렇게 고친다.
- **D21 의 `CONFLICT` 는 D32 가 개정한다.** D30 자체는 새 발신 조건을 만들지 않는다 —
  `UNIQUE (project, repo, path)` 충돌은 upsert 로 접힌다.
- **D25 를 뒤집지 않는다.** enum 검증은 서비스에 두고 DDL 에는 아무것도 더하지 않는다.
- **D19·D20 의 CLI 계약을 넓히지 않는다.** 인자는 `--project` 와 `--workspace` 둘뿐이다.
  `--commit-sha`·`--paths`·`--since` 같은 플래그를 만들지 않는다.
- **`002` 를 고치지 않는다.** 새 컬럼은 `003` 이고 `ADD COLUMN IF NOT EXISTS` 라 멱등이다(D17).
  새 환경변수도 없고, 이 결정이 요구하는 것은 표준 라이브러리의 `hashlib` 과 `pathlib` 뿐이다.

### D30이 닫지 않는 것

- **`commit_sha` 가 비어 있는 것을 아무도 탐지하지 못한다.** 빈 값이 정상값이라 결함과 구분되지 않는다.
  채우기로 하는 결정이 그때 함께 정한다. 그때 `kb_documents` 와 `kb_ingest_runs` 의
  부재 표기 비대칭도 같이 본다
- **유니코드 정규화(NFC/NFD)를 정하지 않았다.** 같은 글자를 다르게 인코딩한 두 파일은 다른 해시를 갖는다.
  macOS 체크아웃에서 한글이 NFD 로 오는 것이 알려진 경로다. 관측되면 그때 정한다
- **해시 알고리즘을 바꾸면 전 문서가 변경으로 판정된다.** 알고리즘 이름을 어디에도 저장하지 않으므로
  바꾸는 결정이 전량 재색인을 함께 적어야 한다
- **전체 스캔의 비용을 재지 않았다.** 지금은 파일 열 개다. 수천 개가 되면 변경 목록 모드가 다시 후보가 되고,
  그때 삭제 판정을 어떻게 유지할지가 그 결정의 숙제다
- **확장자 없는 `README` 는 조용히 색인되지 않는다.** 오늘 존재하지 않고 게이트도 같은 이유로 검사하지 않는다.
  게이트가 D9 경로 안의 *색인되지 않는 파일*을 목록으로 출력하게 하는 것이 다음 후보다
  (D29 가 면제 목록에 쓴 방식)
- **`token_count` 는 v1 내내 NULL 이고 `commit_sha` 는 v1 내내 빈 문자열이다.** 네 컬럼이 정의만 있고 값이 없다
- **Q22 는 열려 있다.** `repo` 를 비워 두는 것은 의미를 정한 것이 아니라 정하지 않기로 한 것이다.
  삭제 판정의 범위가 그 컬럼에 걸려 있으므로, Q22 를 닫는 결정은 기존 행을 어떻게 옮길지 함께 정해야 한다
- **D22 가 남긴 숙제는 줄었을 뿐 닫히지 않았다** — `test` 이미지에 `docs/`·`adr/` 가 없다는 것.
  이 결정의 규칙은 대부분 순수 로직이라 `tmp_path` 로 만든 최소 workspace 트리에서 검사한다.
  작업 트리를 마운트하지 않는다 — 마운트하면 검사가 저장소의 지금 내용에 묶여 문서를 고칠 때마다 깨진다.
  남는 것은 upsert 와 삭제뿐이고 그것은 DB 검사다
- **[plan.md](../docs/plan.md) §9 의 `docker compose exec api sillok ingest` 가 그대로 도는지 확인하지 않았다.**
  `Dockerfile` 에 가상환경 경로를 PATH 에 넣는 줄이 없고 CMD 는 `uv run --no-sync` 로 우회한다.
  파일을 읽어 안 사실이고 실행해 보지는 않았다. 5단계 구현이 확인할 자리다

## D31 — 백필은 `sillok ingest` 의 마지막 패스다 (2026-09-01 확정)

[open-questions.md](../docs/open-questions.md) Q7을 마감한다. 5단계를 막던 셋 중 하나다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D31 | A | 임베딩 경로는 **하나뿐이다.** `sillok ingest` 가 매 run 끝에 그 project 의 `embedding IS NULL` 인 청크를 전부 채운다. 별도 명령도 플래그도 새 컬럼도 만들지 않고, 남은 수를 `kb_status` 가 상시 드러낸다 | Q7 |

**Q7 이 지적한 것은 미래의 위험이 아니라 이미 놓인 함정이다.**
키 없이 한 번 색인하면 `content_hash` 가 같아 다음 run 이 "변경 없음"으로 접고,
나중에 키를 넣어도 그 문서의 벡터는 영원히 NULL 이다.
그리고 그 상태에서 **아무것도 비명을 지르지 않는다** — 명령은 0 으로 끝나고,
검색은 D2 대로 키워드로 결과를 돌려주며, `kb_status` 의 다섯 필드 중 어느 것도 벡터를 보지 않는다.
감사에서 1위였던 부류(도구가 비명을 지르지 않는 결함)이고, D28 이 같은 이유로 마운트를 골랐다.

### 지금 상태 — 코드와 정본 DDL 에서 읽은 사실

```text
kb_chunks.embedding      vector(1536) nullable · 기본값 없음 · 인덱스 없음   data-model.md
kb_chunks.content        text NOT NULL — 청크 본문이 DB 에 그대로 있다        data-model.md
kb_chunks.heading_path   text — tsv 생성식이 쓰는 접두                        data-model.md
키 유무 판정             config 에 이미 있다                                 src/sillok/config.py
kb_status 응답 5필드     documents · chunks · events · last_ingest_at · zero_hit_queries
kb_events.embedding      save_event 의 INSERT 목록에 없다 — 전부 NULL 이다    src/sillok/service.py
```

**두 번째·세 번째 줄이 이 결정을 싸게 만든다.** 본문과 헤딩이 DB 에 남아 있으므로
**백필은 파일을 다시 읽지 않는다.** 워크스페이스도 Git 도 해시도 필요 없다.

### D31 선택지

| A | B | C | D | 버린 이유 |
|---|---|---|---|---|
| ingest 마지막 패스가 `embedding IS NULL` 을 채운다 | 별도 명령 | 전체 재색인 플래그 | `serve` 기동 시 자동 백필 | B는 함정을 **이름만 바꿔 남긴다** — 그 명령을 돌려야 한다는 사실을 모르면 벡터는 여전히 영원히 비어 있고, D19 의 CLI 계약에 없는 명령을 발명한다. C는 텍스트가 그대로인데 청크를 지우고 다시 넣어 `content_hash` 판정을 무의미하게 만들고 `indexed_at` 을 거짓으로 갱신하며, 역시 사람이 플래그를 기억해야 한다. D는 bind 전 기동을 외부 API 지연·요금에 묶고(D17 은 그 자리에 마이그레이션만 둔다), `--project` 가 없어 무엇을 채울지 정할 수 없다 (D5) |

### 세부 규칙

- **경로가 하나다.** ingest 는 (1) 스캔·해시·청크·`tsv` 를 쓴 뒤
  (2) 그 project 의 `embedding IS NULL` 인 청크를 채운다.
  새 청크도 그 순간 NULL 이므로 같은 패스가 집는다.
  **"최초 임베딩"이라는 두 번째 경로를 만들지 않는다** — 경로가 둘이면 입력 텍스트가 갈라져도 아무도 모른다.
  갈라질 수 없게 만드는 것이 이 선택의 핵심이다
- **입력 텍스트는 SQL 안에서 만든다.** 백필의 SELECT 가
  `coalesce(heading_path,'') || ' ' || content` 를 **서버에서** 계산해 그 문자열을 그대로 임베딩에 넘긴다.
  `kb_chunks.tsv` 생성식과 **같은 식**이라 벡터와 키워드가 같은 것을 본다.
  두 컬럼을 따로 SELECT 해 파이썬에서 이어 붙이면 같은 규칙의 **세 번째 사본**이 생기고,
  아래 검사가 DDL 과 테스트만 비교하게 되어 파이썬 쪽 이탈을 못 문다
- 그 식은 이제 두 곳에 있다 — DDL 과 백필 SELECT. **어긋나면 무엇이 비명을 지르는가:**
  DB 검사가 전 청크에 대해 `to_tsvector('simple', <백필 SELECT 의 식>) = tsv` 를 단언한다
- **대상은 run 의 `--project` 전체다.** 이번 run 에서 파일이 하나도 안 변해도 채운다.
  그것이 Q7 을 닫는 방식이다 — 키를 넣은 뒤 **평소 명령을 그대로 다시 돌리면** 채워진다.
  새로 기억할 것이 없다
- 다른 project 는 건드리지 않는다. 자기 인자 밖의 행을 고치는 명령은 조용한 부작용이다.
  `repo`·`path` 단위로 좁히는 플래그도 만들지 않는다 — D19 의 인자 목록에 없다
- **처리 순서는 `ORDER BY document_id, chunk_idx` 다.** 중간에 실패하면 어디까지 채웠는지가
  실행마다 같아야 한다 (D23 선례)
- **첫 실패에서 백필 단계를 멈춘다.** 인증·한도·요금 같은 실패는 남은 청크에서도 똑같이 실패하고,
  계속하면 실패 호출만 수백 번 더 만든다. 정렬이 완결돼 있으므로 다시 돌리면 멈춘 자리부터다.
  이 규칙이 사고가 났을 때 폭주를 막는 실질적인 상한 역할도 한다
- **이미 값이 있는 벡터는 다시 계산하지 않는다.** `embedding IS NULL` 만 본다.
  따라서 백필은 **모델 교체를 수행하지 못한다** — 옛 모델의 벡터를 그대로 둔다
- **`kb_documents` 를 건드리지 않는다.** 백필이 쓰는 문장은 `UPDATE kb_chunks SET embedding = …` 하나다.
  `content_hash`·`indexed_at`·`commit_sha` 는 그대로다 — 건드리면 "마지막 색인 시각"이 조용히 거짓이 된다.
  `tsv` 는 `GENERATED ALWAYS` 라 애초에 쓸 수 없다
- **키가 없으면 무동작이다** (D2). run 은 그대로 성공이고, 남은 수만 `kb_status` 에 남는다
- **키 없이 재색인하면 이미 있던 벡터가 사라진다.** 텍스트가 바뀐 문서는 청크를 지우고 다시 넣으므로
  벡터도 함께 사라지고 채워지지 않는다. **그것이 맞다** — 옛 벡터는 옛 텍스트의 것이고,
  남겨 두면 검색이 바뀐 문서를 옛 내용으로 맞힌다. 잃었다는 사실은 아래 필드가 드러낸다
- **차원 불일치는 DDL 이 막는다.** `vector(1536)` 컬럼이 다른 길이를 거절한다. 조용히 들어가지 않는다

### 값을 어떻게 쓰는가 — 어댑터를 쓴다

`pyproject.toml` 의 의존성에 `pgvector` 가 없고 `service.connect` 는 타입 어댑터를 등록하지 않는다.
정하지 않으면 구현자가 둘 사이에서 고른다.

- **`pgvector` 의 psycopg 어댑터를 등록해 파이썬 리스트를 그대로 바인딩한다.**
  1536 개 부동소수를 손으로 문자열 리터럴로 만들어 `::vector` 로 캐스팅하지 않는다 —
  그것은 아무도 검사하지 않는 **두 번째 직렬화 형식**이고, 부동소수 표기의 왕복이 정확히
  이 저장소가 싸우는 조용한 결함 부류다.
- 그래서 의존성이 둘 는다 — 임베딩 클라이언트와 `pgvector`. **`uv.lock` 이 바뀌므로 D28 대로
  `test` 이미지를 사람이 다시 빌드해야 한다.** 그것을 강제하는 검사는 여전히 없다.

### `kb_status` 에 필드 하나를 더한다

나머지 신호는 전부 순간적이다. CLI 출력은 run 이 끝나면 사라지고, `kb_ingest_runs` 는 run 을 셀 뿐
벡터를 세지 않는다. **키를 아직 넣지 않은 상태는 오류가 아니라 정상 상태(D2)이므로,
오류 경로가 아니라 현황에 드러나야 한다.**

```json
{ "documents": 12, "chunks": 340, "events": 5,
  "last_ingest_at": "2026-09-01T09:00:00+00:00",
  "zero_hit_queries": 0, "chunks_without_embedding": 340 }
```

- 값은 `embedding IS NULL` 인 **청크** 수다. 이벤트는 세지 않는다 (아래 `닫지 않는 것`)
- `chunks` 와 같으면 그 project 는 벡터가 하나도 없다 — 키 없이 색인했다는 뜻이다
- 0 이 아닌데 키가 있으면 임베딩 호출이 실패했다는 뜻이다.
  **둘을 응답만으로 구분하지 못한다** — 그 구분은 `kb_ingest_runs.status`·`error` 가 하고
  그 값 집합은 D32 가 소유한다
- 이름을 `pending_embeddings` 로 하지 않는다. 이벤트까지 센다고 읽히기 때문이다
- **스키마 변경은 없다.** `embedding` 에 인덱스가 없어 전 구간 스캔이지만 `chunks` 자신도 이미 그렇다

**이 필드가 낡히는 사본은 다섯이다.** 계약을 고칠 때 전부 함께 고친다:
[service-and-mcp.md](../docs/service-and-mcp.md) 의 상태 응답 JSON 과 그 위의 산문 목록,
[README.md](../README.md) 와 [README.ko.md](../README.ko.md) 의 빠른 시작 JSON 예시,
그리고 다섯 키를 하나씩 단언하는 4단계 검사. 두 README 는 표시폭 규칙과 산문 블록 대칭까지 걸린다.

### 새 컬럼을 만들지 않는다

- 백필이 필요로 하는 상태는 `kb_chunks.embedding IS NULL` 이 **전부** 표현한다.
  `embedded_at` 같은 컬럼은 같은 사실의 두 번째 사본이고, 사본이 어긋나면 아무도 비명을 지르지 않는다
- **어느 청크가 어느 모델로 임베딩됐는지 아는 방법은 지금 없다.** 그리고 만들지 않는다 —
  D2 가 모델 하나를 고정했으므로 v1 에서 그 컬럼은 언제나 값 하나만 갖는다
- 모델 교체는 여전히 D2 개정이고 **전체 재색인**이다. 백필은 그것을 대신하지 않는다
- **그때 벡터를 비우는 SQL 을 마이그레이션 파일에 넣지 않는다.** D17 러너는 적용 이력을 두지 않고
  매 기동마다 모든 `.sql` 을 다시 실행한다. `UPDATE kb_chunks SET embedding = NULL` 한 줄은
  기동마다 벡터를 지우고 다음 ingest 가 전부 다시 임베딩하는 무한 청구서가 된다.
  **기동은 성공하고 검색은 키워드로 계속 돌기 때문에 조용하다.** 추측하지 않도록 여기 적는다

### 임베딩 호출이 실패하면

- **텍스트 색인 결과는 되돌리지 않는다.** 문서·청크·`tsv` 까지 되돌리면 벡터를 못 얻은 대가로
  키워드 검색마저 잃는다. 벡터 없는 인덱스는 D2 가 이미 정상으로 정한 상태다.
  **D31 은 트랜잭션 경계를 정하지 않는다 — D32 에 제약 하나를 걸 뿐이다:
  텍스트 색인 결과는 백필 실패로 되돌아가지 않는다**
- **그 run 은 성공으로 보고되지 않는다.** 값 이름은 D32 가 정한다.
  D31 이 거는 요구는 하나다: **임베딩 실패가 성공과 구분될 것**
- 실패 요약은 이미 있는 `kb_ingest_runs.error` 에 적는다.
  **키·DSN·응답 본문을 싣지 않는다** — API 키는 요청 헤더에 실려 예외에 딸려 나오는 일이 잦다.
  D21 이 `INTERNAL` 에 예외 문구를 싣지 않는 것과 같은 이유다
- `sillok ingest` 는 **종료 코드 1** 로 끝난다. 러너가 이미 실패에 쓰는 값이다
- HTTP 얼굴(`POST /v1/ingest`)은 **상태코드로 말하지 않는다.** 같은 함수의 같은 dict 를 공통 봉투에 담고
  남은 수가 그 안에 있다. D21 의 다섯 코드에 "절반 성공"은 없고, 발신 조건을 발명하는 것은
  D21 이 이미 거부한 일이다. **D31 은 D21 을 개정하지 않는다**
- 다음 run 이 같은 청크를 다시 집는다. 재시도 경로가 따로 없다 — `embedding IS NULL` 이 그대로다

### 채운 수와 남은 수가 사는 자리

- run 응답 dict 의 `chunks_embedded`(이번 run 이 채운 수)와 `chunks_pending`(끝난 뒤 남은 수)이다.
  전체 응답 모양은 D30 이 소유한다.
- **`kb_ingest_runs` 에 임베딩 카운터 컬럼을 더하지 않는다.** 그 숫자는 응답과 CLI 출력에만 있고,
  지속되는 신호는 `kb_status.chunks_without_embedding` 하나다.

### 비용 상한은 v1 에서 두지 않는다

**두지 않기로 명시적으로 정한다.** 대상은 유한하고(D9 세 패턴) 성공하면 다시 대상이 아니므로 수렴한다.
상한을 두면 **"한도에 걸려 절반만 채워진 상태"** 가 새로 생기는데, 그것이 정확히 Q7 이 지적한 부류다 —
정상처럼 보이고 아무도 비명을 지르지 않는다. 대신 CLI 가 채운 수와 남은 수를 출력하고,
`kb_status` 가 남은 수를 상시 보여 준다. 폭주는 위의 "첫 실패에서 멈춘다"가 막는다.
상한이 필요해지는 첫 신호는 D9 밖 경로를 색인하게 될 때이고 그것 자체가 D9 개정이다. 그때 함께 정한다.
배치 크기와 재시도 백오프는 계약이 아니라 구현이다. **순서는 계약이다**(위).

### 계약 문구를 고친다

[service-and-mcp.md](../docs/service-and-mcp.md) §색인의 `해시 비교 후 변경분만 임베딩` 은
이 결정 뒤 정확하지 않다 — 변경분만 다시 쪼개지만 임베딩은 **벡터가 빈 청크 전부**를 본다.
그 한 줄이 Q7 의 함정을 만든 정본이다. 고치고 **옛 문구를 게이트의 `RETIRED` 에 등록한다.**

### 기존 결정을 뒤집지 않는다

- **D2 그대로.** 키가 없으면 `embedding` 은 NULL 이고 `tsv` 만 검색한다.
  D31 은 그 상태를 *영구*에서 *일시*로 바꿀 뿐이다
- **D19·D20 그대로.** 새 명령도 새 인자도 없다. 백필은 Service 함수 안에서 일어나고
  CLI 는 여전히 자기 SQL 을 갖지 않는다
- **D21 그대로.** 새 코드도 `CONFLICT` 발신도 없다
- **D25 그대로.** 새 CHECK 도 새 enum 도 없다
- **D17 그대로.** 새 마이그레이션이 없다. 다만 위 마지막 항목은 D17 러너의 성질(이력 없음·매번 재실행)에 의존한다

### D31이 닫지 않는 것

- **`kb_events.embedding` 은 이 결정 밖이다.** 같은 함정이 이벤트에도 있고 **더 나쁘다** —
  이벤트는 Git 에 원본이 없어 다시 만들 수 없고, 4단계 `save_event` 는 키가 있어도 임베딩하지 않는다.
  그러나 이벤트 벡터의 소비자는 `search_events`(6단계)이고 그 결정은 Q8·Q9 와 함께 온다.
  **여기서 이벤트를 ingest 에 끌어들이면 6단계를 5단계로 당기는 것이다.**
  `chunks_without_embedding` 이 이벤트를 세지 않는 것도 그래서다
- **차원이 같은 다른 모델로 갈아타면 섞인 벡터를 아무도 탐지하지 못한다.** 백필은 non-NULL 을 덮지 않으므로
  옛 청크는 옛 모델, 새 청크는 새 모델 벡터를 갖는다. DDL 이 안 바뀌므로 마이그레이션도 안 걸리고
  검색 품질만 조용히 떨어진다. `kb_chunks` 에 모델 컬럼을 두거나 교체 시 전 벡터를 NULL 로 만드는
  마이그레이션이 다음 후보다. 둘 다 v1 밖이다
- **`kb_chunks.embedding` 에 인덱스가 없다.** `embedding IS NULL` 스캔과 `kb_status` 의 남은 수 카운트는
  그 project 청크 전 구간을 읽는다. HNSW 는 D14 가 이미 미룬 자리다
- **`POST /v1/ingest` 는 동기다.** 백필까지 한 요청 안에서 돌고 타임아웃은 호출자 문제다.
  D19 가 A 안을 버린 이유("스캔+임베딩이 단일 긴 요청이 되어 타임아웃·진행률 문제를 부른다")가 그대로 남는다.
  운영자 진입점이 CLI 라는 것이 v1 의 답이다 (D20)
- **`POST /v1/ingest` 의 호출자는 종료 코드를 받지 못한다.** 부분 실행 신호는 응답 본문의 카운터뿐이다 —
  나중에 webhook 이 이 얼굴을 쓰면 그쪽이 카운터를 보게 만들어야 한다
- **부분 임베딩 상태는 정상이다.** 한 문서의 청크 일부만 벡터를 갖는 상태가 언제든 있을 수 있고,
  그동안 그 문서는 벡터로 덜 맞는다. 6단계가 병합을 정할 때(Q8) 이 비대칭을 다시 본다
- **호출이 성공했는데 벡터가 쓸모없는 경우는 탐지하지 않는다.** 차원만 DDL 이 본다
- **키가 있는 상태의 검사 경로가 없다.** `--profile test` 는 키를 갖지 않으므로 백필 패스는
  커밋된 구성에서 **무동작으로만** 돈다. 실제 호출은 사람이 한 번 돌려 확인한다 —
  D22 가 남긴 workspace 숙제와 같은 자리이고, 5단계 검사를 쓸 때 함께 본다

## D32 — ingest 의 트랜잭션 경계 · 동시 실행 · `kb_ingest_runs.status` (2026-09-01 확정)

[open-questions.md](../docs/open-questions.md) Q10을 마감한다. 5단계 ingest 를 막던 마지막 항목이다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D32 | A | **파일 하나가 트랜잭션 하나다.** 임베딩 호출은 어떤 배치든 트랜잭션 밖이고, 같은 project 의 동시 ingest 는 세션 advisory 락으로 **즉시 거절**한다. `status` 는 `running`·`ok`·`partial`·`failed` | Q10 |

**Q10 이 묻는 셋은 하나의 실패 모드로 이어져 있다.** 재색인은 `(project, repo, path)` 단위로
청크를 지우고 다시 넣는데, 그 삭제와 insert 가 다른 트랜잭션이면 사이에 들어온 검색이 그 문서를
**0건으로** 돌려준다. 오류는 나지 않는다 — 결과가 조용히 줄어들 뿐이다.
동시 실행도, 중단된 run 도 같은 부류다.
그래서 이 결정은 **어떤 답이 조용히 틀리는가**를 먼저 적고 시끄러운 쪽을 고른다.

### 조용히 틀리는 자리

| 자리 | 어떻게 조용히 틀리는가 | 이 결정이 고른 것 |
|---|---|---|
| 청크 교체 | DELETE 와 INSERT 가 다른 트랜잭션이면 그 사이 검색이 문서를 잃는다 | 문서 하나의 삭제·insert 는 한 트랜잭션 |
| 연결 모드 | 비-autocommit 에서 첫 문장이 암묵 트랜잭션을 열면 이후 트랜잭션 블록이 전부 **세이브포인트**가 된다. 파일 단위 커밋이 사라지는데 코드는 그대로 통과한다 | ingest 연결은 autocommit 으로 연다 |
| 락 수준 | 트랜잭션 수준 락은 첫 파일 커밋에서 풀린다. 두 run 이 나란히 돌아도 아무도 모른다 | 세션 수준 `pg_try_advisory_lock` |
| 락 대기 | 블로킹 락은 매달린다 — 느린 색인과 구분되지 않는다 | `try_` 계열, 즉시 거절 |
| `last_ingest_at` | 실패한 run 에 `finished_at` 을 넣으면 `kb_status` 가 실패를 마지막 색인으로 보고한다 | 성공한 run 만 센다 |
| 거절된 시도 | 락을 못 얻은 시도까지 행으로 남기면 같은 거짓말이 된다 | 행을 만들지 않는다 |
| 죽은 run | 행으로 잠그는 설계는 프로세스가 죽으면 **영구히** 막는다. 그때 CLI 는 "실행 중"이라고 말한다 | advisory 락은 세션이 끊기면 풀린다 |
| 파일 순서 | 순서가 실행마다 다르면 부분 run 이 남긴 상태가 재현되지 않는다 (D23 선례) | 경로 오름차순으로 고정 |

### D32 선택지

| ID | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D32 경계 | 파일 하나 = 트랜잭션 하나 | run 전체가 하나 | 청크 배치 단위 | B는 중단되면 **아무 진전도 남지 않고**, 임베딩 호출을 트랜잭션 안에 넣거나(유휴 트랜잭션이 run 내내 열린다) 결과를 전부 메모리에 모은 뒤 쓰게 된다. C는 한 문서의 청크가 절반만 보이는 창을 만든다 — 위 첫 줄의 실패를 문서 안으로 옮길 뿐이다 |
| D32 동시 실행 | 세션 advisory try-lock | 허용하고 upsert 에 맡긴다 | `running` 행에 부분 유니크 인덱스 | B는 두 run 의 DELETE 가 서로의 청크를 지우고 `UNIQUE (project, repo, path)` 경쟁이 `INTERNAL` 로 나간다(D21) — 마지막에 남는 것이 어느 run 것인지 정해지지 않는다. C는 새 마이그레이션이 필요하고, 프로세스가 죽으면 사람이 행을 지울 때까지 색인이 멈춘다 |
| D32 status | `running`·`ok`·`partial`·`failed` | `partial` 없이 셋 | 값 집합을 DDL CHECK 로 | B는 임베딩이 절반만 채워진 run 을 `ok`(거짓말)나 `failed`(성공한 텍스트 색인까지 실패로) 중 하나로 적게 만든다. **C는 D25 를 뒤집는다** — CHECK 위반은 Postgres 예외가 되고 D21 이 그것을 `INTERNAL 500` 으로 접는다 |

### 트랜잭션 경계

- **연결 하나, 트랜잭션 여럿.** `service.ingest` 는 연결을 하나 열고 run 내내 쓴다.
  마이그레이션 러너가 이미 같은 모양이다 — 파일 하나가 트랜잭션 하나다.
- **그 연결은 autocommit 으로 연다.** `service.connect` 는 지금 autocommit 을 켜지 않으므로
  ingest 는 그것을 **기본값이 꺼짐인 인자로** 켠다. 기본값을 유지하는 것은 4단계 세 함수의 동작을
  바꾸지 않기 위해서다. 켜지 않으면 위 표의 두 번째 줄이 그대로 일어난다 —
  블록 밖 문장 하나가 암묵 트랜잭션을 열고, 그 뒤의 트랜잭션 블록이 전부 세이브포인트가 되어
  **run 전체가 한 트랜잭션이 된다.** 그리고 그 고장은 실패가 아니라 통과로 나온다.
- **그래서 규칙에 검사를 붙인다.** 5단계 DB 검사가 파일 하나를 처리한 직후 **별도 연결**에서
  `kb_documents` 를 세어 그 행이 이미 보이는지 확인한다. 규칙만 적고 검사가 없으면
  세이브포인트 붕괴는 영원히 조용하다 (D28 논지).
- 한 트랜잭션이 담는 것은 **문서 하나**다 — `kb_documents` upsert + 그 문서의 청크 `DELETE` + `INSERT`.
  `ON DELETE CASCADE` 는 문서 행을 지울 때만 돌므로 재색인 경로에서는 명시적 DELETE 다.
- 파일 하나의 순서는 고정이다 — 읽기 → 해시 판정 → 청크 → 트랜잭션 열고 쓰기 → 커밋.
  **임베딩은 이 루프 안에 없다.** D31 이 경로를 하나로 정했으므로 임베딩은 파일 루프가 끝난 뒤
  `embedding IS NULL` 을 훑는 마지막 패스에서만 일어난다.
- **임베딩 API 호출은 어떤 배치든 트랜잭션 밖이다.** 백필은 호출한 뒤 그 결과를
  `UPDATE kb_chunks SET embedding = …` 으로 쓰고, 배치 하나가 트랜잭션 하나다. 배치 크기는 구현이다.
- **D31 이 건 제약을 지킨다: 텍스트 색인 결과는 백필 실패로 되돌아가지 않는다.**
  파일 루프가 이미 커밋했고 백필은 별도 트랜잭션이다. 그리고 그것이 Q7 의 함정을 새로 만들지 않는다 —
  다음 run 의 백필이 `content_hash` 와 무관하게 `embedding IS NULL` 을 다시 집기 때문이다.
- 파일은 workspace 상대 경로의 **오름차순**으로 처리한다. 로케일 정렬이 아니라 코드포인트 순이다.
  파일 단위로 커밋하므로 중단된 run 이 남긴 상태가 곧 관측 대상이고, 그것이 실행마다 같아야 한다.
- `commit_sha` 의 *출처*는 D30 이 정한다(v1 은 채우지 않는다). 여기서 정하는 것은 **읽는 횟수**다 —
  값이 생기면 run 시작 시 한 번 읽고 그 run 이 쓰는 모든 행에 같은 값을 넣는다.
  파일마다 다시 읽으면 run 도중의 커밋이 문서마다 다른 sha 로 박힌다.
- run 행은 서로 독립된 쓰기다 — 시작 INSERT(`running`) → 파일 루프 → **삭제 반영** → 백필 → 종료 UPDATE.
  **삭제는 백필 앞이다.** 뒤에 두면 백필 첫 실패에서 멈추는 run(`partial`)이 삭제를 영구히 건너뛴다 —
  텍스트 색인의 일부인데 벡터 때문에 빠지는 것이다. 삭제 자체도 자기 트랜잭션이다.
  run 전체를 감싸는 트랜잭션은 없다.
- **카운터는 종료 UPDATE 에서 상태와 같은 트랜잭션에 쓴다. 진행 중에는 NULL 이다.**
  대가는 진행률이 DB 에 없다는 것이다. 다음 후보는 파일마다 카운터를 UPDATE 하는 것이고,
  run 당 수백 번의 쓰기라 지금은 하지 않는다.
- 검색과의 관계: 기본 격리 수준에서 `serve` 의 읽기는 커밋된 옛 청크나 커밋된 새 청크 중 하나를 본다.
  빈 상태는 어느 시점에도 보이지 않는다. **그것을 보장하는 것은 위 문서 단위 트랜잭션 규칙과
  autocommit 규칙뿐이다.**
- `statement_timeout` 과 `idle_in_transaction_session_timeout` 을 설정하지 않는다. 기본값 그대로다.

### 동시 실행

```sql
SELECT pg_try_advisory_lock(hashtext('sillok:ingest'), hashtext(%(project)s));
```

- 락은 **Service 함수 안에서** 잡는다. CLI 는 자기 SQL 을 갖지 않는다 (D19).
  그래서 `sillok ingest` 와 `POST /v1/ingest` 가 같은 락을 두고 경쟁한다 —
  진입점이 둘이어도 직렬화는 하나다. `serve` 와 `ingest` 가 각자 세션을 여는 것은 그대로다.
- **세션 수준이다.** 트랜잭션 수준 락은 첫 파일 커밋에서 풀린다.
- **락 키의 `project` 는 D25 로 정규화한 값이다.** 정규화 전 문자열로 잡으면 같은 프로젝트가 갈라진다.
- **키를 서버가 계산한다.** 파이썬의 내장 해시는 실행마다 달라진다.
  경쟁하는 두 세션은 같은 서버에 붙으므로, `hashtext` 의 값이 판마다 다르더라도 둘의 값은 언제나 같다.
- **`hashtext` 충돌은 오진으로 끝난다.** 데이터는 상하지 않고 다른 project 하나가 불필요하게
  직렬화될 뿐이다. 다만 거절 문구는 **호출자의** project 를 기준으로 말하므로,
  충돌 시 실제로 도는 것은 다른 project 인데 이 project 가 실행 중인 것처럼 읽힌다.
  **그 오진을 받아들인다.** 관측되면 그때 키 계산을 바꾼다.
- **락 해제는 명시적이다.** run 이 끝나면 `pg_advisory_unlock` 을 부른다.
  부르지 못한 경우(프로세스 사망) 연결이 닫히는 것이 해제다. `POST /v1/ingest` 는 장수 `serve`
  프로세스 안에서 돌므로 명시적 해제가 없으면 세션 락이 남는다.
  **연결 풀을 도입하면 이 전제가 깨진다 — v1 에 풀은 없다.**
- project 가 다르면 동시에 돈다. 락 키가 다르다.
- **거절은 `CONFLICT` 다.** 아래 `D21 개정`.
- 거절된 시도는 `kb_ingest_runs` 에 행을 만들지 않는다.
- 진단은 `SELECT classid, objid FROM pg_locks WHERE locktype = 'advisory'` 로 본다.
  스키마도 응답 필드도 늘리지 않는다.
- 락을 얻은 직후, 같은 project 의 `running` 행을 **전부** `failed` 로 회수한다.
  락이 그 행들이 죽었다는 증거다 — 살아 있는 run 이 있었다면 락을 못 얻었다.
  회수 행의 `error` 는 고정 문구 `interrupted` 이고 `finished_at` 은 **NULL 로 둔다.**
  언제 죽었는지 모르는데 지금 시각을 넣으면 그것이 새 거짓말이다.
  **이 회수 규칙은 `kb_ingest_runs` 에 행을 쓰는 경로가 이 락을 잡은 run 하나뿐이라는 전제에 기댄다.**
  락 없이 그 테이블에 쓰는 경로가 생기면 회수가 살아 있는 run 을 죽은 것으로 적는다.

### `kb_ingest_runs.status`

| 값 | 뜻 |
|---|---|
| `running` | 시작했고 끝나지 않았다. DDL 기본값이다 |
| `ok` | 파일 루프와 백필이 둘 다 끝까지 갔다. 키가 없어 백필이 무동작인 것도 `ok` 다 (D2) |
| `partial` | 텍스트 색인은 끝까지 갔고 **백필이 첫 실패에서 멈췄다** (D31) |
| `failed` | run 자체가 중단됐다 — 디코드 실패, 0건 스캔, DB 오류, 그리고 회수된 행 |

- 전이는 `running` → `ok` | `partial` | `failed` 하나뿐이다. 셋은 종단이고 다시 `running` 이 되지 않는다.
  재실행은 같은 행의 갱신이 아니라 새 행이다.
- **값 집합은 서비스 모듈 상수와 [data-model.md](../docs/data-model.md) 의 컬럼 주석에 둔다.
  DDL 에 CHECK 를 넣지 않는다 (D25).** 다른 enum 컬럼이 전부 값 주석을 갖는데 이 컬럼만 없었다.
- **`002` 에도 같은 값 주석 한 줄만 더한다.** 주석 외에는 `002` 를 고치지 않는다.
  스키마를 바꾸면 새 파일이다. 주석을 빼면 이 결정이 고치려는 비대칭을 사본에 그대로 재생산한다.
- **값 집합에는 읽는 자리가 하나는 있어야 한다** — 아무도 읽지 않는 값은 틀려도 드러나지 않는다.
  그 자리가 아래 `kb_status.last_ingest_at` 이다.
- `finished_at` 은 run 이 끝난 시각이다. `ok`·`partial`·`failed` 모두 채우고, 회수된 행만 NULL 이다.
- `error` 는 `partial`·`failed` 에서 **반드시 있고** `ok` 에서 NULL 이다. 5단계 검사가 이 짝을 단언한다.
- **`error` 는 첫 실패의 첫 줄이고 500자에서 자른다.** 전체 목록도 트레이스백도 담지 않는다 —
  담으면 run 하나가 로그가 된다. 실패 파일 수는 앞에 붙인다.
- `error` 는 DSN 을 가리는 기존 함수를 통과시킨다. 그리고 **HTTP 응답에 싣지 않는다** —
  D21 의 `INTERNAL` 본문은 고정 문자열이다.
- **키가 없으면(D2) 모든 청크의 `embedding` 이 NULL 이고 그 run 은 `ok` 다.**
  `partial` 은 키가 있는데 임베딩을 못 얻은 경우다. 둘을 같은 값으로 부르면 정상 상태가 경보가 된다.
- 스캔이 예외로 끝난 run(`failed`)은 삭제 반영(D30)을 하지 않는다.
  **못 읽은 파일과 사라진 파일을 구분할 수 없다.**
- 종료 UPDATE 자체가 실패하면(DB 가 끊긴 경우) 행은 `running` 으로 남고 다음 run 이 회수한다.

CLI 와 HTTP 얼굴:

- `sillok ingest` 는 `ok` 에만 `0` 을 돌려준다. `partial`·`failed`·락 거절은 `1` 이다.
  셋의 구분은 종료 코드가 아니라 stderr 문구와 run 행이 한다 — 종료 코드 관용구를 늘리지 않는다.
- `POST /v1/ingest` 는 **run 행이 생긴 모든 경우에 `ok: true` 와 `data.status` 를 돌려준다** —
  `ok` 도 `partial` 도 `failed` 도 그렇다. 봉투의 `ok: false` 는 요청이 처리되지 못했다는 뜻이고,
  시작한 run 은 결과가 무엇이든 처리된 것이다. **이 엔드포인트가 내는 `ok: false` 는 락 거절 하나뿐이다.**
  대신 **`status` 를 안 읽는 클라이언트는 실패를 놓친다** — 운영자 진입점이 CLI 인 이유다 (D20).

### D21 개정 — `CONFLICT` 에 첫 발신자가 생긴다

D21 은 `CONFLICT` 를 예약으로 두면서 그 근거로 "동시 ingest 는 Q10 이 열려 있다"를 적었다.
Q10 을 닫으면 그 칸의 근거가 사라진다. **v1 은 이제 `CONFLICT` 를 정확히 한 자리에서 발신한다** —
`POST /v1/ingest` 가 같은 project 의 락을 얻지 못했을 때다.
발신 조건을 발명한 것이 아니라 D21 이 미뤄 둔 조건이 정해진 것이다.

- **발신 경로를 만든다.** `api` 에는 지금 검증 실패 핸들러와 포괄 예외 핸들러뿐이고 후자가 전부
  `INTERNAL 500` 으로 접는다. 그대로 두면 락 거절이 409 가 아니라 500 으로 나간다.
  서비스가 전용 예외를 올리고 `api` 가 그것을 `CONFLICT` 로 접는 핸들러를 더한다.
  **매핑 표를 잠그는 검사가 있듯 이 발신 경로도 검사로 잠근다.**
- **거절 응답의 `message` 는 고정 문구 `ingest already running for this project` 다.**
  `project` 값을 문구에 넣지 않는다 — 고정 문구여야 검사가 잠글 수 있고, D21 이 `INTERNAL` 에
  세운 원칙과 같은 모양이다.
- 상태 매핑은 이미 있다. 코드도 상태도 늘지 않는다.
- **낡는 사본이 여섯이다.** `CONFLICT` 를 "예약, v1 미발신"으로 적은 곳을 전부 고친다 —
  D21 의 표와 그 본문, D24 의 같은 문장, [service-and-mcp.md](../docs/service-and-mcp.md) 의 에러 표,
  [CLAUDE.md](../CLAUDE.md) 의 미러, [AGENTS.md](../AGENTS.md) 의 전제 블록.
  [open-questions.md](../docs/open-questions.md) 의 Q11 해결 서술은 본문 불변 규칙에 걸리므로
  D29 가 Q23 에 한 것처럼 **후속 줄을 추가**하고 기존 줄은 둔다.
  **옛 문구는 게이트의 `RETIRED` 에 등록하고 주입을 함께 넣는다.**
- 경쟁 상황의 유니크 위반은 그대로 `INTERNAL` 이다. 락이 그 경쟁을 없애므로 발생하면 결함이다.
- `save_event`·`save_doc` 은 그대로 발신하지 않는다 (D24 · D3). 발신자는 이 한 자리뿐이다.

### 4단계 코드를 건드리는 곳은 둘이다

- **`kb_status.last_ingest_at` 의 뜻이 좁아진다** — `status IN ('ok','partial')` 인 run 의
  마지막 `finished_at` 이다. `service.py` 의 SQL 과 [service-and-mcp.md](../docs/service-and-mcp.md) 의
  그 줄을 함께 고친다. 실패한 run 이 마지막 색인으로 보고되는 것을 막는다.
- **`service.connect` 에 autocommit 인자가 는다.** 기본값은 꺼짐이라 기존 세 함수의 동작은 바뀌지 않는다.

### D32가 닫지 않는 것

- **죽은 run 은 다음 run 이 올 때까지 `running` 으로 남는다.** 회수는 락을 잡은 다음 run 이 한다.
  다시 돌리지 않으면 영원히 그대로다. 해가 해소된 것이 아니라 **받아들여진 것이다** (D24 선례).
  드러낼 곳이 필요해지면 `kb_status` 에 필드를 더하는 계약 변경이고,
  그때는 [service-and-mcp.md](../docs/service-and-mcp.md) 를 먼저 고친다. 그것이 다음 후보다
- **새 마이그레이션을 만들지 않는다.** 값 집합은 서비스에 있고 락은 스키마를 쓰지 않는다.
  `kb_ingest_runs` 는 PK 외 인덱스가 없는 채로 둔다 — v1 규모에서 `kb_status` 의 스캔은 문제가 아니다.
  (D30 이 같은 표에 `files_deleted` 를 더하므로 파일 자체는 생긴다)
- **`POST /v1/ingest` 는 동기다.** 진행률도 취소도 없고, 큰 workspace 에서 단일 긴 요청이 되는 문제는
  D19 가 A 를 버린 이유 그대로 남는다. 운영자 진입점이 CLI 라는 것이 v1 의 답이다
- **`partial` 의 재시도를 자동화하지 않는다.** 다시 `sillok ingest` 를 돌리는 것이 재시도다
- **`hashtext` 충돌을 검사하지 않는다.** 위의 오진을 관측하면 그때 키 계산을 바꾼다
- **진행률이 DB 에 없다.** 카운터는 종료 UPDATE 에서 한 번 쓴다
- **Q6(D30) · Q7(D31)에 속한 것은 여기서 정하지 않는다** — 확장자 필터, 해시 알고리즘,
  `commit_sha` 출처, 삭제된 파일의 처리 방식, 청크 경계, 백필의 대상과 순서
- 5단계 검사가 workspace 파일을 어디서 얻는지는 D22 가 남긴 숙제 그대로다 —
  `test` 이미지에는 `docs/`·`adr/` 가 없다. 트랜잭션 경계와 락 검사는 임시 디렉터리의 파일로도
  돌릴 수 있고 D30 이 그 방향을 골랐다. 남는 것은 D9 경로 자체를 대상으로 하는 검사뿐이다

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
- ingest 확장자 필터 `.md`, 청크 소프트 상한 1200자·하드 상한 4000자, overlap 없음 (D30)
- `heading_path` 구분자 ` > ` (D30, 형식 정본은 service-and-mcp.md)
- `kb_ingest_runs.status` 값 집합 `running`·`ok`·`partial`·`failed` (D32)
- ingest 락은 세션 advisory, 거절은 `CONFLICT` 409 (D32)

## 이 값들이 복제된 위치

정본은 이 파일이다. 아래 사본이 어긋나면 **이 파일이 이긴다.** 값을 바꿀 때 함께 고친다.

| 사본 | 복제된 값 |
|---|---|
| [docs/plan.md](../docs/plan.md) §2 | 확정 스택 표 전체 |
| [CLAUDE.md](../CLAUDE.md) | 확정 스택 표 (도구 컨텍스트용 미러) |
| [docs/data-model.md](../docs/data-model.md) | `vector(1536)`, 모델 ID, 확장 목록 |
| [docs/service-and-mcp.md](../docs/service-and-mcp.md) | 서비스 주소, 인증, `top_k`, 색인 경로. **`heading_path` 형식은 그쪽이 정본** |
| [scripts/check-layout.mjs](../scripts/check-layout.mjs) | ingest 확장자 필터 `.md` (D30 이 정본) |
| [migrations/002_schema.sql](../migrations/002_schema.sql) | `kb_ingest_runs.status` 값 주석 (D32) |
| [AGENTS.md](../AGENTS.md) | 확정 전제 요약 블록 |
| [.env.example](../.env.example) | D16 환경변수 이름과 기본값 |

## 나중에 바꿔도 되는 것 (v1 비범위)

- D2를 Voyage / Gemini / Qwen3 / xAI로 교체 → **스키마 변경 + 전체 재색인**이 따라온다
- D7을 토큰으로 상향
- D8에 n8n webhook 추가
- D12 작은 웹 UI
- D13을 기존 Postgres에 붙이기

## 미기록

D33 이후로 기록해야 할 미해결 결정은 [docs/open-questions.md](../docs/open-questions.md)에 전부 모여 있다.
2026-09-01 기준 남은 것은 B절의 Q8·Q9 · C절의 Q12–Q15·Q17 · D절의 Q19·Q20·Q22·Q23과 Q24·Q25다.
Q23 은 D29 가 절반만 답했다 — 값을 어디서 얻는지는 정해졌고 `status` 의 생애가 남았다.
E절(검증 경로)은 Q26 하나였고 D22로 닫혔다. B절의 Q6·Q7·Q10은 D30–D32로 닫혔다.
