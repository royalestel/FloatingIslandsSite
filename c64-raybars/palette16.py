#!/usr/bin/env python3
"""The 16-colour multicolour palette used for W6's right waves: all 16 C64 colours,
dark to light by CIE L* (ghost_part4.ORDER16), one solid swatch each, three lines,
numbered.  CRT look.

    python3 palette16.py palette16.mp4     (or palette16.png for a still)
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import ghost_part4 as g4

def main(path):
    order = g4.ORDER16
    Z, ROWS, PAD = 7, 3, 4
    font, small = fl.fonts()
    txt = [f"{i + 1:2d}   {fl.NAMES[c]}   L* {g4.L16[i]:.0f}" for i, c in enumerate(order)]
    tw = int(max(small.getlength(t) for t in txt)) + 4
    WIDTH = -(-tw // Z // 8) * 8
    h = PAD * 2 + ROWS * 16
    img = np.zeros((h, WIDTH), int)
    for i, c in enumerate(order):
        for s in range(ROWS):
            img[PAD + ROWS * i + s] = c
    look = lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z)
    W, H = WIDTH * Z, h * Z
    if path.endswith(".png"):
        c = Image.new("RGB", (16 + W + 16 + tw + 16, H + 100), (8, 8, 16))
        c.paste(look, (16, 34))
        dr = ImageDraw.Draw(c)
        for i, t in enumerate(txt):
            dr.text((W + 32, 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8), t, fill=(190, 195, 225), font=small)
        c.save(path)
        print("wrote", path)
        return
    v = iv.Video(path, 16 + W + 16 + tw + 16, H + 50)
    for f in range(6 * 60):
        c = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(c)
        dr.text((16, 8), "the 16-colour palette, dark to light (by L*)   CRT", fill=(170, 176, 210), font=small)
        c.paste(look, (16, 34))
        for i, t in enumerate(txt):
            dr.text((W + 32, 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8), t, fill=(190, 195, 225), font=small)
        v.add(c)
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    main(sys.argv[1])
