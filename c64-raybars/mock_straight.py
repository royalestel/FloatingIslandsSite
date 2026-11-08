#!/usr/bin/env python3
"""MOCK (no C64 code): each bar moves in a STRAIGHT LINE (centre line and thickness, both linear in time) from its place in the fully rotated stack
   (spacing S0) to its place on the final floor (spacing S1).  Compare mock_spacing.py (the model's own path).
   python3 mock_straight.py [out.mp4] [ramp frames at 60 fps]"""
import os, sys, math
os.environ["SPLITS"] = "6"
import numpy as np
import flyby3d as fb, ideas_video as iv, loop_video as lv
import part1 as p1, part1_proc as q
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mock_straight.mp4"
RAMP = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 120      # [--gap N]: the final bars N blank lines apart
HOLD = 30
H = 200
def state(u):                                     # the model's bars at spacing parameter u (0 = stack spacing, 1 = floor): [(centre line, base thickness)]
    p = 1.0; alpha = math.pi / 2
    s = p1.S0 + (p1.S1 - p1.S0) * u
    yp = p1.YP0 + (p1.YP1 - p1.YP0) * p; zp = p1.Z0 + (p1.ZP1 - p1.Z0) * p
    y0 = H / 2 + (p1.HORIZON - H / 2) * p
    out = []
    for m in range(p1.NSTACK):
        y = yp + m * s * math.cos(alpha); z = zp + m * s * math.sin(alpha)
        yc = (1 - u) * (y0 - p1.F * y / z) + u * p1.floor_yc(z)
        d = math.hypot(z, y * p)
        out.append((yc, 2 * p1.F * p1.R / max(d, 0.6)))
    return out
A, B = state(0.0), state(1.0)
GAP = int(sys.argv[sys.argv.index("--gap") + 1]) if "--gap" in sys.argv else None
if GAP is not None:                              # the final floor: every bar GAP blank line(s) above the one below it, thicknesses as the model's floor
    Td = [p1.gp.BT(max(1, min(p1.TMAX, int(round(B[m][1])))), p1.gp.edge_level(m), m, 1.0) for m in range(p1.NSTACK)]
    y0s = []
    for m in range(p1.NSTACK):
        y0s.append(int(round(B[0][0] - Td[0] / 2)) if m == 0 else y0s[-1] - GAP - Td[m])
    B = [(y0s[m] + Td[m] / 2.0, B[m][1]) for m in range(p1.NSTACK)]
    print("final y0, thickness (nearest first):", list(zip(y0s, Td)))
if "--path" in sys.argv:
    for m in (3, 9, 15):
        print("bar", m, "the model's own path (centre line at u = 0, .25, .5, .75, 1):", [round(state(u)[m][0], 1) for u in (0, .25, .5, .75, 1)])
    sys.exit()
v = iv.Video(OUT, 960, 600, fps=60)
for n in range(HOLD + RAMP + HOLD):
    u = min(max((n - HOLD) / float(RAMP), 0.0), 1.0)
    buf = [0] * H
    for m in range(p1.NSTACK - 1, -1, -1):        # far first
        yc = A[m][0] + (B[m][0] - A[m][0]) * u
        T = max(1, min(p1.TMAX, int(round(A[m][1] + (B[m][1] - A[m][1]) * u))))
        T = p1.gp.BT(T, p1.gp.edge_level(m), m, 1.0)
        y0 = int(round(yc - T / 2))
        if y0 >= H or y0 + T <= 0: continue
        for i, k in enumerate(p1.gp.PROF[T]):
            if k and 0 <= y0 + i < H: buf[y0 + i] = k + 32 * (y0 & 1)
    lv_, par = q.parity_of(buf)
    img = np.array([p1.gp.draw([c] * p1.gp.SEGS, (y & ~1) | par[y], n) for y, c in enumerate(lv_)])
    v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), 3))
v.close(); print("wrote", OUT, HOLD + RAMP + HOLD, "frames")
