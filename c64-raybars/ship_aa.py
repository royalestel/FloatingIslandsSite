#!/usr/bin/env python3
"""GOLDSHIP's ship at 9 x 9 attitudes, each an antialiased pair of sprite
frames shown on alternate frames (ship3d.py's model is the master).

The grid: roll -25..25 degrees in 6.25-degree steps (goldship's eased roll,
-8..8, two units a step) by pitch -30..30 in 7.5-degree steps (its eased
climb speed vy, -64..64, 16 a step).  81 pairs, 162 frames, 10368 bytes.

A pair.  From the model's sample counts (8 x 4 per multicolour pixel):
  - a covered pixel is lit in both frames; a pixel with a touch of the
    nose light shows it in one frame;
  - a half covered edge pixel is lit in one frame of the two, in a
    checkerboard, so it shows at half strength in time and the edge is
    dithered on / off along the line, which composite video blurs;
  - a pixel split between shadowed and lit hull alternates purple and
    light blue in time, in opposite phase on neighbouring lines, so the
    PAL delay line blends them as well (purple and light blue are one
    brightness level apart: little flicker).
The thresholds and the checkerboard's phase are chosen per attitude: each
candidate pair is seen through interlace.py's PAL CRT model and the eye,
and compared with the model's coverage seen through the same CRT; the
closest wins.

    python3 ship_aa.py              # preview_ship_aa.png (all 81: full
                                    # colour, one frame, the pair as seen)
    python3 ship_aa.py page.html    # also the live page (the ship flying,
                                    # its pair swapping 60 times a second)
"""
import base64, io, json, math, os, sys
import numpy as np
import ship3d

HERE = os.path.dirname(os.path.abspath(__file__))
NR = NP = 9
ROLLS = [-25 + 6.25 * i for i in range(NR)]
PITCHES = [-30 + 7.5 * j for j in range(NP)]
GRID = [(r, p) for r in ROLLS for p in PITCHES]        # frame pair k = ri * 9 + pi

SHIPPAL = {1: (0x8A, 0x46, 0xAE), 2: (0x7C, 0x70, 0xDA), 3: (0xFF, 0xFF, 0xFF)}
REDPAL = {1: (0x89, 0x40, 0x36), 2: (0x90, 0x5F, 0x25), 3: (0xD0, 0xDC, 0x71)}

def make_pair(counts, single, hi, lo, phase, lines):
    """Two 21 x 12 class frames from sample counts (see the docstring)."""
    tot = ship3d.SX * ship3d.SY
    f0 = [[0] * 12 for _ in range(21)]
    f1 = [[0] * 12 for _ in range(21)]
    for r in range(21):
        for c in range(12):
            n0, n1, n2, n3 = counts[r][c]
            cov = (n1 + n2 + n3) / tot
            hull = n1 + n2
            col = 2 if n2 >= n1 else 1
            split = hull and min(n1, n2) >= 0.3 * hull
            odd = (r + c + phase) % 2
            if n3 * 5 >= tot:
                f0[r][c] = f1[r][c] = 3
            elif cov >= hi:
                a, b = (1, 2) if split else (col, col)
                if lines and r % 2:
                    a, b = b, a
                f0[r][c], f1[r][c] = a, b
                if n3 * 12 >= tot:                   # a touch of the light
                    (f1 if odd else f0)[r][c] = 3
            elif cov >= lo or single[r][c]:
                v = 3 if n3 > hull else col
                (f1 if odd else f0)[r][c] = v
    return f0, f1

def rgb(frame, pal=SHIPPAL, pad=4):
    """A class frame -> sRGB pixels (2 per multicolour pixel), black around."""
    a = np.zeros((21 + 2 * pad, 24 + 4 * pad, 3), np.uint8)
    for r, line in enumerate(frame):
        for c, v in enumerate(line):
            if v:
                a[pad + r, 2 * pad + 2 * c:2 * pad + 2 * c + 2] = pal[v]
    return a

def target(counts, pad=4):
    """The model's own colour per pixel: its samples' mean in linear light."""
    import flicker as fl
    tot = ship3d.SX * ship3d.SY
    L = {k: fl.lin(v) for k, v in SHIPPAL.items()}
    a = np.zeros((21 + 2 * pad, 24 + 4 * pad, 3))
    for r in range(21):
        for c in range(12):
            n = counts[r][c]
            m = sum(n[k] * L[k] for k in (1, 2, 3)) / tot
            a[pad + r, 2 * pad + 2 * c:2 * pad + 2 * c + 2] = m
    return fl.srgb(a)

def err(a, b):
    """Difference of two pictures as seen, with a little eye blur."""
    a, b = a.astype(float), b.astype(float)
    def blur(x):
        x = (np.roll(x, 1, 0) + 2 * x + np.roll(x, -1, 0)) / 4
        return (np.roll(x, 1, 1) + 2 * x + np.roll(x, -1, 1)) / 4
    d = blur(a) - blur(b)
    return float(np.sqrt((d ** 2).mean()))

CANDS = [(hi, lo, ph, ln) for hi in (0.6, 0.7, 0.8) for lo in (0.2, 0.28, 0.36)
         for ph in (0, 1) for ln in (False, True)]

def best_pair(roll, pitch):
    """-> (f0, f1, single frame, error of the pair, error of the single)."""
    import interlace as il
    counts = ship3d.sample_counts(roll, pitch)
    single = ship3d.render(roll, pitch)
    want = il.crt(target(counts))
    best = None
    for cand in CANDS:
        f0, f1 = make_pair(counts, single, *cand)
        e = err(il.seen([rgb(f0), rgb(f1)]), want)
        if best is None or e < best[0]:
            best = (e, f0, f1)
    es = err(il.seen([rgb(single)]), want)
    return best[1], best[2], single, best[0], es

def pack(frame):
    out = []
    for row in frame:
        bits = 0
        for v in row:
            bits = bits << 2 | v
        out += [bits >> 16 & 255, bits >> 8 & 255, bits & 255]
    return out + [0]

_cache = None
def pairs():
    """All 81: [(f0, f1, single, err pair, err single)], cached."""
    global _cache
    if _cache is None:
        _cache = [best_pair(r, p) for r, p in GRID]
    return _cache

def sprite_bytes():
    """162 frames x 64 bytes: pair k's two frames at 2k, 2k + 1."""
    out = []
    for f0, f1, *_ in pairs():
        out += pack(f0) + pack(f1)
    return out

def roll_index(roll):
    """goldship's roll -8..8 -> grid row, the nearest (ties away from 0)."""
    return 4 + int(math.copysign(math.floor(abs(roll) / 2 + 0.5), roll))

def pitch_index(v8):
    """(vy + 64) >> 3, 0..16 -> grid column (vy 16 a step; ties away from 0)."""
    vy = v8 * 8 - 64 + 4                       # the middle of the 8 vy values
    return max(0, min(8, 4 + int(math.copysign(math.floor(abs(vy) / 16 + 0.5), vy))))

# ---- previews --------------------------------------------------------------------
def sheet(path):
    from PIL import Image, ImageDraw
    import interlace as il
    import ship_hires as sh
    import flicker as fl
    font, small = fl.fonts()
    Z = 4
    VW, VH = 200, 175
    cw, chh = VW + 12, VH + 21 * Z + 26
    W, H = 70 + NP * cw, 80 + NR * chh
    im = Image.new("RGB", (W, H), (8, 8, 14))
    dr = ImageDraw.Draw(im)
    dr.text((10, 10), "GOLDSHIP: 81 attitudes (roll down, pitch across). Each: full colour; "
            "below, one frame (left) and the antialiased pair as a PAL TV shows it (right), at 4x",
            fill=(225, 225, 235), font=font)
    for j, p in enumerate(PITCHES):
        dr.text((70 + j * cw + 4, 48), f"pitch {p:+g}", fill=(170, 170, 190), font=small)
    faces = ship3d.model()
    tot_p = tot_s = 0
    for k, ((r, p), (f0, f1, single, ep, es)) in enumerate(zip(GRID, pairs())):
        i, j = divmod(k, NP)
        x, y = 70 + j * cw, 72 + i * chh
        if j == 0:
            dr.text((8, y + VH // 2), f"roll\n{r:+g}", fill=(170, 170, 190), font=small)
        im.paste(sh.view(faces, r, p), (x, y))
        two = il.seen([rgb(f0, pad=0), rgb(f1, pad=0)]).astype(np.uint8)
        im.paste(Image.fromarray(rgb(single, pad=0)).resize((24 * Z, 21 * Z), Image.NEAREST),
                 (x + 2, y + VH + 4))
        im.paste(Image.fromarray(two).resize((24 * Z, 21 * Z), Image.NEAREST),
                 (x + VW - 24 * Z - 2, y + VH + 4))
        dr.text((x + 2, y + VH + 6 + 21 * Z), f"err {es:.0f} -> {ep:.0f}",
                fill=(130, 130, 150), font=small)
        tot_p += ep
        tot_s += es
    im.save(path, optimize=True)
    return tot_s / len(GRID), tot_p / len(GRID)

def page(path):
    """A live page: the ship flying through bars on autopilot, its pair
    swapping 60 times a second."""
    data = {"rolls": ROLLS, "pitches": PITCHES,
            "pairs": [["".join(map(str, sum(f, []))) for f in (f0, f1)]
                      for f0, f1, *_ in pairs()]}
    tpl = open(os.path.join(HERE, "ship_aa_page.html")).read()
    open(path, "w").write(tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"))))

if __name__ == "__main__":
    es, ep = sheet(os.path.join(HERE, "preview_ship_aa.png"))
    print(f"wrote preview_ship_aa.png; mean error as seen: one frame {es:.1f}, pair {ep:.1f}")
    if len(sys.argv) > 1:
        page(sys.argv[1])
        print("wrote", sys.argv[1])
