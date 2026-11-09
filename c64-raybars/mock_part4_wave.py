#!/usr/bin/env python3
"""MOCK (no C64 code): part 4 as DELAYED COPIES.  Two movement sources (A: 20 bars, B: 20 bars; each with its own random speeds/swings/flashes, taken
from columns 0 and 1 of mock_part4_seq's model, matching off) feed the six columns: even columns (0,2,4) show A, odd columns (1,3,5) show B, each
delayed by D_k = 16 k frames (A: 0, 32, 64; B: 16, 48, 80).  A column that has not started yet shows its source's first state (part 3's end:
even = multicolour, odd = red).  Both sources end at rest, blue; the wipe starts when the last column has settled.
On the C64 this is a ring of pages per source: ~146 slots (37 KB), a 127..135-byte page copy per source per frame, no change stream.
    python3 mock_part4_wave.py [out.mp4]"""
import os, sys
os.environ["SPLITS"] = "6"
import numpy as np
import mock_part4_seq as ms
STEP = 16
D = [STEP * k for k in range(6)]                       # column k's delay (even: A, odd: B)
LAST = ms.T_SETTLE0 + ms.SETTLE                         # the sources are at rest from here
NMAX = ms.own.shape[0] - 1

_palette = ms.palette                                   # the model's own (events of its columns 0 and 1)

def pos(i, k, t):
    ts = min(max(0, t - D[k]), NMAX)
    return float(ms.own[ts, i, k % 2]), float(ms.thick[ts, i, k % 2])

def palette(i, k, t):
    return _palette(i, k % 2, min(max(0, t - D[k]), NMAX))

ms.pos, ms.palette = pos, palette
ms.T_SWEEP0 = LAST + D[5] + 30                          # every column at rest, a short hold, then the wipe
T_END = ms.T_SWEEP0 + ms.T_UP + ms.T_DOWN + 60

def first_rows():
    f = []
    for t in range(T_END):
        seg = ms.tokens(t)
        nz = np.where(seg.any(axis=0))[0]
        f.append(int(nz[0]) if len(nz) else 200)
    return f

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mock_part4_wave.mp4"
    if os.environ.get("STATS"):
        f = first_rows(); busy = [x for x in f[:ms.T_SWEEP0]]
        print("first active row F: min %d, mean %.0f (before the wipe); frames %d" % (min(busy), np.mean(busy), T_END)); sys.exit()
    print("frames", T_END, "sources at rest from", LAST, "all columns at rest from", LAST + D[5], "wipe from", ms.T_SWEEP0, flush=True)
    Z = 3
    v = ms.iv.Video(out, ms.m.W * Z, ms.H * Z)
    for f in range(T_END):
        seg = ms.tokens(f); img = []
        for y in range(ms.H):
            line, _ = ms.g4.fix_line([int(seg[k, y]) for k in range(ms.SEGS)], y, f)
            img.append(ms.g4.draw(line, y, f))
        v.add(ms.lv.crt_look(ms.fb.C64RGB[np.array(img)].astype(np.uint8), Z))
    v.close(); print("wrote", out)
