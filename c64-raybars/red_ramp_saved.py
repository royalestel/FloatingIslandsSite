#!/usr/bin/env python3
"""The saved red ramp: ramp_extra_sorted (the 26-swatch ramp with its tosses,
moves, stripes and 3-line swatch 7), as the red ramp for the animation.

Interface (what ghost_part2.py uses, drop-in for red_ramp25):
  N, WHITE, FLAT, RAMP_L (L*), Lstar, name(i)
  colour(i, y, f), ghost(i, y, f)   y = screen line, f = frame (global)

  * a line's parity (y & 1) and frame parity (f & 1) pick the flicker phase,
    as in the swatches;
  * 3-line swatch 7 is laid out on screen lines by y % 3;
  * swatches 2-4 move their idle-byte pattern one pixel right every frame
    (ROR by f % 8, rx.ROT_NUMS).
"""
import numpy as np
import ramp_extra_video as rx

ROWS = rx.build_rows(merged=True)
N = len(ROWS)
RAMP_L = np.array([float(ls) for _, ls, _ in ROWS])
Lstar = lambda y: np.where(y > 0.008856, 116 * np.cbrt(y) - 16, y * 903.3)
WHITE = N - 1

def _three(i):
    return getattr(ROWS[i][2], "three", False)

FLAT = [i for i in range(N) if not _three(i)
        and all(rx._c(ROWS[i][2], rp, p, 0)[1] == 0 for rp in (0, 1) for p in (0, 1))]

def _raw(i, y, f):
    return rx._c(ROWS[i][2], y & 1, f & 1, y % 3)

def colour(i, y, f):
    return _raw(i, y, f)[0]

def ghost(i, y, f):
    c, g = _raw(i, y, f)
    if g and (i + 1) in rx.ROT_NUMS:
        g = rx.ror(g, f % 8)
    return g

def name(i):
    return ROWS[i][0]
