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

import { cpSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SKIP = new Set(['.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache'])
const NL = String.fromCharCode(10)   // 백슬래시 리터럴을 앵커로 쓰지 않기 위한 상수
const F3 = '`'.repeat(3)
const F4 = '`'.repeat(4)
// 지금 저장소가 말하는 단계. 박아 두면 단계가 늘 때마다 여기가 낡아 주입이 헛돈다
// (실제로 D35–D38 때 그렇게 됐다). 값이 아니라 **다르게 만드는 것**이 주입의 요점이다.
const STAGE_NOW = Number(
  /1–(\d+)단계를 이제 검증할 수 있다/.exec(readFileSync(join(ROOT, 'docs/plan.md'), 'utf8'))[1]
)
const claim = (n) => `1–${n}단계를 이제 검증할 수 있다`
const CLAIM_NOW = claim(STAGE_NOW)
const CLAIM_OFF = claim(STAGE_NOW + 1)   // 어긋난 주장. RETIRED 와 겹치지 않는 쪽으로 고른다

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
const remove = (...rels) => (dir) => {
  for (const rel of rels) rmSync(join(dir, rel), { recursive: true, force: true })
}

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
    // 7단계(Q12·Q15·Q19·Q20)가 D35–D38 로 닫히면서 이 라우트는 더 이상 막히지 않는다.
    // 케이스 10·11 과 같은 형태로 바꾼다 — Q 를 다시 열어 게이트가 문서를 따라가는지 본다.
    id: '09 Q19 를 다시 열면 7단계 라우트가 막힌다',
    expect: 'fail',
    mentions: ['7단계', 'Q19', '/v1/files'],
    mutate: (dir) => {
      // Q19 를 다시 열면 7단계 표면이 전부 막힌다 (같은 단계의 Q 하나만 열려도 막는다).
      edit(dir, 'docs/open-questions.md', (t) => t.replace(' — **해결 → D36**', ''))
      write('src/sillok/_probe.py', '@app.get("/v1/files")' + NL + 'def s(): pass' + NL)(dir)
    },
  },
  {
    // 반대 방향. 닫힌 단계의 표면은 통과해야 한다 (10b · 11b 와 같은 이유).
    id: '09b 7단계 라우트는 이제 통과한다',
    expect: 'pass',
    mutate: write('src/sillok/_probe.py', '@app.get("/v1/files")' + NL + 'def s(): pass' + NL),
  },
  {
    // 6단계(Q8·Q9)가 D33–D34 로 닫히면서 검색 라우트는 더 이상 막히지 않는다.
    // 케이스 11 과 같은 형태로 바꾼다 — Q 를 다시 열어 게이트가 문서를 따라가는지 본다.
    id: '10 Q8 을 다시 열면 6단계 라우트가 막힌다',
    expect: 'fail',
    mentions: ['6단계', 'Q8', '/v1/search/docs'],
    mutate: (dir) => {
      edit(dir, 'docs/open-questions.md', (s) => s.replace(' — **해결 → D33**', ''))
      write('src/sillok/_probe.py', '@app.post("/v1/search/docs")' + NL + 'def s(): pass' + NL)(dir)
    },
  },
  {
    id: '10b 6단계 라우트는 이제 통과한다',
    expect: 'pass',
    mutate: write('src/sillok/_probe.py', '@app.post("/v1/search/docs")' + NL + 'def s(): pass' + NL),
  },
  {
    // 5단계(Q6·Q7·Q10)가 D30–D32 로 닫히면서 ingest 는 더 이상 막히지 않는다.
    // CLI_STEP 에는 ingest 하나뿐이라 이제 그 분기가 막는 단계가 없다 —
    // 그래서 **Q 를 다시 열어** 분기가 살아 있는지 본다. 게이트가 문서를 따라간다는 증거다.
    // 메타 케이스를 두지 않는다. 5단계가 구현되면서 src 에 /v1/ingest 가 생겼으므로
    // Q6 를 다시 열면 CLI 분기를 꺼도 HTTP 분기가 문다 — 분리가 성립하지 않는다.
    // 대신 아래 mentions 의 `CLI ingest` 가 그 자리를 잠근다: 분기가 죽으면 그 문구가 없어
    // 이 케이스가 BAD 로 떨어진다.
    id: '11 Q6 를 다시 열면 CLI ingest 가 막힌다',
    expect: 'fail',
    mentions: ['5단계', 'Q6', 'CLI ingest'],
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
    // 8단계(Q17)가 D42–D46 으로 닫히면서 이 import 는 더 이상 막히지 않는다.
    // 케이스 09·10·11 과 같은 형태로 바꾼다 — Q 를 다시 열어 게이트가 문서를 따라가는지 본다.
    id: '12 Q17 을 다시 열면 8단계 MCP import 가 막힌다',
    expect: 'fail',
    mentions: ['8단계', 'Q17'],
    mutate: (dir) => {
      edit(dir, 'docs/open-questions.md', (t) => t.replace('— **해결 → D42–D46.**', ''))
      write('src/sillok/_probe.py', 'from mcp import server' + NL)(dir)
    },
  },
  {
    // 반대 방향. 닫힌 단계의 표면은 통과해야 한다 (09b · 10b · 11b 와 같은 이유).
    id: '12b 8단계 MCP import 는 이제 통과한다',
    expect: 'pass',
    mutate: write('src/sillok/_probe.py', 'from mcp import server' + NL),
  },
  {
    // CLI 분기도 8단계를 안다 (D45). Q 를 다시 열어 그 분기가 살아 있는지 본다.
    id: '12c Q17 을 다시 열면 CLI mcp 가 막힌다',
    expect: 'fail',
    mentions: ['8단계', 'Q17', 'CLI mcp'],
    mutate: (dir) => {
      edit(dir, 'docs/open-questions.md', (t) => t.replace('— **해결 → D42–D46.**', ''))
      write('src/sillok/_probe.py', 'sub.add_parser("mcp")' + NL)(dir)
    },
  },
  {
    id: '13 APIRouter(prefix) + 상대 경로',
    expect: 'fail',
    mentions: ['7단계', 'Q19', '/v1/files'],
    mutate: (dir) => {
      // Q19 를 다시 열면 7단계 표면이 전부 막힌다 (같은 단계의 Q 하나만 열려도 막는다).
      edit(dir, 'docs/open-questions.md', (t) => t.replace(' — **해결 → D36**', ''))
      write(
        'src/sillok/_probe.py',
        'router = APIRouter(prefix="/v1")' + NL + NL + '@router.get("/files")' + NL + 'def s(): pass' + NL
      )(dir)
    },
  },
  {
    // /v1/search/* 는 6단계라 이제 안 막힌다. 같은 문법을 아직 막힌 단계로 옮긴다.
    id: '14 include_router(prefix=) + 상대 경로',
    expect: 'fail',
    mentions: ['7단계', 'Q19', '/v1/docs/proposals'],
    mutate: (dir) => {
      // Q19 를 다시 열면 7단계 표면이 전부 막힌다 (같은 단계의 Q 하나만 열려도 막는다).
      edit(dir, 'docs/open-questions.md', (t) => t.replace(' — **해결 → D36**', ''))
      write(
        'src/sillok/_probe.py',
        'app.include_router(r, prefix="/v1")' + NL + NL + '@r.post("/docs/proposals")' + NL + 'def s(): pass' + NL
      )(dir)
    },
  },
  {
    id: '15 path= 키워드 인자',
    expect: 'fail',
    mentions: ['7단계', 'Q19', '/v1/events/'],
    mutate: (dir) => {
      // Q19 를 다시 열면 7단계 표면이 전부 막힌다 (같은 단계의 Q 하나만 열려도 막는다).
      edit(dir, 'docs/open-questions.md', (t) => t.replace(' — **해결 → D36**', ''))
      write('src/sillok/_probe.py', '@app.get(path="/v1/events/1")' + NL + 'def s(): pass' + NL)(dir)
    },
  },
  {
    id: '16 add_api_route',
    expect: 'fail',
    mentions: ['7단계', 'Q19', '/v1/files'],
    mutate: (dir) => {
      // Q19 를 다시 열면 7단계 표면이 전부 막힌다 (같은 단계의 Q 하나만 열려도 막는다).
      edit(dir, 'docs/open-questions.md', (t) => t.replace(' — **해결 → D36**', ''))
      write('src/sillok/_probe.py', 'app.add_api_route("/v1/files", h)' + NL)(dir)
    },
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
    // D47. 가상환경은 우리 문서가 아니다 — 서드파티의 끊긴 링크로 게이트가 붉어졌던 자리다.
    // 복사본에는 .venv 가 없으므로 여기서 만들어 넣는다.
    id: '25e .venv 안의 깨진 링크는 무시한다',
    expect: 'pass',
    mutate: (dir) => {
      mkdirSync(join(dir, '.venv/pkg'), { recursive: true })
      writeFileSync(
        join(dir, '.venv/pkg/NOTICE.md'),
        '# 서드파티' + NL + '[없는 파일](../../License.txt)' + NL,
        'utf8'
      )
    },
  },
  {
    // 그 건너뛰기가 실제로 무는지. 목록에서 .venv 를 빼면 같은 주입이 붉어져야 한다.
    id: '25f 건너뛰기를 끄면 그 링크가 걸린다',
    expect: 'fail',
    mentions: ['끊긴 링크'],
    mutate: (dir) => {
      mkdirSync(join(dir, '.venv/pkg'), { recursive: true })
      writeFileSync(
        join(dir, '.venv/pkg/NOTICE.md'),
        '# 서드파티' + NL + '[없는 파일](../../License.txt)' + NL,
        'utf8'
      )
      edit(dir, 'scripts/check-layout.mjs', (s) => s.replace("'.venv', ", ''))
    },
  },
  {
    // 7단계가 구현되면서 낡은 문장. 6단계에서 이미 한 번 난 부류라 문구마다 등록한다.
    id: '25c 7단계가 폐기한 "아직 404" 문구',
    expect: 'fail',
    mentions: ['폐기된 문구', 'get_file'],
    mutate: append('docs/spec.md', NL + '아직이다 — 그 경로는 정직하게 404다' + NL),
  },
  {
    // 영문 README 만 낡는 부류. 한국어 쪽을 고치고 저쪽을 잊는 것이 실제로 났다.
    id: '25d 영문 README 의 폐기 문구',
    expect: 'fail',
    mentions: ['폐기된 문구', 'those routes honestly return 404'],
    mutate: append('docs/spec.md', NL + 'Not yet — those routes honestly return 404' + NL),
  },
  {
    // D34 는 확장을 선언만 하고 쓰지 않기로 정했다. 검사가 없으면 다음 사람이 조용히 쓴다.
    // 인덱스가 실제로 들어올 자리는 migrations/ 라 거기까지 본다.
    id: '26b migrations 에 trgm 인덱스가 들어오면 운다',
    expect: 'fail',
    mentions: ['pg_trgm 은 v1 미사용', 'gin_trgm_ops'],
    mutate: write('migrations/900_probe.sql', 'CREATE INDEX x ON t USING gin (c gin_trgm_ops);' + NL),
  },
  {
    id: '26c src 에 trgm 유사도 함수가 들어와도 운다',
    expect: 'fail',
    mentions: ['pg_trgm 은 v1 미사용'],
    mutate: write('src/sillok/_probe.py', 'SQL = "select similarity(a,b)"' + NL),
  },
  {
    // 단계가 하나 늘 때 세 문서 중 하나만 고치면 게이트가 초록인 채로 옛 단계를 말한다.
    // 실측으로 한 번 났다 — plan 과 CLAUDE 는 1–5, open-questions 는 1–6 이었다.
    // **1–5 로 주입하지 않는다.** 그 문자열은 RETIRED 에도 있어 검사 11 이 함께 운다 —
    // 검사 14 를 통째로 지워도 붉은불이 유지되고, 그러면 이 케이스는 아무것도 증명하지 않는다.
    id: '27b 단계 주장이 세 문서에서 어긋나면 운다',
    expect: 'fail',
    mentions: ['단계 주장이 어긋난다', 'docs/plan.md'],
    mutate: (dir) =>
      edit(dir, 'CLAUDE.md', (s) => s.replace(CLAIM_NOW, CLAIM_OFF)),
  },
  {
    id: '27c 그 문장이 사라져도 운다',
    expect: 'fail',
    mentions: ['문장이 없다'],
    mutate: (dir) =>
      edit(dir, 'docs/open-questions.md', (s) => s.replace(CLAIM_NOW, '')),
  },
  {
    // 가장 흔한 실수는 하나만 고치는 것이 아니라 **셋을 한 번에 틀리게 고치는 것**이다.
    // 일치만 보는 검사는 여기서 초록불을 준다. Q 게이트에서 N 을 유도하는 이유다.
    // 막는 Q 가 남아 있을 때는 사유가 "n단계를 막는 Q" 이고, 다 풀린 뒤에는
    // "하나도 남지 않았다" 다. 사유 문구를 박지 않는다 — 박으면 Q 가 닫힐 때마다 낡는다.
    id: '27d 셋이 사이좋게 틀린 단계를 말해도 운다',
    expect: 'fail',
    mentions: [`Q 게이트로는 1–${STAGE_NOW}단계다`, '문장이 아니라 Q 를 먼저 본다'],
    mutate: (dir) => {
      for (const f of ['docs/plan.md', 'CLAUDE.md', 'docs/open-questions.md']) {
        edit(dir, f, (s) => s.replaceAll(CLAIM_NOW, CLAIM_OFF))
      }
    },
  },
  {
    // 첫 개만 보면 위만 고치고 아래를 잊는 길이 열린다. 한 파일 안의 불일치도 결함이다.
    id: '27e 한 파일 안에서 두 벌이 갈리면 운다',
    expect: 'fail',
    mentions: ['한 파일 안에서 단계 주장이 갈린다'],
    mutate: append('docs/plan.md', NL + '옛 문장: 1–4단계를 이제 검증할 수 있다.' + NL),
  },
  {
    // 마지막 Q 가 닫히는 날 유도가 멈추면(예전 코드) 검사의 절반이 조용히 은퇴하고
    // "셋이 사이좋게 틀림" 이 다시 통과한다. Q17 이 닫히는 순간 — v1 이 끝나기 전이다.
    // Q 가 다 풀린 지금은 반대 방향으로 주입한다 — 주장을 한 단계 **내리면** 운다.
    // (예전에는 열린 Q 를 전부 닫아 주장이 낮은 것을 드러냈다. 이제는 그것이 기본 상태다.)
    id: '27g Q 가 다 풀렸는데 주장이 낮으면 운다',
    expect: 'fail',
    mentions: ['Q 게이트로는 1–10단계다', '막는 Q 가 하나도 남지 않았다'],
    mutate: (dir) => {
      for (const f of ['docs/plan.md', 'CLAUDE.md', 'docs/open-questions.md']) {
        edit(dir, f, (s) => s.replaceAll(CLAIM_NOW, claim(STAGE_NOW - 1)))
      }
    },
  },
  {
    // 마지막 단계를 §7 의 번호 목록에서 읽는다. 목록을 못 읽으면 N 을 정할 수 없는데
    // 조용히 넘기면 틀린 N 이 강요된다 — 파싱 실패 자체를 결함으로 본다 (Q 게이트와 같은 규칙).
    id: '27h §7 번호 목록이 어긋나면 운다',
    expect: 'fail',
    mentions: ['번호 목록을 읽지 못했다'],
    mutate: (dir) =>
      edit(dir, 'docs/plan.md', (t) => t.replace(NL + '9. `kb_query_logs` 기록', NL + '11. `kb_query_logs` 기록')),
  },
  {
    // 최대값과 개수만 보면 이것이 빠져나간다: 10 이 사라지고 9 가 둘이면
    // 개수도 최대값도 9 라서 이어져 보이는데, N 이 조용히 하나 작아진다.
    id: '27i §7 마지막 번호가 하나 내려가도 운다',
    expect: 'fail',
    mentions: ['번호 목록을 읽지 못했다'],
    mutate: (dir) =>
      edit(dir, 'docs/plan.md', (t) => t.replace(NL + '10. 스모크', NL + '9. 스모크')),
  },
  {
    // lastStep 은 **막힌 단계가 없을 때만** 쓰인다. 펜스만 주입하면 그 가지에 닿지 못하고
    // stripCode 를 빼도 초록이다 — 실측으로 확인했다. Q 를 전부 닫아 그 가지로 들어간 뒤에 본다.
    // 기대 메시지가 1–10 인 것이 요점이다: 펜스 안의 11 을 세면 1–11 이 되고 이 케이스가 운다.
    // 펜스 안의 `11.` 이 세어지면 게이트가 1–11 을 요구한다. 세지 않으므로 1–10 을 요구하고,
    // 주장을 1–11 로 올려 둔 이 복사본은 **그 차이 때문에** 운다.
    id: '27j §7 펜스 안의 번호는 마지막 단계로 세지 않는다',
    expect: 'fail',
    mentions: ['Q 게이트로는 1–10단계다'],
    mutate: (dir) => {
      edit(dir, 'docs/plan.md', (t) =>
        t.replace(NL + '10. 스모크', NL + '10. 스모크' + NL + NL + F3 + 'text' + NL + '11. 예시일 뿐이다' + NL + F3)
      )
      for (const f of ['docs/plan.md', 'CLAUDE.md', 'docs/open-questions.md']) {
        edit(dir, f, (s) => s.replaceAll(CLAIM_NOW, CLAIM_OFF))
      }
    },
  },
  {
    // 세 문서 밖의 네 번째 파일이 옛 단계를 말하는 부류. 필수는 셋이지만 검사는 셋에서 끝나지 않는다.
    id: '27k 세 문서 밖에서 옛 단계를 말해도 운다',
    expect: 'fail',
    mentions: ['docs/spec.md', `Q 게이트로는 1–${STAGE_NOW}단계다`],
    mutate: append('docs/spec.md', NL + '옛 문장: ' + claim(4) + '.' + NL),
  },
  {
    // 펜스 안의 인용은 주장이 아니다. 빼지 않으면 예시 하나가 N 을 정한다.
    id: '27f 코드 펜스 안의 옛 문장은 주장으로 세지 않는다',
    expect: 'pass',
    mutate: append('CLAUDE.md', NL + F3 + 'text' + NL + '1–4단계를 이제 검증할 수 있다' + NL + F3 + NL),
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

  // --- 주입이 없던 검사들. 통과 출력만 보고 살아 있다고 믿던 자리다 ---
  {
    // 검사 1. 이전 배치의 실제 실패 모드다 — D9 패턴에 걸리는 문서가 하나도 없는 상태.
    id: '34 색인 대상이 0개면 운다',
    expect: 'fail',
    mentions: ['색인 대상이 0개다'],
    mutate: remove('docs', 'adr', 'README.md', 'README.ko.md'),
  },
  {
    // 검사 2. 이름이 같으면 어디 있든 색인되면 안 된다 (docs/CLAUDE.md 같은 사본).
    id: '35 색인 밖 이름이 색인 경로에 나타나면 운다',
    expect: 'fail',
    mentions: ['색인 대상이 아니어야 하는데'],
    mutate: write('docs/CLAUDE.md', FM + '# 사본'),
  },
  {
    // 검사 2 의 다른 갈래. 있어야 할 파일이 사라진 것도 잡아야 한다.
    id: '36 색인 밖 파일이 아예 없어지면 운다',
    expect: 'fail',
    mentions: ['AGENTS.md 가 없다'],
    mutate: remove('AGENTS.md'),
  },
  {
    // 검사 3 의 taxonomy 갈래.
    id: '37 doc_type 이 taxonomy 밖이면 운다',
    expect: 'fail',
    mentions: ['taxonomy 밖'],
    mutate: (dir) => edit(dir, 'docs/spec.md', (t) => t.replace('doc_type: other', 'doc_type: 없는종류')),
  },
  {
    // 검사 3 의 status 갈래. doc_type 과 다른 enum 이라 따로 민다.
    id: '38 status 가 enum 밖이면 운다',
    expect: 'fail',
    mentions: ['가 enum 밖'],
    mutate: (dir) => edit(dir, 'docs/spec.md', (t) => t.replace('status: current', 'status: 없는상태')),
  },
  {
    // 검사 3 의 module 갈래. 값은 null 이어도 되지만 **키는 있어야 한다.**
    id: '39 module 키가 없으면 운다',
    expect: 'fail',
    mentions: ['module 키 없음'],
    mutate: (dir) => edit(dir, 'docs/spec.md', (t) => t.replace('module: null', '')),
  },
  {
    // 검사 5. 색인은 되는데 진입점에서 못 닿는 문서 — 고아다.
    id: '40 진입점에서 못 닿는 문서가 생기면 운다',
    expect: 'fail',
    mentions: ['도달 불가'],
    mutate: write('docs/orphan.md', FM + '# 고아'),
  },
  {
    // 검사 6. 재배선 전의 파일명이 되살아나는 것.
    id: '41 구 파일명 참조가 되살아나면 운다',
    expect: 'fail',
    mentions: ['구 파일명'],
    mutate: append('docs/spec.md', NL + '옛 이름 01-SPEC 을 다시 가리킨다.' + NL),
  },
  {
    // 검사 7 의 연속성 갈래. 번호가 끊기면 다른 문서의 참조가 조용히 허공을 가리킨다.
    id: '42 Q 번호가 끊기면 운다',
    expect: 'fail',
    mentions: ['번호가 연속되지 않는다'],
    mutate: (dir) => edit(dir, 'docs/open-questions.md', (t) => t.replace('**Q2. ', '**Q2 ')),
  },
  {
    // 검사 9 의 파싱 갈래. 문장은 있는데 못 읽으면 Q 게이트가 조용히 비어도 통과한다.
    id: '43 §7 게이트 문장을 읽지 못하면 운다',
    expect: 'fail',
    mentions: ['건만 읽었다'],
    mutate: (dir) => edit(dir, 'docs/plan.md', (t) => t.replace('9단계 전에 Q32', '9단계 전에 Q없음')),
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
    id: 'M7 검사 14(단계 주장)를 끄면 어긋난 단계가 통과한다',
    disable: (s) => s.replace('for (const p of STAGE_CLAIM_FILES) {', 'for (const p of []) {'),
    inject: (dir) =>
      edit(dir, 'CLAUDE.md', (s) => s.replace(CLAIM_NOW, CLAIM_OFF)),
  },
  {
    // 앞의 줄바꿈이 **필수**다. 같은 문자열이 검사 2 안에도 들여쓰기된 채 있고
    // String.replace 는 첫 개를 잡는다 — 열 0 의 검사 3 만 끄려면 \n 을 붙여야 한다.
    id: 'M6 검사 3(front matter 필수)을 끄면 docs 문서의 결손이 통과한다',
    disable: (s) => s.replace('\nfor (const p of indexed) {', '\nfor (const p of []) {'),
    inject: dropFM('docs/spec.md'),
  },
  {
    id: 'M8 검사 4(끊긴 링크)를 끄면 끊긴 링크가 통과한다',
    disable: (s) => s.replace('if (!existsSync(resolve(ROOT, dirname(p), t))) fail(', 'if (false) fail('),
    inject: append('docs/spec.md', NL + '[없는 것](./아무데도-없다.md)' + NL),
  },
  {
    id: 'M9 검사 7(Q 참조)을 끄면 없는 Q 참조가 통과한다',
    disable: (s) => s.replace('if (!defined.has(n)) fail(', 'if (false) fail('),
    inject: append('docs/spec.md', NL + '없는 Q999 를 가리킨다.' + NL),
  },

  // **34·35·36·42 에는 메타가 없다.** 문서를 들어내거나 파일을 지우면 다른 검사도 함께 운다 —
  // 그 트리에서는 "이 검사 때문에 운다" 를 분리할 수 없기 때문이다. `mentions` 로 그 검사가
  // 실제로 울었다는 것까지는 잠근다. 분리할 수 있는 37·38·39·40·41 에는 메타를 붙였다.
  {
    id: 'M11 검사 3(taxonomy)을 끄면 doc_type 주입이 통과한다',
    disable: (s) => s.replace(NL + 'for (const p of indexed) {', NL + 'for (const p of []) {'),
    inject: (dir) => edit(dir, 'docs/spec.md', (t) => t.replace('doc_type: other', 'doc_type: 없는종류')),
  },
  {
    id: 'M12 검사 3(status)을 끄면 status 주입이 통과한다',
    disable: (s) => s.replace(NL + 'for (const p of indexed) {', NL + 'for (const p of []) {'),
    inject: (dir) => edit(dir, 'docs/spec.md', (t) => t.replace('status: current', 'status: 없는상태')),
  },
  {
    id: 'M13 검사 3(module 키)을 끄면 module 주입이 통과한다',
    disable: (s) => s.replace(NL + 'for (const p of indexed) {', NL + 'for (const p of []) {'),
    inject: (dir) => edit(dir, 'docs/spec.md', (t) => t.replace('module: null', '')),
  },
  {
    id: 'M14 검사 5(도달성)를 끄면 고아 문서가 통과한다',
    disable: (s) =>
      s.replace('for (const p of indexed) if (!reach.has(p)) fail(', 'for (const p of []) if (!reach.has(p)) fail('),
    inject: write('docs/orphan.md', FM + '# 고아'),
  },
  {
    id: 'M15 검사 6(구 파일명)을 끄면 옛 이름이 통과한다',
    disable: (s) => s.replace('if (s.includes(k)) fail(', 'if (false) fail('),
    inject: append('docs/spec.md', NL + '옛 이름 01-SPEC 을 다시 가리킨다.' + NL),
  },
  {
    id: 'M10 검사 13(pg_trgm)을 끄면 trgm 사용이 통과한다',
    disable: (s) => s.replace('for (const [needle, what] of TRGM) {', 'for (const [needle, what] of []) {'),
    inject: append('src/sillok/search.py', NL + '# gin_trgm_ops' + NL),
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
