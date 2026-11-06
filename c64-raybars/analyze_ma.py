#!/usr/bin/env python3
"""analyze_onebar.py's profile with a 6-frame moving average: per frame,
the bar's rows (left of the ship) in linear light, the core (middle fifth)
and the whole bar; the light averaged over 6 frames (the flicker and the
frame-to-frame steps smoothed as the eye might), shown as L*, with the
two-frame values faint behind.  Writes analysis_ma.png.

    VARIANTS="v3,v3 + patterns,v6 (all swatches)" python3 analyze_ma.py
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import analyze_onebar as ao

def per_frame(variant):
    fr = ao.frames(variant)
    ds, core, bar = [], [], []
    for d, h, img in fr:
        lum = (img.astype(np.float64).mean(axis=1) / 65535) @ ao.LW
        c0, c1 = int(h * 0.4), max(int(h * 0.4) + 1, int(np.ceil(h * 0.6)))
        ds.append(d)
        core.append(lum[c0:c1].mean())
        bar.append(lum.mean())
    return np.array(ds), np.array(core), np.array(bar)

def avg(x, n):
    return np.convolve(x, np.ones(n) / n, mode="valid")

def main():
    variants = os.environ.get("VARIANTS", "v3,v3 + patterns,v6 (all swatches)").split(",")
    colours = ["#1baf7a", "#eb6834", "#2a78d6"]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")
    for vi, v in enumerate(variants):
        ds, core, bar = per_frame(v)
        for ax, y, what in ((axes[0], core, "core"), (axes[1], bar, "whole bar")):
            two = ao.lstar(avg(y, 2)[::2])
            ax.plot(avg(ds, 2)[::2], two, color=colours[vi], lw=1, alpha=0.25)
            ma = ao.lstar(avg(y, 6))
            dma = avg(ds, 6)
            ax.plot(dma, ma, color=colours[vi], lw=2, label=v)
            dy = np.diff(ma)
            idx = np.where(dy < -0.3)[0]
            print(f"{v:18s} {what:9s} 6-frame average: {len(idx)} drops of more than 0.3 L*"
                  + (f", largest {dy.min():.1f} L* at {dma[np.argmin(dy) + 1]:.2f} m" if len(idx) else ""))
    for ax, title in zip(axes, ("Core of the bar (middle fifth of its rows)",
                                "Whole bar (all its rows)")):
        ax.set_facecolor("#fcfcfb")
        ax.set_title(title, loc="left", fontsize=11, color="#0b0b0b")
        ax.set_ylabel("brightness, L*", color="#52514e")
        ax.grid(True, color="#e6e5e0", lw=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors="#52514e")
    ax = axes[-1]
    ax.set_xscale("log")
    ax.set_xlim(ao.sv.lv.FAR * 1.02, ao.DNEAR * 0.85)
    ticks = [28, 20, 14, 10, 7, 5, 3, 2, 1.4, 1, 0.7, 0.5]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g}" for t in ticks])
    ax.set_xlabel("distance from the camera, m (the bar coming closer, left to right)",
                  color="#52514e")
    axes[0].legend(frameon=False, loc="upper left")
    fig.suptitle("One bar flying in: 6-frame moving average of its brightness (faint: every two frames)",
                 x=0.01, ha="left", fontsize=12, color="#0b0b0b")
    fig.tight_layout()
    fig.savefig("analysis_ma.png", dpi=110)
    print("wrote analysis_ma.png")

if __name__ == "__main__":
    main()
