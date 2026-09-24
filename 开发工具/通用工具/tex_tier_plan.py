# -*- coding: utf-8 -*-
r"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途　　：**不开 Unity** 算出贴图分档方案 —— 场景 → 材质 → 贴图 → .meta 导入设置，全链路纯文本。

为什么要它：
  · 80 阶段最大的一块收益在贴图，而「哪张是主图」必须**按 shader 属性判，不能按文件名判**
    （lilToon 把法线图叫 N01.png 这种事很常见）。属性信息在 .mat 里，是纯文本，不必开 Unity。
  · 只统计**场景真正用到**的贴图。全工程扫会把厂商包里几千张没用上的图算进来，
    结论会大到没有意义（实测工程C全工程 1530 张贴图，场景实际用到的是个位数百）。

分档（来自 SOP 80_性能优化/贴图与动骨.md，作者 2026-09-01 定的红线）：
  · 主图（底色/花纹/皮肤/面部）      2048  —— **红线，不再往下**，降了明显掉观感
  · 遮罩/法线/发光/高光/MatCap/alpha 1024
  · Cubemap                          512
  只降不升：当前值已经低于目标的**一律不动**（厂商可能是刻意压低的）。

⚠ 三个必须知道的：
  ① 判主图用**白名单**不用黑名单。lilToon 辅助属性有几十个，黑名单必漏，
     漏掉的会被当主图抬到 2048，实测反而让贴图内存涨了 37 MB。
  ② `.meta` 里 **默认平台条目**（DefaultTexturePlatform）才是真正生效的那条，
     只看 Standalone 覆盖会以为一切正常。本脚本两条都读，取实际生效值。
  ③ 本脚本**只出方案不改文件**。按 SOP80 审核 CSV，确认没有 Unity 打开该工程后，
     用 tex_tier_apply.py 应用并保留回滚记录；重新导入后回读实际值及内存。
     TexOptimize.cs 的旧文件名分类法只留作历史样本。

用法：
    python tex_tier_plan.py <工程目录> [--scene <场景相对路径>] [--csv out.csv]
"""
import argparse
import io
import os
import re
import sys
from collections import defaultdict

# 主图白名单 —— 不在这里的一律当辅助图（见坑①）
# ⚠ lilToon 的主色层不止三层：`_Main4thTex` 也是主图。
#   2026-09-09 实测：白名单漏了它，把一张 2048 的 _Main4thTex 降成 1024 —— 踩了用户的观感红线。
#   所以除了显式列举，还用正则兜住任何 `_Main<第N层>Tex` 形态。
#   注意区分：`_Main2ndBlendMask` / `_Main3rdBlendMask` / `_MainColorAdjustMask` 名字里也有 Main，
#   但它们是**遮罩**不是主图，属辅助 —— 正则只匹配以 Tex 结尾且不含 Mask 的。
MAIN_PROPS = {"_MainTex", "_Main2ndTex", "_Main3rdTex", "_Main4thTex",
              "_BaseMap", "_BaseColorMap", "_Albedo"}
MAIN_RE = re.compile(r"^_Main\d*(st|nd|rd|th)?Tex$")
CUBE_HINT = re.compile(r"cube|reflection", re.I)


def is_main_prop(props):
    return any(p in MAIN_PROPS or MAIN_RE.match(p) for p in props)

TIER_MAIN, TIER_AUX, TIER_CUBE = 2048, 1024, 512

GUID_RE = re.compile(r"guid:\s*([0-9a-f]{32})")
TEXENV_RE = re.compile(
    r"-\s+(_[A-Za-z0-9_]+):\s*\n\s*m_Texture:\s*\{fileID:\s*(-?\d+)(?:,\s*guid:\s*([0-9a-f]{32}))?")
MAXSIZE_RE = re.compile(r"maxTextureSize:\s*(\d+)")
PLATFORM_BLOCK = re.compile(
    r"-\s+serializedVersion:\s*\d+\s*\n\s*buildTarget:\s*(\S+)(.*?)(?=\n\s+-\s+serializedVersion:|\n\s*spriteSheet:|\Z)",
    re.S)


def build_guid_index(proj):
    """GUID -> 资产相对路径。跳过 Library/Temp，那里是缓存不是权威产物。"""
    idx = {}
    for dirp, dirs, files in os.walk(proj):
        low = dirp.lower()
        if any(x in low for x in (os.sep + "library", os.sep + "temp", os.sep + "obj", os.sep + "logs")):
            dirs[:] = []
            continue
        for f in files:
            if not f.endswith(".meta"):
                continue
            p = os.path.join(dirp, f)
            try:
                head = io.open(p, encoding="utf-8", errors="replace").read(400)
            except OSError:
                continue
            m = GUID_RE.search(head)
            if m:
                idx[m.group(1)] = os.path.relpath(p[:-5], proj)
    return idx


def guids_in(path):
    try:
        return set(GUID_RE.findall(io.open(path, encoding="utf-8", errors="replace").read()))
    except OSError:
        return set()


def image_dims(path):
    """读图像文件头拿**真实尺寸**。
    ⚠ 这一步不能省：`maxTextureSize` 是**上限不是实际尺寸** ——
      一张 512 的源图设了 2048 上限，占的显存还是 512。
      按上限估算会虚报，实测差了 7 倍（估 1107 MB / 实际 160.7 MB），结论完全不能用。
    读不出来的返回 None，调用方按「未知」处理，不要拿上限顶替。"""
    try:
        with io.open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                w = int.from_bytes(head[16:20], "big")
                h = int.from_bytes(head[20:24], "big")
                return w, h
            if head[:2] == b"\xff\xd8":            # JPEG：扫 SOF 段
                f.seek(2)
                while True:
                    b = f.read(1)
                    if not b:
                        return None
                    if b != b"\xff":
                        continue
                    m = f.read(1)
                    while m == b"\xff":
                        m = f.read(1)
                    if not m:
                        return None
                    if m[0] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        f.read(3)
                        hh = int.from_bytes(f.read(2), "big")
                        ww = int.from_bytes(f.read(2), "big")
                        return ww, hh
                    ln = int.from_bytes(f.read(2), "big")
                    if ln < 2:
                        return None
                    f.seek(ln - 2, 1)
            if head[:4] == b"8BPS":                 # PSD
                h = int.from_bytes(head[14:18], "big")
                w = int.from_bytes(head[18:22], "big")
                return w, h
    except OSError:
        return None
    return None


def effective_max_size(meta_path):
    """返回 (生效上限, 默认平台值, 各平台原始值).

    ⚠ 这里踩过一个代价很大的坑（2026-09-09）：
      平台块**存在不等于生效**。每个块有 `overridden` 标志，为 0 时那块的数值是死的。
      实测一张图：DefaultTexturePlatform=1024、Standalone=2048，但三个块的 overridden 全是 0，
      Unity 实际按 **1024** 导入（贴图清单可证）。
      我最初直接取 Standalone=2048，于是把一堆「本来就已经是对的尺寸」判成需要下调，
      改了 78 个文件实际只省了 5 MB —— 改的全是不起作用的字段。

    正确口径：生效值 = DefaultTexturePlatform 的值；
              只有当 Standalone 块 `overridden: 1` 时才用它的值覆盖。
    """
    try:
        txt = io.open(meta_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None, None, {}
    per_platform = {}
    for bt, body in PLATFORM_BLOCK.findall(txt):
        m = MAXSIZE_RE.search(body)
        ov = re.search(r"overridden:\s*(\d+)", body)
        if m:
            per_platform[bt] = {"size": int(m.group(1)),
                                "overridden": bool(ov and ov.group(1) != "0")}
    dflt = per_platform.get("DefaultTexturePlatform")
    default = dflt["size"] if dflt else None
    if default is None:
        m = MAXSIZE_RE.search(txt)
        default = int(m.group(1)) if m else None
    sa = per_platform.get("Standalone")
    eff = sa["size"] if (sa and sa["overridden"]) else default
    return eff, default, per_platform


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proj")
    ap.add_argument("--scene", default=None, help="场景相对路径；缺省自动找 Assets/_Work/*.unity")
    ap.add_argument("--csv", default=None)
    a = ap.parse_args()
    proj = os.path.abspath(a.proj)

    scene = a.scene
    if not scene:
        work = os.path.join(proj, "Assets", "_Work")
        cands = [os.path.join("Assets", "_Work", f) for f in sorted(os.listdir(work))
                 if f.endswith(".unity")] if os.path.isdir(work) else []
        if not cands:
            print("找不到场景，用 --scene 指定", file=sys.stderr)
            return 2
        scene = cands[0]
    scene_abs = os.path.join(proj, scene)
    if not os.path.isfile(scene_abs):
        print("场景不存在: " + scene_abs, file=sys.stderr)
        return 2

    print("工程   : " + proj)
    print("场景   : " + scene)
    idx = build_guid_index(proj)
    print("GUID 索引: %d 条" % len(idx))

    # 场景引用的材质 —— 必须做**传递闭包**。
    # ⚠ 踩过：只看场景 YAML 里直接出现的 GUID，工程C只找到 10 个材质，
    #   而性能报告显示实际有 70 个不同材质 —— 因为预制体实例上的材质挂在 .prefab 里，
    #   场景只引用了预制体。不展开就会严重低估，结论没有意义。
    seen, frontier = set(), guids_in(scene_abs)
    mats = {}
    depth = 0
    while frontier and depth < 6:
        nxt = set()
        for g in frontier:
            if g in seen:
                continue
            seen.add(g)
            rel = idx.get(g)
            if not rel:
                continue
            low = rel.lower()
            if low.endswith(".mat"):
                mats[g] = rel
            elif low.endswith((".prefab", ".controller", ".overridecontroller", ".asset")):
                nxt |= guids_in(os.path.join(proj, rel))
        frontier = nxt - seen
        depth += 1
    print("传递闭包展开 %d 层，命中材质: %d 个" % (depth, len(mats)))

    # 材质 -> (属性, 贴图 GUID)
    tex_props = defaultdict(set)   # texGuid -> {属性名}
    tex_mats = defaultdict(set)    # texGuid -> {材质路径}
    for g, rel in mats.items():
        p = os.path.join(proj, rel)
        try:
            txt = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for prop, fid, tguid in TEXENV_RE.findall(txt):
            if not tguid or fid == "0":
                continue          # 空槽，不是贴图
            tex_props[tguid].add(prop)
            tex_mats[tguid].add(rel)

    print("被这些材质引用的贴图: %d 张" % len(tex_props))
    print("")

    rows, total_now, total_after = [], 0.0, 0.0
    for tguid, props in sorted(tex_props.items()):
        rel = idx.get(tguid)
        if not rel:
            continue              # 贴图不在本工程内（外部包被剔了），跳过并计数
        meta = os.path.join(proj, rel + ".meta")
        eff, default, per = effective_max_size(meta)
        if eff is None:
            continue
        # ⚠ 必须走 is_main_prop()，不能写成 `props & MAIN_PROPS` 的集合交集。
        #   2026-09-09 DSH 审出来的：MAIN_RE / is_main_prop 定义了却从未被调用，
        #   注释里「正则兜住任何 _Main<N>Tex」的承诺当时是假的（死代码）。
        #   现在四层都在显式白名单里所以结果没错，但将来出 _Main5thTex 就会漏判成辅助、被降档。
        is_main = is_main_prop(props)
        is_cube = bool(CUBE_HINT.search(rel)) and not is_main
        want = TIER_CUBE if is_cube else (TIER_MAIN if is_main else TIER_AUX)
        tier = "Cubemap" if is_cube else ("主图" if is_main else "辅助")

        dims = image_dims(os.path.join(proj, rel))
        if dims:
            # 实际占用 = min(源图长边, 导入上限)。这才是显存里真正的尺寸。
            cur = min(max(dims), eff)
            unknown = ""
        else:
            cur = eff
            unknown = "?"          # 读不出尺寸（exr/hdr/tga 等），标出来别当准数
        new = min(cur, want)       # 只降不升
        mem_now = (cur ** 2) * 1.33 / 1024 / 1024
        mem_new = (new ** 2) * 1.33 / 1024 / 1024
        total_now += mem_now
        total_after += mem_new
        if new < cur:
            rows.append((rel, tier + unknown, sorted(props), cur, new, mem_now - mem_new))

    rows.sort(key=lambda r: -r[5])
    print("=== 建议下调的贴图（按节省量降序）===")
    print("%-62s %-7s %6s→%-6s %8s  %s" % ("路径", "档位", "现在", "目标", "省(MB)", "挂在哪些属性"))
    for rel, tier, props, eff, new, saved in rows[:60]:
        print("%-62s %-7s %6d→%-6d %8.1f  %s" % (rel[-62:], tier, eff, new, saved, ",".join(props)[:40]))

    print("")
    print("需要下调的贴图：%d 张（上界口径：%.1f MB → %.1f MB）" % (len(rows), total_now, total_after))
    print("")
    print("⚠ **这个总量是上界，不是预期收益，别拿去汇报。** 三个原因：")
    print("   ① 闭包会把构建后被 AAO 剔掉的材质也算进来（实测工程C上界 623 MB / 烘焙体实测 160.7 MB）")
    print("   ② 压缩格式按 DXT5 1B/px 假设，实际 DXT1 只有一半")
    print("   ③ 量的是工程资产，性能报告量的是**烘焙克隆体**，两者口径本来就不同")
    print("   → **真实收益只有一个判据：改完重跑 PerfReport 对比前后。**")
    print("")
    print("⚠ 逐张建议本身是可靠的（按 shader 属性判档，与总量无关），可以照着改。")
    print("⚠ 本脚本只出方案不改文件。主图降档前必须做 A/B —— 判据是「看不出来」，不是「省了多少 MB」。")

    if a.csv:
        with io.open(a.csv, "w", encoding="utf-8") as f:
            f.write("path,tier,props,current,target,saved_mb\n")
            for rel, tier, props, eff, new, saved in rows:
                f.write('"%s",%s,"%s",%d,%d,%.2f\n' % (rel, tier, " ".join(props), eff, new, saved))
        print("CSV 已写: " + a.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
