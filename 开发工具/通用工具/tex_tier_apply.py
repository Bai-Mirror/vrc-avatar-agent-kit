# -*- coding: utf-8 -*-
r"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途　　：把 `tex_tier_plan.py` 出的分档方案**应用到 .meta**，并同时写一份可精确回滚的记录。

为什么不用现成的 TexOptimize.cs：
  那个脚本按**文件名关键词**判辅助图，而 SOP 80 自己那一页明写「按着色器属性判，
  不要按文件名」—— lilToon 把法线图命名成 N01.png 这种很常见，按名字判会漏判成主图。
  本脚本吃的是 tex_tier_plan.py 的 CSV，那份是按 shader 属性判的。

⚠ 改哪几处（少改一处就等于没生效）：
  一个贴图 .meta 里 maxTextureSize 出现在**多个位置**：
    · 顶层 `maxTextureSize:`（老式全局设置）
    · platformSettings 下 `DefaultTexturePlatform` 那条
    · platformSettings 下 `Standalone` / `Android` 等**平台覆盖**
  **PC 构建实际生效的是 Standalone 覆盖**。实测见过 DefaultTexturePlatform 已经是 256、
  Standalone 却写着 2048 的情况 —— 只改默认条目会以为改好了，实际一点没降。
  本脚本把**所有超过目标值的条目**一起降下来，低于目标的一律不动（只降不升）。

⚠ 回滚：
  每次运行都写一份 `<工程>/_贴图回滚_<时间戳>.json`，记录每个文件每个位置的原值。
  回滚：`python tex_tier_apply.py --rollback <那个 json>`

用法：
    python tex_tier_apply.py <工程目录> --csv <plan.csv> [--dry-run]
    python tex_tier_apply.py --rollback <回滚json>
"""
import argparse
import csv
import io
import json
import os
import re
import sys
from datetime import datetime

SIZE_RE = re.compile(r"^(\s*)maxTextureSize:\s*(\d+)\s*$", re.M)


def apply_file(meta_path, target, dry):
    """把该 .meta 里所有 > target 的 maxTextureSize 降到 target。
    返回 [(行号, 原值)]，空列表表示没改。"""
    try:
        txt = io.open(meta_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    changes, out, lineno = [], [], 0
    for line in txt.splitlines(keepends=True):
        lineno += 1
        m = SIZE_RE.match(line.rstrip("\n").rstrip("\r"))
        if m and int(m.group(2)) > target:
            changes.append([lineno, int(m.group(2))])
            line = "%smaxTextureSize: %d\n" % (m.group(1), target)
        out.append(line)
    if changes and not dry:
        io.open(meta_path, "w", encoding="utf-8", newline="").write("".join(out))
    return changes


def do_rollback(path):
    rec = json.load(io.open(path, encoding="utf-8"))
    proj = rec["project"]
    ok = bad = 0
    for item in rec["files"]:
        meta = os.path.join(proj, item["meta"])
        if not os.path.exists(meta):
            print("  ⚠ 文件不在了: " + item["meta"]); bad += 1; continue
        lines = io.open(meta, encoding="utf-8", errors="replace").read().splitlines(keepends=True)
        for ln, orig in item["changes"]:
            i = ln - 1
            if i < len(lines) and "maxTextureSize:" in lines[i]:
                indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
                lines[i] = "%smaxTextureSize: %d\n" % (indent, orig)
            else:
                print("  ⚠ 行对不上，跳过: %s:%d" % (item["meta"], ln)); bad += 1
        io.open(meta, "w", encoding="utf-8", newline="").write("".join(lines))
        ok += 1
    print("回滚完成：%d 个文件已还原，%d 处异常" % (ok, bad))
    print("⚠ 回到 Unity 后要等它重新导入这些贴图，再重跑 PerfReport 确认数字回去了。")
    return 0 if bad == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proj", nargs="?")
    ap.add_argument("--csv")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback")
    a = ap.parse_args()

    if a.rollback:
        return do_rollback(a.rollback)
    if not a.proj or not a.csv:
        ap.error("需要 <工程目录> 与 --csv")

    proj = os.path.abspath(a.proj)
    rows = list(csv.DictReader(io.open(a.csv, encoding="utf-8")))
    print("工程: %s" % proj)
    print("方案: %d 张%s" % (len(rows), "（试跑，不写文件）" if a.dry_run else ""))

    # 安全闸：用户定的红线是「主图**可接受 2048**，不再往下」。
    # ⚠ 所以闸口要卡的是**目标值低于 2048**，不是「出现主图就拒」——
    #   见主图就拒会把 4096→2048 这种完全合规的降档一起拦掉（2026-09-09 实测撞到：
    #   工程A 的 check_navy.png 是 4096 的 _MainTex，降到 2048 正是该做的，省 16 MB）。
    TIER_MAIN = 2048
    bad = [r for r in rows if r["tier"].startswith("主图") and int(r["target"]) < TIER_MAIN]
    if bad:
        print("⛔ 有 %d 张主图的目标值低于 %d，拒绝执行 —— 这是用户定的观感红线。" % (len(bad), TIER_MAIN))
        print("   主图降到 2048 以下必须先做 A/B 并由人确认。先把这些行从 CSV 里去掉再跑。")
        for r in bad[:5]:
            print("     %s  %s→%s" % (r["path"], r["current"], r["target"]))
        return 2
    mains = [r for r in rows if r["tier"].startswith("主图")]
    if mains:
        print("ℹ 清单含 %d 张主图，目标均为 %d（合规：只是从更高档降到 2048）：" % (len(mains), TIER_MAIN))
        for r in mains[:5]:
            print("     %s  %s→%s" % (r["path"], r["current"], r["target"]))
        print("   建议改完抽这几张做一次 A/B —— 判据是「看不出来」，不是「省了多少 MB」。")

    record, changed, skipped = [], 0, 0
    for r in rows:
        rel = r["path"]
        target = int(r["target"])
        meta = os.path.join(proj, rel + ".meta")
        if not os.path.exists(meta):
            print("  ⚠ 缺 .meta: " + rel); skipped += 1; continue
        ch = apply_file(meta, target, a.dry_run)
        if ch is None:
            print("  ⚠ 读不了: " + rel); skipped += 1; continue
        if ch:
            record.append({"meta": os.path.relpath(meta, proj), "target": target, "changes": ch})
            changed += 1

    print("")
    print("实际改动: %d 个文件（共 %d 处），跳过 %d 个"
          % (changed, sum(len(x["changes"]) for x in record), skipped))

    if not a.dry_run and record:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = os.path.join(proj, "_贴图回滚_%s.json" % ts)
        json.dump({"project": proj, "created": ts, "files": record},
                  io.open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("回滚记录: %s" % out)
        print("回滚命令: python 开发工具/通用工具/tex_tier_apply.py --rollback \"%s\"" % out)
    print("")
    print("⚠ 改完必须做两件事，否则不算完成：")
    print("   ① 回 Unity 让它重新导入这些贴图（Assets > Reimport 或直接等它自动扫）")
    print("   ② 重跑 PerfReport.cs 对比前后贴图内存 —— **这是唯一的收益判据**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
