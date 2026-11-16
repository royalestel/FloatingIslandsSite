#!/usr/bin/env python3
"""Orbit study: the camera swung round the ship to the side (yaw about the
ship), the ship flying over a gold bar.  For each angle: the true 3D render
(full colour, 4 x 4 samples a pixel) and its C64 decimation -- the bar as
raster splits, the ship as multicolour sprites.

Scene (flyby3d.py's: metres, focal length 200 lines, the ship at 3 m ahead,
its wingspan 24 pixels): one gold bar (radius 0.12 m, along x, the gold
palette's 48 bands), right under the ship, its top edge 10 lines below the
ship's centre line.  The camera orbits the ship by `yaw` degrees to the
right, still looking at it, so the bar recedes to the left and comes nearer
to the right.

The C64 version:
  * the bar: each raster line split in GOLDSHIP's 6 segments (window x
    0-32, 32-96, 96-160, 160-224, 224-288, 288-320), one colour per
    segment per line: the 3D render's average over that piece of the line,
    to the nearest C64 colour; black where the bar covers under half of it.
    Each segment reads its own colour column (lda colk,y), so the slant
    and the bar's thickness can differ per segment.
  * the ship: multicolour sprites (pixels 2 wide), purple / light blue /
    white over transparent: each pixel the nearest of the three to the
    render's average if the ship covers half of it.

    python3 orbit_shots.py out.png [angles]      # default 3,7,14
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import ship3d
import flicker as fl
import loop_video as lv

W, H, SS, F, CY = fb.W, fb.H, fb.SS, fb.F, fb.CY
ZS, R = fb.ZS, fb.R
GAP = 10                                   # bar top: lines below the ship's centre
SEG = [0, 32, 96, 160, 224, 288, 320]      # GOLDSHIP's split points (window x)
SPRCOL = [4, 14, 1]                        # sprite colours: purple, light blue, white
GOLD48 = fb.bands48(fb.GOLD)
YC = -(GAP / F * ZS) - R                   # the bar's centre height (ship at y = 0)

def rot(yaw):
    """World -> camera rotation (about y) for a camera orbited `yaw` degrees
    to the right of the ship, looking at it."""
    a = math.radians(yaw)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])

def camera(yaw):
    """Camera position in the world: on a circle of radius ZS round the ship."""
    a = math.radians(yaw)
    return np.array([ZS * math.sin(a), 0.0, ZS - ZS * math.cos(a)])

def rays_world(yaw):
    dx, dy = fb.rays()
    d = np.stack([dx, dy, np.ones_like(dx)], -1) @ rot(yaw)   # camera -> world (R^T)
    return d

def bar(yaw):
    """Depth along the ray (camera z) and colour of the bar, per sample."""
    d = rays_world(yaw)
    o = camera(yaw)
    vy, vz = d[..., 1], d[..., 2]
    oy, oz = o[1] - YC, o[2] - ZS
    a = vy * vy + vz * vz
    b = 2 * (oy * vy + oz * vz)
    c = oy * oy + oz * oz - R * R
    disc = b * b - 4 * a * c
    hit = disc >= 0
    t = np.where(hit, (-b - np.sqrt(np.maximum(disc, 0))) / (2 * a), np.inf)
    y = np.where(hit, o[1] + t * vy, YC)
    band = np.clip(((YC + R - y) / (2 * R) * 48).astype(int), 0, 47)
    return np.where(hit, t, np.inf), GOLD48[band]

def ship(yaw):
    """Depth and colour of the ship (z-buffered, flat-shaded), per sample."""
    dx, dy = fb.rays()
    s = 0.36 / 23.6
    Rm, o = rot(yaw), camera(yaw)
    zb = np.full(dx.shape, np.inf)
    col = np.zeros(dx.shape + (3,))
    L = Rm @ (np.array(ship3d.LIGHT, float) / np.linalg.norm(ship3d.LIGHT))
    mat = {"hull": np.array([138, 70, 174.]), "trim": np.array([124, 112, 218.]),
           "glow": np.array([255, 255, 255.])}
    sx, sy = dx * F + W / 2, CY + 0.5 - dy * F
    for poly, kind in ship3d.model():
        Pw = np.array([(x * s, y * s, ZS + z * s) for x, y, z in poly])
        P = (Pw - o) @ Rm.T
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if np.linalg.norm(n) < 1e-12:
            continue
        n /= np.linalg.norm(n)
        if n @ P[0] > 0:
            n = -n
        c = mat["glow"] if kind == "glow" else mat[kind] * (0.35 + 0.8 * max(0.0, n @ L))
        Q = np.column_stack([P[:, 0] / P[:, 2] * F + W / 2, CY + 0.5 - P[:, 1] / P[:, 2] * F, P[:, 2]])
        for k in range(1, len(Q) - 1):
            a, b, cc = Q[0], Q[k], Q[k + 1]
            dd = (b[1] - cc[1]) * (a[0] - cc[0]) + (cc[0] - b[0]) * (a[1] - cc[1])
            if abs(dd) < 1e-12:
                continue
            w0 = ((b[1] - cc[1]) * (sx - cc[0]) + (cc[0] - b[0]) * (sy - cc[1])) / dd
            w1 = ((cc[1] - a[1]) * (sx - cc[0]) + (a[0] - cc[0]) * (sy - cc[1])) / dd
            w2 = 1 - w0 - w1
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            iz = w0 / a[2] + w1 / b[2] + w2 / cc[2]
            z = np.where(inside, 1 / np.maximum(iz, 1e-9), np.inf)
            m = z < zb
            zb[m] = z[m]
            col[m] = c
    return zb, col

def shot(yaw):
    """The 3D render (RGB, W x H, averaged) and the C64 version (colour indices)."""
    zb, bc = bar(yaw)
    zs, sc = ship(yaw)
    img = np.zeros(zb.shape + (3,))
    hb = np.isfinite(zb)
    img[hb] = bc[hb]
    hs = zs < zb
    img[hs] = sc[hs]
    true = img.reshape(H, SS, W, SS, 3).mean(axis=(1, 3))
    # the bar alone, by raster line and segment
    barimg = np.where(hb[..., None], bc, 0.0)
    cov = hb.reshape(H, SS, W, SS).mean(axis=(1, 3))
    avg = barimg.reshape(H, SS, W, SS, 3).mean(axis=(1, 3))
    c64 = np.zeros((H, W), int)
    for x0, x1 in zip(SEG, SEG[1:]):
        cv = cov[:, x0:x1].mean(1)
        a = avg[:, x0:x1].mean(1) / np.maximum(cv, 1e-9)[:, None]
        idx = fb.to_c64(a)
        c64[:, x0:x1] = np.where(cv >= 0.5, idx, 0)[:, None]
    # the ship as multicolour sprite pixels (2 wide)
    m = hs.reshape(H, SS, W // 2, 2 * SS).mean(axis=(1, 3))
    sa = np.where(hs[..., None], sc, 0.0).reshape(H, SS, W // 2, 2 * SS, 3).sum(axis=(1, 3))
    sa = sa / np.maximum(hs.reshape(H, SS, W // 2, 2 * SS).sum(axis=(1, 3)), 1)[..., None]
    pal = fb.C64RGB[SPRCOL]
    near = np.argmin(((sa[..., None, :] - pal) ** 2).sum(-1), -1)
    on = m >= 0.5
    ys, xs = np.nonzero(on)
    for y, x in zip(ys, xs):
        c64[y, 2 * x:2 * x + 2] = SPRCOL[near[y, x]]
    box = (xs.min(), xs.max(), ys.min(), ys.max()) if len(xs) else None
    return true, c64, box

def main(path, angles):
    Z = 3
    font, small = fl.fonts()
    rows = []
    for yaw in angles:
        true, c64, box = shot(yaw)
        rgb = fb.C64RGB[c64].astype(np.uint8)
        a = Image.fromarray(np.clip(true, 0, 255).astype(np.uint8)).resize((W * Z, H * Z), Image.BICUBIC)
        b = Image.fromarray(rgb).resize((W * Z, H * Z), Image.NEAREST)
        c = lv.crt_look(rgb, Z)
        wmc = box[1] - box[0] + 1 if box else 0
        hl = box[3] - box[2] + 1 if box else 0
        rows.append((yaw, (a, b, c), wmc, hl))
        print(f"yaw {yaw:4.1f}: ship {wmc} multicolour pixels x {hl} lines "
              f"({math.ceil(wmc / 12)} sprite(s) wide)")
    pad, top = 16, 30
    cw, ch = W * Z, H * Z
    sheet = Image.new("RGB", (pad + 3 * (cw + pad), top + len(rows) * (ch + top) + pad), (8, 8, 16))
    dr = ImageDraw.Draw(sheet)
    for i, (yaw, ims, wmc, hl) in enumerate(rows):
        y = top + i * (ch + top)
        labels = (f"3D render, camera orbited {yaw:g} degrees",
                  f"C64: raster splits + sprites (ship {wmc} MC px wide)", "C64, CRT")
        for j, (im, lab) in enumerate(zip(ims, labels)):
            x = pad + j * (cw + pad)
            sheet.paste(im, (x, y))
            dr.text((x, y - 22), lab, fill=(200, 205, 230), font=small)
    sheet.save(path)
    print("wrote", path)
    return rows

if __name__ == "__main__":
    ang = [float(a) for a in sys.argv[2].split(",")] if len(sys.argv) > 2 else [3, 7, 14]
    main(sys.argv[1], ang)
