---
title: v1 확정 결정 D1–D29
doc_type: adr
status: current
module: null
---

# ADR 0001 — v1 확정 결정 D1–D29

상위: [docs/plan.md](../docs/plan.md) · [README](../README.md)
상태: D1–D15 **2026-08-30 확정** (묶음 추천 수용) · D16–D28 **2026-08-31 확정** (부트스트랩, HTTP 에러 표면, 테스트 경로, 4단계 계약, 공개 전환, 라이선스, 증거 신선도)
· D29 **2026-09-01 확정** (README front matter)

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
| `CONFLICT` | 409 | **예약. v1은 발신하지 않는다** — 아래 참조 |
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

### `CONFLICT`에 v1 발신자가 없다

Q11이 이미 `발생 조건조차 없다`고 적었고, 실제로 없다.

| 표면 | 왜 CONFLICT가 아닌가 |
|---|---|
| `POST /v1/events` | `id`가 `bigserial`이고 payload에 유일성이 없다. 여기서 유일성을 발명하면 **Q18을 추측으로 닫는 것**이다 |
| `POST /v1/docs/proposals` | D3대로 쓰지 않는다. 충돌할 대상이 없다 |
| ingest의 `UNIQUE (project, repo, path)` | 재색인은 청크를 지우고 다시 넣는 upsert다 |
| 동시 ingest | **Q10이 열려 있다.** 경쟁 상황의 UniqueViolation은 명시된 발신 조건이 아니라 `INTERNAL`이다 |

**코드는 예약으로 남기고 매핑만 정한다.** 아무도 만들지 않는 코드를 지우는 것은 계약 변경이고,
쓰이는 것처럼 보이려고 발신 조건을 발명하는 것은 더 나쁘다.

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
- **Q10** 동시 실행. 경쟁 UniqueViolation을 `INTERNAL`로 둔다는 것 외에는 정하지 않았다

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
- D21의 `CONFLICT`는 예약 그대로다. v1은 여전히 발신하지 않는다
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
- **Q10** ingest 트랜잭션 경계와 동시 실행. `serve`와 `ingest`가 각자 세션을 여는 것까지만 정했다
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

- **pytest 는 더 이상 `COPY src`·`COPY tests` 를 목격하지 않는다.** 이미지가 소스를 제대로
  담았는지는 이제 검사가 아니라 재빌드로만 드러난다. 조용한 통과를 없애려고 치른 값이고,
  이 결정이 고른 쪽이다. `pyproject.toml`·`uv.lock`·`migrations/`도 마운트하지 않는다
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

D30 이후로 기록해야 할 미해결 결정은 [docs/open-questions.md](../docs/open-questions.md)에 전부 모여 있다.
2026-09-01 기준 남은 것은 B절(색인·검색 결정성) · C절의 Q12–Q15·Q17 · D절의 Q19·Q20·Q22·Q23과 Q24·Q25다.
Q23 은 D29 가 절반만 답했다 — 값을 어디서 얻는지는 정해졌고 `status` 의 생애가 남았다.
E절(검증 경로)은 Q26 하나였고 D22로 닫혔다.
