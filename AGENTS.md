# Sillok — Agent 협업 규칙

Claude와 Grok이 같은 저장소를 만질 때 따른다.
세션 시작 시 **[docs/plan.md](docs/plan.md)** 를 먼저 읽는다. 저장소 지도는 [docs/conventions.md](docs/conventions.md).

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
그 다음 하위 문서([conventions](docs/conventions.md), [spec](docs/spec.md), [data-model](docs/data-model.md), [service-and-mcp](docs/service-and-mcp.md), [SKILL](docs/skills/sillok-storage/SKILL.md))와 구현을 맞춘다.

같은 값이 여러 문서에 있으면 사본에 정본 위치를 적는다. 어긋나면 정본이 이긴다.
**충돌 판정은 파일 서열보다 사실 소유권이 먼저다** — [docs/conventions.md](docs/conventions.md)의 문서 지도에서 그 사실을 소유한 파일이 이긴다.
소유자가 지도에 없으면 위 서열로 판정하고, 판정 후 그 사실의 소유자를 지도에 추가한다.

문서를 옮기거나 링크를 고쳤으면 `node scripts/check-layout.mjs` 를 돌린다. 실패하면 머지하지 않는다.

## 변경 하나가 나가는 순서

무엇을 어떤 순서로 만드는지는 [docs/plan.md](docs/plan.md) §7이 소유한다. 여기는 **한 변경이 나가는 절차**다.

1. 그 단계를 막는 Q를 **먼저** 답하고 ADR에 `Dnn`으로 적는다. 어느 Q가 어느 단계를 막는지는 §7이 소유한다.
   `scripts/check-layout.mjs`가 이것을 강제한다 — 열린 Q가 막는 단계의 표면이 `src/`에 있으면 실패한다.
2. 위 `명세를 고치는 순서`대로 문서를 맞춘 뒤 구현한다.
3. **살아 있는 것을 때린다.** 새로 생긴 표면을 실제로 호출한 출력이 증거다.
4. 적대적 리뷰를 받는다. 리뷰는 diff만 읽지 않고 라이브를 때린다.
   **BLOCKER**는 계약 위반(공통 봉투, 불변식, 비밀 유출). 나머지는 닛이다.
5. 지적은 **고장을 재현하는 테스트로 잠근다.** 고치고 끝내지 않는다.
6. BLOCKER를 고쳤으면 **재검토를 받고** 머지한다. 무시하고 머지하지 않는다.
7. 머지까지가 끝이다. PR을 열어 둔 상태는 종료가 아니다.

## PR 하나의 증거

주장이 아니라 **출력**이 남아야 한다.

```bash
node scripts/evidence.mjs
```

위 목록을 한 번에 돌리고 PR 본문에 붙일 블록을 낸다. **하나라도 못 돌리면 실패한다** —
손으로 따로 돌리면 빠뜨린 것을 아무도 알아채지 못한다(실제로 그렇게 여러 PR이 증거를 덜 싣고 머지됐다).

- `check-layout.mjs` — 문서 게이트. 무는지까지 보려면 `check-layout.test.mjs`
- `pytest -q` — 통과 개수와 **skip 개수를 함께**. 호스트에서는 DB 검사가 skip된다.
  **`skip 0`은 `5432`를 게시했다는 신호이지 더 나은 결과가 아니다**
- `docker compose --profile test run --rm test` — DB 검사까지 (D22)

여기에 더해 **새로 생긴 표면을 실제로 호출한 결과 하나**를 손으로 붙인다. 그건 자동화하지 않는다 —
무엇이 새 표면인지는 사람이 안다.

**숫자는 PR 본문에만 적고 문서에는 적지 않는다.** 문서에 박은 개수는 검사가 늘 때마다 낡는다.
`check-layout`의 검사 10이 흔한 형태(`N passed`·`N skipped`·`skip 0`·`N종 통과`)를 잡는다.
**부분 문자열 목록이지 "낡은 수치"의 증명이 아니다** — 목록 밖 표현은 통과하므로 규칙 자체를 지킨다.

§9는 **v1의** 완료 조건이지 PR 하나의 완료 조건이 아니다.

## 테스트를 쓰는 방식

- **명세에 답이 있으면 테스트를 먼저 쓴다. 여기에는 불변식도 포함된다.**
  - `error()`의 `INTERNAL` 고정 — D21에 문장으로 있었는데 구현이 어겼다
  - `/openapi.json`이 살아남은 것과 빈 본문 307 — D12(웹 페이지 없음)와 D21(본문은 언제나 봉투)에서 나온다.
    `test_openapi_docs_are_off`가 `/docs`만 때린 것은 **불완전한 TDD**였지 도달 불가가 아니었다
  - 파서·새니타이저 같은 순수 로직 — `redact_dsn`의 libpq 대체 형식, Q 게이트 파서.
    게이트 파서는 **테스트 0개로 나갔고 결함이 3건 있었다**
- **테스트 먼저로 도달하지 못하는 것은 프레임워크·인프라의 우연한 기본값이다.**
  Starlette `Headers.get`이 첫 값만 보는 것, `compare_digest`의 latin-1/UTF-8 어긋남,
  healthcheck가 자기 D7 게이트에 막히는 것. 라이브 고장 주입으로 찾고 그 자리에서 잠근다.
- 검사를 만들면 통과만 보지 말고 **고장을 주입해 실제로 실패하는지** 확인하고, **그 주입을 커밋한다.**
  주입이 저장소에 없으면 검사가 살아 있는지 아무도 재현할 수 없다.
  `scripts/check-layout.test.mjs`가 그 자리다 — 저장소를 임시로 복사해 복사본에 주입하므로
  작업 트리를 더럽히지 않는다. 검사를 늘리면 여기에 케이스를 더한다.
  **메타 케이스도 함께 더한다** — 그 검사를 껐을 때 주입이 통과하는지 본다.
  그러지 않으면 케이스가 다른 검사에 걸려 "엉뚱한 이유로" 붉은불이 켜져도 모른다.
- **문구를 바꿔 고쳤으면 옛 문구를 `check-layout.mjs`의 `RETIRED`에 등록한다.**
  정본만 고치고 사본에 옛 문장을 남기는 것이 재발 3위 부류였다.

> 위 분류는 2026-08-31 감사에서 한 번 틀렸다. `/openapi.json`과 307을 *명세에 문장이 없던 것*으로
> 적었는데 D12·D21이 그 문장이다. 측정하지 않은 추론을 규약에 적지 않는다.

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
         CONFLICT 409 (D32: concurrent ingest on the same project), INTERNAL 500
DECIDED: body is always the {ok, data|error} envelope; INTERNAL message is a fixed string
```
