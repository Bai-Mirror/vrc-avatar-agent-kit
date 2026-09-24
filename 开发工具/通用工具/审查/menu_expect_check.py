#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W5「编译态菜单断言」——把交付说明承诺的菜单行为与构建后 T1 实测逐条比对。
【项目沉淀】通用工具
适用素体：无关
相关素材：交付说明/菜单说明（期望来源）+ 工程 T4 params.json + T1 构建后扫描输出
工具链　：Python 3（离线）
可复用性：★★★ 期望 JSON 格式固定；参数名/取值沿用 T4 params.json
用途　　：W5「编译态菜单断言」：期望（第二视角，交付说明写出）与实测（构建后 T1 扫描）机械比对，
          输出逐条 PASS/FAIL，代替「开发态工程里自验自己的假设」。

两个子命令：

  gen-request  期望.json + T4 params.json → 标准 T1 请求（校验参数名/取值；slot:N 按显式档数求代表值）
  check        期望.json + T1 扫描输出    → 逐条比对报告（Markdown / JSON）

设计依据：派工 `W5_编译态菜单断言工具.md`；样本数据
`_长程任务_20260918/审查产出/工程A/seq_CL_verify_v3/`（T1+T4）。
期望文件格式与流程见同目录 `docs/menu-expect.md`（旧称 README_menu_expect.md，续页 menu-expect-rules / menu-expect-samples）。

只依赖 Python 3 标准库；只读输入、只写 --out 指定处；不启动 Unity、不调 MCP、不碰工程。
输出统一 UTF-8 无 BOM、LF。

两种模式：

* 研究模式（默认）：局部检查，允许「期望只覆盖部分参数」，未覆盖 / 歧义只记录、不拦。
* 交付模式（`--delivery`）：严格，不能误放行。强制 --params、source 与每条 note 出处；
  拒绝空检查结果；Bool 核 0/1、Int 核 `menu_values`（真正离散、有证据）；连续 Float/radial/轴
  必须有**显式且带出处的 coverage 约定**（不默认端点、不拿 `radial_labels` 当档数）；
  未覆盖、无法确定覆盖、声明解析错误、重复/非法输入、歧义匹配一律非零退出。

关键口径（取舍都写在 docs/menu-expect*.md）：

* 可见渲染器：用 T1 快照 `renderers[].visible`（= activeInHierarchy && enabled）。
  匹配模式可写完整路径、唯一叶名或含 `*` 的通配；名字还原规则照抄 T5
  （路径段 `名$原物体$编号` → `原物体`）。
* 形态键：`shapes` 的键写 `<网格>:<键名>`；网格/键名都可含 `*`，并同时匹配原样名与
  T5 还原名（`AAO_Merged_<原名>_<n>` → `<原名>`）。
* `set` 里 Float/轴/radial 的数值**原样透传，不做吸附或档中点改写**（要测 0.25 就发 0.25）；
  只有显式 `slot:N` 才按有效档数求代表值 `(i+0.5)/N`：档数优先取顶层 `coverage.gears`，
  研究模式可退回 `radial_labels` 个数，交付模式必须显式声明。Bool/Int 原值。
* `check` 与 `gen-request` 用同一套 `resolve_value` 与同一份有效约定；`slot:N`、显式档数
  不会因 T1 存的是换算后的数而被误判「缺失」，也不会为凑覆盖改写期望数值。
* 所有模式都拒绝「visible/hidden/shapes 全空」的状态：只写 `set` 只证明参数名出现，
  不是可验证行为，参数名覆盖 ≠ 行为覆盖。
* 退出码：0 全过；1 业务失败 / 缺失 / 未覆盖；2 检查失败（输入异常 / 无法确定覆盖 /
  前置缺失 / 歧义 / 空检查结果）。
"""

import argparse
import fnmatch
import glob
import json
import math
import os
import re
import sys
import time

TOOL = "menu_expect_check"
EPS = 1e-4
AAO_SHAPE_PREFIX = "AAO_Merged_"
_SEG_RENAME = re.compile(r"^(.*)\$([^$]+)\$(\d+)$")
_TRAIL_NUM = re.compile(r"^(.*)_(\d+)$")
_TRACK_BONES = ["Hips", "LeftFoot", "RightFoot", "LeftToes", "RightToes", "Head"]

# 出处字段（source/note）的最小「有效」判据：非空且不是占位符。
# 只查「写了没有」，不查被引用的文件是否真的存在——这一层没做，见 docs/menu-expect-samples.md §5 局限。
_PLACEHOLDER_TEXT = {
    "", "-", "--", "---", "?", "??", "n/a", "na", "none", "todo", "tbd",
    "无", "待补", "待定", "待查", "略", "同上",
}
# 连续参数（Float/radial/轴）的覆盖口径：
#   * 研究模式：允许按 radial_labels 个数或首/末档边界**推测**，并在报告里注明是推测。
#   * 交付模式：必须在期望文件顶层 coverage{参数: {gears|units|boundaries, note/source}}
#     显式声明并经人工审核，否则判「无法确定覆盖」→ exit 2。绝不默认端点算完成。
# 见 parse_contracts / build_coverage / README。


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

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
    eprint("[menu_expect_check] 错误：" + msg)
    sys.exit(code)


def fnum(v):
    """bool/int/float/数字字符串 → float；解析不了返回 None。"""
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


def is_bool_like(v):
    if isinstance(v, bool):
        return True
    if isinstance(v, int):
        return v in (0, 1)
    if isinstance(v, str):
        return v.strip().lower() in ("true", "false", "on", "off", "yes", "no", "0", "1")
    return False


def strict_number(v):
    """`set` 取值与 coverage 声明里允许的数值：int/float（非 bool）或纯数字字符串，
    且必须有限。NaN/Infinity、true/on 之类一律返回 None（不静默当成 0/1）。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
    elif isinstance(v, str):
        try:
            f = float(v.strip())
        except ValueError:
            return None
    else:
        return None
    return f if math.isfinite(f) else None


def is_continuous(pinfo):
    """连续参数（Float / radial / axis2 / axis4）：无法从 schema 穷尽离散档。"""
    kinds = pinfo.get("menu_value_kinds") or []
    if "radial" in kinds or "axis2" in kinds or "axis4" in kinds:
        return True
    return pinfo.get("value_type_name") == "Float"


def sanitize(s):
    out = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff]+", "_", str(s)).strip("_")
    return out or "state"


def restore_seg(seg):
    """路径段 `名$原物体$编号` → `原物体`；不匹配原样返回。"""
    m = _SEG_RENAME.match(seg)
    if m:
        return m.group(2)
    return seg


def restore_path(path):
    return "/".join(restore_seg(s) for s in str(path).split("/"))


def restore_shape(name):
    """`AAO_Merged_<原名>_<n>` → `<原名>`；不匹配原样返回。"""
    if not name:
        return name
    if name.startswith(AAO_SHAPE_PREFIX):
        n = name[len(AAO_SHAPE_PREFIX):]
        m = _TRAIL_NUM.match(n)
        if m:
            n = m.group(1)
        return n
    return name


def md_cell(v):
    s = str(v)
    return s.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# 期望文件
# ---------------------------------------------------------------------------

class Expect(object):
    def __init__(self, obj, path):
        self.path = path
        if not isinstance(obj, dict):
            die("期望文件顶层必须是 JSON 对象：%s" % path)
        self.avatar = obj.get("avatar") or ""
        self.source = obj.get("source") or ""
        self.raw = obj
        cov = obj.get("coverage")
        if cov is None:
            cov = {}
        if not isinstance(cov, dict):
            die("期望文件 coverage 必须是对象（{参数名: 约定}）：%s" % path)
        for cname, cspec in cov.items():
            if not isinstance(cspec, (dict, list)):
                die("coverage[%r] 必须是数组或对象：%s" % (cname, path))
        self.coverage = dict(cov)
        states = obj.get("states")
        if not isinstance(states, list) or not states:
            die("期望文件缺少非空的 states 数组：%s" % path)
        self.states = []
        seen = set()
        for i, st in enumerate(states):
            if not isinstance(st, dict):
                die("states[%d] 不是对象：%s" % (i, path))
            name = st.get("name")
            sset = st.get("set")
            if not name or not isinstance(name, str):
                die("states[%d] 缺少 name 字符串：%s" % (i, path))
            if name in seen:
                die("states 里 name 重复：%r（比对靠 name 区分同 set 的多条期望）" % name)
            seen.add(name)
            if not isinstance(sset, dict) or not sset:
                die("states[%r] 的 set 必须是非空对象" % name)
            for key in ("visible", "hidden"):
                if st.get(key) is not None and not isinstance(st[key], list):
                    die("states[%r].%s 必须是数组" % (name, key))
            if st.get("shapes") is not None and not isinstance(st["shapes"], dict):
                die("states[%r].shapes 必须是对象" % name)
            visible = list(st.get("visible") or [])
            hidden = list(st.get("hidden") or [])
            shapes = dict(st.get("shapes") or {})
            if not (visible or hidden or shapes):
                die("states[%r] 没有任何行为断言（visible/hidden/shapes 全空）：只写 set "
                    "只证明参数名出现，不是可验证行为（参数名覆盖 ≠ 行为覆盖）" % name)
            self.states.append({
                "name": name,
                "set": sset,
                "visible": visible,
                "hidden": hidden,
                "shapes": shapes,
                "t1_state": st.get("t1_state"),
                "note": st.get("note") or "",
            })


def load_expect(path):
    if not os.path.exists(path):
        die("期望文件不存在：%s" % path)
    try:
        obj = read_json(path)
    except Exception as e:
        die("期望文件读取失败：%s（%s）" % (path, e))
    return Expect(obj, path)


# ---------------------------------------------------------------------------
# T4 params.json
# ---------------------------------------------------------------------------

def load_params(path):
    """读 T4 params.json，并严格核输入 schema 与唯一性。

    错误（类型不对 / 重名 / 名单与 parameters 冲突）一律 die(2)，不退成宽松默认，
    更不允许同一个 name 被后面的条目静默覆盖。"""
    if not path:
        return None
    if not os.path.exists(path):
        die("params.json 不存在：%s" % path)
    try:
        obj = read_json(path)
    except Exception as e:
        die("params.json 读取失败：%s（%s）" % (path, e))
    if not isinstance(obj, dict):
        die("params.json 顶层必须是 JSON 对象，收到 %s：%s" % (type(obj).__name__, path))
    pars = obj.get("parameters")
    if pars is None:
        pars = []
    if not isinstance(pars, list):
        die("params.json 的 parameters 必须是数组，收到 %s：%s" % (type(pars).__name__, path))
    by_name = {}
    dup = []
    bad = []
    for i, p in enumerate(pars):
        if not isinstance(p, dict):
            bad.append("parameters[%d] 不是对象（%s）" % (i, type(p).__name__))
            continue
        nm = p.get("name")
        if not isinstance(nm, str) or not nm.strip():
            bad.append("parameters[%d] 缺少非空 name 字符串" % i)
            continue
        if nm in by_name:
            dup.append(nm)
        else:
            by_name[nm] = p
    if bad:
        die("params.json schema 不合法：%s（%s）" % ("；".join(bad), path))
    if dup:
        die("params.json 参数名重复，违反唯一性（不得静默覆盖）：%s（%s）"
            % ("、".join(sorted(set(dup))), path))
    # 名单字段与 parameters 的一致性：重复 / 列了却未定义，都是输入错误。
    for field in ("declared_param_names", "menu_param_names"):
        val = obj.get(field)
        if val is None:
            continue
        if not isinstance(val, list):
            die("params.json 的 %s 必须是数组，收到 %s：%s"
                % (field, type(val).__name__, path))
        seen = set()
        dups = []
        for x in val:
            if not isinstance(x, str) or not x:
                die("params.json 的 %s 含非字符串/空项：%r（%s）" % (field, x, path))
            if x in seen and x not in dups:
                dups.append(x)
            seen.add(x)
        if dups:
            die("params.json 的 %s 有重复项：%s（%s）" % (field, "、".join(dups), path))
        missing = sorted(set(val) - set(by_name))
        if missing:
            die("params.json 的 %s 与 parameters 冲突（列出但未定义）：%s（%s）"
                % (field, "、".join(missing), path))
    # menu_param_names 与实际菜单引用（menu_value_kinds / referenced_by）口径必须一致，
    # 冲突是可诊断的输入错误，不能静默忽略。
    if obj.get("menu_param_names") is not None:
        declared_menu = set(obj["menu_param_names"])
        derived_menu = set()
        for p in pars:
            if isinstance(p, dict) and p.get("name") and (
                    (p.get("menu_value_kinds") or []) or (p.get("referenced_by") or [])):
                derived_menu.add(p["name"])
        only_listed = sorted(declared_menu - derived_menu)
        only_derived = sorted(derived_menu - declared_menu)
        if only_listed or only_derived:
            parts = []
            if only_listed:
                parts.append("menu_param_names 列了但无菜单引用：%s" % "、".join(only_listed))
            if only_derived:
                parts.append("有菜单引用但 menu_param_names 未列：%s" % "、".join(only_derived))
            die("params.json 的 menu_param_names 与实际菜单引用口径冲突：%s（%s）"
                % ("；".join(parts), path))
    obj["by_name"] = by_name
    return obj


def resolve_value(pinfo, name, raw, gears=None):
    """把期望里的一个参数值转成 T1 请求值；返回 (value, note)。不合法时抛 ValueError。

    **数值一律原样透传，不做吸附、不做档中点改写**：要测 radial 的 0.25 就发 0.25，
    不会被悄悄改成 0.375 再称通过。只有显式字符串 `slot:N` 才按有效档数 `gears`
    求代表值 `(N+0.5)/N`；`gears` 来自顶层 `coverage.gears`（研究模式可退回
    `radial_labels` 个数，交付模式必须显式声明）。整数 0/1 是端点数值，不是槽号。"""
    vtype = pinfo.get("value_type_name")
    kinds = pinfo.get("menu_value_kinds") or []
    suggested = [f for f in (strict_number(x) for x in (pinfo.get("suggested_values") or []))
                 if f is not None]

    if vtype == "Bool":
        if not is_bool_like(raw):
            raise ValueError("Bool 参数只接受 0/1/true/false，收到 %r" % (raw,))
        return (1 if fnum(raw) >= 0.5 else 0), "Bool 原值"

    if vtype == "Int":
        f = strict_number(raw)
        if f is None or abs(f - round(f)) > 1e-9:
            raise ValueError("Int 参数只接受整数，收到 %r" % (raw,))
        return int(round(f)), "Int 原值"

    # Float（含 radial / axis）
    if isinstance(raw, str) and raw.strip().lower().startswith("slot:"):
        tail = raw.split(":", 1)[1].strip()
        if gears is None:
            raise ValueError("slot: 形式需要显式 coverage.gears 定出档数"
                             "（研究模式可退回 radial_labels ≥2；交付模式必须显式声明），"
                             "收到 %r" % (raw,))
        if not tail.isdigit():
            raise ValueError("slot: 后必须是整数槽号，收到 %r" % (raw,))
        i = int(tail)
        if not (0 <= i < gears):
            raise ValueError("槽号 %d 超出 0..%d" % (i, gears - 1))
        return (i + 0.5) / float(gears), "slot:%d → 第 %d/%d 档中点" % (i, i + 1, gears)

    if isinstance(raw, bool):
        raise ValueError("Float 参数不接受布尔值，收到 %r" % (raw,))
    f = strict_number(raw)
    if f is None:
        raise ValueError("Float 参数只接受有限数值（不接受 true/on/NaN/Infinity），"
                         "收到 %r" % (raw,))

    # 取值合法区间：只校验，不改写
    if "radial" in kinds:
        lo, hi = 0.0, 1.0
    elif ("axis2" in kinds) or ("axis4" in kinds):
        lo, hi = -1.0, 1.0
    elif suggested:
        lo, hi = min(suggested), max(suggested)
    else:
        lo, hi = 0.0, 1.0
    if not (lo - EPS <= f <= hi + EPS):
        # 整数落在 0..N-1 档号范围却超出连续区间：多半是旧式整数槽号写法。
        # 明确报错并提示，不自动改写、也不吞掉 0/1 端点。
        if ("radial" in kinds and gears is not None
                and isinstance(raw, int) and not isinstance(raw, bool)
                and 0 <= raw < gears):
            raise ValueError("整数 %d 在 0..%d 档号范围内，但 radial 取值区间是 [0, 1]；"
                             "若要槽号请显式写 \"slot:%d\"（本工具不把整数自动当槽号）"
                             % (raw, gears - 1, raw))
        raise ValueError("Float 取值 %r 不在 [%s, %s] 内" % (raw, lo, hi))
    return f, "Float 原值"


# ---------------------------------------------------------------------------
# 出处 / 归一化 / 覆盖模型
# ---------------------------------------------------------------------------

def is_meaningful_text(s):
    if not isinstance(s, str):
        return False
    t = s.strip()
    if not t:
        return False
    return t.lower() not in _PLACEHOLDER_TEXT and t not in _PLACEHOLDER_TEXT


def provenance_problems(exp):
    """交付模式的出处检查：source 与每条 state.note 都要有实质内容。

    只查「写了没有」，不查被引用的文件/行号是否真实存在（明确没做，见 docs/menu-expect-samples.md §5 局限）。"""
    probs = []
    if not is_meaningful_text(exp.source):
        probs.append("顶层 source 缺失或为占位符（交付模式要求写出处）")
    for st in exp.states:
        if not is_meaningful_text(st["note"]):
            probs.append("状态 %r 缺少出处（note 为空或占位符）" % st["name"])
    return probs


def normalize_expect_sets(exp, params_obj, delivery, gear_map=None):
    """按 gen-request 同一套 resolve_value 归一化每个状态的 set。

    返回 (results, errors, warns)：results 与 exp.states 一一对应，元素为 (norm, errs)。
    params_obj 为 None（研究模式未给 --params）时原值透传。
    `gear_map`（{参数: 档数}）来自同一份有效约定：`slot:N` 在 check 与 gen-request
    里换算成同一个代表值，不会把 slot: 形式误判成「T1 里没有」。
    **数值不被改写**：非 slot: 的 Float/radial 取值原样保留。"""
    gear_map = gear_map or {}
    by_name = params_obj["by_name"] if params_obj else {}
    results = []
    errors = []
    warns = []
    for st in exp.states:
        norm = {}
        errs = []
        for pname, raw in st["set"].items():
            if not params_obj:
                norm[pname] = raw
                continue
            pinfo = by_name.get(pname)
            if pinfo is None:
                msg = "状态 %r：参数 %r 不在 params.json" % (st["name"], pname)
                if delivery:
                    errs.append(msg)
                    errors.append(msg)
                else:
                    warns.append(msg + "（研究模式：按原值匹配，不做归一化）")
                    norm[pname] = raw
                continue
            if not pinfo.get("declared_in_expression"):
                warns.append("状态 %r：参数 %r 未声明在 expressionParameters（T1 可能设不上）"
                             % (st["name"], pname))
            try:
                val, how = resolve_value(pinfo, pname, raw, gear_map.get(pname))
            except ValueError as e:
                msg = "状态 %r：参数 %r %s" % (st["name"], pname, e)
                errs.append(msg)
                errors.append(msg)
                continue
            norm[pname] = val
            if how.startswith("slot:"):
                warns.append("状态 %r：%s=%r → %r（%s）" % (st["name"], pname, raw, val, how))
        results.append((norm, errs))
    return results, errors, warns


def _float_eq(a, b):
    return a is not None and b is not None and abs(a - b) <= EPS


def _fnum_list(vals):
    """schema 派生值（menu_values/suggested_values）里的数值，去重升序。"""
    out = []
    for v in vals or []:
        f = strict_number(v)
        if f is not None:
            out.append(round(f, 6))
    return sorted(set(out))


def _fmt_val(v):
    f = strict_number(v)
    if f is None:
        f = fnum(v)
    if f is None:
        return str(v)
    if abs(f - round(f)) <= EPS:
        return str(int(round(f)))
    return "%g" % f


def _units_from_values(vals):
    """schema 派生值 → 覆盖单元。"""
    units = []
    for v in vals:
        f = strict_number(v)
        if f is None:
            f = fnum(v)
        if f is None:
            continue
        units.append({"label": _fmt_val(f),
                      "match": (lambda fv: (lambda x: _float_eq(fnum(x), fv)))(round(f, 6))})
    return units


def _units_from_values_strict(vals, where):
    """显式声明里的数值：任一元素不是有限数值即报错，**不静默过滤**。"""
    if not isinstance(vals, list):
        return None, "%s 必须是数组（收到 %s）" % (where, type(vals).__name__)
    if not vals:
        return None, "%s 不能为空" % where
    units = []
    seen = set()
    for i, v in enumerate(vals):
        f = strict_number(v)
        if f is None:
            return None, ("%s[%d]=%r 不是有限数值（true/on、NaN、Infinity、"
                          "非数字字符串都不接受）" % (where, i, v))
        label = _fmt_val(f)
        if label in seen:
            continue
        seen.add(label)
        units.append({"label": label,
                      "match": (lambda fv: (lambda x: _float_eq(fnum(x), fv)))(round(f, 6))})
    return units, None


def radial_gear_count(pinfo):
    """radial_labels ≥2 个时给档数 N，否则 None。**只作研究模式推测**：
    docs/menu-dump-output.md（旧称 README_T4）说 radial_labels 只是引用该参数的 Radial 控件标签名，个数不保证等于
    真实档数（同一参数多控件会合并）。"""
    labels = pinfo.get("radial_labels") or []
    if len(labels) >= 2:
        return len(labels)
    return None


def gear_of(v, n):
    f = fnum(v)
    if f is None or f < -EPS or f > 1.0 + EPS:
        return None
    if f >= 1.0 - EPS:
        return n - 1
    return max(0, min(n - 1, int(f * n + 1e-9)))


def _units_from_gears(n):
    units = []
    for i in range(n):
        units.append({"label": "档%d/%d" % (i + 1, n),
                      "match": (lambda ii, nn: (lambda x: gear_of(x, nn) == ii))(i, n)})
    return units


def _derive_units(pinfo, delivery):
    """按 T4 schema 建覆盖单元；返回 (units, convention, determinate)。

    Bool/Int(有 menu_values) 是**真正离散、有证据**的类型，可直接定档。
    连续参数（Float/radial/轴）在交付模式一律 determinate=False：档位必须由顶层
    `coverage` 显式声明（带出处），不拿 `radial_labels` 当档数，也不默认 0/1 端点算完成。
    研究模式才允许用 schema / labels 推测（并在 convention 里标注是推测）。"""
    kind = pinfo.get("value_type_name")
    kinds = pinfo.get("menu_value_kinds") or []
    if kind == "Bool":
        return _units_from_values([0, 1]), "Bool 开关两态 0/1", True
    # 菜单里真实出现过的离散值：对 Int 与「真正离散的 Float/radial」都是有证据的档位
    # （docs/menu-dump-output.md，旧称 README_T4：menu_values 是菜单里真实出现过的离散值，Radial/轴的连续参数通常为空）。
    mv = _fnum_list(pinfo.get("menu_values") or [])
    if mv:
        return _units_from_values(mv), "%s 各档（menu_values，菜单真实值）" % (kind or "?"), True
    if kind == "Int":
        if not delivery:
            vals = _fnum_list(pinfo.get("suggested_values") or [])
            if vals:
                return _units_from_values(vals), "Int 各档（suggested_values 兜底，研究模式）", True
        return None, "", False
    if is_continuous(pinfo):
        if delivery:
            return None, "", False
        if "radial" in kinds:
            n = radial_gear_count(pinfo)
            if n:
                return _units_from_gears(n), "轮盘 %d 档（radial_labels 推测，研究模式）" % n, True
            return _units_from_values([0.0, 1.0]), "轮盘档数未知 → 首/末档边界（研究模式推测）", True
        if ("axis2" in kinds) or ("axis4" in kinds):
            return _units_from_values([-1.0, 0.0, 1.0]), "连续轴 → -1/0/1 边界（研究模式推测）", True
        return _units_from_values([0.0, 1.0]), "连续 Float → 0/1 边界（研究模式推测）", True
    return None, "", False


_DECL_KEYS = ("gears", "units", "boundaries", "note", "source")
# 显式档数上限：防止坏约定写出天文数字把工具拖死（既不是正常档数，也非「宽松默认」）。
_MAX_GEARS = 4096


def _parse_one_contract(cname, spec, delivery):
    """严格解析 coverage[cname]；返回 (units, conv, note, gears, err)。

    err 非空即输入错误，调用方必须报错——**不能**因为 schema 已能定档就吞掉。
    禁止：小数/布尔 gears、混入非法数值再静默过滤、NaN/Infinity、未知字段、多重约定。"""
    if isinstance(spec, list):
        if delivery:
            return None, "", "", None, (
                "交付模式要求对象形式并写 note/source 出处；数组形式没有出处（研究模式才允许）")
        units, err = _units_from_values_strict(spec, "coverage[%r] 数组" % cname)
        if err:
            return None, "", "", None, err
        return units, "期望显式声明 units（无出处，研究模式）", "", None, None
    if not isinstance(spec, dict):
        return None, "", "", None, "类型必须是数组或对象"
    unknown = sorted(set(spec) - set(_DECL_KEYS))
    if unknown:
        return None, "", "", None, ("无法识别的字段：%s（只允许 %s）"
                                    % ("、".join(unknown), "/".join(_DECL_KEYS)))
    present = [k for k in ("gears", "units", "boundaries") if spec.get(k) is not None]
    if not present:
        return None, "", "", None, "对象里既无 gears 也无 units/boundaries"
    if len(present) > 1:
        return None, "", "", None, "同时声明了 %s，覆盖约定歧义" % "、".join(present)
    note = ""
    for k in ("note", "source"):
        if is_meaningful_text(spec.get(k)):
            note = str(spec[k]).strip()
            break
    # 先解析结构（gears/units/boundaries），再核出处：结构错误优先暴露，
    # 不会因为缺 note 就把坏的 gears 吞掉；两者都坏时一起报。
    err = None
    units = conv = None
    gears_n = None
    if "gears" in present:
        g = spec["gears"]
        if isinstance(g, bool) or not isinstance(g, int):
            err = ("gears 必须是整数（收到 %r；不接受小数或字符串，更不得截断）" % (g,))
        elif g < 2:
            err = "gears 必须 >= 2（收到 %d）" % g
        elif g > _MAX_GEARS:
            err = "gears 过大（%d > %d），请核对该参数真实档数" % (g, _MAX_GEARS)
        else:
            units, conv, gears_n = _units_from_gears(g), "期望显式声明 %d 档" % g, g
    else:
        field = "units" if "units" in present else "boundaries"
        units, err = _units_from_values_strict(spec.get(field) or [],
                                               "coverage[%r].%s" % (cname, field))
        if not err:
            conv = "期望显式声明 %s" % field
    if err:
        if delivery and not note:
            err += "；且交付模式要求带 note/source 出处（人工审核来源）"
        return None, "", "", None, err
    if delivery and not note:
        return None, "", "", None, "交付模式要求 coverage 声明带 note/source 出处（人工审核来源）"
    return units, conv, note, gears_n, None


def parse_contracts(params_obj, exp, delivery):
    """解析所有 coverage 声明 → (contracts, errors, warns)。

    errors：未知参数、非菜单参数（交付模式）、无法解析的声明、交付缺出处。
    这些在交付模式必须非零；研究模式下**解析错误同样非零**（输入错误）。
    params_obj 为 None（研究模式未给 --params）时只做语法校验，不核参数存在性。"""
    by_name = params_obj["by_name"] if params_obj else None
    menu_names = set(menu_params(params_obj)) if params_obj else None
    contracts = {}
    errors = []
    warns = []
    for cname, spec in (exp.coverage or {}).items():
        if by_name is not None and cname not in by_name:
            errors.append("coverage[%r] 不在 params.json 的参数里（未知参数约定）" % cname)
            continue
        if menu_names is not None and cname not in menu_names:
            msg = ("coverage[%r] 在 params.json 里存在，但不是本次菜单参数"
                   "（menu_value_kinds/referenced_by 皆空）" % cname)
            if delivery:
                errors.append(msg)
            else:
                warns.append(msg + "（研究模式：仍按该声明加严）")
        units, conv, note, gears, err = _parse_one_contract(cname, spec, delivery)
        if err:
            errors.append("coverage[%r] 无法解析：%s" % (cname, err))
            continue
        contracts[cname] = {"units": units, "conv": conv, "note": note, "gears": gears}
    return contracts, errors, warns


def build_coverage(params_obj, exp, norm_sets, delivery, contracts):
    """按 T4 schema + 显式约定，逐菜单参数建「每档 / 每开关 0 与 1」覆盖要求。

    返回 (requirements, uncovered, undetermined, errors)：
      requirements：每参数档位清单（label/convention/covered），用于报告；
      uncovered：期望状态没覆盖到的档/态（业务缺口）；
      undetermined：schema 与声明都定不出档位；
      errors：交付模式下覆盖约定缺失/不合规（检查失败，exit 2）。

    覆盖只看期望 `set` 归一化后的取值，与 T1 是否找到该状态无关（「缺失」另计），
    两类失败不会互相掩盖。schema 能定档时，显式 coverage 只允许加严（并集），
    不能借声明把 Bool 降成只测一态。"""
    by_name = params_obj["by_name"]
    requirements = []
    uncovered = []
    undetermined = []
    errors = []
    for name in menu_params(params_obj):
        pinfo = by_name.get(name)
        if pinfo is None:
            continue
        kind = pinfo.get("value_type_name") or "?"
        cont = is_continuous(pinfo)
        decl = contracts.get(name)
        # 一个参数可同时被轮盘和按钮引用；按钮的离散值不代表轮盘已覆盖。
        if delivery and decl is None and any(
                k in (pinfo.get("menu_value_kinds") or []) for k in ("radial", "axis2", "axis4")):
            reason = "含连续控件，必须有显式 coverage 约定；同参数的按钮值不能替代连续覆盖"
            errors.append("无法确定覆盖：参数 %r（%s）%s" % (name, kind, reason))
            undetermined.append({"param": name, "kind": kind, "reason": reason})
            continue
        units, conv, determinate = _derive_units(pinfo, delivery)
        if determinate and units:
            if decl is not None:
                have = {u["label"] for u in units}
                for u in decl["units"]:
                    if u["label"] not in have:
                        units.append(u)
                        have.add(u["label"])
                conv = conv + "；并期望声明（%s）" % decl["conv"]
                if decl["note"]:
                    conv += " [出处：%s]" % decl["note"]
        else:
            if decl is None:
                if cont:
                    reason = ("连续 %s 交付检查必须有显式 coverage 约定与来源（人工审核），"
                              "不默认端点当完成；radial_labels 只是控件标签名，不保证真实档数"
                              % kind)
                else:
                    reason = ("schema 定不出可达档位（无 menu_values），"
                              "且期望未在顶层 coverage 声明 gears/units/boundaries")
                if delivery:
                    errors.append("无法确定覆盖：参数 %r（%s）%s" % (name, kind, reason))
                undetermined.append({"param": name, "kind": kind, "reason": reason})
                continue
            units = decl["units"]
            conv = decl["conv"] + (" [出处：%s]" % decl["note"] if decl["note"] else "")
        covered = set()
        for norm in norm_sets:
            if name not in norm:
                continue
            v = norm[name]
            for i, u in enumerate(units):
                if u["match"](v):
                    covered.add(i)
        for i, u in enumerate(units):
            if i not in covered:
                uncovered.append({"param": name, "kind": kind, "unit": u["label"],
                                  "convention": conv,
                                  "reason": "期望状态未覆盖该档/态"})
        requirements.append({"param": name, "kind": kind, "convention": conv,
                             "units": [u["label"] for u in units],
                             "covered": [units[i]["label"] for i in sorted(covered)]})
    return requirements, uncovered, undetermined, errors


def cmd_gen_request(args):
    exp = load_expect(args.expect)
    params_obj = load_params(args.params)
    if params_obj is None:
        die("gen-request 必须给 --params <T4 params.json>")
    by_name = params_obj["by_name"]
    delivery = bool(getattr(args, "delivery", False))

    errors = []
    warns = []
    states = []
    if delivery:
        for p in provenance_problems(exp):
            errors.append("交付模式出处检查：" + p)

    # 解析 coverage 声明（严格）：解析错误任何模式都非零；交付模式还要求连续参数有显式约定+出处。
    contracts, cov_errors, cov_warns = parse_contracts(params_obj, exp, delivery)
    errors.extend(cov_errors)
    warns.extend(cov_warns)
    norm_sets = [{k: v for k, v in st["set"].items()} for st in exp.states]
    if delivery:
        _, _, _cov_undetermined, cov_missing = build_coverage(
            params_obj, exp, norm_sets, delivery, contracts)
        errors.extend(cov_missing)
    gear_map = {n: c["gears"] for n, c in contracts.items() if c.get("gears") is not None}
    if not delivery:
        # 研究模式：slot:N 可退回 radial_labels 推测的档数（交付模式必须显式声明）
        for name, pinfo in by_name.items():
            if name in gear_map:
                continue
            n = radial_gear_count(pinfo)
            if n and is_continuous(pinfo):
                gear_map[name] = n

    for idx, st in enumerate(exp.states):
        resolved = {}
        for pname, raw in st["set"].items():
            pinfo = by_name.get(pname)
            if pinfo is None:
                errors.append("状态 %r：参数名 %r 不在 params.json（声明 %d 个 / 菜单用到 %d 个）"
                              % (st["name"], pname,
                                 len(params_obj.get("declared_param_names") or []),
                                 len(params_obj.get("menu_param_names") or [])))
                continue
            if not pinfo.get("declared_in_expression"):
                warns.append("状态 %r：参数 %r 未声明在 expressionParameters（T1 可能设不上）"
                             % (st["name"], pname))
            try:
                val, how = resolve_value(pinfo, pname, raw, gear_map.get(pname))
            except ValueError as e:
                errors.append("状态 %r：参数 %r %s" % (st["name"], pname, e))
                continue
            resolved[pname] = val
            if how.startswith("slot:"):
                warns.append("状态 %r：%s=%r → %r（%s）" % (st["name"], pname, raw, val, how))
        sid = "exp_%03d__%s" % (idx, sanitize(st["name"]))
        states.append({"id": sid, "params": resolved, "name": st["name"]})

    if errors:
        eprint("[menu_expect_check] gen-request 校验失败，共 %d 条：" % len(errors))
        for e in errors:
            eprint("  - " + e)
        sys.exit(2)

    avatar = args.avatar or exp.avatar
    if not avatar:
        die("期望文件没有 avatar，且命令行没给 --avatar")
    scan_out = args.scan_out or (os.path.splitext(os.path.abspath(args.out))[0] + "_t1")
    request = {
        "tool": "state",
        "avatar": avatar,
        "out": scan_out,
        "settle_frames": int(args.settle_frames),
        "volatile_probe": False,
        "track_bones": list(_TRACK_BONES),
        "states": [{"id": s["id"], "params": s["params"]} for s in states],
        "note": "menu_expect_check gen-request；期望文件 %s；来源 %s"
                % (os.path.abspath(args.expect), exp.source),
    }
    write_json(args.out, request)

    print("[menu_expect_check gen-request] 期望状态 %d 个 → T1 请求 %s" % (len(states), args.out))
    print("  avatar=%s  out=%s  settle_frames=%d" % (avatar, scan_out, args.settle_frames))
    for s in states:
        print("  - %-16s %s" % (s["id"], json.dumps(s["params"], ensure_ascii=False)))
    for w in warns:
        eprint("  ⚠ " + w)
    if warns:
        print("  ⚠ %d 条 slot 换算/未声明提醒（细节见 stderr）" % len(warns))
    print("  跑法：把该文件复制成 <工程>/Library/AvatarAudit/request.json，在 Play 里触发 "
          "Tools/AvatarAudit/Run Request。")


# ---------------------------------------------------------------------------
# T1 输出
# ---------------------------------------------------------------------------

def load_t1(path):
    """读 T1 输出：目录（递归找 state_*.json）/ state_*.json / states.json。"""
    files = []
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "**", "state_*.json"), recursive=True))
    elif os.path.isfile(path):
        base = os.path.basename(path)
        if base == "states.json":
            d = os.path.dirname(os.path.abspath(path))
            try:
                sj = read_json(path)
            except Exception as e:
                die("states.json 读取失败：%s（%s）" % (path, e))
            for sid in (sj.get("states") or []):
                f = os.path.join(d, "state_%s.json" % sid)
                if os.path.exists(f):
                    files.append(f)
                elif not str(sid).endswith(".repeat"):
                    eprint("  ⚠ 缺少 state_%s.json（states.json 列了但目录里没有）" % sid)
        else:
            files = [path]
    else:
        die("--t1 路径不存在：%s" % path)

    states = []
    for f in files:
        base = os.path.basename(f)
        if base.endswith(".repeat.json"):
            continue
        try:
            d = read_json(f)
        except Exception as e:
            eprint("  ⚠ 读取失败，跳过：%s（%s）" % (f, e))
            continue
        if not isinstance(d, dict) or "renderers" not in d:
            eprint("  ⚠ 不是 T1 状态快照，跳过：%s" % f)
            continue
        st = dict(d)
        st["_file"] = f
        sid = st.get("id")
        if not sid:
            m = re.match(r"^state_(.*)\.json$", base)
            st["id"] = m.group(1) if m else base
        states.append(st)
    if not states:
        die("--t1 里没有可用的 state_*.json：%s" % path)
    return states


def params_equal(a, b):
    fa, fb = fnum(a), fnum(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) <= EPS
    return str(a) == str(b)


def match_state(states, want, t1_state=None):
    """按 set 子集匹配 T1 状态；返回 (best, candidates)。"""
    cands = []
    for st in states:
        if t1_state and str(st.get("id")) != str(t1_state):
            continue
        applied = st.get("params_applied") or {}
        if all(k in applied and params_equal(applied[k], v) for k, v in want.items()):
            extra = len(applied) - len(want)
            cands.append((extra, st))
    if not cands:
        return None, []
    cands.sort(key=lambda x: x[0])
    return cands[0][1], [c[1] for c in cands]


def renderer_candidates(rd):
    out = set()
    for base in (rd.get("path") or "", rd.get("key") or ""):
        if not base:
            continue
        out.add(base)
        segs = base.split("/")
        out.add(segs[-1])
        out.add(restore_path(base))
        out.add(restore_seg(segs[-1]))
        for s in segs:
            out.add(s)
            out.add(restore_seg(s))
    return out


def shape_entries(state):
    """返回 [(mesh_cands, shape_cands, value, mesh, shape)]，覆盖 keys_all 与 blendshapes。

    keys_all（全量键）优先；blendshapes（只存非零）补齐 keys_all 缺的。
    同一 (网格, 键名) 只出一行，免得报告里同一条重复两遍。"""
    out = []
    seen = set()
    for mname, blk in (state.get("keys_all") or {}).items():
        if not isinstance(blk, dict):
            continue
        meshes = {mname, blk.get("built_name"), blk.get("built_path")}
        bp = blk.get("built_path")
        if bp:
            meshes.add(str(bp).split("/")[-1])
        meshes = {m for m in meshes if m}
        for k in blk.get("keys") or []:
            nm = k.get("name")
            if not nm or (mname, nm) in seen:
                continue
            seen.add((mname, nm))
            out.append((meshes, {nm, restore_shape(nm)}, fnum(k.get("weight")), mname, nm))
    for mname, dd in (state.get("blendshapes") or {}).items():
        if not isinstance(dd, dict):
            continue
        for sname, val in dd.items():
            if (mname, sname) in seen:
                continue
            seen.add((mname, sname))
            out.append(({mname}, {sname, restore_shape(sname)}, fnum(val), mname, sname))
    return out


def pat_match(cands, pattern):
    return any(fnmatch.fnmatchcase(str(c), str(pattern)) for c in cands if c)


def check_state(exp_state, state):
    """返回该期望状态的行 list；每行 dict(state,item,expect,actual,ok)。"""
    rows = []
    name = exp_state["name"]
    vis = [r for r in (state.get("renderers") or []) if r.get("visible")]
    hid = [r for r in (state.get("renderers") or []) if not r.get("visible")]
    allr = state.get("renderers") or []

    for pattern in exp_state["visible"]:
        hit = [r for r in allr if pat_match(renderer_candidates(r), pattern)]
        if not hit:
            rows.append({"state": name, "item": "visible %s" % pattern,
                         "expect": "可见", "actual": "未找到匹配渲染器", "ok": False})
            continue
        bad = [r for r in hit if not r.get("visible")]
        actual = "%s（%s）" % ("可见" if not bad else "有不可见匹配",
                              "、".join(str(r.get("path")) for r in hit[:3]))
        rows.append({"state": name, "item": "visible %s" % pattern,
                     "expect": "可见", "actual": actual, "ok": not bad})

    for pattern in exp_state["hidden"]:
        hit = [r for r in allr if pat_match(renderer_candidates(r), pattern)]
        if not hit:
            rows.append({"state": name, "item": "hidden %s" % pattern,
                         "expect": "不可见", "actual": "未找到匹配渲染器", "ok": False})
            continue
        bad = [r for r in hit if r.get("visible")]
        actual = "%s（%s）" % ("不可见" if not bad else "有可见匹配",
                              "、".join(str(r.get("path")) for r in hit[:3]))
        rows.append({"state": name, "item": "hidden %s" % pattern,
                     "expect": "不可见", "actual": actual, "ok": not bad})

    entries = shape_entries(state)
    for spec, raw_exp in exp_state["shapes"].items():
        mesh_pat, sep, shape_pat = str(spec).partition(":")
        if not sep:
            rows.append({"state": name, "item": "shape %s" % spec,
                         "expect": raw_exp, "actual": "格式应为 网格:键名", "ok": False})
            continue
        want = fnum(raw_exp)
        hit = [e for e in entries
               if pat_match(e[0], mesh_pat) and pat_match(e[1], shape_pat)]
        if not hit:
            rows.append({"state": name, "item": "shape %s" % spec,
                         "expect": raw_exp, "actual": "未找到匹配形态键", "ok": False})
            continue
        vals = [e[2] for e in hit]
        if want is None:
            rows.append({"state": name, "item": "shape %s" % spec,
                         "expect": raw_exp, "actual": "期望值非数值", "ok": False})
            continue
        bad = [v for v in vals if v is None or abs(v - want) > EPS]
        detail = "、".join("%s=%s" % (e[3], e[4]) for e in hit[:3])
        if bad:
            got = "、".join(str(v) for v in vals[:3])
            actual = "%s（%s）" % (got, detail)
            rows.append({"state": name, "item": "shape %s" % spec,
                         "expect": want, "actual": actual, "ok": False})
        else:
            rows.append({"state": name, "item": "shape %s" % spec,
                         "expect": want, "actual": "=%s（%s）" % (vals[0], detail), "ok": True})
    return rows


# ---------------------------------------------------------------------------
# 子命令 2：check
# ---------------------------------------------------------------------------

def menu_params(params_obj):
    if not params_obj:
        return []
    out = []
    for p in params_obj.get("parameters") or []:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        if (p.get("menu_value_kinds") or []) or (p.get("referenced_by") or []):
            out.append(p["name"])
    return sorted(set(out))


def cmd_check(args):
    delivery = bool(getattr(args, "delivery", False))
    exp = load_expect(args.expect)
    states = load_t1(args.t1)
    params_obj = load_params(args.params) if args.params else None

    check_failures = []   # 检查失败（输入/前置/无法确定）→ 退出码 2
    warns = []

    # (a) 交付模式前置：必须能核覆盖、必须有出处
    if delivery:
        if params_obj is None:
            check_failures.append("交付模式必须提供 --params <T4 params.json>（否则无法核每档/每开关覆盖）")
        for p in provenance_problems(exp):
            check_failures.append(p)

    # (a2) coverage 声明严格解析：解析错误任何模式都非零；交付模式还要求出处
    contracts, cov_errors, cov_warns = parse_contracts(params_obj, exp, delivery)
    check_failures.extend(cov_errors)
    warns.extend(cov_warns)
    gear_map = {}
    if params_obj:
        gear_map = {n: c["gears"] for n, c in contracts.items() if c.get("gears") is not None}
        if not delivery:
            # 研究模式：slot:N 可退回 radial_labels 推测的档数
            for name, pinfo in params_obj["by_name"].items():
                if name in gear_map or not is_continuous(pinfo):
                    continue
                n = radial_gear_count(pinfo)
                if n:
                    gear_map[name] = n

    # (b) set 值归一化：与 gen-request 同一套 resolve_value + 同一份有效约定（不改写数值）
    norm_results, _norm_errors, norm_warns = normalize_expect_sets(exp, params_obj, delivery, gear_map)
    warns.extend(norm_warns)

    rows = []
    not_found = []
    per_state = []
    input_anomaly_states = []
    for st, (norm, errs) in zip(exp.states, norm_results):
        if errs:
            input_anomaly_states.append({"name": st["name"], "errors": errs})
            per_state.append({"name": st["name"], "matched": None, "rows": [],
                              "ambiguous": 0, "note": st["note"], "input_error": True})
            continue
        best, cands = match_state(states, norm, st.get("t1_state"))
        if best is None:
            not_found.append({"name": st["name"], "set": st["set"], "normalized_set": norm,
                              "visible": st["visible"], "hidden": st["hidden"],
                              "shapes": st["shapes"], "note": st["note"]})
            per_state.append({"name": st["name"], "matched": None, "rows": [],
                              "ambiguous": 0, "note": st["note"]})
            continue
        srows = check_state(st, best)
        rows.extend(srows)
        per_state.append({"name": st["name"], "matched": best.get("id"),
                          "file": best.get("_file"), "rows": srows,
                          "ambiguous": max(0, len(cands) - 1), "note": st["note"]})

    fail_rows = [r for r in rows if not r["ok"]]
    ambiguous = [p for p in per_state if p.get("ambiguous")]

    # (c) 覆盖：按 T4 schema + 显式约定逐参数建「每档 / 每开关 0 与 1」
    requirements = []
    uncovered = None
    uncovered_params = None
    undetermined = []
    if params_obj:
        requirements, uncovered, undetermined, cov_missing = build_coverage(
            params_obj, exp, [r[0] for r in norm_results], delivery, contracts)
        uncovered_params = sorted(set(u["param"] for u in uncovered))
        check_failures.extend(cov_missing)

    # (d) 交付模式严格判据：未覆盖 / 无法确定覆盖 / 歧义 / 空结果 / 输入异常一律不能放行
    if delivery:
        for s in input_anomaly_states:
            check_failures.extend(s["errors"])
        if not rows:
            check_failures.append("检查结果为空：没有任何成功比对的行为断言行，不能证明任何行为")
        for p in ambiguous:
            check_failures.append("状态 %r 匹配到 %d 个 T1 状态，无法唯一判定"
                                  % (p["name"], p["ambiguous"] + 1))
    else:
        # 研究模式：取值非法仍是输入错误；参数名不在 params 已降级为 warning
        for s in input_anomaly_states:
            check_failures.extend(s["errors"])

    business_fail = len(fail_rows)
    missing = len(not_found)
    uncovered_n = len(uncovered) if uncovered is not None else 0
    undetermined_n = len(undetermined)
    ambiguous_n = len(ambiguous)

    if check_failures:
        exit_code = 2
    elif business_fail or missing:
        exit_code = 1
    elif delivery and uncovered_n:
        exit_code = 1
    else:
        exit_code = 0

    if delivery:
        if exit_code == 0:
            conclusion = ("**菜单行为断言通过（约定覆盖）**：在编辑器构建后口径下，期望按显式约定"
                          "覆盖的各档/开关/边界断言行全部通过。这不代表参数全组合、游戏端同步，"
                          "也不代表断言与参数效果语义对应；仍缺的业务前提须人工另行核验。")
        elif exit_code == 1:
            conclusion = "**不通过**：存在业务失败 / 缺失 / 未覆盖，见下。"
        else:
            conclusion = "**不通过（检查失败）**：输入、前置或覆盖口径无法判定，结果不进入正常差异判定。"
    else:
        if exit_code == 0:
            conclusion = ("**局部通过**：仅本次写进期望的状态通过。研究模式不核每档/每开关覆盖，"
                          "未覆盖与歧义只记录、不拦，不代表交付完整。")
        elif exit_code == 1:
            conclusion = ("**局部不通过**：本次写进期望的状态有 FAIL 或缺失；研究模式不把未覆盖计入判定，"
                          "不代表交付完整。")
        else:
            conclusion = "**局部检查失败（输入不合法）**：取值/参数校验未过，结果不进入差异判定。"

    covered_params = [r for r in requirements if len(r["covered"]) == len(r["units"])]
    limitations = [
        "逐条离散状态覆盖，不代表参数全组合，也不代表参数间相互影响已测。",
        "T1 是编辑器构建后口径，不等于游戏端（参数压缩/远端量化/同步位/他人视角）；PASS 只证明编辑器构建后一致。",
        "可见性只看 renderers[].visible（activeInHierarchy && enabled），不看材质透明度。",
        "出处只查「写了没有」，没有核对被引用的文件/行号是否真实存在（约定来源同理）。",
        "交付模式的连续 Float/radial/轴覆盖来自期望显式声明的 coverage 约定（带出处）；"
        "radial_labels 只是控件标签名、可能合并多控件，本工具不拿它当交付档数依据。",
        "状态里的断言不与被覆盖参数逐个绑定：某档有状态且有断言，不等于断言针对该参数的效果。",
    ]

    # ---- Markdown ----
    L = []
    L.append("# 菜单行为断言报告（menu_expect_check）")
    L.append("")
    L.append("- 模式：**%s**" % ("交付模式（严格，不可误放行）" if delivery else "研究模式（局部检查）"))
    L.append("- 生成时间：%s" % now_str())
    L.append("- 期望文件：`%s`" % os.path.abspath(args.expect))
    L.append("- 期望来源：%s" % (exp.source or "（期望文件未写 source）"))
    L.append("- T1 输入：`%s`（读到状态 %d 个）" % (os.path.abspath(args.t1), len(states)))
    if args.params:
        L.append("- params.json：`%s`" % os.path.abspath(args.params))
    else:
        L.append("- params.json：（未提供；不核覆盖）")
    L.append("")

    L.append("## 汇总")
    L.append("")
    L.append("| 类别 | 数量 | 含义 |")
    L.append("|---|---|---|")
    L.append("| 业务失败（比对不一致） | %d | 期望与构建后实测不符 |" % business_fail)
    L.append("| 缺失（未在 T1 找到） | %d | 期望状态没扫到，无法判定 |" % missing)
    L.append("| 未覆盖（档/开关/边界） | %s | 期望没有覆盖到该参数的可达档/态 |"
             % ("未评估（未给 --params）" if uncovered is None else uncovered_n))
    L.append("| 无法确定覆盖 | %s | schema 与声明都定不出档位 |"
             % ("未评估（未给 --params）" if uncovered is None else undetermined_n))
    L.append("| 歧义匹配 | %d | 同一 set 命中多个 T1 状态%s |"
             % (ambiguous_n, "（研究模式取参数最少者）" if not delivery else ""))
    L.append("| 检查失败（输入/前置） | %d | 不进入业务差异判定 |" % len(check_failures))
    L.append("")
    L.append("- 退出码：**%d**（0 全过 / 1 业务失败·缺失·未覆盖 / 2 检查失败）" % exit_code)
    L.append("- 结论：%s" % conclusion)
    L.append("")

    if check_failures:
        L.append("## 检查失败（不进入业务差异判定）")
        L.append("")
        for e in check_failures:
            L.append("- %s" % e)
        L.append("")

    L.append("## 逐条比对")
    L.append("")
    L.append("| 状态 | 项 | 期望 | 实测 | 判定 |")
    L.append("|---|---|---|---|---|")
    if rows:
        for r in rows:
            L.append("| %s | %s | %s | %s | %s |"
                     % (md_cell(r["state"]), md_cell(r["item"]), md_cell(r["expect"]),
                        md_cell(r["actual"]), "PASS" if r["ok"] else "**FAIL**"))
    else:
        L.append("| （无） |  |  |  |  |")
    L.append("")

    if not_found:
        L.append("## 未在 T1 里找到的状态（缺失）")
        L.append("")
        for nf in not_found:
            L.append("- **%s**  set=`%s`" % (nf["name"], json.dumps(nf["set"], ensure_ascii=False)))
            if nf["note"]:
                L.append("  - 出处：%s" % nf["note"])
            L.append("  - 可用 `gen-request` 生成请求（见 docs/menu-expect.md）。")
        L.append("")

    if ambiguous:
        L.append("## 匹配到多个 T1 状态（歧义）")
        L.append("")
        for p in ambiguous:
            L.append("- %s（T1=%s，另有 %d 个同 set 候选）"
                     % (p["name"], p["matched"], p["ambiguous"]))
        L.append("")

    L.append("## 覆盖（对照 params.json 的 T4 schema）")
    L.append("")
    L.append("- 口径：Bool 必测 0/1 两态；Int 必测每个 `menu_values`（菜单真实离散值）。"
             "连续参数（Float / radial / 二维·四维轴）在交付模式**必须**在期望顶层 `coverage` "
             "显式声明 `gears` / `units` / `boundaries` 并写 `note`/`source` 出处，"
             "不默认端点、不拿 `radial_labels` 当档数；研究模式才允许按 labels/边界推测。"
             "声明解析错误（未知字段/参数、小数 gears、混入 NaN/Infinity 或非法数值）一律非零。")
    L.append("")
    if uncovered is None:
        L.append("- 未提供 `--params`，跳过覆盖检查（研究模式不核）。")
        L.append("")
    else:
        by_param = {}
        for u in uncovered:
            by_param.setdefault(u["param"], []).append(u)
        L.append("### 未覆盖（共 %d 个档/态，涉及 %d 个参数）" % (uncovered_n, len(by_param)))
        L.append("")
        if not uncovered:
            L.append("- （无；期望已覆盖 params.json 全部菜单参数的每个可达档/态）")
        else:
            for pname in sorted(by_param):
                us = by_param[pname]
                miss = "、".join(u["unit"] for u in us)
                L.append("- `%s`（%s，口径：%s）：缺 %s"
                         % (pname, us[0]["kind"], us[0]["convention"], miss))
        L.append("")
        L.append("### 无法确定覆盖（%d）" % undetermined_n)
        L.append("")
        if not undetermined:
            L.append("- （无）")
        else:
            for u in undetermined:
                L.append("- `%s`（%s）：%s" % (u["param"], u["kind"], u["reason"]))
        L.append("")
        L.append("### 参数覆盖一览")
        L.append("")
        L.append("- 已完整覆盖：**%d / %d** 个菜单参数" % (len(covered_params), len(requirements)))
        if undetermined:
            L.append("- 无法确定：%d 个（见上）" % undetermined_n)
        L.append("")

    L.append("## 局限（本报告没有证明的）")
    L.append("")
    for lim in limitations:
        L.append("- %s" % lim)
    L.append("")
    write_text(args.out, "\n".join(L))

    if args.json:
        write_json(args.json, {
            "tool": TOOL + ".check",
            "mode": "delivery" if delivery else "research",
            "generated_at": now_str(),
            "expect_file": os.path.abspath(args.expect),
            "source": exp.source,
            "t1": os.path.abspath(args.t1),
            "params_file": os.path.abspath(args.params) if args.params else None,
            "state_count": len(exp.states),
            "t1_state_count": len(states),
            "rows": rows,
            "per_state": per_state,
            "not_found_states": not_found,
            "input_anomaly_states": input_anomaly_states,
            "uncovered_menu_params": uncovered_params,
            "uncovered_units": uncovered if uncovered is not None else [],
            "undetermined_coverage": undetermined,
            "coverage_requirements": requirements,
            "warnings": warns,
            "check_failures": check_failures,
            "fail_row_count": business_fail,
            "not_found_count": missing,
            "business_fail_count": business_fail,
            "missing_count": missing,
            "uncovered_count": uncovered_n,
            "undetermined_count": undetermined_n,
            "ambiguous_count": ambiguous_n,
            "check_failure_count": len(check_failures),
            "exit_code": exit_code,
            "limitations": limitations,
        })

    print("[menu_expect_check check] 模式=%s 期望 %d 个状态 / 比对 %d 行；"
          "业务失败 %d；缺失 %d；未覆盖 %s；无法确定 %s；歧义 %d；检查失败 %d。"
          % ("delivery" if delivery else "research", len(exp.states), len(rows),
             business_fail, missing,
             "未评估" if uncovered is None else uncovered_n,
             "未评估" if uncovered is None else undetermined_n,
             ambiguous_n, len(check_failures)))
    for e in check_failures:
        print("  ! " + e)
    for r in fail_rows:
        print("  ✗ %s | %s | 期望 %s | 实际 %s" % (r["state"], r["item"], r["expect"], r["actual"]))
    for nf in not_found:
        print("  ? 未找到：%s" % nf["name"])
    if uncovered:
        print("  期望未覆盖的档/态：%d 个（详见报告）" % uncovered_n)
    print("  报告：%s" % os.path.abspath(args.out))
    return exit_code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="menu_expect_check.py",
        description="W5 编译态菜单断言：期望（交付说明）↔ 实测（构建后 T1）逐条比对。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  # 研究模式（局部检查）\n"
               "  gen-request --expect 期望.json --params <t4>/params.json --out t1_request.json\n"
               "  check --expect 期望.json --t1 <T1 输出目录> --params <t4>/params.json \\\n"
               "        --out 报告.md --json 报告.json\n"
               "  # 交付模式（严格，不能误放行）\n"
               "  gen-request --delivery --expect 期望.json --params <t4>/params.json --out t1_request.json\n"
               "  check --delivery --expect 期望.json --t1 <T1 输出目录> --params <t4>/params.json \\\n"
               "        --out 报告.md --json 报告.json\n")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen-request", help="期望.json + T4 params.json → 标准 T1 请求（并校验参数）")
    g.add_argument("--expect", required=True, help="期望.json")
    g.add_argument("--params", required=True, help="T4 导出的 params.json")
    g.add_argument("--out", required=True, help="输出 T1 请求 JSON 的路径")
    g.add_argument("--avatar", default=None, help="覆盖期望文件里的 avatar（默认用期望文件的）")
    g.add_argument("--scan-out", default=None, dest="scan_out",
                   help="写进请求 out 的 T1 扫描输出目录（默认 <--out 去掉扩展名>_t1）")
    g.add_argument("--settle-frames", type=int, default=30, dest="settle_frames",
                   help="T1 settle_frames（默认 30）")
    g.add_argument("--delivery", action="store_true",
                   help="交付严格模式：要求 source 与每条 state.note 出处非空")
    g.set_defaults(func=cmd_gen_request)

    c = sub.add_parser("check", help="期望.json + T1 扫描输出 → 逐条比对报告")
    c.add_argument("--expect", required=True, help="期望.json")
    c.add_argument("--t1", required=True, help="T1 扫描输出目录、state_*.json 或 states.json")
    c.add_argument("--out", required=True, help="输出 Markdown 报告的路径")
    c.add_argument("--json", default=None, help="可选，同时输出结构化 JSON 报告")
    c.add_argument("--params", default=None,
                   help="T4 params.json（研究模式可选；交付模式必给，否则核不了覆盖）")
    c.add_argument("--delivery", action="store_true",
                   help="交付严格模式：强制 --params 与出处，拒绝空检查结果，"
                        "核每档/每开关 0 与 1 覆盖，未覆盖/无法确定覆盖/歧义/输入异常一律非零退出")
    c.set_defaults(func=cmd_check)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
