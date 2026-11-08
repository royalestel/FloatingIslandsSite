import os, sys, subprocess, itertools
os.environ["VICEXTRA"] = "-VICIImodel 6567"
import numpy as np
import vice_check_2c as v2
pal = v2.palette()
W, PRE = sys.argv[1], sys.argv[2]
for h, hb in itertools.product(range(0, 6), (0, 1)):
    env = dict(os.environ, WAITX=W, PRE=PRE, FREEZE="500", HTUNE=str(h))
    if not hb: env["NOHBIT"] = "1"; 
    r = subprocess.run(["python3", "mk_cart_p.py", "part2c", "/tmp/cal4.crt"], env=dict(env, **({"X": "1"})), capture_output=True, text=True)
    out = []
    for k in range(2):
        fcl = v2.one(3, "/tmp/cal4.png", crt="/tmp/cal4.crt", lbl="part2c.lbl")
        V = v2.decode("/tmp/cal4.png", pal)
        out.append(round(float(100 * max((V[:, 1:] == v2.model(f)[:, 1:]).mean() for f in range(fcl - 3, fcl + 1))), 1))
    print(f"WAITX={W} PRE={PRE} HTUNE={h} HBIT={hb}: {out}", flush=True)
