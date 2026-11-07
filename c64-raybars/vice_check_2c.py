#!/usr/bin/env python3
"""VICE check of part2c.crt (the earthquake, 6 columns): screenshots at several moments against the model of
what the loop shows (part2c_gen's patterns read at the frame's shifts).

    SPLITS=6 python3 vice_check_2c.py [seconds ...]
"""
import os, re, socket, subprocess, sys, time
os.environ.setdefault("SPLITS", "6")
import numpy as np
from PIL import Image
import part2c_gen as g

PORT = 6510
EDGES = [0, 33, 97, 161, 225, 289, 320]        # where the writes land on the screen (8 px a cycle; the VIC shows a write 1 pixel later than 32)
PAT = g.patterns()
OFFS = g.offsets()

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

def model(f, edges=EDGES):
    d = OFFS[f % g.NF]; fp = f & 1
    same = len(set(d)) == 1
    src = PAT[("g" if same else "f", fp)]
    gh = PAT[("h", fp)] if same else PAT[("z", 0)]
    img = np.zeros((200, 320), int)
    x = np.arange(320)
    for y in range(200):
        row = np.zeros(320, int)
        for k in range(6):
            yy = y - d[k]
            row[edges[k]:edges[k + 1]] = src[yy] if 0 <= yy < 200 else 0
        yy = y - d[0]
        gb = gh[yy] if 0 <= yy < 200 else 0
        if gb:
            row[((gb >> (7 - x % 8)) & 1) == 1] = 0
        img[y] = row
    return img

def one(wait, shot, crt="part2c.crt"):
    proc = subprocess.Popen(["xvfb-run", "-a", "x64sc", "+sound", "-warp", "-VICIIfilter", "0", "-VICIIextpal",
                             "-VICIIpalette", "colodore", "-remotemonitor", "-remotemonitoraddress",
                             f"ip4://127.0.0.1:{PORT}", *os.environ.get("VICEXTRA", "").split(), "-cartcrt", crt],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(wait)
        for _ in range(60):
            try:
                s = socket.create_connection(("127.0.0.1", PORT)); s.settimeout(3); break
            except OSError:
                time.sleep(0.5)
        lbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open("part2c.lbl")}
        vcmd(s, f'screenshot "{shot}" 2', 2)
        m = vcmd(s, "m %04x %04x" % (lbl["fcl"], lbl["fcl"] + 1))
        a, b = re.findall(r">C:[0-9a-f]{4}\s+([0-9a-f]{2})\s+([0-9a-f]{2})", m)[0]
        vcmd(s, "quit")
        return int(b + a, 16)
    finally:
        time.sleep(1)
        subprocess.run(["pkill", "-x", "x64sc"]); subprocess.run(["pkill", "-x", "Xvfb"])

def decode(shot, pal):
    im = np.array(Image.open(shot).convert("RGB")).astype(int)[35:235, 32:352]
    return ((im[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(-1).argmin(-1)

def main():
    pal = palette(); ok = True
    for w in [float(a) for a in sys.argv[1:]] or [4, 6, 8, 10]:
        shot = f"/tmp/v2c_{w}.png"
        fcl = one(w, shot)
        V = decode(shot, pal)
        best = max(((V[:, 1:] == model(f)[:, 1:]).mean(), f) for f in range(max(0, fcl - 4), fcl + 1))
        print(f"after {w}s: frame counter {fcl}; best match frame {best[1]}: {100 * best[0]:.2f} % (columns 1-319)")
        ok &= best[0] == 1.0
    print("all pixel exact" if ok else "MISMATCH")

if __name__ == "__main__":
    main()
