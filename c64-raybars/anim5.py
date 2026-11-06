#!/usr/bin/env python3
"""anim5: three blue cosmic strings in a black screen.
  A  three bars rise from the bottom into the spaced-out layout (the same as the last
     frame), then slide up and down past one another like classic rasterbars: the
     same size and colour, only the draw order changes as they pass
  B  they blend into a circle in depth (away, down, towards, up), 120 degrees
     apart, so they follow each other round and change colour with distance
  C  they blend back to three bars at one distance, spaced out vertically.
Every bar is lit and sized from its own distance (gen_cosmic.row_v3, F * R / d),
drawn far to near with the flat blue ramp (no ghost-byte swatches); black is
the background and is never drawn over a bar.  CRT look, 60 fps.

    python3 anim5.py anim5.mp4
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
Z_EQ, DY_EQ = 1.7, 0.32              # final: one distance, bars spaced DY_EQ apart (m)
OMEGA = 2 * np.pi / 240              # one turn every 4 s
T_BLACK = 30
T_ENTER = [30, 100, 170]             # frame each bar starts rising; 90 frames to get there
T_MOVE = 90                          # the phase angle starts to run (as before: fixes the circle's phase)
T_SLIDE = 300                        # the bars leave their spaced-out layout and start sliding
T_B0, T_B1 = 500, 620                # sliding at one distance -> circle
T_C0, T_C1 = 1100, 1230              # circle -> three bars spaced out
T_END = T_C1 + 120

smooth = lambda x: (lambda u: u * u * (3 - 2 * u))(min(max(x, 0.0), 1.0))

def theta(t):
    """Angle of bar 0 (starts at 270 deg: nearest, centre height); speed ramps up."""
    k = max(0, t - T_MOVE)
    ramp = min(k, 60)
    ang = ramp * ramp / 120 + max(0, k - 60)            # integral of the speed ramp
    return 1.5 * np.pi + OMEGA * ang

def bars(t):
    """(z, y_world, rise offset in lines, draw-order key) of the three bars at frame t."""
    th = theta(t)
    m = smooth((t - T_SLIDE) / 60)                      # 0 spaced out .. 1 sliding
    s = smooth((t - T_B0) / (T_B1 - T_B0))              # 0 one distance .. 1 circle
    e = smooth((t - T_C0) / (T_C1 - T_C0))              # 0 circle .. 1 spaced out
    slots = np.argsort(np.argsort([-AY * np.cos(theta(T_C0) + 2 * np.pi * k / 3)
                                   for k in range(3)]))     # highest bar -> top slot
    y0 = [0.0, DY_EQ, -DY_EQ]                           # the opening layout
    out = []
    for k in range(3):
        ph = th + 2 * np.pi * k / 3
        zc = ZC + AZ * np.sin(ph)                       # circle: away, down, towards, up
        z = (1 - s) * Z_EQ + s * zc
        y = (1 - m) * y0[k] + m * AY * np.cos(ph)       # the circle seen edge-on is the slide
        z = (1 - e) * z + e * Z_EQ
        y = (1 - e) * y + e * (1 - slots[k]) * DY_EQ
        key = z + 0.001 * (1 - e) * np.sin(ph)          # far (sin > 0) behind, also when sliding
        out.append((z, y, 200 * (1 - smooth((t - T_ENTER[k]) / 90)), key))
    return out

def render(t):
    col = np.zeros(H, int)
    for z, y, rise, _ in sorted(bars(t), key=lambda b: -b[3]):    # far first
        z = max(z, 0.6)
        yc = H / 2 - F * y / z + rise * (1 + 60 / H)
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
