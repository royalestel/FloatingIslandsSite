#!/usr/bin/env python3
"""PART 4 (7 splits).  Starts where part 3 ends: even split columns multicolour, odd red.

  A  every split column slides up and down on the screen (each at its own pace); 3 times a
     second one bar element (the piece of a bar inside a column) flashes white and fades to
     one of the 3 palettes (blue / red / multicolour).
  B  after a few seconds the bars of each column, independently, start moving in circles in
     depth (the bars follow each other round); the colour changes go on.
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

t = FLASH_EVERY
while t < T_ALIGN:                                                  # the random flashes
    i, k = rng.randrange(NS), rng.randrange(SEGS)
    events[i, k].append((t, "blue" if t >= T_BLUE else rng.choice(["blue", "red", "multi"])))
    t += FLASH_EVERY
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
def amps(t):
    settle = 1.0 - smooth((t - T_SETTLE0) / SETTLE)
    return min(1.0, t / 60.0) * settle, smooth((t - T_CIRC) / 120.0) * settle

def traj(k, i, t):
    """(centre line, thickness) of bar i in column k's own motion."""
    sa, ca = amps(t)
    slide = SLIDE_AMP * sa * math.sin(2 * math.pi * t / PERIOD[k] + 0.8 * k)
    th = OMEGA[k] * t + 0.22 * i + 1.3 * k
    rho = 1.0 + CIRC_Z * ca * math.sin(th)
    return YC[i] + slide - CIRC_Y * ca * math.cos(th), STR[i][1] / rho

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
