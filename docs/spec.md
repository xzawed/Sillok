---
title: Sillok 명세
doc_type: other
status: current
module: null
---

# Sillok 명세

상위: [plan.md](plan.md) · [README](../README.md)

버전: 0.1 · 날짜: 2026-08-30 · 상태: 설계 확정

진행 상태는 여기서 관리하지 않는다 — [plan.md](plan.md) §7과 §9가 소유한다.

> 이 문서는 배경이다. 값이 [plan.md](plan.md)나
> [adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md)와 다르면 그 둘이 이긴다.

## 문제

프로젝트 문서와 성공·실패 이력이 레포 안에 같이 쌓이면:

1. 현재 규칙과 과거 사건이 한 파일에서 섞인다.
2. AI가 큰 문서를 통째로 읽어 토큰을 쓰고 중간을 놓친다.
3. 횟수·재발·기간 통계를 글에서 뽑을 수 없다.

## 한 문장 정의

현재 문서는 Git에, 성공·실패 이력은 Postgres에 두고, AI는 MCP로 필요한 행만 읽게 하여 위키를 로그로 만들지 않는 지식 원장.

## 목표

- Git에는 *지금 무엇이 맞는가*만 남긴다.
- Postgres에는 *언제 무엇이 일어났는가*와, Git 문서의 검색용 인덱스를 남긴다.
- AI는 DB를 통째로 보지 않는다. 도구가 반환한 조각만 본다.
- 사람은 프로젝트별 문서 목록과 통계를 JSON 현황 API로 본다. 웹 UI는 v1 이후다 (D12).
- 적재량이 늘어도 질의당 토큰은 거의 고정된다.

## 비목표 (v1)

- SCAManager 또는 다른 품질 게이트를 이 안에 넣지 않는다.
- 전사 검색(슬랙, 드라이브, 위키 SaaS)을 대체하지 않는다.
- 공개 라이브러리 문서 서비스(Context7류)를 대체하지 않는다.
- 지식그래프, LangGraph 멀티에이전트를 전제로 하지 않는다.
- AI가 Git에 문서를 직접 커밋하지 않는다. `save_doc`는 제안만.

## 은유

조선왕조실록.  
일기는 매일 쌓이고, 실록은 가려 남긴다.  
Sillok의 이벤트 테이블이 기사 원장이고, Git 문서가 편찬된 현재본이다.

## 세 층

```text
[1] PostgreSQL + pgvector
      kb_documents, kb_chunks, kb_events, 로그

[2] Knowledge Service
      검색 / 저장 / 통계 / 색인
      DB를 만지는 유일한 문

[3] 출구
      MCP  — AI의 손
      Skill — skills/sillok-storage/SKILL.md (판단 기준)
      UI    — v1은 JSON 현황 API (같은 Service)
```

**`DB를 만지는 유일한 문`의 단위는 [2]의 함수이지 HTTP가 아니다 (D19).**
MCP와 사람용 UI는 HTTP만 호출한다. CLI `sillok ingest`는 둘 중 어느 쪽도 아니고,
같은 앱의 [2] 함수를 인프로세스로 호출한다. 금지되는 것은 CLI가 자기 SQL 계층을 갖는 것이다.
계약 전문은 [service-and-mcp.md](service-and-mcp.md), 결정은 [adr/0001](../adr/0001-v1-stack-decisions.md) §D19.

Plugin은 특정 IDE 포장이다. v1에서 만들지 않는다.

n8n은 색인·배치 보조로 쓸 수 있으나 v1에서는 만들지 않는다. AI 질의의 본체가 아니다.

## 저장 원칙 (요약)

상세는 [skills/sillok-storage/SKILL.md](skills/sillok-storage/SKILL.md).

- 시간축이 있으면 이벤트, 현재형 규범이면 Git 문서.
- 과정과 횟수는 DB, 결론만 Git.
- 같은 원인이 반복되면 v1은 `repeat_causes` 통계와 승격 *제안*까지만 한다. Git 자동 승격 없음.

## 토큰 전제

적재 ≠ 활용.

- 한 질의에 모델이 보는 양은 top-k 청크 + 이벤트 요약이다.
- 통계 질문은 집계 숫자만 반환한다.
- “관련 문서 전부”를 기본 반환하면 Sillok이 아니다.

## 성공 조건 (v1)

> 정본: [plan.md](plan.md) §9 — 값이 다르면 정본이 이긴다.

여기에 목록을 복제하지 않는다.
목록·타임라인 엔드포인트가 없다는 사실은 [open-questions.md](open-questions.md) Q13이 소유한다.

## 1차 산출물

1. 스키마 마이그레이션
2. Knowledge Service
3. MCP 서버
4. Skill 파일 ([skills/sillok-storage/](skills/sillok-storage/)를 대상 프로젝트에 복사)
5. JSON 현황 API (`GET /v1/status`). 웹 페이지는 v1 이후

## 명시적으로 미룸

자동 승격, 다중 조직 권한, IDE Plugin, 복잡한 대시보드, PDF/스캔 ingest.
