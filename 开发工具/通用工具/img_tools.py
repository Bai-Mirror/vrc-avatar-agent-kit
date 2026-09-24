# -*- coding: utf-8 -*-
"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无（overlay 子命令：任意稀疏 RGBA 叠加层贴图）
可复用性：★★★ 换个单子直接能用
用途　　：图像小工具合集（子命令）：sheet 联系表 / sheet-by-tag 按标签挑图拼表 / diff-crop 差异热区裁图 / overlay 叠加层 alpha-over 合成 / autocrop 按像素裁紧

2026-09-25 由 contact_sheet.py、sheet_by_tag.py、diff_crop.py、overlay_composite.py、autocrop.py
五个脚本合并（kit-prep 整理）。各子命令的参数、输出文字、退出码与原脚本一致，只是前面多一个子命令名：

    python img_tools.py sheet        输出.png --cols 4 --cell 420 图1.png 图2.png ...     （原 contact_sheet.py）
    python img_tools.py sheet        输出.png --cols 4 --list 清单.txt
    python img_tools.py sheet-by-tag <渲染目录> <输出.png> <视角> <前缀1> [前缀2 ...] [--cols N] [--cell N]  （原 sheet_by_tag.py）
    python img_tools.py diff-crop    <输出目录> <图1> <图2> [图3 ...] [--top 0.66] [--thr 0.06] [--long 1400]  （原 diff_crop.py）
    python img_tools.py overlay      <底图.png> <叠加层.png> --out <输出.png> [--alpha-thr 0]  （原 overlay_composite.py）
    python img_tools.py autocrop     输出目录 图1.png 图2.png ... | --glob "某目录/*_1样式.png" [--tol 12 --margin 0.06 --size 860]  （原 autocrop.py）

`python img_tools.py <子命令>` 不带参数打印该子命令的完整说明（为什么要它、判据、坑）。
可 import 的函数：sheet()（原 contact_sheet.sheet）、collect()（原 sheet_by_tag.collect）、
over()/load()（原 overlay_composite）、bg_color()/content_box()/crop_one()（原 autocrop）。
"""
import argparse
import glob as globmod
import io
import os
import re
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))


# ══════════════════════════════════════════════════════════════════
# sheet（原 contact_sheet.py）
# ══════════════════════════════════════════════════════════════════
SHEET_DOC = """
sheet：把一堆定妆照拼成带标题的联系表（contact sheet），一张图看完一整组

为什么要它：验收标准是「每件衣服 × 每个配饰 × 各开关组合全部截图」，
一组几十上百张。逐张看既慢又容易漏掉「这两张之间差在哪」。拼成一张网格图，
差异是并排的，异常一眼就跳出来。

用法：
    python img_tools.py sheet 输出.png --cols 4 --cell 420 图1.png 图2.png ...
    python img_tools.py sheet 输出.png --cols 4 --list 清单.txt

清单文件每行 `路径<TAB>标题`（标题可省，省了就用文件名）。
"""


def load_font(size):
    # 中文标题字体统一走 cjk_font，找不到直接抛错。
    # 原来这里是四条 Windows 路径（msyh/simhei/msyhbd）+ 一条本机不存在的 wqy，
    # 四条全落空 → 静默回退 ImageFont.load_default()，那个字体没有 CJK 字形，
    # 中文全渲成方框，而脚本不报错、日志一片 PASS。2026-09-21 作者拿到图才发现。
    sys.path.insert(0, HERE)
    from cjk_font import cjk_font
    return cjk_font(size)


def sheet(items, out, cols=4, cell=420, bar=30, pad=6, bg=(24, 24, 28), fg=(235, 235, 240)):
    """items: [(路径, 标题)]。等比缩放进 cell×cell，下面压一条标题带。"""
    font = load_font(max(11, bar - 12))
    rows = (len(items) + cols - 1) // cols
    W = cols * (cell + pad) + pad
    H = rows * (cell + bar + pad) + pad
    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    for n, (path, title) in enumerate(items):
        cx = pad + (n % cols) * (cell + pad)
        cy = pad + (n // cols) * (cell + bar + pad)
        try:
            im = Image.open(path).convert("RGB")
        except OSError as e:
            draw.text((cx + 6, cy + 6), "读不到:\n%s" % e, font=font, fill=(255, 90, 90))
            continue
        im.thumbnail((cell, cell), Image.LANCZOS)
        canvas.paste(im, (cx + (cell - im.width) // 2, cy + (cell - im.height) // 2))
        draw.text((cx + 4, cy + cell + 4), title[:52], font=font, fill=fg)

    canvas.save(out)
    return W, H, len(items)


def cmd_sheet(argv):
    # 参数手工解析（与原脚本一致）：--list 与散列图片可交错，拼表顺序＝命令行出现顺序；argparse 保不住这个顺序。
    if len(argv) < 2:
        print(SHEET_DOC)
        return 1
    out = argv[1]
    cols, cell = 4, 420
    items, i = [], 2
    while i < len(argv):
        a = argv[i]
        if a == "--cols":
            cols = int(argv[i + 1]); i += 2
        elif a == "--cell":
            cell = int(argv[i + 1]); i += 2
        elif a == "--list":
            for line in io.open(argv[i + 1], encoding="utf-8"):
                line = line.rstrip("\n")
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.split("\t", 1)
                items.append((parts[0], parts[1] if len(parts) > 1 else
                              os.path.splitext(os.path.basename(parts[0]))[0]))
            i += 2
        else:
            items.append((a, os.path.splitext(os.path.basename(a))[0]))
            i += 1
    if not items:
        print("没有输入图")
        return 1
    W, H, n = sheet(items, out, cols, cell)
    print("%s  %dx%d  %d 张" % (out, W, H, n))
    return 0


# ══════════════════════════════════════════════════════════════════
# sheet-by-tag（原 sheet_by_tag.py）
# ══════════════════════════════════════════════════════════════════
SHEET_BY_TAG_DOC = """
sheet-by-tag：按「组合标签前缀 + 视角」从渲染目录里挑图，拼成联系表

为什么单独做一个：手写文件清单会过期。渲染文件名里带头像名，
场景里多一个头像（比如 NDMF 烘焙留下的 (Clone)）文件名就会多出 _00_/_01_ 索引，
按名字排序取第一个会取到**克隆体**的图 —— 于是「改了参数图却没变」，
我据此误判过一轮。这里改成每次现扫目录、并显式排除带索引的旧文件。

用法：
    python img_tools.py sheet-by-tag <渲染目录> <输出.png> <视角> <前缀1> [前缀2 ...] [--cols N] [--cell N]
    python img_tools.py sheet-by-tag 组合 out.png 1正面 A B C
"""

INDEXED = re.compile(r"_\d\d_[^_]*_[^_]*\.png$")   # 多头像时才有的 _00_/_01_ 索引


def collect(src, view, prefixes):
    files = sorted(f for f in os.listdir(src) if f.endswith(view + ".png"))
    rows = []
    for f in files:
        if INDEXED.search(f):
            continue                                   # 克隆体/多头像的旧渲染，跳过
        tag = f.split("_" + view)[0]
        # 去掉尾部的头像名，只留组合标签
        tag = tag.rsplit("_", 1)[0] if "_" in tag else tag
        if prefixes and not any(tag.startswith(p) for p in prefixes):
            continue
        rows.append((os.path.join(src, f), tag))
    rows.sort(key=lambda r: r[1])
    return rows


def cmd_sheet_by_tag(argv):
    if len(argv) < 5:
        print(SHEET_BY_TAG_DOC)
        return 1
    src, out, view = argv[1], argv[2], argv[3]
    cols, cell, prefixes = 4, 420, []
    i = 4
    while i < len(argv):
        if argv[i] == "--cols":
            cols = int(argv[i + 1]); i += 2
        elif argv[i] == "--cell":
            cell = int(argv[i + 1]); i += 2
        else:
            prefixes.append(argv[i]); i += 1

    rows = collect(src, view, prefixes)
    if not rows:
        print("没挑到图：目录 %s 视角 %s 前缀 %s" % (src, view, prefixes))
        return 1
    # 原脚本经清单文件转调 contact_sheet.py；合并后进程内调 sheet 子命令，清单往返保留（行为一致）
    lst = out + ".list.txt"
    io.open(lst, "w", encoding="utf-8").write(
        "\n".join("%s\t%s" % (p, t) for p, t in rows))
    rc = cmd_sheet(["sheet", out, "--cols", str(cols), "--cell", str(cell), "--list", lst])
    if rc:
        raise SystemExit("sheet 子命令失败（清单留在 %s）" % lst)
    os.remove(lst)
    return 0


# ══════════════════════════════════════════════════════════════════
# diff-crop（原 diff_crop.py）
# ══════════════════════════════════════════════════════════════════
DIFF_CROP_DOC = """
diff-crop：**用方案之间的差异图自动定位「要评的区域」**，把同一批图裁到同一个框并放大，
再喂给评审模型。解决「要评的东西在整图里占比太小、模型判定互相矛盾」。

用法：
    python img_tools.py diff-crop <输出目录> <图1> <图2> [图3 ...]
    可选：--top 0.66   只在上 N 比例内找热区（排除嘴/下巴等无关改动，默认 1.0）
          --thr 0.06   热力阈值占峰值的比例（默认 0.06）
          --long 1400  裁图放大后的长边像素（默认 1400）

为什么不自己指坐标：
  评「几个捏脸方案的眼型差别」时，眼睛在整脸特写里只占画面宽 15%，
  远低于「被评对象要占 ≥1/3」的门槛，模型给出的判定会互相矛盾
  （2026-09-06 实测：同一模型对三组候选的判定彼此打架，且与像素差矛盾）。
  而**自己看图指裁切坐标正是最容易错的一环**。
  形态键/参数只作用在特定区域 → **方案两两相减后亮起来的地方，按定义就是被改动的区域**。

实测效果（工程C 三组捏脸候选）：
  眼部框自动定位到 480x292，占画面宽 **15% → 44%**；
  裁图两两 sumdiff 从 100 万级升到 **1200 万级**，单像素最大差 **231/255**。
  差异本来就很大，只是在整脸视野里被稀释了。

坑：
  * **裁完必须自检两两仍不同**（sumdiff ≠ 0），否则等于换个方式喂空图。本脚本自动打印。
  * 证伪任务里要加一条**通道自检**声明（「这张图是 X 部位的特写，能看到 Y」）——
    连它都判「矛盾」，说明是裁切错了，不是方案的问题。
  * 放大是 LANCZOS 重采样，**边缘发虚是放大所致**，提示词里要写明别当缺陷。
"""


def cmd_diff_crop(argv):
    import numpy as np
    ap = argparse.ArgumentParser(prog="img_tools.py diff-crop", description=DIFF_CROP_DOC,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--top", type=float, default=1.0,
                    help="只在上 N 比例内找热区（0<N<=1），排除无关区域")
    ap.add_argument("--thr", type=float, default=0.06, help="热力阈值占峰值的比例")
    ap.add_argument("--long", type=int, default=1400, help="裁图放大后的长边像素")
    a = ap.parse_args(argv[1:])

    if len(a.images) < 2:
        sys.exit("至少要两张图才能做差")
    os.makedirs(a.outdir, exist_ok=True)

    ims = [Image.open(p).convert("RGB") for p in a.images]
    W, H = ims[0].size
    for p, im in zip(a.images, ims):
        if im.size != (W, H):
            sys.exit("!! 尺寸不一致：%s 是 %s，应为 %s（必须同机位同分辨率）" % (p, im.size, (W, H)))
    arr = [np.asarray(im, dtype=np.int16) for im in ims]

    heat = np.zeros((H, W), dtype=np.int64)
    for i in range(len(arr)):
        for j in range(i + 1, len(arr)):
            heat += np.abs(arr[i] - arr[j]).sum(axis=2)

    mask = heat > heat.max() * a.thr
    if a.top < 1.0:
        mask[int(H * a.top):, :] = False
    if mask.sum() < 200:
        sys.exit("!! 改动区太小（%d 像素），判据不适用 —— 先确认这几张图真的不同" % mask.sum())

    ys, xs = np.nonzero(mask)
    x0, x1 = int(np.percentile(xs, 2)), int(np.percentile(xs, 98))
    y0, y1 = int(np.percentile(ys, 2)), int(np.percentile(ys, 98))
    padx, pady = int((x1 - x0) * 0.12), int((y1 - y0) * 0.35)
    x0, x1 = max(0, x0 - padx), min(W, x1 + padx)
    y0, y1 = max(0, y0 - pady), min(H, y1 + pady)
    bw, bh = x1 - x0, y1 - y0
    print("热力区 %d 像素 | 框=(%d,%d)-(%d,%d) %dx%d | 占画面宽 %.0f%%"
          % (mask.sum(), x0, y0, x1, y1, bw, bh, 100.0 * bw / W))
    if bw < W * 0.25:
        print("  ⚠ 框仍不到画面宽的 1/4 —— 考虑调小 --thr，或本来就该重渲更近的机位")

    scale = max(1, int(a.long / max(bw, bh)))
    outs = []
    for p, im in zip(a.images, ims):
        c = im.crop((x0, y0, x1, y1)).resize((bw * scale, bh * scale), Image.LANCZOS)
        q = os.path.join(a.outdir, os.path.splitext(os.path.basename(p))[0] + "_crop.png")
        c.save(q)
        outs.append(q)
        print("  wrote %s  %dx%d" % (os.path.basename(q), c.size[0], c.size[1]))

    print("自检：裁图两两必须仍不同")
    bad = 0
    ca = [np.asarray(Image.open(q).convert("RGB"), dtype=np.int16) for q in outs]
    for i in range(len(ca)):
        for j in range(i + 1, len(ca)):
            d = np.abs(ca[i] - ca[j])
            flag = "" if d.sum() else "  ✗ 完全相同！"
            if not d.sum():
                bad += 1
            print("  %-24s vs %-24s sumdiff=%12d 最大单像素差=%3d%s"
                  % (os.path.basename(outs[i]), os.path.basename(outs[j]),
                     int(d.sum()), int(d.max()), flag))
    sys.exit(1 if bad else 0)


# ══════════════════════════════════════════════════════════════════
# overlay（原 overlay_composite.py）
# ══════════════════════════════════════════════════════════════════
OVERLAY_DOC = """
overlay：把一张稀疏叠加层贴图 alpha-over 到一张底图上，产出完整 _MainTex，
底图路径做成参数——底图换了（比如客户换瞳色后脸部底图要换成
Assets/<素体>/Texture/Eye/ 下的某个变体）用同一个脚本重跑即可，不用改代码。
相关素材：任意「稀疏叠加层」贴图（舌头/乳首/纹身/伤疤一类小面积 RGBA 叠加）

为什么离线合成而不是挂 lilToon 的 _Main2ndTex/_Main3rdTex：
  这两个叠加层本来就是「盖在整张 MainTex 上」的定位（舌头贴在舌头 UV 岛、乳首贴在对应岛位），
  不是一张独立可开关的装饰层；而 Main2nd/Main3rd 两个槽位在这份材质上已经被厂商的妆容占用
  （见 Shinano_face.mat 现状），硬塞进去还要处理混合模式/挡光顺序，不如离线合成直接可控。

用法：
    python img_tools.py overlay <底图.png> <叠加层.png> --out <输出.png>

自检输出：
  - 叠加层自身不透明像素占比（重新测一遍，与已知实测数字互相印证，不是直接抄数）
  - 合成图与底图的逐像素差异占比 —— 期望 ≈ 叠加层不透明占比，差太多说明合成错了
"""


def load(p):
    import numpy as np
    Image.MAX_IMAGE_PIXELS = None
    return np.asarray(Image.open(p).convert("RGBA"))


def over(base, top):
    """标准 alpha-over：top 压在 base 上。两张都是 RGBA uint8，尺寸必须一致。"""
    import numpy as np
    b = base.astype(np.float32) / 255.0
    t = top.astype(np.float32) / 255.0
    ta = t[..., 3:4]
    ba = b[..., 3:4]
    oa = ta + ba * (1 - ta)
    safe = np.where(oa > 1e-6, oa, 1.0)
    rgb = (t[..., :3] * ta + b[..., :3] * ba * (1 - ta)) / safe
    out = np.concatenate([rgb, oa], axis=-1)
    return (np.clip(out, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def cmd_overlay(argv):
    import numpy as np
    Image.MAX_IMAGE_PIXELS = None
    ap = argparse.ArgumentParser(prog="img_tools.py overlay", description=OVERLAY_DOC,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", help="底图路径（会被 alpha-over 覆盖，原图不改动，只读）")
    ap.add_argument("overlay", help="叠加层路径（稀疏 RGBA，不透明处盖住底图）")
    ap.add_argument("--out", required=True, help="合成结果输出路径（不得与 base 相同）")
    ap.add_argument("--alpha-thr", type=int, default=0, help="判定「不透明像素」的 alpha 阈值，默认 >0 即算")
    a = ap.parse_args(argv[1:])

    if os.path.abspath(a.out) == os.path.abspath(a.base):
        sys.exit("!! --out 不能等于 base，禁止覆盖底图原图")
    if not os.path.exists(a.base):
        sys.exit("!! 缺底图 " + a.base)
    if not os.path.exists(a.overlay):
        sys.exit("!! 缺叠加层 " + a.overlay)

    base = load(a.base)
    top = load(a.overlay)
    print("底图   %s  %dx%d" % (a.base, base.shape[1], base.shape[0]))
    print("叠加层 %s  %dx%d" % (a.overlay, top.shape[1], top.shape[0]))

    if base.shape[:2] != top.shape[:2]:
        sys.exit("!! 尺寸不一致，禁止硬resize——先确认素材对不对：底图%s 叠加层%s"
                  % (base.shape[:2], top.shape[:2]))

    overlay_opaque = top[..., 3] > a.alpha_thr
    overlay_pct = 100.0 * overlay_opaque.sum() / overlay_opaque.size
    print("叠加层不透明像素占比（现场重测） = %.4f%%  （%d / %d 像素，阈值>%d）"
          % (overlay_pct, overlay_opaque.sum(), overlay_opaque.size, a.alpha_thr))
    if overlay_opaque.sum() > 0:
        ys, xs = np.where(overlay_opaque)
        print("叠加层不透明像素 bbox：x[%d,%d] y[%d,%d]" % (xs.min(), xs.max(), ys.min(), ys.max()))

    out = over(base, top)

    diff = np.abs(out[..., :3].astype(np.int16) - base[..., :3].astype(np.int16)).max(axis=2) > 2
    diff_pct = 100.0 * diff.sum() / diff.size
    print("合成图与底图差异像素占比 = %.4f%%  （%d / %d 像素，阈值>2）" % (diff_pct, diff.sum(), diff.size))
    ratio = diff_pct / overlay_pct if overlay_pct > 1e-9 else float("nan")
    ok = 0.85 <= ratio <= 1.15 if overlay_pct > 1e-9 else diff.sum() == 0
    print("差异占比 / 叠加层不透明占比 = %.3f  --> %s" % (ratio, "自检通过" if ok else "**自检未过，合成可能有问题，需要人工核对**"))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    Image.fromarray(out).save(a.out)
    print("已写出 -> %s  %dx%d  mode=%s" % (a.out, out.shape[1], out.shape[0], "RGBA"))
    return 0


# ══════════════════════════════════════════════════════════════════
# autocrop（原 autocrop.py）
# ══════════════════════════════════════════════════════════════════
AUTOCROP_DOC = """
autocrop：把纯色背景的离屏渲染图**按实际画到的像素**裁紧，让被评对象占满画面

为什么要它：取景是按包围盒算的，而**厂商的蒙皮网格常常声明一个错的 localBounds**
（记忆 skinned-bounds-culling）。实测 Hug me Bear 的声明包围盒是真实几何的 2.35 倍，
于是渲出来的熊只占画面 10~15%，评审模型直接判「主体过小，看不清材质」。
与其在 Unity 里跟错误的包围盒较劲，不如渲完之后按像素裁 —— 像素不会撒谎。

判据：以四角像素的中位色作为背景色，任一通道差 > tol 即算「画到了」。
裁完补成正方形并缩回原尺寸，保证联络表里各格构图一致。

用法：
    python img_tools.py autocrop 输出目录 图1.png 图2.png ...
    python img_tools.py autocrop 输出目录 --glob "某目录/*_1样式.png"
    可选 --tol 12 --margin 0.06 --size 860
"""


def bg_color(im):
    """四角各取一小块的中位色 —— 单点像素可能正好压在抗锯齿边上。"""
    w, h = im.size
    k = max(2, min(w, h) // 100)
    px = []
    for x0, y0 in ((0, 0), (w - k, 0), (0, h - k), (w - k, h - k)):
        px += list(im.crop((x0, y0, x0 + k, y0 + k)).getdata())
    px.sort()
    return px[len(px) // 2]


def content_box(im, tol):
    bg = bg_color(im)
    # 逐通道差的最大值 > tol → 前景。用 point 做成单通道掩码再让 PIL 求 bbox，比逐像素快得多
    ch = im.split()
    mask = None
    for c, b in zip(ch[:3], bg[:3]):
        m = c.point(lambda v, b=b: 255 if abs(v - b) > tol else 0)
        mask = m if mask is None else Image.blend(mask, m, 0.5).point(lambda v: 255 if v > 0 else 0)
    return mask.getbbox(), bg


def crop_one(src, dst, tol=12, margin=0.06, size=None):
    im = Image.open(src).convert("RGB")
    box, bg = content_box(im, tol)
    if box is None:                       # 整张都是背景：原样复制，别裁成 0×0
        im.save(dst)
        return src, "全空，未裁"
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    half = max(x1 - x0, y1 - y0) / 2.0 * (1.0 + margin * 2)
    half = max(half, 8)
    # 正方形取景框可能越界 —— 越界的部分用背景色补，不要把框推回去（推回去主体就偏心了）
    L, T, R, B = int(cx - half), int(cy - half), int(cx + half), int(cy + half)
    out = Image.new("RGB", (R - L, B - T), bg)
    sx0, sy0 = max(L, 0), max(T, 0)
    sx1, sy1 = min(R, im.width), min(B, im.height)
    out.paste(im.crop((sx0, sy0, sx1, sy1)), (sx0 - L, sy0 - T))
    if size:
        out = out.resize((size, size), Image.LANCZOS)
    out.save(dst)
    fill = (x1 - x0) * (y1 - y0) / float(im.width * im.height)
    return src, "原始占比 %.0f%% → 裁到 %dpx" % (fill * 100, out.width)


def cmd_autocrop(argv):
    if len(argv) < 3:
        print(AUTOCROP_DOC)
        return 1
    outdir = argv[1]
    tol, margin, size = 12, 0.06, None
    files, i = [], 2
    while i < len(argv):
        a = argv[i]
        if a == "--glob":
            files += sorted(globmod.glob(argv[i + 1])); i += 2
        elif a == "--tol":
            tol = int(argv[i + 1]); i += 2
        elif a == "--margin":
            margin = float(argv[i + 1]); i += 2
        elif a == "--size":
            size = int(argv[i + 1]); i += 2
        else:
            files.append(a); i += 1
    if not files:
        print("没有输入图")
        return 1
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    for f in files:
        dst = os.path.join(outdir, os.path.basename(f))
        src, note = crop_one(f, dst, tol, margin, size)
        print("%-70s %s" % (os.path.basename(src), note))
    print("共 %d 张 → %s" % (len(files), outdir))
    return 0


# ══════════════════════════════════════════════════════════════════
# 子命令分发
# ══════════════════════════════════════════════════════════════════
# 子命令自己解析其余参数（sheet/sheet-by-tag/autocrop 沿用原脚本的手工解析，diff-crop/overlay 沿用原 argparse），
# 所以外层 argparse 只负责列子命令与 -h，不吞子命令参数（原脚本的选项可以出现在位置参数之前或之间）。
COMMANDS = {
    "sheet": (cmd_sheet, "拼联系表（原 contact_sheet.py）"),
    "sheet-by-tag": (cmd_sheet_by_tag, "按组合标签前缀＋视角挑图拼表（原 sheet_by_tag.py）"),
    "diff-crop": (cmd_diff_crop, "按方案差异热区裁图并放大（原 diff_crop.py）"),
    "overlay": (cmd_overlay, "稀疏叠加层 alpha-over 到底图（原 overlay_composite.py）"),
    "autocrop": (cmd_autocrop, "纯色背景渲染图按像素裁紧（原 autocrop.py）"),
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(
        prog="img_tools.py",
        description="图像小工具合集。`img_tools.py <子命令>` 不带参数看该子命令的完整说明。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", metavar="子命令")
    for name, (_fn, help_) in COMMANDS.items():
        sub.add_parser(name, help=help_, add_help=False)
    if not argv or argv[0] not in COMMANDS:
        ap.parse_args(argv[:1] or ["-h"])   # 未知子命令 → argparse 报错；无参数 → 打印帮助
        return 2
    fn = COMMANDS[argv[0]][0]
    return fn(argv)


if __name__ == "__main__":
    sys.exit(main())
