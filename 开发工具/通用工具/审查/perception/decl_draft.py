#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decl_draft.py —— 感知声明草案生成器（T-04，04 第一期开工清单 §T-04）。
【项目沉淀】通用工具
适用素体：无关
相关素材：工程生成器源码与场景
工具链　：Python 3 + PyYAML（离线）
可复用性：★★ 改写者来源表即可复用
用途　　：感知声明草案生成器：从工程里能读到的事实起草 _感知/声明.yaml，人只补 human 项。


从工程里能读到的事实起草 `_感知/声明.yaml`：人只补 `human:` 项。
来源（03a §Q1-⑤ S1–S9）：

  S1 生成器表      MenuGenA2.cs 的 OUTFITS/OUTFIT_HIDE/PARTS/ACCPARTS/HEADPARTS/
                   HAIRS/EARTAILS/HALOS/HEADDRESSES/PART_SHAPES/CHEST_PARTS/
                   VENDOR_CLIP/VENDOR_ALT/CONFLICTS + Suppress/ShowInRange 调用
  S2 场景/prefab   MA ShapeChanger / BlendshapeSync / ObjectToggle（复用 writers_static）
  S3 厂商 clip      VENDOR_CLIP 指向的 <件> ON/OFF.anim 曲线
  S7 T4 params     params.json（参数默认值；menu 段仍以生成器表为准）
  S9 素体档案/片段  Kaguya.yaml（baseline/键类别/厂商惯例/alt_pieces）、*.decl.yaml
  T-05 盘点         inventory.json（covers/closed/切换方式/渲染器路径）

原则：**厂商写者一律 `confidence.correct: unknown`；拿不准的机制标 `human:`，不编。**

用法：
    python3 decl_draft.py --project <工程目录> --out <草案.yaml> \
        [--profile <素体档案.yaml>] [--inventory <inventory.json>] [--params <params.json>] \
        [--scene <场景.unity>] [--menu-gen <MenuGenA2.cs>]
    python3 decl_draft.py --selftest        # 对 工程A 起草并与人写声明比对（只读工程）
    python3 decl_draft.py --selftest-blind  # 盲起草预演（git show ceb4070b^ 的旧源，只读 git）

验收（04 §T-04，2026-09-19 签字 B-T04 改严格口径；09-19 CK2 落实 B-T04b 六条裁决）：
草案过 decl_validate.py 0 error；parts 覆盖率 ≥90%；D1/D3/D4a/D6「与人写一致」=
kind＋目标集合全等＋when＋expect 全同，一致率 ≥80%（selftest 同时打印旧口径
kind＋目标重叠 作对照，并给两口径的分子/分母）。

严格口径的**规范化**（2026-09-19 C-K 补，2026-09-19 CK2 补 6–9；仅限语义等价、
文本不同的写法；目标集合仍要求全等，不放宽）
--------------------------------------------------------------------------------
人写声明允许 `cases:` 多分支与 `else:` 兜底，草案则按「一个 (when, expect) 一个条目」
平铺。直接字符串比对会把等价写法判成不一致，故 selftest 的严格比较先做下列规范化，
再比 `kind / 目标集合 / when / expect`：

1. **cases 展开**：带 `cases` 的 dep 取每条 `case` 的 `(when, expect)` 作一个比较单元；
   `expect: dont_care` 的 case 与 `else` 不参与（它们不是可判定的守卫断言）。无 `cases`
   的 dep 只有一个单元。
2. **when 布尔规范化**：按顶层 `|` 拆成析取子句集合，子句内按 `&` 拆成原子集合，
   原子排序、去多余括号、`and`→`&`、`{...}` 集合内元素排序。于是
   `vis(a) and vis(b)` ≡ `vis(b) & vis(a)`、`outfit in {B, A}` ≡ `outfit in {A, B}`。
3. **when 析取覆盖**：人写一条 `A | B`（＝两个蕴含）可由草案的 `A` 与 `B` 两条共同覆盖；
   反向，草案一条 `A`（或 `A | B`）只要被某条人写的析取集合包含即算命中。这不是放宽
   目标——每条覆盖都必须 kind／目标集合／expect 全同。
4. **expect 数值/默认容差规范化**：整数与浮点同值（`100` ≡ `100.0`）；省略的 `tol`
   与显式 `tol: 0.5` 同（0.5 是 schema 默认容差）。其余键（含 `class`、`deleted`、
   `hidden/shown`）一律原样比较，不丢。
5. **键类别别名（CK 裁决 2）**：厂商同一 clip（`kaguya outer ON/OFF.anim`）里同时有
   `outer_shlink` 与 `outer_shrink` 两个键，profile `key_classes.shrink` 只收了后者。
   `shlink` 是厂商拼写，视作 `shrink` 别名补 `expect.class`（草案生成与比较两侧都按别名）。
6. **部件身份按对象路径（CK 裁决 3）**：目标里的 `part: <id>` 先经各自声明的
   `parts[].objects[].path`（规范化后的根相对路径）解析成路径集合再比；id 文本不同、
   路径相同即同一件（人写 `Kitty.shirt_a` ≡ 草案 `Kitty.kaguya_shirt_big`）。`when` 里
   `vis(<id>)` 同理先映射到路径。声明里查不到该 id 的才退回 id 文本。
7. **可见件过滤（CK 裁决 5）**：比较 targets 前，用声明/盘点里的 `outfit`/`toggle`
   显隐关系，把在 when 条件下**必然不可见**的件从两边 targets 里剔掉（hood 类
   「不可见件不列」）。规则：某件有显式 `outfit` 档集合、而 when 每个析取子句都把
   outfit 限到与它不相交的档（且没有 `vis(<该件>)`）→ 该件必然不可见，剔除；只要有一
   个子句不约束 outfit 或与它有交集，就保留（宁多留不误删）。
8. **被取代条目不进分母（CK 裁决 4）**：人写后条 `supersedes: [前条]` 时，前条
   （如 `MMN.socks_foot_flat`）不进严格口径的分母；它若仍与草案对应也不计分母。
9. **迁移条目不进分母（CK 裁决 1）**：由 B-T07a 从生成器迁入声明、工程里已无其它
   事实来源的条目记 `human_only`，不进分母，单独列一行计数。判定依据：**草案只读
   工程事实，不读自己的下游产物**（`Gen/Clip/Decl_*.anim`、`gen_writers.json` 都是
   本声明的下游，读了就是抄答案）。识别走声明条目自身的 `origin`/`human_only` 字段，
   退而扫 `source`/`note` 里的迁移标记；名单本身是数据常量（不写进比较逻辑），
   名单里有、但声明里识别不出迁移标记的，selftest 会点名交 Claude 补标，不猜。

草案侧另有两条（CK 裁决 6）：`pending_cleanup` 条目（场景里待清的旧冗余 SC，如
`d1.kaguya_outer_sailor_shrink`）不进精确率分母；草案多出条目若与某条 `human_only`
迁移条目 when 等价、targets 重叠 ≥80%，记为「草案佐证」计入命中，否则单列。
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Sequence, Set, Tuple

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
WORKSPACE = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))

import unity_yaml  # noqa: E402
import writers_static  # noqa: E402

VALIDATE = os.path.join(_HERE, "decl_validate.py")

# ===========================================================================
# CK2 裁决的数据常量（名单是数据，不写进比较逻辑）
# ---------------------------------------------------------------------------
# human_only：B-T07a 把生成器事实搬进声明、工程里已无其它事实来源的条目
# （草案只读工程事实、不读自己的下游产物，故永久不进严格口径分母）。识别靠声明
# 条目自身的 `human_only`/`origin` 字段，或 `source`/`note` 里的迁移标记；名单与
# 识别结果对不上时 selftest 点名交 Claude 补标。见文件头规则 9。
HUMAN_ONLY_IDS = (
    "RePoppin.shirt_under_parker",
    "工程A.default_hat_hides_added_ear",
    "工程A.head_acc_hides_ears",
    "工程A.hood_hides_head_items",
    "kaguya.nipple_hidden_when_chest_covered",
    # 09-20 Claude 裁决：声明先行（HoleHeel，DSH CL 新增），工程里无生成器表可读
    "工程A.holeheel_shown",
    "工程A.holeheel_hides_shoes",
    "工程A.holeheel_foot_hiheel",
)
# 迁移标记：出现在 source/note 里即认为是「生成器表/层已被 B-T07a 删并迁入声明」。
MIGRATION_MARKERS = ("B-T07a", "b-t07a", "声明先行")  # 09-20 Claude：声明先行条目（工程里无生成器表可读，如 HoleHeel）同迁移条目处理
# pending_cleanup：草案从当前工程读出的真实写入者，但已知是待清冗余（A-工程A-12
# 在清），不计入草案精确率分母。见文件头「草案侧另有两条」。
PENDING_CLEANUP_IDS = ("d1.kaguya_outer_sailor_shrink",)
# 草案佐证：草案多出条目与 human_only 迁移条目 when 等价时，targets 重叠阈值。
CORROBORATE_OVERLAP = 0.8

# 生成器表里的参数 → 槽/控件键。键名按 03a/声明惯例。
SLOT_KEYS = {
    "A2_Coat": "coat", "A2_Top": "top", "A2_Btm": "bottom",
    "A2_Und": "under", "A2_Sok": "socks", "A2_Sho": "shoes",
}
CONTROL_KEYS = {
    "A2_Hed": "hed", "A2_Arm": "arm", "A2_Chm": "chm", "A2_Mth": "mth",
    "A2_Neck": "neck", "A2_Boot": "boot",
    "A2_Hair": "hair", "A2_EarTail": "eartail", "A2_Halo": "halo", "A2_Head": "head",
}
KIND_BY_SLOT = {
    "coat": "outer", "top": "top", "bottom": "bottom", "under": "underwear",
    "socks": "socks", "shoes": "shoes",
}
KIND_HINTS = [
    ("glove", "gloves"), ("sock", "socks"), ("stocking", "socks"),
    ("shoe", "shoes"), ("boot", "shoes"), ("loafer", "shoes"),
    ("skirt", "bottom"), ("culotte", "bottom"), ("pant", "bottom"),
    ("bra", "underwear"), ("panties", "underwear"),
    ("ear", "hat"), ("cap", "hat"), ("beret", "hat"), ("ribbon", "hat"),
    ("hood", "hat"), ("hair", "hair"),
]
COVER_BY_KIND = {
    "shoes": ["LeftFoot", "RightFoot", "LeftToes", "RightToes"],
    "socks": ["LeftLowerLeg", "RightLowerLeg", "LeftFoot", "RightFoot",
              "LeftToes", "RightToes"],
    "gloves": ["LeftHand", "RightHand"],
    "outer": ["Chest", "UpperChest", "Spine"],
    "top": ["Chest", "UpperChest", "Spine"],
    "onepiece": ["Chest", "UpperChest", "Spine", "Hips"],
    "bottom": ["Hips", "Spine", "LeftUpperLeg", "RightUpperLeg"],
    "underwear": ["Hips"],
    "hat": ["Head"],
    "hair": ["Head"],
    "acc": [],
    "body_part": [],
}
FIT_BY_KIND = {
    "shoes": "closed", "socks": "tight", "gloves": "closed",
    "underwear": "tight", "outer": "loose", "bottom": "loose",
    "top": "tight", "onepiece": "loose", "hat": "none", "hair": "none",
    "acc": "none", "body_part": "none",
}


# ===========================================================================
# C# 文本小解析（只吃 MenuGenA2 的表结构与 Suppress 调用，不做通用 C# 解析）
# ===========================================================================
def strip_cs_comments(text: str) -> str:
    """去 // 与 /* */ 注释，保留换行；不碰字符串字面量。"""
    out = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


_BRACKETS = {"{": "}", "(": ")", "[": "]"}


def match_bracket(text: str, start: int) -> int:
    """text[start] 是开括号；返回配对的闭括号下标（-1 表示没配上）。"""
    opener = text[start]
    closer = _BRACKETS[opener]
    depth = 0
    i = start
    in_str = False
    n = len(text)
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def split_top(text: str, sep: str = ",") -> List[str]:
    """按顶层分隔符切分，忽略括号/字符串里的分隔符。"""
    out, depth, i, n = [], 0, 0, len(text)
    cur = []
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            cur.append(c)
            if c == "\\" and i + 1 < n:
                cur.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
        elif c in "{([":
            depth += 1
        elif c in "})]":
            depth -= 1
        elif c == sep and depth == 0:
            out.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    out.append("".join(cur))
    return out


_STR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def unescape_cs(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "u" and i + 6 <= len(s):
                try:
                    out.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "'": "'"}
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
                continue
        out.append(c)
        i += 1
    return "".join(out)


def strings_in(text: str) -> List[str]:
    return [unescape_cs(m.group(1)) for m in _STR_RE.finditer(text)]


def find_block(text: str, name: str) -> Optional[str]:
    """找 `name ... = { ... }` 的块内容（含外层大括号）。"""
    for m in re.finditer(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"\b", text):
        eq = text.find("=", m.end())
        if eq < 0:
            continue
        j = text.find("{", eq)
        semi = text.find(";", eq)
        if j < 0 or (semi >= 0 and semi < j):
            continue
        end = match_bracket(text, j)
        if end > 0:
            return text[j:end + 1]
    return None


def parse_string_array(text: str, name: str) -> List[str]:
    blk = find_block(text, name)
    return strings_in(blk) if blk else []


def parse_tuple_rows(text: str, name: str) -> List[List[str]]:
    blk = find_block(text, name)
    if not blk:
        return []
    inner = blk[1:-1]

    def scalar(p: str) -> str:
        p = p.strip()
        if re.fullmatch(r'"(?:[^"\\]|\\.)*"', p):
            return unescape_cs(p[1:-1])
        return p

    rows = []
    for group in split_top(inner):
        g = group.strip()
        if not g:
            continue
        if g.startswith("(") and g.endswith(")"):
            g = g[1:-1]
        rows.append([scalar(p) for p in split_top(g)])
    return rows


def parse_int_strarray_dict(text: str, name: str) -> Dict[int, List[str]]:
    blk = find_block(text, name)
    if not blk:
        return {}
    out: Dict[int, List[str]] = {}
    for group in split_top(blk[1:-1]):
        g = group.strip()
        if not g.startswith("{"):
            continue
        parts = split_top(g[1:-1])
        num = None
        sels: List[str] = []
        for p in parts:
            m = re.match(r"^\s*(-?\d+)\s*$", p)
            if m:
                num = int(m.group(1))
            else:
                sels = strings_in(p)
        if num is not None:
            out[num] = sels
    return out


def parse_str_str_dict(text: str, name: str) -> Dict[str, str]:
    blk = find_block(text, name)
    if not blk:
        return {}
    out: Dict[str, str] = {}
    for group in split_top(blk[1:-1]):
        g = group.strip().lstrip("{").rstrip("}")
        strs = strings_in(g)
        if len(strs) >= 2:
            out[strs[0]] = strs[1]
    return out


def parse_hashset(text: str, name: str) -> Set[str]:
    blk = find_block(text, name)
    return set(strings_in(blk)) if blk else set()


def parse_calls(text: str, fname: str) -> List[List[str]]:
    out = []
    for m in re.finditer(r"(?<![A-Za-z0-9_])" + re.escape(fname) + r"\s*\(", text):
        i = text.find("(", m.start())
        end = match_bracket(text, i)
        if end > 0:
            out.append([p.strip() for p in split_top(text[i + 1:end])])
    return out


# ===========================================================================
# 场景渲染器扫描（补盘点只导 SMR 的缺口：MeshRenderer 件如 PixelBoot）
# ===========================================================================
def _go_path(idx, go_fid: int) -> str:
    names = []
    fid = go_fid
    seen = set()
    while fid and fid not in seen:
        seen.add(fid)
        gd = idx.by_fid.get(fid)
        if gd is None or gd.class_id != 1:
            break
        nm = gd.get("m_Name")
        if nm is None:
            corr = gd.get("m_CorrespondingSourceObject") or {}
            nm = "<stripped#%s>" % corr.get("fileID", "?")
        names.append(nm)
        tf_fid = idx.go_transform(fid)
        if tf_fid is None:
            break
        tf = idx.by_fid.get(tf_fid)
        if tf is None:
            break
        father = (tf.get("m_Father") or {}).get("fileID", 0) or 0
        if not father:
            break
        parent_tf = idx.by_fid.get(father)
        if parent_tf is None:
            break
        fid = (parent_tf.get("m_GameObject") or {}).get("fileID", 0) or 0
    return "/".join(reversed(names))


def scan_scene_renderers(scene_path: str, cache: "unity_yaml.YamlCache") -> List[dict]:
    if not scene_path or not os.path.exists(scene_path):
        return []
    try:
        idx = unity_yaml.DocIndex(cache.load(scene_path))
    except Exception:
        return []
    out = []
    for cls, typ in ((137, "SkinnedMeshRenderer"), (23, "MeshRenderer")):
        for d in idx.all(cls):
            go_fid = (d.get("m_GameObject") or {}).get("fileID", 0)
            path = _go_path(idx, go_fid)
            if not path or path.startswith("<stripped"):
                continue
            out.append({"path": path, "name": leaf(path), "type": typ,
                        "active_self": True, "closed": None, "covers": []})
    return out


# ===========================================================================
# 工程数据载入
# ===========================================================================
class Ctx:
    def __init__(self, project: str, profile_path: Optional[str] = None,
                 inventory_path: Optional[str] = None, params_path: Optional[str] = None,
                 scene: Optional[str] = None, menu_gen: Optional[str] = None):
        self.project = os.path.abspath(project)
        self.project_id = os.path.basename(self.project.rstrip("/"))
        self.profile_path = profile_path
        self.inventory_path = inventory_path
        self.params_path = params_path
        self.scene = os.path.abspath(scene) if scene else None
        self.menu_gen = os.path.abspath(menu_gen) if menu_gen else None
        self.profile: dict = {}
        self.params: dict = {}
        self.inventory: dict = {}
        self.avatar_name = ""
        self.body = "Body"
        self.renderers: List[dict] = []
        self.path2r: Dict[str, dict] = {}
        self.menu = {}          # 解析后的生成器表
        self.gen_src = ""
        self._load()

    # -- 路径发现 --------------------------------------------------------
    def _find(self, *rels: str) -> Optional[str]:
        for r in rels:
            p = os.path.join(self.project, r)
            if os.path.exists(p):
                return p
        return None

    def _load(self):
        # profile
        if not self.profile_path:
            cands = sorted(glob.glob(os.path.join(WORKSPACE, "开发工具", "素体档案", "*.yaml")))
            for c in cands:
                try:
                    with open(c, encoding="utf-8") as f:
                        self.profile = yaml.safe_load(f) or {}
                except Exception:
                    continue
                if self.profile.get("mesh"):
                    self.profile_path = c
                    break
        if self.profile_path:
            with open(self.profile_path, encoding="utf-8") as f:
                self.profile = yaml.safe_load(f) or {}
        # inventory
        if not self.inventory_path:
            self.inventory_path = self._find("_感知/out/inventory.json",
                                             "_感知/inventory.json")
        if self.inventory_path and os.path.exists(self.inventory_path):
            with open(self.inventory_path, encoding="utf-8") as f:
                self.inventory = json.load(f)
            avs = self.inventory.get("avatars") or []
            if avs:
                self.avatar_name = avs[0].get("name") or ""
                self.body = avs[0].get("body_path") or self.body
                self.renderers = avs[0].get("renderers") or []
                self.path2r = {r["path"]: r for r in self.renderers}
        if self.profile.get("mesh"):
            self.body = self.profile["mesh"]
        # params
        if not self.params_path:
            t4 = os.path.join(WORKSPACE, "_长程任务_20260918", "审查产出")
            cands = sorted(glob.glob(os.path.join(t4, self.project_id + "*", "t4_menu", "params.json")))
            if cands:
                self.params_path = cands[0]
        if self.params_path and os.path.exists(self.params_path):
            with open(self.params_path, encoding="utf-8") as f:
                self.params = json.load(f)
            if not self.avatar_name:
                self.avatar_name = self.params.get("avatar") or ""
        # menu-gen
        if not self.menu_gen:
            self.menu_gen = self._find("Assets/Editor/AvatarGen/MenuGenA2.cs")
            if not self.menu_gen:
                hits = sorted(glob.glob(os.path.join(
                    self.project, "Assets", "Editor", "**", "MenuGen*.cs"), recursive=True))
                if hits:
                    self.menu_gen = hits[0]
        if self.menu_gen:
            with open(self.menu_gen, encoding="utf-8") as f:
                self.gen_src = strip_cs_comments(f.read())
        # scene
        if not self.scene:
            try:
                scan = writers_static.ProjectScan(self.project)
                self.scene = scan.scene_path
            except Exception:
                pass
        # 补盘点缺口：场景里的 MeshRenderer（盘点只导 SMR）
        if self.scene:
            try:
                for r in scan_scene_renderers(self.scene, unity_yaml.YamlCache()):
                    if r["path"] not in self.path2r:
                        self.renderers.append(r)
                        self.path2r[r["path"]] = r
            except Exception:
                pass
        self.menu = parse_menu_gen(self.gen_src, self.params)

    # -- 工具 ------------------------------------------------------------
    def params_by_name(self) -> Dict[str, dict]:
        return {p["name"]: p for p in self.params.get("parameters") or []}

    def default_of(self, param: str, fallback=0):
        p = self.params_by_name().get(param)
        if p and p.get("default_value") is not None:
            return p["default_value"]
        return fallback


# ===========================================================================
# MenuGenA2 表解析
# ===========================================================================
def parse_menu_gen(src: str, params: dict) -> dict:
    m: dict = {}
    m["outfits"] = parse_string_array(src, "OUTFITS")
    m["outfit_labels"] = parse_string_array(src, "OUTFIT_LABELS")
    m["outfit_hide"] = parse_int_strarray_dict(src, "OUTFIT_HIDE")
    m["hairs"] = parse_string_array(src, "HAIRS")
    m["hair_labels"] = parse_string_array(src, "HAIR_LABELS")
    m["eartails"] = parse_string_array(src, "EARTAILS")
    m["eartail_labels"] = parse_string_array(src, "EARTAIL_LABELS")
    m["halos"] = parse_string_array(src, "HALOS")
    m["headdresses"] = parse_string_array(src, "HEADDRESSES")
    m["onoff_labels"] = parse_string_array(src, "ONOFF_LABELS3")
    m["vendor_clip"] = parse_str_str_dict(src, "VENDOR_CLIP")
    m["vendor_alt"] = parse_hashset(src, "VENDOR_ALT")
    m["chest_parts"] = parse_string_array(src, "CHEST_PARTS")
    m["footnail_sel"] = parse_string_array(src, "FOOTNAIL_SEL")
    m["ear_sel"] = parse_string_array(src, "EAR_SEL")
    m["nipple_keys"] = parse_string_array(src, "SK_NIPPLE")
    m["part_shapes"] = parse_tuple_rows(src, "PART_SHAPES")
    m["parts"] = parse_tuple_rows(src, "PARTS")
    m["accparts"] = parse_tuple_rows(src, "ACCPARTS")
    m["headparts"] = parse_tuple_rows(src, "HEADPARTS")
    # 常量
    consts: Dict[str, object] = {}
    for mm in re.finditer(r"const\s+int\s+(\w+)\s*=\s*(-?\d+)", src):
        consts[mm.group(1)] = int(mm.group(2))
    for arr in ("OUTFITS", "HAIRS", "HEADDRESSES", "BEARS", "EARTAILS", "HALOS"):
        consts[arr] = len(parse_string_array(src, arr))
    m["consts"] = consts
    m["suppress"] = parse_calls(src, "Suppress")
    m["suppress_gated"] = parse_calls(src, "SuppressBoolGated")
    m["show_in_range"] = parse_calls(src, "ShowInRange")
    dials = {}
    for mm in re.finditer(r'Dial\(\s*[^,]+,\s*"([^"]+)"\s*,\s*"([^"]+)"', src):
        dials[mm.group(1)] = mm.group(2)
    m["dial_params"] = dials
    m["outfit_param"] = dials.get("整套", "A2_Outfit")
    return m


def eval_cs_num(expr: str, menu: dict) -> Optional[float]:
    e = expr.strip()
    e = e.replace("(float)", "")
    e = re.sub(r"([0-9]*\.?[0-9]+)f\b", r"\1", e)
    e = re.sub(r"(\w+)\.Length", lambda mm: str(menu["consts"].get(mm.group(1), 0)), e)
    for name, val in menu["consts"].items():
        e = re.sub(r"\b" + re.escape(name) + r"\b", str(val), e)
    try:
        return float(eval(e, {"__builtins__": {}}, {}))  # noqa: S307 - 表达式来自本仓库
    except Exception:
        return None


# ===========================================================================
# 选择器解析 / 部件构建
# ===========================================================================
def leaf(path: str) -> str:
    return path.rstrip("/").split("/")[-1] if path else path


def sanitize(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_]+", "_", name)
    s = s.strip("_")
    return s or "x"


def resolve_selector(sel: str, renderers: List[dict]) -> List[str]:
    """把 MenuGenA2 选择器解析成盘点里的渲染器路径。忽略 vendor:。"""
    out: List[str] = []
    for one in sel.split("|"):
        one = one.strip()
        if not one or ":" not in one:
            continue
        kind, arg = one.split(":", 1)
        if kind == "vendor":
            continue
        base = {
            "outfit": "_Outfit/" + arg, "hair": "_Hair/" + arg,
            "in": "_Outfit/" + arg, "path": arg, "root": arg,
        }.get(kind)
        for r in renderers:
            p = r["path"]
            if kind == "name":
                if any(seg.startswith(arg) for seg in p.split("/")):
                    out.append(p)
                continue
            if kind == "acc":
                b = "_Acc/" + arg
                if p == b or p.startswith(b + "/") or ("/" + arg + "/") in ("/" + p + "/"):
                    out.append(p)
                continue
            if base and (p == base or p.startswith(base + "/")):
                out.append(p)
    # 去重保序
    seen = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def outfit_root_of(path: str) -> str:
    for top in path.split("/"):
        if top.startswith("Outfit_"):
            return "_Outfit/" + top
    return ""


def selector_id(sel: str, outfit_labels_of_root) -> str:
    """给选择器起一个稳定 id（尽量贴近人写惯例）。"""
    one = sel.split("|")[0]
    if ":" not in one:
        return sanitize(one)
    kind, arg = one.split(":", 1)
    if kind in ("in", "outfit"):
        root, _, piece = arg.partition("/")
        prefix = outfit_labels_of_root.get("_Outfit/" + root, root)
        prefix = re.sub(r"^Outfit_", "", prefix)
        prefix = re.sub(r"^(MMN|ANEMONE|Kitty|RePoppin).*", r"\1", prefix)
        if not piece:
            return sanitize(prefix)
        piece = re.sub(r"^\([A-Z]\)", "", piece)
        return sanitize(prefix) + "." + sanitize(piece).lower()
    if kind == "root":
        if arg == "Bra":
            return "base.bra"
        if arg == "Pants":
            return "base.panties"
        if arg == "Hair":
            return "hair.default"
        if arg.startswith("ear"):
            return "kaguya.ear"
        if arg.startswith("tail"):
            return "kaguya.tail"
        return "base." + sanitize(arg)
    if kind == "acc":
        return "acc." + sanitize(arg)
    if kind == "name":
        return "acc." + sanitize(arg.rstrip("_"))
    if kind == "hair":
        return "hair." + sanitize(arg)
    return sanitize(arg)


def kind_for(slot: Optional[str], leaf_name: str, path: str) -> str:
    if slot and slot in KIND_BY_SLOT:
        return KIND_BY_SLOT[slot]
    low = (leaf_name or "").lower()
    for hint, kind in KIND_HINTS:
        if hint in low:
            return kind
    if "shirt" in low or "maid" in low or "jersey" in low or "bra" in low:
        return "top"
    if "hood" in low or "cap" in low:
        return "hat"
    if "bag" in low or "cat" in low or "phone" in low or "acc" in low:
        return "acc"
    return "acc"


class Draft:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.parts: List[dict] = []
        self.deps: List[dict] = []
        self._ids: Set[str] = set()
        self.claimed: Set[str] = set()
        self.notes: List[str] = []
        self.skipped: List[str] = []
        self.unresolved: List[str] = []
        self.frag_includes: List[dict] = []
        self.frag_paths: Set[str] = set()
        self.frag_deps: List[dict] = []
        self.frag_parts: List[dict] = []
        self.path2part: Dict[str, str] = {}

    # -- id --------------------------------------------------------------
    def uid(self, base: str) -> str:
        base = base or "x"
        if base not in self._ids:
            self._ids.add(base)
            return base
        i = 2
        while "%s_%d" % (base, i) in self._ids:
            i += 1
        out = "%s_%d" % (base, i)
        self._ids.add(out)
        return out

    # -- fragments -------------------------------------------------------
    def discover_fragments(self):
        frag_dir = os.path.join(WORKSPACE, "开发工具", "素材包说明")
        body = (self.ctx.profile.get("body") or "").strip()
        outfit_roots = set()
        for sel in self.ctx.menu.get("outfits") or []:
            if sel.startswith("outfit:"):
                outfit_roots.add(sel.split(":", 1)[1].split("/")[0])
        for p in self.ctx.path2r:
            r = outfit_root_of(p)
            if r:
                outfit_roots.add(r.split("/")[-1])
        for fp in sorted(glob.glob(os.path.join(frag_dir, "*.decl.yaml"))):
            try:
                with open(fp, encoding="utf-8") as f:
                    frag = yaml.safe_load(f) or {}
            except Exception:
                continue
            pkg = frag.get("package") or {}
            if body and (pkg.get("body") or "") and pkg.get("body") != body:
                continue
            name = pkg.get("name") or os.path.basename(fp).split(".")[0]
            mount = None
            for root in sorted(outfit_roots):
                if name and name.lower() in root.lower():
                    mount = "_Outfit/" + root
                    break
            if not mount:
                continue
            outfit = self.outfit_labels_for_mount(mount)
            self.frag_includes.append({
                "fragment": os.path.relpath(fp, WORKSPACE),
                "mount": mount,
                "as": sanitize(name),
                "outfit": outfit if outfit else None,
            })
            # 片段部件 → mount 后的路径集合 + 片段 dep 签名
            as_ = sanitize(name)
            for part in frag.get("parts") or []:
                pid = as_ + "." + part["id"]
                objs = [mount + "/" + o.get("path", "") for o in part.get("objects") or []]
                self.frag_parts.append({
                    "id": pid,
                    "kind": part.get("kind"),
                    "objects": objs,
                    "mount": mount,
                    # C-K：片段 YAML 的 slot/fit/covers/toggle 也保留，否则按 slot 聚合
                    # 的规则（遮胸件集合等）会漏片段件（ANEMONE.decl.yaml:skirt slot=coat）。
                    # 来源 S9 开发工具/素材包说明/*.decl.yaml。
                    "slot": part.get("slot"),
                    "fit": part.get("fit"),
                    "covers": part.get("covers"),
                    "toggle": part.get("toggle"),
                })
                for op in objs:
                    self.frag_paths.add(op)
                    self.claimed.add(op)          # 主体声明不再重复声明片段的件
                    self.path2part.setdefault(op, pid)
            for dep in frag.get("deps") or []:
                sig = self.frag_dep_sig(dep, as_, frag)
                if sig:
                    self.frag_deps.append({"sig": sig, "id": as_ + "." + dep["id"]})

    def frag_dep_sig(self, dep: dict, as_: str, frag: dict):
        local_ids = {p["id"] for p in (frag.get("parts") or [])}
        when = dep.get("when") or ""
        for pid in local_ids:
            when = re.sub(r"(?<![A-Za-z0-9_.])" + re.escape(pid) + r"(?![A-Za-z0-9_])",
                          as_ + "." + pid, when)
        return (dep.get("kind"), target_sig(dep), when, disp_expect(dep))

    # -- menu ------------------------------------------------------------
    def outfit_labels_for_mount(self, mount: str) -> List[str]:
        """挂载根 → 它服务的整套标签。"""
        menu = self.ctx.menu
        outfits = menu.get("outfits") or []
        labels = menu.get("outfit_labels") or []
        root = mount.split("/")[-1]
        out = []
        for i, sel in enumerate(outfits):
            if not sel.startswith("outfit:"):
                continue
            if sel.split(":", 1)[1].split("/")[0] == root and i < len(labels):
                if labels[i] not in out:
                    out.append(labels[i])
        return out

    # -- parts -----------------------------------------------------------
    def add_part(self, pid_base: str, objects: List[dict], kind: str, fit: str,
                 outfit, slot=None, toggle=None, covers=None, vendor_clip=None,
                 alt_of=None, human=None, source=None, note=None,
                 allow_fragment_override=False):
        objs = []
        seen = set()
        for o in objects:
            p = o.get("path")
            if not p or p in self.claimed or p in seen:
                continue
            seen.add(p)
            objs.append(o)
        if not objs:
            return None
        pid = self.uid(pid_base)
        for o in objs:
            self.claimed.add(o["path"])
            self.path2part[o["path"]] = pid
        part = {"id": pid, "kind": kind, "objects": objs, "fit": fit}
        if outfit:
            part["outfit"] = outfit
        if slot:
            part["slot"] = slot
        elif toggle:
            part["toggle"] = toggle
        if alt_of:
            part["alt_of"] = alt_of
        if covers:
            part["covers"] = covers
        if vendor_clip:
            part["vendor_clip"] = vendor_clip
        if human:
            part["human"] = human
        if source:
            part["source"] = source
        if note:
            part["note"] = note
        self.parts.append(part)
        return part

    def obj(self, path: str) -> dict:
        r = self.ctx.path2r.get(path) or {}
        rt = r.get("type") or ""
        renderer = "smr" if rt == "SkinnedMeshRenderer" else "mesh"
        return {"path": path, "renderer": renderer}

    def covers_of(self, paths: List[str], kind: str) -> Optional[List[str]]:
        cov: List[str] = []
        for p in paths:
            r = self.ctx.path2r.get(p) or {}
            for c in r.get("covers") or []:
                if c and c != "Other" and c not in cov:
                    cov.append(c)
        if not cov:
            cov = list(COVER_BY_KIND.get(kind, []))
        return cov or None

    def fit_of(self, paths: List[str], kind: str) -> str:
        if kind == "shoes":
            for p in paths:
                r = self.ctx.path2r.get(p) or {}
                if r.get("closed"):
                    return "closed"
        return FIT_BY_KIND.get(kind, "none")

    # -- 主体起草 --------------------------------------------------------
    def build(self):
        self.discover_fragments()
        self.build_vendor_parts()
        self.build_selector_parts()
        self.build_outfit_hide_parts()
        self.build_special_parts()
        self.build_deps()

    # 厂商件：VENDOR_CLIP → ON/OFF clip 里被 m_IsActive/m_Enabled 驱动的物体
    def vendor_clip_paths(self):
        """{item: (on_clip_rel, off_clip_rel, [paths_on], [paths_off])}"""
        menu = self.ctx.menu
        out = {}
        anim_dir = os.path.join(self.ctx.project, "Assets", "IKUSIA", "kaguya", "cloth", "Animation")
        for item, stem in (menu.get("vendor_clip") or {}).items():
            on = off = None
            for cand in ("%s ON.anim" % stem, "%s ON 1.anim" % stem):
                p = os.path.join(anim_dir, cand)
                if os.path.exists(p):
                    on = p
                    break
            for cand in ("%s OFF.anim" % stem, "%s OFF 1.anim" % stem):
                p = os.path.join(anim_dir, cand)
                if os.path.exists(p):
                    off = p
                    break
            if not on:
                self.skipped.append("厂商件 %s 找不到 ON clip" % item)
                continue
            on_paths, off_paths = [], []
            try:
                on_doc = unity_yaml.DocIndex(unity_yaml.load_unity_yaml(on)).first(74)
                on_paths = clip_toggle_paths(on_doc)
                if off:
                    off_doc = unity_yaml.DocIndex(unity_yaml.load_unity_yaml(off)).first(74)
                    off_paths = clip_toggle_paths(off_doc)
            except Exception as e:  # noqa: BLE001
                self.skipped.append("厂商件 %s clip 读取失败：%s" % (item, e))
                continue
            out[item] = (os.path.relpath(on, self.ctx.project),
                         os.path.relpath(off, self.ctx.project) if off else None,
                         on_paths, off_paths)
        return out

    def vendor_entry_of(self, item: str):
        """在 PARTS/ACCPARTS/HEADPARTS 里找哪个开关/槽挂了 vendor:<item>。"""
        menu = self.ctx.menu
        for table in ("parts", "accparts", "headparts"):
            for row in menu.get(table) or []:
                if len(row) < 3:
                    continue
                param, label, sel_expr = row[0], row[1], row[2]
                sels = strings_in(sel_expr)
                for s in sels:
                    if s == "vendor:" + item:
                        return table, param, label, sels
        return None

    def slot_or_toggle(self, param: str):
        if param in SLOT_KEYS:
            return SLOT_KEYS[param], None, param
        if param in CONTROL_KEYS:
            return None, CONTROL_KEYS[param], param
        return None, None, param

    def build_vendor_parts(self):
        vc = self.vendor_clip_paths()
        alt_set = set(self.ctx.profile.get("vendor_conventions", {})
                      .get("kaguya_cloth", {}).get("alt_pieces") or [])
        for item, (on_rel, off_rel, on_paths, off_paths) in vc.items():
            entry = self.vendor_entry_of(item)
            param = entry[1] if entry else None
            slot, ctl, _ = self.slot_or_toggle(param) if param else (None, None, None)
            paths = sorted(set(on_paths) | set(off_paths))
            mains, alts = [], []
            for p in paths:
                leafp = leaf(p)
                if leafp in alt_set or p in alt_set:
                    alts.append(p)
                else:
                    mains.append(p)
            outfit = ["素体水手服"]
            kind = kind_for(slot, item, mains[0] if mains else "")
            fit = self.fit_of(mains, kind)
            toggle = {"control": ctl, "shown_at": 1} if ctl else None
            vclip = {"on_clip": on_rel, "off_clip": off_rel or on_rel}
            base_id = "kaguya." + sanitize(item)
            part = self.add_part(base_id, [self.obj(p) for p in mains], kind, fit,
                                 outfit, slot=slot, toggle=toggle,
                                 covers=self.covers_of(mains, kind),
                                 vendor_clip=vclip,
                                 source=["S1 生成器表 MenuGenA2.cs VENDOR_CLIP",
                                         "S3 厂商 clip %s" % on_rel])
            for ap in alts:
                self.add_part("kaguya." + sanitize(leaf(ap)), [self.obj(ap)], kind,
                              self.fit_of([ap], kind), outfit, slot=None,
                              covers=self.covers_of([ap], kind),
                              alt_of=(part["id"] if part else base_id),
                              human="备选件（厂商说明书要求二选一；何时启用未核）",
                              source=["S3 厂商 clip %s（同时写 m_Enabled）" % on_rel,
                                      "S9 素体档案 vendor_conventions.alt_pieces"],
                              note="S4/alt_pieces：厂商 clip 会把互为备选的两件一起开，"
                                   "默认 m_IsActive=0，不进主组")

    def base_outfit(self, sel: str) -> Optional[List[str]]:
        menu = self.ctx.menu
        labels = menu.get("outfit_labels") or []
        hidden = set()
        for si, sels in (menu.get("outfit_hide") or {}).items():
            if sel in sels:
                hidden.add(si)
        out = [labels[i] for i in range(len(labels)) if i not in hidden]
        return out or None

    def build_selector_parts(self):
        menu = self.ctx.menu
        outfits = menu.get("outfits") or []
        labels = menu.get("outfit_labels") or []
        root2labels: Dict[str, List[str]] = {}
        for i, sel in enumerate(outfits):
            if sel.startswith("outfit:") and i < len(labels):
                r = sel.split(":", 1)[1].split("/")[0]
                root2labels.setdefault("_Outfit/" + r, [])
                if labels[i] not in root2labels["_Outfit/" + r]:
                    root2labels["_Outfit/" + r].append(labels[i])
        for table in ("parts", "accparts", "headparts"):
            for row in menu.get(table) or []:
                if len(row) < 3:
                    continue
                param, label, sel_expr = row[0], row[1], row[2]
                sels = strings_in(sel_expr)
                slot, ctl, _ = self.slot_or_toggle(param)
                for s in sels:
                    if s.startswith("vendor:"):
                        continue
                    paths = resolve_selector(s, self.ctx.renderers)
                    if not paths:
                        self.unresolved.append("%s %s → 无渲染器" % (param, s))
                        continue
                    root = outfit_root_of(paths[0])
                    outfit = root2labels.get(root) or None
                    if not outfit and s.startswith("root:"):
                        outfit = self.base_outfit(s)
                    pid = selector_id(s, {k: (v[0] if v else "") for k, v in root2labels.items()})
                    leafn = leaf(s.split(":", 1)[1])
                    kind = kind_for(slot, leafn, paths[0])
                    fit = self.fit_of(paths, kind)
                    toggle = {"control": ctl, "shown_at": 1} if (ctl and not slot) else None
                    human = None
                    if kind in ("shoes",):
                        human = "是否包趾/是否设计开口未核（需对照厂商展示图）"
                    self.add_part(pid, [self.obj(p) for p in paths], kind, fit, outfit,
                                  slot=slot, toggle=toggle,
                                  covers=self.covers_of(paths, kind),
                                  human=human,
                                  source=["S1 生成器表 MenuGenA2.cs:%s(%s=%s)" % (table.upper(), param, label),
                                          "S2 盘点 inventory.json 渲染器路径"])

    def build_outfit_hide_parts(self):
        menu = self.ctx.menu
        outfits = menu.get("outfits") or []
        labels = menu.get("outfit_labels") or []
        for slot_i, sels in (menu.get("outfit_hide") or {}).items():
            slot_labels = []
            if 0 <= slot_i < len(labels):
                slot_labels = [labels[slot_i]]
            # 该档隐藏的「另一件」属于相邻档（Kitty/RePoppin 的变体二选一）
            alt_labels = []
            for j, lab in enumerate(labels):
                if j != slot_i and j < len(outfits) and slot_i < len(outfits) \
                        and outfits[j] == outfits[slot_i]:
                    alt_labels.append(lab)
            for s in sels:
                if s.startswith(("root:", "acc:", "name:")):
                    continue  # 素体件/配饰由别处管
                paths = resolve_selector(s, self.ctx.renderers)
                if not paths:
                    continue
                root = outfit_root_of(paths[0])
                outfit = slot_labels
                low = leaf(paths[0]).lower()
                if "shirt" in low or "hood" in low:
                    outfit = alt_labels or slot_labels
                pid = selector_id(s, {})
                leafn = leaf(s.split(":", 1)[1])
                kind = kind_for(None, leafn, paths[0])
                self.add_part(pid, [self.obj(p) for p in paths], kind,
                              self.fit_of(paths, kind), outfit or None,
                              covers=self.covers_of(paths, kind),
                              source=["S1 生成器表 MenuGenA2.cs OUTFIT_HIDE 档 %d" % slot_i])

    def build_special_parts(self):
        menu = self.ctx.menu
        # 发型
        hairs = menu.get("hairs") or []
        hlabels = menu.get("hair_labels") or []
        for i, sel in enumerate(hairs):
            paths = resolve_selector(sel, self.ctx.renderers)
            if not paths:
                continue
            lab = hlabels[i] if i < len(hlabels) else str(i)
            hid = "hair.default" if i == 0 else "hair." + sanitize(lab)
            self.add_part(hid, [self.obj(p) for p in paths],
                          "hair", "none", None,
                          toggle={"control": "hair", "shown_at": lab},
                          source=["S1 生成器表 MenuGenA2.cs HAIRS"])
        # 耳尾（物体 + 参数驱动尾数）
        eartails = menu.get("eartails") or []
        elabels = menu.get("eartail_labels") or []
        eartail_paths: List[str] = []
        for i, sel in enumerate(eartails):
            if not sel:
                continue
            for p in resolve_selector(sel, self.ctx.renderers):
                if p not in eartail_paths:
                    eartail_paths.append(p)
        # 原生耳/尾（由 EAR_SEL/EARTAILS 的 root: 选择器给出）
        for i, sel in enumerate(eartails):
            for one in sel.split("|"):
                if one.startswith("root:ear"):
                    paths = resolve_selector(one, self.ctx.renderers)
                    self.add_part("kaguya.ear", [self.obj(p) for p in paths], "body_part",
                                  "none", None,
                                  toggle={"control": "eartail",
                                          "shown_at": [x for x in (elabels[0:2] or ["原始九尾"])]},
                                  source=["S1 生成器表 MenuGenA2.cs EARTAILS/EAR_SEL"])
                if one.startswith("root:tail"):
                    paths = resolve_selector(one, self.ctx.renderers)
                    self.add_part("kaguya.tail", [self.obj(p) for p in paths], "body_part",
                                  "none", None,
                                  toggle={"control": "eartail",
                                          "shown_at": [x for x in (elabels[0:2] or ["原始九尾"])]},
                                  source=["S1 生成器表 MenuGenA2.cs EARTAILS"])
            break
        newtail_paths = [p for p in eartail_paths if "_Acc/" in p]
        if newtail_paths:
            self.add_part("acc.eartail", [self.obj(p) for p in newtail_paths], "acc", "none",
                          None,
                          toggle={"control": "eartail",
                                  "shown_at": [elabels[2]] if len(elabels) > 2 else ["新耳尾"]},
                          source=["S1 生成器表 MenuGenA2.cs EARTAILS 新耳尾档"])
        # 光环 / 头饰
        halos = menu.get("halos") or []
        for i, sel in enumerate(halos):
            if not sel:
                continue
            paths = resolve_selector(sel, self.ctx.renderers)
            lab = (menu.get("onoff_labels") or ["关", "金", "银"])[i] if i < 3 else str(i)
            self.add_part("acc.halo", [self.obj(p) for p in paths], "acc", "none", None,
                          toggle={"control": "halo", "shown_at": lab},
                          source=["S1 生成器表 MenuGenA2.cs HALOS"])
        heads = menu.get("headdresses") or []
        for i, sel in enumerate(heads):
            if not sel:
                continue
            paths = resolve_selector(sel, self.ctx.renderers)
            lab = (menu.get("onoff_labels") or ["关", "金", "银"])[i] if i < 3 else str(i)
            self.add_part("acc.headdress", [self.obj(p) for p in paths], "acc", "none", None,
                          toggle={"control": "head", "shown_at": lab},
                          source=["S1 生成器表 MenuGenA2.cs HEADDRESSES"])
        # 脚甲
        for sel in menu.get("footnail_sel") or []:
            paths = resolve_selector(sel, self.ctx.renderers)
            self.add_part("acc.foot_nail", [self.obj(p) for p in paths], "acc", "none",
                          None,
                          source=["S1 生成器表 MenuGenA2.cs FOOTNAIL_SEL"])

    # -- deps ------------------------------------------------------------
    def build_deps(self):
        self.build_d1_d2_d3_d4a_d7_from_clips()
        self.build_ma_deps()
        self.build_part_shape_deps()
        self.build_d6_deps()
        self.dedup_exact_deps()
        self.resolve_else_conflicts()

    def dedup_exact_deps(self):
        """C-K：同一 (kind, 目标, when, expect, else) 的重复条目合一。

        来源：多个厂商 clip / 多个同值写者写同一个键（如 MMN Socks 与 Shoes 各写
        Foot_heel_OFF=100 且当件同名时），草案会平铺出内容完全相同的两条。语义重复，
        只保留第一条。when 不同的**不合并**（留给严格口径的「析取覆盖」判等价）。
        """
        seen: Dict[Tuple, str] = {}
        out: List[dict] = []
        for dep in self.deps:
            sig = (dep.get("kind"), target_sig(dep),
                   norm_when_clauses(dep.get("when")),
                   cmp_expect(dep.get("expect")),
                   json.dumps(dep.get("else"), ensure_ascii=False, sort_keys=True))
            if sig in seen:
                self.skipped.append("重复条目合一：%s ← %s" % (seen[sig], dep["id"]))
                continue
            seen[sig] = dep["id"]
            out.append(dep)
        self.deps = out

    def resolve_else_conflicts(self):
        """SEM-22：同一 (mesh,key) 有 ≥2 个自动写者时，任一条目断言的基线 else
        都可能被另一写者的 when 区覆盖。例：kaguya.sailor 的 `else: value=0` 与
        kaguya.outer 的 `when: value=100` 在「outer 可见、sailor 不可见」状态互斥。
        生成器无法证明两写者互斥，故把这类数值 else 降为 dont_care（when 区取值
        保留，真正的 when 区互相矛盾仍由 decl_validate SEM-22 报出）。
        """
        groups: Dict[Tuple[str, ...], List[dict]] = {}
        for dep in self.deps:
            sig = target_sig(dep)
            if sig:
                groups.setdefault(sig, []).append(dep)
        for sig, deps in groups.items():
            if len(deps) < 2:
                continue
            for dep in deps:
                if dep.get("else") not in (None, "dont_care"):
                    dep["else"] = "dont_care"
                    self.skipped.append(
                        "SEM-22 else 降为 dont_care：%s（%s 共 %d 个写者）"
                        % (dep["id"], " ".join(sig), len(deps)))

    def _part_by_path(self, path: str) -> Optional[str]:
        return self.path2part.get(path)

    def _objects_of(self, pid: str) -> List[str]:
        for p in list(self.parts) + list(self.frag_parts):
            if p["id"] == pid:
                return [o["path"] if isinstance(o, dict) else o for o in p.get("objects") or []]
        return []

    def add_dep(self, dep: dict):
        if dep["id"] in self._ids:
            dep = dict(dep)
            dep["id"] = self.uid(dep["id"])
        self._ids.add(dep["id"])
        self.deps.append(dep)

    def frag_override_id(self, kind, target, when, expect):
        sig = (kind, target, when, expect)
        for fd in self.frag_deps:
            if fd["sig"] == sig:
                return fd["id"]
        return None

    def build_d1_d2_d3_d4a_d7_from_clips(self):
        menu = self.ctx.menu
        kc = self.ctx.profile.get("key_classes") or {}
        key_class = {}
        for cls, group in kc.items():
            if isinstance(group, dict):
                for k in group:
                    key_class[k] = cls
        vc = self.vendor_clip_paths()
        body = self.ctx.body
        prof = self.ctx.profile
        for item, (on_rel, off_rel, on_paths, off_paths) in vc.items():
            entry = self.vendor_entry_of(item)
            param = entry[1] if entry else None
            slot, ctl, _ = self.slot_or_toggle(param) if param else (None, None, None)
            part_ids = [self.path2part.get(p) for p in on_paths]
            part_ids = [x for x in part_ids if x]
            if not part_ids:
                continue
            # 用第一个主件（备选件不驱动依赖）
            host_id = part_ids[0]
            host_when = "vis(%s)" % host_id
            on_doc = unity_yaml.DocIndex(unity_yaml.load_unity_yaml(
                os.path.join(self.ctx.project, on_rel))).first(74)
            off_doc = None
            if off_rel:
                off_doc = unity_yaml.DocIndex(unity_yaml.load_unity_yaml(
                    os.path.join(self.ctx.project, off_rel))).first(74)
            on_curves = clip_curves(on_doc)
            off_curves = clip_curves(off_doc) if off_doc else {}
            involved_keys = set()
            for (path, attr), vals in on_curves.items():
                if not attr.startswith("blendShape."):
                    continue
                key = attr[len("blendShape."):]
                onv = vals[0] if vals else None
                offv = (off_curves.get((path, attr)) or [0])[0]
                if onv is None:
                    continue
                if path == body:
                    cls = key_class.get(key, "")
                    if cls == "shrink":
                        kind = "D1"
                    else:
                        kind = "D3" if slot in ("socks", "shoes") else "D1"
                    self.emit_value_dep(kind, host_id, host_when,
                                        {"mesh": body, "key": key}, onv, offv, cls,
                                        on_rel)
                    involved_keys.add(key)
                elif leaf(path).lower() == "hair":
                    tgt_part = self._part_by_path(path)
                    if tgt_part:
                        self.emit_value_dep("D7", host_id, host_when,
                                            {"part": tgt_part, "key": key}, onv, offv,
                                            "", on_rel)
                else:
                    tgt_part = self._part_by_path(path)
                    if tgt_part:
                        # C-K：D4a 让位键也补 key_classes 的 class；厂商拼写 shlink 视为
                        # shrink 别名（Kaguya.yaml key_classes 只收 shrink）。来源 S9 档案。
                        cls4 = key_class.get(key, "")
                        if not cls4 and ("shrink" in key.lower() or "shlink" in key.lower()):
                            cls4 = "shrink"
                        self.emit_value_dep("D4a", host_id, host_when,
                                            {"part": tgt_part, "key": key}, onv, offv,
                                            cls4, on_rel, cases_for_inner=True)
                        involved_keys.add(key)
            # 鞋/袜：厂商 clip 不写任何身体脚型键 → D2 not_written（厂商惯例）
            if slot in ("shoes", "socks") and not any(
                    k.startswith("Foot_") or k.startswith("foot_") for k in involved_keys):
                self.emit_d2_not_written(item, host_id, host_when, kind_for(slot, item, ""), on_rel)

    def emit_value_dep(self, kind, host_id, when, target, onv, offv, cls, clip_rel,
                       cases_for_inner=False):
        key_name = target.get("key") or target.get("part")
        base_id = "%s.%s" % (kind.lower(), sanitize(host_id))
        dep = {
            "id": base_id,
            "kind": kind,
            "when": when,
            "target": target,
            "expect": {"value": float(onv)},
            "else": {"value": float(offv)},
            "writer": "vendor_clip",
            "source": ["S3 厂商 clip %s" % clip_rel],
            "confidence": {"writer": "high", "correct": "unknown"},
            "note": "厂商写者：对错未经 S4 人判（correct: unknown）",
        }
        if cls:
            dep["expect"]["class"] = cls
        ov = self.frag_override_id(kind, target_sig(dep), when, disp_expect(dep))
        if ov:
            dep["id"] = ov
        self.add_dep(dep)

    def emit_d2_not_written(self, item, host_id, when, kind, clip_rel):
        dep = {
            "id": "d2.%s" % sanitize(host_id),
            "kind": "D2",
            "when": when,
            "target": {"mesh": self.ctx.body,
                       "keys": ["Foot_heel_OFF_____足_ヒールオフ",
                                "Foot_Hiheel_____足_ハイヒール"]},
            "expect": {"not_written": True},
            "else": "dont_care",
            "writer": "unknown",
            "source": ["S3 厂商 clip %s（只写 m_IsActive，不写身体键）" % clip_rel],
            "confidence": {"writer": "mid", "correct": "unknown"},
            "note": "厂商鞋袜不带脚型键；此处只锁「不该写脚型键」",
        }
        self.add_dep(dep)

    def build_ma_deps(self):
        """S2：MA ShapeChanger/BlendSync/ObjectToggle → 依赖。

        宿主名解析：场景/prefab 里 stripped GameObject 的 m_CorrespondingSourceObject
        若指向文本 prefab 可读出 m_Name；指向 .fbx（二进制）读不出，这时用 S9 档案的
        vendor_conventions（sc_on / *_sc_ours_legacy）按「目标键」反查宿主件。
        """
        try:
            scan = writers_static.ProjectScan(self.ctx.project, scene=self.ctx.scene)
            writers = list(writers_static.scan_ma_in_file(scan, scan.scene_path, is_scene=True))
            for p in scan.reachable_prefabs:
                writers += writers_static.scan_ma_in_file(scan, p, is_scene=False)
        except Exception as e:  # noqa: BLE001
            self.skipped.append("MA 扫描失败：%s" % e)
            return
        kc = self.ctx.profile.get("key_classes") or {}
        key_class = {}
        for cls, group in kc.items():
            if isinstance(group, dict):
                for k in group:
                    key_class[k] = cls
        for w in writers:
            mesh = w.get("mesh") or ""
            key = w.get("key") or ""
            if not key or mesh != self.ctx.body:
                continue
            host_id = self.ma_host_part(key, w.get("source") or "", w.get("where") or "")
            if not host_id:
                self.skipped.append("MA 写者目标键 %r 的宿主无法对应部件（%s）"
                                    % (key, w.get("where")))
                continue
            when = "vis(%s)" % host_id
            if w.get("type") == "Delete":
                dep = {
                    "id": "%s.%s_%s" % ("d3" if is_foot_key(key) else "d1", sanitize(host_id), sanitize(key)),
                    "kind": "D3" if is_foot_key(key) else "D1",
                    "when": when,
                    "target": {"mesh": mesh, "keys": [key]},
                    "expect": {"deleted": {"region": region_for_key(key), "min_ratio": 0.8}},
                    "else": "dont_care",
                    "writer": w.get("source") or "vendor_sc",
                    "source": ["S2 %s" % w.get("where", "")],
                    "confidence": {"writer": "high", "correct": "unknown"},
                    "note": "厂商 SC Delete；min_ratio 0.8 待几何标定",
                }
                final = self._merge_delete_dep(dep)
                ov = self.frag_override_id(final["kind"], target_sig(final), final["when"],
                                           disp_expect(final))
                if ov:
                    final["id"] = ov
                continue
            cls = key_class.get(key, "")
            kind = "D3" if (cls == "pose" or is_foot_key(key)) else \
                ("D1" if cls == "shrink" else "D3")
            expect = {"value": float(w.get("value") if w.get("value") is not None else 0)}
            if cls:
                expect["class"] = cls
            dep = {
                "id": "%s.%s_%s" % ("d3" if is_foot_key(key) else "d1", sanitize(host_id), sanitize(key)),
                "kind": kind,
                "when": when,
                "target": {"mesh": mesh, "key": key},
                "expect": expect,
                "else": "dont_care",
                "writer": w.get("source") or "vendor_sc",
                "source": ["S2 %s" % w.get("where", "")],
                "confidence": {"writer": "high", "correct": "unknown"},
                "note": "厂商 SC Set；对错未经 S4 人判（correct: unknown）",
            }
            ov = self.frag_override_id(kind, target_sig(dep), when, disp_expect(dep))
            if ov:
                dep["id"] = ov
            self.add_dep(dep)

    # -- MA 宿主映射 ----------------------------------------------------
    def _frag_by_name(self) -> Dict[str, dict]:
        out = {}
        for inc in self.frag_includes:
            out[inc["as"]] = inc
        return out

    def detect_package(self, where: str) -> Optional[str]:
        path = where.split(":")[0] if where else ""
        npath = re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]+", "", path.lower())
        stop = re.sub(r"[^0-9a-z]+", "", self.ctx.project_id.lower())
        for inc in self.frag_includes:
            fragp = os.path.join(WORKSPACE, inc["fragment"])
            try:
                with open(fragp, encoding="utf-8") as f:
                    frag = yaml.safe_load(f) or {}
            except Exception:
                continue
            src = ((frag.get("package") or {}).get("source") or "")
            toks = {inc["as"]}
            # 源 zip 的文件名与父目录名（去掉工程目录名本身的 token，防止整个工程都命中）
            parts = [x for x in src.replace("\\", "/").split("/") if x]
            for chunk in parts[-2:]:
                chunk = re.sub(r"\.(zip|rar|7z)$", "", chunk, flags=re.I)
                toks.update(norm_tokens(chunk))
            for t in toks:
                nt = re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]+", "", t.lower())
                if len(nt) < 4 or nt in stop:
                    continue
                if nt in npath:
                    return inc["as"]
        return None

    def _conv_hint(self, conv: dict, key: str, source: str) -> Optional[str]:
        hints: List[Tuple[str, bool]] = []  # (host, is_ours)

        def split_sub(sub: str) -> str:
            h = re.split(r"_sc(?:_|$)", sub)[0]
            return h or sub

        sc = conv.get("sc_on")
        if isinstance(sc, dict):
            for host, ks in sc.items():
                if key_matches(str(ks), key):
                    hints.append((host, "ours" in str(host).lower()))
        for sub, val in conv.items():
            if sub == "sc_on" or not isinstance(val, str):
                continue
            if key_matches(val, key):
                hints.append((split_sub(sub), "ours" in sub.lower() or "legacy" in sub.lower()))
        if not hints:
            return None
        ours = source == "ours_legacy"
        prefer = [h for h in hints if h[1] == ours]
        return (prefer or hints)[0][0]

    def ma_host_part(self, key: str, source: str, where: str) -> Optional[str]:
        conv = self.ctx.profile.get("vendor_conventions") or {}
        pkgs = []
        det = self.detect_package(where)
        if det:
            pkgs.append(det)
        for name in conv:
            if name not in pkgs:
                pkgs.append(name)
        for pkg in pkgs:
            c = conv.get(pkg)
            if not isinstance(c, dict):
                continue
            host = self._conv_hint(c, key, source)
            if not host:
                continue
            pid = self._part_in_mount(pkg, host)
            if pid:
                return pid
        # 兜底：按键区域 + 来源在全部部件里挑
        return self._part_by_region(key, source, det)

    def _part_in_mount(self, pkg: str, host: str) -> Optional[str]:
        inc = self._frag_by_name().get(pkg)
        mount = inc["mount"] if inc else ""
        h = host.lower().rstrip("s")
        pool = list(self.parts) + list(self.frag_parts)
        best = None
        for p in pool:
            for o in p.get("objects") or []:
                path = o["path"] if isinstance(o, dict) else o
                if mount and not path.startswith(mount + "/"):
                    continue
                lf = leaf(path).lower()
                if lf == host.lower() or lf.rstrip("s") == h or host.lower() in lf:
                    return p["id"]
                if best is None and (lf.rstrip("s") == h):
                    best = p["id"]
        return best

    def _part_by_region(self, key: str, source: str, pkg: Optional[str] = None) -> Optional[str]:
        if is_foot_key(key):
            kinds = ["socks", "shoes"] if source != "ours_legacy" else ["shoes", "socks"]
        elif any(s in key.lower() for s in ("spine", "腰")):
            kinds = ["bottom", "underwear"]
        else:
            kinds = ["outer", "top"]
        inc = self._frag_by_name().get(pkg) if pkg else None
        mount = inc["mount"] if inc else ""
        pool = list(self.parts) + list(self.frag_parts)
        for kind in kinds:
            for p in pool:
                if p.get("kind") != kind:
                    continue
                objs = [o["path"] if isinstance(o, dict) else o for o in p.get("objects") or []]
                if mount and not any(o.startswith(mount + "/") for o in objs):
                    continue
                return p["id"]
        return None

    def _merge_delete_dep(self, dep):
        tgt_mesh = dep["target"]["mesh"]
        for existing in self.deps:
            if existing.get("kind") != dep["kind"] or existing.get("when") != dep["when"]:
                continue
            if existing.get("target", {}).get("mesh") != tgt_mesh:
                continue
            if "deleted" not in (existing.get("expect") or {}):
                continue
            ek = existing["target"].get("keys") or []
            nk = dep["target"].get("keys") or []
            merged = list(dict.fromkeys(ek + nk))
            merged.sort()
            existing["target"] = {"mesh": tgt_mesh, "keys": merged}
            return existing
        self.add_dep(dep)
        return dep

    def build_part_shape_deps(self):
        menu = self.ctx.menu
        for row in menu.get("part_shapes") or []:
            if len(row) < 5:
                continue
            param, sel, key, on, off = row[0], row[1], row[2], row[3], row[4]
            paths = resolve_selector(sel, self.ctx.renderers)
            host_id = None
            for p in paths:
                host_id = self._part_by_path(p)
                if host_id:
                    break
            owner = self._part_by_path(paths[0]) if paths else None
            # 让位键写在「被让位的内层件」上；宿主＝该内层件
            inner = None
            for one in sel.split("|"):
                if one.startswith("in:"):
                    rp = "_Outfit/" + one.split(":", 1)[1]
                    inner = self._part_by_path(rp)
            inner = inner or owner
            # 触发者＝与内层件同一整套、同 param 槽的外套件（PART_SHAPES 的 param 是 A2_Coat）
            slot, c, _ = self.slot_or_toggle(param)
            trigger = None
            inner_root = ""
            for o in (self._objects_of(inner) if inner else []):
                inner_root = outfit_root_of(o)
                if inner_root:
                    break
            for p in self.parts:
                if not slot or p.get("slot") != slot:
                    continue
                roots = {outfit_root_of(o["path"]) for o in p.get("objects") or []}
                if inner_root and inner_root not in roots:
                    continue
                leafs = " ".join(leaf(o["path"]).lower() for o in p.get("objects") or [])
                score = 2 if any(w in leafs for w in ("parker", "jacket", "coat", "outer")) else 1
                if trigger is None or score > trigger[1]:
                    trigger = (p["id"], score)
            if trigger:
                trigger = trigger[0]
            if not trigger and slot:
                for p in self.parts:
                    if p.get("slot") == slot:
                        trigger = p["id"]
                        break
            if not inner or not trigger:
                self.skipped.append("PART_SHAPES %s 找不到宿主/触发件" % param)
                continue
            try:
                onv = float(on.replace("f", "")) if isinstance(on, str) else float(on)
                offv = float(off.replace("f", "")) if isinstance(off, str) else float(off)
            except ValueError:
                onv, offv = 100.0, 0.0
            dep = {
                "id": "d4a.%s_%s" % (sanitize(inner), sanitize(key)),
                "kind": "D4a",
                "when": "vis(%s)" % trigger,
                "target": {"part": inner, "key": key},
                "expect": {"value": onv},
                "else": {"value": offv},
                "writer": "gen",
                "source": ["S1 生成器表 MenuGenA2.cs PART_SHAPES"],
                "confidence": {"writer": "high", "correct": "high"},
            }
            ov = self.frag_override_id("D4a", target_sig(dep), dep["when"], disp_expect(dep))
            if ov:
                dep["id"] = ov
            self.add_dep(dep)

    # D6 遮挡显隐
    def build_d6_deps(self):
        menu = self.ctx.menu
        rules = []  # (layer, cond, [parts], mode)

        def unq(s: str) -> str:
            s = s.strip()
            if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
                return unescape_cs(s[1:-1])
            return s

        for call in menu.get("suppress") or []:
            if len(call) < 5 or call[0].strip() != "ctrl":
                continue
            layer, param, threshold, sel = unq(call[1]), unq(call[2]), call[3], call[4]
            th = eval_cs_num(threshold, menu)
            if th is None:
                continue
            tgt_ids = self._resolve_sel_to_parts(sel)
            if not tgt_ids:
                continue
            cond = self._param_condition(param, th, 0.0)
            if not cond:
                self.skipped.append("抑制层 %s：参数 %s 不在 menu，未起草" % (layer, param))
                continue
            rules.append((layer, cond, tgt_ids, "hidden"))
        for call in menu.get("show_in_range") or []:
            if len(call) < 6 or call[0].strip() != "ctrl":
                continue
            layer, param, lo, hi, sel = unq(call[1]), unq(call[2]), call[3], call[4], call[5]
            lo_v, hi_v = eval_cs_num(lo, menu), eval_cs_num(hi, menu)
            tgt_ids = self._resolve_sel_to_parts(sel)
            cond = self._outfit_range_condition(param, lo_v, hi_v)
            if cond and tgt_ids:
                rules.append((layer, cond, tgt_ids, "shown"))
        for call in menu.get("suppress_gated") or []:
            if len(call) < 7 or call[0].strip() != "ctrl":
                continue
            layer, bparam, gparam = unq(call[1]), unq(call[2]), unq(call[3])
            lo_v, hi_v = eval_cs_num(call[4], menu), eval_cs_num(call[5], menu)
            tgt_ids = self._resolve_sel_to_parts(call[6])
            bcond = self._param_condition(bparam, 0.0, 0.0, bool_on=True)
            gcond = self._param_condition(gparam, lo_v, hi_v)
            if not bcond or not gcond or not tgt_ids:
                if not bcond or not gcond:
                    self.skipped.append("抑制层 %s：门参数不在 menu，未起草" % layer)
                continue
            rules.append((layer, "%s & %s" % (bcond, gcond), tgt_ids, "hidden"))

        # 同一部件既被 hidden 又被 shown → 合成一条 cases（顺序优先，避免 SEM-22 冲突）
        target_rules: Dict[str, List[Tuple[str, str, str]]] = {}
        for layer, cond, targets, mode in rules:
            for t in targets:
                target_rules.setdefault(t, []).append((cond, mode, layer))
        mixed = {t for t, rs in target_rules.items() if len({m for _, m, _ in rs}) > 1}
        for t in sorted(mixed):
            rs = target_rules[t]
            cases = [{"when": c, "expect": {"shown": True}}
                     for c, m, _ in rs if m == "shown"]
            cases += [{"when": c, "expect": {"hidden": True}}
                      for c, m, _ in rs if m == "hidden"]
            dep = {
                "id": "d6.%s" % sanitize(t),
                "kind": "D6",
                "target": {"part": t},
                "cases": cases,
                "else": {"shown": True},
                "writer": "gen",
                "source": ["S1 生成器表 MenuGenA2.cs 压制层 %s"
                           % "/".join(sorted({l for _, _, l in rs}))],
                "confidence": {"writer": "high", "correct": "mid"},
            }
            self.add_dep(dep)

        # 其余按层合并（多目标一条）
        by_layer: Dict[str, dict] = {}
        for layer, cond, targets, mode in rules:
            rest = [t for t in targets if t not in mixed]
            if not rest:
                continue
            g = by_layer.setdefault(layer, {"layer": layer, "conds": [], "targets": [],
                                            "modes": set()})
            g["conds"].append(cond)
            g["modes"].add(mode)
            for t in rest:
                if t not in g["targets"]:
                    g["targets"].append(t)
        # C-K：同一 (条件集合, 模式) 的不同压制层（如 `耳尾压制` 与 `发夹让位发型` 同为
        # ctl(hair) in {...} 的 hidden）是并列写者，合成一条（目标并集），避免同一断言
        # 平铺成多条。条件不同的层不并。
        merged: Dict[Tuple, dict] = {}
        for layer, g in by_layer.items():
            key = (tuple(sorted(g["conds"])), tuple(sorted(g["modes"])))
            mg = merged.get(key)
            if mg is None:
                mg = {"layer": layer, "conds": list(g["conds"]),
                      "layers": [g["layer"]], "targets": [], "modes": set(g["modes"])}
                merged[key] = mg
            elif g["layer"] not in mg["layers"]:
                mg["layers"].append(g["layer"])
            for t in g["targets"]:
                if t not in mg["targets"]:
                    mg["targets"].append(t)
        for g in merged.values():
            self._emit_d6_group(g)

        # FOOTNAIL_SEL：常驻无开关脚甲，被鞋/袜遮住时收掉（生成器注释
        # MenuGenA2.cs:398「被鞋袜遮住时收掉」、644-649）。hide 判据按**可见件**；
        # Kitty 露出档由上面的 ShowInRange 另起一条（同 target 不同 when，非冲突）。
        fn_ids: List[str] = []
        for sel in menu.get("footnail_sel") or []:
            for p in resolve_selector(sel, self.ctx.renderers):
                pid = self._part_by_path(p)
                if pid and pid not in fn_ids:
                    fn_ids.append(pid)
        for t in fn_ids:
            self.add_dep({
                "id": "d6.%s_hidden" % sanitize(t),
                "kind": "D6",
                "when": "vis(any.shoes) | vis(any.socks)",
                "target": {"part": t},
                "expect": {"hidden": True},
                "else": "dont_care",
                "writer": "gen",
                "source": ["S1 生成器表 MenuGenA2.cs FOOTNAIL_SEL"
                           "（注释：被鞋袜遮住时收掉）"],
                "confidence": {"writer": "high", "correct": "mid"},
                "note": "hide 按可见件判；Kitty 露出档由 ShowInRange 另一条",
            })

        # 胸部 nipple：CHEST_PARTS + SK_NIPPLE
        chest = menu.get("chest_parts") or []
        nipple = menu.get("nipple_keys") or []
        if chest and nipple:
            parts_conds = []
            for p in chest:
                s, c, _ = self.slot_or_toggle(p)
                if s:
                    parts_conds.append("slot(%s)=1" % s)
            if parts_conds:
                dep = {
                    "id": "d6.nipple_chest_covered",
                    "kind": "D6",
                    "when": " | ".join(parts_conds),
                    "target": {"mesh": self.ctx.body, "keys": nipple},
                    "expect": {"value": 0},
                    "else": {"value": 100},
                    "writer": "gen",
                    "source": ["S1 生成器表 MenuGenA2.cs CHEST_PARTS/SK_NIPPLE"],
                    "confidence": {"writer": "high", "correct": "mid"},
                    "human": "遮胸按部位开关判（现生成器）还是按实际可见件判？",
                }
                self.add_dep(dep)

    def _emit_d6_group(self, g):
        mode = "hidden" if "hidden" in g["modes"] else "shown"
        expect = {"hidden": True} if mode == "hidden" else {"shown": True}
        sec = sanitize(g["layer"])
        if sec == "x":
            self._d6n = getattr(self, "_d6n", 0) + 1
            sec = "layer_%d" % self._d6n
        dep = {
            "id": "d6.%s" % sec,
            "kind": "D6",
            "when": None,
            "targets": [{"part": t} for t in g["targets"]],
            "expect": expect,
            "else": "dont_care",
            "writer": "gen",
            "source": ["S1 生成器表 MenuGenA2.cs 压制层 %s"
                       % "/".join(g.get("layers") or [g["layer"]])],
            "confidence": {"writer": "high", "correct": "mid"},
        }
        if len(g["conds"]) == 1 and len(g["targets"]) == 1:
            dep["when"] = g["conds"][0]
            dep.pop("targets")
            dep["target"] = {"part": g["targets"][0]}
        elif len(g["conds"]) == 1:
            dep["when"] = g["conds"][0]
        else:
            # 多个同层条件：一个 when 用 | 合并
            dep["when"] = " | ".join("(%s)" % c for c in g["conds"])
        self.add_dep(dep)

    def _resolve_sel_to_parts(self, sel_expr: str) -> List[str]:
        out = []
        for s in strings_in(sel_expr):
            for p in resolve_selector(s, self.ctx.renderers):
                pid = self._part_by_path(p)
                if pid and pid not in out:
                    out.append(pid)
        # 变量标识符（EAR_SEL / hedSel / headAll / FOOTNAIL_SEL）
        for ident in re.findall(r"(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_]*)\b", sel_expr):
            sels = self._ident_sels(ident)
            for s in sels:
                for p in resolve_selector(s, self.ctx.renderers):
                    pid = self._part_by_path(p)
                    if pid and pid not in out:
                        out.append(pid)
        return out

    def _ident_sels(self, ident: str) -> List[str]:
        menu = self.ctx.menu
        if ident == "FOOTNAIL_SEL":
            return menu.get("footnail_sel") or []
        if ident == "EAR_SEL":
            return menu.get("ear_sel") or []
        if ident == "hedSel":
            for row in menu.get("accparts") or []:
                if row and row[0] == "A2_Hed":
                    return strings_in(row[2])
        if ident == "headAll":
            hed = self._ident_sels("hedSel")
            return hed + (menu.get("ear_sel") or []) + ["acc:Acc_头饰_金"]
        return []

    def _param_condition(self, param: str, lo: float, hi: float,
                         bool_on: bool = False) -> Optional[str]:
        menu = self.ctx.menu
        if param == menu.get("outfit_param"):
            return self._outfit_range_condition(param, lo, hi)
        if param in SLOT_KEYS:
            return "slot(%s)=1" % SLOT_KEYS[param]
        if param in CONTROL_KEYS:
            key = CONTROL_KEYS[param]
            if bool_on:
                return "ctl(%s)=1" % key
            return self._control_range_condition(param, lo, hi)
        return None

    @staticmethod
    def _slots_in_range(n: int, lo: Optional[float], hi: Optional[float]) -> List[int]:
        """档位 i 的 Motion Time＝i/n；压制阈值取档下界，用 eps 消掉 6/7==6/7 的边界。"""
        eps = 1e-6
        idxs = []
        for i in range(n):
            v = i / n
            if lo is not None and lo >= 0 and v < lo - eps:
                continue
            if hi is not None and hi > 0 and not (v < hi - eps):
                continue
            idxs.append(i)
        return idxs

    def _outfit_range_condition(self, param: str, lo: Optional[float],
                                hi: Optional[float]) -> Optional[str]:
        labels = self.ctx.menu.get("outfit_labels") or []
        n = len(labels)
        if not n:
            return None
        idxs = self._slots_in_range(n, lo, hi)
        return outfit_cond([labels[i] for i in idxs])

    def _control_range_condition(self, param: str, lo: Optional[float],
                                 hi: Optional[float]) -> Optional[str]:
        table = {
            "A2_Hair": self.ctx.menu.get("hair_labels") or [],
            "A2_Head": self.ctx.menu.get("onoff_labels") or [],
            "A2_Halo": self.ctx.menu.get("onoff_labels") or [],
        }.get(param) or []
        n = len(table)
        if not n:
            return None
        idxs = self._slots_in_range(n, lo, hi)
        key = CONTROL_KEYS[param]
        if not idxs:
            return None
        return "ctl(%s) in {%s}" % (key, ", ".join(label_tok(table[i]) for i in idxs))


# ===========================================================================
# 小工具（条件、签名、clip）
# ===========================================================================
def clip_curves(clip) -> Dict[Tuple[str, str], List[float]]:
    out: Dict[Tuple[str, str], List[float]] = {}
    if not clip:
        return out
    for fc in clip.get("m_FloatCurves") or []:
        path = fc.get("path") or ""
        attr = fc.get("attribute") or ""
        vals = [k.get("value") for k in (fc.get("curve") or {}).get("m_Curve") or []]
        out[(path, attr)] = vals
    return out


def clip_toggle_paths(clip) -> List[str]:
    paths = []
    for (path, attr) in clip_curves(clip):
        if attr in ("m_IsActive", "m_Enabled"):
            if path not in paths:
                paths.append(path)
    return paths


def is_foot_key(key: str) -> bool:
    k = key.lower()
    return any(s in k for s in ("toe", "foot", "ankle", "つま先", "足", "足首"))


def region_for_key(key: str) -> object:
    k = key.lower()
    if any(s in k for s in ("spine1", "spine2", "腰")):
        return "Spine"
    if any(s in k for s in ("toe", "foot", "ankle", "つま先", "足", "足首")):
        return ["LeftFoot", "RightFoot", "LeftToes", "RightToes"]
    if any(s in k for s in ("hand", "finger", "指")):
        return ["LeftHand", "RightHand"]
    return "Spine"


def norm_tokens(s: str) -> List[str]:
    return [t for t in re.split(r"[^0-9A-Za-z\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+", s) if t]


def key_matches(text: str, key: str) -> bool:
    nt = re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]+", "", text.lower())
    if not nt:
        return False
    for tok in norm_tokens(key):
        t = re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]+", "", tok.lower())
        cjk = bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", t))
        if (cjk and len(t) >= 1) or len(t) >= 3:
            if t in nt:
                return True
    return False


def target_sig(dep: dict) -> Tuple[str, ...]:
    ts = []
    targets = []
    if isinstance(dep.get("target"), dict):
        targets.append(dep["target"])
    for t in dep.get("targets") or []:
        if isinstance(t, dict):
            targets.append(t)
    for t in targets:
        if t.get("part"):
            # CK 裁决 3：pathify_dep 会按声明 objects[].path 给 `_paths`；有则按路径比，
            # 没有（id 在声明里查不到）才退回 id 文本。
            if t.get("_paths"):
                ts.append("partpath:" + ",".join(sorted(t["_paths"])))
            else:
                ts.append("part:" + t["part"])
        else:
            keys = t.get("keys")
            if keys:
                for k in keys:
                    ts.append("mesh:%s:%s" % (t.get("mesh", ""), k))
            else:
                ts.append("mesh:%s:%s" % (t.get("mesh", ""), t.get("key", "")))
    return tuple(sorted(ts))


def canon(o):
    if isinstance(o, bool):
        return o
    if isinstance(o, (int, float)):
        return float(o)
    if isinstance(o, dict):
        return {k: canon(v) for k, v in o.items()}
    if isinstance(o, list):
        return [canon(x) for x in o]
    return o


def disp_expect(dep: dict) -> str:
    exp = dep.get("expect")
    if isinstance(exp, str):
        return exp
    return json.dumps(canon(exp), ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------------------
# 严格口径规范化（C-K）：见文件头「严格口径的规范化」。只服务 selftest 比较，
# 不进入草案 YAML，也不改变 decl_validate 的校验。
# ---------------------------------------------------------------------------
DEFAULT_TOL = 0.5


def _strip_outer_parens(s: str) -> str:
    s = s.strip()
    while len(s) >= 2 and s[0] == "(" and s[-1] == ")":
        depth = 0
        balanced = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(s) - 1:
                    balanced = False
                    break
        if not balanced:
            break
        s = s[1:-1].strip()
    return s


def _canon_atom(a: str) -> str:
    """单个合取原子：去多余括号、并空白、集合字面量排序。"""
    a = re.sub(r"\s+", " ", _strip_outer_parens(a.strip()))
    m = re.search(r"\{([^{}]*)\}", a)
    if m:
        items = sorted(x.strip() for x in m.group(1).split(",") if x.strip())
        a = a[:m.start()] + "{" + ", ".join(items) + "}" + a[m.end():]
    return a


def norm_when_clauses(when) -> frozenset:
    """when → 顶层析取的子句集合；子句内原子排序。语义等价的文本归一到同一集合。"""
    s = (when or "").strip()
    if s == "" or s.lower() == "true":
        return frozenset({"true"})
    s = re.sub(r"\s+and\s+", " & ", s, flags=re.I)
    s = re.sub(r"\s*&\s*", " & ", s)
    out = set()
    for disj in split_top(s, "|"):
        atoms = [_canon_atom(x) for x in split_top(disj, "&") if x.strip()]
        if atoms:
            out.add(" & ".join(sorted(atoms)))
    return frozenset(out)


# ---------------------------------------------------------------------------
# CK2 裁决 3/5：部件身份按对象路径、when 条件下的可见件过滤
# ---------------------------------------------------------------------------
def norm_obj_path(path) -> str:
    """对象路径规范化：反斜杠→斜杠、折叠重复斜杠、去首尾斜杠（根相对）。"""
    p = str(path or "").strip().replace("\\", "/")
    p = re.sub(r"/{2,}", "/", p)
    return p.strip("/")


def part_path_index(decl: dict) -> Dict[str, Tuple[str, ...]]:
    """part id → 规范化后的对象路径元组（declared + fragment 都收，供路径比对）。"""
    out: Dict[str, Tuple[str, ...]] = {}
    for p in decl.get("parts") or []:
        paths = []
        for o in p.get("objects") or []:
            path = o.get("path") if isinstance(o, dict) else o
            n = norm_obj_path(path)
            if n:
                paths.append(n)
        if paths:
            out[p["id"]] = tuple(sorted(set(paths)))
    return out


def _path_token(paths: Sequence[str]) -> str:
    """路径集合的规范 token（放在 vis(...) 里；括号外不会被 |/& 拆开）。"""
    return "path:" + ",".join(sorted(paths))


def _subst_when_paths(when, index: Dict[str, Tuple[str, ...]]) -> str:
    """把 when 里的 `vis(<part id>)` 换成 `vis(<path token>)`，先映射到对象路径再比。"""
    s = str(when or "")
    for pid, paths in index.items():
        s = re.sub(r"(?<![A-Za-z0-9_.])vis\(\s*" + re.escape(pid) + r"\s*\)",
                   "vis(%s)" % _path_token(paths), s)
    return s


def pathify_dep(dep: dict, index: Dict[str, Tuple[str, ...]]) -> dict:
    """返回 dep 的拷贝：part 目标补 `_paths`，when/cases.when 里的 vis(<id>) 换路径。"""
    d = copy.deepcopy(dep)

    def tgt(t):
        if isinstance(t, dict) and t.get("part") and not t.get("_paths"):
            paths = index.get(t["part"])
            if paths:
                t = dict(t)
                t["_paths"] = list(paths)
        return t

    if isinstance(d.get("target"), dict):
        d["target"] = tgt(d["target"])
    if d.get("targets"):
        d["targets"] = [tgt(t) for t in d["targets"]]
    if d.get("when"):
        d["when"] = _subst_when_paths(d["when"], index)
    for c in d.get("cases") or []:
        if isinstance(c, dict) and c.get("when"):
            c["when"] = _subst_when_paths(c["when"], index)
    return d


def when_disjuncts(when) -> List[frozenset]:
    """when → 析取子句列表，每个子句是规范化原子集合（供可见性判定用）。"""
    s = (when or "").strip()
    if s == "" or s.lower() == "true":
        return [frozenset()]
    s = re.sub(r"\s+and\s+", " & ", s, flags=re.I)
    s = re.sub(r"\s*&\s*", " & ", s)
    out = []
    for disj in split_top(s, "|"):
        atoms = frozenset(_canon_atom(x) for x in split_top(disj, "&") if x.strip())
        if atoms:
            out.append(atoms)
    return out


def _outfit_set_in_atom(atom: str) -> Optional[Set[str]]:
    """原子若是 outfit 约束，返回它限定的 label 集合；否则 None。"""
    m = re.match(r'^outfit\s+(?:=|in)\s*\{(.*)\}$', atom)
    if m:
        return {x.strip().strip('"') for x in m.group(1).split(",") if x.strip()}
    m = re.match(r'^outfit\s*=\s*(.+)$', atom)
    if m:
        return {m.group(1).strip().strip('"')}
    return None


def part_visible_under(part: dict, when) -> bool:
    """件在 when 条件下是否**可能**可见（保守：拿不准就判可见，不误删）。

    用声明里的 `outfit` 显隐关系：某件有显式 outfit 档集合，而 when 的**每个**析取
    子句都把 outfit 限到与它不相交的档（且没有 `vis(<该件>)`），才判必然不可见。
    没有 outfit 约束的子句、或与该件有交集的子句，都判可见。盘点里没有 outfit 的件
    （素体件/配饰）恒可见。
    """
    labels = part.get("outfit")
    if isinstance(labels, str):
        labels = {labels}
    labels = {str(x) for x in (labels or []) if str(x)}
    if not labels:
        return True
    paths = part.get("_paths") or []
    vis_tokens = {"vis(%s)" % _path_token(paths)} if paths else set()
    pid = part.get("part")
    for atoms in when_disjuncts(when):
        if pid and ("vis(%s)" % pid) in atoms:
            return True
        if any(a in vis_tokens for a in atoms):
            return True
        constrained = False
        allowed: Set[str] = set()
        for a in atoms:
            s = _outfit_set_in_atom(a)
            if s is not None:
                constrained = True
                allowed |= s
        if not constrained or (labels & allowed):
            return True
    return False


def filter_visible_targets(dep: dict, parts_by_id: Dict[str, dict]) -> dict:
    """按 when 可见性过滤 dep 的 part 目标（CK 裁决 5）；mesh 目标不参与。

    调用前 dep 应已 pathify（targets 带 `_paths`、when 已换路径 token）。被剔到
    空目标的 dep 仍保留（其目标集合为空，任何一侧都不会误配）。
    """
    d = copy.deepcopy(dep)
    when = d.get("when")
    if d.get("cases"):
        # cases 展开后每个分支的 when 不同，取所有非 dont_care 分支的并集判可见性
        when = " | ".join("(%s)" % c.get("when") for c in d["cases"]
                          if isinstance(c, dict) and c.get("when"))

    def keep(t) -> bool:
        if not isinstance(t, dict) or not t.get("part"):
            return True
        merged = dict(parts_by_id.get(t["part"]) or {})
        merged["part"] = t["part"]
        if t.get("_paths"):
            merged["_paths"] = list(t["_paths"])
        return part_visible_under(merged, when)

    for key in ("target", "targets"):
        val = d.get(key)
        if isinstance(val, dict):
            if not keep(val):
                d.pop(key, None)
        elif isinstance(val, list):
            d[key] = [t for t in val if keep(t)]
    return d


def vis_parts_index(decl: dict, index: Dict[str, Tuple[str, ...]]) -> Dict[str, dict]:
    """声明 parts → {id: part}，并补上 `_paths`（可见性判定要按路径认 vis token）。"""
    out: Dict[str, dict] = {}
    for p in decl.get("parts") or []:
        q = dict(p)
        if p["id"] in index:
            q["_paths"] = list(index[p["id"]])
        out[p["id"]] = q
    return out


def is_migration_marked(dep: dict) -> bool:
    """从声明条目的 origin/human_only/source/note 识别「生成器→声明」迁移条目。"""
    if dep.get("human_only") is True:
        return True
    origin = str(dep.get("origin") or "")
    if "migrat" in origin.lower() or "迁移" in origin or "迁入" in origin:
        return True
    texts = [str(s) for s in (dep.get("source") or [])]
    if dep.get("note"):
        texts.append(str(dep["note"]))
    blob = " ".join(texts)
    return any(m in blob for m in MIGRATION_MARKERS)


def target_overlap_ratio(a: dict, b: dict) -> float:
    """两个 dep 目标集合的 Jaccard 重叠比（0..1）。"""
    A, B = set(target_sig(a)), set(target_sig(b))
    if not A or not B:
        return 0.0
    return len(A & B) / float(len(A | B))


def cmp_expect(exp) -> str:
    """expect 规范化：数值 int/float 同值，省略 tol 与 tol=0.5 同；其余原样。"""
    if exp is None:
        return "null"
    if isinstance(exp, str):
        return exp
    c = canon(exp)
    if isinstance(c, dict) and len(c) > 1 and c.get("tol") == DEFAULT_TOL:
        c = {k: v for k, v in c.items() if k != "tol"}
    return json.dumps(c, ensure_ascii=False, sort_keys=True)


def dep_units(dep: dict) -> List[Tuple[Tuple[str, ...], frozenset, str]]:
    """dep → 比较单元列表 [(目标集合, when 子句集合, expect 规范串)]。

    带 `cases` 者展开为多条（跳过 dont_care）；无 `cases` 者一条。`else` 不参与。
    """
    tgt = target_sig(dep)
    cases = dep.get("cases") or []
    if cases:
        out = []
        for c in cases:
            e = c.get("expect")
            if e == "dont_care":
                continue
            out.append((tgt, norm_when_clauses(c.get("when")), cmp_expect(e)))
        return out
    e = dep.get("expect")
    if e == "dont_care":
        return []
    return [(tgt, norm_when_clauses(dep.get("when")), cmp_expect(e))]


def human_dep_hit(h: dict, draft_deps: Sequence[dict]) -> bool:
    """人写一条是否被草案命中：每条非 dont_care 单元都要被草案析取并集覆盖。"""
    hunits = dep_units(h)
    if not hunits:
        return False
    for tgt, wset, exp in hunits:
        covered = set()
        for y in draft_deps:
            for t2, w2, e2 in dep_units(y):
                if t2 == tgt and e2 == exp:
                    covered |= w2
        if not wset <= covered:
            return False
    return True


def draft_dep_hit(y: dict, human_deps: Sequence[dict]) -> bool:
    """草案一条是否命中某人写条：每条单元必须是某人写条单元的析取子集。"""
    for tgt, wset, exp in dep_units(y):
        ok = False
        for x in human_deps:
            for t2, w2, e2 in dep_units(x):
                if t2 == tgt and e2 == exp and wset <= w2:
                    ok = True
                    break
            if ok:
                break
        if not ok:
            return False
    return True


def label_tok(label: str) -> str:
    if re.search(r"[\s,{}|&!()\[\]\"<>:=]", label) or re.fullmatch(r"-?\d+(\.\d+)?", label):
        return '"%s"' % label
    return label


def outfit_cond(labels: Sequence[str]) -> Optional[str]:
    labels = list(labels)
    if not labels:
        return None
    if len(labels) == 1:
        return "outfit = %s" % label_tok(labels[0])
    return "outfit in {%s}" % ", ".join(label_tok(x) for x in labels)


# ===========================================================================
# 输出 YAML
# ===========================================================================
def build_menu(ctx: Ctx) -> dict:
    menu = ctx.menu
    labels = menu.get("outfit_labels") or []
    if not labels:
        return {}
    outfit = {
        "param": "A2_Outfit", "type": "float_slots", "labels": labels,
        "default": ctx.default_of("A2_Outfit", 0), "label": "整套",
    }
    slots = {}
    for row in menu.get("parts") or []:
        if len(row) < 2:
            continue
        param, label = row[0], row[1]
        slot = SLOT_KEYS.get(param)
        if not slot:
            continue
        slots[slot] = {"param": param, "type": "bool",
                       "default": ctx.default_of(param, 1), "label": label}
    controls = {}
    # 配饰（ACCPARTS/HEADPARTS）连表里的参数一起收
    for table in ("accparts", "headparts"):
        for row in menu.get(table) or []:
            if len(row) < 2:
                continue
            param, label = row[0], row[1]
            ctl = CONTROL_KEYS.get(param)
            if ctl and ctl not in controls:
                controls[ctl] = {"param": param, "type": "bool",
                                 "default": ctx.default_of(param, 1), "label": label}
    for param, key, labels2 in (
            ("A2_Hair", "hair", menu.get("hair_labels") or []),
            ("A2_EarTail", "eartail", menu.get("eartail_labels") or []),
            ("A2_Halo", "halo", menu.get("onoff_labels") or []),
            ("A2_Head", "head", menu.get("onoff_labels") or [])):
        if key in controls or not labels2:
            continue
        ctl_label = {"hair": "发型", "eartail": "耳尾", "halo": "光环", "head": "头饰"}[key]
        controls[key] = {"param": param, "type": "float_slots", "labels": labels2,
                         "default": ctx.default_of(param, 0), "label": ctl_label}
    return {"outfit": outfit, "slots": slots, "controls": controls}


def build_avatar(ctx: Ctx) -> dict:
    prof = ctx.profile
    prof_name = prof.get("body") or "Kaguya"
    prof_ver = prof.get("version") or "0"
    root = ctx.avatar_name or os.path.basename(ctx.project)
    av = {
        "project": ctx.project_id,
        "root": root,
        "body": ctx.body,
        "profile": "%s@%s" % (prof_name, prof_ver),
    }
    if ctx.scene:
        try:
            rel = os.path.relpath(ctx.scene, ctx.project)
            if rel.startswith("Assets/") and rel.endswith(".unity"):
                av["scene"] = rel
        except ValueError:
            pass
    return av


def dump_yaml(doc: dict, header: str) -> str:
    body = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False,
                          default_flow_style=False, width=1000)
    return header + body


def generate(ctx: Ctx) -> Tuple[dict, "Draft"]:
    d = Draft(ctx)
    d.build()
    # CK2 裁决 6：场景里待清的旧冗余 SC（A-工程A-12 在清）标 pending_cleanup；
    # schema 不允许新字段，标在 note 上；selftest 按 PENDING_CLEANUP_IDS 不计精确率分母。
    for dep in d.deps:
        if dep.get("id") in PENDING_CLEANUP_IDS:
            dep["note"] = ("pending_cleanup：待清冗余（A-工程A-12 在清），"
                           "不计入草案精确率分母。" + (" " + dep["note"]
                                                       if dep.get("note") else ""))
    doc = {
        "schema": "perception/0.2",
        "avatar": build_avatar(ctx),
        "includes": d.frag_includes,
        "menu": build_menu(ctx),
        "geo_defaults": True,
        "parts": d.parts,
        "deps": d.deps,
    }
    if not doc["includes"]:
        doc.pop("includes")
    return doc, d


def header_text(ctx: Ctx, d: "Draft") -> str:
    lines = [
        "# 感知机制声明草案（T-04 decl_draft.py 自动起草；人只需补 human: 项）",
        "#",
        "# 来源：S1 生成器表 %s" % (os.path.relpath(ctx.menu_gen, ctx.project) if ctx.menu_gen else "—"),
        "#       S2 场景/prefab MA 组件 + 盘点 %s" % (os.path.relpath(ctx.inventory_path, ctx.project) if ctx.inventory_path else "—"),
        "#       S3 厂商 ON/OFF clip、S7 T4 params.json、S9 素体档案与服装包片段",
        "# 厂商写者一律 confidence.correct: unknown；拿不准的机制标 human:。",
        "# 人判清单：",
    ]
    for p in d.parts:
        if isinstance(p.get("human"), str):
            lines.append("#   [part] %s: %s" % (p["id"], p["human"]))
    for dep in d.deps:
        if isinstance(dep.get("human"), str):
            lines.append("#   [dep]  %s: %s" % (dep["id"], dep["human"]))
    if d.unresolved:
        lines.append("# 未解析选择器（工程里没有对应渲染器）：")
        for u in d.unresolved[:20]:
            lines.append("#   %s" % u)
    if d.skipped:
        lines.append("# 未起草的机制（工具读不懂/参数不在 menu，待人核）：")
        for s in d.skipped[:30]:
            lines.append("#   %s" % s)
    lines.append("")
    return "\n".join(lines) + "\n"


# ===========================================================================
# selftest：与人写声明比对
# ===========================================================================
def load_decl_json(yaml_path: str, profile: Optional[str], inventory: Optional[str],
                   out_json: str) -> Tuple[Optional[dict], str]:
    cmd = [sys.executable, VALIDATE, "--in", yaml_path, "--out", out_json, "--quiet"]
    if profile:
        cmd += ["--profile", profile]
    if inventory:
        cmd += ["--inventory", inventory]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 or not os.path.exists(out_json):
        return None, out
    with open(out_json, encoding="utf-8") as f:
        return json.load(f), out


def non_geo_deps(decl: dict, kinds=("D1", "D3", "D4a", "D6")) -> List[dict]:
    out = []
    for dep in decl.get("deps") or []:
        if dep.get("origin") == "geo_default":
            continue
        if dep.get("kind") in kinds:
            out.append(dep)
    return out


def part_objects(decl: dict, origin: str = "declared") -> Dict[str, Set[str]]:
    out = {}
    for p in decl.get("parts") or []:
        if origin and p.get("origin") != origin:
            continue
        out[p["id"]] = {o["path"] for o in (p.get("objects") or [])}
    return out


def compare_and_report(human_json: dict, draft_json: dict) -> Tuple[bool, List[str]]:
    log: List[str] = []
    # ---- parts 覆盖率：按「件」计（人写每件是否被草案覆盖） ----
    hp = part_objects(human_json, "declared")
    dp = part_objects(draft_json, "declared")
    draft_paths = set()
    for s in dp.values():
        draft_paths |= s
    # 草案 includes 带来的片段部件（片段件由 include 覆盖，与主体声明同位）
    frag_paths = set()
    for p in draft_json.get("parts") or []:
        if p.get("origin") == "fragment":
            for o in p.get("objects") or []:
                frag_paths.add(o["path"])
    all_draft = draft_paths | frag_paths

    log.append("")
    log.append("== parts 覆盖率（人写主体 parts → 草案） ==")
    covered = 0
    miss_parts = []
    path_total = path_hit = 0
    for pid, paths in sorted(hp.items()):
        if paths and paths <= all_draft:
            covered += 1
        else:
            miss_parts.append((pid, sorted(paths - all_draft)))
        for path in paths:
            path_total += 1
            if path in all_draft:
                path_hit += 1
    cov = (covered / len(hp) * 100.0) if hp else 100.0
    log.append("  件覆盖 %d/%d = %.1f%%（阈值 90%%）" % (covered, len(hp), cov))
    log.append("  （诊断）物体路径覆盖 %d/%d = %.1f%%"
               % (path_hit, path_total, (path_hit / path_total * 100.0) if path_total else 100.0))
    for pid, missing in miss_parts:
        log.append("  [miss] %s  %s" % (pid, " ".join(missing)[:110]))
    parts_ok = cov >= 90.0

    # ---- D1/D3/D4a/D6 一致性 ----
    hd_raw = non_geo_deps(human_json)
    dd_raw = non_geo_deps(draft_json)

    def _tgt_set(dep: dict) -> Set[str]:
        return set(target_sig(dep))

    # CK2 裁决 3/5：先按各自声明的对象路径 pathify（part 身份按路径比、when 里件名
    # 映射到路径），再用声明/盘点的 outfit/toggle 显隐关系剔掉 when 下必然不可见的件。
    h_idx = part_path_index(human_json)
    d_idx = part_path_index(draft_json)
    h_vis = vis_parts_index(human_json, h_idx)
    d_vis = vis_parts_index(draft_json, d_idx)
    hd = [filter_visible_targets(pathify_dep(x, h_idx), h_vis) for x in hd_raw]
    dd = [filter_visible_targets(pathify_dep(y, d_idx), d_vis) for y in dd_raw]

    # CK2 裁决 1/4：human_only（B-T07a 迁移、工程里无别的来源）与被取代条目不进分母。
    present = {x["id"]: x for x in hd}
    human_only = [i for i in HUMAN_ONLY_IDS if i in present]
    human_only_set = set(human_only)
    unmarked = [i for i in human_only if not is_migration_marked(present[i])]
    marked_extra = [x["id"] for x in hd
                    if is_migration_marked(x) and x["id"] not in human_only_set
                    and not human_dep_hit(x, dd)]
    superseded: Set[str] = set()
    for x in hd:
        for s in x.get("supersedes") or []:
            superseded.add(s)
    excluded_h = human_only_set | superseded

    # CK2 裁决 6：pending_cleanup 不进精确率分母；草案佐证计入命中。
    pending_set = {y["id"] for y in dd if y["id"] in PENDING_CLEANUP_IDS}
    d_eval = [y for y in dd if y["id"] not in pending_set]

    def _guard_sets(dep: dict) -> List[frozenset]:
        out = []
        if dep.get("cases"):
            for c in dep["cases"]:
                if isinstance(c, dict) and c.get("expect") != "dont_care" and c.get("when"):
                    out.append(norm_when_clauses(c["when"]))
        elif dep.get("when") is not None:
            w = norm_when_clauses(dep["when"])
            if w != frozenset({"true"}):
                out.append(w)
        return out

    def corroborated(y: dict) -> Optional[str]:
        """草案多出条目与某条 human_only 迁移条目 when 等价且 targets 重叠 ≥80%。"""
        for x in hd:
            if x["id"] not in human_only_set:
                continue
            if any(a == b for a in _guard_sets(y) for b in _guard_sets(x)) \
                    and target_overlap_ratio(y, x) >= CORROBORATE_OVERLAP:
                return x["id"]
        return None

    log.append("")
    log.append("== D1/D3/D4a/D6 自动条目一致性 ==")
    log.append("  口径 A（旧）= kind + 目标重叠；口径 B（严格，09-19 签字 B-T04，"
               "C-K 规范化＋CK2 六条裁决）= kind + 目标集合全等（按对象路径）"
               "+ when 同 + expect 同")
    log.append("  规范化见文件头：cases 展开 / when 布尔与析取覆盖 / expect 数值与默认 tol"
               " / shlink=shrink / 部件按路径 / 可见件过滤")
    log.append("  %-5s %-13s %-13s %-13s %-13s"
               % ("kind", "A 人写", "A 草案", "B 人写", "B 草案"))
    per_kind = {}
    for kind in ("D1", "D3", "D4a", "D6"):
        hs = [x for x in hd if x.get("kind") == kind]
        ds = [x for x in dd if x.get("kind") == kind]
        hs_eval = [x for x in hs if x["id"] not in excluded_h]
        ds_eval = [y for y in ds if y["id"] not in pending_set]
        a_h = sum(1 for x in hs if any(target_overlap(x, y) for y in ds))
        a_d = sum(1 for y in ds if any(target_overlap(x, y) for x in hs))
        b_h = sum(1 for x in hs_eval if human_dep_hit(x, ds))
        b_d = sum(1 for y in ds_eval
                  if draft_dep_hit(y, hd) or corroborated(y) is not None)
        per_kind[kind] = (a_h, len(hs), a_d, len(ds), b_h, len(hs_eval),
                          b_d, len(ds_eval))
        log.append("  %-5s %-13s %-13s %-13s %-13s"
                   % (kind, "%d/%d" % (a_h, len(hs)), "%d/%d" % (a_d, len(ds)),
                      "%d/%d" % (b_h, len(hs_eval)), "%d/%d" % (b_d, len(ds_eval))))
    a_h_tot = sum(v[0] for v in per_kind.values())
    a_all = sum(v[1] for v in per_kind.values())
    a_d_tot = sum(v[2] for v in per_kind.values())
    a_d_all = sum(v[3] for v in per_kind.values())
    b_h_tot = sum(v[4] for v in per_kind.values())
    b_h_all = sum(v[5] for v in per_kind.values())
    b_d_tot = sum(v[6] for v in per_kind.values())
    b_d_all = sum(v[7] for v in per_kind.values())
    a_recall = (a_h_tot / a_all * 100.0) if a_all else 100.0
    a_prec = (a_d_tot / a_d_all * 100.0) if a_d_all else 100.0
    b_recall = (b_h_tot / b_h_all * 100.0) if b_h_all else 100.0
    b_prec = (b_d_tot / b_d_all * 100.0) if b_d_all else 100.0
    log.append("  A 旧口径：人写命中 %d/%d = %.1f%%；草案命中 %d/%d = %.1f%%"
               % (a_h_tot, a_all, a_recall, a_d_tot, a_d_all, a_prec))
    log.append("  B 严格口径：人写命中 %d/%d = %.1f%%；草案命中 %d/%d = %.1f%%（均阈值 80%%）"
               % (b_h_tot, b_h_all, b_recall, b_d_tot, b_d_all, b_prec))
    log.append("  human_only（迁移，不计分母）%d 条：%s"
               % (len(human_only), " ".join(human_only) or "—"))
    log.append("  被取代（不计分母）%d 条：%s"
               % (len(superseded), " ".join(sorted(superseded)) or "—"))
    log.append("  pending_cleanup（不计精确率分母）%d 条：%s"
               % (len(pending_set), " ".join(sorted(pending_set)) or "—"))
    corroborated_list = [(y["id"], corroborated(y)) for y in d_eval
                         if corroborated(y) and not draft_dep_hit(y, hd)]
    log.append("  草案佐证（计入命中）%d 条：%s"
               % (len(corroborated_list),
                  " ".join("%s←%s" % (a, b) for a, b in corroborated_list) or "—"))
    if unmarked:
        log.append("  [需 Claude 补标] human_only 名单里的条目在声明里找不到迁移标记"
                   "（origin/human_only/source/note）：%s" % " ".join(unmarked))
    if marked_extra:
        log.append("  声明里带迁移标记、但不在 human_only 名单（不猜，交 Claude 核）：%s"
                   % " ".join(marked_extra))
    # 断言：名单里的迁移条目必须都在声明里、且能被迁移标记识别（识别不了就点名，不猜）。
    missing_ids = [i for i in HUMAN_ONLY_IDS if i not in present]
    human_only_ok = not missing_ids and not unmarked
    if missing_ids:
        log.append("  [FAIL] human_only 断言：名单里的条目在声明中不存在：%s"
                   % " ".join(missing_ids))
    if not human_only_ok:
        log.append("  [FAIL] human_only 断言未过：名单 %d 条 / 识别 %d 条 / 未识别 %d 条"
                   % (len(HUMAN_ONLY_IDS), len(human_only), len(unmarked)))
    deps_ok = b_recall >= 80.0 and b_prec >= 80.0 and human_only_ok

    # ---- 差异表 ----
    log.append("")
    log.append("== 差异表（人写 D1/D3/D4a/D6 → 草案最相近条目） ==")
    unresolved = []
    for x in hd:
        kind, xtgt = x.get("kind"), _tgt_set(x)
        sup = x.get("supersedes") or []
        sup_note = ("（取代 %s）" % ",".join(sup)) if sup else ""
        if x["id"] in human_only_set:
            tag = "迁移" if is_migration_marked(x) else "迁移(未标)"
            log.append("  [human_only/%s] %-34s 不进分母" % (tag, x["id"]))
            continue
        if x["id"] in superseded:
            log.append("  [被取代] %-42s 不进分母" % x["id"])
            continue
        cand = [y for y in dd if y.get("kind") == kind and target_overlap(x, y)]
        hit = human_dep_hit(x, dd)
        if hit:
            cover = [y["id"] for y in dd
                     if y.get("kind") == kind and draft_dep_hit(y, [x])]
            log.append("  [命中] %-42s%s ← %s"
                       % (x["id"], sup_note, ", ".join(cover)[:100]))
            continue
        unresolved.append(x["id"])
        if not cand:
            log.append("  [未命中] %-42s%s %s" % (x["id"], sup_note, short_target(x)))
            continue
        y = cand[0]
        log.append("  %-42s%s → %-42s 目标=%s when=%s expect=%s"
                   % (x["id"], sup_note, y["id"],
                      "全等" if xtgt == _tgt_set(y) else "重叠",
                      "同" if norm_when_clauses(x.get("when"))
                      == norm_when_clauses(y.get("when")) else "异",
                      "同" if cmp_expect(x.get("expect")) == cmp_expect(y.get("expect"))
                      else "异"))
    if unresolved:
        log.append("  未命中且未分类（非迁移/非取代，逐条交 Claude 裁决）：%s"
                   % " ".join(unresolved))
    log.append("")
    log.append("== 草案多出的自动条目（人写未声明） ==")
    for y in dd:
        if y["id"] in pending_set:
            log.append("  [pending_cleanup] %-32s %s" % (y["id"], short_target(y)))
            continue
        if draft_dep_hit(y, hd):
            continue
        cid = corroborated(y)
        if cid:
            log.append("  [草案佐证] %-36s ← %s（when 等价、目标重叠 ≥%.0f%%）"
                       % (y["id"], cid, CORROBORATE_OVERLAP * 100))
            continue
        log.append("  [+] %-42s %s" % (y["id"], short_target(y)))
    return (parts_ok and deps_ok), log


def short_target(dep: dict) -> str:
    ts = target_sig(dep)
    return " ".join(ts)[:90]


def targets_of(dep: dict) -> Set[str]:
    return set(target_sig(dep))


def target_overlap(a: dict, b: dict) -> bool:
    return bool(targets_of(a) & targets_of(b))


# ===========================================================================
# selftest 主体
# ===========================================================================
PROJECT_A_DIR = os.path.join(WORKSPACE, "工程A")
TMP = os.path.join(WORKSPACE, "_长程任务_20260918", "派工", "tmp", "ai")


def _工程A_ctx() -> Ctx:
    return Ctx(PROJECT_A_DIR,
               profile_path=os.path.join(WORKSPACE, "开发工具", "素体档案", "Kaguya.yaml"),
               inventory_path=os.path.join(PROJECT_A_DIR, "_感知", "out", "inventory.json"),
               params_path=os.path.join(WORKSPACE, "_长程任务_20260918", "审查产出",
                                        "工程A", "t4_menu", "params.json"))


def selftest() -> int:
    os.makedirs(TMP, exist_ok=True)
    ctx = _工程A_ctx()
    doc, d = generate(ctx)
    draft_yaml = os.path.join(TMP, "draft_工程A.yaml")
    with open(draft_yaml, "w", encoding="utf-8") as f:
        f.write(dump_yaml(doc, header_text(ctx, d)))
    print("[selftest] project=%s" % ctx.project)
    print("[selftest] scene=%s" % ctx.scene)
    print("[selftest] draft -> %s（parts=%d deps=%d includes=%d）"
          % (draft_yaml, len(doc["parts"]), len(doc["deps"]), len(doc.get("includes") or [])))

    profile = os.path.join(WORKSPACE, "开发工具", "素体档案", "Kaguya.yaml")
    inventory = os.path.join(PROJECT_A_DIR, "_感知", "out", "inventory.json")
    draft_json_path = os.path.join(TMP, "draft_工程A.decl.json")
    human_json_path = os.path.join(TMP, "human_工程A.decl.json")
    human_yaml = os.path.join(PROJECT_A_DIR, "_感知", "声明.yaml")

    dj, out = load_decl_json(draft_yaml, profile, inventory, draft_json_path)
    if dj is None:
        print("[FAIL] 草案未过 decl_validate：")
        print(out)
        return 1
    print("[selftest] decl_validate(draft): OK（0 error）")
    hj, hout = load_decl_json(human_yaml, profile, inventory, human_json_path)
    if hj is None:
        print("[FAIL] 人写声明未过 decl_validate：")
        print(hout)
        return 1
    ok, log = compare_and_report(hj, dj)
    for line in log:
        print(line)
    if ok:
        print("[selftest] OK（覆盖率与 D1/D3/D4a/D6 一致性均达标）")
        return 0
    print("[FAIL] 覆盖率或一致性未达标")
    return 1


def selftest_blind() -> int:
    os.makedirs(TMP, exist_ok=True)
    blind_dir = os.path.join(TMP, "blind")
    os.makedirs(blind_dir, exist_ok=True)
    proj_rel = "工程A"
    old_cs = os.path.join(blind_dir, "MenuGenA2.cs")
    old_scene = os.path.join(blind_dir, "工程A.unity")
    for src, dst in ((proj_rel + "/Assets/Editor/AvatarGen/MenuGenA2.cs", old_cs),
                     (proj_rel + "/Assets/_Work/工程A.unity", old_scene)):
        r = subprocess.run(["git", "-C", WORKSPACE, "show", "ceb4070b^:" + src],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("[FAIL] git show 失败：%s\n%s" % (src, r.stderr))
            return 1
        with open(dst, "w", encoding="utf-8") as f:
            f.write(r.stdout)
    ctx = Ctx(PROJECT_A_DIR,
              profile_path=os.path.join(WORKSPACE, "开发工具", "素体档案", "Kaguya.yaml"),
              inventory_path=os.path.join(PROJECT_A_DIR, "_感知", "out", "inventory.json"),
              params_path=os.path.join(WORKSPACE, "_长程任务_20260918", "审查产出",
                                       "工程A", "t4_menu", "params.json"),
              scene=old_scene, menu_gen=old_cs)
    doc, d = generate(ctx)
    blind_yaml = os.path.join(TMP, "draft_blind.yaml")
    with open(blind_yaml, "w", encoding="utf-8") as f:
        f.write(dump_yaml(doc, header_text(ctx, d)))
    print("[selftest-blind] 旧源：git show ceb4070b^ 的 MenuGenA2.cs + 场景 → %s" % blind_dir)
    print("[selftest-blind] draft -> %s（parts=%d deps=%d）"
          % (blind_yaml, len(doc["parts"]), len(doc["deps"])))

    # 判据 1：MMN 脚型条目 when 只含 socks 且 correct unknown
    foot = []
    for dep in doc["deps"]:
        tg = target_sig(dep)
        if any(t.endswith("Foot_heel_OFF_____足_ヒールオフ") for t in tg):
            foot.append(dep)
    ok1 = False
    for dep in foot:
        when = dep.get("when") or ""
        if "MMN" in when and "socks" in when and "shoes" not in when \
                and (dep.get("confidence") or {}).get("correct") == "unknown":
            print("[selftest-blind] OK 脚型条目 %s: when=%r correct=%s"
                  % (dep["id"], when, dep["confidence"]["correct"]))
            ok1 = True
    if not ok1:
        print("[FAIL] 未找到「when 只含 socks 且 correct: unknown」的 MMN 脚型条目：")
        for dep in foot:
            print("   %s when=%r correct=%s" % (dep["id"], dep.get("when"),
                                                (dep.get("confidence") or {}).get("correct")))

    # 判据 2：外套备选件含 big_open 且带 human
    ok2 = False
    for p in doc["parts"]:
        paths = " ".join(o["path"] for o in p.get("objects") or [])
        if "outer_breast_big_open" in paths:
            if isinstance(p.get("human"), str) and p["human"]:
                print("[selftest-blind] OK 备选外套 %s: path=%s human=%r"
                      % (p["id"], paths, p["human"][:40]))
                ok2 = True
            else:
                print("[FAIL] big_open 部件 %s 没有 human:" % p["id"])
    if not ok2:
        big = [p["id"] for p in doc["parts"]
               if any("outer_breast_big_open" in o["path"] for o in p.get("objects") or [])]
        print("[FAIL] 未找到带 human: 的 big_open 部件；相关部件=%s" % big)

    # 附加：盲草案也过校验（0 error）
    draft_json = os.path.join(TMP, "draft_blind.decl.json")
    dj, out = load_decl_json(blind_yaml,
                             os.path.join(WORKSPACE, "开发工具", "素体档案", "Kaguya.yaml"),
                             os.path.join(PROJECT_A_DIR, "_感知", "out", "inventory.json"),
                             draft_json)
    if dj is None:
        print("[FAIL] 盲草案未过 decl_validate：")
        print(out)
        return 1
    print("[selftest-blind] decl_validate(blind draft): OK（0 error）")
    shutil.rmtree(blind_dir, ignore_errors=True)
    return 0 if (ok1 and ok2) else 1


# ===========================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="感知声明草案生成器（T-04）")
    ap.add_argument("--project", help="工程根目录")
    ap.add_argument("--out", help="输出草案 YAML")
    ap.add_argument("--profile", help="素体档案 YAML（S9）")
    ap.add_argument("--inventory", help="T-05 盘点 inventory.json")
    ap.add_argument("--params", help="T4 params.json（S7；只取默认值）")
    ap.add_argument("--scene", help="场景 .unity（缺省自动探测）")
    ap.add_argument("--menu-gen", help="MenuGen*.cs（缺省自动探测）")
    ap.add_argument("--selftest", action="store_true", help="对 工程A 起草并与人写声明比对")
    ap.add_argument("--selftest-blind", dest="selftest_blind", action="store_true",
                    help="盲起草预演（git show ceb4070b^ 旧源）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.selftest_blind:
        return selftest_blind()
    if not args.project or not args.out:
        ap.error("需要 --project 与 --out（或 --selftest / --selftest-blind）")
    ctx = Ctx(args.project, profile_path=args.profile, inventory_path=args.inventory,
              params_path=args.params, scene=args.scene, menu_gen=args.menu_gen)
    doc, d = generate(ctx)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(dump_yaml(doc, header_text(ctx, d)))
    if not args.quiet:
        print("[decl_draft] parts=%d deps=%d includes=%d → %s"
              % (len(doc["parts"]), len(doc["deps"]), len(doc.get("includes") or []), args.out))
        from collections import Counter
        print("  deps kind=%s" % dict(Counter(x["kind"] for x in doc["deps"])))
        for s in d.skipped[:10]:
            print("  [skip] %s" % s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
