#!/usr/bin/env python3
"""MOCK (not C64 code) of part 1d.  mode "hold": the rotation held until HOLD (fraction), then the flat easing over the rest;
   mode "late": the scene rotates as now and the bars spread (spacing + landing on the floor lines) only from HOLD of the rotation on.
   python3 mock_rotation.py [fraction] [out.mp4] [hold|late]   -> NTSC 60 Hz timeline, film time 1270 .. end"""
import sys, math
import numpy as np
import flyby3d as fb, ideas_video as iv, loop_video as lv
import part1r_gen as g, part1 as p1, part1_proc as q
HOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/mock_rotation.mp4"
H = 200
def delayed_stack(t):
    lin = min(max((t - p1.T_ROT0) / float(p1.T_ROT1 - p1.T_ROT0), 0.0), 1.0)
    u = min(max((lin - HOLD) / (1.0 - HOLD), 0.0), 1.0)          # nothing moves until HOLD, then 0 -> 1
    p = 0.5 * u + 0.5 * p1.smooth(u)
    alpha = math.pi / 2 * p
    s = p1.S0 + (p1.S1 - p1.S0) * p; yp = p1.YP0 + (p1.YP1 - p1.YP0) * p; zp = p1.Z0 + (p1.ZP1 - p1.Z0) * p
    y0 = H / 2 + (p1.HORIZON - H / 2) * p
    out = []
    for m in range(p1.NSTACK):
        y = yp + m * s * math.cos(alpha); z = zp + m * s * math.sin(alpha)
        yc = y0 - p1.F * y / z
        w = p1.smooth((p - 0.6) / 0.4); yc = (1 - w) * yc + w * p1.floor_yc(z)
        d = math.hypot(z, y * p)
        if m < 3: yc += 260 * (1 - p1.smooth((t - p1.T_NEWB[2 - m]) / p1.NEW_LEN))
        elif m > 5: yc -= 600 * (1 - p1.smooth((t - p1.T_TOPB) / (p1.NEW_LEN + 10)))
        out.append((d, yc, d, m, p))
    return out
def late_spread_stack(t):
    """the scene rotates as now (flat easing) with the bars at the stack's spacing; the spreading (spacing S0 -> S1 and the landing on the
    floor's lines) happens only from SPREAD0 of the rotation on"""
    lin = min(max((t - p1.T_ROT0) / float(p1.T_ROT1 - p1.T_ROT0), 0.0), 1.0)
    p = 0.5 * lin + 0.5 * p1.smooth(lin)                                   # the rotation
    ps = p1.smooth(min(max((lin - SPREAD0) / (1.0 - SPREAD0), 0.0), 1.0))  # the spreading, late
    alpha = math.pi / 2 * p
    s = p1.S0 + (p1.S1 - p1.S0) * ps; yp = p1.YP0 + (p1.YP1 - p1.YP0) * p; zp = p1.Z0 + (p1.ZP1 - p1.Z0) * p
    y0 = H / 2 + (p1.HORIZON - H / 2) * p
    out = []
    for m in range(p1.NSTACK):
        y = yp + m * s * math.cos(alpha); z = zp + m * s * math.sin(alpha)
        yc = y0 - p1.F * y / z
        w = ps; yc = (1 - w) * yc + w * p1.floor_yc(z)
        d = math.hypot(z, y * p)
        if m < 3: yc += 260 * (1 - p1.smooth((t - p1.T_NEWB[2 - m]) / p1.NEW_LEN))
        elif m > 5: yc -= 600 * (1 - p1.smooth((t - p1.T_TOPB) / (p1.NEW_LEN + 10)))
        out.append((d, yc, d, m, p))
    return out
MODE = sys.argv[3] if len(sys.argv) > 3 else "hold"
SPREAD0 = HOLD
p1.stack = late_spread_stack if MODE == "late" else delayed_stack
g._state.update(order=None, last=None, memo={})
w = iv.Video(OUT, 960, 600, fps=60)
n0 = int(math.ceil(g.T_ORD0 / g.RATE))
for n in range(n0, g.NN):
    t = g.tau(n); buf = [0] * H
    for y0, T in g.sticky_frame_list(t):
        base = [f & 31 for f in q.FULL[T]] if t < p1.T_STACK else list(p1.gp.PROF[T])
        for i, k in enumerate(base):
            if k and 0 <= y0 + i < H: buf[y0 + i] = k + 32 * (y0 & 1)
    lv_, par = q.parity_of(buf)
    img = np.array([p1.gp.draw([c] * p1.gp.SEGS, (y & ~1) | par[y], n) for y, c in enumerate(lv_)])
    w.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), 3))
w.close(); print("done", g.NN - n0, "frames from film time", g.tau(n0))
