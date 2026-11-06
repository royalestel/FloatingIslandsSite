#!/usr/bin/env python3
"""Run anim0.prg's code on an emulated 6502 (py65 + the stable illegal opcodes).

 1. the speedcode: all 200 rows exactly 63 cycles, each row's $d020 write is
    the line buffer's byte for that line;
 2. update() for every frame of the film: its line buffer equals the generator's
    reference (anim_gen.compose_ref), and its cycles fit between the last line
    and the next frame's IRQ;
 3. renders the buffers the program makes as sim_anim0.mp4 (CRT look, 60 fps,
    384 pixels a line: the whole line is border).

    python3 anim_gen.py && cl65 -g -t none -C anim.cfg -Ln anim0.lbl -o anim0.prg anim0.s
    python3 sim_anim0.py [out.mp4] [first_frame last_frame]   (no video without a name)
"""
import os, sys
import numpy as np
from c64cpu import MPU
import anim_gen as gen

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS, ROWSIZE = 200, 34
FIRST_LINE = gen.P["FIRST_LINE"]

labels = {}
for ln in open(os.path.join(HERE, "anim0.lbl")):
    _, addr, name = ln.split()
    labels[name.lstrip(".")] = int(addr, 16)

prg = open(os.path.join(HERE, "anim0.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])
mem = mpu.memory
block, upd, buf = labels["block"], labels["update"], labels["linebuf"]

TRAMP = 0xF000
for i in range(2, 0x80):                          # start-up: clear the zero page, point at the scene
    mem[i] = 0
mem[labels["rp"]], mem[labels["rp"] + 1] = labels["scene"] & 255, labels["scene"] >> 8
mem[TRAMP:TRAMP + 4] = [0x20, upd & 255, upd >> 8, 0x00]

def run_update():
    mpu.pc, mpu.sp = TRAMP, 0xFF
    c = mpu.processorCycles
    while mpu.pc != TRAMP + 3:
        mpu.step()
    return mpu.processorCycles - c

def run_rows():
    """Execute the 200 rows; returns (cycles per row, the $d020 value written on each)."""
    mpu.pc = block
    per, written = [], []
    for r in range(ROWS):
        start, end = mpu.processorCycles, block + (r + 1) * ROWSIZE
        val = None
        while mpu.pc != end:
            op, lo, hi = mem[mpu.pc], mem[mpu.pc + 1], mem[mpu.pc + 2]
            sta_d020 = op == 0x8D and lo == 0x20 and hi == 0xD0
            mpu.step()
            if sta_d020:
                val = mem[0xD020]
        per.append(mpu.processorCycles - start)
        written.append(val)
    return per, written

def main(video=None, lo=0, hi=None):
    lists, rec, prof, off = gen.build()
    n = gen.sc.T_END
    hi = n if hi is None else hi
    ok = True
    run_update()                                     # the program's start-up call: frame 0
    first = [mem[buf + i] for i in range(ROWS)]
    worst, mx, bufs = 0, 0, []
    budget = ((312 - (FIRST_LINE + ROWS + 2)) + (FIRST_LINE - 2 - 2)) * 63 - 150
    for f in range(n):
        got = [mem[buf + i] for i in range(ROWS)]    # frame f's buffer
        want = gen.compose_ref(lists[f], f)
        if got != want:
            print(f"frame {f}: line buffer differs from the reference "
                  f"(lines {[i for i in range(ROWS) if got[i] != want[i]][:8]})")
            ok = False
            break
        if f % 61 == 0 or f in (0, n - 1):           # a sample of frames through the rows
            per, written = run_rows()
            if per != [63] * ROWS or written != got:
                print(f"frame {f}: rows: cycles {set(per)}, writes match {written == got}")
                ok = False
        if lo <= f < hi:
            bufs.append(got)
        cyc = run_update()                           # builds frame f + 1 (wraps after the last)
        mx = max(mx, cyc)
    print(f"{n} frames: line buffers match the reference: {ok}")
    print(f"rows: every sampled row 63 cycles, $d020 writes = buffer: {ok}")
    print(f"update(): worst {mx} cycles of {budget} available between the last line and "
          f"the next IRQ ({100 * mx / budget:.0f}%)")
    ok &= mx <= budget
    if video and ok:
        import flyby3d as fb
        import loop_video as lv
        import ideas_video as iv
        Wd, Z = 384, 3
        v = iv.Video(video, Wd * Z, ROWS * Z)
        for b in bufs:
            img = np.repeat(np.array(b)[:, None], Wd, axis=1)
            v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
        v.close()
        print("wrote", video, len(bufs), "frames")
    return ok

if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(0 if main(a[0] if a else None, int(a[1]) if len(a) > 2 else 0,
                       int(a[2]) if len(a) > 2 else None) else 1)
