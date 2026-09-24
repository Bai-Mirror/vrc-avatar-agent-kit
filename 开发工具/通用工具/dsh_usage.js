#!/usr/bin/env node
/**
 * 用途　　：按 ~/.dsh/sessions 会话日志估算 DSH 的 token 与费用（按模型、按时段、缓存命中），对账以 DeepSeek 后台为准。
 *
 * dsh_usage.js —— 从 DSH 会话日志里统计 token 用量与估算费用。
 *
 * 为什么单独写一个：`dsh_session.js stats` 只数会话/工具次数，**不报 token 也不报钱**，
 * 而作者 2026-09-11 明确要「回报本次任务的使用量和费用统计」。
 *
 * 数据来源：会话日志里 `assistant/chunk` 且 `chunk.type === 'usage'` 的事件，字段为
 *   inputTokens / outputTokens / totalTokens / cacheReadTokens / reasoningTokens
 * ⚠ 同一 step 会多次上报累计值，**同一 (turn, step) 只取最后一条**，否则会重复计数。
 *
 * 费率来自 DeepSeek 官方《模型细节》页（2026-09-11 抄录，单位 元/百万 token）：
 *
 *            | 缓存命中输入 | 缓存未命中输入 | 输出
 *   flash 空闲 |    0.02     |      1        |  4
 *   flash 高峰 |    0.04     |      2        |  8
 *   pro   空闲 |    0.15     |      4.5      | 13.5
 *   pro   高峰 |    0.30     |      9.0      | 27.0
 *
 *   **高峰时段 = 北京时间 周一~周五 09:00-12:00 与 14:00-18:00，其余为空闲（半价）。**
 *
 * ⚠ 两条会让数字偏一点的近似，用之前先知道：
 *   ① 计费按**每次请求**发生的时段算，本脚本按**会话开始时刻**统一归档 ——
 *      跨越时段边界的长会话会被算到起始那一档。
 *   ② 2026-09-11 起旧模型名（v4-flash / vision-exp）的请求实际由 V4.1-Flash 承接
 *      并按 flash 价计费，所以历史会话里这些名字一律按 flash 价算。
 *      v4-pro 在 09-14 12:00 之前仍是 pro 价，之后也会转成 flash 价。
 *   对账以 DeepSeek 后台账单为准。
 *
 * 用法：
 *   node dsh_usage.js                      统计全部会话
 *   node dsh_usage.js --since <ISO时间>     只统计该时刻之后开始的会话
 *   node dsh_usage.js --dir <会话目录名过滤子串>
 *   node dsh_usage.js --json               机器可读输出
 */
const fs = require('fs')
const path = require('path')
const zlib = require('zlib')

const HOME = process.env.USERPROFILE || process.env.HOME
const ROOT = path.join(HOME, '.dsh', 'sessions')

// ¥ / 每百万 token，见文件头的官方价表。off = 空闲时段，peak = 高峰时段。
const RATE = {
  pro: {
    off: { cached: 0.15, miss: 4.5, out: 13.5 },
    peak: { cached: 0.30, miss: 9.0, out: 27.0 },
  },
  flash: {
    off: { cached: 0.02, miss: 1, out: 4 },
    peak: { cached: 0.04, miss: 2, out: 8 },
  },
}
// 只有 v4-pro 走 pro 价；其余（含已下线的旧 flash 名）一律 flash 价。
const isPro = (m) => /v4-pro/.test(m || '')

/** 北京时间周一~周五 09:00-12:00、14:00-18:00 为高峰。 */
function isPeak(ms) {
  const bj = new Date(ms + 8 * 3600 * 1000) // 用 UTC 取值 + 8 小时 = 北京时间
  const dow = bj.getUTCDay()                // 0=周日
  if (dow === 0 || dow === 6) return false
  const h = bj.getUTCHours() + bj.getUTCMinutes() / 60
  return (h >= 9 && h < 12) || (h >= 14 && h < 18)
}

function arg(name, dflt) {
  const i = process.argv.indexOf(name)
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : dflt
}
const has = (n) => process.argv.indexOf(n) >= 0

function readEvents(file) {
  const buf = fs.readFileSync(file)
  const MAGIC = Buffer.from([0x28, 0xb5, 0x2f, 0xfd])
  const parts = []
  let i = 0
  while (i < buf.length) {
    let n = buf.indexOf(MAGIC, i + 4)
    if (n < 0) n = buf.length
    try { parts.push(zlib.zstdDecompressSync(buf.subarray(i, n)).toString('utf8')) } catch (e) { /* 坏帧跳过 */ }
    i = n
  }
  return parts.join('').split('\n').filter(Boolean).map((l) => {
    try { return JSON.parse(l) } catch (e) { return null }
  }).filter(Boolean)
}

function collect() {
  const since = arg('--since', null)
  const sinceMs = since ? Date.parse(since) : null
  const dirFilter = arg('--dir', null)
  const out = []
  if (!fs.existsSync(ROOT)) return out
  for (const ws of fs.readdirSync(ROOT)) {
    if (dirFilter && !ws.includes(dirFilter)) continue
    const wsDir = path.join(ROOT, ws)
    if (!fs.statSync(wsDir).isDirectory()) continue
    for (const sd of fs.readdirSync(wsDir)) {
      const f = path.join(wsDir, sd, 'session.jsonl.zstd')
      if (!fs.existsSync(f)) continue
      let evs
      try { evs = readEvents(f) } catch (e) { continue }
      // ⚠ 不是每条 session/turn-start 都带 time（实测有会话没有），
      //    取第一个真的有 time 的事件，再退回文件 mtime。否则 new Date(undefined) 会抛。
      const stamped = evs.find((e) => Number.isFinite(e.time) && e.time > 0)
      const t0 = stamped ? stamped.time : fs.statSync(f).mtimeMs
      if (sinceMs && t0 < sinceMs) continue
      const hdr = evs.find((e) => e.type === 'request/header')
      const model = (hdr && hdr.data && hdr.data.header && hdr.data.header.config
        && hdr.data.header.config.model) || '?'
      // 同一 (turn, step) 只取最后一条 usage —— 它是该 step 的累计值
      const last = new Map()
      for (const e of evs) {
        if (e.type !== 'assistant/chunk') continue
        const c = e.data && e.data.chunk
        if (!c || c.type !== 'usage' || !c.usage) continue
        last.set(`${e.data.turn}/${e.data.step}`, c.usage)
      }
      let inTok = 0, outTok = 0, cache = 0, reason = 0
      for (const u of last.values()) {
        inTok += u.inputTokens || 0
        outTok += u.outputTokens || 0
        cache += u.cacheReadTokens || 0
        reason += u.reasoningTokens || 0
      }
      const title = (evs.find((e) => e.type === 'session/title') || {})
      out.push({
        workspace: ws, session: sd, model, startedMs: t0,
        title: (title.data && (title.data.title || title.data.text)) || '',
        inputTokens: inTok, outputTokens: outTok,
        cacheReadTokens: cache, reasoningTokens: reason,
        steps: last.size,
      })
    }
  }
  out.sort((a, b) => a.startedMs - b.startedMs)
  return out
}

function cost(s) {
  const r = (isPro(s.model) ? RATE.pro : RATE.flash)[isPeak(s.startedMs) ? 'peak' : 'off']
  // inputTokens 是「缓存未命中」部分；cacheReadTokens 是命中部分，单独计价。
  return (s.inputTokens / 1e6) * r.miss
    + (s.cacheReadTokens / 1e6) * r.cached
    + (s.outputTokens / 1e6) * r.out
}
const fmt = (n) => n.toLocaleString('en-US')

const rows = collect()
if (has('--json')) {
  console.log(JSON.stringify(rows.map((r) => ({ ...r, costCNY: +cost(r).toFixed(4) })), null, 1))
  process.exit(0)
}
if (!rows.length) { console.log('没有匹配的会话。'); process.exit(0) }

let tin = 0, tout = 0, tc = 0, tr = 0, tcost = 0
const byModel = new Map()
console.log('会话明细：\n')
for (const s of rows) {
  const c = cost(s)
  tin += s.inputTokens; tout += s.outputTokens; tc += s.cacheReadTokens
  tr += s.reasoningTokens; tcost += c
  const m = byModel.get(s.model) || { n: 0, in: 0, out: 0, cache: 0, cost: 0 }
  m.n++; m.in += s.inputTokens; m.out += s.outputTokens; m.cache += s.cacheReadTokens; m.cost += c
  byModel.set(s.model, m)
  // 时间按北京时间显示（计费时段就是按北京时间划的）
  const t = new Date(s.startedMs + 8 * 3600 * 1000).toISOString().replace('T', ' ').slice(5, 16)
  console.log(`  ${t}${isPeak(s.startedMs) ? '高峰' : '空闲'}  ${s.model.padEnd(34)} `
    + `输入 ${fmt(s.inputTokens).padStart(9)} `
    + `缓存 ${fmt(s.cacheReadTokens).padStart(10)} 输出 ${fmt(s.outputTokens).padStart(8)} `
    + `≈ ¥${c.toFixed(3)}`)
  if (s.title) console.log(`      ${s.title.slice(0, 90)}`)
}
console.log('\n按模型：')
for (const [m, v] of byModel) {
  console.log(`  ${m.padEnd(36)} ${String(v.n).padStart(3)} 个会话  `
    + `输入 ${fmt(v.in).padStart(9)}  缓存 ${fmt(v.cache).padStart(10)}  输出 ${fmt(v.out).padStart(8)}  ≈ ¥${v.cost.toFixed(2)}`)
}
console.log('\n合计：')
console.log(`  会话 ${rows.length} 个`)
console.log(`  输入(未命中) ${fmt(tin)}   缓存命中 ${fmt(tc)}   输出 ${fmt(tout)}（其中思考 ${fmt(tr)}）`)
console.log(`  总 token ${fmt(tin + tc + tout)}`)
console.log(`  估算费用 ≈ ¥${tcost.toFixed(2)}`)
// 反事实：把缓存命中的部分也按「未命中」计价，看缓存到底省了多少。
let noCache = 0
for (const s of rows) {
  const r = (isPro(s.model) ? RATE.pro : RATE.flash)[isPeak(s.startedMs) ? 'peak' : 'off']
  noCache += ((s.inputTokens + s.cacheReadTokens) / 1e6) * r.miss + (s.outputTokens / 1e6) * r.out
}
console.log(`  若缓存全部未命中 ≈ ¥${noCache.toFixed(2)}  ⇒ 缓存省下 ≈ ¥${(noCache - tcost).toFixed(2)}`)
const peakCount = rows.filter((s) => isPeak(s.startedMs)).length
console.log(`  时段分布：高峰 ${peakCount} 个 / 空闲 ${rows.length - peakCount} 个（空闲是高峰的半价）`)
console.log('\n⚠ 费率抄自 DeepSeek 官方《模型细节》（2026-09-11）。两条近似见文件头：')
console.log('  计费按每次请求的时段算，这里按会话开始时刻归档；旧 flash 名一律按 flash 价。')
console.log('  对账以 DeepSeek 后台账单为准。')
