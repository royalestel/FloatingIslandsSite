#!/usr/bin/env python3
"""Cosmic strings: slices of single bars side by side, from the farthest
(12 m: dark blue, 8 lines, the flickering 1-of-8 dither) to the nearest
before the clip (0.45 m: the full glow, 100+ lines), each with its own
colour choice, idle-byte pattern and flicker exactly as loop_video.py draws
it, through the CRT look.  The scene holds still: only the flicker moves.

    python3 strings_slices.py out.mp4 [seconds]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flight_video as fv
import glow_video as gv
import loop_video as lv
import ideas_video as iv
import flicker as fl

DISTS = [12, 11.5, 11, 10.5, 10, 9.5, 9, 8.5, 8, 7, 6, 5, 4, 3, 2, 1.2, 0.7, 0.45]
SW, GAP, H = 30, 6, 200            # slice width and gap (pixels), lines

def slice_frame(d, p):
    """One bar at distance d, centred, as a column of C64 colours on frame
    parity p, and its per-line idle bytes."""
    h = lv.bar_lines(d)
    top = H // 2 - h // 2
    tgt = np.zeros((fb.H, 3))
    who = np.full(fb.H, -1)
    big = np.zeros(fb.H, bool)
    byte = np.zeros(fb.H, int)
    fc = lv.fade(d)
    name, light, pbyte = lv.pattern_at(d)
    for j in range(h):
        r = top + j
        if 0 <= r < H:
            who[r], big[r] = 0, h >= lv.BIG
            tgt[r] = fv.fl_lin(gv.glow(fc * (1 - abs(2 * (j + 0.5) / h - 1)) ** 0.9))
            byte[r] = pbyte(r, p)
    cols = lv.choose(tgt, who, big)
    return cols[:, p], byte, h, name

def frame(p):
    W = len(DISTS) * (SW + GAP) + GAP
    img = np.zeros((H, W, 3), np.uint8)
    info = []
    for i, d in enumerate(DISTS):
        col, byte, h, name = slice_frame(d, p)
        x0 = GAP + i * (SW + GAP)
        x = np.arange(x0, x0 + SW)
        for r in range(H):
            c = fb.C64RGB[col[r]]
            black = (byte[r] >> (7 - (x % 8))) & 1 if byte[r] else np.zeros(SW, int)
            img[r, x0:x0 + SW] = np.where(black[:, None] == 1, 0, c)
        info.append((x0, d, h, name))
    return img, info

def main(path, seconds=8):
    font, small = fl.fonts()
    Z = 2
    frames = [frame(p) for p in (0, 1)]
    W = frames[0][0].shape[1]
    looks = [lv.crt_look(img, Z) for img, _ in frames]
    lab = 70
    v = iv.Video(path, W * Z + 32, H * Z + lab + 40)
    for k in range(int(seconds * 60)):
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), "Cosmic strings: one bar at each distance, farthest to nearest "
                "(colour fade, flicker pairs, idle-byte patterns, CRT)", fill=(190, 195, 225),
                font=small)
        canvas.paste(looks[k & 1], (16, 34))
        for x0, d, h, name in frames[0][1]:
            x = 16 + x0 * Z
            y = 34 + H * Z + 6
            dr.text((x, y), f"{d:g} m", fill=(200, 205, 235), font=small)
            dr.text((x, y + 18), f"{h} ln", fill=(150, 155, 185), font=small)
            short = {"full": "full", "1/2": "1/2", "1/4": "1/4", "1/4 flickering": "1/4 fl",
                     "1/8 dithered, flickering": "1/8 d fl"}[name]
            dr.text((x, y + 36), short, fill=(150, 155, 185), font=small)
        v.add(canvas)
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 8)
