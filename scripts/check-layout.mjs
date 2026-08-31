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
  (p) => /^README[^/]*$/i.test(p),   // D9 는 확장자·대소문자를 가리지 않는다
  (p) => p.startsWith('adr/'),
]
// 색인되면 안 되는 것. 에이전트 도구 설정이지 프로젝트 지식이 아니다.
const MUST_EXCLUDE = ['AGENTS.md', 'CLAUDE.md']
const basename = (p) => p.slice(p.lastIndexOf('/') + 1)

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
  if (!existsSync(join(ROOT, x))) fail(`${x} 가 없다.`)
  // 경로가 어디든, 이름이 같으면 색인되면 안 된다 (docs/CLAUDE.md 같은 사본 포함)
  for (const p of indexed) {
    if (basename(p) === x) fail(`${p} 는 색인 대상이 아니어야 하는데 D9 패턴에 걸렸다.`)
  }
}

// 3. 색인 대상 전부 front matter 를 갖고 값이 taxonomy 안에 있는가
const seen = { doc_type: {}, status: {} }
for (const p of indexed) {
  const s = readFileSync(join(ROOT, p), 'utf8')
  const m = s.match(/^---\r?\n([\s\S]*?)\r?\n---/)
  if (!m) { fail(`${p} : front matter 없음`); continue }
  const fm = Object.fromEntries(
    m[1].split(/\r?\n/).filter((l) => l.includes(':'))
      .map((l) => [l.slice(0, l.indexOf(':')).trim(), l.slice(l.indexOf(':') + 1).replace(/\s+#.*$/, '').trim()])
  )
  for (const k of ['title', 'doc_type', 'status']) if (!fm[k]) fail(`${p} : front matter 에 ${k} 없음`)
  if (!('module' in fm)) fail(`${p} : front matter 에 module 키 없음 (값은 null 가능)`)
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

// 5. 진입점에서 모든 색인 문서에 도달하는가 (고정점까지 확장)
const reach = new Set(['README.md'])
for (let n = -1; n !== reach.size;) {
  n = reach.size
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

// 7. 존재하지 않는 Q 번호를 가리키는 참조가 없는가.
//    전체 집합을 "Q1-QN" 으로 인용하면 Q 를 추가할 때마다 조용히 낡으므로,
//    전체 인용은 문서에서 없앴다. 남은 것은 Q1-Q5 같은 안정적인 부분집합 참조뿐이며
//    여기서는 그것들이 실재하는 Q 를 가리키는지만 본다.
const oqPath = 'docs/open-questions.md'
if (existsSync(join(ROOT, oqPath))) {
  const oq = readFileSync(join(ROOT, oqPath), 'utf8')
  const defined = new Set([...oq.matchAll(/\*\*Q(\d+)\./g)].map((m) => Number(m[1])))
  if (defined.size === 0) fail(`${oqPath} : Q 항목을 하나도 찾지 못했다.`)
  else {
    const maxQ = Math.max(...defined)
    for (let i = 1; i <= maxQ; i++) if (!defined.has(i)) fail(`${oqPath} : Q${i} 이 빠져 번호가 연속되지 않는다.`)
    for (const p of md) {
      const body = readFileSync(join(ROOT, p), 'utf8')
      for (const m of body.matchAll(/\bQ(\d+)\b/g)) {
        const n = Number(m[1])
        if (!defined.has(n)) fail(`${p} : 존재하지 않는 ${m[0]} 을 참조한다 (${oqPath} 는 Q1..Q${maxQ}).`)
      }
    }
  }
}

// 8. 머지되면 의미를 잃는 지시어.
//    diff 안에서만 해석되는 말은 머지된 뒤 어느 변경인지 가리키지 못한다.
//    실제 사고: Q25 는 #2 에서 작성되며 "이 PR" 이라 썼는데 그 작업은 #1(bfc047c) 의 것이었다.
//    머지 후에도 유효한 참조(커밋 해시, 날짜, PR 번호)로 고정한다.
//    코드 스팬·코드 블록은 제외한다. 규칙 자체를 인용하려면 그 표현을 적어야 하고,
//    백틱으로 감싼 인용까지 잡으면 이 검사를 문서화하는 순간 자기 자신을 잡는다.
//
//    조사가 붙는 자리(은/는/에서/의)까지 열거하면 반드시 빠지는 게 생기므로 어간만 본다.
//    "이 작업" 류는 일반 문장에서도 흔해 넣지 않았다 — 여기서 잡으려는 건 PR·커밋 참조다.
const DEICTIC = [
  '이 PR', '이번 PR', '본 PR', '해당 PR', '현재 PR', '이 MR',
  '이 커밋', '이번 커밋', '본 커밋', '해당 커밋', '현재 커밋',
  '이 변경', '이번 변경', '본 변경', '해당 변경',
  '이 브랜치', '이번 브랜치', '본 브랜치',
  '이 패치', '이번 패치',
]

// 펜스를 정규식으로 짝지으면 열린 펜스 하나가 다음 펜스까지의 본문을 통째로 먹어
// 그 사이의 위반이 사라진다(false negative). 줄 단위로 상태를 추적하고,
// 닫히지 않은 펜스는 그 자체를 결함으로 보고한다. ~~~ 펜스도 같이 처리된다.
function stripCode(src) {
  const out = []
  let fence = null
  for (const line of src.split('\n')) {
    const m = /^ {0,3}(`{3,}|~{3,})/.exec(line)
    if (m) {
      // CommonMark: 닫는 펜스는 여는 펜스와 같은 문자이고 길이가 같거나 길어야 한다.
      // 길이를 무시하면 ```` 로 연 블록이 안쪽 예시의 ``` 에 닫혀 그 뒤가 산문으로 샌다.
      const marker = m[1][0]
      const len = m[1].length
      if (fence === null) fence = { marker, len }
      else if (marker === fence.marker && len >= fence.len) fence = null
      continue
    }
    if (fence === null) out.push(line.replace(/`[^`\n]*`/g, ''))
  }
  return { prose: out.join('\n'), unclosed: fence !== null }
}

for (const p of md) {
  const { prose, unclosed } = stripCode(readFileSync(join(ROOT, p), 'utf8'))
  if (unclosed) fail(`${p} : 닫히지 않은 코드 펜스 — 이후 본문이 코드로 먹혀 검사에서 빠진다.`)
  for (const d of DEICTIC) {
    if (prose.includes(d)) fail(`${p} : 머지 후 의미를 잃는 지시어 "${d}" — 커밋 해시·날짜·PR 번호로 고정한다.`)
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
