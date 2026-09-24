#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具 · 部件图鉴
适用素体：无关          相关素材：开发工具/素材包说明/*、<素材库>/*-<商品号>
可复用性：★★★ 换个单子直接能用
用途　　：派工前查一件 Booth 商品有没有「部件图鉴」，返回四态之一，供 DSH 决定
          是照图鉴动手、补图鉴，还是从头建档。规程见
          开发工具/SOP/50_服装发型装配/部件理解与菜单编排.md 第一节（四态表）。

查什么（只读，不改任何工程）：
  · <素材库>/*-<商品号>                      —— 厂商素材源（目录名常含方括号，用 listdir 过滤后缀，别用 glob）
  · 开发工具/素材包说明/*/部件图鉴.md          —— grep 商品号或名字
  · 开发工具/素材包说明/<商品名>/部件清单.json 与 部件图/

用法：
  python3 check_parts_doc.py --item <商品号> [--item <商品号> ...] [--avatar Kaguya]
  python3 check_parts_doc.py --name "The Velour" [--name NewOutfit_Velour_Pink]
  python3 check_parts_doc.py --selftest
  --json 输出结构化结果（dsh_task.js 自动查档用）

退出码（多个查询取最不完整的一态）：
  0  = 有图鉴（含本素体）
  10 = 有图鉴（缺本素体）
  20 = 只有清单和图
  30 = 都没有
  2  = 脚本自身出错（参数、环境）

相关：开发工具/通用工具/dsh_task.js（派工前自动跑本脚本并把结果追加到任务书末尾）
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
WS = HERE.parents[3]                       # 仓库根
PKG = WS / '开发工具' / '素材包说明'
sys.path.insert(0, str(HERE.parents[1]))
import kit_env  # noqa: E402  素材库根＝kit.env 的 VRC_ASSET_ROOT（可选；不设则只查仓库内的素材包说明）

_ASSET_ROOT = kit_env.get('VRC_ASSET_ROOT')
VRC = Path(_ASSET_ROOT).expanduser() if _ASSET_ROOT else None

# 四态与退出码（顺序＝完整度）
STATE_EXIT = {
    '有图鉴（含本素体）': 0,
    '有图鉴（缺本素体）': 10,
    '只有清单和图': 20,
    '都没有': 30,
}


def read_text(p):
    try:
        return p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def rel(p):
    try:
        return str(Path(p).relative_to(WS)).replace(os.sep, '/')
    except ValueError:
        return str(p)


def scan_products():
    """扫 开发工具/素材包说明/ 下的商品目录（图鉴/清单/图 三件套的实际位置）。"""
    out = []
    if not PKG.is_dir():
        return out
    for name in sorted(os.listdir(PKG)):
        d = PKG / name
        if not d.is_dir():
            continue
        doc, man, imgs = d / '部件图鉴.md', d / '部件清单.json', d / '部件图'
        out.append({
            'dir': d,
            'name': name,
            'doc': doc,
            'manifest': man,
            'images': imgs,
            'doc_text': read_text(doc) if doc.is_file() else '',
            'manifest_text': read_text(man) if man.is_file() else '',
        })
    return out


def vrc_dirs(item):
    """找 <素材库>/*-<商品号>；目录名可能含方括号/emoji，不能用 glob。"""
    if VRC is None:
        return []
    try:
        names = os.listdir(VRC)
    except OSError:
        return []
    return [str(VRC / n) for n in names if n.endswith('-' + item)]


def match_products(products, kind, query):
    hits = []
    for p in products:
        if kind == 'item':
            in_doc = query in p['doc_text']
            in_man = query in p['manifest_text']
            in_name = query in p['name']
        else:  # name：目录名 / 商品名 / 厂商预制件名 / 场景根名都算
            in_doc = (query in p['doc_text']) or (query == p['name'])
            in_man = (query in p['manifest_text']) or (query == p['name'])
            in_name = query == p['name']
        if in_doc or in_man or in_name:
            hits.append(p)
    return hits


def resolve(kind, query, avatar, products):
    hits = match_products(products, kind, query)
    docs = [rel(p['doc']) for p in hits if p['doc'].is_file()]
    manifests = [rel(p['manifest']) for p in hits if p['manifest'].is_file()]
    images = [rel(p['images']) for p in hits if p['images'].is_dir()]
    prods = [rel(p['dir']) for p in hits]
    sources = vrc_dirs(query) if kind == 'item' else []

    if docs:
        if avatar:
            mentioned = any(avatar in p['doc_text'] for p in hits if p['doc'].is_file())
            state = '有图鉴（含本素体）' if mentioned else '有图鉴（缺本素体）'
        else:
            state = '有图鉴（含本素体）'  # 没给素体名，无从判缺
    elif manifests or images:
        state = '只有清单和图'
    else:
        state = '都没有'

    return {
        'query': query,
        'kind': kind,
        'state': state,
        'exit_code': STATE_EXIT[state],
        'avatar': avatar,
        'products': prods,
        'docs': docs,
        'manifests': manifests,
        'images': images,
        'source_dirs': sources,
    }


def fmt(r):
    lines = ['【%s】%s' % (r['query'], r['state'])]
    for p in r['products']:
        lines.append('  商品目录: ' + p)
    for d in r['docs']:
        lines.append('  图鉴    : ' + d)
    for m in r['manifests']:
        lines.append('  部件清单: ' + m)
    for i in r['images']:
        lines.append('  部件图  : ' + i + '/')
    for s in r['source_dirs']:
        lines.append('  素材源  : ' + s)
    if not (r['products'] or r['docs'] or r['source_dirs']):
        lines.append('  （仓库与素材库 VRC_ASSET_ROOT 都没有命中路径）')
    return '\n'.join(lines)


def do_selftest():
    products = scan_products()
    ok = True

    # 正例需要一个本机素材库里「有清单和图、无图鉴」的商品号：用环境变量 PARTS_SELFTEST_ITEM 指定，没配就跳过
    item = os.environ.get('PARTS_SELFTEST_ITEM', '').strip()
    if not item:
        print('SKIP: 正例（未设 PARTS_SELFTEST_ITEM）')
    else:
        r1 = resolve('item', item, None, products)
        if r1['state'] == '只有清单和图' and r1['exit_code'] == 20 and r1['manifests'] and r1['images']:
            print('PASS: %s → 只有清单和图，清单与图都在' % item)
        else:
            ok = False
            print('FAIL: %s 期望 只有清单和图/20 且清单、图都在，实际 %s/%s manifests=%s images=%s'
                  % (item, r1['state'], r1['exit_code'], r1['manifests'], r1['images']))

    r2 = resolve('item', '99999999', None, products)
    if r2['state'] == '都没有' and r2['exit_code'] == 30:
        print('PASS: 99999999（不存在的商品号）→ 都没有')
    else:
        ok = False
        print('FAIL: 99999999 期望 都没有/30，实际 %s/%s' % (r2['state'], r2['exit_code']))

    if ok:
        print('ALL PASS')
        return 0
    return 1


def main():
    ap = argparse.ArgumentParser(description='部件图鉴查档（四态）')
    ap.add_argument('--item', action='append', nargs='+', metavar='商品号',
                    help='Booth 商品号，可多个（空格或重复 --item）')
    ap.add_argument('--name', action='append', nargs='+', metavar='名字',
                    help='目录名 / 预制件名 / 场景根名，可多个')
    ap.add_argument('--avatar', default=None, help='素体名，用于判「含/缺本素体」')
    ap.add_argument('--json', action='store_true', help='输出结构化 JSON')
    ap.add_argument('--selftest', action='store_true', help='用当前仓库真实数据自检')
    args = ap.parse_args()

    if args.selftest:
        return do_selftest()

    items = [x for grp in (args.item or []) for x in grp]
    names = [x for grp in (args.name or []) for x in grp]
    if not items and not names:
        ap.error('至少给一个 --item 或 --name（或 --selftest）')

    products = scan_products()
    results = [resolve('item', q, args.avatar, products) for q in items]
    results += [resolve('name', q, args.avatar, products) for q in names]
    code = max(r['exit_code'] for r in results)

    if args.json:
        print(json.dumps({'avatar': args.avatar, 'results': results, 'exit_code': code},
                         ensure_ascii=False, indent=2))
    else:
        print('\n'.join(fmt(r) for r in results))
    return code


if __name__ == '__main__':
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(2)
