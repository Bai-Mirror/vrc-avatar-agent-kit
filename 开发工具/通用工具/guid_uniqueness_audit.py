# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途    ：全工程 GUID 唯一性审计。**一个 GUID 只允许对应一个路径** ——
          出现一 GUID 多路径，Unity 打开工程时会静默给其中几个重新发号，
          引用它们的预制体当场断链、渲染成洋红，而且日志里什么都不报。

用法：
    python guid_uniqueness_audit.py <工程目录>
    python guid_uniqueness_audit.py <工程目录> --refs     # 顺带扫未解析引用

为什么要有这一条（2026-09-06，工程C 一天内撞了两次）：

  ① 厂商公共材质：厂商升版**挪了文件位置却保留 GUID**（新版把公共材质挪进子目录）。
     同一厂商的两个商品一新一旧混装 → 磁盘两份同 GUID → 两个发型预制体断链。

  ② 狐耳包 `GOTHIC ROSE NEKOMIMI` 自带 lilToon 兜底副本
     （`lts.shader` / `ltspass_opaque.shader` / `lil_noise_fur_2.png`），
     GUID 与 `Packages/jp.lilxyzw.liltoon` **完全相同**。
     这一起波及的不是那件配饰，是**全工程所有 lilToon 材质**。

  两起都躲过了 `unpack_unitypackage.py` 的逐包 clash 计数 ——
  那个只查「同路径不同 GUID」，查不出「同 GUID 不同路径」，
  更查不出跨商品、跨厂商、跨 Assets/Packages 的撞法。

  **共用资产的边界是「厂商」，不是「商品」**，甚至跨越 Assets/ 与 Packages/。
  所以判据必须是**全工程穷举**，不能按包分组去防。

坑：
  * **必须同时扫 `Assets/` 和 `Packages/`**。只扫 Assets 会把 SDK 组件的脚本 GUID
    全报成「未解析引用」—— 我据此误报过一轮（说发型预制体有 3 个断引用，实际只有 1 个）。
  * 修法是**原地改 .meta 的 guid 回厂商原值 + 删掉重复那份**，不要删了重建
    （删再建会再换一次号）。厂商原始 GUID 去源 unitypackage 里取：
    它是 tar.gz，条目形如 `<guid>/pathname`，搜 pathname 反查即可，那是唯一权威来源。
"""
import os, io, re, sys, collections

SCAN_ROOTS = ("Assets", "Packages", os.path.join("Library", "PackageCache"))
GUID_RE = re.compile(r"guid:\s*([0-9a-f]{32})")

# Unity 内置资源的固定 GUID（`0000000000000000?000000000000000`）——
# 它们没有 .meta，永远「解析不出」，但完全正常。不白名单掉就是一堆噪声。
BUILTIN_RE = re.compile(r"^0{16}[0-9a-f]0{15}$")


def guid_of_meta(path):
    try:
        for line in io.open(path, encoding="utf-8", errors="replace"):
            if line.startswith("guid:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def collect(project):
    """guid -> [相对路径…]。只走 Assets 与 Packages（PackageCache 只用于解析引用，不算撞车）。"""
    owned = collections.defaultdict(list)      # 参与撞车判定的
    known = set()                              # 用于解析引用的全集
    for root_name in SCAN_ROOTS:
        base = os.path.join(project, root_name)
        if not os.path.isdir(base):
            continue
        for r, ds, fs in os.walk(base):
            for f in fs:
                if not f.endswith(".meta"):
                    continue
                p = os.path.join(r, f)
                g = guid_of_meta(p)
                if not g:
                    continue
                known.add(g)
                # PackageCache 是只读镜像，不参与「重复」判定
                if not root_name.startswith("Library"):
                    owned[g].append(os.path.relpath(p, project)[:-5])
    return owned, known


def scan_refs(project, known):
    """返回 [(引用方相对路径, guid, 次数)]，只报解析不了的。"""
    out = []
    exts = (".prefab", ".mat", ".asset", ".unity", ".controller", ".anim", ".overrideController")
    base = os.path.join(project, "Assets")
    for r, ds, fs in os.walk(base):
        for f in fs:
            if not f.lower().endswith(exts):
                continue
            p = os.path.join(r, f)
            try:
                txt = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            c = collections.Counter(GUID_RE.findall(txt))
            for g, n in c.items():
                if g not in known and not BUILTIN_RE.match(g):
                    out.append((os.path.relpath(p, project), g, n))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    project = os.path.abspath(args[0]) if args else os.getcwd()
    if not os.path.isdir(os.path.join(project, "Assets")):
        sys.exit("不像 Unity 工程（没有 Assets/）：%s" % project)

    owned, known = collect(project)
    dup = {g: ps for g, ps in owned.items() if len(ps) > 1}

    print("工程：%s" % project)
    print("GUID 总数（Assets+Packages）：%d，另有 PackageCache 合计可解析 %d" % (len(owned), len(known)))
    print()
    print("=== 判据一：一个 GUID 多个路径 == 0 ===")
    if dup:
        print("  ✗ 撞车 %d 组：" % len(dup))
        for g, ps in sorted(dup.items()):
            print("    %s" % g)
            for p in ps:
                print("        %s" % p)
    else:
        print("  ✓ 0 组 —— 通过")

    if "--refs" in sys.argv:
        print()
        print("=== 判据二：未解析引用 ===")
        miss = scan_refs(project, known)
        if miss:
            byg = collections.defaultdict(list)
            for p, g, n in miss:
                byg[g].append((p, n))
            print("  未解析 GUID %d 种，出现在 %d 个文件里：" % (len(byg), len(miss)))
            for g, lst in sorted(byg.items(), key=lambda kv: -sum(n for _, n in kv[1]))[:20]:
                tot = sum(n for _, n in lst)
                print("    %s  共 %d 次，例如 %s" % (g, tot, lst[0][0]))
            print("\n  ⚠ 未解析 ≠ 一定是缺陷。厂商多头像模板/demo 常自带悬空引用（无害）。")
            print("     去**源 unitypackage** 里搜这个 GUID：搜得到=我们漏装了兄弟包；搜不到=厂商自带。")
        else:
            print("  ✓ 0 条 —— 通过")

    sys.exit(1 if dup else 0)


if __name__ == "__main__":
    main()
