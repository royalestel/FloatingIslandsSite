#!/usr/bin/env python3
"""Video (60 Hz): every ladder step, left the real swatch (colour + ghost byte, both flipping with frame parity), right its flat
version for the tilted segments (flat_ladder.py, the bar's upper half).  Pixels as the C64 shows them, no blending: the eye does it.
    python3 flat_ladder_video.py out.mp4 [seconds]"""
import sys, subprocess
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flat_ladder as fl
import preview_v10 as v10
OUT = sys.argv[1] if len(sys.argv) > 1 else "flat_ladder.mp4"
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 8
H, W, GAP, GX, S, TOP = 12, 128, 4, 24, 2, 14
pairs = fl.flat_pairs()
n = len(v10.LAD)
def frame(f):
    p = f & 1
    img = np.zeros((TOP + n * (H + GAP), 2 * W + 3 * GX, 3), np.uint8)
    for i, k in enumerate(v10.LAD):
        y0 = TOP + i * (H + GAP)
        rows = fl.real_rows(k, p)
        for r in range(H):
            img[y0 + r, GX:GX + W] = fb.C64RGB[[rows[r & 1][x % 8] for x in range(W)]]
            img[y0 + r, 2 * GX + W:2 * GX + 2 * W] = fb.C64RGB[fl.flat_colour(pairs[i], r & 1, p, i)]
    im = Image.fromarray(img); d = ImageDraw.Draw(im)
    d.text((GX, 1), "ghost byte (now)", fill=(255, 255, 160)); d.text((2 * GX + W, 1), "flat (tilted)", fill=(255, 255, 160))
    for i in range(n):
        d.text((2, TOP + i * (H + GAP) + 1), str(i), fill=(160, 160, 160))
    a = np.array(im)
    return np.repeat(np.repeat(a, S, 0), S, 1)
f0 = frame(0)
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{f0.shape[1]}x{f0.shape[0]}", "-r", "60",
                       "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "10", OUT], stdin=subprocess.PIPE)
fr = [frame(0).tobytes(), frame(1).tobytes()]
for f in range(int(SECS * 60)):
    ff.stdin.write(fr[f & 1])
ff.stdin.close(); ff.wait(); print("wrote", OUT)
