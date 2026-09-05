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
> 계약 구멍은 [open-questions.md](open-questions.md) C절에 있었고 전부 닫혔다 (D58–D64).

Knowledge Service가 DB의 유일한 문이다.  
MCP와 사람용 UI는 이 HTTP API만 호출한다.

> **불변식의 단위는 Service 함수이지 HTTP가 아니다 (D19).**
> 위 두 번째 줄은 MCP와 사람용 UI에 대한 규칙이다. CLI는 둘 중 어느 쪽도 아니며,
> `sillok ingest`는 같은 앱에서 Service 함수를 인프로세스로 호출한다.
> **금지되는 것은 CLI가 자기 SQL 계층을 갖는 것이다.**
>
> **D6과 혼동하지 않는다.** D6은 프로세스 동일성이다 — MCP는 `serve`와 같은 프로세스의 다른 앞면이다.
> `ingest`는 **별도 프로세스이고 같은 코드의 함수를 쓴다.** 공유되는 것은 데이터 접근 계층 하나뿐이지 프로세스가 아니다.
> `serve`와 `ingest`가 각자 DB 세션을 여는 문제는 **D32가 세션 advisory 락으로 닫았다** — 같은 project 는 직렬화된다.

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
| `NOT_FOUND` | 404 | **하나를 지목한 조회**에 답이 없을 때. 집합 질의는 404가 아니라 빈 결과다 (D35) |
| `CONFLICT` | 409 | 발신자가 **둘**이다. ① 같은 project 의 ingest 가 이미 돌고 있다 (D32) — `message`는 고정 문구 `ingest already running for this project`. ② `save_doc` 의 `base_hash` 가 현재 내용과 다르다 (D38). **①의 고정 문구를 ②에 쓰지 않는다** |
| `INTERNAL` | 500 | 서버 결함. `message`는 고정 문자열 `internal error` |

`INTERNAL`에 예외 문구·트레이스백·경로를 싣지 않는다. DSN·`SILLOK_BEARER_TOKEN`·`OPENAI_API_KEY`가 새는 길이다.
`에러 메시지를 그대로 돌려준다`는 규칙은 `VALIDATION`에만 해당한다.

**`INTERNAL`은 서버 결함 전용이다.** 클라이언트가 보낸 값 때문에 나는 실패는 `VALIDATION`이다 —
D25가 `resolved_at`에서 이미 이름 붙인 부류이고(`클라이언트 입력 문제인데 서버 결함으로 보고된다`),
자리마다가 아니라 **부류로** 막는다. 규칙의 정본은 [adr/0001](../adr/0001-v1-stack-decisions.md) §D21·§D25:

- **담을 수 없는 문자열**은 어느 필드에서든 `VALIDATION`이다 — NUL(Postgres `text`가 담지 못한다)과
  **짝 없는 서로게이트**(UTF-8로 인코딩되지 않는다). 문구는 `<field> must not contain NUL` ·
  `<field> must not contain unpaired surrogates`. 이모지처럼 **짝이 맞는** 값은 걸리지 않는다
- **UTC로 옮기면 표현 범위를 벗어나는 시각**도 `VALIDATION`이다 (`0001-01-01T00:00:00+23:59` 같은 값).
  ISO-8601로도 `datetime`으로도 멀쩡하고 옮기는 순간 깨지므로 오프셋 검사와는 다른 자리다

FastAPI 기본 응답(`{"detail": ...}`)은 이 계약 위반이다. 요청 검증 실패와 없는 경로 둘 다 핸들러로 덮는다.
표에 없는 상태(405 등)는 표 안의 코드로 접고 **그 코드의 상태**로 나간다 — 405는 `VALIDATION`/422가 된다.
`/openapi.json`과 슬래시 리다이렉트도 꺼야 한다 — 전자는 봉투 밖 200을, 후자는 핸들러보다 먼저 **빈 본문 307**을 낸다.

**봉투가 닿지 않는 한 곳:** HTTP 자체가 깨져 ASGI 앱에 도달하지 못한 요청은
서버(uvicorn)가 `text/plain`의 400으로 거절한다 — 예: `Content-Length: abc`, 잘린 요청 라인.
앱 밖이라 감쌀 수 없다. 클라이언트는 이 한 가지를 예외로 알고 있어야 한다.
(큰 헤더 자체는 여기 해당하지 않는다 — 64KB 헤더도 봉투로 응답하는 것을 실측했다.)
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

**`query`는 필수다.** 없거나 공백뿐이면 `VALIDATION`이다 (D33) — 문서 검색에는 질의 말고 신호가 없어
필터만으로는 "관련 문서 전부"가 되고 그것은 설계 위반이다. `search_events`는 반대다.

`heading_path`는 그 청크가 속한 절까지의 제목을 상위부터 ` > `로 이은 문자열이다 (D30).
첫 제목 앞 서두는 `null`이고, 레벨을 건너뛴 문서는 빈 칸을 채우지 않는다. 길이 상한은 없다.
`commit_sha`는 D30에 따라 **v1 내내 빈 문자열**이다 — 필드는 계약이고 값이 생기면 채우는 자리다.

`score`는 두 순위를 RRF(`k=60`)로 합친 값이고 **이 응답 안에서만** 비교된다 (D33).
질의 사이에도 project 사이에도 비교되지 않는다 — `results`가 이미 그 순서로 정렬돼 있다.
`excerpt`는 **키워드로 걸린 행에만** `tsv` 생성식과 같은 텍스트에 `ts_headline`을 걸어 만든다 (D33).
걸리지 않은 행 — 벡터 팔로만 올라온 행 — 은 `content` 의 앞머리를 쓴다.
매칭이 없으면 `ts_headline` 의 출력 길이가 통제되지 않기 때문이다.
둘 다 800자에서 자르고, 잘렸으면 끝에 `…` 한 글자가 붙는다.

**한 문서는 최대 2행을 차지하므로 `top_k`보다 적게 올 수 있다** (D33).
여덟을 요청해 다섯이 오는 것은 정상이고, 결과가 없어서가 아니다.

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

**`summary`는 `excerpt`와 같은 방식으로 자른다** (D58) — 799자 + `…` 로 합 800자다 (D33 §8).
같은 함수를 쓴다. 두 벌로 만들면 한쪽이 801자가 된다 —
원문은 `get_event`에서 본다. 자르지 않으면 한 응답이 `top_k` × 2000자가 된다.

**이벤트 검색은 키워드만이다** — v1은 이벤트를 임베딩하지 않는다 (D34).
키워드는 `title`·`summary`·`root_cause`·`resolution` 네 필드를 이은 `tsv`에 건다.
**뒤의 둘로 걸린 히트는 응답만 보고 설명할 수 없다** — 그 두 필드가 응답에 없다.
원문은 `get_event`(7단계)에서 본다.
**`query`는 선택이다.** 없거나 공백뿐이면 필터 집합이 그대로 결과이고 `score`는 `null`이다 (D33).
순서는 `occurred_at DESC, id DESC`다. `query`가 있으면 `ts_rank` 순이고 같은 두 키가 타이브레이크다.
`query`에 값이 있는데 렉심이 하나도 나오지 않으면 결과는 0건이다 — 필터 집합을 돌려주지 않는다.

### 단건

- `GET /v1/events/{id}?project=` — `project`는 **필수**다. 없으면 `VALIDATION`,
  행의 `project`와 다르면 `NOT_FOUND`다. 없는 id와 남의 id는 같은 응답이다 (D35)
- `GET /v1/files?project=&path=&offset=` — 설정된 workspace에서 원문 읽기 (D4 확정).
  **`kb_documents`에 행이 있는 경로만 연다** — 색인이 곧 허용 목록이다 (D36).
  응답은 파일이 아니라 **4000자 창**이고 `offset`·`next_offset`·`total_bytes`는 바이트다.
  `project`는 경로 성분이 아니다. 한 인스턴스는 한 workspace를 섬긴다 (D37)

`get_event`의 응답 `data`는 **그 행 자체다** (D39). 한 겹 싸지 않는다.

```json
{ "id": 1, "project": "sillok", "module": "auth", "kind": "failure",
  "title": "…", "summary": "…", "root_cause": "…", "resolution": "…",
  "result": "failure", "severity": "high",
  "occurred_at": "2026-08-31T09:00:00+00:00", "resolved_at": null,
  "source": "agent", "related_doc_path": null, "payload": {},
  "created_at": "2026-08-31T09:04:11+00:00", "created_by": "claude" }
```

`save_event`가 받는 필드에 `id`와 `created_at`을 더한 것이다.
`tsv`는 생성 컬럼이라, `embedding`은 v1이 채우지 않으므로(D34) 싣지 않는다.
시각은 ISO-8601 문자열이다.

`get_file`의 응답 `data`도 평평하다 (D36).

```json
{ "project": "sillok", "path": "docs/plan.md", "text": "…",
  "offset": 0, "next_offset": 3980, "total_bytes": 24117, "truncated": true }
```

`text`는 **원본 바이트를 그대로 푼 것이다** — 정규화하지 않는다 (D41).
창의 세 숫자가 바이트이므로 정규화하면 그 숫자가 무엇의 offset인지 사라진다.
`truncated`는 `next_offset < total_bytes`와 같은 뜻이고, `offset == total_bytes`는
오류가 아니라 끝이다(빈 `text`). 가장자리 표는 [adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md) D36이 소유한다.

### 저장

`POST /v1/events`

[skills/sillok-storage/SKILL.md](skills/sillok-storage/SKILL.md)의 필수 6개 필드. 하나라도 없으면 `VALIDATION`.

```json
{
  "project": "sillok",
  "kind": "failure",
  "title": "배포 후 커넥션 풀 고갈",
  "summary": "…",
  "occurred_at": "2026-08-31T09:00:00Z",
  "result": "failure",
  "module": "auth",
  "root_cause": "pool exhausted",
  "resolution": "…",
  "severity": "high",
  "resolved_at": "2026-08-31T10:00:00Z",
  "related_doc_path": "docs/runbook.md",
  "source": "agent",
  "payload": {},
  "created_by": "claude"
}
```

응답 `data`: `{ "id": 1 }`.

검증 세부는 D25다:

- `occurred_at`·`resolved_at`은 **오프셋이 있어야 한다**(`Z` 또는 `±HH:MM`). 오프셋 없는 값과 날짜만 있는 값은 `VALIDATION`
- `resolved_at < occurred_at`이면 `VALIDATION`
- `title` 200자 초과, `summary` 2000자 초과는 `VALIDATION`
- `project`는 앞뒤 공백을 제거한 뒤 비어 있거나 64자 초과이거나 공백·슬래시·**역슬래시**·NUL을
  포함하면 `VALIDATION`. 대소문자는 구분한다
- `source`를 생략하면 `agent`다
- **멱등이 아니다 (D24).** 같은 요청을 두 번 보내면 행이 둘 생긴다. 재시도는 통계를 부풀린다

`POST /v1/docs/proposals`

현재 진실 패치 제안. v1 기본 가정: Git에 직접 쓰지 않고 diff/본문을 반환한다 (D3·D38).

```json
{ "project": "sillok", "path": "docs/plan.md", "body": "…전체 새 본문…", "base_hash": "sha256:…" }
```

```json
{ "proposal": { "project": "sillok", "path": "docs/plan.md",
                "exists": true, "diff": "--- a/docs/plan.md\n+++ b/…", "body": "…" } }
```

- `path`는 `get_file`과 같은 판정을 받는다 — `kb_documents`에 행이 있어야 한다. 없으면 404
- `body`는 **문서 전체**다. 부분 패치를 받지 않는다
- `base_hash`가 있고 현재 내용 해시와 다르면 `CONFLICT` 409. 없으면 검사하지 않는다
- `base_hash`의 형식은 `sha256:` + **소문자 16진 64자**다 (D40).
  콜론 뒤는 D30 `content_hash`와 같은 문자열이고, 다른 형식은 `VALIDATION`이다 —
  접두사를 관대하게 벗기지 않는다
- **`save_doc`이 보는 현재 내용은 정규화한 텍스트다** (D41) — 선행 BOM 제거, CRLF와 홀로 있는 CR을 LF로.
  해시와 diff가 같은 텍스트를 본다. `body`도 같은 정규화를 거친다.
  `get_file`의 창이 원본 바이트인 것과 **일부러 다르다**
- `body`가 현재 내용과 같으면 `diff`는 빈 문자열이고 `exists: true`다. 오류가 아니다 (D38)
- 행은 있는데 파일이 없거나 열 수 없으면 `exists: false`, `diff`는 `/dev/null`에서의 추가다.
  그 상태에서 `base_hash`를 보냈으면 `CONFLICT`다 (D41)
- **새 문서 제안은 v1 비범위다** — 색인된 경로만 고칠 수 있다

### 통계

`GET /v1/stats/events?project=&module=&since=`

```json
{
  "total": 12,
  "by_kind": { "failure": 7, "success": 4, "incident": 1 },
  "by_result": { "failure": 6, "success": 5, "partial": 1 },
  "by_module": { "auth": 4, "billing": 2 },
  "by_module_omitted": 0,
  "repeat_causes": [{ "module": "auth", "root_cause": "pool exhausted", "count": 3 }],
  "avg_resolution_seconds": 3600
}
```

벡터를 쓰지 않는다. 규칙은 D23이다:

- `repeat_causes`는 `module`까지 묶는다 — Skill의 결정 트리가 `project+module+root_cause`로 세기 때문이다.
  `root_cause`만 묶으면 `?module=` 없이 부른 결과가 그 트리와 어긋난다. `project`는 질의 파라미터이므로 항목에 넣지 않는다
- `root_cause`가 없는 행은 제외. **2회 이상만**, `count` 내림차순 → `root_cause` 오름차순 → `module` 오름차순(NULL 은 마지막), **최대 12개**
- `module`이 없는 반복도 `"module": null`로 나간다. `by_module`이 NULL 키를 못 만드는 것과 다르다 — 여기는 필드다
- `by_module`은 `module`이 없는 행의 키를 넣지 않는다. 그 행들은 `total`에 남아 있으므로 `sum(by_module) <= total`이다. 0인 키도 넣지 않는다
- **`by_module`은 12개까지다** — `count` 내림 → 키 오름 (D58). 잘라 낸 키 수는 `by_module_omitted`로 나간다.
  그 숫자가 없으면 위 부등식이 *module 없는 행*과 *천장에 잘린 키* 두 가지를 한꺼번에 뜻하게 된다
- `avg_resolution_seconds`는 정수 초 또는 `null`. `resolved_at`이 없는 행은 평균에서 빠지고, 전부 미해결이면 `0`이 아니라 `null`이다

### 상태

`GET /v1/status?project=`

문서 수, 청크 수, 이벤트 수, 마지막 ingest, 최근 hit_count=0 질의 수, 벡터가 빈 청크 수.

```json
{
  "documents": 0,
  "chunks": 0,
  "events": 0,
  "last_ingest_at": null,
  "zero_hit_queries": 0,
  "chunks_without_embedding": 0
}
```

`last_ingest_at`은 `status`가 `ok`나 `partial`인 run 의 마지막 `finished_at`이다 (D32).
실패한 run 은 세지 않는다 — 세면 실패가 마지막 색인으로 보고된다.
성공한 run 이 한 번도 없는 project 는 `null`이다.
`zero_hit_queries`는 `kb_query_logs`의 `hit_count = 0` 건수다.
그 행을 쓰는 것은 검색 둘뿐이다 — **`kb_status` 자신은 쓰지 않는다** (D48).
현황을 묻는 질의가 자기가 보고할 수를 늘리면 그 지표가 자기 자신을 센다.
`chunks_without_embedding`은 `embedding IS NULL`인 청크 수다 (D31). 이벤트는 세지 않는다.
`chunks`와 같으면 키 없이 색인했다는 뜻이고, 0이 아닌데 키가 있으면 임베딩이 실패했다는 뜻이다 —
**둘을 이 응답만으로 구분하지 못한다.** 그 구분은 `kb_ingest_runs.status`·`error`가 한다.
**둘 다 빈 값이 정상이지 스텁이 아니다.**

모르는 `project`도 같은 0을 돌려준다. `NOT_FOUND`가 아니다 — 통계는 집합을 묻는 질의이고,
집합을 물으면 빈 집합이 답이다 (D35). 지목한 조회만 404를 낸다.
목록·타임라인은 v1 에 없다 (D58).

### 색인

`POST /v1/ingest`

요청은 CLI 인자와 같다 — `project` 필수, `workspace` 선택. **변경 파일 목록을 받지 않는다** (D30).
부분 목록에서는 "목록에 없다"가 *안 바뀌었다*인지 *사라졌다*인지 구분되지 않아 삭제 판정이 성립하지 않는다.

```json
{ "project": "sillok", "workspace": "/workspace" }
```

해시 비교 후 변경분만 다시 쪼개고, **벡터가 빈 청크를 임베딩한다** (D31).

```json
{ "ok": true, "data": {
  "run_id": 7, "project": "sillok", "status": "ok", "commit_sha": "",
  "files_seen": 10, "files_changed": 3, "files_deleted": 0, "chunks_upserted": 41,
  "chunks_embedded": 0, "chunks_pending": 151,
  "skipped": [{ "path": "docs/skills/sillok-storage/example.json", "reason": "not-md" }]
} }
```

`status`는 `ok` | `partial` | `failed` 중 하나다 (D32). **`partial`도 봉투는 `ok: true`다** —
요청이 처리되지 못한 것이 아니라 일부만 채워진 것이다. `status`를 안 읽는 클라이언트는 그것을 놓친다.
락을 얻지 못하면 본문 대신 `CONFLICT` 409다.
`skipped[]`의 `reason`은 `not-md`와 `symlink` 둘뿐이고 **응답에만 있다** — 컬럼으로 만들지 않는다.

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
**resources·prompts·notifications도 v1에 없다.** 도구 여덟뿐이다 (D42–D46).

### 표면과 전송 (D43 · D45)

| 전송 | 표면 |
|---|---|
| Streamable HTTP | `POST /mcp` 와 `POST /mcp/` — **같은 핸들러다.** 그 둘 말고는 없다 |
| stdio | CLI `sillok mcp`. bind 플래그를 갖지 않고 **stdout은 프로토콜 채널**이라 로그는 stderr로 간다 |

`/mcp` 아래의 본문은 JSON-RPC이고 **`{ok, data|error}` 봉투 계약 밖이다.** 봉투는 `/v1`의 본문 계약이다.
`/mcp/아무거나`는 MCP가 아니라 **이 앱의 404 봉투**로 돌아온다 — 마운트가 아니라 두 경로만 이었기 때문이다.
D7 게이트는 앱 미들웨어라 `/mcp`도 덮는다. stdio는 부모 프로세스의 파이프라 토큰이 없다.

### 인자 (D42)

**전부 선택이다.** 필수 판정은 Service가 하고, 그래야 `save_event`의 거절 문구가 모델에게 그대로 간다.
기본값을 여기 복제하지 않는다 — `top_k`를 비우면 Service가 D33의 기본값을 쓴다.

| 도구 | 인자 |
|---|---|
| `search_docs` | `project` · `query` · `top_k` · `doc_type` · `status` · `module` |
| `search_events` | `project` · `query` · `kind` · `module` · `since` · `until` · `top_k` |
| `get_event` | `event_id` · `project` |
| `get_file` | `project` · `path` · `offset` |
| `save_event` | 저장 계약의 필드 그대로 (`project`…`created_by`) |
| `save_doc` | `project` · `path` · `body` · `base_hash` |
| `event_stats` | `project` · `module` · `since` |
| `kb_status` | `project` |

**타입을 어긴 호출은 예외다.** 값의 타입이 스키마와 다르면 SDK가 도구를 부르기 전에 거절하고
그 본문은 봉투가 아니다. 전송 계층의 일이며, HTTP 얼굴에서 FastAPI가 `offset=x`를 먼저 거절하는 것과
같은 자리다 — 다른 점은 그쪽은 D21이 봉투로 덮고 이쪽은 덮지 못한다는 것뿐이다.

### 결과 (D44)

성공이든 실패든 **정상 결과**이고, 내용은 텍스트 한 덩이이며, 그 텍스트는
HTTP 얼굴이 돌려주는 **같은 봉투 JSON**이다. `structuredContent`를 함께 내보내지 않는다.
`VALIDATION`·`NOT_FOUND`·`CONFLICT`를 프로토콜 오류로 접지 않는다 — 셋을 나눠 둔 이유가 사라지고
모델이 같은 인자로 재시도한다. `INTERNAL`은 여기서도 고정 문구다.
`UNAUTHORIZED`는 HTTP 얼굴에만 있다.

**같은 인자면 두 얼굴의 봉투가 같아야 한다** (D46). 그 대조는 검사가 한다.

## 반환 크기

- excerpt / summary: **799자 + `…` 로 합 800자**다 (D33 §8). 원문은 `get_file` / `get_event`.
- `payload`: `json.dumps(payload, ensure_ascii=False, separators=(",", ":"))`가 2000자를 넘으면
  `VALIDATION` 이고 문구는 `payload longer than 2000` 이다 (D58).
  **구분자를 빼면 기본값이 공백을 넣어 같은 객체가 재는 사람에 따라 갈린다.**
  `summary`와 같은 숫자다 — `get_event`가 행을 통째로 돌려주므로 같은 이유가 걸린다.
  저장된 `jsonb`는 Postgres가 정규화하므로 이 수는 **입력을 재는 것**이다.
- `ingest`의 `skipped[]`에는 천장이 없다 (D58). MCP 도구가 아니고 운영자는 목록 전체를 원한다.
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
