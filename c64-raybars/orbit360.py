#!/usr/bin/env python3
"""Mockup: the ship flying through gold bars, over and under them, while
the camera orbits 360 degrees round it, starting and ending behind it.
C64 version only, CRT look, 60 fps, one C64 frame per video frame.

* World: the ship flies along z at 0.045 m a frame (the game's base speed).
  Gold bars (radius 0.12 m, along x, endless) every SPACING m,
  dimmed by distance in 4 steps (LEVELS) and not drawn past 16 m,, alternately
  below and above the ship: the near edge 10 lines from the ship's centre
  at 3 m (0.27 m from it), some further out (0.6 m).
* Camera: 3 m from the ship, at its height, orbiting it (yaw), looking at
  it.  HOLD frames behind the ship, a full turn over TURN frames, HOLD more.
* Bars, algorithmically (orbit_algo.py): each bar is two edge lines on the
  screen; each of the 6 raster-split segments takes every bar's top and
  bottom at its centre column, the nearest bar in front, and colours from
  the gold gradient stretched over that height (ramp by height).
* Ship: big_ship.py's two-sprite ship (no nose light), only its two engine
  pods' exhausts glowing, the glow colour white and cyan on alternate frames
  so the engines flicker; antialiased with a pair of frames shown in turn
  (big_ship.pair's rules).  One pair per YAWSTEPS directions, rendered in
  perspective from the orbit camera (as the C64 would store them).

    python3 orbit360.py out.mp4
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import orbit_shots as o
import orbit_algo as oa

W, H, F, CY, SS = fb.W, fb.H, fb.F, fb.CY, fb.SS
SPEED, SPACING = 0.045, 2.5
NEAR = 10 / F * o.ZS + o.R                       # 0.27 m: the near edge 10 lines off at 3 m
HEIGHTS = [-NEAR, NEAR, -0.6, NEAR, -NEAR, 0.6]  # bar centres (ship at 0), repeating
HOLD, TURN = 60, 2880
YAWSTEPS = 128
_SPR = {}
LEVELS = [(5.0, 1.0), (8.0, 0.7), (12.0, 0.45), (16.0, 0.25)]   # (up to this depth, brightness)
_RAMPS = {}

def ramp(h, b):
    """The gold gradient at brightness b stretched over h lines (C64 colours)."""
    if (h, b) not in _RAMPS:
        g = o.GOLD48 * b
        out = []
        for j in range(h):
            a, c = 48 * j / h, 48 * (j + 1) / h
            xs = np.linspace(a, c, 16, endpoint=False) + (c - a) / 32
            out.append(int(fb.to_c64(g[np.clip(xs.astype(int), 0, 47)].mean(0)[None])[0]))
        _RAMPS[(h, b)] = out
    return _RAMPS[(h, b)]

def level(d):
    for dmax, b in LEVELS:
        if d <= dmax:
            return b
    return None

def edges(yaw, yc, barz):
    keep = o.YC
    o.YC = yc
    try:
        return oa.edges(yaw, barz)
    finally:
        o.YC = keep

def depth_at(e, xs):
    c0, c1 = e
    k = (xs - W / 2) / F
    den = c1[0] - k * c1[2]
    if abs(den) < 1e-12:
        return None
    t = -(c0[0] - k * c0[2]) / den
    return (c0 + t * c1)[2]

SHIPSCALE = 1.5                                  # the two-sprite ship (big_ship.py): 1.5 x the single one
GLOW = (1, 3)                                    # the engines' colour ($D025) by frame: white, cyan

def ship_model():
    """big_ship.py's model (no nose light) with only the two engine pods'
    exhausts glowing: the main nozzle's glow is dropped (trim)."""
    import big_ship
    out = []
    for poly, kind in big_ship.model():
        if kind == "glow" and abs(sum(p[0] for p in poly) / len(poly)) < 1.0:
            kind = "trim"
        out.append((poly, kind))
    return out

def counts(yaw, x0=96, x1=224, y0=78, y1=120):
    """Sample counts per multicolour pixel (8 x 4 samples) of the ship seen
    from the orbit camera, classes 0 none, 1 shadowed hull (and the dark
    canopy), 2 lit hull and trim, 3 the engines' glow: (rows, cols, 4)."""
    import ship3d
    sxn, syn = ship3d.SX, ship3d.SY                  # 8 x 4 per multicolour pixel
    w, h = (x1 - x0) // 2, y1 - y0
    xs = np.arange(w * sxn) + 0.5
    ys = np.arange(h * syn) + 0.5
    px, py = np.meshgrid(x0 + xs * 2 / sxn, y0 + ys / syn)
    zb = np.full(px.shape, np.inf)
    cls = np.zeros(px.shape, int)
    s = 0.36 / 23.6 * SHIPSCALE
    Rm, cam = o.rot(yaw), o.camera(yaw)
    L = Rm @ (np.array(ship3d.LIGHT, float) / np.linalg.norm(ship3d.LIGHT))
    for poly, kind in ship_model():
        Pw = np.array([(x * s, y * s, o.ZS + z * s) for x, y, z in poly])
        P = (Pw - cam) @ Rm.T
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if np.linalg.norm(n) < 1e-12:
            continue
        n /= np.linalg.norm(n)
        if n @ P[0] > 0:
            n = -n
        c = 3 if kind == "glow" else 1 if kind == "dark" else \
            2 if kind == "trim" or n @ L > 0.55 else 1
        Q = np.column_stack([P[:, 0] / P[:, 2] * F + W / 2, CY + 0.5 - P[:, 1] / P[:, 2] * F, P[:, 2]])
        for k in range(1, len(Q) - 1):
            a, b, cc = Q[0], Q[k], Q[k + 1]
            dd = (b[1] - cc[1]) * (a[0] - cc[0]) + (cc[0] - b[0]) * (a[1] - cc[1])
            if abs(dd) < 1e-12:
                continue
            w0 = ((b[1] - cc[1]) * (px - cc[0]) + (cc[0] - b[0]) * (py - cc[1])) / dd
            w1 = ((cc[1] - a[1]) * (px - cc[0]) + (a[0] - cc[0]) * (py - cc[1])) / dd
            w2 = 1 - w0 - w1
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            iz = w0 / a[2] + w1 / b[2] + w2 / cc[2]
            z = np.where(inside, 1 / np.maximum(iz, 1e-9), np.inf)
            m = z < zb
            zb[m] = z[m]
            cls[m] = c
    out = np.zeros((h, w, 4), int)
    for k in range(4):
        out[..., k] = (cls == k).reshape(h, syn, w, sxn).sum(axis=(1, 3))
    return out, (x0, y0)

def sprite(yaw):
    """The ship's antialiased pair of sprite frames at the nearest of
    YAWSTEPS directions (big_ship.pair's rules: covered pixels lit in both
    frames, half covered ones in one frame in a checkerboard, pixels split
    between shadowed and lit hull alternating), as [{(row, col): class}] x 2."""
    import big_ship
    q = round(yaw / (360 / YAWSTEPS)) % YAWSTEPS
    if q not in _SPR:
        cn, (x0, y0) = counts(q * 360 / YAWSTEPS)
        f0, f1 = big_ship.pair_from_counts(cn)
        _SPR[q] = []
        for fr in (f0, f1):
            _SPR[q].append({(y0 + r, x0 + 2 * c): int(fr[r, c]) for r, c in zip(*np.nonzero(fr))})
        cols = np.nonzero((f0 | f1).any(0))[0]
        WIDTHS[q] = cols.max() - cols.min() + 1 if len(cols) else 0
    return _SPR[q]

WIDTHS = {}
SHIPCOL = {1: 4, 2: 14}                          # %01 purple, %10 light blue; %11 GLOW by frame

SEG_FRAME = (o.SEG, [0, 64, 128, 192, 256, 320])   # frame 0: GOLDSHIP's 6 segments; frame 1: 5 of 64

def frame(yaw, zship, p=0):
    img = np.zeros((H, W), int)
    k0 = math.floor((zship - 8) / SPACING)
    bars = []
    for k in range(k0, k0 + int(20 / SPACING) + 2):
        barz = o.ZS + k * SPACING - zship
        yc = HEIGHTS[k % len(HEIGHTS)]
        bars.append(edges(yaw, yc, barz))
    seg = SEG_FRAME[p & 1]                           # option D: the splits move 32 pixels over on alternate frames
    for (x0, x1), xm in zip(zip(seg, seg[1:]), [(a + b) / 2 for a, b in zip(seg, seg[1:])]):
        spans = []
        for es in bars:
            ys = [oa.edge_y(e, xm) for e in es]
            if None in ys:
                continue
            top, bot = min(ys), max(ys)
            r0, r1 = math.ceil(top - 0.5), math.floor(bot - 0.5)
            if r1 < r0 or r1 < 0 or r0 >= H:
                continue
            d = depth_at(es[0], xm)
            if d is None or level(d) is None:
                continue
            spans.append((d, r0, r1))
        for d, r0, r1 in sorted(spans, reverse=True):   # far first, near over it
            h = r1 - r0 + 1
            rp = ramp(min(h, 2000), level(d))
            for j in range(max(0, -r0), min(h, H - r0)):
                img[r0 + j, x0:x1] = rp[j]
    for (r, c), k in sprite(yaw)[p].items():
        img[r, c:c + 2] = GLOW[p] if k == 3 else SHIPCOL[k]
    return img

FAST_FROM, FAST_TO = 21.0, 159.0                 # twice as fast from here to here (and mirrored: 201..339)

def speedup(yaw):
    """The orbit's speed factor at this angle: 1 behind and in front of the
    ship, 2 between FAST_FROM and FAST_TO degrees (and 180 + the same),
    faded smoothly (a cosine) between the two."""
    a = yaw % 180.0
    if a < FAST_FROM:
        k = 0.5 - 0.5 * math.cos(math.pi * a / FAST_FROM)
    elif a > FAST_TO:
        k = 0.5 - 0.5 * math.cos(math.pi * (180.0 - a) / (180.0 - FAST_TO))
    else:
        k = 1.0
    return 1.0 + k

def yaw_table(turn=TURN, steps=40000):
    """frame (from the start of the turn) -> yaw: the eased orbit (a cosine
    in time, the speed zero at both ends) with its speed multiplied by
    speedup(yaw): elapsed time = turn * integral du / speedup(yaw(u))."""
    u = np.linspace(0, 1, steps + 1)
    th = 360 * (0.5 - 0.5 * np.cos(np.pi * u))
    g = np.array([speedup(x) for x in th])
    t = np.concatenate([[0], np.cumsum(0.5 * (1 / g[1:] + 1 / g[:-1]) * np.diff(u))]) * turn
    return t, th

def main(path):
    Z = 3
    font, small = fl.fonts()
    v = iv.Video(path, W * Z + 32, H * Z + 50)
    tt, th = yaw_table()
    turn = int(round(tt[-1]))
    n = HOLD + turn + HOLD
    print("turn", turn, "frames (was", TURN, ")", flush=True)
    for f in range(n):
        yaw = float(np.interp(min(max(f - HOLD, 0), turn), tt, th))   # eased in and out
        img = frame(yaw % 360, f * SPEED, f & 1)
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), f"C64 mockup: camera orbiting the ship {yaw:5.1f} degrees   "
                f"raster splits (6 a line) + sprite   CRT", fill=(170, 176, 210), font=small)
        canvas.paste(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z), (16, 34))
        v.add(canvas)
        if f % 60 == 0:
            print("frame", f, "of", n, "sprites", len(_SPR), flush=True)
    v.close()
    print("wrote", path, n, "frames; ship width in multicolour pixels by direction:",
          dict(sorted(WIDTHS.items())))

if __name__ == "__main__":
    main(sys.argv[1])
