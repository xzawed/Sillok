# Sillok — 구현용 문서 묶음

프로젝트 지식 원장.  
현재 진실은 Git, 성공·실패 이력은 PostgreSQL, AI는 MCP로 필요한 행만 읽고 쓴다.

이 폴더는 Claude와 Grok이 **같은 명세를 보고 구현**하기 위한 문서다.  
구현 코드가 아니라 계약이다. 코드가 문서와 어긋나면 문서를 먼저 고친다.

**양쪽 에이전트 시작점: [PLAN.md](PLAN.md)**  
나머지 파일은 PLAN이 가리키는 상세다.

## 읽을 순서

| 파일 | 용도 | 누가 읽나 |
|---|---|---|
| [PLAN.md](PLAN.md) | 공동 구현 기준 (이 파일부터) | Claude / Grok |
| [01-SPEC.md](01-SPEC.md) | 문제, 목표, 비목표, 세 층 | PLAN의 배경 |
| [02-STORAGE-RULES.md](02-STORAGE-RULES.md) | Git vs DB 분류. Skill 본문 | 저장 경로를 만지는 AI |
| [03-DATA-MODEL.md](03-DATA-MODEL.md) | 테이블, 인덱스, 제약 | Service / DB 담당 |
| [04-SERVICE-AND-MCP.md](04-SERVICE-AND-MCP.md) | HTTP API와 MCP 도구 계약 | Service / MCP 담당 |
| [05-OPEN-DECISIONS.md](05-OPEN-DECISIONS.md) | D1–D15 확정 기록 | 구현 전제 |
| [AGENTS.md](AGENTS.md) | Claude / Grok 협업 규칙 | 양쪽 에이전트 |

사람용 요약본: `Sillok-설계서.docx`

## 한 문장

Sillok은 RAG 플랫폼이 아니라, 위키가 로그가 되지 않게 저장 위치를 강제하는 지식 원장이다.

## 상태

- 이름: Sillok (실록) — 확정
- SCAManager 연동: 비범위
- D1–D15: 2026-08-30 묶음 추천 수용으로 확정 → `05-OPEN-DECISIONS.md`
- 스택: Python FastAPI, OpenAI text-embedding-3-small (1536), Compose, MCP stdio+HTTP
