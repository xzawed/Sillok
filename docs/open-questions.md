---
title: 구현 전 미해결 공백
doc_type: other
status: current
module: null
---

# 구현 전 미해결 공백

상위: [plan.md](plan.md) · [README](../README.md)

2026-08-30 문서 전수 감사에서 확정된 **명세 공백**이다.
모순이 아니라 *아무 문서에도 답이 없는* 항목만 모았다. 확정된 모순은 이미 각 문서에서 고쳤다.

A–D절은 구현 **전에** 답해야 하는 것들이다. **E절은 구현이 시작된 뒤 드러난 공백**이라
제목의 `구현 전`에 들어맞지 않는다 — 그래도 Q 번호 체계를 쪼개지 않으려고 같은 파일에 둔다.

각 항목은 **결정이 필요하다.** 추측으로 채우지 않는다.
답이 정해지면 [adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md)에 D33 이후로 기록하고,
**이 항목은 지우지 말고 `해결 → Dnn` 으로 표시만 바꾼다.**
Q 번호는 다른 문서가 참조하는 식별자다. 지우거나 재사용하거나 순서를 바꾸지 않는다.
질문 본문도 고치지 않는다 — 전제가 틀린 채 닫힌 항목은 그 사실이 보여야 한다 (Q4가 그렇다).

> **A절은 D16–D20, Q11은 D21, Q26은 D22, Q16·Q18·Q21은 D23–D25로 마감됐다** (2026-08-31).
> **B절은 Q6·Q7·Q10이 D30–D32로, Q8·Q9가 D33–D34로 마감됐다** (2026-09-01).
> [plan.md](plan.md) §7 1–7단계를 이제 검증할 수 있다.
> 남은 것은 5단계 이후를 단계별로 막는다 — 아래 목록의 4단계 절은 해결됐어도 지우지 않는다 (D22) —
> 4단계 전에 Q16·Q18·Q21, 5단계 전에 Q6·Q7·Q10, 6단계 전에 Q8·Q9, 7단계 전에 Q12·Q15·Q19·Q20, 8단계 전에 Q17.

---

## A. 부트스트랩 — §9 첫 항목을 막는 것

**전부 해결됐다.** 아래 항목은 이력으로 남긴다.

**Q1. 환경변수 계약이 `OPENAI_API_KEY` 하나뿐이다.** — **해결 → D16**
DB 접속 문자열, 서비스 포트, workspace 경로, 외부 노출 시 Bearer 토큰의 변수 이름이 어디에도 없다.
→ `.env.example`이 필요하다.
→ 단일 DSN `DATABASE_URL` + `SILLOK_*` 4개 + `OPENAI_API_KEY`. [.env.example](../.env.example) 추가됨.
~~**Q20(project→workspace 매핑)은 닫히지 않았다**~~ — D16은 workspace 루트 하나의 이름만 정했고,
D37이 **그 하나로 충분하다**고 답했다. 매핑은 만들지 않는다.

**Q2. 마이그레이션 실행 수단이 없다.** — **해결 → D17**
[data-model.md](data-model.md)에 DDL은 있으나 `CREATE EXTENSION vector` / `pg_trgm` 문이 빠져 있고, 마이그레이션을 적용하는 도구·순서가 미정이다.
→ §9 `Compose로 DB가 뜬다`를 통과시킬 방법이 없다.
→ 버전 붙인 raw `.sql`을 `serve` 기동 시 bind 전에 멱등 적용. 빠져 있던 `CREATE EXTENSION` 두 줄은 [data-model.md](data-model.md)에 추가했다.

**Q3. 실행 환경이 미정이다.** Python 버전, 의존성 관리자(uv/poetry/pip), 테스트 러너, 스모크 실행 명령. — **해결 → D18**
→ §9 체크리스트 전체를 돌릴 수단이 없다.
→ CPython 3.12 · uv · pytest. **v1 판정 명령**은 [plan.md](plan.md) §9에 적었다 — 그 블록은 목표이고, 지금 돌릴 수 있는 줄은 일부다.
오늘의 증거 3종은 [AGENTS.md](../AGENTS.md) `PR 하나의 증거`가 소유한다.

**Q4. CLI 계약이 없다.** `sillok ingest` / `sillok serve`의 인자가 정의되지 않았고,
**ingest가 DB에 직접 붙는지 HTTP를 타는지**가 미정이다.
[service-and-mcp.md](service-and-mcp.md)의 `Service가 DB의 유일한 문` 불변식을 지키려면 HTTP여야 하지만, 명시된 곳이 없다.
— **해결 → D19. 단, 위 질문의 전제가 틀렸다.**
불변식이 요구하는 것은 *Service 함수가 유일한 문*이지 *모든 호출자가 HTTP를 타라*가 아니다.
`MCP와 사람용 UI는 HTTP만 호출한다`는 그 둘에 대한 규칙이고 CLI는 어느 쪽도 아니다.
따라서 제3의 답 — 같은 앱에서 인프로세스로 Service 함수 호출 — 이 채택됐다. 금지되는 것은 CLI가 자기 SQL을 갖는 것이다.

**Q5. `POST /v1/ingest`와 D8 `색인은 CLI`의 관계가 불명확하다.** — **해결 → D20**
[service-and-mcp.md](service-and-mcp.md)는 엔드포인트를 정의하는데 [plan.md](plan.md) §5 표에는 없다. 둘 중 무엇이 진입점인가.
→ **둘 중 틀린 쪽은 없다.** 운영자 진입점은 CLI이고, 엔드포인트는 같은 함수의 HTTP 얼굴이다.
§5 표에 없는 것은 의도이며 바로 다음 줄의 `MCP에 노출하지 않는 HTTP`가 그것을 명시하고 있었다.

## B. 색인·검색 결정성

**Q6. ingest가 결정론적으로 구현될 만큼 정의돼 있지 않다.** — **해결 → D30**
확장자 필터, 해시 알고리즘, `commit_sha` 출처, **삭제된 파일 처리**, 청크 경계 판정이 모두 미정.

**Q7. 임베딩 백필 경로가 없다.** — **해결 → D31**
키 없이 색인하면 `embedding`이 NULL이고 `content_hash`는 동일하다. 나중에 키를 넣어도 **변경 없음으로 판정되어 벡터가 영구히 비어 있다.**

**Q8. RRF·점수·중복 제거가 정의돼 있지 않다.** — **해결 → D33** [data-model.md](data-model.md)는 `가능하면 RRF로 합친다`고만 한다. `score`의 의미와 범위, 같은 문서의 여러 청크가 걸릴 때의 처리도 미정.

**Q9. `kb_events`에 `tsv` 컬럼과 GIN 인덱스가 없다.** — **해결 → D34**
`키 없으면 키워드만`이라는 전제가 **이벤트 검색에서는 성립하지 않는다.** 선언된 `pg_trgm`은 어느 설계에도 쓰이지 않는다.

**Q10. ingest의 트랜잭션 경계와 동시 실행 규칙이 없고, `kb_ingest_runs.status`의 값 집합이 정의되지 않았다.** — **해결 → D32**

## C. API 계약 구멍

**Q11. 에러 코드가 HTTP 상태코드에 매핑돼 있지 않다.** — **해결 → D21**
`CONFLICT`는 발생 조건조차 없다. FastAPI 기본 422 바디는 공통 `{ok,error}` 형식과 다르므로 처리 규칙이 필요하다.
→ 매핑 확정, FastAPI 기본 응답은 핸들러로 덮는다. **`CONFLICT`는 v1 발신자가 없어 예약으로 남긴다** — 쓰이는 것처럼 보이려고 발신 조건을 발명하지 않는다.
→ **D32가 첫 발신자를 만들었다.** 같은 project 의 동시 ingest 를 거절할 때다 —
발신 조건을 발명한 것이 아니라 D21이 Q10에 미뤄 둔 조건이 정해진 것이다.
→ D7 게이트를 표현할 코드가 없어 **`UNAUTHORIZED`를 추가**했다. 넷 중 어느 것도 맞지 않았고 억지로 끼우면 모델이 인자를 고쳐 재시도한다.
~~**Q12(404 대 빈 결과, 프로젝트 경계)는 닫히지 않았다**~~ — D21은 *없는 경로*의 404만 정했고,
D35가 나머지를 정했다: 지목한 조회는 404, 집합 질의는 빈 결과.

**Q12. 404 대 빈 결과 규칙이 없다.** `get_event`에 **프로젝트 경계 검사**가 없어 타 프로젝트 이벤트가 id만으로 읽힌다. — **해결 → D35**

**Q13. 페이지네이션 개념이 전 API에 없고, 문서 목록·이벤트 타임라인 엔드포인트가 없다.**
[service-and-mcp.md](service-and-mcp.md) `## UI — v1 비범위`는 그 화면을 v1 이후 최소 요건으로 든다.
v1의 JSON 현황만으로 목록·타임라인을 돌려주려면 엔드포인트와 페이지네이션을 먼저 정의해야 한다.

**Q14. 이벤트 수정 경로가 권고되는데 엔드포인트가 없다.**
[data-model.md](data-model.md)는 `v1은 삭제보다 payload/summary 수정`이라 하지만 수정 API가 정의된 적 없다.

**Q15. `save_doc` / `POST /v1/docs/proposals`에 요청·응답 계약이 전혀 없다.** — **해결 → D38**
또한 Skill의 거절 규칙 `Git 후보인데 본문에 날짜별 시도가 3건 이상`은 기계적으로 판정 불가능한 휴리스틱이다.

**Q16. `event_stats` 계약에 구멍이 있다.** — **해결 → D23**
`repeat_causes` 그룹 키가 Skill(`project+module+root_cause`)과 [service-and-mcp.md](service-and-mcp.md)(`root_cause`만)에서 다르다.
[data-model.md](data-model.md)가 근거로 든 `AVG(resolved_at - occurred_at)`에 대응하는 응답 필드가 없다.
→ **두 문서가 서로 다른 사실을 말한 것이지 모순이 아니었다.** Skill이 소유한 것은 *승격 식별자*이고
service-and-mcp가 소유한 것은 *응답 JSON*이다. 응답에 `module`을 넣어 둘이 같은 것을 세게 했다. `project`는 질의 파라미터라 항목에 없다.
→ `avg_resolution_seconds` 추가, `count >= 2`, `LIMIT 12`, `by_module`은 NULL 키 생략.

**Q17. MCP 도구의 입력 스키마, HTTP 마운트 경로, `Service와 동일 동작`의 판정 기준이 정의돼 있지 않다.**

## D. 무결성·보안

**Q18. `save_event` 멱등성 규칙이 없다.** 재시도 한 번이 `event_stats`와 `repeat_causes`를 조용히 오염시킨다.
— **해결 → D24. 단, 해가 해소된 것이 아니라 받아들여졌다.**
필수 필드로 만든 내용 해시로 접는 안은 **D11을 파괴한다** — 같은 `project+module+root_cause`의 반복이
바로 `repeat_causes`인데 합치면 탐지 대상이 사라진다. 그래서 append-only로 확정하고 재시도 부풀림을 문서에 적었다.
멱등이 필요해지면 클라이언트 `idempotency_key` + 부분 UNIQUE 인덱스가 다음 후보다.

**Q19. `get_file`에 경로 탈출 방어, 크기 상한, 허용 확장자 규칙이 없다.** workspace 밖 파일을 읽을 수 있다. — **해결 → D36**

**Q20. `project` → workspace 경로 매핑이 정의되지 않았다.** — **해결 → D37**
D4(설정된 workspace)와 D5(멀티 프로젝트)가 만나는 지점인데 설정 형식이 없어 **`get_file`을 구현할 수 없다.**

**Q21. `project` 식별자에 정규화·레지스트리가 없다.** 이벤트 필드 검증 세부(타임존 처리, `resolved_at >= occurred_at`, `title` 길이 상한, DDL에 CHECK 제약을 둘지)도 미정 — 현재 DDL에는 enum CHECK가 하나도 없고 검증은 서비스에만 있다.
— **해결 → D25**
레지스트리는 두지 않는다 — `project`→경로 매핑(Q20)이 열린 채라 지금 만들면 7단계를 4단계로 끌어온다.
정규화 규칙만 정했고, `title` 200자는 **새 사실**이라 Skill과 API 계약에 함께 적었다.
**DDL에 CHECK를 넣지 않는다** — CHECK 위반은 Postgres 예외가 되어 D21이 `INTERNAL 500`으로 접는데,
클라이언트 입력 문제가 서버 결함으로 보고되는 것이다. enum은 서비스에만 둔다.

**Q22. `kb_documents.repo` 컬럼의 의미가 정의되지 않았고**, 검색 결과와 단건 조회에 `repo`가 없어 다중 레포에서 결과가 모호해진다.

**Q23. `status` / `doc_type` / `module` / `title`을 무엇으로 채우는지 규칙이 없다.**
`search_docs`의 기본 필터 `status: "current"`가 이 값에 의존한다.
→ 2026-08-30 재배선(`bfc047c`)이 각 문서에 YAML front matter(`title`, `doc_type`, `status`, `module`)를 넣어 **이 저장소에 한해** 규칙을 세웠다. ingest가 front matter를 읽을지, 경로 규칙으로 추론할지는 여전히 미정.
→ **절반 마감 (D29).** 값을 *어디서* 얻는지는 정해졌다 — 루트 `README*`는 경로와 첫 H1에서 유도하고, `docs/**`·`adr/**`는 front matter를 읽는다.
**남은 것은 `status` 의 생애다** — 문서가 언제 `draft`·`superseded`·`stale` 이 되는지는 여전히 어느 문서에도 없다. 그래서 이 항목은 열려 있다.

---

## 문서 자체의 공백

**Q24. D1–D15의 선택지 정의가 유실됐다.**
[adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md)는 `A`/`B`/`C` 라벨을 15회 쓰는데, **그 선택지가 무엇이었는지는 어느 문서에도 없다.**
`D6=C`, `D9=B`, `D14=C`처럼 비-A 선택이 있으므로 최소 3개 안이 있었으나 복원 불가다.
ADR의 핵심 가치인 *왜 다른 안을 버렸는가*가 비어 있다.

**Q25. 배포된 Skill 사본이 낡았는지 탐지할 방법이 없다.**
[skills/sillok-storage/SKILL.md](skills/sillok-storage/SKILL.md)는 다른 레포로 물리 복제된다. 2026-08-30 재배선(`bfc047c`)이 원본 위치와 기준일을 헤더에 넣었으나, **사본이 자기가 낡았음을 스스로 확인할 경로는 없다.**
대상 레포는 이 저장소의 검증 밖이므로 `check-layout.mjs`도 닿지 않는다.
제안(미결정): Service가 Skill 본문을 서빙하고(`GET /v1/skill`) `kb_status` 응답에 `skill_version`을 포함시켜 사본이 대조하게 한다. 새 엔드포인트라 결정이 필요하다.

---

## E. 검증 경로

**Q26. 커밋된 구성에서 DB 검사를 돌릴 방법이 없다.** — **해결 → D22**
`tests/test_migrations.py`의 19개는 호스트에서 `5432`에 닿아야 도는데 **D16이 그 포트를 게시하지 않는다.**
컨테이너 안에서도 못 돈다 — 이미지가 `tests`를 제외하고(`.dockerignore`) `--no-dev`로 설치해 `pytest`가 없다.
결과: 커밋된 구성에서는 DB 검사가 전부 skip되고, `skip 0`은 D16을 어긴 상태에서만 나온다.
(발견 당시 수치는 `71 passed, 19 skipped` 대 `90 passed`였다. 개수는 검사가 늘면 낡으므로 이력으로만 적는다.)

> 2026-08-31 감사에서 발견. PR #5·#6·#7이 `skip 0`을 머지 근거의 머리줄로 썼다.
> (#5 본문은 다른 대목에서 `DB 검사 13건만 skip`을 적었으므로 전제를 완전히 감춘 것은 아니다.
> 문제는 머지 판정에 쓰인 숫자가 커밋된 구성의 것이 아니었다는 점이다.)

후보: (a) 내부 네트워크 전용 compose `test` 서비스(호스트 포트 없음, dev 의존성 포함) —
D13 `두 개`와 부딪히는지 판단 필요. (b) skip을 그대로 두고 보고에서 항상 드러낸다.
(c) 운영 이미지에 테스트를 넣는다 — 런타임에 테스트 러너를 싣게 되므로 권하지 않는다.

→ **(a)로 확정 (D22).** `profiles: ["test"]`가 붙어 기본 `up`에 나타나지 않으므로 D13의 `두 개`
(기본 `up`의 제품 스택)를 어기지 않는다. `docker compose --profile test run --rm test`.
**호스트의 `uv run pytest -q`는 그대로 skip이 나오고 그것이 정상이다** — 보고에서 skip을 빼지 않는다.
실측(당시): `db PORTS: 5432/tcp`(미게시) 상태에서 `--profile test run`이 skip 없이 전부 통과했다.
