#!/usr/bin/env python3
"""Run part1.prg's code on an emulated 6502: every frame's line buffer against the Python
model (part1_gen.compose_ref), the 200 rows of sampled frames (cycles per row, the idle byte
and $d021 each row writes against the swatch tables), and update()'s cycle count against the
time between the last line and the irq0 of the next frame.

    python3 part1_gen.py && cl65 -g -t none -C part1.cfg -Ln part1.lbl -o part1.prg part1.s
    python3 sim_part1.py
"""
import os, sys
from c64cpu import MPU
import part1_gen as gen

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS, ROWSIZE = 200, 20
labels = {}
for ln in open(os.path.join(HERE, "part1.lbl")):
    _, addr, name = ln.split()
    labels[name.lstrip(".")] = int(addr, 16)
prg = open(os.path.join(HERE, "part1.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])
mem = mpu.memory
for i in range(2, 0x80):
    mem[i] = 0
mem[labels["rp"]], mem[labels["rp"] + 1] = labels["scene"] & 255, labels["scene"] >> 8
TRAMP = 0x0334
upd, buf = labels["update"], 0x0400
mem[TRAMP:TRAMP + 4] = [0x20, upd & 255, upd >> 8, 0x00]
COL, GH = gen.tables()

def run_update():
    mpu.pc, mpu.sp = TRAMP, 0xFF
    c = mpu.processorCycles
    while mpu.pc != TRAMP + 3:
        mpu.step()
    return mpu.processorCycles - c

def run_rows(fp):
    """Execute the 200 rows of the frame-parity set; returns (cycles per row, [(idle, d021)])."""
    base = labels["rows1" if fp else "rows0"]
    mpu.pc = base
    per, writes = [], []
    for n in range(ROWS):
        start, end = mpu.processorCycles, base + (n + 1) * ROWSIZE
        w = {}
        while mpu.pc != end:
            op, lo, hi = mem[mpu.pc], mem[mpu.pc + 1], mem[mpu.pc + 2]
            sta = op == 0x8D
            mpu.step()
            if sta and hi == 0x3F and lo == 0xFF:
                w["idle"] = mem[0x3FFF]
            if sta and hi == 0xD0 and lo == 0x21:
                w["bg"] = mem[0xD021]
        per.append(mpu.processorCycles - start)
        writes.append((w.get("idle"), w.get("bg")))
    return per, writes

def main():
    lists, rec0, rec1, prof = gen.build()
    n = gen.p1.T_END
    run_update()                                          # frame 0
    ok, worst = True, 0
    budget = (312 - (51 + ROWS) + 46) * 63 - 200
    for f in range(n):
        got = [mem[buf + i] for i in range(ROWS)]
        want = gen.compose_ref(lists[f], f)
        if got != want:
            print(f"frame {f}: line buffer differs at lines {[i for i in range(ROWS) if got[i] != want[i]][:6]}")
            ok = False
            break
        if f % 83 == 0 or f == n - 1:
            fp = f & 1
            entry = labels["entry"]
            tgt = mem[entry + 1] | mem[entry + 2] << 8
            if tgt != labels["rows1" if fp else "rows0"]:
                print(f"frame {f}: entry points at {tgt:#x}, not the row set for parity {fp}")
                ok = False
            per, writes = run_rows(fp)
            exp = [(GH[fp * 2 + (i & 1)][got[i]] & 255, COL[fp * 2 + (i & 1)][got[i]]) for i in range(ROWS)]
            if per != [63] * ROWS or writes != exp:
                bad = [i for i in range(ROWS) if writes[i] != exp[i]][:4]
                print(f"frame {f}: rows: cycles {set(per)}, writes differ at {bad}")
                ok = False
        worst = max(worst, run_update())
    print(f"{n} frames: line buffers equal the model: {ok}")
    print(f"rows: every sampled row 63 cycles, idle byte and $d021 writes equal the swatch tables: {ok}")
    print(f"update(): worst {worst} cycles of about {budget} between the last line and irq0 "
          f"({100 * worst / budget:.0f}%)")
    return ok and worst <= budget

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
