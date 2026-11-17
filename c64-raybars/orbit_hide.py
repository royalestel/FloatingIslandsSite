#!/usr/bin/env python3
"""Where a bar comes between the camera and the ship, and what hiding the
sprite there costs on the C64.

Ground truth, from the 3D scene: the ship's model vertices (posed: pitch,
height) are seen from the orbiting camera; a vertex is hidden if the
camera-to-vertex segment cuts through a bar (a cylinder along x, so a circle
in the y-z plane).  The C64 version: orbit360.frame() hides the sprite
pixels where a nearer bar's slab covers them.  Both per frame, compared,
and the cost of the C64 version counted: the sprite is two halves (two
sprites, x 136-160 and 160-184), each with a pointer; to hide lines mid-
sprite, the pointer is switched to a blank block (the data counter goes on,
so switching back shows the right rows).  Writes per frame, and the frames
where a half is hidden whole (no writes: it starts the frame blank, or
disabled).

    python3 orbit_hide.py [stride]
"""
import math, sys
import numpy as np
import orbit_shots as o
import orbit360 as m

def truth(yaw, zship):
    """Fraction of the ship's vertices the camera cannot see (bars between)."""
    a = math.radians(yaw)
    cam = np.array([0.0, o.ZS - o.ZS * math.cos(a)])            # (y, z) of the camera
    pitch = math.radians(m.ship_pitch(zship))
    cp, sp = math.cos(pitch), math.sin(pitch)
    ys = m.ship_y(zship)
    s = 0.36 / 23.6 * m.SHIPSCALE
    pts = np.array([(((y * cp + z * sp) * s) + ys, o.ZS + (-y * sp + z * cp) * s)
                    for poly, _ in m.ship_model() for _, y, z in poly])
    hidden = np.zeros(len(pts), bool)
    for z, yc in m.bars():
        bz = o.ZS + z - zship
        if abs(bz - o.ZS) > 6:
            continue
        c = np.array([yc, bz])
        d = pts - cam
        t = np.clip(((c - cam) @ d.T) / (d * d).sum(1), 0, 1)
        near = cam + t[:, None] * d
        hidden |= ((near - c) ** 2).sum(1) < o.R ** 2
    return hidden.mean()

def runs(lines):
    """[(first line, last line, hidden)] over the sprite half's lines."""
    out = []
    for y, g in lines.items():
        if out and out[-1][2] == g and y == out[-1][1] + 1:
            out[-1][1] = y
        else:
            out.append([y, y, g])
    return out

def main(stride=1):
    tt, th = m.yaw_table()
    turn = int(round(tt[-1]))
    n = m.HOLD + turn + m.HOLD
    rows = []
    for f in range(0, n, stride):
        yaw = float(np.interp(min(max(f - m.HOLD, 0), turn), tt, th)) % 360
        z = f * m.SPEED
        info = {}
        m.frame(yaw, z, f & 1, info)
        writes, whole = 0, 0
        for h in (0, 1):
            r = runs(info["lines"][h])
            if r and all(g for _, _, g in r):
                whole += 1                                   # hidden whole: no writes
            elif any(g for _, _, g in r):
                writes += sum(1 for i, (_, _, g) in enumerate(r) if i > 0)   # a switch at each change
        rows.append((f, yaw, truth(yaw, z), info["hidden"], writes, whole))
    arr = np.array(rows)
    tr, c64 = arr[:, 2] > 0.05, arr[:, 3] > 0.05
    print(f"frames {len(rows)} (stride {stride}): hidden in the 3D scene {tr.sum()}, "
          f"hidden by the C64 rule {c64.sum()}, both {(tr & c64).sum()}, "
          f"3D only {(tr & ~c64).sum()}, C64 only {(~tr & c64).sum()}")
    def spans(mask):
        out, start = [], None
        for i, v in enumerate(mask):
            if v and start is None:
                start = i
            if not v and start is not None:
                out.append((start, i - 1)); start = None
        if start is not None:
            out.append((start, len(mask) - 1))
        return out
    for name, mask in (("3D scene", tr), ("C64", c64)):
        for a, b in spans(mask):
            print(f"  {name}: frames {int(arr[a, 0])}-{int(arr[b, 0])}  camera yaw {arr[a, 1]:.0f}-{arr[b, 1]:.0f}  "
                  f"hidden up to {arr[a:b + 1, 2 if name == '3D scene' else 3].max():.0%}")
    print(f"pointer writes in a frame: max {int(arr[:, 4].max())}, total {int(arr[:, 4].sum() * stride)}; "
          f"frames with a half hidden whole: {int((arr[:, 5] > 0).sum() * stride)}")

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
