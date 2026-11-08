#!/usr/bin/env python3
"""MOCK (no C64 code): part 3's second wave (3d) on the floor that the 'no spreading' rotation ends on (mock_rotation.py nospread).
   python3 mock_wave3d.py [out.mp4]"""
import os, sys
os.environ["SPLITS"] = "6"
sys.argv = [sys.argv[0], "1.0", "/dev/null", "nospread", "0"] + sys.argv[1:2]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_rotation.py")).read().split("g._state.update")[0]
exec(src)                                                     # the nospread stack in the model
OUT = sys.argv[5] if len(sys.argv) > 5 else "/tmp/mock_wave3d.mp4"
import numpy as np
import part3 as p3, flyby3d as fb, ideas_video as iv, loop_video as lv
bars = {b["id"]: b for b in g._bars_at(p1.T_END - 0.5)}
NEW = [(bars[("s", m)]["y0"], bars[("s", m)]["T"]) for m in range(p3.NS)]   # m = 0 nearest (bottom), as STR
print("old floor", p3.STR); print("new floor", NEW)
p3.STR = NEW
g4 = p3.g4
wave = (p3.NS - 1) * p3.STAG + p3.TILT
pre, post = 20, 30
v = iv.Video(OUT, p3.W * 3, p3.H * 3)
f = 0
for t in range(pre + wave + post):
    seg = p3.tokens(p3.SPEC_3D, p3.STATE_3C, t - pre)
    img = []
    for y in range(p3.H):
        toks = [int(seg[k, y]) for k in range(p3.SEGS)]
        line, _ = g4.fix_line(toks, y, f)
        img.append(g4.draw(line, y, f))
    v.add(lv.crt_look(fb.C64RGB[np.array(img)].astype(np.uint8), 3)); f += 1
v.close(); print("wrote", OUT, f, "frames")
