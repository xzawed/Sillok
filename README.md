---
title: Sillok
doc_type: readme
status: current
module: null
---

# Sillok

Git에는 **현재 진실**만. Postgres에는 **사건 원장**과 문서 인덱스만.
AI는 MCP로 필요한 행 몇 개만 읽는다.

Sillok은 RAG 플랫폼이 아니라, 위키가 로그가 되지 않게 **저장 위치를 강제하는 지식 원장**이다.

이 저장소에는 아직 코드가 없다. **문서가 곧 구현 계약이다.**
동작이 문서와 어긋나면 코드가 틀린 것으로 본다.

## 시작점

구현 에이전트는 **[docs/plan.md](docs/plan.md)** 부터 읽는다. 나머지 문서는 PLAN이 가리킨다.
협업 규칙은 [AGENTS.md](AGENTS.md).

## 문서 지도

| 경로 | 역할 | `doc_type` | 이 문서가 **정본**으로 소유하는 것 |
|---|---|---|---|
| [docs/plan.md](docs/plan.md) | 구현 계약. 진입 문서 | `other` | 작업 순서, v1 완료 조건, 금지 목록 |
| [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md) | 확정 결정 D1–D15 | `adr` | **모든 확정값** (스택, 차원, 경로, 인증, 범위) |
| [docs/spec.md](docs/spec.md) | 문제·목표·비목표·세 층 | `other` | 세 층 구조, 비목표, 은유 |
| [docs/data-model.md](docs/data-model.md) | 테이블·인덱스·제약 | `schema` | DDL, 컬럼 enum 값 |
| [docs/service-and-mcp.md](docs/service-and-mcp.md) | HTTP API와 MCP 도구 계약 | `api` | 엔드포인트, 도구 8개, 요청·응답 JSON |
| [docs/skills/sillok-storage/SKILL.md](docs/skills/sillok-storage/SKILL.md) | 저장 위치 규칙 (타 프로젝트 배포용) | `other` | 이벤트 필수 필드, 결정 트리, 거절 규칙 |
| [docs/open-questions.md](docs/open-questions.md) | 구현 전 답해야 할 공백 | `other` | 미해결 질문 Q1–Q23 |
| [AGENTS.md](AGENTS.md) | 에이전트 협업 규약 | *(색인 안 함)* | 역할 분담, 금지 행위 |
| [CLAUDE.md](CLAUDE.md) | Claude Code 전용 컨텍스트 | *(색인 안 함)* | 없음 — 전부 미러 |

`AGENTS.md`와 `CLAUDE.md`는 **에이전트 도구 설정**이지 프로젝트 지식이 아니다.
그래서 의도적으로 색인 경로(`docs/**`, 루트 `README*`, `adr/**`) 밖에 둔다.

## 우선순위

```text
docs/plan.md = adr/0001-v1-stack-decisions.md   (이 둘이 이긴다)
        >  docs/spec.md, docs/data-model.md, docs/service-and-mcp.md, docs/skills/**
```

계약을 바꾸려면 `docs/plan.md`와 `adr/0001-v1-stack-decisions.md`를 **먼저** 고치고 나서 하위 문서와 구현을 맞춘다.

## 정본 표기 규칙

같은 값이 여러 문서에 나오면, 사본에는 반드시 정본 위치를 적는다.

> 정본: [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md) — 값이 다르면 정본이 이긴다.

사본을 지우지 않는 이유는 진입 문서와 도구 컨텍스트에서 값이 바로 보여야 하기 때문이다.
대신 **어긋났을 때 누가 이기는지가 항상 명시**되어야 한다.

## 자기 색인

Sillok의 색인 대상은 `docs/**`, 루트 `README*`, `adr/**`다 (D9).
이 저장소의 배치는 그 규칙을 그대로 따른다 — 즉 **Sillok의 첫 ingest 스모크 테스트는 이 저장소 자신을 대상으로 돌릴 수 있다.**

## 상태

- 이름: Sillok (실록) — 확정
- D1–D15: 2026-08-30 확정 → [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md)
- 스택: Python FastAPI, OpenAI `text-embedding-3-small` (1536), Docker Compose, MCP stdio + HTTP
- SCAManager 연동: 비범위
- 구현: 시작 전. 착수 전에 [docs/open-questions.md](docs/open-questions.md)를 먼저 처리한다.
