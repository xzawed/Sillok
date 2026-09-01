#!/usr/bin/env node
// check-layout.mjs 의 검사가 실제로 무는지 확인한다.
//
// 왜 있나: 통과 출력만으로는 검사가 살아 있는지 알 수 없다 (AGENTS.md).
// 실제로 Q 게이트는 고장 주입으로만 드러난 결함을 3건 갖고 나갔었다 —
// 다음 단계의 숫자를 먹는 파싱, 주석 오검출, 문장을 지워도 침묵.
// 그때 쓴 하네스가 저장소 밖에 있어 아무도 재현할 수 없었다. 그래서 커밋한다.
//
// 어떻게: 저장소를 임시 디렉토리로 복사하고 **복사본에** 고장을 주입한다.
// 추적 파일을 건드리지 않으므로 중간에 죽어도 작업 트리가 더러워지지 않는다.
// 복사본 안의 scripts/check-layout.mjs 를 돌리면 ROOT 가 복사본으로 잡힌다.
//
// 사용: node scripts/check-layout.test.mjs

import { cpSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SKIP = new Set(['.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache'])
const NL = String.fromCharCode(10)   // 백슬래시 리터럴을 앵커로 쓰지 않기 위한 상수
const F3 = '`'.repeat(3)
const F4 = '`'.repeat(4)

function copyRepo() {
  const dest = mkdtempSync(join(tmpdir(), 'sillok-layout-'))
  cpSync(ROOT, dest, { recursive: true, filter: (src) => !SKIP.has(basename(src)) })
  return dest
}

function run(dir) {
  try {
    const out = execFileSync('node', [join(dir, 'scripts', 'check-layout.mjs')], {
      cwd: dir,
      encoding: 'utf8',
      // stderr 를 명시하지 않으면 execFileSync 는 자식의 stderr 를 **부모에게도 흘린다.**
      // 주입한 고장이 전부 화면에 쏟아져 정작 OK/BAD 줄이 묻힌다. 잡기만 하고 흘리지 않는다.
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    return { code: 0, out }
  } catch (e) {
    return { code: e.status ?? 1, out: (e.stdout || '') + (e.stderr || '') }
  }
}

// 치환이 빗나가면 파일이 그대로다. 그러면 "고장을 주입했다" 는 전제가 거짓인데
// 케이스는 조용히 통과한다 — 문서 문구가 바뀌면 정확히 그렇게 된다.
const edit = (dir, rel, fn) => {
  const p = join(dir, rel)
  const before = readFileSync(p, 'utf8')
  const after = fn(before)
  if (after === before) throw new Error(`주입이 아무것도 바꾸지 못했다: ${rel}`)
  writeFileSync(p, after, 'utf8')
}
const append = (rel, text) => (dir) => edit(dir, rel, (s) => s + text)
const prepend = (rel, text) => (dir) => edit(dir, rel, (s) => text + s)
const write = (rel, text) => (dir) => writeFileSync(join(dir, rel), text, 'utf8')

// 검사 12 가 지우게 한 바로 그 덩어리. 되살려 넣는 것이 주입이다 (D29).
const FM = '---\ntitle: X\ndoc_type: readme\nstatus: current\nmodule: null\n---\n\n'
const dropFM = (rel) => (dir) =>
  edit(dir, rel, (s) => s.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, ''))

// expect: 'pass' | 'fail'. mentions: 실패 메시지에 반드시 들어가야 하는 조각들.
const CASES = [
  // 0. 대조군. 이게 깨지면 아래 "fail" 단언은 전부 무의미하다.
  { id: '00 무손상 복사본', expect: 'pass', mutate: () => {} },

  // --- 검사 8·9: 지시어와 펜스 ---
  {
    id: '01 산문 속 "이 PR"',
    expect: 'fail',
    mentions: ['지시어', '이 PR'],
    mutate: append('docs/spec.md', '\n이 PR은 세 층 구조를 확정했다.\n'),
  },
  {
    id: '02 조사 변형 "이 변경은"',
    expect: 'fail',
    mentions: ['지시어', '이 변경'],
    mutate: append('docs/spec.md', '\n이 변경은 비목표를 정리했다.\n'),
  },
  {
    id: '03 코드 스팬 인용은 잡지 않는다',
    expect: 'pass',
    mutate: append('docs/spec.md', '\n금지 예시: `이 PR` 은 쓰지 않는다.\n'),
  },
  {
    id: '04 닫히지 않은 펜스',
    expect: 'fail',
    mentions: ['닫히지 않은 코드 펜스'],
    mutate: append('docs/spec.md', `\n${F3}\n열린 채 끝난다\n`),
  },
  {
    id: '05 정상 펜스 뒤 산문 위반',
    expect: 'fail',
    mentions: ['지시어', '이 커밋'],
    mutate: append('docs/spec.md', `\n${F3}\n코드\n${F3}\n\n산문: 이 커밋에서 고쳤다.\n`),
  },
  {
    id: '06 4중 백틱이 안쪽 3중에 닫히지 않는다',
    expect: 'pass',
    mutate: append('docs/spec.md', `\n${F4}\n${F3}\n이 PR 은 쓰지 않는다\n${F3}\n${F4}\n`),
  },
  {
    id: '07 ~~~ 펜스 안 인용',
    expect: 'pass',
    mutate: append('docs/spec.md', '\n~~~\n이 PR 은 쓰지 않는다\n~~~\n'),
  },

  // --- 검사 7: 존재하지 않는 Q ---
  {
    id: '08 없는 Q 번호 참조',
    expect: 'fail',
    mentions: ['존재하지 않는'],
    mutate: append('docs/spec.md', '\n자세한 것은 Q99 를 본다.\n'),
  },

  // --- 검사 9: Q 게이트 ---
  {
    // 케이스는 **아직 막혀 있는** 단계의 표면을 써야 한다.
    // 4단계(Q16·Q18·Q21)가 D23–D25로 닫히면서 /v1/status 는 더 이상 막히지 않는다.
    // 게이트가 문서를 따라간다는 증거이기도 하다.
    id: '09 7단계 라우트',
    expect: 'fail',
    mentions: ['7단계', 'Q12', 'Q15', 'Q19', 'Q20'],
    mutate: write('src/sillok/_probe.py', '@app.get("/v1/files")\ndef s(): pass\n'),
  },
  {
    id: '10 6단계 라우트',
    expect: 'fail',
    mentions: ['6단계', 'Q8', 'Q9'],
    mutate: write('src/sillok/_probe.py', '@app.post("/v1/search/docs")\ndef s(): pass\n'),
  },
  {
    // 5단계(Q6·Q7·Q10)가 D30–D32 로 닫히면서 ingest 는 더 이상 막히지 않는다.
    // CLI_STEP 에는 ingest 하나뿐이라 이제 그 분기가 막는 단계가 없다 —
    // 그래서 **Q 를 다시 열어** 분기가 살아 있는지 본다. 게이트가 문서를 따라간다는 증거다.
    id: '11 Q6 를 다시 열면 CLI ingest 가 막힌다',
    expect: 'fail',
    mentions: ['5단계', 'Q6'],
    mutate: (dir) => {
      edit(dir, 'docs/open-questions.md', (s) => s.replace(' — **해결 → D30**', ''))
      write('src/sillok/_probe.py', 'sub.add_parser("ingest")' + NL)(dir)
    },
  },
  {
    // 반대 방향. 닫힌 단계의 표면은 통과해야 한다 —
    // 안 그러면 게이트가 문서를 따라가는 것이 아니라 그냥 막는 것이다.
    id: '11b 5단계 CLI ingest 는 이제 통과한다',
    expect: 'pass',
    mutate: write('src/sillok/_probe.py', 'sub.add_parser("ingest")' + NL),
  },
  {
    id: '12 8단계 MCP import',
    expect: 'fail',
    mentions: ['8단계', 'Q17'],
    mutate: write('src/sillok/_probe.py', 'from mcp import server\n'),
  },
  {
    id: '13 APIRouter(prefix) + 상대 경로',
    expect: 'fail',
    mentions: ['7단계', '/v1/files'],
    mutate: write(
      'src/sillok/_probe.py',
      'router = APIRouter(prefix="/v1")\n\n@router.get("/files")\ndef s(): pass\n'
    ),
  },
  {
    // /v1/ingest 는 5단계라 이제 안 막힌다. 같은 문법을 아직 막힌 단계로 옮긴다.
    id: '14 include_router(prefix=) + 상대 경로',
    expect: 'fail',
    mentions: ['6단계', '/v1/search/docs'],
    mutate: write(
      'src/sillok/_probe.py',
      'app.include_router(r, prefix="/v1")' + NL + NL + '@r.post("/search/docs")' + NL + 'def s(): pass' + NL
    ),
  },
  {
    id: '15 path= 키워드 인자',
    expect: 'fail',
    mentions: ['6단계', '/v1/search/events'],
    mutate: write('src/sillok/_probe.py', '@app.get(path="/v1/search/events")\ndef s(): pass\n'),
  },
  {
    id: '16 add_api_route',
    expect: 'fail',
    mentions: ['7단계', '/v1/files'],
    mutate: write('src/sillok/_probe.py', 'app.add_api_route("/v1/files", h)\n'),
  },
  {
    id: '17 주석에만 있는 경로는 잡지 않는다',
    expect: 'pass',
    mutate: write(
      'src/sillok/_probe.py',
      '# 7단계에서 @app.get("/v1/files") 를 붙인다\nX = "/v1/ingest"\n'
    ),
  },
  {
    id: '18 Q 를 닫으면 같은 라우트가 통과한다',
    expect: 'pass',
    mutate: (dir) => {
      write('src/sillok/_probe.py', '@app.get("/v1/files")\ndef s(): pass\n')(dir)
      edit(dir, 'docs/open-questions.md', (s) => {
        for (const q of [12, 15, 19, 20]) {
          s = s.replace(new RegExp(`(\\*\\*Q${q}\\.[^\\n]*)`), '$1 — **해결 → D99**')
        }
        return s
      })
    },
  },
  {
    id: '19 §7 게이트 문장을 통째로 지우면 운다',
    expect: 'fail',
    // "문장을 하나도 찾지 못했다" 를 콕 집는다. 단계별 메시지만 남아도 통과하면 안 된다.
    mentions: ['문장을 하나도 찾지 못했다'],
    mutate: (dir) =>
      edit(dir, 'docs/plan.md', (s) =>
        s.replace(/남은 공백은 단계별로 걸린다 —[\s\S]*?필요하다\./, '남은 공백이 있다.')
      ),
  },
  {
    id: '20 한 단계 절만 지워도 운다',
    expect: 'fail',
    mentions: ['5단계 게이트 문장이 없다'],
    mutate: (dir) =>
      edit(dir, 'docs/plan.md', (s) => s.replace(', 5단계 전에 Q6·Q7·Q10', '')),
  },

  // --- 검사 10: 산문에 박힌 테스트 수치 ---
  {
    id: '21 산문 속 "N passed"',
    expect: 'fail',
    mentions: ['테스트 수치', 'passed'],
    mutate: append('docs/spec.md', '\n검사 결과는 42 passed 였다.\n'),
  },
  {
    id: '22 산문 속 "skip 0"',
    expect: 'fail',
    mentions: ['테스트 수치'],
    mutate: append('docs/spec.md', '\n머지 근거는 skip 0 이었다.\n'),
  },
  {
    id: '23 백틱 안 수치는 이력이므로 잡지 않는다',
    expect: 'pass',
    mutate: append('docs/spec.md', '\n당시 수치는 `42 passed, 7 skipped` 였다.\n'),
  },
  {
    id: '23b 산문 속 "N skipped" (passed 없이)',
    expect: 'fail',
    mentions: ['테스트 수치', 'skipped'],
    mutate: append('docs/spec.md', '\n그때는 7 skipped 였다.\n'),
  },
  {
    id: '23c 산문 속 "N종 통과"',
    expect: 'fail',
    mentions: ['테스트 수치'],
    mutate: append('docs/spec.md', '\n검사는 26종 통과했다.\n'),
  },
  {
    id: '23d 숫자 없는 "통과" 는 잡지 않는다',
    expect: 'pass',
    mutate: append('docs/spec.md', '\n배치 검증 통과가 전제다.\n'),
  },
  {
    // 단위를 선택으로 두면 이런 정상 문장이 전부 붉은불이 된다.
    id: '23e 단위 없는 "단계 2 통과" · 날짜 · Q번호는 잡지 않는다',
    expect: 'pass',
    mutate: append(
      'docs/spec.md',
      '\n단계 2 통과가 조건이다. 2026-08-31 통과였고 Q26 통과로 적었다.\n'
    ),
  },

  // --- 검사 11: 폐기된 문구 ---
  {
    id: '24 폐기 문구가 문서에 되살아나면 운다',
    expect: 'fail',
    mentions: ['폐기된 문구', '같은 구조다'],
    mutate: append('docs/spec.md', '\n예전에는 같은 구조다 라고 적었다.\n'),
  },
  {
    id: '25 폐기 문구가 코드 주석에 되살아나도 운다',
    expect: 'fail',
    mentions: ['폐기된 문구'],
    mutate: write('src/sillok/_probe.py', '# 업무 라우트는 아직 없다\n'),
  },
  {
    // D32 가 CONFLICT 의 첫 발신자를 만들었다. 옛 문구가 어딘가에 되살아나면 계약이 갈라진다.
    id: '25b D32 가 폐기한 CONFLICT 문구',
    expect: 'fail',
    mentions: ['폐기된 문구', 'D32'],
    mutate: append('docs/spec.md', NL + 'CONFLICT 는 예약. v1은 발신하지 않는다.' + NL),
  },
  {
    id: '26 문서에서 백틱으로 인용하는 것은 허용한다',
    expect: 'pass',
    // 왜 폐기했는지 적으려면 그 말을 써야 한다.
    mutate: append('docs/spec.md', '\n예전 문구 `같은 구조다` 는 쓰지 않는다.\n'),
  },

  // --- 검사 12: 루트 README* 의 front matter (D29) ---
  {
    id: '27 루트 README 에 front matter 가 되살아나면 운다',
    expect: 'fail',
    // 파일명만 인용하면 통과 출력의 색인 목록에도 있어 아무것도 증명하지 못한다.
    mentions: ['README.md : front matter 가 있다', 'D29'],
    mutate: prepend('README.md', FM),
  },
  {
    id: '28 한국어 사본도 같이 본다',
    expect: 'fail',
    mentions: ['README.ko.md : front matter 가 있다'],
    mutate: prepend('README.ko.md', FM),
  },
  {
    // 검사 3 에 뚫은 예외가 docs/** 까지 새면 이 케이스가 조용히 통과한다.
    // D29 가 만드는 유일한 새 실패 모드다.
    id: '29 docs 문서의 front matter 는 여전히 필수다',
    expect: 'fail',
    mentions: ['docs/spec.md : front matter 없음'],
    mutate: dropFM('docs/spec.md'),
  },
  {
    // GitHub 의 여는 울타리는 `---` 뒤 공백·탭을 허용한다. 좁게 잡으면 게이트는 통과하는데
    // 첫 화면에는 표가 뜬다 — 검사 12 가 막으려던 바로 그 상태다.
    id: '30 여는 울타리 뒤 공백이 붙어도 잡는다',
    expect: 'fail',
    mentions: ['README.md : front matter 가 있다'],
    mutate: prepend('README.md', FM.replace('---\n', '--- \n')),
  },
  {
    id: '31 선행 BOM 이 붙어도 잡는다',
    expect: 'fail',
    mentions: ['README.md : front matter 가 있다'],
    mutate: prepend('README.md', '﻿' + FM),
  },
  // 아래 둘은 **한 번에 하나씩만** 어긋나게 한다. 둘을 겹치면 어느 쪽 때문에
  // 통과했는지 고립되지 않아 한쪽 규칙이 느슨해져도 초록불이 유지된다.
  {
    id: '32 빈 첫 줄이 앞서면 front matter 가 아니다 (GitHub 도 그렇다)',
    expect: 'pass',
    mutate: prepend('README.md', '\n' + FM),
  },
  {
    id: '33 네 줄표는 front matter 가 아니다 (GitHub 도 그렇다)',
    expect: 'pass',
    mutate: prepend('README.md', FM.replace('---\n', '----\n')),
  },
]

// 메타 케이스: **이 케이스가 정말 그 검사 때문에 실패하는가.**
// 검사를 끄고 같은 고장을 주입했을 때 통과해야 한다. 여전히 실패하면
// 그 케이스는 다른 검사에 걸려 "엉뚱한 이유로" 붉은불이 켜졌던 것이다.
const CHECKER = 'scripts/check-layout.mjs'
const META = [
  {
    id: 'M1 검사 9(Q 게이트)를 끄면 라우트 주입이 통과한다',
    disable: (s) => s.replace('for (const hit of found) {', 'for (const hit of []) {'),
    inject: write('src/sillok/_probe.py', '@app.get("/v1/files")\ndef s(): pass\n'),
  },
  {
    id: 'M2 검사 10(수치)을 끄면 수치 주입이 통과한다',
    disable: (s) =>
      s.replace('for (const [pattern, label] of NUMBER_CLAIMS) {', 'for (const [pattern, label] of []) {'),
    inject: append('docs/spec.md', '\n검사 결과는 42 passed 였다.\n'),
  },
  {
    id: 'M3 검사 11(폐기 문구)을 끄면 폐기 문구가 통과한다',
    disable: (s) =>
      s.replace('for (const [phrase, why] of RETIRED) {', 'for (const [phrase, why] of []) {'),
    inject: append('docs/spec.md', '\n예전에는 같은 구조다 라고 적었다.\n'),
  },
  {
    id: 'M4 검사 8(지시어)을 끄면 지시어 주입이 통과한다',
    disable: (s) => s.replace('for (const d of DEICTIC) {', 'for (const d of []) {'),
    inject: append('docs/spec.md', '\n이 PR은 그것을 고쳤다.\n'),
  },
  {
    id: 'M5 검사 12(루트 README front matter)를 끄면 주입이 통과한다',
    disable: (s) => s.replace('for (const p of readmes) {', 'for (const p of []) {'),
    inject: prepend('README.md', FM),
  },
  {
    // 앞의 줄바꿈이 **필수**다. 같은 문자열이 검사 2 안에도 들여쓰기된 채 있고
    // String.replace 는 첫 개를 잡는다 — 열 0 의 검사 3 만 끄려면 \n 을 붙여야 한다.
    id: 'M6 검사 3(front matter 필수)을 끄면 docs 문서의 결손이 통과한다',
    disable: (s) => s.replace('\nfor (const p of indexed) {', '\nfor (const p of []) {'),
    inject: dropFM('docs/spec.md'),
  },
]

let failures = 0
for (const c of CASES) {
  const dir = copyRepo()
  try {
    try {
      c.mutate(dir)
    } catch (e) {
      // 주입이 실패하면 그 케이스만 BAD 로 두고 나머지는 계속 돌린다.
      failures++
      console.log(`BAD  ${c.id}  주입 실패: ${e.message}`)
      continue
    }
    const { code, out } = run(dir)
    // 대조군이 깨지면 아래 "fail" 단언은 이미 실패하는 복사본에 얹히는 것이라
    // 아무것도 증명하지 못한다. 즉시 멈춘다.
    if (c.id.startsWith('00') && code !== 0) {
      console.log('BAD  00 무손상 복사본이 이미 실패한다. 이후 케이스는 의미가 없다.')
      console.log(out)
      process.exit(1)
    }
    const got = code === 0 ? 'pass' : 'fail'
    let ok = got === c.expect
    const missing = []
    if (ok && c.expect === 'fail') {
      for (const m of c.mentions || []) {
        if (!out.includes(m)) {
          ok = false
          missing.push(m)
        }
      }
    }
    if (!ok) failures++
    console.log(`${ok ? 'OK  ' : 'BAD '} ${c.id}  기대=${c.expect} 실제=${got}`)
    if (!ok) {
      if (missing.length) console.log(`       메시지에 없음: ${missing.join(', ')}`)
      for (const line of out.split('\n').filter((l) => l.trim().startsWith('-')).slice(0, 4)) {
        console.log('       ' + line.trim())
      }
    }
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

for (const m of META) {
  const dir = copyRepo()
  try {
    // 검사를 끄는 것 자체가 실패하면(문구가 바뀌었으면) 조용히 넘어가면 안 된다.
    edit(dir, CHECKER, m.disable)
    m.inject(dir)
    const { code, out } = run(dir)
    const ok = code === 0
    if (!ok) failures++
    console.log(`${ok ? 'OK  ' : 'BAD '} ${m.id}`)
    if (!ok) {
      console.log('       검사를 껐는데도 실패한다 — 그 케이스는 다른 검사에 걸리고 있었다.')
      for (const line of out.split('\n').filter((l) => l.trim().startsWith('-')).slice(0, 3)) {
        console.log('       ' + line.trim())
      }
    }
  } catch (e) {
    failures++
    console.log(`BAD  ${m.id}  검사를 끄지 못했다: ${e.message}`)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

console.log(
  failures === 0
    ? `\n고장 주입 ${CASES.length}종 + 메타 ${META.length}종 전부 기대와 일치`
    : `\n불일치 ${failures}건`
)
process.exit(failures === 0 ? 0 : 1)
