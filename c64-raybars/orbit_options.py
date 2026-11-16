#!/usr/bin/env python3
"""Options for the gold bars past 30 degrees of orbit, where the 6 raster
splits a line turn the bar into a staircase.  One sheet: rows = orbit angle,
columns = option, all the C64 version through the CRT look (flickering
options: the two frames averaged in linear light, as the eye does).

  A  now: each segment a flat slab (top / bottom at its centre column)
  B  steps shaded: rows the true edges only partly cross within a segment
     take a dimmer gold by their coverage (the distance-dimming ramps)
  C  steps flickered: those rows shown on one frame of two (coverage
     1/3..2/3), phase swapped line to line
  D  half-shifted splits: alternate frames split 32 pixels over (5
     segments of 64), each a flat slab; the eye sees steps half the size
  E  D + B: half-shifted splits with shaded steps
  F  sprite masks: slabs drawn to the edges' full extent, 4 black x- and
     y-expanded sprites (48 x 42) cut the 4 biggest corners to the true
     diagonal (the sprite budget beside the ship's two)

    python3 orbit_options.py out.png [angles]     # default 45,60
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import loop_video as lv
import orbit_shots as o
import orbit_algo as oa
import orbit360 as o3

W, H = fb.W, fb.H
SEG6 = o.SEG
SEG5 = [0, 64, 128, 192, 256, 320]
DIM = [(0.75, 1.0), (0.5, 0.7), (0.25, 0.45)]        # coverage -> brightness

def lines(yaw, barz):
    """top(x), bottom(x) of the bar's silhouette, or None where unseen."""
    es = oa.edges(yaw, barz)
    def at(x):
        ys = [oa.edge_y(e, x) for e in es]
        return None if None in ys else (min(ys), max(ys))
    return at

def segment(img, at, x0, x1, mode, p):
    xm = (x0 + x1) / 2
    m, a, b = at(xm), at(x0 + 0.5), at(x1 - 0.5)
    if m is None:
        return
    a, b = a or m, b or m
    r0, r1 = math.ceil(m[0] - 0.5), math.floor(m[1] - 0.5)
    h = max(1, r1 - r0 + 1)
    if mode == "slab":
        rows = {r: 1.0 for r in range(r0, r1 + 1)}
    else:
        xs = np.linspace(0, 1, 17)[:-1] + 1 / 32
        top = a[0] + (b[0] - a[0]) * xs
        bot = a[1] + (b[1] - a[1]) * xs
        rows = {}
        for r in range(math.floor(top.min()), math.ceil(bot.max()) + 1):
            c = float(((r + 0.5 >= top) & (r + 0.5 <= bot)).mean())
            if mode == "shade":
                lev = next((bb for cc, bb in DIM if c >= cc), None)
            elif mode == "flicker":
                thr = (1 / 3, 2 / 3)[(r + p) & 1]
                lev = 1.0 if c >= thr else None
            else:                                    # "full": the edges' whole extent
                lev = 1.0 if c > 0 else None
            if lev:
                rows[r] = lev
    for r, lev in rows.items():
        if 0 <= r < H:
            j = min(max(r - r0, 0), h - 1)
            img[r, x0:x1] = o3.ramp(h, lev)[j]

def bar(yaw, barz, seg, mode, p=0):
    img = np.zeros((H, W), int)
    at = lines(yaw, barz)
    for x0, x1 in zip(seg, seg[1:]):
        segment(img, at, x0, x1, mode, p)
    return img, at

def masks(img, at, seg, n=4):
    """n black expanded sprites (48 x 42) on the biggest corners."""
    cand = []
    for x0, x1 in zip(seg, seg[1:]):
        a, b = at(x0 + 0.5), at(x1 - 0.5)
        if a is None or b is None:
            continue
        for e in (0, 1):
            cand.append((abs(b[e] - a[e]), x0, x1, e, a[e], b[e]))
    for step, x0, x1, e, ya, yb in sorted(cand, reverse=True)[:n]:
        # the excess is thickest where the edge is furthest inside the slab
        outer = min(ya, yb) if e == 0 else max(ya, yb)
        thick_left = (ya != outer)
        sx = x0 if thick_left else max(x0, x1 - 48)
        for x in range(sx, min(sx + 48, x1), 2):
            t = at(x + 1)
            if t is None:
                continue
            if e == 0:
                y0, y1 = math.floor(outer), math.ceil(t[0] - 0.5)
            else:
                y0, y1 = math.floor(t[1] + 0.5), math.ceil(outer) + 1
            y0 = max(y0, (y1 - 42) if e == 0 else y0)
            y1 = min(y1, y0 + 42)
            img[max(0, y0):max(0, y1), x:x + 2] = 0
    return img

def add_ship(img, yaw, p):
    for (r, c), k in o3.sprite(yaw)[p].items():
        img[r, c:c + 2] = o3.GLOW[p] if k == 3 else o3.SHIPCOL[k]
    return img

def seen(frames, z):
    """The CRT look of one frame, or of two alternating (averaged in light)."""
    ims = [np.asarray(lv.crt_look(fb.C64RGB[f].astype(np.uint8), z), float) / 255 for f in frames]
    lin = sum(i ** 2.2 for i in ims) / len(ims)
    return Image.fromarray(np.clip(lin ** (1 / 2.2) * 255, 0, 255).astype(np.uint8))

def options(yaw, barz):
    S = lambda seg, mode, p: add_ship(bar(yaw, barz, seg, mode, p)[0], yaw, p)
    def F(p):
        img, at = bar(yaw, barz, SEG6, "full", p)
        return add_ship(masks(img, at, SEG6), yaw, p)
    return [
        ("A  now: flat slabs, 6 splits", [S(SEG6, "slab", 0), S(SEG6, "slab", 1)]),
        ("B  steps shaded by coverage (dimmer gold)", [S(SEG6, "shade", 0), S(SEG6, "shade", 1)]),
        ("C  steps flickered (one frame of two)", [S(SEG6, "flicker", 0), S(SEG6, "flicker", 1)]),
        ("D  splits shifted 32 px on alternate frames", [S(SEG6, "slab", 0), S(SEG5, "slab", 1)]),
        ("E  D + B: shifted splits, shaded steps", [S(SEG6, "shade", 0), S(SEG5, "shade", 1)]),
        ("F  4 black sprite masks on the biggest corners", [F(0), F(1)]),
    ]

def main(path, angles, dz=0.6):
    Z = 2
    font, small = fl.fonts()
    cw, ch, pad, top = W * Z, H * Z, 14, 26
    crop = (0, 40 * Z, cw, 180 * Z)                    # the band with the bar
    chh = crop[3] - crop[1]
    sheet = Image.new("RGB", (pad + 3 * (cw + pad), 30 + len(angles) * 2 * (chh + top) + pad), (8, 8, 16))
    dr = ImageDraw.Draw(sheet)
    y = 8
    for yaw in angles:
        o.BARZ = o.ZS + dz
        dr.text((pad, y), f"camera orbited {yaw:g} degrees (C64, CRT look; flicker shown as the eye averages it)",
                fill=(235, 235, 120), font=font)
        y += 26
        for i, (lab, frames) in enumerate(options(yaw, o.BARZ)):
            x = pad + (i % 3) * (cw + pad)
            yy = y + (i // 3) * (chh + top)
            dr.text((x, yy), lab, fill=(200, 205, 230), font=small)
            sheet.paste(seen(frames, Z).crop(crop), (x, yy + 18))
        y += 2 * (chh + top)
    sheet = sheet.crop((0, 0, sheet.width, y + pad))
    sheet.save(path)
    print("wrote", path)

if __name__ == "__main__":
    ang = [float(a) for a in sys.argv[2].split(",")] if len(sys.argv) > 2 else [45, 60]
    main(sys.argv[1], ang)
