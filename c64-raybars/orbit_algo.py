#!/usr/bin/env python3
"""The orbit flyby drawn algorithmically: no per-frame colour lists.

Per frame the bar is two straight lines on the screen -- the top and bottom
edges of its silhouette (the two lines along the cylinder that the camera
just grazes, projected).  Each of the 6 raster-split segments takes the
bar's top and bottom where those lines cross its centre column, so its
rows are top..bottom, h lines.  Its colours come from one ramp per height
h: the gold gradient (48 bands) stretched evenly over h lines, each line
the nearest C64 colour to its slice -- built once, like COSMIC STRINGS'
ramps by height.

So the C64 needs per frame: 2 lines (a start and a step each, at the
segments' centres: 6 adds), and per segment a ramp pointer from h and the
line it starts on.  Memory: the ramps, sum of h for h = 1..HMAX bytes.

Video: 3D render | the per-frame decimation (orbit_video.py's) | this, the
two C64 versions with the CRT look.

    python3 orbit_algo.py out.mp4 [yaw] [from_dz] [to_dz]
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import orbit_shots as o

SPEED = 0.045
W, H, F, CY = fb.W, fb.H, fb.F, fb.CY
MIDS = [(a + b) / 2 for a, b in zip(o.SEG, o.SEG[1:])]
_RAMPS = {}

def ramp(h):
    """The gold gradient stretched over h lines: C64 colours, top first."""
    if h not in _RAMPS:
        g = o.GOLD48
        out = []
        for j in range(h):
            a, b = 48 * j / h, 48 * (j + 1) / h
            xs = np.linspace(a, b, 16, endpoint=False) + (b - a) / 32
            c = g[np.clip(xs.astype(int), 0, 47)].mean(0)
            out.append(int(fb.to_c64(c[None])[0]))
        _RAMPS[h] = out
    return _RAMPS[h]

def edges(yaw, barz):
    """The silhouette's two edge lines: for each, (c0, c1) with its camera
    coordinates c0 + t c1 along the bar (t = world x)."""
    Rm, cam = o.rot(yaw), o.camera(yaw)
    q = np.array([o.YC, barz])                   # the bar's axis in the y-z plane
    c = np.array([cam[1], cam[2]])
    v = c - q
    d = np.linalg.norm(v)
    u = v / d
    up = np.array([-u[1], u[0]])
    cs = o.R / d
    sn = math.sqrt(max(0.0, 1 - cs * cs))
    out = []
    for s in (1, -1):
        ty, tz = q + o.R * (cs * u + s * sn * up)
        p0 = np.array([0.0, ty, tz])
        out.append((Rm @ (p0 - cam), Rm[:, 0]))
    return out

def edge_y(e, xs):
    """Screen line (sample units) of an edge at screen column xs, or None
    where that column sees no part of it in front of the camera."""
    c0, c1 = e
    k = (xs - W / 2) / F
    den = c1[0] - k * c1[2]
    if abs(den) < 1e-12:
        return None
    t = -(c0[0] - k * c0[2]) / den
    p = c0 + t * c1
    if p[2] <= 0.05:
        return None
    return CY + 0.5 - F * p[1] / p[2]

def frame(yaw, barz):
    """The C64 bar, algorithmically: 6 segments, each rows top..bottom of
    its centre column, coloured from ramp(h)."""
    img = np.zeros((H, W), int)
    es = edges(yaw, barz)
    for (x0, x1), xm in zip(zip(o.SEG, o.SEG[1:]), MIDS):
        ys = [edge_y(e, xm) for e in es]
        if None in ys:
            continue
        top, bot = min(ys), max(ys)
        r0, r1 = math.ceil(top - 0.5), math.floor(bot - 0.5)
        h = r1 - r0 + 1
        if h < 1:
            continue
        rp = ramp(h)
        for j in range(h):
            r = r0 + j
            if 0 <= r < H:
                img[r, x0:x1] = rp[j]
    return img

def main(path, yaw=90.0, dz0=7.0, dz1=-2.5):
    Z = 2
    Wz, Hz = W * Z, H * Z
    font, small = fl.fonts()
    v = iv.Video(path, 3 * Wz + 64, Hz + 70)
    n = int((dz0 - dz1) / SPEED)
    last, hmax = None, 0
    for f in range(n):
        dz = dz0 - f * SPEED
        o.BARZ = o.ZS + dz
        true, c64, box = o.shot(yaw)
        alg = frame(yaw, o.BARZ)
        spr = o.SPR >= 0
        alg[spr] = o.SPR[spr]
        hmax = max([hmax] + list(_RAMPS))
        a = Image.fromarray(np.clip(true, 0, 255).astype(np.uint8)).resize((Wz, Hz), Image.LANCZOS)
        b = lv.crt_look(fb.C64RGB[c64].astype(np.uint8), Z)
        c = lv.crt_look(fb.C64RGB[alg].astype(np.uint8), Z)
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), f"camera orbited {yaw:g} degrees; the bar passes under the ship   {dz:+.2f} m",
                fill=(170, 176, 210), font=small)
        for i, (im, lab) in enumerate(((a, "3D render"), (b, "C64: colours decimated every frame"),
                                       (c, "C64: algorithmic (2 edge lines + ramps by height)"))):
            x = 16 + i * (Wz + 16)
            dr.text((x, 38), lab, fill=(200, 205, 230), font=small)
            canvas.paste(im, (x, 56))
        v.add(canvas)
        last = canvas
        if f % 40 == 0:
            print("frame", f, "of", n, flush=True)
    for _ in range(30):
        v.add(last)
    v.close()
    hs = sorted(_RAMPS)
    print("wrote", path, n, "frames; ramps used: h", hs[0], "..", hs[-1],
          f"({len(hs)} heights; all heights 1..{hs[-1]} = {hs[-1] * (hs[-1] + 1) // 2} bytes)")

if __name__ == "__main__":
    a = sys.argv
    main(a[1], float(a[2]) if len(a) > 2 else 90.0,
         float(a[3]) if len(a) > 3 else 7.0, float(a[4]) if len(a) > 4 else -2.5)
