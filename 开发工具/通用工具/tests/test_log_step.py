# -*- coding: utf-8 -*-
# 用途：验证施工记录状态头刷新、字段保留及提交错误传播；只用于离线测试。
"""P01 log_step 独立测试：状态头刷新 / 字段保留 / 显式 --last / 不重复 / --show 只读 / --commit 回传失败。

运行：python3 -m pytest 开发工具/通用工具/tests/test_log_step.py -q
"""
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _p01_helpers import (BEGIN, END, OLD_STATE_RECORD, commit_all, head,  # noqa: E402
                          head_files, init_repo, log_step, read, run,
                          state_block, state_line, tmp_workspace, write)


def _entry_args(title):
    return ['--title', title, '--by', 'DSH', '--did', 'd', '--verify', 'v',
            '--result', '✓', '--open', '无']


def _setup(record=None):
    ws = tmp_workspace()
    proj = os.path.join(ws, 'proj')
    write(os.path.join(proj, '_施工记录.md'), record if record is not None else OLD_STATE_RECORD)
    return ws, proj, os.path.join(proj, '_施工记录.md')


def test_plain_append_refreshes_last_step_and_state_time():
    ws, proj, rec = _setup()
    r = run(['python3', log_step(ws), proj] + _entry_args('普通追加'), ws)
    assert r.returncode == 0, r.stderr
    s = read(rec)
    # 最近一步 = 本条标题；状态时间 = 本刻（旧头里的 2020-01-01 被覆盖）
    assert state_line(s, '最近一步') == '普通追加'
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    assert '## 当前状态（' + today in s
    assert '2020-01-01 00:00' not in state_block(s)   # 旧头里的时间被刷新掉（旧时间线条目仍在）
    # 未点名的既有字段原样保留
    blk = state_block(s)
    for keep in ('阶段甲 / 进行中', '下一步甲', '未决甲', '禁区甲'):
        assert keep in blk, keep
    # 条目已追加到文末
    assert s.rstrip().endswith('未决**：无')


def test_second_plain_append_is_the_latest_step():
    ws, proj, rec = _setup()
    assert run(['python3', log_step(ws), proj] + _entry_args('第一条'), ws).returncode == 0
    assert run(['python3', log_step(ws), proj] + _entry_args('第二条'), ws).returncode == 0
    assert state_line(read(rec), '最近一步') == '第二条'


def test_explicit_last_wins_over_title():
    ws, proj, rec = _setup()
    r = run(['python3', log_step(ws), proj] + _entry_args('标题不该进状态') + ['--last', '显式最近一步'], ws)
    assert r.returncode == 0, r.stderr
    assert state_line(read(rec), '最近一步') == '显式最近一步'


def test_no_duplicate_state_header_across_appends():
    ws, proj, rec = _setup()
    for t in ('A', 'B', 'C'):
        assert run(['python3', log_step(ws), proj] + _entry_args(t), ws).returncode == 0
    s = read(rec)
    assert s.count(BEGIN) == 1
    assert s.count(END) == 1
    assert s.count('## 当前状态') == 1
    assert len(re.findall(r'^## ', s, flags=re.M)) == 5  # 1 状态头 + 1 旧条目 + 3 新条目


def test_show_is_read_only():
    ws, proj, rec = _setup()
    before = read(rec).encode('utf-8')
    r = run(['python3', log_step(ws), proj, '--show'], ws)
    assert r.returncode == 0, r.stderr
    assert read(rec).encode('utf-8') == before
    assert '最近一步' in r.stdout


def test_state_only_does_not_touch_last_step():
    ws, proj, rec = _setup()
    assert run(['python3', log_step(ws), proj] + _entry_args('一条'), ws).returncode == 0
    last = state_line(read(rec), '最近一步')
    r = run(['python3', log_step(ws), proj, '--state-only', '--stage', '阶段乙 / 完成'], ws)
    assert r.returncode == 0, r.stderr
    s = read(rec)
    assert state_line(s, '阶段 / 交付状态') == '阶段乙 / 完成'
    assert state_line(s, '最近一步') == last


def test_missing_state_header_gets_created_once():
    ws, proj, rec = _setup(record='# 施工记录\n\n## 2020-01-01 00:00 · 旧（Claude）\n- **执行**：Claude\n')
    assert run(['python3', log_step(ws), proj] + _entry_args('新建头'), ws).returncode == 0
    s = read(rec)
    assert s.count(BEGIN) == 1 and s.count(END) == 1
    assert state_line(s, '最近一步') == '新建头'


def test_commit_failure_relayed_and_head_unchanged():
    ws, proj, rec = _setup()
    init_repo(ws)
    commit_all(ws, 'init')
    before = head(ws)
    r = run(['python3', log_step(ws), proj] + _entry_args('提交失败用例') +
            ['--commit', '[P01] 应失败', '--paths', 'proj/不存在.txt'], ws)
    assert r.returncode == 3, (r.returncode, r.stdout, r.stderr)
    assert '提交失败' in r.stderr
    assert head(ws) == before                      # HEAD 没动
    assert '提交失败用例' in read(rec)              # 记录本身已落盘


def test_commit_success_advances_head():
    ws, proj, rec = _setup()
    init_repo(ws)
    commit_all(ws, 'init')
    before = head(ws)
    r = run(['python3', log_step(ws), proj] + _entry_args('提交成功用例') +
            ['--commit', '[P01] 记录提交'], ws)
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert head(ws) != before
    assert 'proj/_施工记录.md' in head_files(ws)
