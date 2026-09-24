# -*- coding: utf-8 -*-
"""素材应用表：素材包里的每一项，导进来没有、用上没有。
【项目沉淀】通用工具
适用素体：无关
相关素材：任意素材包 unitypackage + 工程
工具链　：Python 3（离线，只读）
可复用性：★★★ 换个单子直接能用
用途　　：按 GUID 出素材应用表：素材包里每一项导进来没有、用上没有、完整性如何。


**按 GUID 匹配，不按目录名猜。** 厂商解包后的目录名跟 Booth 商品名常常毫无关系
（「揺れるハートのリング」解出来叫 `HINO shop`，「Makeup & Eye Texture」叫 `cumulus`），
靠名字对应必然错。unitypackage 里每个资产带着原始 GUID，跟工程 .meta 的 GUID 直接取交集才是准的。

三级判据：
  导入率  = 包内 GUID ∩ 工程 GUID / 包内 GUID
  被引用  = 包内 GUID ∩ 场景可达 GUID（场景 → 材质/预制体/控制器 → … 传递闭包）
  完整性  = 导入率 < 95% 且缺的是真文件（不是目录条目）→ 半途导入，会静默出错

「用途 / 不用的原因」这一列是手写的，重跑会**原样保留**（按素材包名回填）。

    python pack_usage.py <工程目录> <素材包目录> [-o 输出.md]
"""
import argparse
import io
import os
import re
import sys
import tarfile
import zipfile

TEXT_ASSET = (".mat", ".prefab", ".asset", ".controller", ".anim",
              ".overridecontroller", ".unity", ".physicmaterial", ".mask")
GUID_RE = re.compile(r"guid:\s*([0-9a-f]{32})")


def index_project(assets, extra=()):
    """guid → 相对路径；同时留一份文件名索引给非 unitypackage 的散图用。
    extra 传 Packages/ —— VPM 包不在 Assets 下，不吃进来会把 LLC 这类一律误判成未导入。"""
    g2p, byname = {}, {}
    for base in (assets,) + tuple(extra):
      if not os.path.isdir(base):
          continue
      for root, _dirs, files in os.walk(base):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, assets).replace("\\", "/")
            if f.endswith(".meta"):
                try:
                    m = GUID_RE.search(io.open(full, encoding="utf-8", errors="replace").read(400))
                except OSError:
                    continue
                if m:
                    g2p[m.group(1)] = rel[:-5]
            else:
                byname.setdefault(f.lower(), []).append(rel)
    return g2p, byname


def reachable(assets, g2p, scenes):
    """场景 GUID 的传递闭包。贴图是被材质引用的，只看场景一层会把贴图全判成没用。"""
    seen = set()
    frontier = []
    for s in scenes:
        frontier.append(s)
    while frontier:
        p = frontier.pop()
        full = p if os.path.isabs(p) else os.path.join(assets, p)
        if not os.path.isfile(full) or not full.lower().endswith(TEXT_ASSET):
            continue
        try:
            txt = io.open(full, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for g in GUID_RE.findall(txt):
            if g in seen:
                continue
            seen.add(g)
            if g in g2p:
                frontier.append(g2p[g])
    return seen


def unitypackage_guids(fobj):
    """.unitypackage 是 tar.gz，每个 <guid>/ 目录一个资产"""
    out = {}
    try:
        with tarfile.open(fileobj=fobj, mode="r:gz") as tf:
            for m in tf.getmembers():
                if not m.name.endswith("/pathname"):
                    continue
                guid = m.name.split("/")[0]
                p = tf.extractfile(m).read().decode("utf-8", "replace").strip().splitlines()[0]
                out[guid] = p
    except Exception:
        pass
    return out


def scan_zip(path):
    """返回 (guid→包内路径, 非 unitypackage 的散文件路径)"""
    guids, loose = {}, []
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:
        return guids, ["!!打不开: " + str(e)[:60]]
    with z:
        for n in z.namelist():
            if n.endswith("/"):
                continue
            if n.lower().endswith(".unitypackage"):
                with z.open(n) as f:
                    guids.update(unitypackage_guids(io.BytesIO(f.read())))
            else:
                loose.append(n)
    return guids, loose


def dir_entries(paths):
    """哪些条目其实是目录：它是另一个条目的父路径。

    不靠扩展名猜。`.prefab` `.controller` `.overrideController` 都超过 5 个字符，
    按扩展名长度筛会把预制体整批漏掉，而预制体正是场景引用的主体；
    反过来 `gesture animation/1.v1`、`3.cool` 这种目录名又长得像文件。
    unitypackage 里目录和文件同列，父目录必然是某个路径的前缀 —— 这个判据是确定的。
    """
    s = set(paths)
    dirs = set()
    for p in s:
        i = p.rfind("/")
        while i > 0:
            d = p[:i]
            if d in s:
                dirs.add(d)
            i = p.rfind("/", 0, i)
    return dirs


def keep_notes(out_path):
    """把上一版表格里手写的最后一列捞回来"""
    notes = {}
    if not os.path.isfile(out_path):
        return notes
    for line in io.open(out_path, encoding="utf-8"):
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 7 and cells[1] and cells[1] != "素材包":
            notes[cells[1]] = cells[6]
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("pack")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--scene", default=None,
                    help="指定工作场景；默认取 Assets/_Work/ 下的全部 .unity")
    a = ap.parse_args()

    assets = os.path.join(a.project, "Assets")
    if not os.path.isdir(assets):
        sys.exit("没有 " + assets)
    out_path = a.out or os.path.join(a.project, "_素材应用表.md")

    g2p, byname = index_project(assets, [os.path.join(a.project, "Packages")])
    # ⚠ 只从**我们自己的**工作场景出发。厂商包常自带演示场景（PoLKA 的 Generator、
    # 眼罩的 LockDev、Catchable ERP 的 Sample Scene），把它们当起点会把整包资产
    # 全标成「用上了」—— 判据被自己没装的东西污染，这一列就废了。
    work = os.path.join(assets, "_Work")
    src = work if os.path.isdir(work) else assets
    scenes = [os.path.relpath(os.path.join(r, f), assets).replace("\\", "/")
              for r, _d, fs in os.walk(src) for f in fs if f.endswith(".unity")]
    if a.scene:
        scenes = [os.path.relpath(a.scene, assets).replace("\\", "/")]
    reach = reachable(assets, g2p, scenes)
    sys.stderr.write("工程 %d 个资产，工作场景 %r，可达 %d 个 GUID\n" % (len(g2p), scenes, len(reach)))

    # 素材包的两级结构：<分类>/<商品名>/
    items = []
    for cat in sorted(os.listdir(a.pack)):
        cd = os.path.join(a.pack, cat)
        if not os.path.isdir(cd):
            continue
        for name in sorted(os.listdir(cd)):
            nd = os.path.join(cd, name)
            if os.path.isdir(nd):
                items.append((cat, name, nd))

    notes = keep_notes(out_path)
    rows = []
    for cat, name, d in items:
        allg, loose = {}, []
        per_zip, zip_names = [], []
        for r, _dd, fs in os.walk(d):
            for f in sorted(fs):
                if not f.lower().endswith(".zip"):
                    continue
                g, l = scan_zip(os.path.join(r, f))
                allg.update(g)
                loose += l
                _zd = dir_entries(g.values())
                zf = {k: v for k, v in g.items() if v not in _zd}
                if zf:
                    per_zip.append(sum(1 for k in zf if k in g2p) * 100.0 / len(zf))
                    zip_names.append(f)
        if not allg and not loose:
            rows.append((cat, name, "—", "包里没有压缩包", "", "", notes.get(name, "")))
            continue

        if allg:
            _dirs = dir_entries(allg.values())
            files = {g: p for g, p in allg.items() if p not in _dirs}
            got = [g for g in files if g in g2p]
            used = sum(1 for g in got if g in reach)
            # 工程目录 = 命中资产路径的最长公共前缀（截到两层）
            dirs = ["/".join(g2p[g].split("/")[:2]) for g in got]
            folder = max(set(dirs), key=dirs.count) if dirs else "—"
            # 一个商品常常一个素体一个 zip。把 28 个 zip 合起来算导入率只会得到
            # 「73%」这种没有意义的数 —— 该按**分包**数：装了几个、有没有半装的。
            # 只看**最佳分包**。同一商品往往并存 7 个版本的 zip（PoLKA v1.0.1..v1.1.1），
            # 装了新版后旧版 zip 自然只命中一部分 —— 那不是半装，是版本迭代。
            # 同理一件衣服 15 个素体的 zip 共享同一个材质包，也会各自命中三成。
            # 真正该报警的是：**没有任何一个分包装全**。
            best = max(per_zip) if per_zip else 0.0
            full_n = sum(1 for r in per_zip if r >= 95)
            if best < 5:
                imp = "**未导入**"
            elif best < 95:
                imp = f"**⚠半装 {best:.0f}%**"
            elif len(per_zip) == 1:
                imp = "已导入"
            else:
                imp = f"已导入 {full_n}/{len(per_zip)}"
            ref = f"{used}" if used else "**0**"
            rows.append((cat, name, folder, imp, f"{len(files)}", ref, notes.get(name, "")))
        else:
            _ld = dir_entries(loose)
            real = [p for p in loose if p not in _ld]
            got = [p for p in real if os.path.basename(p).lower() in byname]
            pct = len(got) * 100.0 / len(real) if real else 0.0
            imp = "**未导入**" if pct < 5 else ("已导入" if pct >= 95 else f"部分 {pct:.0f}%")
            rows.append((cat, name, "（散文件，按名匹配）", imp, f"{len(real)}", "?",
                         notes.get(name, "")))

    buf = io.StringIO()
    buf.write("# 素材应用表\n\n")
    buf.write("> `python 开发工具/通用工具/pack_usage.py <工程> <素材包>` 重跑。\n")
    buf.write("> 前六列机器生成，**最后一列手写**，重跑按素材包名原样保留。\n")
    buf.write("> 「引用」= 场景传递可达的资产数；**0** 就是导进来了但一个都没用上。\n\n")
    buf.write("> 「导入」写 `k/M 分包`：一个商品常常一个素体一个 zip，只装对应素体的那个是正常的；"
              "`⚠半装` 才是要查的 —— 半途导入不会报错，效果会默默不对。\n\n")
    buf.write("| 分类 | 素材包 | 工程目录 | 导入 | 文件 | 引用 | 用途 / 不用的原因 |\n")
    buf.write("|---|---|---|---|---:|---:|---|\n")
    for r in rows:
        buf.write("| " + " | ".join(r) + " |\n")
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(buf.getvalue())
    print(buf.getvalue())
    sys.stderr.write("-> " + out_path + "\n")


if __name__ == "__main__":
    main()
