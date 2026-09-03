<div align="center">

# Sillok · 실록

**A knowledge ledger that forces the storage decision.**<br>
Current truth lives in Git. What happened lives in Postgres. AI reads a handful of rows.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![uv](https://img.shields.io/badge/uv-managed-DE5FE9?logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

[한국어 README](README.ko.md) · this English page is canonical; the Korean one is a copy (D27)

</div>

---

## What it is

Sillok is **not** a RAG platform.
It is a small, opinionated store that keeps a project's **rules** and its **history**
in separate places, on purpose — so a wiki never turns into a log.

- **Git** holds current truth: one latest version, written in the present tense.
- **Postgres** holds the event ledger plus a search index over the Git documents.
- **AI** reaches both through a narrow tool surface that returns a few rows, never whole files.

The point is that **cost per query stays roughly flat as the corpus grows.**
Returning "all the relevant documents" is treated as a design violation, not a feature.

## Why

| Symptom | What Sillok does |
|---|---|
| The wiki becomes a log | Norms go to Git, "what happened when" goes to an event ledger. There is no path that mixes them |
| The model reads a huge file and gets it wrong | Tools return **rows**, not documents |
| You cannot count incidents or repeats from prose | Events are aggregated in SQL. `repeat_causes` counts recurring causes |

## Quick start

Requires Docker. Nothing else — the API container carries its own Python.

```bash
docker compose up -d --wait
curl -s "http://127.0.0.1:8080/v1/status?project=demo"
```

Only `8080` is published.
Postgres stays on the internal network, so nothing reaches the database except the service itself.

```json
{ "ok": true, "data": { "documents": 0, "chunks": 0, "events": 0, "last_ingest_at": null,
                        "zero_hit_queries": 0, "chunks_without_embedding": 0 } }
```

### Events are rejected, not repaired

Six fields are required. A request missing any of them is **not stored**.

```bash
curl -s -X POST http://127.0.0.1:8080/v1/events \
  -H 'Content-Type: application/json' -d '{"project":"demo"}'
```

```json
{ "ok": false, "error": { "code": "VALIDATION",
  "message": "missing required field: kind, title, summary, occurred_at, result" } }
```

Record the same failure twice in `auth` and twice in `billing`:

```bash
for m in auth auth billing billing; do
  curl -s -X POST http://127.0.0.1:8080/v1/events \
    -H 'Content-Type: application/json' \
    -d "{\"project\":\"demo\",\"kind\":\"failure\",
         \"title\":\"pool exhausted after deploy\",
         \"summary\":\"connection pool ran out\",
         \"occurred_at\":\"2026-08-31T09:00:00Z\",
         \"resolved_at\":\"2026-08-31T10:00:00Z\",
         \"result\":\"failure\",\"module\":\"$m\",
         \"root_cause\":\"pool exhausted\"}"
done
```

Four calls, four envelopes. Ids start at 1 on an empty database and increment.

```json
{ "ok": true, "data": { "id": 1 } }
{ "ok": true, "data": { "id": 2 } }
{ "ok": true, "data": { "id": 3 } }
{ "ok": true, "data": { "id": 4 } }
```

Success or failure, **the body is always the same envelope.**
Framework defaults never leak through.

### Repeats are counted per module

The same `root_cause` in a different module is a different repeat.
Collapsing them would report **four recurrences that never happened**.

```bash
curl -s "http://127.0.0.1:8080/v1/stats/events?project=demo"
```

```json
{ "ok": true, "data": {
  "total": 4,
  "by_kind":   { "failure": 4 },
  "by_result": { "failure": 4 },
  "by_module": { "auth": 2, "billing": 2 },
  "repeat_causes": [
    { "module": "auth",    "root_cause": "pool exhausted", "count": 2 },
    { "module": "billing", "root_cause": "pool exhausted", "count": 2 }
  ],
  "avg_resolution_seconds": 3600
} }
```

Statistics **never use vectors** — filters plus `COUNT` / `AVG` only.
Unresolved events are excluded from the average,
so an all-unresolved window returns `null` rather than `0`.
`by_*` are JSON objects; key order is not guaranteed.

## How it works

```text
[1] PostgreSQL + pgvector   kb_documents · kb_chunks · kb_events · logs
[2] Knowledge Service       FastAPI. The only door to the database
[3] Exits                   MCP tools · Skill · JSON status API
```

Layers 1 and 2 are running. Layer 3 currently exposes the JSON API only.

- **The unit of the invariant is the Service function, not HTTP.**
  MCP and any human UI must go through the HTTP API; the CLI calls the same functions in-process.
  What is forbidden is a second SQL layer anywhere.
- **Embeddings are optional by design.** Without `OPENAI_API_KEY` the `embedding` column
  stays NULL and document search will use `tsv` keywords only. Event search is keywords only
  either way — v1 does not embed events.
  A key turns the vector arm on; without one the merge runs over the keyword list alone.
- **Secrets come from the environment only.** See [.env.example](.env.example).

## Status

| Area | State |
|---|---|
| Compose, migrations, FastAPI skeleton | Working |
| `POST /v1/events`, `GET /v1/stats/events`, `GET /v1/status` | Working |
| Search — `POST /v1/search/docs` and `/v1/search/events` | Working. Without a key the vector arm is empty, which is the designed normal state |
| `get_event`, `get_file`, `save_doc` | Working. `get_file` opens indexed rows only and answers with a 4000-character window; `save_doc` returns a proposal and never writes Git |
| Indexing — `sillok ingest` and `POST /v1/ingest` | Working. Embeddings need a key; without one the vectors stay NULL |
| MCP tools | Working. Eight tools over `POST /mcp` and stdio (`sillok mcp`); each answers with the same envelope as its HTTP face |
| Query ledger — `kb_query_logs` | Working. The two search tools write one row per query; `kb_status` counts the zero-hit ones from it |

> The source of truth for progress is [docs/plan.md](docs/plan.md) §7 and §9.

**No stubs.**
A route that merely responds, parked on a completion criterion, would look like progress.

Open design questions are tracked in [docs/open-questions.md](docs/open-questions.md),
and they **block the stages that depend on them** — enforced by a check, not by convention.

## Documentation

The design documents are written in Korean.

| Document | What it owns |
|---|---|
| [docs/plan.md](docs/plan.md) | The implementation contract. Build order, v1 done criteria |
| [adr/0001-v1-stack-decisions.md](adr/0001-v1-stack-decisions.md) | Every settled value — stack, dimensions, paths, auth, error mapping, licence |
| [docs/conventions.md](docs/conventions.md) | Document map, conflict resolution, the documentation gate |
| [docs/spec.md](docs/spec.md) · [docs/data-model.md](docs/data-model.md) · [docs/service-and-mcp.md](docs/service-and-mcp.md) | Problem framing · schema · API and MCP contract |
| [docs/skills/sillok-storage/SKILL.md](docs/skills/sillok-storage/SKILL.md) | The storage decision tree — which writes become documents and which become events |
| [docs/open-questions.md](docs/open-questions.md) | What has no answer yet |
| [AGENTS.md](AGENTS.md) | How a change ships, and what counts as evidence |

**Documents beat code here.** If behaviour and the contract disagree, the code is wrong.

## Development

```bash
node scripts/evidence.mjs   # runs everything a change must show, in one command
```

| Command | What it checks |
|---|---|
| `node scripts/check-layout.mjs` | The documentation gate. Independent of the code |
| `node scripts/check-layout.test.mjs` | **Whether that gate actually bites.** It copies the repo to a temp directory and injects faults into the copy |
| `uv run pytest -q` | Host tests. Database tests are skipped |
| `docker compose --profile test run --rm test` | Everything, including database tests, with `5432` still closed |

Seeing `skip 0` on the host means the port override is on — it is a signal, not a better result.
The committed Compose file does not publish `5432`;
copy `compose.override.example.yml` if you need to reach the database from the host.

<details>
<summary>If <code>docker compose build</code> fails on DNS</summary>

Some environments attach a proxy to runtime containers but not to the build sandbox.
Pass the proxy through only in that case:

```bash
docker compose build \
  --build-arg HTTP_PROXY="$HTTP_PROXY" \
  --build-arg HTTPS_PROXY="$HTTPS_PROXY" api
```

It is an environment problem, so it is never baked into the image.

</details>

## Project layout

| Path | Role |
|---|---|
| `docker-compose.yml` · `Dockerfile` | `db` + `api`. A `test` service sits behind a Compose profile |
| `migrations/` | Versioned raw SQL, applied before the server binds |
| `src/sillok/service.py` | The only door to the database. Validation lives here, not in DDL constraints |
| `src/sillok/api.py` | The HTTP adapter — the common envelope and the bearer gate. Holds no SQL |
| `src/sillok/cli.py` | `sillok migrate` · `sillok serve` · `sillok ingest` |
| `scripts/` | Documentation gate, its fault-injection harness, evidence collector |
| `tests/` | pytest |

## License

[MIT](LICENSE).

This is a **personal tool** that happens to be public. There is no contribution process,
no issue template, and no backward-compatibility promise.
