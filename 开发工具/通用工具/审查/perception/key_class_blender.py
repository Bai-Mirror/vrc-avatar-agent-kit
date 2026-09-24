#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-17 / E5 —— 形态键类别标定（Blender 离线）
【项目沉淀】通用工具
适用素体：无关
相关素材：素体 FBX 的候选形态键
工具链　：Blender 5.2 headless + Python 3
可复用性：★★ 按素体档案复用
用途　　：T-17 形态键类别标定（Blender 离线）：量刚体拟合残差与法向内收均值，判 pose/shrink/other。


对素体 FBX 的候选形态键，量出「刚体拟合残差」与「法向内收均值」，按
03a_Q1_声明模型.md §Q1-⑤ 的规则判 pose / shrink / other，并把 key_classes
与指标出处写进素体档案。

规则出处：`_长程任务_20260918/感知机制研究/03a_Q1_声明模型.md` §Q1-⑤
任务出处：`_长程任务_20260918/感知机制研究/04_第一期开工清单.md` T-17

运行（本机 blender 5.2 LTS，命令行）：
  # 验收：用 Kaguya + Milfy 两份素体厂商原件 FBX 跑全流程，写素体档案
  # （FBX 位置用参数或环境变量给，未指定则报错提示用法）
  blender -b --factory-startup --python \
      开发工具/通用工具/审查/perception/key_class_blender.py -- --selftest \
      --kaguya-fbx <kaguya.fbx> --milfy-fbx <Milfy 原件.fbx>
  #   或 export KEYCLASS_KAGUYA_FBX=… KEYCLASS_MILFY_FBX=…（相对路径按仓库根解析）

  # 单跑
  blender -b --factory-startup --python .../key_class_blender.py -- \
      --fbx <path.fbx> --mesh Body_b --body Kaguya \
      --keys "Foot_heel_OFF_____足_ヒールオフ,outer_shrink" \
      --out /tmp/metrics.json --yaml-out 开发工具/素体档案/Kaguya.yaml

分类规则（E5 标定后的建议阈值；判定以「归一化刚体残差」为主，尺度无关）：
  ① pose   ：残差比 = 刚体残差 RMS / RMS|Δ| < 0.30 且 旋转角 > 5°
  ② shrink ：残差比 ≥ 0.50 且 法向内收均值 / RMS|Δ| > 0.15（或绝对内收 > 1 mm）
  ③ 灰带 [0.30, 0.50) 与其余情况 → other，保持人判（不硬塞进两簇）
  ④ delete_target/异常：位移集中在极少顶点（选中占比 < 2%）且幅度 > 100 mm
  另附刚体拟合优度 R² 作补充证据。
  03a §Q1-⑤ 的占位绝对阈值（残差 < 2 mm、内收 > 1 mm、残差大）在 Kaguya/Milfy
  实测上判不对已知正样本（pose 键的「部位」含脚踝混合区，残差 3–5 mm），
  故 E5 改用残差比并给出「保守带 + 灰带」建议阈值，工具仍打印占位规则的对照结果。
验收：已知 pose 簇与 shrink 簇的残差比 > 3×，且两簇正样本分类正确；
否则整体报「不可分」，所有键回 other/人判（不写高置信度）。

取舍：
  - 「只取某部位顶点」离线下没有 Unity 的骨权重映射，用「位移幅度 ≥ 最大位移
    的 10%」近似——pose 键的刚性主体位移大、脚踝混合区位移小，天然被排除；
    shrink 键整体位移同量级，不会被误切。默认值可用 --disp-frac 改。
  - 绝对 mm 换算按网格高度自动选 10 的幂（avatar 落在 ~1.5 m）。
  - 只用标准库 + numpy（Blender 自带），YAML 手写保证确定性排序。
"""

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy  # noqa: F401  (仅 Blender 内可用)
import numpy as np

try:
    _HERE = Path(__file__).resolve()
except NameError:  # pragma: no cover
    _HERE = Path.cwd()


# --------------------------------------------------------------------------
# 仓库定位 / 默认档案
# --------------------------------------------------------------------------
def find_repo(explicit=None):
    cands = []
    if explicit:
        cands.append(Path(explicit).resolve())
    cands.append(_HERE)
    cands.append(Path.cwd().resolve())
    for start in cands:
        for p in [start, *start.parents]:
            if (p / "开发工具").is_dir() and (p / "工程A").is_dir():
                return p
    return None


# T-17 指定的标定样本（键名逐一取自 FBX 探针，见 04 T-17 / 03a §Q1-⑤）
SELFTEST_PROFILES = [
    {
        "body": "Kaguya",
        "version": "1.06",
        "fbx_arg": "kaguya_fbx",
        "fbx_env": "KEYCLASS_KAGUYA_FBX",
        "mesh": "Body_b",
        "expected": {
            "pose": [
                "Foot_heel_OFF_____足_ヒールオフ",
                "Foot_Hiheel_____足_ハイヒール",
            ],
            "shrink": [
                "outer_shrink",
                "sailor_shrink",
                "toe_narrow_つま先縮める_R",
                "toe_narrow_つま先縮める_L",
                "toe_horizontal_arch_narrow_つま先ヨコアーチ縮める_R",
                "toe_horizontal_arch_narrow_つま先ヨコアーチ縮め_L",
            ],
        },
    },
    {
        # 素体取厂商原件：工程内的素体 FBX 可能已被捏脸导出覆盖，
        # 须指向与素材包 sha 一致的 v1.5.0 原件（如捏脸前留的还原点）。
        "body": "Milfy",
        "version": "1.5.0",
        "fbx_arg": "milfy_fbx",
        "fbx_env": "KEYCLASS_MILFY_FBX",
        "mesh": "Body_base",
        "expected": {
            "pose": ["Foot_heels", "Foot_highheels"],
            "shrink": ["Foot", "Toe", "Foot_L", "Foot_R", "Toe_L", "Toe_R"],
        },
    },
]


# --------------------------------------------------------------------------
# 参数
# --------------------------------------------------------------------------
def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser(description="T-17 E5 键类别标定")
    ap.add_argument("--selftest", action="store_true",
                    help="用 Kaguya/Milfy 厂商原件 FBX 跑全流程并写素体档案（需 --kaguya-fbx/--milfy-fbx 或对应环境变量）")
    ap.add_argument("--kaguya-fbx", default="", help="selftest 用 Kaguya FBX；缺省读环境变量 KEYCLASS_KAGUYA_FBX")
    ap.add_argument("--milfy-fbx", default="", help="selftest 用 Milfy v1.5.0 原件 FBX；缺省读环境变量 KEYCLASS_MILFY_FBX")
    ap.add_argument("--fbx")
    ap.add_argument("--mesh")
    ap.add_argument("--body")
    ap.add_argument("--version", default="")
    ap.add_argument("--keys", default="", help="逗号分隔；默认取 --expected-pose/--expected-shrink")
    ap.add_argument("--expected-pose", default="")
    ap.add_argument("--expected-shrink", default="")
    ap.add_argument("--out", default="", help="指标表 JSON（缺省不写）")
    ap.add_argument("--yaml-out", default="", help="素体档案 YAML（缺省不写）")
    ap.add_argument("--repo", default=None)
    # 度量参数
    ap.add_argument("--disp-frac", type=float, default=0.0,
                    help="选中顶点：位移 ≥ 最大位移×该比例；0=只按 --floor-mm 取该键的全部有效位移顶点（默认）")
    ap.add_argument("--floor-mm", type=float, default=0.02, help="位移下限 mm（排除数值噪声/未动顶点）")
    # 标定后的分类阈值（E5 实测；原 03a 占位阈值见 --pose-resid-mm/--shrink-inward-mm）
    ap.add_argument("--pose-ratio-max", type=float, default=0.30,
                    help="归一化刚体残差 < 该值视为刚体/pose（保守上限，标定：0.30）")
    ap.add_argument("--shrink-ratio-min", type=float, default=0.50,
                    help="归一化刚体残差 ≥ 该值才可判 shrink（标定：0.50）；两者之间为灰带→other/人判")
    ap.add_argument("--pose-rot-deg", type=float, default=5.0)
    ap.add_argument("--shrink-inward-norm", type=float, default=0.15,
                    help="法向内收 / RMS 位移 > 该值视为 shrink（标定：0.15）")
    ap.add_argument("--pose-resid-mm", type=float, default=2.0,
                    help="03a 占位绝对阈值，仅用于对照报告")
    ap.add_argument("--shrink-inward-mm", type=float, default=1.0,
                    help="03a 占位绝对阈值，仅用于对照报告")
    ap.add_argument("--shrink-resid-ratio", type=float, default=0.5,
                    help="03a 占位：shrink 要求残差比 > 该值")
    ap.add_argument("--sep-min", type=float, default=3.0, help="验收残差比阈值")
    return ap.parse_args(argv)


# --------------------------------------------------------------------------
# FBX 导入与网格度量
# --------------------------------------------------------------------------
def import_fbx(fbx_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx_path))
    return [o for o in bpy.data.objects if o.type == "MESH"]


def auto_mm_per_bu(dims):
    """按最长边自动选 10 的幂，使模型高度落在 ~1.5 m（mm 世界）。"""
    h = max(dims) if max(dims) > 0 else 1.0
    best = None
    for f in (1000.0, 100.0, 10.0, 1.0, 0.1):
        d = abs(h * f - 1500.0)
        if best is None or d < best[0]:
            best = (d, f)
    return best[1]


def _foreach(collection, attr, ncomp):
    n = len(collection)
    arr = np.empty(n * ncomp, dtype=np.float64)
    try:
        collection.foreach_get(attr, arr)
        return arr.reshape(n, ncomp)
    except Exception:
        return np.array([getattr(x, attr)[:ncomp] for x in collection], dtype=np.float64)


def kabsch(P, Q):
    """最优刚体 R,t 使 R@P.T+t ≈ Q.T。"""
    cp = P.mean(axis=0)
    cq = Q.mean(axis=0)
    H = (P - cp).T @ (Q - cq)
    U, _S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T
    t = cq - R @ cp
    return R, t


def analyze_key(ob, base_co, kb, normals, mm_per_bu, args):
    n = len(ob.data.vertices)
    q = _foreach(kb.data, "co", 3)
    d = (q - base_co) * mm_per_bu                      # 位移，mm
    mag = np.linalg.norm(d, axis=1)
    max_d = float(mag.max())
    floor = args.floor_mm
    sel = mag >= max(args.disp_frac * max_d, floor)
    n_sel = int(sel.sum())
    out = {
        "key": kb.name,
        "n_verts": n,
        "n_sel": n_sel,
        "sel_frac": n_sel / n if n else 0.0,
        "max_delta_mm": max_d,
        "rms_delta_mm": float(np.sqrt((mag[sel] ** 2).mean())) if n_sel else 0.0,
        "class": "other",
        "reason": "",
    }
    if n_sel < 8 or max_d < args.floor_mm:
        out["reason"] = "位移过小/顶点过少"
        return out

    P = base_co[sel]
    Q = q[sel]
    R, t = kabsch(P, Q)
    res = Q - (P @ R.T + t)
    resid_mm = float(np.sqrt((res ** 2).sum(axis=1).mean())) * mm_per_bu   # ← 换算到 mm
    rms_delta = out["rms_delta_mm"] or 1e-12
    ratio = resid_mm / rms_delta
    cos = (np.trace(R) - 1.0) / 2.0
    cos = max(-1.0, min(1.0, cos))
    rot_deg = math.degrees(math.acos(cos))
    n_sel_v = normals[sel]
    inward = -np.einsum("ij,ij->i", d[sel], n_sel_v)    # >0 = 内收
    mean_inward = float(inward.mean())
    inward_norm = mean_inward / rms_delta
    inward_frac = float((inward > 0).mean())
    # 刚体拟合优度 R²（0..1，1=纯刚体；对径向收缩敏感，作残差比的补充证据）
    ss_tot = float(((Q - Q.mean(axis=0)) ** 2).sum())
    rigid_r2 = 1.0 - float((res ** 2).sum()) / ss_tot if ss_tot > 0 else None

    out.update({
        "rms_delta_mm": float(rms_delta),
        "rigid_residual_mm": resid_mm,
        "residual_ratio": ratio,
        "rigid_r2": rigid_r2,
        "rotation_deg": rot_deg,
        "mean_inward_mm": mean_inward,
        "mean_inward_norm": inward_norm,
        "inward_frac": inward_frac,
    })

    # 对照：03a §Q1-⑤ 的占位绝对阈值（E5 实测判不对，仅打印）
    lit = "other"
    if resid_mm < args.pose_resid_mm and rot_deg > args.pose_rot_deg:
        lit = "pose"
    elif abs(mean_inward) > args.shrink_inward_mm and ratio > args.shrink_resid_ratio:
        lit = "shrink"
    out["class_literal"] = lit

    # 规则 ③：位移集中在极少顶点且幅度 > 100 mm
    if out["sel_frac"] < 0.02 and max_d > 100.0:
        out["class"] = "delete_target"
        out["reason"] = "位移集中于 <2% 顶点且 >100mm（疑 Delete 目标/异常）"
    elif ratio < args.pose_ratio_max and rot_deg > args.pose_rot_deg:
        out["class"] = "pose"
        out["reason"] = (f"残差比 {ratio:.2f} < {args.pose_ratio_max} 且旋转 {rot_deg:.1f}° > "
                         f"{args.pose_rot_deg}°（绝对残差 {resid_mm:.1f}mm，R²={rigid_r2:.3f}）")
    elif ratio >= args.shrink_ratio_min and (inward_norm > args.shrink_inward_norm
                                             or abs(mean_inward) > args.shrink_inward_mm):
        out["class"] = "shrink"
        out["reason"] = (f"残差比 {ratio:.2f} ≥ {args.shrink_ratio_min} 且内收 {mean_inward:.2f}mm"
                         f"（归一 {inward_norm:.2f} > {args.shrink_inward_norm}）")
    elif args.pose_ratio_max <= ratio < args.shrink_ratio_min:
        out["class"] = "other"
        out["reason"] = (f"残差比 {ratio:.2f} 落在灰带 [{args.pose_ratio_max}, {args.shrink_ratio_min})"
                         f"—— 不可判，保持人判")
    else:
        out["class"] = "other"
        out["reason"] = (f"残差比 {ratio:.2f}，旋转 {rot_deg:.1f}°，内收 {mean_inward:.2f}mm"
                         f"（归一 {inward_norm:.2f}）—— 归 other 待人判")
    return out


# --------------------------------------------------------------------------
# 单档案标定
# --------------------------------------------------------------------------
def calibrate(profile, repo, args):
    fbx = Path(profile["fbx"])
    if not fbx.is_absolute():
        fbx = repo / fbx
    expected = profile.get("expected", {"pose": [], "shrink": []})
    if args.keys:
        keys = [k for k in args.keys.split(",") if k]
        expected = {"pose": [], "shrink": []}
    elif args.expected_pose or args.expected_shrink:
        expected = {
            "pose": [k for k in args.expected_pose.split(",") if k],
            "shrink": [k for k in args.expected_shrink.split(",") if k],
        }
        keys = expected["pose"] + expected["shrink"]
    else:
        keys = expected["pose"] + expected["shrink"]
    expected_of = {}
    for cls in ("pose", "shrink"):
        for k in expected.get(cls, []):
            expected_of[k] = cls

    if not fbx.exists():
        raise SystemExit(f"[T-17] 找不到 FBX：{fbx}")

    meshes = import_fbx(fbx)
    ob = next((o for o in meshes if o.name == profile["mesh"]), None)
    if ob is None:
        names = ", ".join(o.name for o in meshes)
        raise SystemExit(f"[T-17] FBX 里没有网格 {profile['mesh']}；现有：{names}")

    mm_per_bu = auto_mm_per_bu([ob.dimensions.x, ob.dimensions.y, ob.dimensions.z])
    sk = ob.data.shape_keys
    if sk is None:
        raise SystemExit(f"[T-17] 网格 {ob.name} 没有形态键")

    base_co = _foreach(sk.reference_key.data, "co", 3)
    normals = _foreach(ob.data.vertices, "normal", 3)
    nlen = np.linalg.norm(normals, axis=1, keepdims=True)
    nlen[nlen == 0] = 1.0
    normals = normals / nlen

    have = {kb.name for kb in sk.key_blocks}
    missing = [k for k in keys if k not in have]

    rows = []
    for k in keys:
        kb = sk.key_blocks.get(k)
        if kb is None:
            rows.append({"key": k, "class": "missing", "reason": "FBX 中无此键"})
            continue
        rows.append(analyze_key(ob, base_co, kb, normals, mm_per_bu, args))

    # 簇分离度：已知正样本的残差/位移比 与 原始残差
    def cluster_mean(cls, field):
        vals = [r[field] for r in rows if expected_of.get(r["key"]) == cls and field in r]
        return float(np.mean(vals)) if vals else None

    def cluster_minmax(cls, field):
        vals = [r[field] for r in rows if expected_of.get(r["key"]) == cls and field in r]
        return (float(np.min(vals)), float(np.max(vals))) if vals else (None, None)

    pose_ratio = cluster_mean("pose", "residual_ratio")
    shrink_ratio = cluster_mean("shrink", "residual_ratio")
    pose_resid = cluster_mean("pose", "rigid_residual_mm")
    shrink_resid = cluster_mean("shrink", "rigid_residual_mm")
    ratio_norm = (shrink_ratio / pose_ratio) if pose_ratio not in (None, 0) else None
    ratio_abs = (shrink_resid / pose_resid) if pose_resid not in (None, 0) else None
    separable = ratio_norm is not None and ratio_norm > args.sep_min
    hits = {r["key"]: r["class"] for r in rows}
    correct = all(hits.get(k) == c for k, c in expected_of.items() if hits.get(k) != "missing")
    mismatches = [(k, c, hits.get(k)) for k, c in expected_of.items() if hits.get(k) != c]

    # 建议阈值：取 pose 簇最大残差比 与 shrink 簇最小残差比 的几何中点
    pose_max = cluster_minmax("pose", "residual_ratio")[1]
    shrink_min = cluster_minmax("shrink", "residual_ratio")[0]
    suggested = (math.sqrt(pose_max * shrink_min)
                 if pose_max and shrink_min and pose_max > 0 else None)
    # literal(03a 占位) 规则正确率对照
    lit_hits = {r["key"]: r.get("class_literal") for r in rows}
    lit_correct = all(lit_hits.get(k) == c for k, c in expected_of.items()
                      if lit_hits.get(k) is not None)
    lit_mismatch = [(k, c, lit_hits.get(k)) for k, c in expected_of.items()
                    if lit_hits.get(k) != c]

    result = {
        "body": profile.get("body"),
        "version": profile.get("version", ""),
        "mesh": ob.name,
        "fbx": str(fbx),
        "fbx_bytes": fbx.stat().st_size,
        "fbx_sha256": sha256(fbx),
        "blender": bpy.app.version_string,
        "mm_per_bu": mm_per_bu,
        "mesh_dims_mm": [round(v * mm_per_bu, 1) for v in (ob.dimensions.x, ob.dimensions.y, ob.dimensions.z)],
        "n_shapekeys": len(sk.key_blocks),
        "params": {
            "disp_frac": args.disp_frac, "floor_mm": args.floor_mm,
            "pose_ratio_max": args.pose_ratio_max, "shrink_ratio_min": args.shrink_ratio_min,
            "pose_rot_deg": args.pose_rot_deg,
            "shrink_inward_norm": args.shrink_inward_norm,
            "shrink_inward_mm": args.shrink_inward_mm, "pose_resid_mm": args.pose_resid_mm,
            "shrink_resid_ratio": args.shrink_resid_ratio, "sep_min": args.sep_min,
        },
        "cluster": {
            "pose_mean_residual_ratio": pose_ratio,
            "shrink_mean_residual_ratio": shrink_ratio,
            "ratio_normalized": ratio_norm,
            "pose_mean_residual_mm": pose_resid,
            "shrink_mean_residual_mm": shrink_resid,
            "ratio_absolute": ratio_abs,
            "pose_max_residual_ratio": pose_max,
            "shrink_min_residual_ratio": shrink_min,
            "suggested_ratio_threshold": suggested,
            "pose_rotation_deg_range": cluster_minmax("pose", "rotation_deg"),
            "shrink_rotation_deg_range": cluster_minmax("shrink", "rotation_deg"),
            "pose_inward_norm_range": cluster_minmax("pose", "mean_inward_norm"),
            "shrink_inward_norm_range": cluster_minmax("shrink", "mean_inward_norm"),
            "literal_rule_correct": bool(lit_correct),
            "literal_rule_mismatches": lit_mismatch,
            "separable": bool(separable),
            "criterion": f"归一化残差比 > {args.sep_min}×",
            "expected_correct": bool(correct),
            "mismatches": mismatches,
        },
        "keys": rows,
        "missing_keys": missing,
    }
    if not separable:
        for r in result["keys"]:
            if r["class"] in ("pose", "shrink"):
                r["class"] = "other"
                r["reason"] = "簇不可分（" + (r.get("reason") or "") + "）→ 保持人判"
    return result


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# 输出：指标表 + 素体档案 YAML
# --------------------------------------------------------------------------
def confidence_of(row):
    if row["class"] in ("pose", "shrink"):
        return "high"
    if row["class"] == "other":
        return "mid"
    return "low"


def yaml_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return repr(v)
    return json.dumps(str(v), ensure_ascii=False)


def yaml_flow(v):
    """list/tuple → YAML flow 序列；标量走 yaml_scalar。"""
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(yaml_flow(x) for x in v) + "]"
    if isinstance(v, float):
        return repr(round(v, 6))
    return yaml_scalar(v)


def write_yaml(result, path, repo):
    tool_rel = os.path.relpath(_HERE, repo) if str(_HERE).startswith(str(repo)) else str(_HERE)
    fbx_rel = os.path.relpath(result["fbx"], repo) if result["fbx"].startswith(str(repo)) else result["fbx"]
    by_class = {"pose": [], "shrink": [], "delete_target": [], "other": [], "missing": []}
    for r in result["keys"]:
        by_class.setdefault(r["class"], []).append(r)

    L = []
    L.append(f"# 素体档案 · {result['body']} —— T-17 / E5 键类别标定产物")
    L.append("# 本文件当前只写 key_classes 与指标出处；baseline/regions/vendor_conventions")
    L.append("# 等段由 T-03 起草补全（03a §Q1-④）。key_classes 由 key_class_blender.py 实测生成。")
    L.append("schema: body-profile/0.1")
    L.append(f"body: {yaml_scalar(result['body'])}")
    if result.get("version"):
        L.append(f"version: {yaml_scalar(result['version'])}")
    L.append(f"mesh: {yaml_scalar(result['mesh'])}")
    L.append("key_classes:")
    for cls in ("pose", "shrink", "delete_target", "other"):
        cls_key = {"delete_target": "delete_targets"}.get(cls, cls)
        items = by_class.get(cls, [])
        if not items:
            L.append(f"  {cls_key}: {{}}")
            continue
        L.append(f"  {cls_key}:")
        for r in items:
            L.append(f"    {yaml_scalar(r['key'])}:")
            L.append(f"      confidence: {confidence_of(r)}")
            L.append(f"      source: {yaml_scalar('T-17 E5 Blender 实测（key_class_blender.py）')}")
            if r["class"] in ("pose", "shrink"):
                if "rotation_deg" in r:
                    L.append(f"      rotation_deg: {round(r['rotation_deg'], 2)}")
                if "rigid_residual_mm" in r:
                    L.append(f"      rigid_residual_mm: {round(r['rigid_residual_mm'], 4)}")
                if "residual_ratio" in r:
                    L.append(f"      residual_ratio: {round(r['residual_ratio'], 4)}")
                if "mean_inward_mm" in r:
                    L.append(f"      mean_inward_mm: {round(r['mean_inward_mm'], 4)}")
                L.append(f"      reason: {yaml_scalar(r.get('reason', ''))}")
    # 指标出处
    c = result["cluster"]
    L.append("key_classes_metrics:")
    L.append(f"  source: {yaml_scalar('T-17 E5 键类别标定（04_第一期开工清单.md T-17；规则 03a §Q1-⑤）')}")
    L.append(f"  tool: {yaml_scalar(tool_rel)}")
    L.append(f"  blender: {yaml_scalar(result['blender'])}")
    L.append(f"  fbx: {{path: {yaml_scalar(fbx_rel)}, sha256: {yaml_scalar(result['fbx_sha256'])}, bytes: {result['fbx_bytes']}}}")
    L.append(f"  mesh: {yaml_scalar(result['mesh'])}")
    L.append(f"  mesh_dims_mm: [{', '.join(str(v) for v in result['mesh_dims_mm'])}]")
    L.append(f"  mm_per_blender_unit: {yaml_scalar(result['mm_per_bu'])}")
    p = result["params"]
    L.append("  params: {" + ", ".join(f"{k}: {yaml_scalar(v)}" for k, v in p.items()) + "}")
    L.append("  cluster:")
    L.append(f"    pose_mean_residual_ratio: {yaml_scalar(c['pose_mean_residual_ratio'])}")
    L.append(f"    shrink_mean_residual_ratio: {yaml_scalar(c['shrink_mean_residual_ratio'])}")
    L.append(f"    ratio_normalized: {yaml_scalar(c['ratio_normalized'])}")
    L.append(f"    pose_mean_residual_mm: {yaml_scalar(c['pose_mean_residual_mm'])}")
    L.append(f"    shrink_mean_residual_mm: {yaml_scalar(c['shrink_mean_residual_mm'])}")
    L.append(f"    ratio_absolute: {yaml_scalar(c['ratio_absolute'])}")
    L.append(f"    pose_max_residual_ratio: {yaml_scalar(c['pose_max_residual_ratio'])}")
    L.append(f"    shrink_min_residual_ratio: {yaml_scalar(c['shrink_min_residual_ratio'])}")
    L.append(f"    suggested_ratio_threshold: {yaml_scalar(round(c['suggested_ratio_threshold'], 4) if c['suggested_ratio_threshold'] else None)}")
    L.append(f"    pose_rotation_deg_range: {yaml_flow(list(c['pose_rotation_deg_range']))}")
    L.append(f"    shrink_rotation_deg_range: {yaml_flow(list(c['shrink_rotation_deg_range']))}")
    L.append(f"    pose_inward_norm_range: {yaml_flow(list(c['pose_inward_norm_range']))}")
    L.append(f"    shrink_inward_norm_range: {yaml_flow(list(c['shrink_inward_norm_range']))}")
    L.append(f"    literal_rule_correct: {yaml_scalar(c['literal_rule_correct'])}")
    L.append(f"    literal_rule_mismatches: {yaml_flow([list(t) for t in c['literal_rule_mismatches']])}")
    L.append(f"    separable: {yaml_scalar(c['separable'])}")
    L.append(f"    criterion: {yaml_scalar(c['criterion'])}")
    L.append(f"    expected_correct: {yaml_scalar(c['expected_correct'])}")
    L.append("  suggested_thresholds:")
    L.append(f"    residual_ratio_pose_max: {yaml_scalar(result['params']['pose_ratio_max'])}")
    L.append(f"    residual_ratio_shrink_min: {yaml_scalar(result['params']['shrink_ratio_min'])}")
    L.append(f"    gray_band_route: {yaml_scalar('other/人判')}")
    L.append(f"    rotation_deg_pose_min: {yaml_scalar(result['params']['pose_rot_deg'])}")
    L.append(f"    inward_norm_shrink_min: {yaml_scalar(result['params']['shrink_inward_norm'])}")
    L.append(f"    per_body_geometric_midpoint: {yaml_scalar(round(c['suggested_ratio_threshold'], 4) if c['suggested_ratio_threshold'] else None)}")
    L.append(f"    note: {yaml_scalar('残差比阈值取 pose 簇最大与 shrink 簇最小的几何中点；E5 实测 pose≤%.3f、shrink≥%.3f；操作上取保守带 [%.2f, %.2f)，灰带归人判' % (c['pose_max_residual_ratio'] or 0, c['shrink_min_residual_ratio'] or 0, result['params']['pose_ratio_max'], result['params']['shrink_ratio_min']))}")
    L.append("  per_key:")
    for r in result["keys"]:
        L.append(f"    {yaml_scalar(r['key'])}:")
        L.append(f"      class: {yaml_scalar(r['class'])}")
        L.append(f"      confidence: {yaml_scalar(confidence_of(r))}")
        if "class_literal" in r:
            L.append(f"      class_literal_03a: {yaml_scalar(r['class_literal'])}")
        for f in ("n_sel", "sel_frac", "rms_delta_mm", "rigid_residual_mm",
                  "residual_ratio", "rigid_r2", "rotation_deg", "mean_inward_mm",
                  "mean_inward_norm", "inward_frac", "max_delta_mm"):
            if f in r:
                L.append(f"      {f}: {round(r[f], 6) if isinstance(r[f], float) else r[f]}")
        L.append(f"      reason: {yaml_scalar(r.get('reason', ''))}")
    if result["missing_keys"]:
        L.append("  missing_keys: " + yaml_flow(result["missing_keys"]))
    text = "\n".join(L) + "\n"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    return text


def print_table(result):
    print(f"\n=== T-17 E5 · {result['body']} · mesh={result['mesh']} "
          f"({result['n_shapekeys']} keys, {result['mesh_dims_mm']} mm) ===")
    hdr = f"{'key':<42} {'class':<8} {'lit03a':<8} {'sel':>6} {'rmsΔ':>8} {'resid':>8} {'ratio':>7} {'R²':>6} {'rot°':>6} {'inward':>8} {'inN':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in result["keys"]:
        if "rigid_residual_mm" not in r:
            print(f"{r['key']:<42} {r['class']:<8} {'-':<8}  -- {r.get('reason','')}")
            continue
        r2 = f"{r['rigid_r2']:.3f}" if r.get("rigid_r2") is not None else "-"
        print(f"{r['key']:<42} {r['class']:<8} {r.get('class_literal','-'):<8} {r['n_sel']:>6} "
              f"{r['rms_delta_mm']:>8.3f} {r['rigid_residual_mm']:>8.3f} "
              f"{r['residual_ratio']:>7.3f} {r2:>6} {r['rotation_deg']:>6.1f} {r['mean_inward_mm']:>8.3f} "
              f"{r['mean_inward_norm']:>6.2f}")
    c = result["cluster"]
    print(f"pose 簇 残差比 mean={c['pose_mean_residual_ratio']:.4f} max={c['pose_max_residual_ratio']:.4f}"
          f" | shrink 簇 mean={c['shrink_mean_residual_ratio']:.4f} min={c['shrink_min_residual_ratio']:.4f}")
    sug = c['suggested_ratio_threshold']
    rn, ra = c['ratio_normalized'], c['ratio_absolute']
    if rn is not None and ra is not None:
        sep_line = (f"分离度(归一化) = {rn:.2f} ×   (绝对 {ra:.2f} ×)   "
                    f"-> {'可分' if c['separable'] else '不可分'}")
        if sug is not None:
            sep_line += f"        建议残差比阈值 = {sug:.3f}"
    else:
        sep_line = "分离度 = 无法计算（缺簇）"
    print(sep_line)
    print(f"已知正样本分类正确(标定规则) = {c['expected_correct']}   mismatches={c['mismatches']}")
    print(f"03a 占位阈值对照 = {c['literal_rule_correct']}   mismatches={c['literal_rule_mismatches']}")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    args = parse_args()
    repo = find_repo(args.repo)
    if repo is None:
        raise SystemExit("[T-17] 找不到仓库根（含 开发工具/ 与 工程A/）")

    if args.selftest:
        missing = []
        profiles = []
        for base in SELFTEST_PROFILES:
            prof = dict(base)
            prof["fbx"] = getattr(args, prof["fbx_arg"]) or os.environ.get(prof["fbx_env"], "")
            if not prof["fbx"]:
                missing.append(f"--{prof['fbx_arg'].replace('_', '-')} / {prof['fbx_env']}")
            profiles.append(prof)
        if missing:
            raise SystemExit("[T-17] --selftest 需要素体 FBX 路径，未指定：" + "；".join(missing) +
                             "\n用法：... key_class_blender.py -- --selftest --kaguya-fbx <kaguya.fbx> --milfy-fbx <Milfy.fbx>")
        overall = []
        for prof in profiles:
            res = calibrate(prof, repo, args)
            print_table(res)
            yaml_path = repo / "开发工具" / "素体档案" / f"{prof['body']}.yaml"
            write_yaml(res, yaml_path, repo)
            print(f"[T-17] 写入 {yaml_path}")
            overall.append(res)
        ok = all(r["cluster"]["separable"] and r["cluster"]["expected_correct"] for r in overall)
        print("\n[SELFTEST] " + ("PASS" if ok else "FAIL") +
              " —— pose 簇 / shrink 簇残差比 " +
              ", ".join(f"{r['body']}={r['cluster']['ratio_normalized']:.2f}x" for r in overall))
        if args.out:
            Path(args.out).write_text(json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8")
        # 非零退出让验收可判
        if not ok:
            raise SystemExit(1)
        return

    if not args.fbx:
        raise SystemExit("[T-17] 需要 --fbx（或用 --selftest）")
    prof = {
        "body": args.body or Path(args.fbx).stem,
        "version": args.version,
        "fbx": args.fbx,
        "mesh": args.mesh,
        "expected": {
            "pose": [k for k in args.expected_pose.split(",") if k],
            "shrink": [k for k in args.expected_shrink.split(",") if k],
        },
    }
    res = calibrate(prof, repo, args)
    print_table(res)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[T-17] 指标表 -> {args.out}")
    if args.yaml_out:
        y = args.yaml_out if os.path.isabs(args.yaml_out) else str(repo / args.yaml_out)
        write_yaml(res, y, repo)
        print(f"[T-17] 素体档案 -> {y}")
    if not res["cluster"]["separable"] or not res["cluster"]["expected_correct"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
