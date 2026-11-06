#!/usr/bin/env python3
"""The v10 ramp without the ghost-byte swatches (every idle byte 00): black
and v10 #8..#24, darkest first, two lines per swatch, numbered 1..18 for
reference; both frames alternating, CRT look.

    python3 ramp_flat_video.py out.mp4
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import swatch_ramp_video as sr
import swatch_loop_video as sv
import preview_v10 as v10          # applies the row swap / shift to v7.colour/ghost
v7 = v10.v7

ROWS, Z, PAD, WIDTH = 2, 8, 4, 160

def flat():
    """(v10 index, swatch) for the swatches whose idle byte is always 00."""
    return [(i, k) for i, k in enumerate(v10.LAD)
            if all(v7.ghost(k, r, p) == 0 for r in (0, 1) for p in (0, 1))]

def name(k):
    a, b, *_r, n = sv.PAL[k]
    return n if n != "full" else (fl.NAMES[a] if a == b else f"{fl.NAMES[a]} / {fl.NAMES[b]}")

def main(path, seconds=6):
    ramp = flat()
    h = PAD * 2 + ROWS * len(ramp)
    looks = []
    for p in (0, 1):
        img = np.zeros((h, WIDTH), int)
        for i, (_, k) in enumerate(ramp):
            for s in range(ROWS):
                r = PAD + ROWS * i + s
                img[r] = v7.colour(k, r & 1, p)
        looks.append(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    font, small = fl.fonts()
    W, H = WIDTH * Z, h * Z
    v = iv.Video(path, W + 420, H + 50)
    for f in range(seconds * 60):
        c = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(c)
        dr.text((16, 8), "v10 ramp, no ghost-byte swatches, two lines each, darkest first   CRT",
                fill=(170, 176, 210), font=small)
        c.paste(looks[f & 1], (16, 34))
        for i, (j, k) in enumerate(ramp):
            y = 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8
            dr.text((W + 32, y), f"{i + 1:2d}   {name(k)}   (v10 #{j})",
                    fill=(190, 195, 225), font=small)
        v.add(c)
    v.close()
    print("wrote", path, len(ramp), "swatches")

if __name__ == "__main__":
    main(sys.argv[1])
