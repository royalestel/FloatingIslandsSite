#!/usr/bin/env python3
"""Every swatch we have (the 29, purple and light blue 1/4 inverting, and
the white centre's cyan + white every other / cyan | white stripes), in
order of linear light, darkest at the top, two rows per swatch; both frames
alternating, CRT look, 5 seconds; a square of colour with the labels beside
it (number, name, L* by linear light).

    python3 swatch_ramp_video.py out.mp4
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import swatch_loop_video as sv
import preview_v7 as v7

ROWS, Z, PAD = 2, 8, 3

def reorder(lad):
    """By eye (the CRT ramp): 6 <-> 7, 8 <-> 9; the light blue, grey and cyan
    checker inverting (13, 15, 24) darker than they measure: moved up --
    13 and 15 to just above blue, 24 to just above purple / dark grey."""
    lad = list(lad)
    lad[5], lad[6] = lad[6], lad[5]
    lad[7], lad[8] = lad[8], lad[7]
    m13, m15, m24 = lad[12], lad[14], lad[23]
    for k in (m13, m15, m24):
        lad.remove(k)
    blue = [k for k in lad if sv.PAL[k][6] == "full" and sv.PAL[k][0] == sv.PAL[k][1] == 6][0]
    pdg = [k for k in lad if sv.PAL[k][6] == "full" and {sv.PAL[k][0], sv.PAL[k][1]} == {4, 11}][0]
    i = lad.index(blue)
    lad[i:i] = [m13, m15]
    i = lad.index(pdg)
    lad[i:i] = [m24]
    return lad

DROP = {13, 15, 19, 24, 27}           # by eye: dark grey, cyan checker inverting,
                                      # dark grey / grey, grey, light grey
DROP2 = {7, 10, 25}                   # then: dark grey checker inverting,
                                      # grey checker inverting, light grey / white
SHIFT_N = {6}                         # light blue 1/4 inverting: pixels one to the right
SHIFT = set()
SWAP_ROWS = {v7.STRIPES}              # cyan | white stripes: its two rows swapped

SWAPS3 = [(19, 20), (17, 18), (16, 15), (14, 13), (12, 11), (8, 9)]   # by eye, after the drops

def main(path, seconds=5):
    """Split screen: left the last ramp, right with SWAPS3 applied."""
    def lin(k):
        frames = []
        for p in (0, 1):
            img = np.zeros((8, 8, 3))
            for r in range(8):
                c = fb.C64RGB[v7.colour(k, r & 1, p)]
                g = v7.ghost(k, r & 1, p)
                for x_ in range(8):
                    img[r, x_] = 0 if (g >> (7 - x_)) & 1 else c
            frames.append(img)
        return float(np.mean([fl.lin(f) @ sv.LW for f in frames]))
    lums = {k: lin(k) for k in range(len(sv.PAL))}
    lad = sorted(lums, key=lambda k: lums[k])
    lad = reorder(lad)
    lad = [k for i, k in enumerate(lad) if i + 1 not in DROP]
    lad = [k for i, k in enumerate(lad) if i + 1 not in DROP2]
    SHIFT.update(lad[i - 1] for i in SHIFT_N)
    new = list(lad)
    for a, b in SWAPS3:
        new[a - 1], new[b - 1] = new[b - 1], new[a - 1]
    L = lambda y: 116 * y ** (1 / 3) - 16 if y > 0.008856 else y * 903.3
    h = PAD * 2 + ROWS * len(lad)
    WIDTH = h                                # a square of colour
    font, small = fl.fonts()
    def names(order):
        out = []
        for k in order:
            a, b, *_r, name = sv.PAL[k]
            out.append((name if name != "full" else
                        (fl.NAMES[a] if a == b else f"{fl.NAMES[a]} / {fl.NAMES[b]}"))
                       + f"   L* {L(lums[k]):.0f}")
        return out
    x = np.arange(WIDTH)
    def looks(order):
        out = []
        for p in (0, 1):
            img = np.zeros((h, WIDTH), int)
            for i, k in enumerate(order):
                for s_ in range(ROWS):
                    r = PAD + ROWS * i + s_
                    rp = (r + (k in SWAP_ROWS)) & 1
                    img[r] = v7.colour(k, rp, p)
                    g = v7.ghost(k, rp, p)
                    if k in SHIFT:
                        g = (g >> 1) | ((g & 1) << 7)
                    if g:
                        img[r, ((g >> (7 - x % 8)) & 1) == 1] = 0
            out.append(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
        return out
    lo, ln = looks(lad), looks(new)
    no, nn = names(lad), names(new)
    W, H = WIDTH * Z, h * Z
    LBL = 300
    v = iv.Video(path, 2 * W + 2 * LBL + 48, H + 50)
    xo, xn = 16 + LBL, 16 + LBL + W + 16
    for f in range(seconds * 60):
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), "left: last ramp      right: new (19-20, 17-18, 15-16, 13-14, 11-12, 8-9 swapped)   CRT",
                fill=(170, 176, 210), font=small)
        canvas.paste(lo[f & 1], (xo, 34))
        canvas.paste(ln[f & 1], (xn, 34))
        for i, (a, b) in enumerate(zip(no, nn)):
            y = 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8
            t = f"{a}  {i + 1:2d}"
            tw = dr.textlength(t, font=small)
            dr.text((xo - 12 - tw, y), t, fill=(190, 195, 225), font=small)
            dr.text((xn + W + 12, y), f"{i + 1:2d}  {b}", fill=(190, 195, 225), font=small)
        v.add(canvas)
    v.close()
    print("wrote", path, len(lad), "swatches")

if __name__ == "__main__":
    main(sys.argv[1])
