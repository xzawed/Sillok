#!/usr/bin/env node
// Sillok 저장소 배치 검증.
// 이 레포가 자기 색인 계약(D9: docs/**, 루트 README*, adr/**)을 지키는지 검사한다.
// sillok ingest 가 생기기 전까지 "색인 0건이 정상인지 버그인지" 구분하는 유일한 수단이다.
// 사용: node scripts/check-layout.mjs

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import { join, dirname, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const DOC_TYPES = ['adr', 'api', 'runbook', 'readme', 'schema', 'other']
const STATUSES = ['current', 'draft', 'superseded', 'stale']

// D9 색인 대상. 값을 바꾸려면 adr/0001-v1-stack-decisions.md 를 먼저 고친다.
const INCLUDE = [
  (p) => p.startsWith('docs/'),
  (p) => /^README[^/]*\.md$/.test(p),
  (p) => p.startsWith('adr/'),
]
// 색인되면 안 되는 것. 에이전트 도구 설정이지 프로젝트 지식이 아니다.
const MUST_EXCLUDE = ['AGENTS.md', 'CLAUDE.md']

const problems = []
const fail = (m) => problems.push(m)

const rel = (p) => relative(ROOT, p).split(sep).join('/')
function walk(dir, acc = []) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.name === '.git' || e.name === 'node_modules') continue
    const p = join(dir, e.name)
    e.isDirectory() ? walk(p, acc) : acc.push(p)
  }
  return acc
}

const all = walk(ROOT).map(rel)
const md = all.filter((p) => p.endsWith('.md'))
const indexed = md.filter((p) => INCLUDE.some((f) => f(p))).sort()

// 1. 색인 대상이 비어 있지 않은가 — 이전 배치의 실제 실패 모드다.
if (indexed.length === 0) fail('색인 대상이 0개다. D9 패턴에 걸리는 문서가 없다.')

// 2. 색인되면 안 되는 파일이 걸리지 않는가
for (const x of MUST_EXCLUDE) {
  if (indexed.includes(x)) fail(`${x} 는 색인 대상이 아니어야 하는데 D9 패턴에 걸렸다.`)
  if (!existsSync(join(ROOT, x))) fail(`${x} 가 없다.`)
}

// 3. 색인 대상 전부 front matter 를 갖고 값이 taxonomy 안에 있는가
const seen = { doc_type: {}, status: {} }
for (const p of indexed) {
  const s = readFileSync(join(ROOT, p), 'utf8')
  const m = s.match(/^---\r?\n([\s\S]*?)\r?\n---/)
  if (!m) { fail(`${p} : front matter 없음`); continue }
  const fm = Object.fromEntries(
    m[1].split(/\r?\n/).filter((l) => l.includes(':'))
      .map((l) => [l.slice(0, l.indexOf(':')).trim(), l.slice(l.indexOf(':') + 1).trim()])
  )
  for (const k of ['title', 'doc_type', 'status']) if (!fm[k]) fail(`${p} : front matter 에 ${k} 없음`)
  if (fm.doc_type && !DOC_TYPES.includes(fm.doc_type)) fail(`${p} : doc_type "${fm.doc_type}" 이 taxonomy 밖 (${DOC_TYPES.join('|')})`)
  if (fm.status && !STATUSES.includes(fm.status)) fail(`${p} : status "${fm.status}" 가 enum 밖 (${STATUSES.join('|')})`)
  if (fm.doc_type) seen.doc_type[fm.doc_type] = (seen.doc_type[fm.doc_type] || 0) + 1
  if (fm.status) seen.status[fm.status] = (seen.status[fm.status] || 0) + 1
}

// 4. 상대 링크가 전부 해석되는가
let links = 0
for (const p of md) {
  const s = readFileSync(join(ROOT, p), 'utf8')
  for (const m of s.matchAll(/\[([^\]]*)\]\(([^)]+)\)/g)) {
    let t = m[2].trim()
    if (/^(https?:|mailto:|#)/.test(t)) continue
    t = t.split('#')[0]
    if (!t) continue
    links++
    if (!existsSync(resolve(ROOT, dirname(p), t))) fail(`${p} : 끊긴 링크 -> ${t}`)
  }
}

// 5. 진입점에서 모든 색인 문서에 도달하는가 (1홉 이상)
const reach = new Set(['README.md'])
for (let i = 0; i < 5; i++) {
  for (const p of [...reach]) {
    if (!p.endsWith('.md') || !existsSync(join(ROOT, p))) continue
    const s = readFileSync(join(ROOT, p), 'utf8')
    for (const m of s.matchAll(/\[([^\]]*)\]\(([^)]+)\)/g)) {
      let t = m[2].trim()
      if (/^(https?:|mailto:|#)/.test(t)) continue
      t = t.split('#')[0]
      if (!t) continue
      const abs = resolve(ROOT, dirname(p), t)
      if (existsSync(abs) && statSync(abs).isFile()) reach.add(rel(abs))
    }
  }
}
for (const p of indexed) if (!reach.has(p)) fail(`${p} : 진입점 README.md 에서 도달 불가 (고아 문서)`)

// 6. 구 파일명 잔존 참조
for (const p of md) {
  const s = readFileSync(join(ROOT, p), 'utf8')
  for (const k of ['00-README', '01-SPEC', '02-STORAGE-RULES', '03-DATA-MODEL', '04-SERVICE-AND-MCP', '05-OPEN-DECISIONS']) {
    if (s.includes(k)) fail(`${p} : 구 파일명 "${k}" 잔존 참조`)
  }
}

console.log(`색인 대상 ${indexed.length}개`)
for (const p of indexed) console.log(`  ${p}`)
console.log(`제외 확인   ${MUST_EXCLUDE.join(', ')}`)
console.log(`doc_type    ${JSON.stringify(seen.doc_type)}`)
console.log(`status      ${JSON.stringify(seen.status)}`)
console.log(`상대 링크   ${links}개`)

if (problems.length) {
  console.error(`\n실패 ${problems.length}건:`)
  for (const p of problems) console.error(`  - ${p}`)
  process.exit(1)
}
console.log('\n배치 검증 통과')
