#!/usr/bin/env python3
"""PART 1: the intro film (ghost-byte swatches, no splits): three bars slide in, circle in
depth, settle into the stack and tilt into the floor.  In the circle section the whole circle
moves off into the distance (no bar smaller than 8 lines: the rearmost is 8 lines at 6 m), then
closer to the camera than it started (centre 1.6 m instead of 2.0), then back to neutral, and
the film goes on as before.

    python3 part1.py part1.mp4
"""
import sys
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import anim_params as ap
import anim_scene as sc
import ghost_preview as gp

REAR_8_LINES = 2 * 200 * 0.12 / 8.0            # 6 m: a bar this far is 8 lines thick
P = dict(ap.P)
P.update(FAR_KEYS=[(640, P["ZC"]), (760, REAR_8_LINES - P["AZ"]), (790, REAR_8_LINES - P["AZ"]),
                   (890, 1.6), (910, 1.6), (1000, P["ZC"])])
sc.configure(P)

def main(path, a=0, b=None):
    Z = 3
    v = iv.Video(path, gp.W * Z, gp.H * Z)
    n = sc.T_END if b is None else b
    for f in range(a, n):
        col = gp.film_lines(gp.frame_list(f))
        img = np.array([gp.draw([c] * gp.SEGS, y, f) for y, c in enumerate(col)])
        v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    v.close()
    print("wrote", path, n - a, "frames")

if __name__ == "__main__":
    a = sys.argv[2:]
    main(sys.argv[1], int(a[0]) if a else 0, int(a[1]) if len(a) > 1 else None)
