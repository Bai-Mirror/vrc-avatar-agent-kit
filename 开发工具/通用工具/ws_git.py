#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途　　：工作区 git 的唯一提交入口（强制准则 6：每步写施工记录并提交）。

为什么不直接 git add -A：
  工程里有大量单个几十 MB 的文本资产（面捕生成网格、BlendShare、厂商 AFK 动画），
  .gitignore 管不了「按大小排除」。本脚本每次提交前把 > 5 MB 的文件写进 .git/info/exclude，
  **但工程主场景 <工程>/Assets/_Work/<名>.unity 例外，上限 32 MB**（来由见下方 SCENE_LIMIT 注释），
  并扫一遍待提交内容里有没有 API key（sk-…），有就中止。

用法：
    python3 开发工具/通用工具/ws_git.py status                    # 按工程汇总未提交改动
    python3 开发工具/通用工具/ws_git.py commit -m "[工程C] 70 回归：…"  # 刷新大文件排除 → add → 扫密钥 → 提交
    python3 开发工具/通用工具/ws_git.py commit -m "…" 路径1 路径2      # 只提交指定路径
    python3 开发工具/通用工具/ws_git.py refresh-excludes             # 只刷新大文件排除表

提交信息约定：`[工程简称] <阶段号> <一句话>`，与该工程 _施工记录.md 的条目标题一致。
在 Claude Code 里运行时自动追加 Co-Authored-By 尾注。
"""
import os, re, sys, subprocess, argparse

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LIMIT = 5 * 1024 * 1024

# ── 工程主场景白名单（2026-09-22）────────────────────────────────────────────
# 来由：09-22 工程B_Milfy 拆分第 1 步后，主场景
#   工程B/Assets/_Work/工程B_Milfy.unity 涨到 6.28 MB，
#   被本脚本按 5 MB 线判为大文件并 rm --cached 移出版本库（提交 e9f37012 里
#   136692 行删除）；同一天 工程A 主场景 4.78 MB 也快到线。
# 为什么该例外：主场景是手工搭出来的装配结果，丢了不能从素材包重建，性质与
#   面捕生成网格 / BlendShare / 厂商 AFK 动画（都能重新生成）完全不同。
# 依据：开发工具/SOP/04_施工记录与版本管理.md:62 早就写了
#   「主场景超过 5 MB 被排除了，要单独处理，别整体调线」——这条白名单就是
#   那个「单独处理」。
# 规则：路径匹配 MAIN_SCENE 的文件上限 SCENE_LIMIT；超过 32 MB 的主场景仍被
#   排除，并打一行醒目警告（refresh_excludes 里），不静默吞掉。
MAIN_SCENE = re.compile(r'^[^/]+/Assets/_Work/[^/]+\.unity$')
SCENE_LIMIT = 32 * 1024 * 1024

BEGIN = '# >>> ws_git.py 自动生成：> 5 MB 的文件（勿手改）'
END = '# <<< ws_git.py'
SECRET = re.compile(rb'sk-[A-Za-z0-9]{32,}')
TRAILER = os.environ.get('WS_GIT_TRAILER', 'Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>')


def limit_for(p):
    """工程主场景走 32 MB 线，其它文件仍走 5 MB 线。"""
    return SCENE_LIMIT if MAIN_SCENE.match(p) else LIMIT


# git 的报错走固定英文（2026-09-25）：本机 LANG=zh_CN 时 git 输出「路径规格…未匹配」而非
# 「pathspec…did not match」，下面按 stderr 文本判断（如 git_retry 找 index.lock）与测试断言
# 都会随语言漂移。C.UTF-8 只换消息语言、仍是 UTF-8 字符集，中文路径与提交说明不受影响。
GIT_ENV = dict(os.environ, LC_ALL='C.UTF-8', LANGUAGE='C')


def git(*args, check=True, capture=True):
    r = subprocess.run(['git', '-C', WS, '-c', 'core.quotepath=false', *args],
                       capture_output=capture, text=False, env=GIT_ENV)
    if check and r.returncode != 0:
        sys.stderr.write((r.stderr or b'').decode('utf-8', 'replace'))
        sys.exit(r.returncode)
    return r


def _strip_block(ex):
    try:
        s = open(ex, encoding='utf-8').read()
    except FileNotFoundError:
        s = ''
    s = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END) + r'\n?', '', s, flags=re.S)
    open(ex, 'w', encoding='utf-8', newline='\n').write(s)
    return s


def refresh_excludes():
    # 用 git 问真实路径：git worktree 里的 .git 是文件，拼 .git/info/exclude 会写不进去（2026-09-25 kit-prep 踩过）
    ex = git('rev-parse', '--git-path', 'info/exclude').stdout.decode('utf-8').strip()
    ex = ex if os.path.isabs(ex) else os.path.join(WS, ex)
    os.makedirs(os.path.dirname(ex), exist_ok=True)
    # ⚠ 先把上次生成的排除块拿掉再列候选：否则已排除的大文件不会出现在 --others 里，
    #   会被当成「不存在」从排除表里删掉，下一次 add 又被加回来（2026-09-18 首次提交时踩过）。
    s = _strip_block(ex)
    out = git('ls-files', '-z', '--cached', '--others', '--exclude-standard').stdout
    big = []
    for p in out.decode('utf-8', 'replace').split('\0'):
        if not p:
            continue
        fp = os.path.join(WS, p)
        try:
            if os.path.isfile(fp) and os.path.getsize(fp) > limit_for(p):
                big.append(p)
        except OSError:
            pass
    def esc(p):
        return '/' + re.sub(r'([\[\]*?!#\\ ])', r'\\\1', p)
    block = BEGIN + '\n' + ''.join(esc(p) + '\n' for p in sorted(big)) + END + '\n'
    open(ex, 'w', encoding='utf-8', newline='\n').write(s.rstrip('\n') + ('\n' if s.strip() else '') + block)
    # 已经被跟踪的大文件：从索引移除（保留工作区文件）
    tracked = set(git('ls-files', '-z').stdout.decode('utf-8', 'replace').split('\0'))
    for p in big:
        if p in tracked:
            git('rm', '--cached', '-q', '--', p)
    # 主场景超过 32 MB：仍排除，但必须让人看见，不能静默（SOP 04:62）
    for p in big:
        if MAIN_SCENE.match(p):
            try:
                mb = os.path.getsize(os.path.join(WS, p)) / 1048576.0
            except OSError:
                mb = 0.0
            sys.stderr.write('⚠️ 主场景超过 %d MB，已排除出版本库，需单独处理（SOP 04:62）：%s（%.2f MB）\n'
                             % (SCENE_LIMIT >> 20, p, mb))
    return big


def status():
    out = git('status', '--porcelain', '-z', '--untracked-files=all').stdout.decode('utf-8', 'replace')
    groups = {}
    for e in out.split('\0'):
        if len(e) < 4:
            continue
        p = e[3:]
        top = p.split('/', 1)[0]
        groups[top] = groups.get(top, 0) + 1
    if not groups:
        print('工作区干净')
    for k, v in sorted(groups.items(), key=lambda x: -x[1]):
        print('%6d  %s' % (v, k))
    # 2026-09-23 工作流审理 A7：_dsh_tmp_* 中间产物无人清（7 个目录 170 MB 停了一天多）。保留期 48 h，超期在这里点名，删不删由人定。
    import time, glob
    stale = []
    for d in sorted(glob.glob(os.path.join(WS, '_dsh_tmp_*'))):
        try:
            age_h = (time.time() - max(os.path.getmtime(d), max((os.path.getmtime(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs), default=0))) / 3600
        except OSError:
            continue
        if age_h > 48:
            stale.append('%s（%.0f h 未动）' % (os.path.basename(d), age_h))
    if stale:
        print('⚠ 超过 48 h 没动的 DSH 临时目录（SOP 沙箱限制：用完删；确认无人在用再 rm -rf）：\n  ' + '\n  '.join(stale))


def git_retry(*args, capture=True):
    """并行派工时别的进程可能正拿着 index.lock：重试 10 次、每次等 1 s，再失败才退出。"""
    import time
    for i in range(10):
        r = git(*args, check=False, capture=capture)
        if r.returncode == 0:
            return r
        err = (r.stderr or b'').decode('utf-8', 'replace') if capture else ''
        if 'index.lock' not in err or i == 9:
            sys.stderr.write(err)
            sys.exit(r.returncode)
        time.sleep(1)


def commit(msg, paths):
    # 点名提交必须只提交点名的路径（2026-09-22 修）：原来是「add 点名路径 → git commit 整个暂存区」，
    # 并行时别的进程（DSH 派工）已 add 的文件会被卷进这次提交（49384441 卷走 L5-4c 两个文件）。
    # 现在：add 点名路径（被忽略的 png 之类只警告不中止）→ 只列点名路径里已暂存的文件 → `git commit -- <这些文件>`（--only 语义，别人暂存的留在暂存区）。
    big = refresh_excludes()
    # 2026-09-23 工作流审理 A1：流水账由 dsh_task.js 自动追加，单独为它提交是噪音（8 次「流水账自动追加」提交、16 次闸口拦截）。
    # 点名提交时若它有改动就顺手带上；不点名（全量）本来就包含。
    if paths:
        jp = os.path.join(WS, '_DSH流水账.md')
        if os.path.isfile(jp) and '_DSH流水账.md' not in [os.path.basename(x) for x in paths]:
            st = git('status', '--porcelain', '--', '_DSH流水账.md', check=False).stdout.decode('utf-8', 'replace').strip()
            if st:
                paths = list(paths) + ['_DSH流水账.md']
    if paths:
        # 区分「明确允许忽略」与真正的路径/锁错误（2026-09-23 清账 P01）：
        # 原实现把所有 git add 非零都当「多半是被忽略的文件」警告放行。实际
        # `git add -A -- 缺失路径 真实改动路径` 会 exit 128 且一个都不暂存，于是下面 staged 为空、
        # 打印「没有可提交的改动」exit 0，真实改动被静默丢掉。现在：命中 .gitignore / .git/info/exclude
        # 且确实存在的路径才跳过并告警（大文件/生成物），其余交给 git add；add 因缺失路径 / index.lock
        # 等失败时非零退出，由调用方（log_step --commit 会退 3）感知。
        ignored = [p for p in paths
                   if os.path.exists(os.path.join(WS, p))
                   and git('check-ignore', '-q', '--', p, check=False).returncode == 0]
        wanted = [p for p in paths if p not in ignored]
        if ignored:
            sys.stderr.write('（点名路径被忽略，跳过不提交（大文件/生成物）：%s）\n' % '、'.join(ignored))
        if wanted:
            git_retry('add', '-A', '--', *wanted)   # 非零即真正的路径/锁错误，不静默继续
            out = git_retry('diff', '--cached', '--name-only', '-z', '--', *wanted).stdout
        else:
            out = b''
    else:
        git_retry('add', '-A')
        out = git_retry('diff', '--cached', '--name-only', '-z').stdout
    staged = [p for p in out.decode('utf-8', 'replace').split('\0') if p]
    if not staged:
        print('没有可提交的改动')
        return
    hits = []
    for p in staged:
        fp = os.path.join(WS, p)
        try:
            if os.path.isfile(fp) and os.path.getsize(fp) <= limit_for(p) and SECRET.search(open(fp, 'rb').read()):
                hits.append(p)
        except OSError:
            pass
    if hits:
        git('reset', '-q', '--', *staged)          # 只撤自己这批，不动别的进程暂存的
        sys.exit('⛔ 待提交文件里有疑似 API key（sk-…），已取消暂存，先处理：\n  ' + '\n  '.join(hits))
    if os.environ.get('CLAUDECODE') and TRAILER not in msg:
        msg = msg.rstrip() + '\n\n' + TRAILER
    if paths:
        git_retry('commit', '-q', '-m', msg, '--', *staged)
    else:
        git_retry('commit', '-q', '-m', msg)
    head = git('log', '-1', '--format=%h %s').stdout.decode('utf-8', 'replace').strip()
    print('已提交 %s（%d 个文件；本次排除的大文件 %d 个）' % (head, len(staged), len(big)))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    sub.add_parser('refresh-excludes')
    c = sub.add_parser('commit')
    c.add_argument('-m', required=True)
    c.add_argument('paths', nargs='*')
    a = ap.parse_args()
    if not os.path.exists(os.path.join(WS, '.git')):   # worktree 里 .git 是文件，不能用 isdir
        sys.exit('工作区还没有 git 仓库：' + WS)
    if a.cmd == 'status':
        status()
    elif a.cmd == 'refresh-excludes':
        print('大文件排除 %d 个' % len(refresh_excludes()))
    else:
        commit(a.m, a.paths)


if __name__ == '__main__':
    main()
