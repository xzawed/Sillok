---
title: Sillok
doc_type: readme
status: current
module: null
---

# Sillok

Git에는 **현재 진실**만. Postgres에는 **사건 원장**과 문서 인덱스만.
AI는 MCP로 필요한 행 몇 개만 읽는다.

Sillok은 RAG 플랫폼이 아니라, 위키가 로그가 되지 않게 **저장 위치를 강제하는 지식 원장**이다.

**문서가 곧 구현 계약이다.** 동작이 문서와 어긋나면 코드가 틀린 것으로 본다.
[docs/plan.md](docs/plan.md) §7의 1–3단계(Compose · 마이그레이션 · FastAPI 골격)까지 구현돼 있다.

> 진행 상태의 정본은 [docs/plan.md](docs/plan.md) §7·§9다 — 값이 다르면 정본이 이긴다.

## 시작점

구현 에이전트는 **[docs/plan.md](docs/plan.md)** 부터 읽는다. 나머지 문서는 PLAN이 가리킨다.
협업 규칙은 [AGENTS.md](AGENTS.md).

## 문서 지도

| 경로 | 역할 | `doc_type` | 이 문서가 **정본**으로 소유하는 것 |
|---|---|---|---|
| [docs/plan.md](docs/plan.md) | 구현 계약. 진입 문서 | `other` | 작업 순서, v1 완료 조건, 금지 목록 |
| [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md) | 확정 결정 D1–D21 | `adr` | **모든 확정값** (스택, 차원, 경로, 인증, 범위, **에러 코드↔HTTP 매핑**) |
| [docs/spec.md](docs/spec.md) | 문제·목표·비목표·세 층 | `other` | 세 층 구조, 비목표, 은유 |
| [docs/data-model.md](docs/data-model.md) | 테이블·인덱스·제약 | `schema` | DDL, 컬럼 enum 값 |
| [docs/service-and-mcp.md](docs/service-and-mcp.md) | HTTP API와 MCP 도구 계약 | `api` | 엔드포인트, 도구 8개, 요청·응답 JSON, **에러 코드 enum** |
| [docs/skills/sillok-storage/SKILL.md](docs/skills/sillok-storage/SKILL.md) | 저장 위치 규칙 (타 프로젝트 배포용) | `other` | 이벤트 필수 필드, 결정 트리, 거절 규칙 |
| [docs/open-questions.md](docs/open-questions.md) | 구현 전 답해야 할 공백 | `other` | 미해결 질문 전체 |
| [AGENTS.md](AGENTS.md) | 에이전트 협업 규약 | *(색인 안 함)* | 역할 분담, 금지 행위, **출하 루프 · PR 증거 · 테스트 방식** |
| [CLAUDE.md](CLAUDE.md) | Claude Code 전용 컨텍스트 | *(색인 안 함)* | 없음 — 전부 미러 |
| [.env.example](.env.example) | 환경변수 계약 사본 (D16) | *(색인 안 함)* | 없음 — 정본은 ADR §D16 |

`AGENTS.md`와 `CLAUDE.md`는 **에이전트 도구 설정**이지 프로젝트 지식이 아니다.
그래서 의도적으로 색인 경로(`docs/**`, 루트 `README*`, `adr/**`) 밖에 둔다.

## 우선순위

```text
docs/plan.md = adr/0001-v1-stack-decisions.md   (이 둘이 이긴다)
        >  docs/spec.md, docs/data-model.md, docs/service-and-mcp.md, docs/skills/**
```

계약을 바꾸려면 `docs/plan.md`와 `adr/0001-v1-stack-decisions.md`를 **먼저** 고치고 나서 하위 문서와 구현을 맞춘다.

### 충돌 판정

**파일 서열보다 사실 소유권이 먼저다.**
두 문서가 같은 사실을 다르게 말하면, 위 문서 지도에서 **그 사실을 정본으로 소유한 파일이 이긴다.**

소유자가 표에 없는 새 사실이면 위 서열로 판정하고, **그 사실의 소유자를 표에 추가한다.**
서열만으로 판정하면 새 문서가 늘어날 때마다 서열을 다시 협상해야 한다.

## 정본 표기 규칙

같은 값이 여러 문서에 나오면, 사본에는 반드시 정본 위치를 적는다.

> 정본: [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md) — 값이 다르면 정본이 이긴다.

사본을 지우지 않는 이유는 진입 문서와 도구 컨텍스트에서 값이 바로 보여야 하기 때문이다.
대신 **어긋났을 때 누가 이기는지가 항상 명시**되어야 한다.

## 자기 색인

Sillok의 색인 대상은 `docs/**`, 루트 `README*`, `adr/**`다 (D9).
이 저장소의 배치는 그 규칙을 그대로 따른다 — 즉 **Sillok의 첫 ingest 스모크 테스트는 이 저장소 자신을 대상으로 돌릴 수 있다.**

## 검증

```bash
node scripts/check-layout.mjs
```

이 저장소가 자기 색인 계약을 지키는지 검사한다. 코드와 무관한 **문서 게이트**다.

구현된 부분(§7 1–2단계)의 검증은 따로 있다:

```bash
docker compose up -d --wait   # db + api. 5432 는 게시하지 않고 8080 만 게시한다 (D16)
curl -i http://127.0.0.1:8080/v1/nope   # 404 + 공통 봉투. FastAPI 기본 detail 이 아니다
uv run pytest -q              # DB 가 없으면 DB 검사만 skip 된다
```

`api`는 bind 전에 마이그레이션을 돌린다 (D17) — 기동 로그에서 순서가 보인다.
**업무 라우트는 아직 없다.** `/v1/status` 같은 4단계 경로는 정직하게 404를 돌려준다.

호스트에서 DB 에 직접 붙어야 하면(`uv run pytest`의 DB 검사, `uv run sillok migrate`)
`compose.override.example.yml` 를 복사해 쓴다.

> 이 머신에서 `docker compose build`가 DNS로 실패하면 Docker Desktop의 프록시를 빌드에 넘긴다:
> `docker compose build --build-arg HTTP_PROXY=http://http.docker.internal:3128 --build-arg HTTPS_PROXY=http://http.docker.internal:3128 api`
> 런타임 컨테이너는 프록시가 자동으로 붙지만 빌드 샌드박스는 아니다. 환경 문제이므로 이미지에 굽지 않는다.

- D9 색인 대상(`docs/**`, 루트 `README*`, `adr/**`)에 걸리는 문서 목록과 `doc_type` 분포
- `AGENTS.md`·`CLAUDE.md`가 **색인되지 않는지** — 색인 0건이 정상인지 버그인지 구분하려면 양방향을 다 봐야 한다
- front matter 존재와 `doc_type`·`status` 값이 taxonomy 안에 있는지
- 상대 링크 전부 해석되는지, 진입점에서 모든 문서에 도달하는지
- 구 파일명 잔존 참조
- 존재하지 않는 `Q` 번호 참조 — `open-questions.md`가 실제로 정의한 집합과 대조
- 머지되면 의미를 잃는 지시어(`이 PR` 등) — 커밋 해시·날짜·PR 번호로 고정해야 한다
- 닫히지 않은 코드 펜스 — 열린 펜스가 뒤 본문을 코드로 먹어 위 검사를 무력화하는 것을 막는다
- **Q 게이트** — 어떤 단계를 막는 Q가 아직 열려 있는데 그 단계의 라우트·CLI 명령·MCP가
  `src/`에 있으면 실패한다. `plan.md` §7의 *"n단계 전에 Qx"* 문장을 읽어 강제하므로,
  그 문장을 고치면 검사가 따라온다 — 같은 사실을 두 곳에 적지 않는다.
  §7에서 절이 사라지거나 파싱되지 않으면 그 자체를 실패로 본다(게이트가 조용히 비는 것을 막는다).
  **한계:** 경로가 **문자열 리터럴**일 때만 본다. 데코레이터·`add_api_route`·`mount`·`include_router`와
  라우터 `prefix` 조합까지는 잡지만, 변수나 f-string으로 만든 경로는 못 잡는다.
  `prefix`는 **같은 파일 안에서만** 합쳐 보므로, 라우터를 여러 모듈로 쪼개면 놓친다 —
  지금은 `api.py` 하나라 성립하고, 쪼갤 때 이 검사를 함께 넓힌다

`sillok ingest`가 생기면 이 스크립트를 실제 색인 결과 대조로 확장한다 →
[docs/plan.md](docs/plan.md) §7 5단계·§9. 그 전에 [docs/open-questions.md](docs/open-questions.md) Q6(ingest 결정성)이 답해져야 한다.

## 상태

- 이름: Sillok (실록) — 확정
- D1–D15: 2026-08-30 확정 · D16–D20: 2026-08-31 확정 → [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md)
- 스택: Python 3.12 · uv · pytest · FastAPI, OpenAI `text-embedding-3-small` (1536), Docker Compose, MCP stdio + HTTP
- SCAManager 연동: 비범위
- 구현: **§7 1–3단계 완료** (2026-08-31 실측). 4단계(`save_event`·`event_stats`·`kb_status`)부터 남았다.
  [docs/open-questions.md](docs/open-questions.md)가 단계별로 막는다 — **4단계 전에 Q16·Q18·Q21**.

## 코드 배치

| 경로 | 역할 |
|---|---|
| `docker-compose.yml` · `Dockerfile` | D13 스택 — `db` + `api` |
| `compose.override.example.yml` | 호스트에서 DB에 붙어야 할 때만 복사해 쓰는 오버라이드 (D16) |
| `migrations/001_extensions.sql` · `002_schema.sql` | D17. DDL 정본은 [docs/data-model.md](docs/data-model.md) |
| `src/sillok/config.py` | D16 환경변수 계약 |
| `src/sillok/migrations.py` | D17 러너. **Service 쪽이지 CLI 쪽이 아니다** (D19) |
| `src/sillok/api.py` | D21 공통 봉투와 D7 게이트. **업무 라우트는 없다** — 4단계 |
| `src/sillok/cli.py` | `sillok migrate` · `sillok serve`. SQL을 갖지 않는다 |
| `tests/` | pytest. DB 없으면 DB 검사만 skip |
