"""Ship design sheets: each design's 9 attitudes rendered in full colour at
200 x 175 (numpy z-buffer, 2 x 2 supersampled, flat shading with a
specular touch, bloom on the light), each with its sprite version below.

    python3 ship_hires.py sheet.png [letters]   # e.g. "AC": designs A and C
    python3 ship_hires.py sheet.png gulls       # the gull variations C1-C5
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import ship3d
import ship_designs as designs

ATT = ship3d.ATT
R, P = ship3d.R, ship3d.P
LABELS = ["tail (no input)", "up", "down", "left", "right", "left-up", "left-down",
          "right-up", "right-down"]
VW, VH, SS = 200, 175, 2               # view size, supersampling
MAT = {"hull": np.array([138, 70, 174]), "trim": np.array([124, 112, 218]),
       "glow": np.array([255, 255, 255])}
L = np.array(ship3d.LIGHT, float); L /= np.linalg.norm(L)
H = L + np.array([0, 0, -1.0]); H /= np.linalg.norm(H)
BG = (14, 14, 24)

def view(faces, roll, pitch):
    W, Hh = VW * SS, VH * SS
    scale = W / 26.0
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    cr, sr = math.cos(math.radians(-roll)), math.sin(math.radians(-roll))
    zb = np.full((Hh, W), np.inf)
    img = np.zeros((Hh, W, 3))
    glow = np.zeros((Hh, W))
    fid = np.full((Hh, W), -1)
    ys, xs = np.mgrid[0:Hh, 0:W] + 0.5
    for idx, (poly, kind) in enumerate(faces):
        P3 = []
        for x, y, z in poly:
            y, z = y * cp + z * sp, -y * sp + z * cp
            x, y = x * cr - y * sr, x * sr + y * cr
            P3.append((x, y, z))
        P3 = np.array(P3)
        n = np.cross(P3[1] - P3[0], P3[2] - P3[0])
        if np.linalg.norm(n) < 1e-9:
            continue
        n /= np.linalg.norm(n)
        if n[2] > 0:
            n = -n
        if kind == "glow":
            col = MAT["glow"].astype(float)
        else:
            d = max(0.0, n @ L)
            spec = max(0.0, n @ H) ** 24
            col = MAT[kind] * (0.30 + 0.85 * d) + 255 * 0.45 * spec
        S = np.column_stack([W / 2 + P3[:, 0] * scale, Hh / 2 - P3[:, 1] * scale, P3[:, 2]])
        for k in range(1, len(S) - 1):
            a, b, c = S[0], S[k], S[k + 1]
            x0, x1 = int(max(0, min(a[0], b[0], c[0]))), int(min(W - 1, max(a[0], b[0], c[0]) + 1))
            y0, y1 = int(max(0, min(a[1], b[1], c[1]))), int(min(Hh - 1, max(a[1], b[1], c[1]) + 1))
            if x1 < x0 or y1 < y0:
                continue
            d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(d) < 1e-9:
                continue
            px, py = xs[y0:y1 + 1, x0:x1 + 1], ys[y0:y1 + 1, x0:x1 + 1]
            w0 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / d
            w1 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / d
            w2 = 1 - w0 - w1
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            z = w0 * a[2] + w1 * b[2] + w2 * c[2]
            sub = zb[y0:y1 + 1, x0:x1 + 1]
            m = inside & (z < sub)
            sub[m] = z[m]
            img[y0:y1 + 1, x0:x1 + 1][m] = col
            glow[y0:y1 + 1, x0:x1 + 1][m] = 1.0 if kind == "glow" else 0.0
            fid[y0:y1 + 1, x0:x1 + 1][m] = idx
    cov = np.isfinite(zb)
    # outline: darken where the face changes, and around the silhouette
    edge = np.zeros_like(cov)
    edge[:, 1:] |= fid[:, 1:] != fid[:, :-1]
    edge[1:, :] |= fid[1:, :] != fid[:-1, :]
    out = np.where(cov[..., None], img, np.array(BG, float))
    out[edge & cov] *= 0.72
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).resize((VW, VH), Image.LANCZOS)
    # bloom on the glowing parts
    g = Image.fromarray((glow * 255).astype(np.uint8)).resize((VW, VH), Image.LANCZOS)
    g = g.filter(ImageFilter.GaussianBlur(5))
    ga = np.asarray(g, float)[..., None] / 255 * 0.8
    arr = np.asarray(im, float) * (1 - ga) + np.array([255, 250, 235]) * ga
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def sprite(fn, roll, pitch, z=7):
    old = ship3d.model
    ship3d.model = fn
    try:
        rows = ship3d.render(roll, pitch)
    finally:
        ship3d.model = old
    pal = {1: (0x8A, 0x46, 0xAE), 2: (0x7C, 0x70, 0xDA), 3: (0xFF, 0xFF, 0xFF)}
    im = Image.new("RGB", (24, 21), BG)
    px = im.load()
    for y, row in enumerate(rows):
        for c, v in enumerate(row):
            if v:
                px[2 * c, y] = px[2 * c + 1, y] = pal[v]
    return im.resize((24 * z, 21 * z), Image.NEAREST)

def sheet(path, which=None):
    rows = [d for d in designs.DESIGNS if which is None or d[0][0] in which]
    pad, head = 10, 34
    SW, SH = 24 * 7, 21 * 7
    rowh = head + VH + 6 + SH + 18
    W = pad + 9 * (VW + pad)
    Hh = 40 + len(rows) * rowh
    im = Image.new("RGB", (W, Hh), (8, 8, 14))
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
        small = ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        font = small = ImageFont.load_default()
    for i, lab in enumerate(LABELS):
        dr.text((pad + i * (VW + pad) + 4, 12), lab, fill=(170, 170, 190), font=small)
    for r, (name, fn) in enumerate(rows):
        y = 40 + r * rowh
        dr.text((pad, y + 6), name, fill=(235, 235, 245), font=font)
        faces = fn()
        for i, (rr, pp) in enumerate(ATT):
            x = pad + i * (VW + pad)
            im.paste(view(faces, rr * R, pp * P), (x, y + head))
            im.paste(sprite(fn, rr * R, pp * P), (x + (VW - SW) // 2, y + head + VH + 6))
    im.save(path)

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "gulls":
        designs.DESIGNS = designs.GULLS
        sheet(sys.argv[1])
    else:
        sheet(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
