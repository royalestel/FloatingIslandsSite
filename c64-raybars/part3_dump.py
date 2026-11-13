#!/usr/bin/env python3
"""Dumps part 3's frames as the C64 must show them (6 columns): per frame 200 x 6 colour bytes and the 200 idle bytes,
with the video's rule (ghost swatches only on lines where every column agrees) -> /tmp/part3_frames.pkl

    SPLITS=6 python3 part3_dump.py
"""
import os, pickle, math
os.environ.setdefault("SPLITS", "6")
import numpy as np
import part3 as p3, ghost_part4 as g4

seq = [("3c", p3.SPEC_3C, p3.START, 30, (p3.NS - 1) * p3.STAG + p3.TILT, 20),
       ("3d", p3.SPEC_3D, p3.STATE_3C, 0, (p3.NS - 1) * p3.STAG + p3.TILT, 20),
       ("3e", p3.COLS_3E, p3.STATE_3D, 0, (p3.NS - 1) * p3.STAG + p3.TILT, 90)]
RATE = 1.0                                                   # one film frame per displayed frame (the 60 fps mock-up's timing)
segs_all = []
for name, cols, static, pre, L, post in seq:
    for t in range(pre + L + post):
        segs_all.append(p3.tokens(cols, static, t - pre))
NN = int(math.ceil(len(segs_all) / RATE)); NN += NN % 2
frames, idle = [], []
for n in range(NN):
    seg = segs_all[min(int(round(n * RATE)), len(segs_all) - 1)]
    f = n                                                    # the flicker parity of the displayed frame
    lines, gh = [], []
    for y in range(200):
        toks = [int(seg[k, y]) for k in range(p3.SEGS)]
        line, flat = g4.fix_line(toks, y, f)
        lines.append([g4.colour(tk, y, f) if tk else 0 for tk in line])
        gh.append(g4.ghost(next((tk for tk in line if tk), 0), y, f) if not flat and any(line) else 0)
    frames.append(np.array(lines, dtype=np.uint8)); idle.append(gh)
pickle.dump((frames, idle), open("/tmp/part3_frames.pkl", "wb"))
print(len(frames), "frames")
