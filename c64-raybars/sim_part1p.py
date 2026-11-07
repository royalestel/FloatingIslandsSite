#!/usr/bin/env python3
"""Runs part1p.prg's update() on an emulated 6502 for every frame and compares LINEBUF with the Python spec
(part1_proc.film_buf); reports the cycles of update (budget: the blank, about 6,500 cycles).

    python3 part1p_gen.py && cl65 -g -t none -C part1p.cfg -Ln part1p.lbl -o part1p.prg part1p.s part1p_tab.s
    python3 sim_part1p.py [first last]
"""
import os, sys
from c64cpu import MPU
import part1_proc as q
import part1 as p1

HERE = os.path.dirname(os.path.abspath(__file__))
labels = {}
for ln in open(os.path.join(HERE, "part1p.lbl")):
    _, addr, name = ln.split()
    labels[name.lstrip(".")] = int(addr, 16)
prg = open(os.path.join(HERE, "part1p.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])
mem = mpu.memory
for i in range(2, 0x80):
    mem[i] = 0
TRAMP = 0x0334
BUF = 0x0400

def call(addr):
    mem[TRAMP:TRAMP + 4] = [0x20, addr & 255, addr >> 8, 0x00]
    mpu.pc, mpu.sp = TRAMP, 0xFF
    c = mpu.processorCycles
    while mpu.pc != TRAMP + 3:
        mpu.step()
    return mpu.processorCycles - c

def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else p1.T_END
    call(labels["restart"])
    if a:                                   # start in the middle: set the frame, the phase and the stream pointer
        mem[labels["fcl"]], mem[labels["fch"]] = a & 255, a >> 8
        pa = (q.PH0 + a * q.INC) & 0xFFFF
        mem[labels["pa"]], mem[labels["pa"] + 1] = pa & 255, pa >> 8
    ok, worst, wf, bad = True, 0, 0, 0
    budget = (312 - (51 + 200) + 46) * 63 - 200
    for f in range(a, b):
        c = call(labels["update"])
        got = [mem[BUF + i] for i in range(200)]
        want = q.film_buf(f)
        if c > worst: worst, wf = c, f
        if got != want:
            bad += 1
            if bad <= 5:
                diff = [i for i in range(200) if got[i] != want[i]]
                print(f"frame {f}: {len(diff)} lines differ, first {diff[:6]}: got {[got[i] for i in diff[:4]]} want {[want[i] for i in diff[:4]]}")
            ok = False
    print(f"{b - a} frames: LINEBUF equals the spec: {ok} ({bad} frames differ)")
    print(f"update(): worst {worst} cycles (frame {wf}) of about {budget} ({100 * worst / budget:.0f} %)")
    return ok and worst <= budget

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
