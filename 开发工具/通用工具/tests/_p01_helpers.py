# -*- coding: utf-8 -*-
# 用途：隔离临时仓库的记录与提交测试辅助函数；只用于离线测试。
"""P01 独立测试共用工具。

做法：把 log_step.py / ws_git.py 按真实相对位置复制进一个临时工作区，使脚本里用
__file__ 算出来的 WS 指向临时目录（而不是真实 <工作区>），
从而在独立仓库里测提交语义，不对真实工作区制造失败。
"""
import os
import shutil
import subprocess
import tempfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(TESTS_DIR)
LOG_STEP = os.path.join(TOOLS, 'log_step.py')
WS_GIT = os.path.join(TOOLS, 'ws_git.py')


def tmp_workspace():
    """建一个含 开发工具/通用工具/{log_step,ws_git}.py 的临时工作区，返回其根。"""
    ws = tempfile.mkdtemp(prefix='p01_ws_')
    dst = os.path.join(ws, '开发工具', '通用工具')
    os.makedirs(dst)
    shutil.copy2(LOG_STEP, dst)
    shutil.copy2(WS_GIT, dst)
    return ws


def log_step(ws):
    return os.path.join(ws, '开发工具', '通用工具', 'log_step.py')


def ws_git(ws):
    return os.path.join(ws, '开发工具', '通用工具', 'ws_git.py')


def git(ws, *args, check=True):
    r = subprocess.run(['git', '-C', ws, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError('git %s failed rc=%d: %s' % (' '.join(args), r.returncode, r.stderr))
    return r


def init_repo(ws):
    git(ws, 'init', '-q')
    git(ws, 'config', 'user.email', 'p01@test')
    git(ws, 'config', 'user.name', 'P01')
    git(ws, 'config', 'commit.gpgsign', 'false')


def commit_all(ws, msg='init'):
    git(ws, 'add', '-A')
    git(ws, 'commit', '-q', '-m', msg)


def head(ws):
    return git(ws, 'rev-parse', 'HEAD').stdout.strip()


def head_files(ws):
    out = git(ws, 'ls-tree', '-r', '-z', '--name-only', 'HEAD').stdout
    return set(p for p in out.split('\0') if p)


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(s)


# 一份「旧状态头」的初始记录：用来验证普通追加后状态头被刷新而不是停在旧值。
OLD_STATE_RECORD = '''# 施工记录

<!-- 状态头:BEGIN（可整块改写，由 log_step.py 或验收者维护；下面的时间线只追加不改） -->
## 当前状态（2020-01-01 00:00）
- **阶段 / 交付状态**：阶段甲 / 进行中
- **最近一步**：旧步骤
- **下一步**：
  1. 下一步甲
- **未决 / 等用户**：
  - 未决甲
- **不许动**：
  - 禁区甲
<!-- 状态头:END -->

## 2020-01-01 00:00 · 第一步（Claude）
- **执行**：Claude
- **做了什么**：a
- **怎么验**：b
- **结果**：✓
- **未决**：无
'''

BEGIN = '<!-- 状态头:BEGIN'
END = '<!-- 状态头:END -->'


def state_block(s):
    i = s.index(BEGIN)
    j = s.index(END) + len(END)
    return s[i:j]


def state_line(s, field):
    """取状态头里单行字段的值；列表字段返回空串。"""
    for line in state_block(s).split('\n'):
        prefix = '- **%s**：' % field
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None
