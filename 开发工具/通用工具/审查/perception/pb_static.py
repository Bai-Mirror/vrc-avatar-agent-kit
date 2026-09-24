# -*- coding: utf-8 -*-
"""pb_static.py — PhysBone 静态清单与 U7（T-30，04 第一期开工清单 §T-30）。
【项目沉淀】通用工具
适用素体：无关
相关素材：工程场景/预制体 PhysBone
工具链　：Python 3 + PyYAML（离线）
可复用性：★★ 审查工具链的一环
用途　　：PhysBone 静态清单与 U7 判据：解析 VRCPhysBone/Collider，算每个覆盖件的链与碰撞体。


任务（04 §T-30）
----------------
解析场景/prefab（含 `m_AddedComponents`，只算活跃头像根）的 `VRCPhysBone` /
`VRCPhysBoneCollider`：根骨、链上骨、`colliders` 引用、`immobile/immobileType`、
`isAnimated`、`resetWhenDisabled` 当前值；根骨→部位（父链映射）；对每个声明覆盖件给
`pb: {has_pb, chains[], colliders_on_regions[]}`（T-27 settle 收敛只看 `chains[]`）。
U7：覆盖区域 R 的 PB 缺 R 关节链上骨的碰撞体 → `pb_no_collider(R)`。
输出 `_感知/out/pb.json`；`--diff` 比对 T-27 导出的运行时 PB 表（M6）。

判据（03 §8.3）
--------------
- `rigid` 对配碰撞体的裙会多报；`settle` 才是主口径。这里只做**静态**清单与归因线索。
- U7 **不单独判违例**，只作归因线索（缺碰撞体 → PB 兜不住 → rigid/settle 差异可解释）。

离线限制（重要，写进输出 `warnings`）
------------------------------------
Unity 把 FBX 内的节点名只存在**二进制 FBX** 里；prefab/场景 YAML 里对这些节点只有
`stripped`（`m_CorrespondingSourceObject` 指向 .fbx）的引用，`.fbx.meta` 的
`internalIDToNameTable` 为空。因此：**prefab 内出自 FBX 的骨/链节点拿不到名字**，
本脚本用 `#<fileID>` 占位（字段 `name_source: "placeholder"`），链退化为
`[自身]`。场景里被工具改活（real GO）的对象能拿到真名。运行时真名由 T-27 在 Unity
里导出、经 `--diff` 与本表对齐（M6，正是本设计存在的原因）。

    python3 pb_static.py --project <工程根> [--scene ...] [--decl ...] [--out ...]
    python3 pb_static.py --project <工程根> --diff <runtime.json> [--out ...]
    python3 pb_static.py --selftest            # 工程A 数据自验（只读工程）

依赖：PyYAML（复用 `unity_yaml.py`）。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from unity_yaml import (  # noqa: E402
    DocIndex,
    UnityDoc,
    YamlCache,
    build_guid_index,
)

# VRC.SDK3.Dynamics.PhysBone.dll（7 单同一 md5，F20）
PB_GUID = "2a2c05204084d904aa4945ccff20d8e5"
PB_FILEID = 1661641543          # VRCPhysBone 类
PB_COLLIDER_FILEID = -1631200402  # VRCPhysBoneCollider 类

MONO_CLASS = 114
GAMEOBJECT_CLASS = 1
TRANSFORM_CLASS = 4
PREFAB_INSTANCE_CLASS = 1001
ANIMATOR_CLASS = 95

DEFAULT_OUT = ("_感知", "out", "pb.json")

# 人体骨链（region -> 允许的「同链」region）。U7 判「R 关节链上骨」用：
# 碰撞体根骨的 region 落在该集合里，就算覆盖了 R。数值来自 Unity HumanBodyBones
# 的层级关系（03 §8.3 例子：裙→大腿，袖→上臂/前臂）。
REGION_CHAIN: Dict[str, Set[str]] = {
    "Hips": {"Hips", "Spine"},
    "Spine": {"Spine", "Chest", "Hips"},
    "Chest": {"Chest", "UpperChest", "Spine"},
    "UpperChest": {"UpperChest", "Chest", "Neck"},
    "Neck": {"Neck", "Head", "UpperChest"},
    "Head": {"Head", "Neck"},
    "LeftShoulder": {"LeftShoulder", "LeftUpperArm", "UpperChest"},
    "RightShoulder": {"RightShoulder", "RightUpperArm", "UpperChest"},
    "LeftUpperArm": {"LeftUpperArm", "LeftLowerArm", "LeftShoulder"},
    "RightUpperArm": {"RightUpperArm", "RightLowerArm", "RightShoulder"},
    "LeftLowerArm": {"LeftLowerArm", "LeftHand", "LeftUpperArm"},
    "RightLowerArm": {"RightLowerArm", "RightHand", "RightUpperArm"},
    "LeftHand": {"LeftHand", "LeftLowerArm"},
    "RightHand": {"RightHand", "RightLowerArm"},
    "LeftUpperLeg": {"LeftUpperLeg", "LeftLowerLeg", "Hips"},
    "RightUpperLeg": {"RightUpperLeg", "RightLowerLeg", "Hips"},
    "LeftLowerLeg": {"LeftLowerLeg", "LeftFoot", "LeftUpperLeg"},
    "RightLowerLeg": {"RightLowerLeg", "RightFoot", "RightUpperLeg"},
    "LeftFoot": {"LeftFoot", "LeftToes", "LeftLowerLeg"},
    "RightFoot": {"RightFoot", "RightToes", "RightLowerLeg"},
    "LeftToes": {"LeftToes", "LeftFoot"},
    "RightToes": {"RightToes", "RightFoot"},
}
# 脚子部位归到所在脚
FOOT_SUB_REGION = {
    "LeftFoot.forefoot": "LeftFoot", "LeftFoot.arch": "LeftFoot",
    "LeftFoot.heel": "LeftFoot", "LeftFoot.ankle": "LeftFoot",
    "RightFoot.forefoot": "RightFoot", "RightFoot.arch": "RightFoot",
    "RightFoot.heel": "RightFoot", "RightFoot.ankle": "RightFoot",
}

HUMANOID_NAMES = set(REGION_CHAIN) | {
    "LeftEye", "RightEye", "Jaw",
    "LeftThumbProximal", "LeftThumbIntermediate", "LeftThumbDistal",
    "LeftIndexProximal", "LeftIndexIntermediate", "LeftIndexDistal",
    "LeftMiddleProximal", "LeftMiddleIntermediate", "LeftMiddleDistal",
    "LeftRingProximal", "LeftRingIntermediate", "LeftRingDistal",
    "LeftLittleProximal", "LeftLittleIntermediate", "LeftLittleDistal",
    "RightThumbProximal", "RightThumbIntermediate", "RightThumbDistal",
    "RightIndexProximal", "RightIndexIntermediate", "RightIndexDistal",
    "RightMiddleProximal", "RightMiddleIntermediate", "RightMiddleDistal",
    "RightRingProximal", "RightRingIntermediate", "RightRingDistal",
    "RightLittleProximal", "RightLittleIntermediate", "RightLittleDistal",
}


def _rel(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def _join(prefix: str, path: str) -> str:
    path = (path or "").strip("/")
    if not prefix:
        return path
    return (prefix.rstrip("/") + "/" + path) if path else prefix.rstrip("/")


def _fid(ref) -> int:
    if isinstance(ref, dict):
        try:
            return int(ref.get("fileID", 0) or 0)
        except (TypeError, ValueError):
            return 0
    if isinstance(ref, int):
        return ref
    return 0


# ---------------------------------------------------------------------------
# 每个文件内的对象树（名字 / 父链 / 子链）
# ---------------------------------------------------------------------------
class LocalTree:
    """一篇 Unity YAML 内的 GO/Transform 树，用于路径与 region 推断。

    `stripped` 节点（出自 FBX/prefab）没有名字与本地 Transform，退化为占位。
    """

    def __init__(self, docs: Sequence[UnityDoc]):
        self.idx = DocIndex(docs)
        self.tf_go: Dict[int, int] = {}
        self.go_tf: Dict[int, int] = {}
        self.children: Dict[int, List[int]] = {}
        for d in self.idx.all(TRANSFORM_CLASS):
            g = _fid(d.get("m_GameObject"))
            self.tf_go[d.file_id] = g
            if g:
                self.go_tf[g] = d.file_id
            for ch in (d.get("m_Children") or []):
                self.children.setdefault(d.file_id, []).append(_fid(ch))
        self._path_cache: Dict[int, str] = {}
        self._name_cache: Dict[int, Tuple[str, str]] = {}

    def go_name(self, go_fid: int) -> Tuple[Optional[str], str]:
        """返回 (名字, 来源)。来源 ∈ file|placeholder|none。"""
        if go_fid in self._name_cache:
            return self._name_cache[go_fid]
        d = self.idx.by_fid.get(go_fid)
        out: Tuple[Optional[str], str] = (None, "none")
        if d is not None and d.class_id == GAMEOBJECT_CLASS:
            if not d.stripped and d.get("m_Name"):
                out = (d.get("m_Name"), "file")
            else:
                out = (None, "placeholder")
        self._name_cache[go_fid] = out
        return out

    def tf_name(self, tf_fid: int) -> Tuple[Optional[str], str]:
        return self.go_name(self.tf_go.get(tf_fid, 0))

    def tf_path(self, tf_fid: int) -> str:
        if tf_fid in self._path_cache:
            return self._path_cache[tf_fid]
        segs: List[str] = []
        seen: Set[int] = set()
        cur = tf_fid
        while cur and cur not in seen:
            seen.add(cur)
            name, src = self.tf_name(cur)
            segs.append(name if (name and src == "file") else "#%d" % cur)
            d = self.idx.by_fid.get(cur)
            if d is None or d.class_id != TRANSFORM_CLASS:
                break
            cur = _fid(d.get("m_Father"))
        path = "/".join(reversed(segs))
        self._path_cache[tf_fid] = path
        return path

    def go_path(self, go_fid: int) -> str:
        tf = self.go_tf.get(go_fid)
        if tf is None:
            name, src = self.go_name(go_fid)
            return name if (name and src == "file") else ("#%d" % go_fid if go_fid else "")
        return self.tf_path(tf)

    def descendants(self, tf_fid: int, limit: int = 64) -> List[int]:
        """沿 m_Children 线性/分支收集后代；链式 PB 用前 limit 个。"""
        out: List[int] = []
        stack = list(self.children.get(tf_fid, []))
        seen = {tf_fid}
        while stack and len(out) < limit:
            cur = stack.pop(0)
            if cur in seen:
                continue
            seen.add(cur)
            out.append(cur)
            stack.extend(self.children.get(cur, []))
        return out


# ---------------------------------------------------------------------------
# 记录
# ---------------------------------------------------------------------------
@dataclass
class PbRecord:
    file: str
    file_id: int
    game_object_path: str
    root_path: str
    chain: List[str] = field(default_factory=list)
    colliders: List[str] = field(default_factory=list)
    colliders_on_regions: List[str] = field(default_factory=list)
    region: Optional[str] = None
    region_chain: List[str] = field(default_factory=list)
    name_source: str = "placeholder"
    enabled: bool = True
    immobile: Optional[float] = None
    immobile_type: Optional[int] = None
    is_animated: Optional[int] = None
    reset_when_disabled: Optional[int] = None
    allow_collision: Optional[int] = None
    source_prefab: Optional[str] = None
    instance: str = ""

    def key(self) -> str:
        return "%s#%d@%s" % (self.file, self.file_id, self.instance)


@dataclass
class ColliderRecord:
    file: str
    file_id: int
    game_object_path: str
    root_path: str
    region: Optional[str] = None
    name_source: str = "placeholder"
    shape_type: Optional[int] = None
    radius: Optional[float] = None
    height: Optional[float] = None
    inside_bounds: Optional[int] = None
    enabled: bool = True
    source_prefab: Optional[str] = None
    instance: str = ""

    def key(self) -> str:
        return "%s#%d@%s" % (self.file, self.file_id, self.instance)


# ---------------------------------------------------------------------------
# 工程扫描
# ---------------------------------------------------------------------------
class PbScan:
    def __init__(self, project: str, scene: Optional[str] = None,
                 cache: Optional[YamlCache] = None):
        self.project = os.path.abspath(project)
        self.cache = cache or YamlCache()
        self.guid = build_guid_index(self.project, ["Packages"])
        self.scene_path = os.path.abspath(scene) if scene else self.detect_scene()
        self.scene_idx = DocIndex(self.cache.load(self.scene_path))
        self.warnings: List[str] = []
        self._tree_cache: Dict[str, LocalTree] = {}
        self._idx_cache: Dict[str, Optional[DocIndex]] = {}
        self._human_map: Dict[str, str] = {}     # boneName -> humanName
        self._skeleton: Dict[str, str] = {}      # name -> parentName
        self._human_loaded = False

    # -- 定位 -------------------------------------------------------------
    def detect_scene(self) -> str:
        best, best_score = None, -1
        for dirpath, dirnames, filenames in os.walk(os.path.join(self.project, "Assets")):
            dirnames[:] = [d for d in dirnames if d not in ("Library", "Temp", "obj", ".git")]
            for fn in filenames:
                if not fn.endswith(".unity"):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        score = sum(1 for line in f if line.startswith("--- !u!1001"))
                except OSError:
                    continue
                if score > best_score or (score == best_score and best and
                                          os.path.getsize(p) > os.path.getsize(best)):
                    best, best_score = p, score
        if not best:
            raise SystemExit("找不到任何 .unity 场景，请用 --scene 指定")
        return best

    def tree(self, path: str) -> LocalTree:
        key = os.path.abspath(path)
        if key not in self._tree_cache:
            self._tree_cache[key] = LocalTree(self.cache.load(key))
        return self._tree_cache[key]

    def _has_descriptor(self, prefab_path: str) -> bool:
        try:
            idx = DocIndex(self.cache.load(prefab_path))
        except Exception:  # noqa: BLE001
            return False
        for d in idx.all(MONO_CLASS):
            if "ViewPosition" in d.data and "baseAnimationLayers" in d.data:
                return True
        return False

    def avatar_instance(self, pi_doc: UnityDoc) -> Optional[str]:
        g = (pi_doc.get("m_SourcePrefab") or {}).get("guid")
        p = self.guid.get(g or "")
        if p and p.endswith(".prefab") and self._has_descriptor(p):
            return p
        return None

    def active_avatar_instances(self) -> List[UnityDoc]:
        """场景根上、源 prefab 带头像描述符、且未被 m_IsActive=0 关掉的实例。"""
        out = []
        for d in self.scene_idx.all(PREFAB_INSTANCE_CLASS):
            mod = d.get("m_Modification") or {}
            parent = _fid(mod.get("m_TransformParent"))
            if parent != 0:
                continue
            src = self.avatar_instance(d)
            if not src:
                continue
            if self._instance_active(d, src):
                out.append(d)
            else:
                self.warnings.append("跳过非活跃头像根：%s（PI %d）"
                                     % (os.path.basename(src), d.file_id))
        return out

    def _instance_active(self, pi_doc: UnityDoc, src_path: str) -> bool:
        """读 m_Modifications 里针对源 prefab 头像根 GO 的 m_IsActive。

        根 GO 取带头像描述符的那个（VRCAvatarDescriptor 挂在根上；FBX 变体 prefab 的
        根 Transform 常是 stripped，拿不到 GO，所以不能只看 m_Father==0）。
        """
        src_idx = DocIndex(self.cache.load(src_path))
        root_go = None
        for d in src_idx.all(MONO_CLASS):
            if "ViewPosition" in d.data and "baseAnimationLayers" in d.data:
                root_go = _fid(d.get("m_GameObject"))
                break
        if root_go is None:
            tree = self.tree(src_path)
            for t in src_idx.all(TRANSFORM_CLASS):
                if _fid(t.get("m_Father")) == 0 and tree.tf_go.get(t.file_id):
                    root_go = tree.tf_go[t.file_id]
                    break
        mods = (pi_doc.get("m_Modification") or {}).get("m_Modifications") or []
        active = True
        for m in mods:
            if (m.get("propertyPath") or "") != "m_IsActive":
                continue
            if _fid(m.get("target")) != root_go:
                continue
            try:
                active = int(float(m.get("value", 1))) != 0
            except (TypeError, ValueError):
                pass
        return active

    def detect_avatar_prefab(self) -> Optional[str]:
        for d in self.active_avatar_instances():
            p = self.avatar_instance(d)
            if p:
                return p
        for d in self.scene_idx.all(PREFAB_INSTANCE_CLASS):
            p = self.avatar_instance(d)
            if p:
                return p
        return None

    # -- 人体映射 ---------------------------------------------------------
    def humanoid_map(self, avatar_prefab: Optional[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        if self._human_loaded:
            return self._human_map, self._skeleton
        self._human_loaded = True
        if not avatar_prefab:
            return self._human_map, self._skeleton
        idx = DocIndex(self.cache.load(avatar_prefab))
        avatar_ref = None
        for d in idx.all(ANIMATOR_CLASS):
            av = d.get("m_Avatar") or {}
            if av.get("guid"):
                avatar_ref = av
                break
        if not avatar_ref:
            return self._human_map, self._skeleton
        src = self.guid.get(avatar_ref.get("guid"))
        if not src:
            return self._human_map, self._skeleton
        if src.endswith((".fbx", ".FBX", ".obj", ".model")):
            meta = src + ".meta"
            if os.path.exists(meta):
                self._parse_human_meta(meta)
        return self._human_map, self._skeleton

    def _parse_human_meta(self, meta_path: str) -> None:
        try:
            with open(meta_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            return
        # humanDescription.human: - boneName: X / humanName: Y
        for m in re.finditer(
                r"-\s*boneName:[ \t]*(\S+)[ \t]*\n[ \t]*humanName:[ \t]*(\S+)", text):
            self._human_map[m.group(1)] = m.group(2)
        # skeleton: - name: X / parentName: Y（humanDescription 下的 4 空格键）
        m = re.search(
            r"\n    skeleton:\n(.*?)(?=\n    [A-Za-z_]|\n  [A-Za-z_]|\Z)",
            text, re.S)
        if m:
            for mm in re.finditer(
                    r"-\s*name:[ \t]*(.*?)\n[ \t]*parentName:[ \t]*(.*?)\n",
                    m.group(1)):
                self._skeleton[mm.group(1).strip()] = mm.group(2).strip()

    def _region_by_name(self, name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        if name in HUMANOID_NAMES:
            return name
        if name in self._human_map:
            return self._human_map[name]
        # 沿 skeleton 父链上溯找第一个人形骨
        cur = name
        seen = set()
        while cur and cur not in seen:
            seen.add(cur)
            if cur in self._human_map:
                return self._human_map[cur]
            if cur in HUMANOID_NAMES:
                return cur
            cur = self._skeleton.get(cur)
        return None

    def region_of_tf(self, tree: LocalTree, tf_fid: int) -> Optional[str]:
        cur = tf_fid
        seen = set()
        while cur and cur not in seen:
            seen.add(cur)
            name, src = tree.tf_name(cur)
            if name:
                r = self._region_by_name(name)
                if r:
                    return r
            d = tree.idx.by_fid.get(cur)
            if d is None or d.class_id != TRANSFORM_CLASS:
                break
            cur = _fid(d.get("m_Father"))
        return None

    # -- PB / Collider 组件 ----------------------------------------------
    @staticmethod
    def _classify(d: UnityDoc) -> Optional[str]:
        if d.class_id != MONO_CLASS:
            return None
        s = d.get("m_Script") or {}
        if s.get("guid") != PB_GUID:
            return None
        fid = s.get("fileID")
        if fid == PB_FILEID:
            return "pb"
        if fid == PB_COLLIDER_FILEID:
            return "collider"
        # 兼容：老版本或未知 fileID 时按字段判
        if "shapeType" in d.data:
            return "collider"
        if "ignoreOtherPhysBones" in d.data or "endpointPosition" in d.data:
            return "pb"
        return None

    def _pb_record(self, d: UnityDoc, tree: LocalTree, file_path: str,
                   source_prefab: Optional[str], prefix: str = "",
                   instance: str = "") -> PbRecord:
        go = _fid(d.get("m_GameObject"))
        rt = _fid(d.get("rootTransform"))
        root_tf = rt or tree.go_tf.get(go, 0)
        root_path = _join(prefix, tree.tf_path(root_tf)) if root_tf \
            else _join(prefix, tree.go_path(go))
        # 链：根 + 后代（本地树能拿到的部分）
        chain = [root_path]
        if root_tf:
            for ch in tree.descendants(root_tf):
                chain.append(_join(prefix, tree.tf_path(ch)))
        region = self.region_of_tf(tree, root_tf) if root_tf else None
        rchain: List[str] = []
        if region:
            rchain = sorted(REGION_CHAIN.get(region, {region}))
        _, name_src = tree.tf_name(root_tf) if root_tf else tree.go_name(go)
        return PbRecord(
            file=file_path, file_id=d.file_id,
            game_object_path=_join(prefix, tree.go_path(go)), root_path=root_path,
            chain=chain, region=region, region_chain=rchain,
            name_source=name_src,
            enabled=int(d.get("m_Enabled", 1) or 0) != 0,
            immobile=_num(d.get("immobile")), immobile_type=_int(d.get("immobileType")),
            is_animated=_int(d.get("isAnimated")),
            reset_when_disabled=_int(d.get("resetWhenDisabled")),
            allow_collision=_int(d.get("allowCollision")),
            source_prefab=source_prefab, instance=instance,
        )

    def _collider_record(self, d: UnityDoc, tree: LocalTree, file_path: str,
                         source_prefab: Optional[str], prefix: str = "",
                         instance: str = "") -> ColliderRecord:
        go = _fid(d.get("m_GameObject"))
        rt = _fid(d.get("rootTransform"))
        root_tf = rt or tree.go_tf.get(go, 0)
        root_path = _join(prefix, tree.tf_path(root_tf)) if root_tf \
            else _join(prefix, tree.go_path(go))
        region = self.region_of_tf(tree, root_tf) if root_tf else None
        _, name_src = tree.tf_name(root_tf) if root_tf else tree.go_name(go)
        return ColliderRecord(
            file=file_path, file_id=d.file_id,
            game_object_path=_join(prefix, tree.go_path(go)), root_path=root_path,
            region=region, name_source=name_src,
            shape_type=_int(d.get("shapeType")), radius=_num(d.get("radius")),
            height=_num(d.get("height")), inside_bounds=_int(d.get("insideBounds")),
            enabled=int(d.get("m_Enabled", 1) or 0) != 0,
            source_prefab=source_prefab, instance=instance,
        )

    # -- 场景内属于某实例的组件 ------------------------------------------
    def _top_instance(self, tf_fid: int) -> Optional[int]:
        cur = tf_fid
        seen = set()
        while cur and cur not in seen:
            seen.add(cur)
            d = self.scene_idx.by_fid.get(cur)
            if d is None or d.class_id != TRANSFORM_CLASS:
                return None
            pi = _fid(d.get("m_PrefabInstance"))
            if pi:
                return pi
            cur = _fid(d.get("m_Father"))
        return None

    def _scene_child_instances(self, pi_doc: UnityDoc) -> List[UnityDoc]:
        """场景里挂在头像实例子树下的子 PrefabInstance（衣服/配饰/功能件）。"""
        pid = pi_doc.file_id
        out = []
        for d in self.scene_idx.all(PREFAB_INSTANCE_CLASS):
            if d.file_id == pid:
                continue
            parent = _fid((d.get("m_Modification") or {}).get("m_TransformParent"))
            if not parent:
                continue
            if self._top_instance(parent) == pid:
                out.append(d)
        return out

    def _inst_name(self, pi_doc: UnityDoc, src: Optional[str]) -> str:
        """实例名：优先 m_Name 覆盖，其次源 prefab 文件名。"""
        for m in ((pi_doc.get("m_Modification") or {}).get("m_Modifications") or []):
            if (m.get("propertyPath") or "") == "m_Name" and m.get("value"):
                return str(m["value"])
        if src:
            return os.path.splitext(os.path.basename(src))[0]
        return "PI%d" % pi_doc.file_id

    def _scene_components(self, pi_doc: UnityDoc):
        """场景文件里挂在该头像实例下的 PB/collider（含 m_AddedComponents）。"""
        pbs: List[PbRecord] = []
        cols: List[ColliderRecord] = []
        tree = self.tree(self.scene_path)
        pid = pi_doc.file_id
        inst = self._inst_name(pi_doc, self.avatar_instance(pi_doc))
        for d in self.scene_idx.all(MONO_CLASS):
            kind = self._classify(d)
            if not kind:
                continue
            go = _fid(d.get("m_GameObject"))
            tf = tree.go_tf.get(go)
            if tf is None or self._top_instance(tf) != pid:
                continue
            if kind == "pb":
                pbs.append(self._pb_record(d, tree, self.scene_path, None,
                                           prefix="", instance=inst))
            else:
                cols.append(self._collider_record(d, tree, self.scene_path, None,
                                                  prefix="", instance=inst))
        return pbs, cols

    # -- prefab 树（含 m_AddedComponents）---------------------------------
    def _prefab_tree_components(self, path: str, prefix: str = "",
                                depth: int = 0):
        """递归收集 prefab 及其嵌套 prefab 的 PB/collider。

        嵌套实例里 `m_AddedComponents` 写的组件本身就落在**当前 prefab 文件**里
        （class 114 文档），所以扫本文件即可，再对所有嵌套 PrefabInstance 递归其
        `m_SourcePrefab`。`prefix` 是该实例在头像下的路径前缀（用于区分重复实例）。
        """
        pbs: List[PbRecord] = []
        cols: List[ColliderRecord] = []
        if depth > 12:
            self.warnings.append("prefab 递归过深，停在 %s" % path)
            return pbs, cols
        tree = self.tree(path)
        for d in self.cache.load(path):
            kind = self._classify(d)
            if not kind:
                continue
            if kind == "pb":
                pbs.append(self._pb_record(d, tree, path, path,
                                           prefix=prefix, instance=prefix))
            else:
                cols.append(self._collider_record(d, tree, path, path,
                                                  prefix=prefix, instance=prefix))
        for d in self.cache.load(path):
            if d.class_id != PREFAB_INSTANCE_CLASS:
                continue
            g = (d.get("m_SourcePrefab") or {}).get("guid")
            sp = self.guid.get(g or "")
            if sp and sp.endswith(".prefab"):
                a, b = self._prefab_tree_components(
                    sp, _join(prefix, self._inst_name(d, sp)), depth + 1)
                pbs.extend(a)
                cols.extend(b)
            elif sp and sp.endswith(".fbx"):
                pass  # FBX 内的组件不在此序列化（由 m_AddedComponents 落盘）
        return pbs, cols

    # -- 主入口 -----------------------------------------------------------
    def collect(self, decl: Optional[dict] = None) -> dict:
        roots = self.active_avatar_instances()
        if not roots:
            self.warnings.append(
                "场景根上没有活跃的带头像描述符的 prefab 实例；"
                "本脚本按「头像 = 场景 prefab 实例」解析，请确认 --scene")
        avatar_prefab = roots[0] and self.avatar_instance(roots[0]) if roots else None
        if not avatar_prefab:
            avatar_prefab = self.detect_avatar_prefab()
        self.humanoid_map(avatar_prefab)  # 填充 self._human_map / self._skeleton

        pbs: List[PbRecord] = []
        cols: List[ColliderRecord] = []

        for pi in roots:
            src = self.avatar_instance(pi)
            a, b = self._scene_components(pi)
            pbs.extend(a)
            cols.extend(b)
            if src:
                c, d = self._prefab_tree_components(src)
                pbs.extend(c)
                cols.extend(d)
            # 头像根子树下的场景子 prefab 实例（衣服/配饰/功能件）
            for cpi in self._scene_child_instances(pi):
                g = (cpi.get("m_SourcePrefab") or {}).get("guid")
                csrc = self.guid.get(g or "")
                if csrc and csrc.endswith(".prefab"):
                    pref = self._inst_name(cpi, csrc)
                    e, f = self._prefab_tree_components(csrc, prefix=pref)
                    pbs.extend(e)
                    cols.extend(f)

        # collider 按 (文件, fileID, 实例) 建索引，供 colliders 引用在同实例内解析。
        uniq_col: Dict[str, ColliderRecord] = {}
        for r in cols:
            uniq_col.setdefault(r.key(), r)
        pb_list = list(pbs)
        col_list = list(cols)

        # 补 colliders 字段（引用是 fileID，不跨实例）
        for r in pb_list:
            refs = []
            comp = self._component_by_key(r)
            for ref in (comp.get("colliders") or []) if comp else []:
                fid = _fid(ref)
                c = uniq_col.get("%s#%d@%s" % (r.file, fid, r.instance))
                if c is None:
                    for cand in col_list:
                        if cand.file_id == fid and cand.instance == r.instance:
                            c = cand
                            break
                refs.append(c.key() if c else ("%s#%d" % (r.file, fid)))
                if c and c.region:
                    r.colliders_on_regions.append(c.region)
            r.colliders = refs

        parts, matched_by_part = self._map_parts(decl, pb_list)
        u7 = self._u7(parts, matched_by_part)
        return {
            "pbs": pb_list, "colliders": col_list,
            "parts": parts, "u7": u7,
            "avatar_prefab": avatar_prefab,
            "scene": self.scene_path,
            "grep_like": self._grep_like(pb_list, col_list),
        }

    def _grep_like(self, pb_list: List[PbRecord],
                   col_list: List[ColliderRecord]) -> dict:
        """`grep -c "VRCPhysBone"` 的近似：只数 m_EditorClassIdentifier 里带类型名的。

        `m_AddedComponents` 落的组件 `m_EditorClassIdentifier` 为空，grep 会漏；
        所以它通常小于 GUID 口径。把两者都写进产物便于核对。
        """
        def hits(records, needle):
            n = 0
            for r in records:
                comp = self._component_by_key(r)
                if comp and needle in (comp.get("m_EditorClassIdentifier") or ""):
                    n += 1
            return n
        return {
            "identifier_physbone": hits(pb_list, "VRCPhysBone"),
            "identifier_collider": hits(col_list, "VRCPhysBoneCollider"),
        }

    def _component_by_key(self, r) -> Optional[UnityDoc]:
        key = os.path.abspath(r.file)
        if key not in self._idx_cache:
            try:
                self._idx_cache[key] = DocIndex(self.cache.load(key))
            except Exception:  # noqa: BLE001
                self._idx_cache[key] = None
        idx = self._idx_cache[key]
        return idx.by_fid.get(r.file_id) if idx else None

    # -- 根骨 -> 部位 -----------------------------------------------------
    @staticmethod
    def _object_paths(part: dict) -> List[str]:
        out = []
        for o in (part.get("objects") or []):
            if isinstance(o, dict) and o.get("path"):
                out.append(str(o["path"]).strip("/"))
            elif isinstance(o, str):
                out.append(o.strip("/"))
        return out

    def _map_parts(self, decl: Optional[dict], pb_list: List[PbRecord]):
        out: dict = {}
        matched_by_part: Dict[str, List[PbRecord]] = {}
        parts = (decl or {}).get("parts") or []
        if not isinstance(parts, list):
            return out, matched_by_part
        for part in parts:
            if not isinstance(part, dict):
                continue
            pid = part.get("id")
            if not pid:
                continue
            obj_paths = self._object_paths(part)
            covers = [c for c in (part.get("covers") or []) if isinstance(c, str)]
            matched = [r for r in pb_list if self._pb_belongs(r, obj_paths, covers)]
            matched_by_part[pid] = matched
            out[pid] = {
                "has_pb": bool(matched),
                "chains": sorted({ch for r in matched for ch in r.chain}),
                "colliders_on_regions": sorted(
                    {reg for r in matched for reg in r.colliders_on_regions}),
                "covers": covers,
                "objects": obj_paths,
            }
        return out, matched_by_part

    @staticmethod
    def _seg_overlap(a: str, b: str) -> int:
        """两个 `/` 路径从尾部起连续相同的段数。"""
        sa = [s for s in (a or "").split("/") if s]
        sb = [s for s in (b or "").split("/") if s]
        n = 0
        for x, y in zip(reversed(sa), reversed(sb)):
            if x != y:
                break
            n += 1
        return n

    @classmethod
    def _pb_belongs(cls, r: PbRecord, obj_paths: List[str], covers: List[str]) -> bool:
        if obj_paths:
            for op in obj_paths:
                if not op:
                    continue
                for p in (r.root_path, r.game_object_path):
                    if not p:
                        continue
                    if p == op or p.startswith(op + "/") or op.startswith(p + "/"):
                        return True
                    need = min(2, min(len(op.split("/")), len(p.split("/"))))
                    if need >= 1 and cls._seg_overlap(p, op) >= need:
                        return True
            return False
        # 没有 objects 时（草案片段）才退回 region 覆盖
        if r.region and covers:
            return r.region in covers or bool(REGION_CHAIN.get(r.region, set()) & set(covers))
        return False

    def _u7(self, parts: dict, matched_by_part: Dict[str, List[PbRecord]]) -> List[dict]:
        out: List[dict] = []
        for pid, info in parts.items():
            if not info.get("has_pb"):
                continue
            covers = info.get("covers") or []
            matched = matched_by_part.get(pid) or []
            on_regions = set(info.get("colliders_on_regions") or [])
            for region in covers:
                base = FOOT_SUB_REGION.get(region, region)
                wanted = REGION_CHAIN.get(base, {base})
                if on_regions & wanted:
                    continue
                # 缺：给出该部件名下第一条 PB 的根骨路径
                pb_path = ""
                for r in matched:
                    pb_path = r.root_path
                    break
                out.append({
                    "rule": "pb_no_collider",
                    "part": pid,
                    "region": region,
                    "pb": pb_path,
                    "missing": region,
                })
        return out


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v):
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
def build_pb_json(scan: PbScan, res: dict, decl_path: Optional[str]) -> dict:
    body = {
        "schema": "pb.json/1",
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "project": scan.project,
        "scene": _rel(scan.scene_path, scan.project),
        "avatar_prefab": _rel(res["avatar_prefab"], scan.project) if res["avatar_prefab"] else None,
        "decl": decl_path,
        "counts": {
            "physbones": len(res["pbs"]),
            "colliders": len(res["colliders"]),
            "parts_with_pb": sum(1 for v in res["parts"].values() if v.get("has_pb")),
            "u7": len(res["u7"]),
        },
        "checks": {
            "physbone_script_guid": PB_GUID,
            "physbone_class_file_id": PB_FILEID,
            "collider_class_file_id": PB_COLLIDER_FILEID,
            "distinct_pb_docs": len({(r.file, r.file_id) for r in res["pbs"]}),
            "distinct_collider_docs": len({(r.file, r.file_id) for r in res["colliders"]}),
            "name_resolved": sum(1 for r in res["pbs"] if r.name_source == "file"),
            "name_placeholder": sum(1 for r in res["pbs"] if r.name_source != "file"),
            "grep_like": res.get("grep_like", {}),
        },
        "physbones": [_serialize_pb(r, scan.project)
                      for r in sorted(res["pbs"], key=lambda x: x.key())],
        "colliders": [_serialize_col(r, scan.project)
                      for r in sorted(res["colliders"], key=lambda x: x.key())],
        "parts": res["parts"],
        "u7": res["u7"],
        "warnings": scan.warnings,
    }
    return body


def _serialize_pb(r: PbRecord, project: str) -> dict:
    return {
        "key": r.key(),
        "file": _rel(r.file, project) if r.file else r.file,
        "file_id": r.file_id,
        "instance": r.instance,
        "game_object_path": r.game_object_path,
        "root_path": r.root_path,
        "chain": r.chain,
        "colliders": r.colliders,
        "colliders_on_regions": sorted(set(r.colliders_on_regions)),
        "region": r.region,
        "region_chain": r.region_chain,
        "name_source": r.name_source,
        "enabled": r.enabled,
        "immobile": r.immobile,
        "immobile_type": r.immobile_type,
        "is_animated": r.is_animated,
        "reset_when_disabled": r.reset_when_disabled,
        "allow_collision": r.allow_collision,
        "source_prefab": os.path.basename(r.source_prefab) if r.source_prefab else None,
    }


def _serialize_col(r: ColliderRecord, project: str) -> dict:
    return {
        "key": r.key(),
        "file": _rel(r.file, project) if r.file else r.file,
        "file_id": r.file_id,
        "instance": r.instance,
        "game_object_path": r.game_object_path,
        "root_path": r.root_path,
        "region": r.region,
        "name_source": r.name_source,
        "shape_type": r.shape_type,
        "radius": r.radius,
        "height": r.height,
        "inside_bounds": r.inside_bounds,
        "enabled": r.enabled,
        "source_prefab": os.path.basename(r.source_prefab) if r.source_prefab else None,
    }


def write_json(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# --diff：与 T-27 运行时 PB 表比对（M6）
# ---------------------------------------------------------------------------
def load_runtime_table(path: str) -> Dict[str, dict]:
    """兼容 T-27 可能导出的几种形态：list / {physbones:[...]} / {by_key:{...}}。"""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    items = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        if isinstance(raw.get("physbones"), list):
            items = raw["physbones"]
        elif isinstance(raw.get("by_key"), dict):
            items = list(raw["by_key"].values())
    out: Dict[str, dict] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        k = it.get("key") or _runtime_key(it)
        out[k] = it
    return out


def _runtime_key(it: dict) -> str:
    for cand in ("root_path", "root", "path", "chain0"):
        v = it.get(cand)
        if isinstance(v, str) and v:
            return v
        if isinstance(v, list) and v:
            return str(v[0])
    return "?"


def diff_runtime(pb: dict, runtime: Dict[str, dict]) -> dict:
    """按 key / root_path 对齐，报增删改。key 优先（能区分同路径的重复实例）。"""
    static_by_key: Dict[str, dict] = {}
    for r in pb.get("physbones", []):
        static_by_key.setdefault(r.get("key") or r.get("root_path"), r)
    rt_by_key: Dict[str, dict] = {}
    for k, it in runtime.items():
        rt_by_key.setdefault(it.get("key") or it.get("root_path") or k, it)
    # 若一侧没有 key，则退化为 root_path 对齐
    if not any(it.get("key") for it in runtime.values()):
        static_by_key = {}
        for r in pb.get("physbones", []):
            static_by_key.setdefault(r.get("root_path"), r)
        rt_by_key = {}
        for k, it in runtime.items():
            rt_by_key.setdefault(it.get("root_path") or k, it)

    added, removed, changed = [], [], []
    for root, it in rt_by_key.items():
        if root not in static_by_key:
            added.append({"key": root, "root_path": it.get("root_path")})
    for root, st in static_by_key.items():
        if root not in rt_by_key:
            removed.append({"key": root, "root_path": st.get("root_path")})
            continue
        rt = rt_by_key[root]
        diffs = {}
        for f_st, f_rt in (("immobile", "immobile"), ("is_animated", "isAnimated"),
                           ("reset_when_disabled", "resetWhenDisabled"),
                           ("colliders_on_regions", "colliders_on_regions"),
                           ("region", "region")):
            a, b = st.get(f_st), rt.get(f_rt)
            if b is None:
                continue
            if isinstance(a, list) or isinstance(b, list):
                if sorted(a or []) != sorted(b or []):
                    diffs[f_st] = {"static": a, "runtime": b}
            elif a != b:
                diffs[f_st] = {"static": a, "runtime": b}
        if diffs:
            changed.append({"key": root, "root_path": st.get("root_path"), "diff": diffs})
    return {
        "schema": "pb_runtime_diff.json/1",
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "counts": {"static": len(static_by_key), "runtime": len(rt_by_key),
                   "added": len(added), "removed": len(removed), "changed": len(changed)},
        "added": added, "removed": removed, "changed": changed,
    }


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------
def _selftest() -> int:
    project = os.path.abspath(os.path.join(
        _HERE, "..", "..", "..", "..", "工程A"))
    if not os.path.isdir(project):
        print("[FAIL] 找不到 %s" % project)
        return 2
    fails: List[str] = []
    scan = PbScan(project)
    res = scan.collect(None)
    n_pb, n_col = len(res["pbs"]), len(res["colliders"])
    print("[selftest] scene=%s" % _rel(scan.scene_path, project))
    print("[selftest] avatar_prefab=%s" % _rel(res["avatar_prefab"], project))
    print("[selftest] PhysBone 组件 %d，碰撞体 %d（活跃头像根；含 m_AddedComponents）"
          % (n_pb, n_col))
    # 文档口径核对：_工程状态.md:197 记 158，PhysBoneAudit.cs 注释记当前源场景 164。
    # 本脚本按「活跃头像根 + 其下全部子 prefab 实例（含 inactive 子物体）」计数，
    # 与 PhysBoneAudit 的 GetComponentsInChildren(true) 同口径 → 应为 164。
    print("[selftest] 口径核对：当前源场景应为 164（PhysBoneAudit.cs 注释）；"
          "_工程状态.md:197 的 158 为更早快照。本脚本得到 %d。" % n_pb)
    gl = res.get("grep_like", {})
    print("[selftest] grep 对照：GUID 口径 PB=%d；`grep -c \"VRCPhysBone\"` 口径≈%d"
          "（m_AddedComponents 的 m_EditorClassIdentifier 为空，grep 会漏）"
          % (n_pb, gl.get("identifier_physbone", 0)))
    if n_pb != 164:
        fails.append("活跃头像根 PB 计数应为 164（PhysBoneAudit 口径），实际 %d" % n_pb)
    if n_col <= 0:
        fails.append("碰撞体数为 0")

    # 用真实 PB 路径动态造两个声明件：尾（配饰，覆盖 Hips）+ 裙（kaguya_cloth，覆盖双腿）。
    tail_pb = next((r for r in res["pbs"] if "tail" in r.root_path), None)
    skirt_pb = next((r for r in res["pbs"]
                     if "kaguya_cloth" in (r.source_prefab or "")), None)
    spec = []
    if tail_pb:
        spec.append({"id": "工程A.tail", "kind": "acc", "fit": "none",
                     "covers": ["Hips"],
                     "objects": [{"path": tail_pb.root_path, "renderer": "mesh"}]})
    if skirt_pb:
        spec.append({"id": "工程A.skirt", "kind": "bottom", "fit": "loose",
                     "covers": ["LeftUpperLeg", "RightUpperLeg"],
                     "objects": [{"path": skirt_pb.root_path, "renderer": "smr"}]})
    decl = {"parts": spec}
    parts, matched = scan._map_parts(decl, res["pbs"])
    u7 = scan._u7(parts, matched)
    print("[selftest] 命中部件：%s" % [
        k for k, v in parts.items() if v.get("has_pb")])

    for pid, label in (("工程A.tail", "尾"), ("工程A.skirt", "裙")):
        info = parts.get(pid, {})
        if not info.get("has_pb"):
            fails.append("%s（%s）应 has_pb=true" % (pid, label))
        if not info.get("chains"):
            fails.append("%s 的 chains[] 应非空" % pid)
        elif not (1 <= len(info["chains"]) <= 80):
            fails.append("%s chains 数量异常（%d），疑似父链映射过宽"
                         % (pid, len(info["chains"])))
        else:
            print("[selftest] %s has_pb=%s chains=%d，示例：%s"
                  % (pid, info["has_pb"], len(info["chains"]),
                     info["chains"][0]))
    # 裙类 U7：碰撞体 region 在离线多为 null，应至少报出一条带 PB 路径 + region 的记录
    skirt_u7 = [u for u in u7 if u["part"] == "工程A.skirt"]
    if skirt_pb and not skirt_u7:
        fails.append("裙类部件应至少报出一条 pb_no_collider")
    for u in u7[:1]:
        print("[selftest] U7 示例：%s → 缺 %s（PB %s）"
              % (u["part"], u["missing"], u["pb"]))

    # U7：合成用例——覆盖 LeftUpperLeg 的部件只有 RightUpperLeg 的碰撞体 → 必须报缺
    fake_pb = PbRecord(file="<synth>", file_id=1, game_object_path="synth/skirt",
                       root_path="synth/skirt", chain=["synth/skirt"],
                       colliders=["col1"], colliders_on_regions=["RightUpperLeg"])
    sparts = {"synth.skirt": {"has_pb": True, "chains": ["synth/skirt"],
                              "colliders_on_regions": ["RightUpperLeg"],
                              "covers": ["LeftUpperLeg"], "objects": ["synth"]}}
    su7 = scan._u7(sparts, {"synth.skirt": [fake_pb]})
    if not any(u["rule"] == "pb_no_collider" and u["missing"] == "LeftUpperLeg"
               and u["pb"] == "synth/skirt" for u in su7):
        fails.append("U7 合成用例：LeftUpperLeg 缺碰撞体未报出；实际 %r" % su7)
    else:
        print("[selftest] U7 合成用例 OK：%s" % su7[0])
    sparts_ok = {"synth.skirt": {"has_pb": True, "chains": ["synth/skirt"],
                                 "colliders_on_regions": ["LeftUpperLeg"],
                                 "covers": ["LeftUpperLeg"], "objects": ["synth"]}}
    if scan._u7(sparts_ok, {"synth.skirt": [fake_pb]}):
        fails.append("U7 合成用例：已覆盖 LeftUpperLeg 仍误报")

    # --diff：手改运行时表
    pb = build_pb_json(scan, res, None)
    runtime = {r["key"]: {
        "key": r["key"], "root_path": r["root_path"],
        "immobile": r.get("immobile"), "isAnimated": r.get("is_animated"),
        "resetWhenDisabled": r.get("reset_when_disabled"),
        "colliders_on_regions": r.get("colliders_on_regions"),
        "region": r.get("region"),
    } for r in pb["physbones"]}
    if len(runtime) >= 3:
        keys = sorted(runtime)
        # 删 1、改 1、加 1
        del runtime[keys[0]]
        runtime[keys[1]]["immobile"] = 999.0
        runtime["__hand_added__"] = {"key": "__hand_added__",
                                     "root_path": "__hand_added__", "immobile": 1.0}
        d = diff_runtime(pb, runtime)
        c = d["counts"]
        print("[selftest] --diff：added=%d removed=%d changed=%d"
              % (c["added"], c["removed"], c["changed"]))
        if not (c["added"] == 1 and c["removed"] == 1 and c["changed"] >= 1):
            fails.append("--diff 未按预期报出增删改：%r" % c)
    else:
        fails.append("PB 太少，无法测 --diff")

    if fails:
        for f in fails:
            print("[FAIL] %s" % f)
        return 1
    print("[selftest] pb_static OK")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="PhysBone 静态清单与 U7（T-30）")
    ap.add_argument("--project", help="工程根目录")
    ap.add_argument("--scene", help="场景文件（默认自动探测）")
    ap.add_argument("--decl", help="声明 JSON（默认 <工程>/_感知/decl.json）")
    ap.add_argument("--out", help="输出 JSON（默认 <工程>/_感知/out/pb.json）")
    ap.add_argument("--diff", help="与 T-27 运行时 PB 表比对，写 pb_runtime_diff.json")
    ap.add_argument("--selftest", action="store_true", help="工程A 数据自验")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.project:
        ap.error("需要 --project（或 --selftest）")

    project = os.path.abspath(args.project)
    scan = PbScan(project, args.scene)
    decl_path = args.decl or os.path.join(project, "_感知", "decl.json")
    decl = None
    if os.path.exists(decl_path):
        try:
            with open(decl_path, "r", encoding="utf-8") as f:
                decl = json.load(f)
        except Exception as e:  # noqa: BLE001
            print("[warn] 读声明失败：%s" % e)
    elif args.decl:
        print("[warn] 指定声明不存在：%s" % decl_path)

    res = scan.collect(decl)
    pb = build_pb_json(scan, res, decl_path if os.path.exists(decl_path) else None)
    out = args.out or os.path.join(project, *DEFAULT_OUT)
    write_json(out, pb)
    print("[pb_static] 写出 %s（PB %d / collider %d / parts_with_pb %d / U7 %d）"
          % (out, pb["counts"]["physbones"], pb["counts"]["colliders"],
             pb["counts"]["parts_with_pb"], pb["counts"]["u7"]))
    for w in scan.warnings:
        print("[warn] %s" % w)

    if args.diff:
        runtime = load_runtime_table(args.diff)
        d = diff_runtime(pb, runtime)
        diff_out = os.path.join(os.path.dirname(out), "pb_runtime_diff.json")
        write_json(diff_out, d)
        c = d["counts"]
        print("[pb_static] --diff → %s（added %d / removed %d / changed %d）"
              % (diff_out, c["added"], c["removed"], c["changed"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
