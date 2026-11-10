#!/usr/bin/env python3
"""MOCK (python only): part 1a-1b with three extra bars that appear at 16 s (frame 960, where the music gets loud).
They sit between the three circling bars (midpoints of each pair) and blink on/off three times (6 frames each) before they stay.
From one second after the loud beat (frame 1198) every other bar of the circle (the three original ones, ring positions 0, 2, 4) turns into the
flat dark red checkerboard swatch (red ramp swatch #4: C64 red, a black checkerboard that alternates by row and by frame) on EVERY row.
    python3 mock_part1_flicker.py out.mp4 [last_frame]"""
import os, sys
os.environ.setdefault("SPLITS", "6")
import part1 as p1

T0, N_BLINK = 960, 3
BEAT = 1218                             # 20.3 s: the red flicker starts here (frame 1218)
SOLID_RED = 11                          # red_ramp_saved swatch #11: flat C64 red, no checkerboard (lines where two red bars overlap)
RED_SWATCH = 4                          # red_ramp_saved swatch #4: flat red, black checkerboard alternating by row and frame                    # 16 s; three off/on blinks, one per two frames

def extra_visible(t):
    """off, on, off, on, off, on: every other frame, three times; then they stay"""
    u = t - T0
    if u < 0: return False
    if u < 8: return (u // 2) % 2 == 0               # on 2, off 2, on 2, off 2
    return True

_orig = p1.bars_all

def bars_all(t):
    """the three circling bars, plus three more with the SAME motion (slide / circle in depth) but a phase shifted by 1/3 and 2/3 of
    a turn, so they sit between the existing three"""
    bars = _orig(t)
    if t >= p1.T_STACK or not extra_visible(t):
        return bars
    import math
    sc = p1.sc
    th0 = sc.theta
    extra = []
    for shift in (math.pi / 3,):                      # one shift: its three bars sit at phases 1/3, 1/3+1/3 and 1/3+2/3 of the way round
        sc.theta = (lambda sh: (lambda x: th0(x) + sh))(shift)
        try:
            extra += sc.bars(t)[:3]
        finally:
            sc.theta = th0
    return bars + extra
p1.bars_all = bars_all

import numpy as np
import red_ramp_saved as rr
import ghost_preview as gp

def swatch_row(ramp, k, par, f):
    """320 colours of a row drawn with swatch k of the blue ramp (gp) or the red ramp (rr; part 2's)"""
    if ramp == "blue":
        return gp.draw([k] * gp.SEGS, par, f)
    row = np.full(gp.W, rr.colour(k, par, f), int)
    g = rr.ghost(k, par, f)
    if g:
        x = np.arange(gp.W)
        row[((g >> (7 - x % 8)) & 1) == 1] = 0
    return row

def red_row(par, f):
    return swatch_row("red", RED_SWATCH, par, f)

def red_on(t):
    """red 2 frames, blue ramp 2, red 2, blue ramp 2, then red for good"""
    u = t - BEAT
    if u < 0: return False
    if u < 8: return (u // 2) % 2 == 0
    return True

def _depth_range():
    """nearest and farthest depth (z) the circling bars reach in the part where they are red"""
    zs = [b[0] for t in range(BEAT, 1800, 4) for b in p1.sc.bars(t)[:3]]
    return min(zs), max(zs)
ZMIN, ZMAX = _depth_range()

def red_swatch_for(z):
    """red ramp swatch by depth: nearest = #4, then #3, #2, farthest = #1 (receding steps 4->3->2->1, returning 1->2->3->4)"""
    d = (z - ZMIN) / max(ZMAX - ZMIN, 1e-6)
    return int(np.clip(4 - int(d * 4), 1, 4))

def red_state(t, idx, b):
    """is bar idx red at frame t?  Red from the first flicker (red_on) until it lines up in the stack; then it flickers to blue:
    2 blue, 2 red, 2 blue, 2 red, then blue for good.  Each red bar lines up 10 frames after the one before it."""
    if t < p1.T_STACK:
        if idx not in (0, 1, 2): return False
        start = p1.T_STACK + 10 * idx
    else:
        m = b[3] if len(b) > 3 else -1
        if m not in (3, 4, 5): return False
        start = p1.T_STACK + 10 * (m - 3)
    if t < start: return red_on(t)
    u = t - start
    if u < 8: return (u // 2) % 2 == 1                 # blue, red, blue, red
    return False                                       # blue for good

def rows_for(t):
    """Two layers.  blue[y] = swatch of the nearest blue bar on line y (0 = none); redcov[y] = a red bar covers line y.
    The red bars are TRANSPARENT: where a red bar overlaps a blue bar, the line shows the blue bar's swatch from the red ramp
    (same swatch number); where a red bar is alone, the flat red checkerboard; where only a blue bar is, the blue ramp."""
    bars = p1.bars_all(t)
    chosen = {i for i, b in enumerate(bars) if red_state(t, i, b)}
    H = p1.H
    blue = np.zeros(H, int); bpar = np.arange(H) & 1
    redcov = np.zeros(H, bool); rpar = np.arange(H) & 1; redk = np.full(H, RED_SWATCH, int); redn = np.zeros(H, int)
    for idx in sorted(range(len(bars)), key=lambda i: -bars[i][2]):       # far first
        b = bars[idx]
        z, yc = max(b[0], 0.6), b[1]
        T = max(1, min(p1.TMAX, int(round(2 * p1.F * p1.R / z))))
        if len(b) > 3:
            e_i = b[5] if len(b) > 5 else b[3]
            T = gp.BT(T, gp.edge_level(e_i), e_i, b[4])                 # the stack bars have their own edge swatch (as part1.frame_list)
        y0 = int(round(yc - T / 2))
        if y0 >= H or y0 + T <= 0 or not any(gp.PROF[T][max(0, -y0):H - y0]): continue
        prof = gp.PROF[T]
        for i in range(int(T)):
            y = y0 + i
            if not (0 <= y < H): continue
            par = y & 1 if t >= p1.T_BLEND0 + p1.BLEND_LEN else min(i, int(T) - 1 - i) & 1
            if idx in chosen:
                redcov[y] = True; rpar[y] = par; redk[y] = red_swatch_for(z); redn[y] += 1
            elif prof[i]:
                blue[y] = prof[i]; bpar[y] = par
    return blue, redcov, bpar, rpar, redk, redn

def render(out, last, crt=False, start=0):
    v = p1.iv.Video(out, p1.W * 3, p1.H * 3)
    for f in range(start, last):
        blue, redcov, bpar, rpar, redk, redn = rows_for(f)
        tint = redcov & (blue > 0)                        # a red bar over a blue bar
        redonly = redcov & (blue == 0)
        col = blue.copy()
        g = p1.dim(f)
        if g < 1.0:                                       # the dimming of part 1 (copied from part1.main), on the blue layer
            u = (1.0 - g) / (1.0 - p1.DIM[1][1])
            cen = np.zeros(len(col), bool); y = 0
            while y < len(col):
                if col[y]:
                    y1 = y
                    while y1 < len(col) and col[y1]: y1 += 1
                    if y1 - y >= 8: m = (y + y1) // 2; cen[m - 2:m + 2] = True
                    y = y1
                else: y += 1
            def dimk(k, c):
                if not k: return 0
                v_ = k * g
                if k >= 16: v_ = max(v_, k * (1 - u) + (11 + k - 16 + (1 if c else 0)) * u)
                return max(1, int(round(v_)))
            col = np.array([dimk(k, c) for k, c in zip(col, cen)])
        rows = []
        for y in range(p1.H):
            if redn[y] >= 2: rows.append(swatch_row("red", SOLID_RED, int(rpar[y]), f))   # two red bars overlap: solid red
            elif tint[y]:   rows.append(swatch_row("red", min(int(col[y]), len(rr.RAMP_L) - 1), int(bpar[y]), f))   # the blue bar's swatch, red ramp
            elif redonly[y]: rows.append(swatch_row("red", int(redk[y]), int(rpar[y]), f))
            else:         rows.append(swatch_row("blue", int(col[y]), int(bpar[y]), f))
        img = p1.fb.C64RGB[np.array(rows)].astype(np.uint8)
        if crt: v.add(p1.lv.crt_look(img, 3))
        else:                                                                 # plain 3x nearest-neighbour (no CRT effect)
            from PIL import Image
            v.add(Image.fromarray(np.repeat(np.repeat(img, 3, axis=0), 3, axis=1)))
    v.close(); print("wrote", out, last, "frames")

if __name__ == "__main__":
    out = sys.argv[1]
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 1240
    render(out, last, crt=bool(os.environ.get("CRT")), start=int(os.environ.get("START", "0")))
