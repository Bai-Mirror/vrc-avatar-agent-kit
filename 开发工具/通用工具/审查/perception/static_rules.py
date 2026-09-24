#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""static_rules.py — T-11 静态规则候选表（在 writers.json 上离线跑）
【项目沉淀】通用工具
适用素体：无关
相关素材：writers.json
工具链　：Python 3（离线）
可复用性：★★ 审查工具链的一环
用途　　：T-11 静态规则候选表，在 writers.json 上离线跑。


出处
  - 03c §Q8/Q11 与实验单 E8：`感知机制研究/03c_Q8-Q11_接口与实验单.md:82,110`
  - 03 §4.4/§4.5 通用规则与勾选表口径：`03_研究与方案.md:132,150-151`
  - E-T11-01 验收（静态规则结果缺失）：`派工/验收_20260919_AV至BB.md:30`

输入是 `perception/writers/1`（T-11 `writers_static.py` 产物），**只列候选、不判对错**：
对错要靠几何实测/构建期截获/人判（03 §4.5「静态规则结果不进用户表」）。

六类规则
  K1 multi_writer      同键多写者：同一 (mesh,key) 有 ≥2 个配置型写者
                       （ShapeChanger/BlendshapeSync/ObjectToggle），标值是否不同
  K2 set_delete        同键 Set/Delete 并存
  K3 dial_vs_item      同键既有档位/整套写者（Dial/整套），又有逐件/部位写者
  K4 shrink_setroot    收缩键挂在套装根、目标是身体网格
  K5 foot_owner        脚型键的 ShapeChanger 归属（袜/鞋/未知），标「厂商 prefab 独有」
  K6 out_of_range      形态键目标值越界（<0 或 >100）

口径与已知盲区（随产物一起读）
  1. 只读 writers.json，不重扫工程；宿主被 `writers_static` 折叠到套装根的
     （如 工程A MMN 的 Socks/Shoes 都折成 `_Outfit/Outfit_MMN_黑`）从本文件
     分不出袜/鞋。K5 按写者 `where`（`<文件>:<行>`）回读该 prefab/场景里的
     GameObject 名（`where_names`）；`.fbx` 源的名字离线取不到时，**结论字段
     `sock_owner`/`shoe_owner` 一律判不了**（`owner_unknown=True`），按 `where` 文件
     类型推的「厂商 prefab 写者=袜、场景补挂写者=鞋」只写进
     `sock_owner_guess`/`shoe_owner_guess`，并在 `owner_kind_source` 写明来源
     （验收_20260919_BC至BH.md BG2：猜测不许进结论字段）。
  2. clip 写者数量极大（14 工程 149,891 条），K1 只统计配置型写者，避免把
     动画曲线的正常差异当成冲突；K3 单独处理档位 vs 逐件的 clip。
  3. 「值不同」用 value/values 的数值集合，四舍五入 4 位；curve 写者没有常量值，
     不参与 K1 的比较。
  4. 越界只看形态键（有 mesh、key 不是 `material.`/`m_` 这类属性路径）。

用法
  python3 static_rules.py --writers <writers.json> [--json out.json] [--md out.md]
  python3 static_rules.py --batch <目录> --md <汇总.md> [--json <汇总.json>]
  python3 static_rules.py --selftest        # 真实工程已知样本（工程A / 工程B）
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
ZAIJIAN_PROJECT = os.path.join(REPO, "工程B")
PROJECT_A_DIR = os.path.join(REPO, "工程A")
MMN_FIX_COMMIT = "ceb4070b"
MMN_FIX_SCENE = "工程A/Assets/_Work/工程A.unity"

SCHEMA = "perception/writers/1"
CONFIG_COMPONENTS = {"ShapeChanger", "BlendshapeSync", "ObjectToggle"}

BODY_RE = re.compile(r"^(Body|Body_base|Body_b|Body2|body)$", re.I)
SHRINK_RE = re.compile(r"shrink|收缩", re.I)
# 脚型/脚背姿态键（不含 Shrink_*，那些归 K4）
FOOT_RE = re.compile(
    r"Foot_|Toe_|^Foot$|^Toe$|Heel_Feet|foot_足|つま先|ヒール",
    re.I,
)
DIAL_RE = re.compile(
    r"dial|slider|スライダー|ラジアル|radial|puppet|ホイール|整套", re.I
)
PART_RE = re.compile(
    r"部位|On_部位|Off_部位|上衣|下着|内衣|外套|袜子|鞋子|发型|头饰|耳尾"
    r"|戒指|抱抱熊|光环|目元",
    re.I,
)
SOCK_RE = re.compile(
    r"sok|sock|stocking|靴下|ソックス|くつした|袜|タイツ|tights", re.I
)
SHOE_RE = re.compile(
    r"sho|shoe|boot|sandal|heel|靴|くつ|鞋|pump|slipper|サンダル|ブーツ|パンプス",
    re.I,
)
PROP_RE = re.compile(r"\.|^m_|^material")
MA_CONTAINER_RE = re.compile(r"/ModularAvatar(?:/|$)|_MA(?:/|$)", re.I)
PREFAB_RE = re.compile(r"\.prefab:\d+")


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def is_prop_key(key: str) -> bool:
    return bool(PROP_RE.search(key or ""))


def num_values(w: dict) -> set:
    """写者的常量数值集合（value/values，去 bool，四舍五入 4 位）。"""
    out = set()
    raw = []
    if w.get("value") is not None:
        raw.append(w["value"])
    raw.extend(w.get("values") or [])
    for v in raw:
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out.add(round(float(v), 4))
    return out


def owner_of(w: dict) -> Tuple:
    if w.get("component") == "clip":
        return ("clip", w.get("source"), w.get("clip"),
                w.get("layer"), w.get("state"))
    return ("cfg", w.get("source"), w.get("component"),
            w.get("host") or w.get("where"))


def owner_label(w: dict) -> str:
    if w.get("component") == "clip":
        return "%s[%s]" % (w.get("clip") or "?", w.get("source"))
    host = w.get("host") or ""
    return "%s%s" % (host or "(无宿主)", " <%s>" % w.get("source") if w.get("source") else "")


def where_of(w: dict) -> str:
    return str(w.get("where") or "")


def is_vendor_prefab_writer(w: dict) -> bool:
    return bool(PREFAB_RE.search(where_of(w)))


def iter_keys(doc: dict) -> Iterable[Tuple[str, str, List[dict]]]:
    for full, ws in (doc.get("writers") or {}).items():
        mesh, _, key = full.partition("::")
        yield mesh, key, ws


def rule_context(doc: dict) -> dict:
    return {
        "project": doc.get("project") or "",
        "name": os.path.basename(str(doc.get("project") or "").rstrip("/")),
        "scene": doc.get("scene") or "",
        "schema": doc.get("schema") or "",
        "sources": doc.get("sources") or {},
        "summary": doc.get("summary") or {},
    }


def _cand(category: str, mesh: str, key: str, summary: str,
          owners: List[dict], **flags) -> dict:
    return {
        "category": category,
        "mesh": mesh,
        "key": key,
        "full": "%s::%s" % (mesh, key),
        "summary": summary,
        "flags": flags,
        "owners": owners,
        "evidence": sorted({where_of(w) for w in owners if where_of(w)}),
    }


# ---------------------------------------------------------------------------
# K1 同键多写者（配置型）
# ---------------------------------------------------------------------------
def rule_multi_writer(doc: dict) -> List[dict]:
    out = []
    for mesh, key, ws in iter_keys(doc):
        cfg = [w for w in ws if w.get("component") in CONFIG_COMPONENTS]
        owners: Dict[Tuple, List[dict]] = collections.OrderedDict()
        for w in cfg:
            owners.setdefault(owner_of(w), []).append(w)
        if len(owners) < 2:
            continue
        vals: set = set()
        for grp in owners.values():
            for w in grp:
                vals |= num_values(w)
        diff = len(vals) >= 2
        rep = []
        for grp in owners.values():
            w = grp[0]
            vv = sorted({v for x in grp for v in num_values(x)})
            rep.append({"source": w.get("source"), "component": w.get("component"),
                        "host": w.get("host") or "", "where": where_of(w),
                        "values": vv, "type": w.get("type")})
        out.append(_cand(
            "K1", mesh, key,
            "%d 个配置写者%s" % (len(owners), "，值不同" if diff else "，值相同"),
            cfg, value_diff=diff, owner_count=len(owners),
            values=sorted(vals),
        ))
    return out


# ---------------------------------------------------------------------------
# K2 Set/Delete 并存
# ---------------------------------------------------------------------------
def rule_set_delete(doc: dict) -> List[dict]:
    out = []
    for mesh, key, ws in iter_keys(doc):
        types = {w.get("type") for w in ws}
        if "Set" in types and "Delete" in types:
            # Delete 写者排在前（验收 E-T11-01：K2 行不能把 Delete 藏进「…(+N)」）；
            # 行内保持稳定：先 Delete 再 Set，各自按 where 排序。
            ordered = sorted(ws, key=lambda w: (0 if w.get("type") == "Delete" else 1,
                                                where_of(w)))
            out.append(_cand(
                "K2", mesh, key, "同一键同时有 Set 与 Delete 写者",
                ordered, types=sorted(t for t in types if t),
            ))
    return out


# ---------------------------------------------------------------------------
# K3 档位/整套 写者 vs 逐件/部位 写者
# ---------------------------------------------------------------------------
def rule_dial_vs_item(doc: dict) -> List[dict]:
    """两路：
    (a) 名字含 Dial/整套 的档位写者 与 逐件/部位写者 抢同键；
    (b) 同一 layer 上 ≥2 个互斥 state 取不同常量值（档位/选择器）与配置型写者抢同键。
    """
    out = []
    for mesh, key, ws in iter_keys(doc):
        def _text(w):
            return " ".join(str(w.get(f) or "") for f in ("clip", "layer", "state"))

        dial = [w for w in ws if DIAL_RE.search(_text(w))]
        dial_ids = {id(w) for w in dial}
        part = [w for w in ws
                if id(w) not in dial_ids
                and (PART_RE.search(_text(w)) or w.get("component") in CONFIG_COMPONENTS)]
        by_layer: Dict[Tuple[str, str], List[dict]] = collections.OrderedDict()
        for w in ws:
            if w.get("component") == "clip" and (w.get("layer") or ""):
                by_layer.setdefault((str(w.get("layer")), str(w.get("state"))), []).append(w)
        selector = []
        layer_groups: Dict[str, List[dict]] = collections.OrderedDict()
        for (layer, state), grp in by_layer.items():
            layer_groups.setdefault(layer, []).extend(grp)
        for layer, grp in layer_groups.items():
            states = {w.get("state") for w in grp}
            vals = set()
            for w in grp:
                vals |= num_values(w)
            if len(states) >= 2 and len(vals) >= 2:
                selector.extend(grp)
        cfg = [w for w in ws if w.get("component") in CONFIG_COMPONENTS]
        if (dial and part) or (selector and cfg):
            owners = dial + part + selector + cfg
            out.append(_cand(
                "K3", mesh, key,
                "档位/整套写者 与 逐件/部位写者 抢同一键",
                owners,
                dial=sorted({str(w.get("clip") or w.get("layer")) for w in dial}),
                part=sorted({str(w.get("clip") or w.get("layer") or w.get("host"))
                             for w in part}),
                selector_layers=sorted({str(w.get("layer")) for w in selector}),
                cfg_hosts=sorted({str(w.get("host")) for w in cfg}),
            ))
    return out


# ---------------------------------------------------------------------------
# K4 收缩键挂在套装根（目标是身体网格）
# ---------------------------------------------------------------------------
def _targets_body(mesh: str, w: dict) -> bool:
    if BODY_RE.match(mesh or ""):
        return True
    path = str(w.get("path") or "")
    top = path.split("/", 1)[0]
    return bool(BODY_RE.match(top))


def _host_level(host: str) -> str:
    """宿主是「套装/头像根」还是「物件」的粗判。

    去掉 `/ModularAvatar...` 容器后：末段以 `_MA` 结尾、或整条只有一段 → setroot；
    还有物件段（如 `..._MA/Sleeve_shinano`）→ item。只是候选排序用，不判对错。
    """
    h = str(host or "")
    if "/ModularAvatar" in h:
        h = h.split("/ModularAvatar", 1)[0]
    segs = [s for s in h.split("/") if s]
    if not segs:
        return "unknown"
    if len(segs) == 1 or re.search(r"_MA$", segs[-1]):
        return "setroot"
    return "item"


def rule_shrink_setroot(doc: dict) -> List[dict]:
    out = []
    for mesh, key, ws in iter_keys(doc):
        if not SHRINK_RE.search(key or ""):
            continue
        sc = [w for w in ws if w.get("component") == "ShapeChanger"
              and _targets_body(mesh, w)]
        if not sc:
            continue
        hosts = sorted({str(w.get("host") or "") for w in sc})
        levels = sorted({_host_level(h) for h in hosts})
        ma_container = any(MA_CONTAINER_RE.search(h) for h in hosts)
        out.append(_cand(
            "K4", mesh, key,
            "收缩键目标是身体网格（%d 个 ShapeChanger；宿主 %s）"
            % (len(sc), "/".join(levels)),
            sc, hosts=hosts, ma_container=ma_container, host_levels=levels,
        ))
    return out


# ---------------------------------------------------------------------------
# K5 脚型键的 ShapeChanger 归属（袜/鞋/未知）
#
# 归属判据按验收 E-T11-01：「按写者 `where` 字段指向的 prefab 读件的类型区分袜/鞋，
# 不靠折叠后的宿主名」。宿主经 `writers_static` 折叠到套装实例根（工程A MMN 的
# Socks/Shoes 都成 `_Outfit/Outfit_MMN_黑`）后已无区分力，所以：
#   1. 宿主名 token（老口径，保留）；
#   2. `where` = `<文件>:<行>`：回读该 prefab/场景，解析 ShapeChanger 所在 GameObject
#      的名字（stripped 顺 `m_CorrespondingSourceObject` 找源 prefab；源是 `.fbx` 等
#      二进制只能给 `<文件名#fid>`，对象名在 FBX 里离线取不到）；
#   3. 前两步都分不出时，按 `where` 指向的文件类型**猜**：厂商 prefab 写者=袜、
#      场景补挂写者=鞋（工程A MMN 修前 `vendor_only=True` 的「只挂袜不挂鞋」签名）。
#      这是本工作流的惯例判据，不是语义：只写进 `sock_owner_guess`/`shoe_owner_guess`，
#      结论字段保持判不了（`owner_unknown=True`），`owner_kind_source` 写明来源。
#      验收_20260919_BC至BH.md BG2：兜底猜测不许写进结论字段。
# ---------------------------------------------------------------------------
_WHERE_RE = re.compile(r"^(?P<file>.+):(?P<line>\d+)$")
_UNIT_RE = re.compile(r"^--- !u!(\d+) &(\d+)( stripped)?")
_GO_CLASS = 1


class WhereReader:
    """按写者 `where` 的 `<文件>:<行>` 回读 prefab/场景，解析所在 GameObject 名。

    只读候选真正用到的文件，按文件缓存；拿不到就返回 None，不猜。
    """

    def __init__(self, project: str):
        self.project = os.path.abspath(project) if project else ""
        self._files: Dict[str, Any] = {}
        self._guid: Optional[Dict[str, str]] = None

    @staticmethod
    def parts(w: dict) -> Tuple[Optional[str], Optional[int]]:
        m = _WHERE_RE.match(where_of(w))
        if not m:
            return None, None
        return m.group("file"), int(m.group("line"))

    @staticmethod
    def kind(w: dict) -> str:
        """`where` 指向的文件类型：prefab / scene / 扩展名 / unknown。"""
        f, _ = WhereReader.parts(w)
        if not f:
            return "unknown"
        ext = os.path.splitext(f)[1].lower()
        if ext == ".prefab":
            return "prefab"
        if ext == ".unity":
            return "scene"
        return ext.lstrip(".") or "unknown"

    def _guid_index(self) -> Dict[str, str]:
        """{guid: 资产绝对路径}；只在需要跟 stripped 源时建一次。"""
        if self._guid is not None:
            return self._guid
        idx: Dict[str, str] = {}
        root = os.path.join(self.project, "Assets")
        if os.path.isdir(root):
            for dp, _dn, fn in os.walk(root):
                for f in fn:
                    if not f.endswith(".meta"):
                        continue
                    p = os.path.join(dp, f)
                    try:
                        with open(p, encoding="utf-8", errors="ignore") as fh:
                            for _ in range(8):
                                line = fh.readline()
                                if not line:
                                    break
                                m = re.match(r"\s*guid:\s*([0-9a-fA-F]{32})\s*$", line)
                                if m:
                                    idx[m.group(1)] = p[:-len(".meta")]
                                    break
                    except OSError:
                        continue
        self._guid = idx
        return idx

    def _file(self, rel_file: str):
        """解析一个文件的 YAML 单元，返回 (units_by_fid, [(start_line, fid)], abs_path)。"""
        if rel_file in self._files:
            return self._files[rel_file]
        path = os.path.join(self.project, rel_file)
        units: Dict[int, Tuple[int, bool, str]] = {}
        order: List[Tuple[int, int]] = []
        cur = None
        cur_lines: List[str] = []
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                data = f.read()
        except OSError:
            self._files[rel_file] = (units, order, None)
            return self._files[rel_file]
        for i, ln in enumerate(data.splitlines(), 1):
            m = _UNIT_RE.match(ln)
            if m:
                if cur is not None:
                    units[cur[1]] = (cur[0], cur[2], "\n".join(cur_lines))
                    order.append((cur[3], cur[1]))
                cur = (int(m.group(1)), int(m.group(2)), bool(m.group(3)), i)
                cur_lines = []
            if cur is not None:
                cur_lines.append(ln)
        if cur is not None:
            units[cur[1]] = (cur[0], cur[2], "\n".join(cur_lines))
            order.append((cur[3], cur[1]))
        self._files[rel_file] = (units, order, path)
        return self._files[rel_file]

    @staticmethod
    def _field(text: str, name: str) -> Optional[str]:
        m = re.search(r"^\s*%s:\s*(.*?)\s*$" % re.escape(name), text, re.M)
        return m.group(1) if m else None

    def _go_name(self, rel_file: str, go_fid: int, depth: int = 0) -> Optional[str]:
        units, _order, _path = self._file(rel_file)
        unit = units.get(int(go_fid))
        if not unit:
            return None
        cid, stripped, text = unit
        if cid == _GO_CLASS and not stripped:
            return self._field(text, "m_Name") or ""
        m = re.search(
            r"m_CorrespondingSourceObject:\s*\{fileID:\s*(-?\d+),\s*guid:\s*([0-9a-fA-F]{32})",
            text)
        if not m:
            return None
        asset = self._guid_index().get(m.group(2))
        if not asset:
            return None
        ext = os.path.splitext(asset)[1].lower()
        if ext == ".prefab" and depth < 8:
            srel = os.path.relpath(asset, self.project)
            return self._go_name(srel, int(m.group(1)), depth + 1)
        # .fbx 等二进制：对象名在资产里，离线只能给定位
        return "<%s#%s>" % (os.path.basename(asset), m.group(1))

    def name_of(self, w: dict) -> Optional[str]:
        """`where` 行所在 MonoBehaviour 的 GameObject 名；解析不了返回 None。"""
        rel_file, line = self.parts(w)
        if not rel_file or line is None:
            return None
        units, order, path = self._file(rel_file)
        if not path or not order:
            return None
        fid = None
        for start, f in order:  # order 按文件顺序 → start 递增
            if start <= line:
                fid = f
            else:
                break
        if fid is None:
            return None
        unit = units.get(fid)
        if not unit:
            return None
        go_field = self._field(unit[2], "m_GameObject")
        if not go_field:
            return None
        m = re.search(r"fileID:\s*(-?\d+)", go_field)
        if not m:
            return None
        return self._go_name(rel_file, int(m.group(1)))


def run_rule_foot(doc: dict) -> List[dict]:
    """返回脚型键候选；供 selftest 直接调用。"""
    out = []
    reader = WhereReader(doc.get("project") or "")
    for mesh, key, ws in iter_keys(doc):
        if not FOOT_RE.search(key or "") or SHRINK_RE.search(key or ""):
            continue
        sc = [w for w in ws if w.get("component") in ("ShapeChanger", "BlendshapeSync")]
        if not sc:
            continue
        sock = shoe = 0
        sock_guess = shoe_guess = 0
        guess_used = False
        hosts = []
        where_names = []
        kind_sources = []
        for w in sc:
            h = str(w.get("host") or "")
            hosts.append(h)
            name = reader.name_of(w)
            if name:
                where_names.append(name)
            hay = " ".join(x for x in (h, name or "") if x)
            if SOCK_RE.search(hay):
                sock += 1
            if SHOE_RE.search(hay):
                shoe += 1
        if sock or shoe:
            kind_sources.append("where/宿主 token")
        else:
            # 名字两级都分不出时，才按 where 文件类型**猜**：厂商 prefab 写者=袜、
            # 场景补挂写者=鞋。这是工作流惯例不是语义，所以只进 `*_guess` 字段，
            # 结论字段 `sock_owner`/`shoe_owner` 一律判不了（验收_20260919_BC至BH.md
            # BG2：19/31 条 K5 只有兜底、不能写进结论）。
            guess_used = True
            kinds = [WhereReader.kind(w) for w in sc]
            prefab_w = [k for k in kinds if k == "prefab"]
            scene_w = [w for w, k in zip(sc, kinds) if k == "scene"]
            if prefab_w:
                sock_guess = len(prefab_w)
                kind_sources.append("where=prefab(厂商件)")
            if scene_w:
                shoe_guess = len(scene_w)
                kind_sources.append("where=scene(场景补挂)")
        scene_added = [w for w in sc if w.get("source") in ("ours_legacy", "gen")]
        vendor_only = bool(sc) and not scene_added and all(
            w.get("source") == "vendor_sc" for w in sc)
        flags = {
            "sock_owner": sock > 0,
            "shoe_owner": shoe > 0,
            "sock_owner_guess": sock_guess > 0,
            "shoe_owner_guess": shoe_guess > 0,
            "owner_unknown": (sock == 0 and shoe == 0),
            "scene_added": bool(scene_added),
            "vendor_only": vendor_only,
            "hosts": sorted(set(hosts)),
            "where_names": sorted(set(n for n in where_names if n)),
            "owner_kind_source": "；".join(kind_sources) or "判不了",
        }
        symptom = []
        if guess_used:
            g = []
            if sock_guess:
                g.append("厂商 prefab 写者=袜")
            if shoe_guess:
                g.append("场景补挂写者=鞋")
            symptom.append("袜/鞋归属判不了" + ("（猜测：%s）" % "、".join(g) if g else ""))
        elif sock and not shoe:
            symptom.append("只识别到袜件写者、没有鞋件写者")
        elif shoe and not sock:
            symptom.append("只识别到鞋件写者、没有袜件写者")
        elif sock and shoe:
            symptom.append("袜/鞋写者同时存在")
        else:
            symptom.append("宿主与 where 都分不出袜/鞋（判不了）")
        if vendor_only:
            symptom.append("写者全在厂商 prefab 内（场景无补挂）")
        if scene_added:
            symptom.append("有场景补挂写者")
        out.append(_cand("K5", mesh, key, "；".join(symptom), sc, **flags))
    return out


rule_foot_owner = run_rule_foot


# ---------------------------------------------------------------------------
# K6 形态键目标值越界
# ---------------------------------------------------------------------------
def rule_out_of_range(doc: dict) -> List[dict]:
    out = []
    for mesh, key, ws in iter_keys(doc):
        if not mesh or is_prop_key(key):
            continue
        bad = []
        for w in ws:
            # 只认形态键（SkinnedMeshRenderer, class_id 137）；相机 FOV、Trail m_Time
            # 这类也有 mesh/key 但不是形态键，靠 class_id 排除。
            if w.get("class_id") != 137:
                continue
            vals = num_values(w)
            if any(v < 0 or v > 100 for v in vals):
                bad.append(w)
        if bad:
            out.append(_cand(
                "K6", mesh, key, "形态键目标值越界（<0 或 >100）", bad,
                values=sorted({v for w in bad for v in num_values(w)}),
            ))
    return out


RULES = [
    ("K1", "multi_writer", rule_multi_writer),
    ("K2", "set_delete", rule_set_delete),
    ("K3", "dial_vs_item", rule_dial_vs_item),
    ("K4", "shrink_setroot", rule_shrink_setroot),
    ("K5", "foot_owner", rule_foot_owner),
    ("K6", "out_of_range", rule_out_of_range),
]
CATEGORY_TITLES = {
    "K1": "K1 同键多写者（配置型）",
    "K2": "K2 Set/Delete 并存",
    "K3": "K3 档位/整套 与 逐件/部位 抢键",
    "K4": "K4 收缩键挂套装根（目标是身体）",
    "K5": "K5 脚型键归属（袜/鞋/未知）",
    "K6": "K6 形态键目标值越界",
}


def run_rules(doc: dict) -> Dict[str, List[dict]]:
    return {cat: fn(doc) for cat, _name, fn in RULES}


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------
def _owner_line(o: dict) -> str:
    if o.get("component") == "clip":
        return "%s [%s]" % (o.get("clip") or "?", o.get("source"))
    vv = o.get("values") or []
    vs = "/".join(_fmt(v) for v in vv)
    host = o.get("host") or "(无宿主)"
    return "%s <%s>%s" % (host, o.get("source"), (" =%s" % vs) if vs else "")


def _fmt(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _esc(s: Any) -> str:
    return str(s).replace("|", "\\|")


def render_project_md(doc: dict, cands: Dict[str, List[dict]]) -> List[str]:
    ctx = rule_context(doc)
    L = []
    L.append("### %s" % ctx["name"])
    L.append("")
    L.append("- 场景：`%s`；keys=%s writers=%s；sources=%s"
             % (ctx["scene"], (ctx["summary"] or {}).get("keys"),
                (ctx["summary"] or {}).get("writers"),
                json.dumps(ctx["sources"], ensure_ascii=False)))
    L.append("")
    for cat, _name, _fn in RULES:
        rows = cands.get(cat) or []
        L.append("#### %s（%d）" % (CATEGORY_TITLES[cat], len(rows)))
        if not rows:
            L.append("")
            L.append("（无候选）")
            L.append("")
            continue
        L.append("")
        L.append("| mesh::key | 症状 | 写者（宿主 / 来源 / 值） | 证据（文件:行） |")
        L.append("|---|---|---|---|")
        for c in sorted(rows, key=lambda x: (x["mesh"], x["key"])):
            owners_all = c["owners"]
            if cat == "K2":
                # Set/Delete 并存行：Delete 写者必须全部列出、排在前（验收 E-T11-01）。
                owners = "; ".join(_owner_line(o) for o in owners_all)
            else:
                owners = "; ".join(_owner_line(o) for o in owners_all[:6])
                if len(owners_all) > 6:
                    owners += " …(+%d)" % (len(owners_all) - 6)
            ev = c["evidence"][:2]
            L.append("| `%s` | %s | %s | %s |" % (
                _esc(c["full"]), _esc(c["summary"]), _esc(owners),
                _esc("；".join(_short(e) for e in ev)) if ev else ""))
        L.append("")
    return L


def _short(path: str, n: int = 70) -> str:
    p = str(path)
    return p if len(p) <= n else "…" + p[-n:]


def render_aggregate(docs: List[dict], results: List[Dict[str, List[dict]]],
                     title: str = "T-11 静态规则候选（14 个历史工程）",
                     selftest_text: Optional[str] = None) -> str:
    L = ["# %s" % title, ""]
    L.append("> 生成：`开发工具/通用工具/审查/perception/static_rules.py`（在 writers.json 上离线跑，"
             "不重扫工程、不判对错）。")
    L.append("> 输入：`_长程任务_20260918/审查产出/_历史工程/<工程>/writers.json`"
             "（schema `%s`，T-11/writers_static.py 09-19 版产物）。" % SCHEMA)
    L.append("> 规则出处：03c Q11/E8（`03c_Q8-Q11_接口与实验单.md:82,110`）、"
             "03 §4.4/§4.5（`03_研究与方案.md:132,150-151`）；验收要求见 "
             "`派工/验收_20260919_AV至BB.md:30`。")
    L.append("> **本表只列候选，对错要几何/构建期截获/人判；静态规则结果不进用户表。**")
    L.append("")
    L.append("## 0. 汇总")
    L.append("")
    # 输入自检：schema / scene / gen_writers
    bad = [rule_context(d)["name"] for d in docs
           if (d.get("schema") or "") != SCHEMA]
    scenes = {rule_context(d)["scene"] for d in docs}
    gens = {bool(d.get("gen_writers")) for d in docs}
    L.append("- 输入自检：%d 份 writers.json；schema 非 `%s` 的 %d 份%s"
             % (len(docs), SCHEMA, len(bad),
                ("（%s）" % "、".join(bad)) if bad else ""))
    L[-1] += "；gen_writers=%s；场景 %d 个（见下表）。" % (
        sorted(gens), len(scenes))
    L.append("")
    header = "| 工程 | 场景 | " + " | ".join(
        "%s %s" % (cat, CATEGORY_TITLES[cat].split(" ", 1)[1]) for cat, _n, _f in RULES
    ) + " | 合计 |"
    L.append(header)
    L.append("|" + "---|" * (len(RULES) + 3))
    totals = collections.Counter()
    for doc, res in zip(docs, results):
        counts = [len(res.get(cat) or []) for cat, _n, _f in RULES]
        for cat, c in zip([c for c, _n, _f in RULES], counts):
            totals[cat] += c
        L.append("| %s | `%s` | %s | %d |" % (
            rule_context(doc)["name"], rule_context(doc)["scene"],
            " | ".join(str(c) for c in counts), sum(counts)))
    L.append("| **合计** |  | %s | **%d** |" % (
        " | ".join(str(totals[c]) for c, _n, _f in RULES), sum(totals.values())))
    L.append("")
    L.append("## 1. 逐工程候选")
    L.append("")
    for doc, res in zip(docs, results):
        L.extend(render_project_md(doc, res))
    L.append("## 2. 口径、盲区与未决")
    L.append("")
    k1 = [c for res in results for c in (res.get("K1") or [])]
    k1_diff = sum(1 for c in k1 if c["flags"].get("value_diff"))
    L.append("1. **K1 只统计配置型写者**（ShapeChanger/BlendshapeSync/ObjectToggle），"
             "不含 14 工程 149,891 条 clip 写者；后者跨状态本来就会取不同值，"
             "全算进来会淹没候选。本批 K1 %d 条：**值不同 %d 条（冲突候选）、"
             "值相同 %d 条（多写者但一致，信息）**。" % (len(k1), k1_diff, len(k1) - k1_diff))
    L.append("2. **K3 在 14 历史工程为 0**：14 工程没有任何 `Dial/整套/スライダー` 档位层，"
             "也没有「同一 layer 多态选择器 + 配置型写者同键」的组合。已知真样本在客户单："
             "工程B `Body_base::Foot` 等 3 键有厂商 `Foot` 层 4 档（Foot_无/Foot/Foot+Toe/"
             "Foot_highheels）与 LopEar/LUNALICE 的 ShapeChanger 抢键；工程A `Dial_整套` "
             "与 `Off_部位_*` 同键 32 例——都不在这 14 工程里。")
    L.append("3. **K4 的 `host_levels` 是粗判**：末段 `_MA`/单段宿主记 `setroot`，"
             "`..._MA/Sleeve_shinano` 这种还有物件段的记 `item`——`item` 行不一定误报"
             "（物件级也能收缩身体），只是按任务口径「挂整套根」优先看 `setroot`；"
             "`ma_container=False` 的 `PurpleWhite`/`Cloth`/`Shinano` 仍是套装/头像根，"
             "本表把宿主原样列出由人判。")
    L.append("4. **K5 的袜/鞋判定**：先宿主名 token，再按写者 `where`（`<文件>:<行>`）回读该 "
             "prefab/场景里 ShapeChanger 所在 GameObject 名（`where_names`，stripped 顺源 "
             "prefab 找；`.fbx` 源只能给 `<文件名#fid>`）。两级都取不到真名时，结论字段 "
             "`sock_owner`/`shoe_owner` 一律**判不了**（`owner_unknown=True`）；按 `where` "
             "文件类型推的「厂商 prefab 写者=袜、场景补挂写者=鞋」只写进 "
             "`sock_owner_guess`/`shoe_owner_guess`（`owner_kind_source` 写明来源；"
             "这是工作流惯例不是语义，验收_20260919_BC至BH.md BG2）。"
             "工程A MMN 的 Socks/Shoes 被折成 `_Outfit/Outfit_MMN_黑`，"
             "只能给 `sock_owner_guess=True` 的猜测。")
    L.append("5. **K2 行内 Delete 写者排在前、不折叠**（`…(+N)` 会把 Delete 藏掉）。")
    L.append("6. **K6 排除属性路径与非形态键**（`material.*`/`m_*`、class_id≠137）：否则把材质 "
             "`_DissolvePos.y=-1.27`、Trail `m_Time=10000`、相机 FOV 这类合法值误报成越界；"
             "14 工程真形态键越界 = 0。")
    L.append("7. 未做胜负判定：`winner_rule.ma` 留空等 T-12 构建期截获（writers_汇总 §4.6）；"
             "本表不排序、不给建议。")
    if selftest_text:
        L.append("")
        L.append("## 3. 已知样本自验（`static_rules.py --selftest`）")
        L.append("")
        L.append("```")
        L.append(selftest_text.rstrip("\n"))
        L.append("```")
        L.append("")
        L.append("- 工程B垂耳兔 11 个 `Shrink_*` 落在 `08_WhitePink_Milfy_MA/ModularAvatar/"
                 "MA Shape Changer`（K4 正样本）。")
        L.append("- 工程A MMN 平脚键 `Foot_heel_OFF_____足_ヒールオフ`：live 有厂商 prefab "
                 "写者（袜）+ 场景补挂写者（鞋，`ours_legacy`），但两者都取不到真名，K5 结论 "
                 "`owner_unknown=True`、`sock_owner_guess=shoe_owner_guess=True`；"
                 "**真修前场景**（git `ceb4070b^` 的 hardlink 影子工程，非手工删写者）只有厂商 "
                 "prefab 写者，K5 标 `vendor_only=True` + `sock_owner_guess=True` + "
                 "`owner_unknown=True`（「只挂袜不挂鞋」只能是猜测）。影子工程放 `派工/_scratch/`，"
                 "`finally` 删。")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def load_doc(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_one(args) -> int:
    if args.writers:
        doc = load_doc(args.writers)
    elif args.project:
        sys.path.insert(0, _HERE)
        import writers_static as W  # noqa: E402
        scan = W.ProjectScan(args.project, args.scene)
        doc = W.build_writer_graph(scan)
    else:
        print("需要 --writers 或 --project", file=sys.stderr)
        return 2
    res = run_rules(doc)
    ctx = rule_context(doc)
    print("[static_rules] %s scene=%s" % (ctx["name"], ctx["scene"]))
    for cat, name, _fn in RULES:
        print("  %s %-14s %d" % (cat, name, len(res.get(cat) or [])))
    if args.json:
        _dump_json(args.json, [doc], [res])
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(render_aggregate([doc], [res], title="T-11 静态规则候选（单工程）",
                                     selftest_text=_read_text(args.selftest_log)))
    return 0


def cmd_batch(args) -> int:
    base = args.batch
    files = sorted(
        os.path.join(base, d, "writers.json")
        for d in os.listdir(base)
        if os.path.isfile(os.path.join(base, d, "writers.json"))
    )
    docs, results = [], []
    for p in files:
        doc = load_doc(p)
        docs.append(doc)
        results.append(run_rules(doc))
        ctx = rule_context(doc)
        print("[static_rules] %-22s %s" % (
            ctx["name"], {cat: len(results[-1].get(cat) or []) for cat, _n, _f in RULES}))
    if args.json:
        _dump_json(args.json, docs, results)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(render_aggregate(docs, results,
                                     selftest_text=_read_text(args.selftest_log)))
        print("[static_rules] → %s（%d 工程）" % (args.md, len(docs)))
    return 0


def _read_text(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _dump_json(path: str, docs: List[dict], results: List[Dict[str, List[dict]]]) -> None:
    payload = {
        "schema": "perception/static_rules/1",
        "generated_by": "static_rules.py",
        "rule_version": "2026-09-19",
        "projects": [
            {"context": rule_context(doc),
             "counts": {cat: len(res.get(cat) or []) for cat, _n, _f in RULES},
             "candidates": {cat: res.get(cat) or [] for cat, _n, _f in RULES}}
            for doc, res in zip(docs, results)
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("[static_rules] → %s" % path)


# ---------------------------------------------------------------------------
# selftest：真实工程已知样本
# ---------------------------------------------------------------------------
def _scan_live(project: str):
    sys.path.insert(0, _HERE)
    import writers_static as W  # noqa: E402
    return W.build_writer_graph(W.ProjectScan(project))


def _scratch_root() -> str:
    """测试副本目录：`<repo>/_长程任务_20260918/派工/_scratch/`（已 gitignore）。

    硬链接影子工程必须放这里、由 `selftest` 的 finally 删掉——留在工作树里会被
    `git add -A` 把影子里的文本资产收进库（验收 E-T11-01 问题③）。
    """
    d = os.path.join(REPO, "_长程任务_20260918", "派工", "_scratch")
    os.makedirs(d, exist_ok=True)
    return d


def _prepare_prefix_shadow() -> Optional[str]:
    """用 git 里的修前场景搭一个 hardlink 影子工程（只改场景文件），返回工程路径。

    路径在 `派工/_scratch/`（已 gitignore），由调用方 finally 删除。
    注意：`Assets/`/`Packages/` 是 `cp -al` 的**硬链接**（不占额外磁盘）；影子工程只读，
    绝不能在里面对已有文件做原地写（会改到真 工程A）。只替换场景文件时用
    「先 rm 再写新文件」，断开硬链接。
    """
    shadow = os.path.join(_scratch_root(), "static_rules_selftest", "工程A_prefix")
    scene = os.path.join(shadow, "Assets/_Work/工程A.unity")
    try:
        subprocess.run(["git", "-C", REPO, "rev-parse", "--verify",
                        MMN_FIX_COMMIT + "^"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return None
    try:
        if not os.path.isdir(os.path.join(shadow, "Assets")):
            os.makedirs(shadow, exist_ok=True)
            for sub in ("Assets", "Packages"):
                subprocess.run(["cp", "-al", os.path.join(PROJECT_A_DIR, sub),
                                os.path.join(shadow, sub)], check=True)
        pre = subprocess.run(
            ["git", "-C", REPO, "show", "%s^:%s" % (MMN_FIX_COMMIT, MMN_FIX_SCENE)],
            check=True, stdout=subprocess.PIPE).stdout
        if os.path.exists(scene):
            os.remove(scene)
        with open(scene, "wb") as f:
            f.write(pre)
        return shadow
    except (OSError, subprocess.CalledProcessError):
        return None


def selftest() -> int:
    fails: List[str] = []

    # --- 正样本 1：工程B垂耳兔 11 个收缩键挂在整套根 08_WhitePink_Milfy_MA ---
    if os.path.isdir(ZAIJIAN_PROJECT):
        doc = _scan_live(ZAIJIAN_PROJECT)
        res = run_rules(doc)
        k4 = res["K4"]
        got = {c["key"]: c for c in k4
               if any("08_WhitePink_Milfy_MA" in h for h in c["flags"].get("hosts", []))}
        print("[selftest:工程B] scene=%s K4=%d，落在 08_WhitePink_Milfy_MA 的键=%d"
              % (doc.get("scene"), len(k4), len(got)))
        for k in sorted(got):
            print("[selftest:工程B]   %-14s <- %s" % (k, got[k]["flags"]["hosts"][0]))
        if len(got) < 11:
            fails.append("垂耳兔收缩键应 ≥11 个挂在 08_WhitePink_Milfy_MA，实际 %d：%s"
                         % (len(got), sorted(got)))
        if not any(c["flags"].get("ma_container") for c in got.values()):
            fails.append("垂耳兔收缩键未标出 MA 容器宿主")
        # 正样本 3：工程B Foot 层 4 档选择器 与 逐件 SC 抢键（K3）
        k3 = [c for c in res["K3"] if "Foot" in c["flags"].get("selector_layers", [])]
        print("[selftest:工程B] K3 选择器档位抢键=%d：%s"
              % (len(k3), sorted(c["full"] for c in k3)))
        if not k3:
            fails.append("工程B Foot 层档位 与 逐件 SC 抢键未被 K3 纳入")
    else:
        print("[selftest:工程B] SKIP（缺 %s）" % ZAIJIAN_PROJECT)

    # --- 正样本 2：工程A MMN 平脚键挂袜子（厂商 prefab SC）+ 场景补挂鞋 ---
    mmn_key = "Foot_heel_OFF_____足_ヒールオフ"
    if os.path.isdir(PROJECT_A_DIR):
        doc = _scan_live(PROJECT_A_DIR)
        res = run_rules(doc)
        foot = [c for c in res["K5"] if c["key"] == mmn_key]
        print("[selftest:工程A] scene=%s K5=%d，MMN 平脚键候选=%d"
              % (doc.get("scene"), len(res["K5"]), len(foot)))
        if not foot:
            fails.append("MMN 平脚键 %s 未被 K5 纳入" % mmn_key)
        else:
            c = foot[0]
            f = c["flags"]
            print("[selftest:工程A]   %s | sock=%s shoe=%s sock_guess=%s shoe_guess=%s "
                  "owner_unknown=%s scene_added=%s vendor_only=%s"
                  % (mmn_key, f["sock_owner"], f["shoe_owner"],
                     f["sock_owner_guess"], f["shoe_owner_guess"], f["owner_unknown"],
                     f["scene_added"], f["vendor_only"]))
            print("[selftest:工程A]   宿主=%s where_names=%s owner_kind_source=%s"
                  % (f["hosts"], f.get("where_names"), f.get("owner_kind_source")))
            got_src = {o.get("source") for o in c["owners"]}
            if not ({"vendor_sc"} & got_src):
                fails.append("MMN 平脚键缺厂商 prefab 写者（袜子 SC）")
            if not ({"ours_legacy", "gen"} & got_src):
                fails.append("MMN 平脚键缺场景补挂写者（鞋 SC）")
            # BG2 返工（验收_20260919_BC至BH.md）：MMN 的袜/鞋只能靠 where 文件类型猜，
            # 结论字段必须判不了，猜测另放 `*_guess`。
            if not f["sock_owner_guess"]:
                fails.append("MMN 平脚键应在 sock_owner_guess 给出「厂商 prefab=袜」猜测")
            if not f["shoe_owner_guess"]:
                fails.append("MMN 平脚键应在 shoe_owner_guess 给出「场景补挂=鞋」猜测")
            if not f["owner_unknown"]:
                fails.append("MMN 平脚键袜/鞋结论应为判不了（owner_unknown=True）")
            if f["sock_owner"] or f["shoe_owner"]:
                fails.append("MMN 平脚键不得把兜底猜测写进结论字段 sock_owner/shoe_owner")
            if f.get("owner_kind_source") in (None, "", "判不了"):
                fails.append("MMN 平脚键没给出 owner_kind_source（where 回读未生效）")
        # 修前影子工程（hardlink，放 _scratch，finally 删——不留工作树）
        shadow = None
        try:
            shadow = _prepare_prefix_shadow()
            if shadow:
                pdoc = _scan_live(shadow)
                pres = run_rules(pdoc)
                pfoot = [c for c in pres["K5"] if c["key"] == mmn_key]
                print("[selftest:工程A:修前] scene=%s MMN 候选=%d"
                      % (pdoc.get("scene"), len(pfoot)))
                if not pfoot:
                    fails.append("修前影子工程里 MMN 平脚键未被 K5 纳入")
                else:
                    pf = pfoot[0]["flags"]
                    print("[selftest:工程A:修前]   sock=%s shoe=%s sock_guess=%s "
                          "owner_unknown=%s vendor_only=%s scene_added=%s hosts=%s"
                          % (pf["sock_owner"], pf["shoe_owner"], pf["sock_owner_guess"],
                             pf["owner_unknown"], pf["vendor_only"],
                             pf["scene_added"], pf["hosts"]))
                    if not pf["vendor_only"]:
                        fails.append("修前 MMN 平脚键应 vendor_only=True")
                    if pf["scene_added"]:
                        fails.append("修前 MMN 平脚键不应有场景补挂写者")
                    if not pf["sock_owner_guess"] or not pf["owner_unknown"]:
                        fails.append("修前 MMN 平脚键应在 sock_owner_guess 给出「厂商 prefab=袜」"
                                     "猜测且结论判不了（owner_unknown=True）")
                    if pf["sock_owner"]:
                        fails.append("修前 MMN 平脚键不得把兜底猜测写进 sock_owner")
            else:
                print("[selftest:工程A:修前] SKIP（git/影子工程不可用）")
        finally:
            shutil.rmtree(os.path.join(_scratch_root(), "static_rules_selftest"),
                          ignore_errors=True)
    else:
        print("[selftest:工程A] SKIP（缺 %s）" % PROJECT_A_DIR)

    if fails:
        for f in fails:
            print("[FAIL] %s" % f)
        return 1
    print("[selftest] OK")
    return 0


# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="T-11 静态规则候选（writers.json）")
    ap.add_argument("--writers", help="writers.json 路径")
    ap.add_argument("--project", help="工程根目录（现扫）")
    ap.add_argument("--scene", help="场景（配合 --project）")
    ap.add_argument("--batch", help="目录：跑 <dir>/*/writers.json")
    ap.add_argument("--md", help="输出 markdown")
    ap.add_argument("--json", help="输出 JSON")
    ap.add_argument("--selftest", action="store_true", help="真实工程已知样本自验")
    ap.add_argument("--selftest-log", help="把该日志嵌进 markdown（配合 --md）")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.batch:
        return cmd_batch(args)
    return cmd_one(args)


if __name__ == "__main__":
    sys.exit(main())
