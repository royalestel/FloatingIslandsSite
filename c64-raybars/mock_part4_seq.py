#!/usr/bin/env python3
"""MOCK (no C64 code): part 4, new motion model.
  1. a gradual run-up: every 10 frames, in each column, one more bar (chosen at random) starts moving with its own random speed and swing; the more bars move, the faster a random subset of them goes.
  2. then the ORIGINAL matching and slowdown (matches accelerate, groups follow one bar, the motion eases out after the last match).
  3. the nearest bar sweeps up and off (unchanged).
  Nothing rises above visible line 50.    python3 mock_part4_seq.py [out.mp4]"""
import os, sys, math, random
os.environ["SPLITS"] = "6"
import numpy as np
import part4m as m
fb, iv, lv, p3, g4 = m.fb, m.iv, m.lv, m.p3, m.g4
STR, NS, H, SEGS, YC = m.STR, m.NS, m.H, m.SEGS, m.YC
smooth = m.smooth
rng = random.Random(11)
CAPY, FLOORY = 50.0, 185.0                 # the C64 draws rows 0..184 (the floor ends at 184): nothing goes below
EASE, SETTLE, T_UP, T_DOWN = 20, 90, 120, 90      # the original values
RAMP = 40                                                  # a bar's swing grows in over 40 frames

# ---- when bars start moving: every frame one more bar per column ----
T_START = 30
start = {}
for k in range(SEGS):
    order = list(range(NS)); rng.shuffle(order)
    for n, i in enumerate(order):
        start[i, k] = T_START + n * 10                        # gradual: one more bar per column every 10 frames
T_MOVING = T_START + NS * 10 + RAMP                            # all bars moving at full swing
T_ALIGN = T_MOVING + 60                                   # the matches follow soon after everything is moving
# ---- the matches ----
pairs = [(i, k) for i in range(NS) for k in range(SEGS - 1)]
rng.shuffle(pairs)
match_t, tt = [], float(T_ALIGN)
for j in range(len(pairs)):
    match_t.append(tt); tt += max(0.4, 20 * 0.95 ** j)     # the original match pace
T_LAST = match_t[-1]
T_SETTLE0 = int(T_LAST) + EASE + 5
T_SWEEP0 = T_SETTLE0 + SETTLE
T_END = T_SWEEP0 + T_UP + T_DOWN + 60

# ---- per-piece motion: random speed (period) and random swing ----
om = {}; amp = {}; ph = {}; ph3 = {}; boost = {}; cen = {}
for key in start:
    om[key] = 2 * math.pi / rng.uniform(45, 230) * rng.choice([-1, 1])
    # a swing that fits the screen: centre c and amplitude A such that the whole sine stays between line 50 and the bottom
    # (with the depth wobble allowed for), so a bar never sits at a limit or leaves the screen; it is always moving
    Tm = STR[key[0]][1] * 1.4
    lo, hi = CAPY + Tm / 2.0 + 1, FLOORY - Tm / 2.0 - 1
    c = rng.uniform(lo + 14, hi - 14)
    amp[key] = rng.uniform(0.5, 1.0) * min(c - lo, hi - c)
    if key[0] == 0:                                   # the nearest bars: swing from 76 lines above rest (top line ~96) down to the bottom
        c = YC[0] - 38.0                          # nearest bars: from rest (bottom at row 184) up 76 lines
        amp[key] = 38.0
    cen[key] = c
    ph[key] = rng.uniform(0, 2 * math.pi)
    ph3[key] = rng.uniform(0, 2 * math.pi)
    boost[key] = rng.random() ** 2                          # a random subset speeds up the most
group = {i: list(range(SEGS)) for i in range(NS)}
events = {key: [] for key in start}                       # (t0, palette)
hist = {key: [] for key in start}                         # (t_change, rep column)
speed_changes = []                                        # (t, [(i,k)...], factor-owner pair)
for n, (i, k) in enumerate(pairs):
    tm = match_t[n]
    ra, rb = group[i][k], group[i][k + 1]
    members = [kk for kk in range(SEGS) if group[i][kk] in (ra, rb)]
    speed_changes.append((tm, i, k, members))
    for kk in range(SEGS):
        if group[i][kk] == rb:
            group[i][kk] = ra; hist[i, kk].append((tm, ra))
    events[i, k].append((tm, "blue")); events[i, k + 1].append((tm, "blue"))
# the random colour flashes (3 a second) until the matching starts
t = 10
while t < T_ALIGN:
    key = (rng.randrange(NS), rng.randrange(SEGS))
    events[key].append((t, rng.choice(["red", "multi"])))
    t += 20
for key in events: events[key].sort()
PAL0 = ["multi" if k % 2 == 0 else "red" for k in range(SEGS)]
FL = 40

def palette(i, k, t):
    base, flash = PAL0[k], None
    for t0, end in events[i, k]:
        if t >= t0 + FL: base = end
        elif t >= t0: flash = (end, 1.0 - (t - t0) / FL); break
    return base, flash

# ---- simulate the phases frame by frame (speed changes at the matches) ----
def cap(y, T):
    lo, hi = CAPY + T / 2.0, FLOORY - T / 2.0
    for sgn, lim in ((1, lo), (-1, hi)):
        d = sgn * (y - lim)
        if d < 8.0: y = lim + sgn * 8.0 * math.exp((d - 8.0) / 8.0)
    return y

own = np.zeros((T_END + 1, NS, SEGS)); thick = np.zeros((T_END + 1, NS, SEGS))
sc = sorted(speed_changes); si = 0
phase = dict(ph); phase3 = dict(ph3)
for t in range(T_END + 1):
    while si < len(sc) and sc[si][0] <= t:
        _, i, k, members = sc[si]; si += 1
        pass                                                         # (original: no speed change at a match)
    st = 1.0 - smooth((t - T_SETTLE0) / SETTLE)
    frac = sum(1 for key in start if t >= start[key]) / float(len(start))     # how many bars move so far
    for (i, k) in start:
        mult = 1.0 + 3.0 * boost[i, k] * frac
        phase[i, k] += om[i, k] * mult; phase3[i, k] += om[i, k] * mult * 0.8
        a = smooth((t - start[i, k]) / RAMP) * st
        rho = 1.0                                       # no depth wobble: bars keep their starting thickness
        T = STR[i][1] / max(rho, 0.35)
        own[t, i, k] = cap(YC[i] + (cen[i, k] - YC[i]) * a + amp[i, k] * a * math.sin(phase[i, k]), T) if a > 1e-4 else YC[i]
        thick[t, i, k] = T if a > 1e-4 else STR[i][1]

def pos(i, k, t):
    y, T = own[t, i, k], thick[t, i, k]
    for tc, rep in hist[i, k]:
        if t < tc: break
        w = smooth((t - tc) / EASE)
        y = y + (own[t, i, rep] - y) * w; T = T + (thick[t, i, rep] - T) * w
    return y, T

def tokens(t):
    out = np.zeros((SEGS, H), int)
    sweeping = t >= T_SWEEP0
    if sweeping:
        u = t - T_SWEEP0; top = STR[0][1] / 2.0
        if u < T_UP: yc0 = YC[0] + (top - YC[0]) * smooth(u / T_UP)
        else:
            v = (u - T_UP) / T_DOWN; yc0 = top + (H + STR[0][1] / 2.0 + 2 - top) * v * v
    for k in range(SEGS):
        items = []
        for i in range(NS):
            if sweeping:
                y, T = YC[i], float(STR[i][1])
                if i == 0: y = yc0
                elif T_UP >= u and yc0 - STR[0][1] / 2.0 <= YC[i] or u > T_UP: continue
            else:
                y, T = pos(i, k, t)
            items.append((T, y, i))
        for T, y, i in sorted(items, key=lambda a: a[0]):
            Tn = max(1, min(m.TMAX, int(round(T))))
            Tn = p3.gp.BT(Tn, p3.gp.edge_level(i), i)
            y0 = int(round(y - Tn / 2.0))
            base, flash = palette(i, k, t)
            for r in range(Tn):
                tok = p3.fade_tok(flash[0], Tn, r, flash[1], "white") if flash else p3.base_tok(base, Tn, r)
                if tok and 0 <= y0 + r < H: out[k, y0 + r] = tok
    return out

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mock_part4_seq.mp4"
    print("frames", T_END, "all moving at", T_MOVING, "matches", int(T_ALIGN), "-", int(T_LAST), flush=True)
    Z = 3
    v = iv.Video(out, m.W * Z, H * Z)
    for f in range(T_END):
        seg = tokens(f - f % 2 if os.environ.get("HOLD2") else f); img = []      # HOLD2: the picture only changes every other frame (the flicker still uses f)
        for y in range(H):
            line, _ = g4.fix_line([int(seg[k, y]) for k in range(SEGS)], y, f)
            img.append(g4.draw(line, y, f))
        v.add(lv.crt_look(fb.C64RGB[np.array(img)].astype(np.uint8), Z))
    v.close(); print("wrote", out)
