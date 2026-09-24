'use strict'
// 【项目沉淀】通用工具
// 适用素体：无关；相关素材：无；可复用性：★★★
// 用途：DSH 前后快照的执行状态、落盘与保留行序/重复行的比较；不调用模型。
const fs = require('fs')
const path = require('path')
const { spawnSync } = require('child_process')

function captureSnapshot(command, { cwd, file, phase, index, timeout = 180000, maxBuffer = 64 * 1024 * 1024 }) {
  let result
  try {
    result = spawnSync('bash', ['-c', command], {
      cwd, encoding: 'utf8', timeout, maxBuffer, stdio: ['ignore', 'pipe', 'pipe'],
    })
  } catch (error) {
    result = { status: null, signal: null, error }
  }
  const stdout = result.stdout || ''
  const execution = {
    phase, index, command, file, ok: false,
    status: result.status ?? null, signal: result.signal || null,
    errorCode: result.error ? result.error.code || 'SPAWN_ERROR' : null,
    error: result.error ? result.error.message : null,
    stderr: (result.stderr || '').slice(-1000), persisted: false, writeError: null,
  }
  try {
    fs.mkdirSync(path.dirname(file), { recursive: true })
    fs.writeFileSync(file, stdout, 'utf8')
    execution.persisted = true
  } catch (error) {
    execution.writeError = error.message
  }
  execution.ok = result.status === 0 && !result.signal && !result.error && execution.persisted
  return { ok: execution.ok, stdout, execution }
}

function snapshotFailure(snapshot) {
  const e = snapshot.execution
  const details = []
  if (e.status !== 0) details.push('exit=' + e.status)
  if (e.signal) details.push('signal=' + e.signal)
  if (e.error) details.push((e.errorCode || 'error') + ': ' + e.error)
  if (e.writeError) details.push('落盘失败: ' + e.writeError)
  if (e.stderr) details.push(e.stderr.trim())
  return (e.phase === 'before' ? '前' : '后') + '快照 ' + e.index + ' 执行失败（' + details.join('；') + '）'
}

function compareSnapshotText(before, after) {
  if (before === after) return { changed: false, added: [], removed: [] }
  // 只裁掉相同前后缀，保留变更区里的行序与重复行；线性开销，避免大快照做 LCS。
  const a = before.split('\n'), b = after.split('\n')
  let start = 0, aEnd = a.length, bEnd = b.length
  while (start < aEnd && start < bEnd && a[start] === b[start]) start++
  while (aEnd > start && bEnd > start && a[aEnd - 1] === b[bEnd - 1]) { aEnd--; bEnd-- }
  return { changed: true, added: b.slice(start, bEnd), removed: a.slice(start, aEnd) }
}

module.exports = { captureSnapshot, snapshotFailure, compareSnapshotText }
