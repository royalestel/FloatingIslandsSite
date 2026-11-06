#!/usr/bin/env python3
"""A 25-swatch multicolour palette built on seven base colours -- blue, dark grey,
purple, light red, cyan, yellow, white -- (and black as swatch 1), dark to light.
Between each pair of bases the gaps are filled with in-betweens made of the same
techniques as the other ramps: flicker pairs (phase swapped line to line and frame
to frame), stripes, "x + y every other", and ghost-byte patterns (1/4, 1/4 on/off,
checker).  Greedy: the biggest gap in lightness gets the candidate nearest its
middle, among mixes of the two bases at its ends (and ghost patterns of either for
the dark end).  Three lines a swatch, numbered, CRT look, 60 Hz.

    python3 palette25.py palette25.mp4     (or palette25.png for a still)
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv

BASES = [6, 11, 4, 10, 3, 7, 1]               # blue, dark grey, purple, light red, cyan, yellow, white
N = fl.NAMES
M = np.array([0.2126, 0.7152, 0.0722])

def lin(c):
    return float(((fb.C64RGB[c] / 255) ** 2.2) @ M)

def Ls(y):
    return float(116 * y ** (1 / 3) - 16) if y > 0.008856 else y * 903.3

# a swatch: (name, kind, spec); fn(rp, p, s) -> (colour, idle byte)
def f_solid(a):
    return lambda rp, p, s: (a, 0)
def f_flick(a, b):
    return lambda rp, p, s: (a if (rp + p) % 2 == 0 else b, 0)
def f_stripes(a, b):
    return lambda rp, p, s: (a if rp == 0 else b, 0)
def f_every(a, b):                                       # a on one line in four, b the rest
    return lambda rp, p, s: (a if rp == 0 and p == 0 else b, 0)
def g_checker(a):
    return lambda rp, p, s: (a, 0x55 if (rp + p) % 2 == 0 else 0xAA)
def g_quarter(a):
    return lambda rp, p, s: (a, 0x77 if (rp + p) % 2 == 0 else 0xDD)
def g_onoff(a):
    return lambda rp, p, s: (a, (0x77 if rp == 0 else 0xDD) if p == 0 else 0xFF)

def light(fn):
    y = 0.0
    for rp in (0, 1):
        for p in (0, 1):
            c, g = fn(rp, p, 0)
            y += lin(c) * ((8 - bin(g).count("1")) / 8 if g else 1.0) / 4
    return Ls(y)

# swatches the eye rejected (too much flicker): never used
EXTRA_OK = {(7, 10)}                                 # light red with yellow (a warm hue step) may fill a gap
ROUGH_PAIRS = {(3, 10), (3, 7)}                      # cyan with light red / yellow: only stripes
BANNED = {"purple / light red", "light red + purple every other", "light red / cyan",
          "cyan + light red every other", "cyan / yellow"}

def pool():
    """Every candidate: (name, fn, colours used) over the seven bases (black included for ghosts)."""
    out = []
    for a in BASES:
        out += [(f"{N[a]} 1/4 on/off [ghost]", g_onoff(a), {a}), (f"{N[a]} 1/4 inverting [ghost]", g_quarter(a), {a}),
                (f"{N[a]} checker inverting [ghost]", g_checker(a), {a})]
    for i, a in enumerate(BASES):
        for b in BASES[i + 1:]:
            out += [(f"{N[a]} / {N[b]}", f_flick(a, b), {a, b}),
                    (f"{N[a]} | {N[b]} stripes", f_stripes(a, b), {a, b}),
                    (f"{N[a]} + {N[b]} every other", f_every(b, a), {a, b}),
                    (f"{N[b]} + {N[a]} every other", f_every(a, b), {a, b})]
    def rough(cols):                                  # pairs that flickered too much: stripes only
        return tuple(sorted(cols)) in ROUGH_PAIRS
    return [(n, fn, cols, light(fn)) for n, fn, cols in out
            if n not in BANNED and not (len(cols) == 2 and rough(cols) and "stripes" not in n)]

def penalty(c):
    """Flicker shows most where the two colours differ a lot: prefer low-contrast mixes,
    stripes and ghost patterns over big-contrast flicker."""
    n, cols = c[0], c[2]
    if len(cols) < 2:
        return 0.0
    a, b = sorted(cols)
    contrast = abs(Ls(lin(a)) - Ls(lin(b)))
    return (0.03 if "stripes" in n else 0.12) * contrast

# the curated 25 (after the five that flickered too much were removed and the greedy
# fill was tidied by hand): names as pool() makes them
FINAL = ["black", "blue 1/4 on/off [ghost]", "blue 1/4 inverting [ghost]",
         "dark grey 1/4 inverting [ghost]", "blue checker inverting [ghost]",
         "dark grey checker inverting [ghost]", "blue", "blue + dark grey every other",
         "blue | dark grey stripes", "dark grey + blue every other", "dark grey",
         "dark grey | purple stripes", "purple", "purple + light red every other",
         "purple | light red stripes", "light red", "yellow checker inverting [ghost]",
         "light red | cyan stripes", "cyan", "cyan | yellow stripes", "yellow",
         "yellow + white every other", "yellow | white stripes", "white + yellow every other", "white"]

def build(total=25):
    allc = {"black": ("black", f_solid(0), {0}, 0.0)}
    for c in BASES:
        allc[N[c]] = (N[c], f_solid(c), {c}, light(f_solid(c)))
    for n, fn, cols, l in pool():
        allc[n] = (n, fn, cols, l)
    sw = [allc[n] for n in FINAL]
    sw.sort(key=lambda t: t[3])
    return [(n, fn, l) for n, fn, _, l in sw]

def main(path):
    sw = build()
    Z, ROWS, PAD = 7, 3, 4
    font, small = fl.fonts()
    txt = [f"{i + 1:2d}   {n}   L* {l:.0f}" for i, (n, _, l) in enumerate(sw)]
    tw = int(max(small.getlength(t) for t in txt)) + 4
    WIDTH = -(-tw // Z // 8) * 8
    h = PAD * 2 + ROWS * len(sw)
    x = np.arange(WIDTH)
    looks = []
    for p in (0, 1):
        img = np.zeros((h, WIDTH), int)
        for i, (_, fn, _) in enumerate(sw):
            for s in range(ROWS):
                r = PAD + ROWS * i + s
                c, g = fn(r & 1, p, s)
                img[r] = c
                if g:
                    img[r, ((g >> (7 - x % 8)) & 1) == 1] = 0
        looks.append(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    W, H = WIDTH * Z, h * Z
    if path.endswith(".png"):
        c = Image.new("RGB", (16 + W + 16 + tw + 16, H + 100), (8, 8, 16))
        c.paste(looks[0], (16, 34))
        dr = ImageDraw.Draw(c)
        for i, t in enumerate(txt):
            dr.text((W + 32, 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8), t, fill=(190, 195, 225), font=small)
        c.save(path)
        print("wrote", path)
    else:
        v = iv.Video(path, 16 + W + 16 + tw + 16, H + 50)
        for f in range(6 * 60):
            c = Image.new("RGB", (v.w, v.h), (8, 8, 16))
            dr = ImageDraw.Draw(c)
            dr.text((16, 8), "25-swatch multicolour palette (7 bases + black + in-betweens)   CRT",
                    fill=(170, 176, 210), font=small)
            c.paste(looks[f & 1], (16, 34))
            for i, t in enumerate(txt):
                dr.text((W + 32, 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8), t, fill=(190, 195, 225), font=small)
            v.add(c)
        v.close()
        print("wrote", path)
    for i, t in enumerate(txt):
        print(t)

if __name__ == "__main__":
    main(sys.argv[1])
