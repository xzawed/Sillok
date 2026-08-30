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

각 항목은 **결정이 필요하다.** 추측으로 채우지 않는다.
답이 정해지면 [adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md)에 D16 이후로 기록하고,
**이 항목은 지우지 말고 `해결 → Dnn` 으로 표시만 바꾼다.**
Q 번호는 다른 문서가 참조하는 식별자다. 지우거나 재사용하거나 순서를 바꾸지 않는다.

> [plan.md](plan.md) §9 완료 조건 중 여러 항목이 아래 공백 때문에 **현재 판정 불가**다.

---

## A. 부트스트랩 — §9 첫 항목을 막는 것

**Q1. 환경변수 계약이 `OPENAI_API_KEY` 하나뿐이다.**
DB 접속 문자열, 서비스 포트, workspace 경로, 외부 노출 시 Bearer 토큰의 변수 이름이 어디에도 없다.
→ `.env.example`이 필요하다.

**Q2. 마이그레이션 실행 수단이 없다.**
[data-model.md](data-model.md)에 DDL은 있으나 `CREATE EXTENSION vector` / `pg_trgm` 문이 빠져 있고, 마이그레이션을 적용하는 도구·순서가 미정이다.
→ §9 `Compose로 DB가 뜬다`를 통과시킬 방법이 없다.

**Q3. 실행 환경이 미정이다.** Python 버전, 의존성 관리자(uv/poetry/pip), 테스트 러너, 스모크 실행 명령.
→ §9 체크리스트 전체를 돌릴 수단이 없다.

**Q4. CLI 계약이 없다.** `sillok ingest` / `sillok serve`의 인자가 정의되지 않았고,
**ingest가 DB에 직접 붙는지 HTTP를 타는지**가 미정이다.
[service-and-mcp.md](service-and-mcp.md)의 `Service가 DB의 유일한 문` 불변식을 지키려면 HTTP여야 하지만, 명시된 곳이 없다.

**Q5. `POST /v1/ingest`와 D8 `색인은 CLI`의 관계가 불명확하다.**
[service-and-mcp.md](service-and-mcp.md)는 엔드포인트를 정의하는데 [plan.md](plan.md) §5 표에는 없다. 둘 중 무엇이 진입점인가.

## B. 색인·검색 결정성

**Q6. ingest가 결정론적으로 구현될 만큼 정의돼 있지 않다.**
확장자 필터, 해시 알고리즘, `commit_sha` 출처, **삭제된 파일 처리**, 청크 경계 판정이 모두 미정.

**Q7. 임베딩 백필 경로가 없다.**
키 없이 색인하면 `embedding`이 NULL이고 `content_hash`는 동일하다. 나중에 키를 넣어도 **변경 없음으로 판정되어 벡터가 영구히 비어 있다.**

**Q8. RRF·점수·중복 제거가 정의돼 있지 않다.** [data-model.md](data-model.md)는 `가능하면 RRF로 합친다`고만 한다. `score`의 의미와 범위, 같은 문서의 여러 청크가 걸릴 때의 처리도 미정.

**Q9. `kb_events`에 `tsv` 컬럼과 GIN 인덱스가 없다.**
`키 없으면 키워드만`이라는 전제가 **이벤트 검색에서는 성립하지 않는다.** 선언된 `pg_trgm`은 어느 설계에도 쓰이지 않는다.

**Q10. ingest의 트랜잭션 경계와 동시 실행 규칙이 없고, `kb_ingest_runs.status`의 값 집합이 정의되지 않았다.**

## C. API 계약 구멍

**Q11. 에러 코드가 HTTP 상태코드에 매핑돼 있지 않다.**
`CONFLICT`는 발생 조건조차 없다. FastAPI 기본 422 바디는 공통 `{ok,error}` 형식과 다르므로 처리 규칙이 필요하다.

**Q12. 404 대 빈 결과 규칙이 없다.** `get_event`에 **프로젝트 경계 검사**가 없어 타 프로젝트 이벤트가 id만으로 읽힌다.

**Q13. 페이지네이션 개념이 전 API에 없고, 문서 목록·이벤트 타임라인 엔드포인트가 없다.**
[service-and-mcp.md](service-and-mcp.md) `## UI — v1 비범위`는 그 화면을 v1 이후 최소 요건으로 든다.
v1의 JSON 현황만으로 목록·타임라인을 돌려주려면 엔드포인트와 페이지네이션을 먼저 정의해야 한다.

**Q14. 이벤트 수정 경로가 권고되는데 엔드포인트가 없다.**
[data-model.md](data-model.md)는 `v1은 삭제보다 payload/summary 수정`이라 하지만 수정 API가 정의된 적 없다.

**Q15. `save_doc` / `POST /v1/docs/proposals`에 요청·응답 계약이 전혀 없다.**
또한 Skill의 거절 규칙 `Git 후보인데 본문에 날짜별 시도가 3건 이상`은 기계적으로 판정 불가능한 휴리스틱이다.

**Q16. `event_stats` 계약에 구멍이 있다.**
`repeat_causes` 그룹 키가 Skill(`project+module+root_cause`)과 [service-and-mcp.md](service-and-mcp.md)(`root_cause`만)에서 다르다.
[data-model.md](data-model.md)가 근거로 든 `AVG(resolved_at - occurred_at)`에 대응하는 응답 필드가 없다.

**Q17. MCP 도구의 입력 스키마, HTTP 마운트 경로, `Service와 동일 동작`의 판정 기준이 정의돼 있지 않다.**

## D. 무결성·보안

**Q18. `save_event` 멱등성 규칙이 없다.** 재시도 한 번이 `event_stats`와 `repeat_causes`를 조용히 오염시킨다.

**Q19. `get_file`에 경로 탈출 방어, 크기 상한, 허용 확장자 규칙이 없다.** workspace 밖 파일을 읽을 수 있다.

**Q20. `project` → workspace 경로 매핑이 정의되지 않았다.**
D4(설정된 workspace)와 D5(멀티 프로젝트)가 만나는 지점인데 설정 형식이 없어 **`get_file`을 구현할 수 없다.**

**Q21. `project` 식별자에 정규화·레지스트리가 없다.** 이벤트 필드 검증 세부(타임존 처리, `resolved_at >= occurred_at`, `title` 길이 상한, DDL에 CHECK 제약을 둘지)도 미정 — 현재 DDL에는 enum CHECK가 하나도 없고 검증은 서비스에만 있다.

**Q22. `kb_documents.repo` 컬럼의 의미가 정의되지 않았고**, 검색 결과와 단건 조회에 `repo`가 없어 다중 레포에서 결과가 모호해진다.

**Q23. `status` / `doc_type` / `module` / `title`을 무엇으로 채우는지 규칙이 없다.**
`search_docs`의 기본 필터 `status: "current"`가 이 값에 의존한다.
→ 이 PR은 각 문서에 YAML front matter(`title`, `doc_type`, `status`, `module`)를 넣어 **이 저장소에 한해** 규칙을 세웠다. ingest가 front matter를 읽을지, 경로 규칙으로 추론할지는 여전히 미정.

---

## 문서 자체의 공백

**Q24. D1–D15의 선택지 정의가 유실됐다.**
[adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md)는 `A`/`B`/`C` 라벨을 15회 쓰는데, **그 선택지가 무엇이었는지는 어느 문서에도 없다.**
`D6=C`, `D9=B`, `D14=C`처럼 비-A 선택이 있으므로 최소 3개 안이 있었으나 복원 불가다.
ADR의 핵심 가치인 *왜 다른 안을 버렸는가*가 비어 있다.

**Q25. 배포된 Skill 사본이 낡았는지 탐지할 방법이 없다.**
[skills/sillok-storage/SKILL.md](skills/sillok-storage/SKILL.md)는 다른 레포로 물리 복제된다. 이 PR에서 원본 위치와 기준일을 헤더에 넣었으나, **사본이 자기가 낡았음을 스스로 확인할 경로는 없다.**
대상 레포는 이 저장소의 검증 밖이므로 `check-layout.mjs`도 닿지 않는다.
제안(미결정): Service가 Skill 본문을 서빙하고(`GET /v1/skill`) `kb_status` 응답에 `skill_version`을 포함시켜 사본이 대조하게 한다. 새 엔드포인트라 결정이 필요하다.
