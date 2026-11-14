#!/usr/bin/env python3
"""The whole NTSC routine on one EasyFlash cartridge: part 1 .. part 4d (mk_cart_all.py's), then the gold sequence (mk_gold_ntsc.py): part 4d loads goldtilt
in the idle time of its blanks (bgload.s), plays NFE frames (the wipe ends at 1075), and goes on into goldtilt's blue bar move + fade, goldtilt, goldlight, goldorbit,
goldtwin, goldfly, then the cartridge loader (part 1 again).    python3 mk_ntsc_full.py [out.crt]"""
import os, struct, subprocess, sys
import c64build
import mk_gold_ntsc as g
NFE = 1076                         # part 4 frames shown: 0 .. 1075
PARTS = ["part1r", "part2c", "part2w", "part3c", "part4d"]
SKIP_TUNE = ("part2c", "part2w", "part3c", "part4c", "part4d")        # parts that keep the tune ($1000-$2A33) resident and put their tables at $2B00
HERE = g.HERE

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "routine_ntsc_gold.crt")
    import music_ntsc_patch
    music_ntsc_patch.ensure()
    chips, bank, table, body = [], 1, [], []
    def chip(b, addr, data):
        chips.append(b"CHIP" + struct.pack(">IHHHH", 0x2010, 2, b, addr, 0x2000) + bytes(data))
    for name in PARTS:
        flags = ["-Wa", f"-DBASE={bank}"] + (["-Wa", "-DCHAIN=1", "-Wa", f"-DNFE={NFE}"] if name == "part4d" else [])
        prg, _ = c64build.build(name, flags)
        image = b"\0" + prg[2:]
        lbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open(os.path.join(HERE, f"{name}.lbl"))}
        nb = -(-len(image) // 0x4000)
        pages = -(-len(image) // 256)
        assert pages < 256
        table.append((bank, pages, lbl["start"] | (0x8000 if name in SKIP_TUNE else 0)))
        padded = image.ljust(nb * 0x4000, b"\xff")
        for b in range(nb): body.append((bank + b, padded[b * 0x4000:(b + 1) * 0x4000]))
        bank += nb
        if os.path.exists(os.path.join(HERE, f"{name}_str.bin")):
            st = open(os.path.join(HERE, f"{name}_str.bin"), "rb").read()
            for b in range(len(st) // 0x4000): body.append((bank + b, st[b * 0x4000:(b + 1) * 0x4000]))
            bank += len(st) // 0x4000
        print(f"{name}: image {len(image)} bytes, next bank {bank}")
    # the gold sequence: part 4d's memory (the loader, its code, its pages) is what goldtilt may only write over at the switch
    jobs, report = g.make_jobs([(0x0300, 0x0400), (0x0800, 0x1000), (0x2B00, 0xB400)], [])
    joblist, gbanks, nbanks, total, nrec = g.layout(jobs, bank)
    for r in report: print(r)
    print(f"{nrec} job records, {total} bytes of gold data in banks {bank}..{nbanks - 1}")
    open(os.path.join(HERE, "cartparts.inc"), "w").write(f"NPARTS = {len(table)}\n.macro PARTS_TABLE\n" + "".join(f"        .byte {b}, {p}, <${s:04x}, >${s:04x}\n" for b, p, s in table) + ".endmacro\n")
    g.run(["ca65", "-o", "cartboot_all.o", "cartboot_all.s"])
    g.run(["ld65", "-C", "cartboot.cfg", "-o", "cartboot_all.bin", "cartboot_all.o"])
    boot = open(os.path.join(HERE, "cartboot_all.bin"), "rb").read()
    subprocess.run(["git", "checkout", "-q", "cartparts.inc", "cartboot_all.bin"], cwd=HERE)
    os.remove(os.path.join(HERE, "cartboot_all.o"))
    chip(0, 0x8000, joblist.ljust(0x2000, b"\xff")); chip(0, 0xA000, boot)
    for b, d in body: chip(b, 0x8000, d[:0x2000]); chip(b, 0xA000, d[0x2000:])
    for b in sorted(gbanks): chip(b, 0x8000, gbanks[b][:0x2000]); chip(b, 0xA000, gbanks[b][0x2000:])
    hdr = b"C64 CARTRIDGE   " + struct.pack(">IHHBB6x", 0x40, 0x0100, 32, 1, 0) + b"FLOATING ISLANDS".ljust(32, b"\0")
    open(out, "wb").write(hdr + b"".join(chips))
    print(out, len(chips) // 2 if False else len({c[10:12] for c in chips}), "banks used of 64 (highest bank %d)" % (nbanks - 1))
    for f in os.listdir(HERE):
        if f.endswith(".o"): os.remove(os.path.join(HERE, f))

if __name__ == "__main__":
    main()
