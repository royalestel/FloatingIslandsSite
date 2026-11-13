#!/usr/bin/env python3
"""Runs part4d.prg's update() frame by frame on the emulated 6502 (EasyFlash window at $8000-$BFFF while $01 = $37) and compares what the raster loop
would read (the 7 page operands and the page bytes, rows F..184) with the generator's frames (/tmp/part4d_shown.pkl).   python3 sim_part4d.py [last_frame]"""
import pickle, sys
import numpy as np
from c64cpu import MPU
lab = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open("part4d.lbl")}
prg = open("part4d.prg", "rb").read(); st = open("part4d_str.bin", "rb").read()
IMG = 1
class Mem(list):
    def __init__(self): super().__init__([0] * 65536); self.bank = 0; self.ras = 0
    def __getitem__(self, a):
        if isinstance(a, int) and a == 0xD012: self.ras = (self.ras + 7) & 255; return self.ras      # a raster counter that moves
        if isinstance(a, int) and 0x8000 <= a < 0xC000 and list.__getitem__(self, 1) == 0x37:
            b = self.bank - 1 - IMG
            return st[b * 0x4000 + a - 0x8000] if 0 <= b < len(st) // 0x4000 else 0xFF
        return list.__getitem__(self, a)
    def __setitem__(self, a, v):
        if isinstance(a, int) and a == 0xDE00: self.bank = v
        list.__setitem__(self, a, v)
mpu = MPU(memory=Mem()); mem = mpu.memory
for i, b in enumerate(prg[2:]): list.__setitem__(mem, (prg[0] | prg[1] << 8) + i, b)
def call(addr, limit=400000):
    for i, v in enumerate([0x20, addr & 255, addr >> 8, 0]): list.__setitem__(mem, 0x0334 + i, v)
    mpu.pc, mpu.sp = 0x0334, 0xFF; c = mpu.processorCycles
    while mpu.pc != 0x0337:
        mpu.step()
        if mpu.processorCycles - c > limit: raise SystemExit(f"runaway at pc={mpu.pc:04x} sp={mpu.sp:02x}")
    return mpu.processorCycles - c
shown = pickle.load(open("/tmp/part4d_shown.pkl", "rb"))
last = int(sys.argv[1]) if len(sys.argv) > 1 else len(shown) - 1
zp = lambda n, v: list.__setitem__(mem, lab[n], v)
list.__setitem__(mem, 1, 0x35)
zp("fcl", 0); zp("fch", 0); zp("sp", 0x00); zp("sp", 0x00); list.__setitem__(mem, lab["sp"] + 1, 0x80); zp("bank", 1 + IMG)
for a in range(0x2B00, 0x2C00): list.__setitem__(mem, a, 0)               # (start zeroes the zero page)
bad, worst = 0, (0, 0); tot = 0
for t in range(last + 1):
    c = call(lab["update"])
    worst = max(worst, (c, t)); tot += c
    F = list.__getitem__(mem, lab["nf"])
    hi = [list.__getitem__(mem, lab[f"rP{k}"] + 2) for k in range(6)] + [list.__getitem__(mem, lab["rG"] + 2)]
    got = np.zeros((200, 7), np.uint8)
    for y in range(F, 185):
        for k in range(6): got[y, k] = list.__getitem__(mem, (hi[k] << 8) + y)
        got[y, 6] = list.__getitem__(mem, (hi[6] << 8) + y + 1) if y < 184 else 0       # (the idle byte of row y is read in row y - 1: lda page+1,x)
    exp = shown[t].copy()
    # the idle byte row y is written during row y-1 from page[y]; compare the idle byte of rows F..184 (row F's comes from update itself)
    gi = np.zeros(200, np.uint8)
    for y in range(F, 185): gi[y] = list.__getitem__(mem, (hi[6] << 8) + y)
    got[:, 6] = gi
    if F != int(np.where(exp.any(axis=1))[0][0]) if exp.any() else False: pass
    if not (got[F:185] == exp[F:185]).all():
        bad += 1
        if bad < 4: print("frame", t, "F", F, "differs at rows", [y for y in range(F, 185) if (got[y] != exp[y]).any()][:10], "hi", hi)
print(f"{last + 1} frames, {bad} differ; worst update {worst[0]} cycles (frame {worst[1]}), mean {tot // (last + 1)}")
