#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rules_universal.py —— T-14 通用规则（与声明无关，每批必跑）＋构后改名解析。
【项目沉淀】通用工具
适用素体：无关
相关素材：T-14 各批数据（geo/T1/writers）
工具链　：Python 3（离线）
可复用性：★★ 审查工具链的一环
用途　　：T-14 通用规则（U1 起，与声明无关、每批必跑）＋构后改名解析。


设计口径（03 §4.1）：
  U1 任一可见覆盖件对其覆盖子部位静态穿出斑块 = 0        → 需 geo_*.json（T-10/T-28a），缺席 no_data
  U2 两件同时可见衣物重合比例 < 50%                      → 需 T1 probes.coincident
  U3 收缩/姿态键在其全部写者宿主不可见时 = 基线            → 需 writers.json（T-11），缺席 no_data
  U4 抓取点 ≥ 声明值 且抓取点之后无非抓屏可见材质          → 需 T1 probes.grab_chain
  U5 权重 0–100                                          → 需 T1 probes.range（或状态 blendshapes 兜底）
  U6 同网格顶点数跨状态不变（V4/Delete 解释除外）          → 需 T1 v4 顶点数，缺席 no_data
  U7 挂 PB 的覆盖件碰撞体须含覆盖区关节链上的骨（归因线索）  → 需 pb.json，只报 info
  U-KF 同名键失配：件带身体同名键、件可见时件值 ≠ 身体值     → 需 key_follow 候选 + T1；
        AM 的 `perception/key_follow_verdict.py` 出现后优先调用它（见 README「T-14」节）

本模块只读输入、不写工程；名字解析对「Play 后 AAO/MA 改名」做后备匹配，匹配不上记 unmatched 不猜。
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import decl_validate as dv  # noqa: E402  （复用条件语法 parse_cond/eval_cond/EvalState）

# ---------------------------------------------------------------------------
# 构后改名：后备名字解析
# ---------------------------------------------------------------------------

_AAO_MERGE_RE = re.compile(r"\$\$AAO_AUTO_MERGE_SKINNED_MESH_(\d+)")
_AAO_KEY_RE = re.compile(r"AAO_Merged_(.*)_(\d+)$")
_DOLLAR_NUM_RE = re.compile(r"\$(\d+)")


def norm_path(p):
    """把 Unity/AAO 构后路径归一成纯段列表。

    `_Outfit$Outfit_MMN_黑$164/Shoes` → ["_Outfit","Outfit_MMN_黑","Shoes"]
    `[An-Labo]HoroNail_[空色]$FootNail_Default Variation$198` → [...,"FootNail_Default Variation"]
    `$$AAO_AUTO_MERGE_SKINNED_MESH_3` 保留为单段（身体合并后的通用名）。
    """
    if not p:
        return []
    s = _AAO_MERGE_RE.sub(lambda m: "$$AAO_AUTO_MERGE_SKINNED_MESH", p)
    s = _DOLLAR_NUM_RE.sub("", s)
    s = s.replace("$", "/")
    return [seg for seg in s.split("/") if seg]


def _is_subseq(sub, seq):
    i = 0
    for x in seq:
        if i < len(sub) and sub[i] == x:
            i += 1
    return i == len(sub)


def resolve_mesh_matches(declared, candidates):
    """返回 (最佳匹配列表, 分数)。列表 >1 表示多义。

    评分：完全相等 100；归一段序列包含声明段 60+len；末段相等 40；末段是声明末段 20；
    父路径命中 AAO 合并网格（`$$AAO_AUTO_MERGE_SKINNED_MESH_n`）30+len。
    """
    if not declared or not candidates:
        return [], -1
    if declared in candidates:
        return [declared], 100
    da = norm_path(declared)
    best, best_score, ties = None, -1, []
    for c in candidates:
        ca = norm_path(c)
        score = -1
        if da == ca:
            score = 100
        elif da and ca and da[-1] == ca[-1] and _is_subseq(da, ca):
            score = 60 + len(da)
        elif da and ca and da[-1] == ca[-1]:
            score = 40
        elif da and ca and da[-1] in ca:
            score = 20
        elif (len(da) >= 2 and ca and "AAO_AUTO_MERGE_SKINNED_MESH" in ca[-1]
              and _is_subseq(da[:-1], ca[:-1])):
            # 件被 AAO 合并：声明父路径仍可对上合并网格
            score = 30 + len(da)
        if score > best_score:
            best, best_score, ties = c, score, [c]
        elif score == best_score and score >= 0:
            ties.append(c)
    if best_score < 0:
        return [], -1
    return list(dict.fromkeys(ties)), best_score


def resolve_mesh(declared, candidates):
    """把声明里的 mesh/objects.path 解析到状态里实际存在的渲染器路径。

    返回 (actual_path, ambiguous)。匹配不上 (None, False)；多义 (None, True)。
    """
    matches, _score = resolve_mesh_matches(declared, candidates)
    if not matches:
        return None, False
    if len(matches) > 1:
        return None, True
    return matches[0], False


def key_match_score(orig, cand):
    """构后键名匹配：精确 > AAO_Merged_<键>_<n> > ...__<键> > ..._<键> > 包含。"""
    if cand == orig:
        return 100
    m = _AAO_KEY_RE.match(cand)
    if m and m.group(1) == orig:
        return 90
    if cand.endswith("__" + orig):
        return 80
    if cand.endswith("_" + orig):
        return 70
    if orig and orig in cand:
        return 50
    return -1


def resolve_key(orig, candidates):
    """返回 (actual_key, ambiguous)。"""
    if not orig:
        return None, False
    best, best_score, ties = None, -1, []
    for c in candidates:
        s = key_match_score(orig, c)
        if s > best_score:
            best, best_score, ties = c, s, [c]
        elif s == best_score and s >= 0:
            ties.append(c)
    if best_score < 0:
        return None, False
    uniq = list(dict.fromkeys(ties))
    if len(uniq) > 1:
        return None, True
    return best, False


# ---------------------------------------------------------------------------
# 状态视图
# ---------------------------------------------------------------------------

def _truthy(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v >= 0.5
    s = str(v).strip().lower()
    return s in ("1", "true", "on", "yes")


def slot_index(raw, labels, kind):
    """GRAMMAR §2.1：float_slots 按 [i/n,(i+1)/n) 取槽号；int 取整数值。"""
    n = len(labels)
    if n == 0:
        return 0
    if kind == "int":
        try:
            i = int(round(float(raw)))
        except (TypeError, ValueError):
            i = 0
        return max(0, min(n - 1, i))
    try:
        f = float(raw)
    except (TypeError, ValueError):
        f = 0.0
    i = int(f * n)
    if i >= n:
        i = n - 1
    if i < 0:
        i = 0
    return i


class StateView:
    """一个 T1 状态文件的可判视图：参数、可见性、形态键、探针。"""

    def __init__(self, sid, raw, decl, catalog):
        self.id = sid
        self.raw = raw
        self.params = dict(raw.get("params_applied") or {})
        self.renderers = {r.get("path"): r for r in (raw.get("renderers") or [])}
        self.blendshapes = dict(raw.get("blendshapes") or {})
        self.probes = dict(raw.get("probes") or {})
        self.catalog = list(catalog)
        self.by_mesh = {}
        for p, ks in self.blendshapes.items():
            self.by_mesh[p] = dict(ks)
        self.unmatched = []          # [(kind, declared)]
        self._mesh_cache = {}
        self._key_cache = {}
        self._resolve_parts(decl)
        self._build_eval_state(decl)

    # -- 部件名解析 -------------------------------------------------------
    def _resolve_parts(self, decl):
        """解析 part → 实测渲染器，并给出**可归属的**实测可见性（B-补-12）。

        可见性归属三条口径
        ------------------
        1. 件解析到独立渲染器（非 `$$AAO_AUTO_MERGE_SKINNED_MESH_n`）：
           该物体可见 = 其任一独立渲染器 visible。
        2. 件只解析到 AAO 合并网格：AAO 只把 **activeness 动画完全相同**的网格合到一块
           （SOP/80）。若该件命中的合并块可见性一致 → 可见/不可见可判；
           若不一致（有的块可见、有的不可见）→ 该物体**归属不了**，记 unknown。
        3. 一个件声明了多个物体：只要各物体的可判结论不一致（含 unknown）→ 整件 unknown。
           （反例：`RePoppin.parker` 里 `(A)Parker` 不可见、领带 `(A)Necltie` 可见——
           按「任一物体可见即件可见」会把骑在胸上的领带算成外套盖胸。）

        `part_visible` 对 unknown 一律取 False（`vis()` 仍按「没有可归属的可见件」求值），
        但 **B-补-12 之后不许再拿这个 False 直接判 pass/fail**：`verdict.py` 走
        `eval_decl_dep(..., unknown=sv.vis_unknown())`，`when` 一旦依赖 unknown 件即落
        `undecidable`（`rules_universal.UNDECIDABLE`）；直接比 `visible(pid)` 的
        baseline/visibility/variant 判定也先查 `part_vis_unknown` 再判。unknown 另记在
        `part_vis_unknown`，并在 `self.unmatched` 里留 `mesh/merged-ambiguous`，不静默丢。
        """
        parts = decl.get("parts") or []
        self.part_paths = {}         # part_id -> [actual paths]（含合并块，兼容旧逻辑）
        self.part_visible = {}       # part_id -> bool（unknown 取 False）
        self.part_vis_unknown = {}   # part_id -> True 表示可见性归属不了
        self.parts_by_kind = {}
        self.parts_by_id = {}
        for p in parts:
            pid = p.get("id")
            self.parts_by_id[pid] = p
            kind = p.get("kind")
            if kind:
                self.parts_by_kind.setdefault(kind, []).append(pid)
        for p in parts:
            pid = p.get("id")
            own_paths, merged_paths, obj_vis = [], [], []
            for obj in (p.get("objects") or []):
                declared = obj.get("path")
                matches, _score = resolve_mesh_matches(declared, self.catalog)
                if not matches:
                    self.unmatched.append(("mesh", declared))
                    obj_vis.append(None)
                    continue
                own = [m for m in matches if "AAO_AUTO_MERGE_SKINNED_MESH" not in m]
                merged = [m for m in matches if "AAO_AUTO_MERGE_SKINNED_MESH" in m]
                if len(own) == 1:
                    own_paths.append(own[0])
                    obj_vis.append(bool(self.renderers.get(own[0], {}).get("visible")))
                elif len(own) > 1:
                    # 多义（多个独立渲染器都命中）：不猜，记 unmatched
                    self.unmatched.append(("mesh/ambiguous", declared))
                    obj_vis.append(None)
                elif merged:
                    merged_paths.extend(merged)
                    vis = [bool(self.renderers.get(x, {}).get("visible")) for x in merged]
                    if all(vis):
                        obj_vis.append(True)
                    elif not any(vis):
                        obj_vis.append(False)
                    else:
                        obj_vis.append(None)
                        self.unmatched.append(("mesh/merged-ambiguous", declared))
                else:
                    obj_vis.append(None)
            self.part_paths[pid] = own_paths + merged_paths
            if not obj_vis or all(v is None for v in obj_vis):
                self.part_visible[pid] = False
                self.part_vis_unknown[pid] = True
            elif all(v is True for v in obj_vis):
                self.part_visible[pid] = True
            elif all(v is False for v in obj_vis):
                self.part_visible[pid] = False
            else:
                # 部分物体可判可见/不可见，或含 unknown：整件归属不了
                self.part_visible[pid] = False
                self.part_vis_unknown[pid] = True

    # -- 状态参数 → EvalState --------------------------------------------
    def _build_eval_state(self, decl):
        st = dv.EvalState()
        menu = decl.get("menu") or {}
        for name, c in (menu.get("slots") or {}).items():
            param = c.get("param")
            raw = self.params.get(param, c.get("default", 0))
            bit = 1 if _truthy(raw) else 0
            st.slots[name] = bit
            st.params[param] = bit
        for name, c in (menu.get("controls") or {}).items():
            param = c.get("param")
            raw = self.params.get(param, c.get("default", 0))
            st.params[param] = raw
            t = c.get("type")
            labels = c.get("labels") or []
            if t == "bool":
                st.ctl[name] = {"kind": "bool", "bit": 1 if _truthy(raw) else 0}
            elif t in ("int", "float_slots") and labels:
                idx = slot_index(raw, labels, t)
                st.ctl[name] = {"kind": t, "label": labels[idx], "slot": idx, "bit": idx}
            else:
                st.ctl[name] = {"kind": "float", "raw": raw}
        outfit = menu.get("outfit") or {}
        param = outfit.get("param")
        raw = self.params.get(param, outfit.get("default", 0))
        st.params[param] = raw
        labels = outfit.get("labels") or []
        if labels:
            st.outfit_label = labels[slot_index(raw, labels, outfit.get("type") or "float_slots")]
        # body_axes：T1 状态头不带体型轴值，按档案 baseline（工程A 恒 0）——报告里列 no_data
        self.body_axes_no_data = []
        for name in (decl.get("body_axes") or {}):
            st.body[name] = 0.0
            self.body_axes_no_data.append(name)
        st.pose_id = None
        st.pose_tags = frozenset()
        self.st = st

    # -- 取值 -------------------------------------------------------------
    def mesh_candidates(self, mesh):
        """把声明里的 mesh（可能是名字、part 的 object 路径）映射到实际路径列表。"""
        if mesh in self._mesh_cache:
            return self._mesh_cache[mesh]
        res = None
        if mesh in self.renderers:
            res = [mesh]
        elif mesh in self.by_mesh:
            res = [mesh]
        else:
            actual, _amb = resolve_mesh(mesh, list(self.renderers.keys()))
            if actual:
                res = [actual]
            else:
                # 身体被 AAO 合并时的后备
                base = os.path.basename(mesh or "")
                merged = [p for p in self.renderers
                          if "AAO_AUTO_MERGE_SKINNED_MESH" in p]
                if base and merged:
                    res = merged
        if res is None:
            res = []
        self._mesh_cache[mesh] = res
        return res

    def value(self, mesh, key, default=0.0):
        """取 (mesh,key) 实测权重；键缺席即 0。返回 (value, actual_path, actual_key, unmatched)。"""
        for p in self.mesh_candidates(mesh):
            keys = self.by_mesh.get(p)
            if keys is None:
                continue
            ck = (p, key)
            if ck in self._key_cache:
                ak, amb = self._key_cache[ck]
            else:
                ak, amb = resolve_key(key, list(keys.keys()))
                self._key_cache[ck] = (ak, amb)
            if ak is not None:
                return float(keys[ak]), p, ak, None
            if amb:
                return default, p, None, "ambiguous"
            # 键缺席：该网格存在但键为 0
            return default, p, None, None
        return default, None, None, "mesh"

    def visible(self, part_id):
        return bool(self.part_visible.get(part_id, False))

    def eval_vis(self):
        return dict(self.part_visible)

    def vis_unknown(self):
        """可见性归属不了的件（合并网格可见性不一致 / 多物体结论不一致）。"""
        return dict(self.part_vis_unknown)


# ---------------------------------------------------------------------------
# 期望可见性 E（GRAMMAR §2.2；baseline 对 {part} 目标时用）
# ---------------------------------------------------------------------------

def compute_expected_visibility(decl, st):
    """菜单推出的期望可见件集合 E（不做 Play）。返回 {part_id: bool}。"""
    parts = decl.get("parts") or []
    pbk = {}
    for p in parts:
        if p.get("kind"):
            pbk.setdefault(p["kind"], []).append(p.get("id"))
    E = {}
    for p in parts:
        E[p.get("id")] = _base_visible(p, st)
    # 单趟修正：target 为 {part} 且结果 hidden/shown 的依赖
    for dep in (decl.get("deps") or []):
        tgt = dep.get("target")
        if not isinstance(tgt, dict) or "part" not in tgt:
            continue
        if any(k in tgt for k in ("key", "keys", "submesh")):
            continue
        pid = tgt["part"]
        if pid not in E:
            continue
        out = eval_decl_dep(dep, st, E, pbk)
        if isinstance(out, dict):
            if out.get("hidden") is True:
                E[pid] = False
            elif out.get("shown") is True:
                E[pid] = True
    return E


def _base_visible(part, st):
    if part.get("alt_of"):
        return False
    outfit = part.get("outfit")
    if outfit:
        labels = outfit if isinstance(outfit, list) else [outfit]
        if st.outfit_label not in labels:
            return False
    slot = part.get("slot")
    if slot and int(st.slots.get(slot, 0)) != 1:
        return False
    tog = part.get("toggle")
    if isinstance(tog, dict):
        c = st.ctl.get(tog.get("control"))
        if c is None:
            return False
        shown = tog.get("shown_at")
        vals = shown if isinstance(shown, list) else [shown]
        hit = False
        for v in vals:
            if isinstance(v, int) and not isinstance(v, bool):
                if c.get("kind") == "bool" and c.get("bit") == v:
                    hit = True
            elif c.get("label") == v:
                hit = True
        if not hit:
            return False
    return True


class _Undecidable(object):
    """`eval_decl_dep` 的返回值：`when` 依赖「可见性归属不了」的件，期望无从谈起。

    B-补-12 的硬口径：归属不了只能落 `undecidable`，**不许**按不可见（`E` 里取 False）
    走进 `else` 判 pass/fail。`verdict.judge` 见到这个单例就记 undecidable。
    """
    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super(_Undecidable, cls).__new__(cls)
        return cls._inst

    def __repr__(self):
        return "UNDECIDABLE"


UNDECIDABLE = _Undecidable()


def _vis_ref_states(ref, E, parts_by_kind, unknown):
    """把一个 vis/chain 引用展开成 [True/False/None]（None=归属不了）。"""
    if ref.startswith("any."):
        parts = list(parts_by_kind.get(ref[4:], ()))
    else:
        parts = [ref]
    out = []
    for p in parts:
        if p in unknown:
            out.append(None)
        else:
            out.append(True if E.get(p, False) else False)
    return out


def eval_cond_3(ast, st, E, parts_by_kind, unknown):
    """三值条件求值：True / False / None（None=依赖归属不了的件，判不了）。

    `vis` / `chain` 节点按三值或（OR）：任一 True→True；否则任一 None→None；全 False→False。
    `not`/`and`/`or` 按 Kleene 三值逻辑短路；其余节点只依赖参数/控制/体型（与可见性无关），
    直接复用 `dv.eval_cond` 的二元结果。
    """
    tag = ast[0]
    if tag in ("vis", "chain"):
        refs = [ast[1]] if tag == "vis" else list(ast[1])
        any_unknown = False
        for ref in refs:
            for v in _vis_ref_states(ref, E, parts_by_kind, unknown):
                if v is True:
                    return True
                if v is None:
                    any_unknown = True
        return None if any_unknown else False
    if tag == "not":
        v = eval_cond_3(ast[1], st, E, parts_by_kind, unknown)
        return None if v is None else (not v)
    if tag == "and":
        any_unknown = False
        for x in ast[1]:
            v = eval_cond_3(x, st, E, parts_by_kind, unknown)
            if v is False:
                return False
            if v is None:
                any_unknown = True
        return None if any_unknown else True
    if tag == "or":
        any_unknown = False
        for x in ast[1]:
            v = eval_cond_3(x, st, E, parts_by_kind, unknown)
            if v is True:
                return True
            if v is None:
                any_unknown = True
        return None if any_unknown else False
    # 与可见性无关的节点：参数/控制/槽位/体型，二元即确定
    return bool(dv.eval_cond(ast, st, E, parts_by_kind))


def eval_decl_dep(dep, st, E, parts_by_kind=None, unknown=None):
    """按 GRAMMAR §2.3 求一条 dep 在该状态下的期望（字符串或 dict）。

    `unknown` = 该状态里「可见性归属不了」的件 id 集合（B-补-12）。给了它就走三值求值：
    `when`/`cases.when` 依赖 unknown 件时返回 `UNDECIDABLE`，不再退 `else`。
    不传（如 pose_plan）时保持旧的二元行为。
    """
    parts_by_kind = parts_by_kind or {}
    unknown = set(unknown or ())
    else_out = dep.get("else")
    if else_out is None:
        else_out = "dont_care" if dep.get("origin") == "fragment" else "baseline"
    when = dep.get("when")
    try:
        ast = dv.parse_cond(when) if when is not None else ("true",)
    except Exception:
        return else_out
    w = eval_cond_3(ast, st, E, parts_by_kind, unknown)
    if w is None:
        return UNDECIDABLE
    if not w:
        return else_out
    if "expect_by_leader" in dep:
        return _leader_out(dep, ast, st, E, else_out, parts_by_kind, unknown)
    if "cases" in dep:
        for c in (dep.get("cases") or []):
            if not isinstance(c, dict):
                continue
            try:
                cast = dv.parse_cond(c.get("when"))
            except Exception:
                continue
            cw = eval_cond_3(cast, st, E, parts_by_kind, unknown)
            if cw is None:
                return UNDECIDABLE
            if cw:
                return c.get("expect", else_out)
        return else_out
    if "expect" in dep:
        return dep["expect"]
    return else_out


def _eval_cond(ast, st, E, parts_by_kind):
    return dv.eval_cond(ast, st, E, parts_by_kind)


def _leader_out(dep, ast, st, E, else_out, parts_by_kind=None, unknown=None):
    parts_by_kind = parts_by_kind or {}
    unknown = set(unknown or ())
    for item in dv.top_level_conjuncts(ast):
        if item[0] == "chain":
            for ref in item[1]:
                if ref.startswith("any."):
                    parts = list(parts_by_kind.get(ref[4:], ()))
                    if any(E.get(p, False) for p in parts):
                        for p in parts:
                            if E.get(p, False):
                                return (dep.get("expect_by_leader") or {}).get(p, else_out)
                    if any(p in unknown for p in parts):
                        return UNDECIDABLE
                    continue
                if ref in unknown:
                    return UNDECIDABLE
                if E.get(ref, False):
                    return (dep.get("expect_by_leader") or {}).get(ref, else_out)
            return else_out
    return else_out


# ---------------------------------------------------------------------------
# 通用规则
# ---------------------------------------------------------------------------

def _f(rule, state, message, severity, **kw):
    d = {"rule": rule, "state": state, "severity": severity, "message": message}
    d.update(kw)
    return d


def rule_u1(geo, ctx):
    """U1 静态穿出斑块（T-28a）。geo_*.json 缺席即 no_data。"""
    out = []
    if not geo:
        return out, [{"rule": "U1", "status": "no_data",
                      "reason": "无 geo_*.json（T-10/T-28a 未产出）；静态斑块判不了"}]
    for sid, g in geo.items():
        patches = _collect_patches(g)
        for pt in patches:
            area = pt.get("area_cm2")
            if area is None:
                continue
            if area >= ctx["U1"]["min_area_cm2"]:
                out.append(_f("U1", sid,
                              "静态穿出斑块 %.2f cm² ≥ %.2f cm²" % (area, ctx["U1"]["min_area_cm2"]),
                              "advisory", target=pt.get("part") or pt.get("garment"),
                              metric="poke.area_cm2", actual=area,
                              expected="<%.2f" % ctx["U1"]["min_area_cm2"],
                              advisory=True))
    if not out:
        out.append(_f("U1", None, "geo 数据存在但未识别出斑块条目（schema 未定，见 T-10 交付）",
                      "no_data", advisory=True))
    return out, []


def _collect_patches(g):
    if not isinstance(g, dict):
        return []
    for k in ("patches", "poke_patches", "poke", "patches_all"):
        v = g.get(k)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
    return []


def rule_u2(states, ctx):
    """U2 两件重合。命中 = coincident.hits>0；ratio 由 coincident_pairs 给出。"""
    out, no_data = [], []
    seen = False
    for sv in states:
        co = sv.probes.get("coincident")
        if not co:
            continue
        seen = True
        hits = co.get("hits")
        pairs = co.get("coincident_pairs") or []
        if hits:
            for pr in pairs:
                ratio = pr.get("ratio") if isinstance(pr, dict) else None
                out.append(_f("U2", sv.id,
                              "两件可见网格重合 %s" % (("%.2f" % ratio) if ratio is not None else "≥阈值"),
                              "violation", target=_pair_name(pr),
                              metric="overlap_ratio", actual=ratio,
                              expected="<%.2f" % ctx["U2"]["max"],
                              writer_blamed=None))
    if not seen:
        no_data.append({"rule": "U2", "status": "no_data",
                        "reason": "状态文件无 probes.coincident"})
    return out, no_data


def _pair_name(pr):
    if not isinstance(pr, dict):
        return None
    a = pr.get("a") or pr.get("mesh_a") or ""
    b = pr.get("b") or pr.get("mesh_b") or ""
    return "%s × %s" % (a, b)


def rule_u3(states, writers, profile, ctx):
    """U3 收缩/姿态键在其全部写者宿主不可见时须回基线。需 writers.json。"""
    out, no_data = [], []
    if not writers:
        return out, [{"rule": "U3", "status": "no_data",
                      "reason": "无 writers.json（T-11 未产出）；写者宿主不可见性判不了"}]
    classes = _profile_key_classes(profile)
    we = writers.get("writers") or {}
    hosts = {}   # (mesh,key) -> [host 描述（部件 id 或路径）]
    for k, entries in we.items():
        if "::" not in k:
            continue
        mesh, key = k.split("::", 1)
        for e in entries:
            for cand in (e.get("host"), e.get("component_path"), e.get("path"), e.get("mesh")):
                if cand:
                    hosts.setdefault((mesh, key), [])
                    if cand not in hosts[(mesh, key)]:
                        hosts[(mesh, key)].append(cand)
    if not hosts:
        return out, [{"rule": "U3", "status": "no_data",
                      "reason": "writers.json 里没有可解析的 (mesh,key)→宿主"}]
    for sv in states:
        for (mesh, key), hs in hosts.items():
            cls = classes.get(key)
            if cls not in ("shrink", "pose"):
                continue
            visible_host = False
            unknown_host = False
            for h in hs:
                if h in sv.vis_unknown():
                    unknown_host = True
                if h in sv.part_visible and sv.visible(h):
                    visible_host = True
                    break
                for p in sv.mesh_candidates(h):
                    if sv.renderers.get(p, {}).get("visible"):
                        visible_host = True
                        break
                if visible_host:
                    break
            if visible_host:
                continue
            if unknown_host:
                # B-补-12：宿主可见性归属不了 → U3 判不了，不许按不可见判违例
                no_data.append({"rule": "U3", "status": "undecidable",
                                "reason": "%s.%s：写者宿主可见性归属不了，U3 判不了"
                                          % (mesh, key), "state": sv.id})
                continue
            val, _p, _k, _u = sv.value(mesh, key)
            base = baseline_value(profile, key)
            if abs(val - base) > ctx["U3"]["tol"]:
                out.append(_f("U3", sv.id,
                              "%s.%s 在全部写者宿主不可见时为 %.2f（应回基线 %.2f）"
                              % (mesh, key, val, base),
                              "violation", target="%s.%s" % (mesh, key),
                              metric="value_abs_diff", actual=val, expected=base))
    return out, no_data


def rule_u4(states, ctx):
    """U4 抓屏链：hidden_materials 超上限即违例；point_warn 只记 info。"""
    out, no_data = [], []
    seen = False
    hidden_max = ctx["U4"]["hidden_max"]
    warn_below = ctx["U4"]["point_warn_below"]
    for sv in states:
        gc = sv.probes.get("grab_chain")
        if not gc:
            continue
        seen = True
        q = gc.get("grab_point_queue")
        if q is not None and q < warn_below:
            out.append(_f("U4", sv.id, "抓取点 %s < %d（危险信号，非违例）" % (q, warn_below),
                          "info", metric="grab.point_queue", actual=q,
                          expected="≥%d" % warn_below))
        hidden = gc.get("hidden_materials") or []
        if not hidden:
            continue
        # 没有抓屏材质时 grab_point_queue=null，不算违例
        if q is None:
            continue
        n = len(hidden)
        if n > hidden_max:
            for h in hidden:
                out.append(_f("U4", sv.id,
                              "抓屏点之后有非抓屏可见材质 q=%s（透过抓屏窗口看不见）"
                              % (h.get("render_queue") if isinstance(h, dict) else "?"),
                              "violation", target=_mat_name(h),
                              metric="grab.hidden_count", actual=n,
                              expected="≤%d" % hidden_max, writer_blamed=None))
    if not seen:
        no_data.append({"rule": "U4", "status": "no_data",
                        "reason": "状态文件无 probes.grab_chain"})
    return out, no_data


def _mat_name(h):
    if not isinstance(h, dict):
        return None
    return "%s[%s]" % (h.get("material"), h.get("slot"))


def rule_u5(states, ctx):
    """U5 权重 0–100。优先用 range 探针；没有则扫 blendshapes。"""
    out, no_data = [], []
    seen = False
    for sv in states:
        rg = sv.probes.get("range")
        items = []
        if rg:
            seen = True
            items = rg.get("out_of_range") or []
        if not items:
            for p, ks in sv.blendshapes.items():
                for k, v in ks.items():
                    try:
                        fv = float(v)
                    except (TypeError, ValueError):
                        continue
                    if fv < ctx["U5"]["min"] - 1e-9 or fv > ctx["U5"]["max"] + 1e-9:
                        items.append({"renderer": p, "key": k, "value": fv})
        for it in items:
            out.append(_f("U5", sv.id,
                          "权重越界 %s" % json.dumps(it, ensure_ascii=False)[:120],
                          "violation", target=it.get("key") or it.get("renderer"),
                          metric="value_abs_diff", actual=it.get("value"),
                          expected="0–100"))
    if not seen and not out:
        no_data.append({"rule": "U5", "status": "no_data",
                        "reason": "无 probes.range 且状态里没有可扫的 blendshapes"})
    return out, no_data


def rule_u6(states, ctx):
    """U6 同网格顶点数跨状态不变。T1 v4 前状态文件没有顶点数 → no_data。"""
    series = {}
    found = False
    for sv in states:
        for r in (sv.raw.get("renderers") or []):
            vc = r.get("vertex_count") or r.get("vertexCount")
            if vc is None:
                continue
            found = True
            series.setdefault(r.get("path"), set()).add(vc)
    out, no_data = [], []
    if not found:
        return out, [{"rule": "U6", "status": "no_data",
                      "reason": "状态文件无顶点数（需 T1 v4 键存在表/V4 桶）"}]
    for path, vals in series.items():
        if len(vals) > 1:
            out.append(_f("U6", None, "%s 顶点数跨状态变化 %s" % (path, sorted(vals)),
                          "violation", target=path, metric="vertex_count_diff",
                          actual=sorted(vals), expected="恒定（V4/Delete 解释除外）"))
    return out, no_data


def rule_u7(pb, ctx):
    """U7 PB 碰撞体覆盖：只作归因线索（info）。"""
    if not pb:
        return [], [{"rule": "U7", "status": "no_data", "reason": "无 pb.json（T-30 未产出）"}]
    out = []
    for it in (pb.get("u7") or []):
        if not isinstance(it, dict):
            it = {"message": str(it)}
        out.append(_f("U7", None, "PB 缺碰撞体：%s" % (it.get("message") or json.dumps(it, ensure_ascii=False)[:120]),
                      "info", target=it.get("part") or it.get("pb_path"),
                      advisory=True))
    return out, []


def key_follow_verdict(states, key_follow, decl, profile, ctx, t1_dirs=None,
                       key_follow_path=None):
    """U-KF 同名键失配。

    优先调用 AM 的 `perception/key_follow_verdict.py`（已交付）：
    其 API 是 `load_states(t1_dirs)` + `build_result(inventory_path, t1_dirs, states)`；
    若它暴露 `analyze(key_follow, t1_dirs)` 也认。调用失败或模块缺席时退本模块内联实现
    （判据相同：件可见时 |件值−身体值| > 阈 → mismatch）。返回 (findings, no_data, unmatched)。
    """
    ext = _load_am_module()
    no_data_extra = []
    if ext is not None:
        try:
            if key_follow_path and hasattr(ext, "build_result") and hasattr(ext, "load_states"):
                ext_states = ext.load_states(list(t1_dirs or []))
                res = ext.build_result(str(key_follow_path), list(t1_dirs or []), ext_states)
            elif hasattr(ext, "analyze"):
                res = ext.analyze(key_follow=key_follow, t1_dirs=list(t1_dirs or []))
            else:
                res = None
            if res is not None:
                return _kf_from_external(res, ctx)
        except Exception as exc:  # 外部模块失败 → 不静默，退内联并记录
            no_data_extra = [{"rule": "U-KF", "status": "no_data",
                              "reason": "key_follow_verdict.py 调用失败：%s；退内联实现" % exc}]
    out, unmatched = [], []
    no_data = list(no_data_extra)
    if not key_follow:
        no_data.append({"rule": "U-KF", "status": "no_data",
                        "reason": "无 key_follow 候选清单（T-05/AK 未产出）；同名键失配判不了"})
        return out, no_data, unmatched
    body, candidates = _extract_candidates(key_follow)
    if not body:
        no_data.append({"rule": "U-KF", "status": "no_data", "reason": "key_follow 里没有 body 字段"})
        return out, no_data, unmatched
    if not candidates:
        no_data.append({"rule": "U-KF", "status": "no_data", "reason": "key_follow 里没有 candidates"})
        return out, no_data, unmatched
    tol = ctx["U_KF"]["mismatch_tol"]
    for cand in candidates:
        rend = cand.get("renderer")
        key = cand.get("key")
        piece_path, amb = resolve_mesh(rend, list(_catalog(states)))
        if piece_path is None:
            unmatched.append({"kind": "candidate-mesh" + ("/ambiguous" if amb else ""),
                              "renderer": rend, "key": key})
            continue
        vis_states, mismatch = [], []
        for sv in states:
            # 件可见：该渲染器 visible
            r = sv.renderers.get(piece_path)
            if r is None:
                continue
            if not r.get("visible"):
                continue
            vis_states.append(sv.id)
            pv, _pp, _pk, _pu = sv.value(piece_path, key)
            bv, _bp, _bk, _bu = sv.value(body, key)
            if abs(pv - bv) > tol:
                mismatch.append({"state": sv.id, "piece": pv, "body": bv})
        if not vis_states:
            no_data.append({"rule": "U-KF", "status": "no_data",
                            "reason": "候选 %s × %s 在所有状态里件都不可见" % (rend, key)})
            continue
        if mismatch:
            worst = max(mismatch, key=lambda m: abs(m["piece"] - m["body"]))
            out.append(_f("U-KF", worst["state"],
                          "%s 带身体同名键 %s：件可见时件值 %.2f ≠ 身体值 %.2f（差 %.2f > %.2f），%d 个状态失配"
                          % (rend, key, worst["piece"], worst["body"],
                             abs(worst["piece"] - worst["body"]), tol, len(mismatch)),
                          "violation", target="%s.%s" % (rend, key),
                          metric="value_abs_diff", actual=abs(worst["piece"] - worst["body"]),
                          expected="≤%.1f" % tol, dep=None,
                          writer_blamed=None, states_visible=len(vis_states),
                          states_mismatch=mismatch, source="verdict.py:inline"))
        else:
            out.append(_f("U-KF", None,
                          "%s × %s：件可见 %d 态，件值与身体值无失配（benign）"
                          % (rend, key, len(vis_states)),
                          "pass", target="%s.%s" % (rend, key),
                          states_visible=len(vis_states), states_mismatch=[],
                          source="verdict.py:inline"))
    return out, no_data, unmatched


def _load_am_module():
    """尝试导入 AM 的 key_follow_verdict.py（T-14 规格允许的直连）。"""
    path = os.path.join(HERE, "key_follow_verdict.py")
    if not os.path.exists(path):
        return None
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("key_follow_verdict_ext", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "analyze") or (hasattr(mod, "build_result")
                                       and hasattr(mod, "load_states")):
            return mod
    except Exception:
        return None
    return None


def _kf_from_external(res, ctx):
    """把外部模块（AM 的 build_result 或自定义 analyze）结果规范成 findings/no_data/unmatched。"""
    out, no_data, unmatched = [], [], []
    if not isinstance(res, dict):
        return out, [{"rule": "U-KF", "status": "no_data",
                      "reason": "key_follow_verdict 返回非 dict：%r" % type(res)}], unmatched
    # AM build_result 形状：{candidates:[{verdict, renderer, key, ...}], unmatched:[...]}
    if "candidates" in res:
        for it in (res.get("candidates") or []):
            if not isinstance(it, dict):
                continue
            rend = it.get("renderer")
            key = it.get("key")
            target = "%s.%s" % (rend, key)
            verdict = it.get("verdict")
            if verdict == "mismatch":
                ms = it.get("states_mismatch") or []
                worst = max(ms, key=lambda m: _nf(m.get("diff"), 0.0)) if ms else {}
                out.append(_f("U-KF", worst.get("state"),
                              "%s 带身体同名键 %s：件可见时失配 %d 个状态（最大差 %.2f）"
                              % (rend, key, len(ms), _nf(it.get("max_diff"), 0.0)),
                              "violation", target=target, metric="value_abs_diff",
                              actual=it.get("max_diff"), expected="≤%s" % ctx["U_KF"]["mismatch_tol"],
                              states_visible=it.get("states_visible"), states_mismatch=ms,
                              source="key_follow_verdict.py"))
            elif verdict == "benign":
                out.append(_f("U-KF", None,
                              "%s × %s：件可见 %s 态，件值与身体值无失配（benign）"
                              % (rend, key, it.get("states_visible")),
                              "pass", target=target,
                              states_visible=it.get("states_visible"),
                              source="key_follow_verdict.py"))
            elif verdict == "benign_geometry":
                # B-补-07：数值失配但几何 <1 mm → 不是缺陷，记 pass，明细留给 key_follow_verdict
                g = it.get("geometry") or {}
                out.append(_f("U-KF", None,
                              "%s × %s：件可见 %s 态，数值失配但几何几乎不动"
                              "（p50Δ=%s mm / 件位移=%s mm < 1 mm，benign_geometry）"
                              % (rend, key, it.get("states_visible"),
                                 g.get("p50_delta_mm"), g.get("piece_key_disp_max_mm")),
                              "pass", target=target,
                              states_visible=it.get("states_visible"),
                              geometry=g, numeric_verdict=it.get("numeric_verdict"),
                              source="key_follow_verdict.py"))
            else:
                reason = it.get("missing") or "no_data"
                if it.get("states_visible", 0) == 0:
                    unmatched.append({"kind": "candidate", "renderer": rend,
                                      "key": key, "reason": reason,
                                      "match": (it.get("match") or {}).get("piece_methods")})
                else:
                    no_data.append({"rule": "U-KF", "status": "no_data",
                                    "reason": "%s × %s：%s" % (rend, key, reason)})
        for u in (res.get("unmatched") or []):
            unmatched.append(u if isinstance(u, dict) else {"kind": "unmatched", "what": str(u)})
        return out, no_data, unmatched
    # 自定义 analyze 形状：{findings:[...], no_data:[...], unmatched:[...]}
    for f in res.get("findings") or []:
        if isinstance(f, dict):
            if "status" not in f:
                v = f.get("verdict")
                f["status"] = {"mismatch": "violation", "benign": "pass",
                               "benign_geometry": "pass"}.get(
                    v, f.get("severity") or "no_data")
            out.append(f)
        else:
            no_data.append({"rule": "U-KF", "status": "no_data", "reason": str(f)})
    for n in res.get("no_data") or []:
        no_data.append(n if isinstance(n, dict)
                       else {"rule": "U-KF", "status": "no_data", "reason": str(n)})
    for u in res.get("unmatched") or []:
        unmatched.append(u if isinstance(u, dict) else {"kind": "unmatched", "what": str(u)})
    return out, no_data, unmatched


def _nf(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _extract_candidates(key_follow):
    """兼容两种输入：inventory（avatars[].key_follow）与 AM 的 key_follow JSON。"""
    body = None
    candidates = []
    avatars = key_follow.get("avatars")
    if isinstance(avatars, list) and avatars:
        kf = (avatars[0] or {}).get("key_follow") or {}
        body = kf.get("body")
        candidates = kf.get("candidates") or []
    else:
        kf = key_follow.get("key_follow") or key_follow
        body = kf.get("body")
        candidates = kf.get("candidates") or []
    return body, candidates


def _catalog(states):
    seen = []
    for sv in states:
        for p in sv.renderers:
            if p not in seen:
                seen.append(p)
    return seen


# ---------------------------------------------------------------------------
# 其它共用
# ---------------------------------------------------------------------------

def _profile_key_classes(profile):
    cls = {}
    kc = (profile or {}).get("key_classes") or {}
    for group in ("pose", "shrink", "body", "face", "nail", "delete_target"):
        for k in (kc.get(group) or {}):
            cls[k] = group
    for k in (kc.get("delete_targets") or {}):
        cls[k] = "delete_target"
    return cls


def baseline_value(profile, key):
    """素体档案 baseline：client 覆盖 neutral_foot 覆盖 factory，缺省 0。"""
    b = (profile or {}).get("baseline") or {}
    val = 0.0
    for group in ("factory", "neutral_foot", "client"):
        g = b.get(group)
        if isinstance(g, dict) and key in g:
            try:
                val = float(g[key])
            except (TypeError, ValueError):
                pass
    return val
