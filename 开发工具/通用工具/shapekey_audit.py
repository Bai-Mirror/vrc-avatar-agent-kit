# -*- coding: utf-8 -*-
"""捏脸烘焙后的全量形态键影响检查。
【项目沉淀】通用工具
适用素体：无关
相关素材：工程 .anim + 烘焙清单.json
工具链　：Python 3（离线，只读）
可复用性：★★★ 换个单子直接能用
用途　　：捏脸烘焙后的全量形态键影响检查：动画峰值加烘焙量 > 100 即判双重应用破形。


烘焙把捏脸写进了 Basis，被烤的那些键**权重归零但位移还在**。
于是任何动画再把它推到 100，实际效果 = 捏脸 + 该键完整位移 = **双重应用**，
总量越过 0–100 就进入外推区，破形。

扫法（照 SOP 30 / 记忆 shapekey-bake-and-compensation）：
  遍历全工程 .anim，对每条 `blendShape.X` 曲线取峰值，
  加上该键的烘焙量，看是否 > 100。

    python shapekey_audit.py <工程目录> --baked <烘焙清单.json>

烘焙清单是 {键名: 烘焙权重0-100}。没有就只报「哪些键被动画驱动」。
"""
import argparse
import io
import json
import os
import re
import sys
from collections import defaultdict

CURVE = re.compile(
    r"m_Curve:\s*\n((?:\s+-\s+serializedVersion:.*?\n(?:\s+.*\n)*?)+?)"
    r"\s+attribute:\s*blendShape\.(.+?)\s*\n", re.M)
VAL = re.compile(r"^\s+value:\s*(-?[\d.eE+]+)\s*$", re.M)


def peaks_in(path):
    """返回 {键名: (峰值, 关键帧数)}。按 attribute 分段读 value。"""
    try:
        t = io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return {}
    out = {}
    # 每条曲线块：从 "- curve:" 到 "attribute:"，attribute 在块尾
    for blk in re.split(r"\n\s+-\s+curve:", t)[1:]:
        m = re.search(r"attribute:\s*blendShape\.(.+?)\s*\n", blk)
        if not m:
            continue
        name = m.group(1).strip()
        head = blk[:m.start()]
        vals = [float(x) for x in VAL.findall(head)]
        if not vals:
            continue
        p = max(vals)
        old = out.get(name)
        if old is None or p > old[0]:
            out[name] = (p, len(vals))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--baked", default=None, help="烘焙清单 json：{键名: 权重}")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()

    assets = os.path.join(a.project, "Assets")
    if not os.path.isdir(assets):
        sys.exit("没有 " + assets)
    baked = {}
    if a.baked:
        baked = json.load(io.open(a.baked, encoding="utf-8"))
    out_path = a.out or os.path.join(a.project, "Assets", "_Work", "形态键全量检查.md")

    anims = []
    for r, _d, fs in os.walk(assets):
        for f in fs:
            if f.endswith(".anim"):
                anims.append(os.path.join(r, f))
    sys.stderr.write("扫描 %d 个 .anim\n" % len(anims))

    # 键 → [(clip 相对路径, 峰值, 关键帧数)]
    driven = defaultdict(list)
    for p in anims:
        for k, (pk, nk) in peaks_in(p).items():
            driven[k].append((os.path.relpath(p, assets).replace("\\", "/"), pk, nk))

    buf = io.StringIO()
    buf.write("# 形态键全量检查（捏脸烘焙后）\n\n")
    buf.write("> `python 开发工具/通用工具/shapekey_audit.py <工程> --baked <清单.json>` 重跑。\n")
    buf.write("> 判据：**烘焙量 + 动画峰值 > 100 就进外推区**，会破形。\n")
    buf.write("> 修法（记忆 shapekey-bake-and-compensation）：峰值 >120 的把写入值改成 "
              "`100 − 烘焙量`；多关键帧的整条按比例缩；峰值 <120 的不动（改的收益不抵幅度损失）。\n\n")
    buf.write("- 工程 `.anim` 共 %d 个，其中驱动形态键的键名 %d 个\n" % (len(anims), len(driven)))
    buf.write("- 烘焙清单 %d 个键\n\n" % len(baked))

    # ── 越界的 ────────────────────────────────────────────
    bad = []
    for k, w in baked.items():
        for clip, pk, nk in driven.get(k, []):
            total = w + pk
            if total > 100.5:
                bad.append((total, k, w, pk, nk, clip))
    bad.sort(reverse=True)

    buf.write("## ① 外推越界（烘焙量 + 峰值 > 100）\n\n")
    if not bad:
        buf.write("**无。** 被烤的键没有任何一个被动画推到越界。\n\n")
    else:
        buf.write("| 合计 | 形态键 | 烘焙量 | 动画峰值 | 关键帧 | clip |\n")
        buf.write("|---:|---|---:|---:|---:|---|\n")
        for total, k, w, pk, nk, clip in bad[:80]:
            mark = "**" if total > 120 else ""
            buf.write(f"| {mark}{total:.1f}{mark} | {k} | {w:.0f} | {pk:.1f} | {nk} | `{clip}` |\n")
        if len(bad) > 80:
            buf.write(f"\n（还有 {len(bad) - 80} 条）\n")
        buf.write(f"\n其中 **峰值 >120 需要改**：{sum(1 for x in bad if x[0] > 120)} 条；"
                  f"其余 {sum(1 for x in bad if x[0] <= 120)} 条按规程不动。\n\n")

    # ── 静息表情里写了捏脸键 = 双重叠加 ───────────────────
    buf.write("## ② 静息表情里写了被烤的键（双重叠加，要清零）\n\n")
    rest = [(k, w, clip, pk) for k, w in baked.items()
            for clip, pk, nk in driven.get(k, [])
            if re.search(r"default|idle|neutral|静息|素", clip, re.I)]
    if not rest:
        buf.write("无。\n\n")
    else:
        buf.write("| 形态键 | 烘焙量 | 峰值 | clip |\n|---|---:|---:|---|\n")
        for k, w, clip, pk in sorted(rest, key=lambda x: -x[3])[:40]:
            buf.write(f"| {k} | {w:.0f} | {pk:.1f} | `{clip}` |\n")
        buf.write("\n")

    # ── 被烤但没被任何动画驱动的（安全） ──────────────────
    safe = [k for k in baked if k not in driven]
    buf.write("## ③ 被烤且**无动画驱动**（安全，不用管）\n\n")
    buf.write("%d / %d 个：%s\n\n" % (len(safe), len(baked), ", ".join(sorted(safe))))

    # ── 被动画驱动最多的键（供人工扫一眼） ────────────────
    buf.write("## ④ 被动画驱动最频繁的形态键（前 30，供人工对照）\n\n")
    buf.write("| 形态键 | 出现 clip 数 | 最高峰值 | 是否被烤 |\n|---|---:|---:|---|\n")
    for k, lst in sorted(driven.items(), key=lambda x: -len(x[1]))[:30]:
        buf.write(f"| {k} | {len(lst)} | {max(x[1] for x in lst):.1f} | "
                  f"{('是 ' + format(baked[k], '.0f')) if k in baked else ''} |\n")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(buf.getvalue())
    print(buf.getvalue()[:4000])
    sys.stderr.write("-> " + out_path + "\n")


if __name__ == "__main__":
    main()
