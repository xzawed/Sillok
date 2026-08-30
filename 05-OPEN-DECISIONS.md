# Sillok — 결정 기록

상태: **2026-08-30 확정** (묶음 추천 수용)  
구현 에이전트는 이 값을 전제로 한다. 바꾸려면 이 파일을 먼저 고친다.

| ID | 결정 | 내용 |
|---|---|---|
| D1 | **A** | Python FastAPI + MCP Python SDK |
| D2 | **A** | OpenAI `text-embedding-3-small`, 차원 **1536**. 키 없으면 키워드만 (`embedding` NULL) |
| D3 | **A** | `save_doc`는 제안만. Git 직접 커밋 없음 |
| D4 | **A** | `get_file`은 설정된 workspace / 로컬 클론 경로를 읽음 |
| D5 | **A** | `project` 필수. 멀티 프로젝트 |
| D6 | **C** | MCP stdio + Streamable HTTP. 같은 Service |
| D7 | **A** (노출 시 **B**) | 로컬 무인증. HTTP를 외부에 열면 공유 토큰 헤더 |
| D8 | **A** | 색인은 CLI `sillok ingest` |
| D9 | **B** | 색인 경로: `docs/**` + 루트 `README*` + `adr/**` |
| D10 | **A** | 이벤트 필수 필드 없으면 거절 |
| D11 | **A** | 반복 원인은 `repeat_causes` 통계만. 자동 승격 없음 |
| D12 | **A** | 사람용은 JSON 현황 API. 웹 UI는 v1 이후 |
| D13 | **A** | 로컬 Docker Compose (Postgres + Service + MCP) |
| D14 | **C** | 본문 한·영 혼용. 검색 구성 `simple` |
| D15 | **A** | 비공개 개인 도구 |

## 구현에 고정되는 값

- `vector(1536)`
- 임베딩 모델 ID: `text-embedding-3-small`
- Git 쓰기는 proposal 응답만
- ingest 기본 include: `docs/`, `README.md`, `README.ko.md` 등 `README*`, `adr/`
- MCP: stdio 클라이언트 + HTTP 서버를 한 코드베이스에서

## 나중에 바꿔도 되는 것 (v1 비범위)

- D2를 Voyage / Gemini / Qwen3 / xAI로 교체 → 재색인
- D7을 토큰으로 상향
- D8에 n8n webhook 추가
- D12 작은 웹
- D13을 기존 Postgres에 붙이기
