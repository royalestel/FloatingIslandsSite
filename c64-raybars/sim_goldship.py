#!/usr/bin/env python3
"""Fly goldship.prg on an emulated 6502 (py65), with an autopilot on the
joystick port: it dodges bars on a collision course, and every 200 frames
rolls fully left, levels, rolls fully right.

Every frame, each scheduled IRQ block is set up by the program's own nextbar
and its row loops are run; the colours they read are what gets rendered,
with the ship's current sprite frame and palette and the border colour.
Checks: every row takes 63 cycles, or 63 - STEAL on the sprite's DMA lines,
and irq2's delay is shortened when its line has that DMA; no column read
crosses a page; every displayed cell shows the nearest bar whose rows cover
it; blocks leave room for the next IRQ; the first IRQ comes after the top
IRQ; the build fits in the frame's free time.  Renders preview_goldship.gif
/ .png.

    cl65 -g -t none -C raybars.cfg -Ln goldship.lbl -o goldship.prg goldship.s
    python3 sim_goldship.py
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
for ln in open(os.path.join(HERE, "goldship.lbl")):
    _, a, nme = ln.split()
    L[nme.lstrip(".")] = int(a, 16)
prg = open(os.path.join(HERE, "goldship.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])
mem = mpu.memory

ok = True
STEAL, BASE = 5, 96
BAND0, BAND1 = SPRY, SPRY + 21
# flight time at which a bar reaches the ship's depth
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
def s16(v):
    return v - 65536 if v & 0x8000 else v
def yrel(sl):
    return s16(((mem[L["swh"] + sl] << 8 | mem[L["swl"] + sl]) -
                (mem[L["shipy"] + 1] << 8 | mem[L["shipy"]])) & 0xFFFF)
hits, redframes, look = 0, 0, []
for f in range(FRAMES):
    # autopilot: dodge the nearest bar on (or close to) a collision course
    stick = 0
    ahead = [(mem[L["st"] + sl], yrel(sl)) for sl in range(NSLOT)
             if mem[L["st"] + sl] < NEARZ3 and abs(yrel(sl)) < 34]
    if ahead:
        stv, y = max(ahead)
        stick |= 1 if y >= 0 else 2     # bar above (or level): dive (stick up), else climb
    # and roll for show, every 200 frames: level, full left (held 60
    # frames), level, full right
    ph = f % 200
    stick |= 4 if 40 <= ph < 100 else 8 if 140 <= ph < 200 else 0
    mem[0xDC00] = 0xFF ^ stick
    hit0 = mem[L["hitfl"]]
    cyc = call(L["build"])
    hits += mem[L["hitfl"]] > hit0
    redframes += mem[0xD025] == 2
    look.append((mem[L["SPRPTR"]] if "SPRPTR" in L else mem[0x87F8],
                 mem[0xD025], mem[0xD027], mem[0xD026], mem[0xD020]))
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
ok &= pagecross == 0 and close == 0 and early == 0
ok &= badrow == 0 and baddly == 0 and badcell == 0
print(f"rows with the wrong length {badrow}, irq2 delays wrong {baddly}, "
      f"cells not showing the nearest bar {badcell}")
print(f"build(): worst {worst:.1f}% of the frame's free time, frames over {over}")
print(f"page-crossing reads {pagecross}, blocks too close {close}, "
      f"IRQs before line 58 {early}")
print(f"autopilot: {hits} hits, collision course shown {redframes} of {FRAMES} frames")
print("blocks per frame:", sorted({len(e) for e in frames}),
      f"- frames with bars merged {merged}")

# --- 3. render ---------------------------------------------------------------------
W, H, SCALE = 384, BOTTOM - TOP, 2
SEGX = [(24, 76), (76, 148), (148, 220), (220, 292), (292, 344)]   # sprite x
def render(f):
    ents = frames[f]
    ptr, c1, c2, c3, border = look[f]
    im = Image.new("RGB", (W, H), RGB[border & 15])
    px = im.load()
    for y in range(max(0, 51 - TOP), min(H, 251 - TOP)):   # the display window
        for x in range(24 + 8, 344 + 8):
            px[x, y] = RGB[0]
    for line, n, rows in ents:
        for r, row in enumerate(rows):
            yy = line + 2 + r - TOP
            if 0 <= yy < H:
                for k, c in enumerate(row):
                    for x in range(SEGX[k][0] + 8, SEGX[k][1] + 8):
                        px[x, yy] = RGB[c]
    spr = mem[0x8000 + ptr * 64: 0x8000 + ptr * 64 + 63]
    MC = {1: RGB[c1 & 15], 2: RGB[c2 & 15], 3: RGB[c3 & 15]}
    for sy in range(21):
        bits = (spr[sy * 3] << 16) | (spr[sy * 3 + 1] << 8) | spr[sy * 3 + 2]
        for cx in range(12):
            v = (bits >> (22 - 2 * cx)) & 3
            if v:
                for dx in (0, 1):
                    px[SPRX + 8 + cx * 2 + dx, SPRY + 1 + sy - TOP] = MC[v]
    return im.resize((W * SCALE, H * SCALE), Image.NEAREST)

imgs = [render(f) for f in range(100, FRAMES, 2)]
imgs[0].save(os.path.join(HERE, "preview_goldship.gif"), save_all=True,
             append_images=imgs[1:], duration=40, loop=0)
sheet = Image.new("RGB", (W * SCALE * 3, H * SCALE * 2))
for i, n in enumerate((90, 290, 490, 190, 390, 590)):   # full left; full right
    sheet.paste(render(n), ((i % 3) * W * SCALE, (i // 3) * H * SCALE))
sheet.save(os.path.join(HERE, "preview_goldship.png"))
print("wrote preview_goldship.gif, preview_goldship.png")
sys.exit(0 if ok else 1)
