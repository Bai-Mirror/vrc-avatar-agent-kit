# -*- coding: utf-8 -*-
"""clip_writes_diff.py — 比对两份 `clip_writes.py` 输出（迁移前后）的写者集合。
【项目沉淀】通用工具
适用素体：无关
相关素材：两份 clip_writes.py 输出
工具链　：Python 3（离线）
可复用性：★★ 审查工具链的一环
用途　　：比对迁移前后两份 clip_writes.py 输出的写者集合，T-07 回归用。


T-07/B-T07a 回归用：把「迁移前控制器/clip」与「迁移后控制器/clip」各自喂给
`clip_writes.py`，再用本脚本看差异。不能替代 Unity 里的真机回读（T1 83 态），
只能证明「哪条 (路径, 键) 在写、写了哪些值」在迁移前后一致。

判据（与 04 §T-07 验收口径对应）：
  · `triples_only_before`：迁移前写、迁移后没人再写的 (路径, 键, 值) —— **必须为空**，
    除非在 `--allow-before` 里显式登记（A-09 有意删除等）。
  · `triples_only_after`：迁移后新写出的 (路径, 键, 值) —— 正常迁移应为空。
  · `value_diff`：同一个 (路径, 键) 两侧写出的值集合不同（如 {0,100} → {0}）—— 应为空。
  · `layer_moves`：同值但写者层变了（迁移的预期现象，仅信息）。

各集合的「值」按取整到 6 位小数的去重集合比；不含时间轴/条件（条件变化看
`DepPlan` 的计划文本与 `decl_validate.py`，本工具看不到 Animator 转移条件）。

用法：
    python3 clip_writes_diff.py --before before.json --after after.json
                                [--allow-before allow.txt] [--out report.json]
`--allow-before` 每行一条 `路径\t键\t值`（值可省＝该 (路径,键) 的全部值都豁免），
豁免项会列进 `allowed`，不算 FAIL。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict


def _val(v) -> float:
    return round(float(v), 6)


def build(entries):
    """(路径, 键) -> {值集合}, 以及 (路径, 键, 值) -> {层名: 状态集合}。"""
    by_pair = defaultdict(set)
    by_triple = defaultdict(lambda: defaultdict(set))
    for e in entries:
        pair = (e.get("path", ""), e.get("attribute", ""))
        for v in e.get("values") or []:
            by_pair[pair].add(_val(v))
            by_triple[(pair[0], pair[1], _val(v))][e.get("layer", "")].add(e.get("state", ""))
    return by_pair, by_triple


def load_allow(path):
    """每行 `路径<TAB>键[<TAB>值]`；返回 ({(path,key)}, {(path,key,val)})。"""
    pairs, triples = set(), set()
    if not path:
        return pairs, triples
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) >= 3:
                triples.add((cols[0], cols[1], _val(cols[2])))
            elif len(cols) == 2:
                pairs.add((cols[0], cols[1]))
            else:
                pairs.add((line, ""))
    return pairs, triples


def main(argv=None):
    ap = argparse.ArgumentParser(description="比对两份 clip_writes.py 输出的写者集合")
    ap.add_argument("--before", required=True, help="迁移前 clip_writes JSON")
    ap.add_argument("--after", required=True, help="迁移后 clip_writes JSON")
    ap.add_argument("--allow-before", help="豁免清单（A-09 等有意删除）")
    ap.add_argument("--out", help="报告 JSON 输出路径（缺省只打印摘要）")
    a = ap.parse_args(argv)

    be = json.load(open(a.before, encoding="utf-8"))["entries"]
    ae = json.load(open(a.after, encoding="utf-8"))["entries"]
    bp, bt = build(be)
    ap_, at = build(ae)
    allow_pairs, allow_triples = load_allow(a.allow_before)

    before_triples = set(bt)
    after_triples = set(at)
    only_before = sorted(before_triples - after_triples)
    only_after = sorted(after_triples - before_triples)

    def allowed(t):
        return (t[0], t[1]) in allow_pairs or t in allow_triples

    allowed_hits = [t for t in only_before if allowed(t)]
    fail_before = [t for t in only_before if not allowed(t)]

    common = sorted(set(bp) & set(ap_))
    value_diff = []
    for pair in common:
        if bp[pair] != ap_[pair]:
            value_diff.append({"path": pair[0], "attribute": pair[1],
                               "before": sorted(bp[pair]), "after": sorted(ap_[pair])})

    # 同值的层迁移（信息）：同一 (路径,键,值) 两侧层名集合不同
    layer_moves = []
    for t in sorted(before_triples & after_triples):
        lb = set(bt[t]); la = set(at[t])
        if lb != la:
            layer_moves.append({"path": t[0], "attribute": t[1], "value": t[2],
                                "before_layers": sorted(lb), "after_layers": sorted(la)})

    pairs_only_before = sorted(set(bp) - set(ap_))
    pairs_only_after = sorted(set(ap_) - set(bp))

    ok = (not fail_before) and (not only_after) and (not value_diff)
    report = {
        "before": a.before, "after": a.after,
        "counts": {"before_entries": len(be), "after_entries": len(ae),
                   "before_triples": len(before_triples), "after_triples": len(after_triples)},
        "FAIL": not ok,
        "triples_only_before": [{"path": t[0], "attribute": t[1], "value": t[2],
                                 "writers": sorted(bt[t])} for t in fail_before],
        "allowed": [{"path": t[0], "attribute": t[1], "value": t[2]} for t in allowed_hits],
        "triples_only_after": [{"path": t[0], "attribute": t[1], "value": t[2],
                                "writers": sorted(at[t])} for t in only_after],
        "value_diff": value_diff,
        "pairs_only_before": [{"path": p[0], "attribute": p[1]} for p in pairs_only_before],
        "pairs_only_after": [{"path": p[0], "attribute": p[1]} for p in pairs_only_after],
        "layer_moves": layer_moves,
    }

    print("[clip_writes_diff] before=%s after=%s" % (a.before, a.after))
    print("  entries %d -> %d ; triples %d -> %d"
          % (len(be), len(ae), len(before_triples), len(after_triples)))
    print("  (路径,键,值) 只在前: %d（豁免 %d，FAIL %d）"
          % (len(only_before), len(allowed_hits), len(fail_before)))
    print("  (路径,键,值) 只在后: %d" % len(only_after))
    print("  同 (路径,键) 值集合不同: %d" % len(value_diff))
    print("  只在前/后的 (路径,键): %d / %d" % (len(pairs_only_before), len(pairs_only_after)))
    print("  同值但层名变了: %d（信息，不算 FAIL）" % len(layer_moves))
    if fail_before:
        print("  !! FAIL triples_only_before:")
        for t in fail_before:
            print("     %s\t%s\t%s   writers=%s" % (t[0], t[1], t[2], sorted(bt[t])))
    if value_diff:
        print("  !! FAIL value_diff:")
        for d in value_diff:
            print("     %s\t%s  before=%s after=%s"
                  % (d["path"], d["attribute"], d["before"], d["after"]))
    if only_after:
        print("  !! FAIL triples_only_after:")
        for t in only_after:
            print("     %s\t%s\t%s" % (t[0], t[1], t[2]))
    print("  RESULT: " + ("PASS" if ok else "FAIL"))

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
        print("  report -> %s" % a.out)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
