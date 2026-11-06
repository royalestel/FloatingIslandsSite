#!/usr/bin/env python3
"""Preview v9: v8 (v3 + the white centre) without the bar seeming to grow
thicker and thinner.  With few brightness steps, each new step started on
the centre line and spread outward, so the bar's light gathered in the
middle (it looked thinner) then spread (thicker), over and over.  Here, for
each height and distance, several candidate patterns are made (v3's centre-
out error diffusion with its thresholds shifted and its error carried more
or less) and the one chosen whose spread of light across the bar (rms
width / height) matches the ideal round profile's, as well as its overall
brightness.  Side by side with v8, CRT; and the width measured over the
flight for v3, v8 and v9.

    python3 preview_v9.py video.mp4 graph.png
"""
import os, sys
import numpy as np
import swatch_loop_video as sv
import gen_cosmic as gc
import preview_v7 as v7
import preview_v8 as v8

LAD = v7.LADDER7
LUM = np.array([sv.LUM[k] for k in LAD])
POS = {k: i for i, k in enumerate(LAD)}
SHIFTS = np.linspace(-0.45, 0.45, 13)
CARRY = (0.0, 0.4, 0.8)
W_WIDTH = 6.0                              # weight of the width match against brightness
W_PREV = 10.0                              # weight of staying close to the last pattern's width
_last = {"w": None, "d": None}

def target_profile(h, d):
    """The ideal light of each row (v8's: v3's, the centre raised near in)."""
    cw, c3 = v8.core_white(d), gc.core_v3(d)
    out = []
    for j in range(h):
        r = 2 * (j + 0.5) / h - 1
        t = gc.row_v3(d, r)
        if cw > c3 * 1.0001 and abs(r) < v8.CORE_R:
            t += (cw - c3) * (1 - (r / v8.CORE_R) ** 2)
        out.append(t)
    return np.array(out)

def rms_width(l):
    y = np.arange(len(l)) - (len(l) - 1) / 2
    return np.sqrt((l * y * y).sum() / max(l.sum(), 1e-12)) / len(l)

def candidate(tgt, shift, carry):
    h = len(tgt)
    half = (h + 1) // 2
    lower, err, kmax = [], 0.0, len(LAD) - 1
    for i in range(half):
        j = h - half + i
        want = tgt[j] + err
        # thresholds shifted: compare against the steps moved by `shift` of a step
        idx = np.searchsorted(LUM, want)
        lo = max(0, min(idx - 1, len(LAD) - 1))
        hi = min(idx, len(LAD) - 1)
        if hi == lo:
            k = lo
        else:
            f = (want - LUM[lo]) / max(LUM[hi] - LUM[lo], 1e-9)
            k = hi if f > 0.5 + shift else lo
        k = min(k, kmax)
        kmax = k
        lower.append(LAD[k])
        err = carry * (want - LUM[k])
    upper = lower[::-1] if h % 2 == 0 else lower[:0:-1]
    return upper + lower

def ramp_v9(h, d):
    """Called along the flight (decreasing d): the width also kept close to
    the last pattern's, so it changes in small, rare steps."""
    if _last["d"] is not None and d > _last["d"] + 1.0:
        _last["w"] = None                        # a new flight
    tgt = target_profile(h, d)
    w0, m0 = rms_width(tgt), tgt.mean()
    best, bc, bw = None, np.inf, None
    for s in SHIFTS:
        for c in CARRY:
            r = candidate(tgt, s, c)
            l = np.array([sv.LUM[k] for k in r])
            w = rms_width(l)
            cost = abs(l.mean() - m0) / max(m0, 1e-6) + W_WIDTH * abs(w - w0)
            if _last["w"] is not None:
                cost += W_PREV * abs(w - _last["w"])
            if cost < bc:
                best, bc, bw = r, cost, w
    _last["w"], _last["d"] = bw, d
    return best

def video(path):
    v8.main(path, v8.ramp_v8, ramp_v9, ("v8", "v9"), "steady thickness")

def widths(rampf):
    """Over the flight: the bar's rms width / height, each frame's own pattern."""
    import loop_video as lv
    out, d = [], sv.lv.FAR
    cache = {}
    while d >= v7.DNEAR:
        h = max(2, min(gc.HMAX, lv.bar_lines(d)))
        key = (h, round(d * 10) / 10)
        if key not in cache:
            r = rampf(h, key[1])
            cache[key] = rms_width(np.array([sv.LUM[k] for k in r]))
        out.append((d, cache[key]))
        d -= v7.SPEED
    return np.array(out)

def graph(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 4.5))
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    for name, f, col in (("v3", gc.ramp_v3, "#1baf7a"), ("v8", v8.ramp_v8, "#eb6834"),
                         ("v9", ramp_v9, "#2a78d6")):
        w = widths(f)
        ax.plot(w[:, 0], w[:, 1], color=col, lw=2 if name == "v9" else 1.5, label=name)
        dw = np.abs(np.diff(w[:, 1]))
        print(f"{name}: width changes over 0.01: {(dw > 0.01).sum()}, largest {dw.max():.3f}")
    ax.set_xscale("log")
    ax.set_xlim(sv.lv.FAR * 1.02, v7.DNEAR * 0.85)
    ticks = [28, 20, 14, 10, 7, 5, 3, 2, 1.4, 1, 0.7, 0.5]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g}" for t in ticks])
    ax.set_xlabel("distance from the camera, m", color="#52514e")
    ax.set_ylabel("spread of the light / height", color="#52514e")
    ax.grid(True, color="#e6e5e0", lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False)
    ax.set_title("The bar's apparent thickness as it flies in (steady is good)", loc="left",
                 fontsize=11, color="#0b0b0b")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    print("wrote", path)

if __name__ == "__main__":
    graph(sys.argv[2])
    if os.environ.get("ONLY") != "graph":
        video(sys.argv[1])
