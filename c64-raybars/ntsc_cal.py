#!/usr/bin/env python3
"""Sweep WAITX / HTUNE / ODD for an NTSC (6567R8) build of a part; prints the best pixel match for each.
   python3 ntsc_cal.py part1p  -> uses vice_check_p; (part must have fcl label and a model)"""
import os, sys, subprocess, itertools, numpy as np
from PIL import Image
import vice_check_p as vp
pal = vp.palette()
part = sys.argv[1]
res = []
for w, h, o in itertools.product(range(4, 14), (0, 1, 2), (0, 1)):
    env = dict(os.environ, WAITX=str(w), HTUNE=str(h))
    if o: env["ODD"] = "1"
    r = subprocess.run(["python3", "mk_cart_p.py", part, "/tmp/cal.crt"], env=env, capture_output=True, text=True)
    if r.returncode: print("build fail", w, h, o, r.stderr[-200:]); continue
    shot = "/tmp/cal.png"
    try:
        fcl = vp.one(4, shot, crt="/tmp/cal.crt", extra=("-VICIImodel", "6567"))
        im = np.array(Image.open(shot).convert("RGB")).astype(int)[35:235, 32:352]
        V = ((im[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(-1).argmin(-1)
        best = max(((V == vp.model(f)).mean(), f) for f in range(max(0, fcl - 6), fcl + 1))[0]
    except Exception as e:
        best = -1
    print(f"WAITX={w} HTUNE={h} ODD={o}: {100*best:.2f} %", flush=True)
