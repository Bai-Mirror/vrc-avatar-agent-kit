#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收缩键宿主静态扫描（T-33 的离线搭档，2026-09-20 · 任务源：用户报工程B 43% 塌脚踝）
【项目沉淀】通用工具
适用素体：无关
相关素材：工程场景/预制体的 MA ShapeChanger
工具链　：Python 3 + PyYAML（离线）
可复用性：★★ 审查工具链的一环
用途　　：收缩键宿主静态扫描：每个 MA ShapeChanger 挂在谁身上、写了哪些键，按宿主件名与影响身体段初筛可疑。


回答一个不用开 Unity 就能回答的问题：**每个 MA ShapeChanger 挂在谁身上、写了哪些键**，
并按「宿主件名 vs 键影响的身体段」给出可疑清单。

它**不是**几何判据（那是 Play 里的 T-33 `shrink_cover`），只做名字层面的初筛：
初筛命中不等于有缺陷，但凡是真缺陷（工程B 43% 的 `Ankle` 挂在鞋上）都会出现在清单里。

⚠ **已知限制（2026-09-20 实测）**：宿主名靠 YAML 回源解析，遇到「预制体变体套预制体变体」
（工程B的 `08_WhitePink_Milfy_MA` → `01_Black_Milfy_MA` → …）时解析不出来，本项会打 `?`。
名字全是 `?` 时**不要**信这里的初筛结论，改用下面的 Unity 侧枚举（几秒钟，结果权威）：

    // execute_code，编辑模式即可（别在 Play 里跑，MA 组件那时已被构建消耗）
    foreach (var mb in Resources.FindObjectsOfTypeAll<MonoBehaviour>()) {
      if (mb == null || mb.gameObject.scene != UnityEngine.SceneManagement.SceneManager.GetActiveScene()) continue;
      if (mb.GetType().Name != "ModularAvatarShapeChanger") continue;
      Debug.Log(路径(mb.transform) + " -> " + UnityEditor.EditorJsonUtility.ToJson(mb));
    }

几何判据是 Play 里的 T-33 `shrink_cover`，本脚本只是它的离线粗筛。

用法：
    python3 shrink_host_scan.py <工程目录> [<工程目录>…]
    python3 shrink_host_scan.py --all          # 扫工作区里所有工程
"""
import os, re, sys, json, collections

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

# 键名 → 身体段。段名只用于和宿主件名对照，不参与几何判断。
SEG_RULES = [
    (re.compile(r'(?i)^ankle', ), 'ankle'),
    (re.compile(r'(?i)^(foot|toe)(_[lr])?$'), 'foot'),
    (re.compile(r'(?i)^foot_(heels|highheels)'), 'posture'),
    (re.compile(r'(?i)^(knee|lower_?leg|upper_?leg|leg)'), 'leg'),
    (re.compile(r'(?i)^(hand|wrist|lower_?arm|elbow|upper_?arm|shoulder)'), 'arm'),
    (re.compile(r'(?i)^(chest|spine|waist|bust|breast)'), 'torso'),
]
# 宿主件名 → 它「盖得住」的段。低帮鞋盖不到脚踝，所以 shoe 不含 ankle（这正是工程B 43% 的坑）。
HOST_RULES = [
    (re.compile(r'(?i)(boots?|長靴|长靴)'), {'ankle', 'foot', 'posture', 'leg'}),
    (re.compile(r'(?i)(shoe|pumps?|sandal|heel|sneaker|slipper)'), {'foot', 'posture'}),
    (re.compile(r'(?i)(sock|stocking|tights|legwarmer|garter|レッグ)'), {'ankle', 'foot', 'leg'}),
    (re.compile(r'(?i)(pants?|skirt|shorts?|trouser)'), {'leg', 'torso'}),
    (re.compile(r'(?i)(glove|cuff|sleeve|armcover)'), {'arm'}),
    (re.compile(r'(?i)(coat|jacket|tops?|shirt|dress|onepiece|bra|underwear|corset|cape)'), {'torso', 'arm'}),
]

def seg_of(key):
    for rx, seg in SEG_RULES:
        if rx.match(key):
            return seg
    return None

def covers_of(host):
    for rx, segs in HOST_RULES:
        if rx.search(host):
            return segs
    return None          # 名字认不出来 → 不初筛，只列出来给人看

GUID_INDEX = {}

def build_guid_index(proj):
    """guid → 资产路径。预制体实例上的组件要靠它回源找宿主名。"""
    idx = {}
    for root, dirs, files in os.walk(os.path.join(proj, 'Assets')):
        for f in files:
            if not f.endswith('.meta'):
                continue
            mp = os.path.join(root, f)
            try:
                with open(mp, encoding='utf-8', errors='replace') as fh:
                    for _ in range(4):
                        line = fh.readline()
                        if line.startswith('guid: '):
                            idx[line[6:].strip()] = mp[:-5]
                            break
            except OSError:
                pass
    return idx

_PREFAB_NAMES = {}
_PREFAB_SRC = {}
_RESOLVED = {}

def prefab_names(path):
    """预制体文件里 fileID → GameObject 名（带缓存）。"""
    if path in _PREFAB_NAMES:
        return _PREFAB_NAMES[path]
    names = {}
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        txt = ''
    docs = re.split(r'^--- !u!(\d+) &(\d+).*$', txt, flags=re.M)
    for i in range(1, len(docs) - 2, 3):
        if docs[i] == '1':
            m = re.search(r'^  m_Name: (.*)$', docs[i + 2], re.M)
            if m:
                names[docs[i + 1]] = m.group(1).strip()
    _PREFAB_NAMES[path] = names
    return names


def resolve_prefab_name(guid, fid, depth=0, seen=None):
    """在 guid 指向的预制体里找 fileID 的 GameObject 名；找不到就沿 m_SourcePrefab 往基座预制体追。
    预制体变体／嵌套预制体里，实例上的 fileID 属于**基座**那一份，只查第一层会全查不到。"""
    if depth == 0 and (guid, fid) in _RESOLVED:
        return _RESOLVED[(guid, fid)]
    if depth > 6:
        return None
    seen = seen if seen is not None else set()
    if guid in seen:
        return None
    seen.add(guid)
    path = GUID_INDEX.get(guid)
    if not path or not os.path.exists(path):
        return None
    nm = prefab_names(path).get(fid)
    if nm:
        if depth == 0:
            _RESOLVED[(guid, fid)] = nm
        return nm
    if path not in _PREFAB_SRC:
        try:
            txt = open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            txt = ''
        _PREFAB_SRC[path] = sorted(set(re.findall(r'm_SourcePrefab: \{fileID: \d+, guid: ([0-9a-f]+)', txt)))
    for g in _PREFAB_SRC[path]:
        nm = resolve_prefab_name(g, fid, depth + 1, seen)
        if nm:
            if depth == 0:
                _RESOLVED[(guid, fid)] = nm
            return nm
    if depth == 0:
        _RESOLVED[(guid, fid)] = None
    return None


def parse_unity_yaml(path):
    """极简 Unity YAML 扫描：拿 GameObject 名、Transform 父子、以及 ShapeChanger 的 m_shapes。
    宿主是预制体实例上的 stripped GameObject 时，按 m_CorrespondingSourceObject 的 guid+fileID 回源取名。"""
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return {}, {}, []
    docs = re.split(r'^--- !u!(\d+) &(\d+).*$', txt, flags=re.M)
    names, parent, scs = {}, {}, []
    # docs = [前言, cls, fid, body, cls, fid, body, …]
    for i in range(1, len(docs) - 2, 3):
        cls, fid, body = docs[i], docs[i + 1], docs[i + 2]
        if cls == '1':                                   # GameObject（含 stripped）
            m = re.search(r'^  m_Name: (.*)$', body, re.M)
            if m:
                names[fid] = m.group(1).strip()
            else:                                        # stripped：回源到预制体里取名
                src = re.search(r'm_CorrespondingSourceObject: \{fileID: (\d+), guid: ([0-9a-f]+)', body)
                if src:
                    names[fid] = resolve_prefab_name(src.group(2), src.group(1)) or '?'
        elif cls == '4':                                 # Transform
            go = re.search(r'm_GameObject: \{fileID: (\d+)\}', body)
            fa = re.search(r'm_Father: \{fileID: (\d+)\}', body)
            if go:
                parent[fid] = (go.group(1), fa.group(1) if fa else '0')
        elif cls == '114' and 'ShapeName' in body:       # MonoBehaviour（ShapeChanger）
            go = re.search(r'm_GameObject: \{fileID: (\d+)\}', body)
            keys = []
            for mm in re.finditer(r'ShapeName: (.*?)\n\s*ChangeType: (\d+)', body):
                keys.append((mm.group(1).strip(), int(mm.group(2))))
            if go and keys:
                scs.append((go.group(1), keys))
    return names, parent, scs

def scan_project(proj):
    global GUID_INDEX
    GUID_INDEX = build_guid_index(proj)
    rows = []
    for root, dirs, files in os.walk(os.path.join(proj, 'Assets')):
        dirs[:] = [d for d in dirs if d not in ('AvatarAudit',)]
        for f in files:
            if not f.endswith(('.unity', '.prefab')):
                continue
            p = os.path.join(root, f)
            names, parent, scs = parse_unity_yaml(p)
            for go_fid, keys in scs:
                host = names.get(go_fid, '?')
                rows.append({'file': os.path.relpath(p, proj), 'host': host,
                             'keys': [{'k': k, 'type': 'Del' if t == 0 else 'Set'} for k, t in keys]})
    return rows

def main(argv):
    projs = argv[1:]
    if projs == ['--all']:
        projs = [os.path.join(WS, d) for d in sorted(os.listdir(WS))
                 if os.path.isdir(os.path.join(WS, d, 'Assets'))]
    if not projs:
        print(__doc__); return 2
    total_sus = 0
    for proj in projs:
        rows = scan_project(proj)
        if not rows:
            continue
        print('=' * 72)
        print(os.path.basename(os.path.abspath(proj)), '：ShapeChanger', len(rows), '个')
        for r in rows:
            segs = collections.Counter(s for s in (seg_of(x['k']) for x in r['keys']) if s)
            cov = covers_of(r['host'])
            sus = sorted(s for s in segs if cov is not None and s not in cov)
            mark = '  ⚠ 可疑：宿主盖不到 ' + '/'.join(sus) if sus else ''
            if sus:
                total_sus += 1
            print('  %-26s %-48s %s%s' % (
                r['host'],
                ','.join(x['k'] + ('(Del)' if x['type'] == 'Del' else '') for x in r['keys'])[:48],
                '段=' + '+'.join(sorted(segs)) if segs else '段=?', mark))
    print('=' * 72)
    print('初筛可疑：%d 条。初筛只看名字，命中要用 Play 里的 T-33 shrink_cover 做几何复核。' % total_sus)
    print('⚠ 宿主名是 `?` 的行说明 YAML 回源没解析出来（预制体变体套变体），那些行没有参与初筛；'
          '这种工程改用文件头里的 Unity 侧枚举。')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
