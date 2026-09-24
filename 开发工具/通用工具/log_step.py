#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途　　：给工程/长程任务追加一条施工记录（时间戳只从系统时钟取）、维护文件顶部的「状态头」、可选一步提交；写后回读，回读不一致就不提交。

为什么要它（工作流审理 2026-09-23，A2/A5；用户拍板）：
  · 09-18/19/20/22 四轮共 20 余条时间戳写成「未来时间」——模型估时不可信，时间只能来自时钟，所以本脚本不接受 --time。
  · 两次「写入失败但提交照跑」——写入与提交之间必须有回读校验，失败就停（退出码 2，不提交）。
  · 施工记录只追加、没有状态头，接手要读几十万字节——「状态头」是文件顶部唯一可整块改写的区域。
  · 两层制（作者 09-23）：撞墙的教训在条目里打「待蒸馏」标签，收尾由干净上下文代理进 SOP，执行会话不改 SOP 主体。

用法：
  log_step.py <工程或长程任务目录> --title "55 狐耳缩放改为 k=0.92" --by Claude|DSH|用户手动 \
      --did "改了什么" --verify "怎么验（工具/判据/读数）" --result "✓|✗|未验证（原因）" --open "未决；没有写 无" \
      [--distill "教训：触发时刻＋可查问句"]... \
      [--stage "80 性能优化 / 进行中"] [--next "一句话（来源 路径:行）"]... [--pending "一句话（来源）"]... [--forbid "用户禁区"]... \
      [--commit "[简称] 一句话" [--paths 路径...]]
  log_step.py <目录> --show                       # 打印状态头＋最后 3 条标题（接手用）
  log_step.py <目录> --state-only --stage ... [--next ...]   # 只改状态头，不追加条目
退出码：0 成功；1 参数/文件错；2 写入后回读不一致（不提交）；3 提交失败。
"""
import argparse, datetime, os, re, subprocess, sys

WS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BEGIN = '<!-- 状态头:BEGIN（可整块改写，由 log_step.py 或验收者维护；下面的时间线只追加不改） -->'
END = '<!-- 状态头:END -->'
FIELDS = ['阶段 / 交付状态', '最近一步', '下一步', '未决 / 等用户', '不许动']


def find_record(d):
    for name in ('_施工记录.md', '施工记录.md'):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def write(p, s):
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(s)


def parse_state(block):
    """状态头 → {字段: 单行值 或 [列表行]}"""
    st = {}
    cur = None
    for line in block.split('\n'):
        m = re.match(r'- \*\*(.+?)\*\*：(.*)', line)
        if m:
            cur = m.group(1)
            v = m.group(2).strip()
            st[cur] = v if v else []
            continue
        if cur and (line.startswith('  ') and line.strip()):
            if isinstance(st[cur], str):
                st[cur] = [st[cur]] if st[cur] else []
            st[cur].append(line.strip())
    return st


def build_state(ts, st):
    out = [BEGIN, '## 当前状态（%s）' % ts]
    for f in FIELDS:
        v = st.get(f, '')
        if isinstance(v, list):
            if f == '下一步':
                out.append('- **%s**：' % f)
                out += ['  %d. %s' % (i + 1, re.sub(r'^\d+\.\s*', '', x)) for i, x in enumerate(v)]
            else:
                out.append('- **%s**：' % f)
                out += ['  - %s' % re.sub(r'^-\s*', '', x) for x in v]
        else:
            out.append('- **%s**：%s' % (f, v if v else '无'))
    out.append(END)
    return '\n'.join(out)


def split_state(s):
    """返回 (前, 状态头块 或 None, 后)。没有状态头时前=引用说明段之前的部分。"""
    i = s.find(BEGIN[:12])
    if i >= 0:
        j = s.find(END, i)
        if j < 0:
            sys.exit('状态头有 BEGIN 无 END，先手工修')
        j += len(END)
        return s[:i], s[i:j], s[j:]
    m = re.search(r'^## ', s, flags=re.M)  # 第一条时间线条目
    k = m.start() if m else len(s)
    return s[:k], None, s[k:]


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('dir')
    ap.add_argument('--title'); ap.add_argument('--by', default='Claude')
    ap.add_argument('--did'); ap.add_argument('--verify'); ap.add_argument('--result'); ap.add_argument('--open')
    ap.add_argument('--distill', action='append', default=[])
    ap.add_argument('--stage'); ap.add_argument('--last')
    ap.add_argument('--next', action='append'); ap.add_argument('--pending', action='append'); ap.add_argument('--forbid', action='append')
    ap.add_argument('--commit'); ap.add_argument('--paths', nargs='*', default=[])
    ap.add_argument('--show', action='store_true'); ap.add_argument('--state-only', action='store_true')
    a = ap.parse_args()

    d = os.path.abspath(a.dir)
    rec = find_record(d)
    if not rec:
        sys.exit('目录下没有 _施工记录.md / 施工记录.md：' + d)
    s = read(rec)
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')  # 唯一的时间来源

    if a.show:
        pre, blk, post = split_state(s)
        print(blk or '（无状态头）')
        titles = re.findall(r'^## .*$', post, flags=re.M)
        print('\n最后 3 条：'); [print('  ' + t) for t in titles[-3:]]
        return 0

    entry = None
    if not a.state_only:
        missing = [k for k in ('title', 'did', 'verify', 'result', 'open') if not getattr(a, k)]
        if missing:
            sys.exit('缺参数：--' + ' --'.join(missing) + '（只改状态头请加 --state-only）')
        lines = ['## %s · %s（%s）' % (ts, a.title, a.by),
                 '- **执行**：%s' % a.by,
                 '- **做了什么**：%s' % a.did,
                 '- **怎么验**：%s' % a.verify,
                 '- **结果**：%s' % a.result,
                 '- **未决**：%s' % a.open]
        for x in a.distill:
            lines.append('- **待蒸馏**：%s' % x)
        entry = '\n'.join(lines) + '\n'

    pre, blk, post = split_state(s)
    want_state = any([a.stage, a.last, a.next, a.pending, a.forbid])
    # 每次成功追加都要刷新状态头（「最近一步」= 本条标题、「状态时间」= 本刻），未点名的字段原样保留；
    # 显式 --last 优先。原实现只在传了阶段/下一步等状态参数时才改写，普通追加后「最近一步」会停在旧条目、
    # 状态时间也不动（2026-09-23 清账 P01 已复现）。
    if entry or want_state:
        st = parse_state(blk) if blk else {}
        if a.stage: st['阶段 / 交付状态'] = a.stage
        if a.last: st['最近一步'] = a.last
        elif entry: st['最近一步'] = a.title
        if a.next: st['下一步'] = a.next
        if a.pending: st['未决 / 等用户'] = a.pending
        if a.forbid: st['不许动'] = a.forbid
        blk_new = build_state(ts, st)
        if not pre.endswith('\n\n'):
            pre = pre.rstrip('\n') + '\n\n'
        s = pre + blk_new + '\n\n' + post.lstrip('\n')
    if entry:
        if not s.endswith('\n'):
            s += '\n'
        s = s + '\n' + entry
    write(rec, s)

    # 回读校验：条目标题在文末、状态头 BEGIN/END 各恰好一个
    back = read(rec)
    ok = True
    if entry and not back.rstrip().endswith(entry.rstrip()):
        ok = False; print('✗ 回读：条目不在文末', file=sys.stderr)
    if back.count(BEGIN[:12]) > 1 or back.count(END) > 1:
        ok = False; print('✗ 回读：状态头标记不唯一', file=sys.stderr)
    if not ok:
        return 2
    print('已写入 %s（%s）%s' % (os.path.relpath(rec, WS), ts, '：' + a.title if entry else '：状态头'))

    if a.commit:
        paths = list(a.paths) + [os.path.relpath(rec, WS)]
        cmd = [sys.executable, os.path.join(WS, '开发工具', '通用工具', 'ws_git.py'), 'commit', '-m', a.commit, '--'] + paths
        r = subprocess.run(cmd, cwd=WS, capture_output=True, text=True)
        sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
        if r.returncode != 0:
            print('✗ 提交失败（记录已写入，未回滚）', file=sys.stderr); return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
