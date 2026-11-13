#!/usr/bin/env python3
"""Video of the frames the C64 shows in part 4d (the generator's /tmp/part4d_shown.pkl: 6 colour bytes + the idle byte a row), plain 3x, 60 fps.
    python3 part4d_video.py out.mp4"""
import os, sys, pickle
os.environ["SPLITS"] = "6"
import numpy as np
import mock_part4_seq as ms
import vice_check_2c as v2
EDGES = v2.EDGES
shown = pickle.load(open("/tmp/part4d_shown.pkl", "rb"))
v = ms.iv.Video(sys.argv[1], 320 * 3, 200 * 3, fps=60)
X = np.arange(320)
from PIL import Image
for a in shown:
    img = np.zeros((200, 320), int)
    for y in range(185):
        row = np.zeros(320, int)
        for k in range(6): row[EDGES[k]:EDGES[k + 1]] = a[y][k]
        if a[y][6]: row[((a[y][6] >> (7 - X % 8)) & 1) == 1] = 0
        img[y] = row
    rgb = ms.fb.C64RGB[img].astype(np.uint8)
    v.add(Image.fromarray(np.repeat(np.repeat(rgb, 3, axis=0), 3, axis=1)))
v.close(); print("wrote", sys.argv[1], len(shown), "frames")
