#!/usr/bin/env node
/**
 * SessionStart 钩子（2026-09-23 工作流审理 A10）：会话开始 / 恢复 / 上下文压缩后，跑一次只读的基线重核并注入。
 * 为什么：错时间戳、卷走 DSH 在写文件、19 分钟失效的计划，都集中在 OOM 之后＋压缩之中＋无人交互连续重试的时段；
 *   压缩后模型对「上一条 / 刚才」的记忆是摘要不是事实，先对一次现实再继续。
 * 解析失败一律静默放过 —— 钩子不该成为故障点。输出上限 6000 字。
 */
'use strict'
const { spawnSync } = require('child_process')
const path = require('path')
let buf = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', d => { buf += d })
process.stdin.on('end', () => {
  let j = {}
  try { j = JSON.parse(buf || '{}') } catch (e) { /* ignore */ }
  const src = String(j.source || '')
  const r = spawnSync('bash', [path.join(__dirname, '..', '..', '开发工具', '通用工具', 'baseline_recheck.sh')], { encoding: 'utf8', timeout: 25000 })
  let out = (r.stdout || '').trim()
  if (!out) return
  if (out.length > 6000) out = out.slice(0, 6000) + '\n…(截断)'
  const head = src === 'compact'
    ? '【上下文刚被压缩。先按下面的基线重核对一次现实再继续：凡「上一条 / 刚才 / 见上」的引用回读原文；计划的前提按此重验；时间戳一律来自 date。】'
    : src === 'resume' ? '【会话恢复：基线重核】' : '【会话开始：基线重核（只读）】'
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: head + '\n' + out } }))
})
