#!/usr/bin/env python3
"""The red ramp (25, as red_ramp25.py) plus purple and yellow swatches, numbered
so the red ones keep 1..25: purple 26.., then yellow, each family ordered by
measured light.  Types: solid, a / b flicker pair (phase swapped line to line),
"x + white every other", and [ghost] ones (an idle byte darkens part of the line:
the blue ramp's 1/4 and checker patterns).  Two lines a swatch, CRT look.

    python3 ramp_extra_video.py out.mp4 [--merged]     (--merged: one ramp, dark to light)
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import preview_v10 as v10
import red_ramp25 as r25

PU, YE, RD, LR, DG, GR, LG, WH = 4, 7, 2, 10, 11, 12, 15, 1

# ("s", c) solid; ("f", a, b) a / b; ("e", a, b) a on one line of 4 else b; ("g", blue swatch, colour)
PURPLE = [("g", 29, PU), ("g", 5, PU), ("s", PU), ("f", PU, DG), ("f", PU, RD),
          ("f", PU, GR), ("f", PU, LR)]
YELLOW = [("g", 29, YE), ("g", 5, YE), ("s", YE), ("f", YE, GR), ("f", LR, YE),
          ("f", YE, LG), ("e", WH, YE), ("f", YE, WH)]

def colour(e, rp, p):
    if e[0] == "s":
        return e[1]
    if e[0] == "f":
        return e[1] if (rp + p) % 2 == 0 else e[2]
    if e[0] == "e":
        return e[1] if rp == 0 and p == 0 else e[2]
    return e[2]

def ghost(e, rp, p):
    return v10.ghost(e[1], rp, p) if e[0] == "g" else 0

def light(e):
    tot = 0
    for rp in (0, 1):
        for p in (0, 1):
            c = ((fb.C64RGB[colour(e, rp, p)] / 255) ** 2.2) @ np.array([0.2126, 0.7152, 0.0722])
            tot += c * (8 - bin(ghost(e, rp, p)).count("1")) / 8
    return tot / 4

def name(e):
    n = fl.NAMES
    if e[0] == "s":
        return n[e[1]]
    if e[0] == "f":
        return f"{n[e[1]]} / {n[e[2]]}"
    if e[0] == "e":
        return f"{n[e[2]]} + {n[e[1]]} every other"
    return n[e[2]] + {29: " 1/4 inverting", 5: " checker inverting"}[e[1]] + "  [ghost]"

# moved by eye (1-based positions in the measured order; each moves this many places darker):
# 20 yellow 1/4 inverting, 28 yellow checker inverting, 32 light red / yellow
MOVE_DARKER = [(20, 4), (28, 4), (32, 4)]

def build_rows(merged):
    rows = []                                          # (label, entry or red index)
    for i in range(r25.N):
        e = r25.ENTRIES[i]
        rows.append((r25.name(i) + ("  [ghost]" if e[0] == "g" else ""),
                     float(r25.RAMP_L[i]), lambda rp, p, i=i: (r25.colour(i, rp, p), r25.ghost(i, rp, p))))
    L = lambda y: float(116 * y ** (1 / 3) - 16 if y > 0.008856 else y * 903.3)
    for fam in (PURPLE, YELLOW):
        for e in sorted(fam, key=light):
            rows.append((name(e), L(light(e)), lambda rp, p, e=e: (colour(e, rp, p), ghost(e, rp, p))))
    if merged:                                         # one ramp: everything dark to light
        rows.sort(key=lambda r: r[1])
        moved = sorted(((old - 1 - places, rows[old - 1]) for old, places in MOVE_DARKER),
                       key=lambda t: t[0])                # (final position, item), by identity
        rows = [r for r in rows if all(r is not m for _, m in moved)]
        for pos, item in moved:
            rows.insert(pos, item)
    return rows

def main(path, seconds=6, merged=False):
    rows = build_rows(merged)
    ROWS, Z, PAD = 2, 7, 4
    font, small = fl.fonts()
    txt = [f"{i + 1:2d}   {n}   L* {ls:.0f}" for i, (n, ls, _) in enumerate(rows)]
    tw = int(max(small.getlength(t) for t in txt)) + 4         # the labels' width in pixels
    WIDTH = -(-tw // Z // 8) * 8                                # swatches as wide as the text (8 px steps)
    h = PAD * 2 + ROWS * len(rows)
    x = np.arange(WIDTH)
    looks = []
    for p in (0, 1):
        img = np.zeros((h, WIDTH), int)
        for i, (_, _, fn) in enumerate(rows):
            for s in range(ROWS):
                r = PAD + ROWS * i + s
                c, g = fn(r & 1, p)
                img[r] = c
                if g:
                    img[r, ((g >> (7 - x % 8)) & 1) == 1] = 0
        looks.append(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    W, H = WIDTH * Z, h * Z
    v = iv.Video(path, 16 + W + 16 + tw + 16, H + 50)
    for f in range(seconds * 60):
        c = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(c)
        dr.text((16, 8), ("all swatches, darkest first (measured light)   CRT" if merged else "red ramp 1-25, then purple, then yellow (each by measured light)   CRT"),
                fill=(170, 176, 210), font=small)
        c.paste(looks[f & 1], (16, 34))
        for i, (n, ls, _) in enumerate(rows):
            y = 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8
            dr.text((W + 32, y), txt[i], fill=(190, 195, 225), font=small)
        v.add(c)
    v.close()
    print("wrote", path, len(rows), "swatches")
    for i, (n, ls, _) in enumerate(rows if merged else rows[r25.N:], 1 if merged else r25.N + 1):
        print(i, n, round(ls))

def still(path, merged=True, scale=2):
    """One big PNG (frame parity 0) for zooming: numbers 2 x larger."""
    from PIL import ImageFont
    import ramp_extra_video as me
    rows = me.build_rows(merged)
    ROWS, Z, PAD = 2, 7 * scale, 4
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 15 * scale)
    txt = [f"{i + 1:2d}  {n}  L* {ls:.0f}" for i, (n, ls, _) in enumerate(rows)]
    tw = int(max(font.getlength(t) for t in txt)) + 4
    WIDTH = -(-tw // Z // 8) * 8                                # swatches as wide as the labels
    h = PAD * 2 + ROWS * len(rows)
    x = np.arange(WIDTH)
    img = np.zeros((h, WIDTH), int)
    for i, (_, _, fn) in enumerate(rows):
        for s_ in range(ROWS):
            r = PAD + ROWS * i + s_
            c, g = fn(r & 1, 0)
            img[r] = c
            if g:
                img[r, ((g >> (7 - x % 8)) & 1) == 1] = 0
    look = lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z)
    W, H = WIDTH * Z, h * Z
    c = Image.new("RGB", (16 + W + 16 + tw + 16, H + 50 * scale), (8, 8, 16))
    dr = ImageDraw.Draw(c)
    c.paste(look, (16, 34 * scale))
    for i, (n, ls, _) in enumerate(rows):
        y = 34 * scale + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 12 * scale
        dr.text((W + 32, y), txt[i], fill=(235, 238, 255), font=font)
    c.save(path)
    print("wrote", path, c.size)

if __name__ == "__main__":
    if sys.argv[1].endswith(".png"):
        still(sys.argv[1], "--merged" in sys.argv)
    else:
        main(sys.argv[1], merged="--merged" in sys.argv)
