# -*- coding: utf-8 -*-
"""眼睛贴图合成：把 cumulus 的眼色层 alpha-over 到素体底图上，产出完整 _MainTex。
【项目沉淀】通用工具
适用素体：无关
相关素材：cumulus 眼色层 + 素体底图
工具链　：Python 3 + Pillow（离线）
可复用性：★★ 换了素材包要改输入目录
用途　　：眼睛贴图离线合成：把眼色层 alpha-over 到素体底图上产出完整 _MainTex，异色瞳按 UV 岛切分。


为什么离线合成而不是挂 lilToon 的 `_Main2ndTex`：
  眼色层不是只有虹膜，它覆盖整个眼睛 UV 岛（岛内大部分不透明），本来就是整眼替换。
  走 `_Main2ndTex` 要额外对 `_Main2ndTexBlendMode` / `_Main2ndTexAlphaMode` /
  `_Color2nd` 一堆开关，结果依赖 shader 版本；离线 alpha-over 出来是什么就是什么，
  能直接开图核对，也不多占一层采样。

异色瞳：眼色层的两只眼睛在 UV 上是**两个完全分离的岛**
（先量出两岛的列范围，确认不重叠、不透明像素数相同），
按中缝列切开、左右各取一个颜色即可，不需要手描蒙版。

    python eye_composite.py <工程目录> --base <素体眼部底图.png> --src <眼色层目录> [--split 2048] [--level 5] [--pair blue yellow]
    （--base / --src 也可用环境变量 EYE_BASE_TEX / EYE_SRC_DIR 指定；路径相对工程 Assets/ 或绝对路径）
"""
import argparse
import io
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

SPLIT = 2048          # 两个眼睛 UV 岛的中缝缺省值；按你的素体实测两岛边界后取中点，用 --split 覆盖


def over(base, top):
    """标准 alpha-over：top 压在 base 上。两张都是 RGBA uint8。"""
    b = base.astype(np.float32) / 255.0
    t = top.astype(np.float32) / 255.0
    ta = t[..., 3:4]
    ba = b[..., 3:4]
    oa = ta + ba * (1 - ta)
    # 除零保护：完全透明处颜色无意义，填 0
    safe = np.where(oa > 1e-6, oa, 1.0)
    rgb = (t[..., :3] * ta + b[..., :3] * ba * (1 - ta)) / safe
    out = np.concatenate([rgb, oa], axis=-1)
    return (np.clip(out, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def load(p):
    return np.asarray(Image.open(p).convert("RGBA"))


LUM = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def colorize(img, mask, target):
    """把 mask 内的像素改成 target 色，但保住原来的相对亮度（笔触/羽化不丢）。

    直接填单色会得到一坨没有笔触的色块。按 lum/mean_lum 缩放，
    平均色等于 target，明暗关系照旧。
    """
    out = img.copy()
    px = img[..., :3][mask].astype(np.float32)
    if px.size == 0:
        return out
    lum = px @ LUM
    ref = float(lum.mean())
    if ref < 1e-3:
        return out
    scale = (lum / ref)[:, None]
    new = np.clip(np.asarray(target, dtype=np.float32)[None, :] * scale, 0, 255)
    out[..., :3][mask] = (new + 0.5).astype(np.uint8)
    return out


def colorize_grad(img, mask, top, bot):
    """竖向渐变着色：mask 内从上（PNG 行号小）到下线性插值 top→bot，同样保住相对亮度。

    方向依据：BrowProbe 实测 v 越大越靠上（12 列 9 列正斜率），
    而 v = 1 − row/H，故行号小 = 脸上的上边。
    """
    out = img.copy()
    ys, xs = np.where(mask)
    if ys.size == 0:
        return out

    # t **逐列**归一化，不用全局 bbox：眉毛是一道弧，全局按行算的话
    # 弧的两端整条都落进「上」或「下」，渐变就跟着弧走歪了。
    ymin = np.full(mask.shape[1], 1 << 30, dtype=np.int64)
    ymax = np.full(mask.shape[1], -1, dtype=np.int64)
    np.minimum.at(ymin, xs, ys)
    np.maximum.at(ymax, xs, ys)
    span = np.maximum(1, ymax[xs] - ymin[xs])
    t = (ys - ymin[xs]) / span                    # 0 = 该列最上，1 = 该列最下

    px = img[..., :3][mask].astype(np.float32)
    lum = px @ LUM
    ref = float(lum.mean())
    if ref < 1e-3:
        return out
    # ⚠ 亮度缩放要**压制**。原始眉毛本来就上浓下淡，
    #   直接乘 lum/ref 会把想要的渐变正好抵消掉（实测上下只差 3.4 亮度）。
    #   压到 K 后既保住笔触，又让渐变说了算。
    K = 0.35
    scale = 1.0 + K * (lum / ref - 1.0)

    tgt = (np.asarray(top, dtype=np.float32)[None, :] * (1 - t)[:, None]
           + np.asarray(bot, dtype=np.float32)[None, :] * t[:, None])
    new = np.clip(tgt * scale[:, None], 0, 255)
    out[..., :3][mask] = (new + 0.5).astype(np.uint8)
    return out


def lash_mask(src_d, lo="ashgray1", hi="black3", thr=12):
    """睫毛掩膜 = 同系列两个色档的差异像素。不猜位置，直接由数据定。"""
    a = load(os.path.join(src_d, lo + ".png")).astype(np.int16)
    b = load(os.path.join(src_d, hi + ".png")).astype(np.int16)
    return np.abs(a[..., :3] - b[..., :3]).max(axis=2) > thr


def hexc(c):
    return "#%02X%02X%02X" % tuple(int(round(x)) for x in c)


def report(img, mask, label):
    px = img[..., :3][mask].astype(np.float32)
    if px.size == 0:
        print("      %s：掩膜为空" % label)
        return
    print("      %-10s 均色 %s  像素 %d" % (label, hexc(px.mean(axis=0)), px.shape[0]))


def main():
    global SPLIT
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--level", type=int, default=5, help="眼色档位 1~5，数字越大越深")
    ap.add_argument("--pair", nargs=2, default=["blue", "yellow"],
                    help="异色瞳用的两个色系")
    ap.add_argument("--base", default=os.environ.get("EYE_BASE_TEX"), help="素体眼部底图（相对 Assets/ 或绝对路径）")
    ap.add_argument("--src", default=os.environ.get("EYE_SRC_DIR"),
                    help="眼色层目录（相对 Assets/ 或绝对路径）；其下按 pupil 档位分子目录时，传到档位目录这一级")
    ap.add_argument("--lash-dir", default=os.environ.get("EYE_LASH_DIR"), help="睫毛层目录（相对 Assets/ 或绝对路径）")
    ap.add_argument("--brow-mask", default=os.environ.get("EYE_BROW_MASK"), help="眉毛遮罩图（相对 Assets/ 或绝对路径）")
    ap.add_argument("--split", type=int, default=SPLIT, help="两个眼睛 UV 岛的中缝列（像素）")
    ap.add_argument("--pupil", default="on", choices=["on", "off"])
    ap.add_argument("--lash", default="ashgray1",
                    help="睫毛层档位（先叠上去再改色；选最浅的一档，改色时要压的量最小）")
    ap.add_argument("--silver", default="D8D8DE",
                    help="眉毛/睫毛的目标银白色（十六进制，不带 #）")
    ap.add_argument("--no-silver", action="store_true", help="不改眉毛睫毛，只做眼色")
    ap.add_argument("--brow-top", default="EFEFF4", help="眉毛上端色（浅）")
    ap.add_argument("--brow-bot", default="9C9CA8", help="眉毛下端色（深）")
    a = ap.parse_args()

    A = os.path.join(a.project, "Assets")
    if not a.base or not a.src:
        sys.exit("要给 --base <素体眼部底图> 和 --src <眼色层目录>（或设 EYE_BASE_TEX / EYE_SRC_DIR）")
    SPLIT = a.split
    base_p = a.base if os.path.isabs(a.base) else os.path.join(A, a.base)
    src_d = a.src if os.path.isabs(a.src) else os.path.join(A, a.src)
    out_d = os.path.join(A, "_Work", "EyeTex")
    for p in (base_p, src_d):
        if not os.path.exists(p):
            sys.exit("缺 " + p)
    os.makedirs(out_d, exist_ok=True)

    base = load(base_p)
    print("底图 %s  %s" % (os.path.basename(base_p), base.shape))

    # ── 睫毛层 + 眉毛/睫毛银白 ──────────────────────────────
    lash_d = (lambda v: "" if not v else (v if os.path.isabs(v) else os.path.join(A, v)))(a.lash_dir)
    brow_p = (lambda v: "" if not v else (v if os.path.isabs(v) else os.path.join(A, v)))(a.brow_mask)
    silver = tuple(int(a.silver[i:i + 2], 16) for i in (0, 2, 4))
    mbrow = mlash = None
    if not a.no_silver:
        lp = os.path.join(lash_d, a.lash + ".png")
        if os.path.exists(lp):
            base = over(base, load(lp))
            print("  叠睫毛层 %s" % a.lash)
        else:
            print("  !! 缺睫毛层 %s，跳过（仍会给原生睫毛改色）" % lp)
        if os.path.isdir(lash_d):
            mlash = lash_mask(lash_d)
            print("  睫毛掩膜 %d 像素（由两个色档相减得到）" % mlash.sum())
        if os.path.exists(brow_p):
            mbrow = load(brow_p)[..., 0] > 128
            print("  眉毛掩膜 %d 像素（包内自带 Brow_mask）" % mbrow.sum())
        btop = tuple(int(a.brow_top[i:i + 2], 16) for i in (0, 2, 4))
        bbot = tuple(int(a.brow_bot[i:i + 2], 16) for i in (0, 2, 4))
        if mlash is not None:
            report(base, mlash, "睫毛(改前)")
            base = colorize(base, mlash, silver)
            report(base, mlash, "睫毛(改后)")
        if mbrow is not None:
            report(base, mbrow, "眉毛(改前)")
            base = colorize_grad(base, mbrow, btop, bbot)
            report(base, mbrow, "眉毛(改后)")
            # 渐变自检：上下两段必须真的分出深浅，否则方向或掩膜有问题
            ys, _ = np.where(mbrow)
            mid = (int(ys.min()) + int(ys.max())) // 2
            up = mbrow.copy(); up[mid:] = False
            dn = mbrow.copy(); dn[:mid] = False
            report(base, up, "  眉上半")
            report(base, dn, "  眉下半")
            lu = (base[..., :3][up].astype(np.float32) @ LUM).mean()
            ld = (base[..., :3][dn].astype(np.float32) @ LUM).mean()
            print("      上半亮度 %.1f  下半亮度 %.1f  → %s"
                  % (lu, ld, "上浅下深 ✓" if lu > ld + 5 else "**方向不对或对比太弱**"))
        print("  睫毛银白 %s   眉毛渐变 %s → %s"
              % ("#" + a.silver.upper(), "#" + a.brow_top.upper(), "#" + a.brow_bot.upper()))

    made = []
    fams = sorted(set(a.pair))
    for fam in fams:
        sp = os.path.join(src_d, "%s%d.png" % (fam, a.level))
        if not os.path.exists(sp):
            print("!! 缺 " + sp)
            continue
        top = load(sp)
        out = over(base, top)
        op = os.path.join(out_d, "eyes_%s%d.png" % (fam, a.level))
        Image.fromarray(out).save(op)
        made.append(op)
        print("  单色 -> " + os.path.relpath(op, a.project))

    # 异色瞳：左岛取 pair[0]，右岛取 pair[1]
    l, r = a.pair
    lp = os.path.join(src_d, "%s%d.png" % (l, a.level))
    rp = os.path.join(src_d, "%s%d.png" % (r, a.level))
    if os.path.exists(lp) and os.path.exists(rp):
        tl, tr = load(lp), load(rp)
        mix = tl.copy()
        mix[:, SPLIT:] = tr[:, SPLIT:]
        out = over(base, mix)
        op = os.path.join(out_d, "eyes_hetero_%s_%s%d.png" % (l, r, a.level))
        Image.fromarray(out).save(op)
        made.append(op)
        print("  异色瞳 -> " + os.path.relpath(op, a.project))

        # 回读自检：两半必须真的不一样，否则就是切缝位置错了。
        # ⚠ 掩膜必须用**眼色层自己的 alpha**，不能用合成图的 alpha ——
        #   底图的不透明区远超眼睛区，按它筛会选到一堆肤色，
        #   量出来两边都是 #D8AE9D 这种，看着像"没生效"其实是判据错了。
        chk = np.asarray(Image.open(op).convert("RGBA")).astype(np.int16)
        al = tl[..., 3] > 128
        for side, sl in (("左岛", slice(0, SPLIT)), ("右岛", slice(SPLIT, None))):
            px = chk[:, sl, :3][al[:, sl]]
            sat = px.max(axis=1) - px.min(axis=1)
            sel = px[sat >= np.percentile(sat, 95)]
            m = sel.mean(axis=0)
            print("      %s 虹膜主色 #%02X%02X%02X" % (side, *[int(round(x)) for x in m]))

    print("\n共 %d 张。别忘了在 Unity 里刷新后再引用。" % len(made))


if __name__ == "__main__":
    main()
