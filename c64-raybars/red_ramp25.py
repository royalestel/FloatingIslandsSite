#!/usr/bin/env python3
"""The red ramp with ghost-byte swatches: black + the blue ramp's 7 ghost swatches
recoloured (blue -> brown, purple -> red, light blue -> light red; the same idle
bytes, so the same patterns) + the 17 flat red swatches of red_ramp.py = 25,
ordered by measured light (no ordering by eye yet).  Video: two lines a swatch,
numbered, CRT look.

    python3 red_ramp25.py red_ramp25.mp4
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import preview_v10 as v10
import swatch_loop_video as sv
import red_ramp as rr

MAP = {6: 9, 4: 2, 14: 10}                     # blue -> brown, purple -> red, light blue -> light red
NAME = {"blue": "brown", "purple": "red", "light blue": "light red"}

def _ghost_name(k):
    n = sv.PAL[k][6]
    for a in ("light blue", "purple", "blue"):
        if n.startswith(a):
            return NAME[a] + n[len(a):]
    return n

# entries: ("g", blue swatch id) = ghost swatch, ("f", red_ramp index) = flat swatch
_entries = [("f", 0)] + [("g", k) for k in v10.LAD[1:8]] + [("f", i) for i in range(1, len(rr.RAMP))]

def _col(e, rp, p):
    return MAP[v10.colour(e[1], rp, p)] if e[0] == "g" else rr.colour(e[1], rp, p)

def _gh(e, rp, p):
    return v10.ghost(e[1], rp, p) if e[0] == "g" else 0

def _lin(e):
    tot = 0
    for rp in (0, 1):
        for p in (0, 1):
            c = (fb.C64RGB[_col(e, rp, p)] / 255) ** 2.2 @ np.array([0.2126, 0.7152, 0.0722])
            g = _gh(e, rp, p)
            tot += c * (8 - bin(g).count("1")) / 8
    return tot / 4

_lights = [_lin(e) for e in _entries]
_order = sorted(range(len(_entries)), key=lambda i: _lights[i])
ENTRIES = [_entries[i] for i in _order]
LIGHT = np.array([_lights[i] for i in _order])
Lstar = lambda y: np.where(y > 0.008856, 116 * np.cbrt(y) - 16, y * 903.3)
RAMP_L = Lstar(LIGHT)
N = len(ENTRIES)
FLAT = [i for i, e in enumerate(ENTRIES) if e[0] == "f"]
WHITE = N - 1                                   # white is the brightest

def colour(i, rp, p):
    return _col(ENTRIES[i], rp, p)

def ghost(i, rp, p):
    return _gh(ENTRIES[i], rp, p)

def name(i):
    e = ENTRIES[i]
    return _ghost_name(e[1]) if e[0] == "g" else rr.name(e[1])

def main(path, seconds=6):
    ROWS, Z, PAD, WIDTH = 2, 8, 4, 160
    h = PAD * 2 + ROWS * N
    looks = []
    x = np.arange(WIDTH)
    for p in (0, 1):
        img = np.zeros((h, WIDTH), int)
        for i in range(N):
            for s in range(ROWS):
                r = PAD + ROWS * i + s
                img[r] = colour(i, r & 1, p)
                g = ghost(i, r & 1, p)
                if g:
                    img[r, ((g >> (7 - x % 8)) & 1) == 1] = 0
        looks.append(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    font, small = fl.fonts()
    W, H = WIDTH * Z, h * Z
    v = iv.Video(path, W + 430, H + 50)
    for f in range(seconds * 60):
        c = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(c)
        dr.text((16, 8), "red ramp with ghost-byte swatches, two lines each, darkest first (measured light)   CRT",
                fill=(170, 176, 210), font=small)
        c.paste(looks[f & 1], (16, 34))
        for i in range(N):
            y = 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8
            tag = "  [ghost]" if ENTRIES[i][0] == "g" else ""
            dr.text((W + 32, y), f"{i + 1:2d}   {name(i)}{tag}   L* {RAMP_L[i]:.0f}",
                    fill=(190, 195, 225), font=small)
        v.add(c)
    v.close()
    print("wrote", path, N, "swatches")

if __name__ == "__main__":
    main(sys.argv[1])
