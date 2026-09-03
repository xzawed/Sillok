#!/usr/bin/env node
// 스모크가 **실제로 무는지** 본다 (AGENTS.md `테스트를 쓰는 방식`).
//
// 통과 출력만으로는 검사가 살아 있는지 알 수 없다. 그래서 고장을 주입하고 그 주입을 커밋한다 —
// `check-layout.test.mjs` 가 문서 게이트에 하는 것과 같은 자리다.
//
// **DB 도 도커도 필요 없다.** 계약이 약속한 모양의 응답을 내는 가짜 서비스를 세우고
// 거기에 스모크를 태운다. 그래야 `실패한 색인이 통과로 나오는가` 같은 물음을
// 실제 스택을 망가뜨리지 않고 물을 수 있다.
//
// 사용: node scripts/smoke.test.mjs

import { createServer } from 'node:http'
import { execFile } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SMOKE = resolve(ROOT, 'scripts/smoke.mjs')

// 계약대로인 응답 셋. 각 케이스는 여기서 필요한 조각만 덮어쓴다.
const HEALTHY = {
  events: { status: 422, body: { ok: false, error: { code: 'VALIDATION', message: 'missing required field: project' } } },
  ingest: {
    status: 200,
    body: { ok: true, data: { run_id: 1, status: 'ok', files_seen: 10, files_changed: 0 } },
  },
  search: { status: 200, body: { ok: true, data: { results: [{ path: 'docs/plan.md' }] } } },
  stats: { status: 200, body: { ok: true, data: { total: 3, by_kind: { failure: 2 }, by_result: {} } } },
}

const CASES = [
  { name: '계약대로면 통과한다', patch: {}, expect: 'pass' },

  // Grok 적대 리뷰가 잡은 자리. `ok: true` 는 색인 성공이 아니다 — 실패한 run 도 행이 생기면
  // 봉투는 성공이고 `status` 만 `failed` 다 (D32·D21). 낡은 인덱스가 히트를 내주면 초록이 된다.
  {
    name: 'ingest 가 failed 인데 검색이 히트하면 운다',
    // `files_seen` 을 살려 둔다. 0 으로 두면 이 케이스가 `status` 가 아니라 그쪽으로 걸려
    // 무엇을 잠갔는지 알 수 없다 (Grok 재검토).
    patch: { ingest: { status: 200, body: { ok: true, data: { run_id: 2, status: 'failed', files_seen: 10, files_changed: 3 } } } },
    expect: 'fail',
  },
  {
    name: 'ingest 가 partial 이어도 운다',
    patch: { ingest: { status: 200, body: { ok: true, data: { run_id: 3, status: 'partial', files_seen: 10, files_changed: 1 } } } },
    expect: 'fail',
  },
  {
    name: '본 파일이 0이면 운다',
    patch: { ingest: { status: 200, body: { ok: true, data: { run_id: 4, status: 'ok', files_seen: 0, files_changed: 0 } } } },
    expect: 'fail',
  },
  {
    name: '거절해야 할 자리가 200 이면 운다',
    patch: { events: { status: 200, body: { ok: true, data: { id: 1 } } } },
    expect: 'fail',
  },
  {
    name: '거절 코드가 다르면 운다',
    patch: { events: { status: 422, body: { ok: false, error: { code: 'INTERNAL', message: 'internal error' } } } },
    expect: 'fail',
  },
  {
    name: '검색이 0건이면 운다',
    patch: { search: { status: 200, body: { ok: true, data: { results: [] } } } },
    expect: 'fail',
  },
  {
    name: '검색 결과가 목록이 아니면 운다',
    patch: { search: { status: 200, body: { ok: true, data: { results: '여덟건' } } } },
    expect: 'fail',
  },
  {
    name: 'stats 가 봉투가 아니면 운다',
    patch: { stats: { status: 200, body: { total: 3 } } },
    expect: 'fail',
  },
  {
    name: 'stats 에 by_kind 가 없으면 운다',
    patch: { stats: { status: 200, body: { ok: true, data: { total: 3 } } } },
    expect: 'fail',
  },
  {
    name: '본문이 JSON 이 아니면 운다',
    patch: { stats: { status: 200, raw: '<html>gateway</html>' } },
    expect: 'fail',
  },
]

function route(url, method) {
  if (method === 'POST' && url.startsWith('/v1/events')) return 'events'
  if (method === 'POST' && url.startsWith('/v1/ingest')) return 'ingest'
  if (method === 'POST' && url.startsWith('/v1/search/docs')) return 'search'
  if (method === 'GET' && url.startsWith('/v1/stats/events')) return 'stats'
  return null
}

function serve(patch) {
  const table = { ...HEALTHY, ...patch }
  return new Promise((done) => {
    const server = createServer((req, res) => {
      const key = route(req.url, req.method)
      if (!key) {
        res.writeHead(404, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ ok: false, error: { code: 'NOT_FOUND', message: 'no route' } }))
        return
      }
      const spec = table[key]
      res.writeHead(spec.status, { 'Content-Type': 'application/json' })
      res.end(spec.raw ?? JSON.stringify(spec.body))
    })
    server.listen(0, '127.0.0.1', () => done(server))
  })
}

function runSmoke(port) {
  return new Promise((done) => {
    execFile(
      process.execPath,
      [SMOKE, '--base', `http://127.0.0.1:${port}`, '--project', 'smoketest', '--query', 'x'],
      { cwd: ROOT, encoding: 'utf8' },
      (err, stdout, stderr) => done({ code: err ? err.code ?? 1 : 0, out: stdout + stderr }),
    )
  })
}

let bad = 0
for (const testcase of CASES) {
  const server = await serve(testcase.patch)
  const { port } = server.address()
  const { code } = await runSmoke(port)
  server.close()

  const actual = code === 0 ? 'pass' : 'fail'
  const agrees = actual === testcase.expect
  if (!agrees) bad += 1
  console.log(
    `${agrees ? 'OK  ' : 'BAD '} ${testcase.name.padEnd(34)} 기대=${testcase.expect} 실제=${actual}`,
  )
}

// 대조군. 서비스가 아예 없을 때도 통과로 나오면 위 결과가 전부 무의미하다.
const dead = await runSmoke(1)
if (dead.code === 0) {
  console.log('BAD  서비스가 없는데 통과했다')
  bad += 1
} else {
  console.log('OK   서비스가 없으면 운다'.padEnd(40) + ' 기대=fail 실제=fail')
}

if (bad) {
  console.error(`\n불일치 ${bad}건 — 스모크가 무엇을 무는지 알 수 없다.`)
  process.exit(1)
}
console.log(`\n고장 주입 ${CASES.length}종 + 대조군 전부 기대와 일치`)
