---
title: Sillok Service와 MCP 계약
doc_type: api
status: current
module: null
---

# Sillok Service와 MCP 계약

상위: [plan.md](plan.md) · [README](../README.md)

> 이 파일은 엔드포인트·도구·요청/응답 JSON의 정본이다.
> 주소·인증·`top_k`·색인 경로의 정본은 [adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md)다.
> 미해결 계약 구멍은 [open-questions.md](open-questions.md) C절.

Knowledge Service가 DB의 유일한 문이다.  
MCP와 사람용 UI는 이 HTTP API만 호출한다.

> **불변식의 단위는 Service 함수이지 HTTP가 아니다 (D19).**
> 위 두 번째 줄은 MCP와 사람용 UI에 대한 규칙이다. CLI는 둘 중 어느 쪽도 아니며,
> `sillok ingest`는 같은 앱에서 Service 함수를 인프로세스로 호출한다.
> **금지되는 것은 CLI가 자기 SQL 계층을 갖는 것이다.**
>
> **D6과 혼동하지 않는다.** D6은 프로세스 동일성이다 — MCP는 `serve`와 같은 프로세스의 다른 앞면이다.
> `ingest`는 **별도 프로세스이고 같은 코드의 함수를 쓴다.** 공유되는 것은 데이터 접근 계층 하나뿐이지 프로세스가 아니다.
> `serve`와 `ingest`가 각자 DB 세션을 여는 문제는 [open-questions.md](open-questions.md) Q10으로 남는다.

로컬 Compose 기본: Service `http://127.0.0.1:8080`.  
인증: 로컬 무인증. HTTP를 외부에 열 때만 `Authorization: Bearer <token>`.

`get_file`은 설정된 workspace 경로의 파일을 읽는다.  
`save_doc`은 Git에 쓰지 않고 제안 본문/diff만 반환한다.  
색인 CLI: `sillok ingest`. 대상은 `docs/**`, 루트 `README*`, `adr/**`.  
MCP는 stdio와 Streamable HTTP를 같은 앱에서 제공한다.

## HTTP API

공통 응답:

```json
{ "ok": true, "data": {} }
{ "ok": false, "error": { "code": "VALIDATION", "message": "result required" } }
```

에러 코드: `VALIDATION` | `UNAUTHORIZED` | `NOT_FOUND` | `CONFLICT` | `INTERNAL`

**성공이든 실패든 본문은 언제나 위 봉투다.** 상태 매핑의 정본은 [adr/0001](../adr/0001-v1-stack-decisions.md) §D21.

| 코드 | HTTP | v1에서 언제 |
|---|---|---|
| `VALIDATION` | 422 | 요청 모델 실패, `save_event` 필수 필드 누락 |
| `UNAUTHORIZED` | 401 | D7 게이트 — `SILLOK_BEARER_TOKEN`이 설정됐는데 헤더가 없거나 다를 때 |
| `NOT_FOUND` | 404 | 없는 경로. `get_event`의 404 대 빈 결과는 **Q12로 미결** |
| `CONFLICT` | 409 | **예약. v1은 발신하지 않는다** — 발신 조건이 없다 |
| `INTERNAL` | 500 | 서버 결함. `message`는 고정 문자열 `internal error` |

`INTERNAL`에 예외 문구·트레이스백·경로를 싣지 않는다. DSN·`SILLOK_BEARER_TOKEN`·`OPENAI_API_KEY`가 새는 길이다.
`에러 메시지를 그대로 돌려준다`는 규칙은 `VALIDATION`에만 해당한다.

FastAPI 기본 응답(`{"detail": ...}`)은 이 계약 위반이다. 요청 검증 실패와 없는 경로 둘 다 핸들러로 덮는다.
빈 검색 결과는 오류가 아니다 — 200에 `{ "results": [] }`.

### 검색

`POST /v1/search/docs`

```json
{
  "project": "myproj",
  "query": "인증 만료 정책",
  "module": null,
  "doc_type": null,
  "status": "current",
  "top_k": 8
}
```

응답 `data.results[]`: `path`, `heading_path`, `excerpt`, `commit_sha`, `status`, `score`

`POST /v1/search/events`

```json
{
  "project": "myproj",
  "query": "배포 후 타임아웃",
  "kind": "failure",
  "module": null,
  "since": "2026-01-01T00:00:00Z",
  "until": null,
  "top_k": 8
}
```

응답 `data.results[]`: `id`, `title`, `summary`, `kind`, `result`, `module`, `occurred_at`, `score`

### 단건

- `GET /v1/docs?project=&path=` — 인덱스 메타 + 원문이 있으면 excerpt 또는 저장본 없음(Git을 열라는 힌트)
- `GET /v1/events/{id}`
- `GET /v1/files?project=&path=` — 설정된 workspace에서 원문 읽기 (D4 확정)

### 저장

`POST /v1/events`

[skills/sillok-storage/SKILL.md](skills/sillok-storage/SKILL.md)의 필수 6개 필드. 하나라도 없으면 `VALIDATION`.

`POST /v1/docs/proposals`

현재 진실 패치 제안. v1 기본 가정: Git에 직접 쓰지 않고 diff/본문을 반환한다.

### 통계

`GET /v1/stats/events?project=&module=&since=`

```json
{
  "total": 12,
  "by_kind": { "failure": 7, "success": 4, "incident": 1 },
  "by_result": { "failure": 6, "success": 5, "partial": 1 },
  "by_module": { "auth": 4, "billing": 2 },
  "repeat_causes": [{ "root_cause": "pool exhausted", "count": 3 }]
}
```

벡터를 쓰지 않는다.

### 상태

`GET /v1/status?project=`

문서 수, 청크 수, 이벤트 수, 마지막 ingest, 최근 hit_count=0 질의 수.

### 색인

`POST /v1/ingest`

변경 파일 목록 또는 repo 경로. 해시 비교 후 변경분만 임베딩.

**운영자 진입점은 이 엔드포인트가 아니라 CLI `sillok ingest`다 (D8·D20).**
여기는 이미 떠 있는 api에 같은 Service 함수를 태우는 HTTP 얼굴이고, MCP에는 노출하지 않는다.
[plan.md](plan.md) §5의 MCP 표에 없는 것은 누락이 아니라 의도다.
나중에 n8n webhook을 붙인다면(ADR `나중에 바꿔도 되는 것`) 이 얼굴을 쓴다.

## MCP 도구

도구 이름을 바꾸지 않는다. 설명이 길면 모델이 도구를 안 고른다. 설명은 짧게.

| 도구 | 대응 API | 메모 |
|---|---|---|
| `search_docs` | `POST /v1/search/docs` | top_k 기본 8, 최대 12 |
| `search_events` | `POST /v1/search/events` | 필터 권장 |
| `get_event` | `GET /v1/events/{id}` | |
| `get_file` | `GET /v1/files` | 부족할 때만 |
| `save_event` | `POST /v1/events` | 필드 없으면 에러 메시지를 그대로 돌려줌 |
| `save_doc` | `POST /v1/docs/proposals` | v1은 제안 |
| `event_stats` | `GET /v1/stats/events` | |
| `kb_status` | `GET /v1/status` | |

노출하지 않음: 임의 SQL, 대량 export, 문서 전체 덤프, 이벤트 일괄 삭제.

## 반환 크기

- excerpt / summary: 800자 절단 가능. 원문은 `get_file` / `get_event`.
- 목록은 8개가 기본.
- 빈 결과는 `{ "results": [] }`. 모델이 채울 문장을 넣지 않음.

## 프롬프트에 넣을 한 줄 (클라이언트)

근거가 빈 배열이면 “Sillok에 없음”이라고 하고 추측하지 말 것.  
`status: current` 문서만 현재 규칙으로 쓴다.  
통계 숫자는 `event_stats`만 믿는다.

## UI — v1 비범위

D12에 따라 v1에서 웹 페이지를 만들지 않는다. 아래는 v1 이후 UI가 생길 때의 최소 요건이며,
v1에서는 같은 데이터를 `GET /v1/status`와 검색 API가 JSON으로 돌려주는 것으로 갈음한다.

최소:

- 프로젝트 선택
- 문서 목록 (path, status, indexed_at)
- 이벤트 타임라인
- 건수 카드 (event_stats)
- 검색 시험창 (search_docs / search_events와 동일 API)

별도 위키 엔진을 만들지 않는다.
