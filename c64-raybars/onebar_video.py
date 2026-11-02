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

SPEED = 0.045                       # metres a frame (cosmicstrings' base speed)
DNEAR = 2 * sv.lv.R_BAR * gc.F / (gc.HMAX + 0.45)

def main(out_crt, out_sharp, below=0.3):
    tabs = [np.frombuffer(t, np.uint8) for t in gc.swatch_tables()]
    ramps = {}
    spr = gc.sprites()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    vids = [iv.Video(out_crt, W + 32, H + 60), iv.Video(out_sharp, W + 32, H + 60)]
    d, f = sv.lv.FAR, 0
    x = np.arange(fb.W)
    while d > DNEAR - 2 * SPEED:
        p = f & 1
        img = np.zeros((fb.H, fb.W), int)
        if d >= DNEAR:
            h = max(2, min(gc.HMAX, lv.bar_lines(d)))
            key = (h, round(d * 2) / 2)          # by distance (0.5 m) as well
            if key not in ramps:
                ramps[key] = gc.ramp_round(h, key[1])
            top = int(round((2 * gc.CYL - 2 * gc.F * (-below) / d - h) / 2))
            for j in range(h):
                ln = top + j
                if 0 <= ln < gc.NLINES:
                    r = ln + 11                  # mock row
                    k = ramps[key][j]
                    t = tabs[p]
                    img[r] = t[32 * (r & 1) + k]
                    g = t[64 + 32 * (r & 1) + k]
                    if g:
                        img[r, ((g >> (7 - x % 8)) & 1) == 1] = 0
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
        for v, crt in zip(vids, (True, False)):
            canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
            dr = ImageDraw.Draw(canvas)
            label = f"{d:5.2f} m   {h} lines" if d >= DNEAR else "clipped"
            dr.text((16, 8), f"one cosmic string, {below:.2f} m below the ship:   {label}   "
                    f"{'CRT' if crt else 'sharp'}", fill=(170, 176, 210), font=small)
            look = lv.crt_look(rgb, Z) if crt else Image.fromarray(rgb).resize((W, H), Image.NEAREST)
            canvas.paste(look, (16, 40))
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
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.3)
