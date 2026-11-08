#!/usr/bin/env python3
"""Render NTSC 60 Hz part 1 (the generator's LINEBUF model, VICE-exact) -> c64_part1n.mp4"""
import numpy as np, flyby3d as fb, ideas_video as iv, loop_video as lv
import vice_check_1n as v
w = iv.Video("c64_part1n.mp4", 960, 600)
for n in range(len(v.bufs)):
    w.add(lv.crt_look(fb.C64RGB[v.model(n)].astype(np.uint8), 3))
w.close()
