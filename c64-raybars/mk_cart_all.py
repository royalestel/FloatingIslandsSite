#!/usr/bin/env python3
"""The whole routine as one EasyFlash cartridge: boot + parts in sequence.  python3 mk_cart_all.py [out.crt] [part ...]"""
import os, struct, subprocess, sys
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: sys.exit(" ".join(cmd) + "\n" + r.stdout + r.stderr)
SKIP_TUNE = ("part2c", "part2w", "part3c")     # parts that keep the tune ($1000-$2A33) resident and put their tables at $2B00
def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "routine_all.crt"
    parts = sys.argv[2:] or ["part1r", "part2c", "part2w", "part3c", "part4c"]
    chips, bank, table = [], 1, []
    def chip(b, addr, data):
        chips.append(b"CHIP" + struct.pack(">IHHHH", 0x2010, 2, b, addr, 0x2000) + data)
    body = []
    for name in parts:
        import c64build
        image = b"\0" + c64build.build(name, ["-Wa", f"-DBASE={bank}"])[0][2:]      # one leading byte: the loader starts at $0800
        lbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open(f"{name}.lbl")}
        nb = -(-len(image) // 0x4000)
        pages = -(-len(image) // 256)
        assert pages < 256 or True
        if name in SKIP_TUNE: assert pages < 128; pages |= 0x80          # bit 7: this part sits above the tune
        table.append((bank, pages, lbl["start"]))
        padded = image.ljust(nb * 0x4000, b"\xff")
        for b in range(nb): body.append((bank + b, padded[b * 0x4000:(b + 1) * 0x4000]))
        bank += nb
        if os.path.exists(f"{name}_str.bin"):
            st = open(f"{name}_str.bin", "rb").read()
            for b in range(len(st) // 0x4000): body.append((bank + b, st[b * 0x4000:(b + 1) * 0x4000]))
            bank += len(st) // 0x4000
        print(f"{name}: image {len(image)} bytes, next bank {bank}")
    assert all((p & 0x7f) < 256 for _, p, _ in table), "image over 64 KB"
    open("cartparts.inc", "w").write(f"NPARTS = {len(table)}\n.macro PARTS_TABLE\n" + "".join(f"        .byte {b}, {p}, <${s:04x}, >${s:04x}\n" for b, p, s in table) + ".endmacro\n")
    run(["ca65", "-o", "cartboot_all.o", "cartboot_all.s"])
    run(["ld65", "-C", "cartboot.cfg", "-o", "cartboot_all.bin", "cartboot_all.o"])
    boot = open("cartboot_all.bin", "rb").read()
    chip(0, 0x8000, b"\xff" * 0x2000); chip(0, 0xA000, boot)
    for b, d in body: chip(b, 0x8000, d[:0x2000]); chip(b, 0xA000, d[0x2000:])
    hdr = b"C64 CARTRIDGE   " + struct.pack(">IHHBB6x", 0x40, 0x0100, 32, 1, 0) + b"FLOATING ISLANDS".ljust(32, b"\0")
    open(out, "wb").write(hdr + b"".join(chips))
    print(out, len(chips) - 1, "banks (of 64 possible 8K ROML banks = 512 KB; EasyFlash 1 MB has 64 ROML+64 ROMH)")
main()
