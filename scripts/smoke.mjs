#!/usr/bin/env node
// 10단계 스모크 (plan.md §7). **살아 있는 HTTP 표면을 때린다.**
//
// §7 이 정한 셋을 그 순서로 본다 — 필수 필드 없는 이벤트 거절 · ingest 후 검색 · stats.
// 여기서 항목을 늘리지 않는다. 늘리려면 §7 을 먼저 고친다 (D53).
//
// **HTTP 만 쓴다.** CLI 경로는 §9 판정 블록의 `compose exec api sillok ingest` 와
// `check-index-parity.mjs` 가 이미 태운다. 스모크가 보는 것은 *배포된 서비스가 도는가* 다.
//
// **`curl -sf` 로는 첫 항목을 볼 수 없다** — 거절을 기대하는데 그 옵션은 4xx 에서 죽는다.
// 그래서 상태코드와 봉투를 함께 판정하는 이 스크립트가 있다 (D53).
//
// 사용: node scripts/smoke.mjs [--base http://127.0.0.1:8080] [--project sillok] [--query Sillok]
// 전제: `docker compose up -d --wait` 로 서비스가 떠 있어야 한다.

const args = process.argv.slice(2)
function flag(name, fallback) {
  const at = args.indexOf(`--${name}`)
  return at >= 0 && args[at + 1] ? args[at + 1] : fallback
}

const BASE = flag('base', process.env.SILLOK_BASE || 'http://127.0.0.1:8080')
const PROJECT = flag('project', 'sillok')
// 검색어는 project 이름과 다른 축이다. 섞어 쓰면 "색인이 비었다" 와
// "그 이름이 본문에 없다" 를 구분하지 못한다 — 고장 주입에서 드러났다.
// 기본값은 이 저장소의 자기 색인을 전제한다 (D53).
const QUERY = flag('query', 'Sillok')
const TOKEN = process.env.SILLOK_BEARER_TOKEN || ''

// D7. 토큰이 설정된 배치에서도 그대로 돌아야 한다.
const HEADERS = {
  'Content-Type': 'application/json',
  ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
}

async function call(method, path, body) {
  const response = await fetch(`${BASE}${path}`, {
    method,
    headers: HEADERS,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await response.text()
  let json = null
  try {
    json = JSON.parse(text)
  } catch {
    // 봉투가 아닌 본문은 그 자체가 계약 위반이다 (D21). 아래 판정이 잡는다.
  }
  return { status: response.status, json, text }
}

// 세 항목. 각자 `check` 가 참이어야 통과하고, `line` 이 증거 줄이 된다.
const CHECKS = [
  {
    name: '필드 없는 이벤트 거절',
    async run() {
      // D10·D25. 관대하게 채우지 않는다 — 저장하지 않고 거절한다.
      const { status, json } = await call('POST', '/v1/events', {})
      const code = json?.error?.code
      const ok = status === 422 && json?.ok === false && code === 'VALIDATION'
      return { ok, line: `${status} ${code ?? '(봉투 아님)'} — ${json?.error?.message ?? ''}` }
    },
  },
  {
    name: 'ingest 후 검색',
    async run() {
      // D20. 같은 Service 함수의 HTTP 얼굴이다. 두 번째 run 은 아무것도 바꾸지 않는다 (D30).
      const ingest = await call('POST', '/v1/ingest', { project: PROJECT })
      if (ingest.status !== 200 || ingest.json?.ok !== true) {
        return { ok: false, line: `ingest 가 실패했다: ${ingest.status} ${ingest.text.slice(0, 120)}` }
      }
      const run = ingest.json.data
      const found = await call('POST', '/v1/search/docs', { project: PROJECT, query: QUERY })
      const hits = found.json?.data?.results ?? []
      return {
        // 색인이 돌았는데 한 건도 안 나오면 색인이 비어 있다는 뜻이다.
        ok: found.status === 200 && found.json?.ok === true && hits.length > 0,
        line:
          `run ${run.run_id} ${run.status} · 본 ${run.files_seen} · 바뀐 ${run.files_changed}` +
          ` → 검색 ${hits.length}건 (첫 행 ${hits[0]?.path ?? '없음'})`,
      }
    },
  },
  {
    name: 'stats',
    async run() {
      // D23. 벡터를 쓰지 않는다 — 필터 + COUNT/AVG 다.
      const { status, json } = await call('GET', `/v1/stats/events?project=${PROJECT}`)
      const data = json?.data
      const ok = status === 200 && json?.ok === true && typeof data?.total === 'number'
      const kinds = Object.keys(data?.by_kind ?? {}).length
      return { ok, line: `${status} · total ${data?.total} · by_kind ${kinds}종` }
    },
  },
]

const results = []
for (const check of CHECKS) {
  try {
    results.push({ name: check.name, ...(await check.run()) })
  } catch (e) {
    // 서비스가 안 떠 있으면 여기로 온다. 통과로 적지 않는다.
    results.push({ name: check.name, ok: false, line: `호출 실패 — ${e.message}` })
  }
}

console.log('## 10단계 스모크 (실측)\n')
console.log('```text')
console.log(`대상 ${BASE} · project ${PROJECT} · 검색어 ${QUERY}`)
for (const { name, ok, line } of results) {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name.padEnd(20)} ${line}`)
}
console.log('```')

const failed = results.filter((r) => !r.ok)
if (failed.length) {
  console.error(`\n스모크 ${failed.length}건이 실패했다. 서비스가 떠 있는지부터 본다 —`)
  console.error('  docker compose up -d --wait')
  process.exit(1)
}
