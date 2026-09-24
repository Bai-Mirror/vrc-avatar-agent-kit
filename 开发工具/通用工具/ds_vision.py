# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途　　：DeepSeek 视觉模型客户端，给 agy_panel 当第四个评审模型用

为什么单独一个文件：agy 走的是它自己的模型池，DeepSeek 不在里面。
这里直接打 DeepSeek 的 OpenAI 兼容接口，输出对齐 agy_panel 的 findings/verdict 结构，
这样两边的结果能放进同一张交叉比对表。

模型：`deepseek-v4-flash-vision-exp`（`/models` 里唯一带 vision 的）。

密钥：**不写进代码、不写进工程**。按顺序找：
    环境变量 DEEPSEEK_API_KEY  →  %LOCALAPPDATA%\\vccprojects\\deepseek.key
放在 LOCALAPPDATA 是因为工程目录会整包打给客户，密钥绝不能跟着走。

用法：
    python ds_vision.py --task task.md --images a.png b.png [--out r.json]
"""
import argparse
import base64
import io
import json
import os
import sys
import urllib.request

API = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-flash-vision-exp"
KEYFILE = (os.path.join(os.environ.get("LOCALAPPDATA", ""), "vccprojects", "deepseek.key") if os.name == "nt"
           else os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "vccprojects", "deepseek.key"))

SYSTEM = """你是一位毫不留情的资深评审。你面前这份东西**已经被当作成品提交**了，
你的职责是在它出问题之前把问题揪出来。

规矩：
1. 这里面**确实有真问题**，找出来。
2. 每条都要给**确切位置**和**哪里错了**，不要给改进建议，不要写"建议考虑…"。
3. **禁止为了凑数编造问题。** 找不到就少写几条，写零条也可以。编造的代价比漏报高。
4. **禁止软化措辞。** 不要写"可能""也许""似乎有点"。你判定是问题就直说是问题。

只输出一个 JSON 对象，不要 markdown 代码围栏，不要任何解释文字：
{"findings":[{"category":"...","location":"...","what_is_wrong":"...",
"severity":"blocker|major|minor","evidence":"..."}],"verdict":"一句话总评"}"""


def key():
    k = os.environ.get("DEEPSEEK_API_KEY")
    if k:
        return k.strip()
    if os.path.exists(KEYFILE):
        return io.open(KEYFILE, encoding="utf-8").read().strip()
    sys.exit("找不到 DeepSeek 密钥：设 DEEPSEEK_API_KEY 或写入 %s" % KEYFILE)


def img_part(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
    if ext == "jpg":
        ext = "jpeg"
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    return {"type": "image_url",
            "image_url": {"url": "data:image/%s;base64,%s" % (ext, b64)}}


def review(task_text, images, timeout=300, system=None, schema=None):
    # system/schema 默认 None → 完全走原来的写死 SYSTEM，行为不变。
    # 传了才会替换掉「揪出问题」这套措辞——给 agy_panel 的 --schema/--system 用，
    # 这样 DeepSeek 跟 agy 那两个模型收到的是同一个任务，不会独自还在挑缺陷。
    sys_prompt = system if system is not None else SYSTEM
    if schema is not None:
        sys_prompt = sys_prompt.rstrip() + (
            "\n\n只输出一个符合以下 JSON Schema 的 JSON 对象，不要 markdown 代码围栏，"
            "不要任何解释文字：\n" + json.dumps(schema, ensure_ascii=False))
    content = [{"type": "text", "text": task_text}]
    for p in images:
        content.append({"type": "text", "text": "图：" + os.path.basename(p)})
        content.append(img_part(p))
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": content}],
        "temperature": 0.2,
        "max_tokens": 4000,
    }
    req = urllib.request.Request(
        API, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode("utf-8"))
    txt = out["choices"][0]["message"]["content"].strip()
    # 有些回合还是会套代码围栏，剥掉再解析
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(txt)
    except ValueError:
        # 解析不了就把原文带回去，别静默吞掉
        return {"findings": [], "verdict": "(解析失败)", "_raw": txt[:2000]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--images", nargs="*", default=[])
    ap.add_argument("--out")
    a = ap.parse_args()
    task = io.open(a.task, encoding="utf-8").read()
    res = review(task, a.images)
    print("[DeepSeek %s] %d 条  —— %s" % (MODEL, len(res.get("findings", [])), res.get("verdict", "")))
    for f in res.get("findings", []):
        print("  [%s] %s @ %s — %s" % (f.get("severity", "?"), f.get("category", "?"),
                                       f.get("location", "?"), f.get("what_is_wrong", "")[:160]))
    if res.get("_raw"):
        print("  (原始输出前 500 字) " + res["_raw"][:500])
    if a.out:
        io.open(a.out, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
