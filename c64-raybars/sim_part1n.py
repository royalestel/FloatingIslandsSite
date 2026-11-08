#!/usr/bin/env python3
"""NTSC part 1: runs the even/odd blanks of part1p.prg, compares each finished buffer with the spec, reports the worst blank (budget ~3,700 cycles)"""
import sys
import sim_part1p as s
import part1_proc as q, part1 as p1
L, mem, call = s.labels, s.mem, s.call
b = int(sys.argv[1]) if len(sys.argv) > 1 else p1.T_END - 1
call(L["restart"]); call(L["ework"]); call(L["owork"]); call(L["ework"]); mem[L["ph"]] = 1
worst = [0, 0]; bad = 0
def fcl(): return mem[L["fcl"]] | mem[L["fch"]] << 8
print("frame0 buf ok:", [mem[0x400 + i] for i in range(200)] == q.film_buf(0))
for f in range(1, b):
    for k in (1, 0):                              # odd blank finishes frame f, then the even blank
        c = call(L["blank"])
        worst[k] = max(worst[k], c)
        if k == 1:
            base = 0x400 if f % 2 == 0 else 0x600
            got = [mem[base + i] for i in range(200)]
            if got != q.film_buf(f):
                bad += 1
                if bad < 4: print("frame", f, "differs")
print("bad frames", bad, "worst odd", worst[1], "worst even", worst[0])
