#!/usr/bin/env python3
"""Part 1 as the C64 draws it.  Frames 0 .. T_STACK-1 (the three bars sliding up, sliding past each other, the
circle in depth with its trips into the distance, the dimming, the settling into the stack) are PROCEDURAL:
sine / smoothstep tables and 8-bit arithmetic, as in a real raster-bar routine, in place of 16 KB of
precalculated bar lists and 12 KB of bar arrays.  Frames T_STACK .. (the extra bars, the rotation into the
floor) are read from a stream (part1_gen.py).  This module is the bit-exact SPEC of part1p.s: every number is
an integer computed the way the 6502 computes it, and the line buffer it returns holds what the program puts
in LINEBUF: swatch index (1..23, 0 = black) + 32 if the bar's first line is odd.  The swatch tables hold both
line parities (the +32 block has them swapped), so a swatch's colour pair and ghost byte follow the row's
parity INSIDE its bar: a bar has exactly two looks (frame parity), however it moves.

    python3 part1_proc.py            compares with the approved film (position / thickness differences)
"""
import math
import numpy as np
import part1 as p1

H = 200
P = p1.P
TURN = P["TURN"]
T_ENTER, ENTER_LEN = P["T_ENTER"], P["ENTER_LEN"]
T_B0, T_B1 = P["T_B0"], P["T_B1"]
T_C0, T_C1 = P["T_C0"], P["T_C1"]
T_STACK = p1.T_STACK                   # 1400

sm = lambda u: u * u * (3 - 2 * u)
# ---- tables (the 6502 gets them as .byte / .word tables) ----------------------------------------
SIN = [int(round(127 * math.sin(2 * math.pi * i / 256))) for i in range(256)]               # signed
def cos8(p): return SIN[(p + 64) & 255]
ZQ = 64                                                                                     # distance unit: 1/64 m (z is 9 bits)
ZMAX = 511
ZMIN = 16                                                                                    # 0.25 m (the circle comes to 0.4 m)
KY = [0] + [min(511, int(round(110 * ZQ / z))) for z in range(1, ZMAX + 1)]                       # lines per unit cos (9 bits)
TT = [0] + [max(1, min(63, int(round(2 * 200 * 0.12 * ZQ / z)))) for z in range(1, ZMAX + 1)]     # thickness
Z_EQ = int(round(P["Z_EQ"] * ZQ))                                                           # 54
AZQ = int(round(P["AZ"] * ZQ))                                                              # 38
AZS = [(AZQ * SIN[i]) >> 7 for i in range(256)]                                              # depth of the circle
NB, NE, NC = T_B1 - T_B0, ENTER_LEN, T_C1 - 1 - T_C0                                        # 120, 90, 129
SB = [int(round(255 * sm(d / NB))) for d in range(NB)]                                       # smoothstep by frame
SE = [int(round(255 * sm(d / NE))) for d in range(NE)]
SC = [int(round(255 * sm(d / NC))) for d in range(NC)]
RISE = [(260 * (255 - v)) >> 8 for v in SE]                                                  # a rising bar's offset
KEYS = [(640, P["ZC"]), (760, p1.REAR_8_LINES - P["AZ"]), (790, p1.REAR_8_LINES - P["AZ"]),
        (890, 1.6), (910, 1.6), (1000, P["ZC"])]
def _zb(t):
    for (t0, z0), (t1, z1) in zip(KEYS, KEYS[1:]):
        if t < t1:
            x = sm((t - t0) / float(t1 - t0))
            return math.exp(math.log(z0) + (math.log(z1) - math.log(z0)) * x)
ZB0, ZB1 = KEYS[0][0], KEYS[-1][0]
ZBF = [int(round(_zb(t) * ZQ)) for t in range(ZB0, ZB1)]                                     # per frame, 1/32 m
ZC0 = int(round(P["ZC"] * ZQ))                                                              # 64
def _slots():
    th0 = 1.5 * math.pi + 2 * math.pi * T_C0 / TURN
    order = np.argsort(np.argsort([-P["AY"] * math.cos(th0 + 2 * math.pi * k / 3) for k in range(3)]))
    return [int(round(p1.sc.YC_WALL[int(j)])) for j in order]
SLOT = _slots()
PH0 = 192 << 8                                                                               # 270 degrees (16-bit)
PHK = [0, 85, 171]
INC = 65536 // TURN
# the dimming: index 0..31 by frame (fade down 1000-1100, hold, back up 1180-1240) and the swatch remap
DIM0 = p1.DIM[0][0]; DIMN = p1.DIM[-1][0] - DIM0
def _dx(f):
    for (t0, a), (t1, b) in zip(p1.DIM, p1.DIM[1:]):
        if f < t1:
            x = sm((f - t0) / float(t1 - t0))
            return (1 - (a + (b - a) * x)) / (1 - p1.DIM[1][1])
    return 0.0
DX = [int(round(31 * _dx(f))) for f in range(DIM0, DIM0 + DIMN)]                             # 240 values 0..31
def _remap(i, c, k):
    if k == 0: return 0
    x = i / 31.0; g = 1 - (1 - p1.DIM[1][1]) * x; u = x
    v = k * g
    if k >= 16: v = max(v, k * (1 - u) + (11 + k - 16 + c) * u)
    return max(1, int(round(v)))
DIMT = [[[_remap(i, c, k) for k in range(32)] for c in range(2)] for i in range(32)]

def smul(a, b):
    """signed a times unsigned b >> 8 or >> 7 callers use: sign-magnitude product."""
    m = abs(a) * b
    return m if a >= 0 else -m
def lerp8(a, b, w):
    """a + (b - a) * w / 255 by sign-magnitude shift-add; exact at w = 0 and 255."""
    if w == 0: return a
    if w == 255: return b
    d = b - a
    m = (abs(d) * (w + (w >> 7))) >> 8
    return a + (m if d >= 0 else -m)

def bars(t):
    """[(thickness, first line)] of the three bars at frame t, far first (frames < T_STACK)."""
    ph = ((PH0 + t * INC) >> 8) & 255
    d = t - T_B0; s = 0 if d <= 0 else (255 if d >= NB else SB[d])
    d = t - T_C0; e = 0 if d <= 0 else (255 if d >= NC else SC[d])
    zb = ZBF[t - ZB0] if ZB0 <= t < ZB1 else ZC0
    out = []
    for k in range(3):
        pk = (ph + PHK[k]) & 255
        zc = zb + AZS[pk]
        z = lerp8(Z_EQ, zc, s)
        z = max(ZMIN, min(ZMAX, z))
        c = cos8(pk)
        off = (abs(c) * KY[z]) >> 7
        yc = 100 - (off if c >= 0 else -off)
        z = lerp8(z, Z_EQ, e)
        yc = lerp8(yc, SLOT[k], e)
        d = t - T_ENTER[k]
        yc += 260 if d <= 0 else (0 if d >= NE else RISE[d])
        z = max(ZMIN, min(ZMAX, z))
        T = TT[z]
        out.append((T, yc - (T >> 1), z * 4 - (SIN[pk] >> 5)))          # draw key: far first, the far side of the circle behind
    out.sort(key=lambda b: -b[2])
    return [(T, y0) for T, y0, _ in out]

def half_levels(n):
    """Levels of the rising half of a bar with n = ceil(T/2) rows: 1 .. 23 spread evenly."""
    if n == 1: return [1]
    step = (22 * 256) // (n - 1)
    h = [1 + ((m * step + 128) >> 8) for m in range(n)]
    h[-1] = 23
    return h

def _full(T):
    n = (T + 1) // 2
    hl = half_levels(n)
    mid = (T - 1) // 2
    row = []
    for r in range(T):
        k = hl[r] if r < n else hl[T - 1 - r]
        if T >= 8 and mid - 1 <= r <= mid + 2:
            k |= 32                                   # the middle 4 rows: the dimming keeps them lighter
        row.append(k)
    return row
FULL = [[]] + [_full(T) for T in range(1, 64)]         # row table of every thickness: level | 32 for the middle rows

def frame_buf(t):
    """LINEBUF at frame t < T_STACK: 200 values, swatch + 32 * (first line odd), dimming applied."""
    buf = [0] * H
    di = DX[t - DIM0] if DIM0 <= t < DIM0 + DIMN else 0
    for T, y0 in bars(t):
        if y0 >= H or y0 + T <= 0:
            continue
        for r, f in enumerate(FULL[T]):
            y = y0 + r
            if 0 <= y < H:
                buf[y] = DIMT[di][f >> 5][f & 31] + 32 * (y0 & 1)
    return buf

def stack_buf(t):
    """LINEBUF at frame t >= T_STACK from part1.frame_list (the data-driven part), same index scheme."""
    buf = [0] * H
    for y0, T in p1.frame_list(t):
        for i, k in enumerate(p1.gp.PROF[T]):
            if k and 0 <= y0 + i < H:
                buf[y0 + i] = k + 32 * (y0 & 1)
    return buf

def film_buf(t):
    return frame_buf(t) if t < T_STACK else stack_buf(t)

def parity_of(buf):
    """(level, parity inside the bar) per line from a LINEBUF: the video's draw() takes these."""
    return [v & 31 for v in buf], [((v >> 5) ^ y) & 1 for y, v in enumerate(buf)]

if __name__ == "__main__":
    worst = {"dy": 0, "dT": 0}; rows = []
    for t in range(0, T_STACK, 3):
        a = bars(t); b = [(int(T), y0) for y0, T in p1.frame_list(t)]
        for (T, y0) in a:
            if not (0 <= y0 + T and y0 < H): continue
            best = min(b, key=lambda x: abs((x[1] + x[0] / 2.0) - (y0 + T / 2.0))) if b else None
            if best:
                worst["dy"] = max(worst["dy"], abs((best[1] + best[0] / 2.0) - (y0 + T / 2.0)))
                worst["dT"] = max(worst["dT"], abs(best[0] - T)); rows.append(abs(best[0] - T))
    print("max centre-line diff", round(worst["dy"], 1), "lines; mean thickness diff", round(float(np.mean(rows)), 2))
    print("last frame:", bars(T_STACK - 1))
    tb = 256 + len(SB) + len(SE) + len(SC) + 2 * len(RISE) + len(ZBF) + 256 + 3 * 512 + len(DX) + 32 * 2 * 32
    print("table bytes", tb)
