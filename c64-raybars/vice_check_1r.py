#!/usr/bin/env python3
"""VICE check of part1r (NTSC 6567 by default; PLATFORM=PAL for the 6569): N screenshots in one session vs the generator's model.
   python3 vice_check_1r.py [N] [crt]"""
import os, sys, time, socket, subprocess, pickle, re
import numpy as np
from PIL import Image
import part1 as p
import part1_proc as q
import vice_check_p as vp
import part1r_gen as g
pal = vp.palette()
M = pickle.load(open("/tmp/part1r_model.pkl", "rb"))
def model(n):
    m = [g.MAPS[M["dis"][n]][b] for b in M["bufs"][n]]
    lv, par = q.parity_of(m)
    return np.array([p.gp.draw([c] * p.gp.SEGS, (y & ~1) | par[y], n) for y, c in enumerate(lv)])
def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    crt = sys.argv[2] if len(sys.argv) > 2 else "part1r.crt"
    lbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open("part1r.lbl")}
    chip = "6567" if M["plat"] == "NTSC" else "6569"
    cropy = 23 if M["plat"] == "NTSC" else 35
    subprocess.Popen(["xvfb-run", "-a", "x64sc", "+sound", "-warp", "-VICIIfilter", "0", "-VICIIextpal", "-VICIIpalette", "colodore",
                      "-VICIImodel", chip, "-remotemonitor", "-remotemonitoraddress", "ip4://127.0.0.1:6510", "-cartcrt", crt],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = True
    try:
        time.sleep(2)
        for _ in range(60):
            try: s = socket.create_connection(("127.0.0.1", 6510)); s.settimeout(3); break
            except OSError: time.sleep(.5)
        for i in range(N):
            vp.vcmd(s, 'screenshot "/tmp/v1r.png" 2', 0.6)
            m = vp.vcmd(s, "m %04x %04x" % (lbl["fcl"], lbl["fcl"] + 1))
            a, b = re.findall(r">C:[0-9a-f]{4}\s+([0-9a-f]{2})\s+([0-9a-f]{2})", m)[0]
            fcl = int(b + a, 16)
            im = np.array(Image.open("/tmp/v1r.png").convert("RGB")).astype(int)[cropy:cropy + 200, 32:352]
            V = ((im[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(-1).argmin(-1)
            best = max(((V == model(f)).mean(), f) for f in range(max(0, fcl - 3), min(len(M["bufs"]), fcl + 1)))
            print(f"shot {i}: frame counter {fcl}; best frame {best[1]}: {100 * best[0]:.2f} %", flush=True)
            ok &= best[0] == 1.0
            vp.vcmd(s, "x", 0.2); time.sleep(0.3 + 1.2 * (i % 4))
        vp.vcmd(s, "quit")
    finally:
        time.sleep(1); subprocess.run(["pkill", "-x", "x64sc"]); subprocess.run(["pkill", "-x", "Xvfb"])
    print("all pixel exact" if ok else "MISMATCH")
if __name__ == "__main__":
    main()
