#!/usr/bin/env python3
"""Render part 1 as the C64 shows it (the generator's model through the dim maps) -> c64_part1r_<platform>.mp4 at 60 / 50 fps"""
import pickle, sys
import numpy as np, flyby3d as fb, ideas_video as iv, loop_video as lv
import vice_check_1r as v
plat = v.M["plat"].lower()
w = iv.Video(f"c64_part1r_{plat}.mp4", 960, 600, fps=60 if plat == "ntsc" else 50)
for n in range(len(v.M["bufs"])):
    w.add(lv.crt_look(fb.C64RGB[v.model(n)].astype(np.uint8), 3))
w.close()
print("done", len(v.M["bufs"]))
