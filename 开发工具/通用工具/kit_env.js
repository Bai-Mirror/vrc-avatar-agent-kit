'use strict'
/**
 * 读取工作区根的 kit.env（KEY=VALUE），环境变量优先。与 kit_env.py 同口径。
 * 工作区根＝环境变量 VRC_WS，缺省按本文件位置推算（开发工具/通用工具/ 往上两级）。
 * 用法：const kit = require('./kit_env'); kit.WS; kit.get('VRC_ASSET_ROOT', '')
 * 只解析 KEY=VALUE 行（可带 export 前缀、可加引号），# 开头为注释；值里的 ~ 与 $VAR/${VAR} 会展开。不执行任何代码。
 */
const fs = require('fs')
const os = require('os')
const path = require('path')

const expandHome = p => (p === '~' || p.startsWith('~/')) ? path.join(os.homedir(), p.slice(1)) : p
const WS_FROM_ENV = !!process.env.VRC_WS
let WS = path.resolve(expandHome(process.env.VRC_WS || path.resolve(__dirname, '..', '..')))
let loaded = null

function parse(file) {
  const out = {}
  let text
  try { text = fs.readFileSync(file, 'utf8') } catch (e) { return out }
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const m = /^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$/.exec(line)
    if (!m) continue
    let v = m[2].trim()
    if (v.length >= 2 && v[0] === v[v.length - 1] && (v[0] === '"' || v[0] === "'")) v = v.slice(1, -1)
    else if (v.includes(' #')) v = v.split(' #')[0].trimEnd()
    out[m[1]] = v
  }
  return out
}

function expandVars(v) {
  return v.replace(/\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)/g,
    (s, a, b) => { const k = a || b; return process.env[k] !== undefined ? process.env[k] : s })
}

/** 读 <WS>/kit.env，把环境里还没有的键写进 process.env；返回 kit.env 的原始键值。 */
function load() {
  if (loaded) return loaded
  loaded = parse(path.join(WS, 'kit.env'))
  for (const [k, v] of Object.entries(loaded)) {
    if (v && process.env[k] === undefined) process.env[k] = expandHome(expandVars(v))   // 空值＝没设，不导出
  }
  // kit.env 里写了 VRC_WS：工具仓库与工作区分开放
  if (!WS_FROM_ENV && process.env.VRC_WS) WS = path.resolve(expandHome(process.env.VRC_WS))
  return loaded
}

/** 环境变量 > kit.env > def；空串视为未设。 */
function get(key, def) {
  load()
  const v = process.env[key]
  return v ? v : def
}

load()
module.exports = { get WS() { return WS }, load, get }
