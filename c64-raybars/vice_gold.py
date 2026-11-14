#!/usr/bin/env python3
"""VICE check of a gold routine on NTSC (6567R8): a one-part test cartridge of `name` (built with the given assembler defines, e.g.
FREEZE=1 MUSIC=0 for a still picture without the tune), screenshots after a few seconds, and the bar's colour edges per raster line:
the raster must be stable (the same edges on every row of the bar and in every screenshot) and the edges one segment apart.

    python3 vice_gold.py goldtilt_ntsc [DEF=v ...]          (writes /tmp/vg_<name>_<i>.png)
"""
import os, re, socket, struct, subprocess, sys, time
import numpy as np
from PIL import Image
import c64build

PORT = 6510

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: sys.exit(" ".join(cmd) + "\n" + r.stdout + r.stderr)

def cart(name, defs, out):
    """boot + the one part (loaded to $0801 by cartboot_all's loader, started at its `start`)"""
    flags = [x for d in defs for x in ("-Wa", f"-D{d}")]
    prg, lbl = c64build.build(name, flags + ["-Wa", "-DBASE=1"])
    image = b"\0" + prg[2:]
    pages = -(-len(image) // 256)
    nb = -(-len(image) // 0x4000)
    open("cartparts.inc", "w").write(f"NPARTS = 1\n.macro PARTS_TABLE\n        .byte 1, {pages}, <${lbl['start']:04x}, >${lbl['start']:04x}\n.endmacro\n")
    run(["ca65", "-o", "cartboot_all.o", "cartboot_all.s"])
    run(["ld65", "-C", "cartboot.cfg", "-o", "cartboot_all.bin", "cartboot_all.o"])
    boot = open("cartboot_all.bin", "rb").read()
    chips = []
    def chip(b, addr, data):
        chips.append(b"CHIP" + struct.pack(">IHHHH", 0x2010, 2, b, addr, 0x2000) + data)
    chip(0, 0x8000, b"\xff" * 0x2000); chip(0, 0xA000, boot)
    padded = image.ljust(nb * 0x4000, b"\xff")
    for b in range(nb):
        d = padded[b * 0x4000:(b + 1) * 0x4000]
        chip(1 + b, 0x8000, d[:0x2000]); chip(1 + b, 0xA000, d[0x2000:])
    hdr = b"C64 CARTRIDGE   " + struct.pack(">IHHBB6x", 0x40, 0x0100, 32, 1, 0) + b"GOLD TEST".ljust(32, b"\0")
    open(out, "wb").write(hdr + b"".join(chips))
    subprocess.run(["git", "checkout", "-q", "cartparts.inc", "cartboot_all.bin"])
    return lbl

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

def shots(crt, times, prefix):
    proc = subprocess.Popen(["xvfb-run", "-a", "x64sc", "+sound", "-warp", "-VICIIfilter", "0", "-VICIIextpal", "-VICIIpalette", "colodore",
                             "-VICIImodel", "6567", "-remotemonitor", "-remotemonitoraddress", f"ip4://127.0.0.1:{PORT}", "-cartcrt", crt],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    files = []
    try:
        time.sleep(times[0])
        for _ in range(60):
            try:
                s = socket.create_connection(("127.0.0.1", PORT)); s.settimeout(3); break
            except OSError:
                time.sleep(0.5)
        for i, t in enumerate(times):
            if i: vcmd(s, "x", 0.2); time.sleep(t)
            f = f"{prefix}_{i}.png"
            vcmd(s, f'screenshot "{f}" 2', 2)
            files.append(f)
        vcmd(s, "quit")
    finally:
        time.sleep(1)
        subprocess.run(["pkill", "-x", "x64sc"]); subprocess.run(["pkill", "-x", "Xvfb"])
    return files

def palette():
    rows = [l.split() for l in open("/usr/share/vice/C64/colodore.vpl") if l.strip() and not l.startswith("#")]
    return np.array([[int(v, 16) for v in r[:3]] for r in rows[:16]])

def decode(f, pal):
    im = np.array(Image.open(f).convert("RGB")).astype(int)
    return ((im[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(-1).argmin(-1)

def edges(img):
    """per screenshot row with more than one colour: the x positions where the colour changes"""
    out = {}
    for y in range(img.shape[0]):
        r = img[y]
        xs = tuple(int(x) for x in np.nonzero(r[1:] != r[:-1])[0] + 1)
        if xs: out[y] = xs
    return out

def main():
    name = sys.argv[1]
    defs = sys.argv[2:] or ["FREEZE=1", "MUSIC=0"]
    crt = f"/tmp/vg_{name}.crt"
    cart(name, defs, crt)
    files = shots(crt, [6, 2, 2], f"/tmp/vg_{name}")
    pal = palette()
    allx = []
    for f in files:
        img = decode(f, pal)
        e = edges(img)
        rows = sorted(e)
        # the bar's rows: colour changes inside the line; the set of change positions modulo the segment width
        xs = sorted({x for y in rows for x in e[y]})
        print(f"{f}: {img.shape[1]}x{img.shape[0]}, {len(rows)} rows with colour changes (y {rows[0] if rows else '-'}..{rows[-1] if rows else '-'}), change x positions: {xs[:16]}")
        allx.append(xs)
    print("same change positions in every screenshot:", all(a == allx[0] for a in allx))

if __name__ == "__main__":
    main()
