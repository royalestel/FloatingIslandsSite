"""Shared cl65 build: if the part has a row loop (labels rloop/rend) that crosses a page, rebuild with SLEDPAD nops
before irq2 so it stays in one page (a page-crossing bne costs a cycle: 66 instead of 65 a line)."""
import os, subprocess, sys

def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(" ".join(cmd) + "\n" + r.stdout + r.stderr)

def labels(name):
    return {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open(f"{name}.lbl")}

def build(name, extra=()):
    srcs = [f"{name}.s"] + [f"{name}{x}.s" for x in ("_tab", "_rout", "_data") if os.path.exists(f"{name}{x}.s")]
    cmd = lambda ex: ["cl65", "-g", "-t", "none", *ex, "-C", f"{name}.cfg", "-Ln", f"{name}.lbl", "-o", f"{name}.prg", *srcs]
    _run(cmd(list(extra)))
    lbl = labels(name)
    if "rloop" in lbl and "rend" in lbl and lbl["rloop"] >> 8 != (lbl["rend"] - 1) >> 8:
        pad = 256 - (lbl["rloop"] & 255)
        _run(cmd(list(extra) + ["-Wa", f"-DSLEDPAD={pad}"]))
        lbl = labels(name)
        assert lbl["rloop"] >> 8 == (lbl["rend"] - 1) >> 8, name
    return open(f"{name}.prg", "rb").read(), lbl
