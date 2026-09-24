# -*- coding: utf-8 -*-
"""writers_static.py — 离线静态写者图（T-11，04 第一期开工清单 §T-11）。
【项目沉淀】通用工具
适用素体：无关
相关素材：工程控制器/clip/场景/prefab
工具链　：Python 3 + PyYAML（离线）
可复用性：★★ 审查工具链的一环
用途　　：离线静态写者图：合并我方控制器、厂商 clip、场景/prefab 的 MA 写者（不重实现 MA 胜负规则）。


合并四路写者（不重实现 MA 胜负规则；MA 段留空等 T-12 构建期截获）：
  1. 我方控制器 + clip（层、状态、WD、曲线 路径/属性/关键帧值，Motion Time 档位按 i/n）
  2. 厂商 clip（只取真正接到头像上的控制器：MergeAnimator 并入 + descriptor 启用层）
  3. 场景与 prefab 的 MA ShapeChanger / BlendshapeSync / ObjectToggle（含 `m_AddedComponents`，
     只算活跃根；非 ASCII 路径由 PyYAML 解 `\\uXXXX`）。任务 AR 起：
     * 变体链（prefab variant 的 `m_SourcePrefab` 递归到基础预制体）与嵌套实例里定义的 MA
       组件也收进来；变体基座是同一根节点，不重复追加实例名；
     * 宿主解析到**场景实例路径**（如 `_Outfit/LopEarMine/08_WhitePink_Milfy_MA/…`），
       不再只给 prefab 内的局部名；场景 `m_AddedComponents` 解析到它所属的实例路径。
  4. `build_plugins`：扫工程 `Packages/*` 的 `[assembly: ExportsPlugin(...)]`（列插件与阶段，
     未登记的标「未审」）

输出 `writers.json`（03c L1 结构；含 `ours_legacy` 与 `gen`（按 `gen_writers.json`）来源）到
`<工程>/_感知/out/writers.json`（可用 `--out` 改）。

    python3 writers_static.py --project <工程根> [--scene ...] [--out ...]
    python3 writers_static.py --selftest        # 工程A + 工程B数据自验（只读工程）

验收（04 §T-11）：sailor.outer_shlink 写者 = {Dial_整套(100/0 按档), Off_部位_外套(0)}；
MMN Foot_heel_OFF 写者 = {Socks SC(vendor_sc), Shoes SC(ours_legacy 或 gen)}；
Body_b.outer_shrink 同 outer_shlink；build_plugins 列 7 项。
任务 AR 追加：工程B垂耳兔 11 个收缩键的宿主要落在 `08_WhitePink_Milfy_MA` 下。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from unity_yaml import (  # noqa: E402
    DocIndex,
    YamlCache,
    build_guid_index,
    leaf,
    restore_shape,
)

# GO/Transform 本地树（名字/父链）复用 T-30 的 pb_static.LocalTree，避免两处各写一份
from pb_static import LocalTree  # noqa: E402

import clip_writes  # noqa: E402

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
SC_GUID = "2db441f589c3407bb6fb5f02ff8ab541"       # ModularAvatarShapeChanger
BSS_GUID = "6fd7cab7d93b403280f2f9da978d8a4f"      # ModularAvatarBlendshapeSync
OT_GUID = "a162bb8ec7e24a5abcf457887f1df3fa"       # ModularAvatarObjectToggle
MA_GUID = "1bb122659f724ebf85fe095ac02dc339"       # ModularAvatarMergeAnimator
MA_SCRIPT_GUIDS = {SC_GUID: "ShapeChanger", BSS_GUID: "BlendshapeSync",
                   OT_GUID: "ObjectToggle", MA_GUID: "MergeAnimator"}

PREFAB_INSTANCE_CLASS = 1001
GAMEOBJECT_CLASS = 1
MONO_CLASS = 114

OURS_PREFIXES = ("Assets/_Work/", "Assets/Editor/AvatarGen/", "Assets/AvatarAudit/",
                 "Packages/local.avatar-audit/")
SKIP_PREFIXES = ("Assets/ZZZ_GeneratedAssets/", "Assets/_Work/__Generated/")

KNOWN_REVIEWED_PACKAGES = {
    "com.anatawa12.avatar-optimizer": "AAO",
    "nadena.dev.modular-avatar": "MA",
    "nadena.dev.ndmf": "NDMF",
    "com.triturbo.face-blendshape-fix": "face-blendshape-fix",
    "com.triturbo.facetrackingframework": "facetrackingframework",
    "io.github.azukimochi.light-limit-changer": "light-limit-changer",
    "world.anlabo.mdnailtool": "mdnailtool",
}

WINNER_RULE = {
    "ours": "我方层按 fx_final 层序与 WriteDefaults 展开（T-14）；本文件只列写者",
    "ma": "留空：MA 反应式写者图由 T-12 Harmony Postfix 截获 ma_analysis.json，"
          "本文件不重实现胜负规则",
    "vendor_sc": "MA ShapeChanger/ObjectToggle 条件 = MenuItem(最近一层) ∧ 宿主到根 activeSelf"
                 "（T-12）；静态只列候选",
    "vendor_clip": "只列接到头像上的控制器（MergeAnimator + descriptor 启用层）所引用的 clip",
}


def _rel(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def _is_ours(rel_path: str) -> bool:
    return any(rel_path.startswith(p) for p in OURS_PREFIXES)


def _fid(ref) -> int:
    """从 {fileID: N} / N 取整数 fileID，取不到返回 0。"""
    if isinstance(ref, dict):
        try:
            return int(ref.get("fileID", 0) or 0)
        except (TypeError, ValueError):
            return 0
    if isinstance(ref, int):
        return ref
    return 0


def _join(prefix: str, path: str) -> str:
    path = (path or "").strip("/")
    if not prefix:
        return path
    return (prefix.rstrip("/") + "/" + path) if path else prefix.rstrip("/")


def _rel_to_root(local_path: str) -> str:
    """去掉本地树路径的首段（prefab 根 GO 名），得到「相对实例根」的路径。

    `LocalTree.go_path` 已含根名字；实例前缀也以根名字结尾，不去重会得到
    `.../ModularAvatar/ModularAvatar/MA Shape Changer` 这种重复段。
    """
    if not local_path:
        return ""
    seg = local_path.split("/", 1)
    return seg[1] if len(seg) == 2 else ""


def _tree_go_path(tree, go_fid: int) -> str:
    """LocalTree 的健壮版 go_path：把名字强制成 str。

    pb_static.LocalTree.tf_path 在 GO 名字是纯数字（YAML 解析成 int，如 `m_Name: 1`）
    时会 `"/".join` 失败；本函数不改 pb_static，只在这里兜住。
    """
    tf = tree.go_tf.get(int(go_fid))
    if tf is None:
        name, src = tree.go_name(int(go_fid))
        return str(name) if (name is not None and src == "file") else ""
    segs: List[str] = []
    seen: Set[int] = set()
    cur = tf
    while cur and cur not in seen:
        seen.add(cur)
        name, src = tree.tf_name(cur)
        segs.append(str(name) if (name is not None and src == "file") else "#%d" % cur)
        d = tree.idx.by_fid.get(cur)
        if d is None or d.class_id != 4:  # TRANSFORM_CLASS
            break
        cur = _fid(d.get("m_Father"))
    return "/".join(reversed(segs))


# ---------------------------------------------------------------------------
# 工程扫描
# ---------------------------------------------------------------------------
class ProjectScan:
    def __init__(self, project: str, scene: Optional[str] = None,
                 cache: Optional[YamlCache] = None):
        self.project = os.path.abspath(project)
        self.cache = cache or YamlCache()
        self.guid = build_guid_index(self.project, ["Packages"])
        self.scene_path = os.path.abspath(scene) if scene else self.detect_scene()
        self.scene_idx = DocIndex(self.cache.load(self.scene_path))
        self.scene_added_components = self._scene_added_components()
        self.scene_overrides = self._scene_active_overrides()
        self.avatar_prefab = self.detect_avatar_prefab()
        self.reachable_prefabs = self._collect_reachable_prefabs()
        self.gen_writers = self._load_gen_writers()
        self.merged_controllers = self._collect_merged_controllers()
        # 场景 GO/Transform 树 + 场景实例路径 + 「prefab → 场景实例前缀」映射（宿主路径解析用）
        self._tree_cache: Dict[str, LocalTree] = {}
        self.scene_tree = self._local_tree(self.scene_path)
        self.scene_instance_paths = self._collect_scene_instance_paths()
        self.prefab_prefixes = self._collect_prefab_prefixes()
        self._prefab_ma_cache: Dict[str, List[dict]] = {}

    # -- 本地 GO/Transform 树 ---------------------------------------------
    def _local_tree(self, path: str) -> LocalTree:
        key = os.path.abspath(path)
        if key not in self._tree_cache:
            self._tree_cache[key] = LocalTree(self.cache.load(key))
        return self._tree_cache[key]

    @staticmethod
    def _inst_name(pi_doc, src: Optional[str]) -> str:
        """实例名：优先 m_Name 覆盖，其次源 prefab 文件名，最后 PI<fileID>。"""
        for m in ((pi_doc.get("m_Modification") or {}).get("m_Modifications") or []):
            if not isinstance(m, dict):
                continue
            if (m.get("propertyPath") or "") == "m_Name" and m.get("value"):
                return str(m["value"])
        if src:
            return os.path.splitext(os.path.basename(src))[0]
        return "PI%d" % pi_doc.file_id

    @staticmethod
    def _is_variant_base(prefab_path: str, pi_doc) -> bool:
        """prefab 文件里的根 PrefabInstance（m_TransformParent==0）是变体基座。

        变体和基座是**同一个根节点**，递归时不能再追加一段实例名，否则
        `08_WhitePink_Milfy_MA/08_WhitePink/...` 会出现重复根。
        """
        if not prefab_path.endswith(".prefab"):
            return False
        mod = pi_doc.get("m_Modification") or {}
        return _fid(mod.get("m_TransformParent")) == 0

    def _scene_instance_path(self, pi_doc) -> str:
        """场景 PrefabInstance 在场景里的路径（父 GO 链 + 实例名），如
        `_Outfit/LopEarMine/08_WhitePink_Milfy_MA`。"""
        mod = pi_doc.get("m_Modification") or {}
        segs: List[str] = []
        cur = _fid(mod.get("m_TransformParent"))
        seen: Set[int] = set()
        while cur and cur not in seen:
            seen.add(cur)
            d = self.scene_idx.by_fid.get(cur)
            if d is None:
                break
            go = _fid(d.get("m_GameObject"))
            god = self.scene_idx.by_fid.get(go) if go else None
            name = god.get("m_Name") if god is not None else None
            if name:
                segs.append(str(name))
            cur = _fid(d.get("m_Father"))
        src = self.guid.get((pi_doc.get("m_SourcePrefab") or {}).get("guid") or "")
        inst = self._inst_name(pi_doc, src)
        return "/".join(list(reversed(segs)) + ([inst] if inst else []))

    def _collect_scene_instance_paths(self) -> Dict[int, str]:
        out: Dict[int, str] = {}
        for d in self.scene_idx.all(PREFAB_INSTANCE_CLASS):
            out[int(d.file_id)] = self._scene_instance_path(d)
        return out

    def _collect_prefab_prefixes(self) -> Dict[str, List[str]]:
        """{prefab 绝对路径: [场景实例路径前缀, ...]}。

        从场景每个 PrefabInstance 出发，按变体链（`m_SourcePrefab`，根实例不追加名）
        与嵌套实例（追加实例名）递归，把「这一份 prefab 在场景里挂在谁下面」解析出来。
        """
        out: Dict[str, List[str]] = {}

        def add(path: str, prefix: str):
            key = os.path.abspath(path)
            lst = out.setdefault(key, [])
            if prefix not in lst:
                lst.append(prefix)

        def walk(path: str, prefix: str, depth: int):
            if depth > 16:
                return
            rel = _rel(path, self.project)
            if rel.startswith(SKIP_PREFIXES):
                return
            add(path, prefix)
            try:
                idx = DocIndex(self.cache.load(path))
            except Exception:  # noqa: BLE001
                return
            for d in idx.all(PREFAB_INSTANCE_CLASS):
                sp = self.guid.get((d.get("m_SourcePrefab") or {}).get("guid") or "")
                if not (sp and sp.endswith(".prefab")):
                    continue
                if self._is_variant_base(path, d):
                    walk(sp, prefix, depth + 1)
                else:
                    walk(sp, _join(prefix, self._inst_name(d, sp)), depth + 1)

        for d in self.scene_idx.all(PREFAB_INSTANCE_CLASS):
            sp = self.guid.get((d.get("m_SourcePrefab") or {}).get("guid") or "")
            if not (sp and sp.endswith(".prefab")):
                continue
            prefix = self.scene_instance_paths.get(int(d.file_id)) \
                or self._inst_name(d, sp)
            walk(sp, prefix, 0)
        return out

    def scene_foreign_prefix(self, go_fid: int) -> str:
        """场景里 stripped GameObject（属于某 prefab 实例）的实例路径；拿不到返回 ""。"""
        god = self.scene_idx.by_fid.get(int(go_fid))
        if god is None:
            return ""
        pi = _fid(god.get("m_PrefabInstance"))
        if pi:
            return self.scene_instance_paths.get(pi, "")
        return ""

    def scene_local_path(self, go_fid: int) -> str:
        """场景内非 stripped GameObject 的场景路径（相对场景根）；拿不到返回 ""。"""
        god = self.scene_idx.by_fid.get(int(go_fid))
        if god is None or god.class_id != GAMEOBJECT_CLASS or god.stripped:
            return ""
        return _tree_go_path(self.scene_tree, int(go_fid))

    # -- 场景/头像定位 ----------------------------------------------------
    def detect_scene(self) -> str:
        best, best_score = None, -1
        for dirpath, dirnames, filenames in os.walk(os.path.join(self.project, "Assets")):
            dirnames[:] = [d for d in dirnames if not any(
                os.path.join(dirpath, d).startswith(
                    os.path.join(self.project, p.rstrip("/")))
                for p in SKIP_PREFIXES)]
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

    def _has_descriptor(self, prefab_path: str) -> bool:
        try:
            idx = DocIndex(self.cache.load(prefab_path))
        except Exception:
            return False
        for d in idx.all(MONO_CLASS):
            if "ViewPosition" in d.data and "baseAnimationLayers" in d.data:
                return True
        return False

    def detect_avatar_prefab(self) -> Optional[str]:
        roots = []
        for d in self.scene_idx.all(PREFAB_INSTANCE_CLASS):
            mod = d.get("m_Modification") or {}
            parent = (mod.get("m_TransformParent") or {}).get("fileID", 1)
            sp = d.get("m_SourcePrefab") or {}
            g = sp.get("guid")
            if parent == 0 and g:
                roots.append(g)
        # 先看根实例，再看全部实例
        for g in roots + [d.get("m_SourcePrefab", {}).get("guid")
                          for d in self.scene_idx.all(PREFAB_INSTANCE_CLASS)]:
            p = self.guid.get(g or "")
            if p and p.endswith(".prefab") and self._has_descriptor(p):
                return p
        return None

    def descriptor_doc(self):
        if not self.avatar_prefab:
            return None, None
        idx = DocIndex(self.cache.load(self.avatar_prefab))
        for d in idx.all(MONO_CLASS):
            if "ViewPosition" in d.data and "baseAnimationLayers" in d.data:
                return d, idx
        return None, None

    def _scene_added_components(self) -> Set[int]:
        """场景 PrefabInstance `m_AddedComponents` 里新增的组件 fileID（MMN Shoes SC 就在这）。"""
        out: Set[int] = set()
        for d in self.scene_idx.all(PREFAB_INSTANCE_CLASS):
            added = (d.get("m_Modification") or {}).get("m_AddedComponents") or []
            for a in added:
                if not isinstance(a, dict):
                    continue
                fid = (a.get("addedObject") or {}).get("fileID")
                if fid is not None:
                    out.add(int(fid))
        return out

    def _scene_active_overrides(self) -> Dict[Tuple[str, int], int]:
        """场景 PrefabInstance 的 m_IsActive 覆盖 → {(源 prefab guid, targetFileID): 0/1}。"""
        out: Dict[Tuple[str, int], int] = {}
        for d in self.scene_idx.all(PREFAB_INSTANCE_CLASS):
            sp = d.get("m_SourcePrefab") or {}
            g = sp.get("guid")
            mods = (d.get("m_Modification") or {}).get("m_Modifications") or []
            for m in mods:
                if not isinstance(m, dict):
                    continue
                if (m.get("propertyPath") or "") != "m_IsActive":
                    continue
                tgt = m.get("target") or {}
                fid = tgt.get("fileID")
                if fid is None:
                    continue
                try:
                    out[(g, int(fid))] = int(float(m.get("value", 1)))
                except (TypeError, ValueError):
                    pass
        return out

    def _prefab_instance_guids(self, path: str) -> Set[str]:
        idx = DocIndex(self.cache.load(path))
        out = set()
        for d in idx.all(PREFAB_INSTANCE_CLASS):
            g = (d.get("m_SourcePrefab") or {}).get("guid")
            if g:
                out.add(g)
        return out

    def _collect_reachable_prefabs(self) -> List[str]:
        seen_g: Set[str] = set()
        out: List[str] = []
        queue: List[str] = list(self._prefab_instance_guids(self.scene_path))
        while queue:
            g = queue.pop(0)
            if not g or g in seen_g:
                continue
            seen_g.add(g)
            p = self.guid.get(g)
            if not p or not p.endswith(".prefab"):
                continue
            rel = _rel(p, self.project)
            if rel.startswith(SKIP_PREFIXES):
                continue
            out.append(p)
            queue.extend(self._prefab_instance_guids(p))
        out.sort()
        return out

    # -- gen_writers / 控制器 --------------------------------------------
    def _load_gen_writers(self) -> dict:
        p = os.path.join(self.project, "_感知", "gen_writers.json")
        if not os.path.exists(p):
            return {}
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:  # noqa: BLE001
            print("[warn] gen_writers.json 读取失败：%s" % e)
            return {}

    def gen_key_set(self) -> Set[Tuple[str, str]]:
        """gen_writers 里 (mesh,key) 集合；兼容 list 与 dict 两种写法。"""
        out: Set[Tuple[str, str]] = set()
        gw = self.gen_writers
        items = gw.get("writers") if isinstance(gw, dict) else gw
        if isinstance(items, dict):
            items = list(items.values())
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            mesh = leaf(it.get("mesh") or it.get("path") or it.get("referencePath") or "")
            key = it.get("key") or it.get("shape") or it.get("shapeName") or ""
            if key.startswith("blendShape."):
                key = key[len("blendShape."):]
            if mesh and key:
                out.add((mesh, key))
        return out

    def _collect_merged_controllers(self) -> List[str]:
        """MergeAnimator 的 animator guid + descriptor 启用层的控制器路径。"""
        ctrls: Set[str] = set()

        def add_from_idx(idx: DocIndex, path: str):
            for comp in idx.iter_components(MA_GUID):
                g = (comp.get("animator") or {}).get("guid")
                p = self.guid.get(g or "")
                if p and p.endswith(".controller"):
                    ctrls.add(os.path.abspath(p))

        add_from_idx(self.scene_idx, self.scene_path)
        for p in self.reachable_prefabs:
            add_from_idx(DocIndex(self.cache.load(p)), p)
        # descriptor 启用层
        d, didx = self.descriptor_doc()
        if d is not None:
            for layer in (d.data.get("baseAnimationLayers") or []) + \
                         (d.data.get("specialAnimationLayers") or []):
                if not isinstance(layer, dict) or not int(layer.get("isEnabled") or 0):
                    continue
                g = (layer.get("animatorController") or {}).get("guid")
                p = self.guid.get(g or "")
                if p and p.endswith(".controller"):
                    ctrls.add(os.path.abspath(p))
        return sorted(ctrls)

    # -- 活跃判定 ---------------------------------------------------------
    def _go_name_and_active(self, path: str, idx: DocIndex, go_fid: int,
                            src_guid: Optional[str] = None):
        """返回 (name, active)。active=None 表示解析不了（按未知，含入）。"""
        doc = idx.by_fid.get(go_fid)
        if doc is None:
            return "", None
        if doc.class_id == GAMEOBJECT_CLASS and not doc.stripped:
            return doc.get("m_Name") or "", idx.go_active(go_fid)
        # stripped：顺着 m_CorrespondingSourceObject 找源 prefab
        src = doc.get("m_CorrespondingSourceObject") or {}
        g = src.get("guid")
        fid = src.get("fileID")
        if g and fid:
            p = self.guid.get(g)
            if p and p.endswith(".prefab"):
                sidx = DocIndex(self.cache.load(p))
                sdoc = sidx.by_fid.get(int(fid))
                if sdoc and sdoc.class_id == GAMEOBJECT_CLASS and not sdoc.stripped:
                    active = sidx.go_active(int(fid))
                    ov = self.scene_overrides.get((src_guid or "", int(fid)))
                    if (src_guid, int(fid)) in self.scene_overrides:
                        active = bool(self.scene_overrides[(src_guid, int(fid))])
                    return sdoc.get("m_Name") or "", active
            if p:
                # 指向 .fbx 等非文本资产：名字拿不到，至少给出可追溯的定位
                return "<%s#%s>" % (os.path.basename(p), fid), None
            return "<guid:%s#%s>" % (str(g)[:8], fid), None
        return "<stripped#%s>" % go_fid, None


# ---------------------------------------------------------------------------
# MA 组件 → 写者
# ---------------------------------------------------------------------------
def _change_type_name(v) -> str:
    try:
        v = int(v)
    except (TypeError, ValueError):
        return "?"
    return {0: "Delete", 1: "Set"}.get(v, "ChangeType%s" % v)


def shapes_from_sc(comp: dict) -> List[dict]:
    out = []
    for s in comp.get("m_shapes") or []:
        if not isinstance(s, dict):
            continue
        obj = s.get("Object") or {}
        ref = obj.get("referencePath") or ""
        out.append({
            "mesh": leaf(ref) if ref else "",
            "path": ref,
            "key": s.get("ShapeName") or "",
            "change": _change_type_name(s.get("ChangeType")),
            "value": s.get("Value"),
            "inverted": bool(comp.get("m_inverted")),
        })
    return out


def shapes_from_bss(comp: dict) -> List[dict]:
    out = []
    bindings = (comp.get("m_bindings") or comp.get("m_Bindings")
                or comp.get("bindings") or [])
    for b in bindings:
        if not isinstance(b, dict):
            continue
        ref = b.get("ReferenceMesh") or {}
        rpath = ref.get("referencePath") or ""
        src = b.get("Blendshape") or b.get("m_Blendshape") or ""
        local = b.get("LocalBlendshape") or b.get("m_LocalBlendshape") or ""
        out.append({
            "mesh": leaf(rpath) if rpath else "",
            "path": rpath,
            "key": src,
            "local_key": local,
            "change": "Sync",
            "value": None,
            "inverted": bool(comp.get("m_inverted")),
        })
    return out


def shapes_from_toggle(comp: dict) -> List[dict]:
    out = []
    for o in comp.get("m_objects") or []:
        if not isinstance(o, dict):
            continue
        ref = o.get("Object") or {}
        rpath = ref.get("referencePath") or ""
        out.append({
            "mesh": leaf(rpath) if rpath else "",
            "path": rpath,
            "key": "@active",
            "change": "Set",
            "value": 1 if o.get("Active") else 0,
            "inverted": bool(comp.get("m_inverted")),
        })
    return out


def scan_ma_in_file(scan: ProjectScan, path: str, is_scene: bool,
                    prefix: Optional[str] = None) -> List[dict]:
    """扫一篇文件里的 MA ShapeChanger/BlendshapeSync/ObjectToggle。

    `prefix` 非 None 时表示这是「场景实例路径前缀」（含实例根名），宿主解析成
    `前缀/本地相对路径`；`is_scene` 时宿主按场景实例路径或场景本地路径解析。
    """
    idx = DocIndex(scan.cache.load(path))
    rel = _rel(path, scan.project)
    tree = None
    out: List[dict] = []
    for comp in idx.all(MONO_CLASS):
        s = comp.get("m_Script") or {}
        guid = s.get("guid")
        if guid not in MA_SCRIPT_GUIDS:
            continue
        kind = MA_SCRIPT_GUIDS[guid]
        if kind == "MergeAnimator":
            continue
        go_fid = int((comp.get("m_GameObject") or {}).get("fileID", 0) or 0)
        src_guid = (comp.get("m_CorrespondingSourceObject") or {}).get("guid")
        host, active = scan._go_name_and_active(path, idx, go_fid, src_guid) \
            if not comp.stripped else ("", None)
        if active is False:
            continue  # 只算活跃根
        # 宿主路径解析到场景实例路径
        if prefix is not None:
            if tree is None:
                tree = scan._local_tree(path)
            host = _join(prefix, _rel_to_root(_tree_go_path(tree, go_fid))) or prefix
        elif is_scene:
            foreign = scan.scene_foreign_prefix(go_fid)
            if foreign:
                host = foreign
            else:
                local = scan.scene_local_path(go_fid)
                if local:
                    host = local
        if kind == "ShapeChanger":
            shapes = shapes_from_sc(comp.data)
        elif kind == "BlendshapeSync":
            shapes = shapes_from_bss(comp.data)
        else:
            shapes = shapes_from_toggle(comp.data)
        if is_scene and (not comp.stripped or comp.file_id in scan.scene_added_components):
            source = "ours_legacy"
        elif _is_ours(rel):
            source = "ours_legacy"
        else:
            source = "vendor_sc"
        for sh in shapes:
            if not sh.get("key"):
                continue
            out.append({
                "source": source,
                "type": sh.get("change", "Set"),
                "where": "%s:%d" % (rel, comp.line),
                "cond": "host_activeSelf ∧ MenuItem(最近一层)",
                "value": sh.get("value"),
                "values": [sh.get("value")] if sh.get("value") is not None else [],
                "mesh": str(sh.get("mesh") or ""),
                "key": str(sh.get("key") or ""),
                "path": str(sh.get("path") or ""),
                "attribute": "",
                "class_id": 1 if sh.get("key") in ("m_IsActive", "@active") else 137,
                "layer": "",
                "state": "",
                "clip": "",
                "host": host or "",
                "component": kind,
                "inverted": sh.get("inverted", False),
                "curve": [],
            })
    return out


# ---------------------------------------------------------------------------
# clip → 写者
# ---------------------------------------------------------------------------
def clip_entries_to_writers(scan: ProjectScan, ctrl_path: str,
                            resolver) -> List[dict]:
    entries = clip_writes.ClipWritesScanner(scan.cache).scan_controller(ctrl_path, resolver)
    rel_ctrl = _rel(ctrl_path, scan.project)
    ours = _is_ours(rel_ctrl)
    gen_keys = scan.gen_key_set()
    out = []
    for e in entries:
        key = str(e["key"]) if e["key"] is not None else ""
        mesh = str(e["mesh"]) if e["mesh"] is not None else ""
        if mesh and key and (mesh, key) in gen_keys:
            source = "gen"
        elif ours:
            source = "ours_legacy"
        else:
            source = "vendor_clip"
        out.append({
            "source": source,
            "type": "curve" if not e["const"] else "Set",
            "where": e["where"],
            "cond": e["cond"] + ((" & time=%s" % e["time_param"]) if e["time_param"] else ""),
            "value": e["values"][0] if e["const"] and e["values"] else None,
            "values": e["values"],
            "mesh": mesh,
            "key": key,
            "path": e["path"],
            "attribute": e["attribute"],
            "class_id": e["class_id"],
            "layer": e["layer"],
            "state": e["state"],
            "clip": e["clip"],
            "host": "",
            "component": "clip",
            "time_param": e["time_param"],
            "curve": [] if e["const"] else e["curve"],
        })
    return out


# ---------------------------------------------------------------------------
# build_plugins
# ---------------------------------------------------------------------------
ASSEMBLY_PLUGIN_RE = re.compile(
    r"\[assembly:\s*ExportsPlugin\(\s*typeof\(\s*([^)]+?)\s*\)\s*\)\]")
PHASE_RE = re.compile(r"InPhase\(\s*(?:ndmf\.)?BuildPhase\.(\w+)")
QUALIFIED_RE = re.compile(r'QualifiedName\s*=>\s*"([^"]+)"')


def scan_build_plugins(project: str) -> List[dict]:
    pkg_root = os.path.join(project, "Packages")
    if not os.path.isdir(pkg_root):
        return []
    out = []
    for pkg in sorted(os.listdir(pkg_root)):
        pdir = os.path.join(pkg_root, pkg)
        if not os.path.isdir(pdir):
            continue
        plugins: List[str] = []
        phases: Set[str] = set()
        qualified: Set[str] = set()
        for dirpath, dirnames, filenames in os.walk(pdir):
            dirnames[:] = [d for d in dirnames if d not in ("Library", "obj", "Temp")]
            for fn in filenames:
                if not fn.endswith(".cs"):
                    continue
                try:
                    with open(os.path.join(dirpath, fn), "r", encoding="utf-8",
                              errors="replace") as f:
                        text = f.read()
                except OSError:
                    continue
                # 去注释：NDMF 的 ExportsPlugin.cs 文档注释里有一个示例属性，别当真插件
                clean = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
                clean = re.sub(r"//[^\n]*", "", clean)
                for m in ASSEMBLY_PLUGIN_RE.finditer(clean):
                    t = m.group(1).strip().replace("global::", "")
                    t = re.sub(r"\\u([0-9a-fA-F]{4})",
                               lambda mm: chr(int(mm.group(1), 16)), t)
                    if t not in plugins:
                        plugins.append(t)
                for m in PHASE_RE.finditer(clean):
                    phases.add(m.group(1))
                for m in QUALIFIED_RE.finditer(clean):
                    qualified.add(m.group(1))
        if not plugins:
            continue
        reviewed = pkg in KNOWN_REVIEWED_PACKAGES
        out.append({
            "package": pkg,
            "label": KNOWN_REVIEWED_PACKAGES.get(pkg, pkg),
            "plugin_types": plugins,
            "qualified_names": sorted(qualified),
            "phases": sorted(phases),
            "reviewed": reviewed,
            "status": "已登记" if reviewed else "未审",
        })
    out.sort(key=lambda x: x["package"])
    return out


# ---------------------------------------------------------------------------
# 合并
# ---------------------------------------------------------------------------
def build_writer_graph(scan: ProjectScan) -> dict:
    all_w: List[dict] = []
    resolver = clip_writes.ClipResolver(scan.project, None)

    # 1) 我方控制器（默认 _Work/Gen/A2_FX.controller，找不到就扫 _Work 下所有 controller）
    ours_ctrls = []
    for root, dirs, files in os.walk(os.path.join(scan.project, "Assets/_Work")):
        dirs[:] = [d for d in dirs if d != "__Generated"]
        for fn in files:
            if fn.endswith(".controller"):
                ours_ctrls.append(os.path.join(root, fn))
    ours_ctrls.sort()
    for c in ours_ctrls:
        all_w.extend(clip_entries_to_writers(scan, c, resolver))

    # 2) MergeAnimator / descriptor 层的厂商控制器
    ours_set = {os.path.abspath(c) for c in ours_ctrls}
    for c in scan.merged_controllers:
        if c in ours_set:
            continue
        all_w.extend(clip_entries_to_writers(scan, c, resolver))

    # 3) MA 组件：场景（含 m_AddedComponents 落到场景的组件）+ 可达 prefab
    #    prefab 里定义的 MA 组件按「场景实例路径前缀」展开（变体链/嵌套实例都在
    #    prefab_prefixes 里），宿主解析到场景实例路径；前缀解析不出的退回旧名字口径。
    all_w.extend(scan_ma_in_file(scan, scan.scene_path, is_scene=True))
    scanned: Set[str] = set()
    for p in scan.reachable_prefabs:
        key = os.path.abspath(p)
        prefixes = scan.prefab_prefixes.get(key)
        if not prefixes:
            continue
        scanned.add(key)
        for pref in prefixes:
            all_w.extend(scan_ma_in_file(scan, p, is_scene=False, prefix=pref))
    for p in scan.reachable_prefabs:
        if os.path.abspath(p) not in scanned:
            all_w.extend(scan_ma_in_file(scan, p, is_scene=False))

    # 去重 + 分组
    groups: Dict[Tuple[str, str], List[dict]] = {}
    seen = set()
    for w in all_w:
        w["mesh"] = str(w["mesh"]) if w.get("mesh") is not None else ""
        w["key"] = str(w["key"]) if w.get("key") is not None else ""
        if not w["mesh"] and not w["key"]:
            continue
        w["key"] = restore_shape(w["key"]) if w["key"] else w["key"]
        if w["key"] == "m_IsActive":
            pass
        sig = (w["mesh"], w["key"], w["source"], w["where"], w["cond"],
               w["type"], json.dumps(w["values"], sort_keys=True),
               w.get("host", ""), w.get("component", ""), w.get("layer", ""),
               w.get("state", ""), w.get("clip", ""), w.get("attribute", ""))
        if sig in seen:
            continue
        seen.add(sig)
        groups.setdefault((w["mesh"], w["key"]), []).append(w)

    writers: "Dict[str, List[dict]]" = {}
    for (mesh, key) in sorted(groups):
        ws = sorted(groups[(mesh, key)], key=lambda x: (
            str(x["source"]), str(x["where"]), str(x.get("layer", "")),
            str(x.get("state", "")), str(x.get("clip", "")), str(x.get("values"))))
        writers["%s::%s" % (mesh, key)] = ws

    src_count: Dict[str, int] = {}
    for ws in writers.values():
        for w in ws:
            src_count[w["source"]] = src_count.get(w["source"], 0) + 1

    return {
        "schema": "perception/writers/1",
        "generated_by": "writers_static.py",
        "project": scan.project,
        "scene": _rel(scan.scene_path, scan.project),
        "avatar_prefab": _rel(scan.avatar_prefab, scan.project) if scan.avatar_prefab else None,
        "gen_writers": bool(scan.gen_writers),
        "winner_rule": WINNER_RULE,
        "build_plugins": scan_build_plugins(scan.project),
        "sources": dict(sorted(src_count.items())),
        # 03c L1：{(mesh,key): [写者...]}；键拼成 "mesh::key"
        "writers": writers,
        "summary": {
            "keys": len(writers),
            "writers": sum(len(ws) for ws in writers.values()),
            "reachable_prefabs": len(scan.reachable_prefabs),
            "merged_controllers": [_rel(c, scan.project) for c in scan.merged_controllers],
        },
    }


# ---------------------------------------------------------------------------
# 查询 / 自验
# ---------------------------------------------------------------------------
def query(graph: dict, mesh: Optional[str] = None, key: Optional[str] = None) -> List[dict]:
    """按 (mesh,key) 查写者组；返回 [{'mesh','key','writers':[...]}]。"""
    out = []
    for full, ws in graph["writers"].items():
        m, _, k = full.partition("::")
        if mesh is not None and m != mesh:
            continue
        if key is not None and k != key:
            continue
        out.append({"mesh": m, "key": k, "writers": ws})
    return out


def selftest_工程A(project: str) -> int:
    scan = ProjectScan(project)
    graph = build_writer_graph(scan)
    fails: List[str] = []
    print("[selftest] project=%s" % scan.project)
    print("[selftest] scene=%s" % graph["scene"])
    print("[selftest] avatar_prefab=%s" % graph["avatar_prefab"])
    print("[selftest] keys=%d writers=%d reachable_prefabs=%d sources=%s"
          % (graph["summary"]["keys"], graph["summary"]["writers"],
             graph["summary"]["reachable_prefabs"], graph["sources"]))

    # 验收 1：sailor.outer_shlink = {Dial_整套(100/0 按档), Off_部位_外套(0)}
    g = query(graph, mesh="sailor", key="outer_shlink")
    if not g:
        fails.append("缺 (sailor, outer_shlink)")
    else:
        got = {}
        for w in g[0]["writers"]:
            got.setdefault(w["clip"], []).append(w)
        print("[selftest] sailor.outer_shlink writers=%s" % sorted(got))
        if set(got) != {"Dial_整套", "Off_部位_外套"}:
            fails.append("sailor.outer_shlink 写者应恰为 Dial_整套+Off_部位_外套，实际 %s"
                         % sorted(got))
        else:
            dial_vals = sorted({v for w in got["Dial_整套"] for v in w["values"]})
            off_vals = sorted({v for w in got["Off_部位_外套"] for v in w["values"]})
            if dial_vals != [0.0, 100.0]:
                fails.append("Dial_整套 值应为 {0,100}，实际 %s" % dial_vals)
            if off_vals != [0.0]:
                fails.append("Off_部位_外套 应为常量 0，实际 %s" % off_vals)
            if any(w["source"] not in ("ours_legacy", "gen") for w in g[0]["writers"]):
                fails.append("sailor.outer_shlink 来源应为 ours_legacy/gen")

    # 验收 2：Body_b.outer_shrink 同 outer_shlink
    g2 = query(graph, mesh="Body_b", key="outer_shrink")
    if not g2:
        fails.append("缺 (Body_b, outer_shrink)")
    else:
        clips = sorted({w["clip"] for w in g2[0]["writers"]})
        print("[selftest] Body_b.outer_shrink writers=%s" % clips)
        if clips != ["Dial_整套", "Off_部位_外套"]:
            fails.append("Body_b.outer_shrink 写者集合不对：%s" % clips)

    # 验收 3：MMN Foot_heel_OFF = {Socks SC(vendor_sc), Shoes SC(ours_legacy/gen)}
    heel = [g for g in query(graph)
            if g["key"].startswith("Foot_heel_OFF")]
    sources = {}
    hosts = {}
    for grp in heel:
        for w in grp["writers"]:
            sources.setdefault(w["source"], 0)
            sources[w["source"]] += 1
            hosts.setdefault(w.get("where", ""), w.get("host", ""))
    print("[selftest] Foot_heel_OFF keys=%s sources=%s where=%s"
          % (sorted({g["key"] for g in heel}), sources,
             sorted(set(hosts))))
    if "vendor_sc" not in sources:
        fails.append("Foot_heel_OFF 缺 vendor_sc 写者（Socks SC）")
    if not ({"ours_legacy", "gen"} & set(sources)):
        fails.append("Foot_heel_OFF 缺 ours_legacy/gen 写者（Shoes SC）")
    if sources.get("vendor_sc", 0) < 1 or sources.get("ours_legacy", 0) < 1:
        pass

    # 验收 4：build_plugins 7 项
    pkgs = [p["package"] for p in graph["build_plugins"]]
    labels = [p["label"] for p in graph["build_plugins"]]
    print("[selftest] build_plugins(%d)=%s" % (len(pkgs), labels))
    expect = set(KNOWN_REVIEWED_PACKAGES)
    missing = expect - set(pkgs)
    if missing:
        fails.append("build_plugins 缺 %s" % sorted(missing))
    if len(graph["build_plugins"]) != 7:
        fails.append("build_plugins 应恰为 7 项（已登记），实际 %d" % len(graph["build_plugins"]))
    unreviewed = [p["package"] for p in graph["build_plugins"] if not p["reviewed"]]
    print("[selftest] 未审插件=%s（当前应 0 个）" % unreviewed)

    if fails:
        for f in fails:
            print("[FAIL] %s" % f)
        return 1
    print("[selftest] OK")
    return 0


# ---------------------------------------------------------------------------
# 工程B用例：垂耳兔（档 5）厂商变体/嵌套 prefab 上的 MA ShapeChanger。
# 契约（任务 AR）：写者图里要出现垂耳兔那 11 个收缩键，宿主解析到场景实例路径、
# 落在 `08_WhitePink_Milfy_MA` 下；不再用 `<prefab#fid>` 这类取不到名的兜底。
# ---------------------------------------------------------------------------
# 施工记录 09-18 22:56 列出的 11 键（场景 m_AddedComponents 落盘的那批）
ZAIJIAN_RECORD_KEYS = [
    "Shoulder", "Upper_arm", "Elbow", "Lower_arm", "Chest_2",
    "Spine_1", "Spine_2", "Ankle", "Foot", "Toe", "Foot_heels",
]
ZAIJIAN_INSTANCE = "08_WhitePink_Milfy_MA"


def selftest_zaijianjian(project: str) -> int:
    scan = ProjectScan(project)
    graph = build_writer_graph(scan)
    fails: List[str] = []
    print("[selftest:工程B] project=%s" % scan.project)
    print("[selftest:工程B] scene=%s" % graph["scene"])
    print("[selftest:工程B] keys=%d writers=%d reachable_prefabs=%d"
          % (graph["summary"]["keys"], graph["summary"]["writers"],
             graph["summary"]["reachable_prefabs"]))

    # A) 变体链/嵌套 prefab 里定义的 MA ShapeChanger（ModularAvatar.prefab 的
    #    Shrink_* 11 键），宿主应解析到 `.../08_WhitePink_Milfy_MA/ModularAvatar/...`
    shrink: Dict[str, Set[str]] = {}
    for full, ws in graph["writers"].items():
        m, _, k = full.partition("::")
        if m != "Body_base" or not k.startswith("Shrink_"):
            continue
        for w in ws:
            if w.get("host"):
                shrink.setdefault(k, set()).add(str(w["host"]))
    print("[selftest:工程B] 变体/嵌套 prefab(ModularAvatar.prefab) Shrink_* 键=%d %s"
          % (len(shrink), sorted(shrink)))
    if len(shrink) != 11:
        fails.append("变体/嵌套 prefab 的 Shrink_* 应 11 键，实际 %d：%s"
                     % (len(shrink), sorted(shrink)))
    for k, hs in sorted(shrink.items()):
        good = sorted(h for h in hs if ZAIJIAN_INSTANCE in h)
        if not good:
            fails.append("%s 的宿主未落到 %s 下：%s" % (k, ZAIJIAN_INSTANCE, sorted(hs)))
        else:
            print("[selftest:工程B]   %s <- %s" % (k, good[0]))

    # B) 施工记录那 11 键（场景 m_AddedComponents 落的 SC），宿主同样要到实例路径
    rec: Dict[str, Set[str]] = {}
    for k in ZAIJIAN_RECORD_KEYS:
        for grp in query(graph, mesh="Body_base", key=k):
            for w in grp["writers"]:
                if w.get("host"):
                    rec.setdefault(k, set()).add(str(w["host"]))
    print("[selftest:工程B] 施工记录 11 键宿主：")
    for k in ZAIJIAN_RECORD_KEYS:
        hs = sorted(rec.get(k, set()))
        good = [h for h in hs if ZAIJIAN_INSTANCE in h]
        print("[selftest:工程B]   %-10s <- %s" % (k, good[0] if good else hs or "(无宿主)"))
        if not good:
            fails.append("%s 的宿主未落到 %s 下：%s" % (k, ZAIJIAN_INSTANCE, hs))
    missing = [k for k in ZAIJIAN_RECORD_KEYS if k not in rec]
    if missing:
        fails.append("写者图缺这些键：%s" % missing)

    if fails:
        for f in fails:
            print("[FAIL:工程B] %s" % f)
        return 1
    print("[selftest:工程B] OK")
    return 0


def selftest(工程A_project: str, zaijianjian_project: Optional[str] = None) -> int:
    rc = selftest_工程A(工程A_project)
    if zaijianjian_project:
        print("")
        rc2 = selftest_zaijianjian(zaijianjian_project)
        rc = rc or rc2
    return rc


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="静态写者图 writers.json（T-11）")
    ap.add_argument("--project", help="工程根目录")
    ap.add_argument("--scene", help="场景（缺省选 PrefabInstance 最多的 .unity）")
    ap.add_argument("--out", help="输出 writers.json（缺省 <工程>/_感知/out/writers.json）")
    ap.add_argument("--selftest", action="store_true", help="工程A + 工程B数据自验（只读工程）")
    ap.add_argument("--selftest-project", default=os.path.join(
        _HERE, "..", "..", "..", "..", "工程A"),
        help=argparse.SUPPRESS)
    ap.add_argument("--selftest-project-2", default=os.path.join(
        _HERE, "..", "..", "..", "..", "工程B"),
        help=argparse.SUPPRESS)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(os.path.abspath(args.selftest_project),
                        os.path.abspath(args.selftest_project_2)
                        if args.selftest_project_2 else None)
    if not args.project:
        ap.error("需要 --project 或 --selftest")
    scan = ProjectScan(args.project, args.scene)
    graph = build_writer_graph(scan)
    out = args.out or os.path.join(scan.project, "_感知", "out", "writers.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=1, sort_keys=False)
    if not args.quiet:
        print("[writers_static] keys=%d writers=%d → %s"
              % (graph["summary"]["keys"], graph["summary"]["writers"], out))
        for g in query(graph):
            if g["key"].startswith(("outer_shlink", "outer_shrink", "Foot_heel_OFF")):
                print("  %s.%s <- %s" % (g["mesh"], g["key"],
                                         sorted({w["clip"] or w["host"] or w["source"]
                                                 for w in g["writers"]})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
