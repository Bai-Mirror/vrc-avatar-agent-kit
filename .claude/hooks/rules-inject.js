#!/usr/bin/env node
/**
 * 强制准则注入 + 行为时间戳记录（UserPromptSubmit / PostToolUse 共用）
 *
 * 为什么要这个钩子（作者 2026-09-18 定）：
 *   准则写在 CLAUDE.md 里只在会话开头进上下文一次；长会话、无人值守连跑时会被挤到很远，
 *   旧Windows机 上「提一次用几次就忘」发生过多次（Gemini 证伪、用 ask 提问、派 DSH）。
 *   所以：每次用户发消息注入一遍；连续调用工具时每 EVERY 次再注入一遍。
 *
 * 顺带记录给 stop-gate.js 用的时间戳（~/.cache/vrc-rules/<session>.json）：
 *   lastVisual —— 看了图（Read 图片、渲图/截图类工具）
 *   lastAgy    —— 调了 agy / DeepSeek 视觉评审
 *   lastDsh / dshCount —— 在 Bash 里跑了 dsh_task.js（派工）；同时把 delegate-check.js 的 directSinceDsh 清零
 *
 * 准则原文只有一份：CLAUDE.md 里 <!-- 强制准则:BEGIN --> 与 END 之间。
 * 解析失败一律静默放过 —— 钩子不该成为故障点。
 */
'use strict'
const fs = require('fs')
const path = require('path')
const os = require('os')

const WS = path.resolve(__dirname, '..', '..')
const EVERY = 25
const STATE_DIR = path.join(os.homedir(), '.cache', 'vrc-rules')

function readRules() {
  try {
    const s = fs.readFileSync(path.join(WS, 'CLAUDE.md'), 'utf8')
    const m = s.match(/<!-- 强制准则:BEGIN -->\n([\s\S]*?)<!-- 强制准则:END -->/)
    return m ? m[1].trim() : ''
  } catch (e) { return '' }
}

function loadState(sid) {
  try { return JSON.parse(fs.readFileSync(path.join(STATE_DIR, sid + '.json'), 'utf8')) } catch (e) { return {} }
}
function saveState(sid, st) {
  try {
    fs.mkdirSync(STATE_DIR, { recursive: true })
    fs.writeFileSync(path.join(STATE_DIR, sid + '.json'), JSON.stringify(st))
  } catch (e) { /* ignore */ }
}

const IMG = /\.(png|jpe?g|webp|gif|bmp|tga|exr)$/i
const VISUAL_TOOL = /^mcp__(UnityMCP__manage_camera|Blender__(render_|get_screenshot_))/
const VISUAL_CMD = /AvatarPortrait|SceneViewShots|contact_sheet|diff_crop|overlay_composite|img_tools|Shot - |--render\b|render_(thumbnail|viewport)/i
const AGY_TOOL = /^mcp__agy__/
const AGY_CMD = /agy_panel\.py|agy-task\.py|ds_vision\.py|\bagy\s+(-p|--print)/

function emit(event, text) {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: event, additionalContext: text } }))
}

let buf = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', d => { buf += d })
process.stdin.on('end', () => {
  let j
  try { j = JSON.parse(buf || '{}') } catch (e) { return }
  const event = j.hook_event_name || ''
  const sid = String(j.session_id || 'nosession').replace(/[^\w-]/g, '')
  const now = Date.now()
  const st = loadState(sid)
  if (!st.start) st.start = now

  if (event === 'UserPromptSubmit') {
    st.calls = 0
    saveState(sid, st)
    const r = readRules()
    if (r) emit(event, '【本工作区强制准则（每轮注入，必须遵从）】\n' + r)
    return
  }

  if (event === 'PostToolUse') {
    const tn = String(j.tool_name || '')
    const ti = j.tool_input || {}
    const cmd = String(ti.command || '')
    const fp = String(ti.file_path || '')
    if ((tn === 'Read' && IMG.test(fp)) || VISUAL_TOOL.test(tn) || (tn === 'Bash' && VISUAL_CMD.test(cmd))) st.lastVisual = now
    if (AGY_TOOL.test(tn) || (tn === 'Bash' && AGY_CMD.test(cmd))) st.lastAgy = now
    // 派了 DSH：delegate-check.js 的「自上次派工起直接改动」计数清零（2026-09-22）
    if (tn === 'Bash' && /dsh_task\.js/.test(cmd) && !/--selftest-record/.test(cmd)) {
      st.lastDsh = now
      st.dshCount = (st.dshCount || 0) + 1
      st.directSinceDsh = 0
    }
    st.calls = (st.calls || 0) + 1
    saveState(sid, st)
    if (st.calls % EVERY === 0) {
      const r = readRules()
      if (r) emit(event, '【强制准则提醒 · 本轮已连续调用工具 ' + st.calls + ' 次】\n' + r)
    }
  }
})
