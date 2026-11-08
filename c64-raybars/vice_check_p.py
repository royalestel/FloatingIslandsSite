#!/usr/bin/env python3
"""Runs routine.crt in VICE (xvfb, warp), stops it at different moments through the remote monitor,
takes a screenshot (no CRT filter, colodore palette) and compares the 320 x 200 window with the Python
model (part1_gen.compose_ref + ghost_preview.draw) pixel for pixel.

    python3 vice_check.py [seconds ...]        needs: vice (x64sc), xvfb, dummy ROMs in /usr/share/vice/C64
"""
CROPY = int(__import__("os").environ.get("CROPY", "23"))   # NTSC (6567R8) screenshot: line 51 at y = 23 (PAL: 35)
import re, socket, subprocess, sys, time
import numpy as np
from PIL import Image
import part1 as p
import part1_proc as q

PORT = 6510
def vcmd(s, c, wait=0.4):
    s.sendall((c + "\n").encode()); time.sleep(wait)
    out = b""
    try:
        while True:
            d = s.recv(65536); out += d
            if len(d) < 65536: break
    except socket.timeout:
        pass
    return out.decode(errors="replace")

def palette():
    rows = [l.split() for l in open("/usr/share/vice/C64/colodore.vpl") if l.strip() and not l.startswith("#")]
    return np.array([[int(v, 16) for v in r[:3]] for r in rows[:16]])

def model(f):
    buf = q.film_buf(f)
    lv, par = q.parity_of(buf)          # swatch, and the row's parity inside its bar
    return np.array([p.gp.draw([c] * p.gp.SEGS, (y & ~1) | par[y], f) for y, c in enumerate(lv)])

def one(wait, shot, crt="routine_p.crt", extra=()):
    proc = subprocess.Popen(["xvfb-run", "-a", "x64sc", "+sound", "-warp", "-VICIIfilter", "0", "-VICIIextpal",
                             "-VICIIpalette", "colodore", "-remotemonitor", "-remotemonitoraddress",
                             f"ip4://127.0.0.1:{PORT}", "-cartcrt", crt, *extra, *__import__("os").environ.get("VICEXTRA", "").split()],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(wait)
        for _ in range(60):
            try:
                s = socket.create_connection(("127.0.0.1", PORT)); s.settimeout(3); break
            except OSError:
                time.sleep(0.5)
        lbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open("part1p.lbl")}
        vcmd(s, f'screenshot "{shot}" 2', 2)
        m = vcmd(s, "m %04x %04x" % (lbl["fcl"], lbl["fcl"] + 1))
        a, b = re.findall(r">C:[0-9a-f]{4}\s+([0-9a-f]{2})\s+([0-9a-f]{2})", m)[0]
        vcmd(s, "quit")
        return int(b + a, 16)
    finally:
        time.sleep(1)
        subprocess.run(["pkill", "-x", "x64sc"]); subprocess.run(["pkill", "-x", "Xvfb"])

def main():
    pal = palette()
    ok = True
    for w in [float(a) for a in sys.argv[1:]] or [4, 5, 6, 7, 8, 9, 10, 11]:
        shot = f"/tmp/vcheck_{w}.png"
        fcl = one(w, shot)
        im = np.array(Image.open(shot).convert("RGB")).astype(int)[CROPY:CROPY + 200, 32:352]
        V = ((im[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(-1).argmin(-1)
        best = max(((V == model(f)).mean(), f) for f in range(max(0, fcl - 4), fcl + 1))
        print(f"after {w}s: frame counter {fcl}; best match frame {best[1]}: {100 * best[0]:.2f} % of 64,000 pixels")
        ok &= best[0] == 1.0
    print("all pixel exact" if ok else "MISMATCH")

if __name__ == "__main__":
    main()
