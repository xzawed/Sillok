# Sillok — Agent 협업 규칙

Claude와 Grok이 같은 저장소를 만질 때 따른다.
세션 시작 시 **[docs/plan.md](docs/plan.md)** 를 먼저 읽는다. 저장소 지도는 [README.md](README.md).

이 파일은 에이전트 운영 규약이지 프로젝트 지식이 아니다. 그래서 Sillok 색인 대상이 아니다.

## 역할 나누기 (권장)

- **Grok**: 명세 해석, 스키마, API 계약, 분류 규칙, 리뷰, 경계 확인
- **Claude**: 서비스/MCP 구현, 테스트, 리팩터
- 어느 쪽이든 문서를 바꾸면 다른 쪽에 변경 요약을 남긴다.

역할은 권장이다. 도구가 바뀌어도 이 파일의 규칙은 유지한다.

## 명세를 고치는 순서

우선순위는 하나뿐이다:

```text
docs/plan.md = adr/0001-v1-stack-decisions.md   >   docs/ 나머지
```

계약을 바꾸려면 **[docs/plan.md](docs/plan.md)와 [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md)를 먼저** 고치고,
그 다음 하위 문서([spec](docs/spec.md), [data-model](docs/data-model.md), [service-and-mcp](docs/service-and-mcp.md), [SKILL](docs/skills/sillok-storage/SKILL.md))와 구현을 맞춘다.

같은 값이 여러 문서에 있으면 사본에 정본 위치를 적는다. 어긋나면 정본이 이긴다.
**충돌 판정은 파일 서열보다 사실 소유권이 먼저다** — [README.md](README.md)의 문서 지도에서 그 사실을 소유한 파일이 이긴다.
소유자가 지도에 없으면 위 서열로 판정하고, 판정 후 그 사실의 소유자를 지도에 추가한다.

문서를 옮기거나 링크를 고쳤으면 `node scripts/check-layout.mjs` 를 돌린다. 실패하면 머지하지 않는다.

## 하지 말 것

- [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md)의 확정 값을 뒤집지 않는다. 바꾸려면 위 순서를 따른다.
- Git 문서 폴더에 이벤트 이력을 append하지 않는다.
- MCP에서 임의 SQL을 노출하지 않는다.
- 검색 결과 없이 모델이 DB 내용을 안다고 가정하는 기능을 만들지 않는다.
- SCAManager, 전사 검색, 공개 라이브러리 문서를 범위에 넣지 않는다.
- [docs/open-questions.md](docs/open-questions.md)의 미해결 항목을 추측으로 채우고 구현하지 않는다. 먼저 결정하고 ADR에 기록한다.

## 할 것

- 식별자(테이블, 도구, 필드)는 영어. 설명 문장은 한국어 가능.
- 저장은 `save_doc` / `save_event`만.
- 검색 기본 `top_k`는 8, 최대 12.
- 통계는 SQL 집계. 통계 질문에 벡터 검색을 쓰지 않는다.
- API와 MCP는 같은 Service 함수를 탄다.

## 문서 우선

동작이 명세와 다르면 코드가 틀린 것으로 본다.

## 확정 전제 (2026-08-30 · D16–D20은 2026-08-31)

> 정본: [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md) — 값이 다르면 정본이 이긴다.

```text
DECIDED: Python FastAPI
DECIDED: embedding = text-embedding-3-small (1536); no key -> keyword only
DECIDED: save_doc = proposal only
DECIDED: get_file = workspace path
DECIDED: MCP = stdio + HTTP, same Service process
DECIDED: ingest CLI; docs/** + root README* + adr/**
DECIDED: no web UI in v1 (JSON status API only)
DECIDED: python 3.12 + uv + pytest
DECIDED: env = DATABASE_URL + SILLOK_{HOST,PORT,WORKSPACE,BEARER_TOKEN} + OPENAI_API_KEY
DECIDED: migrations = versioned raw .sql, idempotent, applied on serve startup before bind
DECIDED: sillok ingest calls Service functions in-process; the CLI owns no SQL
DECIDED: POST /v1/ingest = same function over HTTP; operator entry point is the CLI
DECIDED: error code -> HTTP: VALIDATION 422, UNAUTHORIZED 401, NOT_FOUND 404,
         CONFLICT 409 (reserved, never emitted in v1), INTERNAL 500
DECIDED: body is always the {ok, data|error} envelope; INTERNAL message is a fixed string
```
