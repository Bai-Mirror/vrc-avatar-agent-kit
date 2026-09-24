#!/usr/bin/env node
/**
 * 【项目沉淀】通用工具
 * 适用素体：无关          相关素材：无
 * 可复用性：★★★ 换个单子直接能用
 * 用途　　：把 agy（Antigravity）的多模型评审包成 **MCP 服务器**，
 *           让 DSH 与 Claude 两侧都能把「找第三方证伪」当成一个普通工具来调。
 *
 * 为什么要包成 MCP 而不是继续手敲命令（作者 2026-09-08 定）：
 *   评审做得勤比做得重要，但**主对话上下文一长就会忘了调它** —— 这不是记性问题，
 *   是「它不在工具列表里」的结构问题。摆成工具，模型每一轮都看得见它。
 *   同一个服务器同时挂给 DSH 和 Claude，两边用同一套编成和同一份判据。
 *
 * 暴露两个工具：
 *   agy_review  多模型交叉证伪（缺陷型任务）。mode=fast 单模型秒评 / panel 3 模型 / wide 5 模型。
 *               panel 与 wide 只采信 ≥2 个模型独立指认的问题；fast 不过滤，全部列出待复核。
 *   agy_ask     单次强模型问答（非缺陷型：解读、比较、总结），可挂目录与上下文文件。
 *
 * ⚠ 三个必须知道的（都来自 agy_panel.py 的实测坑）：
 *   · 带图任务会撞 agy 内部超时（≈185s）。本服务器**自动把长边 >1600px 的图等比缩小**再喂。
 *   · agy 对「漏洞扫描/安全审计」这类措辞会拒答，任务描述一律写「质量审查」。
 *   · 评审模型**会认错对象**（实测把耳饰认成光环残件）。
 *     它指的位置比它给的结论可信 —— 结论一律自己复核，别直接采信。
 *
 * 挂载（Claude Code：见仓库根 .mcp.example.json；DSH：写进 ~/.dsh/cordis.patch.yml 的 insert 块）：
 *   - id: mcp-agy
 *     name: '@deepseek-ai/dsh-mcp-client'
 *     config:
 *       serverName: agy
 *       transport: stdio
 *       command: node
 *       args: ['<工作区绝对路径>/开发工具/通用工具/agy_mcp_server.js']
 *       toolCallTimeoutMs: 900000
 *       failOnStartupError: false
 *
 * 配置：AGY_TASK＝agy-task.py 的路径（kit.env 或环境变量），缺省在 PATH 里找 agy-task.py；AGY_PYTHON＝解释器。
 */
'use strict'
const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')

const TOOLS_DIR = __dirname
const PANEL = path.join(TOOLS_DIR, 'agy_panel.py')
const kit = require('./kit_env')   // 读 <工作区>/kit.env（环境变量优先）
function whichInPath(name) {
  for (const d of String(process.env.PATH || '').split(path.delimiter)) {
    if (d && fs.existsSync(path.join(d, name))) return path.join(d, name)
  }
  return ''
}
const AGY_TASK = kit.get('AGY_TASK', '') || whichInPath('agy-task.py') || 'agy-task.py'
const PY = kit.get('AGY_PYTHON', '') || (process.platform === 'win32' ? 'python' : 'python3')
const TMP = path.join(os.tmpdir(), 'agy-mcp')
fs.mkdirSync(TMP, { recursive: true })

/** agy 带图会撞 ~185s 内部超时；长边压到 1600px 是实测的安全线。 */
function shrinkImages(images) {
  if (!images.length) return []
  const outDir = fs.mkdtempSync(path.join(TMP, 'img-'))
  const script = `
import sys, os
from PIL import Image
out = sys.argv[1]
for i, p in enumerate(sys.argv[2:]):
    try:
        im = Image.open(p); im.load()
    except Exception as e:
        print("SKIP\\t" + p + "\\t" + str(e)); continue
    w, h = im.size
    if max(w, h) > 1600:
        s = 1600.0 / max(w, h)
        im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    if im.mode not in ("RGB", "L"): im = im.convert("RGB")
    # ASCII 短名：agy 对中文/emoji 文件名不稳
    d = os.path.join(out, "img%02d.png" % i)
    im.save(d)
    print("OK\\t" + d + "\\t" + str(im.size))
`
  const r = spawnSync(PY, ['-c', script, outDir, ...images], { encoding: 'utf8', timeout: 180000 })
  const kept = []
  for (const line of String(r.stdout || '').split('\n')) {
    const [tag, p] = line.split('\t')
    if (tag === 'OK' && p) kept.push(p)
  }
  return kept
}

function runReview({ task, images = [], mode = 'fast' }) {
  if (!fs.existsSync(PANEL)) return 'agy_panel.py 不存在: ' + PANEL
  const taskFile = path.join(fs.mkdtempSync(path.join(TMP, 'task-')), 'task.md')
  fs.writeFileSync(taskFile, task, 'utf8')
  const outFile = taskFile.replace(/task\.md$/, 'out.json')
  const args = [PANEL, '--task', taskFile, '--out', outFile]
  if (mode === 'fast') args.push('--fast')
  else if (mode === 'wide') args.push('--wide')
  const shrunk = shrinkImages(images)
  if (shrunk.length) args.push('--images', ...shrunk)

  const r = spawnSync(PY, args, { encoding: 'utf8', timeout: 900000, maxBuffer: 64 * 1024 * 1024 })
  let out = String(r.stdout || '').trim()
  if (fs.existsSync(outFile)) {
    const raw = fs.readFileSync(outFile, 'utf8')
    out += '\n\n--- 结构化结果 (' + outFile + ') ---\n' + raw.slice(0, 20000)
  }
  if (!out) out = '(agy_panel 无输出)\nstderr: ' + String(r.stderr || '').slice(-1500)
  if (images.length) {
    out += '\n\n[喂图记录] 原图 ' + images.length + ' 张，实际送入 ' + shrunk.length +
      ' 张（长边 >1600px 的已等比缩小）。'
  }
  out += '\n\n[复核提醒] 评审模型会认错对象：它指的位置比它给的结论可信，逐条自己复核。'
  return out
}

function runAsk({ prompt, dir, context = [], model }) {
  if (!fs.existsSync(AGY_TASK)) return 'agy-task.py 不存在: ' + AGY_TASK + '（在 kit.env 设 AGY_TASK，或把它放进 PATH）'
  const args = [AGY_TASK]
  if (dir) args.push('--dir', dir)
  for (const c of context) args.push('--context', c)
  if (model) args.push('--model', model)
  args.push(prompt)
  const r = spawnSync(PY, args, { encoding: 'utf8', timeout: 900000, maxBuffer: 64 * 1024 * 1024 })
  const out = String(r.stdout || '').trim()
  return out || '(agy-task 无输出)\nstderr: ' + String(r.stderr || '').slice(-1500)
}

const TOOL_DEFS = [
  {
    name: 'agy_review',
    description:
      '多模型交叉证伪：把一份产出（可带图）交给 Antigravity 上的其它厂商模型独立挑毛病，用于第三方质量审查。' +
      'mode=fast 单模型秒评（日常每一步都该用）；panel 3 模型、wide 5 模型，只采信 ≥2 个模型独立指认的问题（大节点用）。' +
      '⚠ 结论必须自己复核：评审模型会认错对象，它指的位置比它给的结论可信。' +
      '⚠ 任务描述写「质量审查」，不要写「漏洞扫描/安全审计」——那类措辞会被拒答。',
    inputSchema: {
      type: 'object',
      properties: {
        task: { type: 'string', description: '评审任务描述：被评对象是什么、要它重点看什么、判据是什么。写得越具体越有用。' },
        images: { type: 'array', items: { type: 'string' }, description: '参考图绝对路径。长边 >1600px 会自动等比缩小（agy 带图有 ~185s 超时）。' },
        mode: { type: 'string', enum: ['fast', 'panel', 'wide'], description: 'fast=1 模型（默认）/ panel=3 模型 / wide=5 模型' },
      },
      required: ['task'],
    },
  },
  {
    name: 'agy_ask',
    description:
      '向 Antigravity 上的强模型问一次（非缺陷型任务：解读、比较、总结、方案权衡），可挂只读目录与上下文文件。' +
      '用于给自己的结论找一个独立的第二意见，尤其是当你已经把同一个判断复述过好几遍、可能被自己的上下文锚定时。',
    inputSchema: {
      type: 'object',
      properties: {
        prompt: { type: 'string', description: '问题。要问得能被证伪，别问「你觉得怎么样」。' },
        dir: { type: 'string', description: '可选：挂载给它只读通读的目录绝对路径' },
        context: { type: 'array', items: { type: 'string' }, description: '可选：内联进提示词的文件路径' },
        model: { type: 'string', description: '可选：指定模型，缺省用 agy-task.py 的默认' },
      },
      required: ['prompt'],
    },
  },
]

// ---- 最小 MCP stdio 服务器（JSON-RPC 2.0，newline-delimited）----
let buf = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', chunk => {
  buf += chunk
  let i
  while ((i = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, i).trim()
    buf = buf.slice(i + 1)
    if (line) handle(line)
  }
})

function send(obj) { process.stdout.write(JSON.stringify(obj) + '\n') }
function ok(id, result) { send({ jsonrpc: '2.0', id, result }) }
function fail(id, code, message) { send({ jsonrpc: '2.0', id, error: { code, message } }) }

function handle(line) {
  let msg
  try { msg = JSON.parse(line) } catch (e) { return }
  const { id, method, params } = msg
  if (method === 'initialize') {
    // 回声客户端的协议版本，避免版本协商失配
    const pv = (params && params.protocolVersion) || '2024-11-05'
    return ok(id, {
      protocolVersion: pv,
      capabilities: { tools: {} },
      serverInfo: { name: 'agy', version: '1.0.0' },
    })
  }
  if (method === 'notifications/initialized' || method === 'initialized') return
  if (method === 'tools/list') return ok(id, { tools: TOOL_DEFS })
  if (method === 'tools/call') {
    const name = params && params.name
    const a = (params && params.arguments) || {}
    try {
      let text
      if (name === 'agy_review') text = runReview(a)
      else if (name === 'agy_ask') text = runAsk(a)
      else return fail(id, -32602, '未知工具: ' + name)
      return ok(id, { content: [{ type: 'text', text: String(text) }] })
    } catch (e) {
      return ok(id, { content: [{ type: 'text', text: '调用失败: ' + (e && e.message) }], isError: true })
    }
  }
  if (method === 'ping') return ok(id, {})
  if (id !== undefined) fail(id, -32601, '未实现的方法: ' + method)
}
