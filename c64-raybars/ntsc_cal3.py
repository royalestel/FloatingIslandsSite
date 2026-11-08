#!/usr/bin/env python3
"""Lock sweep for part2c on NTSC: each (WAITX, PRE, ODD) is run 3 times at FREEZE=500; a reliable lock gives the same match every time."""
import os, sys, subprocess, itertools
os.environ["VICEXTRA"] = "-VICIImodel 6567"
import numpy as np
import vice_check_2c as v2
pal = v2.palette()
for w, pre, o in itertools.product(range(9, 12), (0, 1, 2), (0, 1)):
    env = dict(os.environ, WAITX=str(w), PRE=str(pre), FREEZE="500", HTUNE="0")
    if o: env["ODD"] = "1"
    r = subprocess.run(["python3", "mk_cart_p.py", "part2c", "/tmp/cal3.crt"], env=env, capture_output=True, text=True)
    if r.returncode: print("build fail", w, pre, o, r.stderr[-300:], flush=True); continue
    out = []
    for k in range(3):
        try:
            fcl = v2.one(3, "/tmp/cal3.png", crt="/tmp/cal3.crt", lbl="part2c.lbl")
            V = v2.decode("/tmp/cal3.png", pal)
            out.append(round(100 * max((V[:, 1:] == v2.model(f)[:, 1:]).mean() for f in range(fcl - 3, fcl + 1)), 1))
        except Exception as e:
            out.append(-1)
    print(f"WAITX={w} PRE={pre} ODD={o}: {out}", flush=True)
