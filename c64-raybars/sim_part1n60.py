#!/usr/bin/env python3
"""NTSC 60 Hz part 1: runs part1n.prg's update() for every frame on the emulated 6502, with the EasyFlash banks
($de00 picks the 16 KB bank shown at $8000-$BFFF while $01 = $37), compares LINEBUF with the generator's model
(/tmp/part1n_bufs.pkl) and reports the worst update (budget: about 3,600 cycles of the NTSC blank)."""
import pickle, sys
from c64cpu import MPU
lab = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open("part1n.lbl")}
prg = open("part1n.prg", "rb").read()
st = open("part1n_str.bin", "rb").read()
IMG = 4
class Mem(list):
    def __init__(self):
        super().__init__([0] * 65536); self.bank = 0
    def __getitem__(self, a):
        if isinstance(a, int) and 0x8000 <= a < 0xC000 and list.__getitem__(self, 1) == 0x37:
            b = self.bank - 1 - IMG
            return st[b * 0x4000 + a - 0x8000] if 0 <= b < len(st) // 0x4000 else 0xFF
        return list.__getitem__(self, a)
    def __setitem__(self, a, v):
        if isinstance(a, int) and a == 0xDE00: self.bank = v
        list.__setitem__(self, a, v)
mpu = MPU(memory=Mem()); mem = mpu.memory
load = prg[0] | prg[1] << 8
for i, b in enumerate(prg[2:]): list.__setitem__(mem, load + i, b)
def call(addr):
    mem[0x0334:0x0338] = [0x20, addr & 255, addr >> 8, 0]
    for i, v in enumerate([0x20, addr & 255, addr >> 8, 0]): list.__setitem__(mem, 0x0334 + i, v)
    mpu.pc, mpu.sp = 0x0334, 0xFF; c = mpu.processorCycles
    while mpu.pc != 0x0337: mpu.step()
    return mpu.processorCycles - c
bufs = pickle.load(open("/tmp/part1n_bufs.pkl", "rb"))
list.__setitem__(mem, 1, 0x35)
call(lab["restart"])
worst, bad = (0, 0), 0
for n in range(len(bufs) - 1):            # (the last frame jumps to the chain)
    c = call(lab["update"])
    worst = max(worst, (c, n))
    got = [list.__getitem__(mem, 0x400 + i) for i in range(200)]
    if got != bufs[n]:
        bad += 1
        if bad < 4: print("frame", n, "differs at", [i for i in range(200) if got[i] != bufs[n][i]][:8])
print(f"{len(bufs) - 1} frames, {bad} differ; worst update {worst[0]} cycles (frame {worst[1]})")
