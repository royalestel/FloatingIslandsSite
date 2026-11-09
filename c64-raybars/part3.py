#!/usr/bin/env python3
"""PART 3: starts where part 2 ends (7 splits): the finished floor, the nearest bar
multicolour, the next red, alternating.

Wave shorthand:  [<hand>] <direction> pk <white|black> pal <palette>
  rh / lh      the bar tilts on its right / left end;  with no hand: the part of every
               bar inside the named raster-split column lifts straight up, as one piece
  f2b / b2f    the wave runs front to back / back to front (bar by bar)
  pk white     the piece turns white at the peak of its lift (pk black: black, so it
               vanishes against the background), then fades to the palette as it comes
               back down; before the peak it keeps the palette it had.

  (3a, 3b: the first two column waves -- every other split column f2b pk white pal blue, then
   b2f pk white pal red / f2b pk black pal multicolor -- are no longer in part 3; they are
   still here: python3 part3.py out.mp4 ab)
  Part 3 now begins on part 2's last frame (same floor, same flicker phase) and runs:
  3c  every other bar (the nearest first):        rh f2b pk white pal blue
  3d  the other bars:                             lh b2f pk white pal blue
  3e  at once, per column: even columns f2b pk white pal multicolor,
                           odd columns  b2f pk white pal red

    python3 part3.py out.mp4          # 3a, 3b
    python3 part3.py out.mp4 cde      # 3c, 3d, 3e (from the state 3b ends in)
    python3 part3.py out.mp4 all      # part 3: 3c, 3d, 3e (this is part3.mp4)
"""
import os, sys, math
os.environ.setdefault("SPLITS", "7")
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import ghost_part4 as g4

STR, NS, W, H, SEGS = g4.STR, g4.NS, g4.W, g4.H, g4.SEGS
RED, P25, TOPB, TOP_R, TOP25 = g4.RED, g4.P25, g4.TOPB, g4.TOP_R, g4.TOP25
PROF_R, PROF25, gp = g4.PROF_R, g4.PROF25, g4.gp
TILT, STAG, AMP = 32, 4, 28
F0 = 1895                                    # part 2's last frame number (1896 frames, 20-bar floor): same flicker phase

def base_tok(pal, T, r):
    """The palette's token for row r of a bar T thick (0 = black / not drawn)."""
    if pal == "blue":
        return gp.PROF[T][r]
    if pal == "red":
        kr = PROF_R[T][r]
        return RED + kr if kr else 0
    t = PROF25[T][r]
    return t                                            # P25 + index, or 0

def fade_tok(pal, T, r, f, peak):
    """Token at fade level f (1: the peak colour, 0: the palette's own colour)."""
    if pal == "blue":
        k = gp.PROF[T][r]
        if not k:
            return 0
        return k + int(round((TOPB - k) * f)) if peak == "white" else int(round(k * (1 - f)))
    if pal == "red":
        kr = PROF_R[T][r]
        if not kr:
            return 0
        return (RED + kr + int(round((TOP_R - kr) * f)) if peak == "white"
                else RED + int(round(kr * (1 - f))))
    t = PROF25[T][r]
    if not t:
        return 0
    pr = t - P25
    return (P25 + pr + int(round((TOP25 - pr) * f)) if peak == "white"
            else P25 + int(round(pr * (1 - f))))

LIFT = 16                                     # lines a column's piece rises at its peak

def tokens(spec, static, tw):
    """SEGS x H tokens at frame tw.  spec(i, k): None (bar i's piece in column k stays as
    static[i][k]) or a dict  kind ('lift': the piece rises straight, 'tilt': the bar tilts on
    side 'R' / 'L'), dir ('f2b' / 'b2f'), end (palette), peak ('white' / 'black')."""
    if isinstance(spec, list):                                   # one spec per column
        cols = spec
        spec = lambda i, k: dict(cols[k], kind="lift") if cols[k] else None
    out = np.zeros((SEGS, H), int)
    for i in range(NS - 1, -1, -1):                              # far first
        y0, T = STR[i]
        Tb = gp.BT(T, gp.edge_level(i), i)                      # this bar's own profile, as part 1's floor has it (far bars dimmer)
        for k in range(SEGS):
            sp = spec(i, k)
            pal = static[i][k]
            if sp is None:
                for r in range(T):
                    tok = base_tok(pal, Tb, r)
                    if tok and 0 <= y0 + r < H:
                        out[k, y0 + r] = tok
                continue
            start = i * STAG if sp["dir"] == "f2b" else (NS - 1 - i) * STAG
            u = tw - start
            if 0 < u < TILT:
                a = math.sin(math.pi * u / TILT)
                if sp["kind"] == "lift":
                    s = -int(round(LIFT * a))
                else:
                    c = (k + 0.5) / SEGS
                    s = -int(round(AMP * a * (c if sp["side"] == "R" else 1 - c)))
            else:
                s = 0
            uu = u / TILT
            f = 1.0 - (min(uu, 1.0) - 0.5) / 0.5 if uu >= 0.5 else 0.0
            for r in range(T):
                tok = base_tok(pal, Tb, r) if uu < 0.5 else fade_tok(sp["end"], Tb, r, f, sp["peak"])
                if tok and 0 <= y0 + s + r < H:
                    out[k, y0 + s + r] = tok
    return out

# the state part 2 ends in: even bars (the nearest first) multicolour, odd bars red
START = [["multi" if i % 2 == 0 else "red"] * SEGS for i in range(NS)]

COLS_3A = [dict(dir="f2b", end="blue", peak="white") if k % 2 == 0 else None for k in range(SEGS)]
STATE_3A = [["blue" if k % 2 == 0 else START[i][k] for k in range(SEGS)] for i in range(NS)]
COLS_3B = [dict(dir="b2f", end="red", peak="white") if k % 2 == 0 else
           dict(dir="f2b", end="multi", peak="black") for k in range(SEGS)]

STATE_3B = [["red" if k % 2 == 0 else "multi" for k in range(SEGS)] for i in range(NS)]

# 3c  every other bar (the nearest first):  rh f2b pk white pal blue
def SPEC_3C(i, k):
    return dict(kind="tilt", side="R", dir="f2b", end="blue", peak="white") if i % 2 == 0 else None
STATE_3C = [["blue" if i % 2 == 0 else START[i][k] for k in range(SEGS)] for i in range(NS)]   # 3c now starts from part 2's end
# 3d  the other bars:  lh b2f pk white pal blue
def SPEC_3D(i, k):
    return dict(kind="tilt", side="L", dir="b2f", end="blue", peak="white") if i % 2 == 1 else None
STATE_3D = [["blue"] * SEGS for i in range(NS)]
# 3e  at once, per column:  even columns f2b pk white pal multicolor, odd columns b2f pk white pal red
COLS_3E = [dict(dir="f2b", end="multi", peak="white") if k % 2 == 0 else
           dict(dir="b2f", end="red", peak="white") for k in range(SEGS)]

def main(path, which="ab"):
    Z = 3
    v = iv.Video(path, W * Z, H * Z)
    f = F0 if which == "all" else 0               # part 3 goes on from part 2's last frame
    wave = (NS - 1) * STAG + TILT
    # (name, plans, static state of unmoved bars, lead-in, wave length, tail)
    seq_ab = [("3a", COLS_3A, START, 30, wave, 20),
              ("3b", COLS_3B, STATE_3A, 0, wave, 90)]
    seq_cde = [("3c", SPEC_3C, START, 30, wave, 20),
               ("3d", SPEC_3D, STATE_3C, 0, wave, 20),
               ("3e", COLS_3E, STATE_3D, 0, wave, 90)]
    seq_all = seq_cde                                          # part 3: 3c, 3d, 3e from part 2's end
    seq = {"ab": seq_ab, "cde": seq_cde, "all": seq_all}[which]
    for name, cols, static, pre, length, post in seq:
        n = pre + length + post
        for t in range(n):
            seg = tokens(cols, static, t - pre)
            img = []
            for y in range(H):
                toks = [int(seg[k, y]) for k in range(SEGS)]
                line, _ = g4.fix_line(toks, y, f)
                img.append(g4.draw(line, y, f))
            v.add(lv.crt_look(fb.C64RGB[np.array(img)].astype(np.uint8), Z))
            f += 1
        print(name, n, "frames")
    v.close()
    print("wrote", path, f, "frames")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "ab")
