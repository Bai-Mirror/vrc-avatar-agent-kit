# -*- coding: utf-8 -*-
"""pose_plan.py — 姿势×状态计划（T-29 / 04 第一期开工清单 §3b；原理 03 §8.4）。
【项目沉淀】通用工具
适用素体：无关
相关素材：decl.json + pose_library.json + inventory.json + pb.json
工具链　：Python 3（离线）
可复用性：★★ 审查工具链的一环
用途　　：姿势×状态计划：按 03 §8.4 生成 T1 姿势请求批，并出 pose_plan.json 与被预算截断项。


职责（离线，只读工程；不启动 Unity）
------------------------------------
读 `<工程>/_感知/decl.json`、`_感知/out/pose_library.json`（T-26）、
`_感知/out/inventory.json`（T-05）、`_感知/out/pb.json`（T-30）、
`_感知/out/pose_timing.json`（T-27 实测；缺席退默认值），
按 03 §8.4 生成 T1 姿势请求批 `request_pose_<n>.json`，并写
`pose_plan.json`（每部件表）与 `pose_plan_skipped.json`（被预算截断项）。

它**不测量**，只决定「哪些 (状态, 姿势, PB 模式) 帧要跑、量哪些件、花多少秒、分几批」。

核心规则（03 §8.4）
------------------
1. 只配 `moved_regions(pose) ∩ covers(part) ≠ ∅` 的 (部件, 姿势)；声明的
   `parts[].pose_scope.include` 里的 pose 无条件加入（如 工程A `kaguya.sailor`
   强制 `proxy_sit`，剪枝会把它剪掉）。
2. 计量单位＝帧＝(状态, 姿势, PB 模式)；一帧量该状态下全部可见件；按状态为主序（I3）。
3. 每部件按「写它覆盖件/覆盖区域的写者条件 ∪ 同区域其它部件可见性」的**等价类**挑状态，
   每个等价类至少一个状态；全局再用贪心集合覆盖取尽量少的代表状态。
4. 两趟：趟 1＝库 A ＋ 库 B@100%（含 6 组合）＋ 库 C 极值帧；
   趟 2＝库 B@{25,50,75}，只对趟 1 有斑块、或深度/面积在阈值 2× 以内的 (部件, 关节)。
5. `both` 只给有 PB 的部件（`pb.json.parts[part].has_pb` 或声明 `parts[].pb`）；
   其余默认 `rigid`。缺 PB 信息时**不猜**：记 warning，按 rigid 跑。
6. 按秒预算：每帧成本＝稳定 ＋ settle（该帧含 settle 时）＋ 烘焙×该帧可见件数；
   优先级 库 A(0) ＞ 库 B@100%(1) ＞ 库 C(2) ＞ 趟 2 库 B 低档(3)；
   `--total-budget-min` > 0 时按优先级从低到高截断；每批墙钟 ≤ `--budget-min`（默认 20，R6）。

用法
----
    python3 perception/pose_plan.py --selftest
    python3 perception/pose_plan.py --project <工程根> [--out <目录>]
        [--pose-timing <pose_timing.json>] [--budget-min 20] [--total-budget-min 0]
        [--pass1 <poke_patches.json>]

`--pass1`：T-28b/T-31 的斑块结果，驱动趟 2。接受
`{"hits":[{"part":..,"joint":..,"side":"L|R|null"}...]}`，也接受
`poke_patches.json` 风格的补丁列表（用 `part`＋`joint`/`region` 识别）。

坐标与部位词汇
--------------
`pose_library.json` 的 `moved_regions` 用肌肉组部位名（`thigh/knee/upperarm/...`，
`muscles.MUSCLE_REGIONS`），声明 `covers` 用 Unity 人形骨名（`LeftUpperLeg/Hips/...`）。
两者用 `COVER_TO_REGIONS` 桥接：`Hips` 同时算髋（`thigh`）与腰（`spine`）——
坐姿髋前屈牵动裤腰/内裤，否则 `MMN.pants`（只 covers Hips/Spine）会被漏配坐姿。
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import decl_validate as dv          # noqa: E402
import rules_universal as ru        # noqa: E402
from muscles import JOINT_SCANS     # noqa: E402

SCHEMA = "pose_plan/1"

# T-27 实测缺席时的默认每帧耗时（04 T-29 验收用的假值也是这三个键）
DEFAULT_TIMING = {"stabilize_s": 0.2, "settle_s": 5.0, "bake_s_per_part": 0.7}
TIMING_KEYS = ("stabilize_s", "settle_s", "bake_s_per_part")

BATCH_BUDGET_DEFAULT_MIN = 20.0     # R6

# 趟 2 触发：趟 1 有斑块，或深度/面积在阈值 2× 以内（03 §8.4）
PASS2_TRIGGER_FACTOR = 2.0

# 覆盖骨名 → moved_regions 部位名。手性展开在 `_expand_cover`。
COVER_TO_REGIONS: Dict[str, List[str]] = {
    "Hips": ["thigh", "spine"],
    "Spine": ["spine"],
    "Chest": ["chest"],
    "UpperChest": ["upperchest"],
    "Neck": ["neck"],
    "Head": ["head"],
    "LeftUpperLeg": ["thigh"], "RightUpperLeg": ["thigh"],
    "LeftLowerLeg": ["knee"], "RightLowerLeg": ["knee"],
    "LeftFoot": ["ankle"], "RightFoot": ["ankle"],
    "LeftToes": ["toe"], "RightToes": ["toe"],
    "LeftShoulder": ["shoulder"], "RightShoulder": ["shoulder"],
    "LeftUpperArm": ["upperarm"], "RightUpperArm": ["upperarm"],
    "LeftLowerArm": ["elbow"], "RightLowerArm": ["elbow"],
    "LeftHand": ["hand", "finger"], "RightHand": ["hand", "finger"],
    "LeftEye": ["eye"], "RightEye": ["eye"], "Jaw": ["jaw"],
}

# region（moved_regions 词汇）→ 库 B 关节 id（趟 2 从补丁 region 反推关节时用）
REGION_TO_JOINTS: Dict[str, List[str]] = {}
for _js in JOINT_SCANS:
    REGION_TO_JOINTS.setdefault(_js["region"], []).append(_js["id"])

# 姿势分类的优先级：数值越小越先跑、越后砍
PRIORITY_A = 0
PRIORITY_B100 = 1
PRIORITY_C = 2
PRIORITY_B_LOW = 3

MAX_PART_CANDIDATES = 4096           # 单部件候选状态枚举上限（超出逐级降维）
MAX_EVAL_STATES = 60000              # 全局可见性求值上限（安全阀）


# ---------------------------------------------------------------------------
# 通用小件
# ---------------------------------------------------------------------------
def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def _truthy(v) -> bool:
    return ru._truthy(v)  # noqa: SLF001（同一工具的公共语义）


def _rel(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def cover_regions(covers: Sequence[str]) -> List[str]:
    """声明 covers（人形骨名）→ moved_regions 词汇的部位集合（排序去重）。"""
    out = set()
    for c in covers or []:
        rs = COVER_TO_REGIONS.get(c)
        if rs is None:
            # 未登记：退小写本身（仍可与同名 moved_regions 相交，但不静默丢弃）
            out.add(str(c).lower())
        else:
            out.update(rs)
    return sorted(out)


# ---------------------------------------------------------------------------
# 姿势分类
# ---------------------------------------------------------------------------
def classify_pose(entry: dict) -> dict:
    """给 pose_library 的一条目补 `pass_no / priority / joint / side / dose / combo`。"""
    e = dict(entry)
    g = e.get("group")
    tags = [str(t) for t in (e.get("tags") or [])]
    dose = None
    for t in tags:
        if t.startswith("dose_"):
            try:
                dose = int(t[len("dose_"):])
            except ValueError:
                pass
    if g == "A":
        e.update(pass_no=1, priority=PRIORITY_A, kind="A", joint=None, side=None,
                 dose=None, combo=False)
        return e
    if g == "B":
        pid = str(e.get("id") or "")
        if pid.startswith("B_combo_"):
            e.update(pass_no=1, priority=PRIORITY_B100, kind="B",
                     joint=pid[len("B_"):], side=None, dose=dose or 100, combo=True)
            return e
        parts = pid.split("_")            # B_<joint>_<L|R>_<dose>
        side = parts[-2] if len(parts) >= 2 and parts[-2] in ("L", "R") else None
        joint = "_".join(parts[1:-2]) if len(parts) >= 4 else None
        if joint is None:                 # 兜底：tags 里第一个关节名
            joint = next((t for t in tags if t in {s["id"] for s in JOINT_SCANS}), None)
        if dose == 100:
            e.update(pass_no=1, priority=PRIORITY_B100, kind="B", joint=joint,
                     side=side, dose=100, combo=False)
        else:
            e.update(pass_no=2, priority=PRIORITY_B_LOW, kind="B", joint=joint,
                     side=side, dose=dose, combo=False)
        return e
    # 库 C 真动作极值帧
    e.update(pass_no=1, priority=PRIORITY_C, kind="C", joint=None, side=None,
             dose=None, combo=False)
    return e


def load_poses(lib: dict) -> List[dict]:
    out: List[dict] = []
    libs = (lib or {}).get("libraries") or {}
    for g in ("A", "B", "C"):
        for e in libs.get(g) or []:
            out.append(classify_pose(e))
    return out


# ---------------------------------------------------------------------------
# 部件 / 菜单维度
# ---------------------------------------------------------------------------
def build_parts(decl: dict) -> List[dict]:
    out = []
    for p in decl.get("parts") or []:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        covers = [c for c in (p.get("covers") or []) if isinstance(c, str)]
        scope = p.get("pose_scope") if isinstance(p.get("pose_scope"), dict) else {}
        out.append({
            "id": p["id"],
            "covers": covers,
            "regions": cover_regions(covers),
            "kind": p.get("kind"),
            "outfit": p.get("outfit"),
            "slot": p.get("slot"),
            "toggle": p.get("toggle") if isinstance(p.get("toggle"), dict) else None,
            "include": [x for x in (scope.get("include") or []) if isinstance(x, str)],
            "exclude": [x for x in (scope.get("exclude") or []) if isinstance(x, str)],
            "decl_pb": p.get("pb") if p.get("pb") in ("rigid", "settle", "both") else None,
            "raw": p,
        })
    return out


def _dim_key(kind: str, name: str) -> Tuple[str, str]:
    return (kind, name)


def _dim_default(c: dict) -> float:
    d = c.get("default", 0)
    t = c.get("type")
    labels = c.get("labels") or []
    if t in ("int", "float_slots") and labels:
        try:
            idx = int(d)
        except (TypeError, ValueError):
            return float(d) if isinstance(d, (int, float)) else 0.0
        if 0 <= idx < len(labels):
            return idx / float(len(labels))
        return float(d) if isinstance(d, (int, float)) else 0.0
    if isinstance(d, bool):
        return 1.0 if d else 0.0
    try:
        return float(d)
    except (TypeError, ValueError):
        return 0.0


def menu_dims(decl: dict) -> Dict[Tuple[str, str], dict]:
    """菜单 → {维度键: {param, type, labels, values, default}}。

    维度键：`("outfit","")`、`("slot",<slot名>)`、`("ctl",<控件名>)`。
    `values` 是参数原值（bool→[0,1]，float_slots→[i/n]）。
    """
    dims: Dict[Tuple[str, str], dict] = {}
    menu = decl.get("menu") or {}

    def add(kind: str, name: str, c: dict) -> None:
        if not isinstance(c, dict):
            return
        labels = [x for x in (c.get("labels") or []) if isinstance(x, str)]
        t = c.get("type")
        if t == "bool" or not labels:
            values = [0.0, 1.0]
        else:
            n = len(labels)
            values = [i / float(n) for i in range(n)]
        dims[_dim_key(kind, name)] = {
            "param": c.get("param"), "type": t, "labels": labels,
            "values": values, "default": _dim_default(c),
        }

    for name, c in (menu.get("slots") or {}).items():
        add("slot", name, c)
    for name, c in (menu.get("controls") or {}).items():
        add("ctl", name, c)
    outfit = menu.get("outfit") or {}
    if outfit:
        add("outfit", "", outfit)
    return dims


def make_state(decl: dict, dims: Dict[Tuple[str, str], dict],
               assign: Dict[Tuple[str, str], float]) -> dv.EvalState:
    st = dv.EvalState()
    menu = decl.get("menu") or {}
    for name, c in (menu.get("slots") or {}).items():
        key = _dim_key("slot", name)
        raw = assign.get(key, dims.get(key, {}).get("default", 0.0))
        bit = 1 if _truthy(raw) else 0
        st.slots[name] = bit
        if c.get("param"):
            st.params[c["param"]] = bit
    for name, c in (menu.get("controls") or {}).items():
        key = _dim_key("ctl", name)
        raw = assign.get(key, dims.get(key, {}).get("default", 0.0))
        if c.get("param"):
            st.params[c["param"]] = raw
        t = c.get("type")
        labels = [x for x in (c.get("labels") or []) if isinstance(x, str)]
        if t == "bool":
            st.ctl[name] = {"kind": "bool", "bit": 1 if _truthy(raw) else 0}
        elif t in ("int", "float_slots") and labels:
            idx = ru.slot_index(raw, labels, t)
            st.ctl[name] = {"kind": t, "label": labels[idx], "slot": idx, "bit": idx}
        else:
            st.ctl[name] = {"kind": "float", "raw": raw}
    outfit = menu.get("outfit") or {}
    if outfit:
        key = _dim_key("outfit", "")
        raw = assign.get(key, dims.get(key, {}).get("default", 0.0))
        if outfit.get("param"):
            st.params[outfit["param"]] = raw
        labels = [x for x in (outfit.get("labels") or []) if isinstance(x, str)]
        if labels:
            st.outfit_label = labels[ru.slot_index(raw, labels,
                                                   outfit.get("type") or "float_slots")]
    for ax in (decl.get("body_axes") or {}):
        st.body[ax] = 0.0
    return st


def _param_sig(st: dv.EvalState) -> tuple:
    ctl = []
    for k, v in sorted(st.ctl.items()):
        ctl.append((k, v.get("label", v.get("bit", v.get("raw")))))
    return (st.outfit_label, tuple(sorted(st.slots.items())), tuple(ctl))


def _assign_sig(assign: Dict[Tuple[str, str], float]) -> tuple:
    return tuple(sorted((k[0], k[1], round(float(v), 6)) for k, v in assign.items()))


# ---------------------------------------------------------------------------
# 条件引用（写者条件 → 菜单维度）
# ---------------------------------------------------------------------------
def _walk_cond_refs(ast, acc: dict) -> None:
    if not ast:
        return
    tag = ast[0]
    if tag == "vis":
        acc["vis"].add(ast[1])
    elif tag == "chain":
        for r in ast[1]:
            if isinstance(r, str):
                acc["vis"].add(r)
    elif tag == "ctl":
        acc["ctl"].add(ast[1])
    elif tag == "slot":
        acc["slot"].add(ast[1])
    elif tag == "outfit":
        acc["outfit"] = True
    elif tag == "param":
        acc["param"].add(ast[1])
    elif tag in ("and", "or"):
        for x in ast[1]:
            _walk_cond_refs(x, acc)
    elif tag == "not":
        _walk_cond_refs(ast[1], acc)


def cond_refs(ast) -> dict:
    acc = {"vis": set(), "ctl": set(), "slot": set(), "param": set(), "outfit": False}
    _walk_cond_refs(ast, acc)
    return acc


def _parse_dep_ast(dep: dict):
    when = dep.get("when")
    if when is None:
        return ("true",)
    try:
        return dv.parse_cond(when)
    except Exception:
        return ("false",)


def _dep_output(dep: dict, ast, st, E, pbk) -> object:
    """等价于 `ru.eval_decl_dep`，但复用预解析 AST（省去逐状态重解析 72 条条件）。"""
    else_out = dep.get("else")
    if else_out is None:
        else_out = "dont_care" if dep.get("origin") == "fragment" else "baseline"
    try:
        if not dv.eval_cond(ast, st, E, pbk):
            return else_out
    except Exception:
        return else_out
    if "expect_by_leader" in dep:
        try:
            return ru.eval_decl_dep(dep, st, E, pbk)
        except Exception:
            return else_out
    if "cases" in dep:
        for c in dep.get("cases") or []:
            if not isinstance(c, dict):
                continue
            try:
                cast = dv.parse_cond(c.get("when"))
            except Exception:
                continue
            if dv.eval_cond(cast, st, E, pbk):
                return c.get("expect", else_out)
        return else_out
    if "expect" in dep:
        return dep["expect"]
    return else_out


# ---------------------------------------------------------------------------
# 状态等价类 + 贪心集合覆盖
# ---------------------------------------------------------------------------
class StatePlanner:
    def __init__(self, decl: dict, parts: List[dict], active_ids=None, log=print):
        self.decl = decl
        self.parts = parts
        # 只给「至少配到一个姿势」的件规划状态：没配姿势的件不产生帧，等价类无意义
        self.active_ids = set(active_ids) if active_ids is not None else {p["id"] for p in parts}
        self.log = log
        self.warnings: List[str] = []
        self.dims = menu_dims(decl)
        self.parts_by_kind: Dict[str, List[str]] = {}
        for p in parts:
            if p.get("kind"):
                self.parts_by_kind.setdefault(p["kind"], []).append(p["id"])
        self.parts_by_id = {p["id"]: p for p in parts}
        self.dep_asts = [(d, _parse_dep_ast(d)) for d in (decl.get("deps") or [])
                         if not d.get("superseded_by")]
        self._vis_cache: Dict[tuple, dict] = {}
        self._eval_count = 0
        self.region_parts: Dict[str, List[str]] = {}
        for p in parts:
            for r in p["regions"]:
                self.region_parts.setdefault(r, []).append(p["id"])
        self._dep_vis_refs = [cond_refs(ast) for _, ast in self.dep_asts]

    # -- 可见性 ----------------------------------------------------------
    def expected_visibility(self, st: dv.EvalState) -> Dict[str, bool]:
        sig = _param_sig(st)
        hit = self._vis_cache.get(sig)
        if hit is not None:
            return hit
        self._eval_count += 1
        E = {p["id"]: ru._base_visible(p["raw"], st) for p in self.parts}  # noqa: SLF001
        for (dep, ast) in self.dep_asts:
            tgt = dep.get("target")
            if not isinstance(tgt, dict) or "part" not in tgt:
                continue
            if any(k in tgt for k in ("key", "keys", "submesh")):
                continue
            pid = tgt["part"]
            if pid not in E:
                continue
            out = _dep_output(dep, ast, st, E, self.parts_by_kind)
            if isinstance(out, dict):
                if out.get("hidden") is True:
                    E[pid] = False
                elif out.get("shown") is True:
                    E[pid] = True
        self._vis_cache[sig] = E
        return E

    # -- 每部件相关维度 --------------------------------------------------
    def _visibility_dims(self, part: dict) -> set:
        keys = set()
        if part.get("outfit"):
            keys.add(_dim_key("outfit", ""))
        if part.get("slot") and _dim_key("slot", part["slot"]) in self.dims:
            keys.add(_dim_key("slot", part["slot"]))
        tog = part.get("toggle") or {}
        if tog.get("control") and _dim_key("ctl", tog["control"]) in self.dims:
            keys.add(_dim_key("ctl", tog["control"]))
        return keys

    def same_region(self, part: dict) -> List[str]:
        out = set()
        for r in part["regions"]:
            out.update(self.region_parts.get(r, []))
        out.discard(part["id"])
        return sorted(out)

    def relevant_dep_ids(self, part: dict) -> List[str]:
        """写者条件：目标指本件、或条件里 vis() 提到本件/同区域件。"""
        same = set(self.same_region(part)) | {part["id"]}
        out = []
        for (dep, _ast), refs in zip(self.dep_asts, self._dep_vis_refs):
            tgt = dep.get("target")
            tpart = tgt.get("part") if isinstance(tgt, dict) else None
            if tpart == part["id"]:
                out.append(dep.get("id"))
                continue
            if refs["vis"] & same:
                out.append(dep.get("id"))
        return sorted(str(x) for x in out if x)

    def _assignments_for(self, keys: Iterable[Tuple[str, str]]) -> List[dict]:
        keys = sorted(keys, key=lambda k: (k[0], k[1]))
        vals = [self.dims[k]["values"] for k in keys if k in self.dims]
        keys = [k for k in keys if k in self.dims]
        n = 1
        for v in vals:
            n *= max(1, len(v))
        if n > MAX_PART_CANDIDATES:
            return []
        out = []
        for combo in itertools.product(*vals):
            out.append(dict(zip(keys, combo)))
        return out

    def candidate_states_for(self, part: dict) -> List[dict]:
        """本件候选状态赋值；超出上限逐级降维（去写者维 → 只留自身维）。"""
        base = self._visibility_dims(part)
        same = set()
        for opid in self.same_region(part):
            same |= self._visibility_dims(self.parts_by_id[opid])
        depids = set(self.relevant_dep_ids(part))
        depdims = set()
        for dep, ast in self.dep_asts:
            if dep.get("id") in depids:
                refs = cond_refs(ast)
                for n in refs["slot"]:
                    if _dim_key("slot", n) in self.dims:
                        depdims.add(_dim_key("slot", n))
                for n in refs["ctl"]:
                    if _dim_key("ctl", n) in self.dims:
                        depdims.add(_dim_key("ctl", n))
                if refs["outfit"]:
                    depdims.add(_dim_key("outfit", ""))
        for label, keys in (("full", base | same | depdims),
                            ("no-writers", base | same),
                            ("own-only", base)):
            cands = self._assignments_for(keys)
            if cands:
                if label != "full":
                    self.warnings.append("部件 %s 候选维度过多，退到 %s" % (part["id"], label))
                return cands
        return [{}]

    # -- 主流程 ----------------------------------------------------------
    def build(self) -> dict:
        requirements = []            # [{part, class_key, sigs:set}]
        assignments: Dict[tuple, dict] = {}
        for part in self.parts:
            if part["id"] not in self.active_ids:
                continue
            cands = self.candidate_states_for(part)
            classes: Dict[tuple, set] = {}
            for a in cands:
                st = make_state(self.decl, self.dims, a)
                E = self.expected_visibility(st)
                if not E.get(part["id"]):
                    continue
                key = self._equiv_key(part, st, E)
                sig = _assign_sig(a)
                assignments.setdefault(sig, a)
                classes.setdefault(key, set()).add(sig)
            if not classes:
                # 所有候选态下件都不可见：至少登记默认态，避免静默丢件
                st = make_state(self.decl, self.dims, {})
                E = self.expected_visibility(st)
                if E.get(part["id"]):
                    classes[("visible", ())] = {_assign_sig({})}
                else:
                    self.warnings.append("部件 %s 在候选状态里始终不可见（跳过）" % part["id"])
                    continue
            for key, sigs in classes.items():
                requirements.append({"part": part["id"], "class": key, "sigs": sigs,
                                     "covers": list(part["covers"]),
                                     "regions": list(part["regions"])})

        chosen_sigs = self._greedy_cover(requirements)
        chosen_set = set(chosen_sigs)
        self._sig_to_sid = {sig: "s%02d" % i for i, sig in enumerate(chosen_sigs)}
        planned: Dict[str, set] = {p["id"]: set() for p in self.parts}
        for req in requirements:
            hit = req["sigs"] & chosen_set
            if hit:
                planned[req["part"]].update(self._sig_to_sid[s] for s in hit)
        self.planned_states = {k: sorted(v) for k, v in planned.items()}
        state_list = []
        for i, sig in enumerate(chosen_sigs):
            a = assignments[sig]
            st = make_state(self.decl, self.dims, a)
            E = self.expected_visibility(st)
            state_list.append({
                "id": "s%02d" % i,
                "assignment": {("%s.%s" % k): v for k, v in a.items()},
                "params_applied": dict(sorted(st.params.items())),
                "visible_parts": sorted(p["id"] for p in self.parts if E.get(p["id"])),
            })
        self.state_list = state_list
        self._requirements = requirements
        self._eval_count_note = self._eval_count
        return {
            "states": {s["id"]: s for s in state_list},
            "requirements": requirements,
            "n_eval": self._eval_count,
        }

    def _equiv_key(self, part: dict, st, E) -> tuple:
        same = self.same_region(part)
        vis = tuple(sorted(p for p in same if E.get(p)))
        depids = set(self.relevant_dep_ids(part))
        active = []
        for dep, ast in self.dep_asts:
            if dep.get("id") not in depids:
                continue
            out = _dep_output(dep, ast, st, E, self.parts_by_kind)
            if isinstance(out, dict) or (isinstance(out, str) and out not in
                                         ("dont_care", "baseline")):
                active.append(str(dep.get("id")))
        return (vis, tuple(sorted(active)))

    @staticmethod
    def _greedy_cover(requirements: List[dict]) -> List[tuple]:
        """最少状态覆盖所有 (部件, 等价类)；平局取签名最小者，保证确定性。"""
        uncovered = list(range(len(requirements)))
        chosen: List[tuple] = []
        while uncovered:
            score: Dict[tuple, int] = {}
            for ri in uncovered:
                for sig in requirements[ri]["sigs"]:
                    score[sig] = score.get(sig, 0) + 1
            if not score:
                break
            best = max(sorted(score), key=lambda s: (score[s], tuple(reversed(s))))
            chosen.append(best)
            uncovered = [ri for ri in uncovered
                         if best not in requirements[ri]["sigs"]]
        return chosen


# ---------------------------------------------------------------------------
# 配对 / 两趟
# ---------------------------------------------------------------------------
def resolve_pb(part: dict, pb_parts: dict) -> str:
    if part.get("decl_pb"):
        return part["decl_pb"]
    info = (pb_parts or {}).get(part["id"])
    if isinstance(info, dict) and info.get("has_pb"):
        return "both"
    return "rigid"


def pose_hits(pose: dict, regions: set) -> bool:
    return bool(regions & set(pose.get("moved_regions") or []))


def pair_parts(parts: List[dict], poses: List[dict]) -> dict:
    """返回 {part_id: {"pass1": [pose_id...], "pass2_candidates": [pose_id...]}}。

    `pass2_candidates` 是**全部**低档扫掠；真正趟 2 由趟 1 结果（--pass1）筛。
    """
    by_id = {p["id"]: p for p in parts}
    out = {p["id"]: {"pass1": [], "pass2_candidates": []} for p in parts}
    for pose in poses:
        moved = set(pose.get("moved_regions") or [])
        for p in parts:
            hit = bool(moved & set(p["regions"]))
            if pose["pass_no"] == 1:
                if hit:
                    out[p["id"]]["pass1"].append(pose["id"])
            elif hit:
                out[p["id"]]["pass2_candidates"].append(pose["id"])
    # pose_scope.include 无条件加入（剪枝会剪掉 sit 这类只动髋膝的姿势）
    pose_ids = {pose["id"] for pose in poses}
    for p in parts:
        inc = [x for x in p["include"] if x in pose_ids]
        exc = set(p["exclude"])
        for pid in inc:
            if pid not in out[p["id"]]["pass1"]:
                out[p["id"]]["pass1"].append(pid)
        out[p["id"]]["pass1"] = sorted(set(out[p["id"]]["pass1"]) - exc)
        out[p["id"]]["pass2_candidates"] = sorted(set(out[p["id"]]["pass2_candidates"]) - exc)
    return out


def normalize_pass1(data) -> List[dict]:
    """--pass1 输入 → [{"part","joint","side"}]（只留命中或 2× 阈值内的）。"""
    hits: List[dict] = []
    items = []
    if isinstance(data, dict):
        if isinstance(data.get("hits"), list):
            items = data["hits"]
        elif isinstance(data.get("patches"), list):
            items = data["patches"]
        else:
            items = []
    elif isinstance(data, list):
        items = data
    for it in items:
        if not isinstance(it, dict):
            continue
        part = it.get("part")
        joints = []
        if it.get("joint"):
            joints = [it["joint"]]
        else:
            region = it.get("region") or it.get("子部位")
            if region:
                joints = REGION_TO_JOINTS.get(str(region), [])
        if it.get("near_threshold") is False and it.get("pose_induced") is False:
            continue
        for j in joints:
            hits.append({"part": part, "joint": j, "side": it.get("side")})
    return hits


def select_pass2(parts: List[dict], poses: List[dict], pairs: dict,
                 pass1_hits: List[dict], log=print) -> Dict[str, List[str]]:
    """趟 2 由趟 1 驱动：只保留命中的 (部件, 关节)。"""
    by_id = {p["id"]: p for p in parts}
    want: Dict[str, set] = {}
    for h in pass1_hits:
        pid, joint, side = h.get("part"), h.get("joint"), h.get("side")
        if pid not in by_id or not joint:
            continue
        want.setdefault(pid, set()).add((joint, side))
    if not want:
        return {}
    out: Dict[str, List[str]] = {}
    for pid, specs in want.items():
        cand = set(pairs[pid]["pass2_candidates"])
        sel = []
        for pose in poses:
            if pose["id"] not in cand:
                continue
            ok = False
            for joint, side in specs:
                if pose.get("joint") == joint and (side in (None, pose.get("side"))):
                    ok = True
            if ok:
                sel.append(pose["id"])
        if sel:
            out[pid] = sorted(sel)
    return out


# ---------------------------------------------------------------------------
# 帧 / 预算 / 分批
# ---------------------------------------------------------------------------
def frame_cost(parts: Sequence[str], mode: str, timing: dict) -> float:
    """单帧成本＝稳定 ＋（该帧为 settle 时的）settle ＋ 烘焙×该帧可见件数。"""
    cost = float(timing["stabilize_s"])
    if mode == "settle":
        cost += float(timing["settle_s"])
    cost += float(timing["bake_s_per_part"]) * len(parts)
    return cost


def build_frames(states: Dict[str, dict], parts: List[dict], poses: List[dict],
                 pairs: dict, pass2: Dict[str, List[str]], pb_parts: dict,
                 timing: dict, log=print) -> List[dict]:
    by_id = {p["id"]: p for p in parts}
    pose_by_id = {p["id"]: p for p in poses}
    pb_modes = {p["id"]: resolve_pb(p, pb_parts) for p in parts}
    frames: List[dict] = []
    for sid in sorted(states):
        st = states[sid]
        vis = [pid for pid in st["visible_parts"] if pid in by_id]
        for pose in poses:
            pid = pose["id"]
            frame_parts = []
            for part_id in vis:
                pr = pairs[part_id]
                if pid in pr["pass1"] or pid in pass2.get(part_id, []):
                    frame_parts.append(part_id)
            if not frame_parts:
                continue
            modes = {p: pb_modes[p] for p in frame_parts}
            emit_rigid = any(m in ("rigid", "both") for m in modes.values())
            emit_settle = any(m in ("settle", "both") for m in modes.values())
            for mode, emit in (("rigid", emit_rigid), ("settle", emit_settle)):
                if not emit:
                    continue
                mode_parts = [p for p in frame_parts
                              if pb_modes[p] in (mode, "both")]
                if not mode_parts:
                    continue
                frames.append({
                    "state": sid,
                    "pose": pid,
                    "pb": mode,
                    "parts": mode_parts,
                    "pass": pose["pass_no"],
                    "priority": pose["priority"],
                    "kind": pose["kind"],
                    "joint": pose.get("joint"),
                    "additive": bool(pose.get("additive")),
                    "builtin_params": pose.get("builtin_params") or {},
                    "est_s": round(frame_cost(mode_parts, mode, timing), 4),
                })
    frames.sort(key=lambda f: (f["priority"], f["state"], f["pose"], f["pb"]))
    return frames


def truncate(frames: List[dict], total_budget_s: float) -> Tuple[List[dict], List[dict]]:
    """按优先级从低到高截断（先砍趟 2 低档，再库 C，再 B@100%，最后库 A）。"""
    if total_budget_s <= 0:
        return frames, []
    kept, skipped, acc = [], [], 0.0
    for f in sorted(frames, key=lambda x: (x["priority"], x["state"], x["pose"], x["pb"])):
        if acc + f["est_s"] <= total_budget_s + 1e-9:
            kept.append(f)
            acc += f["est_s"]
        else:
            skipped.append(f)
    kept.sort(key=lambda f: (f["priority"], f["state"], f["pose"], f["pb"]))
    return kept, skipped


def batch_frames(frames: List[dict], batch_budget_s: float) -> List[List[dict]]:
    batches: List[List[dict]] = []
    cur: List[dict] = []
    acc = 0.0
    for f in frames:
        if cur and acc + f["est_s"] > batch_budget_s + 1e-9:
            batches.append(cur)
            cur, acc = [], 0.0
        cur.append(f)
        acc += f["est_s"]
    if cur:
        batches.append(cur)
    return batches


# ---------------------------------------------------------------------------
# 输入装配
# ---------------------------------------------------------------------------
def load_timing(path: Optional[str], log=print) -> dict:
    timing = dict(DEFAULT_TIMING)
    if not path or not os.path.isfile(path):
        log("[warn] 无 pose_timing.json（T-27 未跑），用默认 %s" % DEFAULT_TIMING)
        return timing
    data = load_json(path)
    src = None
    if isinstance(data, dict):
        src = data
        for k in ("timing", "summary", "defaults"):
            if isinstance(data.get(k), dict):
                src = data[k]
                break
    got = {}
    for k in TIMING_KEYS:
        for cand in (k, k.replace("_per_part", ""), k.replace("bake_s_per_part",
                                                              "bake_per_part_s")):
            if isinstance(src, dict) and isinstance(src.get(cand), (int, float)):
                got[k] = float(src[cand])
                break
    timing.update(got)
    missing = [k for k in TIMING_KEYS if k not in got]
    if missing:
        log("[warn] pose_timing.json 缺 %s，用默认值" % ",".join(missing))
    return timing


def plan(project: str, decl_path: str, pose_lib_path: str, inventory_path: str,
         pb_path: str, timing_path: Optional[str], pass1_path: Optional[str] = None,
         batch_budget_s: float = BATCH_BUDGET_DEFAULT_MIN * 60.0,
         total_budget_s: float = 0.0, log=print) -> dict:
    warnings: List[str] = []
    decl = load_json(decl_path)
    pose_lib = load_json(pose_lib_path)
    inv = load_json(inventory_path) if os.path.isfile(inventory_path) else {}
    pb = load_json(pb_path) if os.path.isfile(pb_path) else {}
    timing = load_timing(timing_path, log)

    parts = build_parts(decl)
    poses = load_poses(pose_lib)
    pairs = pair_parts(parts, poses)
    pb_parts = (pb or {}).get("parts") or {}
    # pb.json 对 工程A 因「活跃头像根」判定为空——不猜，明确报出
    if not pb_parts:
        warnings.append("pb.json 无 parts 映射（T-30 可能跳过了非活跃头像根）："
                        "所有件按 rigid 计，`both` 只认声明 parts[].pb")
    n_a = sum(1 for p in poses if p["kind"] == "A")
    if n_a > 60:
        warnings.append("库 A 实际 %d 条（T-26 把 SDK 全部 79 个 proxy 都收进 A），"
                        "远多于 03 §8.1 的「≈33 条」；全量趟 1 远超 20 min/批，"
                        "须靠 --total-budget-min 截断（见 counts）" % n_a)

    sp = StatePlanner(decl, parts,
                      active_ids=[p["id"] for p in parts
                                  if pairs[p["id"]]["pass1"]
                                  or pairs[p["id"]]["pass2_candidates"]],
                      log=log)
    sp.build()
    states = sp.state_list
    states_map = {s["id"]: s for s in states}
    warnings.extend(sp.warnings)
    if sp._eval_count >= MAX_EVAL_STATES:  # noqa: SLF001
        warnings.append("状态求值达安全阀 %d，状态覆盖可能不完整" % MAX_EVAL_STATES)

    pass1_hits = []
    if pass1_path and os.path.isfile(pass1_path):
        pass1_hits = normalize_pass1(load_json(pass1_path))
    elif pass1_path:
        warnings.append("--pass1 文件不存在：%s（趟 2 为空）" % pass1_path)
    else:
        log("[info] 未给 --pass1（T-28b/T-31 斑块结果），趟 2 为空")
    pass2 = select_pass2(parts, poses, pairs, pass1_hits, log=log)

    frames = build_frames(states_map, parts, poses, pairs, pass2, pb_parts, timing, log=log)
    frames, skipped_frames = truncate(frames, total_budget_s)
    batches = batch_frames(frames, batch_budget_s)

    # ---- 每部件表 ----
    frame_count: Dict[str, int] = {}
    for f in frames:
        for p in f["parts"]:
            frame_count[p] = frame_count.get(p, 0) + 1
    part_table = {}
    for p in parts:
        pid = p["id"]
        part_table[pid] = {
            "covers": p["covers"],
            "regions": p["regions"],
            "kind": p["kind"],
            "pb": resolve_pb(p, pb_parts),
            "states": sp.planned_states.get(pid, []),
            "visible_states": sorted(s["id"] for s in states if pid in s["visible_parts"]),
            "pass1": pairs[pid]["pass1"],
            "pass2": pass2.get(pid, []),
            "pass2_candidates": pairs[pid]["pass2_candidates"],
            "frames": frame_count.get(pid, 0),
            "pose_scope_include": p["include"],
        }

    # 「被截断的 (部件, 姿势)」：按 (part, pose) 去重，记被砍掉的帧数
    skipped_pairs: Dict[Tuple[str, str], int] = {}
    for f in skipped_frames:
        for pid in f["parts"]:
            key = (pid, f["pose"])
            skipped_pairs[key] = skipped_pairs.get(key, 0) + 1
    skipped = [{"part": k[0], "pose": k[1], "frames": v, "reason": "budget"}
               for k, v in sorted(skipped_pairs.items())]
    skipped_by_prio: Dict[str, int] = {}
    for f in skipped_frames:
        skipped_by_prio[str(f["priority"])] = skipped_by_prio.get(str(f["priority"]), 0) + 1

    est_total = round(sum(f["est_s"] for f in frames), 2)
    priority_hist: Dict[str, int] = {}
    for f in frames:
        priority_hist[str(f["priority"])] = priority_hist.get(str(f["priority"]), 0) + 1
    return {
        "schema": SCHEMA,
        "source": "pose_plan.py (T-29)",
        "project": project,
        "inputs": {
            "decl": decl_path, "pose_library": pose_lib_path,
            "inventory": inventory_path, "pb": pb_path, "pose_timing": timing_path,
            "pass1": pass1_path,
        },
        "timing": timing,
        "budget": {"batch_s": batch_budget_s, "total_s": total_budget_s},
        "counts": {
            "parts": len(parts),
            "poses": {"A": sum(1 for p in poses if p["kind"] == "A"),
                      "B": sum(1 for p in poses if p["kind"] == "B"),
                      "C": sum(1 for p in poses if p["kind"] == "C")},
            "pass1_poses": sum(1 for p in poses if p["pass_no"] == 1),
            "pass2_poses": sum(1 for p in poses if p["pass_no"] == 2),
            "states": len(states),
            "requirements": len(sp._requirements),  # noqa: SLF001
            "frames": len(frames),
            "skipped": len(skipped),
            "skipped_frames": len(skipped_frames),
            "skipped_by_priority": skipped_by_prio,
            "batches": len(batches),
            "est_total_s": est_total,
            "priority_hist": priority_hist,
        },
        "states": states,
        "parts": part_table,
        "batches": [{"index": i, "frames": len(b), "est_s": round(sum(f["est_s"] for f in b), 2)}
                    for i, b in enumerate(batches)],
        "skipped": skipped,
        "warnings": warnings,
        "_frames": frames, "_batches": batches,
    }


def write_outputs(plan_obj: dict, out_dir: str) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    written = []
    frames = plan_obj.pop("_frames")
    batches = plan_obj.pop("_batches")
    for i, b in enumerate(batches):
        path = os.path.join(out_dir, "request_pose_%d.json" % i)
        write_json(path, {"schema": "pose_request/1", "batch": i,
                          "est_s": round(sum(f["est_s"] for f in b), 2),
                          "frames": b})
        written.append(path)
    p = os.path.join(out_dir, "pose_plan.json")
    write_json(p, plan_obj)
    written.append(p)
    p = os.path.join(out_dir, "pose_plan_skipped.json")
    write_json(p, {"schema": "pose_plan_skipped/1", "skipped": plan_obj.get("skipped") or []})
    written.append(p)
    return written


# ---------------------------------------------------------------------------
# 打印
# ---------------------------------------------------------------------------
def print_part_table(plan_obj: dict, log=print) -> None:
    log("%-22s %7s %7s %7s %7s  %s" %
        ("部件", "状态", "趟1", "趟2", "帧", "pb"))
    for pid in sorted(plan_obj["parts"]):
        t = plan_obj["parts"][pid]
        log("%-22s %7d %7d %7d %7d  %s" %
            (pid, len(t["states"]), len(t["pass1"]), len(t["pass2"]),
             t["frames"], t["pb"]))


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------
def _selftest() -> int:
    repo = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
    project = os.path.join(repo, "工程A")
    if not os.path.isdir(project):
        print("[FAIL] 找不到 工程A 工程：%s" % project)
        return 2
    tmp_root = os.path.join(repo, "_长程任务_20260918", "派工", "tmp", "au")
    out_dir = os.path.join(tmp_root, "pose_plan_selftest")
    os.makedirs(out_dir, exist_ok=True)

    decl = os.path.join(project, "_感知", "decl.json")
    plib = os.path.join(project, "_感知", "out", "pose_library.json")
    inv = os.path.join(project, "_感知", "out", "inventory.json")
    pb = os.path.join(project, "_感知", "out", "pb.json")
    for p in (decl, plib, inv, pb):
        if not os.path.isfile(p):
            print("[FAIL] 缺输入 %s" % p)
            return 2

    timing_path = os.path.join(out_dir, "pose_timing_fake.json")
    write_json(timing_path, {"stabilize_s": 0.2, "settle_s": 5.0, "bake_s_per_part": 0.7})

    fake_pass1 = os.path.join(out_dir, "pass1_fake.json")
    write_json(fake_pass1, {"hits": [
        {"part": "MMN.pants", "joint": "hip_fb"},
        {"part": "MMN.socks", "joint": "knee"},
    ]})

    fails: List[str] = []
    print("== T-29 pose_plan selftest（工程A + 假 pose_timing）==")
    print("timing: 稳定 0.2 s / settle 5.0 s / 烘焙 0.7 s·件；批限 20 min")

    base = plan(project, decl, plib, inv, pb, timing_path,
                pass1_path=None, batch_budget_s=20 * 60, total_budget_s=0)
    part_table = base["parts"]

    # ① 每部件表存在
    if not part_table:
        fails.append("每部件表为空")
    for pid in ("kaguya.sailor", "MMN.skirt", "MMN.pants", "MMN.socks"):
        if pid not in part_table:
            fails.append("每部件表缺 %s" % pid)
    print("\n[1] 每部件表：%d 件；示例 %s" %
          (len(part_table), ", ".join(sorted(part_table)[:4])))
    print_part_table(base)

    # ② sailor 上衣不配髋/膝扫掠
    sailor = part_table.get("kaguya.sailor", {})
    bad = [p for p in sailor.get("pass1", [])
           if p.startswith("B_hip") or p.startswith("B_knee")]
    if bad:
        fails.append("kaguya.sailor 不应配髋/膝扫掠，却配了 %r" % bad)
    if "proxy_sit" not in sailor.get("pass1", []):
        fails.append("kaguya.sailor 的 pose_scope.include 未生效（缺 proxy_sit）")
    print("\n[2] kaguya.sailor：covers=%s regions=%s 趟1=%d，无 B_hip/B_knee=%s，含 proxy_sit=%s"
          % (sailor.get("covers"), sailor.get("regions"), len(sailor.get("pass1", [])),
             not bad, "proxy_sit" in sailor.get("pass1", [])))

    # ③ 裙与 MMN Pants 配坐姿
    for pid in ("MMN.skirt", "MMN.pants"):
        if "B_combo_sit" not in part_table.get(pid, {}).get("pass1", []):
            fails.append("%s 未配坐姿 B_combo_sit" % pid)
        if not any(p.startswith("B_hip") for p in part_table.get(pid, {}).get("pass1", [])):
            fails.append("%s 未配髋前屈扫掠" % pid)
    print("[3] MMN.skirt/MMN.pants 配坐姿：%s / %s（B_combo_sit=%s）"
          % ("B_combo_sit" in part_table["MMN.skirt"]["pass1"],
             "B_combo_sit" in part_table["MMN.pants"]["pass1"],
             "B_combo_sit" in part_table["MMN.skirt"]["pass1"]
             and "B_combo_sit" in part_table["MMN.pants"]["pass1"]))

    # ④ 趟 2 由趟 1 驱动
    p2 = plan(project, decl, plib, inv, pb, timing_path,
              pass1_path=fake_pass1, batch_budget_s=20 * 60, total_budget_s=0)
    t2 = p2["parts"]
    pants2 = t2["MMN.pants"]["pass2"]
    socks2 = t2["MMN.socks"]["pass2"]
    if not pants2 or not all("_hip_fb_" in x for x in pants2):
        fails.append("趟 2 未按假趟 1（MMN.pants/hip_fb）驱动：%r" % pants2)
    if not all(any(x.endswith(d) for d in ("_25", "_50", "_75")) for x in pants2):
        fails.append("趟 2 未生成 25/50/75 档：%r" % pants2)
    if not socks2 or not all("_knee_" in x for x in socks2):
        fails.append("趟 2 未按假趟 1（MMN.socks/knee）驱动：%r" % socks2)
    if t2["MMN.skirt"]["pass2"]:
        fails.append("趟 2 溢出到未命中件 MMN.skirt：%r" % t2["MMN.skirt"]["pass2"])
    print("\n[4] 趟 2（假趟 1: MMN.pants×hip_fb, MMN.socks×knee）：")
    print("    MMN.pants 趟2 %d 条：%s" % (len(pants2), ", ".join(pants2[:6])))
    print("    MMN.socks 趟2 %d 条：%s" % (len(socks2), ", ".join(socks2[:6])))
    print("    MMN.skirt 趟2 %d 条（应为 0）" % len(t2["MMN.skirt"]["pass2"]))

    # ⑤ 预算压缩：先砍库 C 再砍库 B
    frames = base["_frames"]
    cost = {}
    for f in frames:
        cost[f["priority"]] = cost.get(f["priority"], 0.0) + f["est_s"]
    c_a = cost.get(PRIORITY_A, 0.0)
    c_b = cost.get(PRIORITY_B100, 0.0)
    c_c = cost.get(PRIORITY_C, 0.0)
    c_lo = cost.get(PRIORITY_B_LOW, 0.0)
    print("\n[5] 预算压缩（估算秒）：A=%.1f B100=%.1f C=%.1f 趟2低档=%.1f；帧数 %d"
          % (c_a, c_b, c_c, c_lo, len(frames)))
    if c_c <= 0:
        fails.append("库里没有 C 帧，无法验证压缩顺序")
    else:
        def _cut(d, prio):
            return d["counts"]["skipped_by_priority"].get(str(prio), 0)

        bud1 = c_a + c_b + 0.5          # 刚好放下 A+B，放不下任何 C 帧
        b1 = plan(project, decl, plib, inv, pb, timing_path, pass1_path=None,
                  batch_budget_s=20 * 60, total_budget_s=bud1)
        cut_C, cut_B, cut_A = (_cut(b1, PRIORITY_C), _cut(b1, PRIORITY_B100),
                               _cut(b1, PRIORITY_A))
        if not cut_C or cut_B or cut_A:
            fails.append("预算=%.1f 时应只砍 C：C=%d B=%d A=%d"
                         % (bud1, cut_C, cut_B, cut_A))
        print("    预算 %.1f s：砍 C=%d B=%d A=%d（应 C>0, B=0, A=0）"
              % (bud1, cut_C, cut_B, cut_A))
        bud2 = c_a + 0.1                # 刚好放下 A，放不下任何 B
        b2 = plan(project, decl, plib, inv, pb, timing_path, pass1_path=None,
                  batch_budget_s=20 * 60, total_budget_s=bud2)
        cut2_B, cut2_A = _cut(b2, PRIORITY_B100), _cut(b2, PRIORITY_A)
        if not cut2_B or cut2_A:
            fails.append("预算=%.1f 时应在砍完 C 后砍 B：B=%d A=%d"
                         % (bud2, cut2_B, cut2_A))
        print("    预算 %.1f s：砍 C=%d B=%d A=%d（应 B>0, A=0）"
              % (bud2, _cut(b2, PRIORITY_C), cut2_B, cut2_A))
        # 规格里点名的 10 min
        b3 = plan(project, decl, plib, inv, pb, timing_path, pass1_path=None,
                  batch_budget_s=20 * 60, total_budget_s=10 * 60)
        print("    预算 10 min：帧 %d，批 %d，砍 %d 帧（其中 C=%d, B100=%d, A=%d）"
              % (b3["counts"]["frames"], b3["counts"]["batches"],
                 b3["counts"]["skipped_frames"],
                 _cut(b3, PRIORITY_C), _cut(b3, PRIORITY_B100), _cut(b3, PRIORITY_A)))

    print("\n[汇总] 状态 %d（覆盖需求 %d）、趟1 姿势 %d、帧 %d、估算总墙钟 %.1f s、批 %d"
          % (base["counts"]["states"], base["counts"]["requirements"],
             base["counts"]["pass1_poses"], base["counts"]["frames"],
             base["counts"]["est_total_s"], base["counts"]["batches"]))
    if base["warnings"]:
        print("[warnings]")
        for w in base["warnings"]:
            print("  - %s" % w)

    # 落盘（供核验）
    for tag, obj in (("full", base), ("pass2", p2), ("budget10", b3)):
        o = dict(obj)
        o.pop("_frames", None)
        o.pop("_batches", None)
        write_json(os.path.join(out_dir, "plan_%s.json" % tag), o)
    print("\n[输出] %s" % out_dir)

    print("\n" + "=" * 60)
    if fails:
        for f in fails:
            print("[FAIL] %s" % f)
        print("FAILED: %d" % len(fails))
        return 1
    print("ALL PASS")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="姿势×状态计划（T-29）")
    ap.add_argument("--project", default=os.path.abspath(os.path.join(
        _HERE, "..", "..", "..", "..", "工程A")))
    ap.add_argument("--decl", default=None, help="默认 <工程>/_感知/decl.json")
    ap.add_argument("--pose-library", default=None,
                    help="默认 <工程>/_感知/out/pose_library.json")
    ap.add_argument("--inventory", default=None, help="默认 <工程>/_感知/out/inventory.json")
    ap.add_argument("--pb", default=None, help="默认 <工程>/_感知/out/pb.json")
    ap.add_argument("--pose-timing", default=None,
                    help="默认 <工程>/_感知/out/pose_timing.json（缺席退默认值）")
    ap.add_argument("--pass1", default=None, help="T-28b/T-31 斑块结果，驱动趟 2")
    ap.add_argument("--budget-min", type=float, default=BATCH_BUDGET_DEFAULT_MIN,
                    help="每批墙钟上限，分钟（R6 默认 20）")
    ap.add_argument("--total-budget-min", type=float, default=0.0,
                    help="总墙钟上限，分钟；>0 时按优先级截断")
    ap.add_argument("--out", default=None, help="默认 <工程>/_感知/out/")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    project = os.path.abspath(args.project)
    decl = args.decl or os.path.join(project, "_感知", "decl.json")
    plib = args.pose_library or os.path.join(project, "_感知", "out", "pose_library.json")
    inv = args.inventory or os.path.join(project, "_感知", "out", "inventory.json")
    pb = args.pb or os.path.join(project, "_感知", "out", "pb.json")
    timing = args.pose_timing or os.path.join(project, "_感知", "out", "pose_timing.json")
    out_dir = args.out or os.path.join(project, "_感知", "out")
    for p in (decl, plib):
        if not os.path.isfile(p):
            print("[FAIL] 缺输入 %s" % p, file=sys.stderr)
            return 2
    res = plan(project, decl, plib, inv, pb, timing, pass1_path=args.pass1,
               batch_budget_s=args.budget_min * 60.0,
               total_budget_s=args.total_budget_min * 60.0)
    print("状态 %d、趟1 姿势 %d、帧 %d、估算 %.1f s、批 %d、砍 %d"
          % (res["counts"]["states"], res["counts"]["pass1_poses"],
             res["counts"]["frames"], res["counts"]["est_total_s"],
             res["counts"]["batches"], res["counts"]["skipped"]))
    print_part_table(res)
    for w in res["warnings"]:
        print("[warn] %s" % w)
    paths = write_outputs(res, out_dir)
    for p in paths:
        print("写出 %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
