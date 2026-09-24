#!/usr/bin/env node
/**
 * PreToolUse 钩子：Claude 自己动手改工程 / 写项目侧工具时，提醒派 DSH；自上次派工起第 3 次直接改动就拦下。
 *
 * 为什么要这个钩子：
 *   2026-09-09（用户提出）：Claude 自己写了 445 行贴图工具、连调 4 轮，DSH 参与 0 次 —— 全程没有任何东西提醒。
 *     根因不是记性，是**没有结构性触发器**。当时只盯「写 开发工具/通用工具/」。
 *   2026-09-22（作者：「把更主动地调用 DSH 固化到流程中，不要仅限于我提起的时候」）：
 *     工程B删素体发型一整轮——改控制器、删物体、拆厂商层、回收参数、改交付说明——全是 Claude 用
 *     execute_code 和 Bash 里的 python/sed 做的，旧钩子一次都没触发。所以覆盖面扩到：
 *       · Write / Edit 写进任何 Unity 工程目录（`_施工记录.md` 除外，那是验收记录）
 *       · Bash 里对工程目录的写操作（重定向、sed -i、rm/mv/cp、python/node 的写文件 API…）
 *       · Unity MCP：带修改 API 的 execute_code、execute_menu_item、manage_* 的写动作、改脚本、跑测试、进 Play
 *       · Blender 执行代码
 *       · 写 开发工具/通用工具/ 下非 DSH 自身工具链的文件（原有提醒）
 *
 * 升级规则：自上次派 DSH（rules-inject.js 在 Bash 跑 dsh_task.js 后清零计数）起，
 *   第 1、2 次直接改动只提醒；第 3 次起 **deny**，除非已声明豁免：
 *     node .claude/hooks/delegate-check.js --exempt <类别> "<理由>"
 *   类别只认六种：不可逆 / 红线 / 用户确认 / 维护SOP / 迭代DSH / 兜底（DSH 失败或 STOP 后的排障，理由里写会话或退出码）。
 *   豁免 20 分钟有效，逐条留档在 ~/.cache/vrc-rules/exempt.log，stop-gate.js 会要求把本会话的直接改动与豁免记进施工记录。
 *
 * Claude 自己的地盘不算：开发工具/SOP、CLAUDE.md、.claude/、_长程任务_*、_DSH流水账.md、_服务器备份名册.md、
 *   记忆目录、各工程 _施工记录.md、/tmp。只读操作（读回、grep、git status）不算。
 * 解析失败一律静默放过 —— 钩子不该成为故障点。
 */
'use strict'
const fs = require('fs')
const path = require('path')
const os = require('os')

const WS = path.resolve(__dirname, '..', '..')
const STATE_DIR = path.join(os.homedir(), '.cache', 'vrc-rules')
const EXEMPT_FILE = path.join(STATE_DIR, 'exempt.json')
const EXEMPT_LOG = path.join(STATE_DIR, 'exempt.log')
const EXEMPT_MIN = 20
const DENY_AT = 3
const CATS = ['不可逆', '红线', '用户确认', '维护SOP', '迭代DSH', '兜底']

// DSH 自己的工具链归 Claude（第五项职责），不提醒
const DSH_OWN = /^(dsh_task\.js|dsh_session\.js|dsh_usage\.js|agy_mcp_server\.js|delegate-check\.js|ws_git\.py)$/
const TOOLS_RE = /开发工具[\\/]通用工具[\\/]([^\s'"`;|&)]+)/g
const OWN_RE = /(开发工具[\\/]SOP[\\/]|CLAUDE\.md|\.claude[\\/]|_长程任务_|_DSH流水账\.md|_服务器备份名册\.md|_施工记录\.md$|_任务账本\.md$|_工作流审理_|^\/tmp\/|^\/dev\/null$|^&)/  // 09-23：账本与审理报告是规划文档，同施工记录

function loadJson(f) { try { return JSON.parse(fs.readFileSync(f, 'utf8')) } catch (e) { return {} } }
function saveJson(f, o) { try { fs.mkdirSync(STATE_DIR, { recursive: true }); fs.writeFileSync(f, JSON.stringify(o)) } catch (e) { /* ignore */ } }

// ── 豁免声明（CLI 模式）──────────────────────────────────────────────────
if (process.argv.includes('--exempt')) {
  const i = process.argv.indexOf('--exempt')
  const cat = process.argv[i + 1] || ''
  const reason = process.argv.slice(i + 2).join(' ').trim()
  if (!CATS.includes(cat) || reason.length < 6) {
    console.error('豁免要写类别与理由（≥6 字）。类别只认：' + CATS.join(' / ') +
      '\n「上下文都在我脑子里、交代成本高」不是合法理由。')
    process.exit(1)
  }
  const now = Date.now()
  saveJson(EXEMPT_FILE, { cat, reason, at: now, until: now + EXEMPT_MIN * 60000 })
  try { fs.appendFileSync(EXEMPT_LOG, new Date(now).toISOString() + '\t声明\t' + cat + '\t' + reason + '\n') } catch (e) { /* ignore */ }
  console.log('已声明豁免（' + cat + '）：' + reason + '，' + EXEMPT_MIN + ' 分钟内直接改工程放行并逐条留档。收尾时把它写进该工程 _施工记录.md。')
  process.exit(0)
}

function unityProjects() {
  try { return fs.readdirSync(WS).filter(d => fs.existsSync(path.join(WS, d, 'ProjectSettings', 'ProjectVersion.txt'))) }
  catch (e) { return [] }
}
function projOfPath(p, cwd) {
  if (!p) return null
  const abs = path.resolve(cwd || WS, p)
  const rel = path.relative(WS, abs)
  if (rel.startsWith('..')) return null
  const top = rel.split(path.sep)[0]
  return unityProjects().includes(top) ? { proj: top, rel } : null
}

// Bash：把 heredoc 拆开——解释器（python/node/…）的正文是真代码，单独扫写文件 API；
// cat/tee 之类的数据 heredoc 正文是文字（里面的「> 引用」「rm」不算），丢掉。
function splitHeredocs(cmd) {
  let code = ''
  const shell = cmd.replace(/([^\n]*)<<-?[ \t]*(['"]?)([A-Za-z_]\w*)\2([^\n]*)\n([\s\S]*?)\n[ \t]*\3[ \t]*(?=\n|$)/g,
    (m, pre, q, tag, post, body) => {
      if (/\b(python3?|node|perl|ruby|bash|sh)\b/.test(pre)) code += '\n' + body
      return pre + ' ' + post
    })
  // python -c "…" / node -e "…" 的内联代码也是代码
  const inl = /\b(?:python3?|node)\s+(?:-c|-e)\s+("(?:[^"\\]|\\.)*"|'[^']*')/g
  let m
  while ((m = inl.exec(shell))) code += '\n' + m[1].slice(1, -1)
  return { shell, code }
}
function stripQuoted(s) { return s.replace(/"(?:[^"\\]|\\.)*"|'[^']*'/g, '""') }

function pathHits(text) {
  const hits = []
  // 要求「工程名/」带分隔符，免得把含工程名的文件名（如 归档包 工程B_归档_….7z）当成工程路径（09-22 误报）
  for (const d of unityProjects()) if (text.includes(d + '/') || text.includes(d + '\\') || new RegExp(d.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '["\'\\s]').test(text) || text.endsWith(d)) hits.push(d)
  TOOLS_RE.lastIndex = 0
  let t
  while ((t = TOOLS_RE.exec(text))) {
    const n = t[1].split(/[\\/]/)[0]
    if (!DSH_OWN.test(n) && !/^(审查|生成)$/.test(n)) hits.push('通用工具/' + n)
  }
  return hits
}

// 解释器代码里的写入目标。全部写 API 的目标都能解析成字符串字面量时返回数组，否则返回 null（调用方退回全文扫描）。
function writeTargets(code) {
  const vars = {}
  const asg = /(?:^|[\s;(,])([A-Za-z_]\w*)\s*=\s*[rbuf]?(['"])((?:\\.|(?!\2)[^\\\n])*)\2/g
  let m
  while ((m = asg.exec(code))) (vars[m[1]] = vars[m[1]] || []).push(m[3])
  const resolve = e => {
    e = e.trim()
    const lit = e.match(/^[rbuf]?(['"])(.*)\1$/)
    if (lit) return [lit[2]]
    if (/^[A-Za-z_]\w*$/.test(e) && vars[e]) return vars[e]
    return null
  }
  const out = []
  let n = 0
  const W = /\b(?:io\.)?open\(\s*([^,()]+?)\s*,\s*(?:mode\s*=\s*)?['"][wax]\+?b?['"]|\b(?:writeFileSync|writeFile|appendFileSync|appendFile)\(\s*([^,()]+?)\s*,/g
  while ((m = W.exec(code))) { n++; const r = resolve(m[1] || m[2]); if (!r) return null; out.push(...r) }
  // 有写模式 open 但首参带括号（os.path.join(…) 等）解析不了 → 交给全文扫描
  const loose = (code.match(/\bopen\([^\n]*?,\s*(?:mode\s*=\s*)?['"][wax]\+?b?['"]/g) || []).length
  if (loose > n) return null
  // 其它写 API（write_text、os.remove、shutil、rename…）解析不了目标 → 交给全文扫描
  const OTHER = /\.write_(text|bytes)\(|os\.(remove|unlink|rename|replace|makedirs|rmdir)\b|shutil\.|unlinkSync|renameSync|rmSync|mkdirSync|copyFileSync/
  if (OTHER.test(code)) return null
  return n ? out : null
}

// 逐条写证据各自判断目标落在哪；工程名只出现在 heredoc 数据正文（任务书、施工记录文字）里不算。
function classifyBash(cmd, cwd) {
  const c = String(cmd || '')
  // 派工、提交、豁免声明本身不算
  if (/dsh_task\.js|delegate-check\.js\s+--exempt|^\s*(cd\s+\S+\s*&&\s*)?python3\s+\S*ws_git\.py\b/.test(c)) return null
  const { shell, code } = splitHeredocs(c)
  const bare = stripQuoted(shell)
  // 有效工作目录落在哪个工程：钩子给的 cwd，或命令里 cd 到的目录
  let cwdProj = (projOfPath(cwd, WS) || {}).proj || null
  const cdRe = /\bcd\s+("[^"]+"|'[^']+'|[^\s;&|]+)/g
  let m
  // cd 到哪就以哪为准：cd 出工程（如工作区根）要清空，否则会把 SOP 编辑误判成改工程（09-22 实测误报）
  while ((m = cdRe.exec(shell))) { const pp = projOfPath(m[1].replace(/^['"]|['"]$/g, ''), cwd); cwdProj = pp ? pp.proj : null }
  const rel = s => s && !/^[\/~$-]/.test(s)
  const hits = new Set(), kinds = new Set()
  const add = (arr, k) => { if (arr.length) { arr.forEach(h => hits.add(h)); kinds.add(k) } }
  // ① 重定向（在去掉引号内容的 shell 部分上找，引号里的「->」不算）
  const redir = /(?:^|[^<>&\d=-])(?:\d?>>?|&>>?)\s*([^\s;&|)<>]+)/g
  while ((m = redir.exec(bare))) {
    const t = m[1]
    if (!t || t === '""' || OWN_RE.test(t)) continue
    add(t.startsWith('/') ? pathHits(t) : (cwdProj ? [cwdProj] : []), '重定向→' + t)
  }
  // 引号括起来的重定向目标（含中文路径时常见）
  const qredir = /(?:^|[^<>&\d=-])(?:\d?>>?)\s*("[^"]+"|'[^']+')/g
  while ((m = qredir.exec(shell))) {
    const t = m[1].slice(1, -1)
    if (OWN_RE.test(t)) continue
    add(t.startsWith('/') ? pathHits(t) : (cwdProj ? [cwdProj] : []), '重定向→' + t)
  }
  // ② 写命令：取该命令到下一个 ; & | 换行 为止的片段，看参数落在哪
  const verb = /(?:^|[\s;&|(])((?:sed|perl)\s+(?:-\w+\s+)*-i\b|rm|rmdir|mv|cp|mkdir|touch|tee|ln|unzip|install|7z\s+[xe]|tar\s+-?\w*x\w*|git\s+(?:checkout|restore|reset|rm|mv|stash|clean|apply))(?=\s)([^;&|\n]*)/g
  // 09-23：动词只认引号外的（log_step.py --did "…cp 到临时目录…" 这种参数正文里的 cp 曾被计成改工程两次）
  const qspans = []
  { const qre = /"(?:[^"\\]|\\.)*"|'[^']*'/g; let qm; while ((qm = qre.exec(shell))) qspans.push([qm.index, qm.index + qm[0].length]) }
  const inQuotes = i => qspans.some(([a, b]) => i > a && i < b)
  while ((m = verb.exec(shell))) {
    if (inQuotes(m.index + 1)) continue
    const seg = m[2]
    const args = seg.trim().split(/\s+/).map(a => a.replace(/^['"]|['"]$/g, '')).filter(a => a && !a.startsWith('-'))
    const h = pathHits(seg)
    if (!h.length && cwdProj && args.some(a => rel(a) && !OWN_RE.test(a))) h.push(cwdProj)
    add(h, m[1].split(/\s+/)[0])
  }
  // ③ 解释器代码里的写文件 API
  const API = /open\([^\n]*?,\s*(?:mode\s*=\s*)?['"][wax]\+?b?['"]|\.write_(text|bytes)\(|write(File|FileSync)\(|appendFile(Sync)?\(|os\.(remove|unlink|rename|replace|makedirs|rmdir)\b|shutil\.|unlinkSync|renameSync|rmSync|mkdirSync|copyFileSync/
  if (API.test(code)) {
    // 能认出写入目标（open(p,'w') 且 p='…'、writeFileSync('…')）就只按目标判断；
    // 否则退回全文找工程名。09-22 误报：python 写 `_长程任务_` 文档，字符串里引用了「工程/_施工记录.md:735」也被算成改工程。
    const tg = writeTargets(code)
    let h = []
    if (tg) {
      for (const t of tg) {
        if (OWN_RE.test(t)) continue
        const ph = pathHits(t)
        if (ph.length) ph.forEach(x => h.push(x))
        else if (!t.startsWith('/') && cwdProj) h.push(cwdProj)
      }
    } else {
      h = pathHits(code)
      if (!h.length && cwdProj) h.push(cwdProj)
    }
    add(h, '脚本写文件')
  }
  if (!hits.size) return null
  const hs = [...hits]
  const projs = hs.filter(h => !h.startsWith('通用工具/')), tools = hs.filter(h => h.startsWith('通用工具/'))
  return (projs.length ? '改工程 ' + projs.join('、') : '写' + tools.join('、')) +
    '（Bash：' + [...kinds].slice(0, 3).join('，') + '）'
}

const UNITY_MUT = /SetDirty|SaveAssets|SaveOpenScenes|SaveScene|MarkSceneDirty|DestroyImmediate|DestroyObjectImmediate|Undo\.|\.SetActive\(|AddComponent|Remove(Layer|State|AnyStateTransition|Transition|Parameter|StateMachine)\b|Add(Layer|State|AnyStateTransition|Transition|Parameter|StateMachineBehaviour)\b|SetEditorCurve|SetObjectReferenceCurve|(Create|Delete|Move|Copy|Import|Rename)Asset\b|\.(parameters|conditions|defaultState|sharedMaterials?|sharedMesh|layers|bones|ignoreTransforms|rootTransform)\s*=[^=]|\.Set(Float|Color|Texture|Vector|Int)\(|SetBlendShapeWeight|ExecuteMenuItem|File\.(Write|Append|Delete|Move|Copy)|Directory\.(Delete|Move|CreateDirectory)|EnterPlaymode|isPlaying\s*=|ApplyModifiedProperties|PrefabUtility\.(Save|Apply|Unpack)/
const READ_ACT = /^(get|list|find|read|search|info|inspect|status|query|describe|capabilities|validate|ping|preview)(_\w+)?$/i

function classify(tn, ti, cwd) {
  if (tn === 'Write' || tn === 'Edit' || tn === 'NotebookEdit') {
    const f = String(ti.file_path || ti.filePath || ti.notebook_path || '')
    const pp = projOfPath(f, cwd)
    if (pp && !/_施工记录\.md$/.test(f)) return '改工程 ' + pp.proj + '（' + tn + ' ' + pp.rel + '）'
    TOOLS_RE.lastIndex = 0
    const tm = TOOLS_RE.exec(f)
    if (tm) { const n = f.split(/[\\/]/).pop(); if (!DSH_OWN.test(n)) return '写通用工具 ' + n + '（' + tn + '）' }
    return null
  }
  if (tn === 'Bash') return classifyBash(ti.command, cwd)
  if (/^mcp__UnityMCP__/.test(tn)) {
    const op = tn.replace('mcp__UnityMCP__', '')
    // 先去掉字符串字面量再匹配：只读查询里的 "isPlaying=" 这类文字曾被误判成修改（09-22）
    if (op === 'execute_code') return UNITY_MUT.test(String(ti.code || '').replace(/"(?:[^"\\]|\\.)*"/g, '""')) ? 'Unity 改动（execute_code 含修改 API）' : null
    if (op === 'execute_menu_item') return 'Unity 跑菜单项 ' + String(ti.menu_path || ti.menuPath || '')
    if (/^(script_apply_edits|apply_text_edits|create_script|delete_script|import_model|import_model_file|run_tests|batch_execute|generate_\w+)$/.test(op)) return 'Unity ' + op
    if (op === 'manage_editor') return /^(play|pause|stop|enter_play|set_\w+|add_\w+|remove_\w+)$/i.test(String(ti.action || '')) ? 'Unity manage_editor ' + ti.action : null
    if (/^manage_/.test(op)) { const a = String(ti.action || ''); return a && !READ_ACT.test(a) ? 'Unity ' + op + ' ' + a : null }
    return null
  }
  if (/^mcp__Blender__execute_blender_code/.test(tn)) return 'Blender 执行代码'
  return null
}

let buf = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', d => { buf += d })
process.stdin.on('end', () => {
  let j
  try { j = JSON.parse(buf || '{}') } catch (e) { return }
  let what = null
  try { what = classify(String(j.tool_name || ''), j.tool_input || {}, j.cwd || WS) } catch (e) { return }
  if (!what) return
  const sid = String(j.session_id || 'nosession').replace(/[^\w-]/g, '')
  const sf = path.join(STATE_DIR, sid + '.json')
  const st = loadJson(sf)
  const now = Date.now()
  const ex = loadJson(EXEMPT_FILE)
  const exempt = ex.until && ex.until > now
  st.directTotal = (st.directTotal || 0) + 1
  st.direct = (st.direct || []).concat([{ t: now, what, ex: exempt ? ex.cat : '' }]).slice(-30)
  const out = { hookEventName: 'PreToolUse' }
  if (exempt) {
    st.directExempt = (st.directExempt || 0) + 1
    try { fs.appendFileSync(EXEMPT_LOG, new Date(now).toISOString() + '\t放行\t' + ex.cat + '\t' + what + '\n') } catch (e) { /* ignore */ }
    out.additionalContext = '【派工闸口·豁免中（' + ex.cat + '：' + ex.reason + '）】' + what + ' 已放行并留档；收尾时写进该工程 _施工记录.md。'
  } else {
    st.directSinceDsh = (st.directSinceDsh || 0) + 1
    st.directUnexempt = (st.directUnexempt || 0) + 1
    const n = st.directSinceDsh
    const recent = st.direct.filter(x => !x.ex).slice(-3).map(x => '  · ' + x.what).join('\n')
    const how =
      '按准则 5：执行活（含改工程、改交付文档、跑构建/测试）默认写任务书派 DSH：\n' +
      '  node 开发工具/通用工具/dsh_task.js --model flash --cwd "$PWD" --record <工程目录> [--lock unity] --task-file <任务书.md> --timeout 3600\n' +
      '  （--record 让 DSH 自己追加施工记录并 ws_git 提交，跑完用 git 核对；Claude 只验收：git show --stat、回读值、复跑判据）\n' +
      '合法例外只有六类，先声明再动手：node .claude/hooks/delegate-check.js --exempt <' + CATS.join('|') + '> "<理由>"\n' +
      '「上下文都在我脑子里、交代成本高」「就改一行」不是合法理由。'
    if (n >= DENY_AT) {
      out.permissionDecision = 'deny'
      out.permissionDecisionReason = '【派工闸口·已拦】自上次派 DSH 以来你已第 ' + n + ' 次直接改工程/写项目工具：\n' + recent + '\n' + how
    } else {
      out.additionalContext = '【派工闸口·提醒 ' + n + '/' + (DENY_AT - 1) + '】' + what + ' —— 这是 Claude 直接动手。第 ' + DENY_AT + ' 次起会被拦。\n' + how
    }
  }
  saveJson(sf, st)
  process.stdout.write(JSON.stringify({ hookSpecificOutput: out }))
})
