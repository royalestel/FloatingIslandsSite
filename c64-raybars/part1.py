#!/usr/bin/env python3
"""PART 1: the intro film (ghost-byte swatches, no splits): three bars slide in, circle in
depth, settle into the stack and tilt into the floor.  In the circle section the whole circle
now moves off into the distance until its rearmost bar is just visible (a 2-line bar at 31.5 m),
then comes back to the foreground and the film goes on as before.

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

REAR_JUST_VISIBLE = 31.5                       # m: a bar this far is a 2-line bar, the last one that shows
P = dict(ap.P)
P.update(FAR_ZC=REAR_JUST_VISIBLE - P["AZ"], FAR_T0=640, FAR_LEN=160, FAR_HOLD=40)
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
