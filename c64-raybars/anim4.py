#!/usr/bin/env python3
# anim4: anim3 starting in the blue ramp; each string flashes white on the frame of its
# apex tilt and fades down the red ramp (red_ramp.py) to its own red swatches as it comes to rest.
# Black rows are not drawn (black is just $d021 background), so they never hide a string behind.
"""The cosmic strings floor (floor_video, stationary camera) with raster
splits: each line is 6 $d021 segments (GOLDSHIP's split points, sprite x
56/120/184/248/312: window x 32/96/160/224/288, so 32 | 64 x4 | 32 px), and
a string tilts by shifting each segment's copy of its column a whole number
of lines (the staircase).  Pivot at the left end, the right end rises and
falls back (half a sine, TILT_T frames); the closest string starts first,
each string further back STAGGER frames later.  Each string keeps its own
swatches, only moved.  Both frames alternating, CRT look.

    python3 anim4.py anim4.mp4
"""
import sys
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import anim1_floor as fv          # frozen copy of floor_video.py
import red_ramp as rr
v7 = fv.v7

W, H, Z = fv.W, fv.H, fv.Z
EDGES = [0, 32, 96, 160, 224, 288, 320]          # segment boundaries in the window
XC = np.array([(a + b) / 2 for a, b in zip(EDGES, EDGES[1:])])
TILT_T, STAGGER = 32, 4                          # frames up and down; start delay per string
RISE = 28                                        # the closest string's right-end rise (lines)
RISE_EXP = 0.0                                   # every string rises the same RISE lines

HOLD0, HOLD1 = 60, 60                            # still frames before / after

def strings():
    """Each string near to far: its rows {y: ramp index} (floor_video's rule)
    and half-thickness."""
    out = []
    zs = fv.SPACING * np.arange(1, int(fv.ZMAX / fv.SPACING) + 1)
    for z in [z for z in zs if z >= 0.3 and fv.screen_y(z) > -4]:   # the ones on screen
        d = np.hypot(z, fv.CAM_H)
        yc, half = fv.screen_y(z), fv.F * fv.R / d
        both = []
        for ramp_l in (fv.RAMP_L, rr.RAMP_L):           # blue, red
          rows = {}
          for y in range(int(np.floor(yc - half)), int(np.ceil(yc + half))):
            r = (y + (np.arange(fv.SUB) + 0.5) / fv.SUB - yc) / half
            r = r[np.abs(r) < 1]
            if len(r) < fv.SUB / 2:
                continue
            lit = sum(fv.gc.row_v3(d, v) for v in r) / fv.SUB
            k = int(np.argmin(np.abs(rr.Lstar(np.array(lit)) - ramp_l)))
            if k:                                    # black is the background: never painted
                rows[y] = k
          both.append(rows)
        out.append((both[0], both[1], half))
    return out

RED = 100                                        # seg values >= RED: red ramp index + RED

def frame(strs, t):
    """Ramp index per (segment, line) at animation frame t."""
    seg = np.zeros((len(XC), H), int)
    half0 = strs[0][2]
    for i in range(len(strs) - 1, -1, -1):               # far first
        blue, red, half = strs[i]
        u = (t - STAGGER * (len(strs) - 1 - i)) / TILT_T     # rear string first
        a = RISE * (half / half0) ** RISE_EXP * np.sin(np.pi * u) if 0 < u < 1 else 0.0
        offs = -np.round(a * XC / W).astype(int)          # right end up
        top = len(rr.RAMP) - 1
        if u < 0.5:                                       # blue until the apex
            rows, shade = blue, (lambda k: k)
        else:                                             # white at the apex, then down
            f_ = max(0.0, 1 - (u - 0.5) / 0.5)            # the red ramp: 1 at the apex .. 0 at rest
            rows = red
            shade = lambda k: RED + k + int(round((top - k) * f_))
        for s, o in enumerate(offs):
            for y, k in rows.items():
                k = shade(k)
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
                k = seg[s, y]
                img[y, a:b] = (rr.colour(k - RED, y & 1, f & 1) if k >= RED
                               else v7.colour(fv.RAMP[k], y & 1, f & 1))
        v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    v.close()
    print("wrote", path, len(strs), "strings", HOLD0 + n_anim + HOLD1, "frames")

if __name__ == "__main__":
    main(sys.argv[1])
