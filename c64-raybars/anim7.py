#!/usr/bin/env python3
"""anim5: three blue cosmic strings in a black screen.
  A  a bar slides up from the bottom and starts moving up and down; a second follows,
     then a third: classic rasterbars sliding past one another, the same size and
     colour, only the draw order changes as they pass
  B  they blend into a circle in depth (away, down, towards, up), 120 degrees
     apart, so they follow each other round and change colour with distance
  C  they settle into the top three slots of a stack of six; three more bars slide up
     from the bottom until the stack fills the screen, 3 black lines between bars;
     then the stack tilts into the distance and becomes a six-bar floor (the first
     six strings of floor_video); while it forms, the rest of the floor (every further
     string that is on screen, 23) slides in from the top, behind the others, nearest first.
Every bar is lit and sized from its own distance (gen_cosmic.row_v3, F * R / d),
drawn far to near with the flat blue ramp (no ghost-byte swatches); black is
the background and is never drawn over a bar.  CRT look, 60 fps.

    python3 anim7.py anim7.mp4
"""
import sys
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import anim1_floor as fv
v7 = fv.v7

W, H, Z = fv.W, fv.H, fv.Z
F, R, SUB = fv.F, fv.R, fv.SUB
RAMP, RAMP_L, Lstar = fv.RAMP, fv.RAMP_L, fv.Lstar

ZC, AZ, AY = 2.0, 1.2, 0.55          # circle centre distance, depth and height radius (m)
Z_EQ = 1.7                           # distance of the flat bars
HALF_EQ = F * R / Z_EQ               # their half thickness (lines)
PITCH_PX = 2 * HALF_EQ + 3           # stack pitch: 3 black lines between bars
OMEGA = 2 * np.pi / 240              # one turn every 4 s
T_ENTER = [30, 90, 150]              # each of the first three bars slides up (90 frames)
T_B0, T_B1 = 500, 620                # sliding at one distance -> circle
T_C0, T_C1 = 1100, 1230              # circle -> the top three slots of a 6-bar stack
T_NEW = [1230, 1290, 1350]           # three more bars slide up from the bottom (70 frames)
T_TILT0, T_TILT1 = 1450, 1610        # the stack tilts into the distance: a floor
T_X0, T_XSTAG, T_XSLIDE = T_TILT0 + 20, 3, 60   # the extra strings: first start, stagger, slide time
T_END = T_TILT1 + 120
FLOOR_Z = [fv.SPACING * (6 - j) for j in range(6)]       # slot j (0 top) -> its string's z
# the slots of the stack, and of the floor (the first six strings of floor_video)
YC_WALL = [H / 2 + (j - 2.5) * PITCH_PX for j in range(6)]
D_FLOOR = [float(np.hypot(z, fv.CAM_H)) for z in FLOOR_Z]
YC_FLOOR = [float(fv.screen_y(z)) for z in FLOOR_Z]
# the further strings of the floor (as in the earlier floor videos: every one on screen)
EXTRA_Z = [fv.SPACING * k for k in range(7, int(fv.ZMAX / fv.SPACING) + 1)
           if fv.screen_y(fv.SPACING * k) > -4]
EXTRA_D = [float(np.hypot(z, fv.CAM_H)) for z in EXTRA_Z]
EXTRA_YC = [float(fv.screen_y(z)) for z in EXTRA_Z]

smooth = lambda x: (lambda u: u * u * (3 - 2 * u))(min(max(x, 0.0), 1.0))

def theta(t):
    """Angle of bar 0 (starts at 270 deg: centre height, nearest on the circle)."""
    return 1.5 * np.pi + OMEGA * t

def bars(t):
    """(distance, centre line, draw-order key) of the six bars at frame t
    (bars not on screen yet are far below it)."""
    th = theta(t)
    s = smooth((t - T_B0) / (T_B1 - T_B0))              # 0 one distance .. 1 circle
    e = smooth((t - T_C0) / (T_C1 - T_C0))              # 0 circle .. 1 stack slots
    a = smooth((t - T_TILT0) / (T_TILT1 - T_TILT0))     # 0 wall .. 1 floor
    slots = np.argsort(np.argsort([-AY * np.cos(theta(T_C0) + 2 * np.pi * k / 3)
                                   for k in range(3)]))     # highest bar -> top slot
    out = []
    for k in range(6):
        if k < 3:
            ph = th + 2 * np.pi * k / 3
            zc = ZC + AZ * np.sin(ph)                   # circle: away, down, towards, up
            z = (1 - s) * Z_EQ + s * zc                 # sliding = the circle edge-on
            yc = H / 2 - F * AY * np.cos(ph) / z
            z = (1 - e) * z + e * Z_EQ
            yc = (1 - e) * yc + e * YC_WALL[slots[k]]
            key = z + 0.001 * (1 - e) * np.sin(ph)      # far (sin > 0) behind, also when sliding
            j = slots[k]
            rise = 200 * (1 - smooth((t - T_ENTER[k]) / 90))
        else:
            j = k                                       # slots 3, 4, 5: slide in from the bottom
            z, yc, key = Z_EQ, YC_WALL[j], Z_EQ
            rise = 200 * (1 - smooth((t - T_NEW[k - 3]) / 70))
        z = (1 - a) * z + a * D_FLOOR[j]
        yc = (1 - a) * yc + a * YC_FLOOR[j]
        out.append((z, yc + rise * 1.3, key if a == 0 else z))
    for i, (d, y) in enumerate(zip(EXTRA_D, EXTRA_YC)):      # slide in from the top, nearest first
        u = smooth((t - T_X0 - T_XSTAG * i) / T_XSLIDE)
        out.append((d, y - 300 * (1 - u), d))
    return out

def render(t):
    col = np.zeros(H, int)
    for z, yc, _ in sorted(bars(t), key=lambda b: -b[2]):         # far first
        z = max(z, 0.6)
        half = F * R / z
        for line in range(max(0, int(np.floor(yc - half))), min(H, int(np.ceil(yc + half)))):
            r = (line + (np.arange(SUB) + 0.5) / SUB - yc) / half
            r = r[np.abs(r) < 1]
            if len(r) < SUB / 2:
                continue
            lit = sum(fv.gc.row_v3(z, v) for v in r) / SUB
            k = int(np.argmin(np.abs(Lstar(np.array(lit)) - RAMP_L)))
            if k:                                                  # black = background
                col[line] = k
    return col

def main(path):
    v = iv.Video(path, W * Z, H * Z)
    for f in range(T_END):
        col = render(f)
        img = np.zeros((H, W), int)
        for y in range(H):
            img[y] = v7.colour(RAMP[col[y]], y & 1, f & 1)
        v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    v.close()
    print("wrote", path, T_END, "frames")

if __name__ == "__main__":
    main(sys.argv[1])
