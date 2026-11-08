#!/usr/bin/env python3
"""Runs part1r.prg's update() frame by frame on the emulated 6502 (EasyFlash window at $8000-$BFFF while $01 = $37), compares the buffer
at $0500 with the generator's model, reports the worst cycles.   python3 sim_part1r.py [last_frame]"""
import pickle, sys
from c64cpu import MPU
lab = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open("part1r.lbl")}
prg = open("part1r.prg", "rb").read(); st = open("part1r_str.bin", "rb").read()
inc = open("part1r.inc").read(); IMG = 4
class Mem(list):
    def __init__(self): super().__init__([0] * 65536); self.bank = 0
    def __getitem__(self, a):
        if isinstance(a, int) and 0x8000 <= a < 0xC000 and list.__getitem__(self, 1) == 0x37:
            b = self.bank - 1 - IMG
            return st[b * 0x4000 + a - 0x8000] if 0 <= b < len(st) // 0x4000 else 0xFF
        return list.__getitem__(self, a)
    def __setitem__(self, a, v):
        if isinstance(a, int) and a == 0xDE00: self.bank = v
        list.__setitem__(self, a, v)
mpu = MPU(memory=Mem()); mem = mpu.memory
for i, b in enumerate(prg[2:]): list.__setitem__(mem, (prg[0] | prg[1] << 8) + i, b)
def call(addr, limit=200000):
    for i, v in enumerate([0x20, addr & 255, addr >> 8, 0]): list.__setitem__(mem, 0x0334 + i, v)
    mpu.pc, mpu.sp = 0x0334, 0xFF; c = mpu.processorCycles
    while mpu.pc != 0x0337:
        mpu.step()
        if mpu.processorCycles - c > limit: raise SystemExit(f"runaway at pc={mpu.pc:04x} sp={mpu.sp:02x}")
    return mpu.processorCycles - c
M = pickle.load(open("/tmp/part1r_model.pkl", "rb"))
last = int(sys.argv[1]) if len(sys.argv) > 1 else len(M["bufs"]) - 1
list.__setitem__(mem, 1, 0x35)
# start(): the part of it that matters
for k, v in (("rp", 0x00), ): pass
zp = lambda n, v: list.__setitem__(mem, lab[n], v)
zp("rp", 0); zp("rp", 0)
list.__setitem__(mem, lab["rp"], 0x00); list.__setitem__(mem, lab["rp"] + 1, 0x80)
zp("bank", 1 + IMG); zp("fcl", 0); zp("fch", 0)
list.__setitem__(mem, lab["dm"], lab["map0"] & 255); list.__setitem__(mem, lab["dm"] + 1, lab["map0"] >> 8)
import part1r_gen as G
PLAY = G.play_costs()
worst, bad, wt = (0, 0), 0, (0, 0)
for n in range(last + 1):
    c = call(lab["update"])
    worst = max(worst, (c, n)); wt = max(wt, (c + PLAY[n], n))
    got = [list.__getitem__(mem, 0x500 + i) for i in range(200)]
    if got != M["bufs"][n]:
        bad += 1
        if bad < 4: print("frame", n, "differs at rows", [i for i in range(200) if got[i] != M["bufs"][n][i]][:8])
print(f"{last + 1} frames, {bad} differ; worst update {worst[0]} cycles (frame {worst[1]}); worst update + the tune {wt[0]} (frame {wt[1]})")
