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
* Ship: multicolour sprite frames rendered from the 3D model, one per
  YAWSTEPS directions (as the C64 would store them).

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
HOLD, TURN = 60, 720
YAWSTEPS = 32
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

def sprite(yaw):
    """The ship's sprite pixels at the nearest of YAWSTEPS directions:
    {(row, col): colour}, from a cropped 3D render."""
    q = round(yaw / (360 / YAWSTEPS)) % YAWSTEPS
    if q not in _SPR:
        x0, x1, y0, y1 = 128, 192, 84, 116
        xs = np.arange(x0 * SS, x1 * SS)
        ys = np.arange(y0 * SS, y1 * SS)
        px, py = np.meshgrid((xs + 0.5) / SS, (ys + 0.5) / SS)
        dx, dy = (px - W / 2) / F, (CY + 0.5 - py) / F
        zs, sc = o.ship(q * 360 / YAWSTEPS, (dx, dy))
        hs = np.isfinite(zs)
        h, w = y1 - y0, (x1 - x0) // 2
        m = hs.reshape(h, SS, w, 2 * SS).mean(axis=(1, 3))
        sa = np.where(hs[..., None], sc, 0.0).reshape(h, SS, w, 2 * SS, 3).sum(axis=(1, 3))
        sa = sa / np.maximum(hs.reshape(h, SS, w, 2 * SS).sum(axis=(1, 3)), 1)[..., None]
        pal = fb.C64RGB[o.SPRCOL]
        near = np.argmin(((sa[..., None, :] - pal) ** 2).sum(-1), -1)
        out = {}
        for r, c in zip(*np.nonzero(m >= 0.5)):
            out[(y0 + r, x0 + 2 * c)] = o.SPRCOL[near[r, c]]
        _SPR[q] = out
    return _SPR[q]

def frame(yaw, zship):
    img = np.zeros((H, W), int)
    k0 = math.floor((zship - 8) / SPACING)
    bars = []
    for k in range(k0, k0 + int(20 / SPACING) + 2):
        barz = o.ZS + k * SPACING - zship
        yc = HEIGHTS[k % len(HEIGHTS)]
        bars.append(edges(yaw, yc, barz))
    for (x0, x1), xm in zip(zip(o.SEG, o.SEG[1:]), oa.MIDS):
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
    for (r, c), col in sprite(yaw).items():
        img[r, c:c + 2] = col
    return img

def main(path):
    Z = 3
    font, small = fl.fonts()
    v = iv.Video(path, W * Z + 32, H * Z + 50)
    n = HOLD + TURN + HOLD
    for f in range(n):
        t = min(max(f - HOLD, 0), TURN) / TURN
        yaw = 360 * (0.5 - 0.5 * math.cos(math.pi * t))     # eased in and out
        img = frame(yaw % 360, f * SPEED)
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), f"C64 mockup: camera orbiting the ship {yaw:5.1f} degrees   "
                f"raster splits (6 a line) + sprite   CRT", fill=(170, 176, 210), font=small)
        canvas.paste(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z), (16, 34))
        v.add(canvas)
        if f % 60 == 0:
            print("frame", f, "of", n, "sprites", len(_SPR), flush=True)
    v.close()
    print("wrote", path, n, "frames")

if __name__ == "__main__":
    main(sys.argv[1])
