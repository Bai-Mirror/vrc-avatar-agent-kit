#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""key_follow 候选 × T1 实测状态 → 同名键失配判定（任务 AM）。
【项目沉淀】通用工具
适用素体：无关
相关素材：T-05 key_follow + T1 实测状态
工具链　：Python 3（离线）
可复用性：★★ 审查工具链的一环
用途　　：key_follow 候选 × T1 实测状态 → 同名键失配判定 mismatch/benign/no_data。


背景：`AuditPartInventory` 的 `key_follow` 只列「件带身体同名键、件上没人写」的候选
（`candidates`），**候选不等于缺陷**。只有「件可见时，件的值 ≠ 身体的值」才可能穿模。
本脚本把候选逐条拿到 T1 实测状态里对账，判 `mismatch | benign | no_data`。

输入
----
* `--inventory <key_follow.json>`：`审查产出/key_follow/<工程>.json`
* `--t1 <目录> [--t1 ...]`：含 `state_*.json` 的目录；目录里没有就直接递归找。
  状态文件字段：`renderers[].{path,visible}`、`blendshapes{渲染器路径:{键:值}}`
  （**只列非零值，缺席即 0**）。

判定口径（与任务 AM / SOP 一致）
--------------------------------
1. 只比「件可见」的态；身体该键值取 `blendshapes[身体渲染器][含原键名的键]`，缺席 = 0。
2. `|身体值 - 件值| > 5` 记一条失配；`verdict`：
   * `mismatch` 有失配态；
   * `benign` 有可见态、身体键至少在某态被驱动为非 0、但可见态全部对得上（例：工程A
     stocking/FootNail 的 7 个身体非 0 态与两件可见态零重叠）；
   * `no_data` 没有可见态，或身体键在全部态都没被驱动为非 0（没有该类的拉满/开启态）。
3. **B-补-07 几何加权**：数值失配时再看 inventory 候选自带的 `geom`（AY，`AuditPartInventory`）：
   * `geom.body_piece_dist_mm.p50_delta_mm`（件到身体表面最近距离 p50，身体键 0→100 的差）
     与 `geom.piece_key_disp_mm.max`（件自身该键 0→100 的最大顶点位移）都 < `GEOM_BENIGN_MM`
     → 降为 `benign_geometry`（数值变了但几何没穿出来）；
   * 任一 ≥ 阈值 → 维持 `mismatch`；
   * `geom` 缺席 / `available=false` / 没有可比数值 → **维持数值原判**并标 `no_geometry=true`。
   原数值判定另存 `numeric_verdict`，几何明细写入 `geometry`。
4. **Play 构建后名字会变**（AAO 合并）：
   * 身体 → `$$AAO_AUTO_MERGE_SKINNED_MESH_n`，键 → `AAO_Merged_<键>_<n>` 或
     `<n>_<身体名>__<键>`；
   * 件 → 如 `[An-Labo]HoroNail_[空色]$FootNail_Default Variation$198`。
   匹配顺序：路径全等 → 末段包含件名（同父再收窄）→ 键前缀 `<n>_<件名>__`；
   身体：路径全等 → 末段/路径含身体名 → 键标记 `_<身体名>__`。
   多处命中或都命中不了记 `unmatched` 并原样列出，**不猜、不静默丢**。

用法
----
    python3 perception/key_follow_verdict.py \
        --inventory <审查产出>/key_follow/<工程>.json \
        --t1 <审查产出>/<工程>/t1_full_probes --out <...>/verdict_<工程>.json
    python3 perception/key_follow_verdict.py --selftest
    python3 perception/key_follow_verdict.py --aggregate <汇总.md> a.json b.json ...

只读，不启动 Unity。
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

DIFF_THRESHOLD = 5.0
# B-补-07：数值失配但几何几乎不动 → 不算缺陷。阈值 1 mm 来自 AY 实测：
# 工程D harness 的 body_piece_dist p50 恒为 5.8 mm（delta 0）判 benign_geometry；
# 乳贴修前 p50 5.74→14.95 mm（delta 9.21）判 mismatch。阈值留给实测/人工复核。
GEOM_BENIGN_MM = 1.0

BUST_TOKENS = ("breast", "bust", "chest", "胸")
FOOT_TOKENS = ("foot", "heel", "toe", "足", "ヒール", "hiheel", "nail")


# ────────────────────────── 基础读取与匹配 ──────────────────────────

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def state_id(path):
    """`.../t1_full_probes/state_ANEMONE__all.json` → `t1_full_probes/ANEMONE__all`。"""
    p = Path(path)
    stem = p.stem
    if stem.startswith("state_"):
        stem = stem[len("state_"):]
    return "%s/%s" % (p.parent.name, stem)


def load_states(t1_dirs):
    """读入全部 T1 状态，只保留对账需要的 renderers/blendshapes。"""
    states = []
    for d in t1_dirs:
        d = Path(d)
        files = sorted(d.glob("state_*.json"))
        if not files:
            files = sorted(d.glob("**/state_*.json"))
        if not files:
            print("WARN: %s 下没有 state_*.json" % d, file=sys.stderr)
            continue
        for f in files:
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                print("WARN: 读不了 %s：%s" % (f, e), file=sys.stderr)
                continue
            renderers = {}
            for r in raw.get("renderers", []):
                p = r.get("path")
                if p is not None:
                    renderers[p] = r
            states.append({
                "id": state_id(f),
                "file": str(f),
                "renderers": renderers,
                "blendshapes": raw.get("blendshapes", {}) or {},
            })
    return states


def key_hits(blendshapes_of_renderer, orig_key):
    """该渲染器上所有「键名包含原键名」的 (键, 值)。"""
    out = []
    for k, v in (blendshapes_of_renderer or {}).items():
        if key_token_match(k, orig_key):
            out.append((k, _num(v)))
    return out


def _alnum_boundary_ok(hay, needle, i):
    """needle 命中 hay 的 i 处时，两侧不能被「同类 alnum 字符」粘住。
    替 AAO 的 `_<n>` / `__` 改名留出下划线边界，同时挡掉 `Coat`→`TrenchCoat`
    这种裸子串误配（任务 AM 要求「包含」，但不能包含到别的件/键上）。"""
    j = i + len(needle)
    if needle[0].isalnum() and i > 0 and hay[i - 1].isalnum():
        return False
    if needle[-1].isalnum() and j < len(hay) and hay[j].isalnum():
        return False
    return True


def key_token_match(hay, needle):
    if not needle:
        return False
    start = 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            return False
        if _alnum_boundary_ok(hay, needle, i):
            return True
        start = i + 1


def leaf_token_match(hay, needle):
    """T1 末段里找件名。Play 后会夹 `$` 实例号（`$FootNail_Default Variation$198`），
    所以不能用全等；但命中两端必须是 `/`/`$` 或串首尾，挡掉 `Coat`→`TrenchCoat`。"""
    if hay == needle:
        return True
    if not needle:
        return False
    start = 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            return False
        before = hay[i - 1] if i > 0 else "/"
        j = i + len(needle)
        after = hay[j] if j < len(hay) else "/"
        if before in "/$" and after in "/$":
            return True
        start = i + 1


def single_value(hits):
    """命中多条时只有数值一致才算确定，否则返回 None（标 unmatched）。"""
    if not hits:
        return 0.0, None
    vals = {round(v, 6) for _, v in hits}
    if len(vals) != 1:
        return None, hits
    return hits[0][1], hits[0][0]


def resolve_body_renderer(state, body_name):
    paths = list(state["renderers"].keys())
    if body_name in paths:
        return body_name, "exact"
    leaf = [p for p in paths if p.split("/")[-1] == body_name]
    if len(leaf) == 1:
        return leaf[0], "leaf_exact"
    contains = [p for p in paths if body_name in p]
    if len(contains) == 1:
        return contains[0], "path_contains"
    if len(contains) > 1:
        return None, "path_ambiguous(%d)" % len(contains)
    marker = "_%s__" % body_name
    hits = {p for p, bl in state["blendshapes"].items()
            if any(marker in k for k in bl)}
    if len(hits) == 1:
        return hits.pop(), "key_marker"
    if len(hits) > 1:
        return None, "key_marker_ambiguous(%d)" % len(hits)
    return None, "not_found"


def resolve_piece_renderer(state, piece_path, orig_key):
    paths = list(state["renderers"].keys())
    if piece_path in paths:
        return piece_path, "exact"
    leaf = piece_path.split("/")[-1]
    cands = [p for p in paths if leaf_token_match(p.split("/")[-1], leaf)]
    if len(cands) == 1:
        return cands[0], "leaf_contains"
    if len(cands) > 1:
        # Play 后路径分隔符会从 `/` 变成 `$` 并夹实例号（`_Outfit$Outfit_X$62/stocking`），
        # 用候选的父级名（`Outfit_X`）在路径里是否存在来收窄。
        parent = piece_path.rsplit("/", 2)[-2] if piece_path.count("/") >= 1 else None
        if parent:
            sub = [p for p in cands if parent in p]
            if len(sub) == 1:
                return sub[0], "leaf_contains+parent"
        return None, "piece_ambiguous(%d)" % len(cands)
    # 件被 AAO 合并且末段被换成 $$AAO_AUTO_MERGE...：靠「键前缀 <n>_<件名>__」找。
    hits = set()
    for p, bl in state["blendshapes"].items():
        for k in bl:
            if not key_token_match(k, orig_key):
                continue
            if ("_%s__" % leaf) in k:
                hits.add(p)
    if len(hits) == 1:
        return hits.pop(), "key_prefix"
    if len(hits) > 1:
        return None, "key_prefix_ambiguous(%d)" % len(hits)
    return None, "not_found"


def body_value_for(state, body_name, orig_key):
    """(身体值, 身体渲染器, 匹配方式, 说明)。值 None 表示匹配不上。"""
    bpath, method = resolve_body_renderer(state, body_name)
    if bpath is not None:
        val, _ = single_value(key_hits(state["blendshapes"].get(bpath, {}), orig_key))
        if val is None:
            return None, bpath, method, "body_key_ambiguous"
        return val, bpath, method, None
    # 身体渲染器路径认不出：退而找「键里带 _<身体名>__ 标记」的唯一渲染器。
    marker = "_%s__" % body_name
    hits = set()
    for p, bl in state["blendshapes"].items():
        for k in bl:
            if key_token_match(k, orig_key) and marker in k:
                hits.add(p)
    if len(hits) == 1:
        p = hits.pop()
        val, _ = single_value(key_hits(state["blendshapes"][p], orig_key))
        if val is None:
            return None, p, "key_marker", "body_key_ambiguous"
        return val, p, "key_marker", None
    return None, None, method, "body_renderer_" + method


# ────────────────────────── 候选判定 ──────────────────────────

def classify(renderer, key):
    low = (renderer + " " + key).lower()
    if any(t in low for t in BUST_TOKENS):
        return "bust"
    if any(t in low for t in FOOT_TOKENS):
        return "foot"
    return "other"


def no_data_reason(states_visible, states_body_nonzero, body_unresolved,
                   piece_unresolved, klass):
    if piece_unresolved:
        return "件在全部态都匹配不上（Play 后可能改名或被 AAO 合并；见 unmatched）"
    if states_visible == 0:
        return "没有件可见的态"
    if body_unresolved:
        return "身体渲染器/键在全部态都匹配不上（可能被 AAO 合并后改名）"
    if states_body_nonzero == 0:
        return {
            "bust": "没有胸型拉满的态（身体该键从未被驱动为非 0）",
            "foot": "没有足/鞋键开启的态（身体该键从未被驱动为非 0）",
        }.get(klass, "没有任何态驱动身体该键为非 0")
    return "无可比态"


def verdict_of(candidate, states, body_name, avatars_label):
    renderer = candidate.get("renderer")
    key = candidate.get("key")
    klass = candidate.get("class") or classify(renderer or "", key or "")

    states_visible = 0
    states_body_nonzero = 0
    evaluated = 0
    mismatches = []
    max_diff = 0.0
    unmatched = []
    piece_paths = {}
    piece_methods_used = {}
    body_methods_used = {}

    for st in states:
        ppath, pmethod = resolve_piece_renderer(st, renderer, key)
        if ppath is None:
            unmatched.append({"state": st["id"], "side": "piece",
                              "reason": pmethod, "renderer": renderer})
            continue
        piece_paths.setdefault(ppath, 0)
        piece_paths[ppath] += 1
        piece_methods_used[pmethod] = piece_methods_used.get(pmethod, 0) + 1

        bval, bpath, bmethod, berr = body_value_for(st, body_name, key)
        if bval is None:
            unmatched.append({"state": st["id"], "side": "body",
                              "reason": berr, "renderer": bpath})
            continue
        body_methods_used[bmethod] = body_methods_used.get(bmethod, 0) + 1
        if abs(bval) > 1e-9:
            states_body_nonzero += 1

        rec = st["renderers"].get(ppath) or {}
        if not rec.get("visible"):
            continue

        states_visible += 1
        evaluated += 1
        pval, pkey = single_value(key_hits(st["blendshapes"].get(ppath, {}), key))
        if pval is None:
            unmatched.append({"state": st["id"], "side": "piece_key",
                              "reason": "piece_key_ambiguous", "renderer": ppath})
            continue
        diff = abs(bval - pval)
        if diff > max_diff:
            max_diff = diff
        if diff > DIFF_THRESHOLD:
            mismatches.append({"state": st["id"], "body": bval, "piece": pval,
                               "diff": round(diff, 3),
                               "body_renderer": bpath, "piece_renderer": ppath,
                               "piece_key": pkey})

    body_unresolved = bool(unmatched) and all(u["side"] == "body" for u in unmatched)
    piece_unresolved = any(u["side"] == "piece" for u in unmatched)
    if mismatches:
        numeric_verdict = "mismatch"
    elif states_visible > 0 and states_body_nonzero > 0:
        numeric_verdict = "benign"
    else:
        numeric_verdict = "no_data"

    # ── B-补-07：几何加权（只影响数值失配态；缺数据不猜，标 no_geometry 维持原判）──
    geom = candidate.get("geom") or {}
    g_avail = bool(geom.get("available"))
    g_dist = geom.get("body_piece_dist_mm") or {}
    g_piece = geom.get("piece_key_disp_mm") or {}
    p50_delta = g_dist.get("p50_delta_mm")
    piece_disp = g_piece.get("max")
    signals = []
    if isinstance(p50_delta, (int, float)):
        signals.append(abs(float(p50_delta)))
    if isinstance(piece_disp, (int, float)):
        signals.append(abs(float(piece_disp)))
    geom_verdict = "no_geometry"
    if g_avail and signals:
        geom_verdict = "benign_geometry" if max(signals) < GEOM_BENIGN_MM else "mismatch"
    no_geometry = geom_verdict == "no_geometry"

    verdict = numeric_verdict
    if numeric_verdict == "mismatch":
        if geom_verdict == "benign_geometry":
            verdict = "benign_geometry"
        elif geom_verdict == "mismatch":
            verdict = "mismatch"
        # no_geometry → 维持 numeric_verdict（mismatch），另标 no_geometry

    return {
        "avatar": avatars_label,
        "renderer": renderer,
        "key": key,
        "class": klass,
        "verdict": verdict,
        "numeric_verdict": numeric_verdict,
        "no_geometry": no_geometry,
        "geometry": {
            "available": g_avail,
            "verdict": geom_verdict,
            "p50_delta_mm": p50_delta,
            "piece_key_disp_max_mm": piece_disp,
            "threshold_mm": GEOM_BENIGN_MM,
            "body_key_disp_mm": geom.get("body_key_disp_mm"),
            "body_piece_dist_mm": geom.get("body_piece_dist_mm") or None,
            "geometry_source": geom.get("geometry_source"),
        },
        "states_visible": states_visible,
        "states_body_nonzero": states_body_nonzero,
        "states_evaluated": evaluated,
        "states_mismatch": mismatches,
        "max_diff": round(max_diff, 3),
        "piece_paths": sorted(piece_paths.keys()),
        "piece_methods_used": piece_methods_used,
        "body_methods_used": body_methods_used,
        "match": {
            "piece_methods": sorted({u["reason"] for u in unmatched if u["side"] == "piece"}) or ["matched"],
            "body_methods": sorted({u["reason"] for u in unmatched if u["side"] == "body"}) or ["matched"],
        },
        "unmatched": unmatched,
        "states_unmatched": len(unmatched),
        "missing": None if numeric_verdict != "no_data"
                   else no_data_reason(states_visible, states_body_nonzero,
                                       body_unresolved, piece_unresolved, klass),
    }


def build_result(inventory_path, t1_dirs, states):
    inv = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
    items = []
    seen = {}
    unmatched_top = []

    for av in inv.get("avatars", []):
        kf = av.get("key_follow") or {}
        by_class = {}
        for cls, lst in (kf.get("candidates_by_class") or {}).items():
            for c in (lst or []):
                by_class[(c.get("renderer"), c.get("key"))] = cls
        body_name = av.get("body_path")
        if not body_name:
            print("WARN: 头像 %r 没有 body_path，跳过" % av.get("name"), file=sys.stderr)
            continue
        for cand in (kf.get("candidates") or []):
            # 一个工程里同内容的头像变体（如工程C两套）会给同一 (身体,件,键) 重复候选，
            # 同一份 T1 数据判出来也一样，去重并记下都有哪些头像。
            dkey = (body_name, cand.get("renderer"), cand.get("key"))
            if dkey in seen:
                seen[dkey]["avatars"].append(av.get("name"))
                continue
            c = dict(cand)
            c["class"] = by_class.get((c.get("renderer"), c.get("key"))) or classify(
                c.get("renderer") or "", c.get("key") or "")
            item = verdict_of(c, states, body_name, av.get("name"))
            item["body_name"] = body_name
            item["avatars"] = [av.get("name")]
            seen[dkey] = item
            items.append(item)
            # 只要有任何态匹配不上就单列（不分工况），避免「部分态匹配失败被 benign/mismatch
            # 盖住」——任务 AM 要求匹配不上的不许静默丢。
            if item["unmatched"]:
                unmatched_top.append({
                    "avatar": av.get("name"), "renderer": item["renderer"],
                    "key": item["key"], "verdict": item["verdict"],
                    "reason": item["missing"] or "部分态匹配不上",
                    "match": item["match"], "n_unmatched_states": len(item["unmatched"]),
                })

    return {
        "tool": "key_follow_verdict",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "inventory": str(inventory_path),
        "t1_dirs": [str(d) for d in t1_dirs],
        "state_count": len(states),
        "candidates": items,
        "unmatched": unmatched_top,
        "summary": {
            "candidates": len(items),
            "mismatch": sum(1 for i in items if i["verdict"] == "mismatch"),
            "benign_geometry": sum(1 for i in items if i["verdict"] == "benign_geometry"),
            "benign": sum(1 for i in items if i["verdict"] == "benign"),
            "no_data": sum(1 for i in items
                           if i["verdict"] == "no_data" and not piece_unmatched_item(i)),
            "no_geometry": sum(1 for i in items if i.get("no_geometry")),
            "unmatched_candidates": sum(1 for i in items if piece_unmatched_item(i)),
            "candidates_with_unmatched_states": len(unmatched_top),
            "unmatched_states_total": sum(len(i["unmatched"]) for i in items),
        },
    }


# ────────────────────────── 输出 ──────────────────────────

def fmt_states(ms, limit=3):
    if not ms:
        return ""
    out = []
    for m in ms[:limit]:
        out.append("%s(身体%g/件%g)" % (m["state"], m["body"], m["piece"]))
    if len(ms) > limit:
        out.append("…共 %d 态" % len(ms))
    return "；".join(out)


def piece_unmatched_item(item):
    """该候选的件是否在全部态都匹配不上（含歧义）。"""
    return item["states_visible"] == 0 and any(
        m in ("not_found",) or m.startswith("piece_ambiguous") or m.startswith("key_prefix_ambiguous")
        for m in item["match"]["piece_methods"])


def state_match_summary(item):
    if not item["unmatched"]:
        return "全匹配"
    sides = {}
    for u in item["unmatched"]:
        sides[u["side"]] = sides.get(u["side"], 0) + 1
    return "失败 %d 态(%s)" % (len(item["unmatched"]),
                              ",".join("%s×%d" % kv for kv in sorted(sides.items())))


def failure_methods(item):
    ms = set(item["match"]["piece_methods"]) | set(item["match"]["body_methods"])
    ms.discard("matched")
    return ";".join(sorted(ms)) or "?"


def render_markdown(result):
    lines = []
    lines.append("# key_follow 失配判定 — %s" % Path(result["inventory"]).stem)
    lines.append("")
    lines.append("- 生成：%s" % result["generated_at"])
    lines.append("- T1 目录：%s" % "，".join(result["t1_dirs"]))
    lines.append("- 状态数：%d；候选 %d（mismatch %d / benign_geometry %d / benign %d / no_data %d / 全态匹配不上 %d；no_geometry %d）" % (
        result["state_count"], result["summary"]["candidates"], result["summary"]["mismatch"],
        result["summary"].get("benign_geometry", 0), result["summary"]["benign"],
        result["summary"]["no_data"], result["summary"]["unmatched_candidates"],
        result["summary"].get("no_geometry", 0)))
    lines.append("- 口径：件可见时 `|身体该键 - 件该键| > %g` 记失配；缺席即 0。"
                 "B-补-07：数值失配但 `p50_delta_mm` 与 `piece_key_disp_mm.max` 均 < %g mm → "
                 "`benign_geometry`；缺 geom → 维持原判并标 `no_geometry`。" % (
                     DIFF_THRESHOLD, GEOM_BENIGN_MM))
    lines.append("")
    lines.append("| 件 | 键 | 判定 | 数值原判 | 几何 p50Δ/件位移(mm) | no_geom | 可见态 | 身体非0态 | 失配态数 | 最大差 | 匹配 | 典型状态 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for it in result["candidates"]:
        g = it.get("geometry") or {}
        def _fmt(v):
            return "-" if not isinstance(v, (int, float)) else "%.2f" % v
        lines.append("| %s | %s | **%s** | %s | %s/%s | %s | %d | %d | %d | %.3f | %s | %s |" % (
            it["renderer"], it["key"], it["verdict"], it.get("numeric_verdict", it["verdict"]),
            _fmt(g.get("p50_delta_mm")), _fmt(g.get("piece_key_disp_max_mm")),
            "yes" if it.get("no_geometry") else "no",
            it["states_visible"],
            it["states_body_nonzero"], len(it["states_mismatch"]), it["max_diff"],
            state_match_summary(it), fmt_states(it["states_mismatch"])))
    no_data = [i for i in result["candidates"]
               if i["verdict"] == "no_data" and not piece_unmatched_item(i)]
    if no_data:
        lines.append("")
        lines.append("## no_data 原因")
        lines.append("")
        lines.append("| 件 | 键 | 原因 |")
        lines.append("|---|---|---|")
        for i in no_data:
            lines.append("| %s | %s | %s |" % (i["renderer"], i["key"], i["missing"]))
    un = [i for i in result["candidates"] if i["unmatched"]]
    if un:
        lines.append("")
        lines.append("## 匹配不上（含部分态；未判/未计）")
        lines.append("")
        lines.append("| 件 | 键 | 判定 | 失败态 | 匹配方式 | 说明 |")
        lines.append("|---|---|---|---|---|---|")
        for i in un:
            lines.append("| %s | %s | %s | %d | %s | %s |" % (
                i["renderer"], i["key"], i["verdict"], len(i["unmatched"]),
                failure_methods(i),
                i["missing"] or "部分态匹配不上"))
    return "\n".join(lines) + "\n"


def aggregate_markdown(results, title, note=""):
    lines = ["# %s" % title, ""]
    if note:
        lines.append(note)
        lines.append("")
    lines.append("| 工程 | 状态数 | 候选 | mismatch | benign_geometry | benign | no_data | 全态匹配不上 | 有失败态候选 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        s = r["summary"]
        lines.append("| %s | %d | %d | **%d** | %d | %d | %d | %d | %d |" % (
            Path(r["inventory"]).stem, r["state_count"], s["candidates"],
            s["mismatch"], s.get("benign_geometry", 0), s["benign"], s["no_data"],
            s["unmatched_candidates"],
            s.get("candidates_with_unmatched_states", 0)))
    for r in results:
        lines.append("")
        lines.append("## %s" % Path(r["inventory"]).stem)
        lines.append("")
        mm = [i for i in r["candidates"] if i["verdict"] == "mismatch"]
        bg = [i for i in r["candidates"] if i["verdict"] == "benign_geometry"]
        bn = [i for i in r["candidates"] if i["verdict"] == "benign"]
        un = [i for i in r["candidates"] if piece_unmatched_item(i)]
        nd = [i for i in r["candidates"]
              if i["verdict"] == "no_data" and not piece_unmatched_item(i)]
        lines.append("mismatch **%d** / benign_geometry %d / benign %d / no_data %d / 全态匹配不上 %d" % (
            len(mm), len(bg), len(bn), len(nd), len(un)))
        if mm:
            lines.append("")
            lines.append("### mismatch")
            lines.append("")
            lines.append("| 件 | 键 | 失配态数 | 最大差 | p50Δ(mm) | 典型状态 |")
            lines.append("|---|---|---|---|---|---|")
            for i in mm:
                g = i.get("geometry") or {}
                p50 = g.get("p50_delta_mm")
                lines.append("| %s | %s | %d | %.3f | %s | %s |" % (
                    i["renderer"], i["key"], len(i["states_mismatch"]), i["max_diff"],
                    "-" if not isinstance(p50, (int, float)) else "%.2f" % p50,
                    fmt_states(i["states_mismatch"], 2)))
        if bg:
            lines.append("")
            lines.append("### benign_geometry（数值失配但几何 <%.1f mm）" % GEOM_BENIGN_MM)
            lines.append("")
            lines.append("| 件 | 键 | 失配态数 | p50Δ(mm) | 件位移(mm) |")
            lines.append("|---|---|---|---|---|")
            for i in bg:
                g = i.get("geometry") or {}
                p50 = g.get("p50_delta_mm")
                pd = g.get("piece_key_disp_max_mm")
                lines.append("| %s | %s | %d | %s | %s |" % (
                    i["renderer"], i["key"], len(i["states_mismatch"]),
                    "-" if not isinstance(p50, (int, float)) else "%.2f" % p50,
                    "-" if not isinstance(pd, (int, float)) else "%.2f" % pd))
        if nd:
            lines.append("")
            lines.append("### no_data（说明缺哪种态）")
            lines.append("")
            lines.append("| 件 | 键 | 原因 |")
            lines.append("|---|---|---|")
            for i in nd:
                lines.append("| %s | %s | %s |" % (i["renderer"], i["key"], i["missing"]))
        if un:
            lines.append("")
            lines.append("### unmatched（全态匹配不上，未判）")
            lines.append("")
            lines.append("| 件 | 键 | 匹配方式 | 说明 |")
            lines.append("|---|---|---|---|")
            for i in un:
                lines.append("| %s | %s | %s | %s |" % (
                    i["renderer"], i["key"],
                    failure_methods(i),
                    i["missing"]))
        partial = [i for i in r["candidates"] if i["unmatched"] and not piece_unmatched_item(i)]
        if partial:
            lines.append("")
            lines.append("### 部分态匹配失败（已判但没覆盖全态）")
            lines.append("")
            lines.append("| 件 | 键 | 判定 | 失败态 | 匹配方式 |")
            lines.append("|---|---|---|---|---|")
            for i in partial:
                lines.append("| %s | %s | %s | %d | %s |" % (
                    i["renderer"], i["key"], i["verdict"], len(i["unmatched"]),
                    failure_methods(i)))
    return "\n".join(lines) + "\n"


# ────────────────────────── selftest ──────────────────────────

def selftest(root):
    ok = True
    base = Path(root) / "_长程任务_20260918" / "审查产出"

    # ① 工程A：stocking / FootNail 应为 benign（7 个身体非 0 态与件可见态零重叠）
    inv = base / "key_follow" / "工程A.json"
    t1 = base / "工程A" / "t1_full_probes"
    states = load_states([t1])
    res = build_result(inv, [t1], states)
    print("== selftest ① 工程A (%d 态) ==" % res["state_count"])
    print(render_markdown(res))
    for want in ("kaguya_cloth/stocking",
                 "[An-Labo]HoroNail_[空色]/FootNail_Default Variation"):
        hit = [i for i in res["candidates"] if i["renderer"] == want]
        if not hit:
            print("FAIL: 找不到候选 %s" % want)
            ok = False
        elif hit[0]["verdict"] != "benign":
            print("FAIL: %s 期望 benign，实为 %s" % (want, hit[0]["verdict"]))
            ok = False
        else:
            print("ok: %s → benign（可见 %d 态，最大差 %.3f）" % (
                want, hit[0]["states_visible"], hit[0]["max_diff"]))

    # ② 工程E：手工构造 (A)Shirt × Breast_big(limit)，set3_repoppin bust1 应判 mismatch（身体 100、件 0）
    inv = base / "key_follow" / "工程E.json"
    t1 = base / "工程E" / "t1_sweep_out"
    states = load_states([t1])
    inv_obj = json.loads(Path(inv).read_text(encoding="utf-8"))
    synth = {"renderer": "Re-Poppin' Cat_RURUNE/(A)Shirt", "key": "Breast_big(limit)",
             "piece_current_weight": 0, "body_writers": [], "piece_writers": []}
    inv_obj["avatars"][0]["key_follow"]["candidates"] = [synth]
    tmp_inv = Path(root) / "_长程任务_20260918" / "派工" / "tmp" / "bf" / "easy_synth_inventory.json"
    tmp_inv.parent.mkdir(parents=True, exist_ok=True)
    tmp_inv.write_text(json.dumps(inv_obj, ensure_ascii=False, indent=1), encoding="utf-8")
    res2 = build_result(tmp_inv, [t1], states)
    print("== selftest ② 工程E 手工候选 (%d 态) ==" % res2["state_count"])
    print(render_markdown(res2))
    hit = res2["candidates"][0] if res2["candidates"] else None
    if hit is None or hit["verdict"] != "mismatch":
        print("FAIL: 手工候选期望 mismatch，实为 %s" % (hit and hit["verdict"]))
        ok = False
    else:
        bust1 = [m for m in hit["states_mismatch"] if "bust1" in m["state"]]
        if not bust1:
            print("FAIL: mismatch 里没有 set3_repoppin__all__bust1 态")
            ok = False
        elif not (abs(bust1[0]["body"] - 100) < 1e-6 and abs(bust1[0]["piece"]) < 1e-6):
            print("FAIL: bust1 期望身体 100/件 0，实为 身体 %g/件 %g" % (
                bust1[0]["body"], bust1[0]["piece"]))
            ok = False
        else:
            print("ok: (A)Shirt × Breast_big(limit) → mismatch（%d 失配态，最大差 %.3f，"
                  "bust1 身体 %g/件 %g）" % (
                      len(hit["states_mismatch"]), hit["max_diff"],
                      bust1[0]["body"], bust1[0]["piece"]))

    # ③ B-补-07 几何加权：同一数值失配候选，按 geom 分成 benign_geometry / mismatch / no_geometry。
    #    几何数据形如 AY 的 AttachFollowGeometry：p50_delta_mm + piece_key_disp_mm.max <1mm 才算不动。
    def _geom(p50, piece_max, avail=True):
        g = {"available": avail,
             "body_piece_dist_mm": {"p50_delta_mm": p50},
             "geometry_source": "bake"}
        if piece_max is not None:
            g["piece_key_disp_mm"] = {"max": piece_max}
        return g

    cases = [
        ("<1mm 降 benign_geometry", _geom(0.4, 0.3), "benign_geometry", False),
        ("≥1mm 维持 mismatch", _geom(9.21, 12.0), "mismatch", False),
        ("缺 geom 维持原判 no_geometry", None, "mismatch", True),
        ("available=false 维持原判 no_geometry", _geom(0.0, 0.0, avail=False), "mismatch", True),
    ]
    for name, geom, want_v, want_ng in cases:
        c = dict(synth)
        if geom is not None:
            c["geom"] = geom
        inv_obj["avatars"][0]["key_follow"]["candidates"] = [c]
        tmp_inv.write_text(json.dumps(inv_obj, ensure_ascii=False, indent=1), encoding="utf-8")
        rr = build_result(tmp_inv, [t1], states)
        got = rr["candidates"][0] if rr["candidates"] else {}
        good = got.get("verdict") == want_v and bool(got.get("no_geometry")) == want_ng
        ok = ok and good
        print("%s B-补-07 %s → %s（no_geometry=%s；p50Δ=%s 件位移=%s）" % (
            "ok:" if good else "FAIL:", name, got.get("verdict"),
            got.get("no_geometry"), (got.get("geometry") or {}).get("p50_delta_mm"),
            (got.get("geometry") or {}).get("piece_key_disp_max_mm")))

    print("\n%s" % ("ALL PASS" if ok else "SELFTEST FAILED"))
    return 0 if ok else 1


# ────────────────────────── CLI ──────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description="key_follow 候选 × T1 实测状态失配判定")
    ap.add_argument("--inventory", help="key_follow JSON")
    ap.add_argument("--t1", action="append", default=[], help="含 state_*.json 的目录（可多次）")
    ap.add_argument("--out", help="verdict.json 输出路径")
    ap.add_argument("--aggregate", nargs="+", metavar="FILE",
                    help="汇总模式：第一个参数是输出 .md，其后是要汇总的 verdict.json")
    ap.add_argument("--title", default="key_follow 同名键失配判定汇总")
    ap.add_argument("--note", default="")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parents[4]

    if args.selftest:
        return selftest(root)

    if args.aggregate:
        out_md = Path(args.aggregate[0])
        results = [json.loads(Path(p).read_text(encoding="utf-8"))
                   for p in args.aggregate[1:]]
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(aggregate_markdown(results, args.title, args.note), encoding="utf-8")
        print("写出 %s（%d 个工程）" % (out_md, len(results)))
        return 0

    if not args.inventory or not args.t1:
        ap.error("需要 --inventory 与至少一个 --t1（或用 --selftest / --aggregate）")

    states = load_states(args.t1)
    result = build_result(args.inventory, args.t1, states)
    md = render_markdown(result)
    print(md)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("写出 %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
