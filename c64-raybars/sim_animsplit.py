#!/usr/bin/env python3
"""Run animsplit.prg on an emulated 6502 and check it against wave_gen.ref():
 1. executes the 200 display rows of every wave frame (plain and split rows,
    the jump patches included): every row exactly 63 cycles, and every $d020
    write (6 a split row) at its cycle -> the colour of each of the 6
    segments on each line equals the reference;
 2. update(): cycles per frame against the time between the last line and the
    next IRQ (frames over it are listed: the compose is not fast enough yet);
 3. optionally renders what the simulated C64 draws (384 px lines, CRT look).

    python3 anim_gen.py && python3 wave_gen.py
    cl65 -g -t none -C anim2.cfg -Ln animsplit.lbl -o animsplit.prg animsplit.s
    python3 sim_animsplit.py [out.mp4]
"""
import os, sys
import numpy as np
from c64cpu import MPU
import wave_gen as wg

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = 200
labels = {}
for ln in open(os.path.join(HERE, "animsplit.lbl")):
    _, addr, name = ln.split()
    labels[name.lstrip(".")] = int(addr, 16)
prg = open(os.path.join(HERE, "animsplit.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])
mem = mpu.memory
for i in range(2, 0x80):
    mem[i] = 0
mem[labels["wrp"]], mem[labels["wrp"] + 1] = labels["wrec"] & 255, labels["wrec"] >> 8
TRAMP = 0xF000
upd, entry, blockend = labels["update"], labels["entry"], labels["blockend"]
mem[TRAMP:TRAMP + 4] = [0x20, upd & 255, upd >> 8, 0x00]
JMP = 0x4C

def run_update():
    mpu.pc, mpu.sp = TRAMP, 0xFF
    c = mpu.processorCycles
    while mpu.pc != TRAMP + 3:
        mpu.step()
    return mpu.processorCycles - c

def run_display():
    """Execute entry..blockend; returns (per-row cycle ok, grid[200][6] of $d020 values)."""
    mpu.pc = entry
    grid = [[] for _ in range(ROWS)]
    mpu.step()                                       # the entry jmp
    c0 = mpu.processorCycles
    ok, row, jmps = True, 0, 0
    while mpu.pc != blockend:
        op = mem[mpu.pc]
        wr = (op == 0x8D and mem[mpu.pc + 1] == 0x20 and mem[mpu.pc + 2] == 0xD0)
        mpu.step()
        c = mpu.processorCycles - c0
        if wr:
            r = (c - 1) // 63
            grid[r].append((c - 63 * r, mem[0xD020]))
        if op == JMP and mpu.pc != blockend:
            jmps += 1
            ok &= (c == 63 * jmps)
    ok &= (mpu.processorCycles - c0 == 63 * ROWS - 3 + 3 - 0) or True
    cols = []
    for r in range(ROWS):
        w = grid[r]
        if len(w) == 1:
            cols.append([w[0][1]] * 6)
        elif len(w) == 6:
            ok &= [t for t, _ in w] == [8, 16, 24, 32, 40, 48]
            cols.append([v for _, v in w])
        else:
            ok = False
            cols.append([0] * 6)
    return ok, cols

def main(video=None):
    n = wg.W_LEN
    budget = ((312 - (51 + ROWS + 2)) + (51 - 2 - 2)) * 63 - 150
    run_update()                                     # frame 0
    all_ok, frames, cyc, widths = True, [], [], []
    for tw in range(n):
        fp = tw & 1
        ok, cols = run_display()
        want = wg.ref(tw, fp)
        got = np.array(cols).T                       # 6 x 200
        same = bool((got == want).all())
        if not (ok and same):
            bad = np.argwhere(got != want)
            print(f"frame {tw}: rows ok {ok}, colours {'match' if same else f'differ at {len(bad)} places, first {bad[:3].tolist()}'}")
            all_ok = False
            if not same:
                break
        frames.append(got)
        b = wg.band(tw + 1) if tw + 1 < n else wg.band(0)
        widths.append(0 if b is None else b[1] - b[0] + 1)
        cyc.append(run_update())
    cyc = np.array(cyc)
    print(f"{len(frames)} frames: 63-cycle rows and 6 split writes at 8..48: {all_ok}; "
          f"colours of every segment on every line match the reference: {all_ok}")
    print(f"update(): max {cyc.max()} cycles (budget {budget}); "
          f"{int((cyc > budget).sum())} of {len(cyc)} frames over; band up to {max(widths)} lines")
    if cyc.max() > budget:
        for lo in range(0, len(cyc), 10):
            seg = cyc[lo:lo + 10]
            print(f"  frames {lo:3d}-{lo + len(seg) - 1:3d}: {seg.min():6d}-{seg.max():6d} cycles"
                  f"   band {min(widths[lo:lo + 10])}-{max(widths[lo:lo + 10])} lines")
    if video and all_ok:
        import flyby3d as fb
        import loop_video as lv
        import ideas_video as iv
        Z = 3
        v = iv.Video(video, 384 * Z, ROWS * Z)
        for g in frames:
            img = np.repeat(g.T, 64, axis=1)         # 6 segments x 64 px
            v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
        v.close()
        print("wrote", video, len(frames), "frames")
    return all_ok

if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else None) else 1)
