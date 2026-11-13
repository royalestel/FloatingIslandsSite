#!/usr/bin/env python3
"""Cycles the tune's play routine costs in each blank of part 4 (NTSC): the tune runs on the 6502 simulator through the calls of the whole routine
(part 1 ... part 3, then part 4), five calls in six frames in every part (each part restarts its own counter).  The call that falls on a part 4 blank is
known only to within a call or two (the exact hand-overs are not modelled), so each blank is budgeted with the dearest call within +-WINDOW calls."""
import os, re
WINDOW = 3
def inc(name):
    return int(re.search(r"^NF = (\d+)", open(name).read(), re.M).group(1))
def part4_costs(n4):
    from c64cpu import MPU
    data = open("music/Alpha_ntsc.dat", "rb").read()
    mpu = MPU(); mem = mpu.memory
    for i, b in enumerate(data): mem[0x1000 + i] = b
    def call(addr, a=0):
        for i, v in enumerate([0x20, addr & 255, addr >> 8, 0]): mem[0x0334 + i] = v
        mpu.pc, mpu.sp, mpu.a, mpu.x, mpu.y = 0x0334, 0xFF, a, 0, 0
        c = mpu.processorCycles
        while mpu.pc != 0x0337: mpu.step()
        return mpu.processorCycles - c
    call(0x1000, 0)
    for n in range(1, inc("part1r.inc")):                               # part 1: a call in every blank but every sixth
        if n % 6: call(0x1003)
    for name in ("part2c.inc", "part2w.inc", "part3c.inc"):
        for k in range(1, inc(name)):
            if k % 6: call(0x1003)
    cost = [0] * (n4 + 8)
    for k in range(1, n4 + 8):
        if k % 6: cost[k] = call(0x1003) + 40
    return [max(cost[max(0, k - WINDOW):k + WINDOW + 1]) for k in range(n4 + 1)]
if __name__ == "__main__":
    c = part4_costs(inc("part4c.inc"))
    print(len(c), "blanks: mean %d, max %d, min %d" % (sum(c) / len(c), max(c), min(c)))
