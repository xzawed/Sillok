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
const write = (rel, text) => (dir) => writeFileSync(join(dir, rel), text, 'utf8')

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
    id: '09 4단계 라우트',
    expect: 'fail',
    mentions: ['4단계', 'Q16', 'Q18', 'Q21'],
    mutate: write('src/sillok/_probe.py', '@app.get("/v1/status")\ndef s(): pass\n'),
  },
  {
    id: '10 6단계 라우트',
    expect: 'fail',
    mentions: ['6단계', 'Q8', 'Q9'],
    mutate: write('src/sillok/_probe.py', '@app.post("/v1/search/docs")\ndef s(): pass\n'),
  },
  {
    id: '11 5단계 CLI ingest',
    expect: 'fail',
    mentions: ['5단계', 'Q6', 'Q7', 'Q10'],
    mutate: write('src/sillok/_probe.py', 'sub.add_parser("ingest")\n'),
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
    mentions: ['4단계', '/v1/status'],
    mutate: write(
      'src/sillok/_probe.py',
      'router = APIRouter(prefix="/v1")\n\n@router.get("/status")\ndef s(): pass\n'
    ),
  },
  {
    id: '14 include_router(prefix=) + 상대 경로',
    expect: 'fail',
    mentions: ['4단계', '/v1/events'],
    mutate: write(
      'src/sillok/_probe.py',
      'app.include_router(r, prefix="/v1")\n\n@r.post("/events")\ndef s(): pass\n'
    ),
  },
  {
    id: '15 path= 키워드 인자',
    expect: 'fail',
    mentions: ['4단계', '/v1/stats/events'],
    mutate: write('src/sillok/_probe.py', '@app.get(path="/v1/stats/events")\ndef s(): pass\n'),
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
      '# 4단계에서 @app.get("/v1/status") 를 붙인다\nX = "/v1/events"\n'
    ),
  },
  {
    id: '18 Q 를 닫으면 같은 라우트가 통과한다',
    expect: 'pass',
    mutate: (dir) => {
      write('src/sillok/_probe.py', '@app.get("/v1/status")\ndef s(): pass\n')(dir)
      edit(dir, 'docs/open-questions.md', (s) => {
        for (const q of [16, 18, 21]) {
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

console.log(
  failures === 0
    ? `\n고장 주입 ${CASES.length}종 전부 기대와 일치`
    : `\n불일치 ${failures}건`
)
process.exit(failures === 0 ? 0 : 1)
