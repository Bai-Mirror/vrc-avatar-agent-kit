#!/usr/bin/env node
/**
 * 【项目沉淀】通用工具
 * 适用素体：无关          相关素材：无
 * 可复用性：★★★ 换个单子直接能用
 * 用途　　：向 DeepSeek Harness 派一次工，并**在事后从会话日志里核验它到底做了什么**。
 *
 * 为什么不用裸 `dsh --profile headless`（三条，都是实测踩出来的）：
 *
 *   ① **模型选错是静默失败。** 2026-09 早期的 deepseek-v4-flash 收到图片不报错、
 *      prompt_tokens 只有 20-40（图根本没进去），然后编出像模像样的答案 ——
 *      实测让它数圆点，真值 23 它答 22；让它读六个色块 hex，六个全是编的。
 *      现在（09-11 起）只剩 V4.1-Flash 一个模型：纯文本走 `flash`（deepseek-flash），
 *      带图必须走 `vision`（deepseek-v4-flash-vision-exp，harness 只给这个名字声明了图像输入）。
 *      闸门保留：`--images` 只放行 VISION_CAPABLE 里的别名，**任何没声明图像输入的别名都会重演这个形态**。
 *
 *   ② **headless 里图片是靠 `read_image` 工具进去的，不是附件。** 因此「它有没有真看图」
 *      的判据不是 token 数，而是**会话日志里 read_image 的调用次数与路径**。
 *      本脚本 --images 会自动追加取图指令，跑完逐张核对，缺一张就判 FAIL。
 *
 *   ③ **Unity / Blender 同一时刻只能一方持有。** Claude 侧和 DSH 侧都会连同一个
 *      Unity 编辑器与 Blender 插件 socket。--lock 走 ~/.dsh/handoff.lock 交接。
 *
 * 用法：
 *   node dsh_task.js --task "..." [--task-file t.md] [--cwd DIR]
 *                    [--model flash] [--images a.png,b.png]
 *                    [--lock unity|blender] [--timeout 900] [--json out.json]
 *                    [--record <工程目录> | --no-record] [--journal [路径] | --no-journal]
 *                    [--no-parts-check] [--dry-run] [--snapshot-cmd "<只读命令>"]... [--snapshot-expect changed|unchanged | --no-snapshot]
 *   ⑥（2026-09-23 工作流审理）：--timeout 没给时按任务书形状定 900/3600；.dsh_slots 槽位让嵌套派工也计入并发；
 *      --snapshot-cmd 前后快照 Diff（B3 基线验收）；回复里「已启动后台 X」用 pgrep 核；渲图洋红只警告。
 *
 *   ④ **改工程的活也派，留痕由 DSH 自己做**（作者 2026-09-22）：带 `--record <工程目录>` 时，
 *      任务书末尾自动附加「追加该工程 _施工记录.md + ws_git.py 提交」的硬要求，跑完用 git 核对
 *      它真的提交了、施工记录在提交里、工程下没有遗留未提交改动；缺一项判 FAIL（退出码 2）。
 *      带 `--lock` 却既没 `--record` 也没 `--no-record` 的派工直接拒绝——动编辑器就得先表态改不改工程。
 *      自检：node dsh_task.js --selftest-record <工程目录> --since <ISO 时间或毫秒>（只跑 git 核对，不派工）
 *   ⑤ **装配/菜单类任务自动查「部件图鉴」**（H-06，作者 2026-09-22）：任务文本命中
 *      `/装配|菜单|部件图鉴|换装|服装/` 时，从文本里抓 6–8 位且 `<素材库>/*-<号>` 存在的
 *      Booth 商品号，逐个跑 `部件图鉴/check_parts_doc.py --json`，结果作为一段
 *      「【部件图鉴查档（dsh_task 自动）】…」追加到任务书末尾并打到 stderr。
 *      **查档失败只告警、不阻断派工**（脚本退出码 10/20/30 是四态，不算失败）；
 *      `--no-parts-check` 关。`--dry-run` 只打印拼好的任务书、不取锁不派工（验收用）。
 *
 *   ⑦ **Codex 引擎**（作者 2026-09-23）：`--engine auto|dsh|codex`（缺省 auto：北京工作日 09-12、14-18 DeepSeek 高峰走 Codex，
 *      其余走 DSH）；Codex 档位 `--model luna|terra|sol|astra|luna6` ＋ `--effort low…ultra`；留痕、快照、锁、流水账与 DSH 同一套。
 *      Codex 并发 ≤2（CODEX_TASK_MAX_SESS），周额度已用 ≥85%（CODEX_MAX_USED_PCT）拒派。规程：SOP/01_自动化执行与并行/Codex派工.md
 *
 * 退出码：0 = DSH 跑完且核验通过；1 = 派工前快照失败或 DSH 失败；2 = DSH 跑完但核验不通过（重点看这个）。
 *
 * 相关：dsh_session.js（读会话）、开发工具/SOP/01_自动化执行与并行/DSH派工.md（规程）
 */
'use strict'
const fs = require('fs')
const path = require('path')
const os = require('os')
const { spawnSync } = require('child_process')
const { captureSnapshot, snapshotFailure, compareSnapshotText } = require('./dsh_snapshot')
const kit = require('./kit_env')   // 读 <工作区>/kit.env（环境变量优先）；路径类配置见仓库根 kit.env.example
// 素材库根（可选）：VRC_ASSET_ROOT，目录下是 `<商品名>-<Booth 商品号>` 子目录；不设则跳过部件图鉴自动查档
const ASSET_ROOT = kit.get('VRC_ASSET_ROOT', '')

const HOME = process.env.DSH_HOME || path.join(os.homedir(), '.dsh')
const LOCK = path.join(HOME, 'handoff.lock')
// ⛔ 2026-09-22 H-05 查实的根因：会话目录必须跟**子进程**走，不能跟 DSH_HOME 走。
//   子进程 env 里 DSH_HOME 被删掉（见下方 childEnv），它按自己的 $HOME 写 `$HOME/.dsh/sessions`；
//   而嵌套派工时本脚本从 DSH 的 bash 工具继承了 DSH_HOME=~/.dsh、HOME=<影子目录>，
//   原来按 DSH_HOME 去找 ⇒ 永远找不到 ⇒ 嵌套派工 100% 假 FAIL（H-05 6/6、10/10）。
//   交接锁 LOCK 仍用 HOME（真家目录），好让嵌套与非嵌套看到同一把锁。
const SESS = path.join(os.homedir(), '.dsh', 'sessions')

// ── 模型：2026-09-11 起只剩 V4.1-Flash 一个模型；纯文本 `flash`，带图 `vision` ─────────
// 现行结论与变更记录见 SOP/01_自动化执行与并行/DSH模型与视觉能力.md 第一节。
// 依据是 DeepSeek 当天的公告与《模型细节》页：
//   · 旧名 `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` 仍可调用，
//     但**对应模型已下线**，请求一律由 DeepSeek-V4.1-Flash 承接、按 Flash 价计费。
//     纯文本只写 `deepseek-flash`；`deepseek-v4-flash-vision-exp` 只因下面那条声明问题留作 `vision` 别名。
//   · `deepseek-v4-pro`：2026-09-14 12:00（北京）之后请求也全部路由到 V4.1-Flash。
//   · `deepseek-flash` **支持图像理解**（官方明确），1M 上下文，最大输出 384K，并发 2500。
//
// ⛔ 一条要记住的教训：2026-09-10 我判过「v4.1 不能读图」，依据是
//    `deepseek-v4.1-flash-expires-on-0910` 对 read_image 硬拒
//    `does not declare image input`。**那是那个临时别名没声明图像输入，
//    不是 V4.1 这个模型不行** —— 官方细节页写着 deepseek-flash 图像理解=支持。
//    ⇒ 能力要按**当前正式模型名**查，别拿一个过期别名的行为去推断模型。
const DEEPSEEK_FLASH = 'deepseek-flash'
// ⛔ 2026-09-11 当天实测出的一条反直觉事实，别再想当然合并这两个别名：
//   `deepseek-flash` 传图会被硬拒 —— `model "deepseek-flash" does not declare image input`。
//   **这不是模型不行**（官方《模型细节》写着 V4.1-Flash 图像理解=支持），
//   是 **DSH 这个 harness 的模型能力声明里没给它加图像输入**。
//   而旧别名 `deepseek-v4-flash-vision-exp` 声明了图像输入，且按 09-11 公告，
//   它底下**也是同一个 V4.1-Flash**、按 Flash 价计费。
//   ⇒ 纯文本用 `flash`；**带图一律用 `vision`**。两者是同一个模型，差的只是声明。
//   （这条是被 --images 的结果核验闸门抓出来的：两路设计评审在没看到图的情况下
//     写了 18KB 的方案，若无闸门会被当成正常结论采信。）
const MODELS = {
  flash: DEEPSEEK_FLASH,                    // 纯文本，默认
  vision: 'deepseek-v4-flash-vision-exp',   // 带图任务用这个（同一模型，harness 声明了图像输入）
  v41: DEEPSEEK_FLASH,                      // 兼容旧命令行
}
// ⛔⛔ 硬禁名单：命中直接拒绝派工。
// **作者 2026-09-11 明令：现在绝对不允许使用 Pro，除非他本人日后解禁。**
// 解禁 = 用户明确说了才能改这段，不是「这次任务好像更适合 pro」就能绕。
const BANNED = {
  pro: 'deepseek-v4-pro 已被用户明令禁用（2026-09-11），**只有用户本人能解禁**。\n' +
       '    附带事实：它 09-14 12:00（北京）后请求也会被路由到 V4.1-Flash，' +
       '不支持图像理解，并发只有 500（flash 是 2500），价格贵 4.5 倍。\n' +
       '    用 --model flash。',
}
// 同时挡住绕过别名、直接把线上 model id 传进来的写法。
const BANNED_ID = /v4-pro|deepseek-pro/i

// ⛔ 2026-09-22 修：原实现无条件取下一个参数当值。规程与用法都把 `--journal` 当开关写，
//   于是 `--journal --json x.json` 把流水账写进了工作区根下一个名叫「--json」的文件，
//   `--journal --task-file t.md` 写进了「--task-file」——09-19 之后 _DSH流水账.md 一条都没进。
//   现在：下一个参数以 -- 开头就视为「没给值」。
function arg(name, dflt) {
  const i = process.argv.indexOf(name)
  const v = i >= 0 ? process.argv[i + 1] : undefined
  return v && !v.startsWith('--') ? v : dflt
}
const has = name => process.argv.indexOf(name) >= 0
const WS_ROOT = kit.WS   // 工作区根：VRC_WS，缺省按本脚本位置推算（开发工具/通用工具/ 往上两级）

// --- --record 的事后核对：DSH 有没有按规程留痕（施工记录 + ws_git 提交、无遗留改动）---
function gitOut(args) {
  const r = spawnSync('git', ['-C', WS_ROOT, '-c', 'core.quotepath=false', ...args],
    { encoding: 'utf8', timeout: 30000, maxBuffer: 64 * 1024 * 1024 })
  return r.status === 0 ? (r.stdout || '') : ''
}
function recordCheck(projAbs, sinceMs, answerText) {
  const rel = path.relative(WS_ROOT, projAbs).split(path.sep).join('/')
  const logRel = rel + '/_施工记录.md'
  const commits = []
  for (const blk of gitOut(['log', '-n', '80', '--format=%x1e%h%x09%ct%x09%s', '--name-only', '--', rel]).split('\x1e')) {
    const lines = blk.split('\n').filter(Boolean)
    if (!lines.length) continue
    const [h, ct, subj] = lines[0].split('\t')
    if (Number(ct) * 1000 < sinceMs - 2000) continue
    commits.push({ hash: h, subject: subj || '', files: lines.slice(1) })
  }
  const pending = []
  const st = gitOut(['status', '--porcelain', '-z', '--untracked-files=all', '--', rel]).split('\0').filter(Boolean)
  for (let i = 0; i < st.length; i++) {
    const code = st[i].slice(0, 2), p = st[i].slice(3)
    if (code[0] === 'R' || code[0] === 'C') i++
    let m = Date.now()
    try { m = fs.statSync(path.join(WS_ROOT, p)).mtimeMs } catch (e) { /* 删除的算本次 */ }
    if (m >= sinceMs - 2000) pending.push(p)
  }
  const withLog = commits.filter(c => c.files.includes(logRel))
  const noChange = /无改动\s*[:：]/.test(answerText || '')
  const probs = []
  if (!withLog.length && !(noChange && !commits.length && !pending.length))
    probs.push('未按规程留痕：派工开始后没有任何提交包含 ' + logRel +
      (commits.length ? '（有 ' + commits.length + ' 个提交但都没带施工记录）' : '（没有提交）'))
  if (pending.length)
    probs.push('工程下还有 ' + pending.length + ' 个本次改动没提交：' + pending.slice(0, 5).join('、'))
  return { rel, commits, withLog: withLog.map(c => c.hash), pending, noChange, problems: probs }
}
if (has('--selftest-record')) {
  const proj = path.resolve(arg('--selftest-record', '.'))
  const sv = arg('--since', null)
  const since = sv ? (/^\d+$/.test(sv) ? Number(sv) : Date.parse(sv)) : Date.now() - 3600 * 1000
  console.log(JSON.stringify(recordCheck(proj, since, ''), null, 2))
  process.exit(0)
}

// ── ⑦ 引擎：DSH（DeepSeek）或 Codex（ChatGPT 订阅），作者 2026-09-23 定 ─────────────
//   北京时间周一~周五 09-12、14-18 是 DeepSeek 高峰（价格翻倍），这段时间执行活改走 Codex；其余时段仍走 DSH Flash。
//   --engine auto（缺省）按时段自动选；显式 dsh / codex 覆盖；--model 给了 Codex 别名也视为 codex。
//   Codex 档位：luna=日常执行；terra/sol=改模、复杂代理；astra=与 Fable 协作的复杂创作；全部能读图（-i 附件）。
//   Codex 沙箱 workspace-write 默认把 .git 设成只读 ⇒ 必须 --add-dir <工作区>/.git，否则 --record 的 ws_git 提交必败（09-23 实测）。
function beijingPeak(d) {
  const b = new Date((d || new Date()).getTime() + 8 * 3600 * 1000)
  const wd = b.getUTCDay(), h = b.getUTCHours() + b.getUTCMinutes() / 60
  return wd >= 1 && wd <= 5 && ((h >= 9 && h < 12) || (h >= 14 && h < 18))
}
const CODEX_MODELS = {
  luna: 'gpt-5.6-luna', terra: 'gpt-5.6-terra', sol: 'gpt-6-sol', astra: 'gpt-6-astra', luna6: 'gpt-6-luna',
}
const CODEX_EFFORTS = { luna: 'max', luna6: 'max', terra: 'ultra', sol: 'ultra', astra: 'ultra' }
const EFFORT_ORDER = ['low', 'medium', 'high', 'xhigh', 'max', 'ultra']
const engineArg = arg('--engine', process.env.DSH_TASK_ENGINE || 'auto')
if (!['auto', 'dsh', 'codex'].includes(engineArg)) { console.error('--engine 只认 auto / dsh / codex'); process.exit(1) }
const modelArg = arg('--model', null)
const engine = engineArg !== 'auto' ? engineArg
  : (modelArg && CODEX_MODELS[modelArg]) ? 'codex' : (beijingPeak() ? 'codex' : 'dsh')
if (engineArg === 'auto') console.error('[引擎] auto → ' + engine + '（北京' + (beijingPeak() ? '高峰' : '空闲') + '时段）')
let modelKey = modelArg || (engine === 'codex' ? 'luna' : 'flash')
if (engine === 'codex' && MODELS[modelKey]) modelKey = 'luna'   // flash/vision 的任务书在高峰期照原样派，落到 luna
if (BANNED[modelKey]) { console.error('⛔ ' + BANNED[modelKey]); process.exit(1) }
if (BANNED_ID.test(modelKey)) {
  console.error('⛔ 拒绝派工：' + modelKey + ' 命中 Pro 禁用名单（作者 2026-09-11 明令）。用 --model flash。')
  process.exit(1)
}
const model = engine === 'codex' ? CODEX_MODELS[modelKey] : MODELS[modelKey]
if (!model) {
  console.error('未知模型别名: ' + modelKey + '（' + engine + ' 可用: ' +
    Object.keys(engine === 'codex' ? CODEX_MODELS : MODELS).join(' / ') + '）')
  process.exit(1)
}
const effort = arg('--effort', 'medium')
if (engine === 'codex' && !(EFFORT_ORDER.indexOf(effort) >= 0 && EFFORT_ORDER.indexOf(effort) <= EFFORT_ORDER.indexOf(CODEX_EFFORTS[modelKey]))) {
  console.error('--effort ' + effort + ' 超出 ' + modelKey + ' 支持范围（最高 ' + CODEX_EFFORTS[modelKey] + '）'); process.exit(1)
}
const AGENT = engine === 'codex' ? 'Codex' : 'DSH'

const cwd = path.resolve(arg('--cwd', process.cwd()))
let timeoutSec = Number(arg('--timeout', 0))
const lockKind = arg('--lock', null)
const jsonOut = arg('--json', null)
// --journal：把这次派工自动追加进工程流水账。
// 为什么要它：文档滞后的根因是「指望模型记得去更新」。模型侧的语义更新照样要做，
// 但**流水账必须是确定性的** —— 谁在什么时候用什么模型干了什么、核验过没有，
// 不能依赖它自觉。这一份是事后复盘时唯一能信的时间线。
//   2026-09-22 起**缺省开启**，写工作区根的 _DSH流水账.md（`--journal <路径>` 改写别处，`--no-journal` 关）。
const journal = has('--no-journal') ? null : path.resolve(arg('--journal', path.join(WS_ROOT, '_DSH流水账.md')))
// --record <工程目录>：见文件头 ④。
let recordProj = null
if (has('--record')) {
  const rv = arg('--record', null)
  if (!rv) { console.error('--record 要跟工程目录'); process.exit(1) }
  recordProj = path.resolve(cwd, rv)
  if (!fs.existsSync(path.join(recordProj, '_施工记录.md'))) {
    console.error('拒绝派工：' + recordProj + ' 下没有 _施工记录.md，不像工程目录'); process.exit(1)
  }
}
if (lockKind && !recordProj && !has('--no-record')) {
  console.error('拒绝派工：带 --lock 说明要动编辑器。改工程的派工必须 --record <工程目录>' +
    '（DSH 自己追加施工记录并 ws_git 提交，Claude 只验收）；纯只读排查请显式写 --no-record。')
  process.exit(1)
}
const images = (arg('--images', '') || '').split(',').map(s => s.trim()).filter(Boolean)

let task = arg('--task', null)
const taskFile = arg('--task-file', null)
if (taskFile) task = fs.readFileSync(taskFile, 'utf8')
if (!task) { console.error('必须给 --task 或 --task-file'); process.exit(1) }
// A4（2026-09-23 工作流审理）：主会话 246 次派工里 102 次没写 --timeout，多步任务书按 900 s 会被中途杀（09-19 三个同批被杀）。
//   没给就看任务书形状：>2000 字或 ≥3 个列表项按 3600 s，否则 900 s。显式给了就不猜。
if (!timeoutSec) {
  const steps = (task.match(/^\s*(\d+[.、)]|[-*])\s+/gm) || []).length
  timeoutSec = (task.length > 2000 || steps >= 3) ? 3600 : 900
  if (timeoutSec === 3600) console.error('[提示] 未给 --timeout，任务书像多步任务（' + task.length + ' 字、' + steps + ' 个列表项），按 3600 s；单步小任务请显式 --timeout 900')
}
// B3 基线 Diff（作者 2026-09-23 拍板）：--snapshot-cmd "<只读命令>" 可重复，派工前后各跑一次，差异印进核验块与流水账；DSH 碰不到它。
const snapCmds = process.argv.reduce((acc, v, i, arr) => (v === '--snapshot-cmd' && arr[i + 1] && !arr[i + 1].startsWith('--') ? acc.concat(arr[i + 1]) : acc), [])
const snapExpect = arg('--snapshot-expect', 'changed')   // changed | unchanged
if (recordProj && !snapCmds.length && !has('--no-snapshot')) {
  console.error('⚠ --record 却没有 --snapshot-cmd：基线 Diff 验收缺前后快照。给 1 条以上只读命令（dump_vrc_menu.py / grep -c / sha256sum …），或 --no-snapshot 明示放弃')
}

// 能读图的别名白名单。
// 2026-09-11 起三个别名底下都是 V4.1-Flash，但 harness 只给 `vision` 的 model id 声明了图像输入，
// 所以名单里只有 `vision`（`flash`/`v41` 传图会被硬拒）。
// ⚠ 这道闸门**不删**：它拦的是「纯文本模型收到图会静默编答案」这一类。
//   将来若再引入不支持图像的模型别名，加进 MODELS 时记得**不要**加进这里，
//   并且先真跑一次 read_image 看它认不认 —— 别信文档里的历史结论。
//   （下面核验段还会按 callId 回查 tool/result，被拒的不计入「读图 N/M」。）
// 只有 `vision` 这个别名对应的 model id 在 harness 里声明了图像输入。见上面 MODELS 的注释。
const VISION_CAPABLE = new Set(['vision'])
if (images.length && engine === 'dsh' && !VISION_CAPABLE.has(modelKey)) {
  console.error('拒绝派工：--images 只能配能读图的模型（' +
    [...VISION_CAPABLE].join(' / ') + '）。' +
    '非视觉模型收到图不会报错，会静默编造答案。')
  process.exit(1)
}
for (const im of images) {
  if (!fs.existsSync(im)) { console.error('图不存在: ' + im); process.exit(1) }
}

// --- --brief：先读工程速查档，别每次重扫原始文件 ---
// 为什么要它（作者 2026-09-09 定）：跨次派工**不共享上下文**，每开一个新会话，
// 那批原始材料就要重新读一遍、全额计费。今晚为脚部一个问题连派 4 次，
// 每次都重读同一批 clip 与场景 —— 等于付了 4 次全额摄入。
// 速查档是「已核验过的事实」的浓缩版（几 K），代替几十 K 的原始扫描。
const briefPath = arg('--brief', null)
if (briefPath) {
  task = '【先读这个 —— 本工程的事实速查档】\n' + briefPath + '\n' +
    '它是前几轮派工核验过的结论汇总，**优先用它，不要重新全量扫描原始文件**。\n' +
    '只有当它没覆盖你要的信息、或你有理由怀疑它过时了，才去读原始资产 —— ' +
    '那种情况请在报告里明写「速查档缺 X，我另外读了 Y」。\n\n---\n\n' + task
}

// 查档只看**用户给的任务正文＋速查档抬头**，不看后面自动附加的留痕/落盘样板，
// 免得样板里的字眼误触发。
const taskForParts = task

// --- --doc：让它把结论就地写回项目文档，而不是只回一段话给我 ---
// 文档滞后的另一半原因：结论只存在于回复里，没人落盘。
// 这条指令是**追加在任务书末尾**的，所以每次派工都会看到，不靠它自觉。
const docPath = arg('--doc', null)
if (docPath) {
  task += '\n\n---\n【落盘要求 —— 这一条不做就算没做完】\n' +
    '完成上面的任务后，把结论**就地写回** `' + docPath + '`：\n' +
    '· 找到该文件里对应的小节；没有对应小节就在文末新增一节，标题带今天的日期。\n' +
    '· 只写**结论与证据**（文件:行号、数值），不要复述过程，不要把整段回复贴进去。\n' +
    '· **不要删除或改写别人写的既有内容**，只新增或在明确过时的行后面追加一行说明。\n' +
    '· 写完回读一遍确认写进去了，并在你的回复末尾单独一行报告：`已更新: <文件> 第X-Y行`。\n' +
    '· 如果判断不需要改动该文档，就在回复末尾写 `无需更新: <一句话理由>`。'
}

// --- --record：留痕要求追加在任务书末尾，每次派工都会看到，不靠它自觉 ---
if (recordProj) {
  const rel = path.relative(WS_ROOT, recordProj).split(path.sep).join('/')
  task += '\n\n---\n【留痕要求 —— 不做就算没做完（dsh_task.js --record 自动附加，事后会用 git 核对）】\n' +
    '你对工程 `' + rel + '` 做了任何改动，收尾前必须依次完成：\n' +
    '1. 在 `' + WS_ROOT + '/' + rel + '/_施工记录.md` **末尾追加**一条：标题 `## YYYY-MM-DD HH:MM · <做了什么>（' + AGENT + '）`，' +
    '正文四段：**做了什么 / 怎么验（贴关键读数与工具输出）/ 结果 / 未决**。只追加，不改别人写的内容。\n' +
    '2. 在 `' + WS_ROOT + '` 下执行 `python3 开发工具/通用工具/ws_git.py commit -m "[<工程简称>] <一句话>（' + AGENT + '）" -- <你改过的每个路径> ' +
    rel + '/_施工记录.md`，**只点名你改过的路径**，不要用 `git add -A`。\n' +
    '3. 回复末尾单独一行写 `已提交: <commit 短哈希>`。若本次确实没有改动任何文件，写 `无改动: <理由>`，此时不要提交。\n' +
    '4. 生成的临时文件放工作区 `_dsh_tmp_<任务名>/`（沙箱里 /tmp 每条命令后清空），用完删；不要留在工程目录里（未提交的遗留改动会判 FAIL）。'
}

// --- 部件图鉴查档（H-06）：装配/菜单类任务自动查档，结果追加到任务书末尾 ---
// 只告警、不阻断派工：脚本退出码 10/20/30 是四态不是失败；跑不起来也只打进 stderr。
const PARTS_DOC_RE = /装配|菜单|部件图鉴|换装|服装/
const PARTS_DOC_PY = path.join(__dirname, '部件图鉴', 'check_parts_doc.py')
function partsCheckSection(source) {
  const head = '【部件图鉴查档（dsh_task 自动）】'
  let vrcNames = []
  if (!ASSET_ROOT) return '\n\n---\n' + head + '\n未配置素材库（kit.env 的 VRC_ASSET_ROOT），跳过自动查档；装配/菜单任务按 SOP 50 第一节手动查档。\n'
  try { vrcNames = fs.readdirSync(ASSET_ROOT) } catch (e) { vrcNames = [] }
  const seen = new Set()
  const items = []
  const re = /(?<!\d)(\d{6,8})(?!\d)/g
  let m
  while ((m = re.exec(source)) !== null) {
    const n = m[1]
    if (seen.has(n)) continue
    if (vrcNames.some(d => d.endsWith('-' + n))) { seen.add(n); items.push(n) }
  }
  if (!items.length) {
    return '\n\n---\n' + head + '\n' +
      '任务文本未含可查的 Booth 商品号（6–8 位且 `' + ASSET_ROOT + '/*-<号>` 存在）。' +
      '若这是装配/菜单任务，仍按 SOP 50 第一节手动查档。\n'
  }
  const lines = [head]
  for (const it of items) {
    try {
      const r = spawnSync('python3', [PARTS_DOC_PY, '--json', '--item', it],
        { encoding: 'utf8', timeout: 60000, maxBuffer: 16 * 1024 * 1024 })
      if (r.error) throw r.error
      const res = JSON.parse((r.stdout || '').trim())
      const one = (res.results || [])[0] || {}
      lines.push('- Booth ' + it + ' → ' + (one.state || '?') +
        '（退出码 ' + (res.exit_code != null ? res.exit_code : '?') + '）')
      for (const p of (one.products || [])) lines.push('    商品目录: ' + p)
      for (const d of (one.docs || [])) lines.push('    图鉴: ' + d)
      for (const mm of (one.manifests || [])) lines.push('    部件清单: ' + mm)
      for (const im of (one.images || [])) lines.push('    部件图: ' + im + '/')
      for (const s of (one.source_dirs || [])) lines.push('    素材源: ' + s)
      if (one.state === '有图鉴（含本素体）') lines.push('    先读图鉴「菜单建议 / 冲突处理 / 未决」三栏再动手（SOP 50 第一节）')
      if (one.state === '有图鉴（缺本素体）') lines.push('    ⚠ 图鉴缺本素体：只补「适配素体差异」与受影响部件（SOP 50 第一节）')
      if (one.state === '只有清单和图') lines.push('    按 SOP 50 第一节：从第 3 步起跑建档，菜单与收缩键在图鉴补全前不定稿')
      if (one.state === '都没有') lines.push('    按 SOP 50 第一节：按顺序建档；装配任务缺图鉴不停工')
    } catch (e) {
      lines.push('- Booth ' + it + ' → ⚠ 查档脚本失败（只告警、不阻断派工）：' + (e && e.message))
    }
  }
  return '\n\n---\n' + lines.join('\n') + '\n'
}
if (!has('--no-parts-check') && PARTS_DOC_RE.test(taskForParts)) {
  const partsSection = partsCheckSection(taskForParts)
  task += partsSection
  console.error(partsSection.replace(/^\n+/, '').replace(/\n+$/, ''))
}

// --- 带图任务：把取图动作写成显式指令，事后可核验 ---
if (images.length && engine === 'codex') {
  task = '本消息附带 ' + images.length + ' 张图（按顺序对应下列路径），结论必须基于你实际看到的图；' +
    '哪张看不清或没收到就明说，不许凭路径名推断：\n' +
    images.map((p, i) => '  ' + (i + 1) + '. ' + path.resolve(p)).join('\n') + '\n\n' + task
} else if (images.length) {
  task = '你必须先逐张调用 read_image 工具读取下列图片，然后再回答。不许跳过任何一张，' +
    '也不许在没读图的情况下作答：\n' +
    images.map((p, i) => '  ' + (i + 1) + '. ' + path.resolve(p)).join('\n') +
    '\n\n读完之后，回答下面的任务：\n\n' + task
}

// ⛔ 2026-09-11 修的一个静默错：会话指纹原来取 `task.slice(0, 120)`。
//   `--brief` 会给**每一路**任务前置同一段固定抬头（「先读这个 —— 本工程的事实速查档」…），
//   那段远超 120 字 ⇒ **所有路的指纹完全相同**。并发派 5 路时五个进程都认领了同一个会话，
//   核验块报出的模型/工具/收尾全是别人的。实测症状：三路报同一个 session id、
//   都判 FAIL（收尾 `?`），**而回答其实都是好的** —— 典型的「核验比任务先坏」。
//   ⇒ 改成在任务末尾埋一个一次性 nonce，按它认领。
//     顺带也解决非并发场景下「两路任务正文开头恰好相同」的误认。
//   ⚠ 必须在 spawn **之前**拼进 task，否则子进程根本没见过这个 nonce。
if (engine === 'codex') {
  task = '【派工身份（dsh_task.js 自动附加）】你是 VRChat 头像定制工作区 `' + WS_ROOT + '` 的执行子代理，主理是 Claude，事后会用 git 与读数验收。\n' +
    '· 规程在 `开发工具/SOP/`（入口 00_总表.md），只读任务书点名或与本任务直接相关的页；不改 SOP 主体、CLAUDE.md、.claude/。\n' +
    '· 不可逆动作（删存档、覆盖交付包、丢弃场景改动、SDK 上传）不做，写进回复的「未决」。Unity 只通过 unityMCP 操作且仅在派工持锁时。\n' +
    '· 结论带证据（文件:行号、读数、工具输出）；做不到就如实写没做到，不要编。\n\n' + task
}
const TASK_NONCE = 'dsh-task-' + process.pid + '-' + Date.now().toString(36)
task += '\n\n<!-- 派工标识 ' + TASK_NONCE + '（供事后核验认领会话用，与任务无关，忽略它） -->\n'

// --- --dry-run：只把拼好的任务书（含自动追加的查档段）打出来，不取锁、不派工 ---
// 给 H-06 这类「改派工脚本本身」的验收用：一眼看到 DSH 将要收到什么。
if (has('--dry-run')) {
  if (lockKind) console.error('（--dry-run：不取 ' + lockKind + ' 锁、不派工；以上查档段为自动追加内容）')
  console.log(task)
  process.exit(0)
}

// --- 交接锁 ---
function readLock() {
  try { return JSON.parse(fs.readFileSync(LOCK, 'utf8')) } catch (e) { return null }
}
function acquire(kind) {
  const cur = readLock()
  if (cur && cur.kind === kind && cur.holder !== 'dsh') {
    console.error('拒绝派工：' + kind + ' 当前被 ' + cur.holder + ' 持有（自 ' + cur.since + '）。' +
      '先交接再派工 —— 两侧同时驱同一个编辑器会互相打断。')
    process.exit(1)
  }
  fs.writeFileSync(LOCK, JSON.stringify({
    kind, holder: 'dsh', since: new Date().toISOString(), pid: process.pid,
  }, null, 2))
}
function release() {
  const cur = readLock()
  if (cur && cur.holder === 'dsh' && cur.pid === process.pid) {
    try { fs.unlinkSync(LOCK) } catch (e) { /* 已被清掉就算了 */ }
  }
}
// --- 槽位文件（2026-09-23）：嵌套派工在沙箱里 pgrep 看不到别的会话，但看得到工作区文件。
//   每个派工写 <工作区>/.dsh_slots/<pid>.json（until = 启动 + timeout + 2 min），闸门取 max(pgrep 数, 活槽位数)。
//   沙箱里写不进工作区根时静默跳过（pgrep 在外层仍数得到它）。
const SLOTS = path.join(WS_ROOT, '.dsh_slots')
let PIDNS = null; try { PIDNS = fs.readlinkSync('/proc/self/ns/pid') } catch (e) { /* 非 Linux */ }  // 嵌套沙箱的 pid 属另一命名空间，只对同命名空间的槽位查存活
function liveSlots(eng) {
  let n = 0
  try {
    fs.mkdirSync(SLOTS, { recursive: true })
    const now = Date.now()
    for (const f of fs.readdirSync(SLOTS)) {
      const fp = path.join(SLOTS, f)
      try { const j = JSON.parse(fs.readFileSync(fp, 'utf8')); let alive = true; if (j.pidns && j.pidns === PIDNS) { try { process.kill(j.pid, 0) } catch (e) { alive = e.code === 'EPERM' } }  // 09-23：会话重启杀掉的派工留下槽位，照 until 算会一直占并发位
      if (!alive) { fs.unlinkSync(fp); continue }
      if (j.until > now) { if ((j.engine || 'dsh') === eng) n++ } else fs.unlinkSync(fp) } catch (e) { try { fs.unlinkSync(fp) } catch (e2) { /* ignore */ } }
    }
  } catch (e) { /* ignore */ }
  return n
}
// --- 内存与并发闸门（2026-09-22 20:28 OOM 事故后加）---
//   Claude 起的 Unity/Blender/DSH 同在 Claude app 的 cgroup 里，峰值 22 GB 时内核把整组杀光。
//   规则见 SOP 02/B850_Linux环境/内存预算与并发.md：available < 8 GB 或本机 DSH 会话 ≥ 4 就等（每 30 s 查一次，最多 90 min）。
//   嵌套派工（在 DSH 沙箱里，PID 命名空间隔离）看不到别的会话，只剩内存那一条生效。`DSH_TASK_NO_GATE=1` 关闭。
function memAvailGB() {
  try {
    const m = /MemAvailable:\s+(\d+) kB/.exec(fs.readFileSync('/proc/meminfo', 'utf8'))
    return m ? Number(m[1]) / 1048576 : 99
  } catch (e) { return 99 }
}
function dshSessions() {
  const r = spawnSync('pgrep', ['-fc', '^[^ ]*node [^ ]*/bin\\.js --profile headless'], { encoding: 'utf8' })  // 只数 node 进程；别数命令行里恰好含这串字的 shell 外壳
  return Number((r.stdout || '0').trim()) || 0
}
// Codex 额度闸门（作者 2026-09-23：高峰期全替 DSH、并发 2）：ChatGPT 订阅按周窗口限额，
//   额度读数只在 rollout 的 token_count.rate_limits 里（最近一次会话的值），used_percent ≥ 阈值或已触限即拒派。
const CODEX_SESS = path.join(os.homedir(), '.codex', 'sessions')
function latestCodexRollouts(limit) {
  const out = []
  const walk = d => { let es = []; try { es = fs.readdirSync(d, { withFileTypes: true }) } catch (e) { return }
    for (const e of es) { const p = path.join(d, e.name); if (e.isDirectory()) walk(p); else if (/^rollout-.*\.jsonl$/.test(e.name)) out.push(p) } }
  walk(CODEX_SESS)
  return out.map(p => ({ p, m: fs.statSync(p).mtimeMs })).sort((a, b) => b.m - a.m).slice(0, limit).map(x => x.p)
}
function codexRateLimits() {
  for (const f of latestCodexRollouts(5)) {
    let rl = null
    try { for (const l of fs.readFileSync(f, 'utf8').split('\n')) { if (l.indexOf('"rate_limits"') < 0) continue
      const e = JSON.parse(l); if (e.payload && e.payload.rate_limits) rl = e.payload.rate_limits } } catch (e) { /* 坏行跳过 */ }
    if (rl) return rl
  }
  return null
}
if (engine === 'codex') {
  const rl = codexRateLimits(), MAXP = Number(process.env.CODEX_MAX_USED_PCT || 85)
  const used = rl && rl.primary ? Number(rl.primary.used_percent) : null
  console.error('[Codex 额度] ' + (used == null ? '无读数（首次派工或旧会话无 rate_limits）' :
    '周窗口已用 ' + used + '%，重置于 ' + new Date(rl.primary.resets_at * 1000).toLocaleString('zh-CN', { hour12: false })) + '，阈值 ' + MAXP + '%')
  if (rl && (rl.rate_limit_reached_type || (used != null && used >= MAXP))) {
    console.error('拒绝派工：Codex 额度触线（' + (rl.rate_limit_reached_type || used + '%') + '）。改 --engine dsh（空闲时段）或交用户决定。')
    process.exit(1)
  }
}
if (!process.env.DSH_TASK_NO_GATE) {
  const MIN_GB = Number(process.env.DSH_TASK_MIN_GB || 8)
  const MAX_SESS = engine === 'codex' ? Number(process.env.CODEX_TASK_MAX_SESS || 2) : Number(process.env.DSH_TASK_MAX_SESS || 4)
  const t0 = Date.now()
  for (;;) {
    const gb = memAvailGB(), n = engine === 'codex' ? liveSlots('codex') : Math.max(dshSessions(), liveSlots('dsh'))
    if (gb >= MIN_GB && n < MAX_SESS) break
    if (Date.now() - t0 > 90 * 60 * 1000) {
      console.error('拒绝派工：等了 90 min 仍不满足（可用内存 ' + gb.toFixed(1) + ' GB、' + AGENT + ' 会话 ' + n + ' 个）')
      process.exit(1)
    }
    console.error('[闸门] 可用内存 ' + gb.toFixed(1) + ' GB（要 ≥' + MIN_GB + '）、' + AGENT + ' 会话 ' + n + ' 个（要 <' + MAX_SESS + '），30 s 后再查')
    spawnSync('sleep', ['30'])
  }
}

if (lockKind) acquire(lockKind)
const SLOT_FILE = path.join(SLOTS, process.pid + '.json')
try {
  fs.writeFileSync(SLOT_FILE, JSON.stringify({ pid: process.pid, pidns: PIDNS, engine, start: Date.now(), until: Date.now() + timeoutSec * 1000 + 120000,
    task: (task.split('\n').find(l => l.trim()) || '').slice(0, 80) }))
} catch (e) { /* 沙箱里写不到工作区根就算了 */ }
process.on('exit', () => { try { fs.unlinkSync(SLOT_FILE) } catch (e) { /* ignore */ } })

const before = new Set(listSessionIds())
const started = Date.now()
function localStamp() { const d = new Date(); const z = n => String(n).padStart(2, '0'); return d.getFullYear() + '-' + z(d.getMonth() + 1) + '-' + z(d.getDate()) + '-' + z(d.getHours()) + z(d.getMinutes()) }
const SNAPDIR = snapCmds.length ? path.join(WS_ROOT, '_dsh_tmp_snapshots', localStamp() + '-' + process.pid) : null
function runSnap(cmd, tag, i) {
  return captureSnapshot(cmd, { cwd, file: path.join(SNAPDIR, tag + '_' + i + '.txt'), phase: tag, index: i })
}
const snapBefore = snapCmds.map((c, i) => runSnap(c, 'before', i))
const preSnapshotProblems = snapBefore.filter(s => !s.ok).map(snapshotFailure)
if (preSnapshotProblems.length) {
  if (lockKind) release()
  console.error('拒绝派工：\n  · ' + preSnapshotProblems.join('\n  · '))
  if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({
    ok: false, model, modelActual: null, elapsedSec: (Date.now() - started) / 1000,
    answer: '', problems: preSnapshotProblems, calls: [], readImages: [],
    outcome: 'snapshot_failed', sessionDir: null, record: null,
    snapshots: { dir: SNAPDIR, lines: [], executions: { before: snapBefore.map(s => s.execution), after: [] } },
    warnings: [], timeoutSec,
  }, null, 2), 'utf8')
  process.exit(1)
}

// --- 前快照有效后才生成模型覆盖层并派工 ---
const patchDir = path.join(os.tmpdir(), 'dsh-task-patches')
fs.mkdirSync(patchDir, { recursive: true })
const patchFile = path.join(patchDir, 'model-' + modelKey + '-' + process.pid + '.yml')
if (engine === 'dsh') fs.writeFileSync(patchFile,
  '# 本次派工的一次性模型覆盖层（由 dsh_task.js 生成）\n' +
  '- id: agent-default-model\n' +
  '  config:\n' +
  '    provider: deepseek-official\n' +
  '    model: ' + model + '\n')
// ⚠ 必须 shell:false 且直接调 bin.js。走 `dsh` 这个 .cmd shim 会经过 cmd.exe，
//   Windows 默认代码页会把任务文本与**中文路径**里的非 ASCII 字符打坏 ——
//   症状是 DSH 反问「请告诉我要读哪些图片」，看起来像它不听话，其实是参数没送到。
//   （2026-09-08 实测：第一版用 shell:true，带中文路径的派工 100% 读不到图。）
// DSH_BIN 指向 @deepseek-ai/dsh 的 lib/bin.js（kit.env 可设）。若另有常驻 DSH 服务，建议把派工用的 DSH 单独装一份
//   （如 ~/.local/opt/dsh-<版本>，npm install --prefix），与服务隔离——版本不同、家目录不同会串。
//   缺省依次找：~/.local/opt/dsh-*（取最新）→ 全局 npm 前缀 → Windows 的 AppData\Roaming\npm。
function findDshBin() {
  const rel = ['node_modules', '@deepseek-ai', 'dsh', 'lib', 'bin.js']
  const cands = []
  const opt = path.join(os.homedir(), '.local', 'opt')
  try {
    fs.readdirSync(opt).filter(d => d.startsWith('dsh-')).sort().reverse()
      .forEach(d => cands.push(path.join(opt, d, ...rel)))
  } catch (e) { /* 没有 ~/.local/opt */ }
  if (process.platform === 'win32') cands.push(path.join(os.homedir(), 'AppData', 'Roaming', 'npm', ...rel))
  for (const p of [path.join(os.homedir(), '.npm-global', 'lib'), '/usr/local/lib', '/usr/lib']) cands.push(path.join(p, ...rel))
  return cands.find(p => fs.existsSync(p)) || cands[0] || path.join(opt, 'dsh', ...rel)
}
const DSH_BIN = kit.get('DSH_BIN', '') || findDshBin()
// ⚠ 必须把 DEEPSEEK_API_KEY 从子进程环境里剔掉（2026-09-09 踩过，查了一个多小时）：
//   适配器的凭据解析链是「ctx.credentials → 受信任的环境变量层」。
//   只要环境里有这个变量，它就可能压过 ~/.dsh/.credentials.yaml 里的正确 key。
//   实测症状：DSH 每次报 `QUOTA: Insufficient Balance`，而同一把新 key 直接 curl
//   （含大 prompt / max_tokens 256000 / 思考 high / 流式，全组合）**全部通过**，
//   /user/balance 也显示有余额 —— 因为 DSH 用的根本是另一把已欠费的旧 key。
//   ⚠ 删 User/Machine 级环境变量对**已经在运行的进程**无效，它会一路继承到子进程。
//   判据：`node -e "console.log(process.env.DEEPSEEK_API_KEY)"` 在派工的那个 shell 里跑。
const childEnv = Object.assign({}, process.env)
delete childEnv.DEEPSEEK_API_KEY
delete childEnv.DSH_HOME // 否则可能串到 Harness 的家目录（~/harness/home）
delete childEnv.CLAUDECODE // 09-23：否则 ws_git.py 把 DSH/Codex 的提交署名成 Claude（C01 bbc7cb5e 实例）
// Codex：任务书走 stdin（`-i` 是可变参数，放在它后面的位置参数会被当成图片路径吞掉，09-23 实测）；
//   --json 的 stdout 只给 thread_id 与消息，工具调用明细要去 ~/.codex/sessions 的 rollout 里读。
const CODEX_BIN = kit.get('CODEX_BIN', '') ||
  [path.join(os.homedir(), '.npm-global', 'bin', 'codex')].find(p => fs.existsSync(p)) || 'codex'
const lastMsgFile = path.join(patchDir, 'codex-last-' + process.pid + '.txt')
let r
if (engine === 'codex') {
  const cargs = ['exec', '-m', model, '-c', 'model_reasoning_effort=' + effort, '-s', 'workspace-write',
    '-C', cwd, '--add-dir', path.join(WS_ROOT, '.git'), '--json', '-o', lastMsgFile]
  if (path.relative(WS_ROOT, cwd).startsWith('..')) cargs.push('--add-dir', WS_ROOT)
  for (const im of images) cargs.push('-i', path.resolve(im))
  cargs.push('-')
  r = spawnSync(CODEX_BIN, cargs, {
    cwd, input: task, encoding: 'utf8', timeout: timeoutSec * 1000, shell: false, maxBuffer: 64 * 1024 * 1024, env: childEnv,
  })
} else {
  if (!fs.existsSync(DSH_BIN)) { console.error('找不到 DSH（' + DSH_BIN + '）：在 kit.env 设 DSH_BIN，或改用 --engine codex'); process.exit(1) }
  r = spawnSync(process.execPath, [DSH_BIN, '--profile', 'headless', '--patch', patchFile, task], {
    cwd, encoding: 'utf8', timeout: timeoutSec * 1000, shell: false, maxBuffer: 64 * 1024 * 1024,
    env: childEnv,
  })
}
const elapsed = ((Date.now() - started) / 1000).toFixed(1)
if (lockKind) release()
try { fs.unlinkSync(patchFile) } catch (e) { /* ignore */ }

let codexThread = null
let answer
if (engine === 'codex') {
  const evs = (r.stdout || '').split('\n').map(l => { try { return JSON.parse(l) } catch (e) { return null } }).filter(Boolean)
  const ts = evs.find(e => e.type === 'thread.started'); codexThread = ts ? ts.thread_id : null
  try { answer = fs.readFileSync(lastMsgFile, 'utf8').trim(); fs.unlinkSync(lastMsgFile) } catch (e) {
    const msgs = evs.filter(e => e.item && e.item.type === 'agent_message'); answer = msgs.length ? msgs[msgs.length - 1].item.text.trim() : ''
  }
} else answer = (r.stdout || '').trim()
console.log(answer)

// --- 事后核验：从新生成的会话日志里读它真做了什么 ---
function listSessionIds() {
  const out = []
  if (!fs.existsSync(SESS)) return out
  for (const ws of fs.readdirSync(SESS)) {
    const d = path.join(SESS, ws)
    let st; try { st = fs.statSync(d) } catch (e) { continue }
    if (!st.isDirectory()) continue
    for (const sd of fs.readdirSync(d)) {
      if (fs.existsSync(path.join(d, sd, 'session.jsonl.zstd'))) out.push(path.join(d, sd))
    }
  }
  return out
}
function readEvents(file) {
  const zlib = require('zlib')
  const M = Buffer.from([0x28, 0xB5, 0x2F, 0xFD])
  const buf = fs.readFileSync(file)
  const parts = []
  let off = 0
  while (off < buf.length) {
    const i = buf.indexOf(M, off); if (i < 0) break
    let n = buf.indexOf(M, i + 4); if (n < 0) n = buf.length
    try { parts.push(zlib.zstdDecompressSync(buf.subarray(i, n)).toString('utf8')) } catch (e) { /* 坏帧 */ }
    off = n
  }
  return parts.join('').split('\n').filter(Boolean)
    .map(l => { try { return JSON.parse(l) } catch (e) { return null } }).filter(Boolean)
}

// ⚠ 认会话必须按**任务原文**匹配，不能按「最新的那个」。
//   2026-09-08 踩过：同时跑两路派工时，另一路的会话也是「新」的且更晚，
//   于是核验块张冠李戴 —— 报了另一次运行的模型和工具调用，判定完全失真。
//   而且它是**静默错**：报告照常出，数字看着也合理。
const fresh = listSessionIds().filter(p => !before.has(p))
const problems = []
let verdict = { model: '?', calls: [], readImages: [], outcome: '?', sessionDir: null }

function firstUserText(evs) {
  const u = evs.find(e => e.type === 'user/message')
  const c = (u && u.data && u.data.content) || []
  if (typeof c === 'string') return c
  return (Array.isArray(c) ? c : []).map(b => (b && b.text) || '').join('')
}
const fingerprint = TASK_NONCE

// 2026-09-22 H-05：6 路嵌套视觉派工共用影子 HOME 时 6/6 认领失败（事后手解 zstd 其实都在）。
//   嫌疑：子进程刚退出、会话文件还没落完就去读；并发时 IO 更慢。改成最多轮询 15 s，
//   且 nonce 在任何一条 user/message 里出现都算（不只第一条）。
function allUserText(evs) {
  return evs.filter(e => e.type === 'user/message').map(u => {
    const c = (u.data && u.data.content) || []
    return typeof c === 'string' ? c : (Array.isArray(c) ? c : []).map(b => (b && b.text) || '').join('')
  }).join('\n')
}
let matched = null
for (let attempt = 0; engine === 'dsh' && attempt < 16 && !matched; attempt++) {
  if (attempt > 0) spawnSync('sleep', ['1'])
  const cands = attempt === 0 ? fresh : listSessionIds().filter(p => !before.has(p))
  for (const dir of cands) {
    try {
      const evs = readEvents(path.join(dir, 'session.jsonl.zstd'))
      if (firstUserText(evs).indexOf(fingerprint) >= 0 || allUserText(evs).indexOf(fingerprint) >= 0) {
        matched = { dir, evs }; break
      }
    } catch (e) { /* 读不了就跳过 */ }
  }
}

if (engine === 'codex') {
  // rollout：turn_context 给实际模型；event_msg/item_completed 给工具明细；task_complete 才算收尾；用户消息里的 input_image 数＝真正附上的图。
  let f = null
  for (let a = 0; a < 10 && !f && codexThread; a++) {
    if (a) spawnSync('sleep', ['1'])
    f = latestCodexRollouts(30).find(p => p.indexOf(codexThread) >= 0) || null
  }
  if (!f) problems.push('没找到本次 Codex 会话的 rollout（thread ' + codexThread + '），核验作废 —— 不要采信模型/工具数字')
  else {
    const evs = fs.readFileSync(f, 'utf8').split('\n').map(l => { try { return JSON.parse(l) } catch (e) { return null } }).filter(Boolean)
    const ctx = evs.find(e => e.type === 'turn_context')
    const items = evs.filter(e => e.payload && e.payload.type === 'item_completed').map(e => e.payload.item || {})
    const NAMES = { CommandExecution: 'shell', FileChange: 'apply_patch', WebSearch: 'web_search' }
    let imgs = 0
    for (const e of evs) {
      const p = e.payload || {}
      if (e.type === 'response_item' && p.type === 'message' && p.role === 'user')
        imgs += (p.content || []).filter(c => c && c.type === 'input_image').length
    }
    verdict = {
      sessionDir: f,
      model: (ctx && ctx.payload && ctx.payload.model) || '?',
      calls: items.filter(it => !['UserMessage', 'AgentMessage', 'Reasoning'].includes(it.type))
        .map(it => NAMES[it.type] || (it.type === 'McpToolCall' ? 'mcp:' + (it.server || '') + '.' + (it.tool || it.name || '') : it.type)),
      readImages: new Array(imgs).fill({}),
      outcome: evs.some(e => e.payload && e.payload.type === 'task_complete') ? 'completed'
        : (evs.some(e => e.payload && /abort/i.test(e.payload.type || '')) ? 'aborted' : '?'),
    }
    if (verdict.model !== model) problems.push('实际用的模型是 ' + verdict.model + '，不是要求的 ' + model)
    if (images.length && imgs < images.length) problems.push('只附上了 ' + imgs + '/' + images.length + ' 张图 —— 需要看图的结论一律不可采信')
    if (verdict.outcome !== 'completed') problems.push('轮次收尾不是 completed，而是 ' + verdict.outcome)
  }
} else if (!matched) {
  problems.push('没能按任务原文认出本次派工的会话日志（并发派工？），核验作废 —— ' +
    '不要采信下面的模型/工具数字')
} else {
  const dir = matched.dir
  const evs = matched.evs
  const hdr = evs.find(e => e.type === 'request/header')
  const calls = evs.filter(e => e.type === 'tool/call')
  const ends = evs.filter(e => e.type === 'turn/end')
  verdict = {
    sessionDir: dir,
    model: (hdr && hdr.data && hdr.data.header && hdr.data.header.config && hdr.data.header.config.model) || '?',
    calls: calls.map(c => c.data && c.data.name).filter(Boolean),
    readImages: calls.filter(c => c.data && c.data.name === 'read_image')
      .map(c => {
        let a = {}
        try { a = JSON.parse(c.data.arguments || '{}') } catch (e) { /* 参数坏了当空对象 */ }
        // ⚠ 有 tool/call 不等于真读到了图，见下面 resultErr 那段的注释。
        a.__callId = c.data.callId || c.data.id ||
          (c.data.toolCall && c.data.toolCall.callId) || null
        return a
      }),
    outcome: (ends.slice(-1)[0] && ends.slice(-1)[0].data && ends.slice(-1)[0].data.reason &&
      ends.slice(-1)[0].data.reason.kind) || '?',
  }
  if (verdict.model !== model) {
    problems.push('实际用的模型是 ' + verdict.model + '，不是要求的 ' + model)
  }
  // ⛔ 事后再兜一道：DSH 的 web UI 切模型会把 agent-default-model 写回
  //    ~/.dsh/settings.yaml，那一层优先级高于本脚本的 --patch。所以「派工时挡住」
  //    不等于「实际没跑 pro」——必须看会话日志里真实用的是什么。
  if (BANNED_ID.test(verdict.model)) {
    problems.push('⛔ 这次实际跑的是被禁用的 ' + verdict.model +
      '（作者 2026-09-11 明令禁 Pro）。多半是 web UI 切过模型、把 agent-default-model ' +
      '写回了 ~/.dsh/settings.yaml —— 去删掉那一段。本次结果按无效处理。')
  }
  if (images.length) {
    // ⛔ 2026-09-10 补的洞：老口径只数 tool/call 里有几条 read_image，**不看结果**。
    //    那天 v4.1 预览到期后 read_image 被硬拒
    //    （`does not declare image input`），三条 call 照样在，
    //    于是核验打印「读图 3/3」并判 ✓ PASS —— 而模型一张图都没看见，
    //    整份回答建立在它自己承认的「我没看到图」之上。
    //    ⇒ 必须按 callId 回查 tool/result 是不是错误。
    const resultErr = new Map()
    for (const e of evs.filter(x => x.type === 'tool/result')) {
      const items = (e.data && e.data.message && e.data.message.content) || []
      for (const it of items) {
        if (!it || !it.toolCallId) continue
        const txt = JSON.stringify(it.content || '')
        resultErr.set(it.toolCallId, Boolean(it.isError) ||
          /does not declare image input|cannot read .* as an image/i.test(txt))
      }
    }
    const bad = a => Boolean(a.__callId) && resultErr.get(a.__callId) === true
    const failed = verdict.readImages.filter(bad)
    verdict.readImagesFailed = failed.length
    if (failed.length) {
      problems.push('read_image 调了 ' + verdict.readImages.length + ' 次，其中 ' +
        failed.length + ' 次被拒（多半是该模型没有图像输入能力）—— ' +
        '它实际没看到那些图，凡是需要看图的结论一律不可采信')
    }
    const seen = verdict.readImages.filter(a => !bad(a))
      .map(a => String(a.path || a.file_path || a.filePath || '')
        .replace(/\\/g, '/').toLowerCase())
    for (const im of images) {
      const want = path.resolve(im).replace(/\\/g, '/').toLowerCase()
      if (!seen.some(s => s === want || s.endsWith(path.basename(want)))) {
        problems.push('这张图它没有真的读: ' + im)
      }
    }
  }
  if (verdict.outcome !== 'completed') problems.push('轮次收尾不是 completed，而是 ' + verdict.outcome)
}
if (r.status !== 0) problems.push(AGENT + ' 退出码 ' + r.status + (r.error ? '（' + r.error.code + '）' : '') + (r.stderr ? '：' + String(r.stderr).slice(-300) : ''))
let rec = null
if (recordProj) {
  rec = recordCheck(recordProj, started, answer)
  problems.push(...rec.problems)
}

// B3：只有执行成功且已落盘的快照才参与比较；错误输出不能成为业务变化。
const snapAfter = snapCmds.map((c, i) => runSnap(c, 'after', i))
const snapLines = []
let snapChanged = 0
snapCmds.forEach((c, i) => {
  if (!snapAfter[i].ok) {
    const failure = snapshotFailure(snapAfter[i])
    problems.push(failure)
    snapLines.push(i + ' `' + c.slice(0, 70) + '`：采集失败，未比较')
    return
  }
  const diff = compareSnapshotText(snapBefore[i].stdout, snapAfter[i].stdout)
  if (diff.changed) snapChanged++
  snapLines.push(i + ' `' + c.slice(0, 70) + '`：' + (diff.changed ? '+' + diff.added.length + ' / −' + diff.removed.length + ' 行（变更区）' : '无差异'))
  try { fs.writeFileSync(path.join(SNAPDIR, 'diff_' + i + '.txt'), diff.added.map(l => '+' + l).concat(diff.removed.map(l => '-' + l)).join('\n') + '\n') }
  catch (e) { problems.push('快照 ' + i + ' 差异落盘失败：' + e.message) }
})
const warnings = []
if (snapCmds.length && snapAfter.every(s => s.ok)) {
  const claimsNoChange = /无改动[:：]/.test(answer)
  if (snapExpect === 'changed' && !snapChanged && !claimsNoChange) problems.push('快照前后全部无差异，但 DSH 未自报「无改动」——改动没落盘，或快照命令没覆盖到改动面（' + SNAPDIR + '）')
  if (snapExpect === 'unchanged' && snapChanged) problems.push('要求前后不变，但 ' + snapChanged + ' 个快照有差异（' + SNAPDIR + '）')
}
// A9：它报「已启动后台 X」→ pgrep 核。沙箱 bwrap --die-with-parent，会话一结束后台任务就被杀，它仍会回报「已启动」。
for (const m of answer.matchAll(/(?:已启动|已在后台|后台运行|后台跑|nohup|setsid)[^\n]{0,80}?([\w.\/\-]+\.(?:sh|py))/g)) {
  const nm = path.basename(m[1])
  const pr = spawnSync('pgrep', ['-f', nm], { encoding: 'utf8' })
  if (!(pr.stdout || '').trim()) problems.push('它报「已启动后台」' + m[1] + '，但 pgrep 找不到——DSH 沙箱 die-with-parent，后台任务随会话结束被杀；长时批处理要由 Claude 侧启动')
}
// A9：渲图产物洋红检测（缺 shader / 沙箱软件 Vulkan），只警告不裁决（荧光材质会假阳）
const pngs = Array.from(new Set(answer.match(/[^\s`'"()（）]+\.png/g) || [])).map(q => path.resolve(cwd, q))
  .filter(q => { try { return fs.statSync(q).mtimeMs >= started } catch (e) { return false } }).slice(0, 12)
if (pngs.length) {
  const py = 'import sys\ntry:\n from PIL import Image\nexcept Exception:\n sys.exit(0)\nfor p in sys.argv[1:]:\n try:\n  im=Image.open(p).convert("RGB"); im.thumbnail((256,256)); px=list(im.getdata()); n=len(px); m=sum(1 for r,g,b in px if r>230 and g<40 and b>230)\n  print(p, round(100.0*m/n,1))\n except Exception:\n  pass\n'
  const pr = spawnSync('python3', ['-c', py, ...pngs], { encoding: 'utf8', timeout: 60000 })
  for (const line of (pr.stdout || '').split('\n')) { const mm = line.match(/^(.*) ([\d.]+)$/); if (mm && Number(mm[2]) > 5) warnings.push('渲图疑似洋红 ' + mm[2] + '%（缺 shader / 沙箱软件 Vulkan）：' + mm[1]) }
}

console.error('')
console.error('──── 派工核验 ' + '─'.repeat(46))
console.error('引擎     : ' + AGENT + (engine === 'codex' ? '（' + effort + '，thread ' + codexThread + '）' : ''))
console.error('模型     : ' + verdict.model + (verdict.model === model ? ' ✓' : ' ✗ 与要求不符'))
console.error('耗时     : ' + elapsed + 's   工具调用: ' + verdict.calls.length +
  (verdict.calls.length ? ' (' + Array.from(new Set(verdict.calls)).join(', ') + ')' : ''))
if (images.length) console.error('读图     : ' +
  (verdict.readImages.length - (verdict.readImagesFailed || 0)) + '/' + images.length +
  (verdict.readImagesFailed ? '   ⚠ 另有 ' + verdict.readImagesFailed + ' 次 read_image 被拒' : ''))
console.error('收尾     : ' + verdict.outcome)
if (rec) console.error('留痕     : ' + (rec.withLog.length ? '✓ 提交 ' + rec.withLog.join(', ') + ' 含施工记录' :
  (rec.noChange && !rec.commits.length ? '— 无改动（DSH 自报）' : '✗ 无含施工记录的提交')) +
  (rec.pending.length ? '   ⚠ 遗留未提交 ' + rec.pending.length : ''))
for (const l of snapLines) console.error('快照     : ' + l)
for (const w of warnings) console.error('警告     : ' + w)
console.error(problems.length ? '判定     : ✗ FAIL\n  · ' + problems.join('\n  · ') : '判定     : ✓ PASS')
console.error('会话     : ' + (verdict.sessionDir || '(无)'))
console.error('─'.repeat(60))

if (journal) {
  // 2026-09-23：原来用 toISOString 是 UTC，本地时区不是 UTC 时旧条目与本地时间错开，与施工记录/git 对不上（蒸馏收集器按本地时间过滤时漏掉整段）。改本地时间。
  const ts = localStamp().replace(/-(\d{2})(\d{2})$/, ' $1:$2')
  const head = task.split('\n').find(l => l.trim()) || ''
  const entry =
    '\n## ' + ts + ' · ' + (problems.length ? '⚠ 核验未过' : '✓') + '\n\n' +
    '- **任务**：' + head.replace(/^【[^】]*】\s*/, '').slice(0, 160) + '\n' +
    '- **模型**：' + AGENT + ' ' + verdict.model + (engine === 'codex' ? '（' + effort + '）' : '') + ' · 耗时 ' + elapsed + 's · 工具 ' +
      (Array.from(new Set(verdict.calls)).join(', ') || '无') + '\n' +
    (problems.length ? '- **核验问题**：' + problems.join('；') + '\n' : '') +
    (snapLines.length ? '- **快照**：' + snapLines.join('；') + '（' + path.relative(WS_ROOT, SNAPDIR) + '）\n' : '') +
    (warnings.length ? '- **警告**：' + warnings.join('；') + '\n' : '') +
    (rec ? '- **留痕**：' + rec.rel + ' · ' + (rec.withLog.length ? '提交 ' + rec.withLog.join(', ') : '无含施工记录的提交') +
      (rec.pending.length ? ' · 遗留未提交 ' + rec.pending.length : '') + '\n' : '') +
    '- **会话**：`' + (verdict.sessionDir ? path.basename(verdict.sessionDir) : '?') + '`\n\n' +
    answer.split('\n').map(l => '> ' + l).join('\n') + '\n'
  try {
    if (!fs.existsSync(journal)) {
      fs.writeFileSync(journal,
        '# DSH 派工流水账\n\n' +
        '> 由 `dsh_task.js --journal` 自动追加，**不要手改**。\n' +
        '> 这是复盘时唯一可信的时间线：谁在什么时候用什么模型干了什么、核验过没有。\n' +
        '> 语义性的结论更新写进各阶段文档，不写这里。\n', 'utf8')
    }
    fs.appendFileSync(journal, entry, 'utf8')
  } catch (e) {
    console.error('⚠ 流水账写入失败: ' + (e && e.message))
  }
}

if (jsonOut) {
  fs.writeFileSync(jsonOut, JSON.stringify({
    ok: problems.length === 0 && r.status === 0,
    engine, effort: engine === 'codex' ? effort : null, codexThread,
    model, modelActual: verdict.model, elapsedSec: Number(elapsed),
    answer, problems, calls: verdict.calls, readImages: verdict.readImages,
    outcome: verdict.outcome, sessionDir: verdict.sessionDir, record: rec,
    snapshots: { dir: SNAPDIR, lines: snapLines,
      executions: { before: snapBefore.map(s => s.execution), after: snapAfter.map(s => s.execution) } }, warnings, timeoutSec,
  }, null, 2), 'utf8')
}

process.exit(r.status !== 0 ? 1 : (problems.length ? 2 : 0))
