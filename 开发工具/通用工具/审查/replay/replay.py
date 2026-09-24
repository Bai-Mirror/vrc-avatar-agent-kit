#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-15 缺陷回放库 CLI（`审查/replay/`）。
【项目沉淀】通用工具
适用素体：无关
相关素材：工程文件 + 回放补丁
工具链　：Python 3（离线）
可复用性：★★ 回放库按工程/缺陷扩充
用途　　：T-15 缺陷回放库 CLI：把已修缺陷按文件反向打回工作区，供一次 Play、盲起草与工具改版回归。


把已修的真实缺陷按文件反向打回工作区（外加一条注入样本 `inject_parker`），供
T-16 一次 Play、E11 盲起草、E12 回放与工具改版回归使用。第一批 4 条来自
工程A（`ceb4070b`）；第二批 5 条来自 工程E / 工程D / 工程B / 工程F（B-T23
之后的 C-06 扩充）。规格：`_长程任务_20260918/感知机制研究/04_第一期开工清单.md`
T-15；03 §4.5；作业清单 C-06。

用法::

    replay.py list                       # 列出全部 case
    replay.py apply  --all               # 打回全部（幂等）
    replay.py apply  grab_headdress      # 单条
    replay.py status                     # 全部状态 + 工作区清单核对（验收用）
    replay.py revert --all               # git checkout HEAD -- <本库清单文件>
    replay.py verify [case...]           # 在干净树上验证补丁正反都能应用（会临时改、结束还原）

约定
----
* `apply` / `revert` 会临时改清单里各工程的工作区文件（工程A、工程E、工程D、
  工程B、工程F）。动手前应先在
  `_长程任务_20260918/派工/tmp/T15_REPLAY_ACTIVE` 建锁文件（写时间），
  revert 并确认 `git diff -- <本库清单>` 为空后再删。工具只检测并提示锁，不强制
  （锁的持有者可能是 Unity 会话或别的 DSH 任务，工具无从判定）。
* `revert` 只 `git checkout HEAD -- <本库清单文件>`，**不动任何工具文件**
  （如 `Assets/Editor/AvatarAudit/*`）与清单外的改动。
* `coat_double` 与 `inject_parker` 共用 `MenuGenA2.cs`：单条 revert 也会把另一条
  一并还原（都回到 HEAD）。`--all` 是推荐用法。
"""

import argparse
import json
import pathlib
import subprocess
import sys

sys.dont_write_bytecode = True  # 不落 __pycache__（case 里的 inject 只是被 import）

CASES_DIR = pathlib.Path(__file__).resolve().parent
ORDER = ["grab_headdress", "coat_double", "mmn_foot", "inject_parker",
         "e1_bust_sync", "b1_rurune_flatfoot", "b23_esmera_nipple",
         "r1_lopear_shrink", "z_outfit_menu"]
LOCK_REL = "_长程任务_20260918/派工/tmp/T15_REPLAY_ACTIVE"


# ---------------------------------------------------------------- 基础设施
def find_root(start=None):
    here = pathlib.Path(start or __file__).resolve()
    base = here if here.is_dir() else here.parent
    for p in [base, *base.parents]:
        if (p / ".git").exists():
            return p
    raise SystemExit("replay.py: 找不到仓库根（.git）")


def git(args, root, check=False):
    # 自带 `-c core.quotepath=false`：不依赖仓库/全局 git 配置。否则非 ASCII 路径
    # （工程目录名带中文、资源名带 CJK）在 git 输出里会被引号+八进制转义，
    # 路径比对与补丁校验会 MISMATCH。参数位置在子命令之前，属 git 顶层选项。
    r = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=false", *args],
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit("replay.py: git %s 失败：\n%s%s"
                         % (" ".join(args), r.stdout, r.stderr))
    return r


def load_cases(root):
    cases = {}
    for d in sorted(CASES_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta = d / "expect.json"
        if not meta.is_file():
            continue
        m = json.loads(meta.read_text(encoding="utf-8"))
        m["_dir"] = d
        cases[m["case"]] = m
    ordered = [cases[k] for k in ORDER if k in cases]
    ordered += [cases[k] for k in sorted(cases) if k not in ORDER]
    return ordered


def patch_path(case):
    return case["_dir"] / case.get("patch", "patch.diff")


def inject_path(case):
    return case["_dir"] / case.get("inject_script", "inject.py")


def case_files(case):
    return list(case["files"])


def scoped_diff(root, files):
    """`git diff --name-only -- <files>`，返回排序后的相对路径列表。"""
    r = git(["diff", "--name-only", "--", *files], root)
    return sorted(x for x in r.stdout.splitlines() if x.strip())


def global_diff(root):
    r = git(["diff", "--name-only"], root)
    return sorted(x for x in r.stdout.splitlines() if x.strip())


def dirty_worktree(root):
    """`git status --porcelain` 的非空行（含未跟踪、重命名）。"""
    r = git(["status", "--porcelain"], root)
    return [ln.rstrip() for ln in r.stdout.splitlines() if ln.strip()]


def assert_clean_worktree(root, allow_dirty=False):
    """任务 BR：任何 `replay.py apply` 之前，`git status --porcelain` 非空就停。

    动机：apply/revert 会改各工程工作区；若本来就有一堆未提交改动（别的会话、Unity 未存盘），
    打完补丁再 revert 会把它们一并 checkout 掉，或让 apply 的上下文对不上。先让人确认干净。
    `--allow-dirty` 是明确知情的逃生口（例如改动确认与本库清单无关、且不会 revert 到那些文件）。
    """
    if allow_dirty:
        print("WARNING: --allow-dirty，跳过「apply 前工作区必须干净」检查。")
        return
    rows = dirty_worktree(root)
    if not rows:
        return
    print("apply 需要干净工作区（任务 BR）：`git status --porcelain` 非空，先停。")
    for ln in rows[:50]:
        print("  %s" % ln)
    if len(rows) > 50:
        print("  ... 还有 %d 条" % (len(rows) - 50))
    raise SystemExit(
        "replay.py: 工作区不干净，拒绝 apply。先确认这些改动不属于本库清单/不是 Unity 未存盘；"
        "确认无关后可用 `--allow-dirty` 跳过。")


def is_applied(root, case):
    if case.get("kind") == "inject":
        sys.path.insert(0, str(case["_dir"]))
        import inject  # noqa: E402  (case 目录里的 inject.py)
        return inject.is_applied(root)
    p = patch_path(case)
    if not p.is_file():
        raise SystemExit("replay.py: 缺补丁 %s" % p)
    return git(["apply", "--check", "-R", str(p)], root).returncode == 0


def worktree_clean_for(root, cases):
    """本库清单文件里有没有未纳入本库状态的改动。"""
    files = sorted({f for c in cases for f in case_files(c)})
    dirty = scoped_diff(root, files)
    expected = sorted({f for c in cases if is_applied(root, c) for f in case_files(c)})
    return dirty, expected


def select(cases, argv, all_flag):
    if all_flag or not argv:
        return list(cases)
    by = {c["case"]: c for c in cases}
    out = []
    for name in argv:
        if name not in by:
            raise SystemExit("replay.py: 未知 case %r（用 list 看清单）" % name)
        out.append(by[name])
    return out


def lock_state(root):
    p = pathlib.Path(root) / LOCK_REL
    return p, p.is_file()


def warn_lock(root, action):
    p, held = lock_state(root)
    if held:
        print("lock: %s（%s）" % (p.relative_to(root), p.read_text(encoding="utf-8").strip()))
    else:
        print("WARNING: 未找到锁文件 %s —— apply/revert 会改清单里各工程的工作区，"
              "建议先建锁（echo $(date) > %s）。" % (p.relative_to(root), p.relative_to(root)))
    return held


# ---------------------------------------------------------------- 命令
def cmd_list(root, cases):
    print("T-15 缺陷回放库：%d 条" % len(cases))
    for c in cases:
        print("  %-16s %-9s %-11s %s"
              % (c["case"], c.get("kind", "?"), c.get("dep_kind", "-"),
                 c.get("dep_id", "-")))
        for f in case_files(c):
            print("      - %s" % f)
    return 0


def cmd_apply(root, cases, sel, dry=False):
    warn_lock(root, "apply")
    rc = 0
    for c in sel:
        name = c["case"]
        if is_applied(root, c):
            print("== %-16s already applied（no-op）" % name)
            continue
        if c.get("kind") == "inject":
            sys.path.insert(0, str(c["_dir"]))
            import inject
            changed = inject.apply(root)
            print("== %-16s inject: %s" % (name, "injected" if changed else "no-op"))
        else:
            p = patch_path(c)
            r = git(["apply", str(p)], root)
            if r.returncode != 0:
                print("== %-16s APPLY FAILED\n%s%s" % (name, r.stdout, r.stderr))
                rc = 1
                break
            rev = git(["apply", "--check", "-R", str(p)], root)
            print("== %-16s applied; reverse-check: %s"
                  % (name, "OK" if rev.returncode == 0 else "FAIL"))
            if rev.returncode != 0:
                rc = 1
    return rc


def cmd_revert(root, cases, sel):
    warn_lock(root, "revert")
    files = sorted({f for c in sel for f in case_files(c)})
    if not files:
        print("没有可回退的文件")
        return 0
    r = git(["checkout", "HEAD", "--", *files], root)
    if r.returncode != 0:
        print("REVERT FAILED:\n%s%s" % (r.stdout, r.stderr))
        return 1
    print("revert: git checkout HEAD -- %d 个文件" % len(files))
    for f in files:
        print("  - %s" % f)
    return 0


def _manifest_check(root, cases):
    files = sorted({f for c in cases for f in case_files(c)})
    expect = sorted({f for c in cases if is_applied(root, c) for f in case_files(c)})
    actual = scoped_diff(root, files)
    ok = expect == actual
    other = sorted(set(global_diff(root)) - set(files))
    return files, expect, actual, ok, other


def cmd_status(root, cases):
    print("T-15 缺陷回放库 status（%d 条）" % len(cases))
    for c in cases:
        st = "APPLIED" if is_applied(root, c) else "clean"
        print("  %-16s %-8s %s" % (c["case"], st, c.get("dep_id", "-")))
    files, expect, actual, ok, other = _manifest_check(root, cases)
    print("")
    print("清单文件（%d）：" % len(files))
    for f in files:
        print("  - %s" % f)
    print("工作区(清单内) git diff --name-only：")
    for f in actual:
        print("  - %s" % f)
    if not actual:
        print("  （空）")
    print("清单核对：%s" % ("MATCH" if ok else "MISMATCH"))
    if not ok:
        print("  期望：%s" % (expect or "（空）"))
    if other:
        print("提示：清单外还有 tracked 改动（非本库、未回退）：%s" % ", ".join(other))
    p, held = lock_state(root)
    print("锁文件 %s：%s" % (p.relative_to(root), "HELD" if held else "absent"))
    return 0 if ok else 1


def cmd_verify(root, cases, sel):
    """在干净树上验证每条补丁正反都 `git apply --check` 通过；结束还原。"""
    dirty_all, _ = worktree_clean_for(root, cases)
    if dirty_all:
        print("verify 需要干净树；以下清单文件当前有改动，请先 revert：")
        for f in dirty_all:
            print("  - %s" % f)
        return 1
    warn_lock(root, "verify")
    rc = 0
    for c in sel:
        name = c["case"]
        if c.get("kind") == "inject":
            sys.path.insert(0, str(c["_dir"]))
            import inject
            inject.apply(root)
            ok = inject.is_applied(root)
            git(["checkout", "HEAD", "--", *case_files(c)], root)
            print("== %-16s inject 往返：%s" % (name, "OK" if ok else "FAIL"))
            rc |= 0 if ok else 1
            continue
        p = patch_path(c)
        fwd = git(["apply", "--check", str(p)], root)
        if fwd.returncode != 0:
            print("== %-16s 正向 --check FAIL\n%s%s" % (name, fwd.stdout, fwd.stderr))
            rc = 1
            continue
        git(["apply", str(p)], root)
        sem = _check_defect_assert(root, c)
        rev = git(["apply", "--check", "-R", str(p)], root)
        git(["checkout", "HEAD", "--", *case_files(c)], root)
        print("== %-16s 正向 --check OK；反向 --check %s；缺陷语义断言 %s"
              % (name, "OK" if rev.returncode == 0 else "FAIL", "OK" if sem else "FAIL"))
        if rev.returncode != 0:
            print(rev.stdout + rev.stderr)
            rc = 1
        if not sem:
            rc = 1
    return rc


def _regen_patch(root, case):
    """按 case 的 `fix_commit` / `pre_fix_rev` 重算补丁（只看两个 commit，不依赖工作区）。"""
    fix = case.get("fix_commit")
    pre = case.get("pre_fix_rev")
    if not fix or not pre:
        raise SystemExit("replay.py: case %s 缺 fix_commit/pre_fix_rev，无法重算补丁"
                         % case.get("case"))
    return git(["diff", fix, pre, "--", *case_files(case)], root, check=True).stdout


def _check_defect_assert(root, case):
    """重定基补丁的语义断言：apply 之后目标文件里必须「缺 / 含」指定标记。

    任务 CF：4 条补丁（mmn_foot / b1 / b23 / z）的修复提交之后场景又被生成器改过，
    逐字反向 diff 不再能落到 HEAD，于是按缺陷语义重定基（见 expect.json.rebase）。
    重定基后 `git diff fix pre` 不再逐字复现，改用本断言保证「打完补丁确实回到了缺陷态」。
    规则见 expect.json.defect_assert：每项 `{file, absent:[...], present:[...]}`；
    `file` 不存在即视为通过（用于「反向补丁会删掉的新增文件」）。缺规则返回 True。
    """
    rules = case.get("defect_assert")
    if not rules:
        return True
    ok = True
    for r in rules:
        p = pathlib.Path(root) / r["file"]
        if not p.exists():
            # 反向补丁会删掉的新建文件：不存在才算对
            if r.get("must_exist"):
                print("    FAIL %s 不存在（应存在）" % r["file"])
                ok = False
            continue
        if r.get("must_not_exist"):
            print("    FAIL %s 仍存在（应被删除）" % r["file"])
            ok = False
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for s in r.get("absent", []):
            if s in text:
                print("    FAIL %s 仍含 %r" % (r["file"], s))
                ok = False
        for s in r.get("present", []):
            if s not in text:
                print("    FAIL %s 缺 %r" % (r["file"], s))
                ok = False
    return ok


def _scene_filter(text):
    """只保留含 232539723 的 hunk（与 mmn_foot 生成时同法）。返回 (text, 原 hunk 数, 保留数)。"""
    lines = text.split("\n")
    idx = next((i for i, l in enumerate(lines) if l.startswith("@@")), len(lines))
    header, hunks, cur = lines[:idx], [], None
    for l in lines[idx:]:
        if l.startswith("@@"):
            if cur is not None:
                hunks.append(cur)
            cur = [l]
        elif cur is not None:
            cur.append(l)
    if cur is not None:
        hunks.append(cur)
    kept = [h for h in hunks if any("232539723" in x for x in h)]
    out = "\n".join(header + [x for h in kept for x in h])
    if not out.endswith("\n"):
        out += "\n"
    return out, len(hunks), len(kept)


def cmd_selftest(root, cases):
    """自带数据自检：干净树 → apply --all → 核对/可复现 → revert → 确认干净。

    任何失败都保证 revert（try/finally）；开始时清单内必须干净。
    """
    print("T-15 replay selftest")
    manifest = sorted({f for c in cases for f in case_files(c)})
    ok = True
    pre = scoped_diff(root, manifest)
    if pre:
        print("  FAIL: 清单内工作区不干净，先 `replay.py revert --all`：")
        for f in pre:
            print("    - %s" % f)
        return 1
    try:
        if cmd_apply(root, cases, cases) != 0:
            ok = False
        applied = all(is_applied(root, c) for c in cases)
        print("  %d 条 APPLIED: %s" % (len(cases), applied))
        ok &= applied
        _, _, _, match, _ = _manifest_check(root, cases)
        print("  清单核对: %s" % ("MATCH" if match else "MISMATCH"))
        ok &= match
        for c in cases:
            if c.get("kind") == "inject":
                sys.path.insert(0, str(c["_dir"]))
                import inject
                good = inject.is_applied(root)
                print("  注入生效 %-16s %s" % (c["case"], "OK" if good else "FAIL"))
                ok &= good
                continue
            if c.get("regen") == "head_rebase":
                # 任务 CF：修复提交之后文件又改过，补丁按缺陷语义重定基到 HEAD；
                # 不再逐字复现 `git diff fix pre`，改用 defect_assert 断言缺陷态。
                good = _check_defect_assert(root, c)
                print("  重定基语义断言 %-16s %s" % (c["case"], "OK" if good else "FAIL"))
                ok &= good
                continue
            regen = _regen_patch(root, c)
            stored = patch_path(c).read_text(encoding="utf-8")
            if c.get("patch_filter") == "mmn_fileid":
                regen, nh, kh = _scene_filter(regen)
                print("  %s hunk 过滤: %d -> %d（噪声 hunk 已剔）" % (c["case"], nh, kh))
            good = regen == stored
            print("  补丁可复现 %-16s %s" % (c["case"], "OK" if good else "MISMATCH"))
            ok &= good
    finally:
        cmd_revert(root, cases, cases)
    post = scoped_diff(root, manifest)
    print("  revert 后清单内 diff: %s" % ("空" if not post else post))
    ok &= not post
    print("selftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser(description="T-15 缺陷回放库")
    ap.add_argument("cmd", nargs="?",
                    choices=["list", "apply", "revert", "status", "verify", "selftest"])
    ap.add_argument("cases", nargs="*", help="case 名（缺省/--all = 全部）")
    ap.add_argument("--all", action="store_true", help="全部 case")
    ap.add_argument("--selftest", action="store_true",
                    help="等价于 `selftest`：干净树往返 + 补丁可复现自检")
    ap.add_argument("--root", default=None, help="仓库根（缺省自动定位）")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="（任务 BR）apply 前跳过 `git status --porcelain` 干净检查")
    a = ap.parse_args(argv)
    root = find_root(a.root) if a.root else find_root()
    cases = load_cases(root)
    if not cases:
        raise SystemExit("replay.py: %s 下没有 case" % CASES_DIR)
    if a.selftest or a.cmd == "selftest":
        return cmd_selftest(root, cases)
    if not a.cmd:
        ap.error("需要一个子命令（list/apply/revert/status/verify/selftest）")
    sel = select(cases, a.cases, a.all)
    if a.cmd == "list":
        return cmd_list(root, cases)
    if a.cmd == "apply":
        assert_clean_worktree(root, a.allow_dirty)
        return cmd_apply(root, cases, sel)
    if a.cmd == "revert":
        return cmd_revert(root, cases, sel)
    if a.cmd == "status":
        return cmd_status(root, cases)
    if a.cmd == "verify":
        return cmd_verify(root, cases, sel)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
