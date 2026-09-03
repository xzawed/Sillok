---
title: Sillok 운영 절차
doc_type: runbook
status: current
module: null
---

# Sillok 운영 절차

상위: [plan.md](plan.md) · [README](../README.md)

> 이 파일은 **절차**의 정본이다 (D54). 값의 정본은 [adr/0001-v1-stack-decisions.md](../adr/0001-v1-stack-decisions.md)다.
> 무엇을 만드는가는 [plan.md](plan.md)가, 어떻게 관리하는가는 [conventions.md](conventions.md)가 소유한다.

네 문서가 **이벤트는 백업 대상**이라고 적어 두었는데 명령이 한 줄도 없었다.
그 공백을 여기서 닫는다 — 절차를 적지 않으면 사고 난 날에 발명하게 된다.

## 무엇을 백업하는가

| 대상 | 백업 | 이유 |
|---|---|---|
| `kb_events` | **한다** | Git에 원본이 없는 유일한 데이터다 (D11) |
| `kb_documents` · `kb_chunks` | 하지 않는다 | Git이 원본이고 `sillok ingest`가 언제든 다시 만든다 |
| `kb_ingest_runs` | 하지 않는다 | 색인 이력이지 지식이 아니다 |
| `kb_query_logs` | 하지 않는다 | v1 성공 조건의 *측정*이다 (D51). 잃으면 측정을 잃지 지식을 잃지 않는다 |

**이벤트만 뜬다.** 전체 덤프는 재생성 가능한 것을 함께 나르고, 복원 때 문서 인덱스가
그 시점의 Git과 어긋나게 만든다.

## 이벤트 백업

`5432`는 호스트에 게시되지 않는다 (D16). 그래서 컨테이너 안에서 뜬다.

```bash
docker compose exec -T db pg_dump -U sillok -d sillok --data-only --table=kb_events > kb_events.sql
```

`--data-only`인 이유는 스키마의 정본이 `migrations/`이기 때문이다.
DDL을 함께 뜨면 그 사본이 마이그레이션과 갈라진다.

## 복원

```bash
docker compose up -d --wait            # 마이그레이션이 bind 전에 적용된다 (D17)
docker compose exec -T db psql -U sillok -d sillok < kb_events.sql
docker compose exec api sillok ingest --project <name>   # 문서 인덱스를 다시 만든다
```

**순서가 이렇다.** 스키마가 먼저 서고, 원장을 붓고, 재생성 가능한 것을 다시 만든다.

`kb_events.id`는 `bigserial`이다. 데이터만 부으면 시퀀스가 따라오지 않으므로
복원 뒤 첫 `save_event`가 중복 키로 죽을 수 있다. 시퀀스를 맞춘다:

```bash
docker compose exec -T db psql -U sillok -d sillok \
  -c "SELECT setval('kb_events_id_seq', COALESCE((SELECT max(id) FROM kb_events), 1));"
```

## 재기동

```bash
docker compose up -d --wait   # 두 컨테이너. 마이그레이션은 멱등이다 (D17)
docker compose restart api    # 코드는 그대로, 프로세스만
```

- `down -v`는 **`db_data` 볼륨을 지운다.** 이벤트가 사라진다. 백업 없이 쓰지 않는다
- `restart: unless-stopped`라 호스트를 껐다 켜면 스스로 돌아온다

## 마이그레이션을 더한 뒤

**`api` 이미지에는 `migrations/`가 구워져 있다.** `test` 서비스만 그것을 마운트한다.
그래서 `.sql`을 더하고 `up -d`만 하면 **api는 옛 목록을 들고 조용히 돈다** (D28이 예고한 자리).

```bash
docker compose build api      # 이 머신에서는 프록시 인자가 필요할 수 있다
docker compose up -d --wait
```

프록시가 필요한 환경이면 `--build-arg HTTP_PROXY=… --build-arg HTTPS_PROXY=…`를 붙인다.

## 마이그레이션이 실패할 때

`serve`는 bind 전에 적용하고 실패하면 **뜨지 않는다** (D17). 그것이 맞는 동작이다 —
스키마 없이 포트를 열면 첫 요청까지 결함이 숨는다.

- `restart: unless-stopped`라 실패가 계속되면 **재시작 루프**가 된다.
  루프를 멈추려면 `docker compose stop api`로 세우고 원인을 고친 뒤 다시 올린다
- 로그는 `docker compose logs api`. DSN은 메시지에서 가려진다 (D21)

**러너의 천장을 안다.** 적용 이력을 두지 않고 매 기동마다 모든 `.sql`을 다시 돌리며,
멱등의 유일한 출처가 `IF NOT EXISTS`다. **같은 이름의 객체가 다른 모양으로 이미 있으면
고치지 않고 넘어가면서 성공을 보고한다.** 컬럼·인덱스 정의를 바꾸는 변경이 필요해지면
멱등만으로는 부족하다 — 먼저 결정하고 ADR에 적는다.

## 검사가 쓰는 DB

`--profile test`는 **제품과 같은 Postgres, 같은 볼륨**을 쓴다 (D55).
격리는 이름으로 한다 — 검사는 `t_`로 시작하는 `project` 밖을 건드리지 않으며,
그 불변식은 검사 하나가 지킨다 (`tests/test_conventions.py`).

지우려면 그 접두사만 지운다:

```bash
docker compose exec -T db psql -U sillok -d sillok \
  -c "DELETE FROM kb_query_logs WHERE project LIKE 't\\_%'; \
      DELETE FROM kb_documents WHERE project LIKE 't\\_%'; \
      DELETE FROM kb_ingest_runs WHERE project LIKE 't\\_%'; \
      DELETE FROM kb_events WHERE project LIKE 't\\_%';"
```
