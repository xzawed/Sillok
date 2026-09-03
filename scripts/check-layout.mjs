#!/usr/bin/env node
// Sillok 저장소 배치 검증.
// 이 레포가 자기 색인 계약(D9: docs/**, 루트 README*, adr/**)을 지키는지 검사한다.
// "색인 0건이 정상인지 버그인지" 를 가르는 기준선이다 — 여기가 **기대**다.
// ingest 가 실제로 무엇을 집는지(**실측**)는 scripts/check-index-parity.mjs 가 이 목록과 대조한다.
// 사용: node scripts/check-layout.mjs

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import { join, dirname, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const DOC_TYPES = ['adr', 'api', 'runbook', 'readme', 'schema', 'other']
const STATUSES = ['current', 'draft', 'superseded', 'stale']

// 검사 3 과 검사 12 가 같은 것을 반대 방향으로 본다. 파서를 두 벌 두면 갈라진다.
// GitHub 이 front matter 로 **인정하는 것**을 기준으로 잡는다 — 좁게 잡으면 검사 12 가
// "게이트는 통과하는데 첫 화면에는 표가 뜨는" 변형을 놓친다.
//   - 여는 울타리 뒤의 공백·탭: micromark 의 fenceOpen 은 `sequenceOpen *spaceOrTab` 다
//   - 선행 BOM: comrak 의 구분자는 BOM 을 허용한다
// 반대로 GitHub 도 거부하는 것(빈 첫 줄, 선행 공백, 네 줄표, `...` 닫기)은 여기서도 안 잡는다.
// 일부러 안 잡는 둘: CR 만 쓰는 줄끝(git 이 통과시키지 않는다)과 빈 front matter (`---\n---`).
// 둘 다 "게이트는 초록인데 첫 화면에 표가 뜨는" 부류가 아니다 — 빈 것은 표로 그릴 행이 없다.
const FRONT_MATTER = /^﻿?---[ \t]*\r?\n([\s\S]*?)\r?\n---/
// 루트 README* — D9 색인 대상이면서 front matter 를 갖지 **않는** 유일한 부류다 (D29).
const isRootReadme = (p) => /^README[^/]*$/i.test(p)   // D9 경로 판정은 확장자·대소문자를 가리지 않는다

// D9 색인 대상. 값을 바꾸려면 adr/0001-v1-stack-decisions.md 를 먼저 고친다.
const INCLUDE = [
  (p) => p.startsWith('docs/'),
  isRootReadme,
  (p) => p.startsWith('adr/'),
]
// 색인되면 안 되는 것. 에이전트 도구 설정이지 프로젝트 지식이 아니다.
const MUST_EXCLUDE = ['AGENTS.md', 'CLAUDE.md']
const basename = (p) => p.slice(p.lastIndexOf('/') + 1)

const problems = []
const fail = (m) => problems.push(m)

const rel = (p) => relative(ROOT, p).split(sep).join('/')
// D47. ingest 의 _SKIP_DIRS 와 **같은 목록**이어야 한다. 정본은 ADR 이다 —
// 게이트는 JS 이고 ingest 는 파이썬이라 코드로 공유할 수 없다.
const SKIP_DIRS = new Set(['.git', 'node_modules', '.venv', 'venv', '__pycache__', '.pytest_cache'])
function walk(dir, acc = []) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(e.name)) continue
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
//    루트 README* 만 예외다 — GitHub 이 최상단에 표로 렌더한다 (D29).
//    유도 규칙(경로 → readme/current/null, 첫 H1 → title)은 ingest 가 소유한다. 여기서 복제해
//    분포를 채우지 않는다 — 같은 규칙이 두 벌이면 그것이 곧 낡는 사본이다. 대신 면제 목록을 출력한다.
//    반대 방향(README 에 front matter 가 되살아나는 것)은 검사 12 가 본다.
const seen = { doc_type: {}, status: {} }
for (const p of indexed) {
  if (isRootReadme(p)) continue
  const s = readFileSync(join(ROOT, p), 'utf8')
  const m = s.match(FRONT_MATTER)
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

// 검사 14 가 쓸 값. Q 게이트가 이미 아는 것에서 유도한다 — 사실을 두 번 적지 않는다.
let verifiableThrough = null
let stageReason = ''

// 9. Q 게이트 — 단계를 막는 질문이 열려 있는데 그 단계의 표면이 코드에 있는가.
//    plan.md §7 이 "n단계 전에 Qx·Qy" 를 소유한다. 여기서는 그 문장을 읽어 강제만 한다.
//    문장을 고치면 검사가 따라온다 — 사실을 두 곳에 적지 않기 위해서다.
//
//    이 검사가 없으면 "먼저 결정한다" 는 강제되지 않는 산문이다.
const planPath = 'docs/plan.md'
if (existsSync(join(ROOT, planPath)) && existsSync(join(ROOT, oqPath))) {
  const plan = readFileSync(join(ROOT, planPath), 'utf8')
  const oq = readFileSync(join(ROOT, oqPath), 'utf8')

  // "4단계 전에 Q16·Q18·Q21" 에서 단계와 Q 목록을 뽑는다.
  const gates = new Map()
  // 쉼표·줄바꿈·한글 중 먼저 오는 것에서 끊는다.
  // 쉼표를 넣지 않으면 "…Q21**, 5" 처럼 **다음 단계의 숫자를 먹어** 그 단계가
  // 통째로 파싱되지 않는다. 실제로 그 상태로 4·6·8단계만 지키고 있었다 (고장 주입으로 발견).
  for (const m of plan.matchAll(/(\d+)단계 전에([^,\n가-힣]*)/g)) {
    const qs = [...m[2].matchAll(/Q(\d+)/g)].map((q) => Number(q[1]))
    if (qs.length) gates.set(Number(m[1]), qs)
  }

  // 파싱 실패를 조용히 넘기지 않는다. 문장은 있는데 못 읽으면 게이트가 비어도 통과한다.
  const declared = (plan.match(/\d+단계 전에/g) || []).length
  if (declared !== gates.size) {
    fail(
      `${planPath} §7 : "n단계 전에 Qx" ${declared}건 중 ${gates.size}건만 읽었다. ` +
        'Q 게이트가 조용히 비어 있게 된다.'
    )
  }
  // 문장을 통째로 바꾸거나 지우면 위 검사는 0 === 0 으로 통과한다. 그것도 막는다.
  if (gates.size === 0) {
    fail(`${planPath} §7 : "n단계 전에 Qx" 문장을 하나도 찾지 못했다. Q 게이트가 비어 있다.`)
  }

  // 해결된 Q. "**Q11. ..." 로 시작하는 덩어리 안에 "해결 →" 가 있으면 닫힌 것이다.
  const resolved = new Set()
  const blocks = oq.split(/(?=\*\*Q\d+\.)/)
  for (const block of blocks) {
    const head = /^\*\*Q(\d+)\./.exec(block)
    if (head && block.includes('해결 →')) resolved.add(Number(head[1]))
  }

  // 단계별 표면. 정본은 plan.md §5 와 docs/service-and-mcp.md 다.
  // 긴 접두사부터 본다 — /v1/events/{id}(7단계 get_event)가 /v1/events(4단계)보다 먼저다.
  // GET /v1/docs 는 §7 이 어느 단계에도 넣지 않았다. 여기서 단계를 발명하지 않는다.
  const SURFACE = [
    ['/v1/search/docs', 6],
    ['/v1/search/events', 6],
    ['/v1/stats/events', 4],
    ['/v1/docs/proposals', 7],
    ['/v1/events/', 7],
    ['/v1/events', 4],
    ['/v1/ingest', 5],
    ['/v1/status', 4],
    ['/v1/files', 7],
  ]
  const CLI_STEP = { ingest: 5, mcp: 8 }
  const TRACKED_STEPS = [...new Set([...SURFACE.map((s) => s[1]), ...Object.values(CLI_STEP), 8])]

  const stepOf = (path) => {
    for (const [prefix, step] of SURFACE) if (path.startsWith(prefix)) return step
    return null
  }

  // 우리가 표면을 추적하는 단계에 게이트 문장이 없으면, 그 단계는 무방비인데 조용히 통과한다.
  // Q 가 다 풀려도 §7 의 절을 지우지 않는다 — open-questions 가 항목을 지우지 않는 것과 같은 이유다.
  for (const step of TRACKED_STEPS.toSorted((a, b) => a - b)) {
    if (!gates.has(step)) {
      fail(
        `${planPath} §7 : ${step}단계 게이트 문장이 없다. ` +
          'Q 가 해결됐더라도 절을 지우지 말고 남긴다 (해결 표시는 open-questions.md 가 한다).'
      )
    }
  }

  // "1–N단계를 이제 검증할 수 있다" 의 N 은 여기서 나온다.
  // **막힌 가장 이른 단계 바로 앞**이 N 이다 — 7단계가 막혀 있으면 8단계 Q 가 다 풀려도 1–6 이다.
  // "Q 가 다 풀린 단계의 **개수**" 가 아니다: 1–N 은 1부터 이어지는 구간이지 세는 값이 아니고,
  // 뒤 단계만 열리는 것은 §7 이 금지하는 건너뛰기다.
  const blockedSteps = [...gates.keys()]
    .filter((step) => gates.get(step).some((q) => !resolved.has(q)))
    .toSorted((a, b) => a - b)

  // 막힌 단계가 없을 때는 §7 목록의 **마지막 단계**가 N 이다.
  // 여기서 유도를 멈추면(예전 코드) 마지막 Q 가 닫히는 순간 검사의 절반이 조용히 은퇴하고
  // "셋이 사이좋게 틀림" 이 다시 통과한다 — 그것이 이 검사의 존재 이유였다.
  // gates 의 최대값(8)을 쓰면 안 된다. Q 가 걸린 적 없는 9·10단계가 영원히 빠진다.
  // 제목은 **줄머리에 고정**한다. indexOf 로 찾으면 산문 속의 "## 7." 이나
  // "### 7." 에도 걸려, 실패하지 않은 채 엉뚱한 구간을 잘라 온다.
  const h7 = plan.search(/^## 7\./m)
  const h8 = plan.search(/^## 8\./m)
  // 펜스·코드 스팬은 뺀다 (검사 8·10·11·14 와 같은 규칙). 예시로 적은 "11. …" 한 줄이
  // 조용히 N 을 올리면, 아직 열지 않은 단계를 게이트가 요구하게 된다.
  const section7 = h7 >= 0 && h8 > h7 ? stripCode(plan.slice(h7, h8)).prose : ''
  const stepNos = [...section7.matchAll(/^(\d+)\. /gm)].map((m) => Number(m[1]))
  const lastStep = stepNos.length ? Math.max(...stepNos) : 0
  // **1,2,…,last 와 정확히 같아야 한다.** 최대값과 개수만 보면 마지막 항목이
  // 하나 내려간 경우(10 → 9 가 둘)가 빠져나가고 N 이 조용히 하나 작아진다.
  const expectedSteps = Array.from({ length: lastStep }, (_, i) => i + 1).join(',')
  if (!lastStep || stepNos.join(',') !== expectedSteps) {
    fail(
      `${planPath} §7 : 번호 목록을 읽지 못했다 (${stepNos.join(',') || '없음'}). ` +
        '검사 14 가 쓸 마지막 단계를 정할 수 없다.'
    )
  } else if (blockedSteps.length) {
    verifiableThrough = blockedSteps[0] - 1
    stageReason = `${blockedSteps[0]}단계를 막는 Q 가 아직 열려 있다`
  } else {
    verifiableThrough = lastStep
    stageReason = '§7 을 막는 Q 가 하나도 남지 않았다'
  }

  const py = all.filter((p) => p.startsWith('src/') && p.endsWith('.py'))
  const found = [] // { step, what, file }
  for (const p of py) {
    // 주석 줄은 지운다. 설명에 적은 경로까지 잡으면 "4단계에서 붙인다" 라는
    // 주석을 쓸 수 없다. 문자열 안의 # 는 건드리지 않으려고 줄 전체 주석만 본다.
    const s = readFileSync(join(ROOT, p), 'utf8')
      .split('\n')
      .filter((line) => !/^\s*#/.test(line))
      .join('\n')

    // 라우터에 붙은 prefix 를 모은다. FastAPI 의 기본 형태가
    //   router = APIRouter(prefix="/v1");  @router.get("/status")
    // 라서, 데코레이터의 경로만 보면 4단계 라우트가 그대로 통과한다.
    // 파일 안의 모든 prefix 를 상대 경로에 붙여 본다 — 어느 라우터인지 정확히 몰라도
    // 막는 쪽으로 틀리는 것이 낫다.
    const prefixes = ['']
    for (const m of s.matchAll(/prefix\s*=\s*["']([^"']*)["']/g)) prefixes.push(m[1])
    for (const m of s.matchAll(/\.mount\(\s*["']([^"']*)["']/g)) prefixes.push(m[1])

    const flag = (rawPath, what) => {
      for (const prefix of prefixes) {
        const step = stepOf(prefix + rawPath)
        if (step) {
          found.push({ step, what: `${what} ${prefix}${rawPath}`, file: p })
          return
        }
      }
    }

    // 데코레이터: @app.get("/x") / @router.post(path="/x")
    for (const m of s.matchAll(
      /@\w+\.(?:get|post|put|patch|delete)\(\s*(?:path\s*=\s*)?["']([^"']+)["']/g
    )) {
      flag(m[1], '라우트')
    }
    // 명시 등록: app.add_api_route("/x", ...)
    for (const m of s.matchAll(/add_api_route\(\s*["']([^"']+)["']/g)) flag(m[1], '라우트')
    // 마운트·include_router 의 첫 인자가 경로인 경우
    for (const m of s.matchAll(/\.(?:mount|include_router)\(\s*["']([^"']+)["']/g)) {
      flag(m[1], '마운트')
    }
    for (const m of s.matchAll(/add_parser\(\s*["']([^"']+)["']/g)) {
      const step = CLI_STEP[m[1]]
      if (step) found.push({ step, what: `CLI ${m[1]}`, file: p })
    }
    if (/^\s*(?:from|import)\s+mcp\b/m.test(s)) {
      found.push({ step: 8, what: 'MCP SDK import', file: p })
    }
  }

  for (const hit of found) {
    const open = (gates.get(hit.step) || []).filter((q) => !resolved.has(q))
    if (open.length) {
      const names = open.map((q) => 'Q' + q).join('·')
      fail(
        `${hit.file} : ${hit.what} 는 ${hit.step}단계인데 ${names} 가 아직 열려 있다 ` +
          `(${planPath} §7). 먼저 결정하고 ADR 에 기록한다.`
      )
    }
  }
}

// 10. 산문에 박힌 테스트 수치.
//     2026-08-31 감사: 잘못된 주장 9건이 **전부 숫자**였고 행위 주장은 하나도 틀리지 않았다.
//     숫자는 검사가 늘 때마다 낡는데 아무도 다시 세지 않는다 — 이번 세션에서만 세 번 고쳤다.
//     이력으로 인용하려면 백틱 안에 넣는다. 코드 스팬·펜스는 검사 8과 같은 이유로 제외한다.
const NUMBER_CLAIMS = [
  [/\d+\s*(tests?\s*)?passed/, 'N passed'],
  [/\d+\s*(tests?\s*)?skipped/, 'N skipped'],
  [/skip\s*0\b/, 'skip 0'],
  // 단위를 **필수**로 둔다. 선택으로 두면 "단계 2 통과", "2026-08-31 통과", "Q26 통과" 까지 잡는다.
  // 대신 단위 없는 "114 통과" 는 빠져나간다 — 이건 부분 문자열 목록이지 증명이 아니다 (AGENTS).
  [/\d+\s*(개|건|종|tests?)\s*통과/, 'N종 통과'],
  [/주입\s*\d+\s*종/, '주입 N종'],
]
for (const p of md) {
  const { prose } = stripCode(readFileSync(join(ROOT, p), 'utf8'))
  for (const [pattern, label] of NUMBER_CLAIMS) {
    const hit = pattern.exec(prose)
    if (hit) {
      fail(
        `${p} : 산문에 테스트 수치 "${hit[0].trim()}" (${label}) — 검사가 늘면 낡는다. ` +
          '규칙만 적거나, 이력이면 백틱 안에 넣는다.'
      )
    }
  }
}

// 11. 폐기된 문구.
//     감사에서 3위 부류였던 "수리 미전파" — 정본을 고치고 사본에 옛 문장을 남기는 것이다.
//     검사 6(구 파일명)과 같은 방식이다. 문구를 바꿔 고쳤으면 옛 문구를 여기 등록한다.
const RETIRED = [
  ['같은 구조다', 'D6 유추 (ingest 는 별도 프로세스다)'],
  ['업무 라우트는 아직 없다', '4단계에서 라우트가 생겼다'],
  ['업무 라우트가 없으므로', '4단계에서 라우트가 생겼다'],
  // "--wait" 까지 포함해야 한다. "고친 후 다시 돌린다" 같은 정상 문장을 잡으면 안 된다.
  ['--wait 후 다시 돌린다', '거짓 skip 사유 (그 명령은 5432 를 게시하지 않는다)'],
  ['이 오버라이드가 필요 없어진다', 'sillok ingest 가 아직 없다'],
  ['-p no:warnings', '증거 명령은 pytest -q 로 통일했다'],
  // 코드 스팬은 stripCode 가 지우므로 백틱 없는 조각을 고른다.
  ['front matter 존재와', 'D29 가 루트 README* 를 반대로 뒤집었다 (있으면 실패)'],
  ['변경 파일 목록 또는 repo 경로', 'D30 이 요청 본문을 CLI 인자와 같게 좁혔다'],
  ['해시 비교 후 변경분만 임베딩', 'D31 이 백필을 마지막 패스로 정했다'],
  ['예약. v1은 발신하지 않는다', 'D32 가 CONFLICT 의 첫 발신자를 만들었다'],
  ['권장 청크: 헤딩 우선', 'D30 이 청크 경계를 계약으로 정했다'],
  ['가능하면 RRF로 합친다', 'D33 이 병합을 계약으로 정했다'],
  ['병합 방식 미정', 'D33 이 Q8 을 닫았다'],
  ['남은 집합에 벡터/키워드', 'D34: v1 이벤트는 키워드만이다'],
  ['나중에 만들어도 된다', 'HNSW 를 만들지 않는 결정은 D33 이 소유한다'],
  // 순차 머지가 남긴 현재형 거짓말. 게이트가 초록인 채로 방문자 README 가 거짓을 말했다.
  ['is stage 6 and is not built yet', '6단계는 구현됐다'],
  ['검색 자체는 6단계이고 아직 없습니다', '6단계는 구현됐다'],
  ['1–5단계를 이제 검증할 수 있다', '1–6단계다'],
  ['지금은 그 명령이 없다', 'sillok ingest 는 5단계에서 생겼다'],
  ['Q9는 그대로 열려 있다', 'D34 가 닫았다'],
  ['v1의 유일한 발신자', 'D38 의 base_hash 불일치가 CONFLICT 의 둘째 발신자다'],
  // 7단계가 구현되면서 낡은 문장들. 같은 부류가 6단계에서 이미 한 번 났다 —
  // 게이트는 초록인데 방문자 문서가 현재형으로 거짓을 말한다.
  ['업무 라우트는 여섯이다', '7단계에서 셋이 늘어 아홉이다'],
  ['1–6단계까지 구현돼 있고', '7단계가 구현됐다'],
  ['아직이다 — 그 경로는 정직하게 404다', 'get_file·save_doc 은 7단계에서 생겼다'],
  ['those routes honestly return 404', 'get_file·save_doc 은 7단계에서 생겼다'],
  ['그 형태로 도는지는 실행해 보지 않았다', 'compose exec api sillok ingest 는 2026-09-02 에 확인했다'],
  // 8단계가 붙으면서 낡은 문장들.
  ['1–7단계까지 구현돼 있고', '8단계가 구현됐다'],
  ['MCP 경로는 정직하게 404다', 'POST /mcp 가 생겼다'],
  ['아직이다 — 도구 표면 자체가 없다', 'MCP 도구 여덟이 생겼다'],
  ['Not yet — the tool surface does not exist', 'MCP 도구 여덟이 생겼다'],
  ['MCP는 아직 없고', '8단계가 구현됐다'],
  // 9단계가 붙으면서 낡은 문장들.
  ['1–8단계까지 구현돼 있고', '9단계가 구현됐다'],
  ['9단계 전까지 0', 'kb_query_logs 에 이제 행이 쌓인다'],
  ['5·9단계 전이라', '9단계는 구현됐다'],
  // 10단계가 붙으면서 낡은 문장들.
  ['1–9단계까지 구현돼 있고', '10단계가 구현됐다'],
  ['이 블록은 **v1 목표**이지 현재 상태가 아니다', '2026-09-03 에 여섯 줄을 다 돌렸다'],
  // D48–D52 가 9단계 계약을 세우면서 낡은 문장들. 이번에도 정본을 고치고 사본이 남을 뻔했다
  // (Grok 적대 리뷰가 잡았다) — 고친 그 커밋에서 등록한다.
  // 문장 시작만 잡으면 `남은 단계 게이트는 없다` 같은 참인 문장도 문다 (Grok 재검토).
  // 취소선으로 남긴 `마지막 단계 게이트…` 는 등록할 수 없다 — 파일에 그대로 있어 자기가 자기를 문다.
  ['남은 단계 게이트는 **8단계의 Q17** 하나다', 'D52 가 9단계 게이트를 세웠다가 닫았다'],
  ['그 7단계를 검증하다 열렸고 아직 답이 없다', 'Q31 은 D47 이 닫았다'],
  ['ADR에 D42 이후로 기록한다', '다음 번호는 D54 이다'],
  ['D47 이후로 기록해야 할', '다음 번호는 D54 이다'],
  ['D33 이후로 기록하고', '다음 번호는 D54 이다'],
  ['D53 이후로', '다음 번호는 D54 이다'],
  ['구현이 다 됐다는 뜻이 아니다', '2026-09-03 에 열 단계가 다 구현됐다'],
  // (e) 드리프트 정리에서 바꾼 문장들. 전부 정본이 먼저 바뀌고 사본이 남아 있던 자리다.
  ['exposes the JSON API only', 'MCP 도구 여덟도 출구다'],
  ['JSON API만 있습니다', 'MCP 도구 여덟도 출구다'],
  // 접두사로 등록하면 참인 반대 문장(`… PATH 에 넣는다`)까지 문다 — 이 파일이 위에서
  // 경고하는 그 함정이다 (Grok 재검토). `넣지 않는다` 까지 포함한다.
  ['가상환경 경로를 PATH 에 넣지 않는다', '2026-09-02 에 고쳤고 지금은 그대로 돈다'],
  ['project -> 경로 매핑은 아직 미정이다', 'D37 이 Q20 을 닫았다 — 매핑은 만들지 않는다'],
  ['기준일 2026-08-30', 'SKILL 은 그 뒤로 두 번 더 고쳤다'],
  // 이 둘은 등록할 수 없다 — 취소선으로 ADR 에 그대로 남겨 두었고, RETIRED 는 코드 스팬만
  // 비켜 가므로 자기가 자기를 문다. D42–D46 의 `마지막 단계 게이트` 와 같은 자리다.
  // 날짜 자체는 참이다. 거짓인 것은 목록이 거기서 끝난다는 것이다 (Grok 재검토).
  ['D35–D41은 2026-09-02 확정. 임의로 뒤집지 않는다', 'D42–D46 도 같은 날이고 D47–D52 가 뒤에 있다'],
]
const textish = all.filter(
  (p) =>
    !p.startsWith('scripts/') && // 목록 자체를 들고 있는 파일
    /\.(md|py|yml|yaml|toml|example|sql)$|(^|\/)Dockerfile$/.test(p)
)
for (const p of textish) {
  // 문서에서는 폐기된 문구를 **인용**할 수 있어야 한다 — 왜 폐기했는지 적으려면 그 말을 써야 한다.
  // 검사 8·10 과 같은 규칙으로 코드 스팬 **과 코드 블록**을 제외한다.
  // 즉 펜스 안에 넣으면 잡히지 않는다. 옛 설정을 예시로 보여 주려면 그렇게 한다.
  // 코드 파일(.py 등)은 마크다운이 아니므로 그대로 본다.
  const raw = readFileSync(join(ROOT, p), 'utf8')
  const s = p.endsWith('.md') ? stripCode(raw).prose : raw
  for (const [phrase, why] of RETIRED) {
    if (s.includes(phrase)) fail(`${p} : 폐기된 문구 "${phrase}" — ${why}`)
  }
}

// 12. 루트 README* 는 front matter 를 갖지 않는가 (D29).
//     GitHub 이 최상단 front matter 를 4행 표로 렌더해 제목보다 위에 얹는다 — 공개 얼굴에 잡음이다.
//     검사 3 이 이 부류를 건너뛰므로 반대 방향은 여기서만 지킨다. 예외만 뚫고 끝내면
//     누군가 되살렸을 때 게이트가 초록불로 통과시키고 첫 화면에 표가 돌아온다.
const readmes = indexed.filter(isRootReadme)
if (readmes.length === 0) fail('루트 README* 가 색인 대상에 없다. D9 패턴이 깨졌다.')
for (const p of readmes) {
  if (FRONT_MATTER.test(readFileSync(join(ROOT, p), 'utf8'))) {
    fail(`${p} : front matter 가 있다 — GitHub 이 최상단에 표로 렌더한다 (D29). 지운다.`)
  }
}

// 13. pg_trgm 을 쓰지 않는가 (D34).
//     확장은 선언돼 있지만 v1 은 쓰지 않기로 정했다 — `%` 는 기본 임계값에서 인덱스를 타고
//     전량을 recheck 로 버려 0건을 돌려주고, `%>` 는 경계를 SQL 이 아니라 세션 GUC 가 정한다.
//     **쓰지 않기로 한 선언은 검사가 없으면 다음 사람이 조용히 쓴다.**
//     인덱스가 실제로 들어올 자리는 migrations/ 다 — 거기를 안 보면 이 검사가 헛돈다.
//     스키마에 trgm 인덱스가 0개라는 것은 DB 검사가 따로 본다. 여기는 소스 쪽이다.
const TRGM = [
  ['gin_trgm_ops', 'trgm 인덱스 연산자 클래스'],
  ['gist_trgm_ops', 'trgm 인덱스 연산자 클래스'],
  ['similarity(', 'trgm 유사도 함수'],
  ['word_similarity(', 'trgm 유사도 함수'],
  ['pg_trgm.', 'trgm GUC'],
]
const trgmish = all.filter(
  (p) => (p.startsWith('src/') && p.endsWith('.py')) || (p.startsWith('migrations/') && p.endsWith('.sql'))
)
for (const p of trgmish) {
  const body = readFileSync(join(ROOT, p), 'utf8')
  for (const [needle, what] of TRGM) {
    // 001 은 확장을 설치하는 파일이다. 설치 자체는 D34 가 남기기로 한 것이라 세지 않는다.
    if (body.includes(needle)) fail(`${p} : ${what} "${needle}" — pg_trgm 은 v1 미사용이다 (D34)`)
  }
}

// 14. "1–N단계를 이제 검증할 수 있다" — 세 곳이 같은 N 을 말하고, 그 N 이 Q 게이트와 맞는가.
//     순차 머지가 남기는 부류다: 단계가 하나 늘 때 세 문서 중 하나만 고치면
//     게이트는 초록인 채로 방문자 문서가 옛 단계를 말한다. 실측으로 한 번 났다 —
//     plan 과 CLAUDE 는 1–5, open-questions 는 1–6 이었다.
//
//     **셋의 일치만 보는 것으로는 부족하다.** 단계가 늘 때는 셋을 한 번에 훑어 고치므로
//     셋이 같이 틀린 N 을 말하는 쪽이 오히려 흔하고, 그때 일치 검사는 초록불을 준다.
//     그래서 N 을 Q 게이트에서 **유도해** 맞춰 본다 (verifiableThrough). 사실은 한 곳에만 있다:
//     어떤 Q 가 어느 단계를 막는지는 plan.md §7 이, 그 Q 가 닫혔는지는 open-questions.md 가 소유한다.
//     이 검사는 그 둘에서 나오는 값을 세 문서의 문장과 대조할 뿐 자기 답을 갖지 않는다.
const STAGE_CLAIM = /1[–-](\d+)단계를 이제 검증할 수 있다/g
const STAGE_CLAIM_FILES = ['docs/plan.md', 'CLAUDE.md', 'docs/open-questions.md']
const stageClaims = []
for (const p of STAGE_CLAIM_FILES) {
  // 없는 파일에서 던지면 **앞선 검사들이 모은 보고가 통째로 사라진다** — 화면에는 스택만 남는다.
  // 게이트는 무엇이 틀렸는지 말하고 끝나야 한다 (고장 주입 34 가 이 자리를 드러냈다).
  if (!existsSync(join(ROOT, p))) { fail(`${p} : 없다 — 단계 주장을 대조할 수 없다.`); continue }
  // 펜스·코드 스팬은 검사 8·10·11 과 같은 이유로 뺀다 — 예시로 옛 문장을 보여 줄 수 있어야 한다.
  // 빼지 않으면 인용 하나가 N 을 정하고, 산문의 진짜 주장이 가려진다.
  const { prose } = stripCode(readFileSync(join(ROOT, p), 'utf8'))
  // 한 파일에 두 벌이 있을 수 있다. 첫 개만 보면 위만 고치고 아래를 잊는 길이 열린다.
  const claims = [...prose.matchAll(STAGE_CLAIM)].map((m) => Number(m[1]))
  if (!claims.length) {
    fail(`${p} : "1–N단계를 이제 검증할 수 있다" 문장이 없다 — 셋이 함께 움직여야 한다.`)
    continue
  }
  const distinct = [...new Set(claims)]
  if (distinct.length > 1) {
    fail(`${p} : 한 파일 안에서 단계 주장이 갈린다 — ${distinct.map((n) => '1–' + n).join(', ')}`)
    continue
  }
  stageClaims.push([p, distinct[0]])
}
if (
  stageClaims.length === STAGE_CLAIM_FILES.length && // 아래에서 늘어나기 **전**이다
  new Set(stageClaims.map((s) => s[1])).size !== 1
) {
  fail(
    '단계 주장이 어긋난다 — ' +
      stageClaims.map(([p, n]) => `${p}=1–${n}`).join(', ') +
      ' (정본은 docs/plan.md §7)'
  )
}
// 세 문서 **밖에서도** 같은 주장을 할 수 있다. 거기까지 보지 않으면
// "네 번째 파일이 옛 단계를 말한다" 가 그대로 남는다. 필수는 셋이고, 나머지는 발견되면 검사한다.
for (const p of md) {
  if (STAGE_CLAIM_FILES.includes(p)) continue
  const { prose } = stripCode(readFileSync(join(ROOT, p), 'utf8'))
  for (const n of new Set([...prose.matchAll(STAGE_CLAIM)].map((m) => Number(m[1])))) {
    stageClaims.push([p, n])
  }
}

// 셋이 같아도 그 값이 틀릴 수 있다. Q 게이트가 유도한 값과 맞춘다.
for (const [p, n] of stageClaims) {
  if (verifiableThrough !== null && n !== verifiableThrough) {
    fail(
      `${p} : 1–${n}단계라고 하는데 Q 게이트로는 1–${verifiableThrough}단계다 ` +
        `(${stageReason}). 문장이 아니라 Q 를 먼저 본다.`
    )
  }
}

// 15. 두 walk 이 같은 목록을 건너뛰는가 (D47).
//     게이트는 JS 이고 ingest 는 파이썬이라 코드로 공유할 수 없다. 정본은 ADR 이고
//     두 구현이 그것을 따르는데, **지금까지 그 둘을 대조하는 것이 아무것도 없었다.**
//     `check-index-parity.mjs` 는 D9 필터를 통과한 뒤의 목록을 비교하므로 원리상 이 갈라짐을 못 본다 —
//     건너뛴 디렉터리 안의 파일은 양쪽 모두에서 애초에 목록에 없다.
const ingestPath = 'src/sillok/ingest.py'
if (!existsSync(join(ROOT, ingestPath))) {
  // 파일이 없다고 넘어가면 D47 이 조용히 강제되지 않는다 (Grok 재검토).
  fail(`${ingestPath} : 없다 — D47 의 두 walk 을 대조할 수 없다.`)
} else {
  const py = readFileSync(join(ROOT, ingestPath), 'utf8')
  // 대입이 둘이면 어느 쪽이 사는지 여기서 알 수 없다 — 주석 처리된 옛 대입이 위에 있으면
  // 첫 개만 읽고 통과할 수 있다. 그 자체를 실패로 본다.
  const hits = [...py.matchAll(/_SKIP_DIRS\s*(?::[^=\n]*)?=\s*(?:frozenset\()?\{([^}]*)\}/g)]
  if (hits.length !== 1) {
    fail(
      `${ingestPath} : _SKIP_DIRS 대입을 ${hits.length}개 찾았다 (하나여야 한다) — ` +
        'D47 의 두 walk 을 대조할 수 없다.'
    )
  } else {
    const m = hits[0]
    const theirs = new Set([...m[1].matchAll(/"([^"]+)"|'([^']+)'/g)].map((x) => x[1] ?? x[2]))
    const mine = SKIP_DIRS
    const onlyMine = [...mine].filter((d) => !theirs.has(d))
    const onlyTheirs = [...theirs].filter((d) => !mine.has(d))
    if (onlyMine.length || onlyTheirs.length) {
      fail(
        `D47 두 walk 의 건너뛰기 목록이 갈라졌다 — 게이트만: [${onlyMine}] · ingest 만: [${onlyTheirs}]`
      )
    }
  }
}

// 16. 두 README 가 구조적으로 갈라지지 않는가 (D27 · D29).
//     영문이 정본이고 한국어가 사본인데 **그 둘을 대조하는 것이 아무것도 없었다.**
//     본문을 번역 대조할 수는 없으므로 *구조*를 본다 — `##`·`###` 수, 표 수, 표 행 수, 펜스 수.
//     **문단까지 세지는 않는다.** conventions.md 의 "산문 블록 수" 요구를 이 검사가 다 덮지는 못한다.
const READMES = ['README.md', 'README.ko.md']
if (READMES.every((p) => existsSync(join(ROOT, p)))) {
  const shape = (p) => {
    const s = readFileSync(join(ROOT, p), 'utf8')
    // 깊이를 눌러 세면 `###` 하나가 `##` 로 올라가고 다른 하나가 사라져도 총합이 같다.
    // 표의 **구분 행**(`|---|`)은 행 수가 아니라 표 개수를 세는 것이라 따로 뺀다.
    const lines = s.split(/\r?\n/)
    return {
      h2: lines.filter((l) => /^##\s/.test(l)).length,
      h3: lines.filter((l) => /^###\s/.test(l)).length,
      tables: lines.filter((l) => /^\|[\s\-:|]+\|\s*$/.test(l)).length,
      rows: lines.filter((l) => /^\|/.test(l) && !/^\|[\s\-:|]+\|\s*$/.test(l)).length,
      fences: lines.filter((l) => l.startsWith('```')).length,
    }
  }
  const [en, ko] = READMES.map(shape)
  for (const k of ['h2', 'h3', 'tables', 'rows', 'fences']) {
    if (en[k] !== ko[k]) {
      fail(
        `두 README 의 구조가 갈라졌다 — ${k}: README.md=${en[k]} vs README.ko.md=${ko[k]}. ` +
          '영문이 정본이다 (D27).'
      )
    }
  }
}


console.log(`색인 대상 ${indexed.length}개`)
for (const p of indexed) console.log(`  ${p}`)
console.log(`제외 확인   ${MUST_EXCLUDE.join(', ')}`)
console.log(`FM 없음     ${readmes.join(', ')}`)
console.log(`doc_type    ${JSON.stringify(seen.doc_type)}`)
console.log(`status      ${JSON.stringify(seen.status)}`)
console.log(`상대 링크   ${links}개`)

if (problems.length) {
  console.error(`\n실패 ${problems.length}건:`)
  for (const p of problems) console.error(`  - ${p}`)
  process.exit(1)
}
console.log('\n배치 검증 통과')
