#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途　　：核对一棵 markdown 目录（默认 开发工具/SOP）里所有相对 .md 链接的目标文件是否存在。

为什么要它：SOP 拆页、并页、改名后最常见的回归就是死链；收尾蒸馏规程
（SOP/04_施工记录与版本管理/收尾蒸馏与状态头.md）要求每轮改过的页跑一遍。
原先只有长程任务派工目录里的一次性副本（写死了相对路径与 before_tree 位置），2026-09-25 入库到这里。

只查 `](目标.md)` / `](目标.md#锚)` 形式的相对目标（`../xx.md`、`子目录/zz.md`）；
http(s)://、mailto:、纯 `#锚` 不查；锚点只取文件名部分，不校验锚点本身。

用法：
  check_links.py [根目录]                      # 默认：本脚本所在目录的 ../SOP
  check_links.py [根目录] --baseline <旧树>    # 旧树里同 (页,行,链接) 已断的算「改前已断（豁免）」
  check_links.py --help

  --baseline 的旧树是改动前的同一目录快照（例：git worktree 或 `git archive HEAD 开发工具/SOP | tar -x -C <dir>`
  后的 <dir>/开发工具/SOP）。没给就不豁免任何断链。

退出码：0 = 没有（新增）断链；1 = 有；2 = 参数错误（根目录不存在）。
"""
import argparse
import os
import re
import sys

LINK = re.compile(r'\]\(([^)\s]+\.md)(#[^)]*)?\)')


def check(root):
    """返回 (链接总数, [(相对页路径, 行号, 链接原文), ...断链])。"""
    broken = []
    n = 0
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if not fn.endswith('.md'):
                continue
            p = os.path.join(dp, fn)
            with open(p, encoding='utf-8') as fh:
                text = fh.read()
            for i, line in enumerate(text.splitlines(), 1):
                for m in LINK.finditer(line):
                    target = m.group(1)
                    if '://' in target or target.startswith('mailto:'):
                        continue
                    n += 1
                    dest = os.path.normpath(os.path.join(os.path.dirname(p), target))
                    if not os.path.exists(dest):
                        broken.append((os.path.relpath(p, root), i, m.group(0)))
    return n, broken


def main(argv=None):
    default_root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'SOP'))
    ap = argparse.ArgumentParser(
        description='核对 markdown 目录里相对 .md 链接的目标是否存在（默认查 开发工具/SOP）。')
    ap.add_argument('root', nargs='?', default=default_root,
                    help='要查的目录（默认 %(default)s）')
    ap.add_argument('--baseline', metavar='旧树',
                    help='改动前的同一目录快照；其中同 (页,行,链接) 已断的链接算豁免')
    a = ap.parse_args(argv)

    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        print('根目录不存在: %s' % root, file=sys.stderr)
        return 2
    n, broken = check(root)
    base = set()
    if a.baseline:
        if not os.path.isdir(a.baseline):
            print('--baseline 目录不存在: %s' % a.baseline, file=sys.stderr)
            return 2
        base = set(check(os.path.abspath(a.baseline))[1])
    pre = [b for b in broken if b in base]
    new = [b for b in broken if b not in base]
    print('检查 %s' % root)
    print('相对 .md 链接共 %d 条；断链 %d 条 = 改前已断（豁免）%d + 新增 %d'
          % (n, len(broken), len(pre), len(new)))
    for f, i, l in pre:
        print('  改前已断(豁免): %s:%d  %s' % (f, i, l))
    for f, i, l in new:
        print('  断链: %s:%d  %s' % (f, i, l))
    print('新增断链数 = %d' % len(new))
    return 1 if new else 0


if __name__ == '__main__':
    sys.exit(main())
