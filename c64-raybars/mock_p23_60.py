#!/usr/bin/env python3
"""MOCK (no C64 code): part 3 = all the waves (part 2's waves, then 3c/3d/3e), ending before the random moves, with every tilt and lift capped at 15 lines.
   6 columns, 50 fps, the model's floor.   python3 mock_part3_cap15.py [out.mp4]"""
import os, sys
os.environ["SPLITS"] = "6"
import numpy as np
import flyby3d as fb, ideas_video as iv, loop_video as lv
import part2 as p2, part3 as p3, ghost_part2 as gp2, ghost_part3 as gp3
START = int(os.environ.get("START", "0"))          # first frame written (the frame counter still runs from 0: flicker parity)
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mock_part3_cap15.mp4"
CAP = 16                                         # a peak of CAP x (5.5/6) = 15 lines in the outermost column
for A in list(gp2.ANIMS) + [gp3.ANIM4]:
    f0 = A["amp"]; A["amp"] = (lambda f: lambda i, T0, T: min(f(i, T0, T), CAP))(f0)
p2.W5["amp"] = min(p2.W5["amp"], CAP); p2.W6["amp"] = min(p2.W6["amp"], CAP)
p3.AMP = min(p3.AMP, CAP); p3.LIFT = 15
v = iv.Video(OUT, 960, 600, fps=60)
def look(img):                                   # CRT filter unless NOCRT=1 (plain 3x nearest-neighbour, as part 1's no-CRT mock)
    if os.environ.get("NOCRT"):
        from PIL import Image
        return Image.fromarray(np.repeat(np.repeat(img, 3, axis=0), 3, axis=1))
    return lv.crt_look(img, 3)
f = 0; n = 0
seq = p2.make_seq()
for n_i, (A, segs, wave) in enumerate(seq):                       # part 2's waves (the earthquake skipped: a short lead-in)
    pre = p2.SHAKE if n_i == 0 else 0               # the earthquake first (part 2's own shake), then no pauses between the waves
    post = 0 if n_i < len(seq) - 1 else 60
    for t in range(pre + wave + post):
        seg = segs(t - pre); img = []
        if n_i == 0 and t < pre:                    # the earthquake: the same whole-floor and column shifts as part2.main
            dy, dk = p2.shake_offsets(t)
            seg = np.stack([p2.shift_rows(seg[k:k + 1], dy + dk[k])[0] for k in range(p2.SEGS)])
        for y in range(p2.H):
            toks = [int(seg[k, y]) for k in range(p2.SEGS)]
            line, _ = p2.fix_line(toks, y, f)
            img.append(p2.draw(line, y, f))
        (v.add(look(fb.C64RGB[np.array(img)].astype(np.uint8))) if f >= START else None); f += 1
wave = (p3.NS - 1) * p3.STAG + p3.TILT
for name, cols, static, pre, length, post in [("3c", p3.SPEC_3C, p3.START, 30, wave, 20), ("3d", p3.SPEC_3D, p3.STATE_3C, 0, wave, 20),
                                              ("3e", p3.COLS_3E, p3.STATE_3D, 0, wave, 90)]:
    for t in range(pre + length + post):
        seg = p3.tokens(cols, static, t - pre); img = []
        for y in range(p3.H):
            toks = [int(seg[k, y]) for k in range(p3.SEGS)]
            line, _ = p3.g4.fix_line(toks, y, f)
            img.append(p3.g4.draw(line, y, f))
        (v.add(look(fb.C64RGB[np.array(img)].astype(np.uint8))) if f >= START else None); f += 1
v.close(); print("wrote", OUT, f, "frames")
