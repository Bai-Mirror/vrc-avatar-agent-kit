# -*- coding: utf-8 -*-
"""pose_frames.py — 姿势帧库（T-26，04 第一期开工清单 §3b；设计依据 03 §8.1）。
【项目沉淀】通用工具
适用素体：无关
相关素材：SDK 姿势 + 工程私有姿势 clip
工具链　：Python 3 + PyYAML（离线）
可复用性：★★ 按工程姿势来源复用
用途　　：姿势帧库：把 SDK/GoGo Loco/工程私有/关节扫掠统一成「95 肌肉向量 + RootT/RootQ」帧库。


把三种来源统一成「95 肌肉向量 + RootT/RootQ」的帧库 `pose_library.json`：
  * 库 A 真实静态姿势：SDK `ProxyAnim/*.anim` 全部 79 个；GoGo Loco 固定 7 条（装了才收）；
    工程私有——头像描述符 5 层控制器（含 MergeAnimator 并入）引用到的全部人形 clip。
    Additive 层的 clip 标 `additive: true`（值是增量，叠加在 `stand_still` 上）。
  * 库 B 关节扫掠：7 个左右分关节组 × {25,50,75,100}% × 左右 + 脊柱前屈 4 档 + 6 组合 = 66 条。
    剂量 = 其余肌肉取 `stand_still` 值，被扫肌肉从 `stand_still` 值向该方向的**库 A 包络极值**
    线性插值（agy D5：不插 HumanDescription ±1；`--envelope extreme` 才另出 ±1 档）。
  * 库 C 真动作 clip：GM 表情 16 个；GoGo 跳跃/knockback/afk_idle；`poses.extra_clips` 用户路径。

读法（M1）
----------
* 只读 `m_FloatCurves`（带 attribute 名）；`m_EditorCurves` 是编辑器副本，不读。
  数字属性在 `m_ClipBindingConstant.genericBindings`（customType 8）**只用来核对条数**：
  肌肉绑定的 `attribute == 肌肉序号 + 42`，据此校验 95 名表的序号（见 `muscles.py`）。
* 手指名 `LeftHand.Index.1 Stretched` → HumanTrait `Left Index 1 Stretched`（显式映射）。
* 身体类 proxy 缺的手指曲线取 `proxy_hands_idle` 的值，**不填 0**。
* `moved_regions` 离线 = 肌肉组 |Δ vs `stand_still`| > 0.1 → 部位（I10）；
  骨骼旋转差由 T-27 在 Unity 里补算写 `moved_regions_bones`。

    python3 pose_frames.py --project <工程根> [--out <path>] [--envelope libraryA|extreme]
    python3 pose_frames.py --selftest        # 工程A 数据自验（只读工程，写临时文件）

确定性：所有 dict 按 key 排序、浮点截到 6 位、条目按 id 排序；同输入两次输出字节一致。
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from unity_yaml import DocIndex, YamlCache  # noqa: E402
import clip_writes as C  # noqa: E402
import muscles as M  # noqa: E402

CLIP_CLASS = C.CLIP_CLASS
TREE_CLASS = C.TREE_CLASS
STATE_CLASS = C.STATE_CLASS
STATE_MACHINE_CLASS = C.STATE_MACHINE_CLASS
CONTROLLER_CLASS = C.CONTROLLER_CLASS

ROUND = 6

# 源定位（各工程一致；工程A 已核）
PROXY_GLOB = "Packages/com.vrchat.avatars/**/ProxyAnim/*.anim"
GM_EMOTE_GLOB = "Packages/*/Resources/Gm/Animations/Emote/*.anim"

# 库 A：03 §8.1 点名的 15 个 SDK proxy 姿势（其余 proxy 是手势/表情/眼动，同样入库存档）
LIB_A_PROXY_POSES: Tuple[str, ...] = (
    "proxy_stand_still", "proxy_tpose", "proxy_crouch_still", "proxy_low_crawl_still",
    "proxy_sit", "proxy_sit2", "proxy_afk",
    "proxy_walk_forward", "proxy_run_forward", "proxy_sprint_forward",
    "proxy_crouch_walk_forward", "proxy_low_crawl_forward",
    "proxy_stand_wave", "proxy_stand_cheer", "proxy_seated_raise_hand",
)

# 库 A：GoGo Loco 固定 7 条（03 §8.1 / F17）
GO_POSE_NAMES: Tuple[str, ...] = (
    "go_sit_crossed_leg", "go_w_sitting_up_low", "go_long_sitting",
    "go_sit_knees_apart_in", "go_laydown_side", "go_sleep_prone_low", "go_stand_wide",
)

# 库 C：GoGo 跳跃 / knockback / afk_idle（03 §8.1；取每个语义最常规的一条，列表写死可复现）
GO_MOTION_NAMES: Tuple[str, ...] = (
    "go_jump_in_place", "go_knockback", "go_manual_afk_idle",
)

# 工程私有：SDK / GoGo 包单独走上面的固定清单，避免库 A 被 308 条 GoGo 撑爆
PRIVATE_EXCLUDE_PREFIXES = (
    "Packages/com.vrchat.avatars/",
    "Packages/gogoloco/",
)

OBSERVATION_MUSCLES: Tuple[str, ...] = (
    "Spine Front-Back", "Chest Front-Back",
    "Left Upper Leg Front-Back", "Right Upper Leg Front-Back",
    "Left Upper Leg In-Out", "Right Upper Leg In-Out",
    "Left Lower Leg Stretch", "Right Lower Leg Stretch",
    "Left Foot Up-Down", "Right Foot Up-Down",
    "Left Arm Down-Up", "Right Arm Down-Up",
    "Left Arm Front-Back", "Right Arm Front-Back",
    "Left Forearm Stretch", "Right Forearm Stretch",
)

MULTIFRAME_DEDUPE_LINF = 0.05
MAX_FRAMES_PER_CLIP = 6


def _r(x) -> float:
    v = round(float(x), ROUND)
    return 0.0 if v == 0 else v


def _rel(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def _sanitize(name: str) -> str:
    """id 化：保留字母数字与 CJK（抱熊/CERP 等中文名不能都塌成 a2）。"""
    s = re.sub(r"[^0-9A-Za-z\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+", "_",
               name or "").strip("_").lower()
    return s or "clip"


# ---------------------------------------------------------------------------
# clip 解析
# ---------------------------------------------------------------------------
class ClipInfo:
    __slots__ = ("path", "name", "stop_time", "muscle_curves", "root_curves",
                 "n_float", "n_generic", "other_attrs", "is_additive", "controller")

    def __init__(self, path, name, stop_time, muscle_curves, root_curves,
                 n_float, n_generic, other_attrs, is_additive=False, controller=""):
        self.path = path
        self.name = name
        self.stop_time = stop_time
        self.muscle_curves = muscle_curves
        self.root_curves = root_curves
        self.n_float = n_float
        self.n_generic = n_generic
        self.other_attrs = other_attrs
        self.is_additive = is_additive
        self.controller = controller

    @property
    def multiframe(self) -> bool:
        return self.stop_time > 1e-9

    def all_times(self) -> List[float]:
        ts = set()
        for ks in list(self.muscle_curves.values()) + list(self.root_curves.values()):
            for t, _v in ks:
                ts.add(round(float(t), ROUND))
        return sorted(ts)

    def muscle_attr_indices(self) -> List[int]:
        """clip 里出现的肌肉序号（按 95 名表），用于与 genericBindings 交叉核对。"""
        return sorted(M.MUSCLE_INDEX[n] for n in self.muscle_curves)


def load_clip_info(path: str, cache: YamlCache,
                   additive: bool = False, controller: str = "") -> Optional[ClipInfo]:
    try:
        docs = cache.load(path)
    except Exception:
        return None
    idx = DocIndex(docs)
    doc = idx.first(CLIP_CLASS)
    if doc is None:
        return None
    settings = doc.get("m_AnimationClipSettings") or {}
    stop = C._num(settings.get("m_StopTime"), 0.0)
    muscle_curves: Dict[str, List[Tuple[float, float]]] = {}
    root_curves: Dict[str, List[Tuple[float, float]]] = {}
    n_float = 0
    other = 0
    for fc in doc.get("m_FloatCurves") or []:
        if not isinstance(fc, dict):
            continue
        n_float += 1
        attr = fc.get("attribute") or ""
        keys = C.curve_keys(fc)
        mname = M.clip_attr_to_muscle(attr)
        if mname:
            muscle_curves.setdefault(mname, keys)
        elif attr.startswith("RootT.") or attr.startswith("RootQ."):
            root_curves.setdefault(attr, keys)
        else:
            other += 1
    gb = (doc.get("m_ClipBindingConstant") or {}).get("genericBindings") or []
    return ClipInfo(path, doc.get("m_Name") or os.path.basename(path), stop,
                    muscle_curves, root_curves, n_float, len(gb), other,
                    additive, controller)


def _eval(keys: Optional[List[Tuple[float, float]]], t: float) -> Optional[float]:
    if not keys:
        return None
    return C._eval_linear(keys, t)


def _root_vec(info: ClipInfo, prefix: str, t: float) -> Optional[List[float]]:
    vals = []
    for c in "xyz":
        v = _eval(info.root_curves.get("%s.%s" % (prefix, c)), t)
        if v is None:
            return None
        vals.append(v)
    return vals


def _root_q(info: ClipInfo, t: float) -> Optional[List[float]]:
    vals = []
    for c in "xyzw":
        v = _eval(info.root_curves.get("RootQ.%s" % c), t)
        if v is None:
            return None
        vals.append(v)
    return vals


# ---------------------------------------------------------------------------
# 帧采样
# ---------------------------------------------------------------------------
def sample_frame(info: ClipInfo, t: float, base_vec: Sequence[float],
                 base_root_t: Sequence[float], base_root_q: Sequence[float],
                 additive: bool) -> dict:
    """在时刻 t 取一帧。additive 时缺曲线取 0（增量语义），否则取 base（=stand_still）。"""
    vec = list(base_vec)
    for nm, ks in info.muscle_curves.items():
        v = _eval(ks, t)
        if v is not None:
            vec[M.MUSCLE_INDEX[nm]] = v
    rv = [0.0, 0.0, 0.0] if additive else list(base_root_t)
    rq = [0.0, 0.0, 0.0, 1.0] if additive else list(base_root_q)
    got = _root_vec(info, "RootT", t)
    if got is not None:
        rv = got
    gotq = _root_q(info, t)
    if gotq is not None:
        rq = gotq
    return {"time": _r(t), "muscles": [_r(v) for v in vec],
            "root_t": [_r(v) for v in rv], "root_q": [_r(v) for v in rq]}


def select_frames(info: ClipInfo, base_vec, base_root_t, base_root_q,
                  additive: bool) -> List[float]:
    """多帧按下行规则选帧；单帧取该帧。返回升序时刻列表。"""
    times = info.all_times()
    if not times:
        return [0.0]
    if not info.multiframe and len(times) == 1:
        return [times[0]]
    cands: List[float] = []
    ry = info.root_curves.get("RootT.y")
    if ry:
        cands.append(min(ry, key=lambda kv: kv[1])[0])
    for nm in ("Left Foot Up-Down", "Right Foot Up-Down"):
        ks = info.muscle_curves.get(nm)
        if ks and len(ks) > 1:
            cands.append(max(ks, key=lambda kv: kv[1])[0])
            cands.append(min(ks, key=lambda kv: kv[1])[0])
    obs = [n for n in OBSERVATION_MUSCLES if n in info.muscle_curves]
    if not obs:
        obs = sorted(info.muscle_curves)
    for nm in obs:
        ks = info.muscle_curves.get(nm)
        if not ks or len(ks) < 2:
            continue
        cands.append(max(ks, key=lambda kv: kv[1])[0])
        cands.append(min(ks, key=lambda kv: kv[1])[0])
    if not cands:
        cands = list(times)
    picked: List[float] = []
    seen: List[List[float]] = []
    for t in cands:
        f = sample_frame(info, t, base_vec, base_root_t, base_root_q, additive)
        v = f["muscles"]
        if any(max(abs(a - b) for a, b in zip(v, s)) < MULTIFRAME_DEDUPE_LINF
               for s in seen):
            continue
        seen.append(v)
        picked.append(round(float(t), ROUND))
        if len(picked) >= MAX_FRAMES_PER_CLIP:
            break
    if not picked:
        picked = [times[0]]
    return sorted(set(picked))


# ---------------------------------------------------------------------------
# 工程私有 clip：描述符 5 层控制器（含 MergeAnimator 并入）
# ---------------------------------------------------------------------------
def _walk_motion(idx: DocIndex, motion: dict, resolver: C.ClipResolver,
                 out: Dict[str, bool], depth: int = 0) -> None:
    if depth > 8 or not motion:
        return
    fid = motion.get("fileID", 0) or 0
    guid = motion.get("guid") or ""
    if guid and guid not in C.ZERO_GUIDS:
        p = resolver.path_for(guid)
        if p:
            out[os.path.abspath(p)] = out.get(os.path.abspath(p), False)
        return
    if not fid:
        return
    doc = idx.by_fid.get(fid)
    if doc is None:
        return
    if doc.class_id == TREE_CLASS:
        for ch in doc.get("m_Children") or []:
            _walk_motion(idx, ch.get("m_Motion") or {}, resolver, out, depth + 1)


def _walk_sm(idx: DocIndex, sm_fid: int, resolver: C.ClipResolver,
             out: Dict[str, bool], seen: set) -> None:
    if not sm_fid or sm_fid in seen:
        return
    seen.add(sm_fid)
    sm = idx.by_fid.get(sm_fid)
    if not sm or sm.class_id != STATE_MACHINE_CLASS:
        return
    for child in sm.get("m_ChildStates") or []:
        st = idx.by_fid.get((child.get("m_State") or {}).get("fileID", 0))
        if st:
            _walk_motion(idx, st.get("m_Motion") or {}, resolver, out)
    for child in sm.get("m_ChildStateMachines") or []:
        _walk_sm(idx, (child.get("m_StateMachine") or {}).get("fileID", 0),
                 resolver, out, seen)


def collect_private_clips(project: str, cache: YamlCache,
                          log=lambda s: None) -> Tuple[dict, List[str]]:
    """返回 ({绝对路径: additive}, [控制器相对路径...])；只取描述符接到的控制器。"""
    import writers_static as W  # 延迟导入：只在需要时建 guid 索引（约 8 s）
    scan = W.ProjectScan(project, cache=cache)
    resolver = C.ClipResolver(project, None)
    out: Dict[str, bool] = {}
    ctrls: List[str] = []
    for ctrl in scan.merged_controllers:
        rel = _rel(ctrl, project)
        if rel.startswith(PRIVATE_EXCLUDE_PREFIXES):
            continue
        ctrls.append(rel)
        try:
            idx = DocIndex(cache.load(ctrl))
        except Exception as e:  # noqa: BLE001
            log("[warn] 控制器解析失败 %s：%r" % (rel, e))
            continue
        for c in idx.all(CONTROLLER_CLASS):
            for layer in c.get("m_AnimatorLayers") or []:
                additive = int(layer.get("m_BlendingMode") or 0) == 1
                layer_out: Dict[str, bool] = {}
                _walk_sm(idx, (layer.get("m_StateMachine") or {}).get("fileID", 0),
                         resolver, layer_out, set())
                for p, _ in layer_out.items():
                    out[p] = out.get(p, False) or additive
    return out, sorted(ctrls)


def _glob_clips(project: str, pattern: str) -> List[str]:
    return sorted(os.path.abspath(p) for p in glob.glob(
        os.path.join(project, pattern), recursive=True))


def _find_go_clip(project: str, name: str) -> Optional[str]:
    hits = _glob_clips(project, "Packages/gogoloco/**/%s.anim" % name)
    return hits[0] if hits else None


# ---------------------------------------------------------------------------
# 建库
# ---------------------------------------------------------------------------
class Builder:
    def __init__(self, project: str, envelope: str = "libraryA", log=lambda s: None,
                 cache: Optional[YamlCache] = None):
        self.project = os.path.abspath(project)
        self.cache = cache or YamlCache()
        self.envelope = envelope
        self.log = log
        self.clips: Dict[str, ClipInfo] = {}
        self.stats: Dict[str, object] = {}
        self.warnings: List[str] = []
        self._multiframe: set = set()

    # -- 载入 -------------------------------------------------------------
    def _info(self, path: str, additive: bool = False, controller: str = "") -> Optional[ClipInfo]:
        key = os.path.abspath(path)
        info = self.clips.get(key)
        if info is None:
            info = load_clip_info(key, self.cache, additive, controller)
            if info is not None:
                if additive:
                    info.is_additive = True
                self.clips[key] = info
        elif additive:
            info.is_additive = True
        return info

    def _resolve(self, info: ClipInfo, base_vec, base_root_t, base_root_q) -> List[dict]:
        frames = []
        for i, t in enumerate(select_frames(info, base_vec, base_root_t, base_root_q,
                                             info.is_additive)):
            f = sample_frame(info, t, base_vec, base_root_t, base_root_q, info.is_additive)
            f["frame"] = i
            frames.append(f)
        return frames

    def build(self) -> dict:
        # --- 基线：proxy_hands_idle（手指缺口用）+ proxy_stand_still（全库基线）
        proxy_files = _glob_clips(self.project, PROXY_GLOB)
        proxy_by_name = {os.path.splitext(os.path.basename(p))[0]: p for p in proxy_files}
        self.stats["proxy_clips"] = len(proxy_files)
        self.stats["proxy_multiframe"] = sorted(
            os.path.splitext(os.path.basename(p))[0][len("proxy_"):]
            for p in proxy_files
            if (self._info(p) is not None and self._info(p).multiframe))

        hands_path = proxy_by_name.get("proxy_hands_idle")
        zero = [0.0] * M.MUSCLE_COUNT
        hands_vec = list(zero)
        if hands_path:
            hinfo = self._info(hands_path)
            if hinfo:
                hf = sample_frame(hinfo, hinfo.all_times()[0] if hinfo.all_times() else 0.0,
                                  zero, [0, 0, 0], [0, 0, 0, 1], False)
                hands_vec = hf["muscles"]
        else:
            self.warnings.append("未找到 proxy_hands_idle，手指缺口只能填 0")
        stand_path = proxy_by_name.get("proxy_stand_still")
        if not stand_path:
            raise SystemExit("找不到 proxy_stand_still（SDK proxy 目录缺）")
        sinfo = self._info(stand_path)
        sframe = sample_frame(sinfo, sinfo.all_times()[0] if sinfo.all_times() else 0.0,
                              zero, [0, 0, 0], [0, 0, 0, 1], False)
        # 身体类 proxy 缺的手指值取 proxy_hands_idle（M1）
        for nm in M.FINGER_MUSCLES:
            if nm not in sinfo.muscle_curves:
                sframe["muscles"][M.MUSCLE_INDEX[nm]] = hands_vec[M.MUSCLE_INDEX[nm]]
        stand_vec = list(sframe["muscles"])
        stand_root_t = list(sframe["root_t"])
        stand_root_q = list(sframe["root_q"])

        # --- 库 A 收集 ---------------------------------------------------
        entries_a: List[dict] = []
        seen_ids: Dict[str, int] = {}

        def add_frames(info: ClipInfo, base_id: str, kind: str, tags: List[str],
                       extra_meta: Optional[dict] = None) -> None:
            if info.multiframe:
                self._multiframe.add(info.name)
            frames = self._resolve(info, stand_vec, stand_root_t, stand_root_q)
            for f in frames:
                pid = base_id if len(frames) == 1 else "%s@%d" % (base_id, f["frame"])
                pid = _dedupe_id(pid, seen_ids)
                vals = {n: f["muscles"][M.MUSCLE_INDEX[n]] for n in M.MUSCLE_NAMES}
                ref = None if info.is_additive else {n: stand_vec[M.MUSCLE_INDEX[n]]
                                                    for n in M.MUSCLE_NAMES}
                entry = {
                    "id": pid,
                    "source": _rel(info.path, self.project),
                    "clip": info.name,
                    "frame": f["frame"],
                    "time": f["time"],
                    "group": "A",
                    "kind": kind,
                    "muscles": f["muscles"],
                    "root_t": f["root_t"],
                    "root_q": f["root_q"],
                    "builtin_params": M.builtin_params_for(pid),
                    "moved_regions": M.moved_regions(vals, ref),
                    "tags": list(tags),
                    "additive": bool(info.is_additive),
                }
                if extra_meta:
                    entry.update(extra_meta)
                entries_a.append(entry)

        for p in proxy_files:
            info = self._info(p)
            if info is None:
                continue
            nm = info.name
            tags = ["proxy"]
            if nm in LIB_A_PROXY_POSES:
                tags.append("library_a_pose")
            add_frames(info, nm, "proxy", tags)

        go_found = []
        for nm in GO_POSE_NAMES:
            p = _find_go_clip(self.project, nm)
            if not p:
                self.warnings.append("gogoloco 缺 %s（未装或改名）" % nm)
                continue
            info = self._info(p)
            if info is None:
                continue
            go_found.append(nm)
            add_frames(info, nm, "gogoloco", ["gogoloco", "library_a_pose"])
        self.stats["gogoloco_clips"] = len(go_found)

        private_map, ctrls = collect_private_clips(self.project, self.cache, self.log)
        priv_used = []
        for p in sorted(private_map):
            relp = _rel(p, self.project)
            if relp.startswith(PRIVATE_EXCLUDE_PREFIXES):
                continue  # 工程控制器引到 SDK/GoGo clip 时不重复计入
            info = self._info(p, additive=private_map[p])
            if info is None or not info.muscle_curves:
                continue
            priv_used.append(relp)
            tags = ["private"]
            if "CERP" in os.path.basename(p):
                tags += ["cerp", "gesture_pose"]
            if "抱熊" in os.path.basename(p):
                tags += ["bearhug"]
            if info.is_additive:
                tags.append("additive")
            else:
                tags.append("library_a_pose")
            add_frames(info, _sanitize(info.name), "private", tags,
                       {"controller": info.controller})
        self.stats["private_controllers"] = ctrls
        self.stats["private_clips"] = priv_used

        # --- 库 B：包络 + 剂量 -------------------------------------------
        env: Dict[str, List[float]] = {n: [] for n in M.MUSCLE_NAMES}
        for e in entries_a:
            if e["additive"]:
                continue
            for i, v in enumerate(e["muscles"]):
                env[M.MUSCLE_NAMES[i]].append(v)
        env_extreme: Dict[Tuple[str, int], Tuple[float, bool]] = {}
        for n in M.MUSCLE_NAMES:
            vals = env[n] or [stand_vec[M.MUSCLE_INDEX[n]]]
            env_extreme[(n, -1)] = (min(vals), False)
            env_extreme[(n, +1)] = (max(vals), False)

        def dose_value(nm: str, direction: int, pct: float) -> Tuple[float, bool]:
            s = stand_vec[M.MUSCLE_INDEX[nm]]
            ext, fallback = env_extreme[(nm, direction)]
            if abs(ext - s) < 1e-6:
                ext, fallback = env_extreme[(nm, -direction)]
                fallback = True
            return s + (pct / 100.0) * (ext - s), fallback

        entries_b: List[dict] = []

        def add_b(pid: str, muscles_vec, tags, moved_ref, extra=None):
            vals = {n: muscles_vec[M.MUSCLE_INDEX[n]] for n in M.MUSCLE_NAMES}
            entries_b.append({
                "id": pid,
                "source": "synthetic:libraryB",
                "clip": pid,
                "frame": 0,
                "time": 0.0,
                "group": "B",
                "kind": "sweep" if not pid.startswith("B_combo") else "combo",
                "muscles": [_r(v) for v in muscles_vec],
                "root_t": [_r(v) for v in stand_root_t],
                "root_q": [_r(v) for v in stand_root_q],
                "builtin_params": M.builtin_params_for(pid),
                "moved_regions": M.moved_regions(vals, moved_ref),
                "tags": list(tags),
                "additive": False,
            })
            if extra:
                entries_b[-1].update(extra)

        fallbacks: List[str] = []
        for scan in M.JOINT_SCANS:
            sides = ("L", "R") if scan["sided"] else ("C",)
            for side in sides:
                names = scan["muscles"][side]
                for dose in M.DOSE_STEPS:
                    vec = list(stand_vec)
                    for nm in names:
                        v, fb = dose_value(nm, scan["dir"], dose)
                        vec[M.MUSCLE_INDEX[nm]] = v
                        if fb:
                            fallbacks.append("%s/%s/%d" % (scan["id"], nm, dose))
                    pid = "B_%s_%s_%d" % (scan["id"], side, dose)
                    add_b(pid, vec, ["sweep", scan["id"], scan["region"], "dose_%d" % dose],
                          {n: stand_vec[M.MUSCLE_INDEX[n]] for n in M.MUSCLE_NAMES},
                          {"joint": scan["id"], "side": side, "dose": dose})
        for combo in M.COMBOS:
            vec = list(stand_vec)
            for jid, dose in combo["doses"].items():
                scan = next(s for s in M.JOINT_SCANS if s["id"] == jid)
                sides = ("L", "R") if scan["sided"] else ("C",)
                for side in sides:
                    for nm in scan["muscles"][side]:
                        v, fb = dose_value(nm, scan["dir"], dose)
                        vec[M.MUSCLE_INDEX[nm]] = v
                        if fb:
                            fallbacks.append("%s/%s/%d" % (jid, nm, dose))
            add_b("B_%s" % combo["id"], vec,
                  ["combo", combo["id"]] + ["dose_%d" % d for d in combo["doses"].values()],
                  {n: stand_vec[M.MUSCLE_INDEX[n]] for n in M.MUSCLE_NAMES},
                  {"combo": combo["id"], "doses": combo["doses"]})
        self.stats["envelope_fallbacks"] = sorted(set(fallbacks))

        # extreme 档：±1（默认不生成；P13 advisory）
        if self.envelope == "extreme":
            for scan in M.JOINT_SCANS:
                sides = ("L", "R") if scan["sided"] else ("C",)
                for side in sides:
                    for sign in (-1, 1):
                        vec = list(stand_vec)
                        for nm in scan["muscles"][side]:
                            vec[M.MUSCLE_INDEX[nm]] = float(sign)
                        add_b("B_%s_%s_extreme_%s" % (scan["id"], side,
                                                      "m1" if sign < 0 else "p1"),
                              vec, ["sweep", "extreme", scan["id"], scan["region"]],
                              {n: stand_vec[M.MUSCLE_INDEX[n]] for n in M.MUSCLE_NAMES},
                              {"joint": scan["id"], "side": side, "extreme": sign})

        # --- 库 C：真动作 clip -------------------------------------------
        entries_c: List[dict] = []
        seen_c: Dict[str, int] = {}

        def add_c(info: ClipInfo, base_id: str, kind: str, tags: List[str]) -> None:
            frames = self._resolve(info, stand_vec, stand_root_t, stand_root_q)
            for f in frames:
                pid = base_id if len(frames) == 1 else "%s@%d" % (base_id, f["frame"])
                pid = _dedupe_id(pid, seen_c)
                vals = {n: f["muscles"][M.MUSCLE_INDEX[n]] for n in M.MUSCLE_NAMES}
                ref = None if info.is_additive else {
                    n: stand_vec[M.MUSCLE_INDEX[n]] for n in M.MUSCLE_NAMES}
                entries_c.append({
                    "id": pid, "source": _rel(info.path, self.project),
                    "clip": info.name, "frame": f["frame"], "time": f["time"],
                    "group": "C", "kind": kind, "muscles": f["muscles"],
                    "root_t": f["root_t"], "root_q": f["root_q"],
                    "builtin_params": M.builtin_params_for(pid),
                    "moved_regions": M.moved_regions(vals, ref),
                    "tags": list(tags), "additive": bool(info.is_additive),
                })

        emote_files = _glob_clips(self.project, GM_EMOTE_GLOB)
        for p in emote_files:
            info = self._info(p)
            if info is None:
                continue
            add_c(info, "C_emote_" + _sanitize(info.name), "emote", ["emote", "gesturemanager"])
        go_motion_found = []
        for nm in GO_MOTION_NAMES:
            p = _find_go_clip(self.project, nm)
            if not p:
                self.warnings.append("gogoloco 动作缺 %s" % nm)
                continue
            info = self._info(p)
            if info is None:
                continue
            go_motion_found.append(nm)
            add_c(info, "C_" + nm, "motion", ["gogoloco", "motion"])
        extra = self._extra_clips()
        for p in extra:
            ap = p if os.path.isabs(p) else os.path.join(self.project, p)
            if not os.path.exists(ap):
                self.warnings.append("poses.extra_clips 不存在：%s" % p)
                continue
            info = self._info(ap)
            if info is None:
                continue
            add_c(info, "C_extra_" + _sanitize(info.name), "extra", ["user", "extra"])

        self.stats["gm_emote_clips"] = len(emote_files)
        self.stats["gogoloco_motion_clips"] = go_motion_found
        self.stats["extra_clips"] = [p for p in extra]

        entries_a.sort(key=lambda e: e["id"])
        entries_b.sort(key=lambda e: e["id"])
        entries_c.sort(key=lambda e: e["id"])
        self.stats["library_A_entries"] = len(entries_a)
        self.stats["library_B_entries"] = len(entries_b)
        self.stats["library_C_entries"] = len(entries_c)
        self.stats["multiframe_clips"] = sorted(self._multiframe)

        return {
            "schema": "pose_library/1",
            "project": os.path.basename(self.project),
            "source": "pose_frames.py (T-26)",
            "muscle_names": list(M.MUSCLE_NAMES),
            "envelope": self.envelope,
            "libraries": {"A": entries_a, "B": entries_b, "C": entries_c},
            "stats": self.stats,
            "warnings": sorted(set(self.warnings)),
        }

    def _extra_clips(self) -> List[str]:
        decl = os.path.join(self.project, "_感知", "声明.yaml")
        if not os.path.exists(decl):
            return []
        try:
            import yaml  # type: ignore
            with open(decl, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return []
        poses = data.get("poses") or {}
        out = poses.get("extra_clips") or []
        return [str(x) for x in out] if isinstance(out, list) else []


def _dedupe_id(pid: str, seen: Dict[str, int]) -> str:
    n = seen.get(pid, 0)
    seen[pid] = n + 1
    return pid if n == 0 else "%s_%d" % (pid, n)


def dump_library(lib: dict) -> str:
    return json.dumps(lib, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def write_library(lib: dict, out_path: str) -> None:
    d = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(d, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(dump_library(lib))


# ---------------------------------------------------------------------------
# 自验
# ---------------------------------------------------------------------------
def _lib_by_id(lib: dict) -> Dict[str, dict]:
    out = {}
    for g in ("A", "B", "C"):
        for e in lib["libraries"][g]:
            out.setdefault(e["id"], e)
    return out


def selftest() -> int:
    project = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "..",
                                           "工程A"))
    if not os.path.isdir(project):
        print("[FAIL] 找不到 工程A 工程：%s" % project)
        return 2
    fails: List[str] = []
    notes: List[str] = []

    b = Builder(project)
    lib = b.build()
    ids = _lib_by_id(lib)
    st = lib["stats"]

    # 1) proxy 79 + 4 条多帧
    if st["proxy_clips"] != 79:
        fails.append("proxy 应 79 条，实际 %s" % st["proxy_clips"])
    want_mf = ["empty", "hands_idle2", "landing", "rotate90_right"]
    if list(st["proxy_multiframe"]) != want_mf:
        fails.append("proxy 多帧应 %r，实际 %r" % (want_mf, st["proxy_multiframe"]))

    # 2) 肌肉序号 vs genericBindings（attribute == 序号+42）
    #    注：`m_FloatCurves` 条数并不总等于 genericBindings 条数——后者会含没有 float 曲线的
    #    常量绑定（本工程 proxy 里 attribute=1/2 各若干条），所以判据取**肌肉序号集合相等**。
    mismatches = []
    count_diffs = []
    for p in _glob_clips(project, PROXY_GLOB):
        info = b._info(p)
        if info is None or info.n_generic == 0:
            continue
        if info.n_float != info.n_generic:
            count_diffs.append("%s %d/%d" % (info.name, info.n_float, info.n_generic))
        gb_idx = set()
        for g in (DocIndex(b.cache.load(p)).first(CLIP_CLASS).get(
                "m_ClipBindingConstant") or {}).get("genericBindings") or []:
            a = int(g.get("attribute") or 0)
            if M.CLIP_ATTR_MUSCLE_OFFSET <= a <= 94 + M.CLIP_ATTR_MUSCLE_OFFSET:
                gb_idx.add(a - M.CLIP_ATTR_MUSCLE_OFFSET)
        got = set(info.muscle_attr_indices())
        if got != gb_idx:
            mismatches.append("%s 名称序号≠genericBindings：多 %r 少 %r"
                              % (info.name, sorted(got - gb_idx)[:4],
                                 sorted(gb_idx - got)[:4]))
    if mismatches:
        fails.append("肌肉序号核对失败：%s" % "; ".join(mismatches[:3]))
    else:
        notes.append("95 名序号与 proxy genericBindings 的肌肉集合逐 clip 相等")
    if count_diffs:
        notes.append("m_FloatCurves≠genericBindings 条数的 proxy（多常量绑定）：%s"
                     % ", ".join(count_diffs))
    else:
        notes.append("proxy m_FloatCurves 条数 == genericBindings 条数（全部）")

    # 3) stand_still / crouch_still 抽值
    ss = ids.get("proxy_stand_still")
    if not ss:
        fails.append("库 A 缺 proxy_stand_still")
    else:
        v = ss["muscles"]
        for nm, want in (("Left Upper Leg Front-Back", 0.633),
                         ("Left Lower Leg Stretch", 1.039)):
            got = v[M.MUSCLE_INDEX[nm]]
            if abs(got - want) > 0.002:
                fails.append("stand_still %s 应≈%.3f，实际 %.4f" % (nm, want, got))
        if abs(ss["root_t"][1] - 0.946) > 0.002:
            fails.append("stand_still root_t[1] 应≈0.946，实际 %.4f" % ss["root_t"][1])
        if ss["moved_regions"]:
            fails.append("stand_still moved_regions 应为空，实际 %r" % ss["moved_regions"])
    cs = ids.get("proxy_crouch_still")
    if not cs:
        fails.append("库 A 缺 proxy_crouch_still")
    else:
        want_q = [0.483, 0.006, -0.018, 0.87]
        if max(abs(a - c) for a, c in zip(cs["root_q"], want_q)) > 0.01:
            fails.append("crouch_still root_q 应≈%r，实际 %r" % (want_q, cs["root_q"]))

    # 15 个点名 proxy 姿势：基线 stand_still 恰 49 身体肌肉 + 7 Root；
    # 其余 proxy 含眼/颌或省略部分肌肉，只要求名字能全部落进 95 名表。
    proxy_by_name = {os.path.splitext(os.path.basename(p))[0]:
                     b._info(p) for p in _glob_clips(project, PROXY_GLOB)}
    ss_info = proxy_by_name.get("proxy_stand_still")
    if ss_info is None:
        fails.append("缺 proxy_stand_still")
    else:
        body = sum(1 for n in ss_info.muscle_curves if n in M.BODY_MUSCLES)
        if body != 49 or len(ss_info.root_curves) != 7:
            fails.append("stand_still 应 49 身体肌肉 + 7 Root，实际 %d + %d"
                         % (body, len(ss_info.root_curves)))
    for nm in LIB_A_PROXY_POSES:
        info = proxy_by_name.get(nm)
        if info is None:
            fails.append("缺 proxy 姿势 %s" % nm)
            continue
        if not info.muscle_curves:
            fails.append("%s 无肌肉曲线" % nm)

    # 4) sit 含 thigh/knee
    sit = ids.get("proxy_sit")
    if not sit:
        fails.append("库 A 缺 proxy_sit")
    elif not ({"thigh", "knee"} <= set(sit["moved_regions"])):
        fails.append("sit moved_regions 应含 thigh/knee，实际 %r" % sit["moved_regions"])

    # 5) GoGo 7
    for nm in GO_POSE_NAMES:
        if nm not in ids:
            fails.append("库 A 缺 GoGo %s" % nm)

    # 6) CERP Pose 1..11
    for i in range(1, 12):
        hit = [e for e in lib["libraries"]["A"]
               if re.match(r"^cerp_pose_%d(@|_|$)" % i, e["id"])]
        if not hit:
            fails.append("库 A 缺 CERP Pose %d" % i)

    # 7) 抱熊 additive
    bh = [e for e in lib["libraries"]["A"] if "抱熊" in (e["source"] or "")]
    if not any(e["additive"] for e in bh):
        fails.append("抱熊 加算差值 未标 additive:true（命中 %r）" % [e["id"] for e in bh])

    # 8) GM 16 emote，各 ≤6 帧
    gm = [e for e in lib["libraries"]["C"] if "gesture-manager" in (e["source"] or "")]
    if st["gm_emote_clips"] != 16:
        fails.append("GM 表情应 16 clip，实际 %s" % st["gm_emote_clips"])
    per = {}
    for e in gm:
        per[e["clip"]] = per.get(e["clip"], 0) + 1
    over = {k: v for k, v in per.items() if v > MAX_FRAMES_PER_CLIP}
    if len(per) != 16 or over:
        fails.append("GM 表情帧选择异常：clip=%d over=%r" % (len(per), over))

    # 9) 库 B 66 + 25% 不是半蹲
    if st["library_B_entries"] != 66:
        fails.append("库 B 应 66 条，实际 %s" % st["library_B_entries"])
    hip25 = ids.get("B_hip_fb_L_25")
    if not hip25:
        fails.append("库 B 缺 B_hip_fb_L_25")
    else:
        s = ss["muscles"][M.MUSCLE_INDEX["Left Upper Leg Front-Back"]]
        e = ids["B_hip_fb_L_100"]["muscles"][M.MUSCLE_INDEX["Left Upper Leg Front-Back"]]
        g = hip25["muscles"][M.MUSCLE_INDEX["Left Upper Leg Front-Back"]]
        if not (min(s, e) < g < max(s, e)):
            fails.append("库 B 髋 25%% 应介于 stand(%.3f) 与 100%%(%.3f) 之间，实际 %.3f"
                         % (s, e, g))

    # 10) 两次输出字节一致（共用 YamlCache，只重跑装配）
    b2 = Builder(project, cache=b.cache)
    lib2 = b2.build()
    if dump_library(lib) != dump_library(lib2):
        fails.append("两次构建输出不一致（非确定性）")

    # 11) 缺一指（空 clip 仍应为 1 帧）
    if "proxy_empty" not in ids:
        fails.append("库 A 缺 proxy_empty")

    print("[stats] proxy=%s multiframe=%s A=%s B=%s C=%s"
          % (st["proxy_clips"], st["proxy_multiframe"],
             st["library_A_entries"], st["library_B_entries"], st["library_C_entries"]))
    print("[stats] private_clips=%d controllers=%d" % (
        len(st["private_clips"]), len(st["private_controllers"])))
    print("[stats] go=%s motion=%s gm=%s extra=%s"
          % (st["gogoloco_clips"], st["gogoloco_motion_clips"],
             st["gm_emote_clips"], st["extra_clips"]))
    if st.get("envelope_fallbacks"):
        notes.append("包络换向：%s" % st["envelope_fallbacks"])
    if lib["warnings"]:
        notes.append("warnings: %s" % lib["warnings"])
    for n in notes:
        print("[note] %s" % n)
    if fails:
        for f in fails:
            print("[FAIL] %s" % f)
        return 1
    print("[selftest] pose_frames OK（工程A：库 A/B/C 与 95 名序号、抽值、确定性全过）")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="姿势帧库（T-26）")
    ap.add_argument("--project", default=os.path.abspath(os.path.join(
        _HERE, "..", "..", "..", "..", "工程A")))
    ap.add_argument("--out", default=None)
    ap.add_argument("--envelope", choices=("libraryA", "extreme"), default="libraryA")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    project = os.path.abspath(args.project)
    out = args.out or os.path.join(project, "_感知", "out", "pose_library.json")
    b = Builder(project, envelope=args.envelope, log=lambda s: print(s))
    lib = b.build()
    write_library(lib, out)
    print("[pose_frames] 写出 %s（A=%d B=%d C=%d）"
          % (out, lib["stats"]["library_A_entries"],
             lib["stats"]["library_B_entries"], lib["stats"]["library_C_entries"]))
    for w in lib["warnings"]:
        print("[warn] %s" % w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
