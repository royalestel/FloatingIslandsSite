#!/usr/bin/env python3
"""Part 1's beginning (frames 0 .. T_STACK: the three bars sliding up, sliding past each other, the circle in
depth with its trips into the distance, the dimming, the settling into the stack) as a PROCEDURAL scene:
sine / smoothstep / reciprocal tables and 8-bit arithmetic, the way a real raster-bar routine does it, in
place of 16 KB of precalculated bar lists and 12 KB of bar arrays.  This module is the model for the 6502
code (part1p.s): every number is an integer exactly as the 6502 will compute it.

    python3 part1_proc.py            compares with the approved film (position / thickness differences)
"""
import math
import numpy as np
import part1 as p1

H = 200
P = p1.P
TURN = P["TURN"]                       # 240 frames per turn
T_ENTER, ENTER_LEN = P["T_ENTER"], P["ENTER_LEN"]
T_B0, T_B1 = P["T_B0"], P["T_B1"]
T_C0, T_C1 = P["T_C0"], P["T_C1"]
T_STACK = p1.T_STACK                   # 1400

# ---- tables (a 6502 gets these as .byte tables) -------------------------------------------------
SIN = [int(round(127 * math.sin(2 * math.pi * i / 256))) for i in range(256)]        # signed
def sin8(p): return SIN[p & 255]
def cos8(p): return SIN[(p + 64) & 255]
SM = [int(round(255 * (lambda u: u * u * (3 - 2 * u))(i / 127.0))) for i in range(128)]  # smoothstep 0..255, 128 steps
ZQ = 32                                                                              # distance unit: 1/32 m
KY = [0] + [min(255, int(round(110 * ZQ / z))) for z in range(1, 256)]                # lines per unit cos at distance z
TT = [0] + [max(1, min(63, int(round(2 * 200 * 0.12 * ZQ / z)))) for z in range(1, 256)]  # thickness at distance z
Z_EQ = int(round(P["Z_EQ"] * ZQ))                                                    # 54
AZQ = int(round(P["AZ"] * ZQ))                                                       # 38
# the circle's centre distance over time: keyframes (frame, metres) eased and interpolated in log distance
KEYS = [(640, P["ZC"]), (760, p1.REAR_8_LINES - P["AZ"]), (790, p1.REAR_8_LINES - P["AZ"]),
        (890, 1.6), (910, 1.6), (1000, P["ZC"])]
ZBSTEP = 8                                                                           # one table byte per 8 frames
def _zb(t):
    if t <= KEYS[0][0] or t >= KEYS[-1][0]:
        return P["ZC"]
    for (t0, z0), (t1, z1) in zip(KEYS, KEYS[1:]):
        if t < t1:
            u = (t - t0) / float(t1 - t0); x = u * u * (3 - 2 * u)
            return math.exp(math.log(z0) + (math.log(z1) - math.log(z0)) * x)
ZB = [int(round(_zb(t) * ZQ)) for t in range(KEYS[0][0], KEYS[-1][0] + ZBSTEP + 1, ZBSTEP)]   # 1/32 m
def zbase(t):
    if t <= KEYS[0][0] or t >= KEYS[-1][0]:
        return int(round(P["ZC"] * ZQ))
    i, f = divmod(t - KEYS[0][0], ZBSTEP)
    return ZB[i] + ((ZB[i + 1] - ZB[i]) * f) // ZBSTEP
# the three settled slots (screen line of each bar's centre in the stack) and which bar goes where
def _slots():
    th0 = 1.5 * math.pi + 2 * math.pi * T_C0 / TURN
    order = np.argsort(np.argsort([-P["AY"] * math.cos(th0 + 2 * math.pi * k / 3) for k in range(3)]))
    return [int(round(p1.sc.YC_WALL[int(j)])) for j in order]
SLOT = _slots()
PH0 = 192                                                                            # 270 degrees
PHK = [0, 85, 171]                                                                   # the bars' phase offsets
INC = 65536 // TURN                                                                  # phase step per frame (16-bit)

def lerp8(a, b, w):
    """a + (b - a) * w / 255, exact at w = 0 and w = 255 (w + w // 128 maps 255 to 256)."""
    return a + (((b - a) * (w + (w >> 7))) >> 8)

def smooth8(t, t0, n):
    """smoothstep 0..255 of (t - t0) / n, via the 128-entry table."""
    if t <= t0: return 0
    if t >= t0 + n: return 255
    return SM[((t - t0) * 127) // n]

def bars(t):
    """[(thickness, first line, order key)] of the three bars at frame t (far first)."""
    ph = (PH0 * 256 + t * INC) >> 8
    s = smooth8(t, T_B0, T_B1 - T_B0)
    e = smooth8(t, T_C0, T_C1 - 1 - T_C0)               # fully settled on the LAST frame: all three bars identical
    zb = zbase(t)
    out = []
    for k in range(3):
        pk = (ph + PHK[k]) & 255
        zc = zb + ((AZQ * sin8(pk)) >> 7)
        z = lerp8(Z_EQ, zc, s)
        yc = 100 - ((cos8(pk) * KY[z]) >> 7)
        z = lerp8(z, Z_EQ, e)
        yc = lerp8(yc, SLOT[k], e)
        rise = (260 * (255 - smooth8(t, T_ENTER[k], ENTER_LEN))) >> 8
        yc += rise
        z = max(1, min(255, z))
        T = TT[z]
        out.append((T, yc - T // 2, z * 256 - sin8(pk) * (255 - e) // 255 if False else z * 4 - (sin8(pk) >> 5)))
    out.sort(key=lambda b: -b[2])
    return [(T, y0) for T, y0, _ in out]

def dim_g(f):                                           # fade down / hold / back up: 8-bit levels
    return p1.dim(f)

def levels(T):
    n = (T + 1) // 2
    if n == 1:
        half = [1]
    else:
        step = (22 * 256) // (n - 1)
        half = [1 + ((m * step + 128) >> 8) for m in range(n)]
        half[-1] = 23
    return half + half[::-1][T % 2:]

def frame_buf(t, dimmed=True, with_par=False):
    """The line buffer (swatch index per line); with_par also gives each line's PARITY IN ITS BAR (row - bar
    top) & 1.  The swatches' colour pairs and ghost bytes are chosen by that, not by the absolute line, so a
    bar shows exactly two looks (frame parity) however it moves.  On the C64 this costs nothing: the bar's
    indices get +32 when its first line is odd, and the tables hold both parities."""
    buf = [0] * H
    par = [0] * H
    g = p1.dim(t) if dimmed else 1.0
    u = (1.0 - g) / (1.0 - p1.DIM[1][1]) if g < 1 else 0.0
    for T, y0 in bars(t):
        arr = levels(T)
        if g < 1.0:
            m = (T - 1) // 2 if T >= 8 else -9
            cen = set(range(((T - 1) // 2) - 1, ((T - 1) // 2) + 3)) if T >= 8 else set()
            arr2 = []
            for i, k in enumerate(arr):
                v = k * g
                if k >= 16: v = max(v, k * (1 - u) + (11 + k - 16 + (1 if i in cen else 0)) * u)
                arr2.append(max(1, int(round(v))))
            arr = arr2
        for i, k in enumerate(arr):
            if 0 <= y0 + i < H:
                buf[y0 + i] = k; par[y0 + i] = i & 1
    return (buf, par) if with_par else buf

if __name__ == "__main__":
    import part1_gen as gen
    worst = {"dy": 0, "dT": 0}
    rows = []
    for t in range(0, T_STACK, 7):
        a = bars(t); b = [(int(T), y0) for y0, T in p1.frame_list(t)]
        b = sorted(b, key=lambda x: x[1])
        # compare as sets, matched by centre line
        for (T, y0) in a:
            if not (0 <= y0 + T and y0 < H): continue
            best = min(b, key=lambda x: abs((x[1] + x[0] / 2.0) - (y0 + T / 2.0))) if b else None
            if best:
                worst["dy"] = max(worst["dy"], abs((best[1] + best[0] / 2.0) - (y0 + T / 2.0)))
                worst["dT"] = max(worst["dT"], abs(best[0] - T))
                rows.append(abs(best[0] - T))
    print("max centre-line diff", round(worst["dy"], 1), "lines; max thickness diff", worst["dT"],
          " mean thickness diff", round(float(np.mean(rows)), 2))
    print("table bytes: SIN 256, SM 128, KY 255, TT 255, ZB", len(ZB), "slots", SLOT)


def stack_buf(t):
    """Line buffer and in-bar parity for the data-driven part (frames >= T_STACK), from part1.frame_list."""
    buf, par = [0] * H, [0] * H
    for y0, T in p1.frame_list(t):
        for i, k in enumerate(p1.gp.PROF[T]):
            if k and 0 <= y0 + i < H:
                buf[y0 + i] = k; par[y0 + i] = i & 1
    return buf, par

def film_buf(t):
    return frame_buf(t, with_par=True) if t < T_STACK else stack_buf(t)
