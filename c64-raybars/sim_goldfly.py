#!/usr/bin/env python3
"""Run goldfly.prg on an emulated 6502 (py65): its frame building and its
display code.

Every frame, each scheduled IRQ block is set up by the program's own nextbar
and its row loops are run; the colours they read are what gets rendered.
Checks: every row takes 63 cycles, or 63 - STEAL on the light's sprite DMA
lines, and irq2's delay is shortened when its line has that DMA; no column
read crosses a page; every displayed cell shows the nearest bar whose rows
cover it (black where none does); blocks leave room for the next IRQ; bars
nearer than the light stay off its lines; the first IRQ comes after the top
IRQ; the build fits in the frame's free time; tilts never repeat within 40
bars.  Renders preview_goldfly.gif / .png.  The VIC's real steal (STEAL) and
the split positions need checking in VICE.

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

ok = True
STEAL, BASE = 5, 96
BAND0, BAND1 = SPRY, SPRY + 21
# flight time from which a bar is nearer than the light
NEARZ3 = int(open(os.path.join(HERE, "fly.inc")).read().split("NEARZ3 = ")[1].split()[0])

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
mpu.pc, mpu.sp = 2061, 0xFF                  # where SYS 2061 lands
while mpu.pc != L["main"]:
    mpu.step()
mem[L["buf"]] = mem[L["nbuf"]] ^ 1
mem[L["ready"]] = 0

over = 0
frames, worst, pagecross, close, sprite_hit, early = [], 0, 0, 0, 0, 0
badrow, baddly, badcell, merged = 0, 0, 0, 0
ROWSTART = {sl: {L[f"n1_{sl}"], L[f"b_{sl}"], L[f"n2_{sl}"]} for sl in range(NSLOT)}
for f in range(FRAMES):
    cyc = call(L["build"])
    # the bars as built: visible slots, their lines and columns
    vis = [sl for sl in range(NSLOT) if mem[L["vis"] + sl]]
    def cell(sl, k, ln):
        idx = mem[L["vpl"] + sl * SEGS + k] + ln - mem[L["vD"] + sl]
        return mem[mem[L["vcp"] + sl * SEGS + k] * 256 + idx], idx
    def want(k, ln):
        best = None
        for sl in vis:
            if mem[L["vD"] + sl] <= ln < mem[L["vE"] + sl]:
                c, idx = cell(sl, k, ln)
                if BASE <= idx < BASE + mem[L["vh"] + sl]:
                    if best is None or mem[L["st"] + sl] > best[0]:
                        best = (mem[L["st"] + sl], c)
        return 0 if best is None else best[1]
    for sl in vis:      # bars nearer than the light keep off its lines
        if mem[L["st"] + sl] >= NEARZ3:
            sprite_hit += mem[L["vD"] + sl] < SPRY + 22 and mem[L["vE"] + sl] > SPRY + 1
    # the top IRQ swaps the frame in
    mem[L["ptr"]:L["ptr"] + NSLOT * SEGS * 2] = mem[L["nptr"]:L["nptr"] + NSLOT * SEGS * 2]
    nb = mem[L["nbuf"]]
    mem[L["scount"]] = cnt = mem[L["ncount"]]
    mem[L["sbase"]] = nb * NSLOT
    merged += cnt < len(vis)
    ents = []
    for i in range(cnt):
        mem[L["sidx"]] = i
        call(L["nextbar"])
        line = mem[0xD012]
        D = line + 2
        dly = mem[L["irq2"] + 2]          # ldx #delay after txs
        baddly += dly != (7 if BAND0 <= D - 1 < BAND1 else 8)
        slot = mem[L["soff"] + nb * NSLOT + i]
        ptrs = [mem[L["ptr"] + (slot * SEGS + k) * 2] |
                mem[L["ptr"] + (slot * SEGS + k) * 2 + 1] << 8 for k in range(SEGS)]
        mpu.pc, mpu.y = mem[L["curvec"]] | mem[L["curvec"] + 1] << 8, 0
        starts, rows = [], []
        while mpu.pc != L["bexit"]:
            if mpu.pc in ROWSTART[slot]:
                starts.append(mpu.processorCycles)
                y = mpu.y
                row = []
                for p in ptrs:
                    if (p + y) >> 8 != p >> 8:
                        pagecross += 1
                    row.append(mem[p + y])
                rows.append(row)
            mpu.step()
        for r in range(len(rows)):
            ln = D + r
            if r + 1 < len(rows):           # (the last row runs into bexit)
                exp = 63 - STEAL if BAND0 <= ln < BAND1 else 63
                badrow += starts[r + 1] - starts[r] != exp
            badcell += sum(rows[r][k] != want(k, ln) for k in range(SEGS))
        n = len(rows)
        ents.append((line, n, rows))
        early += line < 58
    for (l1, n1, _), (l2, n2, _) in zip(ents, ents[1:]):
        if l2 < l1 + 2 + n1 + 4:            # bexit + nextbar need 4 lines
            close += 1
    # free time: not the top IRQ's lines, nor a block's rows, its 2 IRQ lines
    # and 2 more for bexit + nextbar; less the light's DMA (21 lines x 5)
    shown = sum(n + 4 for _, n, _ in ents)
    budget = (312 - 12 - shown) * LINE - 300 - 21 * 5
    worst = max(worst, 100 * cyc / budget)
    ok &= cyc <= budget
    over += cyc > budget
    frames.append(ents)
    mem[L["buf"]] = nb ^ 1
    mem[L["ready"]] = 0
ok &= pagecross == 0 and close == 0 and sprite_hit == 0 and early == 0
ok &= badrow == 0 and baddly == 0 and badcell == 0
print(f"rows with the wrong length {badrow}, irq2 delays wrong {baddly}, "
      f"cells not showing the nearest bar {badcell}")
print(f"build(): worst {worst:.1f}% of the frame's free time, frames over {over}")
print(f"page-crossing reads {pagecross}, blocks too close {close}, "
      f"near bars on the light's lines {sprite_hit}, IRQs before line 58 {early}")
print("blocks per frame:", sorted({len(e) for e in frames}),
      f"- frames with bars merged {merged}")

# --- tilts: 3000 draws with the program's own drawtilt ----------------------
NT = 53
draws = []
for i in range(3000):
    call(L["drawtilt"])
    draws.append(mpu.a)
last, gap = {}, 999
for i, t in enumerate(draws):
    if t in last:
        gap = min(gap, i - last[t])
    last[t] = i
alike = sum(abs(a - b) < 6 for a, b in zip(draws, draws[1:]))
print(f"tilts: {len(set(draws))} of {NT} used, closest repeat {gap} bars apart, "
      f"{alike} of {len(draws) - 1} neighbours alike")
ok &= len(set(draws)) == NT and gap > 40

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
