#!/usr/bin/env python3
"""EasyFlash cartridge of part1p: bank 0 = the boot (cartboot.s), banks 1.. = the program image, which the boot copies to RAM.

    python3 part1p_gen.py && python3 mk_cart_p.py      -> routine_p.crt
"""
import os, struct, subprocess, sys

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)

def main(name="part1p", out="routine_p.crt"):
    extra = []
    for v in ("HTUNE", "WAITX", "FREEZE", "HBIT", "ODD"):
        if v in os.environ: extra += ["-Wa", f"-D{v}={os.environ[v]}"]
    run(["cl65", "-g", "-t", "none", *extra, "-C", f"{name}.cfg", "-Ln", f"{name}.lbl", "-o", f"{name}.prg", f"{name}.s", f"{name}_tab.s"])
    prg = open(f"{name}.prg", "rb").read()
    image = prg[2:]
    img_banks = -(-len(image) // 0x2000)
    lbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open(f"{name}.lbl")}
    open("cartboot.inc", "w").write(f"IMG_PAGES = {-(-len(image) // 256)}\nPROG_START = ${lbl['start']:04x}\n")
    run(["ca65", "-o", "cartboot.o", "cartboot.s"])
    run(["ld65", "-C", "cartboot.cfg", "-o", "cartboot.bin", "cartboot.o"])
    boot = open("cartboot.bin", "rb").read()
    assert len(boot) == 0x2000
    chips = []
    def chip(bank, addr, data):
        chips.append(b"CHIP" + struct.pack(">IHHHH", 0x2010, 2, bank, addr, 0x2000) + data)
    chip(0, 0x8000, b"\xff" * 0x2000)
    chip(0, 0xA000, boot)
    padded = image.ljust(img_banks * 0x2000, b"\xff")
    for b in range(img_banks):
        chip(1 + b, 0x8000, padded[b * 0x2000:(b + 1) * 0x2000])
    if os.path.exists(f"{name}_str.bin"):                  # the stream: more 8 KB ROML banks after the image
        st = open(f"{name}_str.bin", "rb").read()
        for b in range(len(st) // 0x2000):
            chip(1 + img_banks + b, 0x8000, st[b * 0x2000:(b + 1) * 0x2000])
    hdr = b"C64 CARTRIDGE   " + struct.pack(">IHHBB6x", 0x40, 0x0100, 32, 1, 0) + b"FLOATING ISLANDS".ljust(32, b"\0")
    open(out, "wb").write(hdr + b"".join(chips))
    print(f"{out}: {len(chips) - 1} banks; program image {len(image)} bytes, start ${lbl['start']:04x}")

if __name__ == "__main__":
    main(*sys.argv[1:3]) if len(sys.argv) > 2 else main()
