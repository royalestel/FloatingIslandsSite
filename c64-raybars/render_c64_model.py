#!/usr/bin/env python3
"""Render what the C64 shows (VICE-verified models) for part2 (earthquake + waves) and part3 -> c64_part2.mp4, c64_part3.mp4"""
import os, sys, pickle
os.environ["SPLITS"] = "6"
import numpy as np
import flyby3d as fb, ideas_video as iv, loop_video as lv
import vice_check_2c as v2, part2c_gen as g
def wr(path, imgs):
    v = iv.Video(path, 960, 600)
    for im in imgs:
        v.add(lv.crt_look(fb.C64RGB[im].astype(np.uint8), 3))
    v.close()
def pk(p):
    frames, gh = pickle.load(open(p, "rb"))
    def m(f):
        img = np.zeros((200, 320), int); x = np.arange(320)
        for y in range(200):
            row = np.zeros(320, int)
            for k in range(6):
                row[v2.EDGES[k]:v2.EDGES[k+1]] = frames[f][y, k]
            if gh[f][y]: row[((gh[f][y] >> (7 - x % 8)) & 1) == 1] = 0
            img[y] = row
        if CLIP: img[185:] = 0                     # parts 3-4: the C64 loop ends at line 184
        return img
    return len(frames), m
which = sys.argv[1]
CLIP = which in ("3", "4")
if which == "2":
    n, m = pk("/tmp/part2w_frames.pkl")
    wr("c64_part2.mp4", (v2.model(f) for f in range(g.NF)) if False else iter([v2.model(f) for f in range(g.NF)] + [m(f) for f in range(n)]))
elif which == "4":
    n, m = pk("/tmp/part4_frames.pkl")
    wr("c64_part4.mp4", (m(f) for f in range(n)))
else:
    n, m = pk("/tmp/part3_frames.pkl")
    wr("c64_part3.mp4", (m(f) for f in range(n)))
