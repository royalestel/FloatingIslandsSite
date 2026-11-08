#!/usr/bin/env python3
"""Part 4's frames as the C64 shows them (6 columns) -> /tmp/part4_frames.pkl   (SPLITS=6 python3 part4_dump.py)"""
import os, pickle
os.environ["SPLITS"] = "6"
import numpy as np
import part4m as p4
g4 = p4.g4
frames, idle = [], []
for f in range(p4.T_END - (p4.T_END % 2)):
    seg = p4.tokens(f)
    lines, gh = [], []
    for y in range(200):
        toks = [int(seg[k, y]) for k in range(p4.SEGS)]
        line, flat = g4.fix_line(toks, y, f)
        lines.append([g4.colour(tk, y, f) if tk else 0 for tk in line])
        gh.append(g4.ghost(next((tk for tk in line if tk), 0), y, f) if not flat and any(line) else 0)
    frames.append(np.array(lines, dtype=np.uint8)); idle.append(gh)
pickle.dump((frames, idle), open("/tmp/part4_frames.pkl", "wb"))
print(len(frames), "frames")
