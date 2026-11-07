#!/usr/bin/env python3
"""EasyFlash cartridge of part1p: bank 0 = the boot (cartboot.s), banks 1.. = the program image, which the boot copies to RAM.

    python3 part1p_gen.py && python3 mk_cart_p.py      -> routine_p.crt
"""
import struct, subprocess, sys

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)

def main():
    run(["cl65", "-g", "-t", "none", "-C", "part1p.cfg", "-Ln", "part1p.lbl", "-o", "part1p.prg", "part1p.s", "part1p_tab.s"])
    prg = open("part1p.prg", "rb").read()
    image = prg[2:]
    img_banks = -(-len(image) // 0x2000)
    lbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open("part1p.lbl")}
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
    hdr = b"C64 CARTRIDGE   " + struct.pack(">IHHBB6x", 0x40, 0x0100, 32, 1, 0) + b"FLOATING ISLANDS".ljust(32, b"\0")
    open("routine_p.crt", "wb").write(hdr + b"".join(chips))
    print(f"routine_p.crt: {1 + img_banks} banks; program image {len(image)} bytes, start ${lbl['start']:04x}")

if __name__ == "__main__":
    main()
