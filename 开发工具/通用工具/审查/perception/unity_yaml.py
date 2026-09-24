# -*- coding: utf-8 -*-
"""Unity YAML 读取共用件（T-11 输出；被 writers_static.py / clip_writes.py 复用）。
【项目沉淀】通用工具
适用素体：无关
相关素材：Unity .unity/.prefab/.controller/.anim
工具链　：Python 3 + PyYAML（离线）
可复用性：★★★ 换个单子直接能用
用途　　：Unity 多文档 YAML 读取共用件，被 writers_static.py / clip_writes.py 复用。


设计取舍
--------
Unity 的 `.unity` / `.prefab` / `.controller` / `.anim` 都是「多文档 YAML」：一个文件里
若干 `--- !u!<classID> &<fileID>[ stripped]` 文档。PyYAML 直接读会在第二篇文档上炸
（`%TAG !u!` 指令只作用于紧跟的那一篇），所以这里做两件事：

1. 预处理文档头：把 `--- !u!<id> &<fid>[ stripped]` 换成裸 `---`，同时按顺序记下
   classID / fileID / stripped / 起始行号（1-based，用于 `where: 文件:行`）。
2. 用 PyYAML `safe_load_all` 读剩下的纯 YAML；YAML 双引号里的 `\\uXXXX` 由 PyYAML
   自己还原成非 ASCII 字符，所以路径/键名拿到的就是真名。

代价：单个 3 MB 场景约 2–3 s。别在循环里重复 load，同一路径请走 `YamlCache`。

另外把 `t5_shapekey_matrix.py` 里的「AAO 构建后改名还原」小函数抄了过来（`restore_segment`
/`restore_path`/`restore_shape`/`leaf`/`fnum`/`fmt_val`），只抄不改，t5 行为不受影响；写者图
其它离线工具用同一份，避免各抄一遍。

依赖：PyYAML（本机 6.0.3）。若缺失，`load_unity_yaml` 会给出明确报错。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - 环境缺 PyYAML 时给可读报错
    import yaml
    _YAML_OK = True
    _YAML_ERR = ""
except Exception as _e:  # pragma: no cover
    yaml = None
    _YAML_OK = False
    _YAML_ERR = str(_e)


DOC_HEADER_RE = re.compile(r"^--- !u!(\d+) &(-?\d+)( stripped)?\s*$")


# Unity 用的是 YAML 1.1，而 YAML 1.1 会把裸 `On` / `Off` / `Yes` / `No` 读成布尔值，
# 直接把 `m_Name: Off`、`m_Name: On` 这类状态名毁掉。这里去掉 bool/timestamp 的隐式
# 解析，只认 true/false（大小写不敏感），其余一律当字符串。
class UnityLoader(yaml.SafeLoader if _YAML_OK else object):  # type: ignore[misc]
    pass


if _YAML_OK:  # pragma: no cover - 依赖 PyYAML
    UnityLoader.yaml_implicit_resolvers = {
        k: [(tag, rx) for (tag, rx) in v
            if tag not in ("tag:yaml.org,2002:bool", "tag:yaml.org,2002:timestamp")]
        for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    UnityLoader.add_implicit_resolver(
        "tag:yaml.org,2002:bool",
        re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"),
        list("tTfF"),
    )



# ---------------------------------------------------------------------------
# t5_shapekey_matrix.py 抄来的名字还原函数（不得改 t5）
# ---------------------------------------------------------------------------
CJK_RANGES = (
    "\u3040-\u30ff"      # 平假名/片假名
    "\u3400-\u4dbf"      # CJK 扩展 A
    "\u4e00-\u9fff"      # CJK 基本区
    "\uff66-\uff9f"      # 半角片假名
)
_CJK_RE = re.compile("[%s]" % CJK_RANGES)
_TOKEN_SPLIT = re.compile(r"[^0-9a-zA-Z%s]+" % CJK_RANGES)

AAO_SHAPE_PREFIX = "AAO_Merged_"
RE_AAO_MERGE_MESH = re.compile(r"^\$\$AAO_AUTO_MERGE_SKINNED_MESH_(\d+)$", re.IGNORECASE)
RE_DOLLAR_SEG = re.compile(r"^(?P<pre>[^/]*)\$(?P<orig>[^/]*)\$(?P<num>\d+)$")


def restore_segment(seg):
    m = RE_AAO_MERGE_MESH.match(seg)
    if m:
        return "<AAO合并网格#%s>" % m.group(1)
    m = RE_DOLLAR_SEG.match(seg)
    if m:
        return m.group("orig")
    return seg


def restore_path(path):
    if path in (".", "", None):
        return path
    return "/".join(restore_segment(s) for s in str(path).split("/"))


def restore_shape(shape):
    """`AAO_Merged_<原键名>_<n>` → `<原键名>`；非该前缀则原样返回。"""
    if shape is None:
        return None
    name = str(shape)
    if name.startswith(AAO_SHAPE_PREFIX):
        name = name[len(AAO_SHAPE_PREFIX):]
        stripped = re.sub(r"_\d+$", "", name)
        if stripped:
            name = stripped
    return name


def leaf(path):
    if not path or path == ".":
        return path
    return str(path).rstrip("/").split("/")[-1]


def fnum(v):
    """把 bool/int/float/字符串数值统一成 float；解析不了返回 None。"""
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "on", "yes"):
            return 1.0
        if s in ("false", "off", "no"):
            return 0.0
        try:
            return float(s)
        except ValueError:
            return None
    return None


def fmt_val(v):
    """报告里数值的显示：整数不带小数点。"""
    if v is None:
        return "?"
    f = float(v)
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    return ("%.6f" % f).rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# 文档
# ---------------------------------------------------------------------------
@dataclass
class UnityDoc:
    """一篇 Unity YAML 文档。`data` 是去掉最外层类型名后的映射体。"""

    class_id: int
    file_id: int
    stripped: bool
    line: int
    type_name: str
    data: dict = field(default_factory=dict)
    path: str = ""

    def get(self, key, default=None):
        return self.data.get(key, default)


def load_unity_yaml(path: str) -> List[UnityDoc]:
    """读一个 Unity YAML 文件，返回按出现顺序的文档列表。"""
    if not _YAML_OK:  # pragma: no cover
        raise RuntimeError("缺少 PyYAML，无法解析 Unity YAML：%s" % _YAML_ERR)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if "\x00" in text:
        # .fbx / .asset 里可能夹二进制；调用方本该只传 YAML 资产
        raise ValueError("不是文本 Unity YAML（含 NUL 字节）：%s" % path)
    metas = []
    body = []
    for i, line in enumerate(text.split("\n"), start=1):
        m = DOC_HEADER_RE.match(line)
        if m:
            metas.append((int(m.group(1)), int(m.group(2)), bool(m.group(3)), i))
            body.append("---")
        else:
            body.append(line)
    raw = list(yaml.load_all("\n".join(body), Loader=UnityLoader))
    # safe_load_all 对末尾空文档会多吐一个 None，按出现顺序对齐即可
    docs: List[UnityDoc] = []
    for meta, node in zip(metas, raw):
        if not isinstance(node, dict) or len(node) != 1:
            type_name, data = "", node if isinstance(node, dict) else {}
        else:
            type_name = next(iter(node))
            data = node[type_name] if isinstance(node[type_name], dict) else {}
        docs.append(UnityDoc(meta[0], meta[1], meta[2], meta[3], type_name, data, path))
    return docs


class YamlCache:
    """同一路径只读一次；`--selftest` 与批跑都靠它省 IO。"""

    def __init__(self):
        self._cache: Dict[str, List[UnityDoc]] = {}

    def load(self, path: str) -> List[UnityDoc]:
        key = os.path.abspath(path)
        if key not in self._cache:
            self._cache[key] = load_unity_yaml(key)
        return self._cache[key]


class DocIndex:
    """一个文件的文档按 fileID / classID 建索引，并提供 GameObject 名字与 active 查询。"""

    def __init__(self, docs: Sequence[UnityDoc]):
        self.docs = list(docs)
        self.by_fid: Dict[int, UnityDoc] = {}
        self.by_class: Dict[int, List[UnityDoc]] = {}
        self._tf_of_go: Dict[int, int] = {}
        for d in self.docs:
            self.by_fid.setdefault(d.file_id, d)
            self.by_class.setdefault(d.class_id, []).append(d)
        for d in self.by_class.get(4, []):
            go = d.get("m_GameObject") or {}
            self._tf_of_go.setdefault(go.get("fileID", 0) or 0, d.file_id)

    def first(self, class_id: int) -> Optional[UnityDoc]:
        arr = self.by_class.get(class_id) or []
        return arr[0] if arr else None

    def all(self, class_id: int) -> List[UnityDoc]:
        return list(self.by_class.get(class_id) or [])

    def go_name(self, go_fid: int) -> str:
        doc = self.by_fid.get(go_fid)
        if doc and doc.class_id == 1:
            return doc.get("m_Name") or ""
        return ""

    def go_active(self, go_fid: int) -> Optional[bool]:
        """沿 Transform 的 m_Father 走到根，全部 m_IsActive 为真才是活跃。"""
        seen = set()
        fid = go_fid
        active = None
        while fid and fid not in seen:
            seen.add(fid)
            doc = self.by_fid.get(fid)
            if not doc:
                return active
            if doc.class_id == 1:
                val = doc.get("m_IsActive")
                if val is None:
                    val = 1
                active = bool(int(val)) and (active is not False)
                # 继续通过该 GO 的 Transform 往上走
                tf_fid = self.go_transform(fid)
                if tf_fid is None:
                    return active
                fid = tf_fid
                continue
            if doc.class_id == 4:  # Transform
                father = doc.get("m_Father") or {}
                fid = father.get("fileID", 0) or 0
                continue
            return active
        return active

    def go_transform(self, go_fid: int) -> Optional[int]:
        return self._tf_of_go.get(go_fid)

    def iter_components(self, script_guid: str) -> Iterable[UnityDoc]:
        for d in self.by_class.get(114, []):
            s = d.get("m_Script") or {}
            if s.get("guid") == script_guid:
                yield d


# ---------------------------------------------------------------------------
# GUID 索引
# ---------------------------------------------------------------------------
def build_guid_index(project_root: str, extra_dirs: Optional[Sequence[str]] = None) -> Dict[str, str]:
    """扫 `Assets/` 与给定 `Packages/` 下的 `.meta`，返回 {guid: 资源绝对路径}。"""
    idx: Dict[str, str] = {}
    roots = [os.path.join(project_root, "Assets")]
    for d in (extra_dirs or []):
        roots.append(d if os.path.isabs(d) else os.path.join(project_root, d))
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in (".git", "Library", "Temp", "obj")]
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


def _rel(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


# ---------------------------------------------------------------------------
# 自验（库本身也带 --selftest，符合 04 §0 约定）
# ---------------------------------------------------------------------------
def _selftest() -> int:
    project = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "..", "工程A"))
    anim = os.path.join(project, "Assets/_Work/Gen/Clip/Dial_整套.anim")
    if not os.path.exists(anim):
        print("[FAIL] 找不到 %s" % anim)
        return 2
    docs = load_unity_yaml(anim)
    fails = []
    if len(docs) != 1 or docs[0].type_name != "AnimationClip":
        fails.append("Dial_整套.anim 应解析出 1 篇 AnimationClip，实际 %r"
                     % [(d.type_name) for d in docs])
    else:
        idx = DocIndex(docs)
        clip = idx.first(74)
        if clip.get("m_Name") != "Dial_整套":
            fails.append("m_Name 应为 Dial_整套，实际 %r" % clip.get("m_Name"))
        hit = None
        for fc in clip.get("m_FloatCurves") or []:
            if fc.get("attribute") == "blendShape.outer_shlink":
                hit = fc
        if hit is None:
            fails.append("未找到 blendShape.outer_shlink 曲线")
        elif hit.get("path") != "kaguya_cloth/sailor":
            fails.append("path 应为 kaguya_cloth/sailor，实际 %r" % hit.get("path"))
        elif len(hit["curve"]["m_Curve"]) != 3:
            fails.append("outer_shlink 应有 3 个关键帧")
    # YAML 1.1 的 On/Off → bool 陷阱必须被 UnityLoader 关掉
    ctrl = os.path.join(project, "Assets/_Work/Gen/A2_FX.controller")
    if os.path.exists(ctrl):
        cidx = DocIndex(load_unity_yaml(ctrl))
        names = {d.get("m_Name") for d in cidx.all(1102)}
        if True in names or False in names:
            fails.append("状态名 On/Off 被读成 bool，UnityLoader 未生效")
        if not ("On" in names or "Off" in names):
            fails.append("A2_FX 里应能找到 On/Off 状态名")
    if fails:
        for f in fails:
            print("[FAIL] %s" % f)
        return 1
    print("[selftest] unity_yaml OK（%d 篇文档；Dial_整套/outer_shlink 曲线正确）" % len(docs))
    return 0


if __name__ == "__main__":
    import sys as _sys
    if "--selftest" in _sys.argv:
        _sys.exit(_selftest())
    print(__doc__)
