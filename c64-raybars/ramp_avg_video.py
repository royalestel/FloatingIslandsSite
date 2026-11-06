#!/usr/bin/env python3
"""The sorted ramp (ramp_extra_video.build_rows(merged=True)) with every swatch
averaged over its 4 frame/line samples (2 line parities x 2 frames), in linear
light, ghost-byte pixels counted as black.  Each swatch becomes one flat colour
(the average, as RGB: a preview of what the flicker pair looks like to the eye),
and the ramp is reordered by that brightness.  3 lines a swatch, numbered, CRT.

    python3 ramp_avg_video.py out.mp4        (out.png for a still)
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import ramp_extra_video as rx

M = np.array([0.2126, 0.7152, 0.0722])

def averaged(fn):
    """Linear RGB average over (line parity, frame parity), ghost pixels black."""
    acc = np.zeros(3)
    for rp in (0, 1):
        for p in (0, 1):
            c, g = fn(rp, p)
            lit = (8 - bin(g).count("1")) / 8 if g else 1.0
            acc += ((fb.C64RGB[c] / 255) ** 2.2) * lit
    return acc / 4

def srgb(lin):
    return np.clip(lin, 0, 1) ** (1 / 2.2) * 255

def build():
    rows = rx.build_rows(merged=True)
    items = []
    for n, _, fn in rows:
        lin = averaged(fn)
        items.append((n, float(lin @ M), lin))
    items.sort(key=lambda t: t[1])
    return items

def main(path):
    items = build()
    Z, ROWS, PAD = 7, 3, 4
    font, small = fl.fonts()
    txt = [f"{i + 1:2d}   {n}   L* {116 * y ** (1 / 3) - 16 if y > 0.008856 else y * 903.3:.0f}"
           for i, (n, y, _) in enumerate(items)]
    tw = int(max(small.getlength(t) for t in txt)) + 4
    WIDTH = -(-tw // Z // 8) * 8
    h = PAD * 2 + ROWS * len(items)
    img = np.zeros((h, WIDTH, 3))
    for i, (_, _, lin) in enumerate(items):
        for s in range(ROWS):
            img[PAD + ROWS * i + s] = srgb(lin)
    look = lv.crt_look(img.astype(np.uint8), Z)
    W, H = WIDTH * Z, h * Z
    if path.endswith(".png"):
        c = Image.new("RGB", (16 + W + 16 + tw + 16, H + 100), (8, 8, 16))
        c.paste(look, (16, 34))
        dr = ImageDraw.Draw(c)
        for i, t in enumerate(txt):
            dr.text((W + 32, 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8), t,
                    fill=(190, 195, 225), font=small)
        c.save(path)
        print("wrote", path, len(items), "swatches")
        return
    v = iv.Video(path, 16 + W + 16 + tw + 16, H + 50)
    for f in range(6 * 60):
        c = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(c)
        dr.text((16, 8), "averaged over 4 frames, reordered by brightness   CRT", fill=(170, 176, 210), font=small)
        c.paste(look, (16, 34))
        for i, t in enumerate(txt):
            dr.text((W + 32, 34 + (PAD + ROWS * i) * Z + ROWS * Z // 2 - 8), t,
                    fill=(190, 195, 225), font=small)
        v.add(c)
    v.close()
    print("wrote", path, len(items), "swatches")

if __name__ == "__main__":
    main(sys.argv[1])
