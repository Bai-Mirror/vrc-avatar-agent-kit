#!/usr/bin/env node
/**
 * 【项目沉淀】通用工具
 * 适用素体：无关          相关素材：无
 * 可复用性：★★★ 换个单子直接能用
 * 用途　　：把 DeepSeek Harness 的会话日志读回明文，用于**派工复盘与性能评估**。
 *
 * 为什么需要它（作者 2026-09-08 定）：
 *   DSH 的对话与工具调用是明文留痕的，这是评估「它到底做了什么、做没做对」的
 *   唯一可靠证据来源 —— 比让它自己写报告可信得多。子代理报告里凡是
 *   「我没做那个动作就得不出的结论」一律不采信，判别方法就是看它的 tool/call。
 *
 * 存储格式（实测 dsh 0.1.2-rc.1）：
 *   ~/.dsh/sessions/<workspace-slug>/session-<uuid>/session.jsonl.zstd
 *   ⚠ 是**多帧** zstd（一次 append 一帧）。zstdDecompressSync 只解第一帧，
 *     必须按魔数 28 B5 2F FD 逐帧切开再拼 —— 只解一帧会得到「事件数 1」的假象，
 *     我第一次就是这么误判的。
 *
 * 用法：
 *   node dsh_session.js list [--limit N]        列会话：标题/工作目录/轮数/工具调用/模型
 *   node dsh_session.js show <id|latest>        读某次会话的完整轨迹
 *   node dsh_session.js show latest --reasoning 连模型的思考过程一起读
 *   node dsh_session.js grep <正则> [--limit N] 跨会话搜（搜正文与工具参数）
 *   node dsh_session.js stats                   汇总：模型分布/工具频次/失败率
 *
 * 判据提醒：stats 里的「疑似失败」是宽口径正则，会多报不会漏报，逐条复核再下结论。
 */
'use strict'
const fs = require('fs')
const path = require('path')
const zlib = require('zlib')
const os = require('os')

const HOME = process.env.DSH_HOME || path.join(os.homedir(), '.dsh')
const SESS = path.join(HOME, 'sessions')
const MAGIC = Buffer.from([0x28, 0xB5, 0x2F, 0xFD])

function readEvents(file) {
  const buf = fs.readFileSync(file)
  const parts = []
  let off = 0
  while (off < buf.length) {
    const i = buf.indexOf(MAGIC, off)
    if (i < 0) break
    let n = buf.indexOf(MAGIC, i + 4)
    if (n < 0) n = buf.length
    try {
      parts.push(zlib.zstdDecompressSync(buf.subarray(i, n)).toString('utf8'))
    } catch (e) { /* 坏帧跳过，不让一帧毁掉整份日志 */ }
    off = n
  }
  return parts.join('').split('\n').filter(Boolean)
    .map(l => { try { return JSON.parse(l) } catch (e) { return null } })
    .filter(Boolean)
}

function allSessions() {
  if (!fs.existsSync(SESS)) return []
  const out = []
  for (const ws of fs.readdirSync(SESS)) {
    const wsDir = path.join(SESS, ws)
    if (!fs.statSync(wsDir).isDirectory()) continue
    for (const sd of fs.readdirSync(wsDir)) {
      const f = path.join(wsDir, sd, 'session.jsonl.zstd')
      if (fs.existsSync(f)) out.push({ id: sd, file: f, mtime: fs.statSync(f).mtimeMs })
    }
  }
  return out.sort((a, b) => b.mtime - a.mtime)
}

function textOf(content) {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content.map(b => {
    if (b && typeof b.text === 'string') return b.text
    if (b && b.type === 'tool-result') return textOf(b.content)
    return ''
  }).join('')
}

function digest(s) {
  const evs = readEvents(s.file)
  const g = t => evs.filter(e => e.type === t)
  const hdr = g('request/header')[0]
  const ends = g('turn/end')
  const calls = g('tool/call')
  const results = g('tool/result')
  const failed = results.filter(r => {
    const t = JSON.stringify((r.data && r.data.message && r.data.message.content) || '')
    return /is_?error.{0,6}true|status.{0,4}error|Error:/i.test(t)
  }).length
  const titleEv = g('session/title').slice(-1)[0]
  const sessEv = g('session')[0]
  return {
    id: s.id,
    file: s.file,
    mtime: s.mtime,
    title: (titleEv && titleEv.data && titleEv.data.title) || '(无标题)',
    cwd: (sessEv && sessEv.cwd) || '?',
    model: (hdr && hdr.data && hdr.data.header && hdr.data.header.config && hdr.data.header.config.model) || '?',
    effort: (hdr && hdr.data && hdr.data.header && hdr.data.header.config && hdr.data.header.config.reasoningEffort) || '?',
    turns: ends.length,
    outcome: (ends.slice(-1)[0] && ends.slice(-1)[0].data && ends.slice(-1)[0].data.reason && ends.slice(-1)[0].data.reason.kind) || '?',
    tools: calls.map(c => c.data && c.data.name).filter(Boolean),
    nCalls: calls.length,
    nFailed: failed,
    events: evs,
  }
}

const argv = process.argv.slice(2)
const cmd = argv[0] || 'list'
const rest = argv.slice(1)
function flagVal(name, dflt) {
  const i = rest.indexOf(name)
  return i >= 0 && rest[i + 1] ? rest[i + 1] : dflt
}
const positional = []
for (let i = 0; i < rest.length; i++) {
  if (rest[i].startsWith('--')) { if (rest[i] === '--limit') i++; continue }
  positional.push(rest[i])
}

if (cmd === 'list') {
  const lim = Number(flagVal('--limit', 30))
  const rows = allSessions().slice(0, lim).map(digest)
  if (!rows.length) { console.log('(没有会话)'); process.exit(0) }
  for (const r of rows) {
    const t = new Date(r.mtime).toISOString().replace('T', ' ').slice(0, 19)
    console.log(t + '  ' + r.id)
    console.log('   ' + r.title)
    console.log('   模型 ' + r.model + ' (' + r.effort + ') · ' + r.turns + ' 轮 · ' +
      r.nCalls + ' 次工具调用' + (r.nFailed ? ' · ⚠ ' + r.nFailed + ' 次疑似失败' : '') +
      ' · 收尾 ' + r.outcome)
    const uniq = Array.from(new Set(r.tools))
    if (uniq.length) console.log('   工具: ' + uniq.slice(0, 8).join(', ') + (uniq.length > 8 ? ' …' : ''))
    console.log('   cwd: ' + r.cwd)
    console.log('')
  }
} else if (cmd === 'show') {
  const want = positional[0] || 'latest'
  const list = allSessions()
  const s = want === 'latest' ? list[0] : list.find(x => x.id === want || x.id.indexOf(want) >= 0)
  if (!s) { console.error('找不到会话: ' + want); process.exit(1) }
  const d = digest(s)
  const showReason = rest.indexOf('--reasoning') >= 0
  console.log('# ' + d.title)
  console.log('# ' + d.id)
  console.log('# 模型 ' + d.model + ' (' + d.effort + ') · cwd ' + d.cwd)
  console.log('='.repeat(72))
  for (const e of d.events) {
    if (e.type === 'user/message') {
      console.log('\n【用户】\n' + textOf(e.data && e.data.content) + '\n')
    } else if (e.type === 'assistant/message') {
      const blocks = (e.data && e.data.message && e.data.message.content) || []
      for (const b of blocks) {
        if (b.type === 'reasoning' && showReason) console.log('【思考】\n' + b.text + '\n')
        else if (b.type === 'text') console.log('【助手】\n' + b.text + '\n')
      }
    } else if (e.type === 'tool/call') {
      console.log('  → 调用 ' + (e.data && e.data.name) + '  ' + String((e.data && e.data.arguments) || '').slice(0, 300))
    } else if (e.type === 'tool/result') {
      console.log('  ← 返回 ' + textOf(e.data && e.data.message && e.data.message.content).slice(0, 400).replace(/\n/g, ' '))
    } else if (e.type === 'turn/end') {
      console.log('\n--- 轮次结束: ' + (e.data && e.data.reason && e.data.reason.kind) + ' ---')
    }
  }
} else if (cmd === 'grep') {
  if (!positional[0]) { console.error('用法: node dsh_session.js grep <正则>'); process.exit(1) }
  const pat = new RegExp(positional[0], 'i')
  const lim = Number(flagVal('--limit', 20))
  let hits = 0
  for (const s of allSessions()) {
    if (hits >= lim) break
    const d = digest(s)
    for (const e of d.events) {
      let hay = ''
      if (e.type === 'user/message') hay = textOf(e.data && e.data.content)
      else if (e.type === 'assistant/message') {
        hay = ((e.data && e.data.message && e.data.message.content) || []).map(b => b.text || '').join('')
      } else if (e.type === 'tool/call') {
        hay = (e.data && e.data.name) + ' ' + ((e.data && e.data.arguments) || '')
      } else continue
      const m = hay.match(pat)
      if (m) {
        const i = Math.max(0, hay.indexOf(m[0]) - 60)
        console.log(d.id.slice(0, 20) + '… [' + e.type + '] …' + hay.slice(i, i + 200).replace(/\n/g, ' ') + '…')
        if (++hits >= lim) break
      }
    }
  }
  if (!hits) console.log('(无命中)')
} else if (cmd === 'stats') {
  const rows = allSessions().map(digest)
  const models = {}, tools = {}, outcomes = {}
  let calls = 0, failed = 0
  for (const r of rows) {
    models[r.model] = (models[r.model] || 0) + 1
    outcomes[r.outcome] = (outcomes[r.outcome] || 0) + 1
    calls += r.nCalls
    failed += r.nFailed
    for (const t of r.tools) tools[t] = (tools[t] || 0) + 1
  }
  console.log('会话数 ' + rows.length + ' · 工具调用 ' + calls + ' 次 · 疑似失败 ' + failed + ' 次' +
    (calls ? ' (' + (100 * failed / calls).toFixed(1) + '%)' : ''))
  console.log('\n模型分布:')
  for (const k of Object.keys(models)) console.log('  ' + k + ': ' + models[k])
  console.log('\n收尾分布:')
  for (const k of Object.keys(outcomes)) console.log('  ' + k + ': ' + outcomes[k])
  console.log('\n工具频次:')
  Object.entries(tools).sort((a, b) => b[1] - a[1]).slice(0, 20)
    .forEach(([k, v]) => console.log('  ' + k + ': ' + v))
} else {
  console.error('用法: node dsh_session.js [list|show <id|latest>|grep <正则>|stats]')
  process.exit(1)
}
