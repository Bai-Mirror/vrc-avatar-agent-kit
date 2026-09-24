# -*- coding: utf-8 -*-
# 用途：验证点名提交不卷他人暂存及错误不得伪装成功；只用于离线测试。
"""P01 ws_git 独立测试：点名提交的「允许忽略」与「真错误」区分、不卷他人暂存、不静默丢点名改动。

运行：python3 -m pytest 开发工具/通用工具/tests/test_ws_git.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _p01_helpers import (commit_all, git, head, head_files, init_repo, read, run,  # noqa: E402
                          tmp_workspace, write, ws_git)


def _commit(ws, msg, *paths):
    cmd = ['python3', ws_git(ws), 'commit', '-m', msg]
    if paths:
        cmd += ['--'] + list(paths)
    return run(cmd, ws)


def _repo_with_baseline():
    ws = tmp_workspace()
    init_repo(ws)
    write(os.path.join(ws, 'a.txt'), 'a1\n')
    write(os.path.join(ws, 'b.txt'), 'b1\n')
    commit_all(ws, 'init')
    return ws


def test_named_commit_succeeds_and_advances_head():
    ws = _repo_with_baseline()
    write(os.path.join(ws, 'b.txt'), 'b2\n')
    before = head(ws)
    r = _commit(ws, '[P01] 点名提交', 'b.txt')
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert head(ws) != before
    assert git(ws, 'show', 'HEAD:b.txt').stdout == 'b2\n'


def test_missing_path_with_real_change_fails_head_unchanged():
    ws = _repo_with_baseline()
    write(os.path.join(ws, 'b.txt'), 'b2\n')
    before = head(ws)
    r = _commit(ws, '[P01] 应失败', 'missing.txt', 'b.txt')
    assert r.returncode != 0, (r.returncode, r.stdout, r.stderr)
    assert 'pathspec' in (r.stdout + r.stderr).lower()
    assert head(ws) == before
    assert '已提交' not in r.stdout
    assert read(os.path.join(ws, 'b.txt')) == 'b2\n'   # 点名改动没被静默丢掉，还在工作区


def test_other_process_staged_file_not_swept_in():
    ws = _repo_with_baseline()
    write(os.path.join(ws, 'other.txt'), 'other\n')
    git(ws, 'add', '--', 'other.txt')                  # 模拟别的进程已暂存
    write(os.path.join(ws, 'b.txt'), 'b2\n')
    r = _commit(ws, '[P01] 只提交 b', 'b.txt')
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert 'b.txt' in head_files(ws)
    assert 'other.txt' not in head_files(ws)           # 没被卷进这次提交
    staged = git(ws, 'diff', '--cached', '--name-only').stdout.split()
    assert 'other.txt' in staged                       # 仍在暂存区，留给别人
    assert read(os.path.join(ws, 'other.txt')) == 'other\n'


def test_ignored_exception_does_not_mask_real_path_error():
    ws = _repo_with_baseline()
    write(os.path.join(ws, '.gitignore'), '*.log\n')
    commit_all(ws, 'ignore rule')
    write(os.path.join(ws, 'noise.log'), 'noise\n')
    before = head(ws)
    r = _commit(ws, '[P01] 忽略+缺失', 'noise.log', 'missing.txt')
    assert r.returncode != 0, (r.returncode, r.stdout, r.stderr)
    assert head(ws) == before
    assert '被忽略' in r.stderr                         # 有说明，但没掩盖缺失路径错误


def test_ignored_only_is_success_without_commit():
    ws = _repo_with_baseline()
    write(os.path.join(ws, '.gitignore'), '*.log\n')
    commit_all(ws, 'ignore rule')
    write(os.path.join(ws, 'noise.log'), 'noise\n')
    before = head(ws)
    r = _commit(ws, '[P01] 只有忽略文件', 'noise.log')
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert '没有可提交的改动' in r.stdout
    assert head(ws) == before


def test_ignored_path_does_not_block_real_change_commit():
    """点名「被忽略的大文件/生成物 + 真实改动」时，真实改动仍要提交成功（旧实现会整体丢掉）。"""
    ws = _repo_with_baseline()
    write(os.path.join(ws, '.gitignore'), '*.log\n')
    commit_all(ws, 'ignore rule')
    write(os.path.join(ws, 'noise.log'), 'noise\n')
    write(os.path.join(ws, 'b.txt'), 'b2\n')
    before = head(ws)
    r = _commit(ws, '[P01] 忽略+真实改动', 'noise.log', 'b.txt')
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert head(ws) != before
    assert git(ws, 'show', 'HEAD:b.txt').stdout == 'b2\n'
    assert 'noise.log' not in head_files(ws)


def test_no_change_is_idempotent_success_not_error():
    ws = _repo_with_baseline()
    before = head(ws)
    r = _commit(ws, '[P01] 无改动', 'a.txt')
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert '没有可提交的改动' in r.stdout
    assert head(ws) == before


def test_named_deletion_still_commits():
    ws = _repo_with_baseline()
    os.remove(os.path.join(ws, 'a.txt'))
    r = _commit(ws, '[P01] 删除 a', 'a.txt')
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert 'a.txt' not in head_files(ws)


def test_index_lock_is_a_real_error():
    ws = _repo_with_baseline()
    write(os.path.join(ws, 'b.txt'), 'b2\n')
    before = head(ws)
    lock = os.path.join(ws, '.git', 'index.lock')
    with open(lock, 'w') as f:
        f.write('')
    try:
        r = _commit(ws, '[P01] 锁错误', 'b.txt')
    finally:
        os.remove(lock)
    assert r.returncode != 0, (r.returncode, r.stdout, r.stderr)
    assert head(ws) == before
