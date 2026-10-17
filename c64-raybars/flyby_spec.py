#!/usr/bin/env python3
"""The specular highlight: a ground truth vs GOLDSHIP's highlight code.

Ground truth (flyby3d.py's scene): the bars are perfect mirrors and the
light is the sphere on the ship's nose (radius 0.021 m, at Z = 3.16).  Each
camera ray that hits a bar is reflected about the surface normal; where the
reflected ray hits the light, the sample shows the light (white, at full
strength at any distance: a mirror image keeps its brightness).  A modest
bloom follows (Gaussian, sigma 1.5 C64 pixels, half strength), then the
same decimation to 320 x 200 and 16 colours.

The game's code, replicated from its tables: the light seen from the bar
as atan2(dy, dz) with dy = |Y| / 10 and dz = (Z - 3) * 10 (in the game's
units), a spec level per source row spectab[theta2 - angle], lit from
level 3 (+ the segment's drop), coloured by hltab (distance level and
excess), spread over the rows rowstart gives the bar's height.

    python3 flyby_spec.py     # preview_flyby_spec.png, preview_flyby_spec.gif
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import flyby3d as fb
import ship3d

HERE = os.path.dirname(os.path.abspath(__file__))
LZ = fb.ZS + 10.6 * 0.36 / 23.6          # the light on the nose
LR = 1.4 * 0.36 / 23.6                   # its radius
BLOOM_SIGMA = 1.5                        # C64 pixels
BLOOM = 0.5

VS = 64                                  # vertical samples per row in a column

def column_rays():
    """The middle column: 4 samples across, VS down each row."""
    xs = (np.arange(fb.SS) + 0.5) / fb.SS + fb.W // 2
    ys = (np.arange(fb.H * VS) + 0.5) / VS
    px, py = np.meshgrid(xs, ys)
    return (px - fb.W / 2) / fb.F, (fb.CY + 0.5 - py) / fb.F

def column_bloom(h1):
    """Vertical Gaussian of a per-sample-row highlight profile."""
    sig = BLOOM_SIGMA * VS
    k = np.arange(-int(4 * sig), int(4 * sig) + 1)
    g = np.exp(-0.5 * (k / sig) ** 2)
    return np.convolve(h1, g / g.sum(), mode="same")

# ---- ground truth -------------------------------------------------------------------
def mirror(dx, dy, yc, zc, colours, b):
    """Depth, colour and highlight mask of a mirror cylinder per ray."""
    z, col = fb.cylinder(dx, dy, yc, zc, colours, b)
    hit = np.isfinite(z)
    t = np.where(hit, z, 0.0)
    P = np.stack([t * dx, t * dy, t], axis=-1)
    N = np.stack([np.zeros_like(t), P[..., 1] - yc, P[..., 2] - zc], axis=-1) / fb.R
    d = np.stack([dx, dy, np.ones_like(dx)], axis=-1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    r = d - 2 * (d * N).sum(-1, keepdims=True) * N
    oc = P - np.array([0, 0, LZ])
    bq = (oc * r).sum(-1)
    cq = (oc * oc).sum(-1) - LR * LR
    disc = bq * bq - cq
    s = -bq - np.sqrt(np.maximum(disc, 0))
    hl = hit & (disc >= 0) & (s > 0)
    return z, col, hl.astype(float)

def compose(base, hl):
    """The highlight in white over the base, plus the bloom (2-D)."""
    img = base * (1 - hl[..., None]) + 255 * hl[..., None]
    m = Image.fromarray((hl * 255).astype(np.uint8))
    blur = np.asarray(m.filter(ImageFilter.GaussianBlur(BLOOM_SIGMA * fb.SS)), float) / 255
    return np.clip(img + 255 * BLOOM * blur[..., None], 0, 255)

def true_column(yc, z, colours, span=24):
    """Decimated rows around the bar's centre (2 * span + 1 rows), true."""
    dx, dy = column_rays()
    zz, col, hl = mirror(dx, dy, yc, z, colours, fb.bright(z))
    hit = np.isfinite(zz)
    base = np.where(hit[..., None], col, 0.0)
    # bloom along the column (the highlight is a horizontal band: vertical
    # blur is the 2-D blur here)
    blur = column_bloom(hl.mean(axis=1))
    img = base * (1 - hl[..., None]) + 255 * hl[..., None] + 255 * BLOOM * blur[:, None, None]
    avg = np.clip(img, 0, 255).reshape(fb.H, VS, -1, 3).mean(axis=(1, 2))
    idx = fb.to_c64(avg)
    centre = fb.CY - yc / z * fb.F
    c = int(round(centre))
    return [int(idx[r]) if 0 <= r < fb.H else 0 for r in range(c - span, c + span + 1)]

def true_metrics(yc, z, colours):
    """Ground-truth highlight on the middle column: exact thickness (rows of
    coverage), position in the bar (0 top .. 1 bottom), and the rows whose
    decimated colour the highlight and bloom change."""
    dx, dy = column_rays()
    zz, col, hl = mirror(dx, dy, yc, z, colours, fb.bright(z))
    hit = np.isfinite(zz)
    cov = hl.reshape(fb.H, VS, -1).mean(axis=(1, 2))
    barcov = hit.reshape(fb.H, VS, -1).mean(axis=(1, 2))
    thick = cov.sum()
    rows = np.nonzero(barcov >= 0.5)[0]
    pos = None
    if thick > 0 and len(rows):
        c = (cov * np.arange(fb.H)).sum() / thick
        pos = (c - rows[0] + 0.5) / len(rows)
    base = np.where(hit[..., None], col, 0.0)
    blur = column_bloom(hl.mean(axis=1))
    lit = base * (1 - hl[..., None]) + 255 * hl[..., None] + 255 * BLOOM * blur[:, None, None]
    dec = lambda im: fb.to_c64(np.clip(im, 0, 255).reshape(fb.H, VS, -1, 3).mean(axis=(1, 2)))
    changed = int((dec(lit) != dec(base)).sum())
    return thick, pos, changed

def game_metrics(yc, t, h, lev, k=2):
    """The game's highlight on segment k: lit rows and their position."""
    z = fb.zof(t)
    dyv = min(255, int(round(abs(yc) * fb.F / 10)))
    dy = dyv if yc >= 0 else -dyv
    dz = int(round((z - fb.ZS) * 10))
    phi = int(round(math.atan2(dy, dz) * 128 / math.pi)) & 255
    rs = rowstart(h)
    lit = []
    for i in range(24):
        if SPEC[(TH2[i] - phi) & 255] >= HLTHR + DROP[k]:
            lit += range(rs[i], rs[i + 1])
    if not lit:
        return 0, None
    return len(lit), (sum(lit) / len(lit) + 0.5) / h

# ---- the game's code ------------------------------------------------------------------
SPEC = [int(round(8 * max(0.0, math.cos(a * math.pi / 128)) ** 24)) for a in range(256)]
TH2 = [int(round(2 * math.asin((i + 0.5 - 12) / 12) * 128 / math.pi)) & 255 for i in range(24)]
HLTHR, DROP, HLCOL = 3, [4, 2, 0, 2, 4], [12, 12, 15, 1, 1, 1]

def rowstart(h):
    first = [None] * 25
    stp, acc = int(24 * 256 / h), 0
    for j in range(h):
        src = acc >> 8
        if src < 25 and first[src] is None:
            first[src] = j
        acc += stp
    nxt = h
    for i in range(24, -1, -1):
        if first[i] is None:
            first[i] = nxt
        nxt = first[i]
    first[24] = h
    return first

def game_column(yc, t, base_rows, h, lev, k=2):
    """The game's rows for a bar at height yc (metres) at flight frame t,
    segment k: base colours with its highlight overlaid."""
    z = fb.zof(t)
    dyv = min(255, int(round(abs(yc) * fb.F / 10)))
    dy = dyv if yc >= 0 else -dyv                 # above: the light is below
    dz = int(round((z - fb.ZS) * 10))
    phi = int(round(math.atan2(dy, dz) * 128 / math.pi)) & 255
    rows = list(base_rows)
    rs = rowstart(h)
    for i in range(24):
        sp = SPEC[(TH2[i] - phi) & 255]
        e = sp - (HLTHR + DROP[k])
        if e >= 0:
            for j in range(rs[i], rs[i + 1]):
                rows[j] = HLCOL[min(e, 2) + 3 - lev]
    return rows

def game_window(yc, t, rows, span=24):
    """The game's rows placed around the bar's centre like true_column."""
    z = fb.zof(t)
    h = len(rows)
    centre = fb.CY - yc * fb.F / z
    c = int(round(centre))
    top = int(round(centre - h / 2))
    out = []
    for r in range(c - span, c + span + 1):
        out.append(rows[r - top] if top <= r < top + h else 0)
    return out

# ---- outputs ---------------------------------------------------------------------------
CASES = [(0.40, "0.4 m above"), (0.15, "0.15 m above"), (-0.15, "0.15 m below"),
         (-0.40, "0.4 m below")]

def strips(path):
    game, fh = fb.game_lists()
    flev = [0 if h >= 22 else 1 if h >= 16 else 2 if h >= 11 else 3 for h in fh]
    colours = fb.bands48(fb.GOLD)
    PX, RY, SPAN = 3, 3, 24
    rows_n = 2 * SPAN + 1
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
        small = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        font = small = ImageFont.load_default()
    panel = rows_n * RY + 8
    Wd = 150 + fb.FLYD * PX + 20
    Hd = 50 + len(CASES) * (2 * panel + 34)
    im = Image.new("RGB", (Wd, Hd), (14, 14, 22))
    dr = ImageDraw.Draw(im)
    tship = next(t for t in range(fb.FLYD) if fb.zof(t) < fb.ZS)
    dr.text((10, 10), "The gold bar's middle column over a flight, with its highlight "
            "(x: frame 0..239, far to near; ship at frame %d)" % tship,
            fill=(220, 220, 230), font=font)
    y = 50
    for yc, label in CASES:
        for name in ("game now", "ground truth"):
            dr.text((10, y + panel // 2 - 16), label, fill=(200, 200, 210), font=small)
            dr.text((10, y + panel // 2), name, fill=(150, 150, 170), font=small)
            for t in range(fb.FLYD):
                if name == "game now":
                    col = game_window(yc, t, game_column(yc, t, game["gold"][t], fh[t], flev[t]))
                else:
                    col = true_column(yc, fb.zof(t), colours)
                for j, c in enumerate(col):
                    if c:
                        dr.rectangle([150 + t * PX, y + j * RY, 150 + t * PX + PX - 1,
                                      y + j * RY + RY - 1], fill=tuple(int(v) for v in fb.C64RGB[c]))
            dr.line([150 + tship * PX, y, 150 + tship * PX, y + panel - 8], fill=(90, 90, 120))
            y += panel
        y += 34
    im.save(path)

SEGX = [(0, 52), (52, 124), (124, 196), (196, 268), (268, 320)]   # the game's 5 segments

def game_frame(bars, fh, game):
    """What the game's code draws: 5 segments per bar (level roll), its
    highlight per segment, nearer bars over farther, the ship sprite."""
    flev = [0 if h >= 22 else 1 if h >= 16 else 2 if h >= 11 else 3 for h in fh]
    img = np.zeros((fb.H, fb.W), int)
    for yc, t, pal in sorted(bars, key=lambda b: -fb.zof(b[1])):
        h = fh[t]
        top = int(round(fb.CY - yc * fb.F / fb.zof(t) - h / 2))
        for k, (x0, x1) in enumerate(SEGX):
            rows = game_column(yc, t, game[pal][t], h, flev[t], k)
            for j, c in enumerate(rows):
                if 0 <= top + j < fb.H:
                    img[top + j, x0:x1] = c
    rgb = fb.C64RGB[img].astype(np.uint8)
    spr = ship3d.render(0, 0)
    pal = {1: (0x8A, 0x46, 0xAE), 2: (0x7C, 0x70, 0xDA), 3: (255, 255, 255)}
    for r, row in enumerate(spr):
        for c, v in enumerate(row):
            if v:
                yy, xx = fb.CY - 10 + r, fb.W // 2 - 12 + 2 * c
                rgb[yy, xx:xx + 2] = pal[v]
    return rgb

def animation(path, step=3):
    flights = [(fb.GOLD, "gold", -0.30, 0), (fb.P2, "P2", 0.48, 80), (fb.P3, "P3", -0.66, 160)]
    game, fh = fb.game_lists()
    dx, dy = fb.rays()
    ship_z, ship_c = fb.ship_layer(dx, dy)
    frames = []
    for f in range(0, fb.FLYD, step):
        zb = ship_z.copy()
        base = np.where(np.isfinite(zb)[..., None], ship_c, 0.0)
        hl = np.zeros(dx.shape)
        gbars = []
        for pal, pname, yc, st in flights:
            t = (f + st) % fb.FLYD
            z, c, h = mirror(dx, dy, yc, fb.zof(t), fb.bands48(pal), fb.bright(fb.zof(t)))
            m = z < zb
            zb[m] = z[m]
            base[m] = c[m]
            hl[m] = h[m]
            gbars.append((yc, t, pname))
        img = compose(base, hl)
        W2, H2 = fb.W * 2, fb.H * 2
        hi = Image.fromarray(img.astype(np.uint8)).resize((W2, H2), Image.LANCZOS)
        lo = Image.fromarray(fb.C64RGB[fb.decimate(img)].astype(np.uint8)).resize((W2, H2), Image.NEAREST)
        gm = Image.fromarray(game_frame(gbars, fh, game)).resize((W2, H2), Image.NEAREST)
        out = Image.new("RGB", (W2 * 3 + 16, H2), (20, 20, 28))
        out.paste(hi, (0, 0))
        out.paste(lo, (W2 + 8, 0))
        out.paste(gm, (2 * W2 + 16, 0))
        frames.append(out)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=60, loop=0)

def charts(path):
    """Per case: highlight thickness (rows) and position in the bar."""
    game, fh = fb.game_lists()
    flev = [0 if h >= 22 else 1 if h >= 16 else 2 if h >= 11 else 3 for h in fh]
    colours = fb.bands48(fb.GOLD)
    PX, CH = 3, 150
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
        small = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        font = small = ImageFont.load_default()
    Wd = 2 * (60 + fb.FLYD * PX + 30)
    Hd = 70 + len(CASES) * (CH + 50)
    im = Image.new("RGB", (Wd, Hd), (14, 14, 22))
    dr = ImageDraw.Draw(im)
    tship = next(t for t in range(fb.FLYD) if fb.zof(t) < fb.ZS)
    dr.text((10, 8), "Highlight on the gold bar's middle column: thickness (rows, left) and "
            "position in the bar (0 top .. 1 bottom, right); x: flight frame, ship at %d" % tship,
            fill=(220, 220, 230), font=font)
    leg = [((255, 190, 90), "game now: lit rows"), ((120, 220, 255), "ground truth: exact coverage"),
           ((150, 255, 150), "ground truth: rows changed on the C64 (with bloom)")]
    for i, (c, txt) in enumerate(leg):
        dr.text((10 + i * 330, 32), txt, fill=c, font=small)
    summary = []
    y = 70
    for yc, label in CASES:
        g_t, g_p, t_t, t_p, t_c = [], [], [], [], []
        for t in range(fb.FLYD):
            a, b = game_metrics(yc, t, fh[t], flev[t])
            g_t.append(a); g_p.append(b)
            th, ps, ch = true_metrics(yc, fb.zof(t), colours)
            t_t.append(th); t_p.append(ps); t_c.append(ch)
        summary.append((label, g_t, t_t, t_c, g_p, t_p))
        for col, (vals, vmax) in enumerate(((None, 16), (None, 1))):
            x0 = 60 + col * (60 + fb.FLYD * PX + 30)
            dr.rectangle([x0, y, x0 + fb.FLYD * PX, y + CH], outline=(60, 60, 80))
            dr.line([x0 + tship * PX, y, x0 + tship * PX, y + CH], fill=(90, 90, 120))
            dr.text((x0 - 50, y), str(vmax), fill=(150, 150, 170), font=small)
            dr.text((x0 - 50, y + CH - 14), "0", fill=(150, 150, 170), font=small)
            series = ((g_t, (255, 190, 90)), (t_t, (120, 220, 255)), (t_c, (150, 255, 150))) \
                if col == 0 else ((g_p, (255, 190, 90)), (t_p, (120, 220, 255)))
            for vals, c in series:
                for t, v in enumerate(vals):
                    if v is None:
                        continue
                    yy = y + CH - min(v, vmax) / vmax * CH
                    dr.rectangle([x0 + t * PX, yy - 1, x0 + t * PX + 1, yy + 1], fill=c)
        dr.text((10, y + CH + 6), label, fill=(220, 220, 230), font=small)
        y += CH + 50
    im.save(path)
    return summary

if __name__ == "__main__":
    summ = charts(os.path.join(HERE, "preview_flyby_spec_chart.png"))
    print("wrote preview_flyby_spec_chart.png")
    for label, g_t, t_t, t_c, g_p, t_p in summ:
        ahead = range(0, 200)
        print(f"{label}: frames with a highlight: game {sum(1 for v in g_t if v)}, "
              f"truth {sum(1 for v in t_t if v > 0)}; mean thickness while lit: game "
              f"{np.mean([v for v in g_t if v] or [0]):.1f} rows, truth exact "
              f"{np.mean([v for v in t_t if v > 0] or [0]):.2f} rows, truth changed on the C64 "
              f"{np.mean([v for v in t_c if v > 0] or [0]):.1f} rows")
    strips(os.path.join(HERE, "preview_flyby_spec.png"))
    print("wrote preview_flyby_spec.png")
    animation(os.path.join(HERE, "preview_flyby_spec.gif"))
    print("wrote preview_flyby_spec.gif")
