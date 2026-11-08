#!/usr/bin/env python3
"""MOCK (no C64 code): part 1 from the vertical stacking to the end -- 3 bars aligned 6 lines higher, the 3 bottom bars rising from 1.5 s, the scene
   rotating (no spreading), and from 25 % of the rotation on every bar moving in a STRAIGHT LINE (centre line and thickness) to its place on the final
   floor (1 blank line between bars).   python3 mock_full1d.py [out.mp4] [spread start fraction]"""
import os, sys, math
MYOUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mock_full1d.mp4"
START = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
sys.argv = ["x", "1.0", "/tmp/none.mp4", "nospread", "6", "1345"]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_rotation.py")).read().split("g._state.update")[0]
exec(src)                                                  # the rotation without spreading, the shift, the early bottom bars; g._bars_at = mock_bars_at
import numpy as np
H = 200
def floor_state():                                          # the final floor: (centre line, base thickness) per slot m, 1 blank line between bars
    s = p1.S1; p = 1.0
    yp = p1.YP0 + (p1.YP1 - p1.YP0) * p; zp = p1.Z0 + (p1.ZP1 - p1.Z0) * p
    base = []
    for m in range(p1.NSTACK):
        z = zp + m * s; d = math.hypot(z, yp * p)
        base.append(max(1, min(p1.TMAX, int(round(2 * p1.F * p1.R / max(d, 0.6))))))
    Td = [p1.gp.BT(base[m], p1.gp.edge_level(m), m, 1.0) for m in range(p1.NSTACK)]
    y0s = []
    for m in range(p1.NSTACK):
        y0 = int(round(p1.floor_yc(zp + 0 * s) - Td[0] / 2)) if m == 0 else y0s[-1] - 1 - Td[m]
        y0s.append(y0)
    return [(y0s[m] + Td[m] / 2.0, base[m]) for m in range(p1.NSTACK)]
FLOOR = floor_state()
_base_bars_at = g._bars_at
def blended_bars_at(t):
    bars = _base_bars_at(t)
    lin = (t - p1.T_ROT0) / float(p1.T_ROT1 - p1.T_ROT0)
    w = min(max((lin - START) / (1.0 - START), 0.0), 1.0)    # a straight line, no easing
    if w > 0:
        for b in bars:
            m = b["id"][1]
            yc1, T1 = FLOOR[m]
            Tb = max(1, min(p1.TMAX, int(round(2 * p1.F * p1.R / max(-b["key"], 0.6)))))
            Tn = max(1, min(p1.TMAX, int(round(Tb + (T1 - Tb) * w))))
            Tn = p1.gp.BT(Tn, p1.gp.edge_level(m), m, 1.0)
            yc = b["yc"] + (yc1 - b["yc"]) * w
            b.update(yc=yc, T=Tn, y0=int(round(yc - Tn / 2)))
    return bars
g._bars_at = blended_bars_at
g._state.update(order=None, last=None, memo={})
print("final floor (nearest first):", [(int(round(c - p1.gp.BT(b, p1.gp.edge_level(m), m, 1.0) / 2)), p1.gp.BT(b, p1.gp.edge_level(m), m, 1.0)) for m, (c, b) in enumerate(FLOOR)])
w_ = iv.Video(MYOUT, 960, 600, fps=60)
n0 = int(math.ceil(g.T_ORD0 / g.RATE))
for n in range(n0, g.NN):
    t = g.tau(n); buf = [0] * H
    for y0, T in g.sticky_frame_list(t):
        base = [f & 31 for f in q.FULL[T]] if t < p1.T_STACK else list(p1.gp.PROF[T])
        for i, k in enumerate(base):
            if k and 0 <= y0 + i < H: buf[y0 + i] = k + 32 * (y0 & 1)
    lv_, par = q.parity_of(buf)
    img = np.array([p1.gp.draw([c] * p1.gp.SEGS, (y & ~1) | par[y], n) for y, c in enumerate(lv_)])
    w_.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), 3))
w_.close(); print("wrote", MYOUT, g.NN - n0, "frames")
