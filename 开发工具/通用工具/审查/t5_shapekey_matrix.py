#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T5「形态键依赖矩阵」——把「哪个开关动了哪个形态键、谁该收谁没收」数据化。
【项目沉淀】通用工具
适用素体：无关
相关素材：工程 T4 params.json + T1 输出
工具链　：Python 3（离线）
可复用性：★★ 声明/参数结构变了要跟着改
用途　　：T5「形态键依赖矩阵」：用 slots/sweep 生成 T1 请求，再 analyze 出「哪个开关动哪个键、谁该收谁没收」。


配合 T1（AuditStateDriver）使用：先用本工具的三个生成子命令产出 T1 请求，在 Play 构建后的
头像上跑 T1，再用 analyze 把 state_*.json 读成矩阵。

四个子命令（中文帮助见 --help）：

  slots           T4 params.json 里每个 Float 轮盘参数 → 0..1 细扫的 T1 请求
  slots-reduce    细扫结果 → 按「可见渲染器 + 非零形态键」签名合并成区间 slots.json
  sweep           params.json + slots.json → 「整套 × 单关 × 全关」状态集的 T1 请求
  analyze         T1 输出 + sweep 请求 → matrix.json / matrix.md

设计依据：`_长程任务_20260918/派工/` 任务书 P；样例见
`_长程任务_20260918/审查产出/工程A/t1_sweep_outfit_parts/`。

只依赖 Python 3 标准库；只读输入、只写 --out 指定处；不启动 Unity、不调 MCP。
输出统一 UTF-8 无 BOM、LF。

关键口径（取舍都写在这里，docs/shapekey-matrix*.md（旧称 README_T5.md）有更细的说明）：

* 名字还原：Play 构建后 AAO/NDMF 会改名，报告里每处同时给原名与还原名。
  - 形态键 `AAO_Merged_<原名>_<n>` → `<原名>`；
  - 渲染器段 `名$原物体$编号` → `原物体`；
  - `$$AAO_AUTO_MERGE_SKINNED_MESH_n` 原名不可知 → `<AAO合并网格#n>`。
* 「可见」= T1 state 里的 `visible`（activeInHierarchy && enabled）。
* 表情/面捕/眨眼类键默认按键名关键词过滤，可用 --filter-file 覆盖。
* 「服装件」= 还原路径含服装根词（cloth/outfit…）或叶名含服装单品词（pants/skirt/sock…）。
  这是关键词启发式，不是语义理解；可用 --clothing-keywords-file 覆盖。
* 自动候选只给「嫌疑人」，判据写死在候选条目里，不是定论。
"""

import argparse
import glob
import json
import os
import re
import sys
import time

TOOL = "t5_shapekey_matrix"

# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

CJK_RANGES = (
    "\u3040-\u30ff"      # 平假名/片假名
    "\u3400-\u4dbf"      # CJK 扩展 A
    "\u4e00-\u9fff"      # CJK 基本区
    "\uff66-\uff9f"      # 半角片假名
)
_CJK_RE = re.compile("[%s]" % CJK_RANGES)
_TOKEN_SPLIT = re.compile(r"[^0-9a-zA-Z%s]+" % CJK_RANGES)
_ASCII_TOKEN = re.compile(r"[0-9a-zA-Z]+")


def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def write_text(path, text):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def eprint(*a):
    sys.stderr.write(" ".join(str(x) for x in a) + "\n")


def die(msg, code=2):
    eprint("[T5] 错误：" + msg)
    sys.exit(code)


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


def round6(x):
    return round(float(x) + 0.0, 6)


def fmt_val(v):
    """报告里数值的显示：整数不带小数点。"""
    if v is None:
        return "?"
    f = float(v)
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    return ("%.6f" % f).rstrip("0").rstrip(".")


def sanitize(name):
    return re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_") or "p"


# ---------------------------------------------------------------------------
# 名字还原
# ---------------------------------------------------------------------------

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


def _is_cjk(s):
    return bool(_CJK_RE.search(s))


def tokens(s):
    """把名字拆成小写 token（拉丁按非字母数字切，CJK 连续段整体保留）。"""
    if not s:
        return set()
    out = set()
    for p in _TOKEN_SPLIT.split(str(s).lower()):
        if p:
            out.add(p)
    return out


def name_relates(key_name, other_names, stopwords=None):
    """key_name 里是否出现 other_names 中某个 token（拉丁 ≥3 字符 / CJK 任意长度）。

    返回命中的 token；没有返回 None。这是候选 (a)(b)(d) 的「相关性」判据。

    ASCII token 按**完整 token**比对（`tokens(key_name)` 集合成员），不再用子串：
    否则 `dress` 会命中 `HeadDress`（K12 误报）。CJK 无词边界，仍按子串。

    `stopwords`（可选）里的 token 直接跳过——residual 判据用它剔掉状态后缀/角色名
    这类无区分力的 token（见 `RESIDUAL_STOPWORDS`）。一个隐藏件名可能
    同时命中停用词和一个有效 token，这里跳过停用词后仍会返回有效 token。
    **部件词（如 `hood`）不进停用词**：会吞掉真阳性，改由 `RESIDUAL_EXEMPTIONS` 逐对豁免。
    """
    if not key_name:
        return None
    kn = str(key_name).lower()
    ktoks = tokens(kn)
    for nm in other_names:
        if not nm:
            continue
        rn = restore_path(nm) if "/" in str(nm) else str(nm)
        for t in tokens(rn) | tokens(nm):
            if not t:
                continue
            if stopwords and t.lower() in stopwords:
                continue
            if _is_cjk(t):
                if t in kn:
                    return t
            elif len(t) >= 3 and t in ktoks:
                return t
    return None


# ---------------------------------------------------------------------------
# 关键词 / 过滤规则
# ---------------------------------------------------------------------------

DEFAULT_EXPRESSION_KEYWORDS = [
    # 眨眼 / 眼动 / 眼型
    "blink", "eye", "eyelid", "eyelash", "look", "saccade", "wink", "pupil", "iris",
    # 眉 / 口 / 表情
    "brow", "mouth", "jaw", "viseme", "tongue", "teeth", "lip", "cheek", "nose",
    "smile", "frown", "angry", "sad", "happy", "relax", "surprised", "grin",
    "expression", "emote", "face",
    # 日文 / 中文 常见面部词
    "まばたき", "瞬き", "目", "口", "眉", "顔", "齿", "舌", "鼻", "頬",
]

DEFAULT_CLOTHING_ROOT_WORDS = [
    "cloth", "clothes", "clothing", "outfit", "wear", "apparel", "garment",
]

DEFAULT_CLOTHING_ITEM_WORDS = [
    "pants", "trouser", "skirt", "shirt", "blouse", "coat", "outer", "jacket",
    "hood", "hoodie", "parker", "sweater", "vest", "suit", "uniform", "sailor",
    "maid", "jersey", "culotte", "sock", "stocking", "shoe", "boot", "loafer",
    "sneaker", "glove", "bra", "panties", "underwear", "inner", "bandage",
    "gauze", "belt", "bag", "wing", "choker", "necltie", "necktie", "ribbon",
    "apron", "cape", "scarf", "beret", "drip", "cat",
]

DEFAULT_BODY_WORDS = ["body"]

DEFAULT_FOOT_KEY_WORDS = [
    "foot", "heel", "toe", "足", "ヒール", "つま先", "爪先",
]

DEFAULT_SHRINK_KEY_WORDS = [
    "shrink", "shlink", "縮", "収縮", "シュリンク",
]

DEFAULT_SHOE_PARAM_WORDS = [
    "shoe", "shoes", "sho", "boot", "loafer", "sneaker", "heel", "靴", "鞋", "ヒール",
]

DEFAULT_OUTFIT_RADIAL_WORDS = ["整套", "套装", "全身", "outfit", "set"]

DEFAULT_CLOTHING_PART_WORDS = [
    "部件", "鞋", "袜", "外套", "上衣", "下着", "内衣", "裙", "裤", "手套",
    "cloth", "outfit", "shoe", "sock", "coat", "top", "pants", "skirt", "bra", "inner",
]


def load_keyword_file(path, default):
    if not path:
        return list(default)
    obj = read_json(path)
    if isinstance(obj, list):
        return [str(x) for x in obj]
    if isinstance(obj, dict):
        for key in ("keywords", "words", "list"):
            if key in obj and isinstance(obj[key], list):
                return [str(x) for x in obj[key]]
    die("关键词文件格式不认识（应为 JSON 列表，或含 keywords/words/list 的对象）：%s" % path)


def match_any(text, words):
    """关键词匹配（用于服装/身体/脚型等分类）。

    * CJK 关键词按子串匹配（中文/日文无词边界）。
    * ASCII 关键词按「完整 token」匹配；长度 ≥4 时允许 token 以其为前缀
      （sock→Socks、boot→Boots、shoe→Shoes）。这样 "top" 不会误命中 "Stop"、
      "set" 不会误命中 "Seated"。
    """
    if not text:
        return None
    t = str(text).lower()
    ascii_tokens = set(_ASCII_TOKEN.findall(t))
    for w in words:
        if not w:
            continue
        wl = str(w).lower()
        if _is_cjk(wl):
            if wl in t:
                return w
            continue
        if wl in ascii_tokens:
            return w
        if len(wl) >= 4:
            for tok in ascii_tokens:
                if tok.startswith(wl):
                    return w
    return None


def is_expression_key(shape, words):
    return match_any(shape, words) is not None


def is_clothing_renderer(path, root_words, item_words):
    if not path:
        return False
    rp = restore_path(path)
    if match_any(rp, root_words):
        return True
    if match_any(leaf(rp), item_words):
        return True
    return False


# K12 残余误报的**显式豁免表**（只列已逐条复核过的对，不做泛化）。
#
# 背景：候选 (a) residual 的判据是「隐藏件 R 的 token 出现在一个仍在非零的键名里」。
# 工程C的 `O_maid_skirt` 与 `U_garter belt` 会和同套衣服里另一件（AAO 合并到同一网格）
# 的键共享套装名/通用词，纯 token 化消不掉；曾经用「键长在任何仍可见服装上就不计」
# 一条宽判据压掉，但那条太宽——它会把 工程A 里 `kaguya_cloth/sailor.outer_shlink`
# 这类**真阳性**（衣服上的收缩键没跟着外套关回基线）一并吞掉。所以改成只豁免下表里
# 逐条列出的对。
#
# 每条 = (隐藏件名片段, 形态键名片段, 出处)；两段都命中（大小写不敏感）才豁免。
# 复核说明：命中的键其实属于同套里另一件仍在可见的服装，不是被隐藏件留下的身体适配键。
# 出处：验收_20260919_AV至BB.md F-14；AZ 报告 F-14「拿不准/需后续」；
#       工程C矩阵 `_长程任务_20260918/派工/tmp/az/t5_xy_before/matrix.md`（maid 行 27/74、
#       belt 行 28/82；`O_maid_skirt` 隐藏时 `13_O_maid_breast__Corset` 仍 100，
#       `U_garter belt` 隐藏时 `13_U_breast_belt__Corset` 仍 100）。
# 维护：新误报要**先复核实**（键属哪件、是不是同套）再往这里加；不许改成前缀/正则式泛化。
RESIDUAL_EXEMPTIONS = [
    ("O_maid_skirt", "O_maid_breast__Corset",
     "验收_20260919_AV至BB.md F-14；工程C tmp/az/t5_xy_before/matrix.md:27,74"),
    ("U_garter belt", "U_breast_belt__Corset",
     "验收_20260919_AV至BB.md F-14；工程C tmp/az/t5_xy_before/matrix.md:28,82"),
    # 兜帽类：`hood` 是**部件词**，不能进全局停用词（会吞掉真兜帽类键），改用逐对豁免。
    # 出处：工程E `t1_sweep_out` 的 set3_repoppin__all——隐藏 `Re-Poppin' Cat_RURUNE/
    # (A)Hood_OFF` 时，仍可见的 `rurune_angel_enforcement_parka_blue/hood/hood` 上
    # `hood_.handcuffs_front`/`hood_.wide1` 仍非零；两件是不同的 hood，键属后者。
    # 证据：验收_20260919_BC至BH.md BE-T5；`派工/tmp/bn/easy_t5_final2/matrix.json`
    # 的 `candidates.residual_stopworded`（token=hood 2 条）。
    ("(A)Hood_OFF", "hood_.handcuffs_front",
     "验收_20260919_BC至BH.md BE-T5；tmp/bn/easy_t5_final2/matrix.json residual_stopworded"
     "（隐藏 Re-Poppin' Cat_RURUNE/(A)Hood_OFF，键在 rurune_angel_enforcement_parka_blue/hood/hood 上）"),
    ("(A)Hood_OFF", "hood_.wide1",
     "验收_20260919_BC至BH.md BE-T5；tmp/bn/easy_t5_final2/matrix.json residual_stopworded"
     "（同上门/键）"),
]


# residual 判据的 **token 停用词表**：这些 token 太泛，不能用来证明「非零键属于被隐藏的件」。
#
# 与 `RESIDUAL_EXEMPTIONS`（逐对豁免，须逐条复核）不同：这里按「通用 token」一刀切。
# **只收状态后缀与素体/角色名**这类无区分力的词；**不收部件词**（如 `hood`）——部件词
# 会吞掉真兜帽类键，改由 `RESIDUAL_EXEMPTIONS` 逐对豁免并写出处。
# 命中停用词而本来会被算作 residual 的，另列 matrix.md `a″`，不静默丢弃。
#
# 出处（本轮实跑）：`_长程任务_20260918/派工/tmp/bn/easy_t5_cur/`（工程E 的
# `t1_sweep_out` + `t1_sweep_request.json`）：去掉宽判据后 工程E residual 1→9，
# 9 条里 6 条命中 `rurune`、2 条命中 `hood`、1 条命中 `off`（验收_20260919_BC至BH.md
# F-14 记为「8 条新 token 误报」）。真阳性 `kaguya_cloth/sailor.outer_shlink`
# 命中 token `outer`，不在此表，仍会报出。
RESIDUAL_STOPWORDS = {
    "rurune": "素体/角色名（工程E 的 Rurune 素体）；`rurune/ear`、`Re-Poppin' Cat_RURUNE/…`、"
              "`rurune_angel_enforcement_parka_blue/…` 等所有件名都含它，无部件区分力。"
              "出处：验收_20260919_BC至BH.md F-14；tmp/bn/easy_t5_cur/matrix.json（6 条）。",
    "off": "开关状态后缀（`(A)Hood_OFF`、`h_all_off` 等），描述开关态而非部件身份。"
           "出处：同上（旧版 工程E 仅剩的 1 条 residual 即隐藏 `(A)Hood_OFF` → 键 `h_all_off`）。",
    "on": "同 `off`，开关状态后缀（`(A)Hood_ON`、`Outer_on` 等），无部件区分力。"
          "出处：与 `off` 同类，`(A)Hood_ON` 与 `(A)Hood_OFF` 成对出现。"
          "注：`on` 只有 2 字符，`name_relates` 的 ASCII 判据要求 ≥3 字符，本就匹配不到，"
          "此处保留仅作声明性兜底（验收_20260919_BC至BH.md 指出冗余）。",
}


def residual_exempt(hidden_name, shape_name):
    """命中豁免表则返回命中的 (隐藏件片段, 键片段)，否则 None。"""
    h = str(hidden_name or "").lower()
    s = str(shape_name or "").lower()
    for hf, sf, _src in RESIDUAL_EXEMPTIONS:
        if hf.lower() in h and sf.lower() in s:
            return (hf, sf)
    return None


def residual_stopword(token):
    """token 是否命中停用词表（大小写不敏感）；命中返回词条，否则 None。"""
    if not token:
        return None
    return RESIDUAL_STOPWORDS.get(str(token).lower())


def is_body_renderer(path, body_words):
    return match_any(restore_path(path), body_words) is not None


def is_foot_key(shape, words):
    return match_any(shape, words) is not None


def is_shrink_key(shape, words):
    return match_any(shape, words) is not None


def is_shoe_param(param, paths, words):
    if match_any(param, words):
        return True
    for p in paths or []:
        if match_any(p, words):
            return True
    return False


# ---------------------------------------------------------------------------
# 读 T4 params.json
# ---------------------------------------------------------------------------

def load_params(path):
    if not path:
        return {"parameters": [], "by_name": {}}
    obj = read_json(path)
    pars = obj.get("parameters") or []
    by_name = {}
    for p in pars:
        if isinstance(p, dict) and p.get("name"):
            by_name[p["name"]] = p
    obj["by_name"] = by_name
    return obj


def param_paths(pinfo):
    return (pinfo or {}).get("referenced_by") or []


def param_kinds(pinfo):
    return (pinfo or {}).get("menu_value_kinds") or []


def param_value_type(pinfo):
    return (pinfo or {}).get("value_type_name")


def param_default(pinfo):
    if pinfo and pinfo.get("declared_in_expression") and pinfo.get("default_value") is not None:
        return pinfo.get("default_value")
    return 0


def radial_float_params(params_obj, only_re=None, exclude_re=None):
    """Float 且被 radial 控件引用的参数（“轮盘”）。"""
    out = []
    for p in params_obj.get("parameters") or []:
        if not isinstance(p, dict):
            continue
        if param_value_type(p) != "Float":
            continue
        if "radial" not in param_kinds(p):
            continue
        name = p.get("name")
        if not name:
            continue
        if only_re and not re.search(only_re, name):
            continue
        if exclude_re and re.search(exclude_re, name):
            continue
        out.append(p)
    out.sort(key=lambda x: x["name"])
    return out


# ---------------------------------------------------------------------------
# T1 输出读取
# ---------------------------------------------------------------------------

class T1Run(object):
    def __init__(self, t1_dir):
        self.dir = t1_dir
        self.states = {}          # id -> snapshot dict
        self.epsilon = 1e-4
        self.volatile = []        # [(renderer, shape)]
        self.states_json = {}
        self.warnings = []
        self._load()

    def _load(self):
        sj = os.path.join(self.dir, "states.json")
        if os.path.exists(sj):
            try:
                self.states_json = read_json(sj)
            except Exception as e:
                self.warnings.append("states.json 读取失败：%s" % e)
        eps = self.states_json.get("blendshape_epsilon")
        if isinstance(eps, (int, float)) and eps > 0:
            self.epsilon = float(eps)
        for item in self.states_json.get("volatile_blendshapes") or []:
            if isinstance(item, dict) and item.get("path") and item.get("shape"):
                self.volatile.append((item["path"], item["shape"]))
        ids = list(self.states_json.get("states") or [])
        if not ids:
            for f in sorted(glob.glob(os.path.join(self.dir, "state_*.json"))):
                base = os.path.basename(f)[len("state_"):-len(".json")]
                if base.endswith(".repeat"):
                    continue
                ids.append(base)
        for sid in ids:
            f = os.path.join(self.dir, "state_%s.json" % sid)
            if not os.path.exists(f):
                self.warnings.append("缺少 state_%s.json" % sid)
                continue
            try:
                self.states[sid] = read_json(f)
            except Exception as e:
                self.warnings.append("state_%s.json 读取失败：%s" % (sid, e))

    def snapshot(self, sid):
        """返回 (visible_set, blendshape_dict{(renderer,shape): value})。

        blendshape_dict 只收 |值| > epsilon 的键；volatile（自动播放的面部键）在 analyze 里
        另外按需排除，这里保留原始值。
        """
        st = self.states[sid]
        vis = set()
        for r in st.get("renderers") or []:
            if r.get("visible"):
                vis.add(r.get("path"))
        bs = {}
        for rp, dd in (st.get("blendshapes") or {}).items():
            if not isinstance(dd, dict):
                continue
            for shape, val in dd.items():
                fv = fnum(val)
                if fv is None:
                    continue
                if abs(fv) > self.epsilon:
                    bs[(rp, shape)] = fv
        return vis, bs

    def params_of(self, sid):
        st = self.states.get(sid) or {}
        applied = st.get("params_applied")
        if isinstance(applied, dict) and applied:
            return applied
        return {}


# ---------------------------------------------------------------------------
# 子命令 1：slots
# ---------------------------------------------------------------------------

def parse_step(spec):
    """`1/64` 或 `0.015625` → (step_float, 显示串, 分数分子分母或 None)。"""
    spec = str(spec).strip()
    if "/" in spec:
        a, b = spec.split("/", 1)
        num, den = int(a), int(b)
        if den <= 0:
            die("--step 分母必须为正：%s" % spec)
        return float(num) / float(den), spec, (num, den)
    val = float(spec)
    if not (0 < val <= 1):
        die("--step 必须在 (0,1] 内：%s" % spec)
    return val, spec, None


def slot_values(step, frac):
    if frac:
        num, den = frac
        vals = [round6(num * i / float(den)) for i in range(0, den + 1)]
    else:
        n = int(round(1.0 / step))
        if n < 1:
            die("--step 太大，扫不出两个点：%s" % step)
        vals = [round6(i * step) for i in range(0, n + 1)]
    # 去重 & 保证首尾
    out = []
    for v in vals:
        if not out or abs(v - out[-1]) > 1e-9:
            out.append(v)
    if out[0] != 0.0:
        out.insert(0, 0.0)
    if out[-1] != 1.0:
        out.append(1.0)
    return out


def cmd_slots(args):
    step, step_spec, frac = parse_step(args.step)
    params_obj = load_params(args.params)
    radials = radial_float_params(params_obj, args.only, args.exclude)
    if not radials:
        die("params.json 里没有 Float + radial 参数（--only/--exclude 是否把参数滤没了？）")

    values = slot_values(step, frac)
    states = []
    slots = []
    for p in radials:
        name = p["name"]
        san = sanitize(name)
        ids = []
        for i, v in enumerate(values):
            sid = "slot__%s__%03d" % (san, i)
            states.append({"id": sid, "params": {name: v}})
            ids.append(sid)
        labels = [x for x in (p.get("radial_labels") or [])]
        slots.append({
            "param": name,
            "state_id_prefix": "slot__%s__" % san,
            "step": step,
            "values": values,
            "state_ids": ids,
            "labels": labels,
            "label_count": len(labels) if labels else None,
            "menu_paths": param_paths(p),
            "value_type": param_value_type(p),
            "menu_value_kinds": param_kinds(p),
            "menu_values": p.get("menu_values") or [],
            "suggested_values": p.get("suggested_values") or [],
        })

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    request = {
        "tool": "state",
        "avatar": args.avatar,
        "out": out_dir,
        "settle_frames": int(args.settle_frames),
        "volatile_probe": False,
        "track_bones": ["Hips", "LeftFoot", "RightFoot", "LeftToes", "RightToes", "Head"],
        "states": states,
    }
    plan = {
        "tool": TOOL + ".slots",
        "generated_at": now_str(),
        "params_file": os.path.abspath(args.params),
        "step_spec": step_spec,
        "step": step,
        "avatar": args.avatar,
        "state_count": len(states),
        "radial_count": len(radials),
        "values": values,
        "slots": slots,
        "warnings": [],
    }
    if len(states) > 2000:
        plan["warnings"].append(
            "状态数 %d 偏大（%d 个轮盘 × %d 个取值）；T1 跑一轮会很慢，建议先用较粗的 --step 试跑。"
            % (len(states), len(radials), len(values)))
    req_path = os.path.join(out_dir, "t1_request_slots.json")
    plan_path = os.path.join(out_dir, "slots_plan.json")
    write_json(req_path, request)
    write_json(plan_path, plan)
    print("[T5 slots] 轮盘参数 %d 个，每个 %d 个取值（step=%s），共 %d 个状态。"
          % (len(radials), len(values), step_spec, len(states)))
    print("  T1 请求：%s  （复制到 <工程>/Library/AvatarAudit/request.json 后跑 T1）" % req_path)
    print("  扫描计划：%s  （slots-reduce 会回来读它）" % plan_path)
    for w in plan["warnings"]:
        eprint("[T5 slots] 警告：" + w)


# ---------------------------------------------------------------------------
# 子命令 2：slots-reduce
# ---------------------------------------------------------------------------

def signature_of(vis, bs):
    return (tuple(sorted(vis)), tuple(sorted(bs.keys())))


def cmd_slots_reduce(args):
    t1_dir = os.path.abspath(args.t1)
    if not os.path.isdir(t1_dir):
        die("--t1 不是目录：%s" % t1_dir)
    run = T1Run(t1_dir)

    plan = None
    plan_path = os.path.join(t1_dir, "slots_plan.json")
    if os.path.exists(plan_path):
        plan = read_json(plan_path)
    elif args.params:
        # 允许从 params.json 现场重建一个「计划」（无 state_ids，用命名约定推）
        params_obj = load_params(args.params)
        step, step_spec, frac = parse_step(args.step)
        values = slot_values(step, frac)
        plan = {"step": step, "step_spec": step_spec, "values": values, "slots": []}
        for p in radial_float_params(params_obj, args.only, args.exclude):
            name = p["name"]
            san = sanitize(name)
            plan["slots"].append({
                "param": name,
                "state_id_prefix": "slot__%s__" % san,
                "values": values,
                "state_ids": ["slot__%s__%03d" % (san, i) for i in range(len(values))],
                "labels": p.get("radial_labels") or [],
                "label_count": len(p.get("radial_labels") or []) or None,
                "menu_paths": param_paths(p),
            })
    if not plan or not plan.get("slots"):
        die("既没找到 %s，也没有可用的 --params 来重建扫描计划" % plan_path)

    step = plan.get("step") or parse_step(args.step)[0]
    out = {
        "tool": TOOL + ".slots-reduce",
        "generated_at": now_str(),
        "t1_dir": t1_dir,
        "plan_file": plan_path if os.path.exists(plan_path) else None,
        "step": step,
        "step_spec": plan.get("step_spec"),
        "epsilon": run.epsilon,
        "slots": {},
        "warnings": list(run.warnings),
    }

    for slot in plan.get("slots") or []:
        name = slot.get("param")
        values = slot.get("values") or []
        ids = slot.get("state_ids") or []
        entry = {
            "param": name,
            "labels": slot.get("labels") or [],
            "label_count": slot.get("label_count"),
            "menu_paths": slot.get("menu_paths") or [],
            "interval_count": 0,
            "label_mismatch": None,
            "intervals": [],
            "warnings": [],
        }
        # 逐取值算签名
        sigs = []
        for idx, (sid, val) in enumerate(zip(ids, values)):
            if sid not in run.states:
                entry["warnings"].append("缺少状态 %s（第 %d 个取值 %s），该点断开不参与合并"
                                         % (sid, idx, fmt_val(val)))
                sigs.append(None)
                continue
            vis, bs = run.snapshot(sid)
            sigs.append((val, sid, vis, bs, signature_of(vis, bs)))

        # 合并相邻同签名
        intervals = []
        cur = None
        for item in sigs:
            if item is None:
                cur = None
                continue
            val, sid, vis, bs, sig = item
            if cur is not None and cur["sig"] == sig and len(cur["state_ids"]) > 0:
                cur["hi"] = val
                cur["state_ids"].append(sid)
                cur["_last_vis"] = vis
                cur["_last_bs"] = bs
            else:
                if cur is not None:
                    intervals.append(cur)
                cur = {
                    "lo": val, "hi": val, "sig": sig,
                    "state_ids": [sid],
                    "_first_vis": vis, "_last_vis": vis,
                    "_first_bs": bs, "_last_bs": bs,
                }
        if cur is not None:
            intervals.append(cur)

        prev_vis = None
        prev_bs = None
        for it in intervals:
            iv_vis = it["_last_vis"]
            iv_bs = it["_last_bs"]
            width = it["hi"] - it["lo"]
            appeared = sorted(set(restore_path(p) for p in iv_vis)) if prev_vis is None else \
                sorted(set(restore_path(p) for p in (iv_vis - prev_vis)))
            disappeared = [] if prev_vis is None else \
                sorted(set(restore_path(p) for p in (prev_vis - iv_vis)))
            entry["intervals"].append({
                "lo": round6(it["lo"]),
                "hi": round6(it["hi"]),
                "recommended": round6((it["lo"] + it["hi"]) / 2.0),
                "narrow": width < 2 * step - 1e-9,
                "value_count": len(it["state_ids"]),
                "state_ids": it["state_ids"],
                "visible_count": len(iv_vis),
                "nonzero_key_count": len(iv_bs),
                "appeared": appeared,
                "disappeared": disappeared,
                "signature": {
                    "visible": sorted(restore_path(p) for p in iv_vis),
                    "nonzero_keys": sorted("%s.%s" % (restore_path(r), s) for (r, s) in iv_bs),
                },
            })
            prev_vis = iv_vis
            prev_bs = iv_bs

        entry["interval_count"] = len(entry["intervals"])
        lc = entry.get("label_count")
        if lc is not None and lc > 0 and entry["interval_count"] != lc:
            entry["label_mismatch"] = "区间数 %d ≠ 菜单 labels 数 %d" % (entry["interval_count"], lc)
        out["slots"][name] = entry

    out_path = os.path.abspath(args.out)
    write_json(out_path, out)
    total_iv = sum(v["interval_count"] for v in out["slots"].values())
    narrow = sum(1 for v in out["slots"].values() for iv in v["intervals"] if iv["narrow"])
    mism = [k for k, v in out["slots"].items() if v.get("label_mismatch")]
    print("[T5 slots-reduce] %d 个轮盘 → 共 %d 个区间（其中 narrow %d 个）。"
          % (len(out["slots"]), total_iv, narrow))
    if mism:
        print("  labels 数量不一致：%s" % "，".join(mism))
    print("  输出：%s" % out_path)


# ---------------------------------------------------------------------------
# 子命令 3：sweep
# ---------------------------------------------------------------------------

def infer_groups(params_obj):
    """按菜单路径推断「整套轮盘」与「服装部位 Bool」，并返回证据。"""
    outfit_radials, clothing_bools = [], []
    evidence = {}
    notes = []
    for name, p in sorted(params_obj.get("by_name", {}).items()):
        vt = param_value_type(p)
        paths = param_paths(p)
        joined = " | ".join(paths)
        if vt == "Float" and "radial" in param_kinds(p):
            w = match_any(joined, DEFAULT_OUTFIT_RADIAL_WORDS) or match_any(name, DEFAULT_OUTFIT_RADIAL_WORDS)
            if w:
                outfit_radials.append(name)
                evidence[name] = "Float 轮盘，路径/名匹配「%s」" % w
        elif vt == "Bool":
            w = match_any(joined, DEFAULT_CLOTHING_PART_WORDS) or match_any(name, DEFAULT_CLOTHING_PART_WORDS)
            if w:
                clothing_bools.append(name)
                evidence[name] = "Bool，路径/名匹配「%s」" % w
    if not outfit_radials and clothing_bools:
        notes.append("没推断出「整套」轮盘；如需按整套生成状态，请在 groups.json 里显式指定 outfit_radials。")
    if not clothing_bools:
        notes.append("没推断出「服装部位」Bool；请在 groups.json 里显式指定 clothing_bools。")
    return outfit_radials, clothing_bools, evidence, notes


def load_groups(args, params_obj):
    if args.groups:
        g = read_json(args.groups)
        outfit = g.get("outfit_radials") or g.get("outfit_sets") or g.get("整套") or []
        cloth = g.get("clothing_bools") or g.get("clothing_parts") or g.get("服装部位") or []
        notes = list(g.get("notes") or [])
        evidence = {k: "groups.json 指定" for k in list(outfit) + list(cloth)}
        return {
            "source": os.path.abspath(args.groups),
            "outfit_radials": [str(x) for x in outfit],
            "clothing_bools": [str(x) for x in cloth],
            "defaults": g.get("defaults") or g.get("default_params") or {},
            "evidence": evidence,
            "notes": notes,
            "all_radials": [p["name"] for p in radial_float_params(params_obj)],
            "all_bools": sorted(n for n, p in params_obj.get("by_name", {}).items()
                                if param_value_type(p) == "Bool"),
        }
    outfit, cloth, evidence, notes = infer_groups(params_obj)
    return {
        "source": "inferred",
        "outfit_radials": outfit,
        "clothing_bools": cloth,
        "defaults": {},
        "evidence": evidence,
        "notes": notes + ["以下分组是按菜单路径关键词推断的，请人工确认；不对就用 --groups groups.json 覆盖。"],
        "all_radials": [p["name"] for p in radial_float_params(params_obj)],
        "all_bools": sorted(n for n, p in params_obj.get("by_name", {}).items()
                            if param_value_type(p) == "Bool"),
    }


def load_slots(path):
    obj = read_json(path)
    slots = obj.get("slots")
    result = {}
    if isinstance(slots, dict):
        for k, v in slots.items():
            result[k] = v
    elif isinstance(slots, list):
        for v in slots:
            if isinstance(v, dict) and v.get("param"):
                result[v["param"]] = v
    else:
        die("slots.json 里的 slots 既不是对象也不是列表：%s" % path)
    return result


def cmd_sweep(args):
    params_obj = load_params(args.params)
    slots = load_slots(args.slots)
    groups = load_groups(args, params_obj)
    outfit_radials = [x for x in groups["outfit_radials"]]
    clothing_bools = [x for x in groups["clothing_bools"]]

    states = [{"id": "default", "params": {}}]
    plan = {"tool": TOOL + ".sweep", "generated_at": now_str(), "sets": [], "other_bools": [], "other_radials": []}

    def add(sid, params):
        params = {k: v for k, v in params.items()}
        states.append({"id": sid, "params": params})

    # 1) 整套/服装轮盘：每个区间 → 全开 + 单关 + 全关
    for si, rname in enumerate(outfit_radials):
        entry = slots.get(rname) or {}
        intervals = entry.get("intervals") or []
        recs = [iv.get("recommended") for iv in intervals]
        if not recs:
            recs = [0.0]
            plan.setdefault("warnings", []).append(
                "轮盘 %s 在 slots.json 里没有区间，退化为只取 0。" % rname)
        plan["sets"].append({"index": si, "param": rname, "recommended": recs,
                             "interval_count": len(recs)})
        for ii, val in enumerate(recs):
            tag = "set%d" % si
            base = {rname: val}
            for b in clothing_bools:
                base[b] = 1
            add("%s__all" % tag, base)
            for b in clothing_bools:
                p2 = dict(base)
                p2[b] = 0
                add("%s__%s_off" % (tag, sanitize(b)), p2)
            p2 = dict(base)
            for b in clothing_bools:
                p2[b] = 0
            add("%s__naked" % tag, p2)

    # 2) 其余 Bool：默认态下单独翻转
    other_bools = [b for b in groups["all_bools"] if b not in clothing_bools]
    for b in other_bools:
        pinfo = params_obj.get("by_name", {}).get(b)
        cur = param_default(pinfo)
        fv = fnum(cur)
        newv = 0 if (fv is None or fv == 0) else 1
        add("bool__%s__%s" % (sanitize(b), "on" if newv == 1 else "off"), {b: newv})
        plan["other_bools"].append({"param": b, "from": cur, "to": newv})

    # 3) 其余轮盘：默认态下取每个区间推荐值
    other_radials = [r for r in groups["all_radials"] if r not in outfit_radials]
    for r in other_radials:
        entry = slots.get(r) or {}
        intervals = entry.get("intervals") or []
        recs = [iv.get("recommended") for iv in intervals]
        if not recs:
            continue
        for ii, val in enumerate(recs):
            add("radial__%s__%02d" % (sanitize(r), ii), {r: val})
        plan["other_radials"].append({"param": r, "recommended": recs})

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    request = {
        "tool": "state",
        "avatar": args.avatar,
        "out": out_dir,
        "settle_frames": int(args.settle_frames),
        "volatile_probe": False,
        "track_bones": ["Hips", "LeftFoot", "RightFoot", "LeftToes", "RightToes", "Head"],
        "states": states,
    }
    plan.update({
        "params_file": os.path.abspath(args.params),
        "slots_file": os.path.abspath(args.slots),
        "groups": groups,
        "clothing_bools": clothing_bools,
        "outfit_radials": outfit_radials,
        "state_count": len(states),
        "state_ids": [s["id"] for s in states],
    })
    req_path = os.path.join(out_dir, "t1_request_sweep.json")
    grp_path = os.path.join(out_dir, "groups_used.json")
    write_json(req_path, request)
    write_json(grp_path, plan)

    print("[T5 sweep] 整套轮盘 %d 个、服装部位 Bool %d 个、其余 Bool %d 个、其余轮盘 %d 个 → 共 %d 个状态。"
          % (len(outfit_radials), len(clothing_bools), len(other_bools), len(other_radials), len(states)))
    print("  分组来源：%s" % groups["source"])
    print("  T1 请求：%s" % req_path)
    print("  分组与计划（请人工确认）：%s" % grp_path)
    for n in groups.get("notes") or []:
        print("  注意：" + n)


# ---------------------------------------------------------------------------
# 子命令 4：analyze
# ---------------------------------------------------------------------------

def load_sweep(path):
    obj = read_json(path)
    states = obj.get("states")
    if not isinstance(states, list):
        die("--sweep 请求里没有 states 列表：%s" % path)
    out = []
    for st in states:
        if isinstance(st, dict) and st.get("id") is not None:
            out.append({"id": st["id"], "params": st.get("params") or {}})
    return obj, out


def classify_bools(states):
    vals = {}
    for st in states:
        for k, v in (st.get("params") or {}).items():
            vals.setdefault(k, set()).add(fnum(v))
    bools = set()
    for k, vs in vals.items():
        vs2 = set(x for x in vs if x is not None)
        if vs2 and vs2 <= {0.0, 1.0} and len(vs2) <= 2:
            bools.add(k)
    return bools


def find_single_offs(base_params, states, bools):
    out = []
    bs = set(base_params.keys())
    for st in states:
        sp = st.get("params") or {}
        if set(sp.keys()) != bs:
            continue
        diff = [k for k in sp if fnum(sp[k]) != fnum(base_params[k])]
        if len(diff) != 1:
            continue
        k = diff[0]
        if k not in bools:
            continue
        if fnum(sp[k]) == 0.0 and fnum(base_params[k]) == 1.0:
            out.append((st["id"], k))
    out.sort()
    return out


def find_naked(base_params, states, bools, exclude_ids):
    nonbool = {k: fnum(v) for k, v in base_params.items() if k not in bools}
    for st in states:
        if st["id"] in exclude_ids:
            continue
        sp = st.get("params") or {}
        if set(sp.keys()) != set(base_params.keys()):
            continue
        if any(fnum(sp.get(k)) != v for k, v in nonbool.items()):
            continue
        present_bools = [k for k in sp if k in bools]
        if present_bools and all(fnum(sp[k]) == 0.0 for k in present_bools):
            return st["id"]
    return None


def key_display(renderer, shape):
    return {
        "renderer": renderer,
        "renderer_restored": restore_path(renderer),
        "shape": shape,
        "shape_restored": restore_shape(shape),
    }


def diff_snapshot(run, base_id, other_id, expression_words):
    bvis, bbs = run.snapshot(base_id)
    ovis, obs = run.snapshot(other_id)
    hidden = sorted(bvis - ovis)
    shown = sorted(ovis - bvis)
    changed = []
    for k in sorted(set(bbs) | set(obs)):
        a = bbs.get(k, 0.0)
        b = obs.get(k, 0.0)
        if abs(a - b) <= 1e-9:
            continue
        changed.append({
            "renderer": k[0],
            "renderer_restored": restore_path(k[0]),
            "shape": k[1],
            "shape_restored": restore_shape(k[1]),
            "from": a,
            "to": b,
            "expression": is_expression_key(restore_shape(k[1]) or k[1], expression_words),
        })
    nonzero = []
    for k in sorted(bbs):
        sr = restore_shape(k[1]) or k[1]
        if is_expression_key(sr, expression_words):
            continue
        nonzero.append({
            "renderer": k[0],
            "renderer_restored": restore_path(k[0]),
            "shape": k[1],
            "shape_restored": sr,
            "value": bbs[k],
        })
    return {
        "hidden": hidden,
        "hidden_restored": [restore_path(p) for p in hidden],
        "shown": shown,
        "shown_restored": [restore_path(p) for p in shown],
        "key_changes": changed,
        "nonzero_keys": nonzero,
    }


def cmd_analyze(args):
    run = T1Run(os.path.abspath(args.t1))
    sweep_obj, sweep_states = load_sweep(args.sweep)

    expression_words = load_keyword_file(args.filter_file, DEFAULT_EXPRESSION_KEYWORDS)
    clothing_roots = load_keyword_file(args.clothing_roots_file, DEFAULT_CLOTHING_ROOT_WORDS)
    clothing_items = load_keyword_file(args.clothing_keywords_file, DEFAULT_CLOTHING_ITEM_WORDS)
    body_words = load_keyword_file(args.body_words_file, DEFAULT_BODY_WORDS)
    foot_words = load_keyword_file(args.foot_keywords_file, DEFAULT_FOOT_KEY_WORDS)
    shrink_words = load_keyword_file(args.shrink_keywords_file, DEFAULT_SHRINK_KEY_WORDS)
    shoe_words = load_keyword_file(args.shoe_keywords_file, DEFAULT_SHOE_PARAM_WORDS)

    by_name = load_params(args.params).get("by_name", {})

    bools = classify_bools(sweep_states)
    # state 里的 params 以请求为准；请求缺失时用 state 文件 params_applied 兜底
    for st in sweep_states:
        if not st["params"]:
            applied = run.params_of(st["id"])
            if applied:
                st["params"] = applied

    # 单关关系
    children = {}   # base_id -> [(child_id, param)]
    for st in sweep_states:
        ch = find_single_offs(st.get("params") or {}, sweep_states, bools)
        if ch:
            children[st["id"]] = ch
    all_child_ids = set(cid for ch in children.values() for cid, _ in ch)

    baselines = []
    for st in sweep_states:
        if st["id"] in children and st["id"] not in all_child_ids:
            baselines.append(st)

    if not baselines:
        die("没有识别出任何「基准态」。检查 --sweep 里的 states：基准态需与单关态参数键相同、"
            "只差一个 Bool 从 1→0。")

    cand_residual = []
    cand_residual_exempt = []
    cand_residual_stopworded = []
    cand_misbound = []
    cand_nobody = []
    cand_unexpected = []
    cand_range = []

    warnings = list(run.warnings)

    baseline_reports = []
    for st in baselines:
        bid = st["id"]
        bparams = st.get("params") or {}
        bvis, bbs = run.snapshot(bid) if bid in run.states else (set(), {})
        if bid not in run.states:
            warnings.append("基准态 %s 没有对应的 state 文件，跳过。" % bid)
            continue

        clothing_visible = sorted(p for p in bvis if is_clothing_renderer(p, clothing_roots, clothing_items))
        rep = {
            "id": bid,
            "params": bparams,
            "visible_renderer_count": len(bvis),
            "visible_clothing": [{"path": p, "restored": restore_path(p), "leaf": leaf(restore_path(p))}
                                 for p in clothing_visible],
            "visible_clothing_count": len(clothing_visible),
            "nonzero_keys": [],
            "single_off": [],
            "naked": None,
        }
        for k in sorted(bbs):
            sr = restore_shape(k[1]) or k[1]
            if is_expression_key(sr, expression_words):
                continue
            rep["nonzero_keys"].append({
                "renderer": k[0], "renderer_restored": restore_path(k[0]),
                "shape": k[1], "shape_restored": sr, "value": bbs[k],
            })

        # (c) 基准态：可见服装件 > N 但身体无收缩/脚型键
        body_shrink_foot = []
        for k in bbs:
            sr = restore_shape(k[1]) or k[1]
            if not is_body_renderer(k[0], body_words):
                continue
            if is_shrink_key(sr, shrink_words) or is_foot_key(sr, foot_words):
                body_shrink_foot.append({
                    "renderer": k[0], "renderer_restored": restore_path(k[0]),
                    "shape": k[1], "shape_restored": sr, "value": bbs[k],
                })
        rep["body_shrink_foot_keys"] = body_shrink_foot
        if len(clothing_visible) > args.n_clothing and not body_shrink_foot:
            cand_nobody.append({
                "rule": "no_body_keys",
                "baseline": bid,
                "visible_clothing_count": len(clothing_visible),
                "threshold": args.n_clothing,
                "visible_clothing": [restore_path(p) for p in clothing_visible],
                "detail": "可见服装件 %d 件（>%d）但身体渲染器上没有任何收缩/脚型键。"
                          % (len(clothing_visible), args.n_clothing),
            })

        # 每个单关态
        shoe_child_ids = set()
        for cid, cparam in children.get(bid, []):
            if is_shoe_param(cparam, param_paths(by_name.get(cparam)), shoe_words):
                shoe_child_ids.add(cid)

        for cid, cparam in children.get(bid, []):
            if cid not in run.states:
                continue
            d = diff_snapshot(run, bid, cid, expression_words)
            item = {
                "id": cid,
                "param": cparam,
                "hidden": d["hidden"], "hidden_restored": d["hidden_restored"],
                "shown": d["shown"], "shown_restored": d["shown_restored"],
                "key_changes": d["key_changes"],
            }
            rep["single_off"].append(item)

            hidden_names = list(d["hidden"]) + list(d["hidden_restored"])
            param_names = [cparam] + list(param_paths(by_name.get(cparam)))

            # (e) 越界：任何键值 <0 或 >100
            _, obs = run.snapshot(cid)
            for k, v in sorted(obs.items()):
                if v < -1e-9 or v > 100 + 1e-9:
                    cand_range.append({
                        "rule": "out_of_range", "baseline": bid, "state": cid,
                        "renderer": k[0], "renderer_restored": restore_path(k[0]),
                        "shape": k[1], "shape_restored": restore_shape(k[1]), "value": v,
                        "detail": "形态键值 %s 超出 VRChat 客户端钳制范围 [0,100]。" % fmt_val(v),
                    })

            changed_foot = []
            changed_shrink = []
            for ch in d["key_changes"]:
                sr = ch["shape_restored"] or ch["shape"]
                if is_expression_key(sr, expression_words):
                    continue
                if is_foot_key(sr, foot_words):
                    changed_foot.append(ch)
                if is_shrink_key(sr, shrink_words):
                    changed_shrink.append(ch)

            # (a) residual：渲染器被隐藏，但名字与它相关的键仍非零（且该键不在被隐藏的渲染器上）
            for hp in d["hidden"]:
                hset = set(d["hidden"]) | set(d["hidden_restored"])
                for k, v in sorted(obs.items()):
                    sr = restore_shape(k[1]) or k[1]
                    if is_expression_key(sr, expression_words):
                        continue
                    if k[0] in hset:
                        continue  # 键就长在被隐藏的物体上，属无害残留，不计
                    # K12：不用「键长在任何仍可见服装上就不计」这条宽判据——它会把
                    # 「衣服上的收缩键」真阳性（工程A `kaguya_cloth/sailor.outer_shlink`
                    # 这类）也一起吞掉。残余误报改由显式豁免表逐条处理（RESIDUAL_EXEMPTIONS）。
                    raw_tok = name_relates(sr, [hp])
                    tok = name_relates(sr, [hp], RESIDUAL_STOPWORDS)
                    if raw_tok and residual_stopword(raw_tok) and not tok:
                        # 唯一关联 token 是通用停用词（状态后缀/素体名/跨件部件词），
                        # 不足以证明键属于被隐藏件；另列 a″，不静默丢弃。
                        cand_residual_stopworded.append({
                            "baseline": bid, "state": cid, "param": cparam,
                            "hidden_renderer": hp, "hidden_renderer_restored": restore_path(hp),
                            "key_renderer": k[0], "key_renderer_restored": restore_path(k[0]),
                            "shape": k[1], "shape_restored": sr, "value": v, "token": raw_tok,
                            "detail": "隐藏 %s 时 %s 上的键 %s 仍为 %s，但唯一关联 token「%s」"
                                      "在 RESIDUAL_STOPWORDS 里（%s）→ 不计 residual。"
                                      % (restore_path(hp), restore_path(k[0]), sr, fmt_val(v),
                                         raw_tok, RESIDUAL_STOPWORDS.get(str(raw_tok).lower(), "")),
                        })
                        continue
                    if tok:
                        ex = residual_exempt(restore_path(hp), sr) or residual_exempt(hp, sr)
                        if ex:
                            cand_residual_exempt.append({
                                "baseline": bid, "state": cid, "param": cparam,
                                "hidden_renderer": hp, "hidden_renderer_restored": restore_path(hp),
                                "key_renderer": k[0], "key_renderer_restored": restore_path(k[0]),
                                "shape": k[1], "shape_restored": sr, "value": v, "token": tok,
                                "exempt": "%s ~ %s" % ex,
                                "detail": "命中 K12 豁免表：隐藏 %s 时 %s 上的键 %s 仍为 %s；"
                                          "该键属同套里另一件可见服装（出处见 RESIDUAL_EXEMPTIONS）。"
                                          % (restore_path(hp), restore_path(k[0]), sr, fmt_val(v)),
                            })
                            continue
                        cand_residual.append({
                            "rule": "residual", "baseline": bid, "state": cid, "param": cparam,
                            "hidden_renderer": hp, "hidden_renderer_restored": restore_path(hp),
                            "key_renderer": k[0], "key_renderer_restored": restore_path(k[0]),
                            "shape": k[1], "shape_restored": sr, "value": v, "token": tok,
                            "detail": "隐藏了 %s，但键 %s 仍为 %s（键名含 token「%s」）。"
                                      % (restore_path(hp), sr, fmt_val(v), tok),
                        })

            # (b1) 脚型/鞋跟键跟着非鞋开关走
            if changed_foot and not is_shoe_param(cparam, param_paths(by_name.get(cparam)), shoe_words):
                # 基准态自己的「关鞋」子态里，这些脚型键应不变；查一下作为佐证
                shoe_unchanged = None
                for scid in sorted(shoe_child_ids):
                    if scid not in run.states:
                        continue
                    sd = diff_snapshot(run, bid, scid, expression_words)
                    foot_changed_in_shoe = [c for c in sd["key_changes"]
                                            if is_foot_key(c["shape_restored"] or c["shape"], foot_words)]
                    shoe_unchanged = (len(foot_changed_in_shoe) == 0)
                    break
                cand_misbound.append({
                    "rule": "mis_bound.foot", "baseline": bid, "state": cid, "param": cparam,
                    "keys": [dict(k, kind="foot") for k in changed_foot],
                    "shoe_switch": sorted(shoe_child_ids),
                    "foot_key_unchanged_when_shoe_off": shoe_unchanged,
                    "detail": "脚型/鞋跟键 %s 跟着非鞋开关 %s 变化%s。"
                              % ("、".join(c["shape_restored"] or c["shape"] for c in changed_foot),
                                 cparam,
                                 "；且关鞋时这些键不变" if shoe_unchanged else ""),
                })

            # (b2) 收缩类键跟着不相关的开关走（既不对应被隐藏物体，也不对应参数名）
            for ch in changed_shrink:
                sr = ch["shape_restored"] or ch["shape"]
                if not name_relates(sr, hidden_names) and not name_relates(sr, param_names):
                    cand_misbound.append({
                        "rule": "mis_bound.shrink", "baseline": bid, "state": cid, "param": cparam,
                        "keys": [dict(ch, kind="shrink")],
                        "detail": "收缩类键 %s 跟着与之不相关的开关 %s 变化（隐藏物体：%s）。"
                                  % (sr, cparam, "、".join(d["hidden_restored"]) or "无"),
                    })

            # (d) 关一件衣服时，无关的其他“可见服装件”形态键发生变化
            clothing_set = set(clothing_visible)
            hidden_set = set(d["hidden"])
            for ch in d["key_changes"]:
                sr = ch["shape_restored"] or ch["shape"]
                if is_expression_key(sr, expression_words):
                    continue
                if is_foot_key(sr, foot_words) or is_shrink_key(sr, shrink_words):
                    continue  # 脚型/收缩类已归入 b
                kr = ch["renderer"]
                if kr not in clothing_set or kr in hidden_set:
                    continue
                if name_relates(sr, hidden_names) or name_relates(sr, param_names):
                    continue
                cand_unexpected.append({
                    "rule": "unexpected_change", "baseline": bid, "state": cid, "param": cparam,
                    "changed": ch, "detail": "关 %s 时，无关的可见服装件 %s 上的键 %s 从 %s 变为 %s。"
                    % (cparam, restore_path(kr), sr, fmt_val(ch["from"]), fmt_val(ch["to"])),
                })

        # 全关态
        naked_id = find_naked(bparams, sweep_states, bools,
                              exclude_ids=[cid for cid, _ in children.get(bid, [])])
        if naked_id and naked_id in run.states:
            d = diff_snapshot(run, bid, naked_id, expression_words)
            rep["naked"] = {
                "id": naked_id, "hidden": d["hidden"], "hidden_restored": d["hidden_restored"],
                "shown": d["shown"], "shown_restored": d["shown_restored"],
                "key_changes": d["key_changes"],
            }
            _, nbs = run.snapshot(naked_id)
            for k, v in sorted(nbs.items()):
                if v < -1e-9 or v > 100 + 1e-9:
                    cand_range.append({
                        "rule": "out_of_range", "baseline": bid, "state": naked_id,
                        "renderer": k[0], "renderer_restored": restore_path(k[0]),
                        "shape": k[1], "shape_restored": restore_shape(k[1]), "value": v,
                        "detail": "形态键值 %s 超出 [0,100]。" % fmt_val(v),
                    })

        baseline_reports.append(rep)

    # 全域越界扫描：把每个 state 都扫一遍，避免漏掉非基准/非单关的状态
    for sid in sorted(run.states):
        if sid in all_child_ids:
            continue
        _, bs = run.snapshot(sid)
        for k, v in sorted(bs.items()):
            if v < -1e-9 or v > 100 + 1e-9:
                key = (sid, k[0], k[1])
                if any(c.get("state") == sid and c.get("renderer") == k[0] and c.get("shape") == k[1]
                       for c in cand_range):
                    continue
                cand_range.append({
                    "rule": "out_of_range", "state": sid,
                    "renderer": k[0], "renderer_restored": restore_path(k[0]),
                    "shape": k[1], "shape_restored": restore_shape(k[1]), "value": v,
                    "detail": "形态键值 %s 超出 [0,100]。" % fmt_val(v),
                })

    matrix = {
        "tool": TOOL + ".analyze",
        "generated_at": now_str(),
        "t1_dir": os.path.abspath(args.t1),
        "sweep": os.path.abspath(args.sweep),
        "avatar": sweep_obj.get("avatar"),
        "epsilon": run.epsilon,
        "bools": sorted(bools),
        "filters": {
            "expression_keywords": expression_words,
            "clothing_root_words": clothing_roots,
            "clothing_item_words": clothing_items,
            "body_words": body_words,
            "foot_keywords": foot_words,
            "shrink_keywords": shrink_words,
            "shoe_keywords": shoe_words,
            "n_clothing": args.n_clothing,
            "residual_stopwords": sorted(RESIDUAL_STOPWORDS),
        },
        "state_count": len(run.states),
        "baseline_count": len(baseline_reports),
        "baselines": baseline_reports,
        "candidates": {
            "residual": cand_residual,
            "residual_exempted": cand_residual_exempt,
            "residual_stopworded": cand_residual_stopworded,
            "mis_bound": cand_misbound,
            "no_body_keys": cand_nobody,
            "unexpected_change": cand_unexpected,
            "out_of_range": cand_range,
        },
        "warnings": warnings,
    }

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    matrix_path = os.path.join(out_dir, "matrix.json")
    md_path = os.path.join(out_dir, "matrix.md")
    write_json(matrix_path, matrix)
    write_text(md_path, render_markdown(matrix))

    print("[T5 analyze] 基准态 %d 个，读入状态 %d 个。" % (len(baseline_reports), len(run.states)))
    print("  候选：residual %d / mis_bound %d / no_body_keys %d / unexpected_change %d / out_of_range %d"
          % (len(cand_residual), len(cand_misbound), len(cand_nobody),
             len(cand_unexpected), len(cand_range)))
    print("  K12 豁免表命中（已在 residual 里扣除）：%d 条" % len(cand_residual_exempt))
    print("  residual 停用词命中（已在 residual 里扣除）：%d 条" % len(cand_residual_stopworded))
    print("  输出：%s , %s" % (matrix_path, md_path))
    for w in warnings:
        eprint("[T5 analyze] 警告：" + w)


# ---------------------------------------------------------------------------
# matrix.md 渲染
# ---------------------------------------------------------------------------

def _raw_restored(raw, restored):
    """报告里同时给 Play 构建后的原样名字和还原名。"""
    if not raw or raw == restored:
        return str(restored)
    return "%s（原名 %s）" % (restored, raw)


def _renderer_label(restored, raw):
    if not raw or raw == restored:
        return str(restored)
    return "%s（原 %s）" % (restored, raw)


def _change_list(changes):
    lines = []
    for c in changes:
        name = _raw_restored(c["shape"], c["shape_restored"])
        tag = "（表情类，已过滤）" if c.get("expression") else ""
        lines.append("- %s · %s: %s→%s%s"
                     % (c["renderer_restored"], name, fmt_val(c["from"]), fmt_val(c["to"]), tag))
    return lines


def _hidden_shown(restored_list, raw_list):
    """restored 与 raw 一一对应；同时给原名。"""
    parts = []
    for r, raw in zip(restored_list, raw_list):
        parts.append(_renderer_label(r, raw))
    return " | ".join(parts) or "（无）"


def render_markdown(m):
    L = []
    L.append("# 形态键依赖矩阵（T5 analyze）")
    L.append("")
    L.append("- 生成时间：%s" % m["generated_at"])
    L.append("- 头像：%s" % m.get("avatar"))
    L.append("- T1 输出：`%s`" % m["t1_dir"])
    L.append("- sweep 请求：`%s`" % m["sweep"])
    L.append("- 读入状态 %d 个，基准态 %d 个；blendshape_epsilon=%s"
             % (m["state_count"], m["baseline_count"], m["epsilon"]))
    L.append("- 判为 Bool 的参数：%s" % (", ".join(m["bools"]) or "（无）"))
    L.append("- 自动候选只给嫌疑人，判据见文末「候选规则」一节。")
    L.append("")

    for b in m["baselines"]:
        L.append("## 基准态 %s" % b["id"])
        L.append("")
        L.append("参数：`%s`" % json.dumps(b["params"], ensure_ascii=False, sort_keys=True))
        L.append("")
        L.append("可见服装件（%d）：%s"
                 % (b["visible_clothing_count"],
                    " | ".join(_renderer_label(x["restored"], x["path"])
                               for x in b["visible_clothing"]) or "（无）"))
        L.append("")
        L.append("非零形态键（已过滤表情/面捕类，%d）：" % len(b["nonzero_keys"]))
        if b["nonzero_keys"]:
            for k in b["nonzero_keys"]:
                L.append("- %s · %s = %s" % (k["renderer_restored"],
                                             _raw_restored(k["shape"], k["shape_restored"]),
                                             fmt_val(k["value"])))
        else:
            L.append("- （无）")
        L.append("")
        L.append("身体上的收缩/脚型键：%s"
                 % (" | ".join("%s.%s" % (k["renderer_restored"],
                                          _raw_restored(k["shape"], k["shape_restored"]))
                               for k in b["body_shrink_foot_keys"]) or "（无）"))
        L.append("")
        L.append("### 单关态")
        L.append("")
        if not b["single_off"]:
            L.append("- （无）")
            L.append("")
        for s in b["single_off"]:
            L.append("#### [%s off] %s（%s: 1→0）" % (s["param"], s["id"], s["param"]))
            L.append("")
            L.append("隐藏：%s" % _hidden_shown(s["hidden_restored"], s["hidden"]))
            L.append("出现：%s" % _hidden_shown(s["shown_restored"], s["shown"]))
            L.append("")
            L.append("键变化：")
            if s["key_changes"]:
                L.extend(_change_list(s["key_changes"]))
            else:
                L.append("- （无）")
            L.append("")
        if b.get("naked"):
            n = b["naked"]
            L.append("### 全关态 %s" % n["id"])
            L.append("")
            L.append("隐藏：%s" % _hidden_shown(n["hidden_restored"], n["hidden"]))
            L.append("出现：%s" % _hidden_shown(n["shown_restored"], n["shown"]))
            L.append("")
            L.append("键变化：")
            if n["key_changes"]:
                L.extend(_change_list(n["key_changes"]))
            else:
                L.append("- （无）")
            L.append("")

    cand = m["candidates"]
    L.append("## 自动候选")
    L.append("")
    sections = [
        ("residual", "a. residual：渲染器被隐藏，但名字与它相关的键仍非零"),
        ("mis_bound", "b. mis_bound：脚型/收缩类键跟着不相干的开关走"),
        ("no_body_keys", "c. no_body_keys：可见服装件多于阈值但身体没有收缩/脚型键"),
        ("unexpected_change", "d. unexpected_change：关一件衣服时无关可见件的键变化"),
        ("out_of_range", "e. out_of_range：形态键值 <0 或 >100"),
    ]
    for key, title in sections:
        rows = cand.get(key) or []
        L.append("### %s（%d 条）" % (title, len(rows)))
        L.append("")
        if not rows:
            L.append("- （无）")
            L.append("")
            continue
        for r in rows:
            loc = []
            if r.get("baseline"):
                loc.append("基准 %s" % r["baseline"])
            if r.get("state"):
                loc.append("状态 %s" % r["state"])
            if r.get("param"):
                loc.append("开关 %s" % r["param"])
            L.append("- %s：%s" % ("；".join(loc) or "-", r.get("detail") or ""))
        L.append("")

    ex_rows = cand.get("residual_exempted") or []
    L.append("### a′. residual 豁免表命中（%d 条，已从 a 里扣除）" % len(ex_rows))
    L.append("")
    L.append("> 显式豁免，逐条列在代码 `RESIDUAL_EXEMPTIONS` 里（含出处）。不再用"
             "「键长在任何仍可见服装上就不计」那种宽判据。")
    L.append("")
    if not ex_rows:
        L.append("- （无）")
        L.append("")
    else:
        for r in ex_rows:
            L.append("- [%s] 隐藏 %s 时 %s · %s = %s"
                     % (r.get("exempt"), r.get("hidden_renderer_restored"),
                        r.get("key_renderer_restored"), r.get("shape_restored"),
                        fmt_val(r.get("value"))))
        L.append("")

    sw_rows = cand.get("residual_stopworded") or []
    L.append("### a″. residual 停用词命中（%d 条，已从 a 里扣除）" % len(sw_rows))
    L.append("")
    L.append("> 通用 token 停用词表 `RESIDUAL_STOPWORDS`（只收状态后缀 / 素体名；**不收部件词**），"
             "按 token 一刀切、不做逐对豁免；每条词带出处与理由，见 `matrix.json` 的 "
             "`filters.residual_stopwords` 与代码注释。部件词（如 `hood`）改从 "
             "`RESIDUAL_EXEMPTIONS` 逐对豁免（a′）。")
    L.append("")
    if not sw_rows:
        L.append("- （无）")
        L.append("")
    else:
        for r in sw_rows:
            L.append("- [token=%s] 隐藏 %s 时 %s · %s = %s"
                     % (r.get("token"), r.get("hidden_renderer_restored"),
                        r.get("key_renderer_restored"), r.get("shape_restored"),
                        fmt_val(r.get("value"))))
        L.append("")

    if m.get("warnings"):
        L.append("## 警告")
        L.append("")
        for w in m["warnings"]:
            L.append("- %s" % w)
        L.append("")

    L.append("## 候选规则（判据）")
    L.append("")
    L.append("- (a) residual：某单关态的隐藏渲染器 R，存在一个**不在 R 上**的非零键，"
             "其还原键名含 R 的还原名 token（拉丁 ≥3 字符 / CJK 任意）。"
             "**不因键长在服装上就跳过**（那会漏掉「衣服上的收缩键」这类真阳性）；"
             "已复核的共享词误报从 `RESIDUAL_EXEMPTIONS` 显式豁免表扣（a′），"
             "通用 token（只收状态后缀/素体名，不含部件词）从 `RESIDUAL_STOPWORDS` 停用词表扣（a″）。")
    L.append("- (b) mis_bound：")
    L.append("  - foot：脚型/鞋跟类键（foot/heel/toe/足/ヒール/つま先…）在「非鞋」Bool 关掉时变化；"
             "同时基准态的「关鞋」子态里这些键不变。")
    L.append("  - shrink：收缩类键（shrink/shlink/縮/収縮…）变化，但既不对应任何被隐藏物体、"
             "也不对应开关参数名。")
    L.append("- (c) no_body_keys：基准态可见服装件 > n_clothing（默认 3），但身体渲染器上没有任何收缩/脚型键。")
    L.append("- (d) unexpected_change：关一件衣服时，另一件**基准态可见的服装件**上的非脚型/非收缩键变化，"
             "且该键与隐藏物体、与开关参数都无 token 关联。")
    L.append("- (e) out_of_range：任何状态的形态键值 <0 或 >100（VRChat 客户端会钳制）。")
    L.append("")
    L.append("> 「相关」的判断基于名字 token，不理解语义；(b)(d) 的漏报/误报都可能来自命名。"
             "候选一律要人工回到 T1 原始 state_*.json 复核。")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(
        prog="t5_shapekey_matrix.py",
        description="T5 形态键依赖矩阵：生成 T1 请求、合并轮盘区间、生成开关 sweep、把 T1 输出分析成依赖矩阵。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", metavar="子命令")

    p1 = sub.add_parser("slots", help="T4 params.json 的每个 Float 轮盘 → 0..1 细扫 T1 请求")
    p1.add_argument("--params", required=True, help="T4 导出的 params.json")
    p1.add_argument("--avatar", required=True, help="头像根 GameObject 名")
    p1.add_argument("--out", required=True, help="输出目录（T1 请求 + slots_plan.json 都写这里）")
    p1.add_argument("--step", default="1/64", help="扫描步长，如 1/64 或 0.05（默认 1/64）")
    p1.add_argument("--settle-frames", type=int, default=30, help="T1 settle_frames（默认 30）")
    p1.add_argument("--only", default=None, help="只扫参数名匹配该正则的轮盘")
    p1.add_argument("--exclude", default=None, help="排除参数名匹配该正则的轮盘（如面捕 FT/）")
    p1.set_defaults(func=cmd_slots)

    p2 = sub.add_parser("slots-reduce", help="把 T1 细扫结果合并成区间 slots.json")
    p2.add_argument("--t1", required=True, help="T1 输出目录（含 slots_plan.json 与 state_*.json）")
    p2.add_argument("--out", required=True, help="输出的 slots.json 文件路径")
    p2.add_argument("--params", default=None, help="可选：没有 slots_plan.json 时用它重建计划")
    p2.add_argument("--step", default="1/64", help="仅重建计划时用")
    p2.add_argument("--only", default=None, help="仅重建计划时用")
    p2.add_argument("--exclude", default=None, help="仅重建计划时用")
    p2.set_defaults(func=cmd_slots_reduce)

    p3 = sub.add_parser("sweep", help="生成「整套 × 单关 × 全关 + 其余开关」状态集 T1 请求")
    p3.add_argument("--params", required=True, help="T4 导出的 params.json")
    p3.add_argument("--slots", required=True, help="slots-reduce 输出的 slots.json")
    p3.add_argument("--avatar", required=True, help="头像根 GameObject 名")
    p3.add_argument("--out", required=True, help="输出目录")
    p3.add_argument("--groups", default=None, help="可选：人工指定分组的 groups.json")
    p3.add_argument("--settle-frames", type=int, default=30, help="T1 settle_frames（默认 30）")
    p3.set_defaults(func=cmd_sweep)

    p4 = sub.add_parser("analyze", help="T1 输出 + sweep 请求 → matrix.json / matrix.md")
    p4.add_argument("--t1", required=True, help="T1 输出目录（state_*.json / states.json）")
    p4.add_argument("--sweep", required=True, help="sweep 请求 JSON（用哪份请求生成的状态就传哪份）")
    p4.add_argument("--out", required=True, help="输出目录")
    p4.add_argument("--params", default=None, help="可选：T4 params.json，用于更准地判断参数类型/菜单路径")
    p4.add_argument("--n-clothing", type=int, default=3,
                    help="候选 (c) 的可见服装件阈值 N（默认 3）")
    p4.add_argument("--filter-file", default=None, help="表情/面捕类键的关键词 JSON（覆盖默认）")
    p4.add_argument("--clothing-roots-file", default=None, help="服装根词 JSON（覆盖默认）")
    p4.add_argument("--clothing-keywords-file", default=None, help="服装单品词 JSON（覆盖默认）")
    p4.add_argument("--body-words-file", default=None, help="身体渲染器词 JSON（覆盖默认）")
    p4.add_argument("--foot-keywords-file", default=None, help="脚型键关键词 JSON（覆盖默认）")
    p4.add_argument("--shrink-keywords-file", default=None, help="收缩键关键词 JSON（覆盖默认）")
    p4.add_argument("--shoe-keywords-file", default=None, help="鞋类参数关键词 JSON（覆盖默认）")
    p4.set_defaults(func=cmd_analyze)

    return ap


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = build_parser()
    if not argv:
        ap.print_help()
        return 0
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
