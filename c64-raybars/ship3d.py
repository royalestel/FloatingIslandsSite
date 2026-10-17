"""GOLDSHIP's ship: a small 3D model, rendered into C64 multicolour sprite
frames (12 x 21) by gen_tables.py.

The model faces away from the camera (x right, y up, z forward).  Each
attitude is rotated (pitch, then roll), projected orthographically so the
wingspan fills the sprite's 24 pixels in the tail view, and rasterised with
a z-buffer at 8 x 4 samples per multicolour pixel.  Faces are flat-shaded
into the sprite's three colours: %01 hull in shadow, %10 lit hull and trim
(the wingtip fins and engine nacelles), %11 the engines' exhausts and the
light on the nose.  A pixel takes %11 if a fifth of its samples glow,
otherwise the majority hull colour if a third of it is covered.

    python3 ship3d.py frames.png      # preview the 9 attitudes
"""
import math

def loft(sections, kind="hull", caps=("hull", "hull"), dx=0.0):
    """Faces between polygon cross-sections [(z, [(x, y), ...]), ...]."""
    faces = []
    for (za, pa), (zb, pb) in zip(sections, sections[1:]):
        n = len(pa)
        for i in range(n):
            j = (i + 1) % n
            faces.append(([(pa[i][0] + dx, pa[i][1], za), (pa[j][0] + dx, pa[j][1], za),
                           (pb[j][0] + dx, pb[j][1], zb), (pb[i][0] + dx, pb[i][1], zb)], kind))
    z0, p0 = sections[0]
    z1, p1 = sections[-1]
    faces.append(([(x + dx, y, z0) for x, y in p0], caps[0]))
    faces.append(([(x + dx, y, z1) for x, y in p1], caps[1]))
    return faces

def octagon(w, h, cy=0.0):
    a, b = w / 2, h / 2
    return [(-a * 0.45, cy + b), (a * 0.45, cy + b), (a, cy + b * 0.4), (a, cy - b * 0.4),
            (a * 0.45, cy - b), (-a * 0.45, cy - b), (-a, cy - b * 0.4), (-a, cy + b * 0.4)]

def slab(outline, thick, kind="hull"):
    """A flat plate: outline [(x, y, z)] thickened in y."""
    top = [(x, y + thick / 2, z) for x, y, z in outline]
    bot = [(x, y - thick / 2, z) for x, y, z in outline]
    f = [(top, kind), (bot, kind)]
    for i in range(len(outline)):
        j = (i + 1) % len(outline)
        f.append(([top[i], top[j], bot[j], bot[i]], kind))
    return f

def fin(outline, thick, kind="hull"):
    """A vertical plate: outline [(x, y, z)] thickened in x."""
    a = [(x - thick / 2, y, z) for x, y, z in outline]
    b = [(x + thick / 2, y, z) for x, y, z in outline]
    f = [(a, kind), (b, kind)]
    for i in range(len(outline)):
        j = (i + 1) % len(outline)
        f.append(([a[i], a[j], b[j], b[i]], kind))
    return f

def sphere(cx, cy, cz, r, kind, n=8):
    f = []
    for i in range(n):
        t0, t1 = math.pi * i / n, math.pi * (i + 1) / n
        for j in range(2 * n):
            p0, p1 = math.pi * j / n, math.pi * (j + 1) / n
            pt = lambda t, p: (cx + r * math.sin(t) * math.cos(p), cy + r * math.cos(t),
                               cz + r * math.sin(t) * math.sin(p))
            f.append(([pt(t0, p0), pt(t0, p1), pt(t1, p1), pt(t1, p0)], kind))
    return f

def model():
    """x right, y up, z forward: the nose points away from the camera."""
    f = []
    # fuselage: from the tail (z = -7) to the nose (z = 10)
    f += loft([(-7, octagon(4.6, 3.8)), (-3, octagon(7.4, 6.2)),
               (5, octagon(4.6, 3.8)), (10, octagon(1.6, 1.4))])
    # the light on the nose
    f += sphere(0, 0, 10.6, 1.4, "glow")
    # delta wings, drooping a little toward the tips
    for s in (-1, 1):
        f += slab([(s * 3.0, -0.6, 4.0), (s * 11.2, -1.6, -4.0), (s * 11.2, -1.6, -6.2),
                   (s * 3.0, -0.6, -6.2)], 1.6)
        # wingtip fins
        f += fin([(s * 11.4, -4.2, -6.6), (s * 11.4, 2.4, -6.6), (s * 11.4, 2.4, -5.0),
                  (s * 11.4, -4.2, -3.0)], 2.2, "trim")
        # engine pods under the wing roots: their exhausts glow
        f += loft([(-8, octagon(2.8, 2.6, -3.0)), (-1, octagon(2.8, 2.6, -3.0)),
                   (1, octagon(1.2, 1.2, -3.0))], "trim", caps=("glow", "trim"), dx=s * 4.6)
    # tail fin
    f += fin([(0, 2.4, -7.0), (0, 9.4, -7.6), (0, 9.4, -5.6), (0, 2.4, -1.0)], 2.2)
    return f

LIGHT = (-0.45, 0.75, -0.5)            # toward the light: up, left, behind us

def render(roll, pitch, scale=0.96):
    """-> 21 rows of 12 classes: 0 none, 1 dark hull, 2 lit hull, 3 glow."""
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    cr, sr = math.cos(math.radians(-roll)), math.sin(math.radians(-roll))
    def xf(p):
        x, y, z = p
        y, z = y * cp + z * sp, -y * sp + z * cp     # pitch: nose up for +
        x, y = x * cr - y * sr, x * sr + y * cr      # roll: clockwise for +
        return x, y, z
    ll = math.sqrt(sum(c * c for c in LIGHT))
    L = [c / ll for c in LIGHT]
    SX, SY = 8, 4                                    # samples per MC pixel
    W, H = 12 * SX, 21 * SY
    zb = [[1e9] * W for _ in range(H)]
    cls = [[0] * W for _ in range(H)]
    for poly, kind in model():
        P = [xf(p) for p in poly]
        # normal, turned toward the camera (at -z)
        ax, ay, az = (P[1][i] - P[0][i] for i in range(3))
        bx, by, bz = (P[2][i] - P[0][i] for i in range(3))
        n = (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)
        nl = math.sqrt(sum(c * c for c in n)) or 1
        n = [c / nl for c in n]
        if n[2] > 0:
            n = [-c for c in n]
        b = sum(n[i] * L[i] for i in range(3))
        c = 3 if kind == "glow" else 2 if kind == "trim" or b > 0.55 else 1
        S = [((12 + x * scale) * SX / 2, (10.5 - y * scale) * SY, z) for x, y, z in P]
        for k in range(1, len(S) - 1):
            tri = (S[0], S[k], S[k + 1])
            x0 = max(0, int(min(t[0] for t in tri)))
            x1 = min(W - 1, int(max(t[0] for t in tri)) + 1)
            y0 = max(0, int(min(t[1] for t in tri)))
            y1 = min(H - 1, int(max(t[1] for t in tri)) + 1)
            (ax_, ay_, az_), (bx_, by_, bz_), (cx_, cy_, cz_) = tri
            d = (by_ - cy_) * (ax_ - cx_) + (cx_ - bx_) * (ay_ - cy_)
            if abs(d) < 1e-9:
                continue
            for yy in range(y0, y1 + 1):
                for xx in range(x0, x1 + 1):
                    px, py = xx + 0.5, yy + 0.5
                    w0 = ((by_ - cy_) * (px - cx_) + (cx_ - bx_) * (py - cy_)) / d
                    w1 = ((cy_ - ay_) * (px - cx_) + (ax_ - cx_) * (py - cy_)) / d
                    w2 = 1 - w0 - w1
                    if min(w0, w1, w2) < 0:
                        continue
                    z = w0 * az_ + w1 * bz_ + w2 * cz_
                    if z < zb[yy][xx]:
                        zb[yy][xx] = z
                        cls[yy][xx] = c
    rows = []
    for r in range(21):
        row = []
        for cx in range(12):
            cnt = [0, 0, 0, 0]
            for yy in range(r * SY, r * SY + SY):
                for xx in range(cx * SX, cx * SX + SX):
                    cnt[cls[yy][xx]] += 1
            tot = SX * SY
            if cnt[3] * 5 >= tot:
                row.append(3)
            elif cnt[1] + cnt[2] + cnt[3] >= tot * 0.34:
                row.append(2 if cnt[2] >= cnt[1] else 1)
            else:
                row.append(0)
        rows.append(row)
    return rows

# attitudes: level, up, down, left, right, left-up, left-down, right-up,
# right-down (roll / pitch signs; the angles below)
ATT = [(0, 0), (0, 1), (0, -1), (-1, 0), (1, 0), (-1, 1), (-1, -1), (1, 1), (1, -1)]
R, P = 25, 22

def sprite(roll, pitch):
    """63 sprite bytes + 1 pad for one attitude (degrees)."""
    out = []
    for row in render(roll, pitch):
        bits = 0
        for v in row:
            bits = bits << 2 | v
        out += [bits >> 16 & 255, bits >> 8 & 255, bits & 255]
    return out + [0]

if __name__ == "__main__":
    import sys
    from PIL import Image
    pals = [{1: (0x8A, 0x46, 0xAE), 2: (0x7C, 0x70, 0xDA), 3: (0xFF, 0xFF, 0xFF)},
            {1: (0x89, 0x40, 0x36), 2: (0x90, 0x5F, 0x25), 3: (0xD0, 0xDC, 0x71)}]
    im = Image.new("RGB", (9 * 28 + 4, 2 * 25), (0, 0, 0))
    px = im.load()
    for f, (r, p) in enumerate(ATT):
        rows = render(r * R, p * P)
        for k, col in enumerate(pals):
            for y, row in enumerate(rows):
                for c, v in enumerate(row):
                    if v:
                        for d in (0, 1):
                            px[4 + f * 28 + c * 2 + d, 2 + k * 25 + y] = col[v]
    im.resize((im.width * 4, im.height * 4), Image.NEAREST).save(sys.argv[1])
