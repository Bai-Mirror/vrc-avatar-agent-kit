# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途　　：反向评审。两档用法 ——
    ① **快评（默认主力）** `--fast`：只跑 gemini-3.7-flash-high，秒级出结果，全部指认直出。
    ② **大节点交叉**：多模型并发，**只采信 ≥2 个模型独立指认的问题**。

为什么分两档（作者 2026-09-01 定）：
  · 早期多模型交叉是因为单模型会以置信度 1.0 虚报不存在的缺陷，且自报 confidence
    完全不能预测真伪。「≥2 个模型一致」能把真缺陷和幻觉分开。
  · 但 3.7-flash 的幻觉率已经明显下降，且它便宜又快。所以**日常每一步都用它反向评审**，
    把交叉编成留给阶段性提交这种大节点。评审做得勤比做得重要 —— 一步一评比十步一评抓得多。
  · 单模型模式下不做「≥2 一致」过滤（只有一家，永远过不了），全部指认直接列出，
    由我自己逐条复核。复核不是走过场：模型仍会认错对象（实测把耳饰认成光环残件）。

用法：
    python agy_panel.py --task task.md --images a.png b.png --fast          # 日常快评
    python agy_panel.py --task task.md --images a.png b.png                 # 3 模型交叉
    python agy_panel.py --task task.md --images a.png b.png --wide          # 5 模型
    --task    评审任务描述文件（会被内联进提示词；提示词模板见下面 SYSTEM）
    --images  参考图，会被复制成 ASCII 短名再喂（agy 对中文/emoji 文件名不稳）
    --fast    单模型快评：gemini-3.7-flash-high，不带 DeepSeek，不做一致性过滤
    --models  默认 claude-opus-4-6-thinking,gemini-3.7-flash-high（外加 DeepSeek 视觉）
    --wide    扩大编成，再加 gemini-3.1-pro-high 与 gpt-oss-120b-medium

以下三个是可选参数，**不传时行为与之前完全一样**（SCHEMA/SYSTEM 还是写死的缺陷评审结构，
不做 --raw 也照常聚类）。用于「描述/总结」这类非缺陷评审任务：
    --schema <json文件路径>   替换内置 SCHEMA（默认是 findings/verdict 缺陷结构）
    --system <txt文件路径>    替换内置 SYSTEM 提示词前缀（默认措辞是「揪出问题」）
    --raw                    跳过 same() 一致性聚类，每个模型的 structured_output
                             原样并列写进 --out 的 json（不聚类、不合并）
    三者都会同步传给 DeepSeek（ds_vision.review 的 system/schema 形参），
    否则 DeepSeek 会继续用它自己写死的「揪出问题」提示词，跟别的模型不是同一个任务。

坑：
  * 参数必须 `--print=<内容>` 等号形式；stdin 不进上下文；argv 上限约 32KB
  * 读文件靠 `--add-dir`，提示词里要明写「不要用终端命令」，否则模型抓 run_command 撞权限墙返回空
  * Gemini 对「漏洞扫描 / 安全审计」这类措辞会拒答，一律说「质量审查」
  * **带图任务会撞 agy 的内部超时（实测 ≈185s）**。超时时它返回
    `{"status":"ERROR","response":"","error":"timeout waiting for response"}` ——
    response 是空串，stdout 尾巴只剩 json_schema 回显，**极容易误诊为解析 bug**。
    对策：嗂图前一律等比缩到长边 ≤1600px（实测 3840×2160 × 几张就会超）。
  * **两类「假成功」：status=SUCCESS，但 structured_output 缺失**（2026-09-22 实测，
    原始信封存 `agy_panel_samples/`）。同一张图 + 同一提示词连跑 3 次：claude 3/3 有结构化输出，
    gemini-3.7-flash-high 2/3 中招。附件是用提示词里的 `@文件名` 内联的，**模型根本不需要调工具**。
      ① 权限墙：`denied_actions` 非空（实测 `[{"action":"mcp"}]` / `[{"action":"command"}]`）。
         gemini 那次空转到 `duration_seconds≈185`（疑似 agy 内部上限），
         claude 那次 `num_turns=1` 只留一句开场白就收工。
      ② 185s 上限：`status` 仍是 SUCCESS、`response` 空、`duration_seconds ≥ 175`，且没有 denied_actions。
    怎么认：先看 `denied_actions`，再看 status/response/duration 三件套；别再去查解析 bug。
    处置：**自动重试一次**，重试提示词最前面顶一句「附件已 @ 内联，不要调用任何工具」。
    为什么只重试一次：一次 denied/185s 已烧掉最多 ~185s 与数万 token（gemini 那封 input 319k、
    total 347k），配额有限；第二次还失败基本是提示词/模型选择的问题，该换模型或缩图，而不是继续烧。
  * 空 stdout 会出现（撞权限墙时），解析前先判空，别直接 splitlines()[-1]
  * `--selftest` 是离线自检（不联网、不调 agy）：喂真实/构造信封给解析与分类纯函数，断言结果。
"""
import os, sys, io, json, shutil, subprocess, argparse, tempfile, re
from concurrent.futures import ThreadPoolExecutor

AGY = (os.path.expandvars(r"%LOCALAPPDATA%\agy\bin\agy.exe") if os.name == "nt"
       else shutil.which("agy") or os.path.expanduser("~/.local/bin/agy"))
# 编成（作者 2026-09-01 定）：
#   常规：claude-opus-4-6-thinking + gemini-3.7-flash-high + DeepSeek —— **有限使用，省配额**
#   扩大：`--wide` 再加 gemini-3.1-pro-high + gpt-oss-120b-medium，
#         只在需要把任务面铺开（比如全工程审计、方案对比）时才用。
DEFAULT_MODELS = ["claude-opus-4-6-thinking", "gemini-3.7-flash-high"]
FAST_MODEL = "gemini-3.7-flash-high"      # 日常反向评审主力：快、便宜、幻觉率已明显下降
WIDE_MODELS = ["gemini-3.1-pro-high", "gpt-oss-120b-medium"]
# DeepSeek 不在 agy 的模型池里，走它自己的 OpenAI 兼容接口（见 ds_vision.py）。
# 加它是为了把家族数从 2（Gemini/Claude）扩到 3，「≥2 一致」才更有意义 ——
# 同家族的两个模型犯同一种错的概率，比跨家族高得多。
DEEPSEEK_MODEL = "deepseek-v4-flash-vision-exp"

SCHEMA = {
  "type": "object",
  "properties": {
    "findings": {
      "type": "array",
      "description": "发现的具体问题。只写你能指出确切位置的；宁可少写也不要为凑数编造。",
      "items": {
        "type": "object",
        "properties": {
          "category": {"type": "string", "description": "问题类别，如 正确性/一致性/取景/配色/对比度/结构/命名/性能/可维护性"},
          "location":  {"type": "string", "description": "确切位置：文件名、图上的方位、章节号、对象名。不要写「整体」。"},
          "what_is_wrong": {"type": "string", "description": "哪里错了。陈述事实，不要写改进建议。"},
          "severity": {"type": "string", "enum": ["blocker", "major", "minor"]},
          "evidence": {"type": "string", "description": "你据什么这么判断"}
        },
        "required": ["category", "location", "what_is_wrong", "severity"]
      }
    },
    "verdict": {"type": "string", "description": "一句话总评：这份东西能不能交付"}
  },
  "required": ["findings", "verdict"]
}

SYSTEM = """你是一位毫不留情的资深评审。你面前这份东西**已经被当作成品提交**了，你的职责是在它出问题之前把问题揪出来。

规矩：
1. 这里面**确实有真问题**，找出来。
2. 每条都要给**确切位置**和**哪里错了**，不要给改进建议，不要写"建议考虑…"。
3. **禁止为了凑数编造问题。** 找不到就少写几条，写零条也可以。编造的代价比漏报高。
4. **禁止软化措辞。** 不要写"可能""也许""似乎有点"。你判定是问题就直说是问题。
5. **附件已通过 @ 内联，不要调用任何工具**；确需读长文时只用 view_file。

这是一次**质量审查**。

======== 待审对象 ========
"""

# 撞「权限墙 / 185s 假成功」时，重试提示词最前面顶这一句。
# 附件本来就是用提示词里的 @文件名 内联的，模型不需要任何工具；实测它们去调 MCP/终端才空转到超时。
RETRY_PREFIX = ("附件已经通过 @ 引用内联在本消息里。不要调用任何工具（终端、MCP、文件工具都不要），"
                "直接根据内联内容作答，并严格按 JSON schema 输出。\n\n")


def extract_result(envelope):
    """从已解析的信封里取结构化结果（dict）。取不到返回 None。
    纯函数，--selftest 直接用。"""
    if not isinstance(envelope, dict):
        return None
    so = envelope.get("structured_output")
    if so is None:
        # 有些版本把结果放在 result/content 里，且是 JSON 字符串。
        # agy 也把结果同时放在 `response`（一个 JSON 字符串）里；
        # structured_output 偶尔为 null（实测 gemini-3.7 带图时常这样），
        # 这时 response 里其实是有的 —— 漏了这个键就会误报「没解析出」。
        for k in ("response", "result", "content", "output", "text"):
            v = envelope.get(k)
            if isinstance(v, str) and v.strip().startswith("{"):
                try: return json.loads(v)
                except Exception: pass
        return None
    if isinstance(so, str):
        try: so = json.loads(so)
        except Exception: pass
    return so


def parse_stdout(out):
    """三级回退解析 agy stdout，返回 (structured_output, envelope)。
    structured_output 非 None 即成功；envelope 供 classify_failure 用。
    纯函数，--selftest 直接用。

    ⚠ 不能只按「整行是一个 JSON」找：某些模型（实测 gemini-3.7）会把响应
      **美化换行**打印，一行都 parse 不出来，于是明明有结果却报「没解析出」。
      三级回退：整段 JSON → 逐行 JSON → 从尾部找最后一个配平的 {...} 块。
    """
    envelope = None
    try:
        envelope = json.loads(out)
        so = extract_result(envelope)
        if so is not None: return so, envelope
    except Exception:
        pass
    for line in reversed(out.splitlines()):
        line = line.strip()
        if not line.startswith("{"): continue
        try: j = json.loads(line)
        except Exception: continue
        if envelope is None: envelope = j
        so = extract_result(j)
        if so is not None: return so, envelope
    # 尾部配平括号扫描
    depth, end = 0, None
    for i in range(len(out) - 1, -1, -1):
        c = out[i]
        if c == "}":
            if depth == 0: end = i + 1
            depth += 1
        elif c == "{":
            depth -= 1
            if depth == 0 and end is not None:
                try:
                    blk = json.loads(out[i:end])
                    so = extract_result(blk)
                    if so is not None: return so, envelope if envelope is not None else blk
                    if envelope is None: envelope = blk
                except Exception:
                    pass
                end = None
    return None, envelope


def classify_failure(envelope, out=""):
    """拿不到结果时按信封分类，返回 (kind, message)。
    kind ∈ {"denied","timeout185","agy_error","unparsed"}；denied / timeout185
    是两类「假成功」，调用方据此自动重试一次。纯函数，--selftest 直接用。

    ⚠ 2026-09-06 的教训：**先分清「解析不出」和「agy 本身报错」**。那次 gemini 实际是
      agy 侧超时（status=ERROR / timeout waiting for response / duration 185s），
      response 是空串，stdout 尾巴只剩 json_schema 回显 + usage，工具却笼统报
      「没解析出 structured_output」，把两个人先后带去查解析 bug。
    """
    env = envelope if isinstance(envelope, dict) else {}
    duration = float(env.get("duration_seconds") or 0)
    status = str(env.get("status") or "")
    response = env.get("response") or ""
    denied = env.get("denied_actions") or []
    # ① 权限墙：信封里明写被拒的动作（mcp / command / ...）
    if denied:
        acts = "、".join(str(d.get("action") or d.get("display_name") or d)
                         for d in denied if isinstance(d, dict)) or str(denied)
        msg = "撞权限墙：%s（status=%s，耗时 %.0fs）" % (acts, status or "?", duration)
        if not response.strip() and duration >= 175:
            msg += "；同时疑似撞 agy 内部 185s 上限"
        return "denied", msg
    # ② status 仍是 SUCCESS，但 response 空、耗时贴着 185s 内部上限
    if status.upper() == "SUCCESS" and not response.strip() and duration >= 175:
        return "timeout185", "疑似 agy 内部 185s 上限（status 仍是 SUCCESS，耗时 %.0fs）" % duration
    # ③ agy 自己报错：把真错误抠出来（原报法）。两者的处置完全不同：
    #    解析不出要改解析器，超时要缩图/减量/重跑。
    if env.get("error") or status.upper() == "ERROR":
        return "agy_error", "agy 返回 %s：%s（耗时 %.0fs）" % (
            status or "ERROR", env.get("error") or "未给错误信息", duration)
    # ④ 其余：原样报「没解析出」
    return "unparsed", "没解析出 structured_output"


def dump_raw(model, out):
    """把原始 stdout 落盘（诊断用，省下再烧一次配额），返回可拼接的说明。
    这一条是被逼出来的 —— 2026-09-06 gemini 挂掉后，为了看信封形状又白烧了一次配额。"""
    try:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", model)
        path = os.path.join(tempfile.gettempdir(), "agy_raw_%s.txt" % safe)
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(out)
        return "（原始 stdout 已存 %s）" % path
    except Exception:
        return ""


def invoke_agy(model, prompt, adddir, schema_path, timeout=600):
    """跑一次 agy。返回 (structured_output, envelope, err)；err=None 表示成功，
    失败时 err=(kind, message)。"""
    cmd = [AGY, "--model", model, "--output-format", "json", "--json-schema", schema_path]
    if adddir: cmd += ["--add-dir", adddir]
    cmd += ["--print=" + prompt]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, None, ("timeout", "超时（超过 %ds）" % timeout)
    out = (r.stdout or "").strip()
    if not out:
        return None, None, ("empty", "空 stdout（多半撞了权限墙）：" + (r.stderr or "")[:200])
    so, envelope = parse_stdout(out)
    if so is not None:
        return so, envelope, None
    kind, msg = classify_failure(envelope, out)
    if kind == "unparsed":
        msg = msg + "：" + out[-300:]
    return None, envelope, (kind, msg + dump_raw(model, out))


def run_one(model, prompt, adddir, schema_path, timeout=600):
    """跑一个模型；撞「权限墙 / 185s 假成功」时自动重试一次。
    返回 (model, structured_output, error, meta)，
    meta = {"attempts": 1|2, "first_error": 首次失败原因 or None, "kind": ...}。"""
    so, envelope, err = invoke_agy(model, prompt, adddir, schema_path, timeout)
    meta = {"attempts": 1, "first_error": None, "kind": None}
    if so is not None:
        return model, so, None, meta
    kind, msg = err
    if kind not in ("denied", "timeout185"):
        return model, None, msg, meta
    # ★ 两类「假成功」：模型根本不需要调工具（附件已 @ 内联），
    #   重试时把「不要调用任何工具」顶到提示词最前面。
    meta["first_error"] = msg
    meta["kind"] = kind
    so2, _, err2 = invoke_agy(model, RETRY_PREFIX + prompt, adddir, schema_path, timeout)
    meta["attempts"] = 2
    if so2 is not None:
        # 重试结果单独标注（verdict 前缀），别和首次成功混为一谈。
        if isinstance(so2, dict) and isinstance(so2.get("verdict"), str):
            so2["verdict"] = "[重试] " + so2["verdict"]
        return model, so2, None, meta
    kind2, msg2 = err2
    return model, None, "首次：%s；重试仍失败：%s" % (msg, msg2), meta

STOP = set("的了是在有和与也都就很非常这那一个不没被把将该其为之以及或者对于关于".split()) | set(list("的了是在有和与也都就很不没把将该其为之或"))
def toks(s):
    s = (s or "").lower()
    parts = re.findall(r"[a-z0-9_./\\-]{2,}", s)
    cjk = [c for c in s if "一" <= c <= "鿿" and c not in STOP]
    return set(parts) | set("".join(cjk[i:i+2]) for i in range(max(0, len(cjk)-1)))

def same(a, b):
    ta = toks(a["location"]) | toks(a["what_is_wrong"])
    tb = toks(b["location"]) | toks(b["what_is_wrong"])
    if not ta or not tb: return False
    j = len(ta & tb) / len(ta | tb)
    loc = len(toks(a["location"]) & toks(b["location"])) > 0
    return j >= 0.22 or (loc and j >= 0.12)

def run_selftest():
    """离线自检：解析 / 分类纯函数 + `agy_panel_samples/` 两份真实信封 + 构造信封。
    不联网、不调 agy、不碰 AGY。打印 ALL PASS 或失败项，返回进程退出码。"""
    here = os.path.dirname(os.path.abspath(__file__))
    samp = os.path.join(here, "agy_panel_samples")
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print("  PASS  " + name)
        else:
            print("  FAIL  " + name + ("  —— " + detail if detail else ""))
            fails.append(name)

    def load(fn):
        return io.open(os.path.join(samp, fn), encoding="utf-8").read()

    print("agy_panel --selftest：解析 / 失败分类纯函数（离线，不调 agy）\n")

    # ① 真实信封：mcp 权限墙 + 185s 空转（gemini）
    out1 = load("denied_mcp_timeout_gemini.json")
    so1, env1 = parse_stdout(out1)
    check("真实 denied_mcp_timeout_gemini：解析不出结果", so1 is None, repr(so1)[:120])
    k1, m1 = classify_failure(env1, out1)
    check("真实 denied_mcp_timeout_gemini：判为 denied", k1 == "denied", k1)
    check("真实 denied_mcp_timeout_gemini：写明 mcp 权限墙", "mcp" in m1, m1)

    # ② 真实信封：command 权限墙，只留一句开场白（claude）
    out2 = load("denied_command_claude.json")
    so2, env2 = parse_stdout(out2)
    check("真实 denied_command_claude：解析不出结果", so2 is None, repr(so2)[:120])
    k2, m2 = classify_failure(env2, out2)
    check("真实 denied_command_claude：判为 denied", k2 == "denied", k2)
    check("真实 denied_command_claude：写明 command 权限墙", "command" in m2, m2)

    # ③ 构造：正常 structured_output
    out3 = json.dumps({"status": "SUCCESS", "response": "", "duration_seconds": 12.0,
                       "structured_output": {"findings": [], "verdict": "正常"}},
                      ensure_ascii=False)
    so3, _ = parse_stdout(out3)
    check("构造 正常 structured_output：解析成功", isinstance(so3, dict), repr(so3)[:120])
    check("构造 正常 structured_output：verdict 正确", (so3 or {}).get("verdict") == "正常",
          repr(so3)[:120])

    # ④ 构造：结果在 response 的 JSON 字符串里
    out4 = json.dumps({"status": "SUCCESS",
                       "response": json.dumps({"findings": [], "verdict": "内联JSON"},
                                              ensure_ascii=False),
                       "duration_seconds": 9.0}, ensure_ascii=False)
    so4, _ = parse_stdout(out4)
    check("构造 response 是 JSON 字符串：解析成功", isinstance(so4, dict), repr(so4)[:120])
    check("构造 response 是 JSON 字符串：verdict 正确", (so4 or {}).get("verdict") == "内联JSON",
          repr(so4)[:120])

    # ⑤ 构造：status=ERROR 超时（走原报法，不重试）
    out5 = json.dumps({"status": "ERROR", "response": "", "error": "timeout waiting for response",
                       "duration_seconds": 185.1}, ensure_ascii=False)
    so5, env5 = parse_stdout(out5)
    check("构造 ERROR 超时：解析不出结果", so5 is None, repr(so5)[:120])
    k5, m5 = classify_failure(env5, out5)
    check("构造 ERROR 超时：判为 agy_error", k5 == "agy_error", k5)
    check("构造 ERROR 超时：抠出真错误", "timeout waiting for response" in m5, m5)

    # ⑥ 构造：无 denied_actions 的纯 185s 假成功 → timeout185（与 ① 区分）
    out6 = json.dumps({"status": "SUCCESS", "response": "", "duration_seconds": 185.0},
                      ensure_ascii=False)
    so6, env6 = parse_stdout(out6)
    check("构造 纯 185s 假成功：解析不出结果", so6 is None, repr(so6)[:120])
    k6, m6 = classify_failure(env6, out6)
    check("构造 纯 185s 假成功：判为 timeout185", k6 == "timeout185", k6)
    check("构造 纯 185s 假成功：写明 SUCCESS", "SUCCESS" in m6, m6)

    # ⑦ 重试提示词确实顶在最前面、且写了「不要调用任何工具」
    check("重试提示词：以「附件已经通过 @」开头", RETRY_PREFIX.startswith("附件已经通过 @"),
          RETRY_PREFIX[:40])
    check("重试提示词：写明不要调用工具", "不要调用任何工具" in RETRY_PREFIX, RETRY_PREFIX[:60])

    print("")
    if fails:
        print("FAILED %d 项：%s" % (len(fails), "、".join(fails)))
        return 1
    print("ALL PASS")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default=None,
                    help="评审任务描述文件（--selftest 时可省）")
    ap.add_argument("--images", nargs="*", default=[])
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--min-agree", type=int, default=2)
    ap.add_argument("--wide", action="store_true",
                    help="扩大编成：再加 gemini-3.1-pro-high 与 gpt-oss-120b-medium")
    ap.add_argument("--no-deepseek", action="store_true",
                    help="不带 DeepSeek（默认带）")
    ap.add_argument("--fast", action="store_true",
                    help="单模型快评：只跑 " + FAST_MODEL + "，不带 DeepSeek，不做一致性过滤")
    ap.add_argument("--schema", default=None,
                    help="用这个 JSON 文件替换内置 SCHEMA（默认写死的 findings/verdict 缺陷评审结构）；"
                         "不传则完全不变")
    ap.add_argument("--system", default=None,
                    help="用这个文本文件替换内置 SYSTEM 提示词前缀（默认是「揪出问题」的评审措辞）；"
                         "不传则完全不变")
    ap.add_argument("--raw", action="store_true",
                    help="跳过 same() 一致性聚类，每个模型的 structured_output 原样并列写进 --out 的 json；"
                         "不传则完全不变（照常聚类成 confirmed/unconfirmed）")
    ap.add_argument("--selftest", action="store_true",
                    help="离线自检解析/分类纯函数（用 agy_panel_samples/ 的真实信封 + 构造信封），"
                         "不联网、不调 agy，打印 ALL PASS 或失败项")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(run_selftest())
    if not a.task:
        ap.error("--task 是必填的（除非用 --selftest）")
    if a.fast:
        a.models = FAST_MODEL
        a.no_deepseek = True
        a.wide = False

    body = io.open(a.task, encoding="utf-8").read()
    # 不传 --schema/--system 时 schema_obj/system_text 就是原来写死的 SCHEMA/SYSTEM，行为不变。
    schema_obj = json.loads(io.open(a.schema, encoding="utf-8").read()) if a.schema else SCHEMA
    system_text = io.open(a.system, encoding="utf-8").read() if a.system else SYSTEM
    work = tempfile.mkdtemp(prefix="agypanel_")
    refs = []
    for i, p in enumerate(a.images):
        if not os.path.exists(p): print("!! 图不存在", p); continue
        n = "img%02d%s" % (i, os.path.splitext(p)[1].lower())
        shutil.copy2(p, os.path.join(work, n)); refs.append((n, os.path.basename(p)))
    # 任务文本也落盘一份，便于模型 view_file 读长内容
    io.open(os.path.join(work, "task.md"), "w", encoding="utf-8", newline="\n").write(body)
    sp = os.path.join(work, "schema.json")
    io.open(sp, "w", encoding="utf-8", newline="\n").write(json.dumps(schema_obj, ensure_ascii=False))

    prompt = system_text + body
    if refs:
        prompt += "\n\n======== 参考图 ========\n"
        for n, orig in refs: prompt += f"@{n}   （原名 {orig}）\n"
    prompt += "\n完整任务文本也在 @task.md。"

    models = [m.strip() for m in a.models.split(",") if m.strip()]
    if a.wide:
        models += [m for m in WIDE_MODELS if m not in models]
    # 只有一家评审时，「≥2 个模型一致」是个永远不可能满足的门槛 ——
    # 会把全部指认都塞进「待核」，读起来像「零条采信」，非常容易误读成通过。
    n_rev = len(models) + (0 if a.no_deepseek else 1)
    solo = n_rev < 2
    if solo:
        a.min_agree = 1
    print(f"评审模型 {len(models)} 个：{models}\n工作目录 {work}\n提示词 {len(prompt)} 字符\n")
    def run_ds(_):
        # ⚠ DeepSeek 有**对没给它的图凭空编评价**的倾向：实测只发了 2 张图，
        #   它照样对第 4、7、8 张图给出了具体结论。所以：
        #     · 提示词里绝不要列出「有哪些图」的清单，只发实际附上的图；
        #     · 它的指认同样要过「≥2 个模型一致」才采信，不单独采信。
        try:
            import ds_vision
            # 不传 --schema/--system 时两个关键字参数都是 None，ds_vision.review
            # 内部会退回它自己写死的 SYSTEM，行为和之前一模一样。
            return (DEEPSEEK_MODEL, ds_vision.review(
                body, a.images,
                system=(system_text if a.system else None),
                schema=(schema_obj if a.schema else None)), None,
                {"attempts": 1, "first_error": None, "kind": None})
        except Exception as e:
            return (DEEPSEEK_MODEL, None, repr(e),
                    {"attempts": 1, "first_error": None, "kind": None})

    jobs = [(lambda m=m: run_one(m, prompt, work, sp)) for m in models]
    if not a.no_deepseek:
        jobs.append(lambda: run_ds(None))
        print("  （另带 DeepSeek %s，跨家族第三方）" % DEEPSEEK_MODEL)
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        results = list(ex.map(lambda f: f(), jobs))

    if a.raw:
        # 非缺陷类任务（描述/总结）没有 findings/verdict 可聚类，且聚类本身就是
        # 要跳过的东西：每个模型的 structured_output 原样并列，不做 same() 合并。
        print(f"\n{'='*66}\n★ --raw：逐模型原样输出（{len(results)} 路，未做一致性聚类）")
        for model, so, err, meta in results:
            tag = " [重试]" if meta.get("attempts", 1) > 1 else ""
            if err:
                print(f"\n  [{model}]{tag} 失败：{err}")
                continue
            dump = json.dumps(so, ensure_ascii=False, indent=2)
            print(f"\n  [{model}]{tag} structured_output（{len(dump)} 字符）：")
            print(dump[:3000] + ("\n  ...(截断，完整内容见 --out)" if len(dump) > 3000 else ""))
        if a.out:
            io.open(a.out, "w", encoding="utf-8", newline="\n").write(json.dumps(
                {"raw": [{"model": m, "result": so, "error": e,
                          "attempts": meta.get("attempts", 1),
                          "first_error": meta.get("first_error")}
                         for m, so, e, meta in results]},
                ensure_ascii=False, indent=1))
            print("\n结果写入", a.out)
        return

    allf = []
    for model, so, err, meta in results:
        if err: print(f"  [{model}] 失败：{err}"); continue
        fs = (so or {}).get("findings", []) or []
        print(f"  [{model}] {len(fs)} 条  —— {(so or {}).get('verdict','')[:70]}")
        for f in fs:
            f = dict(f); f["_model"] = model; allf.append(f)

    clusters = []
    for f in allf:
        for c in clusters:
            if same(c[0], f) and f["_model"] not in [x["_model"] for x in c]:
                c.append(f); break
        else:
            clusters.append([f])
    clusters.sort(key=lambda c: (-len(c), {"blocker":0,"major":1,"minor":2}.get(c[0].get("severity"), 3)))

    conf = [c for c in clusters if len(c) >= a.min_agree]
    single = [c for c in clusters if len(c) < a.min_agree]
    if solo:
        print(f"\n{'='*66}\n★ 快评指认（单模型 {models[0]}）：{len(conf)} 条 —— 逐条自己复核，别照单全收")
        for c in conf:
            print(f"\n  [{c[0].get('severity')}] {c[0].get('category')} @ {c[0].get('location')}")
            print(f"      {c[0].get('what_is_wrong')}")
        if not conf:
            print("\n  （零条。先问一句：是真没问题，还是我喂的图让它看不见问题）")
    else:
        print(f"\n{'='*66}\n★ 采信（≥{a.min_agree} 个模型独立指认）：{len(conf)} 条")
        for c in conf:
            print(f"\n  [{c[0].get('severity')}] {c[0].get('category')} @ {c[0].get('location')}")
            print(f"      {c[0].get('what_is_wrong')}")
            print(f"      指认者：{', '.join(x['_model'] for x in c)}")
        print(f"\n{'-'*66}\n· 待核（仅 1 个模型指认，按经验多为幻觉，但别直接丢）：{len(single)} 条")
        for c in single:
            print(f"  [{c[0].get('severity')}] {c[0].get('category')} @ {c[0].get('location')} — {c[0].get('what_is_wrong')[:80]}  ({c[0]['_model']})")

    if a.out:
        io.open(a.out, "w", encoding="utf-8", newline="\n").write(json.dumps(
            {"confirmed": [[dict(x) for x in c] for c in conf],
             "unconfirmed": [[dict(x) for x in c] for c in single],
             "raw": [{"model": m, "result": so, "error": e,
                      "attempts": meta.get("attempts", 1),
                      "first_error": meta.get("first_error")}
                     for m, so, e, meta in results]},
            ensure_ascii=False, indent=1))
        print("\n结果写入", a.out)

if __name__ == "__main__":
    main()
