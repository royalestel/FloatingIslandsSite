#!/usr/bin/env python3
"""GOLDSHIP's fly-by, rendered for real: a profiling study.

A true-perspective, full-colour render of the ship (ship3d.py's model) and
three cylinders flying past it, decimated to the C64's 320 x 200 and 16
colours.  From the decimated frames it profiles each bar's height and
per-row colours at every frame of its flight, compares them with the game's
current tables, and writes cached colour tables built from the profile.

Scene (metres; the camera at the origin looking along +z):
  * focal length F = 200 lines.  This is what the game's maths assumes:
    a bar Y/200 m off the centre line and 0.24 m thick shows Y/Z lines off
    centre and 48/Z lines tall.  Screen pixels are taken as square.
  * the ship at Z = 3, its wingspan scaled to 24 pixels (0.36 m), the
    light on its nose.
  * cylinders of radius 0.12 m along x, flying from Z = 12 (4 rows tall)
    to Z = 1.2 at constant speed over FLYD = 240 frames, as in the game.
    Each is painted in 48 horizontal bands: its palette's colours with
    in-between colours mixed in RGB (24 colours: one between each pair;
    12 colours: three).
  * brightness by distance (no light simulation): dim far away (25%),
    rising to the full palette just in front of the ship, then quickly
    falling into shadow once past it (the light is on the nose; the camera
    sees the bars' unlit side): 30% within 0.8 m.

Decimation: 4 x 4 samples per C64 pixel are averaged and matched to the
nearest C64 colour (VICE palette, a perceptual "redmean" distance).

    python3 flyby3d.py            # writes preview_flyby.gif,
                                  # preview_flyby_profile.png, flyprof.inc,
                                  # flyby_sizes.txt (frames at each height)
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import ship3d

HERE = os.path.dirname(os.path.abspath(__file__))
F = 200.0                       # focal length, lines
W, H = 320, 200                 # C64 display window
CY = 99                         # the centre line (raster line 150) in it
SS = 4                          # samples per pixel each way
R = 0.12                        # cylinder radius (0.24 m = 48 units)
ZS = 3.0                        # the ship (and the light on its nose)
Z0, Z1, FLYD = 12.0, 1.2, 240

C64 = [0x000000, 0xFFFFFF, 0x894036, 0x7ABFC7, 0x8A46AE, 0x68A941, 0x3E31A2,
       0xD0DC71, 0x905F25, 0x5C4700, 0xBB776D, 0x555555, 0x808080, 0xACEA88,
       0x7C70DA, 0xABABAB]
C64RGB = np.array([((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in C64], float)
GOLD = [9, 8, 12, 7, 7, 0, 9, 8, 15, 7, 7, 1, 7, 1, 7, 0, 0, 0, 9, 12, 10, 12, 8, 9]
P2 = [8, 12, 7, 8, 11, 8, 15, 7, 1, 7, 1, 7, 7, 15, 8, 11, 9, 9, 11, 8, 12, 10, 12, 8]
P3 = [6, 11, 14, 15, 1, 0, 9, 11, 8, 12, 10, 15]
P4 = [8, 10, 7, 10, 10, 15, 10, 8, 2, 9, 9, 11]
PALETTES = [("gold", GOLD), ("P2", P2), ("P3", P3), ("P4", P4)]

def bands48(pal):
    """48 RGB colours: the palette's colours with in-between colours mixed in."""
    c = C64RGB[pal]
    out = []
    for i in range(48):
        p = i * len(pal) / 48
        a = int(p)
        b = min(a + 1, len(pal) - 1)
        f = p - a
        out.append(c[a] * (1 - f) + c[b] * f)
    return np.array(out)

def zof(t):
    return Z0 - (Z0 - Z1) * t / (FLYD - 1)

def bright(z):
    """Dim far away, full just in front of the ship, quickly into shadow
    past it."""
    if z >= ZS + 0.25:
        return 1.0 - 0.75 * (z - ZS - 0.25) / (Z0 - ZS - 0.25)
    if z >= ZS:
        return 1.0
    return max(0.3, 1.0 - 0.7 * (ZS - z) / 0.8)

def to_c64(rgb):
    """Nearest C64 colour per pixel (redmean distance)."""
    r = rgb[..., None, :]
    d = r - C64RGB
    rm = (r[..., 0] + C64RGB[:, 0]) / 2
    dist = (2 + rm / 256) * d[..., 0] ** 2 + 4 * d[..., 1] ** 2 + (2 + (255 - rm) / 256) * d[..., 2] ** 2
    return np.argmin(dist, axis=-1)

# ---- rays -----------------------------------------------------------------------
def rays(cols=None):
    """Ray directions (x/z, y/z) for the samples of the window, or of some columns."""
    xs = np.arange(W * SS) if cols is None else np.concatenate(
        [np.arange(c * SS, c * SS + SS) for c in cols])
    ys = np.arange(H * SS)
    px, py = np.meshgrid((xs + 0.5) / SS, (ys + 0.5) / SS)
    return (px - W / 2) / F, (CY + 0.5 - py) / F

def cylinder(dx, dy, yc, zc, colours, b):
    """Depth (z) and colour of a cylinder along x at (yc, zc) for each ray."""
    a = dy * dy + 1
    bq = -2 * (dy * yc + zc)
    c = yc * yc + zc * zc - R * R
    disc = bq * bq - 4 * a * c
    hit = disc >= 0
    t = np.where(hit, (-bq - np.sqrt(np.maximum(disc, 0))) / (2 * a), np.inf)
    y = t * dy                                    # the surface point's height
    y = np.where(hit, y, yc)
    band = np.clip(((yc + R - y) / (2 * R) * 48).astype(int), 0, 47)   # top band first
    col = colours[band] * b
    return np.where(hit, t, np.inf), col

def ship_layer(dx, dy):
    """Depth and colour of the ship (z-buffered, flat-shaded), per ray."""
    s = 0.36 / 23.6
    Hh, Ww = dx.shape
    zb = np.full((Hh, Ww), np.inf)
    col = np.zeros((Hh, Ww, 3))
    L = np.array(ship3d.LIGHT, float)
    L /= np.linalg.norm(L)
    mat = {"hull": np.array([138, 70, 174.]), "trim": np.array([124, 112, 218.]),
           "glow": np.array([255, 255, 255.])}
    # screen position of each sample, in pixels
    sx = dx * F + W / 2
    sy = CY + 0.5 - dy * F
    for poly, kind in ship3d.model():
        P = np.array([(x * s, y * s, ZS + z * s) for x, y, z in poly])
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if np.linalg.norm(n) < 1e-12:
            continue
        n /= np.linalg.norm(n)
        if n @ P[0] > 0:                          # face the camera
            n = -n
        if kind == "glow":
            c = mat["glow"]
        else:
            c = mat[kind] * (0.35 + 0.8 * max(0.0, n @ L))
        Q = np.column_stack([P[:, 0] / P[:, 2] * F + W / 2, CY + 0.5 - P[:, 1] / P[:, 2] * F,
                             P[:, 2]])
        for k in range(1, len(Q) - 1):
            a, b, cc = Q[0], Q[k], Q[k + 1]
            d = (b[1] - cc[1]) * (a[0] - cc[0]) + (cc[0] - b[0]) * (a[1] - cc[1])
            if abs(d) < 1e-12:
                continue
            w0 = ((b[1] - cc[1]) * (sx - cc[0]) + (cc[0] - b[0]) * (sy - cc[1])) / d
            w1 = ((cc[1] - a[1]) * (sx - cc[0]) + (a[0] - cc[0]) * (sy - cc[1])) / d
            w2 = 1 - w0 - w1
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            # perspective-correct depth: interpolate 1/z
            iz = w0 / a[2] + w1 / b[2] + w2 / cc[2]
            z = np.where(inside, 1 / np.maximum(iz, 1e-9), np.inf)
            m = z < zb
            zb[m] = z[m]
            col[m] = c
    return zb, col

_SHIP = None

def frame(bars, with_ship=True):
    """bars: [(yc, zc, colours48)] -> RGB samples of the window (H*SS, W*SS, 3)."""
    dx, dy = rays()
    zb = np.full(dx.shape, np.inf)
    img = np.zeros(dx.shape + (3,))
    for yc, zc, colours in bars:
        z, c = cylinder(dx, dy, yc, zc, colours, bright(zc))
        m = z < zb
        zb[m] = z[m]
        img[m] = c[m]
    if with_ship:
        global _SHIP
        if _SHIP is None:
            _SHIP = ship_layer(dx, dy)      # the ship never moves: once
        z, c = _SHIP
        m = z < zb
        zb[m] = z[m]
        img[m] = c[m]
    return img

def decimate(img):
    """Average SS x SS samples per pixel, then the nearest C64 colour."""
    h, w = img.shape[0] // SS, img.shape[1] // SS
    avg = img.reshape(h, SS, w, SS, 3).mean(axis=(1, 3))
    return to_c64(avg)

# ---- the profile: one bar on the centre line, per palette and frame --------
def column(dx, dy, yc, z, cols):
    """The decimated rows (top to bottom) of one bar in the sampled column."""
    zz, c = cylinder(dx, dy, yc, z, cols, bright(z))
    hit = np.isfinite(zz)
    c = np.where(hit[..., None], c, 0.0)
    cov = hit.reshape(H, SS, -1).mean(axis=(1, 2))
    avg = c.reshape(H, SS, -1, 3).sum(axis=(1, 2)) / hit[0].size / SS
    idx = to_c64(avg)
    return [int(idx[r]) for r in range(H) if cov[r] >= 0.5]

def profile(yc=0.0, shifts=8):
    """For each palette and flight frame t: the decimated rows of a bar at
    height yc, in the screen's middle column.  A bar's row count depends on
    where it sits within a line, so each frame is sampled at `shifts`
    sub-line positions; the height is their average, rounded, and the
    colours are those of a position giving that height."""
    dx, dy = rays(cols=[W // 2])
    out = {}
    for name, pal in PALETTES:
        cols = bands48(pal)
        lists = []
        for t in range(FLYD):
            z = zof(t)
            cand = [column(dx, dy, yc + k / shifts * z / F, z, cols) for k in range(shifts)]
            h = int(round(sum(len(c) for c in cand) / shifts))
            lists.append(min(cand, key=lambda c: (abs(len(c) - h), cand.index(c))))
        out[name] = lists
    return out

def true_height(yc, zc):
    """The bar's exact height in lines (tangents from the camera)."""
    d = math.hypot(yc, zc)
    phi, a = math.atan2(yc, zc), math.asin(R / d)
    return F * (math.tan(phi + a) - math.tan(phi - a))

# ---- the game's current tables, for comparison --------------------------------
def game_lists():
    """The colours the game shows now: nearest-neighbour from the 24-row
    palette (P3/P4 dithered to 24), dimmed by distance level."""
    fh, flev = [], []
    for t in range(FLYD):
        z = zof(t)
        h = int(round(48 / z))
        fh.append(h)
        flev.append(0 if h >= 22 else 1 if h >= 16 else 2 if h >= 11 else 3)
    DIMS = [list(range(16)),
            [0, 15, 9, 14, 6, 11, 6, 8, 9, 9, 8, 11, 11, 5, 6, 12],
            [0, 12, 9, 14, 6, 11, 6, 8, 9, 0, 9, 0, 11, 5, 6, 11],
            [0, 11, 0, 6, 0, 0, 0, 9, 0, 0, 9, 0, 0, 11, 0, 11]]
    def rows24(pal):
        if len(pal) == 24:
            return [(c, c) for c in pal]
        out = []
        for i, a in enumerate(pal):
            b = pal[i + 1] if i + 1 < len(pal) else a
            out += [(a, a), (a, b)]
        return out
    out = {}
    for name, pal in PALETTES:
        p = rows24(pal)
        lists = []
        for t in range(FLYD):
            h, lv = fh[t], flev[t]
            stp, acc, rows = int(24 * 256 / h), 0, []
            for j in range(h):
                e, o = p[acc >> 8]
                rows.append(DIMS[lv][e if j % 2 == 0 else o])
                acc += stp
            lists.append(rows)
        out[name] = lists
    return out, fh

# ---- outputs ----------------------------------------------------------------------
def animation(path, step=3):
    """Hi-res render (left) and its C64 decimation (right), side by side."""
    flights = [(GOLD, -0.30, 0), (P2, 0.48, 80), (P3, -0.66, 160)]   # palette, Y, stagger
    frames = []
    for f in range(0, FLYD, step):
        bars = []
        for pal, yc, st in flights:
            t = (f + st) % FLYD
            bars.append((yc, zof(t), bands48(pal)))
        img = frame(bars)
        hi = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((W * 2, H * 2), Image.LANCZOS)
        lo = Image.fromarray(C64RGB[decimate(img)].astype(np.uint8)).resize((W * 2, H * 2), Image.NEAREST)
        both = Image.new("RGB", (W * 4 + 8, H * 2), (20, 20, 28))
        both.paste(hi, (0, 0))
        both.paste(lo, (W * 2 + 8, 0))
        frames.append(both)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=60, loop=0)

def report(path, prof, game, fh, prof_off):
    """Per palette: the game's current column colours vs the profiled ones,
    frame by frame, and the heights."""
    PX = 3                                        # pixels per frame (x)
    RY = 3                                        # pixels per row (y)
    hmax = max(max(len(r) for r in prof[n]) for n, _ in PALETTES)
    panel_h = hmax * RY + 10
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
        small = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        font = small = ImageFont.load_default()
    plot_h = 220
    Wd = 120 + FLYD * PX + 20
    Hd = 50 + len(PALETTES) * (2 * panel_h + 40) + plot_h + 60
    im = Image.new("RGB", (Wd, Hd), (14, 14, 22))
    dr = ImageDraw.Draw(im)
    dr.text((10, 10), "Bar columns over a flight (x: frame 0..239, far to near; ship at frame %d)"
            % next(t for t in range(FLYD) if zof(t) < ZS), fill=(220, 220, 230), font=font)
    y = 50
    tship = next(t for t in range(FLYD) if zof(t) < ZS)
    for name, _ in PALETTES:
        for label, lists in (("now", game[name]), ("profiled", prof[name])):
            dr.text((10, y + panel_h // 2 - 8), f"{name} {label}", fill=(200, 200, 210), font=small)
            for t, rows in enumerate(lists):
                top = y + (hmax - len(rows)) * RY // 2
                for j, c in enumerate(rows):
                    dr.rectangle([120 + t * PX, top + j * RY, 120 + t * PX + PX - 1,
                                  top + j * RY + RY - 1], fill=tuple(int(v) for v in C64RGB[c]))
            dr.line([120 + tship * PX, y, 120 + tship * PX, y + panel_h - 8], fill=(90, 90, 120))
            y += panel_h
        y += 40
    # heights: game (48/Z), exact on the centre line, exact off-centre, decimated
    dr.text((10, y), "bar height, lines", fill=(220, 220, 230), font=font)
    y0 = y + 20
    def plot(vals, colour):
        pts = [(120 + t * PX + 1, y0 + plot_h - v * plot_h / 48) for t, v in enumerate(vals)]
        dr.line(pts, fill=colour, width=2)
    plot(fh, (230, 200, 90))
    plot([true_height(0, zof(t)) for t in range(FLYD)], (120, 220, 255))
    plot([true_height(0.5, zof(t)) for t in range(FLYD)], (255, 120, 160))
    plot([len(r) for r in prof["gold"]], (140, 255, 140))
    dr.text((130, y0 + 4), "game now: round(48/Z)", fill=(230, 200, 90), font=small)
    dr.text((130, y0 + 22), "exact, on the centre line", fill=(120, 220, 255), font=small)
    dr.text((130, y0 + 40), "exact, 0.5 m (100 units) off centre", fill=(255, 120, 160), font=small)
    dr.text((130, y0 + 58), "decimated rows (profiled)", fill=(140, 255, 140), font=small)
    im.save(path)

def size_counts(heights):
    """{height: frames spent at it} over a flight."""
    c = {}
    for h in heights:
        c[h] = c.get(h, 0) + 1
    return c

def size_report(path, fh, prof, prof_off):
    """Frames a bar spends at each size on screen: the game now, and the
    decimated true-perspective bar on the centre line and 0.5 m off it."""
    now = size_counts(fh)
    cen = size_counts([len(r) for r in prof["gold"]])
    off = size_counts([len(r) for r in prof_off["gold"]])
    hs = sorted(set(now) | set(cen) | set(off))
    lines = ["Frames a bar spends at each height (rows) over its 240-frame flight",
             "(Z = 12 -> 1.2 m at constant speed; ship at Z = 3, from frame %d)."
             % next(t for t in range(FLYD) if zof(t) < ZS), "",
             "height | game now (48/Z) | profiled, centre line | profiled, 0.5 m off centre",
             "------ | --------------- | --------------------- | -------------------------"]
    for h in hs:
        lines.append(f"{h:6d} | {now.get(h, 0):15d} | {cen.get(h, 0):21d} | {off.get(h, 0):25d}")
    lines.append(f"{'total':>6} | {sum(now.values()):15d} | {sum(cen.values()):21d} | {sum(off.values()):25d}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return lines

def hl_level(z):
    """The highlight's distance level (0 brightest .. 3), following the bars'
    brightness."""
    b = bright(z)
    return 0 if b >= 0.85 else 1 if b >= 0.6 else 2 if b >= 0.4 else 3

def tables(path, prof):
    """Cached colour tables from the profile, for goldship.s: per palette,
    one list per flight frame (identical lists shared), the profiled height
    per frame, the highlight level per frame, and the near clip's lists."""
    out = ["; Generated by flyby3d.py -- do not edit by hand.",
           "; Bar colours profiled from decimated true-perspective renders.",
           "; flyh: bar height per flight frame t; flylev: highlight level per t;",
           "; flpl<p>/flph<p>: palette p's list for frame t (rows top to bottom);",
           "; flclip<p>: palette p's near-clip list (frame FLYD-2, middle rows black).",
           ""]
    def emit(name, vals):
        out.append(f"{name}:")
        for i in range(0, len(vals), 16):
            out.append("        .byte " + ",".join(f"${v & 255:02x}" for v in vals[i:i + 16]))
    heights = [len(r) for r in prof["gold"]]
    for name, _ in PALETTES:
        assert [len(r) for r in prof[name]] == heights, name
    tc = FLYD - 2
    hc = heights[tc]
    cut = (hc + 2) // 3
    out.insert(5, f"FLCLIPH = {hc}")
    emit("flyh", heights)
    emit("flylev", [hl_level(zof(t)) for t in range(FLYD)])
    pool, data = {}, []
    for p, (name, _) in enumerate(PALETTES):
        addr = []
        for rows in prof[name]:
            key = tuple(rows)
            if key not in pool:
                pool[key] = len(data)
                data += rows
            addr.append(pool[key])
        for half, op in (("l", "lobytes"), ("h", "hibytes")):
            out.append(f"flp{half}{p}:")
            for i in range(0, FLYD, 8):
                out.append(f"        .{op} " + ",".join(f"flcol+{a}" for a in addr[i:i + 8]))
    emit("flcol", data)
    for p, (name, _) in enumerate(PALETTES):
        rows = list(prof[name][tc])
        for j in range(hc // 2 - cut, hc // 2 + cut):
            rows[j] = 0
        emit(f"flclip{p}", rows)
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    return len(data), len(pool)

if __name__ == "__main__":
    prof = profile(0.0)
    prof_off = profile(0.5)
    game, fh = game_lists()
    nbytes, nlists = tables(os.path.join(HERE, "flyprof.inc"), prof)
    report(os.path.join(HERE, "preview_flyby_profile.png"), prof, game, fh, prof_off)
    for ln in size_report(os.path.join(HERE, "flyby_sizes.txt"), fh, prof, prof_off):
        print(ln)
    animation(os.path.join(HERE, "preview_flyby.gif"))
    d0 = [len(r) for r in prof["gold"]]
    d5 = [len(r) for r in prof_off["gold"]]
    print("heights, decimated (centre line):", d0[0], "..", d0[-1],
          " game:", fh[0], "..", fh[-1])
    print("largest height difference, profiled - game: centre %+d, 0.5 m off %+d"
          % (max((a - b for a, b in zip(d0, fh)), key=abs), max((a - b for a, b in zip(d5, fh)), key=abs)))
    print(f"tables: {nlists} distinct lists, {nbytes} colour bytes (4 palettes x {FLYD} frames)")
