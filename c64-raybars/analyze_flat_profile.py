#!/usr/bin/env python3
"""How well can flat palette colours (no ghost byte) reproduce the row profile of real cosmicstrings bars?
Reads VICE frames, cuts every bar into rows (linear-light mean RGB per row), maps each row to (a) the nearest single palette colour,
(b) the best 50/50 pair (two colours alternating rows, swapped every frame), (c) the same restricted to black + one colour,
and reports centre / edge brightness and centre-to-edge contrast kept.   python3 analyze_flat_profile.py frame.png ..."""
import sys, glob
import numpy as np
from PIL import Image
PAL = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in
    "000000 ffffff 813338 75cec8 8e3c97 56ac4d 2e2c9b edf171 8e5029 553800 c46c71 4a4a4a 7b7b7b a9ff9f 706deb b2b2b2".split()], float)
lin = lambda c: (np.asarray(c, float) / 255) ** 2.2
LW = np.array([0.2126, 0.7152, 0.0722])
LP = lin(PAL); LUM = LP @ LW
PAIR = (LP[:, None, :] + LP[None, :, :]) / 2
KEEP = np.r_[40:150, 230:344]
def bars(path):
    img = np.array(Image.open(path).convert("RGB")).astype(float)
    rl = lin(img[:, KEEP]).mean(axis=1) @ LW
    on = rl > 0.004
    run = None
    for y in range(131):
        if on[y] and run is None: run = y
        if (not on[y] or y == 130) and run is not None:
            if y - run >= 6: yield np.array([lin(img[r, 40:344]).mean(axis=0) for r in range(run, y)])
            run = None
def best(t, mode):
    if mode == "single":
        i = int(np.argmin(((LP - t) ** 2).sum(axis=1))); return LP[i]
    c = ((PAIR - t) ** 2).sum(axis=2)
    if mode == "black": c[1:, :] = 1e9
    a, b = np.unravel_index(np.argmin(c), (16, 16)); return PAIR[a, b]
rows = []
for p in sys.argv[1:]:
    for t in bars(p):
        h = len(t); lt = t @ LW
        c0, c1 = h // 2 - 1 if h > 3 else 0, h // 2 + 1                 # centre rows
        d = {"n": h, "mean": lt.mean(), "peak": lt.max(), "edge": (lt[0] + lt[-1]) / 2, "centre": lt[c0:c1 + 1].mean()}
        for m in ("single", "pair", "black"):
            f = np.array([best(r, m) for r in t]) @ LW
            d[m] = dict(mean=f.mean(), peak=f.max(), centre=f[c0:c1 + 1].mean(), edge=(f[0] + f[-1]) / 2,
                        rms=float(np.sqrt(((f - lt) ** 2).mean())))
        rows.append(d)
print("bars analysed:", len(rows))
def table(sel, name):
    sel = [r for r in rows if sel(r)]
    if not sel: return
    print(f"\n{name}: {len(sel)} bars, mean height {np.mean([r['n'] for r in sel]):.1f} rows, target mean {np.mean([r['mean'] for r in sel]):.3f}, "
          f"centre {np.mean([r['centre'] for r in sel]):.3f}, edge {np.mean([r['edge'] for r in sel]):.3f}")
    print("   method   mean   centre  edge   centre/edge   rms err(lum)")
    ce = lambda r, k: (r[k]["centre"] / max(r[k]["edge"], 1e-3)) if k != "t" else r["centre"] / max(r["edge"], 1e-3)
    print("   target  %.3f  %.3f  %.3f   %.2f" % (np.mean([r["mean"] for r in sel]), np.mean([r["centre"] for r in sel]), np.mean([r["edge"] for r in sel]), np.mean([ce(r, "t") for r in sel])))
    for m in ("single", "pair", "black"):
        print("   %-7s %.3f  %.3f  %.3f   %.2f          %.3f" % (m, *(np.mean([r[m][k] for r in sel]) for k in ("mean", "centre", "edge")),
              np.mean([ce(r, m) for r in sel]), np.mean([r[m]["rms"] for r in sel])))
table(lambda r: True, "ALL bars")
table(lambda r: r["mean"] < 0.06, "dim bars (mean < 0.06)")
table(lambda r: 0.06 <= r["mean"] < 0.2, "mid bars")
table(lambda r: r["mean"] >= 0.2, "bright bars (mean >= 0.2)")
table(lambda r: r["n"] <= 12, "short bars (<= 12 rows)")
table(lambda r: r["n"] > 12, "tall bars (> 12 rows)")

# ---- a per-row hybrid: single / pair / black+colour chosen row by row; centre rows may not be dimmer than the target ---------------
def cands(t, centre):
    out = []
    for i in range(16):                                           # single colour: flicker 0
        out.append((LP[i], 0.0))
    for a in range(16):
        for b in range(a, 16):
            out.append((PAIR[a, b], abs(LUM[a] - LUM[b])))        # two colours, swapped every frame: flicker = their luminance difference
    return out
def hybrid(t, centre, lam):
    lt = t @ LW; best, bc = None, 1e9
    for v, fl in cands(t, centre):
        lv = v @ LW
        if centre and lv < 0.95 * lt: continue                    # centre rows: never dimmer than the bar's
        c = ((v - t) ** 2).sum() + lam * fl * fl
        if c < bc: best, bc, bf = v, c, fl
    if best is None: best, bf = max(cands(t, centre), key=lambda x: x[0] @ LW)[0], 0.0
    return best, bf
print("\n--- per-row hybrid (single or pair by row, centre rows not dimmer than target) ---")
for lam in (0.0, 0.3, 1.0):
    agg = dict(mean=[], centre=[], edge=[], ce=[], rms=[], flick=[], dimc=[])
    for p in sys.argv[1:]:
        for t in bars(p):
            h = len(t); lt = t @ LW
            c0, c1 = (h // 2 - 1 if h > 3 else 0), h // 2 + 1
            res = [hybrid(r, c0 <= j <= c1, lam) for j, r in enumerate(t)]
            f = np.array([v for v, _ in res]) @ LW; fk = np.array([k for _, k in res])
            agg["mean"].append(f.mean()); agg["centre"].append(f[c0:c1 + 1].mean()); agg["edge"].append((f[0] + f[-1]) / 2)
            agg["ce"].append(agg["centre"][-1] / max(agg["edge"][-1], 1e-3)); agg["rms"].append(float(np.sqrt(((f - lt) ** 2).mean())))
            agg["flick"].append(fk[c0:c1 + 1].mean()); agg["dimc"].append(float(agg["centre"][-1] < 0.9 * lt[c0:c1 + 1].mean()))
    print("lambda %.1f: mean %.3f centre %.3f edge %.3f centre/edge %.2f rms %.3f  centre flicker amp %.3f  bars with dim centre %.0f%%" %
          (lam, *(np.mean(agg[k]) for k in ("mean", "centre", "edge", "ce", "rms", "flick")), 100 * np.mean(agg["dimc"])))
for m in ("single", "pair", "black"):
    n = np.mean([float(r[m]["centre"] < 0.9 * r["centre"]) for r in rows])
    print("bars whose centre is >10%% dimmer than target, %-6s: %.0f%%" % (m, 100 * n))
