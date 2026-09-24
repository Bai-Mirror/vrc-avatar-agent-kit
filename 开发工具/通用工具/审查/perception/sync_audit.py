#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_audit.py —— 把 `开发工具/通用工具/审查/unity/` 同步到某个 Unity 工程的
【项目沉淀】通用工具
适用素体：无关
相关素材：审查/unity/ 源码 + 目标 Unity 工程
工具链　：Python 3 + rsync（离线）
可复用性：★★ 审查工具链的一环
用途　　：把 审查/unity/ 同步到某个 Unity 工程的 Assets/AvatarAudit/，并清理旧落点（--strip 剥离残留）。

`Assets/AvatarAudit/{Runtime,Editor}/`，并清理旧落点 `Assets/Editor/AvatarAudit/`。

设计出处：`_长程任务_20260918/感知机制研究/04_第一期开工清单.md` T-09（用户 21:40 拍板 P4）。

用法：
    python3 开发工具/通用工具/审查/perception/sync_audit.py <工程目录> [--dry-run]
    python3 开发工具/通用工具/审查/perception/sync_audit.py <工程目录> --from-git <rev> [--dry-run]
    python3 开发工具/通用工具/审查/perception/sync_audit.py <工程目录> --strip [--dry-run]
    python3 开发工具/通用工具/审查/perception/sync_audit.py --selftest

行为（部署）：
    1. `rsync -a --delete` 把 `审查/unity/` 的内容铺到 `<工程>/Assets/AvatarAudit/`；
       `*.meta` 与 `VERSION` 被排除在同步与删除之外（`*.meta` 交给 Unity 自己生成，
       重跑时不能删，否则 GUID 全变）。
    2. 删除旧落点 `<工程>/Assets/Editor/AvatarAudit/`（连它自己的 `.meta`），
       **只删这两个路径**，不动 `Assets/Editor/` 下的其它内容，也不删空的 `Assets/Editor/`。
    3. 写 `<工程>/Assets/AvatarAudit/VERSION`（源文件树的确定性 sha256 + UTC 时间）。

行为（`--from-git <rev>`，任务 AR）：
    改源码时工作区可能是半成品（09-19 工程F因此编译失败）。加 `--from-git` 后不再 rsync
    工作区，而是逐文件 `git show <rev>:<源路径>` 取指定修订的内容铺进工程；`VERSION` 的
    hash 也按取到的 git 内容算。工作区有未提交改动时打印警告并逐条列出（取工作区或 git
    都会警告，git 模式额外注明取的是哪个 rev）。陈旧文件仍按 `--delete` 语义清掉。

行为（`--strip`，供 T-23 交付前剥离）：
    删除 `<工程>/Assets/AvatarAudit/`（含 `.meta`）与旧落点目录，不写 VERSION。

安全：
    删除目录前先看里面有没有本次部署的指纹（asmdef / VERSION / 我们的 `.cs`、`.shader`）；
    不像审查目录就拒绝，除非 `--force`。

约定：本脚本**不启动 Unity**；部署后工程里 .meta 由 Unity 生成（先 refresh 再跑菜单）。
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ── 路径：本文件在 审查/perception/ 下；源在 审查/unity/ ──────────────────────────
HERE = Path(__file__).resolve().parent          # …/审查/perception
AUDIT_ROOT = HERE.parent                        # …/审查
REPO_ROOT = HERE.parents[3]                     # 仓库根
SRC = AUDIT_ROOT / "unity"                      # 同步源
DEPLOY_NAME = "AvatarAudit"                      # <工程>/Assets/AvatarAudit
OLD_REL = Path("Assets/Editor") / DEPLOY_NAME    # 旧落点（相对工程根）

# 本次部署会出现的文件——删除前的“指纹”白名单
KNOWN_FILES = {
    "AuditIO.cs", "AuditStateDriver.cs", "AuditTurntable.cs",
    "AuditFitProbe.cs", "AuditMenuDump.cs", "AuditProbes.cs",
    "AuditBatch.cs", "AuditPartInventory.cs",
    "AuditBuildPasses.cs", "AuditHarmonyMA.cs", "AuditMappingProbeInfo.cs",
    "AuditFxExport.cs", "AuditMappingProbe.cs",
    "AvatarAuditFlat.shader", "AvatarAuditInvisible.shader",
    "AvatarAudit.Editor.asmdef", "AvatarAudit.Runtime.asmdef",
    "VERSION",
}

RSYNC_EXCLUDES = ["*.meta", "VERSION", ".DS_Store", "__pycache__"]


def log(msg):
    print(msg, flush=True)


def die(msg, code=2):
    sys.stderr.write("错误：" + msg + "\n")
    sys.stderr.flush()
    sys.exit(code)


def relp(p: Path) -> str:
    """尽量显示成仓库相对路径，便于人读日志。"""
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


# ── 源 hash ──────────────────────────────────────────────────────────────────
def source_files():
    """源树里参与同步的文件（确定序：相对 posix 路径）。排除 VERSION/.meta/缓存。"""
    out = []
    for p in SRC.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(SRC)
        if rel.name in ("VERSION", ".DS_Store"):
            continue
        if "__pycache__" in rel.parts:
            continue
        if p.suffix == ".meta":
            continue
        out.append(rel)
    return sorted(out, key=lambda r: r.as_posix())


def _hash_pairs(pairs):
    """按顺序把 `<posix相对路径>\\0<文件字节>\\0` 喂进 sha256，返回 hexdigest。"""
    h = hashlib.sha256()
    for rel_posix, data in pairs:
        h.update(rel_posix.encode("utf-8"))
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
    return h.hexdigest()


def source_hash():
    """确定性 sha256：`<posix相对路径>\\0<文件字节>\\0` 按路径排序依次喂入。

    与时间、mtime、绝对路径无关——同样内容永远同 hash。T-13 的版本戳按此算法复核。
    """
    files = source_files()
    digest = _hash_pairs((rel.as_posix(), (SRC / rel).read_bytes()) for rel in files)
    return digest, files


# ── git 取源（任务 AR：--from-git <rev>） ─────────────────────────────────────
def src_rel() -> Path:
    """`审查/unity/` 相对仓库根的路径（git ls-tree/show 的 pathspec）。"""
    try:
        return SRC.relative_to(REPO_ROOT)
    except ValueError:
        return Path(SRC.name)


def _git(args, repo=None):
    return subprocess.run(["git"] + list(args), cwd=str(repo or REPO_ROOT),
                          capture_output=True, text=True)


def _git_bytes(args, repo=None):
    return subprocess.run(["git"] + list(args), cwd=str(repo or REPO_ROOT),
                          capture_output=True)


def git_source_files(rev):
    """`git ls-tree -r <rev> -- <源路径>` 得到的待同步文件（相对 SRC 的 Path，排序）。"""
    base = src_rel()
    r = _git(["ls-tree", "-r", "-z", "--name-only", rev, "--", base.as_posix()])
    if r.returncode != 0:
        die("git ls-tree 失败（rev=%s）：%s" % (rev, r.stderr.strip()))
    out = []
    for p in r.stdout.split("\0"):
        if not p:
            continue
        pr = Path(p)
        try:
            pr = pr.relative_to(base)
        except ValueError:
            continue
        if pr.name in ("VERSION", ".DS_Store") or "__pycache__" in pr.parts:
            continue
        if pr.suffix == ".meta":
            continue
        out.append(pr)
    return sorted(out, key=lambda x: x.as_posix())


def git_file_bytes(rev, rel):
    """`git show <rev>:<源路径>/<rel>` 的原始字节；失败即 die。"""
    full = (src_rel() / rel).as_posix()
    r = _git_bytes(["show", "%s:%s" % (rev, full)])
    if r.returncode != 0:
        die("git show 失败（rev=%s, %s）：%s"
            % (rev, full, r.stderr.decode("utf-8", "replace").strip()))
    return r.stdout


def git_source_hash(rev):
    """按 git 修订内容算的确定性 sha256（与工作区无关）。"""
    files = git_source_files(rev)
    digest = _hash_pairs((rel.as_posix(), git_file_bytes(rev, rel)) for rel in files)
    return digest, files


def uncommitted_source_files():
    """源树（`审查/unity`）下未提交改动（含未跟踪）的 `git status --porcelain` 行。"""
    r = _git(["-c", "core.quotepath=false", "status", "--porcelain", "--",
              src_rel().as_posix()])
    if r.returncode != 0:
        return []
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def warn_uncommitted(rev=None):
    """工作区有未提交改动时打印警告并逐条列出；返回是否有。"""
    lines = uncommitted_source_files()
    if not lines:
        return False
    tag = ("取自 git rev %s，但工作区仍有未提交改动" % rev) if rev \
        else "工作区有未提交改动（半成品会被拷进工程）"
    log("  ⚠ %s（%d 项）：" % (tag, len(lines)))
    for ln in lines:
        log("      " + ln)
    return True


# ── 工程与删除安全 ────────────────────────────────────────────────────────────
def check_project(project: Path):
    if not project.is_dir():
        die(f"工程目录不存在：{project}")
    if not (project / "Assets").is_dir():
        die(f"不像 Unity 工程（缺 Assets/）：{project}")


def looks_like_audit_dir(d: Path) -> bool:
    if not d.is_dir():
        return False
    for p in d.rglob("*"):
        if p.is_file() and p.name in KNOWN_FILES:
            return True
    return False


def rmtree_guarded(d: Path, dry: bool, force: bool, why: str) -> bool:
    """删除目录（连它自己的 .meta）。带指纹校验。返回是否删了/会删。"""
    meta = d.parent / (d.name + ".meta")
    if not d.exists():
        log(f"  · 跳过（不存在）：{relp(d)}")
        return False
    if not (force or looks_like_audit_dir(d)):
        die(f"拒绝删除 {relp(d)}：目录里没有本次部署的指纹（asmdef/VERSION/审查源码）。"
            f"确认无误可加 --force。用途：{why}")
    log(f"  · 删除目录：{relp(d)}" + ("  [dry-run]" if dry else ""))
    if not dry:
        shutil.rmtree(d)
    if meta.exists():
        log(f"  · 删除目录元数据：{relp(meta)}" + ("  [dry-run]" if dry else ""))
        if not dry:
            meta.unlink()
    return True


def rsync(deploy: Path, dry: bool):
    if not dry:
        deploy.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a", "--delete"]
    for e in RSYNC_EXCLUDES:
        cmd += ["--exclude", e]
    if dry:
        cmd += ["-n", "-i"]
    cmd += [str(SRC) + "/", str(deploy) + "/"]
    log("  · rsync" + ("（dry-run）" if dry else "") + "：")
    log("      " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"rsync 失败（exit {r.returncode}）：\n{r.stderr}")
    if dry:
        for line in r.stdout.splitlines():
            log("      " + line)
        if not r.stdout.strip():
            log("      （无差异）")
    return r.returncode == 0


def prune_orphan_meta(deploy: Path, dry: bool):
    """rsync 用 --exclude=*.meta 保护 Unity 生成的 .meta，不删它们；
    但源里删掉一个文件后，它的 .meta 会变成孤儿。这里把没有对应资产的 .meta 清掉。"""
    if not deploy.is_dir():
        return
    for meta in sorted(deploy.rglob("*.meta")):
        if meta.name.endswith(".meta") and not meta.with_suffix("").exists():
            log(f"  · 删除孤儿 meta：{relp(meta)}" + ("  [dry-run]" if dry else ""))
            if not dry:
                meta.unlink()


def deploy_from_git(deploy: Path, rev: str, files, dry: bool) -> str:
    """把 `git show <rev>:<源路径>` 的文件铺到 deploy，返回按 git 内容算的 hash。"""
    log(f"  · git show {rev}:<源路径>（{len(files)} 文件）"
        + ("（dry-run）" if dry else "") + "：")
    h = hashlib.sha256()
    for rel in files:
        data = git_file_bytes(rev, rel)
        h.update(rel.as_posix().encode("utf-8"))
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
        log("      " + rel.as_posix() + ("  [dry-run]" if dry else ""))
        if not dry:
            target = deploy / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return h.hexdigest()


def prune_stale(deploy: Path, files, dry: bool):
    """git 模式的 `--delete`：删掉部署目录里不在 git 源中的陈旧文件（.meta/VERSION 除外）。"""
    if not deploy.is_dir():
        return
    keep = {r.as_posix() for r in files}
    for p in sorted(deploy.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if not p.is_file():
            continue
        rel = p.relative_to(deploy).as_posix()
        if rel in keep or p.name == "VERSION" or p.suffix == ".meta":
            continue
        if "__pycache__" in p.parts:
            continue
        log(f"  · 删除陈旧文件：{relp(p)}" + ("  [dry-run]" if dry else ""))
        if not dry:
            p.unlink()
    if not dry:  # 清空目录（rsync --delete 也会删）
        for d in sorted((x for x in deploy.rglob("*") if x.is_dir()),
                        key=lambda x: len(x.parts), reverse=True):
            try:
                d.rmdir()
            except OSError:
                pass


def write_version(deploy: Path, dry: bool, digest: str, nfiles: int):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = (
        "# AvatarAudit deployment marker —— 由 开发工具/通用工具/审查/perception/sync_audit.py 生成，勿手改。\n"
        f"source: {relp(SRC)}\n"
        f"hash: {digest}\n"
        f"time: {now}\n"
        f"files: {nfiles}\n"
    )
    target = deploy / "VERSION"
    log(f"  · 写 VERSION：{relp(target)}  hash={digest[:16]}…  files={nfiles}"
        + ("  [dry-run]" if dry else ""))
    if not dry:
        target.write_text(body, encoding="utf-8")
    return digest


# ── 主流程 ────────────────────────────────────────────────────────────────────
def do_sync(project: Path, dry: bool, force: bool, from_git: str = None):
    deploy = project / "Assets" / DEPLOY_NAME
    log(f"[sync] {project}  ->  {relp(deploy)}")
    warn_uncommitted(from_git)
    if from_git:
        files = git_source_files(from_git)
        digest = deploy_from_git(deploy, from_git, files, dry)
        prune_stale(deploy, files, dry)
    else:
        rsync(deploy, dry)
        digest, files = source_hash()
    prune_orphan_meta(deploy, dry)
    old = project / OLD_REL
    log(f"[sync] 清理旧落点（只删 {OLD_REL}/ 与其 .meta）：")
    rmtree_guarded(old, dry, force, "旧落点迁移")
    write_version(deploy, dry, digest, len(files))
    log("[sync] 完成" + ("（dry-run，未改盘）" if dry else ""))


def do_strip(project: Path, dry: bool, force: bool):
    deploy = project / "Assets" / DEPLOY_NAME
    old = project / OLD_REL
    log(f"[strip] {project}：移除审查代码")
    rmtree_guarded(deploy, dry, force, "交付前剥离")
    rmtree_guarded(old, dry, force, "交付前剥离旧落点")
    log("[strip] 完成" + ("（dry-run，未改盘）" if dry else ""))


def _selftest_from_git(root: Path, ok):
    """在临时 git 仓里验证 `--from-git`：取修订内容、忽略工作区脏改动、清陈旧文件。"""
    if not shutil.which("git"):
        ok(False, "找不到 git，无法自验 --from-git")
        return
    repo = root / "gitrepo"
    src = repo / "开发工具" / "通用工具" / "审查" / "unity"
    (src / "Editor").mkdir(parents=True)
    (src / "Runtime").mkdir(parents=True)
    f1 = src / "Editor" / "AuditIO.cs"
    f1.write_text("// v1\n", encoding="utf-8")
    (src / "Runtime" / "AvatarAudit.Runtime.asmdef").write_text("{}\n", encoding="utf-8")

    def git(*args):
        r = subprocess.run(["git"] + list(args), cwd=str(repo),
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("git %s 失败：%s" % (" ".join(args), r.stderr.strip()))
        return r

    git("init", "-q")
    git("add", "-A")
    git("-c", "user.email=selftest@example.com", "-c", "user.name=selftest",
        "commit", "-q", "-m", "v1")
    rev = git("rev-parse", "HEAD").stdout.strip()

    saved = (SRC, AUDIT_ROOT, REPO_ROOT)
    globals()["SRC"] = src
    globals()["AUDIT_ROOT"] = src.parent
    globals()["REPO_ROOT"] = repo
    try:
        proj = root / "COMM-GITTEST"
        (proj / "Assets").mkdir(parents=True)
        deploy = proj / "Assets" / DEPLOY_NAME

        # 6a) 从 git 铺 v1，VERSION hash 按 git 内容算
        do_sync(proj, dry=False, force=False, from_git=rev)
        got = (deploy / "Editor" / "AuditIO.cs").read_text(encoding="utf-8")
        ok(got == "// v1\n", "从 git rev 铺出的内容与修订一致")
        vtxt = (deploy / "VERSION").read_text(encoding="utf-8")
        digest = [ln.split(": ", 1)[1] for ln in vtxt.splitlines()
                  if ln.startswith("hash: ")][0]
        ok(digest == git_source_hash(rev)[0], "VERSION hash 与 git 内容一致（非工作区）")

        # 6b) 工作区改脏 + 造陈旧文件，能列出来
        f1.write_text("// v2 worktree\n", encoding="utf-8")
        (deploy / "Editor" / "Stale.cs").write_text("// stale\n", encoding="utf-8")
        dirty = uncommitted_source_files()
        ok(bool(dirty), "git status 能看见未提交改动")
        ok(any("AuditIO.cs" in ln for ln in dirty), "警告清单里列出 AuditIO.cs")

        # 6c) 再从 git 铺：仍是 v1（忽略工作区），陈旧文件清掉
        do_sync(proj, dry=False, force=False, from_git=rev)
        got = (deploy / "Editor" / "AuditIO.cs").read_text(encoding="utf-8")
        ok(got == "// v1\n", "工作区脏改动不进入部署（仍取 git 内容）")
        ok(not (deploy / "Editor" / "Stale.cs").exists(), "git 模式清掉陈旧文件")

        # 6d) 不带 --from-git 时仍取工作区（v2）
        do_sync(proj, dry=False, force=False)
        got = (deploy / "Editor" / "AuditIO.cs").read_text(encoding="utf-8")
        ok(got == "// v2 worktree\n", "默认模式仍取工作区内容")
    except RuntimeError as e:
        ok(False, "git 自验异常：%s" % e)
    finally:
        globals()["SRC"], globals()["AUDIT_ROOT"], globals()["REPO_ROOT"] = saved


def do_selftest() -> int:
    """用临时假工程跑一遍部署/幂等/剥离，断言关键性质。不碰任何真实工程。"""
    root = Path(tempfile.mkdtemp(prefix="sync_audit_selftest_"))
    fails = []

    def ok(cond, label):
        log(("  PASS  " if cond else "  FAIL  ") + label)
        if not cond:
            fails.append(label)

    try:
        proj = root / "COMM-TEST"
        # 旧落点：带一个审查 .cs + 一个无关文件，验证“只删这个目录”
        old = proj / OLD_REL
        old.mkdir(parents=True)
        (old / "AuditIO.cs").write_text("// old\n", encoding="utf-8")
        (old / "AuditIO.cs.meta").write_text("guid: x\n", encoding="utf-8")
        (proj / "Assets" / "Editor").mkdir(parents=True, exist_ok=True)
        (proj / "Assets" / "Editor" / "Other.cs").write_text("// keep\n", encoding="utf-8")

        deploy = proj / "Assets" / DEPLOY_NAME

        # 1) dry-run 不改盘
        log("[selftest] dry-run 不动盘")
        do_sync(proj, dry=True, force=False)
        ok(not deploy.exists(), "dry-run 未创建 Assets/AvatarAudit")
        ok(old.exists(), "dry-run 未删旧落点")

        # 2) 真同步
        log("[selftest] 真实同步")
        do_sync(proj, dry=False, force=False)
        ok((deploy / "Editor" / "AvatarAudit.Editor.asmdef").is_file(), "Editor asmdef 已铺")
        ok((deploy / "Runtime" / "AvatarAudit.Runtime.asmdef").is_file(), "Runtime asmdef 已铺")
        ok((deploy / "Editor" / "AuditIO.cs").is_file(), "AuditIO.cs 已铺到 Editor/")
        ok((deploy / "VERSION").is_file(), "VERSION 已写")
        ok(not old.exists(), "旧落点目录已删")
        ok(not (proj / "Assets" / "Editor" / "AvatarAudit.meta").exists(), "旧落点 .meta 已删")
        ok((proj / "Assets" / "Editor" / "Other.cs").is_file(), "Assets/Editor 其它文件保留")
        vtxt = (deploy / "VERSION").read_text(encoding="utf-8")
        digest = [ln.split(": ", 1)[1] for ln in vtxt.splitlines() if ln.startswith("hash: ")][0]
        ok(digest == source_hash()[0], "VERSION 的 hash 与源树一致")

        # 3) 幂等：造一个 .meta + 一个陈旧文件，重跑后 .meta 保留、陈旧文件删掉
        log("[selftest] 重跑幂等：.meta 保留、陈旧产物清除")
        (deploy / "Editor" / "AuditIO.cs.meta").write_text("guid: unity-generated\n", encoding="utf-8")
        (deploy / "Editor" / "Stale.cs").write_text("// stale\n", encoding="utf-8")
        (deploy / "Editor" / "Stale.cs.meta").write_text("guid: stale\n", encoding="utf-8")
        do_sync(proj, dry=False, force=False)
        ok((deploy / "Editor" / "AuditIO.cs.meta").is_file(), "重跑保留 Unity 生成的 .meta")
        ok(not (deploy / "Editor" / "Stale.cs").exists(), "重跑删除陈旧 .cs")
        ok(not (deploy / "Editor" / "Stale.cs.meta").exists(), "重跑不残留陈旧 .cs.meta")

        # 4) strip
        log("[selftest] --strip")
        do_strip(proj, dry=False, force=False)
        ok(not deploy.exists(), "strip 删除 Assets/AvatarAudit")
        ok(not (proj / "Assets" / "AvatarAudit.meta").exists(), "strip 删除 Assets/AvatarAudit.meta")
        ok((proj / "Assets" / "Editor" / "Other.cs").is_file(), "strip 不动 Assets/Editor 其它文件")

        # 5) 指纹校验：空目录拒绝删
        log("[selftest] 指纹校验拒绝误删")
        bogus = proj / "Assets" / DEPLOY_NAME
        bogus.mkdir(parents=True)
        (bogus / "not_ours.txt").write_text("x\n", encoding="utf-8")
        try:
            do_strip(proj, dry=False, force=False)
            ok(False, "空指纹目录应被拒绝")
        except SystemExit as e:
            ok(e.code == 2, "空指纹目录被拒绝（exit 2）")

        # 6) --from-git：临时 git 仓取源；工作区改动被忽略并告警
        log("[selftest] --from-git <rev>")
        _selftest_from_git(root, ok)

        log("")
        if fails:
            log(f"selftest：{len(fails)} 项失败")
            return 1
        log("selftest：ALL PASS")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="同步 AvatarAudit 审查代码到 Unity 工程（T-09）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("project", nargs="?", help="Unity 工程目录（含 Assets/）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不改盘")
    ap.add_argument("--from-git", metavar="REV", default=None,
                    help="从 `git show <rev>:<源路径>` 取源同步（默认用工作区；"
                         "工作区有未提交改动时警告并列出）")
    ap.add_argument("--strip", action="store_true", help="反向删除：从工程里移除审查代码（T-23）")
    ap.add_argument("--force", action="store_true", help="跳过删除前的指纹校验（慎用）")
    ap.add_argument("--selftest", action="store_true", help="用临时假工程自检本脚本")
    args = ap.parse_args(argv)

    if args.selftest:
        return do_selftest()
    if not args.project:
        ap.error("需要 <工程目录>，或用 --selftest")
    if args.from_git and args.strip:
        ap.error("--from-git 只用于部署，不能与 --strip 同用")
    if not SRC.is_dir():
        die(f"同步源不存在：{SRC}")
    if not args.from_git and not shutil.which("rsync"):
        die("找不到 rsync（部署依赖它）")
    if args.from_git and not shutil.which("git"):
        die("找不到 git（--from-git 依赖它）")

    project = Path(args.project).expanduser().resolve()
    check_project(project)
    if args.strip:
        do_strip(project, args.dry_run, args.force)
    else:
        do_sync(project, args.dry_run, args.force, from_git=args.from_git)
    return 0


if __name__ == "__main__":
    sys.exit(main())
