"""读取工作区根的 kit.env（KEY=VALUE），环境变量优先。
【项目沉淀】通用工具
用途　　：让脚本不写死本机路径。工作区根＝环境变量 VRC_WS，缺省按本文件位置推算（开发工具/通用工具/ 往上两级）。
用法　　：
    import kit_env
    ws = kit_env.WS                                  # pathlib.Path
    unity = kit_env.get('UNITY_BIN', '/opt/Unity')   # 环境变量 > kit.env > 缺省
只解析 `KEY=VALUE` 行（可带 export 前缀、可加引号），`#` 开头为注释；值里的 ~ 与 $VAR/${VAR} 会展开。不执行任何代码。
"""
import os
import re
from pathlib import Path

_LINE = re.compile(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$')

_WS_FROM_ENV = bool(os.environ.get('VRC_WS'))
WS = Path(os.environ.get('VRC_WS') or Path(__file__).resolve().parents[2]).expanduser()
_loaded = None


def _parse(path):
    out = {}
    try:
        text = Path(path).read_text(encoding='utf-8')
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
            v = v[1:-1]
        elif ' #' in v:
            v = v.split(' #', 1)[0].rstrip()
        out[k] = v
    return out


def load():
    """读 <WS>/kit.env，把环境里还没有的键写进 os.environ；返回 kit.env 的原始键值。可重复调用。"""
    global _loaded, WS
    if _loaded is None:
        _loaded = _parse(WS / 'kit.env')
        for k, v in _loaded.items():
            if v and k not in os.environ:            # 空值＝没设，不导出
                os.environ[k] = os.path.expanduser(os.path.expandvars(v))
        if not _WS_FROM_ENV and os.environ.get('VRC_WS'):   # kit.env 里写了 VRC_WS：工具仓库与工作区分开放
            WS = Path(os.environ['VRC_WS']).expanduser()
    return _loaded


def get(key, default=None):
    """环境变量 > kit.env > default；空串视为未设。"""
    load()
    v = os.environ.get(key)
    return v if v else default


def unity_data():
    """Unity 编辑器 Data 目录：UNITY_DATA > UNITY_BIN 同级的 Data > UNITY_EDITOR_ROOT/UNITY_VERSION/Editor/Data。"""
    d = get('UNITY_DATA')
    if d:
        return Path(d).expanduser()
    b = get('UNITY_BIN')
    if b:
        return Path(b).expanduser().parent / 'Data'
    root = get('UNITY_EDITOR_ROOT', str(Path.home() / 'Unity' / 'Hub' / 'Editor'))
    return Path(root).expanduser() / get('UNITY_VERSION', '2022.3.22f1') / 'Editor' / 'Data'


load()
