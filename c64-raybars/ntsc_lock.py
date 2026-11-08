#!/usr/bin/env python3
"""Lock sweep, 2c, NTSC: starts at frame 500 (columns differ), FREEZEd; per combo N runs; prints the first-edge x of each run (33 expected)."""
import os, sys, subprocess, itertools, collections
os.environ["VICEXTRA"] = "-VICIImodel 6567"
import numpy as np
import vice_check_2c as v2
pal = v2.palette()
def edges(r): return [x for x in range(1, 320) if r[x] != r[x-1]]
def first_edge(png):
    V = v2.decode(png, pal)
    c = collections.Counter(edges(V[y])[0] for y in range(200) if len(edges(V[y])) >= 4 and edges(V[y])[1] - edges(V[y])[0] == 64)
    return c.most_common(1)[0][0] if c else None
def run(n, **kw):
    env = dict(os.environ, START="500", FREEZE="500", **{k: str(v) for k, v in kw.items()})
    r = subprocess.run(["python3", "mk_cart_p.py", "part2c", "/tmp/lk.crt"], env=env, capture_output=True, text=True)
    if r.returncode: return ["build fail"]
    out = []
    for _ in range(n):
        v2.one(2.5, "/tmp/lk.png", crt="/tmp/lk.crt", lbl="part2c.lbl")
        out.append(first_edge("/tmp/lk.png"))
    return out
if __name__ == "__main__":
    for w, pre, o in itertools.product(range(*map(int, sys.argv[1:3])), (0, 1), (0, 1)):
        kw = dict(WAITX=w, PRE=pre, HTUNE=0)
        if o: kw["ODD"] = 1
        print(f"WAITX={w} PRE={pre} ODD={o}: {run(4, **kw)}", flush=True)
