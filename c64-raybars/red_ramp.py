#!/usr/bin/env python3
"""A red ramp built like the flat blue one (ramp_flat_video: v10 without the
ghost-byte swatches): each blue-ramp colour swapped for a red-family one
(blue -> brown, purple -> red, light blue -> light red, cyan -> light grey;
dark grey, grey and white kept), same kinds of swatch (solid, a / b flicker
with the phase swapped line to line, x + white every other, stripes),
ordered by measured light (no eye ordering yet).  Video: two lines a
swatch, numbered, CRT.

    python3 red_ramp.py red_ramp.mp4
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv

BK, WH, RD, BR, LR, DG, GR, LG = 0, 1, 2, 9, 10, 11, 12, 15
# (kind, a, b): "s" solid a; "f" a / b flicker (a on frame p where rp+p even);
# "e" a every other (p0 r0), b elsewhere; "t" stripes: a on r0, b on r1
SWATCHES = [("s", BK, BK), ("s", BR, BR), ("f", BR, DG), ("f", BR, RD), ("f", RD, DG),
            ("s", RD, RD), ("f", LR, DG), ("f", RD, LR), ("f", RD, GR), ("s", LR, LR),
            ("f", LR, GR), ("f", LR, LG), ("f", LG, GR), ("s", LG, LG), ("e", WH, LG),
            ("f", LG, WH), ("t", LG, WH), ("s", WH, WH)]

def colour(i, rp, p):
    kind, a, b = RAMP[i]
    if kind == "s":
        return a
    if kind == "f":
        return a if (rp + p) % 2 == 0 else b
    if kind == "e":
        return a if rp == 0 and p == 0 else b
    return a if rp == 0 else b

def _lin(c):
    return ((fb.C64RGB[c] / 255) ** 2.2) @ np.array([0.2126, 0.7152, 0.0722])

def _light(s):
    global RAMP
    RAMP = [s]
    return np.mean([_lin(colour(0, r, p)) for r in (0, 1) for p in (0, 1)])

Lstar = lambda y: np.where(y > 0.008856, 116 * np.cbrt(y) - 16, y * 903.3)
_l = [_light(s) for s in SWATCHES]
RAMP = [s for _, s in sorted(zip(_l, SWATCHES), key=lambda t: t[0])]
LIGHT = np.array(sorted(_l))
RAMP_L = Lstar(LIGHT)

def name(i):
    kind, a, b = RAMP[i]
    A, B = fl.NAMES[a], fl.NAMES[b]
    return {"s": A, "f": f"{A} / {B}", "e": f"{B} + {A} every other",
            "t": f"{A} | {B} stripes"}[kind]

def main(path, seconds=6):
    ROWS, Z, PAD, WIDTH = 2, 8, 4, 160
    h = PAD * 2 + ROWS * len(RAMP)
    looks = []
    for p in (0, 1):
        img = np.zeros((h, WIDTH), int)
        for i in range(len(RAMP)):
            for s in range(ROWS):
                r = PAD + ROWS * i + s
                img[r] = colour(i, r & 1, p)
        looks.append(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    font, small = fl.fonts()
    W, H = WIDTH * Z, h * Z
    v = iv.Video(path, W + 420, H + 50)
    for f in range(seconds * 60):
        c = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(c)
        dr.text((16, 8), "red ramp, two lines each, darkest first (by measured light)   CRT",
                fill=(170, 176, 210), font=small)
        c.paste(looks[f & 1], (16, 34))
        for i in range(len(RAMP)):
            y = 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8
            dr.text((W + 32, y), f"{i + 1:2d}   {name(i)}   L* {RAMP_L[i]:.0f}",
                    fill=(190, 195, 225), font=small)
        v.add(c)
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    main(sys.argv[1])
