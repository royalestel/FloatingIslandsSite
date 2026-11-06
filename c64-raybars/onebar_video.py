#!/usr/bin/env python3
"""One cosmic string from the full distance (28 m) past the camera, drawn
as cosmicstrings.prg draws it: the program's own ramps (gen_cosmic.ramp:
the swatch for each row of a bar h lines tall, blue 1/4 on/off up to 10
lines), swatch tables (colour and idle byte by row parity and frame
parity), bar height and top, near clip at 0.42 m, and the ship's sprites.
60 fps video, one C64 frame per video frame, with the CRT look and sharp.

    python3 onebar_video.py crt.mp4 sharp.mp4 [height below the ship, m]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import swatch_loop_video as sv
import gen_cosmic as gc
gc.ROUND = True                     # round bars at all distances (preview)

import os
V3 = "V3" in os.environ               # the v3 preview ramps (gen_cosmic.ramp_v3)
BLUR = float(os.environ.get("BLUR", 2))   # the extra-blurry look's blur (lines)
MODES = os.environ.get("MODES", "CRT,sharp").split(",")   # the two outputs: CRT, sharp, blurry

def blurry(im):
    """A very soft TV: the CRT look blurred again in linear light, mostly
    vertically (across the lines), BLUR lines."""
    from PIL import ImageFilter
    a = (np.asarray(im, float) / 255) ** 2.2
    def g(x, r):
        b = Image.fromarray(np.clip(x ** (1 / 2.2) * 255, 0, 255).astype(np.uint8))
        return (np.asarray(b.filter(ImageFilter.GaussianBlur(r)), float) / 255) ** 2.2
    # vertical: blur a column-squashed copy, then stretch back
    h, w, _ = a.shape
    small = Image.fromarray(np.clip(a ** (1 / 2.2) * 255, 0, 255).astype(np.uint8)).resize((w // 4, h))
    sv_ = (np.asarray(small.filter(ImageFilter.GaussianBlur(BLUR * 3 / 4)), float) / 255) ** 2.2
    vert = (np.asarray(Image.fromarray(np.clip(sv_ ** (1 / 2.2) * 255, 0, 255).astype(np.uint8)).resize((w, h), Image.BILINEAR), float) / 255) ** 2.2
    out = 0.7 * vert + 0.3 * g(a, BLUR * 3 / 2)
    return Image.fromarray(np.clip(out ** (1 / 2.2) * 255, 0, 255).astype(np.uint8))

PURPLE = "PURPLE" in os.environ       # left v3, right v3 with purple / light blue 1/4 inverting
STOP = float(os.environ.get("STOP", 0))
V5 = "V5" in os.environ               # v3 + patterns with the white on/off core (ramp_v5)
SPEED = 0.045                       # metres a frame (cosmicstrings' base speed)
DNEAR = 2 * sv.lv.R_BAR * gc.F / (gc.HMAX + 0.45)

def main(out_crt, out_sharp, below=0.3, start=None, split=False):
    tabs = [np.frombuffer(t, np.uint8) for t in gc.swatch_tables()]
    ramps = {}
    spr = gc.sprites()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    vids = [iv.Video(out_crt, W + 32, H + 60), iv.Video(out_sharp, W + 32, H + 60)]
    d, f = (start or sv.lv.FAR), 0
    x = np.arange(fb.W)
    while d > max(DNEAR - 2 * SPEED, STOP):
        p = f & 1
        img = np.zeros((fb.H, fb.W), int)
        if d >= DNEAR:
            h = max(2, min(gc.HMAX, lv.bar_lines(d)))
            key = (h, round(d * 10) / 10)        # by distance (0.1 m) as well
            if key not in ramps and V5 and not split:
                ramps[key] = (gc.ramp_v5(h, key[1]),) * 2
            if key not in ramps:
                alt = gc.ramp_v3 if V3 else gc.ramp_smooth
                if PURPLE:                           # v3 vs v3 with the extra patterns
                    ramps[key] = (gc.ramp_v3(h, key[1]), gc.ramp_v3(h, key[1], gc.LADDER_P))
                else:
                  ramps[key] = (gc.ramp_round(h, round(d * 2) / 2),
                                alt(h, key[1]) if split else
                                (gc.ramp_v3(h, key[1], gc.LADDER_P if PURPLE else None) if V3
                                 else gc.ramp_round(h, round(d * 2) / 2)))
            top = int(round((2 * gc.CYL - 2 * gc.F * (-below) / d - h) / 2))
            for j in range(h):
                ln = top + j
                if 0 <= ln < gc.NLINES:
                    r = ln + 11                  # mock row
                    t = tabs[p]
                    for side, (x0, x1) in enumerate(((0, 160), (160, 320)) if split else ((0, 320),)):
                        k = ramps[key][side][j]
                        img[r, x0:x1] = t[32 * (r & 1) + k]
                        g = t[64 + 32 * (r & 1) + k]
                        if g:
                            xs = x[x0:x1]
                            row = img[r, x0:x1]
                            row[((g >> (7 - xs % 8)) & 1) == 1] = 0
        rgb = fb.C64RGB[img].astype(np.uint8)
        cols = {1: 4, 2: 14, 3: (1, 3)[p]}
        for side in (0, 1):
            blk = spr[((4 * 4) + p * 2 + side) * 64:][:63]       # level pitch
            for sy in range(21):
                bits = blk[3 * sy] << 16 | blk[3 * sy + 1] << 8 | blk[3 * sy + 2]
                for cx in range(12):
                    v = (bits >> (22 - 2 * cx)) & 3
                    if v:
                        yy = gc.SPRY + 1 + sy - 51
                        xx = 136 + side * 24 + 2 * cx
                        rgb[yy, xx:xx + 2] = fb.C64RGB[cols[v]]
        last = []
        for v, mode in zip(vids, MODES):
            crt = mode != "sharp"
            canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
            dr = ImageDraw.Draw(canvas)
            label = f"{d:5.2f} m   {h} lines" if d >= DNEAR else "clipped"
            if split:
                dr.text((16, 8), ("left: v3   right: v3 + purple, light blue 1/4 inverting   " if PURPLE else
                         f"left: now   right: {'v3 (L* by log distance, centre-out)' if V3 else 'all 29, centre-out'}   ") +
                        f"{label}   {mode}", fill=(170, 176, 210), font=small)
            else:
                dr.text((16, 8), f"one cosmic string, {below:.2f} m below the ship:   {label}   "
                        f"{mode}", fill=(170, 176, 210), font=small)
            look = lv.crt_look(rgb, Z) if crt else Image.fromarray(rgb).resize((W, H), Image.NEAREST)
            if mode == "blurry":
                look = blurry(look)
            canvas.paste(look, (16, 40))
            # the distance, large, in the empty top right of the window
            big = f"{d:5.2f} m" if d >= DNEAR else "clipped"
            dr.text((v.w - 200, 56), big, fill=(235, 235, 120), font=font)
            if split:
                dr.text((16 + 40, 56), "v3" if PURPLE else "now", fill=(200, 200, 220), font=font)
                dr.text((16 + W // 2 + 40, 56), "+ patterns" if PURPLE else ("v3" if V3 else "all 29"),
                        fill=(200, 200, 220), font=font)
            v.add(canvas)
            last.append(canvas)
        d -= SPEED
        f += 1
    for _ in range(30):                          # a moment after it has gone
        for v, c in zip(vids, last):
            v.add(c)
    for v in vids:
        v.close()
    print("wrote", out_crt, out_sharp, f, "frames")

if __name__ == "__main__":
    import os
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.3,
         float(os.environ["START"]) if "START" in os.environ else None, "SPLIT" in os.environ)
