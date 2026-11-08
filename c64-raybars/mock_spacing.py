#!/usr/bin/env python3
"""MOCK (no C64 code): the scene already rotated completely (the floor view, bars at the stack's spacing S0), then the SPACING alone is animated:
   s = S0 + (S1 - S0) * u, with u a straight line 0 -> 1 (no easing, no smoothing), and the landing on the floor's lines blended with the same u.
   python3 mock_spacing.py [out.mp4] [ramp frames at 60 fps]"""
import os, sys, math
os.environ["SPLITS"] = "6"
import numpy as np
import flyby3d as fb, ideas_video as iv, loop_video as lv
import part1r_gen as g, part1 as p1, part1_proc as q
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mock_spacing.mp4"
RAMP = int(sys.argv[2]) if len(sys.argv) > 2 else 120
HOLD = 30
H = 200
U = [0.0]                                                    # the spacing parameter of the frame being drawn
def spaced_stack(t):
    u = U[0]
    p = 1.0                                                  # the scene is rotated completely
    alpha = math.pi / 2 * p
    s = p1.S0 + (p1.S1 - p1.S0) * u                          # the spacing: a straight line
    yp = p1.YP0 + (p1.YP1 - p1.YP0) * p; zp = p1.Z0 + (p1.ZP1 - p1.Z0) * p
    y0 = H / 2 + (p1.HORIZON - H / 2) * p
    out = []
    for m in range(p1.NSTACK):
        y = yp + m * s * math.cos(alpha); z = zp + m * s * math.sin(alpha)
        yc = y0 - p1.F * y / z
        yc = (1 - u) * yc + u * p1.floor_yc(z)               # landing on the floor's lines, the same straight line
        d = math.hypot(z, y * p)
        out.append((d, yc, d, m, p))
    return out
p1.stack = spaced_stack
g._state.update(order=None, last=None, memo={})
v = iv.Video(OUT, 960, 600, fps=60)
N = HOLD + RAMP + HOLD
for n in range(N):
    U[0] = min(max((n - HOLD) / float(RAMP), 0.0), 1.0)
    buf = [0] * H
    for y0, T in g.sticky_frame_list(2000.0 + n):
        for i, k in enumerate(p1.gp.PROF[T]):
            if k and 0 <= y0 + i < H: buf[y0 + i] = k + 32 * (y0 & 1)
    lv_, par = q.parity_of(buf)
    img = np.array([p1.gp.draw([c] * p1.gp.SEGS, (y & ~1) | par[y], n) for y, c in enumerate(lv_)])
    v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), 3))
v.close(); print("wrote", OUT, N, "frames")
