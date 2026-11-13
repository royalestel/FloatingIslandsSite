#!/usr/bin/env python3
"""Part 4 (mock_part4_seq motion) as the C64 shows it, 60 Hz NTSC, with the busy stretch HELD: in frames 270..729 each
pair (even, odd) shows the even frame's picture AND the same flicker phase (no flicker there); elsewhere the usual
60 Hz flicker.  -> /tmp/part4h_frames.pkl (same format as part4_dump.py)."""
import os, pickle
os.environ["SPLITS"] = "6"
import numpy as np
import mock_part4_seq as ms
g4 = ms.g4
HOLD = tuple(int(v) for v in os.environ.get("HOLDRANGE", "270,730").split(","))
frames, idle = [], []
for t in range(ms.T_END):
    f = t - 1 if (HOLD[0] < t < HOLD[1] and t % 2 == 1) else t          # held: the even frame's picture and colours
    seg = ms.tokens(f)
    lines, gh = [], []
    for y in range(200):
        toks = [int(seg[k, y]) for k in range(ms.SEGS)]
        line, flat = g4.fix_line(toks, y, f)
        lines.append([g4.colour(tk, y, f) if tk else 0 for tk in line])
        gh.append(g4.ghost(next((tk for tk in line if tk), 0), y, f) if not flat and any(line) else 0)
    frames.append(np.array(lines, dtype=np.uint8)); idle.append(gh)
pickle.dump((frames, idle), open("/tmp/part4h_frames.pkl", "wb"))
print(len(frames), "frames")
