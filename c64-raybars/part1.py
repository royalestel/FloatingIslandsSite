#!/usr/bin/env python3
"""PART 1: the intro film (ghost-byte swatches, no splits).

Three bars slide in, circle in depth (the whole circle goes off into the distance -- no bar
under 8 lines -- then closer than it started, then back to neutral), keep circling while they
dim down the ramp to the ghost-byte colours and back up to full brightness, and settle into a
vertical stack.  The floor they end in is pushed back a little (its nearest bar at 1.0 m instead
of 0.8) and has 24 bars instead of 28 (the back 4 removed), so the rear bars' tilt can be seen.
At the end of the part:
  * the stack is built faster: three more bars slide up from the bottom (15 frames apart,
    40 each) and the rest of the stack comes down from above: all 28 floor bars are one
    tall vertical stack, most of it above the top of the screen;
  * then the whole stack of 28 bars rotates down together as one plane, about the nearest
    bar, into the floor (the plane opens as it goes: bar spacing 0.27 m -> 0.8 m, the pivot
    comes to the floor, the horizon drops); the upper bars swing into view as it turns.
    It ends on exactly the floor that part 2 starts with.

    python3 part1.py part1.mp4 [first_frame last_frame]
"""
import sys, math
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import anim_params as ap
import anim_scene as sc
import ghost_preview as gp
import anim1_floor as fv

F, R, H, W = sc.F, sc.R, sc.H, gp.W
TMAX = gp.TMAX
REAR_8_LINES = 2 * 200 * 0.12 / 8.0            # 6 m: a bar this far is 8 lines thick
EXTRA = 60                                     # frames added for the dimming while circling
P = dict(ap.P)
P.update(FAR_KEYS=[(640, P["ZC"]), (760, REAR_8_LINES - P["AZ"]), (790, REAR_8_LINES - P["AZ"]),
                   (890, 1.6), (910, 1.6), (1000, P["ZC"])],
         T_C0=P["T_C0"] + EXTRA, T_C1=P["T_C1"] + EXTRA)
sc.configure(P)

# dimming: after the circle is back at neutral (frame 1000) the bars fade down the ramp to the
# ghost-byte colours and back to full brightness, still circling
DIM = [(1000, 1.0), (1050, 0.28), (1070, 0.28), (1130, 1.0)]

def dim(f):
    if f <= DIM[0][0] or f >= DIM[-1][0]:
        return 1.0
    for (t0, a), (t1, b) in zip(DIM, DIM[1:]):
        if f < t1:
            x = smooth((f - t0) / float(t1 - t0))
            return a + (b - a) * x
    return 1.0

smooth = sc.smooth
T_STACK = P["T_C1"]                            # 1230: the circle bars are in the stack
T_NEWB = [T_STACK, T_STACK + 15, T_STACK + 30]  # the three from the bottom (m = 2, 1, 0)
T_TOPB = T_STACK + 45                           # the upper stack (m >= 6) comes down from above
NEW_LEN = 40
T_ROT0, T_ROT1 = T_STACK + 110, T_STACK + 310   # the unified rotation of the whole stack (3.3 s)
T_END = T_ROT1 + 120
FLOOR_Z0, NSTACK = 1.0, 24                                       # the floor: nearest bar 1.0 m, 24 bars
PITCH = sc.PITCH_PX
Z0 = P["Z_EQ"]
YCW = [H / 2 + (5 - m - 2.5) * PITCH for m in range(NSTACK)]     # stack slot m (0 = bottom), screen line
S0 = PITCH * Z0 / F                                              # wall spacing (m)
S1 = fv.SPACING                                                  # floor spacing (m)
YP0 = -(YCW[0] - H / 2) * Z0 / F                                 # the bottom bar's height (m)
YP1, ZP1, HORIZON = -fv.CAM_H, FLOOR_Z0, fv.HORIZON

def stack(t):
    """[(size distance, centre line, key)] of the 28 stacked / rotating bars at frame t >= T_STACK."""
    p = smooth((t - T_ROT0) / float(T_ROT1 - T_ROT0))
    alpha = math.pi / 2 * p
    s = S0 + (S1 - S0) * p
    yp = YP0 + (YP1 - YP0) * p
    zp = Z0 + (ZP1 - Z0) * p
    y0 = H / 2 + (HORIZON - H / 2) * p                            # the horizon comes down
    out = []
    for m in range(NSTACK):
        y = yp + m * s * math.cos(alpha)
        z = zp + m * s * math.sin(alpha)
        yc = y0 - F * y / z
        w = smooth((p - 0.6) / 0.4)                               # land exactly on part 2's floor
        yc = (1 - w) * yc + w * float(fv.screen_y(z))
        d = math.hypot(z, y * p)                                  # the bar's thickness distance
        if m < 3:
            yc += 260 * (1 - smooth((t - T_NEWB[2 - m]) / NEW_LEN))   # up from the bottom
        elif m > 5:
            yc -= 600 * (1 - smooth((t - T_TOPB) / (NEW_LEN + 10)))   # the upper stack comes down
        out.append((d, yc, d))
    return out

def bars_all(t):
    if t < T_STACK:
        return [b for b in sc.bars(t)[:3]]                        # the three circling bars
    return stack(t)

def frame_list(t):
    out = []
    for z, yc, key in sorted(bars_all(t), key=lambda b: -b[2]):   # far first
        z = max(z, 0.6)
        T = max(1, min(TMAX, int(round(2 * F * R / z))))
        y0 = int(round(yc - T / 2))
        if y0 >= H or y0 + T <= 0 or not any(gp.PROF[T][max(0, -y0):H - y0]):
            continue
        out.append((y0, T))
    return out

def main(path, a=0, b=None):
    Z = 3
    v = iv.Video(path, W * Z, H * Z)
    n = T_END if b is None else b
    for f in range(a, n):
        col = gp.film_lines(frame_list(f))
        g = dim(f)
        if g < 1.0:                                   # fade down the ramp (black stays black)
            col = np.array([max(1, int(round(k * g))) if k else 0 for k in col])
        img = np.array([gp.draw([c] * gp.SEGS, y, f) for y, c in enumerate(col)])
        v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    v.close()
    print("wrote", path, n - a, "frames")

if __name__ == "__main__":
    a = sys.argv[2:]
    main(sys.argv[1], int(a[0]) if a else 0, int(a[1]) if len(a) > 1 else None)
