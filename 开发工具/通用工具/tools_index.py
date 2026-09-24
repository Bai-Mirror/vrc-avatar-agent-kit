#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关
相关素材：无
工具链　：Python 3（离线，只用标准库）
可复用性：★★★ 换个单子直接能用
用途　　：扫描 `开发工具/通用工具/` 下的脚本，把文件头五字段里的「用途 / 可复用性」抽成按目录分组的 markdown 表，分页写进 `开发工具/SOP/00_总表/工具索引/`、导航写进 `工具索引.md` 的自动段；`--check` 列出缺「用途」的文件。

为什么要脚本生成：
  手写的 `工具索引.md` 只点名了 16 个顶层工具，目录里有一百多个脚本 ——
  手写索引必然随新增脚本漂移。文件头是唯一的「用途」真相源，索引从它生成才不会再欠账。

扫描与排除
----------
  · 扫 `通用工具/**/*.{py,js,cs,sh}`（`git-hooks/pre-commit` 无扩展名，不扫）。
  · 排除 `__pycache__/`、`MeteorLens/_trial/`、`审查/replay/`、`agy_panel_samples/`。
  · 只读文件头前 60 行；`.py` 的模块 docstring、`.js/.cs` 的 `/** */` 或 `//`、
    `.sh` 的 `#` 都认（见 `clean_line`）。

字段与判定
----------
  认 `适用素体 / 相关素材 / 工具链 / 可复用性 / 用途` 五字段，行内可为 `：` 或 `:`。
  `--check` 只看「用途」：**没有用途字段的文件一律判缺**，列出来并以退出码 1 结束；
  全齐退出码 0。`--write` 才写索引，默认把生成的 markdown 打到 stdout。
  `--check` 同时查「shebang 不在第 1 行」（2026-09-25：有人手工把用途注释插到
  dsh_usage.js 第 1 行，`#!` 被挤到第 2 行，`node --check` 直接报错）。补用途字段时
  必须写进 shebang 之后的已有文件头，本脚本只读脚本、从不改脚本。

  例外（TASK_PROTECTED）：任务书《_长程任务_20260918/派工/W1_工具索引脚本化与文件头.md》
  的「不许碰」一节明示下列 5 个脚本已有完整文件头、禁改；其中 `dsh_usage.js` 的头部用
  「<文件名> —— 说明」的标题式写法而非五字段，故一并不参与缺「用途」判定（禁改优先），
  索引里的用途回退到它的标题行。

用法
----
    python3 开发工具/通用工具/tools_index.py            # 只打印，不落盘
    python3 开发工具/通用工具/tools_index.py --check     # 缺用途退出 1，全齐退出 0
    python3 开发工具/通用工具/tools_index.py --write     # 写 工具索引/<分页>.md，并把分页导航写进 工具索引.md 的自动段
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(os.path.dirname(HERE))          # 工作区根
INDEX_MD = os.path.join(HERE, os.pardir, 'SOP', '00_总表', '工具索引.md')
INDEX_MD = os.path.abspath(INDEX_MD)

EXTS = ('.py', '.js', '.cs', '.sh')
EXCLUDE = ('__pycache__', 'MeteorLens/_trial', '审查/replay', 'agy_panel_samples')
HEADER_LINES = 60

BEGIN = '<!-- 自动索引:BEGIN -->'
END = '<!-- 自动索引:END -->'
SECTION_TITLE = '## 自动索引（tools_index.py 生成，勿手改）'

# 分页（2026-09-25）：逐文件表写到 00_总表/工具索引/<分页>.md，主页标记之间只放分页导航。
# 取舍：SOP 单页 ≤10 KB，逐文件表全放主页有 29 KB；按目录分页后顶层一百来行仍超，
# 顶层再按扩展名分三页；某页仍超 PAGE_LIMIT 就按排序顺序切成 <分页>-1/-2…（加脚本后页界会挪，
# 但整页由脚本覆盖，不会丢手写内容）。子页首行带 SUB_MARK，只有带它的旧子页才会被清掉。
SUBDIR = os.path.join(os.path.dirname(INDEX_MD), '工具索引')
PAGE_LIMIT = 9 * 1024          # 表体上限；留约 1 KB 给页头，整页 ≤10 KB
SUB_MARK = '<!-- tools_index.py 自动生成：整页覆盖，勿手改 -->'
TOP_EXT_PAGE = {'.cs': '顶层-Unity脚本', '.py': '顶层-Python',
                '.js': '顶层-Node与Shell', '.sh': '顶层-Node与Shell'}

# 任务书「不许碰」的 5 个脚本：已有完整文件头，不参与缺「用途」判定。
TASK_PROTECTED = {
    'dsh_task.js', 'dsh_session.js', 'dsh_usage.js',
    'agy_mcp_server.js', 'ws_git.py',
}

FIELD_LABELS = ('适用素体', '相关素材', '工具链', '可复用性', '用途')


def clean_line(line):
    """把一行注释/字符串的装饰符去掉，返回纯文本。"""
    s = line.strip()
    if s.startswith('/*'):
        s = s.lstrip('/*').strip()
    if s.startswith('*'):
        s = s.lstrip('*').strip()
    if s.startswith('//'):
        s = s.lstrip('/').strip()
    if s.startswith('#'):
        s = s.lstrip('#').strip()
    s = s.strip('"').strip("'").strip()
    return s


def collect_files():
    """返回相对 HERE 的脚本路径（/ 分隔，已排序）。"""
    out = []
    for dp, dns, fns in os.walk(HERE):
        dns[:] = [d for d in dns if d != '__pycache__']
        for fn in fns:
            if not fn.endswith(EXTS):
                continue
            rel = os.path.relpath(os.path.join(dp, fn), HERE).replace(os.sep, '/')
            if any(part in rel for part in EXCLUDE):
                continue
            out.append(rel)
    return sorted(out)


def parse_header(rel):
    """读前 60 行，返回 {字段: 值}。"""
    path = os.path.join(HERE, rel)
    with open(path, encoding='utf-8', errors='replace') as fh:
        lines = [next(fh, '') for _ in range(HEADER_LINES)]
    fields = {}
    cleaned = []
    for raw in lines:
        c = clean_line(raw)
        cleaned.append(c)
        for label in FIELD_LABELS:
            m = re.match(r'^' + re.escape(label) + r'[\s\u3000]*[:：][\s\u3000]*(.*)$', c)
            if m and label not in fields:
                fields[label] = m.group(1).strip()
    return fields, cleaned


def fallback_purpose(rel, cleaned):
    """没有「用途」字段时，从标题行（<文件名> —— 说明）或首行兜底。"""
    base = os.path.basename(rel)
    for c in cleaned:
        if base in c and ('——' in c or '—' in c):
            return c.split('——', 1)[-1].split('—', 1)[-1].strip()
    for c in cleaned:
        if not c:
            continue
        if any(c.startswith(lab) for lab in FIELD_LABELS):
            continue
        if c.startswith('!') or c.startswith('/'):
            continue
        return c
    return ''


def one_line(text, limit=140):
    text = re.sub(r'\s+', ' ', text or '').strip()
    if len(text) > limit:
        text = text[:limit - 1].rstrip() + '…'
    return text.replace('|', '\\|')


def page_key(rel):
    """分页名：顶层按扩展名；审查/<子目录>/… 各自一页；其余按第一级目录。"""
    parts = rel.split('/')
    if len(parts) == 1:
        return TOP_EXT_PAGE.get(os.path.splitext(rel)[1], '顶层-其它')
    if parts[0] == '审查' and len(parts) > 2:
        return '审查-' + parts[1]
    return parts[0]


def build_pages(records):
    """返回 [(分页名, 覆盖目录列表, 文件数, 表体)]，按分页名排序；超 PAGE_LIMIT 的切成 -1/-2…。"""
    keyed = {}
    for rec in records:
        keyed.setdefault(page_key(rec[0]), []).append(rec)
    pages = []
    for key in sorted(keyed, key=lambda k: (not k.startswith('顶层'), k)):
        recs = sorted(keyed[key], key=lambda r: (os.path.dirname(r[0]), r[0]))
        chunks, cur = [], []
        for rec in recs:
            if cur and len(build_body(cur + [rec]).encode('utf-8')) > PAGE_LIMIT:
                chunks.append(cur)
                cur = []
            cur.append(rec)
        chunks.append(cur)
        for i, chunk in enumerate(chunks, 1):
            name = key if len(chunks) == 1 else '{}-{}'.format(key, i)
            dirs = sorted({os.path.dirname(r[0]) for r in chunk})
            pages.append((name, dirs, len(chunk), build_body(chunk)))
    return pages


def build_body(records):
    groups = {}
    for rel, fields in records:
        group = os.path.dirname(rel)
        groups.setdefault(group, []).append((rel, fields))
    lines = []
    for group in sorted(groups, key=lambda g: ('' if g else '', g)):
        title = '通用工具/' + group if group else '通用工具（顶层）'
        lines.append('### ' + title)
        lines.append('')
        lines.append('| 路径 | 用途 | 可复用性 |')
        lines.append('|---|---|---|')
        for rel, fields in sorted(groups[group]):
            purpose = fields.get('用途') or fallback_purpose(rel, fields['__cleaned'])
            rating = fields.get('可复用性') or '（未标）'
            lines.append('| `通用工具/{}` | {} | {} |'.format(
                rel, one_line(purpose), one_line(rating, 80)))
        lines.append('')
    return '\n'.join(lines).rstrip('\n')


def shebang_misplaced(rel):
    """shebang 出现在第 2 行及以后（前 5 行内）即判错位：解释器只认第 1 行。"""
    with open(os.path.join(HERE, rel), encoding='utf-8', errors='replace') as fh:
        head = [next(fh, '') for _ in range(5)]
    return (not head[0].startswith('#!')) and any(l.startswith('#!') for l in head[1:])


def load_records():
    records = []
    missing = []
    for rel in collect_files():
        fields, cleaned = parse_header(rel)
        fields['__cleaned'] = cleaned
        records.append((rel, fields))
        if '用途' not in fields and rel not in TASK_PROTECTED:
            missing.append(rel)
    return records, missing


def page_text(name, n, body):
    return ('> ← [工具索引](../工具索引.md) {mark}\n\n'
            '# 工具索引 · {name}（{n} 个文件）\n\n'
            '由 `python3 开发工具/通用工具/tools_index.py --write` 从各脚本文件头的「用途 / 可复用性」生成，'
            '整页覆盖；要改内容请改脚本文件头。路径相对 `开发工具/`。\n\n'
            '{body}\n').format(mark=SUB_MARK, name=name, n=n, body=body)


def nav_body(pages):
    lines = ['逐文件表按目录分页（各页 ≤10 KB）：', '',
             '| 分页 | 覆盖目录 | 文件数 |', '|---|---|---|']
    for name, dirs, n, _body in pages:
        cover = '、'.join('`通用工具/{}`'.format(d) if d else '`通用工具/`（顶层）' for d in dirs)
        lines.append('| [{0}](工具索引/{0}.md) | {1} | {2} |'.format(name, cover, n))
    return '\n'.join(lines)


def write_pages(pages):
    """写子页并清掉不再生成的旧子页（只清首行带 SUB_MARK 的）；返回清掉的文件名。"""
    os.makedirs(SUBDIR, exist_ok=True)
    want = set()
    for name, _dirs, n, body in pages:
        fn = name + '.md'
        want.add(fn)
        with open(os.path.join(SUBDIR, fn), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(page_text(name, n, body))
    removed = []
    for fn in sorted(os.listdir(SUBDIR)):
        if fn in want or not fn.endswith('.md'):
            continue
        path = os.path.join(SUBDIR, fn)
        with open(path, encoding='utf-8', errors='replace') as fh:
            first = fh.readline()
        if SUB_MARK in first:
            os.remove(path)
            removed.append(fn)
    return removed


def write_index(body):
    with open(INDEX_MD, encoding='utf-8') as fh:
        text = fh.read()
    section = SECTION_TITLE + '\n\n' + BEGIN + '\n' + body + '\n' + END
    pattern = re.compile(re.escape(BEGIN) + r'.*?' + re.escape(END), re.S)
    if pattern.search(text):
        # 手写部分一字不动：只替换两个标记之间的内容
        new_text = pattern.sub(lambda _m: BEGIN + '\n' + body + '\n' + END, text)
    else:
        new_text = text.rstrip('\n') + '\n\n' + section + '\n'
    with open(INDEX_MD, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(new_text)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true',
                    help='列出缺「用途」的文件；有缺退出码 1，全齐退出码 0')
    ap.add_argument('--write', action='store_true',
                    help='把逐文件表写进 工具索引/<分页>.md、分页导航写进 工具索引.md 的自动段（默认只打印）')
    args = ap.parse_args()

    records, missing = load_records()
    body = build_body(records)

    if args.check:
        bad_shebang = [rel for rel, _f in records if shebang_misplaced(rel)]
        if bad_shebang:
            print('shebang 不在第 1 行的文件 {} 个（会导致无法执行）：'.format(len(bad_shebang)))
            for rel in bad_shebang:
                print('  ' + os.path.join('通用工具', rel).replace(os.sep, '/'))
        if missing:
            print('缺「用途」字段的文件 {} 个：'.format(len(missing)))
            for rel in missing:
                print('  ' + os.path.join('通用工具', rel).replace(os.sep, '/'))
            return 1
        if bad_shebang:
            return 1
        n = len(records)
        print('✓ {} 个脚本都有「用途」字段（缺 0 个）'.format(n))
        print('  说明：{} 个任务书「不许碰」脚本按已有完整文件头处理。'.format(
            len(TASK_PROTECTED)))
        return 0

    if args.write:
        pages = build_pages(records)
        removed = write_pages(pages)
        write_index(nav_body(pages))
        print('已写入 {}：分页导航 {} 页、逐文件 {} 条（扫描 {} 个文件）；子页目录 {}{}'.format(
            os.path.relpath(INDEX_MD, WS), len(pages), sum(p[2] for p in pages), len(records),
            os.path.relpath(SUBDIR, WS),
            '；清掉旧子页 ' + '、'.join(removed) if removed else ''))
        return 0

    print(body)
    return 0


if __name__ == '__main__':
    sys.exit(main())
