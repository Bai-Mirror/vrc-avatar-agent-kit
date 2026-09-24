# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关
相关素材：素体 .blend 文件
工具链　：Blender 5.2 headless
可复用性：★★★ 换个单子直接能用
用途　　：dump 一个 .blend 的全部形态键真名表（键名 + 默认值 + 滑块范围 + 受影响顶点数），厂商不公开键名的素体开工前跑一遍。

在 Blender 里 dump 一个 .blend 的全部形态键真名表（key 名 + 默认值 + 滑块范围 + 受影响顶点数）。
用于厂商不公开 key 名的素体（如 Milfy），开工前必须跑一遍。

用法（headless）：
    blender -b --factory-startup \
        <blend路径> --python bl_keydump.py -- <输出json> [过滤关键词]
"""
import bpy, sys, json

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "keydump.json"
FILTER = argv[1] if len(argv) > 1 else None

res = {"objects": []}
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    sk = ob.data.shape_keys
    if not sk or not sk.key_blocks:
        continue
    kb = sk.key_blocks
    basis = kb[0]
    keys = []
    for k in kb:
        if FILTER and FILTER.lower() not in k.name.lower():
            continue
        moved = 0
        if k != basis:
            for i in range(len(ob.data.vertices)):
                d = k.data[i].co - basis.data[i].co
                if d.length > 1e-6:
                    moved += 1
        keys.append({
            "name": k.name,
            "value": round(k.value, 6),
            "min": round(k.slider_min, 6),
            "max": round(k.slider_max, 6),
            "moved": moved,
        })
    res["objects"].append({
        "object": ob.name,
        "mesh": ob.data.name,
        "verts": len(ob.data.vertices),
        "n_keys": len(kb),
        "keys": keys,
    })

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("WROTE", OUT, "objects=", len(res["objects"]))
for o in res["objects"]:
    print("  %s (%s): %d keys" % (o["object"], o["mesh"], o["n_keys"]))
