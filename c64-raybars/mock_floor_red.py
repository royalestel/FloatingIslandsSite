#!/usr/bin/env python3
"""MOCK screenshot (no C64 code): the final floor (1 blank line between bars) with the empty lines' background colour red ($d021 = 2) instead of black.
   The ghost pixels of the bars stay black (the idle byte's 1-bits are always black).   python3 mock_floor_red.py [out.png] [colour index] [shift down]"""
import os, sys, math
os.environ["SPLITS"] = "6"
import numpy as np
from PIL import Image
import flyby3d as fb, loop_video as lv
import part1 as p1, part1_proc as q
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/floor_red.png"
BG = int(sys.argv[2]) if len(sys.argv) > 2 else 2
SHIFT = int(sys.argv[3]) if len(sys.argv) > 3 else 0                # lines the whole floor moves down (15: the nearest bar ends on line 199)
H = 200
s = p1.S1; yp = p1.YP1; zp = p1.ZP1
base = [max(1, min(p1.TMAX, int(round(2 * p1.F * p1.R / max(math.hypot(zp + m * s, yp), 0.6))))) for m in range(p1.NSTACK)]
Td = [p1.gp.BT(base[m], p1.gp.edge_level(m), m, 1.0) for m in range(p1.NSTACK)]
y0s = []
for m in range(p1.NSTACK):
    y0s.append(int(round(p1.floor_yc(zp) - Td[0] / 2)) + SHIFT if m == 0 else y0s[-1] - 1 - Td[m])
buf = [0] * H
for m in range(p1.NSTACK - 1, -1, -1):
    for i, k in enumerate(p1.gp.PROF[Td[m]]):
        if k and 0 <= y0s[m] + i < H: buf[y0s[m] + i] = k + 32 * (y0s[m] & 1)
lv_, par = q.parity_of(buf)
n = 1
img = np.array([p1.gp.draw([c] * p1.gp.SEGS, (y & ~1) | par[y], n) for y, c in enumerate(lv_)])
for y in range(H):
    if lv_[y] == 0: img[y, :] = BG                   # an empty line: $d021 = BG, the idle byte 0
lv.crt_look(fb.C64RGB[img].astype(np.uint8), 3).save(OUT)
Image.fromarray(fb.C64RGB[img].astype(np.uint8)).resize((960, 600), Image.NEAREST).save(OUT.replace(".png", "_sharp.png"))
print("wrote", OUT, "floor y0/T:", list(zip(y0s, Td))[:4], "...")
