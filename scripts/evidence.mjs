#!/usr/bin/env node
// PR 하나의 증거를 한 번에 만든다 (AGENTS.md `PR 하나의 증거`).
//
// 왜 있나: 2026-08-31 감사에서 PR #5~#10 이 요구된 증거 4종 중 1~3종만 싣고 머지됐다.
// 그 뒤로 항목이 늘었다 — 개수를 여기 적지 않는다. 늘 때마다 낡는다.
// 빠뜨린 것을 아무도 알아채지 못한 이유는 명령을 손으로 따로 돌렸기 때문이다.
// 하나라도 못 돌리면 **여기서 실패한다.** 조용히 빠지는 길을 남기지 않는다.
//
// 사용: node scripts/evidence.mjs
// 출력: PR 본문에 그대로 붙이는 블록.

import { execFileSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

// 마지막 요약 줄만 뽑는다. 통과 개수와 skip 개수가 함께 보여야 한다 (AGENTS).
const STEPS = [
  {
    name: '문서 게이트',
    cmd: ['node', ['scripts/check-layout.mjs']],
    summary: (out) => lastMatch(out, /배치 검증 통과|실패 \d+건/),
  },
  {
    name: '게이트 자체 (고장 주입)',
    cmd: ['node', ['scripts/check-layout.test.mjs']],
    // 대조군에서 중단되면 "불일치" 줄이 없다. 그 경로도 잡아야 요약이 비지 않는다.
    summary: (out) => lastMatch(out, /전부 기대와 일치|불일치 \d+건|무손상 복사본이 이미 실패한다/),
  },
  {
    name: '호스트 테스트',
    cmd: ['uv', ['run', 'pytest', '-q']],
    // 전부 skip 된 실행은 "N passed" 줄이 없다. skipped 만 있는 줄도 잡아야
    // 요약이 비지 않는다 — 요약이 비면 아래에서 실패로 본다.
    summary: (out) => lastMatch(out, /\d+ (passed|failed|skipped|error)[^\n]*/),
    note: 'DB 검사는 skip 된다. skip 0 이면 5432 가 게시된 것이다 (D16)',
  },
  {
    name: 'DB 포함 테스트 (D22)',
    // `-rs` 로 skip **사유**를 찍게 한다. 개수로는 판정할 수 없다 — 아래 주석 참고.
    cmd: [
      'docker',
      ['compose', '--profile', 'test', 'run', '--rm', 'test',
       'uv', 'run', '--no-sync', 'pytest', '-q', '-rs'],
    ],
    summary: (out) => lastMatch(out, /\d+ (passed|failed|skipped|error)[^\n]*/),
  },
  {
    // 스모크 자신은 살아 있는 api 를 요구하므로 여기 없다 (D53).
    // **그 스모크가 무는지 보는 주입은 여기 있다** — DB 도 도커도 필요 없다.
    name: '스모크 주입 (D53)',
    cmd: ['node', ['scripts/smoke.test.mjs']],
    summary: (out) => lastMatch(out, /전부 기대와 일치|불일치 \d+건/),
  },
  {
    // 게이트와 ingest 가 같은 집합을 보는가 (D30). 규칙이 두 언어에 있어
    // 단위 검사로는 대조할 수 없다 — 둘 다 실제로 돌려 맞춘다.
    name: '색인 목록 대조 (D30)',
    cmd: ['node', ['scripts/check-index-parity.mjs']],
    summary: (out) => lastMatch(out, /색인 대상 \d+개가 게이트와 같다|색인 목록 불일치/),
    note: '저장소 자신을 대상으로 도는 첫 ingest 스모크다 (자기 색인)',
  },
]

function lastMatch(text, pattern) {
  const hits = text.split('\n').filter((l) => pattern.test(l))
  return hits.length ? hits[hits.length - 1].trim() : null
}

function runStep(step) {
  const [bin, args] = step.cmd
  try {
    const out = execFileSync(bin, args, {
      cwd: ROOT,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    const line = step.summary(out)
    // 명령이 0 으로 끝나도 **요약을 못 뽑으면 증거가 아니다.** 통과로 적지 않는다.
    if (!line) {
      return { ok: false, line: '종료 코드 0 이지만 요약 줄을 찾지 못했다 — 증거로 쓸 수 없다' }
    }
    return { ok: true, line, out }
  } catch (e) {
    if (e.code === 'ENOENT') {
      return { ok: false, line: `실행 불가 — \`${bin}\` 을 찾을 수 없다`, missing: true }
    }
    const out = (e.stdout || '') + (e.stderr || '')
    return { ok: false, line: step.summary(out) || `종료 코드 ${e.status}`, out }
  }
}

const results = STEPS.map((step) => ({ step, ...runStep(step) }))

// Q26 이 막으려던 실패 모드: **DB 검사가 전부 skip 됐는데 통과로 적히는 것.**
// 종료 코드만 보면 그 상태가 PASS 다.
//
// **개수로는 판정할 수 없다.** 처음에는 두 단계의 passed/skipped 를 비교했는데,
// 이 저장소는 CI 가 없어 증거를 호스트에서 모으고 호스트는 Windows 이며 `test` 는 리눅스 이미지다.
// 그래서 DB 에 못 붙어도 posix 전용 검사들이 컨테이너에서 살아나 passed 가 오르고 skipped 가 내린다 —
// **잡으려던 상태가 그 부등식을 만족한다** (Grok 적대 리뷰가 이 자리를 깼다).
// 반대로 리눅스 호스트 + 5432 오버라이드에서는 두 쪽이 같아져 거짓 실패가 난다.
//
// **사유로 본다.** `dbcheck` 의 그 문구는 DB 에 못 붙었을 때만 나온다. 수치가 아니라 원인이다.
const DB_SKIP_REASON = 'Postgres 에 붙을 수 없다'
const withDb = results.find((r) => r.step.name.startsWith('DB 포함'))
if (withDb?.ok && (withDb.out || '').includes(DB_SKIP_REASON)) {
  withDb.ok = false
  withDb.line = `${withDb.line} — DB 검사가 skip 됐다. 그 실행은 D22 의 증거가 아니다 (Q26).`
}

console.log('## 검증 (실측)\n')
console.log('```text')
for (const { step, ok, line } of results) {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${step.name.padEnd(22)} ${line}`)
}
console.log('```')
for (const { step, ok } of results) {
  if (ok && step.note) console.log(`\n> ${step.name}: ${step.note}`)
}

const failed = results.filter((r) => !r.ok)
if (failed.length) {
  console.error(`\n증거 ${failed.length}종이 빠졌다. PR 본문에 위 목록이 다 있어야 한다 (AGENTS).`)
  for (const f of failed) {
    if (f.missing) {
      console.error(`  - ${f.step.name}: 도구가 없다. 빠뜨린 채 머지하지 않는다.`)
    }
  }
  process.exit(1)
}
