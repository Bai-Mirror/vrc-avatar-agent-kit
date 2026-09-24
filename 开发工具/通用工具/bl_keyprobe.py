# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关
相关素材：素体 FBX 文件
工具链　：Blender 5.2 headless
可复用性：★★★ 换个单子直接能用
用途　　：Blender headless 直接读形态键的顶点位移，判定每条键的真实作用方向，不渲图、不喂模型。

在 Blender 里**直接读形态键的顶点位移**，判定每条键的真实作用方向。
不渲图、不喂模型 —— 能写成闭式判据的就别看图。

用法（headless）：
    blender -b --factory-startup \
        --python bl_keyprobe.py -- <fbx路径> <输出json>
"""
import bpy, sys, json, math, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FBX = argv[0]
OUT = argv[1] if len(argv) > 1 else "keyprobe.json"

KEYS = ["eyelid_down", "eyelid_up", "eyelid_tail_up", "eyelid_tail_down",
        "eyelid_tare1", "eyelid_tare2", "eyelid_turi1", "eyelid_turi2", "eyelid_turi3",
        "eyelid_center_down", "eyelid_center_up", "eyelid_under_tare", "eyelid_under_turi",
        "eyelid_thick", "eyelid_thin", "eyelid_head_sharp", "eyelid_head_wide",
        "eye_size_wide", "eye_size_narrow", "eye_size_big", "eye_size_small",
        "eyebrow_straight", "eyebrow_tare", "eyebrow_turi", "eyebrow_up", "eyebrow_down",
        "option_contour_maru", "option_jaw_narrow", "pupil_big",
        "mouth_corner_angle_up"]

# 清场
bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.import_scene.fbx(filepath=FBX)
except Exception as e:
    json.dump({"error": "FBX 导入失败: %s" % e}, open(OUT, "w"), ensure_ascii=False)
    raise SystemExit(1)

# 找形态键最多的网格
target = None
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    sk = ob.data.shape_keys
    n = len(sk.key_blocks) if sk else 0
    if target is None or n > target[1]:
        target = (ob, n)
ob, nkeys = target
me = ob.data
kb = me.shape_keys.key_blocks
basis = kb[0]

# 判上轴：人形网格最长的那一维就是身高方向
bb = [Vector(c) for c in ob.bound_box]
ext = [max(v[i] for v in bb) - min(v[i] for v in bb) for i in range(3)]
up = ext.index(max(ext))
axis_name = "XYZ"[up]
lat = 0 if up != 0 else 1                 # 左右轴
depth = [i for i in range(3) if i not in (up, lat)][0]

res = {"mesh": ob.name, "verts": len(me.vertices), "shape_keys": nkeys,
       "up_axis": axis_name, "lateral_axis": "XYZ"[lat], "depth_axis": "XYZ"[depth],
       "keys": {}, "missing": []}

names = {k.name for k in kb}
for name in KEYS:
    if name not in names:
        res["missing"].append(name)
        continue
    k = kb[name]
    moved = []
    for i in range(len(me.vertices)):
        d = k.data[i].co - basis.data[i].co
        if d.length > 1e-6:
            moved.append((i, basis.data[i].co.copy(), d))
    if not moved:
        res["keys"][name] = {"moved": 0, "note": "该键位移全为 0"}
        continue

    mags = sorted((m[2].length for m in moved), reverse=True)
    thr = mags[0] * 0.25                                  # 只统计位移显著的那批
    core = [m for m in moved if m[2].length >= thr]
    cx = sum(m[1][lat] for m in core) / len(core)

    def side_stats(sel):
        if not sel:
            return None
        n = len(sel)
        return {
            "n": n,
            "pos_up": round(sum(m[1][up] for m in sel) / n, 5),
            "pos_lat": round(sum(m[1][lat] for m in sel) / n, 5),
            "d_up": round(sum(m[2][up] for m in sel) / n, 6),
            "d_lat": round(sum(m[2][lat] for m in sel) / n, 6),
            "d_depth": round(sum(m[2][depth] for m in sel) / n, 6),
            "max_mag": round(max(m[2].length for m in sel), 6),
        }

    # 按「离脸中线的远近」把核心位移分成 内侧 / 外侧 两半 —— 眼头 vs 眼尾
    core_sorted = sorted(core, key=lambda m: abs(m[1][lat] - cx))
    half = len(core_sorted) // 2
    inner, outer = core_sorted[:half], core_sorted[half:]

    res["keys"][name] = {
        "moved": len(moved), "core": len(core),
        "max_mag": round(mags[0], 6),
        "all": side_stats(core),
        "inner": side_stats(inner),      # 靠中线（眼头侧）
        "outer": side_stats(outer),      # 远中线（眼尾侧）
    }

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("WROTE", OUT, "mesh=", ob.name, "keys=", nkeys, "up=", axis_name)
