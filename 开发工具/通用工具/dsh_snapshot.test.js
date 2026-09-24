'use strict'
// 【项目沉淀】通用工具
// 适用素体：无关；相关素材：无；可复用性：★★★
// 用途：快照失败与派工闸口回归；只用临时目录和本地伪执行器，绝不调用 DSH 模型。
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')
const { captureSnapshot, compareSnapshotText } = require('./dsh_snapshot')

function inTemp(fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dsh-snapshot-test-'))
  try { return fn(dir) } finally { fs.rmSync(dir, { recursive: true, force: true }) }
}

function capture(command, dir, overrides = {}) {
  return captureSnapshot(command, { cwd: dir, file: path.join(dir, 'snapshot.txt'), phase: 'before', index: 0, ...overrides })
}

test('successful stdout is preserved; stderr never becomes snapshot data', () => inTemp(dir => {
  const result = capture("printf 'value=1\\n'; printf 'diagnostic\\n' >&2", dir)
  assert.equal(result.ok, true)
  assert.equal(result.stdout, 'value=1\n')
  assert.equal(fs.readFileSync(result.execution.file, 'utf8'), result.stdout)
  assert.equal(result.execution.stderr, 'diagnostic\n')
}))

for (const [name, command, options, check] of [
  ['nonzero exit', "printf 'partial\\n'; exit 7", {}, e => assert.equal(e.status, 7)],
  ['timeout', 'exec sleep 2', { timeout: 50 }, e => assert.equal(e.errorCode, 'ETIMEDOUT')],
  ['signal', 'kill -TERM $$', {}, e => assert.equal(e.signal, 'SIGTERM')],
  ['output truncation', "printf '%010240d' 0", { maxBuffer: 512 }, e => assert.equal(e.errorCode, 'ENOBUFS')],
]) {
  test(name + ' invalidates the snapshot', () => inTemp(dir => {
    const result = capture(command, dir, options)
    assert.equal(result.ok, false)
    assert.equal(result.execution.ok, false)
    check(result.execution)
  }))
}

test('snapshot persistence failure is fatal even when the command succeeds', () => inTemp(dir => {
  const result = capture('printf valid', dir, { file: dir })
  assert.equal(result.execution.status, 0)
  assert.equal(result.execution.persisted, false)
  assert.ok(result.execution.writeError)
  assert.equal(result.ok, false)
}))

test('comparison retains order, duplicate rows, and final newlines', () => {
  assert.equal(compareSnapshotText('a\nb\n', 'b\na\n').changed, true)
  assert.deepEqual(compareSnapshotText('a\na\n', 'a\n').removed, ['a'])
  assert.deepEqual(compareSnapshotText('a\n', 'a\na\n').added, ['a'])
  assert.equal(compareSnapshotText('a', 'a\n').changed, true)
  assert.equal(compareSnapshotText('a\na\n', 'a\na\n').changed, false)
})

// Run the real wrapper in an isolated copy. DSH_BIN points only to this local fixture,
// which writes a minimal completed session so unrelated verification can genuinely pass.
const fakeRunner = `
const fs = require('fs'), path = require('path'), os = require('os'), zlib = require('zlib');
fs.writeFileSync('runner-started', 'yes');
const mode = process.env.SNAPSHOT_TEST_MODE;
if (mode === 'change') fs.writeFileSync('state.txt', 'value=2\\n');
if (mode === 'reorder') fs.writeFileSync('state.txt', 'b\\na\\n');
if (mode === 'duplicate') fs.writeFileSync('state.txt', 'a\\na\\nb\\n');
if (mode === 'delete') fs.unlinkSync('state.txt');
if (mode === 'storage-fail') {
  fs.rmSync('_dsh_tmp_snapshots', { recursive: true });
  fs.writeFileSync('_dsh_tmp_snapshots', 'blocked');
}
const session = path.join(os.homedir(), '.dsh', 'sessions', 'fixture', String(process.pid));
fs.mkdirSync(session, { recursive: true });
const events = [
  { type: 'user/message', data: { content: process.argv.at(-1) } },
  { type: 'request/header', data: { header: { config: { model: 'deepseek-flash' } } } },
  { type: 'turn/end', data: { reason: { kind: 'completed' } } },
];
fs.writeFileSync(path.join(session, 'session.jsonl.zstd'), zlib.zstdCompressSync(Buffer.from(events.map(e => JSON.stringify(e)).join('\\n'))));
fs.writeSync(1, mode === 'no-change-claim' ? '无改动: already correct\\n' : '已完成\\n');
`

function integration({ mode = 'same', command = 'cat state.txt', expect = 'changed', failBeforeStorage = false, noSnapshot = false }, inspect) {
  inTemp(dir => {
    const toolDir = path.join(dir, '开发工具', '通用工具')
    const home = path.join(dir, 'home'), tmp = path.join(dir, 'tmp')
    fs.mkdirSync(toolDir, { recursive: true })
    fs.mkdirSync(path.join(home, '.dsh'), { recursive: true })
    fs.mkdirSync(tmp)
    fs.mkdirSync(path.join(dir, '.dsh_slots'))
    for (const file of ['dsh_task.js', 'dsh_snapshot.js', 'kit_env.js']) fs.copyFileSync(path.join(__dirname, file), path.join(toolDir, file))
    fs.writeFileSync(path.join(dir, 'fake_runner.js'), fakeRunner)
    fs.writeFileSync(path.join(dir, 'state.txt'), 'a\nb\n')
    if (failBeforeStorage) fs.writeFileSync(path.join(dir, '_dsh_tmp_snapshots'), 'blocked')
    const args = [path.join(toolDir, 'dsh_task.js'), '--task', 'snapshot integration fixture',
      '--no-parts-check', '--no-journal', '--lock', 'unity', '--no-record', '--json', path.join(dir, 'result.json')]
    if (!noSnapshot) args.push('--snapshot-cmd', command, '--snapshot-expect', expect)
    const result = spawnSync(process.execPath, args, {
      cwd: dir, encoding: 'utf8', timeout: 10000, stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, HOME: home, TMPDIR: tmp, DSH_HOME: path.join(home, '.dsh'),
        DSH_TASK_NO_GATE: '1', DSH_BIN: path.join(dir, 'fake_runner.js'), SNAPSHOT_TEST_MODE: mode },
    })
    assert.ifError(result.error)
    const report = JSON.parse(fs.readFileSync(path.join(dir, 'result.json'), 'utf8'))
    assert.equal(fs.existsSync(path.join(home, '.dsh', 'handoff.lock')), false)
    assert.deepEqual(fs.readdirSync(path.join(dir, '.dsh_slots')), [])
    inspect({ result, report, dir })
  })
}

for (const options of [{ command: 'exit 7' }, { failBeforeStorage: true }]) {
  test('invalid baseline blocks dispatch and emits failure JSON: ' + JSON.stringify(options), () => {
    integration(options, ({ result, report, dir }) => {
      assert.equal(result.status, 1)
      assert.equal(fs.existsSync(path.join(dir, 'runner-started')), false)
      assert.equal(report.ok, false)
      assert.equal(report.outcome, 'snapshot_failed')
      assert.equal(report.snapshots.executions.before[0].ok, false)
      assert.deepEqual(report.snapshots.executions.after, [])
    })
  })
}

for (const mode of ['delete', 'storage-fail']) {
  test('invalid final snapshot fails verification without a business diff: ' + mode, () => {
    integration({ mode }, ({ result, report }) => {
      assert.equal(result.status, 2)
      assert.equal(report.ok, false)
      assert.equal(report.outcome, 'completed')
      assert.equal(report.snapshots.executions.after[0].ok, false)
      assert.match(report.problems.join('\n'), /后快照 0 执行失败/)
      assert.match(report.snapshots.lines[0], /采集失败，未比较/)
      assert.doesNotMatch(report.snapshots.lines[0], /\+\d/)
    })
  })
}

for (const [mode, expect, exitCode] of [
  ['change', 'changed', 0], ['reorder', 'changed', 0], ['duplicate', 'changed', 0],
  ['same', 'changed', 2], ['same', 'unchanged', 0], ['change', 'unchanged', 2],
  ['no-change-claim', 'changed', 0],
]) {
  test('expectation semantics: ' + mode + ' / ' + expect, () => {
    integration({ mode, expect }, ({ result, report }) => {
      assert.equal(result.status, exitCode, result.stderr + JSON.stringify(report))
      assert.equal(report.ok, exitCode === 0)
      assert.equal(report.snapshots.executions.before[0].ok, true)
      assert.equal(report.snapshots.executions.after[0].ok, true)
      assert.equal(report.snapshots.lines.length, 1)
    })
  })
}

test('no-snapshot callers retain the previous report shape', () => {
  integration({ noSnapshot: true }, ({ result, report }) => {
    assert.equal(result.status, 0, result.stderr)
    assert.equal(report.snapshots.dir, null)
    assert.deepEqual(report.snapshots.lines, [])
    assert.deepEqual(report.snapshots.executions, { before: [], after: [] })
  })
})
