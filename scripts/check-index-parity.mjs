#!/usr/bin/env node
// 게이트가 세는 색인 대상과 ingest 가 실제로 먹는 것이 같은가 (D30).
//
// 왜 따로 있나: D30 의 `어겨지면 무엇이 비명을 지르는가` 표에서 확장자 필터 줄이
// `없다` 였다. 규칙이 두 언어에 있어(게이트는 node, ingest 는 python) 단위 검사로는
// 대조할 수 없고, 갈라지면 **게이트는 초록인데 색인은 비어 있는** 부류가 생긴다.
// 그래서 둘 다 실제로 돌려 목록을 맞춘다.
//
// 저장소 자신을 대상으로 도는 첫 ingest 스모크이기도 하다 (docs/conventions.md 자기 색인).
//
// 사용: node scripts/check-index-parity.mjs

import { execFileSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

// 게이트의 출력에서 색인 대상 목록만 뽑는다. 두 칸 들여쓴 줄이 그것이다.
function gateList() {
  const out = execFileSync('node', ['scripts/check-layout.mjs'], {
    cwd: ROOT,
    encoding: 'utf8',
  })
  const lines = out.split('\n')
  const start = lines.findIndex((l) => l.startsWith('색인 대상 '))
  if (start < 0) throw new Error('게이트 출력에서 색인 대상 줄을 찾지 못했다')
  const found = []
  for (const line of lines.slice(start + 1)) {
    if (!line.startsWith('  ')) break
    found.push(line.trim())
  }
  if (!found.length) throw new Error('게이트가 색인 대상을 하나도 내놓지 않았다')
  return found.sort()
}

// 컨테이너 안에서 ingest.scan 을 돌린다. 저장소를 workspace 로 마운트하되
// **커밋된 compose 는 바꾸지 않는다** — 이 마운트는 이 명령 한 번짜리다 (D28).
const PROBE = [
  'import sys, pathlib',
  'from sillok import ingest',
  'files, skipped = ingest.scan(pathlib.Path("/workspace"))',
  'print("\\n".join(f.path for f in files))',
].join('\n')

function ingestList() {
  const out = execFileSync(
    'docker',
    [
      'compose', '--profile', 'test', 'run', '--rm', '--no-deps',
      '-v', `${ROOT}:/workspace:ro`,
      'test', 'uv', 'run', '--no-sync', 'python', '-c', PROBE,
    ],
    { cwd: ROOT, encoding: 'utf8', env: { ...process.env, MSYS_NO_PATHCONV: '1' } },
  )
  return out
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('Container ') && !l.startsWith('sillok-'))
    .sort()
}

let gate
let mine
try {
  gate = gateList()
  mine = ingestList()
} catch (e) {
  console.error(`색인 목록 대조를 돌리지 못했다: ${e.message}`)
  process.exit(1)
}

const onlyGate = gate.filter((p) => !mine.includes(p))
const onlyIngest = mine.filter((p) => !gate.includes(p))

if (onlyGate.length || onlyIngest.length) {
  console.error('색인 목록 불일치')
  for (const p of onlyGate) console.error(`  게이트만: ${p}`)
  for (const p of onlyIngest) console.error(`  ingest 만: ${p}`)
  process.exit(1)
}

console.log(`색인 대상 ${gate.length}개가 게이트와 같다`)
