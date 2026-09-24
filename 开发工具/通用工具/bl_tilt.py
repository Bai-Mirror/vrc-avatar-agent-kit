# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关
相关素材：素体 FBX 文件
工具链　：Blender 5.2 headless
可复用性：★★ 眼周高度带阈值需按素体调
用途　　：精确测「眼尾相对眼头是抬还是垂」：先按 x 分左右眼，再比每只眼最外 10% 与最内 10% 簇的 Δz。

精确测「眼尾相对眼头是抬还是垂」。

上一版的划分是坏的：把两只眼的全部位移顶点按 |x| 中位数劈半，
会把颧骨/眉骨那些大 |x| 的顶点混进「外侧」。
这一版：**先按 x 正负分成左右眼，再在每只眼内部取最外 10% 与最内 10%**，
比较两簇的 Δz（上轴）。倾斜量 = 外簇Δz − 内簇Δz，正=眼尾相对抬起。

只统计**眼周高度带**内的顶点（用基准形态下、位移最大点的 z 附近 ±3cm），
把眉毛/颧骨排除掉。

用法：blender -b --factory-startup --python bl_tilt.py -- <fbx> <out.json>
"""
import bpy, sys, json
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FBX, OUT = argv[0], argv[1]

KEYS = ["eyelid_tail_up", "eyelid_tail_down", "eyelid_tare1", "eyelid_tare2",
        "eyelid_turi1", "eyelid_turi2", "eyelid_turi3",
        "eyelid_under_tare", "eyelid_under_turi", "eyelid_down", "eyelid_up"]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=FBX)

ob = max((o for o in bpy.data.objects if o.type == "MESH"),
         key=lambda o: len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0)
me = ob.data
kb = me.shape_keys.key_blocks
basis = kb[0]
UP, LAT = 2, 0                      # 上一版已判定：上轴 Z，左右轴 X

res = {"mesh": ob.name, "keys": {}}
for name in KEYS:
    if name not in kb:
        res["keys"][name] = {"err": "键不存在"}
        continue
    k = kb[name]
    moved = []
    for i in range(len(me.vertices)):
        d = k.data[i].co - basis.data[i].co
        if d.length > 1e-6:
            moved.append((basis.data[i].co.copy(), d))
    if not moved:
        res["keys"][name] = {"err": "位移全为 0"}
        continue

    mx = max(m[1].length for m in moved)
    core = [m for m in moved if m[1].length >= mx * 0.20]
    # 眼周高度带：以位移最大的那个点的 z 为中心，上下各 3cm
    zc = max(core, key=lambda m: m[1].length)[0][UP]
    band = [m for m in core if abs(m[0][UP] - zc) < 0.03]
    if len(band) < 40:
        band = core

    out = {"core": len(core), "band": len(band), "max_mag": round(mx, 6), "eyes": {}}
    for side, sel in (("L", [m for m in band if m[0][LAT] > 0]),
                      ("R", [m for m in band if m[0][LAT] < 0])):
        if len(sel) < 20:
            out["eyes"][side] = {"n": len(sel), "err": "样本不足"}
            continue
        sel = sorted(sel, key=lambda m: abs(m[0][LAT]))
        q = max(3, len(sel) // 10)
        inner, outer = sel[:q], sel[-q:]           # 靠中线=眼头，远中线=眼尾
        din = sum(m[1][UP] for m in inner) / len(inner)
        dou = sum(m[1][UP] for m in outer) / len(outer)
        out["eyes"][side] = {
            "n": len(sel), "q": q,
            "inner_dz": round(din, 6), "outer_dz": round(dou, 6),
            "tilt": round(dou - din, 6),           # 正 = 眼尾相对抬起
        }
    tl = [v["tilt"] for v in out["eyes"].values() if "tilt" in v]
    out["tilt_mean"] = round(sum(tl) / len(tl), 6) if tl else None
    res["keys"][name] = out

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("WROTE", OUT)
