#!/usr/bin/env python3
"""Run goldfly.prg's frame building on an emulated 6502 (py65).

Checks: every bar row loop is exactly 63 cycles; no column read crosses a
page; scheduled blocks (overlapping bars merged into one) never share lines
with each other or with the light's sprite; the first bar's IRQ comes after
the top IRQ; and the build fits in the frame's free time.  Renders preview_goldfly.gif / .png.

    cl65 -g -t none -C raybars.cfg -Ln goldfly.lbl -o goldfly.prg goldfly.s
    python3 sim_goldfly.py
"""
import os, sys
from py65.devices.mpu6502 import MPU
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES, NSLOT, SEGS, LINE = int(os.environ.get("FRAMES", 600)), 3, 5, 63
SPRY, SPRX = 150 - 11, 184 - 12
TOP, BOTTOM = 40, 270

PAL = [0x000000, 0xFFFFFF, 0x894036, 0x7ABFC7, 0x8A46AE, 0x68A941, 0x3E31A2,
       0xD0DC71, 0x905F25, 0x5C4700, 0xBB776D, 0x555555, 0x808080, 0xACEA88,
       0x7C70DA, 0xABABAB]
RGB = [((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in PAL]

L = {}
for ln in open(os.path.join(HERE, "goldfly.lbl")):
    _, a, nme = ln.split()
    L[nme.lstrip(".")] = int(a, 16)
prg = open(os.path.join(HERE, "goldfly.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])
mem = mpu.memory

# --- 1. the bar row loops: 63 cycles per row --------------------------------
ok = True
for sl in range(NSLOT):
    for k in range(SEGS):                       # point every pointer at a column
        p = L["cols"] + k * 256
        mem[L["ptr"] + (sl * SEGS + k) * 2] = p & 255
        mem[L["ptr"] + (sl * SEGS + k) * 2 + 1] = p >> 8
    blk = L[f"blk{sl}"]
    mpu.pc, mpu.x, mpu.y = blk, 10, 0
    c0, rows = mpu.processorCycles, []
    while mpu.pc != L["bexit"]:
        if mpu.pc == blk:
            rows.append(mpu.processorCycles)
        mpu.step()
    per = [b - a for a, b in zip(rows, rows[1:])]
    ok &= all(c == LINE for c in per)
print("bar row loops: every row 63 cycles:", ok)

# --- 2. build frames -------------------------------------------------------------
TRAMP = 0xC000
def call(addr):
    mem[TRAMP:TRAMP + 4] = [0x20, addr & 255, addr >> 8, 0x00]
    mpu.pc, mpu.sp = TRAMP, 0xFF
    c = mpu.processorCycles
    while mpu.pc != TRAMP + 3:
        mpu.step()
    return mpu.processorCycles - c

# run the program's own start-up (it builds the first frame) up to its main loop
mpu.pc, mpu.sp = L["start"], 0xFF
while mpu.pc != L["main"]:
    mpu.step()
mem[L["buf"]] = mem[L["nbuf"]] ^ 1
mem[L["ready"]] = 0

frames, worst, pagecross, overlap, sprite_hit, early = [], 0, 0, 0, 0, 0
merged, dropped, badmerge = 0, 0, 0
for f in range(FRAMES):
    cyc = call(L["build"])
    cnt = mem[L["ncount"]]
    nvis = sum(mem[L["vis"] + i] for i in range(NSLOT))
    merged += nvis - cnt == 1
    dropped += nvis - cnt > 1
    ents = []
    for i in range(cnt):
        line, slot = mem[L["nline"] + i], mem[L["nslot"] + i]
        n, ys = mem[L["nnrows"] + i], mem[L["nystart"] + i]
        ptrs = [mem[L["nptr"] + (slot * SEGS + k) * 2] |
                mem[L["nptr"] + (slot * SEGS + k) * 2 + 1] << 8 for k in range(SEGS)]
        rows = []
        for r in range(n):
            y = ys + r
            row = []
            for p in ptrs:
                if (p + y) >> 8 != p >> 8:
                    pagecross += 1
                row.append(mem[p + y])
            rows.append(row)
        ents.append((line, n, rows))
        # sprite rows SPRY+1..SPRY+21, its DMA one line earlier; IRQ lines too
        if line <= SPRY + 21 and line + 2 + n > SPRY - 1:
            sprite_hit += 1
        early += line < 58
    # merged blocks: every line must match the two bars' own columns, the
    # nearer bar's rows in front
    vis = [s_ for s_ in range(NSLOT) if mem[L["vis"] + s_]]
    for i in range(cnt):
        near = mem[L["nslot"] + i]
        line, n, rows = ents[i]
        D0 = line + 2
        for far in vis:
            if far == near or far in [mem[L["nslot"] + j] for j in range(cnt)]:
                continue
            if not (mem[L["vD"] + far] < D0 + n and mem[L["vE"] + far] > D0):
                continue
            BASE = 72
            for r in range(n):
                ln = D0 + r
                for k in range(SEGS):
                    def cell(sl):
                        idx = mem[L["vpl"] + sl * SEGS + k] + ln - mem[L["vD"] + sl]
                        return mem[mem[L["vcp"] + sl * SEGS + k] * 256 + idx], idx
                    cn, ni = cell(near)
                    if BASE <= ni < BASE + mem[L["vh"] + near]:
                        want = cn
                    elif mem[L["vD"] + far] <= ln < mem[L["vE"] + far]:
                        want = cell(far)[0]
                    elif mem[L["vD"] + near] <= ln < mem[L["vE"] + near]:
                        want = 0
                    else:
                        want = 0
                    badmerge += rows[r][k] != want
    for (l1, n1, _), (l2, n2, _) in zip(ents, ents[1:]):
        if l2 < l1 + 2 + n1 + 2:
            overlap += 1
    shown = sum(n + 3 for _, n, _ in ents)
    budget = (312 - 12 - shown) * LINE - 300
    worst = max(worst, 100 * cyc / budget)
    ok &= cyc <= budget
    frames.append(ents)
    # the top IRQ swaps the buffers
    mem[L["buf"]] = mem[L["nbuf"]] ^ 1
    mem[L["ready"]] = 0
ok &= pagecross == 0 and overlap == 0 and sprite_hit == 0 and early == 0
ok &= dropped == 0 and badmerge == 0
print('merged cells not matching the two bars:', badmerge)
print(f"build(): worst {worst:.0f}% of the frame's free time")
print(f"page-crossing reads {pagecross}, overlapping bars {overlap}, "
      f"bars on the light's lines {sprite_hit}, bars before line 58 {early}")
print("blocks per frame:", sorted({len(e) for e in frames}),
      f"- frames with two bars merged {merged}, with a bar dropped {dropped}")

# --- 3. render ---------------------------------------------------------------------
W, H, SCALE = 384, BOTTOM - TOP, 2
SEGX = [(24, 76), (76, 148), (148, 220), (220, 292), (292, 344)]   # sprite x
ball = mem[L["balls"] + 7 * 64: L["balls"] + 7 * 64 + 63]
MC = {1: RGB[8], 2: RGB[7], 3: RGB[1]}
def render(ents):
    im = Image.new("RGB", (W, H))
    px = im.load()
    for line, n, rows in ents:
        for r, row in enumerate(rows):
            yy = line + 2 + r - TOP
            if 0 <= yy < H:
                for k, c in enumerate(row):
                    for x in range(SEGX[k][0] + 8, SEGX[k][1] + 8):
                        px[x, yy] = RGB[c]
    for sy in range(21):
        bits = (ball[sy * 3] << 16) | (ball[sy * 3 + 1] << 8) | ball[sy * 3 + 2]
        for cx in range(12):
            v = (bits >> (22 - 2 * cx)) & 3
            if v:
                for dx in (0, 1):
                    px[SPRX + 8 + cx * 2 + dx, SPRY + 1 + sy - TOP] = MC[v]
    return im.resize((W * SCALE, H * SCALE), Image.NEAREST)

imgs = [render(e) for e in frames[100::2]]
imgs[0].save(os.path.join(HERE, "preview_goldfly.gif"), save_all=True,
             append_images=imgs[1:], duration=40, loop=0)
sheet = Image.new("RGB", (W * SCALE * 3, H * SCALE * 2))
for i, n in enumerate((120, 170, 220, 300, 380, 460)):
    sheet.paste(render(frames[n]), ((i % 3) * W * SCALE, (i // 3) * H * SCALE))
sheet.save(os.path.join(HERE, "preview_goldfly.png"))
print("wrote preview_goldfly.gif, preview_goldfly.png")
sys.exit(0 if ok else 1)
