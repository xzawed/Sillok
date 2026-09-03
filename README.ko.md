<div align="center">

# Sillok · 실록

**저장 위치를 강제하는 지식 원장.**<br>
현재 진실은 Git에, 무슨 일이 있었는지는 Postgres에. AI는 행 몇 개만 읽습니다.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![uv](https://img.shields.io/badge/uv-managed-DE5FE9?logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

[English README](README.md) · 정본은 영문입니다. **어긋나면 영문이 이깁니다 (D27).**

</div>

---

## 무엇인가

Sillok은 RAG 플랫폼이 **아닙니다.**
프로젝트의 **규범**과 **이력**을 일부러 다른 곳에 두는 작고 완고한 저장소입니다 —
위키가 로그가 되지 않게 하려는 것입니다.

- **Git**은 현재 진실을 담습니다. 현재형으로 쓴 최신본 하나면 됩니다.
- **Postgres**는 사건 원장과 Git 문서의 검색 인덱스를 담습니다.
- **AI**는 좁은 도구 표면을 통해서만 닿고, 문서가 아니라 **행**을 받습니다.

핵심은 **적재량이 늘어도 질의당 비용이 거의 고정**이라는 점입니다.
"관련 문서 전부" 반환은 기능이 아니라 설계 위반으로 봅니다.

## 왜

| 증상 | Sillok의 답 |
|---|---|
| 위키가 로그가 된다 | 규범은 Git, "언제 무엇이 있었는지"는 이벤트 원장. 섞이는 경로 자체가 없다 |
| 모델이 큰 파일을 읽고 틀린다 | 도구가 문서가 아니라 **행**을 돌려준다 |
| 건수·재발을 글에서 셀 수 없다 | 이벤트를 SQL로 집계한다. `repeat_causes`가 반복 원인을 센다 |

## 빠른 시작

Docker만 있으면 됩니다. api 컨테이너가 자기 파이썬을 들고 있습니다.

```bash
docker compose up -d --wait
curl -s "http://127.0.0.1:8080/v1/status?project=demo"
```

게시되는 포트는 `8080` 하나입니다.
Postgres는 내부 네트워크에 남으므로 Service 말고는 DB에 닿지 않습니다.

```json
{ "ok": true, "data": { "documents": 0, "chunks": 0, "events": 0, "last_ingest_at": null,
                        "zero_hit_queries": 0, "chunks_without_embedding": 0 } }
```

### 이벤트는 채워 주지 않고 거절한다

필수 필드가 여섯입니다. 하나라도 없으면 **저장하지 않습니다.**

```bash
curl -s -X POST http://127.0.0.1:8080/v1/events \
  -H 'Content-Type: application/json' -d '{"project":"demo"}'
```

```json
{ "ok": false, "error": { "code": "VALIDATION",
  "message": "missing required field: kind, title, summary, occurred_at, result" } }
```

같은 실패를 `auth`에 두 번, `billing`에 두 번 남겨 봅니다.

```bash
for m in auth auth billing billing; do
  curl -s -X POST http://127.0.0.1:8080/v1/events \
    -H 'Content-Type: application/json' \
    -d "{\"project\":\"demo\",\"kind\":\"failure\",
         \"title\":\"pool exhausted after deploy\",
         \"summary\":\"connection pool ran out\",
         \"occurred_at\":\"2026-08-31T09:00:00Z\",
         \"resolved_at\":\"2026-08-31T10:00:00Z\",
         \"result\":\"failure\",\"module\":\"$m\",
         \"root_cause\":\"pool exhausted\"}"
done
```

네 번 부르면 응답도 넷입니다. 빈 DB 기준으로 `id`는 1부터 증가합니다.

```json
{ "ok": true, "data": { "id": 1 } }
{ "ok": true, "data": { "id": 2 } }
{ "ok": true, "data": { "id": 3 } }
{ "ok": true, "data": { "id": 4 } }
```

성공이든 실패든 **본문은 언제나 같은 봉투**입니다.
프레임워크 기본 응답이 새어 나오지 않습니다.

### 반복은 모듈까지 갈라서 센다

같은 `root_cause`라도 모듈이 다르면 다른 반복입니다.
합치면 **있지도 않은 네 번의 반복**을 보고하게 됩니다.

```bash
curl -s "http://127.0.0.1:8080/v1/stats/events?project=demo"
```

```json
{ "ok": true, "data": {
  "total": 4,
  "by_kind":   { "failure": 4 },
  "by_result": { "failure": 4 },
  "by_module": { "auth": 2, "billing": 2 },
  "repeat_causes": [
    { "module": "auth",    "root_cause": "pool exhausted", "count": 2 },
    { "module": "billing", "root_cause": "pool exhausted", "count": 2 }
  ],
  "avg_resolution_seconds": 3600
} }
```

통계는 **벡터를 쓰지 않고** 필터와 `COUNT`/`AVG`만 씁니다.
미해결 건은 평균에서 빠지므로 전부 미해결이면 `0`이 아니라 `null`입니다.
`by_*`는 JSON 객체라 키 순서는 보장하지 않습니다.

## 어떻게 도는가

```text
[1] PostgreSQL + pgvector   kb_documents · kb_chunks · kb_events · 로그
[2] Knowledge Service       FastAPI. DB를 만지는 유일한 문
[3] 출구                    MCP 도구 · Skill · JSON 현황 API
```

[1]과 [2]는 서 있고 [3]은 JSON API와 MCP 도구 여덟을 함께 냅니다.

- **불변식의 단위는 Service 함수이지 HTTP가 아닙니다.** MCP와 사람용 UI는 HTTP API를 통해야 하고,
  CLI는 같은 함수를 인프로세스로 부릅니다.
  금지되는 것은 어디서든 **두 번째 SQL 계층**이 생기는 것입니다.
- **임베딩은 설계상 선택입니다.** `OPENAI_API_KEY`가 없으면 `embedding`은 NULL이고
  문서 검색은 `tsv` 키워드만 씁니다. 이벤트 검색은 키가 있어도 키워드만입니다 —
  v1 은 이벤트를 임베딩하지 않습니다.
  키가 있으면 벡터 팔이 켜지고, 없으면 병합이 키워드 목록 하나 위에서만 돕니다.
- **비밀은 환경변수로만 옵니다.** [.env.example](.env.example)을 참조하십시오.

## 상태

| 영역 | 상태 |
|---|---|
| Compose · 마이그레이션 · FastAPI 골격 | 된다 |
| `POST /v1/events` · `GET /v1/stats/events` · `GET /v1/status` | 된다 |
| 검색 — `POST /v1/search/docs` 와 `/v1/search/events` | 된다. 키가 없으면 벡터 팔이 비는데 그것이 설계상 정상이다 |
| `get_event` · `get_file` · `save_doc` | 된다. `get_file`은 색인된 행만 열고 4000자 창으로 답하며, `save_doc`은 제안만 돌려주고 Git을 건드리지 않는다 |
| 색인 — `sillok ingest` 와 `POST /v1/ingest` | 된다. 임베딩은 키가 있어야 하고, 없으면 벡터가 NULL 로 남는다 |
| MCP 도구 | 된다. `POST /mcp` 와 stdio(`sillok mcp`)로 여덟 개. 각 도구는 HTTP 얼굴과 같은 봉투로 답한다 |
| 질의 원장 — `kb_query_logs` | 된다. 검색 도구 둘이 질의마다 한 행을 남기고, `kb_status` 가 0건 질의를 그 표에서 센다 |

> 진행 상태의 정본은 [docs/plan.md](docs/plan.md) §7·§9입니다.

**스텁은 만들지 않습니다.**
뜨기만 하는 라우트를 완료 조건 자리에 올려 두면 진척처럼 보입니다.

미해결 설계 질문은 [docs/open-questions.md](docs/open-questions.md)에 있고,
**그 질문이 막는 단계는 실제로 막힙니다** — 관례가 아니라 검사가 강제합니다.

## 문서

설계 문서는 한국어로 씁니다.

| 문서 | 소유하는 것 |
|---|---|
| [docs/plan.md](docs/plan.md) | 구현 계약. 작업 순서, v1 완료 조건 |
| [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md) | 모든 확정값 — 스택, 차원, 경로, 인증, 에러 매핑, 라이선스 |
| [docs/conventions.md](docs/conventions.md) | 문서 지도, 충돌 판정, 문서 게이트 |
| [docs/spec.md](docs/spec.md) · [docs/data-model.md](docs/data-model.md) · [docs/service-and-mcp.md](docs/service-and-mcp.md) | 문제 정의 · 스키마 · API와 MCP 계약 |
| [docs/skills/sillok-storage/SKILL.md](docs/skills/sillok-storage/SKILL.md) | 저장 위치 결정 트리 — 무엇이 문서가 되고 무엇이 이벤트가 되는가 |
| [docs/open-questions.md](docs/open-questions.md) | 아직 답이 없는 것 |
| [AGENTS.md](AGENTS.md) | 한 변경이 나가는 절차와 무엇이 증거인가 |

**여기서는 문서가 코드를 이깁니다.** 동작이 계약과 어긋나면 코드가 틀린 것입니다.

## 개발

```bash
node scripts/evidence.mjs   # 변경 하나가 보여야 할 것을 한 명령으로 전부
```

| 명령 | 무엇을 보는가 |
|---|---|
| `node scripts/check-layout.mjs` | 문서 게이트. 코드와 무관하다 |
| `node scripts/check-layout.test.mjs` | **그 게이트가 실제로 무는지.** 저장소를 임시로 복사해 복사본에 고장을 주입한다 |
| `uv run pytest -q` | 호스트 테스트. DB 검사는 skip된다 |
| `docker compose --profile test run --rm test` | DB 검사까지 전부. `5432`는 닫힌 채로 돈다 |

호스트에서 `skip 0`이 보이면 포트 오버라이드가 켜졌다는 뜻입니다.
더 나은 결과가 아니라 신호입니다.
커밋된 Compose는 `5432`를 게시하지 않습니다.
호스트에서 DB에 닿아야 하면 `compose.override.example.yml`을 복사합니다.

<details>
<summary><code>docker compose build</code>가 DNS로 실패한다면</summary>

런타임 컨테이너에는 프록시가 붙지만 **빌드 샌드박스에는 붙지 않는** 환경이 있습니다.
그럴 때만 넘깁니다.

```bash
docker compose build \
  --build-arg HTTP_PROXY="$HTTP_PROXY" \
  --build-arg HTTPS_PROXY="$HTTPS_PROXY" api
```

환경 문제이므로 **이미지에 굽지 않습니다.**

</details>

## 코드 배치

| 경로 | 역할 |
|---|---|
| `docker-compose.yml` · `Dockerfile` | `db` + `api`. `test` 서비스는 Compose 프로필 뒤에 있다 |
| `migrations/` | 버전 붙인 raw SQL. 서버가 bind하기 전에 적용된다 |
| `src/sillok/service.py` | DB를 만지는 유일한 문. 검증은 DDL 제약이 아니라 여기 있다 |
| `src/sillok/api.py` | HTTP 어댑터 — 공통 봉투와 Bearer 게이트. SQL을 갖지 않는다 |
| `src/sillok/cli.py` | `sillok migrate` · `sillok serve` · `sillok ingest` · `sillok mcp` |
| `scripts/` | 문서 게이트, 그 게이트의 고장 주입, 증거 수집기, 10단계 스모크 |
| `tests/` | pytest |

## 라이선스

[MIT](LICENSE).

공개돼 있지만 **개인 도구**입니다.
기여 절차도, 이슈 템플릿도, 하위호환 약속도 없습니다.
