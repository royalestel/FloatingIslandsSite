#!/usr/bin/env python3
"""Profile one bar's brightness as it flies from 28 m to the camera
(onebar_video.py's frames, rendered directly, not from a video).

Each frame: the bar's rows, left of the ship (columns 0..119), in linear
light, 16-bit.  Every two frames are combined (averaged: the flicker pairs
and on/off patterns become their steady brightness) and the crop averaged
across the row (a horizontal blur), then:
  core: the middle fifth of the bar's rows,  bar: all its rows.
Brightness as CIE L* of the mean luminance.  Both colour schemes: "now"
(gen_cosmic.ramp_round, 15-step ladder) and "all 29"
(gen_cosmic.ramp_smooth).  Writes analysis_onebar.png and prints the
places where brightness drops as the bar comes closer.

    python3 analyze_onebar.py
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import flyby3d as fb
import loop_video as lv
import swatch_loop_video as sv
import gen_cosmic as gc
gc.ROUND = True

SPEED = 0.045
DNEAR = 2 * sv.lv.R_BAR * gc.F / (gc.HMAX + 0.45)
BELOW = 0.3
LW = np.array([0.2126, 0.7152, 0.0722])
LIN16 = np.round(((np.arange(256) / 255.0) ** 2.2) * 65535).astype(np.uint16)

def lstar(y):
    y = np.asarray(y, float)
    return np.where(y > 216 / 24389, 116 * np.cbrt(y) - 16, y * 24389 / 27)

def frames(variant):
    """Per frame: distance, and the bar rows' linear RGB (16 bit), cols 0..119."""
    tabs = [np.frombuffer(t, np.uint8) for t in gc.swatch_tables()]
    rampf = gc.ramp_round if variant == "now" else gc.ramp_smooth
    cache = {}
    x = np.arange(120)
    d, f, out = sv.lv.FAR, 0, []
    while d >= DNEAR:
        p = f & 1
        h = max(2, min(gc.HMAX, lv.bar_lines(d)))
        key = (h, round(d * 2) / 2)
        if key not in cache:
            cache[key] = rampf(h, key[1])
        top = int(round((2 * gc.CYL - 2 * gc.F * BELOW / d - h) / 2))
        rows = np.zeros((h, 120), int)
        for j in range(h):
            r = top + j + 11
            k = cache[key][j]
            t = tabs[p]
            rows[j] = t[32 * (r & 1) + k]
            g = t[64 + 32 * (r & 1) + k]
            if g:
                rows[j, ((g >> (7 - x % 8)) & 1) == 1] = 0
        rgb = fb.C64RGB[rows].astype(np.uint8)
        out.append((d, h, LIN16[rgb]))
        d -= SPEED
        f += 1
    return out

def profile(variant):
    fr = frames(variant)
    ds, core, bar = [], [], []
    for (d0, h0, a), (d1, h1, b) in zip(fr[0::2], fr[1::2]):
        m = []
        for h, img in ((h0, a), (h1, b)):
            rowlin = img.astype(np.float64).mean(axis=1) / 65535      # row average (blur)
            lum = rowlin @ LW
            c0, c1 = int(h * 0.4), max(int(h * 0.4) + 1, int(np.ceil(h * 0.6)))
            m.append((lum[c0:c1].mean(), lum.mean()))
        ds.append((d0 + d1) / 2)
        core.append(lstar(np.mean([v[0] for v in m])))
        bar.append(lstar(np.mean([v[1] for v in m])))
    return np.array(ds), np.array(core), np.array(bar)

def drops(ds, y, name, what):
    dy = np.diff(y)                       # distance falls along the arrays
    idx = np.where(dy < -0.5)[0]
    print(f"{name:7s} {what}: {len(idx)} drops of more than 0.5 L*", end="")
    if len(idx):
        k = idx[np.argmin(dy[idx])]
        print(f"; largest {dy[k]:.1f} L* at {ds[k + 1]:.2f} m", end="")
    print(f"; largest rise {dy.max():.1f} L* at {ds[np.argmax(dy) + 1]:.2f} m")
    return idx

def main():
    res = {v: profile(v) for v in ("now", "all 29")}
    colours = {"now": "#2a78d6", "all 29": "#eb6834"}
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")
    for ax, (title, col) in zip(axes, (("Core of the bar (middle fifth of its rows)", 1),
                                       ("Whole bar (all its rows)", 2))):
        ax.set_facecolor("#fcfcfb")
        for v, (ds, core, bar) in res.items():
            y = (core, bar)[col - 1]
            ax.plot(ds, y, color=colours[v], lw=2, label=v)
            idx = drops(ds, y, v, title.split(" (")[0].lower())
            ax.plot(ds[idx + 1], y[idx + 1], "o", ms=5, mfc="none", mec=colours[v], mew=1.5)
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
    ax.set_xlabel("distance from the camera, m (the bar coming closer, left to right)",
                  color="#52514e")
    axes[0].legend(frameon=False, loc="upper left")
    fig.suptitle("One bar flying in: brightness every two frames (circles: a drop of more "
                 "than 0.5 L*)", x=0.01, ha="left", fontsize=12, color="#0b0b0b")
    fig.tight_layout()
    fig.savefig("analysis_onebar.png", dpi=110)
    print("wrote analysis_onebar.png")

if __name__ == "__main__":
    main()
