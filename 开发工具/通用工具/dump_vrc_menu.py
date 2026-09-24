# -*- coding: utf-8 -*-
r"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途　　：不开 Unity，直接从 .asset YAML 还原 VRCExpressionsMenu 树 + VRCExpressionParameters

为什么要它：归纳「以前几单菜单到底是怎么搭的」时，逐个开 Unity 要几十分钟，
而这两类资产都是纯文本。GUID 靠 .meta 建索引，subMenu 引用能完整还原成树。

用法：
    python dump_vrc_menu.py <工程目录> [<工程目录> ...]
"""
import os, re, sys, io, collections

CTRL = {101: "Button", 102: "Toggle", 103: "SubMenu",
        201: "TwoAxis", 202: "FourAxis", 203: "RadialPuppet"}
PT = {0: "Int", 1: "Float", 2: "Bool"}


def guid_index(proj):
    """GUID -> 资产路径。"""
    idx = {}
    for dirp, dirs, files in os.walk(proj):
        if any(x in dirp for x in (os.sep + "Library", os.sep + "Temp", os.sep + "obj")):
            continue
        for f in files:
            if not f.endswith(".meta"):
                continue
            p = os.path.join(dirp, f)
            try:
                head = io.open(p, encoding="utf-8", errors="replace").read(400)
            except Exception:
                continue
            m = re.search(r"^guid:\s*([0-9a-f]{32})", head, re.M)
            if m:
                idx[m.group(1)] = p[:-5]
    return idx


def unesc(x):
    """Unity 会把中文菜单名写成 "\\uXXXX" 形式的带引号字符串，还原成可读文本。"""
    x = x.strip()
    if len(x) >= 2 and x[0] == '"' and x[-1] == '"':
        x = x[1:-1]
    if "\\u" not in x:
        return x
    try:
        return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), x)
    except Exception:
        return x


def parse_menu(path):
    """返回 (菜单名, [控件…])；不是菜单资产就返回 None。"""
    try:
        t = io.open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return None
    if "controls:" not in t or "m_Script" not in t:
        return None
    name = (re.search(r"^\s*m_Name:\s*(.*)$", t, re.M) or [None, ""])[1].strip()
    body = t.split("controls:", 1)[1]
    ctrls = []
    # 控件在 2 空格缩进；subParameters 的条目在 4 空格。
    # 按 `\s*` 切会把 subParameters 也切成控件（第一版就是这么错的），必须锁死两个空格。
    for blk in re.split(r"\n  - name:", body)[1:]:
        blk = "name:" + blk
        def g(k, pat=r"([^\n]*)"):
            m = re.search(r"\b" + k + r":\s*" + pat, blk)
            return m.group(1).strip() if m else ""
        ty = g("type", r"(\d+)")
        sub = re.search(r"subMenu:\s*\{fileID:\s*\d+,\s*guid:\s*([0-9a-f]{32})", blk)
        prm = re.search(r"parameter:\s*\n\s*name:\s*([^\n]*)", blk)
        subp = re.findall(r"-\s*name:\s*([^\n]+)", blk.split("subParameters:", 1)[1]) if "subParameters:" in blk else []
        ctrls.append({
            "name": unesc(g("name").strip(chr(34))),
            "type": int(ty) if ty.isdigit() else -1,
            "param": (prm.group(1).strip() if prm else ""),
            "value": g("value", r"([-\d.]+)"),
            "sub": sub.group(1) if sub else None,
            "subparams": [s.strip() for s in subp if s.strip()],
        })
    return name, ctrls


def parse_params(path):
    try:
        t = io.open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return None
    if "parameters:" not in t or "valueType" not in t:
        return None
    out = []
    for blk in re.split(r"\n\s*-\s+name:", t.split("parameters:", 1)[1])[1:]:
        blk = "name:" + blk
        def g(k, pat=r"([^\n]*)"):
            m = re.search(r"\b" + k + r":\s*" + pat, blk)
            return m.group(1).strip() if m else ""
        vt = g("valueType", r"(\d+)")
        out.append((g("name"), PT.get(int(vt) if vt.isdigit() else -1, "?"),
                    g("defaultValue", r"([-\d.]+)"), g("saved", r"(\d)")))
    return out


def walk(gid, menus, idx, ind, seen, out):
    p = idx.get(gid)
    if not p or p not in menus:
        out.append(ind + "（未解析 " + (gid or "")[:8] + "）")
        return
    if gid in seen:
        out.append(ind + "…（循环引用）")
        return
    seen = seen | {gid}
    for c in menus[p][1]:
        ty = CTRL.get(c["type"], str(c["type"]))
        extra = ""
        if c["param"]:
            extra += f"  param={c['param']}"
        if c["type"] in (102, 101) and c["value"]:
            extra += f" val={c['value']}"
        if c["subparams"]:
            extra += f"  subParams={c['subparams']}"
        out.append(f"{ind}{ty:<12} {c['name']}{extra}")
        if c["type"] == 103 and c["sub"]:
            walk(c["sub"], menus, idx, ind + "    ", seen, out)


def main():
    for proj in sys.argv[1:]:
        name = os.path.basename(proj.rstrip("\\/"))
        print("\n" + "=" * 78)
        print("##### " + name)
        idx = guid_index(proj)
        menus, params = {}, {}
        for dirp, dirs, files in os.walk(proj):
            if any(x in dirp for x in (os.sep + "Library", os.sep + "Temp", os.sep + "obj")):
                continue
            for f in files:
                if not f.endswith(".asset"):
                    continue
                p = os.path.join(dirp, f)
                if os.path.getsize(p) > 3_000_000:
                    continue
                m = parse_menu(p)
                if m and m[1]:
                    menus[p] = m
                    continue
                q = parse_params(p)
                if q:
                    params[p] = q
        # 根菜单 = 没有被别的菜单当 subMenu 引用的
        referenced = set()
        for p, (nm, cs) in menus.items():
            for c in cs:
                if c["sub"] and c["sub"] in idx:
                    referenced.add(os.path.normpath(idx[c["sub"]]))
        roots = [p for p in menus if os.path.normpath(p) not in referenced]
        print(f"  菜单资产 {len(menus)} 个，根菜单 {len(roots)} 个；参数资产 {len(params)} 个")
        rev = {os.path.normpath(v): k for k, v in idx.items()}
        for r in sorted(roots, key=lambda x: -len(menus[x][1])):
            rel = os.path.relpath(r, proj)
            print(f"\n  ── 根菜单 {menus[r][0]}   ({rel})")
            out = []
            walk(rev.get(os.path.normpath(r)), menus, idx, "     ", set(), out)
            for line in out[:120]:
                print(line)
            if len(out) > 120:
                print(f"     … 还有 {len(out)-120} 行")
        for p, ps in sorted(params.items(), key=lambda kv: -len(kv[1]))[:2]:
            bits = sum(1 if t == "Bool" else 8 for _, t, _, _ in ps)
            print(f"\n  ── 参数资产 {os.path.relpath(p, proj)}   {len(ps)} 个 / {bits} bit")
            for n, t, dv, sv in ps[:60]:
                print(f"     {n:<34} {t:<6} 默认={dv:<6} saved={sv}")
            if len(ps) > 60:
                print(f"     … 还有 {len(ps)-60} 个")


if __name__ == "__main__":
    main()
