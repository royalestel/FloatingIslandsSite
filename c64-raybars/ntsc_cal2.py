#!/usr/bin/env python3
"""Sweep WAITX/HTUNE/ODD for part2c on NTSC; prints the match (columns 1-319).  python3 ntsc_cal2.py [wlo whi]"""
import os, sys, subprocess, itertools
os.environ["VICEXTRA"] = "-VICIImodel 6567"
import numpy as np
import vice_check_2c as v2
pal = v2.palette()
lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (3, 10)
for w, h, o in itertools.product(range(lo, hi), (0, 1, 2), (0, 1)):
    env = dict(os.environ, WAITX=str(w), HTUNE=str(h), FREEZE="500")
    if o: env["ODD"] = "1"
    r = subprocess.run(["python3", "mk_cart_p.py", "part2c", "/tmp/cal2.crt"], env=env, capture_output=True, text=True)
    if r.returncode: print("build fail", w, h, o, r.stderr[-300:]); continue
    try:
        fcl = v2.one(3, "/tmp/cal2.png", crt="/tmp/cal2.crt", lbl="part2c.lbl")
        V = v2.decode("/tmp/cal2.png", pal)
        best = max((V[:, 1:] == v2.model(f)[:, 1:]).mean() for f in range(max(0, fcl - 4), fcl + 1))
    except Exception as e:
        best = -1
    print(f"WAITX={w} HTUNE={h} ODD={o}: {100*best:.2f} %", flush=True)
