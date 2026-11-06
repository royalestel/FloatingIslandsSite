#!/usr/bin/env python3
"""Preview v7: one bar from 28 m to the camera, v3's colours plus white
brought into the centre in stripes, with the flickering swatches kept in
place long enough to be seen as their average.

* New swatches (row parity is the bar's own row, see below):
    cyan | white stripes        white on even rows, cyan on odd; no flicker
    cyan + white every other    cyan, with the even rows white on one frame
                                in two (between cyan and the stripes)
* Swatches kept in place: the bar's pattern is built from the centre out,
  each taller / nearer pattern from the last one -- a row keeps its swatch
  while that stays within one ladder step of what it should be, and for at
  least HOLD patterns once it changes -- so the rows near the centre do not
  reshuffle as the bar grows.
* Flicker phase locked to the bar: flicker pairs and patterns take their
  row parity from the bar's row, not the screen line, so a bar moving an
  odd number of lines between frames does not freeze them.  (On the C64:
  the builder picks each span's line code by the bar row's parity.)

    python3 preview_v7.py video.mp4 graph.png     # CRT video; 6-frame-average profile
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import swatch_loop_video as sv
import swatches_video as sw
import gen_cosmic as gc
gc.ROUND = True

SPEED = 0.045
DNEAR = 2 * sv.lv.R_BAR * gc.F / (gc.HMAX + 0.45)
BELOW = 0.3
HOLD = 4                                 # patterns (frames, near) a changed row keeps

# ---- the swatches: colour and idle byte by (swatch, row parity, frame parity)
def colour(k, rp, p):
    if k in SPECIAL:
        return SPECIAL[k](rp, p)
    a, b = sv.PAL[k][0], sv.PAL[k][1]
    return a if (rp + p) % 2 == 0 else b

def ghost(k, rp, p):
    if k in SPECIAL:
        return 0
    return sv.PAL[k][2](rp, p) & 255

SPECIAL = {}
def _add(name, fn):
    frames = []
    for p in (0, 1):
        img = np.zeros((sw.P, sw.P, 3))
        for r in range(sw.P):
            img[r] = fb.C64RGB[fn(r & 1, p)]
        frames.append(img)
    sv.PAL.append((fn(0, 0), fn(1, 0), lambda r, p: 0, sw.blended(frames),
                   sw.brightness(frames), 0, name))
    k = len(sv.PAL) - 1
    SPECIAL[k] = fn
    return k
STRIPES = _add("cyan | white stripes", lambda rp, p: 1 if rp == 0 else 3)
HALFW = _add("cyan + white every other", lambda rp, p: 1 if rp == 0 and p == 0 else 3)
sv.COL = np.array([q[3] for q in sv.PAL])
sv.LUM = np.array([q[4] for q in sv.PAL])
sv.WIDE = np.array([q[5] for q in sv.PAL])
LADDER7 = sorted(gc.LADDER + [STRIPES, HALFW], key=lambda k: sv.LUM[k])
POS = {k: i for i, k in enumerate(LADDER7)}

# ---- the bar's patterns over its flight, each from the last
V7_ANCHORS = [(28.0, 3.0), (20.0, 19.0), (5.0, 62.0), (2.5, 84.0), (0.42, 100.0)]

def ideal_half(h, d):
    """v3's choice, centre row first, on LADDER7 -- the core brighter near in,
    so white comes in sooner."""
    keep, gc.V3_ANCHORS = gc.V3_ANCHORS, V7_ANCHORS
    try:
        r = gc.ramp_v3(h, d, LADDER7)
    finally:
        gc.V3_ANCHORS = keep
    half = (h + 1) // 2
    return r[h - half:]                  # from the centre (or centre pair) out

def flight():
    d, f = sv.lv.FAR, 0
    prev, age = [], []
    out = []
    while d >= DNEAR:
        h = max(2, min(gc.HMAX, lv.bar_lines(d)))
        want = ideal_half(h, round(d * 10) / 10)
        cur, nage = [], []
        for i, k in enumerate(want):
            if i < len(prev):
                old, a = prev[i], age[i]
                if (old == k or a < HOLD) and abs(POS[old] - POS[k]) <= 1:
                    cur.append(old)
                    nage.append(a + 1)
                    continue
            cur.append(k)
            nage.append(1)
        for i in range(1, len(cur)):     # never brighter than the row inside
            if POS[cur[i]] > POS[cur[i - 1]]:
                cur[i] = cur[i - 1]
        prev, age = cur, nage
        full = (cur[::-1] if h % 2 == 0 else cur[:0:-1]) + cur
        out.append((d, h, full))
        d -= SPEED
        f += 1
    return out

def render_rows(f, h, full, width=120):
    """The bar's rows on frame f: C64 colour indices, ghost bytes applied."""
    p = f & 1
    x = np.arange(width)
    rows = np.zeros((h, width), int)
    for j, k in enumerate(full):
        rp = j & 1                       # the bar's own row parity
        rows[j] = colour(k, rp, p)
        g = ghost(k, rp, p)
        if g:
            rows[j, ((g >> (7 - x % 8)) & 1) == 1] = 0
    return rows

def video(path):
    fl_ = flight()
    spr = gc.sprites()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    v = iv.Video(path, W + 32, H + 60)
    last = None
    for f, (d, h, full) in enumerate(fl_):
        img = np.zeros((fb.H, fb.W), int)
        top = int(round((2 * gc.CYL + 2 * gc.F * BELOW / d - h) / 2))   # BELOW the ship
        rows = render_rows(f, h, full, fb.W)
        for j in range(h):
            ln = top + j
            if 0 <= ln < gc.NLINES:
                img[ln + 11] = rows[j]
        rgb = fb.C64RGB[img].astype(np.uint8)
        p = f & 1
        cols = {1: 4, 2: 14, 3: (1, 3)[p]}
        for side in (0, 1):
            blk = spr[((4 * 4) + p * 2 + side) * 64:][:63]
            for sy in range(21):
                bits = blk[3 * sy] << 16 | blk[3 * sy + 1] << 8 | blk[3 * sy + 2]
                for cx in range(12):
                    val = (bits >> (22 - 2 * cx)) & 3
                    if val:
                        rgb[gc.SPRY + 1 + sy - 51, 136 + side * 24 + 2 * cx:][:2] = fb.C64RGB[cols[val]]
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), f"v7: v3 + white stripes in the centre, swatches held, flicker locked "
                f"to the bar   {d:5.2f} m   {h} lines   CRT", fill=(170, 176, 210), font=small)
        canvas.paste(lv.crt_look(rgb, Z), (16, 40))
        dr.text((v.w - 200, 56), f"{d:5.2f} m", fill=(235, 235, 120), font=font)
        v.add(canvas)
        last = canvas
    for _ in range(30):
        v.add(last)
    v.close()
    print("wrote", path)

def profile(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import analyze_onebar as ao
    import analyze_ma as am
    LIN16 = ao.LIN16
    def v7_series():
        ds, core, bar = [], [], []
        for f, (d, h, full) in enumerate(flight()):
            rgb = fb.C64RGB[render_rows(f, h, full)].astype(np.uint8)
            lum = (LIN16[rgb].astype(np.float64).mean(axis=1) / 65535) @ ao.LW
            c0, c1 = int(h * 0.4), max(int(h * 0.4) + 1, int(np.ceil(h * 0.6)))
            ds.append(d); core.append(lum[c0:c1].mean()); bar.append(lum.mean())
        return np.array(ds), np.array(core), np.array(bar)
    series = [("v3", "#1baf7a", am.per_frame("v3")), ("v7", "#2a78d6", v7_series())]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")
    for name, colr, (ds, core, bar) in series:
        for ax, y, what in ((axes[0], core, "core"), (axes[1], bar, "whole bar")):
            ax.plot(am.avg(ds, 2)[::2], ao.lstar(am.avg(y, 2)[::2]), color=colr, lw=1, alpha=0.25)
            ma, dma = ao.lstar(am.avg(y, 6)), am.avg(ds, 6)
            ax.plot(dma, ma, color=colr, lw=2, label=name)
            dy = np.diff(ma)
            idx = np.where(dy < -0.3)[0]
            print(f"{name:4s} {what:9s} 6-frame average: {len(idx)} drops of more than 0.3 L*"
                  + (f", largest {dy.min():.1f} L* at {dma[np.argmin(dy) + 1]:.2f} m" if len(idx) else ""))
    for ax, title in zip(axes, ("Core of the bar (middle fifth of its rows)", "Whole bar (all its rows)")):
        ax.set_facecolor("#fcfcfb")
        ax.set_title(title, loc="left", fontsize=11, color="#0b0b0b")
        ax.set_ylabel("brightness, L*", color="#52514e")
        ax.grid(True, color="#e6e5e0", lw=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors="#52514e")
    ax = axes[-1]
    ax.set_xscale("log")
    ax.set_xlim(sv.lv.FAR * 1.02, DNEAR * 0.85)
    ticks = [28, 20, 14, 10, 7, 5, 3, 2, 1.4, 1, 0.7, 0.5]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g}" for t in ticks])
    ax.set_xlabel("distance from the camera, m (the bar coming closer, left to right)", color="#52514e")
    axes[0].legend(frameon=False, loc="upper left")
    fig.suptitle("v3 vs v7: 6-frame moving average of the bar's brightness (faint: every two frames)",
                 x=0.01, ha="left", fontsize=12, color="#0b0b0b")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    print("wrote", path)

if __name__ == "__main__":
    import os
    if os.environ.get("ONLY") != "graph":
        video(sys.argv[1])
    if os.environ.get("ONLY") != "video":
        profile(sys.argv[2])
