# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关
相关素材：素体 .blend 文件
工具链　：Blender 5.2 headless
可复用性：★★★ 换个单子直接能用
用途　　：打开 .blend 对指定形态键输出位移量级、平均方向与受影响区域质心。

通用形态键方向/强度测量：打开 .blend，对指定键输出 位移量级 + 平均方向 + 受影响区域质心。
用法: blender -b <blend> --python bl_keymeasure.py -- <json输出> <键名...>
"""
import bpy, sys, json
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0]
KEYS = argv[1:]

target = None
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    sk = ob.data.shape_keys
    if sk and (target is None or len(sk.key_blocks) > target[1]):
        target = (ob, len(sk.key_blocks))
ob, nkeys = target
me = ob.data
kb = me.shape_keys.key_blocks
basis = kb[0]

bb = [Vector(c) for c in ob.bound_box]
ext = [max(v[i] for v in bb) - min(v[i] for v in bb) for i in range(3)]
up = ext.index(max(ext))
lat = 0 if up != 0 else 1
depth = [i for i in range(3) if i not in (up, lat)][0]
axis = "XYZ"

res = {"mesh": ob.name, "verts": len(me.vertices), "up": axis[up], "lat": axis[lat], "depth": axis[depth], "keys": {}}
names = {k.name: k for k in kb}
for name in KEYS:
    k = names.get(name)
    if k is None:
        res["keys"][name] = {"missing": True}
        continue
    moved = []
    for i in range(len(me.vertices)):
        d = k.data[i].co - basis.data[i].co
        if d.length > 1e-6:
            moved.append((i, basis.data[i].co.copy(), d))
    if not moved:
        res["keys"][name] = {"moved": 0}
        continue
    mags = sorted([m[2].length for m in moved], reverse=True)
    thr = mags[0] * 0.25
    core = [m for m in moved if m[2].length >= thr]
    n = len(core)
    cx = sum(m[1][lat] for m in core) / n
    cy = sum(m[1][up] for m in core) / n
    cz = sum(m[1][depth] for m in core) / n
    dx = sum(m[2][lat] for m in core) / n
    dy = sum(m[2][up] for m in core) / n
    dz = sum(m[2][depth] for m in core) / n
    dlat_abs = sum(abs(m[2][lat]) for m in core) / n
    du_abs = sum(abs(m[2][up]) for m in core) / n
    dd_abs = sum(abs(m[2][depth]) for m in core) / n
    # 展开度：受影响顶点 lat 坐标的离散度变化（对称键看这个）
    lat_before = [m[1][lat] for m in core]
    lat_after = [m[1][lat] + m[2][lat] for m in core]
    import statistics
    spread = statistics.pstdev(lat_after) - statistics.pstdev(lat_before)
    # 眼尾（外侧10%）的 d_up：判眼尾抬/垂
    maxdev = max(abs(m[1][lat] - cx) for m in core)
    outer = [m for m in core if abs(m[1][lat] - cx) > 0.85 * maxdev]
    o_up = sum(m[2][up] for m in outer) / len(outer) if outer else 0.0
    o_lat = sum(m[2][lat] for m in outer) / len(outer) if outer else 0.0
    res["keys"][name] = {
        "moved": len(moved), "core": n,
        "max_mag": round(mags[0], 5),
        "centroid_lat": round(cx, 4), "centroid_up": round(cy, 4), "centroid_depth": round(cz, 4),
        "d_lat": round(dx, 5), "d_up": round(dy, 5), "d_depth": round(dz, 5),
        "abs_lat": round(dlat_abs, 5), "abs_up": round(du_abs, 5), "abs_depth": round(dd_abs, 5),
        "spread_delta": round(spread, 5),
        "outer_up": round(o_up, 5), "outer_lat": round(o_lat, 5),
    }

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("WROTE", OUT)
