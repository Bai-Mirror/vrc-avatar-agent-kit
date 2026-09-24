#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途　　：两层制的「收尾蒸馏」输入收集器：把某时间点之后的「待蒸馏」标签（各施工记录）、DSH 回复里的「应写进 SOP 的教训」段（流水账）、
          以及这段时间被改过的 SOP 页清单，汇成一份给干净上下文代理读的材料包。只读。

为什么（作者 2026-09-23 拍板两层制）：执行会话在疲劳上下文里随做随记 SOP，产出跨页矛盾与只拆不缩；改成执行会话只打标签，
  收尾由没有对话包袱的代理读「标签＋教训段＋被改的页」在原处合并。本脚本负责把这三样机械地捞出来，代理不必翻大文件。

用法：
  distill_collect.py --since "2026-09-23 00:00" [--out 材料包.md]      # 缺省打印到 stdout
  distill_collect.py --last-mark                                        # 打印上次蒸馏时间（读 _长程任务_20260918/蒸馏记录.md 末行）
  distill_collect.py --mark "一句话" [--since "采集时刻"]              # 蒸馏完成后记边界（缺省用上次采集时刻，不是完成时刻）
"""
import argparse, datetime, os, re, subprocess, sys, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_env  # noqa: E402  读 <工作区>/kit.env；工作区根＝VRC_WS，缺省按本脚本位置推算

WS = str(kit_env.WS)
# 蒸馏边界与采集时刻存放目录（相对工作区，kit.env 的 DISTILL_DIR 可改）
DISTILL_DIR = os.path.join(WS, kit_env.get('DISTILL_DIR', '_长程任务_20260918'))
MARK = os.path.join(DISTILL_DIR, '蒸馏记录.md')


STAMP = os.path.join(DISTILL_DIR, '.distill_collect_stamp')


def _read_collect_stamp():
    try:
        return open(STAMP, encoding='utf-8').read().strip() or None
    except OSError:
        return None


def git(*a):
    return subprocess.run(['git', '-C', WS, '-c', 'core.quotepath=false'] + list(a), capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since'); ap.add_argument('--out'); ap.add_argument('--mark'); ap.add_argument('--last-mark', action='store_true')
    a = ap.parse_args()
    if a.last_mark:
        if os.path.exists(MARK):
            lines = [l for l in open(MARK, encoding='utf-8').read().split('\n') if l.startswith('- ')]
            print(lines[-1] if lines else '（无）')
        else:
            print('（无）')
        return 0
    if a.mark:
        # 边界用「材料包采集时刻」而不是「蒸馏完成时刻」：采集到完成之间新落的标签否则会被下一轮 --since 漏掉（09-23 首跑实测：04:46 采集、04:51 记，04:48 的标签被跳过）。
        ts = a.since or _read_collect_stamp() or datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        os.makedirs(DISTILL_DIR, exist_ok=True)
        new = not os.path.exists(MARK)
        with open(MARK, 'a', encoding='utf-8', newline='\n') as f:
            if new:
                f.write('# 收尾蒸馏记录\n\n> 由 `distill_collect.py --mark` 追加；每行＝一次干净上下文蒸馏完成的时间与一句话。下次 `--since` 从最后一行取。\n\n')
            f.write('- %s · %s\n' % (ts, a.mark))
        print('已记 %s' % ts)
        return 0
    if not a.since:
        sys.exit('要 --since "YYYY-MM-DD HH:MM"（可先 --last-mark 看上次蒸馏时间）')
    since = datetime.datetime.strptime(a.since, '%Y-%m-%d %H:%M')
    try:
        with open(STAMP, 'w', encoding='utf-8') as f:
            f.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))   # 本次采集时刻，供 --mark 当边界
    except OSError:
        pass
    out = ['# 蒸馏材料包（%s 之后）' % a.since, '', '> 由 distill_collect.py 生成。蒸馏代理只读本包与它点名的页；改 SOP 在原处合并，不另起页；改完跑 `_体积欠账.md` 的量法与死链检查。', '']

    # 1. 施工记录里的「待蒸馏」
    out += ['## 一、待蒸馏标签（施工记录）', '']
    n1 = 0
    for f in sorted(glob.glob(os.path.join(WS, '*', '_施工记录.md')) + glob.glob(os.path.join(WS, '_长程任务_*', '施工记录.md'))):
        cur = None
        for line in open(f, encoding='utf-8'):
            m = re.match(r'## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (.*)', line)
            if m:
                cur = (datetime.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M'), m.group(2).strip())
                continue
            if '待蒸馏' in line and cur and cur[0] >= since:
                out.append('- `%s` %s 「%s」：%s' % (os.path.relpath(f, WS), cur[0].strftime('%m-%d %H:%M'), cur[1][:40], line.strip().replace('- **待蒸馏**：', '')))
                n1 += 1
    if not n1:
        out.append('（无）')
    out.append('')

    # 2. 流水账里 DSH 的教训段
    out += ['## 二、DSH 回复里的「应写进 SOP 的教训」（流水账）', '']
    n2 = 0
    j = os.path.join(WS, '_DSH流水账.md')
    if os.path.exists(j):
        entries = re.split(r'\n(?=## \d{4}-\d{2}-\d{2} \d{2}:\d{2})', open(j, encoding='utf-8').read())
        for e in entries:
            m = re.match(r'## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (.*)', e)
            if not m or datetime.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M') < since:
                continue
            if '应写进 SOP 的教训' not in e:
                continue
            task = re.search(r'\*\*任务\*\*：(.*)', e)
            seg = e.split('应写进 SOP 的教训', 1)[1]
            seg = re.split(r'\n> ##? |\n> \*\*[^*]+\*\*：', seg)[0]
            lines = [l[2:] if l.startswith('> ') else l for l in seg.split('\n')]
            lines = [l for l in lines if l.strip()][:12]
            out.append('### %s · %s' % (m.group(1), (task.group(1) if task else '')[:80]))
            out += lines + ['']
            n2 += 1
    if not n2:
        out.append('（无）')
    out.append('')

    # 3. 这段时间被改过的 SOP 页
    out += ['## 三、这段时间被改过的 SOP 页（git）', '']
    files = git('log', '--since=' + a.since, '--name-only', '--format=', '--', '开发工具/SOP').split('\n')
    seen = []
    for f in files:
        if f and f not in seen:
            seen.append(f)
    for f in seen:
        try:
            sz = os.path.getsize(os.path.join(WS, f))
        except OSError:
            sz = 0
        out.append('- %s（%d B%s）' % (f, sz, '，⚠ 超 10 KB' if sz > 10240 else ''))
    if not seen:
        out.append('（无）')
    out.append('')
    out += ['## 四、蒸馏代理的动作清单', '',
            '1. 每条标签/教训：先 `grep` SOP 有没有同义条目；有就在原处改（补触发时刻、可查问句、取舍），没有才加，加在最贴的页。',
            '2. 第三节每页：跑字节数（>10,240 拆子页，步骤表与判据留主页）、`python3 开发工具/通用工具/check_links.py`（死链）、同一主题跨页矛盾（数字/件数/类别）。',
            '3. 不改施工记录、不改流水账；处理过的标签在本包末尾列「已并入 → 页:节」。',
            '4. 完成后 `python3 开发工具/通用工具/distill_collect.py --mark "<一句话>"`，再 `ws_git.py commit` 只点名改过的 SOP 页。', '']
    text = '\n'.join(out)
    if a.out:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print('已写 %s（标签 %d、教训段 %d、SOP 页 %d）' % (a.out, n1, n2, len(seen)))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
