#!/usr/bin/env python3
"""Flicker clip (a simulation, not VICE): for a bright and a dim bar, three stacked rows: the real VICE bar (static ghost byte),
the tilted hybrid flat version with its row pairs swapped every frame at 60 Hz, and the steady average of the two frames.
python3 mock_flicker.py out.mp4 [seconds]"""
import sys, subprocess
import numpy as np
OUTV = sys.argv[1] if len(sys.argv) > 1 else "mock_flicker.mp4"
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 4
sys.argv = [sys.argv[0], "/tmp/sa_19.png", "0", "1", "/tmp/_x.png"]
import importlib.util, io, contextlib
def build(y0, y1):
    sys.argv[2], sys.argv[3] = str(y0), str(y1)
    spec = importlib.util.spec_from_file_location("mth", "mock_tilt_hybrid.py"); m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(m)
    return m.real, m.A, m.B, m.avg
bars = [build(57, 89), build(106, 118)]
S = 2
def frame(f):
    rows = []
    for real, A, B, avg in bars:
        for a in (real, A if f % 2 == 0 else B, avg):
            rows.append(a); rows.append(np.zeros((4, a.shape[1], 3)))
        rows.append(np.zeros((10, real.shape[1], 3)))
    im = np.concatenate(rows).astype(np.uint8)
    return np.repeat(np.repeat(im, S, axis=0), S, axis=1)
f0 = frame(0)
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{f0.shape[1]}x{f0.shape[0]}", "-r", "60",
                       "-i", "-", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", OUTV], stdin=subprocess.PIPE)
for f in range(int(SECS * 60)):
    ff.stdin.write(frame(f).tobytes())
ff.stdin.close(); ff.wait(); print("wrote", OUTV)
