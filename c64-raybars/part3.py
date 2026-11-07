#!/usr/bin/env python3
"""PART 3: starts where part 2 ends (7 splits): the finished floor, the nearest bar
multicolour, the next red, alternating.

Wave shorthand:  <hand> <direction> pk <white|black> pal <palette>
  rh / lh      the bar tilts on its right / left end
  f2b / b2f    the wave runs front to back / back to front
  pk white     the bar turns white at the peak of its tilt (pk black: black, i.e. it
               vanishes against the background), then fades to the palette as it
               comes back down; before the peak it keeps the palette it had.

  3a  every other bar (the nearest, the third, ...):  rh f2b pk white pal blue
  3b  at once:  the bars that just changed:  lh b2f pk white pal red
                the other bars:              rh f2b pk black pal multicolor

    python3 part3.py out.mp4
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

def tokens(plans, static, tw):
    """SEGS x H tokens at frame tw.  plans[i]: None (the bar stays as static[i]) or a dict
    side, start, base, end, peak."""
    out = np.zeros((SEGS, H), int)
    for i in range(NS - 1, -1, -1):                              # far first
        y0, T = STR[i]
        pl = plans[i]
        if pl is None:
            for k in range(SEGS):
                for r in range(T):
                    tok = base_tok(static[i], T, r)
                    if tok and 0 <= y0 + r < H:
                        out[k, y0 + r] = tok
            continue
        u = tw - pl["start"]
        a = AMP * math.sin(math.pi * u / TILT) if 0 < u < TILT else 0.0
        uu = u / TILT
        f = 1.0 - (min(uu, 1.0) - 0.5) / 0.5 if uu >= 0.5 else 0.0
        for k in range(SEGS):
            c = (k + 0.5) / SEGS
            s = -int(round(a * c)) if pl["side"] == "R" else -int(round(a * (1 - c)))
            for r in range(T):
                tok = (base_tok(pl["base"], T, r) if uu < 0.5
                       else fade_tok(pl["end"], T, r, f, pl["peak"]))
                if tok and 0 <= y0 + s + r < H:
                    out[k, y0 + s + r] = tok
    return out

# the state part 2 ends in: even bars (the nearest first) multicolour, odd bars red
START = ["multi" if i % 2 == 0 else "red" for i in range(NS)]

def plans_3a():
    return [dict(side="R", start=i * STAG, base="multi", end="blue", peak="white") if i % 2 == 0 else None
            for i in range(NS)]

STATE_3A = ["blue" if i % 2 == 0 else "red" for i in range(NS)]

def plans_3b():
    out = []
    for i in range(NS):
        if i % 2 == 0:       # the bars that just changed: lh b2f pk white pal red
            out.append(dict(side="L", start=(NS - 1 - i) * STAG, base="blue", end="red", peak="white"))
        else:                # the others: rh f2b pk black pal multicolor
            out.append(dict(side="R", start=i * STAG, base="red", end="multi", peak="black"))
    return out

def main(path):
    Z = 3
    v = iv.Video(path, W * Z, H * Z)
    f = 0
    wave = (NS - 1) * STAG + TILT
    # (name, plans, static state of unmoved bars, lead-in, wave length, tail)
    seq = [("3a", plans_3a(), START, 30, wave, 20),
           ("3b", plans_3b(), STATE_3A, 0, wave, 90)]
    for name, plans, static, pre, length, post in seq:
        n = pre + length + post
        for t in range(n):
            seg = tokens(plans, static, t - pre)
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
    main(sys.argv[1])
