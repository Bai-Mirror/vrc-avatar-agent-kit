#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""profile_keys.py — 把 T-05 盘点的身体全量形态键写进素体档案 `all_keys:` 段。
【项目沉淀】通用工具
适用素体：无关
相关素材：T-05 inventory.json + 素体档案 yaml
工具链　：Python 3 + PyYAML（离线）
可复用性：★★ 按素体档案复用
用途　　：把 T-05 盘点的身体全量形态键写进素体档案的 all_keys 段。


背景（任务 AQ，2026-09-19）
    素体档案 `开发工具/素体档案/<素体>.yaml` 原有 `key_classes` 只收录「已分类」的键
    （T-17 标定产物），于是声明里其它身体键（胸、乳头、脚…）在 SEM-07 里被判「不在档案里」
    → 17 条警告。真实存在性应来自身体网格本身：T-05 盘点现在每个头像输出 `body_keys`
    （身体网格全部形态键名，顺序同网格）。本脚本把它落到档案，校验器据此把「键不存在」
    从警告升为 error。

用法
    python3 perception/profile_keys.py --inventory <工程>/_感知/out/inventory.json \
            --profile 开发工具/素体档案/Kaguya.yaml
    python3 perception/profile_keys.py ... --force     # 已有 all_keys 且不同时强制覆盖
    python3 perception/profile_keys.py --selftest

口径与取舍
    · 只动 `all_keys:` 这一段：首次写入追加到文件末尾（前面加一行可读注释），已存在则
      按「顶层行 + 其后缩进行」精确替换这一段，其它字节/注释一字不动。
    · 键序 = 网格顺序（`blendShapeIndex` 顺序）；写列表不做排序，重复运行字节一致。
    · 已有 all_keys 且与盘点不同：默认**只报告差异、不覆盖**（退出码 2），加 `--force`
      才写。理由：档案是多人改的，盘点可能来自旧场景，静默覆盖会把人工补的键抹掉。
    · 不依赖 PyYAML：档案只按行读 `mesh:` 与 `all_keys:` 块，其余原样保留；键值用
      JSON 双引号转义（YAML 合法）。
    · 头像选择：`--avatar` 精确/子串命中优先；否则用档案 `mesh` 匹配盘点 `body_path`
      （或路径基名）；再否则取第一个有 body_keys 的头像。多头像且选择有歧义时打印提醒。

输出（stdout）与退出码：0 = 已写/已是最新；2 = 有差异但未写（需 --force）；1 = 输入/解析错。
ALL PASS 只出现在 `--selftest`。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

BANNER = ("# ══ all_keys：由 profile_keys.py 从盘点 body_keys 写入；键表来源 = Blender 离线读素体 FBX 的"
          " Body_b 全量形态键（T-17 同源，不是 T-05 盘点自带）（网格顺序，勿手改；重复运行只替换本段）══")
ALL_KEYS_RE = re.compile(r"^all_keys\s*:", re.MULTILINE)
MESH_RE = re.compile(r"^mesh\s*:\s*(.*)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# 读入
# ---------------------------------------------------------------------------

def load_inventory(path):
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def profile_mesh(text):
    """档案顶层 `mesh:` 的值（去引号/行尾注释）；没有返回 None。"""
    for m in MESH_RE.finditer(text):
        raw = m.group(1)
        return _yaml_scalar(raw)
    return None


def _yaml_scalar(s):
    s = s.strip()
    if not s:
        return ""
    if s[0] == '"':
        try:
            return json.loads(s)
        except Exception:
            end = s.rfind('"')
            return s[1:end] if end > 0 else s[1:]
    if s[0] == "'":
        end = s.rfind("'")
        v = s[1:end] if end > 0 else s[1:]
        return v.replace("''", "'")
    return re.split(r"\s+#", s, maxsplit=1)[0].strip()


def quote_key(key):
    return json.dumps(key, ensure_ascii=False)


# ---------------------------------------------------------------------------
# all_keys 段：定位 / 解析 / 生成
# ---------------------------------------------------------------------------

def find_all_keys(lines):
    """返回 (start, end, keys, flow) 或 None。start..end 是含 `all_keys:` 行及其缩进块。"""
    for i, ln in enumerate(lines):
        if not ALL_KEYS_RE.match(ln):
            continue
        rest = ln.split(":", 1)[1].strip() if ":" in ln else ""
        if rest and not rest.startswith("#"):
            return (i, i + 1, _parse_flow(rest), True)
        j = i + 1
        keys = []
        while j < len(lines):
            s = lines[j]
            if s.strip() == "":
                break
            if not re.match(r"^\s+", s):
                break
            m = re.match(r"^\s*-\s*(.*)$", s)
            if m:
                keys.append(_yaml_scalar(m.group(1)))
            j += 1
        return (i, j, keys, False)
    return None


def _parse_flow(rest):
    try:
        v = json.loads(rest)
        if isinstance(v, list):
            return [str(x) for x in v]
    except Exception:
        pass
    # 形如 [a, b]（非 JSON 引号）时退化为朴素切分
    body = rest.strip().lstrip("[").rstrip("]")
    if not body:
        return []
    return [_yaml_scalar(x) for x in body.split(",")]


def block_lines(keys, banner=False):
    out = []
    if banner:
        out.append(BANNER)
    out.append("all_keys:")
    out.extend("  - " + quote_key(k) for k in keys)
    return out


def apply_profile(text, keys, force):
    """按 all_keys 是否存在决定替换/追加；返回 (new_text, status, report)。"""
    lines = text.splitlines()
    found = find_all_keys(lines)
    block = block_lines(keys, banner=False)

    if found is None:
        base = text if text.endswith("\n") or text == "" else text + "\n"
        new_text = base + "\n" + "\n".join(block_lines(keys, banner=True)) + "\n"
        return new_text, "written", ["新增 all_keys：%d 键" % len(keys)]

    start, end, old, flow = found
    if old == keys:
        return text, "unchanged", ["all_keys 已是最新（%d 键，顺序一致）" % len(keys)]

    added = [k for k in keys if k not in set(old)]
    removed = [k for k in old if k not in set(keys)]
    report = ["已有 all_keys 与盘点不同：新增 %d / 删除 %d"
              % (len(added), len(removed))]
    if added:
        report.append("  + " + ", ".join(repr(k) for k in added[:10])
                      + (" …" if len(added) > 10 else ""))
    if removed:
        report.append("  - " + ", ".join(repr(k) for k in removed[:10])
                      + (" …" if len(removed) > 10 else ""))
    if not added and not removed:
        report.append("  （仅顺序不同）")
    if flow:
        report.append("  原段是行内 flow，--force 会改写成块列表")

    if not force:
        return text, "diff", report

    new_lines = lines[:start] + block + lines[end:]
    trailing = "\n" if text.endswith("\n") else ""
    return "\n".join(new_lines) + trailing, "written", report + ["已 --force 覆盖"]


# ---------------------------------------------------------------------------
# 头像 / body_keys
# ---------------------------------------------------------------------------

def pick_keys(inv, profile_mesh_name, avatar_name):
    avatars = inv.get("avatars") or []
    if not isinstance(avatars, list):
        avatars = []
    with_keys = [a for a in avatars if isinstance(a, dict) and a.get("body_keys")]
    root_keys = inv.get("body_keys")
    if not with_keys and root_keys:
        return None, list(root_keys), "inventory 根"

    if avatar_name:
        for a in with_keys:
            if a.get("name") == avatar_name:
                return a, list(a["body_keys"]), "name=="
        for a in with_keys:
            if avatar_name in (a.get("name") or ""):
                return a, list(a["body_keys"]), "name~"
        raise SystemExit("inventory 里没有匹配 --avatar=%r 且有 body_keys 的头像"
                         % avatar_name)

    if profile_mesh_name:
        for a in with_keys:
            bp = a.get("body_path") or ""
            if bp == profile_mesh_name or Path(bp).name == profile_mesh_name:
                return a, list(a["body_keys"]), "mesh=="
    if with_keys:
        return with_keys[0], list(with_keys[0]["body_keys"]), "first"
    raise SystemExit("inventory 里没有任何头像带 body_keys（盘点太旧或身体未识别？）")


# ---------------------------------------------------------------------------
# CLI / selftest
# ---------------------------------------------------------------------------

def run(inventory_path, profile_path, avatar_name=None, force=False, quiet=False):
    out = [] if quiet else None
    emit = (lambda s: out.append(s)) if quiet else print
    inv = load_inventory(inventory_path)
    ptext = Path(profile_path).read_text(encoding="utf-8")
    mesh = profile_mesh(ptext)
    avatar, keys, how = pick_keys(inv, mesh, avatar_name)
    who = (avatar or {}).get("name") if avatar else "(根)"
    emit("盘点：%s" % inventory_path)
    emit("头像：%s（匹配 %s；档案 mesh=%r）→ body_keys %d 个"
         % (who, how, mesh, len(keys)))
    if keys and len(set(keys)) != len(keys):
        emit("警告：body_keys 有重复名 %d 个（按原样写入，保留网格顺序）"
             % (len(keys) - len(set(keys))))

    new_text, status, report = apply_profile(ptext, keys, force)
    for line in report:
        emit("  " + line)

    if status == "written":
        Path(profile_path).write_text(new_text, encoding="utf-8")
        emit("已写入：%s" % profile_path)
        return 0
    if status == "unchanged":
        emit("未改动：%s" % profile_path)
        return 0
    emit("未写入（有差异，加 --force 覆盖）：%s" % profile_path)
    return 2


def run_selftest():
    import tempfile

    fails = []

    def check(cond, msg):
        if not cond:
            fails.append(msg)

    prof_text = (
        "# 头部注释：勿删\n"
        "schema: body-profile/0.1\n"
        'body: "Kaguya"\n'
        'mesh: "Body_b"\n'
        "key_classes:\n"
        "  other:\n"
        "    k1: {}\n"
        "# 尾部注释\n"
    )

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        invp = td / "inventory.json"
        profp = td / "Kaguya.yaml"

        def write_inv(keys):
            invp.write_text(json.dumps(
                {"avatars": [{"name": "Kaguya-test", "body_path": "Body_b",
                              "body_keys": keys}]}, ensure_ascii=False),
                encoding="utf-8")

        def call(avatar=None, force=False):
            buf = []
            try:
                with redirect_stdout(__import__("io").StringIO()) as cap:
                    rc = run(str(invp), str(profp), avatar_name=avatar, force=force)
                buf.append(cap.getvalue())
            except SystemExit as e:
                return e.code if isinstance(e.code, int) else 1, "".join(buf)
            return rc, "".join(buf)

        # 1) 首次写入：原有段与注释不动
        profp.write_text(prof_text, encoding="utf-8")
        write_inv(["k1", "k2", "k3"])
        rc, _ = call()
        wrote = profp.read_text(encoding="utf-8")
        check(rc == 0, "首次写入退出码应为 0，实为 %r" % rc)
        check("# 头部注释：勿删" in wrote and "# 尾部注释" in wrote,
              "写入后原注释丢失")
        check("key_classes:" in wrote and "    k1: {}" in wrote,
              "写入后原有 key_classes 段被破坏")
        check(ALL_KEYS_RE.search(wrote) is not None, "没有写出 all_keys 段")
        got = find_all_keys(wrote.splitlines())
        check(got is not None and got[2] == ["k1", "k2", "k3"],
              "all_keys 内容不是 k1,k2,k3：%r" % (got[2] if got else None))
        check(wrote.startswith(prof_text.rstrip("\n")),
              "新段应追加在文件末尾、前面内容逐字保留")

        # 2) 幂等：同输入再跑一次字节一致
        rc, _ = call()
        check(rc == 0 and profp.read_text(encoding="utf-8") == wrote,
              "重复运行应字节一致（status=unchanged）")

        # 3) 有差异默认只报告、不覆盖
        write_inv(["k1", "k3", "k4"])
        rc, cap = call()
        check(rc == 2, "有差异且无 --force 应退出码 2，实为 %r" % rc)
        check(profp.read_text(encoding="utf-8") == wrote, "无 --force 时不应改动文件")
        check("k4" in cap and "k2" in cap, "差异报告应含新增 k4 与删除 k2：%r" % cap)

        # 4) --force 覆盖
        rc, _ = call(force=True)
        forced = profp.read_text(encoding="utf-8")
        check(rc == 0 and find_all_keys(forced.splitlines())[2] == ["k1", "k3", "k4"],
              "--force 后 all_keys 应为 k1,k3,k4")
        check("# 头部注释：勿删" in forced and "key_classes:" in forced,
              "--force 覆盖后其余段/注释丢失")

        # 5) 档案 mesh 不匹配时退到第一个有键的头像，仍能写
        profp.write_text('mesh: "NoSuchMesh"\n', encoding="utf-8")
        write_inv(["x", "y"])
        rc, _ = call()
        check(rc == 0 and find_all_keys(profp.read_text(encoding="utf-8").splitlines())[2]
              == ["x", "y"], "mesh 不匹配时应退到第一个有 body_keys 的头像")

        # 6) 键序不同也判差异
        profp.write_text("mesh: Body_b\n", encoding="utf-8")
        write_inv(["a", "b"])
        call()
        write_inv(["b", "a"])
        rc, cap = call()
        check(rc == 2 and "顺序" in cap, "仅顺序不同应报差异：rc=%r cap=%r" % (rc, cap))

    if fails:
        print("SELFTEST FAIL:")
        for f in fails:
            print("  " + f)
        return 1
    print("profile_keys.py selftest: 6/6")
    print("ALL PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="把 T-05 盘点的 body_keys 写进素体档案 all_keys:（任务 AQ）")
    ap.add_argument("--inventory", help="T-05 inventory.json")
    ap.add_argument("--profile", help="素体档案 YAML")
    ap.add_argument("--avatar", help="按名字选头像（精确优先，其次子串）")
    ap.add_argument("--force", action="store_true",
                    help="已有 all_keys 且不同时强制覆盖（默认只报告差异）")
    ap.add_argument("--selftest", action="store_true", help="自验（临时文件，不碰仓库）")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()
    if not args.inventory or not args.profile:
        ap.error("需要 --inventory 与 --profile（或 --selftest）")
    return run(args.inventory, args.profile,
               avatar_name=args.avatar, force=args.force)


if __name__ == "__main__":
    sys.exit(main())
