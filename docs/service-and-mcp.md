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

에러 코드: `VALIDATION` | `NOT_FOUND` | `CONFLICT` | `INTERNAL`

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
