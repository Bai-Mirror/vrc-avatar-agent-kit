"""标注图里写中文用这个，别用 ImageFont.load_default()——它没有 CJK 字形，出方框。
【项目沉淀】通用工具
适用素体：无关
相关素材：无
工具链　：Python 3 + Pillow
可复用性：★★★ 换个单子直接能用
用途　　：标注图里写中文用的字体加载器，避开 ImageFont.load_default() 无 CJK 字形出方框。


    from cjk_font import cjk_font
    d.text((8, 8), "电光青", font=cjk_font(20), fill=(235,235,240))

本机实测可用（fc-list :lang=zh）：
  /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc   ← 首选，SC 在 index 2
  ~/.local/share/fonts/sarasa/SarasaMonoSC-Regular.ttf
"""
import os
import sys
from PIL import ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_env  # noqa: E402  kit.env 的 CJK_FONT 可指定首选字体（.ttc 可写 路径:index）

_CANDIDATES = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),   # Noto Sans CJK SC
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc", 2),
    ("~/.local/share/fonts/sarasa/SarasaMonoSC-Regular.ttf", 0),
    ("~/.local/share/fonts/sarasa/SarasaUiSC-Regular.ttf", 0),
    ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 2),
]


def _candidates():
    out = []
    user = kit_env.get("CJK_FONT")
    if user:
        p, _, i = user.rpartition(":") if user.rsplit(":", 1)[-1].isdigit() else (user, "", "0")
        out.append((p, int(i)))
    return out + _CANDIDATES


def cjk_font(size=20):
    """返回一个能画中文的 PIL 字体；全都找不到就抛错，不静默退回方框。"""
    for path, idx in _candidates():
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            continue
        for i in (idx, 0):                     # .ttc 的 index 不对就退回 0
            try:
                f = ImageFont.truetype(path, size, index=i)
                if f.getbbox("电") != f.getbbox("□"):   # 确认不是渲成同一个方框
                    return f
            except Exception:
                pass
    raise RuntimeError("找不到能画中文的字体；先 fc-list :lang=zh 看装了什么，再在 kit.env 设 CJK_FONT")


if __name__ == "__main__":
    f = cjk_font(24)
    print("OK:", f.path if hasattr(f, "path") else f, "size bbox of 电光青 =", f.getbbox("电光青"))
