---
title: v1 확정 결정 D1–D52
doc_type: adr
status: current
module: null
---

# ADR 0001 — v1 확정 결정 D1–D52

상위: [docs/plan.md](../docs/plan.md) · [README](../README.md)
상태: D1–D15 **2026-08-30 확정** (묶음 추천 수용) · D16–D28 **2026-08-31 확정** (부트스트랩, HTTP 에러 표면, 테스트 경로, 4단계 계약, 공개 전환, 라이선스, 증거 신선도)
· D29–D34 **2026-09-01 확정** (README front matter, 5단계 ingest 계약, 6단계 검색 계약)
· D35–D41 **2026-09-02 확정** (7단계 계약, 그리고 그것을 구현하다 드러난 구멍 셋)
· D42–D46 **2026-09-02 확정** (8단계 MCP 표면 — ~~마지막 단계 게이트를 닫았다~~ 그때까지는 그랬다, D52 를 보라)
· D47 **2026-09-03 확정** (두 walk 이 건너뛰는 목록)
· D48–D52 **2026-09-03 확정** (9단계 질의 로그 기록 계약 — Q32를 열고 같은 날 닫았다)

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
| `SILLOK_WORKSPACE` | `.` | workspace 루트 (D4). ~~Q20의 project→경로 매핑은 닫지 않는다~~ — **D37이 "매핑을 만들지 않는다"로 닫았다.** 이 값 하나가 뿌리이고 한 인스턴스는 한 workspace를 섬긴다 |
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
migrations/003_ingest_counters.sql  kb_ingest_runs.files_deleted (D30)
migrations/004_event_tsv.sql        kb_events.tsv + GIN (D34)
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
| `NOT_FOUND` | 404 | 3단계에서는 **없는 경로**에만 썼다. ~~404 대 빈 결과는 Q12로 남는다~~ — **D35가 규칙을 줬다**: 지목한 조회는 404, 집합 질의는 빈 결과 |
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
| `POST /v1/docs/proposals` | ~~D3대로 쓰지 않는다. 충돌할 대상이 없다~~ — **D38이 `base_hash`를 주면서 충돌할 대상이 생겼다** |
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
- ~~**Q20 · Q10 · Q6–Q9 · Q12–Q19 · Q21 · Q23–Q25**는 그대로 열려 있다~~ — 2026-08-31 D22 시점의 목록이다.
  D30–D34가 Q6–Q10을 닫으면서 낡았다. **여기에 최신 목록을 다시 적지 않는다** — 사본이라서 낡은 것이고,
  새로 적으면 같은 자리에서 또 낡는다. 열린 질문의 정본은 [open-questions.md](../docs/open-questions.md) 하나다

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

재시도는 행을 하나 더 넣는다. `kb_events` 에 UNIQUE 도 없고 이 표면은 `CONFLICT` 를 내지 않는다.
(D24 시점에는 `003` 도 없었다. 그 번호는 뒤에 D30 이 `files_deleted` 로 가져갔고 이 결정과 무관하다.)

**필수 필드로 만든 내용 해시로 접는 안(B)을 버린 이유:** 같은 `project+module+root_cause`가 반복되는 것이
바로 `repeat_causes`다. 그 행들을 하나로 합치면 **D11이 탐지하려는 대상 자체가 사라진다.**
"중복 제거"처럼 보이지만 실제로는 통계를 파괴한다.

- `id`는 `bigserial`이고 payload에 유일성이 없다. 이 결정은 그 사실을 **확정**하는 것이지 발견하는 것이 아니다
- D21의 `CONFLICT`를 `save_event`는 발신하지 않는다. 발신자는 D32의 ingest 락 거절과
  D38의 `base_hash` 불일치 **둘**이다 — 각자 다른 `message`를 낸다
- **대가는 남는다.** HTTP 재시도 한 번이 `total`과 `repeat_causes`를 부풀린다.
  Q18이 지적한 해가 해소된 것이 아니라 **받아들여진 것**이다. 문서에 그렇게 적는다

### D25 검증 세부

**`project`** — 레지스트리를 두지 않는다. D5는 문자열이고, ~~`project`→경로 매핑(Q20)은 7단계에서 필요하다~~ —
D37이 매핑 자체를 만들지 않기로 했다. `project`는 끝까지 라벨이다.
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
- ~~**ingest 는 아직 없다 (5단계)**~~ — 5단계가 구현되면서 유도 규칙이 실제로 돈다.
  게이트 말고도 `scripts/check-index-parity.mjs` 가 두 목록을 대조한다
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
- **건너뛰는 디렉터리 목록에는 들어가지 않는다** — 게이트의 walk 와 같다. 목록은 **D47** 이 소유한다
  (그날은 `.git` 과 `node_modules` 둘이었고, D47 이 가상환경과 캐시를 더했다).
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

### 값을 어떻게 쓰는가 — 텍스트 리터럴과 명시적 캐스트 (2026-09-01 개정)

`pyproject.toml` 의 의존성에 `pgvector` 가 없고 `service.connect` 는 타입 어댑터를 등록하지 않는다.
정하지 않으면 구현자가 둘 사이에서 고른다.

**처음에는 `pgvector` 의 psycopg 어댑터를 골랐다. 구현하면서 뒤집었다** — 새 사실이 하나 나왔다.
이 환경의 **빌드 샌드박스에는 DNS 가 없어 이미지를 다시 만들 수 없다** (D28 이 이미 기록한 조건).
계약이 설치할 수 없는 것을 요구하면 5단계는 커밋된 구성에서 검사될 수 없다 —
그것은 D22 가 없애려던 상태 그대로다.

```text
INSERT INTO probe (v) VALUES (%s::vector)   -- v 는 "[0.5,0.25,0,...]" 문자열
읽어 온 값: [0.5,0.25,0,0,0,...      길이 1536      앞 두 값 보존됨
```

- **벡터를 `[a,b,c]` 텍스트로 만들어 `%s::vector` 로 캐스팅한다.** 각 값은 파이썬 `repr(float)` 다.
  컬럼이 `float4` 라 서버가 정밀도를 자르는 것은 어댑터를 써도 같다.
- **버린 위험을 검사로 갚는다.** 손으로 만든 형식은 아무도 검사하지 않는 두 번째 직렬화가 될 수 있다 —
  그래서 DB 검사가 **알려진 벡터를 넣고 다시 읽어 값이 보존되는지** 단언한다.
  검사가 있으면 그것은 사본이 아니라 계약이다.
- 그래서 의존성은 하나만 는다 — 임베딩 클라이언트뿐이다. 그것도 **키가 있을 때만 import 한다.**
  키가 없으면 그 함수가 아예 불리지 않으므로(D2) 커밋된 구성에서 의존성 없이도 검사가 돈다.
- **`uv.lock` 이 바뀌므로 D28 대로 `test` 이미지를 사람이 다시 빌드해야 한다.**
  그것을 강제하는 검사는 여전히 없다.

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
  그 project 청크 전 구간을 읽는다. HNSW 를 만들지 않는 결정은 **D33** 이 소유한다
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
Q10 을 닫으면 그 칸의 근거가 사라진다. **v1 은 이제 `CONFLICT` 를 실제로 발신한다** —
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
- `save_event` 는 그대로 발신하지 않는다 (D24).
  ~~`save_doc` 도 발신하지 않는다. 발신자는 이 한 자리뿐이다~~ —
  **D38 의 `base_hash` 불일치가 둘째 발신자다.** 두 자리는 서로 다른 `message` 를 낸다.

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

## D33 — 검색의 병합 · `score` · 중복 제거 · 순서 · `excerpt` (2026-09-01 확정)

[open-questions.md](../docs/open-questions.md) Q8을 마감한다. 6단계를 막는 둘 중 하나이고, 남은 하나는 Q9다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D33 | A | **두 순위를 RRF(`k=60`)로 합친다.** 각 순위는 완결된 정렬 위의 `rank()` 이고, `search_docs` 의 키워드 순위는 `plainto_tsquery('simple', …)` + `ts_rank(…, 1)` 이다 (`search_events` 는 D34 의 `websearch_to_tsquery`). `score` 는 그 RRF 값이며 **한 응답 안에서만** 비교된다. `top_k` 는 청크 수를 세고 **한 문서는 최대 2행**까지 차지한다. 최종 정렬은 `score DESC, repo, path, chunk_idx` 로 총순서다 | Q8 |

**Q8이 묻는 넷은 하나의 실패 모드로 이어져 있다 — 검색은 틀려도 예외를 던지지 않는다.**
`save_event` 가 필드를 빠뜨리면 `VALIDATION` 이 나가고 ingest 가 중단되면 `failed` 행이 남는다.
검색에는 그런 자리가 없다. 병합이 틀리면 결과가 **조금 덜 맞을 뿐**이고, 순서가 실행마다 달라져도
응답은 200에 여덟 줄이다. 모델은 그것을 근거로 쓰고 사람은 그것을 답으로 읽는다.
그래서 이 결정은 D32와 같은 순서로 쓴다 — **어떤 답이 조용히 틀리는가**를 먼저 적고 시끄러운 쪽을 고른다.

### 조용히 틀리는 자리

| 자리 | 어떻게 조용히 틀리는가 | 이 결정이 고른 것 |
|---|---|---|
| 벡터 후보 수집 | `ORDER BY embedding <=> q LIMIT n` 은 `embedding` 이 NULL 인 행도 **n개 그대로 돌려준다.** 벡터가 하나도 없는 오늘도 행이 나오고, 그것이 벡터 상위로 병합에 들어간다 | 벡터 순위는 `WHERE embedding IS NOT NULL` 을 **먼저** 건다 |
| 순위 함수 | `row_number()` 는 동점에 임의의 서로 다른 순위를 준다. 알파벳 순서가 RRF 점수로 둔갑해 벡터 순위를 이긴다 | 각 순위는 `rank()` — 동점은 동점으로 남는다 |
| `LIMIT` 절단 | 동점이 절단선에 걸치면 어느 행이 나가는지 계획이 정한다. 같은 질의가 실행마다 다른 여덟 줄을 낸다 | 최종 `ORDER BY` 가 총순서다 |
| `ts_rank` 정규화 | 기본값 `0` 은 길이를 보지 않아 분해능이 거의 없다. 순위가 사실상 전부 동점이 되고 RRF 는 타이브레이크 경연이 된다 | 정규화 플래그 `1` 고정 |
| 질의 파서 (`search_docs`) | `to_tsquery` 는 사용자 입력에 **예외를 던진다** — D21이 그것을 `INTERNAL` 고정 문구로 접는다. 오타가 서버 장애로 보인다 | `plainto_tsquery` — 예외도 부정 연산자도 없다 |
| 필터 적용 시점 | 병합 뒤에 거르면 걸러질 행이 후보 칸을 먹는다. 결과는 가득 차 있고 오류는 없다 | 필터는 **두 팔의 `WHERE`** 에 건다 |
| 질의 임베딩 실패 | 키워드 결과로 갈음하면 고장이 D2의 정상 상태와 **같은 모양**으로 200에 나간다 | 실패는 `INTERNAL` 이다. 갈음하지 않는다 |
| 중복 제거 | 규칙이 없으면 가장 긴 문서가 여덟 칸을 다 가져간다. 결과는 가득 차 있어 정상으로 보인다 | 문서당 2행 상한 |
| `score` 정규화 | 후보 풀 min–max로 `[0,1]` 에 맞추면 **1위가 언제나 `1.0`** 이다. 아무것도 안 맞은 질의도 만점을 낸다 | 정규화하지 않는다. RRF 원값 |
| `excerpt` | `ts_headline` 을 `content` 에만 걸면 `heading_path` 로만 매칭된 청크가 **강조 없는 앞머리**를 돌려준다 | `tsv` 생성식과 같은 텍스트에 건다 |
| 상한 미달 | 상한에 걸려 빠진 행을 다른 문서로 메우면 `top_k` 가 늘 채워져 상한이 도는지 알 수 없다 | 메우지 않는다. 다섯 줄이면 다섯 줄이다 |

### 실측 — 이 저장소의 색인 (문서 10개 · 청크 190개 · 벡터 0개)

**`ts_rank` 기본값에는 분해능이 없다.** `plainto_tsquery('simple','ingest')` 에 79개가 걸린다.

```text
정규화 플래그 0 (기본값)   서로 다른 점수  5 / 79
정규화 플래그 1 (결정값)   서로 다른 점수 73 / 79
```

**타이브레이크가 없으면 답이 하나가 아니다.** `ORDER BY ts_rank DESC LIMIT 8` 에 마지막 키만 바꾼 셋:

```text
c.id ASC  -> 428,435,481,357,402,409,415,423
c.id DESC -> 428,481,435,488,478,434,432,424
```

두 답이 모두 같은 `ORDER BY` 를 만족하고 교집합은 여덟 중 셋이다.

**벡터가 없는데 벡터 순위가 행을 낸다.** 오늘 `kb_chunks.embedding` 은 전부 NULL 이고 `NULL <=> v` 는 NULL 이다.

```text
ORDER BY c.embedding <=> q LIMIT 80          -> 80행
WHERE c.embedding IS NOT NULL 을 먼저 건 것   ->  0행
```

**한 문서가 칸을 독점한다.** 아래는 결정한 정규화 플래그 `1` 에서 잰 것이다.

```text
상한 없음    adr ×6, conventions ×1, spec ×1                              -- 문서 3개
문서당 2행   adr ×2, plan ×2, service-and-mcp ×2, conventions ×1, spec ×1 -- 문서 5개
```

**질의 파서 셋의 차이.**

```text
to_tsquery('simple','ingest &')          -> ERROR: no operand in tsquery
websearch_to_tsquery('simple','-백필')   -> !'백필' : 190개 중 184개 매칭, 서로 다른 점수 1개
plainto_tsquery('simple','-백필')        -> '백필'  : 부정 연산자가 없다
```

**`ts_headline` 을 `content` 에만 걸면 근거가 사라진다.** `plainto_tsquery('simple','선택지')`:

```text
tsv 매칭            10
content 안에 있음    4
heading_path 로만    6     <- 이 여섯은 강조 없는 앞머리를 돌려준다
```

매칭이 없는 텍스트에서 `ts_headline` 길이는 통제되지 않는다 — 다섯 청크에서 `2`·`119`·`122`·`149`·`224`자.
**2자짜리 발췌가 정상 출력이다.**

### D33 선택지

| ID | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D33 병합 | RRF, `k=60` | 점수 정규화 후 가중합 | 키워드 우선, 부족분만 벡터 | B는 `ts_rank` 와 코사인 거리를 같은 자로 잰다. 정규화 기준이 후보 풀이면 **풀이 바뀔 때마다 모든 점수가 바뀌고 1위는 언제나 만점**이다. 절대 기준을 쓰면 그 상수를 정할 근거가 없다. C는 두 경로가 합쳐지지 않는다 — 키워드가 여덟을 채우면 벡터는 영원히 호출되지 않고 그 상태가 정상과 구분되지 않는다 |
| D33 `k` | 60 | 0 | 10 | B는 1위에 `1.0`, 2위에 `0.5` 를 주어 **한 목록의 1위가 다른 목록 전체를 이긴다** — 하이브리드가 아니라 우선순위가 된다. C는 60보다 나은 근거가 없다. 60은 출판된 기본값이고, 튜닝할 데이터가 생기기 전에 고르는 값은 근거 없는 값이다 |
| D33 순위 | `rank()` | `row_number()` | `dense_rank()` | B는 동점에 임의의 서로 다른 순위를 준다 — 그 차이는 정렬 타이브레이크가 만든 것인데 RRF 점수가 되어 벡터 순위를 덮는다. C는 동점 무리의 크기를 지워 큰 무리와 작은 무리를 같게 취급한다 |
| D33 `score` | RRF 원값 | 응답 안에서 `[0,1]` 정규화 | 정수 순위 1..`top_k` | B는 위 표의 `score 정규화` 줄이다 — 0건에 가까운 질의도 1위가 `1.0` 이다. C는 정직하지만 동점 정보를 버리고, 이미 `results` 배열 순서가 같은 것을 말한다 |
| D33 중복 제거 | 문서당 2행, `top_k` 는 청크 수 | 문서당 1행 | 상한 없음 | B는 `path`+`heading_path`+`excerpt` 라는 응답 단위와 어긋난다. 긴 문서의 서로 다른 절 셋이 걸려도 하나만 나가고 **나머지가 있었다는 사실이 응답에 없다.** C는 실측대로 여덟 칸 중 여섯을 한 파일이 가져간다 |
| D33 파서 | `plainto_tsquery` | `websearch_to_tsquery` | `to_tsquery` | B는 `-단어` 하나로 184/190을 매칭시키고 그 전부가 동점이다 — 임의의 여덟 청크가 최상위 근거로 나간다. C는 사용자 입력에 예외를 던지고 D21이 그것을 `INTERNAL` 로 접는다. 오타를 낸 호출자가 서버 장애를 본다 |
| D33 `excerpt` | `ts_headline`(생성식과 같은 텍스트) + 앞머리 대체 | `left(content, 800)` | `ts_headline(content, …)` | B는 매칭 위치를 보여주지 않는다 — 2047자 청크의 앞 800자에 질의어가 없을 수 있고 모델은 왜 걸렸는지 모른 채 근거로 쓴다. C는 실측대로 `heading_path` 로만 걸린 청크(열 중 여섯)에서 강조 없는 앞머리를 낸다 |

### 1. 필터가 먼저다

- **`project`·`module`·`doc_type`·`status` 는 두 팔의 `WHERE` 에 건다.** 병합 뒤에 거르면
  걸러질 행이 후보 칸을 먹어 결과가 조용히 줄어든다.
- `project` 는 D25로 정규화한 값이다. 나머지 셋은 **필드가 없거나 `null` 이면 거르지 않는다.**
- **`status: "current"` 는 기본값이 아니다.** [service-and-mcp.md](../docs/service-and-mcp.md) 요청 예시의
  값일 뿐이다. 기본 필터로 만들면 검색이 **아직 열려 있는 Q23**(무엇이 언제 `stale` 이 되는가)에 묶인다.
- 필터 조립은 `event_stats` 의 관용구를 넓혀 쓴다 — 술어 목록과 params dict 를 함께 만들고
  호출자가 `WHERE` 에만 끼운다. f-string 으로 값을 섞지 않는다.

### 2. 병합 — RRF

```text
score(row) = Σ over lists  1 / (RRF_K + rank_in_that_list(row))
RRF_K = 60
```

- **`rank()` 는 점수 식만 본다. 타이브레이크 키는 `LIMIT` 이 자를 대상만 정한다.**
  둘을 한 `ORDER BY` 에 넣으면 `rank()` 가 `row_number()` 와 같아져 **동점이 사라지고
  정렬 키의 알파벳 순서가 그대로 점수가 된다** — 이 결정이 막으려는 바로 그것이다.
  그래서 두 절을 나눈다.

  ```sql
  -- 키워드 팔
  rank() OVER (ORDER BY ts_rank(c.tsv, tq, 1) DESC)        -- 점수가 되는 순위
  ORDER BY ts_rank(c.tsv, tq, 1) DESC,
           d.repo COLLATE "C", d.path COLLATE "C", c.chunk_idx   -- 풀에 들어갈 60행을 고른다
  -- 벡터 팔 (코사인 거리이므로 오름차순이 가까운 것이다)
  rank() OVER (ORDER BY c.embedding <=> q ASC)
  ORDER BY c.embedding <=> q ASC,
           d.repo COLLATE "C", d.path COLLATE "C", c.chunk_idx
  ```

  풀을 고르는 정렬은 여전히 **총순서**여야 한다 — 아니면 어느 60행이 들어오는지가 실행마다 다르다.
- **이벤트는 목록이 하나뿐이라 이 구분이 필요 없다.** 점수가 그 목록 순위의 단조 재표기이므로
  타이브레이크가 점수에 섞여도 다른 목록을 덮을 일이 없다. §7 의 정렬을 그대로 쓴다.
- **벡터 순위는 `WHERE c.embedding IS NOT NULL` 을 먼저 건다.** 최적화가 아니라 정확성이다 —
  위 실측의 80행이 그 증거다. **부분 임베딩은 정상 상태이므로**(D31) 이것은 오늘의 임시 방편이 아니라 영구 규칙이다.
- **벡터가 없는 청크는 "꼴찌"가 아니라 "그 목록에 없다".** RRF 는 없는 목록의 항을 더하지 않는다 —
  그것이 이 형식을 고른 이유다.
- **키가 없으면(D2) 벡터 목록이 비고, 공식은 바뀌지 않는다.** 분기를 만들지 않는다.
  한 목록만 있을 때 RRF 는 그 목록 순위의 단조 재표기이므로 **순서는 키워드 순서와 같다.**
- **후보 풀은 팔마다 60행 고정이다.** 요청 `top_k` 와 무관하다. `top_k` 에 비례시키면
  한쪽 팔 95위이면서 다른 쪽 1위인 행이 풀 120에서는 보이고 풀 80에서는 사라진다 —
  **`top_k` 가 길이만이 아니라 내용을 바꾸는 성질**이 생기고, 팔이 하나인 오늘은 드러나지 않다가
  키가 생기는 날 조용히 나타난다. 60은 `top_k` 상한 12의 다섯 배다.
- **풀은 DB 가 읽는 행 수이지 모델이 보는 양이 아니다** — `excerpt` 는 `LIMIT` 뒤 최대 12행에만 만든다.
  토큰 불변식은 `top_k` 와 800자가 지키지 풀 크기가 지키지 않는다.
- `RRF_K`·풀 크기·문서당 상한·`top_k` 상한은 서비스 모듈 상수로 둔다.

### 3. 키워드 순위의 정의

- **`search_docs` 의 질의 파서는 `plainto_tsquery('simple', query)` 다.** 예외를 던지지 않고,
  부정도 구문 검색도 없다. **`search_events` 는 `websearch_to_tsquery` 를 쓴다 — D34 가 소유한다.**
  두 엔드포인트가 다른 파서를 쓰는 이유는 입력의 성질이 다르기 때문이다: 문서 질의는 자연어 구절이고,
  이벤트 질의는 식별자·에러코드·날짜가 섞인다.
  대가는 정직하게 적는다 — 여러 낱말은 AND 로 묶이므로 `임베딩 백필 경로` 는 이 색인에서 0건이다.
  **0건은 오류가 아니다**(D21).
- **사전 이름을 파이썬에서 두 번 쓰지 않는다.** `EMBED_INPUT_SQL` 옆에 `TS_CONFIG` 상수를 두고
  질의 쪽도 그것을 쓴다. DDL 의 생성식과 갈라지면 색인과 질의가 다른 사전을 보게 되고,
  그 고장은 결과가 줄어드는 모양으로만 나타난다.
- **`ts_rank` 의 정규화 플래그는 `1` 로 고정한다** — `1 + log(길이)` 로 나눈다.
  기본값 `0` 은 실측에서 79행에 서로 다른 점수를 다섯 개밖에 주지 않는다.
  분해능이 없는 순위는 RRF 에 아무것도 기여하지 않는다. 플래그 `2`(길이로 직접 나눔)는
  청크 길이가 20자에서 2047자까지 벌어져 있어 짧은 조각을 과도하게 올린다.
- **낱말이 하나도 남지 않는 질의**(예: `---`)는 `search_docs` 의 **키워드 목록이 빈 것**이다. 오류가 아니다.
  벡터 팔은 그대로 돈다 — 그 문자열도 임베딩 입력으로는 유효하다.
  **빈 `query` 의 처리는 §6 이 소유한다.** 여기서 다시 정하지 않는다.

### 4. 질의 임베딩이 실패하면

- **`INTERNAL` 이다.** 키워드 결과로 갈음하지 않는다 — 갈음하면 고장이 D2의 정상 상태와
  구분되지 않고 200에 그럴듯한 여덟 줄로 나간다. `message` 는 D21의 고정 문자열이다.
- 질의 임베딩을 캐시하지 않는다. **검색 한 번에 호출 한 번**이다.
- 키가 없으면(D2) 호출 자체가 없다. 실패도 없다.

### 5. `score`

- **`score` 는 위 RRF 값이고 다른 무엇도 아니다.** 정규화하지 않고, 코사인 유사도도 `ts_rank` 도 아니다.
- **범위는 `0 < score ≤ 2/(RRF_K+1)` = `0.032787` 이다.** 두 목록 모두에서 1위인 행이 상한이다.
- **비교 가능성은 한 응답 안으로 한정된다.** 질의 사이에도, project 사이에도 비교되지 않는다.
- **`search_events` 에서 질의가 없으면 `score` 는 `null` 이다.** 0이 아니다 —
  0은 "맞았는데 점수가 0" 으로 읽히고, 그때는 순위가 없는 것이다 (D23 의 `avg_resolution_seconds` 선례).
- **그 사실이 눈에 보이는 것이 이 선택의 값어치다.** 목록이 하나뿐인 오늘,
  **결과가 있는 모든 질의의 1위 점수는 정확히 `0.016393`**(= 1/61)이다. 잘 맞았든 겨우 걸렸든 같은 숫자다.
  임계값을 걸려는 소비자는 즉시 그것이 불가능함을 본다. `[0,1]` 정규화는 정반대로 **언제나 확신처럼 읽힌다.**
- **소비자는 점수를 비교할 필요가 없다** — `results` 는 이미 그 순서로 정렬돼 있다.
- 자릿수는 6자리에서 반올림한다. 표시 안정성 때문이고, 정렬은 반올림 전 값으로 한다.
- 부동소수 덧셈의 순서를 고정한다 — **키워드 항을 먼저 더한다.** 순서를 정하지 않으면
  같은 입력이 마지막 자리에서 다른 값을 낼 수 있고 그 차이가 동점 판정을 바꾼다.

### 6. 중복 제거와 `top_k`

- **`top_k` 는 청크 수를 센다.** 응답 단위가 청크(`path`+`heading_path`+`excerpt`)이므로
  문서 수를 세는 해석은 응답 형태와 어긋난다.
- **기본 8, 최대 12다. 범위 밖은 `VALIDATION` 으로 거절한다** — 조용히 12로 접지 않는다(D25 선례).
  이것은 두 엔드포인트에 같이 걸린다.
- **`query` 의 필수 여부는 엔드포인트마다 다르다.**
  - **`search_docs` 에서 `query` 는 필수다.** 없거나 공백뿐이면 `VALIDATION` 이다 —
    문서 검색에는 질의 말고 신호가 없어 필터만으로는 "관련 문서 전부"가 되고, 그것은 설계 위반이다.
  - **`search_events` 에서 `query` 는 선택이다.** 없거나 공백뿐이면 필터 집합이 그대로 결과이고
    `score` 는 `null` 이다 (D34 §3). 이벤트는 필터(project·kind·기간)만으로도 뜻이 있는 질의가 된다 —
    "지난 달 auth 의 실패" 는 낱말이 없어도 완결된 요청이다.
  - 값이 있는데 렉심이 하나도 나오지 않으면 **두 엔드포인트 모두 키워드 술어를 건다.**
    그 갈래를 "질의 없음"으로 접으면 `"???"` 를 친 사람이 필터 집합을 검색 결과로 받는다.
    **결과는 엔드포인트마다 다르다.** `search_events` 는 목록이 하나뿐이라 0건이다 (D34 §3).
    `search_docs` 는 키가 있으면 **벡터 팔만 남은 RRF** 이고, 키가 없으면 두 목록이 다 비어 0건이다.
    v1 은 키가 없어 관측상 같지만 규칙이 같은 것은 아니다.
- **한 문서는 최대 2행을 차지한다.** 1은 긴 문서의 서로 다른 절이 함께 걸리는 정당한 경우를 지우고,
  상한 없음은 실측대로 여덟 칸 중 여섯을 한 파일에 준다. 2이면 `top_k=8` 에서 **최소 네 문서**가 보장된다.
- **상한은 병합 뒤 `LIMIT` 앞에 적용한다.** 문서별로 `score DESC, chunk_idx` 로 순위를 매겨
  3위 이하를 버리고, 남은 것을 최종 정렬해 자른다. 그래서 `top_k=8` 의 결과는
  `top_k=12` 결과의 **앞 여덟 줄**이다.
- **버린 행을 다른 문서로 메우지 않는다.** 메우면 `top_k` 가 늘 가득 차 상한이 도는지 아무도 모른다.
  **여덟을 요청하고 다섯이 오는 것이 정상이다** — 그 사실을
  [service-and-mcp.md](../docs/service-and-mcp.md) §검색에 한 줄로 적는다. 결과가 없어서가 아니다.
- **응답에는 무엇이 가려졌는지 나타나지 않는다.** 필드를 늘리지 않았다 —
  값을 하나 더 실으면 행마다 토큰이 붙는다. 대신 그 자리를 `get_file`(7단계)이 받는다.
  해가 없어진 것이 아니라 **받아들여진 것이다**(D24 선례).

### 7. 순서

- **최종 정렬은 `score DESC, d.repo COLLATE "C", d.path COLLATE "C", c.chunk_idx` 다.**
  `kb_documents` 의 `UNIQUE (project, repo, path)` 와 `kb_chunks` 의 `UNIQUE (document_id, chunk_idx)` 가
  이것을 한 project 안의 총순서로 만든다. **같은 입력에 같은 여덟 줄이 나온다.**
- **`repo` 는 오늘 전부 빈 문자열이지만 키에 넣는다.** Q22가 그 컬럼에 의미를 주는 날
  정렬 키를 다시 협상하지 않기 위해서다. 오늘의 비용은 없다.
- **`c.id` 로 타이브레이크하지 않는다.** 재색인은 청크를 지우고 다시 넣으므로 `bigserial` 이 바뀐다.
  내용이 그대로인데 순서가 달라진다. `(path, chunk_idx)` 는 내용의 자리에서 나오므로 재색인을 넘어 안정하다.
- **`COLLATE "C"` 를 명시한다.** 기본 `ORDER BY path` 는 DB 콜레이션 순서지 바이트 순서가 아니다.
  D30이 스캔 순서에 대해 정한 것과 같은 이유이고, 5단계 검사가 이미 같은 함정을 겪었다.
- **`search_events` 의 정렬은 두 갈래이고 둘 다 여기서 못 박는다.** D34 는 순서를 정하지 않는다 —
  이 결정이 소유한다.

  ```sql
  -- 질의가 있을 때 (키워드 팔의 rank() 도 이 정렬 위에서 매긴다)
  ORDER BY ts_rank(e.tsv, tq, 1) DESC, e.occurred_at DESC, e.id DESC
  -- 질의가 없거나 공백뿐일 때 (score 는 null)
  ORDER BY e.occurred_at DESC, e.id DESC
  ```

  이벤트 팔도 정규화 플래그 `1` 을 쓴다 — 이벤트 텍스트는 청크보다 짧아 동점이 더 잘 나고,
  분해능이 없는 순위는 RRF 에 아무것도 기여하지 않는다.
  **최종 타이브레이크는 `id DESC` 다.** 이벤트 행은 갱신되지도 재삽입되지도 않으므로 `id` 가 안정한 키이고,
  방향은 `occurred_at DESC` 와 같은 쪽으로 맞춘다 — 같은 시각에 저장된 둘 중 나중 것이 앞이다.
  문서 쪽이 `(path, chunk_idx)` 를 쓰는 이유는 재색인이 `bigserial` 을 바꾸기 때문이고,
  이벤트에는 그 경로가 없다 (D24: append-only).
- **이벤트는 목록이 하나뿐이다** (D34: v1 은 이벤트를 임베딩하지 않는다).
  RRF 는 한 목록 위에서 그 순위의 단조 재표기이므로 `score` 는 `1/(60+rank)` 이고 순서는 위 정렬과 같다.
- **왜 v1에서 중요한가:** 9단계가 `kb_query_logs.hit_paths` 를 남기고, §9 완료 조건이
  검색 0건을 `hit_count=0` 으로 요구한다. 같은 질의가 실행마다 다른 행 집합을 돌려주면
  그 원장은 무엇의 기록도 아니다.

### 8. `excerpt`

```sql
ts_headline('simple', <생성식과 같은 텍스트>, <같은 tsquery>,
            'StartSel="",StopSel="",MaxWords=60,MinWords=25,MaxFragments=1')
```

- **입력 텍스트는 `EMBED_INPUT_SQL` 이다** — `tsv` 생성식·백필 입력과 **같은 식**이라야
  발췌가 매칭 근거를 보여준다. `content` 에만 걸면 실측대로 `heading_path` 로만 걸린 청크가
  근거 없는 앞머리를 낸다. **파이썬에서 이어 붙이지 않는다** — 그 순간 같은 규칙의 세 번째 사본이 생기고
  5단계가 만든 `IS DISTINCT FROM` 검사가 그것을 물지 않는다(D31).
- **강조 마커를 넣지 않는다**(`StartSel=""`, `StopSel=""`). 마커는 토큰이고 모델이 되받아 쓴다.
- **키워드로 걸리지 않은 행에는 `ts_headline` 을 쓰지 않는다.** 벡터로만 걸린 행과 낱말이 없는 질의가 그 경우다.
  매칭이 없으면 출력 길이가 통제되지 않는다 — 실측에서 2자짜리 발췌가 나왔다.
  그 행의 `excerpt` 는 **`left(content, 800)`** 이다. 어느 쪽이든 결과는 하나의 결정론적 문자열이다.
- **800자에서 자르고, 잘렸으면 앞 799자 + `…`(U+2026) 한 글자다.** 붙이지 않으면 절단과
  청크의 끝을 구분할 수 없다. **그 한 글자가 API 가 넣는 유일한 문자다** — 빈 결과에 문장을 넣지 않는 금지와 다르다.
- 응답 본문의 천장은 `top_k` × 800 = **9,600자**다. `top_k` 와 함께 토큰 불변식을 지탱하는 두 번째 장치다.
- **`ts_headline` 은 `LIMIT` 뒤에만 돈다.** 후보 풀에 걸면 원문을 그만큼 다시 파싱한다.

### 9. 코드 배치

- **병합·문서당 상한·정렬은 DB 를 모르는 순수 모듈**(`src/sillok/search.py`)이고 SQL 은 `service.py` 에만 있다(D19).
  `ingest.py` 선례와 같은 갈래이고 이유도 같다 — 검사가 싸다.
- **`WHERE c.id = ANY(…)` 는 순서를 보존하지 않는다.** 마지막 본문 조회 뒤 파이썬이
  병합 순서대로 다시 늘어놓는다. 이것을 빠뜨리면 결정성이 조용히 무너진다.

### 어겨지면 무엇이 비명을 지르는가

| 규칙 | 어겨지면 | 무엇이 무는가 |
|---|---|---|
| 벡터 목록에 `IS NOT NULL` | 벡터 없는 청크가 벡터 상위로 병합에 들어간다 | 6단계 DB 검사 — 벡터 0개인 색인에서 벡터 후보가 0행임을 단언 |
| 순위는 `rank()` | 정렬 타이브레이크가 점수로 샌다 | 6단계 순수 검사 — 동점 입력에 같은 순위가 나오는지 |
| 필터는 두 팔의 WHERE | 걸러질 행이 후보 칸을 먹는다 | 6단계 DB 검사 — 필터로 배제될 문서를 상위에 놓고 결과 수를 본다 |
| 최종 정렬이 총순서 | 같은 질의가 실행마다 다른 행을 자른다 | 6단계 DB 검사 — 동점 무리를 만드는 질의를 반복 호출해 같은 목록 단언 |
| `COLLATE "C"` | 같은 색인이 DB 로케일마다 다른 순서를 낸다 | 위와 같은 검사가 로케일 의존 문자를 포함한 경로로 |
| 문서당 2행 | 한 문서가 `top_k` 를 다 가져간다 | 6단계 DB 검사 — 한 문서에 매칭 청크 다섯을 만들고 2행을 단언 |
| 상한 미달을 메우지 않음 | 상한이 도는지 알 수 없게 된다 | 같은 검사가 반환 행 수를 함께 단언 |
| `top_k` 는 앞자리 성질 | 8의 결과가 12의 앞 여덟이 아니게 된다 | 6단계 순수 검사 — 같은 후보로 8과 12를 만들어 앞 여덟을 대조 |
| `search_docs` 는 `plainto_tsquery` | 사용자 오타가 `INTERNAL` 이 되거나 색인 전체가 매칭된다 | 6단계 검사 — `&`·`-단어`·`""` 입력이 예외 없이 지나는지 |
| 질의 임베딩 실패는 `INTERNAL` | 고장이 정상 상태와 같은 모양으로 200에 나간다 | 6단계 검사 — 임베딩을 실패시키고 500과 고정 문구를 단언 |
| `top_k` 범위 밖은 `VALIDATION` | 조용히 12로 접혀 호출자가 자기 요청을 오해한다 | 6단계 검사 |
| `excerpt` 가 생성식과 같은 텍스트 | `heading_path` 로 걸린 행의 발췌에 질의어가 없다 | 6단계 DB 검사 — 제목에만 낱말이 있는 청크로 |
| `excerpt` 800자 + 절단 표시 | 응답 하나가 토큰 불변식을 깨거나 절단이 감춰진다 | 6단계 DB 검사 — 최장 청크로 상한과 말줄임표 단언 |
| `score` 미정규화 | 1위가 언제나 만점이 되어 확신처럼 읽힌다 | 6단계 DB 검사 — 아무거나 걸리는 질의의 1위가 `1/(k+1)` 임을 단언 |
| 후보 풀이 고정 | `top_k` 가 결과의 내용까지 바꾼다 | **없다** — 두 목록이 다 차는 상태를 만들려면 키가 필요하다. 순수 검사로 병합 함수만 잠근다 |
| `ts_rank` 정규화 `1` | 키워드 순위의 분해능이 사라진다 | **없다** — 덜 맞는 것은 실패로 보이지 않는다. 상수와 근거를 주석에 남기는 것이 전부다 |

D28이 정한 대로, **통과 출력만으로는 규칙이 살아 있는지 알 수 없다.** 위에서 "없다"로 남은 둘은
검사를 만들 수 없는 자리이지 만들지 않아도 되는 자리가 아니다 — 키가 있는 상태의 검사 경로가
D31이 남긴 숙제와 같은 자리에서 함께 열린다.

### 기존 결정을 뒤집지 않는다

- **D2 그대로.** 키가 없으면 벡터 목록이 비고 결과는 키워드 순서다. 분기가 아니라 같은 공식이다.
- **D14 그대로.** 구성은 `simple` 이고 이 결정이 더하는 것은 정규화 플래그와 파서다.
- **D21 그대로.** 빈 결과는 200에 `{ "results": [] }` 이고, 새 에러 코드도 새 발신 조건도 없다.
  파서 선택은 오히려 D21이 `INTERNAL` 로 접을 일을 없앤다.
- **D23 그대로.** `event_stats` 는 벡터를 쓰지 않고 이 결정은 통계 경로를 건드리지 않는다.
- **D25 그대로.** `top_k` 범위와 빈 `query` 검증은 서비스에 두고 DDL 에 CHECK 를 더하지 않는다.
- **D30·D31·D32 그대로.** `commit_sha` 는 v1 내내 빈 문자열로 응답에 남고,
  부분 임베딩이 정상 상태라는 D31의 선언이 §2의 `IS NOT NULL` 규칙의 근거다.
- **새 마이그레이션이 없다.** 실측에서 190행 질의는 밀리초이고 플래너는 GIN 조차 쓰지 않는다.
  **이 규모에서 느려서 틀리는 것은 없다 — 틀려서 틀린다.**

### D14 오귀속 정정 — HNSW 는 이제 D33 이 소유한다

`HNSW 는 D14 가 이미 미룬 자리다`(D31 본문)라는 문장은 **틀렸다.**
D14는 `본문 한·영 혼용, tsvector 구성 simple` 이고 HNSW 와 무관하다.
HNSW 를 미룬 문장은 [data-model.md](../docs/data-model.md)와 [plan.md](../docs/plan.md)에만 있었고
D 번호가 붙어 있지 않았다 — 지금까지 그것은 결정이 아니라 산문이었다.

**D33이 그 자리를 소유한다: v1은 HNSW 를 만들지 않는다.** 근거는 실측이다 —
청크 190행에 채워진 벡터 0개이고 전 구간 스캔이 밀리초다. 인덱스가 이득을 내는 규모가 아니다.
만드는 결정은 별도 번호를 받고, 그때 함께 정해야 할 것을 여기 적어 둔다:
**마이그레이션 러너는 파일 하나가 트랜잭션 하나이므로 `CREATE INDEX CONCURRENTLY` 를 쓸 수 없고**(D32),
인덱스 생성은 `serve` 기동 시 bind 전에 테이블을 잠근 채 돈다(D17).
그리고 `IF NOT EXISTS` 는 같은 이름이 **다른 모양**으로 있으면 고치지 않고 러너는 성공을 보고한다 —
인덱스 종류를 바꾸는 변경은 그 자체로 조용히 실패한다.

**옛 문구는 게이트의 `RETIRED` 에 등록한다.**

### 낡는 사본은 다섯이다

- [CLAUDE.md](../CLAUDE.md) 검색 규칙의 `(병합 방식 미정 — Q8)`
- [data-model.md](../docs/data-model.md) §검색의 `가능하면 RRF로 합친다`
- [plan.md](../docs/plan.md) §6 의 같은 요약 줄
- [service-and-mcp.md](../docs/service-and-mcp.md) §검색 — `score`·`excerpt` 설명과
  "`top_k` 보다 적게 올 수 있다" 한 줄을 **더한다**
- [open-questions.md](../docs/open-questions.md) Q8 에 `— **해결 → D33**`

[conventions.md](../docs/conventions.md) 문서 지도에는 **검색 병합·순위·`score` 정의·`excerpt` 구성**을
소유한 파일이 없었다 — `score` 가 응답에 **있다**는 사실에는 소유자가 있었고
**무엇을 뜻하는가**에는 없었다. 지도의 ADR 행에 그것을 더한다.

### D33이 닫지 않는 것

- ~~**Q9 미해결**~~ — **D34 가 같은 자리에서 닫았다.** 이 결정은 이벤트 쪽에
  병합 공식·`score` 정의·정렬 두 갈래를 주지만 **합칠 목록을 주지 않았다.**
  D34 의 `004` 가 `kb_events.tsv` 를 만들면서 그 목록이 생겼다 — 둘이 함께 6단계를 열었다
- **`plainto_tsquery` 의 AND 가 재현율을 얼마나 깎는지 재지 않았다.** `임베딩 백필 경로` 가 0건인 것은
  실측했지만 실사용 질의 분포가 없다. 조사가 붙어 다른 토큰이 되는 손실은 `simple` 구성(D14)의 성질이고
  `kb_chunks` 와 `kb_events` 에 똑같이 걸린다 — **v1 은 그것을 받아들인다.**
  9단계 `kb_query_logs` 에 `hit_count=0` 이 쌓이는 것이 이 결정을 다시 볼 신호다
- **`RRF_K = 60` 을 이 색인에서 검증하지 않았다.** 목록이 하나뿐이라 `k` 는 순서에 아무 영향이 없다.
  두 목록이 다 차는 상태를 이 저장소는 아직 만들 수 없다 — 키가 필요하고 `--profile test` 는 키를 갖지 않는다
- **문서당 상한 2가 가린 행을 소비자가 알 방법이 없다.** 필드를 늘리지 않기로 한 대가다
- **`score` 를 임계값으로 쓰는 소비자를 막을 장치가 없다.** 계약과 도구 설명이 말할 뿐이고,
  1위가 언제나 `0.016393` 인 것은 두 목록이 다 차는 날 더 이상 참이 아니다
- **페이지네이션은 없다**(Q13). `top_k` 를 넘는 결과를 보는 방법이 없다
- **이벤트 히트를 `kb_query_logs` 의 어디에 적을지 정하지 않았다.** `hit_paths` 는 `text[]` 인데
  `search_events` 의 결과는 경로가 아니라 `id` 다. **그때까지 이벤트 질의는 `hit_paths` 를 NULL 로 두고
  `hit_count` 만 쓴다** — 잠정 규칙이고 9단계가 확정한다.
  → **D49 가 그 잠정 규칙을 그대로 확정했다.** 이벤트는 NULL 이다
- **Q22가 열려 있다.** 정렬 키에 `repo` 를 넣었지만 그 값의 의미는 정해지지 않았다
- **`ts_headline` 의 실행 비용을 재지 않았다.** 12행 × 최대 2047자라 문제가 될 규모가 아니라고
  판단했을 뿐 실측하지 않았다. 6단계 구현이 확인할 자리다


## D34 — 이벤트의 키워드 경로 · `pg_trgm` · 이벤트 벡터 (2026-09-01 확정)

[open-questions.md](../docs/open-questions.md) Q9를 마감한다. 6단계를 막는 둘 중 하나다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D34 | A | `kb_events` 에 `tsv` 생성 컬럼과 GIN 을 `004` 로 더한다 — 입력은 `title`·`summary`·`root_cause`·`resolution` 넷. **`pg_trgm` 은 v1에서 쓰지 않기로 정하고** 선언은 남긴다. **v1은 이벤트를 임베딩하지 않는다** — `search_events` 에 벡터 갈래를 두지 않고 `kb_events_hnsw` 도 만들지 않는다 | Q9 |

**Q9가 든 셋은 서로 다른 결함이 아니라 같은 부류의 세 얼굴이다 — 검색이 조용히 덜 맞히는 것.**
`tsv` 가 없으면 `search_events(query=…)` 는 필터만 남고, 그 응답은 200에 `{ "results": [] }` 다.
D21이 빈 결과를 오류가 아니라고 못 박았으므로 클라이언트는 계약대로 "Sillok 에 없음"이라고 말한다.
**있는 이벤트를 없다고 말하는데 어디에도 오류가 없다.**
전부 NULL 인 벡터에 `<=>` 를 거는 것도, 임계값이 SQL 밖에 있는 `pg_trgm` 연산자를 쓰는 것도 같은 모양으로 틀린다.

### 조용히 틀리는 자리

| 자리 | 어떻게 조용히 틀리는가 | 이 결정이 고른 것 |
|---|---|---|
| 이벤트 키워드 | 수단이 없어 질의어가 무시된다. 필터만 걸린 집합이 나가고 오류는 없다 | `kb_events.tsv` + GIN |
| 생성식의 NULL | `coalesce` 없이 이으면 `root_cause` 하나가 NULL 인 행의 `tsv` 가 통째로 NULL 이 되어 **어떤 질의에도 안 걸린다** | 네 필드를 전부 `coalesce` 로 감싼다 |
| 생성식 변경 | `ADD COLUMN IF NOT EXISTS` 는 컬럼이 있으면 **식이 달라도 건너뛴다.** 파일과 DB 가 갈라지고 러너는 성공을 보고한다 | 식을 모듈 상수로 두고 DB 의 실제 식과 대조하는 검사 |
| 사전 이름 | 색인은 `simple`, 질의는 다른 구성이면 히트가 0이다. 오류가 아니다 | 사전 이름도 같은 상수에서 나온다 |
| 렉심 0개 질의 | 값이 있는 질의를 "질의 없음"으로 접으면 **최근 이벤트가 검색 결과로 나간다** | 값이 있으면 술어를 걸고 0건을 돌려준다 |
| `pg_trgm` 의 `%` | 기본 임계값에서 짧은 질의는 아무것도 맞히지 못한다. **인덱스는 쓰이고** recheck 가 전량을 버린다 | v1에서 쓰지 않는다 |
| `pg_trgm` 의 `%>` | 임계값이 SQL 이 아니라 세션 GUC 다. 같은 질의가 서버 설정에 따라 다른 집합을 돌려준다 | 위와 같다 |
| 이벤트 벡터 | 전부 NULL 인 컬럼에 `<=>` 를 걸면 거리가 NULL 이라 **정렬이 물리 순서**가 된다 | v1은 벡터 갈래를 두지 않는다 |
| 이벤트 백필 | ingest 로 채우면 마지막 run 이후에 저장된 이벤트만 벡터가 없다 — 같은 질의의 순서가 **색인 주기**에 따라 달라진다 | 위와 같다 |
| `save_event` 인라인 임베딩 | 실패에 거절하면 Git 에 원본 없는 데이터를 잃고, 받아들이면 그 행은 영원히 NULL 이다 (Q7의 함정) | 위와 같다 |

### 실측 — `simple` 이 조사를 붙인 채 색인한다

이 저장소의 색인본(190 청크)에서 같은 텍스트를 놓고 셋을 비교했다.

```text
질의             tsv    부분문자열   %> (word_similarity)
이벤트            26        30        30
이벤트를           3         3        30
임베딩            19        28        28
마이그레이션       13        22        22
색인              32        55        48
save_event        15        15        24
kb_events         11        14        43
2026-08-31        43        43        47

to_tsvector('simple','… save_event … 2026-08-31')
  -> '-08' '-31' '2026' 'event' 'save' …
```

식별자와 날짜는 온전히 걸린다. 손실은 한국어 명사에만 있고 32~42%다 —
조사가 붙으면 다른 토큰이기 때문이다.
**이 손실은 이벤트의 성질이 아니라 D14(`simple`)의 성질이고, `kb_chunks` 가 이미 같은 손실을 안고 있다.**

### 실측 — `pg_trgm` 을 그대로 쓰면

```text
pg_trgm.similarity_threshold         0.3
pg_trgm.word_similarity_threshold    0.6

질의           max(similarity)   % 히트   max(word_similarity)   <% 히트
오프셋             0.0423           0            0.7500            1
save_event         0.1571           0            1.0000            1

EXPLAIN (ANALYZE) SELECT count(*) FROM big WHERE txt % '오프셋';   -- 5만 행
  Bitmap Heap Scan (actual rows=0)
    Rows Removed by Index Recheck: 50000
    ->  Bitmap Index Scan on big_trgm (actual rows=50000)

%> 5만 행 순차 스캔 402 ms   ·   같은 결과를 내는 ILIKE '%…%' 58 ms
```

`%` 는 **인덱스를 타고, 전량을 recheck 로 버리고, 0건을 돌려준다.** 오류는 없다.
`%>` 는 맞히지만 위 표에서 `kb_events` 를 14 대신 43으로 부풀리고 `색인` 은 55 대신 48로 **덜** 맞힌다 —
부분 문자열의 상위집합도 부분집합도 아니다. 그리고 그 경계를 정하는 것은 SQL 이 아니라 GUC 다.

### 실측 — 생성 컬럼을 나중에 더하는 비용과 함정

```text
-- kb_events 모양 5만 행에 생성 컬럼을 나중에 더한다
ALTER TABLE ev ADD COLUMN IF NOT EXISTS tsv tsvector GENERATED ALWAYS AS (…) STORED;
ALTER TABLE                     968 ms    기존 5만 행 전부 채워짐 (tsv NULL 0건)
테이블 14 MB -> 36 MB (재작성)  ·  잠금 AccessExclusiveLock
CREATE INDEX … USING gin (tsv)  700 ms

-- 같은 파일의 식을 고쳐 다시 돌린다 (D17 러너는 매 기동 전부 재실행한다)
NOTICE:  column "tsv" of relation "ev" already exists, skipping
ALTER TABLE                              <- 러너는 성공을 보고한다
pg_get_expr -> (옛 식 그대로)             <- 파일과 DB 가 갈라졌다

-- coalesce 를 빼면
root_cause = NULL 인 행:  tsv IS NULL = t,  어떤 질의에도 안 걸린다 (오류 없음)

-- 한 인자 형태는 애초에 못 쓴다
ALTER TABLE b ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector(t)) STORED;
ERROR:  generation expression is not immutable

-- PG16 에는 생성식을 바꾸는 문법이 없다
ALTER TABLE kb_chunks ALTER COLUMN tsv SET EXPRESSION AS (…);
ERROR:  syntax error at or near "EXPRESSION"
```

두 번째 블록이 이 결정의 검사 하나를 강제한다 — **파일은 새 식을 말하는데 DB 는 옛 식을 갖고,
러너는 성공을 보고한다.** 마지막 블록은 개정 비용을 정한다(아래 §1).

### 실측 — 벡터가 전부 NULL 인 컬럼에 거리를 걸면

```text
SELECT id, embedding <=> '[0,0,…]'::vector AS distance FROM ev ORDER BY 2 LIMIT 8;
 id | distance
  1 |            거리가 전부 NULL -> 정렬 키가 없다. 반환 순서는 물리 순서다. 오류 없음.
SELECT count(*) FROM ev WHERE embedding IS NOT NULL;  -> 0
```

### D34 선택지

| ID | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D34 키워드 | `tsv` 생성 컬럼 + GIN (`kb_chunks` 와 같은 모양) | `ILIKE '%q%'` 만 | 애플리케이션이 `to_tsvector` 를 계산해 일반 컬럼에 넣는다 | B는 다중 낱말·구문을 받는 수단을 잃는다. C는 저장 시점의 코드가 값을 만들어 **옛 행이 옛 규칙으로 남고 아무도 모른다.** 생성 컬럼은 `ALTER` 하나가 기존 행까지 다시 계산한다(실측) |
| D34 입력 필드 | `title`·`summary`·`root_cause`·`resolution` | `summary` 만 (벡터와 같게) | 위 넷 + `payload` | B는 "왜 깨졌나 / 어떻게 고쳤나"를 묻는 질의를 놓친다 — 실측에서 `root_cause` 에만 있는 낱말은 어느 쪽으로도 안 걸렸다. C는 클라이언트가 넣는 임의 JSON 을 색인에 들여 `tsv` 크기의 상한을 없애고 `payload` 내부 값이 히트로 새어 나온다 |
| D34 `pg_trgm` | 선언을 남기고 **쓰지 않는다고 적는다** | 지금 쓸 자리를 준다 | 선언을 뺀다 | B는 위 실측이 막는다 — `%` 는 0건, `%>` 는 식별자에서 3배로 부풀고 `색인` 에서는 덜 맞히며 경계가 GUC 다. C는 **D17 러너가 매 기동 재실행하는 파일에 `DROP EXTENSION` 을 넣는 것**이다 |
| D34 이벤트 벡터 | v1은 채우지 않는다 | `save_event` 가 인라인으로 임베딩 | D31의 백필을 이벤트로 넓힌다 | B는 Git 에 원본이 없는 유일한 쓰기 경로를 외부 API 에 묶는다 — 실패하면 이벤트를 잃거나(거절) 그 행이 영원히 NULL 이다(수용). C는 이벤트가 계속 쌓이고 ingest 는 가끔 도니 **부분 벡터가 과도 상태가 아니라 정상 상태**가 되고, 같은 질의의 순서가 색인 주기에 따라 달라진다 |

### 1. `004_event_tsv.sql` — 컬럼 하나와 인덱스 하나

```sql
ALTER TABLE kb_events ADD COLUMN IF NOT EXISTS tsv tsvector
  GENERATED ALWAYS AS (
    to_tsvector('simple',
      coalesce(title, '')      || ' ' || coalesce(summary, '')    || ' ' ||
      coalesce(root_cause, '') || ' ' || coalesce(resolution, ''))
  ) STORED;

CREATE INDEX IF NOT EXISTS kb_events_tsv ON kb_events USING gin (tsv);
```

- **DDL 정본은 [data-model.md](../docs/data-model.md) 다. 거기를 먼저 고친다**(D30 선례).
  `002` 는 주석 외에 고치지 않는다 — 이미 테이블이 있는 DB 에서는 조용히 무시된다.
  `003` 이 같은 이유로 남긴 주석과 짝을 맞춰 `004` 에도 **정본 DDL 과 실제 컬럼 순서가 갈라진다**는 사실을 적는다.
- **백필 코드가 없다.** 생성 컬럼이라 `ALTER` 가 기존 행을 전부 채운다(실측).
  Q7의 함정이 이 경로에는 생기지 않는데, 값의 출처가 **행 자신**이고 외부 API 가 아니기 때문이다.
  `save_event` 는 이 컬럼을 쓰지 않는다 — `GENERATED ALWAYS` 는 쓸 수 없다.
- **비용은 테이블 재작성이고 잠금은 `AccessExclusiveLock` 이다**(실측). D17이 이것을 bind 전에 돌린다.
  오늘 `kb_events` 는 0행이라 즉시 끝나고, `IF NOT EXISTS` 라서 **재작성은 DB 당 한 번**이다.
- **`CREATE INDEX CONCURRENTLY` 를 쓸 수 없다** — 러너는 파일 하나를 트랜잭션 하나로 돌린다(D32).
- **입력 네 필드는 v1 고정이다.** PG16에는 생성식을 바꾸는 문법이 없고(실측),
  `DROP COLUMN` + 재추가를 마이그레이션 파일에 넣으면 **기동마다 테이블을 다시 쓴다**(D31이 경고한 부류).
  식을 바꾸려면 D34 개정과 **일회성 복구 SQL**(마이그레이션 파일이 아니라 사람이 한 번 돌리는 문장)이 함께 온다.
- 파괴적 문장을 넣지 않는다. `UPDATE`·`DELETE` 는 매 기동 다시 돈다.

### 2. 무엇을 잇는가

- **네 필드를 이 순서로, 전부 `coalesce` 로 감싸고, 구분자는 한 칸이다.**
  `title`·`summary` 는 NOT NULL 이지만 감싼다 — 규칙이 필드마다 다르면 다음 사람이 `root_cause` 에서도 뺀다.
  실측 그대로 그 순간 행 하나가 검색에서 사라진다.
- **`payload`·`module`·`related_doc_path`·`severity` 는 넣지 않는다.** 앞의 하나는 임의 JSON 이고
  나머지는 필터 축이다. 필터로 풀 것을 키워드로 푸는 것은 이미 금지돼 있다.
- **식은 모듈 상수 하나에서 나온다** — `EVENT_TSV_INPUT_SQL`(D31의 `EMBED_INPUT_SQL` 선례).
  사전 이름도 상수 `TS_CONFIG` 로 두고 **질의 쪽이 같은 상수를 쓴다.**
- **`root_cause`·`resolution` 으로 걸린 히트는 응답만 보고 설명할 수 없다.**
  `search_events` 응답 여덟 필드에 그 둘이 없다. 네 필드를 색인하기로 한 대가이고,
  원문은 `get_event`(7단계)에서 본다. **응답 계약은 D34가 바꾸지 않는다.**
- **벡터와 키워드의 입력이 다르다.** D31은 `kb_chunks` 에서 둘을 같은 식으로 맞췄다.
  이벤트는 임베딩 입력이 `summary` 만이고 키워드 입력이 넷이다. v1에는 이벤트 벡터가 없으므로
  어긋날 대상이 없지만, **이벤트 벡터를 채우는 결정은 이 비대칭을 먼저 봐야 한다.**

### 3. 질의 쪽

- `websearch_to_tsquery('simple', query)` 를 쓴다. 어떤 문자열도 오류 없이 받는다(실측).
  `to_tsquery` 는 문법 오류를 던지고 D21이 그것을 `INTERNAL` 로 접는다 — 클라이언트 입력 문제가 서버 결함으로 보고된다.
- **필터가 먼저다.** `project`·`kind`·`module`·기간을 건 뒤 남은 집합에 `tsv` 를 건다.
  필터 조립은 `event_stats` 의 관용구를 넓혀 쓴다.
- **질의의 세 갈래.** 규칙의 소유자는 **D33** 이고 여기서는 이벤트 쪽 결과만 적는다.
  - `query` 가 없거나 **공백뿐**이면 술어를 걸지 않는다. 필터 집합이 그대로 결과이고 `score` 는 `null` 이다.
  - `query` 에 값이 있는데 **렉심이 하나도 나오지 않으면**(구두점뿐) **술어를 건다.** 결과는 0건이다.
  - 그 밖에는 `tsv @@ tq` 를 건다.
  두 번째 갈래를 첫 번째로 접으면 **`"???"` 를 친 사람이 최근 이벤트를 검색 결과로 받는다.** 오류는 어디에도 없다.
  빈 결과는 오류가 아니다(D21). **정렬은 D33 이 두 갈래로 못 박았다.**

### 4. `pg_trgm` — 쓰지 않는다, 그리고 그것을 검사가 지킨다

- **선언은 남긴다.** 이유 셋: `CREATE EXTENSION IF NOT EXISTS` 는 이미 멱등하고 해가 없다,
  빼려면 매 기동 도는 파일에 `DROP` 을 넣어야 한다, 그리고 **그 확장을 요구하는 문장에는 D 번호가 없다** —
  고정값 블록과 D17의 파일 목록에 이름으로만 있다. **D34가 이 자리를 처음으로 소유한다.**
  [conventions.md](../docs/conventions.md) 문서 지도에 그 소유자를 더한다.
- **쓰지 않기로 한 선언은 검사가 없으면 다음 사람이 조용히 쓴다.** 그래서 검사를 **둘** 만든다.
  - **상시 게이트**(`scripts/check-layout.mjs`)가 `src/**` 와 **`migrations/**`** 에서
    trgm 연산자(`%`·`%>`·`<%`)와 연산자 클래스(`gin_trgm_ops`·`gist_trgm_ops`)를 찾는다.
    **trgm 인덱스가 실제로 들어올 자리가 `migrations/` 다** — 거기를 안 보면 검사가 헛돈다.
    새 게이트에는 `scripts/check-layout.test.mjs` 주입을 함께 넣는다.
  - **DB 검사**가 스키마에 trgm 연산자 클래스를 쓰는 인덱스가 0개임을 단언한다.
    기존 검사는 확장이 *설치됐는지*만 단언한다. 그 짝이다.
- **언제 다시 보는가.** 조사 손실은 이벤트만의 것이 아니다 — 위 실측이 `kb_chunks` 에서 같은 크기의 손실을 보였다.
  그러므로 그것을 고치는 결정은 **두 테이블에 동시에** 적용돼야 하고, Q8이 아니라 **D14를 다시 보는 결정**이다.
  후보는 셋이고 전부 v1 밖이다: 부분 문자열 경로를 더하는 것, 그 경로를 `gin_trgm_ops` 로 받치는 것, 한국어 사전을 들이는 것.
  **한 쪽 테이블에만 먼저 넣지 않는다** — 두 검색이 다른 규칙으로 도는 것이 손실보다 나쁘다.

### 5. 이벤트 벡터 — v1 은 채우지 않는다

- **쓰는 코드도 읽는 코드도 만들지 않는다.** `save_event` 의 INSERT 목록은 그대로다(D24도 그대로다).
  `search_events` 에 `<=>` 가 없다. 실측대로 전부 NULL 인 컬럼 위의 거리 정렬은 오류가 아니라 **물리 순서**다.
- **`kb_events_hnsw` 를 만들지 않는다.** 정본 DDL 의 인덱스 절이 그것을 선언하고 있으므로
  **그 선언 옆에 이유를 적는 것이 이 결정의 일부다** — `kb_chunks_hnsw` 는 *행이 적어서* 미룬 것이고
  이쪽은 **채울 값이 없어서**다. 이유가 다르면 다르게 적는다.
  빈 컬럼에 인덱스가 있으면 그것이 벡터 갈래가 있다는 증거로 읽힌다.
- **`kb_status` 에 이벤트 벡터 카운터를 더하지 않는다.** D31이 `chunks_without_embedding` 을
  그 이름으로 지은 이유가 이것이다. 세면 그 수가 언제나 `events` 와 같고,
  **정상 상태가 상시 경보로 보인다** — D32가 `partial` 과 `ok` 를 가른 것과 같은 논지다.
- 그래서 `kb_events.embedding` 은 `token_count`·`commit_sha` 와 같은 부류가 된다 —
  **정의만 있고 v1 내내 값이 없다.** 다른 점은 하나다: 이 컬럼은 **비어 있는 이유가 결정으로 적혀 있다.**
- **무엇이 이것을 뒤집는가.** 이벤트 벡터를 채우는 결정은 **쓰기 시점의 채움 경로와
  `embedding IS NULL` 백필 경로를 같은 결정에서** 정해야 한다. 저장 경로만 정하는 결정은
  그 이전 이벤트를 영구히 NULL 로 남기므로 Q7의 함정이 이벤트에서 재발한다.

### 어겨지면 무엇이 비명을 지르는가

| 규칙 | 어겨지면 | 무엇이 무는가 |
|---|---|---|
| `tsv` 입력 네 필드 | `root_cause`·`resolution` 으로 검색이 안 된다 | 6단계 DB 검사 — 네 필드에 각각 다른 낱말을 넣고 넷 다 찾는다 |
| 전부 `coalesce` | NULL 하나가 행 전체를 검색에서 지운다 | 6단계 DB 검사 — `root_cause` 가 NULL 인 이벤트를 `title` 의 낱말로 찾는다 |
| 식은 모듈 상수 하나 | 파일과 DB 가 갈라져도 러너가 성공을 보고한다 | 6단계 DB 검사 — `pg_get_expr` 로 읽은 실제 식과 상수를 대조 (D31 선례) |
| 사전 `simple` | 색인과 질의의 구성이 갈라지면 히트가 0이다 | 6단계 DB 검사 — 질의 경로가 같은 상수를 쓰는지, 그리고 실제로 걸리는지 |
| `websearch_to_tsquery` | 괄호 하나가 `INTERNAL` 이 된다 | 6단계 검사 — 깨진 질의 문자열에 200과 빈 배열을 단언 |
| 렉심 0개 질의는 술어를 건다 | 값이 있는 질의가 최근 이벤트 목록을 돌려준다 | 6단계 DB 검사 — `"???"` 로 0건을 단언 |
| `pg_trgm` 미사용 (코드) | 다음 사람이 조용히 쓰고 GUC 가 결과 집합을 정한다 | **상시 게이트** — `src/**`·`migrations/**` 에 trgm 연산자 0건 + 고장 주입 |
| `pg_trgm` 미사용 (스키마) | trgm 인덱스가 들어와도 아무도 모른다 | 6단계 DB 검사 — trgm 연산자 클래스 인덱스 0개 |
| 이벤트 벡터 갈래 없음 | 전부 NULL 위의 정렬이 물리 순서가 된다 | 6단계 검사 — `search_events` 의 SQL 에 벡터 연산자가 없다 |
| `kb_events_hnsw` 미생성 | 빈 컬럼의 인덱스를 근거로 벡터 갈래가 따라온다 | **없다** — 만들지 않는 것에는 걸 검사가 없다. 정본 DDL 의 문장이 전부이고 리뷰가 볼 자리다 |

D28이 정한 대로 **통과 출력만으로는 규칙이 살아 있는지 알 수 없다.** 위에서 "없다"로 남은 하나를 뺀 아홉은
6단계 구현이 검사를 만들 자리이고, 만들지 않으면 그 자체가 결함이다.

### 기존 결정을 뒤집지 않는다

- **D2 그대로.** 키가 없으면 키워드만이다. D34는 이벤트에서 **그 키워드를 실재하게** 만든다.
  다만 이벤트에 한해 키가 있어도 벡터가 없다 — D2는 키가 있으면 벡터가 *생긴다*고 말한 적이 없다.
- **D14 그대로.** 구성은 `simple` 이다. 실측한 조사 손실은 D14의 알려진 대가이고,
  D34는 그것을 이벤트로 확장할 뿐 새로 만들지 않는다.
- **D17 그대로.** 새 파일 `004`, 전부 `IF NOT EXISTS`, 파괴적 문장 없음.
- **D25 그대로.** CHECK 를 더하지 않는다. 생성 컬럼은 제약이 아니라 값이다.
- **D21 그대로.** 새 에러 코드도 새 발신자도 없다. 0건은 200이다.
- **D24 · D19 · D20 그대로.** `save_event` 의 인자도 CLI 의 인자도 늘지 않는다. 6단계는 CLI 표면이 없다.
- **D31을 넓히지 않는다.** 백필은 `kb_chunks` 만 본다. 이벤트를 자기 밖으로 민 D31의 문장은 그대로 유효하고,
  D34는 그 자리를 **채우지 않기로 채운다.**
- **D30 다음 번호를 쓴다.** `003` 은 `files_deleted` 가 가져갔다.
- `docker-compose.yml` 의 `test` 서비스는 이미 `./migrations` 를 마운트한다 — `003` 이 연 구멍은 닫혀 있다.

### 낡는 사본은 아홉이다

- [data-model.md](../docs/data-model.md) §이벤트 원장 DDL — `tsv` 컬럼을 더한다 (**정본을 먼저 고친다**)
- 같은 파일 §인덱스 — `kb_events_tsv` 를 더하고, **`kb_events_hnsw` 옆에 v1 미생성과 그 이유**를 적는다
- 같은 파일의 `embedding vector(1536), -- text-embedding-3-small, summary만` — `v1 은 채우지 않는다 (D34)` 를 붙인다
- [migrations/002_schema.sql](../migrations/002_schema.sql) 의 같은 주석 — **주석 한 줄만** 고친다 (D32 선례)
- [data-model.md](../docs/data-model.md) §검색의 `이벤트: … 남은 집합에 벡터/키워드` — v1 이벤트는 키워드만이다
- [CLAUDE.md](../CLAUDE.md) 검색 규칙의 미러 두 줄 — 같은 문장과 `이벤트 임베딩은 summary만`
- [plan.md](../docs/plan.md) §6 의 `이벤트 임베딩은 summary만`
- [README.md](../README.md) 와 [README.ko.md](../README.ko.md) 의 "키가 없으면 `embedding` 은 NULL 이고
  검색은 `tsv` 키워드만 쓴다" — **이벤트에서는 키가 있어도 무조건**이라 조건문이 거짓을 말한다.
  D27이 두 README 를 대칭으로 묶으므로 두 파일이다

**옛 문구는 게이트의 `RETIRED` 에 등록하고 주입을 함께 넣는다.**
그리고 [open-questions.md](../docs/open-questions.md) Q9에 `— **해결 → D34**` 를 붙인다. 질문 본문은 고치지 않는다.
`구현에 고정되는 값` 블록에 세 줄이 는다 — 이벤트 `tsv` 의 입력 네 필드, `pg_trgm` 은 v1 미사용, 이벤트 벡터는 v1 미충전.

### D33 에 거는 제약

D34는 순서도 `score` 도 정하지 않는다 — **D33 이 이벤트 정렬을 두 갈래로 못 박았다.**
대신 D33이 반드시 받아야 하는 사실 셋을 남기고, 그 셋이 그대로 반영됐다.

- **이벤트 결과에는 벡터 점수가 없다.** `score` 의 정의는 벡터 없이 계산될 수 있어야 한다.
  문서와 이벤트의 `score` 가 다른 의미를 갖는다면 그 사실이 계약에 적혀야 한다 —
  같은 이름의 필드가 두 뜻을 가지면 아무도 비명을 지르지 않는다.
- **마지막 타이브레이커는 유일해야 한다.** 이벤트에서는 `id` 다.
- **`tsv` 가 NULL 인 이벤트는 없다.** 생성식이 전 필드를 `coalesce` 로 감싸므로 값은 언제나 있다 —
  빈 `tsvector` 이지 NULL 이 아니다. 병합이 NULL 분기를 만들 필요가 없다.

### D34가 닫지 않는 것

- **조사 손실은 남는다.** 실측 표의 32~42%가 그대로 v1의 재현율이다. 해가 해소된 것이 아니라
  **받아들여진 것이다**(D24 선례). 고치는 결정은 D14를 다시 보는 결정이고 두 테이블에 동시에 적용돼야 한다
- **`pg_trgm` 은 여전히 아무 인덱스도 받치지 않는다.** 달라진 것은 그것이 이제 누락이 아니라 결정이고, 검사가 지킨다는 것뿐이다
- **이벤트 벡터를 채우는 경로.** 쓰기 시점의 채움 경로와 백필 경로를 **같은 결정에서** 정할 때 함께 본다.
  그때 §2의 입력 비대칭(벡터 `summary` 만 대 키워드 넷)을 먼저 본다
- **`kb_query_logs.hit_paths` 는 `text[]` 인데 이벤트 히트는 경로가 아니라 `id` 다.**
  9단계 결정이 함께 정한다 — 그때까지 이벤트 질의는 `hit_paths` 를 NULL 로 두고 `hit_count` 만 쓴다(D33과 같은 잠정 규칙).
  → **D49 가 정했다.** 잠정이 영구가 됐고, 이유는 한 `text[]` 에 두 종류의 식별자를 섞지 않기 위해서다
- **`result`·`severity` 로 좁히는 필터가 요청 계약에 없다.** `kb_events_filter` 인덱스에는 `result` 가 들어 있는데
  `search_events` 요청 필드에는 없다. 계약의 공백이지 Q9가 아니다
- **필터와 `tsv` 를 한 인덱스로 묶지 않는다.** `btree_gin` 은 새 확장이고,
  마침 이 결정이 확장 하나를 쓰지 않기로 정한 참이다
- **인덱스가 실제로 쓰이는 규모를 재지 않았다.** 오늘 이벤트는 0행이고 190행 청크에서는 플래너가 GIN 을 무시한다(실측)
- **Q12(프로젝트 경계)·Q13(페이지네이션)·Q22(`repo`)는 이 결정 밖이다**


## D35–D38 — 7단계(`get_event` · `get_file` · `save_doc`) (2026-09-02 확정)

[open-questions.md](../docs/open-questions.md) Q12·Q15·Q19·Q20을 마감한다. 7단계 라우트를 막던 것들이다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D35 | A | 단건 조회는 없으면 404, 집합 질의는 빈 결과. `get_event`는 `project`를 요구하고 불일치도 404 | Q12 |
| D36 | C | `get_file`은 **색인된 행만** 연다. 파일은 뿌리 fd에서 한 성분씩 `openat`으로 내려가고, 응답은 4000자 창이다 | Q19 |
| D37 | B | **매핑을 만들지 않는다.** `project`는 원장의 라벨이고 한 인스턴스는 한 workspace를 섬긴다 | Q20 |
| D38 | A | `save_doc`은 `{project, path, body, base_hash?}` → 제안 본문 + unified diff. 판정 불가능한 휴리스틱은 계약에서 뺀다 | Q15 |

### D35 404 대 빈 결과, 그리고 `get_event`의 프로젝트 경계

**규칙 하나로 전부 결정한다.** 하나를 지목하는 조회는 없으면 `NOT_FOUND`이고,
집합을 묻는 조회는 **빈 결과**다. 지목의 기준은 "요청이 답을 하나로 특정하는가"다.

| 표면 | 부류 | 없을 때 |
|---|---|---|
| `GET /v1/events/{id}` | 지목 | 404 |
| `GET /v1/files?project=&path=` | 지목 | 404 |
| `GET /v1/docs?project=&path=` | 지목 | 404 |
| `POST /v1/search/docs` · `POST /v1/search/events` | 집합 | `{ "results": [] }` |
| `GET /v1/stats/events` | 집합 | 0으로 채운 응답 (D23) |

`event_stats`가 모르는 `project`에 0을 돌려주는 것은 이 규칙의 결과이지 예외가 아니다 —
집합을 물었으니 빈 집합이 답이다.

**`get_event`는 `project`를 요구한다.** `GET /v1/events/{id}?project=`이고, 없으면 `VALIDATION`,
행의 `project`와 다르면 `NOT_FOUND`다. D5가 `project`를 필수로 둔 것이 이벤트 저장에만
걸릴 이유가 없다 — 원장이 여러 프로젝트를 담는 순간 id 하나로 남의 사건을 읽는 길이 생긴다.

**불일치를 403이 아니라 404로 돌려준다.** 둘의 차이는 "그 id가 존재한다"는 사실을 흘리는지다.
D7이 로컬 무인증이라 이것은 권한 문제가 아니지만, 그렇다고 존재를 알려 줄 이유도 없다.
D21의 코드 표에 `FORBIDDEN`을 새로 만들지 않는 이유이기도 하다 — **없는 id와 남의 id는 같은 응답이다.**

### D36 `get_file`은 색인된 것만 연다

`GET /v1/files?project=&path=&offset=`.

**허용 목록은 `kb_documents`다.** `(project, path)`로 행을 찾고, 없으면 404다.
D9 경로 규칙(`docs/**` · 루트 `README*` · `adr/**`)과 D30의 `.md`를 **요청 문자열 위에서 다시
구현하지 않는다** — 두 벌이 되면 갈라지고, 갈라진 쪽이 느슨한 쪽이 된다.
색인이 곧 계약이므로 색인되지 않은 것은 이 문에서 존재하지 않는다.

그래도 파일시스템 방어가 남는다. **행은 낡을 수 있다** — 색인 후에 파일이 심볼릭 링크로 바뀌어도
행은 그대로다 (D30의 삭제 패스는 사라진 파일만 지우고, 건너뛴 파일은 표에 남긴다).

읽는 절차를 못 박는다. **경로 문자열을 `stat`하거나 `realpath`하지 않는다** — 검사한 경로와
연 경로가 같다는 보장이 없다(TOCTOU). 신원은 **파일 서술자에서** 얻는다.

1. workspace 뿌리를 한 번 연다: `O_RDONLY | O_DIRECTORY | O_CLOEXEC`
2. `path`를 `/`로 쪼개 **성분마다** `openat(dirfd, 성분, O_RDONLY | O_DIRECTORY | O_NOFOLLOW)`
3. 마지막 성분만 `openat(dirfd, 이름, O_RDONLY | O_NOFOLLOW)`
4. `fstat(fd)`로 `S_ISREG` 확인 — 경로가 아니라 **서술자**를 본다
5. 그 서술자에서만 읽는다

`O_NOFOLLOW`는 **마지막 성분만** 막는다. 그래서 성분마다 내려간다 — `docs/` 자체가 심볼릭 링크면
마지막만 막는 방어는 통과하고, 뿌리 아래 아무 정규 파일이나 열린다.
`realpath`가 뿌리 아래인지 보는 검사도 이것을 막지 못한다. **뿌리 안의 다른 파일**을 요구한 적이
없는데 돌려주게 되기 때문이다. 한 성분씩 내려가면 그 부류가 통째로 사라진다.

`O_NOFOLLOW`나 `O_DIRECTORY`가 없는 플랫폼에서는 **읽지 않고 실패한다.** 없는 채로 도는 것은
방어가 꺼진 것이고, 꺼진 줄 모르는 것이 더 나쁘다. 운영 경로는 `api` 이미지의 Linux다.

**응답은 파일이 아니라 창(window)이다.** 최대 4000자 — D30의 청크 하드 상한과 같은 값이다.

```json
{ "project": "sillok", "path": "docs/plan.md", "text": "…",
  "offset": 0, "next_offset": 3980, "total_bytes": 24117, "truncated": true }
```

`offset`·`next_offset`·`total_bytes`는 **바이트**다. 바이트 offset으로 `seek`하고 `4000*4 + 3`바이트를
읽어 증분 디코더로 UTF-8을 풀고, 끝의 불완전한 시퀀스를 버린 뒤 4000자로 자른다.
`next_offset`은 `offset + len(text.encode())`다 — 잘라 낸 글자는 **다음 창**이지 건너뛴 것이 아니다.

디코드는 **strict**다. `offset`이 문자 경계가 아니면 `VALIDATION`이다.
관대한 디코더는 그 바이트들을 조용히 먹어 `next_offset`이 영영 그것들을 지나치게 만든다.

**크기 상한을 두지 않는다.** 1 MiB 같은 값은 RAM 손잡이지 토큰 손잡이가 아니다 —
1 MiB짜리 UTF-8을 통째로 돌려주면 "질의당 토큰은 거의 고정"이라는 불변식이 그 자리에서 깨진다.
동시에 D30은 색인에 크기 상한을 두지 않았으므로, 상한을 여기에 두면 **색인된 문서가 읽히지 않는**
모순이 생긴다. 창으로 자르면 둘 다 사라진다 — 큰 것을 메모리에 올리는 일 자체가 없다.

### D37 `project` → workspace 매핑은 만들지 않는다

**이것이 결정이다.** Q20은 매핑 형식을 물었고, 답은 "필요 없다"다.

`SILLOK_WORKSPACE`는 그대로 **한 뿌리**이고 (D16 변경 없음), `project`는 원장의 라벨이다 (D25).
경로 성분이 아니다. **한 인스턴스는 한 workspace를 섬긴다.**

`<SILLOK_WORKSPACE>/<project>/…` 로 한 단계를 넣는 안(A)을 버린 이유는 실측이다 —
이 저장소가 이미 그렇게 돌지 않는다. Compose는 `SILLOK_WORKSPACE: /workspace`에
`.:/workspace:ro`를 걸어 **저장소 자신이 뿌리**다. 파일은 `/workspace/docs/plan.md`이지
`/workspace/sillok/docs/plan.md`가 아니다. 한 단계를 요구하면 지금 도는 배치가 깨진다.

설정 파일로 `{"sillok": "/repos/sillok"}` 같은 지도를 두는 안(C)도 버린다.
D16이 환경변수 하나로 끝낸 것을 새 파일 형식으로 되돌리고, 그 지도가 곧 두 번째 진실이 된다.

**ingest와 `get_file`은 같은 뿌리를 봐야 한다.** `sillok ingest --workspace`가 다른 나무를
색인해 두면, `get_file`은 **이 나무**를 저쪽의 `path`로 열게 된다 — 같은 경로에 다른 내용이 있으면
조용히 남의 파일을 돌려준다. 그래서 `ingest`는 `SILLOK_WORKSPACE`와 다른 `--workspace`를 거절한다.
행을 고르는 조건에 `repo = ''`를 유지한다 (ingest가 넣는 값이다). `repo`를 두 번째 뿌리로 쓰면
Q20이 매핑 문제로 되살아난다 — **Q22는 열어 둔다.**

### D37이 받아들이는 비용

여러 저장소의 **파일**까지 한 인스턴스로 섬길 수 없다. 그러려면 인스턴스를 여럿 띄운다.
막히는 것은 `get_file` 하나다 — 이벤트 원장도 문서 검색도 여전히 멀티 프로젝트다 (D5).
v1이 노리는 배치는 "작업 중인 저장소 하나 + 그 저장소의 지식"이고, 그것은 이 형태로 충분하다.

### D38 `save_doc` 계약

`POST /v1/docs/proposals`

```json
{ "project": "sillok", "path": "docs/plan.md", "body": "…전체 새 본문…", "base_hash": "sha256:…" }
```

```json
{ "proposal": { "project": "sillok", "path": "docs/plan.md",
                "exists": true, "diff": "--- a/docs/plan.md\n+++ b/…", "body": "…" } }
```

- `path`는 D36과 **같은 판정**을 받는다 — `kb_documents`에 행이 있어야 한다.
  새 문서 제안은 v1 비범위다. 없는 경로면 404다
- `body`는 **문서 전체**다. 부분 패치를 받지 않는다 — 모델이 만든 조각을 서버가 붙이면
  붙이는 규칙이 두 번째 계약이 되고, 그 규칙은 아무 문서에도 없다
- `diff`는 현재 파일(D36의 절차로 읽은 것)과 `body`의 unified diff다
- `base_hash`가 있고 현재 내용 해시와 다르면 **`CONFLICT` 409**다.
  `message`는 고정 문구 `document changed since base_hash`다 — D32의 문구를 쓰지 않는다.
  현재 해시를 응답에 싣지 않는다. 다시 읽으면 알 수 있고, error 봉투는 값을 나르는 자리가 아니다.
  D21이 예약해 둔 코드이고 D32가 첫 발신자를 만들었으니 이것이 둘째다.
  없으면 검사하지 않는다 — 모르고 보낸 것과 알고 덮어쓰는 것은 다르다
- **Git에 쓰지 않는다.** 응답이 전부다 (D3)

**Skill의 "Git 후보인데 본문에 날짜별 시도가 3건 이상"은 거절 규칙에서 뺀다.**
기계적으로 판정할 수 없는 것을 계약에 두면 구현이 임의로 채우고, 그 임의가 계약이 된다.
[SKILL.md](../docs/skills/sillok-storage/SKILL.md)에 **안내**로 남긴다 — 사람과 모델이 판단하고
API는 그것으로 거절하지 않는다. `save_event`의 필수 필드 거절(D25)과는 부류가 다르다:
저쪽은 값이 있는지 없는지이고 이쪽은 글이 어떤 종류인지다.

### D36·D38의 가장자리 (침묵하면 구현이 발명한다)

이 저장소가 반복해서 당한 부류다 — 계약이 말하지 않은 자리를 구현이 조용히 채우고,
그 임의가 나중에 계약처럼 인용된다. 아래는 전부 못 박는다.

**`path`를 정규화하지 않는다.** `kb_documents`의 값과 **바이트로 같아야** 한다.
빈 문자열, 끝의 `/`, 겹친 `//`, `./`가 섞인 것은 정규화 대상이 아니라 그냥 **행이 없는 것**이고 404다.
정규화를 넣으면 "무엇이 같은 경로인가"라는 두 번째 규칙이 생기고, 그 규칙이 곧 허용 목록을
느슨하게 만드는 손잡이가 된다 — 색인이 허용 목록이라는 D36의 요지가 거기서 무너진다.

| 입력 | 답 |
|---|---|
| `offset` 생략 | `0` |
| `offset` < 0, 또는 정수가 아님 | `VALIDATION` |
| `offset` > `total_bytes` | `VALIDATION` — 파일 밖이다 |
| `offset` == `total_bytes` | `text: ""`, `next_offset` 그대로, `truncated: false`. 오류가 아니라 끝이다 |
| `offset`이 문자 경계가 아님 | `VALIDATION` |
| 0바이트 파일 | `text: ""`, `offset: 0`, `next_offset: 0`, `total_bytes: 0`, `truncated: false` |
| `truncated` | `next_offset < total_bytes` 와 같은 뜻이다. 별도로 판단하지 않는다 |

**`save_doc`의 `diff`는 파일 전체를 본다.** D36의 4000자 창은 `get_file`의 응답 규칙이지
읽기 상한이 아니다 — 창으로 diff를 뜨면 창 밖의 줄이 전부 삭제로 보인다.
`save_doc`은 같은 `openat` 절차로 열되 **끝까지 읽는다.**
`body`가 현재 내용과 같으면 `diff`는 **빈 문자열**이고 `exists: true`다. 오류가 아니다 —
"바꿀 것이 없다"는 답이고, 그것을 오류로 만들면 모델이 같은 제안을 반복하게 된다.

**같은 거절이 HTTP 얼굴에도 걸린다.** `POST /v1/ingest`는 D20이 말하는 "같은 Service 함수의 HTTP 얼굴"이라,
CLI에만 걸면 그 문으로 우회된다. HTTP 쪽 코드는 `VALIDATION`이다.

**CLI 쪽 거절은 CLI에서 끝난다.** `VALIDATION`은 HTTP 표면의 코드다 (D21).
CLI는 0이 아닌 종료 코드와 사람이 읽는 메시지로 거절한다.
같은지는 **정규화한 절대 경로**로 본다 — `.`과 `/workspace`가 같은 곳을 가리켜도 문자열은 다르다.
`SILLOK_WORKSPACE`가 기본값(`.`)이면 프로세스의 작업 디렉터리를 기준으로 푼다.


### D35–D38 선택지

| 결정 | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D35 불일치 응답 | **404** | 403 | 200 + 빈 값 | B는 없는 id와 남의 id를 구분해 존재를 흘리고 D21에 코드를 하나 더 만든다. C는 단건 조회를 집합처럼 만들어 규칙을 둘로 쪼갠다 |
| D36 허용 목록 | 경로 규칙 재구현 | 확장자 허용 목록 | **`kb_documents` 행** | A는 D9·D30을 두 벌로 만들고 갈라지면 느슨한 쪽이 이긴다. B는 목록이 낡고, `.env`·`.git/`를 목록 밖으로 미는 일을 영원히 사람이 한다 |
| D36 크기 | 1 MiB 상한 | 상한 없음 | **4000자 창** | A는 토큰 불변식을 지키지 못하면서 색인된 큰 문서를 읽지 못하게 만든다. B는 그냥 불변식이 없다 |
| D37 매핑 | `<workspace>/<project>` | **매핑 없음** | 지도 파일 | A는 지금 도는 Compose 배치를 깬다(실측). C는 D16이 닫은 문을 새 파일 형식으로 다시 연다 |
| D38 본문 | **전체 본문** | 부분 패치 | diff 입력 | B·C는 서버가 붙이거나 적용하는 규칙을 요구하는데 그 규칙이 아무 문서에도 없다 |

### D35–D38이 닫지 않는 것

- **`GET /v1/docs`도 지목 조회다** (D35 표). 그 표면은 §7이 어느 단계에도 넣지 않았다 —
  D35는 규칙만 주고 언제 붙일지는 정하지 않는다
- **`openat` 걸음은 Linux를 전제한다.** 호스트(Windows) pytest 에서는 이 경로를 돌릴 수 없다.
  D22의 `test` 프로필에서 검사한다 — 호스트에서 skip 되는 것이 정상이다 (D16과 같은 이유)
- **낡은 행 자체는 남는다.** D30의 삭제 패스는 성공한 실행에서 사라진 파일만 지우고,
  심볼릭 링크로 바뀐 파일은 건너뛴 것으로 표에 남는다. `openat` 걸음이 그것을 열지 못하게 할 뿐
  행을 지우지는 않는다 — `get_file`이 404를 내는 것과 행이 없는 것은 다르다
- **`kb_documents.repo`의 의미(Q22)는 그대로 열려 있다.** D37은 `repo = ''`를 유지할 뿐
  그 컬럼이 무엇인지 정하지 않는다
- **`save_doc`의 새 문서 제안은 없다.** 색인된 경로만 고칠 수 있다
- **`kb_query_logs` 기록(9단계)은 이 결정들 밖이다** → **D48–D52 가 그 자리를 닫았다**


## D39–D41 — 7단계를 구현하다 드러난 계약 구멍 (2026-09-02 확정)

D35–D38 을 코드로 옮기는 중에 **계약이 침묵하는 자리 셋**이 나왔다.
[open-questions.md](../docs/open-questions.md) F절 Q27–Q29 로 먼저 적고 여기서 닫는다.
침묵한 자리를 구현이 조용히 채우면 그 임의가 나중에 계약처럼 인용된다 —
D36·D38 이 가장자리 절을 따로 둔 이유와 같은 부류이고, 이번엔 그 절이 덮지 못한 곳이다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D39 | A | `get_event` 응답 `data` 는 그 행 자체다 — `save_event` 가 받는 필드 + `id` + `created_at`. `embedding`·`tsv` 는 싣지 않는다 | Q27 |
| D40 | A | `base_hash` 는 `sha256:` + 소문자 16진 64자다. 콜론 뒤는 D30 `content_hash` 와 같은 문자열이고, 다른 형식은 `VALIDATION` | Q28 |
| D41 | A | `save_doc` 이 보는 **현재 내용**은 D30 정규화를 거친 텍스트다. 해시와 diff 가 같은 텍스트를 본다. 파일이 없으면 빈 내용이 아니라 **부재**다 | Q29 |

### D39 `get_event` 의 응답 필드

**규칙은 하나다 — 행이 가진 사실을 전부 주되, 파생 컬럼과 v1 이 채우지 않는 컬럼은 뺀다.**

| 컬럼 | 응답 |
|---|---|
| `id`·`created_at` | 싣는다. 저장 요청에는 없지만 행이 가진 사실이다 |
| `save_event` 가 받는 15개 (`project`…`created_by`) | 전부 싣는다. `payload` 도 포함이다 |
| `tsv` | 뺀다. 생성 컬럼이라 저장한 사실이 아니라 파생물이다 |
| `embedding` | 뺀다. v1 은 이벤트를 임베딩하지 않는다 (D34) — 언제나 `null` 인 1536칸을 나를 이유가 없다 |

`data` 는 **평평하다.** `{"event": {…}}` 로 한 겹 싸지 않는다 — 같은 부류인 `get_file`(D36)의
응답 예시가 평평하고, 지목 조회 둘이 서로 다른 모양을 갖는 것이 이 표면의 유일한 차이가 된다.

시각은 ISO-8601 문자열이다. `kb_status` 의 `last_ingest_at` 과 `search_events` 의
`occurred_at` 이 이미 그 형식이고, 여기서만 다른 형식을 쓸 이유가 없다.

**이 결정이 없으면 `search_events` 의 설명이 성립하지 않는다.** service-and-mcp 는
`root_cause`·`resolution` 으로 걸린 히트를 "원문은 `get_event` 에서 본다" 로 넘긴다 —
그런데 무엇이 원문인지는 어느 문서에도 없었다.

### D40 `base_hash` 의 와이어 형식

**`sha256:` 접두사를 요구한다.** D38 과 [service-and-mcp.md](../docs/service-and-mcp.md) 의
요청 예시가 `"base_hash": "sha256:…"` 이고, 생략표는 콜론 **뒤**에만 있다.
`"body": "…전체 새 본문…"` 처럼 전체가 생략표인 자리와 다르다 — 접두사는 적힌 글자다.

콜론 뒤는 D30 이 정의한 그 문자열이다: 정규화한 텍스트를 UTF-8 로 인코드한 바이트의
SHA-256, **소문자 16진 64자**. 대문자, 접두사 없는 64자, 다른 알고리즘 이름은 전부 `VALIDATION` 이다.

**관대하게 벗기지 않는다.** 접두사가 있으면 벗기고 없으면 그냥 쓰는 구현은
"무엇이 같은 해시인가" 라는 두 번째 규칙을 만든다 — D36 이 `path` 를 정규화하지 않기로 한 것과 같은 이유다.
받아들이는 형식이 하나면 그 규칙이 아예 없다.

접두사가 값을 나른다는 점도 있다. D2 를 바꾸면 스키마 변경과 전체 재색인이 따라오는데,
그때 옛 클라이언트가 보낸 해시는 **형식만 보고** 거절된다. 접두사가 없으면 64자 16진끼리
조용히 비교되어 언제나 불일치, 즉 영원한 `CONFLICT` 로 나타난다.

### D41 `save_doc` 이 보는 "현재 내용"

**해시와 diff 는 같은 텍스트를 봐야 한다.** 아니면 응답이 자기모순이 된다 —
`base_hash` 는 맞다고 하면서 diff 는 전 줄이 바뀐 것으로 나오는 답이 가능해진다.
작업 트리가 CRLF 인 배치에서 실제로 그렇게 된다 (이 저장소가 그렇다).

그 텍스트는 D30 의 정규화를 거친 것이다 — 선행 BOM 제거, CRLF 와 홀로 있는 CR 을 LF 로.
이 저장소에 정의된 "내용" 은 그것 하나뿐이고 `content_hash` 가 그 함수다.
**`body` 도 같은 정규화를 거친다.** 한쪽만 정규화하면 같은 자기모순이 방향만 바꿔 돌아온다.

**`get_file` 은 반대다 — 원본 바이트를 그대로 본다.** 창의 `offset`·`next_offset`·`total_bytes`
가 바이트이므로, 정규화하면 그 숫자가 무엇의 offset 인지 사라진다.
**두 표면이 다른 텍스트를 본다는 사실을 여기 적어 둔다.** 침묵하면 다음 사람이 둘을
하나로 맞추려다 창을 깨거나 해시를 깬다.

**파일이 없으면 빈 내용이 아니라 부재다.** 행은 있는데 파일이 사라졌거나 심볼릭 링크로
바뀌어 D36 의 걸음이 열지 못하면:

- `exists` 는 `false` 다. 이 필드가 `true` 밖에 못 갖는다면 응답에 있을 이유가 없다
- `diff` 는 `/dev/null` 에서의 추가다 (`--- /dev/null`)
- `base_hash` 를 보냈으면 `CONFLICT` 다. 내용이 있다고 주장했는데 없다 —
  이것도 `document changed since base_hash` 다. 사라진 것은 바뀐 것의 부분집합이다
- **새 문서 제안이 아니다.** 행은 여전히 있어야 한다 (D38). 없는 경로는 그대로 404 다

`get_file` 이 같은 상황에서 404 인 것과 어긋나지 않는다. 저쪽은 **원문을 달라는** 요청이라
줄 것이 없으면 없는 것이고, 이쪽은 **제안을 만들라는** 요청이라 부재도 답의 일부다.

### D39–D41 의 가장자리

| 입력 | 답 |
|---|---|
| `get_event` 의 `{id}` 가 정수가 아님 | `VALIDATION` (D21 이 이미 접는 자리다) |
| `save_doc` 의 `body` 가 문자열이 아니거나 없음 | `VALIDATION` |
| `save_doc` 의 `base_hash` 가 `null` 또는 생략 | 검사하지 않는다 (D38) |
| 창 안에 UTF-8 로 풀 수 없는 바이트 (색인 뒤 파일이 바뀐 경우) | 여기서 처리하지 않는다. D21 의 포괄 예외가 `INTERNAL 500` 으로 접고 서버 로그에 남는다 |
| `offset` 이 문자 경계가 아님 | `VALIDATION` (D36). 창 **첫 바이트**에서 난 디코드 실패만 이것이다 |
| `NOT_FOUND` 의 문구 | service 가 소유한 세 상수(`event`·`file`·`document not found`)만 나간다. 그 밖의 문구는 버리고 `not found` 로 접는다 — 이 핸들러만 `str(exc)` 를 흘리므로 D21 이 `INTERNAL` 에 건 이유(**호출자를 믿지 않는다**)가 여기에도 걸린다 |
| `path` 에 NUL 이 들어옴 | `VALIDATION`. 정규화가 아니라 **물어볼 수 없는 질문**을 거절하는 것이다 — Postgres 의 `text` 는 NUL 을 담지 못해 그런 행이 존재할 수 없고, 그대로 넘기면 드라이버 예외가 `INTERNAL 500` 이 된다. D25 가 `project` 에서 이미 막은 것과 같은 부류다 |
| `O_NOFOLLOW`·`O_DIRECTORY` 가 없는 플랫폼 | 읽지 않고 실패한다 (D36). 코드는 `INTERNAL` 이다 — 서버 쪽 사정이지 클라이언트 입력 문제가 아니다 |

### D39–D41 선택지

| 결정 | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D39 응답 필드 | **행 − 파생 − 미충전** | 모든 컬럼 | `search_events` 의 8개 | B는 언제나 `null` 인 벡터 1536칸과 생성 컬럼을 나른다. C는 `root_cause`·`resolution` 을 빼는데, 그 둘을 보라고 만든 표면이다 |
| D40 접두사 | **`sha256:` 필수** | 접두사 없는 16진 | 둘 다 받는다 | B는 문서 예시 둘을 거짓으로 만든다. C는 "같은 해시" 규칙을 하나 더 만든다 |
| D41 현재 내용 | **정규화한 텍스트** | 원본 바이트 | 해시만 정규화 | B는 CRLF 작업 트리에서 전 줄이 바뀐 diff 를 낸다. C는 `base_hash` 가 맞는데 diff 가 전 줄 변경인 자기모순을 허용한다 |

### D39–D41 이 닫지 않는 것

- **`GET /v1/docs` 의 응답 필드는 그대로 없다.** §7 이 그 표면을 어느 단계에도 넣지 않았다 (D35 와 같다)
- **`kb_documents.repo` 의 의미(Q22)** 는 여전히 열려 있다. `get_file`·`save_doc` 은 `repo = ''` 만 본다 (D37)
- **낡은 행을 지우는 경로는 없다.** `save_doc` 이 `exists: false` 를 돌려줘도 행은 그대로다 (D30 의 삭제 패스만 지운다)
- **`kb_query_logs` 기록(9단계)** 은 이 결정들 밖이다 → **D48–D52 가 그 자리를 닫았다**

## D42–D46 — 8단계 MCP 표면 (2026-09-02 확정)

[open-questions.md](../docs/open-questions.md) Q17을 닫는다. ~~**마지막 단계 게이트였다.**~~
— **그때까지는 그랬다.** D52 가 9단계 게이트(Q32)를 새로 세웠다가 같은 날 닫았다.
Q17은 셋을 물었다 — 도구의 입력 스키마, HTTP 마운트 경로, `Service와 동일 동작`의 판정 기준.
그 셋만으로는 구현이 발명할 자리가 남아서 다섯으로 나눠 못 박는다.

아래 `실측` 은 2026-09-02에 `mcp 2.1.1` 로 직접 재 본 것이다. SDK 문서만 보고 쓰지 않았다.

| ID | 선택 | 결정 내용 | 닫은 질문 |
|---|---|---|---|
| D42 | A | 도구 인자는 함수 서명이 낳는 스키마다. **전부 선택**이고 필수 판정은 Service가 한다 | Q17 |
| D43 | B | 표면은 정확히 `POST /mcp` 와 `POST /mcp/` 둘이다. **마운트하지 않는다** | Q17 |
| D44 | A | 결과는 성공·실패 모두 **정상 결과**이고, 본문은 HTTP와 같은 봉투 하나다 | Q17 |
| D45 | B | stdio는 새 CLI 명령 `sillok mcp` 다. `serve`에 플래그를 붙이지 않는다 | Q17 |
| D46 | A | `동일 동작` 의 판정: 같은 인자로 두 얼굴을 태워 **봉투가 같은지** 대조한다 | Q17 |

### D42 입력 스키마 — 전부 선택이고, 필수는 Service가 판정한다

도구 함수의 서명이 곧 `inputSchema`다. 이름과 타입은 그 도구의 HTTP 얼굴이 받는 것과 같다 —
`get_event(event_id, project)`, `get_file(project, path, offset)`,
`save_doc(project, path, body, base_hash)`, `save_event(project, kind, title, …)`.
**기본값을 스키마에 복제하지 않는다.** `top_k`를 비우면 Service가 D33의 기본값을 쓴다.

**모든 인자가 선택이다.** 필수로 선언하면 SDK가 도구를 부르기도 전에 거절하고,
모델은 [service-and-mcp.md](../docs/service-and-mcp.md)가 약속한 문구(`필드 없으면 에러 메시지를 그대로 돌려줌`)
대신 pydantic 메시지를 받는다. D10·D25의 거절은 **Service의 것**이고 그대로 모델에게 가야 한다.

그래서 검증 계층은 하나로 남는다 — 단, **타입이 걸린 자리는 예외다.** 둘이다.

1. 값의 타입이 스키마와 다르면 SDK가 도구 실행 전에 오류 결과로 답하고, 그 본문은 봉투가 아니다(실측)
2. SDK는 스키마에 맞춰 값을 **넓게 받아들인다** — `"8"`을 `8`로, `'{"a":1}'`을 객체로 바꿔 Service에 넘긴다.
   HTTP 얼굴의 POST 본문에서는 같은 값이 `VALIDATION`이다.
   **같은 글자를 보내도 두 얼굴의 Service가 다른 값을 볼 수 있다** — D46의 대조는
   *같은 인자 dict*가 기준이므로 이 자리를 덮지 않는다. 침묵하면 구현이 발명하므로 여기 적는다
이것은 D43이 말하는 **전송 계층**의 일이고, HTTP 얼굴에서 FastAPI가 `offset=x`를 먼저 거절하는 것과 같은 자리다.
다른 점은 그쪽은 D21이 봉투로 덮을 수 있고 이쪽은 아니라는 것뿐이다. **침묵하지 않고 여기 적는다.**

필드 목록이 두 벌이 되는 값은 치른다. 대신 **검사가 그 둘을 묶는다** — 도구가 받는 이름의 집합이
Service의 필수 필드를 전부 담는지 대조한다. 갈라지면 붉은불이 켜진다.

### D43 표면은 정확히 두 경로다 — 마운트하지 않는다

`POST /mcp` 와 `POST /mcp/` 가 같은 ASGI 핸들러다. 그 둘 말고는 없다.

**뿌리에 마운트하지 않는다.** 그러면 라우트에 걸리지 않은 모든 경로가 MCP 앱으로 흘러
`GET /v1/nope` 가 봉투 대신 SDK의 맨 `Not Found` 를 돌려준다(실측). D21이 무너지는 자리다.
**`/mcp` 에 마운트하지도 않는다.** D21이 `redirect_slashes` 를 껐으므로 마운트는 맨 `/mcp` 를
잡지 못하고(실측), 잡게 만들면 `/mcp/아무거나` 가 통째로 SDK의 404를 받는다.
두 경로만 ASGI로 이으면 `/mcp/nope` 는 **우리 404 봉투**로 돌아온다(실측).

**`/mcp` 아래의 본문은 JSON-RPC 이고 봉투 계약 밖이다.** 봉투는 `/v1` 의 본문 계약이다.
JSON-RPC를 봉투에 넣으면 두 프로토콜이 겹쳐 클라이언트가 무엇을 읽어야 할지 모른다.

**세션을 두지 않는다** — `stateless_http`, 응답은 SSE가 아니라 JSON이다.
도구 여덟은 전부 요청-응답이고 서버가 먼저 보낼 것이 없다.

**DNS 리바인딩 보호는 켠 채로 둔다.** SDK 기본값이 이미 `127.0.0.1:8080` 과 `localhost:8080` 을
받아들인다(실측) — D16의 주소가 그것이다. 검사에서 `Host` 가 막히면 **보호를 끄지 말고 헤더를 고친다.**

### D44 결과는 언제나 정상 결과이고 본문은 봉투 하나다

성공이든 실패든 `isError` 가 아니라 **정상 결과**이고, 내용은 텍스트 한 덩이,
그 텍스트는 HTTP 얼굴이 돌려주는 `{ok, data|error}` JSON 과 **같은 문자열**이다.
`structuredContent` 를 함께 내보내지 않는다 — 두 모양은 곧 두 계약이 된다.

실패를 프로토콜 오류로 접지 않는 이유는 [service-and-mcp.md](../docs/service-and-mcp.md)가 이미 적어 두었다:
`save_event` 는 `필드 없으면 에러 메시지를 그대로 돌려줌`. `VALIDATION`·`NOT_FOUND`·`CONFLICT` 를
"도구가 실패했다" 하나로 접으면 셋을 나눠 둔 이유가 사라지고, 모델은 같은 인자로 재시도한다.
`INTERNAL` 은 여기서도 고정 문구다 — 예외 문구를 싣지 않는다 (D21).

`UNAUTHORIZED` 는 HTTP 얼굴에만 있다. D7 게이트는 앱 미들웨어라 `/mcp` 도 덮고(실측),
stdio 는 부모 프로세스의 파이프라 토큰이 없다.

### D45 stdio 는 `sillok mcp` 다

D19가 CLI 인자를 고정했지만 이것은 편의 플래그가 아니라 **D6이 요구한 두 전송 중 하나**다.

- `sillok serve` 는 그대로 HTTP를 든다. `POST /mcp` 도 그쪽에 붙는다
- `sillok mcp` 는 **stdio 전용**이다. bind 플래그를 갖지 않는다 (주소는 D16의 환경변수다)
- **stdout 은 프로토콜 채널이다.** 로그·마이그레이션 보고는 전부 stderr 로 간다.
  `serve` 에 `--stdio` 를 붙이는 안을 버린 이유가 이것이다 — 같은 명령이 stdout 의 의미를 바꾼다
- 시작 전에 마이그레이션을 적용한다. 스키마 없이 도구를 여는 것은 D17이 막은 것과 같은 상태다
- 같은 Service 함수를 인프로세스로 부른다. HTTP 루프백을 만들지 않는다 (D19)

### D46 `Service와 동일 동작` 의 판정 기준

문장이 아니라 **검사가 판정한다.** 도구 여덟 각각에 대해:

- 같은 인자로 Service 함수를 직접 부른 결과와, `tools/call` 이 돌려준 텍스트를
  **글자까지 같은 봉투**로 대조한다
- 성공 하나와 **그 도구가 낼 수 있는 모든 오류 코드**를 덮는다
- HTTP 상태코드와 JSON-RPC 껍데기는 대조에서 뺀다 — 전송이 다르니 당연히 다르다
- `UNAUTHORIZED` 는 HTTP 전용이라 대조 대상이 아니다

도구가 Service를 인프로세스로 부르는지도 같은 자리에서 본다. 루프백을 넣으면 인자가 두 번 직렬화되고
그 순간 "같은 함수를 탄다"는 D6·D19의 문장이 거짓이 된다.

### D42–D46 이 노출하지 않는 것

도구는 **여덟뿐이다** (이름은 [plan.md](../docs/plan.md) §5가 소유한다).
resources·prompts·notifications 를 v1에서 만들지 않는다.
`POST /v1/ingest` 와 `GET /v1/docs` 는 그대로 MCP 밖이다 (D20 · Q30).
임의 SQL·전체 덤프·일괄 삭제는 애초에 금지다.

### D42–D46 선택지

| 결정 | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D42 필수 여부 | **전부 선택, Service가 판정** | 스키마에 필수 선언 | 인자 하나(dict) | B는 D10의 거절 문구를 모델에게서 빼앗고 검증 계층을 둘로 만든다. C는 모델에게 필드 이름을 알려 주지 않아 도구를 못 고른다 |
| D43 붙이는 법 | 뿌리에 마운트 | **두 경로만 ASGI** | `/mcp` 에 마운트 | A는 없는 경로의 봉투를 깬다(실측). C는 맨 `/mcp` 를 못 잡고(실측), 잡게 고치면 `/mcp/*` 가 통째로 SDK 404를 받는다 |
| D44 실패 표현 | **정상 결과 + 봉투** | 프로토콜 오류 | 봉투 + structuredContent | B는 세 코드를 하나로 접어 모델이 같은 인자로 재시도하게 만든다. C는 같은 사실을 두 모양으로 내보낸다 |
| D45 stdio 진입점 | `serve --stdio` | **`sillok mcp`** | 별도 실행 파일 | A는 한 명령이 stdout 의 의미를 바꾸고 `--host`·`--port` 가 무의미해진다. C는 D19의 CLI 하나 원칙을 깬다 |
| D46 판정 기준 | **봉투 대조 검사** | 문장으로 선언 | 도구별 단위 검사만 | B는 강제되지 않는 산문이다. C는 두 얼굴이 갈라진 것을 잡지 못한다 |

### D42–D46 이 닫지 않는 것

- **`GET /mcp` 의 상태코드**. 스트림도 세션도 없으므로 `POST` 만 받는데, 다른 메서드는 D21이
  405를 `VALIDATION`/422로 접는다. **MCP 명세가 `스트림 없음`의 신호로 쓰는 것은 405다** —
  GET으로 SSE를 떠보고 405만 그 뜻으로 읽는 클라이언트는 422를 치명적 오류로 볼 수 있다.
  **D21에 구멍을 내지 않는다.** 실제로 물리면 그때 결정한다 — 지금은 재 보지 않았다
- **`GET /v1/docs`(Q30)** 는 여전히 열려 있다. MCP 에 노출하지 않으므로 8단계와 독립이다
- **`kb_query_logs`(9단계)** 는 이 결정들 밖이다. MCP 로 들어온 질의도 로그에 남을지는 그때 정한다.
  → **D48·D49 가 정했다. 남는다** — `client` 가 `mcp` 이고 `tool` 은 HTTP 얼굴과 같은 도구 이름이다
- **도구 설명문의 길이 규칙**은 [service-and-mcp.md](../docs/service-and-mcp.md)가 소유한다 (`짧게`)
- **여러 클라이언트가 동시에 붙는 경우**는 세션이 없으므로 서로를 보지 못한다. 그것이 전부이고
  동시성 규칙을 더 만들지 않는다 — DB 쪽 규칙은 D32가 이미 갖고 있다

## D47 — 두 walk 이 건너뛰는 목록 (2026-09-03 확정)

[open-questions.md](../docs/open-questions.md) Q31을 닫는다. **열어 둔 이튿날 사실 하나가 결정을 강제했다.**

8단계가 `mcp` 의존성을 더하자 `.venv` 에 서드파티 문서가 들어왔고, 그중 하나(`pywin32` 의 `NOTICE.md`)의
상대 링크가 끊겨 **문서 게이트가 붉어졌다**(실측). 우리 문서가 아닌 파일을 검사한 것이다.
Q31은 비용 문제로 열렸는데, 같은 walk 이 **정확성 문제**도 만들고 있었다.

**두 walk 은 같은 목록을 건너뛴다** — 그 목록에 셋을 더한다.

```text
.git · node_modules · .venv · venv · __pycache__ · .pytest_cache
```

- **`.venv`·`venv`** 는 이 저장소가 쓰지 않은 파일이다. D9 경로 규칙상 색인 대상이 될 수도 없고
  (`docs/` 로 시작하지 않는다), 게이트가 지킬 계약도 아니다
- **`__pycache__`·`.pytest_cache`** 는 생성물이다. `.md` 를 담지 않으므로 검사에는 영향이 없고, 걸음만 줄인다
- 점으로 시작하는 디렉터리를 통째로 거르지 않는다 — `.github` 처럼 우리 파일이 사는 자리가 있다

**D30 의 목록이 이 목록으로 바뀐다.** 그 문장이 말한 `게이트의 walk 와 같다` 는 유지된다 —
바뀐 것은 목록이지 "둘이 같다"는 규칙이 아니다.

### 버린 안

| 안 | 버린 이유 |
|---|---|
| D9 경로부터 내려가 스캔 자체를 좁힌다 | **전체 스캔이 곧 삭제 판정**이라는 D30 의 뼈대를 건드린다. 루트 `README*` 처리도 특수해진다 |
| 비용을 받아들이고 적어만 둔다 | 게이트가 이미 붉다. 비용이 아니라 정확성이 걸린 자리가 됐다 |
| 게이트만 고친다 | D30 의 `게이트의 walk 와 같다` 가 거짓이 된다. 두 벌이 되면 갈라지고, 갈라진 쪽이 느슨해진다 |

### D47 이 닫지 않는 것

- **`GET /v1/docs`(Q30)** 은 그대로 열려 있다
- 목록을 코드 한 곳에서 공유하지 못한다 — 게이트는 JS, ingest 는 파이썬이다.
  D30 과 마찬가지로 **정본은 이 문서**이고 두 구현이 그것을 따른다.
  `scripts/check-layout.test.mjs` 가 건너뛰기를 고장 주입으로 지킨다

## D48–D52 — 9단계 `kb_query_logs` 기록 계약 (2026-09-03 확정)

[open-questions.md](../docs/open-questions.md) H절 Q32를 닫는다. **다섯 결정이 이 자리를 여기로 미뤄 두었다** —
D33·D34·D35–D38·D39–D41·D42–D46이 각각 `9단계가 확정한다` 또는 `이 결정들 밖이다`라고 적었다.
명세 공백이 아니라 **예약된 자리**이고, 그래서 Q32는 9단계를 막는다.

Q32는 하나로 보이지만 컬럼 여덟과 쓰기 시점과 실패 처리가 각각 발명할 자리를 남긴다.
**D42–D46이 Q17을 다섯으로 나눈 것과 같은 이유로 여기서도 다섯이다.**

아래 `실측` 은 2026-09-03에 이 저장소의 코드를 직접 읽어 확인한 것이다.

| ID | 결정 내용 | 닫은 질문 |
|---|---|---|
| D48 | 로그를 남기는 표면은 `search_docs`·`search_events` 둘뿐이다. `tool` 은 그 도구 이름이고 얼굴이 HTTP 여도 같은 이름이다 | Q32 |
| D49 | 여덟 컬럼의 값을 못 박는다. `client` 는 Service 의 키워드 인자로 받고 `body` 에도 `inputSchema` 에도 넣지 않는다 | Q32 |
| D50 | 쓰기는 Service 함수 안 — 검색 `with` 가 닫히고 응답 dict 가 만들어진 뒤다. 별도 autocommit 연결을 쓰고 실패는 삼킨다 | Q32 |
| D51 | `005` 가 `(project, created_at DESC)` 인덱스를 만든다. v1 은 지우지 않고, 백업 대상이 아니다 | Q32 |
| D52 | §7 에 `9단계 전에 Q32` 를 넣는다. Q32 가 같은 PR 에서 닫히므로 단계 주장은 `1–10단계` 그대로다 | Q32 |

### D48 무엇이 남기는가

`search_docs` 와 `search_events` 둘만 행을 쓴다. `tool` 은 그 **MCP 도구 이름**이고,
HTTP 얼굴로 들어와도 같은 값이다 — 두 얼굴이 같은 Service 함수를 타므로(D19·D46) 이름이 갈라질 이유가 없다.

**`kb_status` 는 쓰지 않는다. 이유는 D46이 아니다.** `kb_status` 는 `hit_count = 0` 인 행을 *세고*,
그 수가 §9의 완료 조건이다 — 현황을 묻는 질의가 자기가 보고할 수를 늘리면 그 지표가 자기 자신을 센다.
(D46의 봉투 대조는 두 호출을 이어서 하므로 `kb_status` 가 `hit_count=0` 을 쓸 때만 깨진다.
그것은 오염의 *결과*이지 금지의 근거가 아니다 — Grok 적대 리뷰가 이 근거를 깼고 여기 고쳐 적는다.)

`event_stats`·`get_event`·`get_file`·`save_event`·`save_doc`·`ingest` 도 쓰지 않는다.
`hit_count` 가 뜻을 갖지 않는 표면이다. **원장의 단위는 `질의`이지 `호출`이 아니다.**

### D49 여덟 컬럼

| 컬럼 | 값 |
|---|---|
| `project` | 정규화한 `project` (D25). 언제나 있다 — 검증을 통과한 뒤에만 행을 쓴다 |
| `client` | 얼굴. `http` 또는 `mcp` |
| `tool` | `search_docs` 또는 `search_events` (D48) |
| `query` | 정규화한 질의 문자열. `search_events` 가 질의 없이 불린 경우 NULL |
| `filters` | **실제로 SQL 에 걸린 필터만.** 문서는 `module`·`doc_type`·`status`, 이벤트는 `kind`·`module`·`since`·`until`. 시각은 ISO-8601 문자열. 없으면 `{}` |
| `hit_paths` | 문서는 돌려준 행의 `path` 를 **결과 순서대로, 중복을 접지 않고**. 이벤트는 NULL |
| `hit_count` | **호출자에게 돌려준 행 수.** 고유 문서 수가 아니다 |
| `latency_ms` | Service 함수 진입부터 로그 쓰기 직전까지. 정수. 로그 쓰기 자체는 재지 않는다 |

**`filters` 에 `project`·`query`·`top_k` 를 넣지 않는다.** 앞의 둘은 자기 컬럼이 있고 `top_k` 는 필터가 아니다.
같은 사실을 두 자리에 적으면 어느 쪽이 정본인지 다시 정해야 한다.

**`client` 는 Service 함수의 키워드 인자다.** `mcp_server` 가 `client="mcp"` 를 넘기고 기본값은 `http` 다.
- **`body` 에 넣지 않는다.** 넣으면 HTTP 호출자가 `mcp` 를 위장할 수 있고, D46의 대조 기준인 `같은 인자 dict` 가 깨진다.
- **`inputSchema` 에도 넣지 않는다.** 도구 함수의 서명이 곧 스키마이고(D42) 그 이름들은 HTTP 얼굴이 받는 것과 같아야 한다.
- **환경변수로 받지 않는다.** D16이 이름 여섯을 못 박아서가 아니라, `serve` 가 FastAPI 와 MCP HTTP 를 **한 프로세스**에 담기 때문이다 —
  프로세스 전역 값은 질의 하나가 어느 얼굴로 들어왔는지 기록할 수 없다.

**`filters` 의 모양을 예로 못 박는다.** 값이 없는 필터는 **키 자체를 넣지 않는다** —
요청이 `"module": null` 을 명시해도 SQL 에 걸리지 않았으므로 로그에도 없다.
MCP 얼굴은 부르지 않은 인자를 `None` 으로 채워 넘기는데(D42) 그 `None` 도 같은 규칙으로 사라진다.
**그래서 같은 질의는 어느 얼굴로 들어와도 같은 `filters` 를 남긴다** — 두 얼굴이 갈라지면 원장이 얼굴을 센다.

```json
// search_docs
{ "status": "current" }
// search_events
{ "kind": "failure", "since": "2026-01-01T00:00:00+00:00" }
```

**두 도구는 키 집합이 다르다** — 한 행에 `status` 와 `since` 가 함께 있을 수 없다.

시각은 **`parse_timestamp` 를 통과한 UTC 값의 `isoformat()`** 이다. 요청에 온 글자를 그대로 싣지 않는다 —
`Z` 와 `+00:00` 은 같은 순간인데 문자열이 다르고, 그러면 원장이 같은 질의를 둘로 센다.

**서명은 키워드 전용이다** — `search_docs(dsn, body, api_key="", *, client="http")`.
`api_key` 가 이미 위치 인자라 `client` 를 그 뒤에 위치로 두면 HTTP 얼굴이 실수로 넘길 수 있다.
값은 `http`·`mcp` 둘뿐이고 **검증하지 않는다** — 클라이언트 입력이 아니라 호출자가 자기를 밝히는 값이다.
Service 를 직접 부르는 검사는 기본값 `http` 로 남는다. 그것이 거짓으로 보이면 검사가 값을 넘기면 된다.

`latency_ms` 는 `time.perf_counter` 로 잰다(벽시계가 아니다). 반올림한 정수이고 1밀리초 미만은 `0` 이다.

**`hit_paths` 의 중복을 접지 않는 이유.** D33의 문서당 상한이 2라 같은 문서의 청크 둘이 한 결과에 들어올 수 있다.
접으면 `[A#0, A#1]` 과 `[A#0]` 이 같은 배열이 되고 `[A, B]` 와 `[B, A]` 가 구분되지 않는다 —
`같은 질의가 실행마다 다른 행 집합을 돌려주면 그 원장은 무엇의 기록도 아니다`(D33)를 지키지 못한다.
**읽을 때 접는 것은 싸고, 접힌 목록에서 배수를 되살리는 것은 불가능하다.**
그래서 `len(hit_paths) = hit_count` 가 문서 질의의 불변식이다.

### D50 어디서 쓰고, 실패하면 어떻게 하는가

**Service 함수 안이다.** 얼굴(`api.py`·`mcp_server.py`)에 두면 같은 원장이 두 벌로 갈라진다 (D19).

**쓰는 자리는 하나로 못 박는다 — 검색 `with` 블록이 닫히고, 돌려줄 dict 가 만들어진 뒤, `return` 직전이다.**
두 함수의 모양이 다르기 때문에 둘 중 하나만 말하면 어긋난다 (실측):
`search_docs` 는 `with` **안에서** 결과를 만들고, `search_events` 는 `with` 가 닫힌 **뒤에** 행을 변환한다.
`with` 뒤`만 말하면 후자에서 이르고, `dict 가 생긴 뒤`만 말하면 전자에서 열린 트랜잭션 안이 된다.

**별도의 `with connect(dsn, autocommit=True)` 연결을 쓴다** (D32가 ingest 에서 이미 쓰는 형태다).
이유는 **내구성이 아니라 격리다** — 같은 연결에 쓰면 INSERT 실패가 검색 트랜잭션을 중단시키고,
psycopg 는 롤백 전까지 그 연결의 모든 문장을 거절한다. **그러면 실패를 삼킬 수가 없다.**
(`같은 연결의 행은 검색과 함께 롤백된다`는 근거는 틀렸다 — 이 계약이 남기는 행은 전부 `with` 가 정상 종료하는 경로라
같은 연결이어도 커밋된다. Grok 적대 리뷰가 깼고 여기 고쳐 적는다.)

**실패는 삼키고 `logging.warning` 으로 남긴다.** 질의는 그대로 답한다 —
원장이 자기가 기록하는 것을 죽일 수 있으면 안 된다. 세 가지를 함께 못 박는다:

- `try` 는 **쓰기뿐 아니라 값 만들기까지** 감싼다. `filters`·`hit_paths` 를 만들다 난 버그가 500이 되면 안 된다
- 경고에 DSN 을 싣지 않는다 — `redact_dsn` 을 쓴다. 이 저장소는 예외 경로로 DSN 을 흘린 적이 이미 있다 (D21)
- 로그 연결도 `with` 로 연다. 안 그러면 연결이 샌다

**남기지 않는 경우 둘.**
- `VALIDATION` 으로 거절된 요청 — `project` 가 정해지기 전이라 적을 자리가 없다
- `INTERNAL` 로 죽은 요청(임베딩 실패·DB 실패) — 남기면 `hit_count = 0` 이 `결과 없음`과 `고장`을 섞어 센다.
  §9의 완료 조건이 바로 그 값 위에 서 있다

**정상 종료했는데 결과가 빈 질의는 반드시 `hit_count = 0` 으로 남긴다.** 그것이 §9에 남은 마지막 조건이다.

### D51 인덱스와 보존

`005_query_log_index.sql` 이 하나를 만든다.

```sql
CREATE INDEX IF NOT EXISTS kb_query_logs_project_time
  ON kb_query_logs (project, created_at DESC);
```

`kb_status` 가 부를 때마다 `WHERE project = … AND hit_count = 0` 을 세는데 이 표에는 PK 말고 인덱스가 없었다.

- **v1 은 지우지 않는다.** append-only 이고 질의량을 따라 자란다. 정리 명령을 만들지 않는다
- **백업 대상이 아니다.** `kb_events` 와 다르다 — 이것은 Git 이 재현하지 못하는 지식이 아니라 v1 성공 조건의 *측정*이다.
  잃으면 측정을 잃지 지식을 잃지 않는다

### D52 §7의 게이트 문장

§7의 단계별 게이트 목록에 `9단계 전에 Q32` 를 넣는다. Q32는 **같은 PR 에서** D48–D52로 닫힌다.

게이트는 N 을 *막힌 가장 이른 단계 바로 앞*으로 유도한다. Q32가 닫힌 뒤에는 막힌 단계가 없으므로
N 은 §7 번호 목록의 마지막인 10 그대로이고, 세 문서의 `1–10단계` 주장은 움직이지 않는다.
문장은 Q32가 닫힌 뒤에도 지우지 않는다 — 다른 게이트 문장과 같은 규칙이다.

### D48–D52 선택지

| 결정 | A | B | C | 버린 이유 |
|---|---|---|---|---|
| D48 대상 | 검색 둘 | 도구 여덟 전부 | 검색 둘 + `kb_status` | B는 `hit_count` 가 뜻 없는 표면에 그 컬럼을 강제하고 원장의 단위를 `호출`로 바꾼다. C는 현황 질의가 자기가 보고하는 수를 늘린다 |
| D49 `client` | 키워드 인자 | 요청 `body` 필드 | 헤더 | B는 HTTP 호출자가 얼굴을 위장할 수 있고 D46의 `같은 인자 dict` 를 깬다. C는 D7 게이트 말고는 헤더를 보지 않는 지금 구조에 표면을 하나 더 만든다 |
| D49 `hit_paths` | 중복 유지 | 중복 제거 | 이벤트도 `event:<id>` 로 섞기 | B는 `[A#0, A#1]` 과 `[A#0]` 을 같게 만들어 D33이 이 원장에 준 목적을 지운다. C는 한 `text[]` 에 두 종류의 식별자를 섞어 소비자가 파싱하게 한다 |
| D50 연결 | 검색과 같은 연결 | **별도 autocommit** | 로그 전용 풀 | A는 INSERT 실패가 검색 트랜잭션을 중단시켜 **실패를 삼킬 수 없게** 만든다. C는 v1 이 갖지 않은 수명 관리를 들여온다 |
| D50 실패 질의 | 남긴다 | **남기지 않는다** | 별도 컬럼으로 구분 | A는 `hit_count=0` 에 고장을 섞어 §9의 조건을 무의미하게 만든다. C는 컬럼 신설이라 `002` 를 다시 여는데, 얻는 것이 v1 에는 없다 |

### D48–D52 가 닫지 않는 것

- **`client` 는 stdio 와 HTTP MCP 를 구분하지 않는다.** 실측 — `mcp_server.build(cfg)` 는 전송 인자를 받지 않고
  분기도 없다. 두 전송이 같은 도구 객체를 공유하므로 이 코드 모양에서는 구분할 방법이 없다.
  구분이 필요해지면 전송을 아는 자리에서 값을 주는 결정이 먼저다
- **`hit_paths` 는 `path` 뿐이라 D33의 안정 키 `(path, chunk_idx)` 보다 약하다.** 같은 문서의 청크 0+1 과 1+2 를 구분하지 못한다.
  `len(hit_paths) = hit_count` 는 지키지만 행 집합을 복원하지는 못한다 — 복원이 필요해지면 컬럼을 늘리는 결정이다
- **고장 난 질의는 원장에 없다.** 그래서 이 표로 실패율을 읽을 수 없다. 그 사실은 `kb_ingest_runs` 와 서버 로그가 갖는다
- **보존 규칙이 없다.** 자라는 것을 받아들인 것이지 해결한 것이 아니다 (D24 선례).
  정리가 필요해지면 기간 기준 삭제가 다음 후보이고, 그때 `zero_hit_queries` 가 `최근` 인지 `전체` 인지도 함께 정해야 한다 —
  [service-and-mcp.md](../docs/service-and-mcp.md)는 `최근`이라 적고 구현은 전체를 센다
- **`event_stats`·`get_*` 이 빠지므로 이 표는 `AI가 무엇을 물었나`의 전부가 아니다.** 검색만의 원장이다
- **`GET /v1/docs`(Q30)** 는 이 결정들 밖이다. 표면이 생기면 로그 대상인지 그때 정한다

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
- 검색 병합은 RRF `k=60`, 후보 풀은 팔마다 60행, 문서당 최대 2행, `excerpt` 800자 (D33)
- 키워드는 `plainto_tsquery` + `ts_rank(…, 1)` (문서) · `websearch_to_tsquery` (이벤트) (D33·D34)
- 이벤트 `tsv` 입력 네 필드 — `title`·`summary`·`root_cause`·`resolution` (D34)
- `pg_trgm` 은 v1 미사용, 이벤트 벡터는 v1 미충전 (D34)
- 질의 로그를 남기는 표면은 `search_docs`·`search_events` 둘, `client` 는 `http`·`mcp` (D48·D49)
- `hit_count` 는 돌려준 행 수, 문서 `hit_paths` 는 중복을 접지 않는다 (D49)

## 이 값들이 복제된 위치

정본은 이 파일이다. 아래 사본이 어긋나면 **이 파일이 이긴다.** 값을 바꿀 때 함께 고친다.

| 사본 | 복제된 값 |
|---|---|
| [docs/plan.md](../docs/plan.md) §2 | 확정 스택 표 전체 |
| [CLAUDE.md](../CLAUDE.md) | 확정 스택 표 (도구 컨텍스트용 미러), Q32 요약 |
| [docs/data-model.md](../docs/data-model.md) | `vector(1536)`, 모델 ID, 확장 목록, 질의 로그 컬럼 의미 (D48–D52) |
| [docs/service-and-mcp.md](../docs/service-and-mcp.md) | 서비스 주소, 인증, `top_k`, 색인 경로, `kb_status` 가 로그를 쓰지 않는다는 것(D48). **`heading_path` 형식은 그쪽이 정본** |
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

D52 이후로 기록해야 할 미해결 결정은 [docs/open-questions.md](../docs/open-questions.md)에 전부 모여 있다.
2026-09-03 기준 남은 것은 C절의 Q13·Q14 · D절의 Q22·Q23 · Q24·Q25 · G절의 Q30이다.
**Q31은 열어 둔 이튿날 D47로 닫혔다** — 8단계가 `.venv` 에 서드파티 문서를 들여 게이트를 붉게 만들었다.
Q23 은 D29 가 절반만 답했다 — 값을 어디서 얻는지는 정해졌고 `status` 의 생애가 남았다.
E절(검증 경로)은 Q26 하나였고 D22로 닫혔다. B절은 Q6·Q7·Q10이 D30–D32로, Q8·Q9가 D33–D34로 닫혀 전부 마감됐다.
7단계를 막던 Q12·Q15·Q19·Q20은 D35–D38로 닫혔고, 8단계를 막던 Q17은 D42–D46으로 닫혔다.
F절(Q27–Q29)은 7단계를 구현하다 열렸고 같은 날 D39–D41로 닫혔다 — 열린 채로 코드가 나간 적은 없다.
**G절은 7단계를 검증하다 열렸다** — Q31은 D47로 닫혔고 **Q30(`GET /v1/docs`의 단계·계약)은 열려 있다.**
Q30은 단계를 막지 않으므로 §7 의 게이트 문장에는 넣지 않는다.
**H절의 Q32는 9단계를 막았고 D48–D52로 닫혔다** (2026-09-03) — 그 게이트 문장은 §7 에 넣는다 (D52).
**지금 단계를 막는 Q는 하나도 없다.**
