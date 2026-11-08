#!/usr/bin/env python3
"""Part 2's waves (frames SHAKE..end) as the C64 shows them (6 columns) -> /tmp/part2w_frames.pkl   (SPLITS=6 python3 part2_dump.py)"""
import os, pickle
os.environ["SPLITS"] = "6"
import numpy as np
import part2 as p2, ghost_part4 as g4
frames, idle, f = [], [], 0
seq = p2.make_seq()
for n_i, (A, segs, wave) in enumerate(seq):
    pre = p2.SHAKE if n_i == 0 else 10
    post = 10 if n_i < len(seq) - 1 else 60
    for t in range(pre + wave + post):
        if n_i == 0 and t < p2.SHAKE:
            f += 1; continue
        seg = segs(t - pre)
        lines, gh = [], []
        for y in range(200):
            toks = [int(seg[k, y]) for k in range(p2.SEGS)]
            line, flat = p2.fix_line(toks, y, f)
            lines.append([p2.colour(tk, y, f) if tk else 0 for tk in line])
            gh.append(p2.ghost(next((tk for tk in line if tk), 0), y, f) if not flat and any(line) else 0)
        frames.append(np.array(lines, dtype=np.uint8)); idle.append(gh); f += 1
pickle.dump((frames, idle), open("/tmp/part2w_frames.pkl", "wb"))
print(len(frames), "frames, last f", f)
