---
title: v1 확정 결정 D1–D25
doc_type: adr
status: current
module: null
---

# ADR 0001 — v1 확정 결정 D1–D25

상위: [docs/plan.md](../docs/plan.md) · [README](../README.md)
상태: D1–D15 **2026-08-30 확정** (묶음 추천 수용) · D16–D25 **2026-08-31 확정** (부트스트랩, HTTP 에러 표면, 테스트 경로, 4단계 계약)

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
- `ORDER BY count DESC, root_cause ASC LIMIT 12` — 상한이 없으면 distinct 원인 전부가 나가 토큰 불변식을 깬다.
  `12`는 검색 최대치와 같은 값이다. **동수일 때 `root_cause`로 다시 정렬한다** — 그렇지 않으면 `LIMIT`이 자르는 대상이 실행마다 달라진다
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

### D23–D25가 닫지 않는 것

- **Q13** 목록·타임라인·페이지네이션. `GET /v1/events` 컬렉션을 만들지 않는다
- **Q14** 이벤트 수정 경로
- **Q12** `get_event`의 404 대 빈 결과, 프로젝트 경계 — 7단계
- **Q22 · Q23 · Q25** `repo` 의미, front matter 규칙, Skill 사본 노후
- D24는 재시도 부풀림을 **해결하지 않고 받아들인다**

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

D26 이후로 기록해야 할 미해결 결정은 [docs/open-questions.md](../docs/open-questions.md)에 전부 모여 있다.
2026-08-31 기준 남은 것은 B절(색인·검색 결정성) · C절의 Q12–Q15·Q17 · D절의 Q19·Q20·Q22·Q23과 Q24·Q25다.
E절(검증 경로)은 Q26 하나였고 D22로 닫혔다.
