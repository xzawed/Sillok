---
title: Sillok
doc_type: readme
status: current
module: null
---

# Sillok 실록

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![uv](https://img.shields.io/badge/uv-managed-DE5FE9?logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![docs-first](https://img.shields.io/badge/docs--first-계약이_코드를_이긴다-2E7D32)](docs/plan.md)

> **Git에는 현재 진실만. Postgres에는 사건 원장만. AI는 필요한 행 몇 개만 읽는다.**

Sillok은 RAG 플랫폼이 아니다. **위키가 로그가 되지 않게 저장 위치를 강제하는 지식 원장**이다.

---

## 무엇을 푸는가

프로젝트 문서에 규칙과 이력이 같이 쌓이면 세 가지가 무너진다.

| 증상 | Sillok의 답 |
|---|---|
| 위키가 로그가 된다 | **현재형 규범은 Git, 언제 무엇이 어땠는지는 이벤트 원장** — 섞이는 경로를 없앤다 |
| 모델이 큰 파일을 읽고 틀린다 | MCP 도구가 **행 몇 개만** 돌려준다. 문서를 대화에 통째로 넣지 않는다 |
| 건수·재발을 글에서 셀 수 없다 | 이벤트를 SQL로 집계한다. `repeat_causes`가 반복 원인을 센다 |

적재량이 늘어도 **질의당 토큰은 거의 고정**이다. "관련 문서 전부" 반환은 설계 위반으로 본다.

## 세 층

```text
[1] PostgreSQL + pgvector   kb_documents · kb_chunks · kb_events · 로그
[2] Knowledge Service       FastAPI. DB를 만지는 유일한 문
[3] 출구                    MCP 도구 8개 · Skill · JSON 현황 API
```

**이건 설계다.** [1]과 [2]는 서 있고 [3]은 JSON API만 있다 — 무엇이 실제로 도는지는 [아래 표](#지금-되는-것--아직-아닌-것)에.

## 빠른 시작

```bash
docker compose up -d --wait                # db + api. 8080만 게시한다
curl -s http://127.0.0.1:8080/v1/status?project=demo
```

```json
{ "ok": true, "data": { "documents": 0, "chunks": 0, "events": 0,
                        "last_ingest_at": null, "zero_hit_queries": 0 } }
```

**필수 6개 필드가 없으면 저장하지 않고 거절한다.** 관대하게 채우지 않는다.

```bash
curl -s -X POST http://127.0.0.1:8080/v1/events \
  -H 'Content-Type: application/json' -d '{"project":"demo"}'
```

```json
{ "ok": false, "error": { "code": "VALIDATION",
  "message": "missing required field: kind, title, summary, occurred_at, result" } }
```

여섯 개를 다 채우면 저장된다. 같은 원인을 `auth`에 두 번, `billing`에 두 번 남겨 본다.

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

```json
{ "ok": true, "data": { "id": 1 } }
```

성공이든 실패든 **본문은 언제나 같은 봉투**다. 프레임워크 기본 응답이 새어 나오지 않는다.

### 반복 원인은 모듈까지 갈라서 센다

같은 `root_cause`라도 모듈이 다르면 다른 반복이다. 한 줄로 합치면
`auth` 두 번과 `billing` 두 번이 **있지도 않은 네 번의 반복**으로 보고된다.

```bash
curl -s "http://127.0.0.1:8080/v1/stats/events?project=demo"
```

```json
{ "ok": true, "data": {
  "total": 4,
  "by_kind":   { "failure": 4 },
  "by_result": { "failure": 4 },
  "by_module": { "billing": 2, "auth": 2 },
  "repeat_causes": [
    { "module": "auth",    "root_cause": "pool exhausted", "count": 2 },
    { "module": "billing", "root_cause": "pool exhausted", "count": 2 }
  ],
  "avg_resolution_seconds": 3600
} }
```

통계는 **벡터를 쓰지 않는다.** 필터와 `COUNT`/`AVG`뿐이다.
아직 해결되지 않은 건은 평균에서 빠진다 — 전부 미해결이면 `0`이 아니라 `null`이다.

## 지금 되는 것 / 아직 아닌 것

| | 상태 |
|---|---|
| Compose · 마이그레이션 · FastAPI 골격 | 된다 |
| `POST /v1/events` · `GET /v1/stats/events` · `GET /v1/status` | 된다 |
| 색인(`sillok ingest`) · 검색 · `get_file` · MCP 도구 | **아직이다. 그 경로는 정직하게 404다** |

> 진행 상태의 정본은 [docs/plan.md](docs/plan.md) §7·§9다 — 값이 다르면 정본이 이긴다.

**스텁을 만들지 않는다.** 뜨기만 하는 라우트를 완료 조건 자리에 올려 두면 통과한 것처럼 보인다.

---

## 이 저장소의 성격

**문서가 곧 구현 계약이다.** 동작이 문서와 어긋나면 **코드가 틀린 것으로 본다.**
구현 에이전트는 [docs/plan.md](docs/plan.md)부터 읽는다. 협업 규칙은 [AGENTS.md](AGENTS.md).

### 문서 지도

| 경로 | 역할 | `doc_type` | 이 문서가 **정본**으로 소유하는 것 |
|---|---|---|---|
| [docs/plan.md](docs/plan.md) | 구현 계약. 진입 문서 | `other` | 작업 순서, v1 완료 조건, 금지 목록 |
| [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md) | 확정 결정 D1–D26 | `adr` | **모든 확정값** (스택, 차원, 경로, 인증, 범위, 에러 코드↔HTTP 매핑) |
| [docs/spec.md](docs/spec.md) | 문제·목표·비목표·세 층 | `other` | 세 층 구조, 비목표, 은유 |
| [docs/data-model.md](docs/data-model.md) | 테이블·인덱스·제약 | `schema` | DDL, 컬럼 enum 값 |
| [docs/service-and-mcp.md](docs/service-and-mcp.md) | HTTP API와 MCP 도구 계약 | `api` | 엔드포인트, 도구 8개, 요청·응답 JSON, 에러 코드 enum |
| [docs/skills/sillok-storage/SKILL.md](docs/skills/sillok-storage/SKILL.md) | 저장 위치 규칙 (타 프로젝트 배포용) | `other` | 이벤트 필수 필드, 결정 트리, 거절 규칙 |
| [docs/open-questions.md](docs/open-questions.md) | 아직 답이 없는 것 | `other` | 미해결 질문 전체 |
| [AGENTS.md](AGENTS.md) | 에이전트 협업 규약 | *(색인 안 함)* | 역할 분담, 금지 행위, 출하 루프 · PR 증거 · 테스트 방식 |
| [CLAUDE.md](CLAUDE.md) | Claude Code 전용 컨텍스트 | *(색인 안 함)* | 없음 — 전부 미러 |
| [.env.example](.env.example) | 환경변수 계약 사본 (D16) | *(색인 안 함)* | 없음 — 정본은 ADR §D16 |

`AGENTS.md`와 `CLAUDE.md`는 **에이전트 도구 설정**이지 프로젝트 지식이 아니다.
그래서 의도적으로 색인 경로(`docs/**`, 루트 `README*`, `adr/**`) 밖에 둔다.

### 충돌은 서열이 아니라 소유권으로 판정한다

```text
docs/plan.md = adr/0001-v1-stack-decisions.md   (이 둘이 이긴다)
        >  docs/spec.md, docs/data-model.md, docs/service-and-mcp.md, docs/skills/**
```

**다만 파일 서열보다 사실 소유권이 먼저다.** 두 문서가 같은 사실을 다르게 말하면
위 지도에서 **그 사실을 정본으로 소유한 파일이 이긴다.** 소유자가 표에 없는 새 사실이면
서열로 판정하고 **그 사실의 소유자를 표에 추가한다** — 서열만으로 판정하면 문서가 늘 때마다 서열을 다시 협상하게 된다.

계약을 바꾸려면 `plan.md`와 ADR을 **먼저** 고치고 나서 하위 문서와 구현을 맞춘다.

### 사본에는 정본 위치를 적는다

> 정본: [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md) — 값이 다르면 정본이 이긴다.

사본을 지우지 않는 이유는 진입 문서와 도구 컨텍스트에서 값이 바로 보여야 하기 때문이다.
대신 **어긋났을 때 누가 이기는지가 항상 명시**되어야 한다.

### 자기 색인

색인 대상은 `docs/**`, 루트 `README*`, `adr/**`다 (D9). **이 저장소의 배치가 그 규칙을 그대로 따른다** —
즉 Sillok의 첫 ingest 스모크는 이 저장소 자신을 대상으로 돌릴 수 있다.

---

## 검증

```bash
node scripts/evidence.mjs   # PR 증거 4종을 한 번에. 하나라도 못 돌리면 실패한다
```

네 가지를 돌리고 PR 본문에 붙일 블록을 낸다 — 문서 게이트 · 그 게이트의 고장 주입 · 호스트 테스트 · DB 포함 테스트.

<table>
<tr><th>명령</th><th>무엇을 보는가</th></tr>
<tr><td><code>check-layout.mjs</code></td><td>문서 게이트. 코드와 무관하다</td></tr>
<tr><td><code>check-layout.test.mjs</code></td><td><b>그 게이트가 실제로 무는지.</b> 저장소를 임시로 복사해 복사본에 고장을 주입한다</td></tr>
<tr><td><code>uv run pytest -q</code></td><td>호스트 테스트. DB 검사는 skip된다</td></tr>
<tr><td><code>docker compose --profile test run --rm test</code></td><td>DB 검사까지. <code>5432</code>는 닫힌 채로 돈다 (D22)</td></tr>
</table>

**`skip 0`을 보았다면 오버라이드가 켜져 있다는 뜻이지 더 나은 결과가 아니다.** D16이 `5432`를 게시하지 않기 때문에
호스트에서는 DB 검사가 skip되는 것이 정상이다. 호스트에서 DB에 직접 붙어야 하면 `compose.override.example.yml`을 복사해 쓴다.

**통과 출력만으로는 검사가 살아 있는지 알 수 없다.** 그래서 고장 주입을 커밋한다 — 각 검사를 껐을 때
같은 주입이 통과하는지 보는 메타 케이스까지 함께 돈다.

<details>
<summary><b>문서 게이트가 검사하는 것</b></summary>

- D9 색인 대상에 걸리는 문서 목록과 `doc_type` 분포
- `AGENTS.md`·`CLAUDE.md`가 **색인되지 않는지** — 색인 0건이 정상인지 버그인지 구분하려면 양방향을 다 봐야 한다
- front matter 존재와 `doc_type`·`status`가 taxonomy 안에 있는지
- 상대 링크가 전부 해석되는지, 진입점에서 모든 문서에 도달하는지
- 구 파일명 잔존 참조 / 존재하지 않는 `Q` 번호 참조
- 머지되면 의미를 잃는 지시어 — 커밋 해시·날짜·PR 번호로 고정해야 한다
- 닫히지 않은 코드 펜스 — 열린 펜스가 뒤 본문을 먹어 위 검사를 무력화하는 것을 막는다
- 산문에 박힌 테스트 수치 — 검사가 늘면 낡는다. 이력으로 인용하려면 백틱 안에 넣는다
- 폐기된 문구 — 정본을 고치고 사본에 옛 문장을 남기는 것을 막는다
- **Q 게이트** — 어떤 단계를 막는 질문이 아직 열려 있는데 그 단계의 라우트·CLI·MCP가 `src/`에 있으면 실패한다.
  `plan.md` §7의 *"n단계 전에 Qx"* 문장을 **읽어서** 강제하므로 그 문장을 고치면 검사가 따라온다.
  §7에서 절이 사라지거나 파싱되지 않으면 그 자체를 실패로 본다.

**Q 게이트의 한계:** 경로가 **문자열 리터럴**일 때만 본다. 데코레이터·`add_api_route`·`mount`·`include_router`와
라우터 `prefix` 조합까지는 잡지만 변수나 f-string 경로는 못 잡는다. `prefix`는 **같은 파일 안에서만** 합쳐 보므로
라우터를 여러 모듈로 쪼개면 놓친다 — 쪼갤 때 이 검사를 함께 넓힌다.

</details>

<details>
<summary><b>Docker 빌드가 DNS로 실패한다면</b></summary>

런타임 컨테이너에는 프록시가 자동으로 붙지만 **빌드 샌드박스에는 붙지 않는** 환경이 있다.
그럴 때만 쓰는 환경의 프록시 주소를 빌드에 넘긴다.

```bash
docker compose build \
  --build-arg HTTP_PROXY="$HTTP_PROXY" \
  --build-arg HTTPS_PROXY="$HTTPS_PROXY" api
```

환경 문제이므로 **이미지에 굽지 않는다.**

</details>

---

## 코드 배치

| 경로 | 역할 |
|---|---|
| `docker-compose.yml` · `Dockerfile` | D13 스택 — `db` + `api`. 테스트용 `test`는 `profiles` 게이트 (D22) |
| `compose.override.example.yml` | 호스트에서 DB에 붙어야 할 때만 복사해 쓰는 오버라이드 (D16) |
| `migrations/001_extensions.sql` · `002_schema.sql` | D17. DDL 정본은 [docs/data-model.md](docs/data-model.md) |
| `src/sillok/config.py` | D16 환경변수 계약 |
| `src/sillok/migrations.py` | D17 러너. **Service 쪽이지 CLI 쪽이 아니다** (D19) |
| `src/sillok/api.py` | D21 공통 봉투와 D7 게이트, 라우트. **SQL을 갖지 않는다** (D19) |
| `src/sillok/service.py` | DB를 만지는 유일한 문. `save_event`·`event_stats`·`kb_status`와 D25 검증 |
| `src/sillok/cli.py` | `sillok migrate` · `sillok serve`. SQL을 갖지 않는다 |
| `scripts/` | 문서 게이트 · 그 게이트의 고장 주입 · 증거 수집기 |
| `tests/` | pytest. DB 없으면 DB 검사만 skip |

## 상태

- 이름: **Sillok**(실록) — 확정
- 확정 결정 **D1–D26** → [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md)
- 스택: Python 3.12 · uv · pytest · FastAPI · PostgreSQL 16 + pgvector · Docker Compose
- **결정만 되어 있고 아직 안 붙은 것**: OpenAI `text-embedding-3-small`(1536) · MCP stdio + HTTP
- **키가 없어도 돈다** — `embedding`은 NULL이고 `tsv` 키워드 검색만 동작한다 (D2)
- 다음: 색인(§7 5단계). 그 전에 [docs/open-questions.md](docs/open-questions.md)의 Q6·Q7·Q10을 답해야 한다
- SCAManager 연동 · 전사 검색 · 웹 UI: **비범위**

## 라이선스

**아직 정하지 않았다.** 라이선스가 없으면 기본적으로 모든 권리가 유보된다.
이 저장소는 공개돼 있지만 **개인 도구**이고, 기여 절차·이슈 템플릿·하위호환 약속은 없다 (D26).
