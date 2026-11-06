#!/usr/bin/env python3
"""The cosmic strings floor (floor_video, stationary camera) with raster
splits: each line is 6 $d021 segments (GOLDSHIP's split points, sprite x
56/120/184/248/312: window x 32/96/160/224/288, so 32 | 64 x4 | 32 px), and
a string tilts by shifting each segment's copy of its column a whole number
of lines (the staircase).  Pivot at the left end, the right end rises and
falls back (half a sine, TILT_T frames); the closest string starts first,
each string further back STAGGER frames later.  Each string keeps its own
swatches, only moved.  Both frames alternating, CRT look.

    python3 tilt_floor_video.py out.mp4
"""
import sys
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import floor_video as fv
v7 = fv.v7

W, H, Z = fv.W, fv.H, fv.Z
EDGES = [0, 32, 96, 160, 224, 288, 320]          # segment boundaries in the window
XC = np.array([(a + b) / 2 for a, b in zip(EDGES, EDGES[1:])])
TILT_T, STAGGER = 16, 2                          # frames up and down; start delay per string
RISE = 28                                        # the closest string's right-end rise (lines)
RISE_EXP = 0.3                                   # rise ~ thickness^0.3: far strings still
                                                 # rise visibly, so the wave reads into the distance
HOLD0, HOLD1 = 60, 60                            # still frames before / after

def strings():
    """Each string near to far: its rows {y: ramp index} (floor_video's rule)
    and half-thickness."""
    out = []
    zs = fv.SPACING * np.arange(1, int(fv.ZMAX / fv.SPACING) + 1)
    for z in [z for z in zs if z >= 0.3 and fv.screen_y(z) > -4]:   # the ones on screen
        d = np.hypot(z, fv.CAM_H)
        yc, half = fv.screen_y(z), fv.F * fv.R / d
        rows = {}
        for y in range(int(np.floor(yc - half)), int(np.ceil(yc + half))):
            r = (y + (np.arange(fv.SUB) + 0.5) / fv.SUB - yc) / half
            r = r[np.abs(r) < 1]
            if len(r) < fv.SUB / 2:
                continue
            lit = sum(fv.gc.row_v3(d, v) for v in r) / fv.SUB
            k = int(np.argmin(np.abs(fv.Lstar(np.array(lit)) - fv.RAMP_L)))
            if k or len(r) == fv.SUB:
                rows[y] = k
        out.append((rows, half))
    return out

def frame(strs, t):
    """Ramp index per (segment, line) at animation frame t."""
    seg = np.zeros((len(XC), H), int)
    half0 = strs[0][1]
    for i in range(len(strs) - 1, -1, -1):               # far first
        rows, half = strs[i]
        u = (t - STAGGER * i) / TILT_T
        a = RISE * (half / half0) ** RISE_EXP * np.sin(np.pi * u) if 0 < u < 1 else 0.0
        offs = -np.round(a * XC / W).astype(int)          # right end up
        for s, o in enumerate(offs):
            for y, k in rows.items():
                yy = y + o
                if 0 <= yy < H:
                    seg[s, yy] = k
    return seg

def main(path):
    strs = strings()
    n_anim = STAGGER * (len(strs) - 1) + TILT_T
    v = iv.Video(path, W * Z, H * Z)
    for f in range(HOLD0 + n_anim + HOLD1):
        seg = frame(strs, f - HOLD0)
        img = np.zeros((H, W), int)
        for s, (a, b) in enumerate(zip(EDGES, EDGES[1:])):
            for y in range(H):
                img[y, a:b] = v7.colour(fv.RAMP[seg[s, y]], y & 1, f & 1)
        v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    v.close()
    print("wrote", path, len(strs), "strings", HOLD0 + n_anim + HOLD1, "frames")

if __name__ == "__main__":
    main(sys.argv[1])
