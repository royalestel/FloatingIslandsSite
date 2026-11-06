#!/usr/bin/env python3
"""The ramp the bars are drawn from (v9's ladder: v3's swatches plus the
white centre swatches), darkest at the top, two rows per swatch, each next
pair one step brighter; both frames alternating, CRT look, 5 seconds.

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

ROWS, WIDTH, Z, PAD = 2, 160, 6, 3

def main(path, seconds=5):
    lad = v7.LADDER7
    h = PAD * 2 + ROWS * len(lad)
    font, small = fl.fonts()
    names = []
    for k in lad:
        a, b, *_r, name = sv.PAL[k]
        names.append(name if name != "full" else
                     (fl.NAMES[a] if a == b else f"{fl.NAMES[a]} / {fl.NAMES[b]}"))
    looks = []
    x = np.arange(WIDTH)
    for p in (0, 1):
        img = np.zeros((h, WIDTH), int)
        for i, k in enumerate(lad):
            for s in range(ROWS):
                r = PAD + ROWS * i + s
                img[r] = v7.colour(k, r & 1, p)
                g = v7.ghost(k, r & 1, p)
                if g:
                    img[r, ((g >> (7 - x % 8)) & 1) == 1] = 0
        looks.append(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    W, H = WIDTH * Z, h * Z
    v = iv.Video(path, W + 360, H + 50)
    for f in range(seconds * 60):
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), "the swatch ramp, two rows each, darkest first   CRT", fill=(170, 176, 210), font=small)
        canvas.paste(looks[f & 1], (16, 34))
        for i, n in enumerate(names):
            y = 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 7
            dr.text((W + 32, y), f"{i + 1:2d}  {n}", fill=(190, 195, 225), font=small)
        v.add(canvas)
    v.close()
    print("wrote", path, len(lad), "swatches")

if __name__ == "__main__":
    main(sys.argv[1])
