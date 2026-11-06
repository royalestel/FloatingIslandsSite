#!/usr/bin/env python3
"""Preview v8: v3 exactly, except the centre of the bar goes white sooner
(v7's white swatches: cyan + white every other row on alternate frames,
cyan | white stripes).  Only the rows within CORE_R of the centre get the
brighter target (v7's near-in brightness, fading to v3's at CORE_R); the
rest of the bar, the flicker phase (by screen line) and the patterns'
choice per height are v3's.  Side by side with v3, CRT.

    python3 preview_v8.py video.mp4
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
import preview_v7 as v7          # the white swatches, colour() / ghost()

CORE_R = 0.4
SPEED, BELOW = v7.SPEED, v7.BELOW
DNEAR = v7.DNEAR

def core_white(d):
    keep, gc.V3_ANCHORS = gc.V3_ANCHORS, v7.V7_ANCHORS
    try:
        return gc.core_v3(d)
    finally:
        gc.V3_ANCHORS = keep

def ramp_v8(h, d):
    """v3's pattern, with only the centre rows (|r| < CORE_R) replaced by
    brighter swatches from v7's ladder (never darker than v3's, never
    brighter than the row inside them); every other row is v3's."""
    base = gc.ramp_v3(h, d)
    lad = v7.LADDER7
    lum = np.array([sv.LUM[k] for k in lad])
    pos = {k: i for i, k in enumerate(lad)}
    cw, c3 = core_white(d), gc.core_v3(d)
    if cw <= c3 * 1.0001:                          # beyond 5 m: v3 exactly
        return base
    half = (h + 1) // 2
    lower = base[h - half:]
    out, err, kmax = [], 0.0, len(lad) - 1
    for i in range(half):
        j = h - half + i
        r = 2 * (j + 0.5) / h - 1
        if abs(r) >= CORE_R:
            out.append(lower[i])
            continue
        want = gc.row_v3(d, r) + (cw - c3) * (1 - (r / CORE_R) ** 2) + err
        k = int(np.argmin(np.abs(lum - want)))
        k = min(max(k, pos[lower[i]]), kmax)       # not darker than v3, not above the row inside
        kmax = k
        out.append(lad[k])
        err = 0.8 * (want - lum[k])
    upper = out[::-1] if h % 2 == 0 else out[:0:-1]
    return upper + out

def main(path):
    spr = gc.sprites()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    v = iv.Video(path, W + 32, H + 60)
    cache = {}
    x = np.arange(fb.W)
    d, f, last = sv.lv.FAR, 0, None
    while d >= DNEAR:
        p = f & 1
        h = max(2, min(gc.HMAX, lv.bar_lines(d)))
        key = (h, round(d * 10) / 10)
        if key not in cache:
            cache[key] = (gc.ramp_v3(h, key[1]), ramp_v8(h, key[1]))
        top = int(round((2 * gc.CYL + 2 * gc.F * BELOW / d - h) / 2))
        img = np.zeros((fb.H, fb.W), int)
        for j in range(h):
            ln = top + j
            if not 0 <= ln < gc.NLINES:
                continue
            r = ln + 11                              # screen row: v3's flicker phase
            for side, (x0, x1) in enumerate(((0, 160), (160, 320))):
                k = cache[key][side][j]
                img[r, x0:x1] = v7.colour(k, r & 1, p)
                g = v7.ghost(k, r & 1, p)
                if g:
                    row = img[r, x0:x1]
                    row[((g >> (7 - x[x0:x1] % 8)) & 1) == 1] = 0
        rgb = fb.C64RGB[img].astype(np.uint8)
        cols = {1: 4, 2: 14, 3: (1, 3)[p]}
        for s in (0, 1):
            blk = spr[((4 * 4) + p * 2 + s) * 64:][:63]
            for sy in range(21):
                bits = blk[3 * sy] << 16 | blk[3 * sy + 1] << 8 | blk[3 * sy + 2]
                for cx in range(12):
                    val = (bits >> (22 - 2 * cx)) & 3
                    if val:
                        rgb[gc.SPRY + 1 + sy - 51, 136 + s * 24 + 2 * cx:][:2] = fb.C64RGB[cols[val]]
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), f"left: v3   right: v8 (v3 + white centre)   {d:5.2f} m   {h} lines   CRT",
                fill=(170, 176, 210), font=small)
        canvas.paste(lv.crt_look(rgb, Z), (16, 40))
        dr.text((16 + 40, 56), "v3", fill=(200, 200, 220), font=font)
        dr.text((16 + W // 2 + 40, 56), "v8", fill=(200, 200, 220), font=font)
        dr.text((v.w - 200, 56), f"{d:5.2f} m", fill=(235, 235, 120), font=font)
        v.add(canvas)
        last = canvas
        d -= SPEED
        f += 1
    for _ in range(30):
        v.add(last)
    v.close()
    print("wrote", path, f, "frames")

if __name__ == "__main__":
    main(sys.argv[1])
