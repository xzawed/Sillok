# Sillok — Agent 협업 규칙

Claude와 Grok이 같은 저장소를 만질 때 따른다.  
세션 시작 시 `PLAN.md`를 먼저 읽는다.

## 역할 나누기 (권장)

- **Grok**: 명세 해석, 스키마, API 계약, 분류 규칙, 리뷰, 경계 확인
- **Claude**: 서비스/MCP 구현, 테스트, 리팩터
- 어느 쪽이든 문서를 바꾸면 다른 쪽에 변경 요약을 남긴다.

역할은 권장이다. 도구가 바뀌어도 이 파일의 규칙은 유지한다.

## 하지 말 것

- `05-OPEN-DECISIONS.md`의 확정 값을 뒤집지 않는다. 바꾸려면 그 파일을 먼저 수정한다.
- Git 문서 폴더에 이벤트 이력을 append하지 않는다.
- MCP에서 임의 SQL을 노출하지 않는다.
- 검색 결과 없이 모델이 DB 내용을 안다고 가정하는 기능을 만들지 않는다.
- SCAManager, 전사 검색, 공개 라이브러리 문서를 범위에 넣지 않는다.

## 할 것

- 식별자(테이블, 도구, 필드)는 영어. 설명 문장은 한국어 가능.
- 저장은 `save_doc` / `save_event`만.
- 검색 기본 `top_k`는 8 이하.
- 통계는 SQL 집계. 통계 질문에 벡터 검색을 쓰지 않는다.
- API와 MCP는 같은 Service 함수를 탄다.

## 문서 우선

동작이 명세와 다르면 코드가 틀린 것으로 본다.  
명세를 바꿔야 하면 `01`~`04`를 먼저 고치고 구현한다.

## 확정 전제 (2026-08-30)

```text
DECIDED: Python FastAPI
DECIDED: embedding = text-embedding-3-small (1536); no key → keyword only
DECIDED: save_doc = proposal only
DECIDED: get_file = workspace path
DECIDED: MCP = stdio + HTTP
DECIDED: ingest CLI; docs + README* + adr
```
