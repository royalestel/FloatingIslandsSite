#!/usr/bin/env python3
"""The ship drawn larger, across several sprites: for a chase camera closer
than GOLDSHIP's 3 m.  ship3d.py's model rendered into any multicolour grid
at any scale, and made into an antialiased pair of frames as
ship_aa.make_pair does for the single sprite.  At 2 m (scale 1.44, 1.5
times the single sprite's) the ship is 18 multicolour pixels wide and at
most 20 lines tall, even pitched 30 degrees: two sprites side by side
(24 x 21 multicolour pixels, 48 screen pixels by 21 lines).

    python3 big_ship.py preview.png      # level, climbing, diving
"""
import math, sys
import numpy as np
import ship3d

SX, SY = ship3d.SX, ship3d.SY

def model():
    """ship3d's gull with more detail for the two-sprite size: no light on
    the nose; a canopy hump (dark), twin tail fins, winglets at the tips,
    and glowing exhausts -- a main nozzle at the back of the body and one
    at the back of each engine pod ("glow", the sprite's %11 colour)."""
    L = ship3d.lozenge
    f = ship3d.loft([(-6, L(4.4, 3.0)), (-1, L(5.0, 3.4)), (6, L(3.0, 2.2)),
                     (10, L(1.2, 1.0))])
    # the main nozzle: a short glowing duct out of the tail
    f += ship3d.loft([(-7.0, L(2.6, 1.6)), (-5.8, L(3.0, 2.0))], "trim",
                     caps=("glow", "trim"))
    # canopy: a low hump on the body's top, in shadow
    f += ship3d.loft([(-0.5, L(1.6, 0.8, 1.9)), (2.0, L(2.0, 1.4, 2.1)),
                      (4.5, L(1.2, 0.6, 1.4))], "dark", caps=("dark", "dark"))
    for s in (-1, 1):
        path = [(s * 2.2, 0.0), (s * 5.2, 1.8), (s * 11.8, -1.6)]
        for (xa, ya), (xb, yb) in zip(path, path[1:]):
            f += ship3d.slab([(xa, ya, 4 - abs(xa) * 0.75), (xb, yb, 4 - abs(xb) * 0.75),
                              (xb, yb, -6.0), (xa, ya, -6.0)], 1.8)
        # engine pods, glowing at the back
        f += ship3d.loft([(-7.5, ship3d.octagon(2.6, 2.6, 1.8)), (0, ship3d.octagon(2.6, 2.6, 1.8)),
                          (2, ship3d.octagon(1.0, 1.0, 1.8))], "trim", caps=("glow", "trim"),
                         dx=s * 5.2)
        # twin tail fins, canted out, on the body's back
        f += ship3d.fin([(s * 1.5, 1.2, -6.0), (s * 2.3, 4.2, -6.8), (s * 2.3, 4.2, -5.2),
                         (s * 1.5, 1.2, -2.0)], 0.7)
        # winglets: down-turned tips
        f += ship3d.fin([(s * 11.8, -1.6, -6.0), (s * 12.2, -3.8, -6.6), (s * 12.2, -3.8, -4.6),
                         (s * 11.8, -1.6, -2.0)], 0.7, "trim")
    return f

def sample_counts(roll, pitch, wmc=24, rows=21, scale=1.44):
    """ship3d.sample_counts for a wmc x rows grid; scale 0.96 is the single
    sprite's (3 m), 1.44 the ship 2 m away."""
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    cr, sr = math.cos(math.radians(-roll)), math.sin(math.radians(-roll))
    L = np.array(ship3d.LIGHT, float)
    L /= np.linalg.norm(L)
    W, H = wmc * SX, rows * SY
    zb = np.full((H, W), np.inf)
    cls = np.zeros((H, W), int)
    ys, xs = np.mgrid[0:H, 0:W] + 0.5
    for poly, kind in model():
        P = []
        for x, y, z in poly:
            y, z = y * cp + z * sp, -y * sp + z * cp
            x, y = x * cr - y * sr, x * sr + y * cr
            P.append((x, y, z))
        P = np.array(P)
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if np.linalg.norm(n) < 1e-9:
            continue
        n /= np.linalg.norm(n)
        if n[2] > 0:
            n = -n
        c = 3 if kind == "glow" else 1 if kind == "dark" else \
            2 if kind == "trim" or n @ L > 0.55 else 1
        S = np.column_stack([(wmc / 2 + P[:, 0] * scale / 2) * SX,
                             (rows / 2 - P[:, 1] * scale) * SY, P[:, 2]])
        for k in range(1, len(S) - 1):
            a, b, cc = S[0], S[k], S[k + 1]
            x0 = int(max(0, min(a[0], b[0], cc[0])))
            x1 = int(min(W - 1, max(a[0], b[0], cc[0]) + 1))
            y0 = int(max(0, min(a[1], b[1], cc[1])))
            y1 = int(min(H - 1, max(a[1], b[1], cc[1]) + 1))
            if x1 < x0 or y1 < y0:
                continue
            d = (b[1] - cc[1]) * (a[0] - cc[0]) + (cc[0] - b[0]) * (a[1] - cc[1])
            if abs(d) < 1e-9:
                continue
            px, py = xs[y0:y1 + 1, x0:x1 + 1], ys[y0:y1 + 1, x0:x1 + 1]
            w0 = ((b[1] - cc[1]) * (px - cc[0]) + (cc[0] - b[0]) * (py - cc[1])) / d
            w1 = ((cc[1] - a[1]) * (px - cc[0]) + (a[0] - cc[0]) * (py - cc[1])) / d
            w2 = 1 - w0 - w1
            z = w0 * a[2] + w1 * b[2] + w2 * cc[2]
            sub = zb[y0:y1 + 1, x0:x1 + 1]
            m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0) & (z < sub)
            sub[m] = z[m]
            cls[y0:y1 + 1, x0:x1 + 1][m] = c
    counts = np.zeros((rows, wmc, 4), int)
    for k in range(4):
        counts[..., k] = (cls == k).reshape(rows, SY, wmc, SX).sum(axis=(1, 3))
    return counts

def pair(roll, pitch, wmc=24, rows=21, scale=1.44, hi=0.7, lo=0.28):
    """Two class frames (rows x wmc, 0 none .. 3 the light): ship_aa's rules
    -- a covered pixel lit in both, a half covered one in one frame in a
    checkerboard, a pixel split between shadowed and lit hull alternating,
    the phase swapped on alternate lines."""
    counts = sample_counts(roll, pitch, wmc, rows, scale)
    tot = SX * SY
    f0 = np.zeros((rows, wmc), int)
    f1 = np.zeros((rows, wmc), int)
    for r in range(rows):
        for c in range(wmc):
            n0, n1, n2, n3 = counts[r, c]
            cov = (n1 + n2 + n3) / tot
            hull = n1 + n2
            col = 2 if n2 >= n1 else 1
            split = hull and min(n1, n2) >= 0.3 * hull
            odd = (r + c) % 2
            if n3 * 5 >= tot:
                f0[r, c] = f1[r, c] = 3
            elif cov >= hi:
                a, b = (1, 2) if split else (col, col)
                if r % 2:
                    a, b = b, a
                f0[r, c], f1[r, c] = a, b
                if n3 * 12 >= tot:
                    (f1 if odd else f0)[r, c] = 3
            elif cov >= lo:
                (f1 if odd else f0)[r, c] = 3 if n3 > hull else col
    return f0, f1

if __name__ == "__main__":
    from PIL import Image
    pal = {1: (0x8A, 0x46, 0xAE), 2: (0x7C, 0x70, 0xDA), 3: (255, 255, 255)}
    views = [(0, 0), (0, 15), (0, -15), (0, 30)]
    im = Image.new("RGB", (len(views) * 60, 29), (0, 0, 0))
    px = im.load()
    for i, (r, p) in enumerate(views):
        f0, f1 = pair(r, p)
        for y in range(21):
            for c in range(24):
                for f in (f0, f1):
                    if f[y, c]:
                        for d in (0, 1):
                            px[i * 60 + 6 + 2 * c + d, 4 + y] = pal[f[y, c]]
    im.resize((im.width * 4, im.height * 4), Image.NEAREST).save(sys.argv[1])
