#!/usr/bin/env python3
"""Part 2 of the film as one preview: the tilt waves anim1..anim4 on the finished
floor, with raster splits (6 segments a line) and the v10 ramp's ghost-byte
swatches under the rule of ghost_preview.py: a split line keeps ghost swatches
only if all its segments agree on the idle byte; where a split moves across a
ghost-byte row the ghost swatches of that line become the nearest flat swatch.

  anim1  first tilt (40-frame tilt, near strings tilt most), near strings first
  anim2  the wave into the distance (16-frame tilt, rise ~ thickness^0.3)
  anim3  every string tilts the same 28 lines, from the rear string, half speed
  anim4  anim3: blue strings flash white at their apex and settle red (red ramp:
         flat swatches only; the blue part may use ghost swatches)

Each has a second of stillness before and after.  320 px lines (the idle byte only
shows in the display window), CRT look, 60 fps.

    python3 ghost_part2.py out.mp4
"""
import sys, math
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import preview_v10 as v10
import red_ramp as rr
import ghost_preview as gp

LAD, FLAT, STR, NS = gp.LAD, gp.FLAT, gp.STR, gp.NS
W, H, SEGS, EDGES = gp.W, gp.H, gp.SEGS, gp.EDGES
RED = 100                                           # token >= RED: red ramp index + RED
HOLD = 60

def _profile_red(T):
    d = 2 * gp.F * gp.R / T
    out = []
    for i in range(T):
        r = (i + (np.arange(8) + 0.5) / 8) * 2 / T - 1
        lit = sum(gp.gc.row_v3(d, v) for v in r) / 8
        out.append(int(np.argmin(np.abs(rr.Lstar(np.array(lit)) - rr.RAMP_L))))
    return out
PROF_R = {T: _profile_red(T) for T in range(1, gp.TMAX + 1)}
TOP_R = len(rr.RAMP) - 1                            # white in the red ramp

def colour(tok, y, f):
    return v10.colour(LAD[tok], y & 1, f & 1) if tok < RED else rr.colour(tok - RED, y & 1, f & 1)

def ghost(tok, y, f):
    return v10.ghost(LAD[tok], y & 1, f & 1) if tok < RED else 0

def light(tok):
    return gp.RAMP_L[tok] if tok < RED else rr.RAMP_L[tok - RED]

def is_black(tok):
    return tok == 0 or tok == RED

ANIMS = [
    dict(name="anim1", TILT=40, STAG=2, amp=lambda i, T0, T: 0.8 * T, near_first=True, red=False),
    dict(name="anim2", TILT=16, STAG=2, amp=lambda i, T0, T: 28 * (T / T0) ** 0.3, near_first=True, red=False),
    dict(name="anim3", TILT=32, STAG=4, amp=lambda i, T0, T: 28, near_first=False, red=False),
    dict(name="anim4", TILT=32, STAG=4, amp=lambda i, T0, T: 28, near_first=False, red=True),
]

def segments(A, tw):
    T0 = STR[0][1]
    out = np.zeros((SEGS, H), int)
    for i in range(NS - 1, -1, -1):                           # far first
        y0, T = STR[i]
        us = i * A["STAG"] if A["near_first"] else (NS - 1 - i) * A["STAG"]
        u = tw - us
        moving = 0 < u < A["TILT"]
        a = A["amp"](i, T0, T) * math.sin(math.pi * u / A["TILT"]) if moving else 0.0
        uu = u / A["TILT"]
        for k in range(SEGS):
            s = -int(round(a * (k + 0.5) / SEGS)) if moving else 0
            for r in range(T):
                if A["red"] and uu >= 0.5:                    # white at the apex, down the red ramp
                    kr = PROF_R[T][r]
                    if not kr:
                        continue
                    f_ = max(0.0, 1 - (uu - 0.5) / 0.5)
                    tok = RED + kr + int(round((TOP_R - kr) * f_))
                else:
                    tok = gp.PROF[T][r]
                    if not tok:
                        continue
                if 0 <= y0 + s + r < H:
                    out[k, y0 + s + r] = tok
    return out

def fix_line(toks, y, f):
    """Same rule as ghost_preview.fix_line, for tokens of either ramp."""
    gb = {ghost(t, y, f) for t in toks if not is_black(t)}
    if len(gb) <= 1:
        return toks, False
    out = []
    for t in toks:
        if not is_black(t) and ghost(t, y, f):
            t = min(FLAT, key=lambda j: abs(gp.RAMP_L[j] - light(t)))
        out.append(t)
    return out, True

def draw(toks, y, f):
    row = np.zeros(W, int)
    g = 0
    for s in range(SEGS):
        row[EDGES[s]:EDGES[s + 1]] = colour(toks[s], y, f)
        if not is_black(toks[s]):
            g = ghost(toks[s], y, f) or g
    if g:
        x = np.arange(W)
        row[((g >> (7 - x % 8)) & 1) == 1] = 0
    return row

def main(path):
    Z = 3
    v = iv.Video(path, W * Z, H * Z)
    f = 0
    for A in ANIMS:
        n = HOLD + (NS - 1) * A["STAG"] + A["TILT"] + HOLD
        fixed = total = 0
        for t in range(n):
            seg = segments(A, t - HOLD)
            img = []
            for y in range(H):
                toks = [int(seg[k, y]) for k in range(SEGS)]
                line, ch = fix_line(toks, y, f)
                fixed += ch
                total += any(ghost(x, y, f) for x in toks if not is_black(x))
                img.append(draw(line, y, f))
            v.add(lv.crt_look(fb.C64RGB[np.array(img)].astype(np.uint8), Z))
            f += 1
        print(f"{A['name']}: {n} frames, ghost swatches replaced on {fixed} of {total} ghost lines")
    v.close()
    print("wrote", path, f, "frames")

if __name__ == "__main__":
    main(sys.argv[1])
