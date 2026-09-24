#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════
# 【通用工具】部件图鉴 · 叠字（PIL）
#
# 【项目沉淀】通用工具
# 适用素体：无关
# 相关素材：PartAtlasCapture.cs 写出的清单 JSON + png
# 工具链　：Python 3 + Pillow（离线）
# 可复用性：★★ 清单字段变了要跟着改
# 用途　　：部件图鉴 · 叠字：把清单 JSON 里的中文行印到 png 左上角，供视觉子代理读字而不是认图。
#
#
# 为什么在 Unity 外面做：Unity 编辑器里没有现成的中文字形光栅化入口，
#   而在图里印字这件事 PIL 一行就行。依据 `SOP/01_自动化执行与并行/DSH模型与视觉能力.md`
#   第二节「把数值印进图里让它读，别让它测」——视觉子代理读印在图上的字符 100% 准，
#   自己数三角形/认材质会错。
#
# 输入：PartAtlasCapture.cs 写出的清单 JSON
#   {"font_size":22, "images":[{"file":"/abs/x.png","lines":["行1","行2"]}, ...]}
# 输出：原地改写这些 png（左上角加深色半透明底 + 中文叠字）
#
# 用法：python3 part_atlas_overlay.py <清单.json>
#   退出码 0 = 全部叠字成功；非 0 = 有失败，stderr 写明。
# ══════════════════════════════════════════════════════════════════
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))          # 开发工具/通用工具
from cjk_font import cjk_font                      # noqa: E402

from PIL import Image, ImageDraw                    # noqa: E402

MARGIN = 10
PAD = 8
LINE_SPACING = 4
MAX_CHARS = 56                                     # 一行最多几个字符，超了折行


def wrap(s, n):
    """按字符数折行（中文/日文按 1 个字符算；mats 列表常超宽）。"""
    if len(s) <= n:
        return [s]
    out = []
    cur = ""
    for ch in s:
        cur += ch
        if len(cur) >= n and ch in " ,":
            out.append(cur.rstrip())
            cur = ""
    if cur:
        out.append(cur)
    return out


def main():
    if len(sys.argv) != 2:
        print("用法: part_atlas_overlay.py <清单.json>", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8") as f:
        spec = json.load(f)
    size = int(spec.get("font_size", 22))
    font = cjk_font(size)
    bad = 0
    total = 0
    for item in spec.get("images", []):
        path = item["file"]
        lines = []
        for ln in item.get("lines", []):
            lines.extend(wrap(ln, MAX_CHARS))
        total += 1
        if not os.path.exists(path):
            print("缺文件: " + path, file=sys.stderr)
            bad += 1
            continue
        try:
            im = Image.open(path).convert("RGB")
            d = ImageDraw.Draw(im, "RGBA")
            # 先量出文字块尺寸，再铺底
            w = 0
            h = 0
            for ln in lines:
                bb = d.textbbox((0, 0), ln, font=font)
                w = max(w, bb[2] - bb[0])
                h += (bb[3] - bb[1]) + LINE_SPACING
            bw = min(im.width, w + 2 * PAD + 2 * MARGIN)
            bh = min(im.height, h + 2 * PAD)
            d.rectangle([MARGIN, MARGIN, MARGIN + bw, MARGIN + bh],
                        fill=(12, 12, 18, 190))
            y = MARGIN + PAD
            for ln in lines:
                bb = d.textbbox((0, 0), ln, font=font)
                lh = bb[3] - bb[1]
                # 描边提升在浅色背景上的可读性
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    d.text((MARGIN + PAD + dx, y - bb[1] + dy), ln, font=font,
                           fill=(0, 0, 0, 220))
                d.text((MARGIN + PAD, y - bb[1]), ln, font=font,
                       fill=(238, 238, 244, 255))
                y += lh + LINE_SPACING
            im.save(path)
        except Exception as e:                       # noqa: BLE001
            print("叠字失败 %s: %s" % (path, e), file=sys.stderr)
            bad += 1
    print("overlay: %d/%d 图成功" % (total - bad, total))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
