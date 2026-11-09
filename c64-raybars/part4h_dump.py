#!/usr/bin/env python3
"""Part 4 (mock_part4_seq motion, HOLD2) as the C64 shows it, 60 Hz NTSC: frames -> /tmp/part4h_frames.pkl (same format as part4_dump.py)."""
import os, pickle
os.environ["SPLITS"] = "6"
import numpy as np
import mock_part4_seq as ms
g4 = ms.g4
frames, idle = [], []
for f in range(ms.T_END):
    seg = ms.tokens(f - f % 2)                                    # HOLD2: the picture changes every other frame; colours use f
    lines, gh = [], []
    for y in range(200):
        toks = [int(seg[k, y]) for k in range(ms.SEGS)]
        line, flat = g4.fix_line(toks, y, f)
        lines.append([g4.colour(tk, y, f) if tk else 0 for tk in line])
        gh.append(g4.ghost(next((tk for tk in line if tk), 0), y, f) if not flat and any(line) else 0)
    frames.append(np.array(lines, dtype=np.uint8)); idle.append(gh)
pickle.dump((frames, idle), open("/tmp/part4h_frames.pkl", "wb"))
print(len(frames), "frames")
