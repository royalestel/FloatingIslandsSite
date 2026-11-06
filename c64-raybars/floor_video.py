#!/usr/bin/env python3
"""A floor of cosmic strings: horizontal strings lying side by side on a
plane, repeating off into the distance, the camera above them gliding
forward.  Each line gets its light from the cosmic strings bar model
(gen_cosmic.row_v3, front-most string wins, 8 samples a line) and is drawn
with the nearest swatch (by L*) of the flat ramp (ramp_flat_video: the v10
ramp without the ghost-byte swatches).  One swatch per line: no splits
needed yet.  Both frames alternating, CRT look.

    python3 floor_video.py out.mp4 [seconds]
"""
import sys
import numpy as np
from PIL import Image
import flyby3d as fb
import gen_cosmic as gc
import ideas_video as iv
import loop_video as lv
import ramp_flat_video as rf
v7 = rf.v7

W, H, Z = fb.W, fb.H, 3
F, R = fb.F, fb.R               # focal length (lines), string radius (m)
CAM_H = 0.55                    # camera height above the strings (m)
SPACING = 0.8                   # string to string (m)
HORIZON = 14                    # screen line of the horizon
# Screen placement, remapped: a true perspective puts the gap between strings
# at 1/z^2 while a string's thickness goes 1/z, so the far ones merge.  Each
# string keeps its own look (thickness and swatches from its true distance)
# but sits at y = Y_NEAR - A (sqrt z - sqrt Z_NEAR): close together near the
# camera (the near ones overlap, the front one on top), wider apart (relative
# to their thickness) the further they are.
Z_NEAR, Z_FAR, Y_NEAR, Y_FAR = 0.45, 18.0, H + 40, HORIZON
A = (Y_NEAR - Y_FAR) / (np.sqrt(Z_FAR) - np.sqrt(Z_NEAR))
MIX = 0.5                       # 0: true perspective, 1: the sqrt remap
def screen_y(z):
    true = HORIZON + F * CAM_H / z
    remap = Y_NEAR - A * (np.sqrt(z) - np.sqrt(Z_NEAR))
    return (1 - MIX) * true + MIX * remap
SPEED = SPACING / 96            # one spacing every 96 frames: a seamless loop
ZMAX = 40.0
SUB = 8

RAMP = [k for _, k in rf.flat()]
Lstar = lambda y: np.where(y > 0.008856, 116 * np.cbrt(y) - 16, y * 903.3)
RAMP_L = Lstar(np.array([rf.v10.EYE[k] for k in RAMP]))

def lines(cam_z):
    """The swatch (ramp index) of every line: each string quantised on its own
    (row_v3 at its true distance, 8 samples a line), then drawn far to near."""
    first = np.ceil((cam_z + Z_NEAR - 0.3) / SPACING)
    zs = first * SPACING + SPACING * np.arange(int(ZMAX / SPACING)) - cam_z
    out = np.zeros(H, int)
    for z in zs[::-1]:                                        # far first
        if z < 0.3:
            continue
        d = np.hypot(z, CAM_H)
        yc, half = screen_y(z), F * R / d
        y0, y1 = max(0, int(np.floor(yc - half))), min(H, int(np.ceil(yc + half)))
        for y in range(y0, y1):
            r = (y + (np.arange(SUB) + 0.5) / SUB - yc) / half
            r = r[np.abs(r) < 1]
            lit = sum(gc.row_v3(d, v) for v in r) / SUB       # coverage-weighted
            if len(r) < SUB / 2:                              # mostly the string behind
                continue
            k = int(np.argmin(np.abs(Lstar(np.array(lit)) - RAMP_L)))
            if k:
                out[y] = k
            elif len(r) == SUB:
                out[y] = 0                                    # black core edge hides
    return out

def main(path, seconds=8):
    v = iv.Video(path, W * Z, H * Z)
    n = seconds * 60
    for f in range(n):
        idx = lines(f * SPEED)
        img = np.zeros((H, W), int)
        for y, i in enumerate(idx):
            img[y] = v7.colour(RAMP[i], y & 1, f & 1)
        v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8)
