#!/usr/bin/env python3
"""PART 4 (7 splits).  Starts where part 3 ends: even split columns multicolour, odd red.

  A  every split column slides up and down on the screen (each at its own pace); 6 times a
     second at first (easing to 3), one bar element (the piece of a bar inside a column) flashes white and fades to
     one of the 3 palettes (blue / red / multicolour).
  B  after a few seconds the bars of each column, independently, start moving in circles in
     depth (the bars follow each other round); the colour changes go on.  From here the
     movement slowly gets crazy: everything speeds up, the slides and circles grow, and more
     and more random bar pieces travel all the way up and down the screen.
  C  3 s later every flash ends in blue.
  D  then the columns start to line up: at 3 matches a second a bar element in one column
     joins the element of the same bar in the next column over (they flash and turn blue);
     the matches speed up until every bar is one piece in all columns, all blue; the motion
     eases to rest.
  E  the nearest bar moves up across the screen, erasing the other bars as it passes, then
     down and off the bottom.

    python3 part4.py out.mp4
"""
import os, sys, math, random
os.environ.setdefault("SPLITS", "7")
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import part3 as p3

g4 = p3.g4
STR, NS, W, H, SEGS = p3.STR, p3.NS, p3.W, p3.H, p3.SEGS
TMAX = g4.gp.TMAX
rng = random.Random(4)

# ---- timeline (frames) ----------------------------------------------------------
FL = 40                       # a flash: white, then fading to its palette
FLASH_EVERY = 20              # 3 a second
T_CIRC = 240                  # the columns start moving in circles (amplitude ramps over 120)
T_BLUE = T_CIRC + 180         # every flash now ends blue
T_ALIGN = T_BLUE + 90         # the matches start
EASE = 20                     # frames a matched element takes to join its neighbour
SETTLE = 90                   # motion eases out after the last match
T_UP, T_DOWN = 120, 90        # the nearest bar's trip up, and down
SLIDE_AMP, CIRC_Y, CIRC_Z = 22.0, 14.0, 0.30

smooth = lambda x: (lambda u: u * u * (3 - 2 * u))(min(max(x, 0.0), 1.0))
PERIOD = [210, 270, 180, 300, 240, 330, 195]            # each column's slide period
OMEGA = [2 * math.pi / p for p in (150, 190, 130, 220, 170, 240, 140)]   # circling speeds
YC = [y0 + T / 2 for y0, T in STR]

# ---- when what happens ----------------------------------------------------------------
pairs = [(i, k) for i in range(NS) for k in range(SEGS - 1)]
rng.shuffle(pairs)
match_t, tt = [], float(T_ALIGN)
for j in range(len(pairs)):
    match_t.append(tt)
    tt += max(0.4, 20 * 0.95 ** j)
T_LAST = match_t[-1]
T_SETTLE0 = int(T_LAST) + EASE + 5
T_SWEEP0 = T_SETTLE0 + SETTLE
T_END = T_SWEEP0 + T_UP + T_DOWN + 60

PAL0 = ["multi" if k % 2 == 0 else "red" for k in range(SEGS)]     # where part 3 ends
events = {(i, k): [] for i in range(NS) for k in range(SEGS)}      # (t0, palette)
hist = {(i, k): [] for i in range(NS) for k in range(SEGS)}        # (t_change, rep column)

t = FLASH_EVERY // 2
while t < T_ALIGN:                                                  # the random flashes
    i, k = rng.randrange(NS), rng.randrange(SEGS)
    events[i, k].append((t, "blue" if t >= T_BLUE else rng.choice(["blue", "red", "multi"])))
    # twice as fast at the beginning (6 a second), easing to 3 a second by the time the circles start
    t += FLASH_EVERY / 2.0 * (1.0 + smooth(t / float(T_CIRC)))
    t = int(round(t))
group = {i: list(range(SEGS)) for i in range(NS)}                   # rep column of each column
for n, (i, k) in enumerate(pairs):                                  # the matches
    tm = match_t[n]
    ra = group[i][k]
    rb = group[i][k + 1]
    for kk in range(SEGS):
        if group[i][kk] == rb:
            group[i][kk] = ra
            hist[i, kk].append((tm, ra))
    events[i, k].append((tm, "blue"))
    events[i, k + 1].append((tm, "blue"))
for key in events:
    events[key].sort()

# ---- positions ------------------------------------------------------------------------------
def settle_at(t):
    return 1.0 - smooth((t - T_SETTLE0) / SETTLE)

def chaos(t):
    """0 until the circles start, 1 at the last match: how crazy the middle section is."""
    return smooth((t - T_CIRC) / float(T_LAST - T_CIRC))

def amps(t):
    st = settle_at(t)
    return min(1.0, t / 60.0) * st, smooth((t - T_CIRC) / 120.0) * st

# phases that speed up with the chaos: slide phase and circle phase of each column
PH_SLIDE, PH_CIRC = [], []
for k in range(SEGS):
    a_, b_, ps, pc = 0.0, 0.0, [], []
    for t_ in range(T_END + 1):
        ps.append(a_)
        pc.append(b_)
        a_ += 2 * math.pi / PERIOD[k] * (1 + 1.2 * chaos(t_))
        b_ += OMEGA[k] * (1 + 1.5 * chaos(t_))
    PH_SLIDE.append(ps)
    PH_CIRC.append(pc)

# random pieces that travel all the way up and down the screen: more and more of them
excursions = {(i, k): [] for i in range(NS) for k in range(SEGS)}      # (start, duration)
# The trips ramp up (slowly at first), then about 50 pieces are on a trip at once for 2.5 s
# (3 trips a frame start at 37 a second, each lasts 50-110 frames), then it tapers as the
# columns start to line up.
P0, P1, RATE = 690, 840, 37.5                                           # plateau 690-840 (2.5 s)
def trips_per_second(t_):
    if t_ < P0:
        return 0.5 + (RATE - 0.5) * ((t_ - T_CIRC) / float(P0 - T_CIRC)) ** 2
    if t_ <= P1:
        return RATE
    return 0.5 + (RATE - 0.5) * (1.0 - smooth((t_ - P1) / float(T_LAST - P1)))
acc = 0.0
for t_ in range(T_CIRC, int(T_LAST) + 1):
    acc += trips_per_second(t_) / 60.0                                   # steady, not random, spacing
    while acc >= 1.0:
        acc -= 1.0
        excursions[rng.randrange(NS), rng.randrange(SEGS)].append((t_, rng.randint(50, 110)))

def excursion(k, i, t):
    """Vertical offset of the piece from its random trip: up to the top, then to the bottom, home."""
    dy = 0.0
    for t0, d in excursions[i, k]:
        if t0 <= t < t0 + d:
            u = (t - t0) / d
            if u < 0.5:
                dy += -(YC[i] + 12.0) * math.sin(2 * math.pi * u)             # up, off the top, back
            else:
                dy += (H - YC[i] + 12.0) * -math.sin(2 * math.pi * u)         # down, off the bottom, back
    return dy

def traj(k, i, t):
    """(centre line, thickness) of bar i in column k's own motion."""
    sa, ca = amps(t)
    ch = chaos(t)
    slide = SLIDE_AMP * (1 + 1.7 * ch) * sa * math.sin(PH_SLIDE[k][t] + 0.8 * k)
    th = PH_CIRC[k][t] + 0.22 * i + 1.3 * k
    rho = 1.0 + CIRC_Z * (1 + 0.8 * ch) * ca * math.sin(th)
    exc = excursion(k, i, t) * settle_at(t) if t >= T_CIRC else 0.0
    return (YC[i] + slide - CIRC_Y * (1 + 1.5 * ch) * ca * math.cos(th) + exc,
            STR[i][1] / max(rho, 0.35))

def pos(i, k, t):
    y, T = traj(k, i, t)
    for tc, rep in hist[i, k]:
        if t < tc:
            break
        w = smooth((t - tc) / EASE)
        y2, T2 = traj(rep, i, t)
        y, T = y + (y2 - y) * w, T + (T2 - T) * w
    return y, T

def palette(i, k, t):
    """(base palette, (end palette, fade level) while flashing else None)."""
    base, flash = PAL0[k], None
    for t0, end in events[i, k]:
        if t >= t0 + FL:
            base = end
        elif t >= t0:
            flash = (end, 1.0 - (t - t0) / FL)
            break
    return base, flash

# ---- one frame -----------------------------------------------------------------------------------
def tokens(t):
    out = np.zeros((SEGS, H), int)
    sweeping = t >= T_SWEEP0
    if sweeping:
        u = t - T_SWEEP0
        top = STR[0][1] / 2.0
        if u < T_UP:
            yc0 = YC[0] + (top - YC[0]) * smooth(u / T_UP)
        else:
            v = (u - T_UP) / T_DOWN
            yc0 = top + (H + STR[0][1] / 2.0 + 2 - top) * v * v
    for k in range(SEGS):
        items = []
        for i in range(NS):
            if sweeping:
                y, T = YC[i], float(STR[i][1])
                if i == 0:
                    y = yc0
                elif T_UP >= u and yc0 - STR[0][1] / 2.0 <= YC[i] or u > T_UP:
                    continue                                   # erased by the nearest bar
            else:
                y, T = pos(i, k, t)
            items.append((T, y, i))
        for T, y, i in sorted(items, key=lambda a: a[0]):       # far (thin) first
            Tn = max(1, min(TMAX, int(round(T))))
            y0 = int(round(y - Tn / 2.0))
            base, flash = palette(i, k, t)
            for r in range(Tn):
                if flash:
                    tok = p3.fade_tok(flash[0], Tn, r, flash[1], "white")
                else:
                    tok = p3.base_tok(base, Tn, r)
                if tok and 0 <= y0 + r < H:
                    out[k, y0 + r] = tok
    return out

def main(path, a=0, b=None):
    Z = 3
    v = iv.Video(path, W * Z, H * Z)
    for f in range(a, T_END if b is None else b):
        seg = tokens(f)
        img = []
        for y in range(H):
            toks = [int(seg[k, y]) for k in range(SEGS)]
            line, _ = g4.fix_line(toks, y, f)
            img.append(g4.draw(line, y, f))
        v.add(lv.crt_look(fb.C64RGB[np.array(img)].astype(np.uint8), Z))
    v.close()
    print("wrote", path, T_END if b is None else b, "frames; matches end at", int(T_LAST),
          "settle", T_SETTLE0, "sweep", T_SWEEP0)

if __name__ == "__main__":
    a = sys.argv[2:]
    main(sys.argv[1], int(a[0]) if a else 0, int(a[1]) if len(a) > 1 else None)
