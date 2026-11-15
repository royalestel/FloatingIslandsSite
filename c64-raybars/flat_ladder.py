#!/usr/bin/env python3
"""Flat colours for the tilted bar segments (no ghost byte there: no cycles for it).

For each step of the cosmicstrings ladder (preview_v10.LAD) the target is what the eye sees of the real swatch: its colour with the
ghost byte's 1-bits black, averaged over both row parities and both frame parities (linear light).  The flat version is one palette
colour, or a pair A / B on alternate rows that swaps every frame (row 0: A on even frames, B on odd; row 1 the other way), whichever
is closest in CIELAB (linear RGB distance picked brown for a dark blue); flicker (the pair's lightness difference) is penalised; the upper half of the ladder (the bars' centres) may not come out
dimmer than 95% of its target.  The table goes into the swatch pages at +128 (even rows) / +160 (odd rows), per frame parity,
indexed like the colour entries by ladder position.

    python3 flat_ladder.py [preview.png]        (prints the table, writes a side-by-side preview)
"""
import sys
import numpy as np
import flyby3d as fb
import flicker as fl
import preview_v10 as v10

LW = np.array([0.2126, 0.7152, 0.0722])
LP = fl.lin(fb.C64RGB)
LUM = LP @ LW
LAM = 1.0                     # flicker penalty
LUMW = 4.0                    # extra weight on the light (the hue alone picked a half-bright blue for a light-blue step)
CENTRE_FROM = 0.5             # ladder fraction from which a step must not come out dimmer
CENTRE_MIN = 0.95
ALL_MIN = 0.8                 # no step dimmer than this (a light-blue ghost step came out at 0.68)
FAINT = 0.03                  # steps fainter than this: black + one colour (the faintest otherwise picked a brown / blue pair 9x too bright)

def lab(l):
    """linear sRGB -> CIELAB (D65)"""
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    x = (m @ np.asarray(l, float)) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(x > 0.008856, np.cbrt(x), 7.787 * x + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])
LABP = np.array([lab(c) for c in LP])
LAMF = 0.3                    # flicker penalty: the pair's frame-to-frame light swing beyond the real swatch's own (x100, squared)

def real_rows(k, p):
    """the swatch's two rows on frame parity p: 8 pixels each, C64 colour indices (-1 = ghost black)"""
    out = []
    for rp in (0, 1):
        c = v10.colour(k, rp, p)
        g = v10.ghost(k, rp, p)
        out.append([0 if (g >> (7 - x)) & 1 else c for x in range(8)])
    return out

def target(k):
    return np.mean([LP[c] for p in (0, 1) for row in real_rows(k, p) for c in row], axis=0)

def real_flicker(k):
    """the real swatch's frame-to-frame light swing, per row, averaged (flicker pairs swing; ghost patterns barely)"""
    sw = []
    for rp in (0, 1):
        l = [np.mean([LP[c] for c in real_rows(k, p)[rp]], axis=0) @ LW for p in (0, 1)]
        sw.append(abs(l[0] - l[1]))
    return float(np.mean(sw))

def choose(t, centre, nonblack, rf=0.0):
    best, bc = None, 1e9
    for a in range(16):
        for b in range(a, 16):
            if nonblack and a == b == 0:
                continue                               # (a faint step must stay visible: the far bars)
            v = (LP[a] + LP[b]) / 2
            if v @ LW < (CENTRE_MIN if centre else ALL_MIN) * (t @ LW):
                continue
            if nonblack and t @ LW < FAINT and a != 0:
                continue
            c = ((lab(v) - lab(t)) ** 2).sum() + LAMF * (100 * max(0.0, abs(LUM[a] - LUM[b]) - rf)) ** 2
            if c < bc:
                best, bc = (a, b), c
    if best is None:                                   # nothing bright enough: the brightest
        best = max(((a, b) for a in range(16) for b in range(a, 16)), key=lambda ab: LUM[ab[0]] + LUM[ab[1]])
    return best

def flat_pairs():
    n = len(v10.LAD)
    return [choose(target(k), i >= CENTRE_FROM * n, i > 0, real_flicker(k)) for i, k in enumerate(v10.LAD)]

def flat_colour(pair, rp, p):
    a, b = pair
    return a if (rp + p) % 2 == 0 else b

def tables():
    """{(p): {offset: byte}}: +128 + 32 * rp + ladder position"""
    pairs = flat_pairs()
    return {p: {128 + 32 * rp + i: flat_colour(pr, rp, p) for i, pr in enumerate(pairs) for rp in (0, 1)} for p in (0, 1)}

def main(out=None):
    pairs = flat_pairs()
    print(" pos swatch  target   flat     (A,B)   flicker (real swatch's)")
    for i, (k, pr) in enumerate(zip(v10.LAD, pairs)):
        t = target(k) @ LW
        f = (LUM[pr[0]] + LUM[pr[1]]) / 2
        print(f" {i:3} {k:5}  {t:.4f}  {f:.4f} {f / max(t, 1e-6):5.2f}x  {pr}  {abs(LUM[pr[0]] - LUM[pr[1]]):.3f} ({real_flicker(k):.3f})")
    if out:
        from PIL import Image
        S, W = 4, 24
        img = np.zeros((len(pairs) * 10 * S, 3 * W * S, 3), np.uint8)
        un = lambda l: (np.clip(l, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)
        for i, (k, pr) in enumerate(zip(v10.LAD, pairs)):
            y = i * 10 * S
            for p in (0, 1):                               # the real swatch, frame p (left: averaged over the two)
                pass
            real = np.zeros((8, W, 3)); flat = np.zeros((8, W, 3))
            for p in (0, 1):
                rows = real_rows(k, p)
                for r in range(8):
                    for x in range(W):
                        real[r, x] += LP[rows[r & 1][x % 8]] / 2
                        flat[r, x] += LP[flat_colour(pr, r & 1, p)] / 2
            for j, blk in enumerate((real, flat)):
                im = np.repeat(np.repeat(un(blk), S, 0), S, 1)
                img[y:y + 8 * S, j * (W + W // 2) * S:j * (W + W // 2) * S + W * S] = im
        Image.fromarray(img).save(out)
        print("wrote", out)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
