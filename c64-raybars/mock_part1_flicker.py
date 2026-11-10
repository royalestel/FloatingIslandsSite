#!/usr/bin/env python3
"""MOCK (python only): part 1a-1b with three extra bars that appear at 16 s (frame 960, where the music gets loud).
They sit between the three circling bars (midpoints of each pair) and blink on/off three times (6 frames each) before they stay.
    python3 mock_part1_flicker.py out.mp4 [last_frame]"""
import os, sys
os.environ.setdefault("SPLITS", "6")
import part1 as p1

T0, N_BLINK = 960, 3                    # 16 s; three off/on blinks, one per two frames

def extra_visible(t):
    """off, on, off, on, off, on: every other frame, three times; then they stay"""
    u = t - T0
    if u < 0: return False
    if u < 2 * N_BLINK: return u % 2 == 1
    return True

_orig = p1.bars_all

def bars_all(t):
    """the three circling bars, plus three more with the SAME motion (slide / circle in depth) but a phase shifted by 1/3 and 2/3 of
    a turn, so they sit between the existing three"""
    bars = _orig(t)
    if t >= p1.T_STACK or not extra_visible(t):
        return bars
    import math
    sc = p1.sc
    th0 = sc.theta
    extra = []
    for shift in (math.pi / 3,):                      # one shift: its three bars sit at phases 1/3, 1/3+1/3 and 1/3+2/3 of the way round
        sc.theta = (lambda sh: (lambda x: th0(x) + sh))(shift)
        try:
            extra += sc.bars(t)[:3]
        finally:
            sc.theta = th0
    return bars + extra
p1.bars_all = bars_all

if __name__ == "__main__":
    out = sys.argv[1]
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    p1.main(out, 0, last)
