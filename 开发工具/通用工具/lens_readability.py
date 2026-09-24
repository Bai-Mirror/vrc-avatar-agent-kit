#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""流星/眼球特效「读不读得出来」的度量。依赖只有 numpy + Pillow。
【项目沉淀】通用工具
适用素体：无关
相关素材：流星/眼球特效静帧与流星帧
工具链　：Python 3 + numpy + Pillow（离线）
可复用性：★★★ 换个单子直接能用
用途　　：度量「流星/眼球特效读不读得出来」：按视距出背景校正后的能量与 ΔE 诊断，给出可复现判据。


用法:
  python3 lens_readability.py 静帧.png 流星帧.png [--tag 名字] [--json out.json]
  python3 lens_readability.py --compare 变体A:静A.png:流A.png 变体B:静B.png:流B.png ...

设计要点（每条都对应一个已实测的坑，见 SOP）：
  * 背景用配对静帧的同一像素，不用环形邻域。环形会吃眼睑/睫毛/limbus 与特效自身辉光。
  * 不设「流星像素」阈值。阈值 1→32 能让 ΔE 中位数从 5.3 变到 18.3。
  * 能量在线性光里算；ΔE 只作诊断分量，不做排序判据。
  * 检出用「带通 + 定向线滤波」，零分布用静帧同尺寸滑窗块极大值（不是逐像素分布）。
  * 每个视距各自出一套数，社交视距优先用真实远距渲图；降采样只作廉价代理。
  * 必跑空跑对照 null_run：把静帧当成「流星帧」喂进去，任何指标都应该归零。
"""
import sys, json
import numpy as np
from PIL import Image

# ---------- 色彩 ----------
_M = np.array([[0.4124564,0.3575761,0.1804375],
               [0.2126729,0.7151522,0.0721750],
               [0.0193339,0.1191920,0.9503041]])
_WP = np.array([0.95047, 1.0, 1.08883])

def to_linear(s):
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)

def to_lab(s):
    t = (to_linear(s) @ _M.T) / _WP
    d = 6 / 29
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1)

def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64) / 255.0

# ---------- 滤波（全部 numpy，无 scipy） ----------
def boxf(a, k):
    k = k | 1                      # 强制奇数，偶数会 off-by-one
    p = k // 2
    b = np.pad(a, ((p, p), (p, p)), mode="edge")
    c = np.vstack([np.zeros((1, b.shape[1])), np.cumsum(b, 0)])
    b = (c[k:, :] - c[:-k, :]) / k
    c = np.hstack([np.zeros((b.shape[0], 1)), np.cumsum(b, 1)])
    return (c[:, k:] - c[:, :-k]) / k

def gaussf(a, s):
    k = max(1, int(round(s * 1.5))) * 2 + 1
    for _ in range(3):
        a = boxf(a, k)
    return a

def dog(L, s1, s2):
    return gaussf(L, s1) - gaussf(L, s2)

def maxfilt(a, k):
    k = k | 1; p = k // 2
    o = a.copy()
    for d in range(-p, p + 1):
        if d: o = np.maximum(o, np.roll(a, d, 0))
    t = o.copy()
    for d in range(-p, p + 1):
        if d: o = np.maximum(o, np.roll(t, d, 1))
    return o

def oriented(base, half, nth=12):
    """定向线积分：流星长宽比约 24:1，各向同性 DoG 对它是失配滤波器。"""
    best = np.full_like(base, -np.inf)
    for k in range(nth):
        th = np.pi * k / nth
        uy, ux = np.sin(th), np.cos(th)
        acc = np.zeros_like(base)
        for t in range(-half, half + 1):
            acc += np.roll(np.roll(base, int(round(t * uy)), 0), int(round(t * ux)), 1)
        best = np.maximum(best, acc / (2 * half + 1))
    return best

def dilate(mask, r):
    m = mask.copy()
    for _ in range(r):
        n = m.copy()
        for dy, dx in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            n |= np.roll(np.roll(m, dy, 0), dx, 1)
        m = n
    return m

# ---------- 眼盘 ----------
def iris_mask(img, margin=0.04):
    """紫/蓝虹膜 vs 粉肤色。换素体要重定这条规则并目视确认像素数。"""
    return img[..., 2] > img[..., 0] + margin

# ---------- 主度量 ----------
def measure(still_p, fx_p, tag="", scale_hint=None, roi=None):
    A, B = load(still_p), load(fx_p)
    if roi:                       # 形状项必须按「单只眼」算，双眼图不切 ROI 会把两眼量成一条线
        x0, y0, x1, y1 = roi
        A, B = A[y0:y1, x0:x1], B[y0:y1, x0:x1]
    assert A.shape == B.shape, "两帧尺寸必须一致（同机位同分辨率）"
    LA, LB = to_lab(A), to_lab(B)
    lin_d = to_linear(B) - to_linear(A)          # 线性光净增量，无阈值
    dd = np.abs(B - A).max(-1) * 255

    ir = iris_mask(A)
    px = int(ir.sum())
    # 按眼盘面积自适应尺度：以 40000 px 的特写眼盘为基准
    k = float(np.clip((px / 40000.0) ** 0.5, 0.25, 4.0)) if scale_hint is None else scale_hint
    er_r   = max(2, int(round(6 * k)))
    s1, s2 = max(1.0, 1 * k), max(3.0, 4 * k)
    half   = max(3, int(round(5 * k)))
    win    = max(5, int(round(15 * k)) | 1)
    er = ~dilate(~ir, er_r)
    if er.sum() < 100:                            # 眼盘太小/掩模失效，退回不腐蚀
        er = ir

    # --- 1. 能量（线性光，无阈值，与抗锯齿无关） ---
    flux      = float(lin_d[er].sum())            # 净加光通量
    absflux   = float(np.abs(lin_d)[er].sum())    # 总扰动（含压暗）
    darkflux  = float(-lin_d[er][lin_d[er] < 0].sum())
    flux_dens = flux / max(px, 1)

    # --- 2. 检出：定向线滤波 + 滑窗块极大值零分布 ---
    base_a, base_b = dog(LA[..., 0], s1, s2), dog(LB[..., 0], s1, s2)
    Ra, Rb = oriented(base_a, half), oriented(base_b, half)
    foot   = (dd > 2) & er                        # 只用来定位峰，不用来统计
    no_signal = foot.sum() < 3 or er.sum() < 100
    valid = er & ~dilate(dd > 0.5, er_r)          # 静帧里排除特效影响区
    vf = boxf(valid.astype(float), win)
    mx = maxfilt(np.where(valid, Ra, -np.inf), win)
    for cut in (0.999, 0.9, 0.7, 0.5):            # 眼盘小的远距图放宽窗口纯度，宁可样本多
        nullmax = mx[vf > cut]
        nullmax = nullmax[np.isfinite(nullmax)]
        if nullmax.size >= 30:
            break
    if no_signal:
        # 空跑保护：没有任何差异就没有峰。不许拿静帧自身的最大值冒充信号，
        # 否则 d' 会退化成「图像极值的 z 分数」这种恒为 2~3 的同义反复。
        peak, dprime, rival = 0.0, 0.0, 0.0
    elif nullmax.size >= 30:
        peak   = float(Rb[foot].max())
        dprime = float((peak - nullmax.mean()) / (nullmax.std() + 1e-9))
        rival  = float(100.0 * (nullmax >= peak).sum() / nullmax.size)
    else:
        peak   = float(Rb[foot].max())
        dprime, rival = float("nan"), float("nan")

    # --- 3. 形状：它读起来像不像「一道」 ---
    w = np.where(dd > 8, dd, 0.0) * er
    if w.sum() > 0:
        ys, xs = np.nonzero(w)
        wv = w[ys, xs]; cy = (ys*wv).sum()/wv.sum(); cx = (xs*wv).sum()/wv.sum()
        c = np.array([[((ys-cy)**2*wv).sum(), ((ys-cy)*(xs-cx)*wv).sum()],
                      [((ys-cy)*(xs-cx)*wv).sum(), ((xs-cx)**2*wv).sum()]]) / wv.sum()
        ev = np.linalg.eigvalsh(c)
        elong = float((ev[1] / max(ev[0], 1e-9)) ** 0.5)
        length = float(ev[1] ** 0.5)
    else:
        elong = length = 0.0

    # --- 4. 诊断分量（解释「为什么」，不排序） ---
    sel = (dd > 8) & er
    if sel.sum() > 10:
        dL = float(np.median(LB[sel][:, 0] - LA[sel][:, 0]))
        Ca = np.hypot(LA[sel][:, 1], LA[sel][:, 2]); Cb = np.hypot(LB[sel][:, 1], LB[sel][:, 2])
        dC = float(np.median(Cb - Ca))
        ha = np.degrees(np.arctan2(LA[sel][:, 2], LA[sel][:, 1]))
        hb = np.degrees(np.arctan2(LB[sel][:, 2], LB[sel][:, 1]))
        dh = float(np.median(np.abs((hb - ha + 180) % 360 - 180)))
        dE = float(np.median(np.sqrt(((LB[sel] - LA[sel]) ** 2).sum(-1))))
    else:
        dL = dC = dh = dE = 0.0

    return dict(tag=tag or fx_p, iris_px=px, scale_k=round(k, 3),
                flux=round(flux, 3), absflux=round(absflux, 3), darkflux=round(darkflux, 4),
                flux_per_Mpx=round(flux_dens * 1e6, 2),
                peak=round(peak, 3), dprime=round(dprime, 2),
                rivals_pct=round(rival, 3), null_n=int(nullmax.size),
                elongation=round(elong, 2), length_px=round(length, 1),
                dL=round(dL, 2), dC=round(dC, 2), dh_deg=round(dh, 1), dE_paired=round(dE, 2))

def null_run(still_p):
    """把静帧同时当静帧和特效帧。所有指标必须归零，否则度量本身在自造信号。"""
    return measure(still_p, still_p, tag="NULL(" + still_p.split("/")[-1] + ")")

COLS = ["tag","iris_px","flux","flux_per_Mpx","darkflux","dprime","rivals_pct",
        "elongation","length_px","dL","dC","dh_deg","dE_paired"]

def show(rows):
    hdr = "%-26s" % "tag" + "".join("%13s" % c for c in COLS[1:])
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print("%-26s" % str(r["tag"])[:26] + "".join("%13s" % r[c] for c in COLS[1:]))

if __name__ == "__main__":
    args = sys.argv[1:]
    out = None
    if "--json" in args:
        i = args.index("--json"); out = args[i+1]; del args[i:i+2]
    rows = []
    if args and args[0] == "--compare":
        for spec in args[1:]:
            parts = spec.split(":")
            tag, s, f = parts[0], parts[1], parts[2]
            r = tuple(int(v) for v in parts[3].split(",")) if len(parts) > 3 else None
            rows.append(measure(s, f, tag, roi=r))
            rows.append(null_run(s))
    else:
        tag = ""
        if "--tag" in args:
            i = args.index("--tag"); tag = args[i+1]; del args[i:i+2]
        rows.append(measure(args[0], args[1], tag))
        rows.append(null_run(args[0]))
    show(rows)
    if out:
        json.dump(rows, open(out, "w"), ensure_ascii=False, indent=1)
        print("->", out)
