#!/usr/bin/env python3
"""The red ramp (25, as red_ramp25.py) plus purple and yellow swatches, numbered
so the red ones keep 1..25: purple 26.., then yellow, each family ordered by
measured light.  Types: solid, a / b flicker pair (phase swapped line to line),
"x + white every other", and [ghost] ones (an idle byte darkens part of the line:
the blue ramp's 1/4 and checker patterns).  Two lines a swatch, CRT look.

    python3 ramp_extra_video.py out.mp4
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

def main(path, seconds=6):
    rows = []                                          # (label, entry or red index)
    for i in range(r25.N):
        e = r25.ENTRIES[i]
        rows.append((r25.name(i) + ("  [ghost]" if e[0] == "g" else ""),
                     float(r25.RAMP_L[i]), lambda rp, p, i=i: (r25.colour(i, rp, p), r25.ghost(i, rp, p))))
    L = lambda y: float(116 * y ** (1 / 3) - 16 if y > 0.008856 else y * 903.3)
    for fam in (PURPLE, YELLOW):
        for e in sorted(fam, key=light):
            rows.append((name(e), L(light(e)), lambda rp, p, e=e: (colour(e, rp, p), ghost(e, rp, p))))
    ROWS, Z, PAD, WIDTH = 2, 7, 4, 160
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
    font, small = fl.fonts()
    W, H = WIDTH * Z, h * Z
    v = iv.Video(path, W + 430, H + 50)
    for f in range(seconds * 60):
        c = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(c)
        dr.text((16, 8), "red ramp 1-25, then purple, then yellow (each by measured light)   CRT",
                fill=(170, 176, 210), font=small)
        c.paste(looks[f & 1], (16, 34))
        for i, (n, ls, _) in enumerate(rows):
            y = 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8
            dr.text((W + 32, y), f"{i + 1:2d}   {n}   L* {ls:.0f}", fill=(190, 195, 225), font=small)
        v.add(c)
    v.close()
    print("wrote", path, len(rows), "swatches")
    for i, (n, ls, _) in enumerate(rows[r25.N:], r25.N + 1):
        print(i, n, round(ls))

if __name__ == "__main__":
    main(sys.argv[1])
