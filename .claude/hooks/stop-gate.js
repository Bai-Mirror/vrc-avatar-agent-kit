#!/usr/bin/env node
/**
 * Stop 闸口：结束回合前，把三条能机器判定的强制准则查一遍，不满足就挡回去一次。
 *
 *   ① 施工记录 + git（准则 6）：本会话开始后改过某个工程的文件，
 *      但该工程的 _施工记录.md 没跟着改 → 挡；记录改了但还没提交 → 挡。
 *   ② 证伪（准则 1）：本会话最后一次「看图/渲图」晚于最后一次 agy 调用 → 挡一次。
 *   ③ 节奏（准则 4）：最后一段回复以问句结尾 → 挡（应改用 AskUserQuestion 并继续干）。
 *   ④ 派工（准则 5，2026-09-22）：delegate-check.js 记下本会话 Claude 直接改工程的次数（含豁免放行的）；
 *      上次挡过之后又有新的直接改动 → 挡一次，要求把「为什么没派 / 豁免理由」写进该工程施工记录，剩余同类活派 DSH。
 *
 *   ⑤ 噪音过滤（2026-09-23 工作流审理 A1）：转写里 92 次拦截约半数是噪音——`_DSH流水账.md`（派工脚本自动追加，
 *      随下次提交带上即可）、`<工程>/ProjectSettings/*`（Play/构建/lilToon 的副作用，不是改动）。这两类不再触发拦截，
 *      只在有别的理由时附一句提示。`_dsh_tmp_*` 已由 .gitignore 挡住。
 *
 * 为什么是「挡一次」而不是一直挡：stop_hook_active 为真时说明已经被挡过、模型正在补救，
 * 再挡会死循环。判定是启发式的，允许模型在回复里说明「本轮不下视觉结论」这类例外。
 * 解析失败一律放行 —— 钩子不该成为故障点。
 */
'use strict'
const fs = require('fs')
const path = require('path')
const os = require('os')
const { spawnSync } = require('child_process')

const WS = path.resolve(__dirname, '..', '..')
const STATE_DIR = path.join(os.homedir(), '.cache', 'vrc-rules')

function loadState(sid) {
  try { return JSON.parse(fs.readFileSync(path.join(STATE_DIR, sid + '.json'), 'utf8')) } catch (e) { return {} }
}
function saveState(sid, st) {
  try { fs.mkdirSync(STATE_DIR, { recursive: true }); fs.writeFileSync(path.join(STATE_DIR, sid + '.json'), JSON.stringify(st)) } catch (e) { /* ignore */ }
}

function unityProjects() {
  try {
    return fs.readdirSync(WS).filter(d => fs.existsSync(path.join(WS, d, 'ProjectSettings', 'ProjectVersion.txt')))
  } catch (e) { return [] }
}

// 正在跑、且带 --record <工程> 的 DSH 派工：它收尾时会自己写施工记录并提交，别把它的中间状态当成 Claude 漏记（09-22 实测误拦：导包中 545 个文件）
function projectsUnderDshRecord() {
  const out = new Set()
  try {
    const r = spawnSync('pgrep', ['-af', 'dsh_task\\.js'], { encoding: 'utf8', timeout: 5000 })
    for (const line of (r.stdout || '').split('\n')) {
      const m = line.match(/--record\s+(\S+)/)
      if (m) out.add(path.basename(path.resolve(WS, m[1])))
    }
  } catch (e) { /* ignore */ }
  return out
}

// 正在跑的 DSH 派工里最早那个的启动时间（ms）；没有就 null。
// 09-22 实测：闸口逼 Claude 把 DSH 正在写的非工程文件（素材说明、长程任务目录）做「进行中存档」提交，
// 卷走了 DSH 的在写文件、提交信息张冠李戴。DSH 跑着时，它启动后才改动的非 --record 文件交给它自己收尾。
function earliestDshStart() {
  try {
    const r = spawnSync('pgrep', ['-f', 'dsh_task\\.js'], { encoding: 'utf8', timeout: 5000 })
    let best = null
    for (const pid of (r.stdout || '').split('\n').map(x => x.trim()).filter(Boolean)) {
      const e = spawnSync('ps', ['-o', 'etimes=', '-p', pid], { encoding: 'utf8', timeout: 3000 })
      const sec = parseInt((e.stdout || '').trim(), 10)
      if (!isNaN(sec)) { const st = Date.now() - sec * 1000; if (best === null || st < best) best = st }
    }
    return best
  } catch (e) { return null }
}

function gitCheck(since) {
  if (!fs.existsSync(path.join(WS, '.git'))) return []
  const r = spawnSync('git', ['-C', WS, '-c', 'core.quotepath=false', 'status', '--porcelain', '-z', '--untracked-files=all'],
    { encoding: 'utf8', timeout: 20000, maxBuffer: 64 * 1024 * 1024 })
  if (r.status !== 0 || !r.stdout) return []
  const entries = r.stdout.split('\0').filter(Boolean)
  let changed = []
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i]
    const code = e.slice(0, 2)
    const p = e.slice(3)
    if (code[0] === 'R' || code[0] === 'C') i++ // 重命名后面跟一个原路径
    let mtime = 0
    try { mtime = fs.statSync(path.join(WS, p)).mtimeMs } catch (err) { mtime = Date.now() } // 删除的文件算本轮
    if (mtime >= since) changed.push(p)
  }
  if (!changed.length) return []
  // ⑤ 噪音过滤：流水账自动追加、ProjectSettings 副作用不算「未记录/未提交」
  const NOISE = /^_DSH流水账\.md$/
  const PS = /^[^/]+\/ProjectSettings\//
  const journalPending = changed.some(p => NOISE.test(p))
  const psNoise = changed.filter(p => PS.test(p))
  changed = changed.filter(p => !NOISE.test(p) && !PS.test(p))
  if (!changed.length) return []
  const note = (psNoise.length ? '（另有 ' + psNoise.length + ' 个 ProjectSettings 改动，多半是 Play/构建副作用：提交前 git diff 看一眼，是副作用就 git checkout 还原）' : '') +
    (journalPending ? '（流水账自动追加随下次提交带上）' : '')
  const reasons = []
  const projects = unityProjects()
  const dshBusy = projectsUnderDshRecord()
  let skipped = 0
  for (const proj of projects) {
    const inProj = changed.filter(p => p.startsWith(proj + '/'))
    if (!inProj.length) continue
    if (dshBusy.has(proj)) { skipped += inProj.length; continue }  // 由正在跑的 DSH --record 任务收尾留痕
    const logChanged = inProj.includes(proj + '/_施工记录.md')
    if (!logChanged) {
      reasons.push('工程「' + proj + '」本会话有 ' + inProj.length + ' 个文件改动未提交，但 _施工记录.md 没有更新（例：' +
        inProj.slice(0, 3).join('、') + '）。先用 log_step.py 追加施工记录（--commit 一步提交），若改动来自用户手动操作，也要记一条「用户手动」。' + note)
    }
  }
  const dshStart = earliestDshStart()
  let dshFresh = 0
  const rest = changed.filter(p => {
    if (dshBusy.has(p.split('/')[0])) return false
    if (dshStart !== null) {
      let mt = 0
      try { mt = fs.statSync(path.join(WS, p)).mtimeMs } catch (err) { mt = Date.now() }
      if (mt >= dshStart) { dshFresh++; return false }   // DSH 跑着、且它启动后才改的：由 DSH 收尾提交
    }
    return true
  })
  if (!rest.length) return []
  if (!reasons.length) {
    reasons.push('本会话有 ' + rest.length + ' 个文件改动还没提交 git（例：' + rest.slice(0, 3).join('、') +
      '）。按准则 6 用 `python3 开发工具/通用工具/ws_git.py commit -m "..."` 提交。' + (skipped ? '（另有 ' + skipped + ' 个属正在跑的 DSH --record 任务，由它收尾留痕）' : '') +
      (dshFresh ? '（另有 ' + dshFresh + ' 个是 DSH 派工启动后才改动的，交给它收尾提交）' : '') + note)
  }
  return reasons
}

function lastAssistantText(transcriptPath) {
  try {
    const lines = fs.readFileSync(transcriptPath, 'utf8').trim().split('\n')
    for (let i = lines.length - 1; i >= 0; i--) {
      let o
      try { o = JSON.parse(lines[i]) } catch (e) { continue }
      if (o.type === 'user' && !o.isMeta) {
        const c = o.message && o.message.content
        const isToolResult = Array.isArray(c) && c.some(x => x && x.type === 'tool_result')
        if (!isToolResult) return ''
      }
      if (o.type === 'assistant' && o.message && Array.isArray(o.message.content)) {
        const texts = o.message.content.filter(x => x && x.type === 'text' && x.text && x.text.trim())
        if (texts.length) return texts[texts.length - 1].text
      }
    }
  } catch (e) { /* ignore */ }
  return ''
}

let buf = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', d => { buf += d })
process.stdin.on('end', () => {
  let j
  try { j = JSON.parse(buf || '{}') } catch (e) { return }
  if (j.stop_hook_active) return
  const sid = String(j.session_id || 'nosession').replace(/[^\w-]/g, '')
  const st = loadState(sid)
  const since = st.start || (Date.now() - 6 * 3600 * 1000)
  const reasons = []

  try { reasons.push(...gitCheck(since)) } catch (e) { /* ignore */ }

  if (st.lastVisual && st.lastVisual > (st.lastAgy || 0) && st.lastVisual > (st.visualAck || 0)) {
    reasons.push('本会话看过/渲过图，但之后没有送 agy 证伪（准则 1）。回复里若含视觉结论，先跑 agy_panel.py --fast 或 agy_ask；若本轮不下视觉结论，在回复里明说。')
    st.visualAck = st.lastVisual
    saveState(sid, st)
  }

  const dTotal = st.directTotal || 0
  if (dTotal > (st.directAck || 0)) {
    const fresh = (st.direct || []).slice(-(dTotal - (st.directAck || 0))).slice(-5)
    const ex = fresh.filter(x => x.ex).length
    reasons.push('本会话 Claude 直接改了工程/项目工具 ' + (dTotal - (st.directAck || 0)) + ' 处（其中豁免放行 ' + ex + ' 处），派 DSH ' +
      (st.dshCount || 0) + ' 次（准则 5）。最近：' + fresh.map(x => x.what + (x.ex ? '〔豁免:' + x.ex + '〕' : '')).join('；') +
      '。在对应工程 _施工记录.md 里写明为什么没派（豁免类别与理由），剩下的同类改动写任务书用 dsh_task.js --record 派出去。')
    st.directAck = dTotal
    saveState(sid, st)
  }

  const t = lastAssistantText(j.transcript_path || '').replace(/[\s*_`>)）\]】」』]+$/u, '')
  if (/[?？]$/.test(t)) {
    reasons.push('回复以问句结尾（准则 4）。需要用户决定的事用 AskUserQuestion 抛出，并继续做不依赖答案的部分；若确实只剩待决项，改成陈述句列出。')
  }

  if (reasons.length) {
    process.stdout.write(JSON.stringify({ decision: 'block', reason: '【强制准则闸口】\n- ' + reasons.join('\n- ') }))
  }
})
