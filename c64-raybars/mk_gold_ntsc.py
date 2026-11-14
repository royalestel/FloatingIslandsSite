#!/usr/bin/env python3
"""The NTSC gold sequence for the EasyFlash cartridge: goldtilt -> goldlight -> goldorbit -> goldtwin -> goldfly, each loaded in the
background while the one before it runs (bgload.s), each started on the frame after the last one's last (GOLD_NTSC_PLAN.md).

  python3 mk_gold_ntsc.py [out.crt]       a test cartridge: goldboot (loader, tune) + the sequence, then the cartridge loader ($0200)

Every routine is linked to its own memory (LAYOUT) and its image is a SNAPSHOT: the program is run on the 6502 simulator from `start` to
`resume` (zero page cleared, columns, sprites, the raster code patched for its first frame, the hardware registers it set).  The bytes
the routine before it may still be using (its memory, its sprites, the zero page, the VIC and CIA registers, the vectors) are copied at
the switch; everything else in the background.  The job list goes to bank 0 ROML ($8000).
"""
import os, struct, subprocess, sys
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = "/tmp/gold_ntsc"
SHARED = (0xE000, 0xFFFA)            # goldshared.inc
HLRUN = (0x4000, 0x5000)             # hlrun.inc

# routine, its defines (the sequence's start phases: mock_gold_seq.py), frames shown, memory areas {name: (start, end, [segments])}
SEQ = [
    ("goldtilt", ["PH_ORBIT=228", "PH_TILT=164"], 270, {
        "T1": (0xB400, 0xD000, ["CODE", "RASTER", "TABLES", "RAMPS", "BSS"])}),
    ("goldlight", ["PH_ORBIT=242", "PH_TILT=178", "PH_LXA=196", "PH_LYA=197"], 360, {
        "L1": (0x2B00, 0x3D40, ["CODE", "TABLES", "RAMPS"]),
        "L3": (0x0500, 0x07F8, ["BSS"]),
        "L2": (0x0800, 0x1000, ["RASTER"]),
        "HL": (HLRUN[0], HLRUN[1], ["HIGHTAB"])}),
    ("goldorbit", ["PH_ORBIT=90", "PH_TILT=26", "PH_LXA=45", "PH_LYA=250", "PH_Q=254", "SPRBUF0=$0400", "SPRBUF1=$0440"], 360, {
        "O1": (0x5000, 0x8000, ["CODE", "RASTER", "TABLES", "RAMPS", "BSS"]),
        "HL": (HLRUN[0], HLRUN[1], ["HIGHTAB"])}),
    ("goldtwin", ["PH_ORBIT=194", "PH_TILT=130", "PH_LXA=0", "PH_LXF=255", "PH_Q=102", "PH_TW=0", "PH_BT=254"], 656, {
        "W1": (0x8800, 0xB400, ["CODE", "RASTER"]),
        "W2": (0xB400, 0xBFFF, ["RAMPS", "BSS"]),
        "W3": (0xC000, 0xD000, ["TABLES"]),
        "HL": (HLRUN[0], HLRUN[1], ["HLRUN"])}),
    ("goldfly", ["SPRBUF=$8080"], 360, {
        "F1": (0x5000, 0x6E00, ["RAMPS"]),
        "F2": (0x6E00, 0x8000, ["CODE", "RASTER", "BSS"]),
        "F3": (0x2B00, 0x4000, ["TABLES"]),
        "HL": (HLRUN[0], HLRUN[1], ["HLRUN"])}),
]
# what each routine keeps writing while it runs, outside its image (sprite buffers, the sprite pointer, the idle byte)
RUNTIME = {
    "goldtilt": [],
    "goldlight": [(0x3D40, 0x4000), (0x07F8, 0x07F9)],
    "goldorbit": [(0x0400, 0x0480), (0x07F8, 0x07F9), (0x3FFF, 0x4000)],
    "goldtwin": [(0x8000, 0x8080), (0x87F8, 0x87F9), (0xBFFF, 0xC000)],
    "goldfly": [(0x8080, 0x80C0), (0x87F8, 0x87F9), (0xBFFF, 0xC000)],
}
VIC = (0xD000, 0xD02F)
CIA2 = (0xDD00, 0xDD03)
VECTORS = (0xFFFA, 0x10000)
ZP = (0x0002, 0x0080)
NIRQ = 0xEF

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    if r.returncode: sys.exit(" ".join(cmd) + "\n" + r.stdout + r.stderr)
    return r.stdout + r.stderr

def link(name, defs, areas):
    """assemble <name>_ntsc.s with CHAIN=1, link it to its areas; returns {address: byte} of the areas, labels"""
    os.makedirs(TMP, exist_ok=True)
    mem = ["    ZP: start = $0002, size = $007E, type = rw;", "    DUMMY: start = $0000, size = $0100, file = \"\";"]
    seg = ["    ZEROPAGE: load = ZP, type = zp;", "    LOADADDR: load = DUMMY, type = ro;", "    EXEHDR: load = DUMMY, type = ro;"]
    shared = {"SH": (SHARED[0], SHARED[1], ["SHARED"])}
    for an, (a, b, segs) in list(areas.items()) + list(shared.items()):
        mem.append(f"    {an}: start = ${a:04X}, size = ${b - a:04X}, file = \"{TMP}/{name}_{an}.bin\";")
        for s in segs:
            align = "" if s in ("CODE",) else ", align = $100"
            seg.append(f"    {s}: load = {an}, type = rw{align}, optional = yes;")
    cfg = f"{TMP}/{name}.cfg"
    open(cfg, "w").write("MEMORY {\n" + "\n".join(mem) + "\n}\nSEGMENTS {\n" + "\n".join(seg) + "\n}\n")
    flags = []
    for d in ["CHAIN=1", f"ENDF={dict(SEQ_ENDF)[name]}"] + defs:
        flags += ["-Wa", f"-D{d}"]
    run(["cl65", "-g", "-t", "none", *flags, "-C", cfg, "-m", f"{TMP}/{name}.map", "-Ln", f"{TMP}/{name}.lbl", "-o", f"{TMP}/{name}.out", f"{name}_ntsc.s"])
    for f in os.listdir(HERE):
        if f.endswith(".o"): os.remove(os.path.join(HERE, f))
    lbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open(f"{TMP}/{name}.lbl")}
    image = {}
    for an, (a, b, _) in list(areas.items()) + list(shared.items()):
        p = f"{TMP}/{name}_{an}.bin"
        data = open(p, "rb").read() if os.path.exists(p) else b""
        assert len(data) <= b - a, (name, an)
        for i, v in enumerate(data): image[a + i] = v
    return image, lbl

SEQ_ENDF = [(n, e) for n, _, e, _ in SEQ]

def snapshot(name, image, lbl):
    """run start .. resume on the simulator; returns the memory and the set of addresses written"""
    written = set()
    mem = ObservableMemory()
    for a, v in image.items(): mem[a] = v
    mem.subscribe_to_write(range(0x10000), lambda addr, val: written.add(addr))
    mpu = MPU(memory=mem)
    mpu.pc, mpu.sp = lbl["start"], 0xFF
    steps = 0
    while mpu.pc != lbl["resume"]:
        mpu.step(); steps += 1
        assert steps < 5_000_000, f"{name}: start does not reach resume"
    return mem, written

def ranges(addrs):
    """sorted addresses -> [(start, end)] contiguous runs"""
    out = []
    for a in sorted(addrs):
        if out and out[-1][1] == a: out[-1][1] = a + 1
        else: out.append([a, a + 1])
    return [tuple(r) for r in out]

def inside(a, rs):
    return any(lo <= a < hi for lo, hi in rs)

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "gold_ntsc.crt")
    import music_ntsc_patch
    music_ntsc_patch.ensure()
    tune = open(os.path.join(HERE, "music", "Alpha_ntsc.dat"), "rb").read()
    os.makedirs(TMP, exist_ok=True)
    # --- goldboot: the first part (the cartridge loader puts it at $0801) ---
    run(["cl65", "-g", "-t", "none", "-C", "goldboot.cfg", "-Ln", f"{TMP}/goldboot.lbl", "-o", f"{TMP}/goldboot.prg", "goldboot.s"])
    for f in os.listdir(HERE):
        if f.endswith(".o"): os.remove(os.path.join(HERE, f))
    blbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open(f"{TMP}/goldboot.lbl")}
    boot_prg = open(f"{TMP}/goldboot.prg", "rb").read()
    # --- the job list: (kind, ...) ---
    jobs = []             # ("copy", dst, bytes) | ("switch",) | ("start", addr)
    jobs.append(("switch",))
    jobs.append(("copy", 0x1000, tune))
    jobs.append(("start", blbl["tinit"]))
    prev_live = [(0x0801, 0x0900)]          # goldboot (its code, until goldtilt starts)
    loaded = {}                              # shared bytes already loaded
    report = []
    for name, defs, endf, areas in SEQ:
        image, lbl = link(name, defs, areas)
        mem, written = snapshot(name, image, lbl)
        own = set(image)
        extras = {a for a in written if not (a < 0x200 or 0xD000 <= a < 0xE000 or VECTORS[0] <= a or a in own)}
        allb = {a: mem[a] for a in own | extras}
        shared_rs = [SHARED, HLRUN]
        bg, sw = {}, {}
        for a, v in allb.items():
            if inside(a, shared_rs):
                if a in loaded:
                    assert loaded[a] == v, f"{name}: shared byte ${a:04X} differs"
                    continue
                loaded[a] = v
            (sw if inside(a, prev_live) else bg)[a] = v
        for a in range(*ZP): sw[a] = mem[a]
        sw[NIRQ] = mem[NIRQ]
        for a in list(range(*VIC)) + list(range(*CIA2)) + list(range(*VECTORS)):
            if a in written: sw[a] = mem[a]  # (only what start wrote: the rest stays as the hardware has it)
        sw[0xD019] = 0x0F                    # acknowledge whatever is pending
        def recs(d):
            return [("copy", lo, bytes(d[a] for a in range(lo, hi))) for lo, hi in ranges(d)]
        jobs += recs(bg)
        jobs.append(("switch",))
        data_sw = {a: v for a, v in sw.items() if not (0xD000 <= a < 0xE000 or VECTORS[0] <= a)}
        io_sw = {a: v for a, v in sw.items() if (0xD000 <= a < 0xE000 or VECTORS[0] <= a)}
        jobs += recs(data_sw) + recs(io_sw)
        jobs.append(("start", lbl["resume"]))
        nsw = sum(len(v) for a, b, v in [(j[0], j[1], j[2]) for j in recs(sw)])
        report.append(f"{name}: image {len(own)} bytes + {len(extras)} written outside it; background {len(bg)}, at the switch {nsw} "
                      f"({len(data_sw) - 0x7E - 1} besides the zero page)")
        prev_live = [(a, b) for (a, b, _) in areas.values()] + RUNTIME[name] + [SHARED]
    jobs.append(("start", 0x0200))           # the end: the cartridge loader (part 1 again)
    # --- the cartridge: bank 0 ROML = the job list, ROMH = the boot; bank 1 = goldboot; banks 2.. = the data ---
    import vice_gold
    data, recbytes, bank, off = [], [], 2, 0
    def place(buf):
        nonlocal bank, off
        out = []
        i = 0
        while i < len(buf):
            n = min(len(buf) - i, 0x4000 - off)
            out.append((bank, 0x8000 + off, i, n))
            data.append((bank, off, buf[i:i + n]))
            off += n; i += n
            if off == 0x4000: bank += 1; off = 0
        return out
    for j in jobs:
        if j[0] == "copy":
            dst, buf = j[1], j[2]
            for b, src, i, n in place(buf):
                recbytes.append(struct.pack("<BHHHB", b, src, dst + i, n, 0))
        elif j[0] == "switch":
            recbytes.append(bytes([0xFD] + [0] * 7))
        else:
            recbytes.append(bytes([0xFF, j[1] & 255, j[1] >> 8] + [0] * 5))
    joblist = b"".join(recbytes)
    assert len(joblist) <= 0x2000, "job list over 8 KB"
    nbanks = bank + (1 if off else 0)
    banks = {}
    for b, o, d in data:
        banks.setdefault(b, bytearray(b"\xff" * 0x4000))[o:o + len(d)] = d
    # goldboot as cartridge part 1 (bank 1): the loader's image starts at $0800
    image = b"\0" + boot_prg[2:]
    pages = -(-len(image) // 256)
    open(os.path.join(HERE, "cartparts.inc"), "w").write(f"NPARTS = 1\n.macro PARTS_TABLE\n        .byte 1, {pages}, <${blbl['start']:04x}, >${blbl['start']:04x}\n.endmacro\n")
    run(["ca65", "-o", "cartboot_all.o", "cartboot_all.s"])
    run(["ld65", "-C", "cartboot.cfg", "-o", "cartboot_all.bin", "cartboot_all.o"])
    bootbin = open(os.path.join(HERE, "cartboot_all.bin"), "rb").read()
    subprocess.run(["git", "checkout", "-q", "cartparts.inc", "cartboot_all.bin"], cwd=HERE)
    os.remove(os.path.join(HERE, "cartboot_all.o"))
    chips = []
    def chip(b, addr, d):
        chips.append(b"CHIP" + struct.pack(">IHHHH", 0x2010, 2, b, addr, 0x2000) + bytes(d))
    chip(0, 0x8000, joblist.ljust(0x2000, b"\xff")); chip(0, 0xA000, bootbin)
    b1 = image.ljust(0x4000, b"\xff")
    chip(1, 0x8000, b1[:0x2000]); chip(1, 0xA000, b1[0x2000:])
    for b in sorted(banks):
        chip(b, 0x8000, banks[b][:0x2000]); chip(b, 0xA000, banks[b][0x2000:])
    hdr = b"C64 CARTRIDGE   " + struct.pack(">IHHBB6x", 0x40, 0x0100, 32, 1, 0) + b"GOLD NTSC".ljust(32, b"\0")
    open(out, "wb").write(hdr + b"".join(chips))
    for r in report: print(r)
    total = sum(len(d) for _, _, d in data)
    print(f"{len(recbytes)} job records, {total} bytes of data in banks 2..{nbanks - 1} ({total / 16384:.2f} banks of 16 KB, the tune included: {len(tune)})")
    print("wrote", out)

if __name__ == "__main__":
    main()
