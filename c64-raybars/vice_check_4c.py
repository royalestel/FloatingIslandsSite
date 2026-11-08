#!/usr/bin/env python3
"""VICE check of part4c.crt: screenshot at several moments vs the model (part 3's frames: colour bytes + idle bytes).
    SPLITS=6 VICEXTRA="-VICIImodel 6569" python3 vice_check_3c.py [seconds ...]"""
import os, pickle, sys
os.environ.setdefault("SPLITS", "6")
import numpy as np
import vice_check_2c as v2

frames, gh = pickle.load(open("/tmp/part4_frames.pkl", "rb"))
N = len(frames)
EDGES = v2.EDGES

def model(f):
    f %= N
    cols, idle = frames[f], gh[f]
    x = np.arange(320)
    img = np.zeros((200, 320), int)
    for y in range(200):
        row = np.zeros(320, int)
        for k in range(6):
            row[EDGES[k]:EDGES[k + 1]] = cols[y, k]
        g = idle[y]
        if g:
            row[((g >> (7 - x % 8)) & 1) == 1] = 0
        img[y] = row
    return img

def main():
    pal = v2.palette(); ok = True
    for w in [float(a) for a in sys.argv[1:]] or [3, 4.5, 6, 7.5]:
        shot = f"/tmp/v4c_{w}.png"
        lblname = "part4c.lbl"
        fcl = v2.one(w, shot, crt="part4c.crt", lbl=lblname) // 2   # NTSC: 2 blanks a film frame
        V = v2.decode(shot, pal)
        best = max(((V == model(f)).mean(), f) for f in range(max(0, fcl - 4), fcl + 1))
        print(f"after {w}s: frame counter {fcl}; best match frame {best[1] % N}: {100 * best[0]:.2f} %" + ("  (a frame with stale lines, by design)" if (best[1] % N) in set(map(int, open("part4c_late.txt").read().split())) else ""))
        late = set(map(int, open('part4c_late.txt').read().split()))
        ok &= best[0] == 1.0 or (best[1] % N) in late
    print("all pixel exact" if ok else "MISMATCH")

if __name__ == "__main__":
    main()
