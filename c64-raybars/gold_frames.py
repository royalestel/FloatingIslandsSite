#!/usr/bin/env python3
"""Runs a gold routine's simulator (sim_<name>.py: the real 6502 code on py65) for n frames and returns its frames as raster images:
    frames_of(name, n) -> list of (TOP, numpy array H x W of RGB)   (raster lines TOP.. ; PAL programs, one frame = one update())"""
import os, re, sys, pickle, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
def _tag(init): return ("_" + re.sub(r"[^0-9a-z]", "", init.replace("=", "").replace(",", ""))) if init else ""
def raw_of(name, n, init=""):
    """the simulator's own per-frame records (goldtilt: (y, grid, cycles); goldlight: (y, grid, ly, lx, cycles); ...) of a frames_of run"""
    return pickle.load(open(f"/tmp/gold_{name}_{n}{_tag(init)}_raw.pkl", "rb"))
def frames_of(name, n, cache=True, init=""):
    """init: "orbit=204,tilt=164" initial zero-page phases (goldtilt, goldlight)"""
    tag = _tag(init)
    p = f"/tmp/gold_{name}_{n}{tag}.pkl"
    os.environ["GOLD_INIT"] = init
    if cache and os.path.exists(p): return pickle.load(open(p, "rb"))
    src = open(os.path.join(HERE, f"sim_{name}.py")).read()
    src = re.sub(r"^FRAMES\s*=\s*[^\n]*", f"FRAMES = {n}", src, count=1, flags=re.M) if name != "goldfly" else src
    if name == "goldfly": os.environ["FRAMES"] = str(n)
    src = re.sub(r"^FRAMES, NSLOT", "FRAMES, NSLOT", src, flags=re.M)
    cut = src.index("\nimgs = ")
    ns = {"__file__": os.path.join(HERE, f"sim_{name}.py"), "__name__": "gold_sim"}
    cwd = os.getcwd(); os.chdir(HERE)
    try: exec(compile(src[:cut], f"sim_{name}.py", "exec"), ns)
    finally: os.chdir(cwd)
    frames, render, SCALE, TOP = ns["frames"], ns["render"], ns["SCALE"], ns["TOP"]
    nargs = {"goldtilt": 2, "goldlight": 4, "goldorbit": 5, "goldtwin": 6, "goldfly": 1}[name]
    out = []
    for fr in frames:
        im = (render(*fr[:4], spr=fr[5]) if name == "goldlight" else render(*fr[:nargs])) if nargs > 1 else render(fr)
        a = np.array(im)[::SCALE, ::SCALE]
        out.append((TOP, a))
    try: pickle.dump([tuple(fr) for fr in frames], open(p.replace(".pkl", "_raw.pkl"), "wb"))
    except Exception: pass
    pickle.dump(out, open(p, "wb"))
    return out
if __name__ == "__main__":
    import time
    for name, n in [(a, int(b)) for a, b in (x.split(":") for x in sys.argv[1:])]:
        t0 = time.time(); fr = frames_of(name, n, cache=False)
        print(name, len(fr), "frames", fr[0][1].shape, "TOP", fr[0][0], "%.0fs" % (time.time() - t0), flush=True)
