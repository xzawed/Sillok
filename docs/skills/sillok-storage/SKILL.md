---
name: sillok-storage
title: Sillok Skill — 저장 위치 규칙
doc_type: other
status: current
module: null
---

# Sillok Skill — 저장 위치 규칙

> **배포용 산출물.** 이 폴더를 대상 프로젝트로 복사해서 쓴다.
> 원본: `Sillok:docs/skills/sillok-storage/SKILL.md` · 기준일 2026-09-26
> 본문 해시: sha256:ef39618bd9bf (게이트가 지킨다, D63)
> 사본을 고치지 말고 원본을 고친 뒤 다시 복사한다.
> 상위 계약: `Sillok:docs/plan.md` §4

AI가 프로젝트 운영 중 생성·정리한 글을 어디에 둘지 이 파일만 따른다.  
감으로 분류하지 않는다.

## 한 줄

지금 구현이 달라지는 규칙 → Git 문서.  
언제 무엇이 어떤 결과였는지 → 이벤트.

## Git 문서 (`save_doc` / docs PR)

현재형이다. 최신본 하나면 된다.

- 모듈 책임, 현재 아키텍처
- 채택된 결정과 제약
- 현재 API·설정·배포 절차
- 코딩/문서 규칙
- 런북의 **결론** (“지금은 이렇게 한다”)

금지:

- 날짜가 다른 시도를 본문에 이어 붙이기
- “어제 실패했다”가 본문 절반인 글
- 초안을 현재 문서로 저장
- 기존 현재 문서와 모순인데 상태를 바꾸지 않음

## Postgres 이벤트 (`save_event`)

과거형이다. 행이 쌓인다.

- 작업 시도의 성공/실패
- 장애, 원인, 조치, 소요 시간
- 실험·벤치 결과
- 그날의 작업 로그
- 결정이 뒤집힌 시점 (내용은 이벤트, 새 규칙은 Git)

필수 필드가 없으면 저장하지 않는다.

필수:

- `project` (문자열, 64자 이하. 공백·슬래시·역슬래시 불가)
- `kind` : `success` | `failure` | `incident` | `decision`
- `title` (짧은 한 줄, **200자 초과 금지**. 공백뿐이면 없는 것)
- `summary` (200~400자 권장, 2000자 초과 금지. 공백뿐이면 없는 것)
- `occurred_at` (ISO-8601, **UTC 오프셋 필수** — `Z` 또는 `±HH:MM`. 날짜만은 불가)
- `result` : `success` | `failure` | `partial` | `unknown`

권장:

- `module` (200자 이하)
- `root_cause` (2000자 이하)
- `resolution` (2000자 이하)
- `severity` : `low` | `medium` | `high` | `critical`
- `resolved_at` (`occurred_at` 과 같은 형식, 그보다 앞서면 안 됨)
- `related_doc_path` (200자 이하)
- `source` : `manual` | `github_issue` | `markdown` | `agent`
- `payload` (객체, 압축 직렬화 2000자 이하. NaN·Infinity 불가)
- `created_by` (200자 이하)

## 결정 트리

```text
1. 이 글이 없어도 내일 구현·운영 방법이 달라지는가?
   예 → Git 후보
   아니오 → 이벤트 후보
2. 날짜·시도·성공실패가 본문의 핵심인가?
   예 → 이벤트
3. 이미 Git에 같은 주제의 현재 문서가 있는가?
   사건이다 → 이벤트
   규칙을 바꾼다 → 기존 Git 문서를 수정 (새 파일 남발 금지)
4. 이벤트인데 필수 필드가 빠졌는가?
   예 → 저장하지 말고 필드를 채운다
5. 같은 project+module+root_cause 이벤트가 2회 이상인가?
   예 → Git에 한 문단 승격 *제안*. 이벤트를 문서로 복사하지 않는다
```

## 쪼개기

한 글이 결론과 과정을 같이 가지면 둘로 나눈다.

- Git: 결론 10~20줄
- 이벤트: 시각, 증상, 원인, 조치, 결과

예: 장애 회고

- Git: “재발 방지로 연결 timeout을 30s로 둔다”
- 이벤트: 발생 시각, 증상, 원인, 조치

## 도구

- 사건 → `save_event`
- 현재 진실 → `save_doc` (v1은 패치 제안일 수 있음)
- 레포에 md를 임의로 추가하지 않음
- 분류가 안 되면 저장하지 않고 사람에게 묻거나 필드를 채움

## 거절

Service가 거절해야 하는 입력:

- 이벤트인데 필수 6개 (`project`, `kind`, `title`, `summary`, `occurred_at`, `result`) 중 하나라도 없음 —
  `title`·`summary`는 공백뿐이어도 없는 것이다
- `kind`·`result`·`severity`·`source`가 허용 값이 아님 (배열·객체도 허용 값이 아니다)
- 오프셋 없는 시각, 날짜만 있는 시각, `occurred_at`보다 앞선 `resolved_at`
- 위 필드 목록의 길이 천장을 넘음
- `project`가 비었거나 가운데에 공백·슬래시·역슬래시를 포함함 (앞뒤 공백은 벗긴다)
- 타입이 틀린 값 — 문자열이 아닌 텍스트 필드, 객체가 아닌 `payload`
- UTC로 옮기면 표현 범위를 벗어나는 시각
- NUL이나 짝 없는 서로게이트가 든 문자열, `payload` 안의 NaN·Infinity

## 판단은 하되 거절하지 않는 것

**Git 후보인데 본문에 날짜별 시도가 여러 건 쌓여 있으면** 그것은 현재 진실이 아니라 사건 이력이다 —
`save_doc`이 아니라 `save_event`로 간다. 다만 **Service는 이것으로 거절하지 않는다** (D38).
기계적으로 판정할 수 없는 것을 계약에 두면 구현이 임의로 채우고, 그 임의가 계약이 된다.
위의 거절 목록은 기계적으로 판정할 수 있는 것만 본다. 글이 어떤 종류인지는 여기서 사람과 모델이 판단한다.
