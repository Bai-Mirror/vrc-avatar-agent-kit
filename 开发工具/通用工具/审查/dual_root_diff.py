#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dual_root_diff.py — 双头像根组件差异普查（离线，只读 Unity YAML）
【项目沉淀】通用工具
适用素体：无关
相关素材：工程场景/预制体 Unity YAML
工具链　：Python 3（离线，只读）
可复用性：★★ 按工程目录跑即可用
用途　　：双头像根组件差异普查（离线只读 Unity YAML），找面捕克隆根与原生根被悄悄改得不一致的地方。


用途
----
一个场景里常常有两份头像根：交付用的面捕克隆根（名字带 `_FT` 等后缀）和原生根。
面捕克隆 / 旧手工操作会让两根悄悄不一致，最险的是「预制体实例在某根上把某个组件
删除（`m_RemovedComponents` 一条）」，构建后 AAO 会把相关形态键一起删掉。

本脚本不启动 Unity，只解析场景 / 预制体的 Unity YAML 文本，对每个工程里
「场景含 >=2 个 VRCAvatarDescriptor 根」的场景做逐 GameObject 差异比对。

判「头像根」
----------
一个 GameObject 的组件里含 VRCAvatarDescriptor（脚本 GUID
`67cc4cb7839cd3741b63733d5adf0442`，fileID `542108242`；两者合起来才是该类，
因为该 GUID 是 VRCSDK3A.dll 整条程序集的 GUID，同一个 guid 下还有很多别的脚本）。
两种形态都认：
  * 场景里直接序列化的 descriptor（inline 根）；
  * 场景里的 PrefabInstance，其源预制体里含 descriptor（prefab 根；工程D即此形态）。
工程D的 `rurune_None_FT` / `rurune_None` 就是同一个 avatar 预制体的两个场景实例。

对齐口径
--------
以每对根为轴，按「根相对路径」对齐两边的**场景级对象**（PrefabInstance 与场景普通
GameObject）。两根的基座预制体通常相同，预制体内部对象逐字节一致；真正会分叉的只有
场景级覆写（`m_RemovedComponents`/`m_AddedComponents`/…）以及 `m_Modifications` 里指向
根预制体**内部对象**的属性覆写（`m_IsActive`/`m_TagString`/`m_Enabled`），两者都比。
挂在预制体内部 transform 上的场景对象，路径里补一段源对象名（补不齐时标
`path_partial`）。路径还原不了的对象记进 `path_unresolved_a/b`，绝不丢弃。

白名单来源
----------
* FT 运行时组件 GUID：`工程D/Packages/com.triturbo.facetrackingframework/Runtime/*.cs.meta`
  与 `Packages/com.triturbo.face-blendshape-fix/Runtime/*.cs.meta`（本机实测读取）。
* 审查 / 感知工具：本工作区 `开发工具/通用工具/审查/unity/Runtime/AuditMappingProbe.cs`
  及各工程 `Assets/AvatarAudit/Runtime/AuditMappingProbe.cs`（每个工程副本 GUID 不同，
  故按解析出的脚本路径识别）。
* FT 安装器加的对象：按名字（`_FT` / `FaceTracking` / `EyeTracking` / `MouthTracking` 等）。
* 其余「厂商组件 GUID→脚本名」现场在工程 `Assets/`+`Packages/` 的 `.meta` 里 grep。

用法
----
  python3 dual_root_diff.py                      # 普查 7 个工程，写 JSON + 汇总.md
  python3 dual_root_diff.py --project COMM-...   # 只跑一个工程
  python3 dual_root_diff.py --scene a.unity --project DIR   # 显式指定
  python3 dual_root_diff.py --selftest           # 工程D基线 vs HEAD 回归
  python3 dual_root_diff.py --list-only          # 只列候选场景，不写产出

只读：本脚本不写任何工程文件（仅写 `_长程任务_20260918/审查产出/` 与 `派工/tmp/cd/`）。
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# 复用写者图那套 Unity 多文档 YAML 读取件（含 UnityLoader 的 On/Off 修正）
sys.path.insert(0, os.path.join(_HERE, "perception"))
try:
    from unity_yaml import load_unity_yaml, DocIndex
except Exception as _e:  # pragma: no cover
    sys.stderr.write("缺少 perception/unity_yaml.py 或 PyYAML：%s\n" % _e)
    raise

# ---------------------------------------------------------------------------
# 常量 / 白名单
# ---------------------------------------------------------------------------
VRC_SCRIPT_GUID = "67cc4cb7839cd3741b63733d5adf0442"   # VRCSDK3A.dll（整条程序集）
VRC_DESCRIPTOR_FILEID = 542108242                       # VRCAvatarDescriptor
VRC_DESCRIPTOR_SIG_KEYS = ("ViewPosition", "ScaleIPD", "lipSync", "customExpressions",
                           "baseAnimationLayers", "FaceMesh")

# 已知 DLL 内脚本 fileID→名（meta 只能给出程序集 GUID，fileID 名字要另找）
DLL_SCRIPT_NAMES = {
    (VRC_SCRIPT_GUID, VRC_DESCRIPTOR_FILEID): "VRCAvatarDescriptor",
    (VRC_SCRIPT_GUID, 1610797297): "VRC_SpatialAudioSource",
}

# 内建组件类型号→名（只列会出现的）
BUILTIN_NAMES = {
    1: "GameObject", 4: "Transform", 20: "Camera", 23: "MeshRenderer",
    33: "MeshFilter", 54: "Rigidbody", 65: "BoxCollider", 82: "AudioSource",
    95: "Animator", 108: "Light", 114: "MonoBehaviour", 120: "LineRenderer",
    136: "CapsuleCollider", 137: "SkinnedMeshRenderer", 143: "CharacterController",
    146: "CapsuleCollider2D", 198: "ParticleSystem", 199: "ParticleSystemRenderer",
    212: "SpriteRenderer", 222: "CanvasRenderer", 223: "Canvas", 224: "RectTransform",
    225: "CanvasGroup", 1001: "PrefabInstance",
}

# --- FT（面捕）白名单：GUID 来源见模块 docstring ---
FT_SCRIPT_GUIDS = {
    # com.triturbo.facetrackingframework / Runtime
    "5d01790a02e6f9047a921c7238e4b936",  # MouthTrackingSettingsComponent
    "eb960126c420f4f488d41da26d4b08f7",  # EmoteLayersModifierComponent
    "90d48a0f737fe9e4ab80300760f6d008",  # InverseVisemeCreatorComponent
    "f26a2ce4169f23c44b75dbdefaf1a9da",  # ExpressionBlendShapesMap
    "0a3c687eef8d0cd46aa00de7cfeb27bb",  # EyeTrackingSettingsComponent
    "3cb2338d9be7a37499cf7d07f9493a60",  # QuantizationParametersCreator
    "445ee76ea8ddc084881a0ebd3b0b176f",  # QuantizationParametersSO
    # com.triturbo.face-blendshape-fix / Runtime
    "b56bc2f54394cf241842f9130e417ccc",  # FaceBlendShapeFixComponent
    "26d17a633b5b405cbd95e81334146333",  # AvatarObjectReference
    "956828ca12e2a4041942ef7c329b4f00",  # TargetShape
    "645cf09d199af324282dd77d3f9ea8cc",  # BlendShapeDefinition
    "b1cb1e3f3ecf68145a6b9532145b558e",  # BlendData
}
FT_SCRIPT_PATH_RE = re.compile(r"facetracking|face.?tracking|triturbo|FaceBlendShapeFix", re.I)
FT_NAME_RE = re.compile(
    r"(^|[/_\- ])(_?FT|FaceTracking|Face Tracking|EyeTracking|Eye Tracking|"
    r"MouthTracking|Mouth Tracking|FACS)([/_\- ]|$)",
    re.I)
# 组件串（如 "addedGO:['Face Tracking']"）里的 FT 关键字：放宽边界
FT_ANY_NAME_RE = re.compile(r"Face ?Tracking|Eye ?Tracking|Mouth ?Tracking|_FT\b|FACS", re.I)
# --- 审查 / 感知工具白名单 ---
AUDIT_SCRIPT_PATH_RE = re.compile(r"AvatarAudit|perception|通用工具/审查|_感知|AuditMapping", re.I)
AUDIT_NAME_RE = re.compile(r"_感知|审计|审查|Audit|Probe", re.I)

# 场景里非主场景的厂商示例 / 备份文件名（范围里要求排除）
NON_MAIN_SCENE_RE = re.compile(
    r"(Sample Scene|LockDev|Generator|_backup|beforeMPBfix|before60B)", re.I)
# 厂商资产目录下的场景不算工程主场景（相对 Assets/ 的路径）
VENDOR_SCENE_RE = re.compile(
    r"^(MOCHIYAMA|YaokiSubWork|RBS|Logilabo|IKUSIA|BUGAISYA|しゃけのいけす|"
    r"Triturbo|ILE'S SHOP)/", re.I)

DEFAULT_OUT = "_长程任务_20260918/审查产出/dual_root_diff"
TMP_DIR = "_长程任务_20260918/派工/tmp/cd"


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def _relpath(path, root):
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def is_descriptor(doc):
    """MonoBehaviour 是否 VRCAvatarDescriptor：fileID 精确匹配，否则用字段签名兜底。"""
    if doc.class_id != 114:
        return False
    s = doc.get("m_Script") or {}
    if s.get("guid") != VRC_SCRIPT_GUID:
        return False
    if s.get("fileID") == VRC_DESCRIPTOR_FILEID:
        return True
    return any(k in doc.data for k in VRC_DESCRIPTOR_SIG_KEYS)


def _fid(d):
    if isinstance(d, dict):
        return d.get("fileID", 0) or 0
    return 0


def _as_bool(v):
    try:
        return bool(int(v))
    except (TypeError, ValueError):
        return None


_AMBIG_SEG_RE = re.compile(r"~\d+$")


def _is_ambiguous_path(path):
    """路径里含同名兄弟消歧后缀 `~N` → 跨根一一对应不确定，不能猜。"""
    return any(_AMBIG_SEG_RE.search(seg) for seg in (path or "").split("/"))


class Project:
    """一个工程：GUID→资源路径索引、脚本名解析、预制体 / 场景文档缓存。"""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.name = os.path.basename(self.root)
        self.guid_index = self._build_guid_index()
        self._docs = {}
        self._tf_info = {}
        self._pf_root_gos = {}
        self._script_cache = {}

    # -- GUID 索引：Assets/ + Packages/ 下所有 .meta --
    def _build_guid_index(self):
        idx = {}
        for base in ("Assets", "Packages"):
            d0 = os.path.join(self.root, base)
            if not os.path.isdir(d0):
                continue
            for dirpath, dirnames, filenames in os.walk(d0):
                dirnames[:] = [d for d in dirnames
                               if d not in (".git", "Library", "Temp", "obj", "node_modules")]
                for fn in filenames:
                    if not fn.endswith(".meta"):
                        continue
                    p = os.path.join(dirpath, fn)
                    try:
                        with open(p, "r", encoding="utf-8", errors="replace") as f:
                            head = f.read(512)
                    except OSError:
                        continue
                    m = re.search(r"^guid:\s*([0-9a-fA-F]+)\s*$", head, re.M)
                    if m:
                        idx.setdefault(m.group(1), p[: -len(".meta")])
        return idx

    def load(self, path):
        path = os.path.abspath(path)
        if path not in self._docs:
            self._docs[path] = load_unity_yaml(path)
        return self._docs[path]

    def guid_path(self, guid):
        return self.guid_index.get(guid)

    def script_name(self, guid, fileid):
        key = (guid, fileid)
        if key in self._script_cache:
            return self._script_cache[key]
        name = None
        if key in DLL_SCRIPT_NAMES:
            name = DLL_SCRIPT_NAMES[key]
        else:
            p = self.guid_path(guid)
            if p:
                base = os.path.basename(p)
                if p.endswith(".dll"):
                    name = "%s#%s" % (base, fileid)
                else:
                    name = os.path.splitext(base)[0] or base
            else:
                name = "guid=%s" % guid
        self._script_cache[key] = name
        return name

    def script_path(self, guid):
        return self.guid_path(guid) or ""

    def is_path_in_project(self, path):
        try:
            return os.path.commonpath([self.root, os.path.abspath(path)]) == self.root
        except ValueError:
            return False

    # -- 预制体解析 --
    def pf_docs(self, path):
        return self.load(path)

    def pf_chain_paths(self, pf_path, depth=0, seen=None):
        """预制体变体链：本体 + 根级 PrefabInstance 的源（递归）。

        工程D的 avatar 预制体把 descriptor 加在自己这层；工程C/工程F的 avatar 是
        `*_FT Variant.prefab` → 基座 prefab 的变体链，descriptor 只在基座里。
        """
        if seen is None:
            seen = set()
        if not pf_path or depth > 12:
            return []
        pf_path = os.path.abspath(pf_path)
        if pf_path in seen or not pf_path.endswith((".prefab", ".asset")):
            return []
        if not os.path.exists(pf_path):
            return []
        seen.add(pf_path)
        out = [pf_path]
        try:
            docs = self.load(pf_path)
        except Exception:
            return out
        for pi in [d for d in docs if d.class_id == 1001]:
            mod = pi.get("m_Modification") or {}
            if _fid(mod.get("m_TransformParent")) or 0:
                continue  # 只跟变体（根级）链，别钻普通嵌套
            guid = (pi.get("m_SourcePrefab") or {}).get("guid")
            child = self.guid_path(guid)
            if child:
                out += self.pf_chain_paths(child, depth + 1, seen)
        return out

    def pf_chain_docs(self, pf_path):
        """变体链上所有文档的并集（fileID 在链上是唯一的）。"""
        key = ("chaindocs", os.path.abspath(pf_path) if pf_path else None)
        if key in self._docs:
            return self._docs[key]
        merged = []
        for p in self.pf_chain_paths(pf_path):
            try:
                merged += self.load(p)
            except Exception:
                pass
        self._docs[key] = merged
        return merged

    @staticmethod
    def comps_by_go(docs):
        m = collections.defaultdict(list)
        for d in docs:
            if d.class_id in (1, 1001):
                continue
            go = _fid(d.get("m_GameObject"))
            if go:
                m[go].append(d)
        return m

    @staticmethod
    def go_name(docs, go_fid):
        for d in docs:
            if d.class_id == 1 and d.file_id == go_fid:
                return d.get("m_Name") or ""
        return ""

    def pf_tf_info(self, pf_path, src_tf):
        """预制体里某 transform 的 (名字, 父 transform fileID 或 None)。

        处理「预制体根本身是嵌套预制体实例」：此时 transform 是 stripped 文档，父取
        嵌套 PrefabInstance 的 m_TransformParent；若嵌套根则继续向外。
        """
        pf_path = os.path.abspath(pf_path) if pf_path else None
        key = (pf_path, src_tf)
        if key in self._tf_info:
            return self._tf_info[key]
        self._tf_info[key] = (None, None)  # 防环
        if not pf_path or not os.path.exists(pf_path):
            return self._tf_info[key]
        if not pf_path.endswith((".prefab", ".asset")):
            # 模型（.fbx/.obj 等）不可当预制体解析：当叶子根，父为空
            leaf = os.path.splitext(os.path.basename(pf_path))[0]
            self._tf_info[key] = (leaf, None)
            return self._tf_info[key]
        try:
            docs = self.pf_chain_docs(pf_path)
        except Exception:
            self._tf_info[key] = (None, None)
            return self._tf_info[key]
        d = next((x for x in docs if x.class_id == 4 and x.file_id == src_tf), None)
        if d is None:
            self._tf_info[key] = (None, None)
            return self._tf_info[key]
        if not d.stripped:
            name = self.go_name(docs, _fid(d.get("m_GameObject")))
            par = _fid(d.get("m_Father")) or None
            self._tf_info[key] = (name, par)
            return self._tf_info[key]
        qfid = _fid(d.get("m_PrefabInstance"))
        q = next((x for x in docs if x.class_id == 1001 and x.file_id == qfid), None)
        if q is None:
            self._tf_info[key] = (None, None)
            return self._tf_info[key]
        qguid = _fid((q.get("m_SourcePrefab") or {}))
        qguid = (q.get("m_SourcePrefab") or {}).get("guid")
        corr = _fid(d.get("m_CorrespondingSourceObject"))
        qpath = self.guid_path(qguid)
        qname, qpar = self.pf_tf_info(qpath, corr)
        if qpar is None:
            mod = q.get("m_Modification") or {}
            qpar2 = _fid(mod.get("m_TransformParent")) or None
            self._tf_info[key] = (qname, qpar2)
        else:
            self._tf_info[key] = (qname, qpar)
        return self._tf_info[key]

    def pf_root_gos(self, pf_path, name_targets=None):
        """预制体根对象 GO fileID 列表（用于取根组件集）。"""
        pf_path = os.path.abspath(pf_path) if pf_path else None
        cache_key = (pf_path, tuple(sorted(name_targets or ())))
        if cache_key in self._pf_root_gos:
            return self._pf_root_gos[cache_key]
        res = []
        if pf_path and os.path.exists(pf_path) and pf_path.endswith((".prefab", ".asset")):
            docs = self.pf_chain_docs(pf_path)
            # 结构性根优先：descriptor 所在 GO / 无父 transform 的普通 GO。
            # 注意：m_Name 覆写的 target 不一定就是根（内部子对象也能改名），
            # 所以 name_targets 只作最后兜底，不能反过来当根用。
            desc = [fid for fid in {_fid(d.get("m_GameObject")) for d in docs if is_descriptor(d)}]
            res = list(desc)
            if not res:
                for d in docs:
                    if d.class_id == 4 and not d.stripped and not _fid(d.get("m_Father")):
                        go = _fid(d.get("m_GameObject"))
                        if go:
                            res.append(go)
            if not res:
                res = [fid for d in docs if d.class_id == 1 and not d.stripped
                       for fid in [d.file_id] if fid]
            if not res and name_targets:
                res = [t for t in name_targets if t]
        elif name_targets:
            res = [t for t in name_targets if t]
        self._pf_root_gos[cache_key] = res
        return res

    def pf_has_descriptor(self, pf_path):
        if not pf_path or not os.path.exists(pf_path):
            return False
        if not pf_path.endswith((".prefab", ".asset")):
            return False
        try:
            return any(is_descriptor(d) for d in self.pf_chain_docs(pf_path))
        except Exception:
            return False


# ---------------------------------------------------------------------------
# 组件键 / 显示名
# ---------------------------------------------------------------------------
def comp_key(doc):
    if doc.class_id == 114:
        s = doc.get("m_Script") or {}
        return "script:%s:%s" % (s.get("guid", ""), s.get("fileID", 0))
    return "builtin:%d" % doc.class_id


def comp_display(doc, project):
    if doc is None:
        return "?"
    if doc.class_id == 114:
        s = doc.get("m_Script") or {}
        return project.script_name(s.get("guid", ""), s.get("fileID", 0))
    return BUILTIN_NAMES.get(doc.class_id, "Class%d" % doc.class_id)


def comp_display_from_key(key, project):
    parts = key.split(":")
    if parts[0] == "script" and len(parts) == 3:
        return project.script_name(parts[1], parts[2])
    if parts[0] == "builtin" and len(parts) == 2:
        try:
            return BUILTIN_NAMES.get(int(parts[1]), "Class%s" % parts[1])
        except ValueError:
            return key
    return key


# ---------------------------------------------------------------------------
# 场景审计
# ---------------------------------------------------------------------------
class Root:
    def __init__(self, owner_key, name, kind, source_prefab=None):
        self.owner_key = owner_key          # "pi:<fid>" | "go:<fid>"
        self.name = name
        self.kind = kind                    # "prefab" | "inline"
        self.source_prefab = source_prefab


class SceneAudit:
    def __init__(self, scene_path, project):
        self.path = os.path.abspath(scene_path)
        self.project = project
        self.docs = project.load(self.path)
        self.idx = DocIndex(self.docs)
        self.by_fid = self.idx.by_fid
        self.comps_by_go = Project.comps_by_go(self.docs)
        self.pi_by_fid = {d.file_id: d for d in self.idx.all(1001)}
        self._owner_of_tf = {}
        self._owner_parent_tf = {}
        self._owner_name = {}
        self._owner_kind = {}     # owner -> "plain" | "prefab"
        self._owner_pi = {}       # owner -> PI doc
        self._owner_go = {}       # owner -> GO doc
        self._pi_corr_tf = collections.defaultdict(dict)  # pi -> {corr_fid: scene_tf}
        self._pi_stripped_tf = collections.defaultdict(set)
        self._path_cache = {}
        self._build_owners()

    # -- 建 owner 图 --
    def _build_owners(self):
        for d in self.idx.all(4):
            pi = _fid(d.get("m_PrefabInstance"))
            if d.stripped and pi:
                if pi in self.pi_by_fid:
                    self._owner_of_tf[d.file_id] = "pi:%d" % pi
                    self._pi_stripped_tf[pi].add(d.file_id)
                    corr = _fid(d.get("m_CorrespondingSourceObject"))
                    if corr:
                        self._pi_corr_tf[pi][corr] = d.file_id
        for d in self.idx.all(4):
            if d.stripped:
                continue
            go = _fid(d.get("m_GameObject"))
            if not go:
                continue
            self._owner_of_tf[d.file_id] = "go:%d" % go
        # GO 名字
        for d in self.idx.all(1):
            if d.stripped:
                continue
            self._owner_go["go:%d" % d.file_id] = d
        # plain GO 的 owner 信息
        for d in self.idx.all(4):
            if d.stripped:
                continue
            go = _fid(d.get("m_GameObject"))
            if not go:
                continue
            ok = "go:%d" % go
            self._owner_parent_tf[ok] = _fid(d.get("m_Father")) or 0
            self._owner_name[ok] = self._go_name_of(go)
            self._owner_kind[ok] = "plain"
        # PI owner
        for pi in self.idx.all(1001):
            ok = "pi:%d" % pi.file_id
            mod = pi.get("m_Modification") or {}
            self._owner_parent_tf[ok] = _fid(mod.get("m_TransformParent")) or 0
            self._owner_name[ok] = self._pi_name(pi)
            self._owner_kind[ok] = "prefab"
            self._owner_pi[ok] = pi

    def _go_name_of(self, go_fid):
        d = self.by_fid.get(go_fid)
        if d is not None and d.class_id == 1:
            return d.get("m_Name") or ""
        return ""

    def _pi_name(self, pi):
        for m in (pi.get("m_Modification") or {}).get("m_Modifications") or []:
            if m.get("propertyPath") == "m_Name":
                return str(m.get("value"))
        guid = (pi.get("m_SourcePrefab") or {}).get("guid")
        p = self.project.guid_path(guid)
        if p:
            return os.path.splitext(os.path.basename(p))[0]
        return "PI:%d" % pi.file_id

    def _pi_name_targets(self, pi):
        """PI 的 m_Name 覆写 target（Unity 约定：它就是实例根对象）。"""
        mod = pi.get("m_Modification") or {}
        return [_fid(m.get("target")) for m in mod.get("m_Modifications") or []
                if m.get("propertyPath") == "m_Name" and _fid(m.get("target"))]

    def _pi_root_go_set(self, pi, ppath):
        """实例根对象集合 = 源预制体结构性根 ∪ m_Name 覆写 target。

        包装型预制体（如 Shinano_AMS.prefab 里再嵌 Shinano.prefab）里，结构性根是
        基座里的 descriptor GO，而场景 mod 的 target 指向包装预制体自己的根对象，
        两者 fileID 不同；两边都要算根，否则根的 m_IsActive 会被当成内部子对象。
        """
        s = set(self.project.pf_root_gos(ppath) or [])
        s |= set(self._pi_name_targets(pi))
        return s

    # -- 找头像根 --
    def find_roots(self):
        roots = []
        # inline descriptor
        seen_go = set()
        for d in self.idx.all(114):
            if not is_descriptor(d):
                continue
            go = _fid(d.get("m_GameObject"))
            if not go or go in seen_go:
                continue
            # 预制体实例上的 descriptor（stripped GO / stripped MB）交给下面的 PI 分支，
            # 否则同一个根会被算两次（工程G.unity 空名根即此）
            if d.stripped or _fid(d.get("m_PrefabInstance")):
                continue
            gd = self.by_fid.get(go)
            if gd is None or gd.stripped:
                continue
            seen_go.add(go)
            ok, kind = self._top_owner_of(go)
            roots.append(Root(ok, self._owner_name.get(ok, self._go_name_of(go)), kind))
        # prefab instance whose source prefab has a descriptor
        for pi in self.idx.all(1001):
            guid = (pi.get("m_SourcePrefab") or {}).get("guid")
            p = self.project.guid_path(guid)
            if not p:
                continue
            if not self.project.pf_has_descriptor(p):
                continue
            ok = "pi:%d" % pi.file_id
            roots.append(Root(ok, self._pi_name(pi), "prefab",
                              _relpath(p, self.project.root)))
        # 去重 + 只保留顶层根（父链里没有别的根）
        uniq = {}
        for r in roots:
            uniq[r.owner_key] = r
        roots = list(uniq.values())
        roots = [r for r in roots if not self._has_root_ancestor(r.owner_key)]
        return roots

    def _top_owner_of(self, go_fid):
        """plain GO 沿 m_Father 上行；若撞到 stripped transform 则归其 PI。"""
        seen = set()
        cur_go = go_fid
        while cur_go and cur_go not in seen:
            seen.add(cur_go)
            tf = self.idx.go_transform(cur_go)
            if tf is None:
                return "go:%d" % cur_go, "inline"
            td = self.by_fid.get(tf)
            if td is None:
                return "go:%d" % cur_go, "inline"
            if td.stripped:
                pi = _fid(td.get("m_PrefabInstance"))
                if pi:
                    return "pi:%d" % pi, "prefab"
                return "go:%d" % cur_go, "inline"
            father = _fid(td.get("m_Father"))
            if not father:
                return "go:%d" % cur_go, "inline"
            fd = self.by_fid.get(father)
            if fd is None:
                return "go:%d" % cur_go, "inline"
            cur_go = _fid(fd.get("m_GameObject"))
        return "go:%d" % go_fid, "inline"

    def _has_root_ancestor(self, owner_key):
        """沿 parent 链上溯，是否经过另一个 prefab 根（防止把根内部的子 PI 当根）。"""
        cur = owner_key
        seen = set()
        first = True
        while cur and cur not in seen:
            seen.add(cur)
            ptf = self._owner_parent_tf.get(cur, 0)
            if not ptf:
                return False
            powner = self._owner_of_tf.get(ptf)
            if powner is None:
                return False
            if not first and self._owner_kind.get(powner) == "prefab":
                pguid = (self._owner_pi.get(powner, {}).get("m_SourcePrefab") or {}).get("guid")
                pp = self.project.guid_path(pguid)
                if pp and self.project.pf_has_descriptor(pp):
                    return True
            first = False
            cur = powner
        return False

    # -- owner 树 --
    def _children_map(self):
        ch = collections.defaultdict(list)
        for owner, ptf in self._owner_parent_tf.items():
            if ptf and ptf in self._owner_of_tf:
                ch[self._owner_of_tf[ptf]].append(owner)
        return ch

    def _internal_extra(self, owner, parent_tf):
        """父 transform 是预制体内部对象时，补一段源名字。"""
        if not parent_tf:
            return None
        td = self.by_fid.get(parent_tf)
        if td is None or not td.stripped:
            return None
        pi = _fid(td.get("m_PrefabInstance"))
        pi_doc = self.pi_by_fid.get(pi)
        if pi_doc is None:
            return None
        guid = (pi_doc.get("m_SourcePrefab") or {}).get("guid")
        p = self.project.guid_path(guid)
        src_tf = _fid(td.get("m_CorrespondingSourceObject"))
        name, par = self.project.pf_tf_info(p, src_tf)
        if par is None:
            return None  # 该 transform 就是 PI 根，不补
        # 名字覆写
        for m in (pi_doc.get("m_Modification") or {}).get("m_Modifications") or []:
            if m.get("propertyPath") == "m_Name" and _fid(m.get("target")) == src_tf:
                if m.get("value"):
                    name = m.get("value")
        return name or None

    def walk(self, root_owner):
        """返回 [(owner, rel_path_list, partial)]，含 root 自身。"""
        ch = self._children_map()
        out = []

        def rec(owner, segs, partial):
            out.append((owner, list(segs), partial))
            # 同名兄弟消歧
            kids = ch.get(owner, [])
            namecount = collections.Counter(self._owner_name.get(k, "") for k in kids)
            idx_of = collections.Counter()
            for k in sorted(kids):
                nm = self._owner_name.get(k, "")
                suf = ""
                if namecount[nm] > 1:
                    idx_of[nm] += 1
                    suf = "~%d" % idx_of[nm]
                ptf = self._owner_parent_tf.get(k, 0)
                extra = self._internal_extra(k, ptf)
                rec(k, segs + ([extra] if extra else []) + [nm + suf],
                    partial or bool(extra))
        rec(root_owner, [], False)
        return out

    # -- 单个 owner 的信息 --
    def owner_info(self, owner):
        info = {
            "owner": owner,
            "name": self._owner_name.get(owner, ""),
            "kind": self._owner_kind.get(owner, ""),
            "source_prefab": None,
            "components": [],       # [(key, display)]
            "removed_components": [],   # [{key, display, target, target_path}]
            "added_components": [],
            "removed_gameobjects": [],
            "added_gameobjects": [],
            "is_active": None,
            "tag": None,
            "enabled_map": {},      # component key -> bool
            "unresolved": [],
        }
        if owner.startswith("go:"):
            go = int(owner.split(":")[1])
            gd = self.by_fid.get(go)
            if gd is not None:
                info["is_active"] = bool(int(gd.get("m_IsActive", 1) or 0))
                tag = gd.get("m_TagString")
                info["tag"] = tag if tag not in (None, "") else "Untagged"
            for cd in self.comps_by_go.get(go, []):
                key = comp_key(cd)
                info["components"].append([key, comp_display(cd, self.project)])
                if "m_Enabled" in cd.data:
                    info["enabled_map"][key] = bool(int(cd.get("m_Enabled", 1) or 0))
            info["components"].sort()
            return info
        # prefab owner
        pi = self._owner_pi.get(owner)
        if pi is None:
            info["unresolved"].append("no_pi_doc")
            return info
        guid = (pi.get("m_SourcePrefab") or {}).get("guid")
        ppath = self.project.guid_path(guid)
        info["source_prefab"] = _relpath(ppath, self.project.root) if ppath else None
        if not ppath or not os.path.exists(ppath):
            info["unresolved"].append("source_prefab_missing:%s" % guid)
            return info
        if not ppath.endswith((".prefab", ".asset")):
            info["unresolved"].append("source_is_model:%s" % _relpath(ppath, self.project.root))
            return info
        mod = pi.get("m_Modification") or {}
        pf_docs = self.project.pf_chain_docs(ppath)
        pf_comps = Project.comps_by_go(pf_docs)
        name_targets = self._pi_name_targets(pi)
        root_gos = sorted(self._pi_root_go_set(pi, ppath)) or list(name_targets)
        base = []
        for go in root_gos:
            for cd in pf_comps.get(go, []):
                base.append(cd)
        # 覆写：m_Modifications 里的 m_IsActive/m_TagString/m_Enabled
        mods = mod.get("m_Modifications") or []
        name_by_target = {}
        for m in mods:
            path = m.get("propertyPath")
            val = m.get("value")
            if path == "m_Name":
                name_by_target[_fid(m.get("target"))] = val
        # 根名字：优先指向结构性根对象的 m_Name 覆写（内部子对象也可能有 m_Name 覆写）
        root_go_set = set(root_gos or [])
        name_mods = [m for m in mods if m.get("propertyPath") == "m_Name"]
        pick = next((m for m in name_mods if _fid(m.get("target")) in root_go_set), None)
        if pick is None and name_mods:
            pick = name_mods[0]
        if pick is not None:
            info["name"] = str(pick.get("value"))
        # active / tag：只认指向根对象的覆写。
        # 一个 PI 常有多条 m_IsActive（分别指向根和内部子对象），取「最后一条」会把
        # 根的开关吞掉——工程A / 工程E 的根 isActive 差异就是这样被漏掉的。
        info["is_active"] = None
        for m in mods:
            if m.get("propertyPath") != "m_IsActive":
                continue
            if root_go_set and _fid(m.get("target")) not in root_go_set:
                continue
            try:
                info["is_active"] = bool(int(m.get("value")))
            except (TypeError, ValueError):
                pass
        if info["is_active"] is None and root_gos:
            gd = next((d for d in pf_docs if d.class_id == 1 and d.file_id == root_gos[0]), None)
            if gd is not None:
                info["is_active"] = bool(int(gd.get("m_IsActive", 1) or 0))
        for m in mods:
            if m.get("propertyPath") != "m_TagString":
                continue
            if root_go_set and _fid(m.get("target")) not in root_go_set:
                continue
            info["tag"] = m.get("value")
        if info["tag"] is None and root_gos:
            gd = next((d for d in pf_docs if d.class_id == 1 and d.file_id == root_gos[0]), None)
            if gd is not None:
                info["tag"] = gd.get("m_TagString") or "Untagged"
        # 组件集 = base - removed + added
        comps = {comp_key(cd): comp_display(cd, self.project) for cd in base}
        fid_to_key = {cd.file_id: comp_key(cd) for cd in base}
        enabled = {}
        for cd in base:
            if "m_Enabled" in cd.data:
                enabled[comp_key(cd)] = bool(int(cd.get("m_Enabled", 1) or 0))
        # 根组件的 m_Enabled 覆写
        for m in mods:
            if m.get("propertyPath") != "m_Enabled":
                continue
            k = fid_to_key.get(_fid(m.get("target")))
            if k is None:
                continue
            try:
                enabled[k] = bool(int(m.get("value")))
            except (TypeError, ValueError):
                pass
        # removed
        for entry in mod.get("m_RemovedComponents") or []:
            cguid = entry.get("guid")
            cfid = _fid(entry)
            cdoc, cpath = self._find_component(cguid, cfid)
            if cdoc is None:
                info["unresolved"].append("removed_component_unresolved:%s:%s" % (cguid, cfid))
                disp = "%s#%s" % (cguid, cfid)
                key = "script:%s:%s" % (cguid, cfid)
            else:
                key = comp_key(cdoc)
                disp = comp_display(cdoc, self.project)
            info["removed_components"].append(
                {"key": key, "display": disp, "target": cpath})
            comps.pop(key, None)
            enabled.pop(key, None)
        # added
        for entry in mod.get("m_AddedComponents") or []:
            scene_fid = _fid(entry.get("addedObject"))
            sd = self.by_fid.get(scene_fid)
            if sd is None:
                info["unresolved"].append("added_component_unresolved:%s" % scene_fid)
                continue
            key = comp_key(sd)
            disp = comp_display(sd, self.project)
            info["added_components"].append({"key": key, "display": disp})
            comps[key] = disp
            if "m_Enabled" in sd.data:
                enabled[key] = bool(int(sd.get("m_Enabled", 1) or 0))
        # removed/added gameobjects
        for entry in mod.get("m_RemovedGameObjects") or []:
            gguid = entry.get("guid")
            gfid = _fid(entry)
            gpath = self.project.guid_path(gguid)
            gname = gfid
            if gpath and os.path.exists(gpath):
                gname = Project.go_name(self.project.load(gpath), gfid) or gfid
            info["removed_gameobjects"].append({"name": gname, "fid": gfid, "guid": gguid})
        for entry in mod.get("m_AddedGameObjects") or []:
            added = entry.get("addedObject") or {}
            afid = _fid(added)
            aname = self._scene_transform_name(afid)
            tgt = entry.get("targetCorrespondingSourceObject") or {}
            info["added_gameobjects"].append(
                {"name": aname, "fid": afid,
                 "target_fid": _fid(tgt), "target_guid": tgt.get("guid")})
        info["components"] = sorted([[k, v] for k, v in comps.items()])
        info["enabled_map"] = enabled
        return info

    def _scene_transform_name(self, tf_fid):
        if not tf_fid:
            return str(tf_fid)
        td = self.by_fid.get(tf_fid)
        if td is None:
            return "#%s" % tf_fid
        if td.stripped:
            pi = _fid(td.get("m_PrefabInstance"))
            pi_doc = self.pi_by_fid.get(pi)
            if pi_doc is not None:
                return self._pi_name(pi_doc)
            return "#%s" % tf_fid
        go = _fid(td.get("m_GameObject"))
        return self._go_name_of(go) or "#%s" % tf_fid

    def _find_component(self, guid, fid):
        """在 guid 对应的预制体里按 fileID 找组件文档；返回 (doc, GO 路径名)。"""
        p = self.project.guid_path(guid)
        if not p or not os.path.exists(p):
            return None, None
        try:
            docs = self.project.pf_chain_docs(p)
        except Exception:
            docs = self.project.load(p)
        d = next((x for x in docs if x.file_id == fid), None)
        if d is None or d.class_id in (1, 4):
            return None, None
        go = _fid(d.get("m_GameObject"))
        return d, Project.go_name(docs, go)

    # -- 预制体内部对象覆写比对 --
    # 两个根实例常共享同一个源预制体；内部对象本身逐字节一致，唯一能分叉的是场景里
    # 那条 PrefabInstance 的 m_Modifications（target 指向源预制体内部对象）。所以只要
    # 把「至少被一根覆写过」的对象挑出来，逐属性比有效值，就能把藏在内部的
    # m_IsActive / m_TagString / m_Enabled 差异挖出来（根对象本身由 owner_info 管）。
    @staticmethod
    def _go_tf_map(docs):
        m = {}
        for d in docs:
            if d.class_id == 4:
                go = _fid(d.get("m_GameObject"))
                if go:
                    m[go] = d.file_id
        return m

    def _tf_path(self, ppath, tf_fid, gomap):
        """预制体内某 transform 的相对路径（用 pf_tf_info 还原变体 / 嵌套名）。"""
        segs = []
        seen = set()
        cur = tf_fid
        ok = False
        while cur and cur not in seen:
            seen.add(cur)
            name, par = self.project.pf_tf_info(ppath, cur)
            if name:
                segs.append(name)
                ok = True
            if par is None:
                break
            cur = par
        segs.reverse()
        return "/".join(segs), ok

    def _resolve_prefab_target(self, ppath, docs, gomap, fid):
        """把 mod target fileID 还原成 {path, kind, doc}；path 还原不了时 path_ok=False。"""
        d = next((x for x in docs if x.file_id == fid), None)
        if d is None:
            return {"path": None, "kind": None, "doc": None, "fid": fid, "path_ok": False}
        if d.class_id == 1:
            tf = gomap.get(fid)
            path, ok = self._tf_path(ppath, tf, gomap) if tf else ("", False)
            return {"path": path, "kind": "go", "doc": d, "fid": fid, "path_ok": ok}
        if d.class_id == 4:
            path, ok = self._tf_path(ppath, fid, gomap)
            go = _fid(d.get("m_GameObject"))
            return {"path": path, "kind": "go", "doc": self.by_fid.get(go) or d,
                    "fid": go or fid, "path_ok": ok}
        go = _fid(d.get("m_GameObject"))
        tf = gomap.get(go)
        path, ok = self._tf_path(ppath, tf, gomap) if tf else ("", False)
        return {"path": path, "kind": "comp", "doc": d, "fid": fid, "path_ok": ok}

    @staticmethod
    def _eff(doc, prop, override):
        if override is not None:
            if prop == "m_TagString":
                return str(override)
            v = _as_bool(override)
            return v
        if doc is None:
            return None
        if prop == "m_TagString":
            return doc.get("m_TagString") or "Untagged"
        if prop in ("m_IsActive", "m_Enabled"):
            return _as_bool(doc.get(prop, 1))
        return None

    def internal_override_diffs(self, a, b):
        """两根实例内部对象（非根）的有效 m_IsActive/m_TagString/m_Enabled 差异。

        返回 (entries, notes)：entries 是待分类的原始条目；notes 记无法对齐的情形。
        """
        notes = []
        pa = self._owner_pi.get(a.owner_key)
        pb = self._owner_pi.get(b.owner_key)
        if pa is None or pb is None:
            return [], notes
        ga = (pa.get("m_SourcePrefab") or {}).get("guid")
        gb = (pb.get("m_SourcePrefab") or {}).get("guid")
        if not ga or ga != gb:
            notes.append("different_source_prefab:%s/%s" % (ga, gb))
            return [], notes
        ppath = self.project.guid_path(ga)
        if not ppath or not os.path.exists(ppath) or not ppath.endswith((".prefab", ".asset")):
            notes.append("source_prefab_unresolved:%s" % ga)
            return [], notes
        docs = self.project.pf_chain_docs(ppath)
        gomap = self._go_tf_map(docs)
        root_skip = self._pi_root_go_set(pa, ppath) | self._pi_root_go_set(pb, ppath)
        # 收集被覆写的 target（只收 m_IsActive / m_TagString / m_Enabled）
        data = {}
        for side, pi in (("a", pa), ("b", pb)):
            mod = pi.get("m_Modification") or {}
            for m in mod.get("m_Modifications") or []:
                prop = m.get("propertyPath")
                if prop not in ("m_IsActive", "m_TagString", "m_Enabled"):
                    continue
                tgt = m.get("target") or {}
                if (tgt.get("guid") or "") != ga:
                    continue
                fid = _fid(tgt)
                if not fid or fid in root_skip:
                    continue
                data.setdefault(fid, {"a": {}, "b": {}})[side][prop] = m.get("value")
        entries = []
        for fid in sorted(data):
            info = self._resolve_prefab_target(ppath, docs, gomap, fid)
            props = data[fid]
            if not info["path_ok"]:
                notes.append("path_unresolved:%s" % fid)
            doc = info["doc"]
            pref = _relpath(ppath, self.project.root)
            for prop in ("m_IsActive", "m_TagString", "m_Enabled"):
                va = props["a"].get(prop)
                vb = props["b"].get(prop)
                if va is None and vb is None:
                    continue
                ea = self._eff(doc, prop, va)
                eb = self._eff(doc, prop, vb)
                if ea == eb or ea is None or eb is None:
                    continue
                if prop == "m_Enabled":
                    kind = "enabled_diff"
                    comp = "%s enabled %s vs %s" % (
                        comp_display(doc, self.project) if doc is not None else "?",
                        ea, eb)
                    key = comp_key(doc) if doc is not None else None
                elif prop == "m_TagString":
                    kind = "tag_diff"
                    comp = "tag %r vs %r" % (ea, eb)
                    key = None
                else:
                    kind = "is_active_diff"
                    comp = "isActive %s vs %s" % (ea, eb)
                    key = None
                entries.append({
                    "type": kind,
                    "path": info["path"] if info["path"] else ("#%s" % fid),
                    "component": comp,
                    "comp_key_": key,
                    "prefab": pref,
                    "detail": "内部对象覆写 fid=%s" % fid,
                })
        return entries, notes

    # -- 配对 --
    @staticmethod
    def _norm_name(name):
        n = str(name)
        n = re.sub(r"-FaceTracking\[[^\]]*\]", "", n, flags=re.I)
        n = re.sub(r"\(Clone\)\s*$", "", n)
        n = re.sub(r"_FT\b", "", n)
        n = re.sub(r"\bFT\b", "", n)
        n = re.sub(r"[\s_\-]+$", "", n)
        return n.strip()

    def pair_roots(self, roots):
        pairs, unpaired = [], []
        used = set()
        for i, a in enumerate(roots):
            if i in used:
                continue
            best = None
            for j, b in enumerate(roots):
                if j <= i or j in used:
                    continue
                same_src = (a.source_prefab and a.source_prefab == b.source_prefab
                            and a.kind == b.kind == "prefab")
                same_name = self._norm_name(a.name) == self._norm_name(b.name)
                if same_src or same_name:
                    score = (2 if same_src else 0) + (1 if same_name else 0)
                    if best is None or score > best[0]:
                        best = (score, j, b, "same_source_prefab" if same_src else "normalized_name")
            if best:
                _, j, b, basis = best
                used.add(i)
                used.add(j)
                pairs.append((a, b, basis))
            else:
                used.add(i)
                unpaired.append(a)
        return pairs, unpaired


# ---------------------------------------------------------------------------
# 差异分类 / 比较
# ---------------------------------------------------------------------------
def classify(path, comp_key_, comp_display_, prefab, project):
    """返回 (是否预期, 原因)。"""
    sguid = ""
    if comp_key_.startswith("script:"):
        sguid = comp_key_.split(":")[1]
    spath = project.script_path(sguid) if sguid else ""
    if sguid in FT_SCRIPT_GUIDS or FT_SCRIPT_PATH_RE.search(spath):
        return True, "FT组件"
    if AUDIT_SCRIPT_PATH_RE.search(spath):
        return True, "审查/感知工具组件"
    if FT_NAME_RE.search(path) or FT_NAME_RE.search(comp_display_ or "") \
            or FT_ANY_NAME_RE.search(comp_display_ or ""):
        return True, "FT命名对象/组件"
    if AUDIT_NAME_RE.search(path):
        return True, "审查/感知工具命名对象"
    return False, ""


def _entry(kind, path, a, b, project, component=None, comp_key_=None,
           component_name=None, prefab=None, detail=""):
    key = comp_key_ or ""
    disp = component_name or component or ""
    expected, reason = classify(path, key, disp, prefab, project)
    return {
        "type": kind,
        "path": path,
        "root_a": a.name if a else None,
        "root_b": b.name if b else None,
        "component_key": key or None,
        "component": disp or None,
        "script_guid": key.split(":")[1] if key.startswith("script:") else None,
        "script_name": disp or None,
        "prefab": prefab,
        "detail": detail,
        "expected": expected,
        "expected_reason": reason,
    }


def compare_pair(a, b, ia, ib, project):
    """ia/ib: {rel_path: info}. 返回 (pending, expected, removed_only, unresolved, ambiguous)."""
    pending, expected, removed_only, unresolved, ambiguous = [], [], [], [], []
    all_paths = sorted(set(ia) | set(ib))
    for p in all_paths:
        x, y = ia.get(p), ib.get(p)
        label = p if p else "<根>"
        if _is_ambiguous_path(p):
            # 同名兄弟（~N）无法跨根确定谁对谁，不在两根间猜配对；只登记。
            ambiguous.append({
                "path": label,
                "root_a": a.name, "root_b": b.name,
                "present": "both" if (x is not None and y is not None)
                           else ("a" if x is not None else "b"),
                "reason": "同名兄弟消歧后缀 ~N，跨根一一对应不确定",
            })
            continue
        if x is None:
            e = _entry("only_on_b", label, a, b, project, prefab=y.get("source_prefab"))
            (expected if e["expected"] else pending).append(e)
            continue
        if y is None:
            e = _entry("only_on_a", label, a, b, project, prefab=x.get("source_prefab"))
            (expected if e["expected"] else pending).append(e)
            continue
        pref = x.get("source_prefab") or y.get("source_prefab")
        # 组件集合
        cx = {k: v for k, v in x["components"]}
        cy = {k: v for k, v in y["components"]}
        for k in sorted(set(cx) | set(cy)):
            if k in cx and k not in cy:
                e = _entry("component_only_on_a", label, a, b, project, k, k, cx[k], pref)
                (expected if e["expected"] else pending).append(e)
            elif k in cy and k not in cx:
                e = _entry("component_only_on_b", label, a, b, project, k, k, cy[k], pref)
                (expected if e["expected"] else pending).append(e)
        # removed components（工程D那类）
        rx = {r["key"]: r for r in x["removed_components"]}
        ry = {r["key"]: r for r in y["removed_components"]}
        for k in sorted(set(rx) | set(ry)):
            inx, iny = k in rx, k in ry
            if inx and iny:
                continue
            side = "a" if inx else "b"
            r = rx[k] if inx else ry[k]
            e = _entry("removed_component_only_on_%s" % side, label, a, b, project,
                       component=r.get("display"), comp_key_=k,
                       component_name=r.get("display"), prefab=pref,
                       detail="target=%s" % r.get("target"))
            removed_only.append(e)
            (expected if e["expected"] else pending).append(e)
        # added components
        ax = {r["key"]: r for r in x["added_components"]}
        ay = {r["key"]: r for r in y["added_components"]}
        for k in sorted(set(ax) | set(ay)):
            if (k in ax) == (k in ay):
                continue
            side = "a" if k in ax else "b"
            r = ax[k] if k in ax else ay[k]
            e = _entry("added_component_only_on_%s" % side, label, a, b, project,
                       component=r.get("display"), comp_key_=k,
                       component_name=r.get("display"), prefab=pref)
            (expected if e["expected"] else pending).append(e)
        # removed / added gameobjects
        rgx = collections.Counter(g["name"] for g in x["removed_gameobjects"])
        rgy = collections.Counter(g["name"] for g in y["removed_gameobjects"])
        if rgx != rgy:
            onlyx = list((rgx - rgy).elements())
            onlyy = list((rgy - rgx).elements())
            side = "a" if onlyx else "b"
            e = _entry("removed_gameobject_only_on_%s" % side, label, a, b, project,
                       component="removedGO:%s" % (onlyx or onlyy), prefab=pref)
            removed_only.append(e)
            (expected if e["expected"] else pending).append(e)
        agx = collections.Counter(g["name"] for g in x["added_gameobjects"])
        agy = collections.Counter(g["name"] for g in y["added_gameobjects"])
        if agx != agy:
            onlyx = list((agx - agy).elements())
            onlyy = list((agy - agx).elements())
            side = "a" if onlyx else "b"
            e = _entry("added_gameobject_only_on_%s" % side, label, a, b, project,
                       component="addedGO:%s" % (onlyx or onlyy), prefab=pref)
            (expected if e["expected"] else pending).append(e)
        # is_active / tag
        if x.get("is_active") != y.get("is_active"):
            e = _entry("is_active_diff", label, a, b, project,
                       component="isActive %s vs %s" % (x.get("is_active"), y.get("is_active")),
                       prefab=pref)
            (expected if e["expected"] else pending).append(e)
        if (x.get("tag") or "") != (y.get("tag") or ""):
            e = _entry("tag_diff", label, a, b, project,
                       component="tag %r vs %r" % (x.get("tag"), y.get("tag")), prefab=pref)
            (expected if e["expected"] else pending).append(e)
        # enabled map：只比两边都存在的组件（只在一边的组件已由 component_only_* 报过）
        ex, ey = x.get("enabled_map") or {}, y.get("enabled_map") or {}
        both = set(cx) & set(cy)
        for k in sorted(both):
            if ex.get(k) != ey.get(k):
                e = _entry("enabled_diff", label, a, b, project,
                           component="%s enabled %s vs %s" % (comp_display_from_key(k, project),
                                                              ex.get(k), ey.get(k)),
                           comp_key_=k, prefab=pref)
                (expected if e["expected"] else pending).append(e)
        # unresolved：区分只在一根上（可能是被 dangling 引用藏起来的真差异）
        ux = set(x.get("unresolved") or [])
        uy = set(y.get("unresolved") or [])
        for u in sorted(ux - uy):
            e = _entry("unresolved_only_on_a", label, a, b, project,
                       component="unresolved:%s" % u, prefab=pref)
            unresolved.append({"path": label, "issue": u, "side": "a",
                               "root_a": a.name, "root_b": b.name})
            (expected if e["expected"] else pending).append(e)
        for u in sorted(uy - ux):
            e = _entry("unresolved_only_on_b", label, a, b, project,
                       component="unresolved:%s" % u, prefab=pref)
            unresolved.append({"path": label, "issue": u, "side": "b",
                               "root_a": a.name, "root_b": b.name})
            (expected if e["expected"] else pending).append(e)
        for u in sorted(ux & uy):
            unresolved.append({"path": label, "issue": u, "side": "both",
                               "root_a": a.name, "root_b": b.name})
    return pending, expected, removed_only, unresolved, ambiguous


# ---------------------------------------------------------------------------
# 单场景审计
# ---------------------------------------------------------------------------
def audit_scene(scene_path, project):
    audit = SceneAudit(scene_path, project)
    roots = audit.find_roots()
    pairs, unpaired = audit.pair_roots(roots)
    root_maps = {}
    for r in roots:
        units = audit.walk(r.owner_key)
        m, partial, dup, path_unresolved = {}, [], [], []
        for owner, segs, is_partial in units:
            path = "/".join(segs)
            # 路径还原不了：名字为空、或退化成 PI:/# 占位（绝不丢弃，只标记）
            if any((not s) or s.startswith("PI:") or s.startswith("#") for s in segs):
                path_unresolved.append(path or "<根>")
            info = audit.owner_info(owner)
            info["rel_path"] = path
            if path in m:
                dup.append(path)
                # 消歧
                path = path + "@" + owner
                info["rel_path"] = path
            m[path] = info
            if is_partial:
                partial.append(path)
        root_maps[r.owner_key] = {"map": m, "partial": partial, "dup": dup,
                                  "path_unresolved": path_unresolved}
    result = {
        "scene": _relpath(scene_path, project.root),
        "roots": [{"name": r.name, "key": r.owner_key, "kind": r.kind,
                   "source_prefab": r.source_prefab} for r in roots],
        "unpaired_roots": [{"name": r.name, "key": r.owner_key, "kind": r.kind}
                           for r in unpaired],
        "pairs": [],
    }
    for a, b, basis in pairs:
        ma = root_maps[a.owner_key]["map"]
        mb = root_maps[b.owner_key]["map"]
        pending, expected, removed_only, unresolved, ambiguous = compare_pair(
            a, b, ma, mb, project)
        # 预制体内部对象的覆写差异（根对象之外的 m_IsActive / m_TagString / m_Enabled）
        internal, internal_notes = audit.internal_override_diffs(a, b)
        for e in internal:
            ent = _entry(e["type"], e["path"], a, b, project,
                         component=e.get("component"), comp_key_=e.get("comp_key_"),
                         prefab=e.get("prefab"), detail=e.get("detail", ""))
            (expected if ent["expected"] else pending).append(ent)
        result["pairs"].append({
            "root_a": {"name": a.name, "key": a.owner_key, "kind": a.kind,
                       "source_prefab": a.source_prefab},
            "root_b": {"name": b.name, "key": b.owner_key, "kind": b.kind,
                       "source_prefab": b.source_prefab},
            "pair_basis": basis,
            "pending": pending,
            "expected": expected,
            "expected_counts": dict(collections.Counter(
                e.get("expected_reason") or "其它预期" for e in expected)),
            "removed_only": removed_only,
            "unresolved": unresolved,
            "ambiguous": ambiguous,
            "internal_notes": internal_notes,
            "path_partial_count_a": len(root_maps[a.owner_key]["partial"]),
            "path_partial_count_b": len(root_maps[b.owner_key]["partial"]),
            "path_unresolved_a": root_maps[a.owner_key]["path_unresolved"],
            "path_unresolved_b": root_maps[b.owner_key]["path_unresolved"],
        })
    return result


# ---------------------------------------------------------------------------
# 工程 → 主场景
# ---------------------------------------------------------------------------
def candidate_scenes(project):
    out = []
    base = os.path.join(project.root, "Assets")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in (".git", "Library", "Temp", "obj")]
        for fn in filenames:
            if fn.endswith(".unity"):
                p = os.path.join(dirpath, fn)
                rel = _relpath(p, base)
                if NON_MAIN_SCENE_RE.search(rel) or VENDOR_SCENE_RE.search(rel):
                    continue
                out.append(p)
    return sorted(out)


def _scene_depth_score(rel):
    depth = rel.count("/")
    if depth == 0:
        return 3
    if rel.startswith("_Work/"):
        return 2
    return 1


def pick_main_scene(project):
    cands = []
    for p in candidate_scenes(project):
        try:
            roots = SceneAudit(p, project).find_roots()
        except Exception as e:
            cands.append({"scene": _relpath(p, project.root), "roots": -1,
                          "error": str(e)})
            continue
        cands.append({"scene": _relpath(p, project.root), "roots": len(roots),
                      "root_names": [r.name for r in roots]})
    qual = [c for c in cands if c.get("roots", 0) >= 1]
    if not qual:
        return None, cands
    # 取根最多者；并列取更浅 / 更短路径
    qual.sort(key=lambda c: (-c["roots"],
                             -_scene_depth_score(c["scene"].split("Assets/", 1)[-1]),
                             len(c["scene"])))
    return qual[0], cands


PROJECTS_ORDER = [
    "工程C",
    "工程D",
    "工程G",
    "工程A",
    "工程E",
    "工程F",
]


def run_all(repo_root, out_dir, list_only=False):
    os.makedirs(out_dir, exist_ok=True)
    projects = list(PROJECTS_ORDER)
    milfy = "工程B"
    if os.path.isdir(os.path.join(repo_root, milfy)):
        projects.append(milfy)
    results = []
    for pname in projects:
        proot = os.path.join(repo_root, pname)
        if not os.path.isdir(proot):
            continue
        project = Project(proot)
        if pname == milfy:
            main = os.path.join(proot, "Assets/_Work/工程B_Milfy.unity")
            chosen, cands = ({"scene": os.path.relpath(main, proot), "roots": None}, [])
            if not os.path.exists(main):
                continue
            scene_path = main
            audit_res = audit_scene(scene_path, project)
            roots_n = len(audit_res["roots"])
            chosen["roots"] = roots_n
        else:
            chosen, cands = pick_main_scene(project)
            if chosen is None:
                results.append({"project": pname, "scene": None,
                                "candidates": cands, "audit": None,
                                "note": "无 descriptor 根"})
                continue
            scene_path = os.path.join(proot, chosen["scene"])
            audit_res = audit_scene(scene_path, project)
            roots_n = len(audit_res["roots"])
        entry = {"project": pname, "scene": chosen.get("scene"),
                 "root_count": roots_n, "candidates": cands, "audit": audit_res}
        results.append(entry)
    if list_only:
        return results
    # 写 JSON
    written = []
    for r in results:
        if not r.get("audit"):
            continue
        out = dict(r)
        fn = os.path.join(out_dir, "%s.json" % r["project"])
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        written.append(fn)
    write_summary(results, out_dir)
    return results


def _md_escape(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def write_summary(results, out_dir):
    lines = ["# 双头像根组件差异普查汇总", "",
             "产物脚本：`开发工具/通用工具/审查/dual_root_diff.py`（离线只读，"
             "不启动 Unity）。", "",
             "读法：",
             "",
             "- 「待定」= 不在白名单里的差异，逐条列出，需人工判；「预期」只给计数。",
             "- 白名单三类（脚本头部注明来源）：面捕根特有的 FT 组件 / 面捕安装器加的对象 / "
             "`_感知`、审查工具的东西。`ModularAvatarShapeChanger` **不**在白名单里——"
             "工程D的 bug 正是它被删，故任何一根上多/少它都进「待定」。",
             "- 「只在一根上有的删除条目」= 某一根的预制体实例 `m_RemovedComponents` 里有、"
             "另一根没有的条目（工程D那类）。",
             "- 「未还原」= dangling 引用（场景里写的被删组件 fileID 在源预制体里已不存在）"
             "或路径/名字取不到；只在一根上出现时同时进「待定」，两边都有的只记账不重复报。",
             "- 挂到预制体内部 transform 的场景对象，路径补一段源对象名（补不齐会在 JSON 里"
             "记 `path_partial_count_*`）。",
             "- 根对象之外的「预制体内部对象覆写」（`m_Modifications` 里指向子对象的 "
             "`m_IsActive`/`m_TagString`/`m_Enabled`）也逐条比；一个 PI 可以有多条同名覆写，"
             "按 target 分别比，不会被「最后一条」吞掉。",
             "- 路径还原不了的对象记在 JSON 的 `path_unresolved_a/b`（标出来，不丢）。",
             "- 同一父节点下同名兄弟用 `~N` 消歧；跨根无法确定谁对谁，按「不许猜」"
             "不参与两两比对，只在「同名兄弟对齐存疑」里登记。",
             ""]
    # 总表
    lines.append("## 工程总表")
    lines.append("")
    lines.append("| 工程 | 主场景 | 根数 | 配对数 | 待定 | 预期 | 未配对根 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for r in results:
        a = r.get("audit")
        if not a:
            lines.append("| %s | （无 descriptor 根，跳过） | 0 | - | - | - | - |"
                         % _md_escape(r["project"]))
            continue
        pend = sum(len(p["pending"]) for p in a["pairs"])
        exp = sum(len(p["expected"]) for p in a["pairs"])
        lines.append("| %s | `%s` | %d | %d | %d | %d | %d |" % (
            _md_escape(r["project"]), _md_escape(a["scene"]), len(a["roots"]),
            len(a["pairs"]), pend, exp, len(a["unpaired_roots"])))
    lines.append("")
    # 每工程一节
    for r in results:
        a = r.get("audit")
        lines.append("## %s" % r["project"])
        lines.append("")
        if not a:
            lines.append("无 VRCAvatarDescriptor 根（脚本已扫过全部非厂商示例场景），跳过。")
            lines.append("")
            if r.get("candidates"):
                lines.append("候选场景扫描：")
                for c in r["candidates"]:
                    lines.append("- `%s` roots=%s" % (_md_escape(c.get("scene")),
                                                     c.get("roots")))
                lines.append("")
            continue
        lines.append("主场景：`%s`；根：%s；未配对根：%s" % (
            _md_escape(a["scene"]),
            ", ".join("`%s`(%s)" % (_md_escape(x["name"]), x["kind"]) for x in a["roots"]) or "无",
            ", ".join("`%s`" % _md_escape(x["name"]) for x in a["unpaired_roots"]) or "无"))
        lines.append("")
        # 候选场景透明度：判法（inline m_Script 542108242）在「根是预制体实例」的行上会失灵，
        # 故工具用「源预制体含 descriptor」的放宽口径自动取根最多者；把候选列出来供人工复核。
        cand_roots = [c for c in (r.get("candidates") or []) if (c.get("roots") or 0) >= 1]
        if len(cand_roots) > 1:
            lines.append("候选场景（自动取根最多者，若主场景判错请指出）：" + "；".join(
                "`%s` roots=%s" % (_md_escape(c.get("scene")), c.get("roots"))
                for c in cand_roots))
            lines.append("")
        if len(a["roots"]) < 2:
            lines.append("按范围「只处理场景里有 ≥2 个 descriptor 根的工程」：本工程根数 %d，"
                         "不做双根比对。" % len(a["roots"]))
            lines.append("")
            continue
        if not a["pairs"]:
            lines.append("本场景有 %d 个 descriptor 根，但按配对规则（去 `_FT`/"
                         "`-FaceTracking[...]`/`(Clone)` 后同名，或同一 `m_SourcePrefab`）"
                         "没有任何一对，已全部列入「未配对根」。" % len(a["roots"]))
            lines.append("")
        for pi, pair in enumerate(a["pairs"]):
            lines.append("### 对 %d：`%s` ↔ `%s`（依据 %s）" % (
                pi + 1, _md_escape(pair["root_a"]["name"]),
                _md_escape(pair["root_b"]["name"]), pair["pair_basis"]))
            lines.append("")
            if pair["expected_counts"]:
                lines.append("预期差异计数：" + "；".join(
                    "%s=%d" % (k, v) for k, v in sorted(pair["expected_counts"].items())))
                lines.append("")
            lines.append("**待定（%d 条）**" % len(pair["pending"]))
            lines.append("")
            if pair["pending"]:
                lines.append("| # | 差异类型 | 根A | 根B | 路径 | 组件/脚本名 | 所在预制体 |")
                lines.append("|---:|---|---|---|---|---|---|")
                for k, e in enumerate(pair["pending"], 1):
                    lines.append("| %d | %s | %s | %s | `%s` | %s | `%s` |" % (
                        k, _md_escape(e["type"]),
                        _md_escape(e["root_a"]), _md_escape(e["root_b"]),
                        _md_escape(e["path"]), _md_escape(e["component"] or ""),
                        _md_escape(e["prefab"] or "")))
                lines.append("")
            else:
                lines.append("（无）")
                lines.append("")
            lines.append("**只在一根上有的删除条目（%d 条）**" % len(pair["removed_only"]))
            lines.append("")
            if pair["removed_only"]:
                lines.append("| # | 类型 | 路径 | 组件/脚本名 | 所在预制体 | 说明 |")
                lines.append("|---:|---|---|---|---|---|")
                for k, e in enumerate(pair["removed_only"], 1):
                    lines.append("| %d | %s | `%s` | %s | `%s` | %s |" % (
                        k, _md_escape(e["type"]), _md_escape(e["path"]),
                        _md_escape(e["component"] or ""), _md_escape(e["prefab"] or ""),
                        _md_escape(e["detail"])))
                lines.append("")
            else:
                lines.append("（无）")
                lines.append("")
            if pair["unresolved"]:
                lines.append("**未还原（%d 条）**" % len(pair["unresolved"]))
                lines.append("")
                for u in pair["unresolved"]:
                    lines.append("- `%s`：%s" % (_md_escape(u["path"]), _md_escape(u["issue"])))
                lines.append("")
            pu_a = pair.get("path_unresolved_a") or []
            pu_b = pair.get("path_unresolved_b") or []
            if pu_a or pu_b:
                lines.append("**路径未还原（A %d 条 / B %d 条）**" % (len(pu_a), len(pu_b)))
                lines.append("")
                for tag, lst in (("A", pu_a), ("B", pu_b)):
                    for p in lst:
                        lines.append("- %s：`%s`" % (tag, _md_escape(p)))
                lines.append("")
            if pair.get("internal_notes"):
                lines.append("**内部覆写对齐备注**：" + "；".join(
                    _md_escape(n) for n in pair["internal_notes"]))
                lines.append("")
            if pair.get("ambiguous"):
                lines.append("**同名兄弟对齐存疑（%d 条，按「不许猜」未参与比对）**"
                             % len(pair["ambiguous"]))
                lines.append("")
                for e in pair["ambiguous"]:
                    lines.append("- `%s`（%s，%s）" % (
                        _md_escape(e["path"]), e.get("present"), _md_escape(e.get("reason", ""))))
                lines.append("")
    with open(os.path.join(out_dir, "汇总.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------
def _repo_root():
    return os.path.abspath(os.path.join(_HERE, "..", "..", ".."))


def _selftest():
    repo = _repo_root()
    proj_dir = os.path.join(repo, "工程D")
    if not os.path.isdir(proj_dir):
        print("[FAIL] 找不到 %s" % proj_dir)
        return 2
    tmp = os.path.join(repo, TMP_DIR)
    os.makedirs(tmp, exist_ok=True)
    baseline = os.path.join(tmp, "baseline_project-d.unity")
    rel = "工程D/Assets/工程D.unity"
    try:
        out = subprocess.check_output(["git", "-C", repo, "show", "d50e7e6e:%s" % rel],
                                      stderr=subprocess.STDOUT)
    except Exception as e:
        print("[FAIL] git show d50e7e6e 失败：%s" % e)
        return 2
    with open(baseline, "wb") as f:
        f.write(out)

    project = Project(proj_dir)

    def scan(scene_path, tag):
        res = audit_scene(scene_path, project)
        hits = []
        for pair in res["pairs"]:
            names = {pair["root_a"]["name"], pair["root_b"]["name"]}
            if not any("rurune_None" in n for n in names):
                continue
            for e in pair["pending"] + pair["expected"]:
                if e["type"].startswith("removed_component") and \
                        "ShapeChanger" in (e["component"] or "") and \
                        "Velvet China" in (e["prefab"] or ""):
                    hits.append(e)
        return res, hits

    base_res, base_hits = scan(baseline, "baseline")
    head_res, head_hits = scan(os.path.join(proj_dir, "Assets/工程D.unity"), "HEAD")

    print("== dual_root_diff --selftest ==")
    print("基线 d50e7e6e: 根=%s" % [r["name"] for r in base_res["roots"]])
    for e in base_hits:
        print("  [基线命中] type=%s root_a=%s root_b=%s path=%s component=%s prefab=%s"
              % (e["type"], e["root_a"], e["root_b"], e["path"], e["component"], e["prefab"]))
    print("HEAD: 根=%s" % [r["name"] for r in head_res["roots"]])
    for e in head_hits:
        print("  [HEAD命中] type=%s root_a=%s root_b=%s path=%s component=%s prefab=%s"
              % (e["type"], e["root_a"], e["root_b"], e["path"], e["component"], e["prefab"]))

    fails = []
    if not base_hits:
        fails.append("基线应报出 Rurune(Velvet China) 上 ShapeChanger 只在 FT 根被删，实际没有")
    if head_hits:
        fails.append("HEAD 不应再有该条，实际仍有 %d 条" % len(head_hits))
    # 额外自检：HEAD 的成对根里不应出现任何 removed_component_only
    head_removed = sum(len(p["removed_only"]) for p in head_res["pairs"])
    print("HEAD 只在一根上有的删除条目数：%d" % head_removed)
    if fails:
        for f in fails:
            print("[FAIL] %s" % f)
        return 1
    print("[OK] 基线报出、HEAD 消失：selftest 通过")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="双头像根组件差异普查（离线只读）")
    ap.add_argument("--project", help="只跑一个工程目录")
    ap.add_argument("--scene", help="显式指定场景文件")
    ap.add_argument("--out", default=None, help="输出目录")
    ap.add_argument("--list-only", action="store_true", help="只列候选场景")
    ap.add_argument("--selftest", action="store_true", help="工程D基线 vs HEAD 回归")
    ap.add_argument("--repo", default=None, help="工作区根目录")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    repo = os.path.abspath(args.repo) if args.repo else _repo_root()
    out_dir = args.out or os.path.join(repo, DEFAULT_OUT)

    if args.project:
        proot = os.path.abspath(args.project)
        project = Project(proot)
        if args.scene:
            scene_path = os.path.abspath(args.scene)
            audit_res = audit_scene(scene_path, project)
            entry = {"project": project.name, "scene": _relpath(scene_path, proot),
                     "root_count": len(audit_res["roots"]), "audit": audit_res}
            if args.list_only:
                print(json.dumps(entry, ensure_ascii=False, indent=2))
                return 0
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "%s.json" % project.name), "w",
                      encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)
            write_summary([entry], out_dir)
            print("已写 %s/%s.json 与 汇总.md" % (out_dir, project.name))
            return 0
        # 只跑该工程，走统一逻辑
        results = run_all_subset(repo, out_dir, [project.name], args.list_only)
        if not args.list_only:
            print("已写 %s" % out_dir)
        else:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    results = run_all(repo, out_dir, list_only=args.list_only)
    if args.list_only:
        for r in results:
            if r.get("audit"):
                print("%s: scene=%s roots=%s" % (r["project"], r["scene"],
                                                 r.get("root_count")))
            else:
                print("%s: 无 descriptor 根" % r["project"])
        return 0
    print("已写 %s" % out_dir)
    return 0


def run_all_subset(repo_root, out_dir, names, list_only=False):
    allres = run_all(repo_root, out_dir, list_only=True)
    keep = [r for r in allres if r["project"] in names]
    if list_only:
        return keep
    os.makedirs(out_dir, exist_ok=True)
    for r in keep:
        if not r.get("audit"):
            continue
        with open(os.path.join(out_dir, "%s.json" % r["project"]), "w",
                  encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
    write_summary(keep, out_dir)
    return keep


if __name__ == "__main__":
    sys.exit(main())
