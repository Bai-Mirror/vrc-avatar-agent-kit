#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""key_gaps.py —— key_follow 盲区补检：件上缺身体被写的键 / 写者挂错件（任务 B-补-06）。
【项目沉淀】通用工具
适用素体：无关
相关素材：T-05 盘点 + T1/T-11 输出
工具链　：Python 3（离线）
可复用性：★★ 审查工具链的一环
用途　　：key_follow 盲区补检：件上缺身体被写的键、写者挂错件。


为什么
------
`key_follow`（`AuditPartInventory` 的 `key_follow` 段 + `key_follow_verdict.py`）只查
「**件自带**身体同名键、但件上没人驱动」的候选。本轮 6 个已修形态键缺陷里只有 1 个在它范围内：

* **件上缺键**：工程D Rurune-Black 鞋缺平脚键（B1）、乳贴缺 `Breast_small` /
  `Breast_big(limit)`（B2/B3）——件上**根本没有**该键/没有写该键的驱动，key_follow 抓不到。
* **写者挂错件**：工程A MMN 平脚键挂在袜子上（A3）、工程B垂耳兔 11 个收缩键挂在整套根上
  （R1）——键在、但宿主不是盖住该部位的件。

本脚本用**离线 inventory**（`审查产出/key_follow/<工程>.json`）做这两类检查，只读、不启 Unity。

两类检查的判据（都可被 Claude 复核，故全部带 `confidence`）
----------------------------------------------------------
0. **覆盖部位**一律取 inventory `renderers[].covers`（HumanBodyBones 名）：
   `foot` → Foot/Toes；`bust` → Chest/UpperChest/Spine。`covers=Other/unknown/空` 的件
   **不参与判定**，另进 `unknown_cover` 单列（B-补-18 的 MA MergeArmature covers 映射
   重导后，这些件才会有具体部位）。
1. `missing_key`（件上缺键）：对每个「有件级、且该件确实覆盖该键部位」的身体被写键 K，
   覆盖同部位的件里**既不是 K 的宿主、也没出现在 `synced`/`candidates` 里**的 → 报缺键。
   * `candidates`（键在件上、只是没人写）归 key_follow，不算缺键，避免重复报。
   * 没有「覆盖该部位的件级宿主」时不报（避免把本来不需要该键的件全报一遍）。
2. `misplaced_writer`（写者挂错件），**只报宿主不在任何覆盖该键部位的件上的情况**：
   * 宿主是**祖先/根/控制物体**（路径不是渲染器）→ 挂错（R1，confidence=high）。
   * 宿主是件、但该件 `covers` 与该键作用部位**不相交** → 挂错（confidence=mid）；
     `covers=Other` 判不了 → 不报，单列。
3. 输出（`missing_key` / `misplaced_writer` / `unknown_cover`）**按置信度 high→mid→low 排序**。

当前数据缺口（需要 `AuditPartInventory` 补，见 README「B-补-06 需求清单」）
----------------------------------------------------------------------------
* **B-补-18 已做**：MA MergeArmature 服装件按 `mergeTarget`+骨名映射到头像人形骨
  （`AuditPartInventory.RegionMapper`），但**要用新工具重导 inventory** 才有具体 covers。
  旧 inventory 仍是 `covers=['Other']`，本脚本把它们单列、不参与判定。
* inventory 不带每渲染器的**形态键名清单**，无法把「件上真缺键」与「键在但没人写」分到
  渲染器级；本脚本用 `synced`/`candidates` 的**有无**做近似。

**现版 7 单为什么是 0/0**：旧 inventory 的 `covers` 全 `Other` → 所有件落 `unknown_cover`
（不参与判定），`missing_key`/`misplaced_writer` 都判不了。**这是「覆盖未知不下结论」，
不是「无缺陷」**。B-补-18 重导 covers 后的复验步骤与预期（B1/B2/B3/A3/R1；A3 落
missing_key（鞋）或 misplaced_writer（袜）皆算报出，判据从导出 `covers` 读）见
`perception/README.md` 的「key_follow 盲区补检」节与
`_长程任务_20260918/派工/tmp/bo/BF_B补06_replay步骤_修正.md`。

用法
----
    python3 perception/key_gaps.py --inventory <...>/COMM-xxx.json [--out gaps.json]
    python3 perception/key_gaps.py --all <key_follow 目录> --out gaps_汇总.json
    python3 perception/key_gaps.py --selftest
    python3 perception/key_gaps.py --requests        # 打印对 AuditPartInventory 的需求清单
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
KF_DIR = os.path.abspath(os.path.join(
    HERE, "..", "..", "..", "..",
    "_长程任务_20260918", "审查产出", "key_follow"))

FOOT_KEY_TOKENS = ("heel", "foot_flat")
BUST_KEY_TOKENS = ("breast",)

# 件 → 槽位。顺序即优先级（`Shoes_Highheels` 先撞 footwear 的 highheel，不会被 legwear 抢）。
SLOT_RULES = (
    ("footwear", ("shoe", "boot", "sandal", "loafer", "sneaker", "slipper",
                  "highheel", "highheels", "ugly_shoes")),
    ("legwear", ("sock", "stocking", "tights", "legging", "highsocks", "knee_high")),
    ("underwear", ("panties", "underwear", "bandage", "bikini", "bra_")),
    ("outer", ("jacket", "coat", "parker", "outer", "cape", "cardigan",
               "windbreak", "hood")),
    ("bottom", ("pants", "skirt", "culottes", "shorts", "jean", "trouser", "bottom")),
    ("top", ("shirt", "_top", "top_", "tops", "jersey", "maid", "sweater", "blouse",
             "corset", "camisole", "uniform", "suit", "sailor", "hoodie", "dress",
             "leotard", "onepiece")),
)

# 键类别 → 应驱动它的主用槽位
KEY_SLOTS = {
    "foot": ("footwear",),
    "bust": ("top", "outer", "underwear"),
}

# B-补-06：键类别 → 该键作用的人形部位（HumanBodyBones 名，来自 inventory `covers`）。
# 「覆盖该键部位的件」只认 covers 命中这些区域；covers 只有 Other/unknown/空 = 覆盖未知。
# foot 只取 Foot/Toes（不含 LowerLeg）：袜子常盖小腿，若把 LowerLeg 算进 foot，
# 「写者挂袜」的 A3 型会被当成「袜子也覆盖了脚」而漏报。
CLASS_REGIONS = {
    "foot": ("LeftFoot", "RightFoot", "LeftToes", "RightToes"),
    "bust": ("Chest", "UpperChest", "Spine"),
}
UNKNOWN_COVER = {"", "other", "unknown"}
CONFIDENCE_RANK = {"high": 0, "mid": 1, "low": 2}

AUDIT_INVENTORY_REQUESTS = [
    "每个渲染器的**形态键名清单**（mesh 上实际存在的 blendshape 名），用来把「件上真缺键」"
    "与「键在件上、只是没人写」（key_follow candidate）分到渲染器级；现在只能用有无 "
    "synced/candidates 近似。",
    "衣物件的**覆盖部位**：B-补-18 已把 MA MergeArmature 服装骨按 mergeTarget+骨名映射到"
    "头像人形骨（RegionMapper），但**必须用新工具重导 inventory** 才会出现具体 covers；"
    "旧 inventory 仍是 covers=['Other']，key_gaps 会把它们单列进 unknown_cover、不参与判定。",
    "写者宿主的**精确归属**：`key_follow.body_written_keys[].writers[].component_path` 只有路径，"
    "且可能指向根/MA 物体；补『该组件归属到哪个渲染器/部件』，或补 transform 层级让离线能判祖先。",
    "每个件的**开关来源**与身体键触发条件的对应（现有 switch.sources 已有，补『哪个开关档位"
    "需要该键 =100/0』），用于判「主件（鞋）缺写者」这类条件性缺陷。",
    "件的**槽位分类**（shoes/boots/socks/top/outer/…）：现在仍按 path/name token 猜（SLOT_RULES），"
    "只用于 unknown_cover 的分组与显示；判定本身已改用 covers。",
    "素体**全量键表**(`开发工具/素体档案/Kaguya.yaml` 的 `all_keys:`)——用于判断身体是否存在该键，"
    "缺时可先把『身体被写键』当全集（B-补-02）。",
]


# ────────────────────────── 基础判定 ──────────────────────────

def key_class(key):
    """foot / bust / None。nail 类外形键、shrink 类收缩键不算「贴合被写键」的同期对比，排除。"""
    if not key:
        return None
    low = key.lower()
    if "nail" in low:
        return None
    if any(t in low for t in FOOT_KEY_TOKENS):
        return "foot"
    if any(t in low for t in BUST_KEY_TOKENS) and "shrink" not in low:
        return "bust"
    return None


def piece_slot(path, name=None):
    low = ("%s/%s" % (path, name or "")).lower()
    for slot, tokens in SLOT_RULES:
        for t in tokens:
            if t in low:
                return slot
    return None


def _hosts(entry):
    hs = set()
    for w in (entry.get("writers") or []):
        cp = w.get("component_path")
        if cp:
            hs.add(cp)
    return hs


def _resolve_host(host, renderer_paths):
    """返回 (exact, descendants, siblings)。

    * exact：host 本身就是一个渲染器；
    * descendants：host 是渲染器的祖先（`host/a/b`）；
    * siblings：host 不是渲染器，但同一父目录下有渲染器（例：MA 控制物体
      `.../08_WhitePink_Milfy_MA/ModularAvatar` 与 `.../08_WhitePink_Milfy_MA/Shoes` 同级）。
    三者用来判「宿主是不是一个盖住该部位的件」。
    """
    exact = [p for p in renderer_paths if p == host]
    if exact:
        return exact, [], []
    desc = [p for p in renderer_paths if p.startswith(host + "/")]
    parent = host.rsplit("/", 1)[0] if "/" in host else ""
    sib = [p for p in renderer_paths if parent and p.startswith(parent + "/")] if parent else []
    return [], desc, sib


# 控制物体（MA/骨架根）：宿主是这些时，不是「盖住某部位的件」
CONTROL_HOST_TOKENS = ("modularavatar", "modular avatar", "armature", "avatar_root",
                       "ma_shape", "shape_changer", "shape changer")


def _finding(category, avatar, key, target, confidence="mid", **kw):
    d = {"category": category, "avatar": avatar, "key": key, "target": target,
         "advisory": True, "confidence": confidence}
    d.update(kw)
    return d


def piece_regions(renderer):
    """件的已知覆盖部位（去掉 Other/unknown/空）。空集 = 覆盖未知。"""
    cov = renderer.get("covers") or []
    out = set()
    for c in cov:
        s = str(c).strip()
        if s.lower() not in UNKNOWN_COVER:
            out.add(s)
    return out


def covers_key_region(renderer, cls):
    """该件的 covers 是否命中该键类别作用的人形部位。"""
    want = set(CLASS_REGIONS.get(cls) or ())
    return bool(piece_regions(renderer) & want)


def sort_findings(findings):
    """输出按置信度排序（high→mid→low），同档按键名/件路径稳定排序。"""
    return sorted(findings, key=lambda f: (
        CONFIDENCE_RANK.get(f.get("confidence"), 9),
        str(f.get("key") or ""), str(f.get("target") or "")))


def analyze_inventory(inv, source=None):
    """返回 {missing_key, misplaced_writer, unknown_cover, notes, avatar_count}。"""
    missing, misplaced, unknown_cover, notes = [], [], [], []
    seen = set()
    avatars = inv.get("avatars") or []
    for av in avatars:
        kf = av.get("key_follow") or {}
        if not kf:
            notes.append("头像 %r 没有 key_follow 段，跳过" % av.get("name"))
            continue
        aname = av.get("name")
        rlist = av.get("renderers") or []
        renderers, renderer_paths = {}, []
        for r in rlist:
            p = r.get("path")
            if p is None:
                continue
            renderers[p] = r
            renderer_paths.append(p)
        name_of = {p: renderers[p].get("name") for p in renderer_paths}
        slot_of = {p: piece_slot(p, name_of.get(p)) for p in renderer_paths}
        body_path = av.get("body_path")
        synced = {(c.get("renderer"), c.get("key")) for c in (kf.get("synced") or [])}
        candidates = {(c.get("renderer"), c.get("key")) for c in (kf.get("candidates") or [])}

        for entry in (kf.get("body_written_keys") or []):
            key = entry.get("key")
            cls = key_class(key)
            hosts = _hosts(entry)
            host_set = set()
            root_hosts = []
            for h in hosts:
                exact, desc, sib = _resolve_host(h, renderer_paths)
                if exact:
                    host_set.update(exact)
                elif len(desc) == 1:
                    host_set.add(desc[0])
                elif len(desc) >= 2:
                    root_hosts.append((h, len(desc), "ancestor"))
                elif any(t in h.rsplit("/", 1)[-1].lower() for t in CONTROL_HOST_TOKENS):
                    root_hosts.append((h, len(sib), "control"))
                elif len(sib) == 1:
                    host_set.add(sib[0])
                else:
                    # 宿主不是渲染器、也对不上唯一件：归属不了，记 note 不猜（不报挂错）
                    notes.append("avatar=%s key=%s 宿主 %s 不是渲染器/不唯一，归属不了，"
                                 "跳过挂错判定" % (aname, key, h))

            # ① 根/祖先/控制物体宿主：宿主根本不是「覆盖件」，与键类别无关都算挂错（R1）
            for h, n, kind in root_hosts:
                rec = ("root", key, h)
                if rec in seen:
                    continue
                seen.add(rec)
                misplaced.append(_finding(
                    "misplaced_writer", aname, key, h, host_kind=kind,
                    n_descendants=n, confidence="high",
                    reason="宿主是%s（对照 %d 个渲染器），不是盖住该部位的件；"
                           "件的开关与它无关时键不会随件收放"
                           % ("控制物体" if kind == "control" else "祖先/根", n)))

            if not cls:
                continue
            want_regions = set(CLASS_REGIONS[cls])

            # 覆盖该键部位、且宿主确实是「件」的集合。没有这样的件级宿主时不报缺键，
            # 免得把「本来就不需要这键的件」全报一遍（降噪）。
            region_hosts = [p for p in sorted(host_set)
                            if p in renderers and covers_key_region(renderers[p], cls)]

            # ② 件上缺键：覆盖该键部位、却不是宿主，也不在 synced/candidates 的件
            if region_hosts:
                for p in renderer_paths:
                    if p == body_path:
                        continue   # 身体本身覆盖所有部位，不是「该带键的服装件」
                    if not covers_key_region(renderers[p], cls):
                        continue
                    if p in host_set:
                        continue
                    if (p, key) in synced or (p, key) in candidates:
                        continue
                    rec = ("missing", key, p)
                    if rec in seen:
                        continue
                    seen.add(rec)
                    missing.append(_finding(
                        "missing_key", aname, key, p, key_class=cls, slot=slot_of.get(p),
                        covers=sorted(piece_regions(renderers[p])), confidence="mid",
                        reason="同部位已有件级宿主 %s，本件覆盖 %s 却既不是宿主、也不在 "
                               "synced/candidates 里 → 疑似件上缺键/缺驱动（key_follow 盲区）"
                               % (region_hosts, sorted(piece_regions(renderers[p])))))

            # ③ 写者挂错件：**没有任何宿主落在覆盖该键部位的件上**时，宿主件里覆盖已知、
            #    却与该键作用部位不相交的 → 挂错（A3）。只要有一个宿主在覆盖件上，就认为
            #    该键挂对了地方，不再对同键的其它宿主报挂错（避免「袜子也需要这键」误报）。
            #    覆盖未知（covers=Other）的宿主判不了，不报、单列。
            if not region_hosts:
                for p in sorted(host_set):
                    if p not in renderers:
                        continue
                    cov = piece_regions(renderers[p])
                    if not cov:
                        continue
                    if cov & want_regions:
                        continue
                    rec = ("cover", key, p)
                    if rec in seen:
                        continue
                    seen.add(rec)
                    misplaced.append(_finding(
                        "misplaced_writer", aname, key, p,
                        host_kind="cover_mismatch", slot=slot_of.get(p),
                        host_covers=sorted(cov), want_regions=sorted(want_regions),
                        confidence="mid",
                        reason="该键没有任何宿主落在覆盖 %s 的件上；本宿主只覆盖 %s，"
                               "键挂在盖不住该部位、或不该由它驱动的件上"
                               % (sorted(want_regions), sorted(cov))))

            # ④ covers=Other 的件不参与缺键判断，单列（B-补-18 映射重导后再生效）
            want_slots = KEY_SLOTS.get(cls, ())
            for p in renderer_paths:
                if p == body_path:
                    continue
                if slot_of.get(p) not in want_slots:
                    continue
                if piece_regions(renderers[p]):
                    continue
                if p in host_set:
                    continue
                if (p, key) in synced or (p, key) in candidates:
                    continue
                rec = ("unknown_cover", key, p)
                if rec in seen:
                    continue
                seen.add(rec)
                unknown_cover.append(_finding(
                    "unknown_cover", aname, key, p, key_class=cls, slot=slot_of.get(p),
                    confidence="low",
                    reason="covers=Other/unknown，覆盖部位未知，缺键判不了；单列待 "
                           "B-补-18 的 MA MergeArmature covers 映射重导后复核"))
    return {
        "source": source,
        "avatar_count": len(avatars),
        "missing_key": sort_findings(missing),
        "misplaced_writer": sort_findings(misplaced),
        "unknown_cover": sort_findings(unknown_cover),
        "notes": notes,
    }


def analyze_files(paths):
    results = []
    for p in paths:
        try:
            inv = json.loads(open(p, encoding="utf-8").read())
        except Exception as e:  # noqa: BLE001
            results.append({"source": p, "error": str(e),
                            "missing_key": [], "misplaced_writer": [],
                            "unknown_cover": [], "notes": []})
            continue
        results.append(analyze_inventory(inv, source=p))
    return results


# ────────────────────────── 输出 ──────────────────────────

def render_markdown(results, title="key_gaps 清单（件上缺键 / 写者挂错件）"):
    lines = ["# %s" % title, "",
             "口径：件的覆盖部位取 inventory `covers`（HumanBodyBones 名）。",
             "`missing_key` = 覆盖该键作用部位、已有件级宿主、却不是宿主也不在 synced/candidates 的件；",
             "`misplaced_writer` = 宿主是根/祖先/控制物体，或宿主件覆盖的部位与该键作用部位不相交；",
             "`unknown_cover` = covers=Other/unknown，覆盖未知、缺键判不了（不参与判定，单列）；",
             "全部按置信度 high→mid→low 排序，为 advisory 候选，需人判。", ""]
    lines.append("| 工程 | 头像数 | missing_key | misplaced_writer | unknown_cover(不参与) |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        lines.append("| %s | %s | %d | %d | %d |" % (
            os.path.basename(r.get("source") or "?") if r.get("source") else "?",
            r.get("avatar_count", 0), len(r.get("missing_key") or []),
            len(r.get("misplaced_writer") or []), len(r.get("unknown_cover") or [])))
    for r in results:
        src = r.get("source") or "?"
        if r.get("error"):
            lines += ["", "## %s" % os.path.basename(src), "", "读不了：%s" % r["error"]]
            continue
        lines += ["", "## %s" % os.path.basename(src), ""]
        miss, mis = r.get("missing_key") or [], r.get("misplaced_writer") or []
        if miss:
            # 分组：同 (类别, 键, 覆盖部位) 只列计数 + 少量例子；全量在 JSON 里
            groups = {}
            for m in miss:
                g = (m.get("key_class"), m["key"], tuple(m.get("covers") or ()))
                groups.setdefault(g, []).append(m["target"])
            lines += ["### missing_key（疑似件上缺键，按 键×覆盖部位 分组）", "",
                      "| 键 | 类别 | 本件覆盖 | 件数 | 例（最多 5） |", "|---|---|---|---|---|"]
            for (cls_, key, cov), targets in sorted(groups.items()):
                ex = "、".join(sorted(targets)[:5]) + ("…" if len(targets) > 5 else "")
                lines.append("| %s | %s | %s | %d | %s |" % (
                    key, cls_, "、".join(cov) or "-", len(targets), ex))
        if mis:
            lines += ["", "### misplaced_writer（写者挂错件）", "",
                      "| 键 | 宿主 | 置信度 | 类型 | 说明 |", "|---|---|---|---|---|"]
            for m in mis:
                lines.append("| %s | %s | %s | %s | %s |" % (
                    m["key"], m["target"], m.get("confidence"), m.get("host_kind"),
                    m.get("reason")))
        unk = r.get("unknown_cover") or []
        if unk:
            groups = {}
            for u in unk:
                groups.setdefault((u["key"], u.get("slot")), []).append(u["target"])
            lines += ["", "### unknown_cover（covers=Other/unknown，不参与缺键判断，单列）", "",
                      "| 键 | 槽位(按名猜) | 件数 | 例（最多 5） |", "|---|---|---|---|"]
            for (key, slot), targets in sorted(groups.items()):
                ex = "、".join(sorted(targets)[:5]) + ("…" if len(targets) > 5 else "")
                lines.append("| %s | %s | %d | %s |" % (key, slot, len(targets), ex))
        if not miss and not mis:
            lines.append("（missing_key / misplaced_writer 无）")
    return "\n".join(lines) + "\n"


def print_requests():
    print("对 AuditPartInventory 的需求清单（B-补-06；不要改 C#，交 Claude）：")
    for i, r in enumerate(AUDIT_INVENTORY_REQUESTS, 1):
        print("  %d. %s" % (i, r))


# ────────────────────────── selftest ──────────────────────────

def _tiny(renderers, keys, synced=None, candidates=None):
    """构造最小 inventory：renderers=[(path, name, covers)], keys={key:[host,...]}。"""
    av = {
        "name": "fixture",
        "body_path": "Body_b",
        "renderers": [{"path": p, "name": n, "covers": list(c or ["Other"]),
                       "dominant_region": (list(c)[0] if c else "Other")}
                      for p, n, c in renderers],
        "key_follow": {
            "body": "Body_b",
            "body_written_keys": [
                {"key": k, "writers": [{"source": "shape_changer", "component_path": h}
                                       for h in hs]}
                for k, hs in keys.items()
            ],
            "synced": synced or [], "candidates": candidates or [],
        },
    }
    return {"avatars": [av]}


FOOT_COV = ("LeftFoot", "RightFoot", "LeftToes", "RightToes")
LEG_COV = ("LeftLowerLeg", "RightLowerLeg")
CHEST_COV = ("Chest", "UpperChest")
HEEL_KEY = "Foot_heel_OFF_____足_ヒールオフ"


def selftest():
    ok = True
    checks = []

    def run(name, inv, want_missing, want_misplaced, want_unknown=None):
        nonlocal ok
        r = analyze_inventory(inv, source=name)
        got_m = {(f["key"], f["target"]) for f in r["missing_key"]}
        got_p = {(f["key"], f["target"]) for f in r["misplaced_writer"]}
        got_u = {(f["key"], f["target"]) for f in r["unknown_cover"]}
        good = set(want_missing) <= got_m and set(want_misplaced) <= got_p
        extra = (got_m - set(want_missing)) | (got_p - set(want_misplaced))
        extra_note = ""
        if want_unknown is not None:
            good = good and set(want_unknown) == got_u
            if set(want_unknown) != got_u:
                extra_note = "；unknown_cover 要 %s 实 %s" % (sorted(want_unknown), sorted(got_u))
        good = good and not extra
        ok = ok and good
        checks.append((name, good,
                       "缺键 %s（要 %s）、挂错 %s（要 %s）%s%s"
                       % (sorted(got_m), sorted(want_missing), sorted(got_p),
                          sorted(want_misplaced),
                          "" if not extra else "；多余 %s" % sorted(extra), extra_note)))

    # B1 工程D Rurune-Black 鞋缺平脚键：键由 Lockon_shoes 驱动，ugly_shoes 没有
    run("B1 Rurune-Black 鞋缺平脚键",
        _tiny([("Rurune-Black/ugly_shoes", "ugly_shoes", FOOT_COV),
               ("Lockon_rurune_Modular Avatar/Lockon_shoes", "Lockon_shoes", FOOT_COV)],
              {HEEL_KEY: ["Lockon_rurune_Modular Avatar/Lockon_shoes"]}),
        [(HEEL_KEY, "Rurune-Black/ugly_shoes")], [])

    # B2 乳贴缺 Breast_small：键由 Lockon 上衣 BlendshapeSync 驱动，乳贴没有
    run("B2 乳贴缺 Breast_small",
        _tiny([("Esmera_For_Rurune 7/Breast_Bandage", "Breast_Bandage", CHEST_COV),
               ("Lockon_rurune_Modular Avatar/Lockon_shirt", "Lockon_shirt", CHEST_COV)],
              {"Breast_small_____胸_小": ["Lockon_rurune_Modular Avatar/Lockon_shirt"]}),
        [("Breast_small_____胸_小", "Esmera_For_Rurune 7/Breast_Bandage")], [])

    # B3 乳贴缺 Breast_big(limit)
    run("B3 乳贴缺 Breast_big(limit)",
        _tiny([("Esmera_For_Rurune 7/Breast_Bandage", "Breast_Bandage", CHEST_COV),
               ("Lockon_rurune_Modular Avatar/Lockon_leotard", "Lockon_leotard", CHEST_COV)],
              {"Breast_big(limit)": ["Lockon_rurune_Modular Avatar/Lockon_leotard"]}),
        [("Breast_big(limit)", "Esmera_For_Rurune 7/Breast_Bandage")], [])

    # A3 MMN 平脚键只挂在袜子上（袜子只盖小腿，不盖脚）→ 袜子记挂错；
    # 没有「覆盖脚的件级宿主」，故不在鞋上报缺键（降噪，缺失由「挂错」这条提示）
    run("A3 MMN 平脚键挂袜",
        _tiny([("_Outfit/Outfit_MMN_黑/Shoes", "Shoes", FOOT_COV),
               ("_Outfit/Outfit_MMN_黑/Socks", "Socks", LEG_COV)],
              {HEEL_KEY: ["_Outfit/Outfit_MMN_黑/Socks"]}),
        [], [(HEEL_KEY, "_Outfit/Outfit_MMN_黑/Socks")])

    # R1 垂耳兔 11 收缩键挂整套根：宿主是 3 个件的祖先
    run("R1 垂耳兔收缩键挂整套",
        _tiny([("_Outfit/LopEarMine/08_WhitePink_Milfy_MA/Shoes", "Shoes", FOOT_COV),
               ("_Outfit/LopEarMine/08_WhitePink_Milfy_MA/Jacket", "Jacket", CHEST_COV),
               ("_Outfit/LopEarMine/08_WhitePink_Milfy_MA/Tops", "Tops", CHEST_COV)],
              {"Shoulder": ["_Outfit/LopEarMine/08_WhitePink_Milfy_MA/ModularAvatar"],
               "Spine_1": ["_Outfit/LopEarMine/08_WhitePink_Milfy_MA/ModularAvatar"],
               "Foot_heels": ["_Outfit/LopEarMine/08_WhitePink_Milfy_MA/ModularAvatar"]}),
        [],
        [("Shoulder", "_Outfit/LopEarMine/08_WhitePink_Milfy_MA/ModularAvatar"),
         ("Spine_1", "_Outfit/LopEarMine/08_WhitePink_Milfy_MA/ModularAvatar"),
         ("Foot_heels", "_Outfit/LopEarMine/08_WhitePink_Milfy_MA/ModularAvatar")])

    # 负样本：键正常挂在鞋上（鞋也盖脚）→ 一条都不报（袜子即使也挂也不算挂错）
    run("负样本 脚型键正常挂鞋",
        _tiny([("_Outfit/Outfit_MMN_黑/Shoes", "Shoes", FOOT_COV),
               ("_Outfit/Outfit_MMN_黑/Socks", "Socks", LEG_COV)],
              {HEEL_KEY: ["_Outfit/Outfit_MMN_黑/Shoes", "_Outfit/Outfit_MMN_黑/Socks"]}),
        [], [])

    # covers=Other 的件不参与缺键判断、单列 unknown_cover
    run("unknown_cover：covers=Other 单列不参与",
        _tiny([("Lockon/Lockon_shoes", "Lockon_shoes", FOOT_COV),
               ("OtherBrand/sneakers", "sneakers", ("Other",))],
              {HEEL_KEY: ["Lockon/Lockon_shoes"]}),
        [], [], want_unknown=[(HEEL_KEY, "OtherBrand/sneakers")])

    # 输出按置信度排序：root 宿主(high) 在 cover_mismatch(mid) 前面，unknown_cover 最后
    r_sort = analyze_inventory(_tiny(
        [("A/Shoes", "Shoes", FOOT_COV), ("B/Socks", "Socks", LEG_COV),
         ("C/sneakers", "sneakers", ("Other",)),
         ("D/Whole/A", "A", FOOT_COV), ("D/Whole/B", "B", FOOT_COV)],
        {HEEL_KEY: ["B/Socks", "D/Whole"]}), source="sort")
    conf = ([f["confidence"] for f in r_sort["misplaced_writer"]]
            + [f["confidence"] for f in r_sort["unknown_cover"]])
    rank = [CONFIDENCE_RANK.get(c, 9) for c in conf]
    good = rank == sorted(rank) and conf[:1] == ["high"]
    ok = ok and good
    checks.append(("输出按置信度排序（high→mid→low）", good, "序列 %s" % conf))

    # ── 真数据「撤销已修」复现（现有 inventory 是修后版、且 covers 还是 Other；
    #    离线没有修前 inventory，故在真数据上：① 按 B-补-18 重导后的形态补 covers，
    #    ② 删掉已知修复，当作修前提交的等价物） ──
    def _load(name):
        p = os.path.join(KF_DIR, name)
        if not os.path.exists(p):
            return None, "缺 %s" % p
        return json.loads(open(p, encoding="utf-8").read()), p

    def _avs(inv):
        return (inv or {}).get("avatars") or []

    def _set_covers(inv, pairs):
        for renderer, cov in pairs:
            for av in _avs(inv):
                for r in av.get("renderers") or []:
                    if r.get("path") == renderer:
                        r["covers"] = list(cov)

    def _drop_body_host(inv, key_sub, host):
        for av in _avs(inv):
            kf = av.get("key_follow") or {}
            for e in kf.get("body_written_keys") or []:
                if key_sub not in (e.get("key") or ""):
                    continue
                e["writers"] = [w for w in e.get("writers") or []
                                if w.get("component_path") != host]

    def _drop_synced(inv, renderer, key_sub):
        for av in _avs(inv):
            kf = av.get("key_follow") or {}
            kf["synced"] = [s for s in kf.get("synced") or []
                            if not (s.get("renderer") == renderer
                                    and key_sub in (s.get("key") or ""))]

    def _real(name, setup, want_missing, want_misplaced, note):
        inv, src = _load(name)
        if inv is None:
            checks.append((note, True, "SKIP：%s" % src))
            return
        setup(inv)
        r = analyze_inventory(inv, source=src)
        got_m = {(f["key"], f["target"]) for f in r["missing_key"]}
        got_p = {(f["key"], f["target"]) for f in r["misplaced_writer"]}
        good = set(want_missing) <= got_m and set(want_misplaced) <= got_p
        checks.append((note, good, "缺键命中 %s / 挂错命中 %s"
                       % (sorted(set(want_missing) & got_m),
                          sorted(set(want_misplaced) & got_p))))

    inv, _ = _load("工程A.json")
    if inv is not None:
        _set_covers(inv, [("_Outfit/Outfit_MMN_黑/Shoes", FOOT_COV),
                          ("_Outfit/Outfit_MMN_黑/Socks", LEG_COV)])
        r = analyze_inventory(inv, source="工程A-修后")
        mp = {(f["key"], f["target"]) for f in r["misplaced_writer"]}
        good = not any("MMN" in t and "Socks" in t for _k, t in mp)
        checks.append(("真数据负样本：工程A 修后 MMN 平脚键不再报挂错", good,
                       "MMN/Socks 命中 %d" % sum(1 for _k, t in mp
                                                 if "MMN" in t and "Socks" in t)))

    _real("工程D.json",
          lambda inv: (_set_covers(inv, [("Rurune-Black/ugly_shoes", FOOT_COV),
                                         ("Lockon_rurune_Modular Avatar/Lockon_shoes", FOOT_COV)]),
                       _drop_body_host(inv, "Foot_heel_OFF", "Rurune-Black/ugly_shoes"),
                       _drop_body_host(inv, "Foot_Hiheel", "Rurune-Black/ugly_shoes")),
          [(HEEL_KEY, "Rurune-Black/ugly_shoes")], [],
          "B1（真数据：补鞋 covers + 删 ugly_shoes 的 SC）")
    _real("工程D.json",
          lambda inv: (_set_covers(inv, [("Esmera_For_Rurune 7/Breast_Bandage", CHEST_COV),
                                         ("Lockon_rurune_Modular Avatar/Lockon_shirt", CHEST_COV)]),
                       _drop_body_host(inv, "Breast_small", "Esmera_For_Rurune 7/Breast_Bandage"),
                       _drop_synced(inv, "Esmera_For_Rurune 7/Breast_Bandage", "Breast_small")),
          [("Breast_small_____胸_小", "Esmera_For_Rurune 7/Breast_Bandage")], [],
          "B2（真数据：补 covers + 删乳贴 Breast_small 宿主）")
    _real("工程D.json",
          lambda inv: _set_covers(inv, [("Esmera_For_Rurune 7/Breast_Bandage", CHEST_COV),
                                        ("Lockon_rurune_Modular Avatar/Lockon_leotard", CHEST_COV),
                                        ("Lockon_rurune_Modular Avatar/Lockon_shirt", CHEST_COV)]),
          [("Breast_big(limit)", "Esmera_For_Rurune 7/Breast_Bandage")], [],
          "B3（真数据本就是修前：乳贴缺 Breast_big(limit)）")
    _real("工程A.json",
          lambda inv: (_set_covers(inv, [("_Outfit/Outfit_MMN_黑/Shoes", FOOT_COV),
                                         ("_Outfit/Outfit_MMN_黑/Socks", LEG_COV)]),
                       _drop_body_host(inv, "Foot_heel_OFF", "_Outfit/Outfit_MMN_黑/Shoes")),
          [],
          [(HEEL_KEY, "_Outfit/Outfit_MMN_黑/Socks")],
          "A3（真数据：删 Shoes 的 SC，只剩袜宿主 → 袜子挂错）")

    def _r1(inv):
        _set_covers(inv, [("_Outfit/LopEarMine/08_WhitePink_Milfy_MA/Shoes", FOOT_COV)])
        root = "_Outfit/LopEarMine/08_WhitePink_Milfy_MA/ModularAvatar"
        for av in _avs(inv):
            kf = av.get("key_follow") or {}
            for e in kf.get("body_written_keys") or []:
                if not any(k in (e.get("key") or "") for k in (
                        "Shoulder", "Upper_arm", "Elbow", "Lower_arm", "Chest_2",
                        "Spine_1", "Spine_2", "Ankle", "Foot", "Toe")):
                    continue
                clips = [w for w in e.get("writers") or [] if w.get("source") == "clip"]
                e["writers"] = clips + [{"source": "shape_changer", "component_path": root}]

    _real("工程B.json", _r1,
          [],
          [("Foot_heels", "_Outfit/LopEarMine/08_WhitePink_Milfy_MA/ModularAvatar"),
           ("Shoulder", "_Outfit/LopEarMine/08_WhitePink_Milfy_MA/ModularAvatar")],
          "R1（真数据把 11 收缩键的 F 宿主换成整套根）")

    print("== key_gaps selftest ==")
    for name, good, detail in checks:
        print("  [%s] %s :: %s" % ("OK" if good else "FAIL", name, detail))
    all_ok = all(good for _n, good, _d in checks)
    print("ALL PASS" if all_ok else "SELFTEST FAIL")
    return 0 if all_ok else 1


# ────────────────────────── CLI ──────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description="key_follow 盲区补检（缺键 / 挂错件）")
    ap.add_argument("--inventory", help="key_follow JSON")
    ap.add_argument("--all", help="key_follow JSON 目录（批量）")
    ap.add_argument("--out", help="写 JSON 结果")
    ap.add_argument("--md", help="写 Markdown 清单")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--requests", action="store_true", help="打印 AuditPartInventory 需求清单")
    args = ap.parse_args(argv)

    if args.requests:
        print_requests()
        return 0
    if args.selftest:
        return selftest()

    paths = []
    if args.inventory:
        paths.append(args.inventory)
    if args.all:
        paths.extend(sorted(p for p in glob.glob(os.path.join(args.all, "*.json"))
                            if not os.path.basename(p).startswith(("verdict", "status"))))
    if not paths:
        ap.error("需要 --inventory 或 --all（或用 --selftest / --requests）")

    results = analyze_files(paths)
    total = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             "tool": "key_gaps",
             "results": results,
             "summary": {
                 "projects": len(results),
                 "missing_key": sum(len(r.get("missing_key") or []) for r in results),
                 "misplaced_writer": sum(len(r.get("misplaced_writer") or []) for r in results),
                 "unknown_cover": sum(len(r.get("unknown_cover") or []) for r in results),
             }}
    print(render_markdown(results))
    print("汇总：%d 工程，missing_key %d，misplaced_writer %d，unknown_cover(不参与) %d"
          % (total["summary"]["projects"], total["summary"]["missing_key"],
             total["summary"]["misplaced_writer"], total["summary"]["unknown_cover"]))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(total, fh, ensure_ascii=False, indent=2)
        print("写出 %s" % args.out)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(render_markdown(results))
        print("写出 %s" % args.md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
