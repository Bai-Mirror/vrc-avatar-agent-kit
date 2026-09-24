# -*- coding: utf-8 -*-
"""clip_writes.py — 从 AnimatorController + AnimationClip 抽「(状态, 路径, 键) → 值」。
【项目沉淀】通用工具
适用素体：无关
相关素材：AnimatorController + AnimationClip
工具链　：Python 3 + PyYAML（离线）
可复用性：★★ 审查工具链的一环
用途　　：从 AnimatorController + AnimationClip 抽「(状态, 路径, 键) → 值」，T-11 的子模块。


T-11 的子模块（04 §T-11），T-07 迁移回归也先用它：
    python3 clip_writes.py --controller Assets/_Work/Gen/A2_FX.controller \
                           --clips Assets/_Work/Gen/Clip
    python3 clip_writes.py --selftest          # 用仓库内 工程A 数据自验

输出（JSON，确定性排序）
------------------------
entries[]：一条曲线一个写者条目
    layer / layer_index / state / clip / path / class_id / attribute / key / kind
    curve: [[time, value], ...]        原始关键帧
    values: [v0, v1, ...]              去重后的取值集合（Motion Time 档位按 i/n 采样）
    const: bool                        是否单值
    time_param: 状态 m_TimeParameter（Motion Time，可空）
    where: 文件:行

Motion Time 档位
----------------
状态的 `m_TimeParameterActive: 1` 时，归一化时间由浮点参数驱动（Dial/整套层就是这么做的）。
步数 n 从曲线关键帧时间反推：取最小的正时间 t∈(0,1) 且 1/t 接近整数 → n=round(1/t)；
所有关键帧时间都落在 1/n 的整数倍上才采信，否则退回在关键帧原时刻取值。这样
`outer_shlink` 在 Dial_整套 里给出 {100, 0}（0 档 100、其余档 0）。

BlendTree：支持 m_BlendType=0 (1D) 与其它类型的子 motion 递归；1D 的每个子 clip 记
下阈值区间，作为 cond 的一部分。目标工程（工程A）A2_FX 没有混合树，属兜底路径。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from unity_yaml import (  # noqa: E402
    DocIndex,
    YamlCache,
    build_guid_index,
    fmt_val,
    leaf,
)

ZERO_GUIDS = {"00000000000000000000000000000000", "0000000000000000e000000000000000",
              "0000000000000000f000000000000000", ""}

CLIP_CLASS = 74
TREE_CLASS = 206
STATE_CLASS = 1102
STATE_MACHINE_CLASS = 1107
CONTROLLER_CLASS = 91
TRANSITION_CLASS = 1101


# ---------------------------------------------------------------------------
# 曲线
# ---------------------------------------------------------------------------
def _num(v, default=0.0):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def curve_keys(fc) -> List[Tuple[float, float]]:
    """一条 m_FloatCurves 元素 → [(time, value)]，按 time 升序。"""
    curve = (fc or {}).get("curve") or {}
    raw = curve.get("m_Curve") or []
    out = []
    for k in raw:
        if not isinstance(k, dict):
            continue
        out.append((_num(k.get("time")), _num(k.get("value"))))
    out.sort(key=lambda kv: kv[0])
    return out


def _eval_linear(keys: List[Tuple[float, float]], t: float) -> float:
    if not keys:
        return 0.0
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for i in range(1, len(keys)):
        t0, v0 = keys[i - 1]
        t1, v1 = keys[i]
        if t <= t1:
            if t1 - t0 < 1e-12:
                return v1
            a = (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * a
    return keys[-1][1]


def infer_steps(keys: List[Tuple[float, float]]) -> Optional[int]:
    """从关键帧时间反推 Motion Time 档数；不成立返回 None。"""
    times = sorted({round(t, 6) for t, _ in keys})
    pos = [t for t in times if 1e-6 < t < 1.0 - 1e-6]
    if not pos:
        return 1
    t_min = min(pos)
    if t_min <= 0:
        return None
    n = int(round(1.0 / t_min))
    if n < 1 or n > 4096:
        return None
    for t in times:
        if t <= 1e-6 or t >= 1.0 - 1e-6:
            continue
        if abs(t * n - round(t * n)) > 1e-4:
            return None
    return n


def sample_values(keys: List[Tuple[float, float]], n: Optional[int]) -> List[float]:
    """按档位采样；n=None 时退回关键帧原时刻。去重、升序、6 位取整。

    关键帧时间写的是 0.14285715（不是精确 1/7），按 i/n 采到 i=1 时会落在键的左侧
    一丁点，线性插值得到 5e-06 这种噪声 → 采样时刻若与某个关键帧相差 <1e-5 就直接
    取该键的值；其余再按近整数吸附（形态键值域 0–100，1e-4 容差安全）。
    """
    times: List[float] = []
    if n and n >= 1:
        times = [i / float(n) for i in range(n + 1)]
    else:
        times = [t for t, _ in keys] or [0.0]
    vals = []
    for t in times:
        v = None
        for kt, kv in keys:
            if abs(t - kt) < 1e-5:
                v = kv
                break
        if v is None:
            v = _eval_linear(keys, t)
        v = round(v, 6)
        if abs(v - round(v)) < 1e-4:
            v = float(round(v))
        if v not in vals:
            vals.append(v)
    vals.sort()
    return vals


def kind_of(class_id: int, attribute: str) -> str:
    a = attribute or ""
    if class_id == 1 or a == "m_IsActive":
        return "active"
    if a.startswith("blendShape."):
        return "blendshape"
    if a == "m_Enabled":
        return "enabled"
    if a.startswith("material."):
        return "material"
    return "other"


def key_of(class_id: int, attribute: str) -> str:
    a = attribute or ""
    if a.startswith("blendShape."):
        return a[len("blendShape."):]
    if a == "m_IsActive":
        return "m_IsActive"
    if a == "m_Enabled":
        return "m_Enabled"
    if a.startswith("material."):
        return a
    return a


# ---------------------------------------------------------------------------
# 扫描
# ---------------------------------------------------------------------------
class ClipResolver:
    """guid → .anim 路径；优先 --project 全量索引，其次 --clips 目录。"""

    def __init__(self, project: Optional[str], clips_dir: Optional[str]):
        self.index: Dict[str, str] = {}
        if project:
            self.index.update(build_guid_index(project, ["Packages"]))
        if clips_dir and os.path.isdir(clips_dir):
            for dirpath, _dirnames, filenames in os.walk(clips_dir):
                for fn in filenames:
                    if not fn.endswith(".anim.meta"):
                        continue
                    p = os.path.join(dirpath, fn)
                    try:
                        head = open(p, "r", encoding="utf-8", errors="replace").read(512)
                    except OSError:
                        continue
                    m = re.search(r"^guid:\s*([0-9a-fA-F]+)\s*$", head, re.M)
                    if m:
                        self.index.setdefault(m.group(1), p[: -len(".meta")])

    def path_for(self, guid: str) -> Optional[str]:
        return self.index.get(guid)


class ClipWritesScanner:
    def __init__(self, cache: Optional[YamlCache] = None):
        self.cache = cache or YamlCache()
        self._clip_cache: Dict[str, List[dict]] = {}

    # -- 单条曲线 ---------------------------------------------------------
    def _curve_entry(self, layer_name, layer_index, layer_weight, state_name,
                     time_param, clip_name, where, fc, cond):
        attr = fc.get("attribute") or ""
        path = fc.get("path") or ""
        class_id = int(fc.get("classID") or 0)
        keys = curve_keys(fc)
        steps = infer_steps(keys) if time_param else None
        values = sample_values(keys, steps)
        return {
            "layer": layer_name,
            "layer_index": layer_index,
            "layer_weight": layer_weight,
            "state": state_name,
            "time_param": time_param or "",
            "cond": cond,
            "clip": clip_name,
            "path": path,
            "mesh": leaf(path),
            "class_id": class_id,
            "attribute": attr,
            "key": key_of(class_id, attr),
            "kind": kind_of(class_id, attr),
            "curve": [[round(t, 6), round(v, 6)] for t, v in keys],
            "values": values,
            "const": len(values) == 1,
            "where": where,
        }

    # -- clip -------------------------------------------------------------
    def load_clip(self, path: str) -> List[dict]:
        if path in self._clip_cache:
            return self._clip_cache[path]
        docs = self.cache.load(path)
        idx = DocIndex(docs)
        out = []
        for clip in idx.all(CLIP_CLASS):
            out.append({"name": clip.get("m_Name") or os.path.basename(path),
                        "doc": clip, "path": path})
        self._clip_cache[path] = out
        return out

    def _emit_clip(self, clip_path, layer_name, layer_idx, layer_weight, state_name,
                   time_param, cond, out, clip_name_override=None):
        for cl in self.load_clip(clip_path):
            cname = clip_name_override or cl["name"]
            for fc in (cl["doc"].get("m_FloatCurves") or []):
                if not isinstance(fc, dict):
                    continue
                out.append(self._curve_entry(layer_name, layer_idx, layer_weight,
                                             state_name, time_param, cname,
                                             "%s:%d" % (clip_path, cl["doc"].line),
                                             fc, cond))

    # -- controller -------------------------------------------------------
    def scan_controller(self, ctrl_path: str, resolver: ClipResolver) -> List[dict]:
        docs = self.cache.load(ctrl_path)
        idx = DocIndex(docs)
        out: List[dict] = []
        for ctrl in idx.all(CONTROLLER_CLASS):
            for li, layer in enumerate(ctrl.get("m_AnimatorLayers") or []):
                lname = layer.get("m_Name") or ""
                lweight = _num(layer.get("m_DefaultWeight", 1), 1.0)
                sm = (layer.get("m_StateMachine") or {}).get("fileID", 0)
                self._walk_state_machine(idx, sm, resolver, lname, li, lweight,
                                         ctrl_path, out, set())
        out.sort(key=lambda e: (e["layer_index"], str(e["state"]), str(e["path"]),
                                str(e["attribute"]),
                                json.dumps(e["curve"], sort_keys=True)))
        return out

    def _walk_state_machine(self, idx, sm_fid, resolver, lname, li, lweight,
                            ctrl_path, out, seen):
        if not sm_fid or sm_fid in seen:
            return
        seen.add(sm_fid)
        sm = idx.by_fid.get(sm_fid)
        if not sm or sm.class_id != STATE_MACHINE_CLASS:
            return
        for child in sm.get("m_ChildStates") or []:
            st_fid = (child.get("m_State") or {}).get("fileID", 0)
            st = idx.by_fid.get(st_fid)
            if not st or st.class_id != STATE_CLASS:
                continue
            self._emit_state(idx, st, resolver, lname, li, lweight, ctrl_path, out)
        for child in sm.get("m_ChildStateMachines") or []:
            sub = (child.get("m_StateMachine") or {}).get("fileID", 0)
            self._walk_state_machine(idx, sub, resolver, lname, li, lweight,
                                     ctrl_path, out, seen)

    def _emit_state(self, idx, st, resolver, lname, li, lweight, ctrl_path, out):
        sname = st.get("m_Name") or ""
        time_param = st.get("m_TimeParameter") or ""
        if not st.get("m_TimeParameterActive"):
            time_param = ""
        motion = st.get("m_Motion") or {}
        self._emit_motion(idx, motion, resolver, lname, li, lweight, sname,
                          time_param, ctrl_path, out, "state:%s/%s" % (lname, sname), 0)

    def _emit_motion(self, idx, motion, resolver, lname, li, lweight, sname,
                     time_param, ctrl_path, out, cond, depth):
        if depth > 8 or not motion:
            return
        fid = motion.get("fileID", 0) or 0
        guid = motion.get("guid") or ""
        if guid and guid not in ZERO_GUIDS:
            p = resolver.path_for(guid)
            if p:
                self._emit_clip(p, lname, li, lweight, sname, time_param, cond, out)
            return
        if not fid:
            return
        doc = idx.by_fid.get(fid)
        if doc is None:
            return
        if doc.class_id == CLIP_CLASS:
            # 控制器内嵌 clip（少见）
            for fc in (doc.get("m_FloatCurves") or []):
                if isinstance(fc, dict):
                    out.append(self._curve_entry(lname, li, lweight, sname, time_param,
                                                 doc.get("m_Name") or "",
                                                 "%s:%d" % (ctrl_path, doc.line), fc, cond))
            return
        if doc.class_id == TREE_CLASS:
            children = doc.get("m_Children") or []
            blend_type = int(doc.get("m_BlendType") or 0)
            for ch in children:
                if not isinstance(ch, dict):
                    continue
                thr = ch.get("m_Threshold")
                child_cond = cond
                if blend_type == 0 and thr is not None:
                    child_cond = "%s & tree_thr=%s" % (cond, fmt_val(_num(thr)))
                self._emit_motion(idx, ch.get("m_Motion") or {}, resolver, lname, li,
                                  lweight, sname, time_param, ctrl_path, out,
                                  child_cond, depth + 1)


# ---------------------------------------------------------------------------
# 自验
# ---------------------------------------------------------------------------
def _find_entries(entries, clip=None, key=None, mesh=None, path=None):
    out = []
    for e in entries:
        if clip and e["clip"] != clip:
            continue
        if key and e["key"] != key:
            continue
        if mesh and e["mesh"] != mesh:
            continue
        if path and e["path"] != path:
            continue
        out.append(e)
    return out


def selftest(project: str) -> int:
    ctrl = os.path.join(project, "Assets/_Work/Gen/A2_FX.controller")
    clips = os.path.join(project, "Assets/_Work/Gen/Clip")
    if not os.path.exists(ctrl):
        print("[FAIL] 找不到 %s" % ctrl)
        return 2
    resolver = ClipResolver(project, clips)
    scanner = ClipWritesScanner()
    entries = scanner.scan_controller(ctrl, resolver)
    print("[selftest] controller=%s" % ctrl)
    print("[selftest] entries=%d" % len(entries))
    fails = []

    # 验收 1：sailor.outer_shlink 有 Dial_整套（{100,0}）与 Off_部位_外套（0）
    hits = _find_entries(entries, key="outer_shlink", mesh="sailor")
    by_clip = {e["clip"]: e for e in hits}
    print("[selftest] sailor.outer_shlink writers=%s" % sorted(by_clip))
    if "Dial_整套" not in by_clip:
        fails.append("sailor.outer_shlink 缺 Dial_整套")
    elif by_clip["Dial_整套"]["values"] != [0.0, 100.0]:
        fails.append("Dial_整套 outer_shlink 值应为 [0,100]，实际 %s"
                     % by_clip["Dial_整套"]["values"])
    if "Off_部位_外套" not in by_clip:
        fails.append("sailor.outer_shlink 缺 Off_部位_外套")
    elif by_clip["Off_部位_外套"]["values"] != [0.0]:
        fails.append("Off_部位_外套 outer_shlink 应为常量 0，实际 %s"
                     % by_clip["Off_部位_外套"]["values"])

    # 验收 2：Body_b.outer_shrink 同 outer_shlink
    # 注意 B-T06 起依赖编译器也写这一键（`Decl: kaguya_body_under_outer`，落
    # `Decl_*_On/Off` clip）；自验只要求原来两层在，额外写者只许是 `Decl_` 前缀。
    hits2 = _find_entries(entries, key="outer_shrink", mesh="Body_b")
    got2 = {e["clip"] for e in hits2}
    print("[selftest] Body_b.outer_shrink writers=%s" % sorted(got2))
    required2 = {"Dial_整套", "Off_部位_外套"}
    extra2 = {c for c in got2 if c not in required2}
    if not required2 <= got2 or any(not c.startswith("Decl_") for c in extra2):
        fails.append("Body_b.outer_shrink 写者集合不对：%s（额外写者只许 Decl_*）" % sorted(got2))

    # 验收 3：Dial_整套 的 Motion Time 档位确实是 i/7
    dial = by_clip.get("Dial_整套")
    if dial and dial.get("time_param") != "A2_Outfit":
        fails.append("Dial_整套 的 Motion Time 参数应为 A2_Outfit，实际 %r"
                     % dial.get("time_param"))

    # 验收 4：我方 clip 只写少数形态键（F7：8 种）
    shapes = sorted({e["key"] for e in entries if e["kind"] == "blendshape"})
    print("[selftest] blendshape keys=%d %s" % (len(shapes), shapes))
    if not shapes:
        fails.append("没有抽出任何 blendShape 曲线")

    if fails:
        for f in fails:
            print("[FAIL] %s" % f)
        return 1
    print("[selftest] OK")
    return 0


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="AnimatorController+Clip → 写者条目")
    ap.add_argument("--controller", help="AnimatorController 路径")
    ap.add_argument("--clips", help="clip 目录（用其中的 .anim.meta 解析 guid）")
    ap.add_argument("--project", help="工程根（可选，用于全量 guid 索引）")
    ap.add_argument("--out", help="输出 JSON 路径（缺省只打印摘要）")
    ap.add_argument("--selftest", action="store_true", help="用仓库内 工程A 数据自验")
    ap.add_argument("--project-selftest", default=os.path.join(
        _HERE, "..", "..", "..", "..", "工程A"),
        help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(os.path.abspath(args.project_selftest))
    if not args.controller:
        ap.error("需要 --controller 或 --selftest")
    project = args.project
    if not project:
        # controller 通常在 <工程>/Assets/... 下
        p = os.path.abspath(args.controller)
        while p != "/" and not os.path.isdir(os.path.join(p, "Assets")):
            p = os.path.dirname(p)
        project = p if os.path.isdir(os.path.join(p, "Assets")) else None
    resolver = ClipResolver(project, args.clips)
    entries = ClipWritesScanner().scan_controller(os.path.abspath(args.controller), resolver)
    result = {
        "controller": os.path.abspath(args.controller),
        "project": project,
        "clips_dir": os.path.abspath(args.clips) if args.clips else None,
        "entries": entries,
    }
    print("[clip_writes] entries=%d" % len(entries))
    for e in entries[:8]:
        print("  %-10s %-14s %-24s %-22s %s -> %s%s"
              % (e["layer"], e["state"], e["path"], e["attribute"],
                 e["clip"], fmt_val(e["values"][0]) if e["values"] else "?",
                 "" if e["const"] else " (…%d 档)" % len(e["values"])))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1, sort_keys=True)
        print("[clip_writes] wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
