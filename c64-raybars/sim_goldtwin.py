#!/usr/bin/env python3
"""Run goldtwin.prg's per-frame code on an emulated 6502 (py65).

Checks row timing for both bars, that the main loop meets its three
deadlines (sprite ready before the top IRQ, bar A patched before bar A's
IRQ, bar B patched before bar B's IRQ), and that the sprite never steals
cycles inside bar B.  Renders preview_goldtwin.gif / .png.

    cl65 -g -t none -C raybars.cfg -Ln goldtwin.lbl -o goldtwin.prg goldtwin.s
    python3 sim_goldtwin.py
"""
import os, sys
from py65.devices.mpu6502 import MPU
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = 512
ROWS, ROWSB, SEGS, SEGSIZE, ROWSIZE = 29, 52, 5, 8, 47
BMAXROWS = 48
SEGW, DENLINE, STEAL, BTOP = 80, 44, 4, 229
TOP, BOTTOM = 50, 290
OP_BCS, OP_BCC = 0xB0, 0x90
LINE = 63
IRQTOP_LINES = 6                # top IRQ: line 44 until DEN is back at 49
SPRITE_DMA = 21 * 5             # worst case cycles the sprite takes per frame

PAL = [0x000000, 0xFFFFFF, 0x894036, 0x7ABFC7, 0x8A46AE, 0x68A941, 0x3E31A2,
       0xD0DC71, 0x905F25, 0x5C4700, 0xBB776D, 0x555555, 0x808080, 0xACEA88,
       0x7C70DA, 0xABABAB]
RGB = [((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in PAL]

labels = {}
for ln in open(os.path.join(HERE, "goldtwin.lbl")):
    _, addr, name = ln.split()
    labels[name.lstrip(".")] = int(addr, 16)
prg = open(os.path.join(HERE, "goldtwin.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])
mem = mpu.memory
block, blockb = labels["block"], labels["blockb"]
Z = {n: labels[n] for n in ("y0", "ly", "lx4", "lptr", "bh", "bt")}

# --- 1. row timing -------------------------------------------------------------
def time_rows(base, n):
    mpu.pc = base
    mpu.p &= ~1
    out = []
    for r in range(n):
        s = mpu.processorCycles
        while mpu.pc != base + (r + 1) * ROWSIZE:
            mpu.step()
        out.append(mpu.processorCycles - s)
    return out
ok = all(c == LINE for c in time_rows(block, ROWS))
for r in range(ROWS):
    mem[block + r * ROWSIZE + SEGS * SEGSIZE] = OP_BCC
ok &= all(c == LINE - STEAL for c in time_rows(block, ROWS))
for r in range(ROWS):
    mem[block + r * ROWSIZE + SEGS * SEGSIZE] = OP_BCS
ok &= all(c == LINE for c in time_rows(blockb, ROWSB))
print(f"rows: bar A 63 (59 on sprite lines), bar B 63: {'OK' if ok else 'WRONG'}")

# --- 2. the main loop's frame work, on a timeline ----------------------------------
# The main loop starts the next sprite + bar A when bar A has been drawn, and
# the next bar B when bar B has been drawn.  Interrupts take the lines they
# draw on; the work runs in the remaining time.  Deadlines: the sprite before
# the top IRQ, bar A before its IRQ, bar B before its IRQ.
TRAMP = 0xC000
def call(addr, stop=None):
    mem[TRAMP:TRAMP + 4] = [0x20, addr & 255, addr >> 8, 0x00]
    mpu.pc, mpu.sp = TRAMP, 0xFF
    c, mark = mpu.processorCycles, None
    while mpu.pc != TRAMP + 3:
        if stop is not None and mpu.pc == stop and mark is None:
            mark = mpu.processorCycles - c
        mpu.step()
    return mpu.processorCycles - c, mark

def advance(line, cycles, blocked):
    """Run `cycles` of main-loop work from `line`, skipping blocked lines."""
    lines = (cycles + 150) / LINE + SPRITE_DMA / LINE
    while lines > 0:
        for lo, hi in blocked:
            if lo <= line < hi:
                line = hi
                break
        step = min(lines, 1)
        line += step
        lines -= step
    return line

call(labels["update"]); call(labels["updateb"])
frames, worst = [], {"sprite": 0, "A": 0, "B": 0}
clear = True
BSTART, BEND = BTOP - 2, BTOP + ROWSB + 1
for f in range(FRAMES):
    y_cur = mem[Z["y0"]]
    ca, cball = call(labels["update"], labels["ballready"])
    cb, _ = call(labels["updateb"])
    y = mem[Z["y0"]]
    a_end = y_cur + ROWS + 2
    blocked = [(BSTART, BEND), (312 + DENLINE, 312 + DENLINE + IRQTOP_LINES),
               (312 + y - 2, 312 + y + ROWS + 2)]
    t_ball = advance(a_end, cball, blocked)
    t_a = advance(a_end, ca, blocked)
    t_b = advance(max(t_a, BEND), cb, blocked)
    for k, t, start, dl in (("sprite", t_ball, a_end, 312 + DENLINE),
                            ("A", t_a, a_end, 312 + y - 2),
                            ("B", t_b, BEND, 312 + BTOP - 2)):
        worst[k] = max(worst[k], 100 * (t - start) / (dl - start))
        ok &= t <= dl
    ly = mem[Z["ly"]]
    clear &= ly + 22 < BTOP - 2
    ga = [[mem[block + r * ROWSIZE + k * SEGSIZE + 1] for k in range(SEGS)]
          for r in range(ROWS)]
    gb = [[mem[blockb + r * ROWSIZE + k * SEGSIZE + 1] for k in range(SEGS)]
          for r in range(ROWSB)]
    spr = list(mem[0x8000 + mem[Z["lptr"]] * 64: 0x8000 + mem[Z["lptr"]] * 64 + 63])
    dzv = mem[labels["dz"]]
    kbv = [mem[labels["kb"] + k] for k in range(SEGS)]
    bcol = labels["bcol"]
    hl = [(r, k) for r in range(ROWSB) for k in range(SEGS)
          if gb[r][k] != mem[bcol + r + kbv[k]]]
    frames.append((y, ga, gb, ly, mem[Z["lx4"]] * 4, spr, mem[Z["bh"]], ca, cb,
                   dzv - 256 * (dzv > 127), hl))
ok &= clear
print(f"main loop: update {min(f[7] for f in frames)}-{max(f[7] for f in frames)}, "
      f"updateb {min(f[8] for f in frames)}-{max(f[8] for f in frames)} cycles")
print("worst use of each deadline window: " +
      ", ".join(f"{k} {v:.0f}%" for k, v in worst.items()))
print("sprite never on bar B's lines:", clear)

# --- 2b. the two highlight fixes, measured -----------------------------------------
# where bar B's highlight sits (0 = top row, 1 = bottom): rows where the
# speedcode differs from bar B's plain dimmed column are the highlight.
front, behind = [], []
for fr in frames:
    gb, bh, dzb, hl = fr[2], fr[6], fr[9], fr[10]
    if bh >= 8 and hl:
        top = (BMAXROWS - bh) // 2
        c = sum((r - top) / bh for r, k in hl) / len(hl)
        (front if dzb > 0 else behind).append(c)
print(f"bar B highlight centre (0 = top, 1 = bottom): light in front of it "
      f"{sum(front)/max(1,len(front)):.2f} ({len(front)} frames), "
      f"bar nearer than the light {sum(behind)/max(1,len(behind)):.2f} ({len(behind)} frames)")
thick = []
for fr in frames:
    gb, bh, lx = fr[2], fr[6], fr[4]
    if bh >= 30:
        counts = [sum(1 for r in range(ROWSB) if gb[r][k] == 1) for k in range(SEGS)]
        if max(counts) >= 2:
            near = min(range(SEGS), key=lambda k: abs(lx + 12 - (32 + 80 * k)))
            thick.append((lx, counts, near))
for lx, counts, near in thick[:: max(1, len(thick) // 5)]:
    print(f"  light x {lx:3d}: bar B white rows per segment {counts} (nearest segment {near})")

# --- 3. render -------------------------------------------------------------------
W, H, SCALE = SEGS * SEGW, BOTTOM - TOP, 2
MC = {1: RGB[8], 2: RGB[7], 3: RGB[1]}
def render(y, ga, gb, ly, lx, spr):
    im = Image.new("RGB", (W, H))
    px = im.load()
    for top, grid in ((y, ga), (BTOP, gb)):
        for r, row in enumerate(grid):
            yy = top + r - TOP
            if 0 <= yy < H:
                for k, c in enumerate(row):
                    for x in range(k * SEGW, (k + 1) * SEGW):
                        px[x, yy] = RGB[c]
    for sy in range(21):
        yy = ly + 1 + sy - TOP
        bits = (spr[sy * 3] << 16) | (spr[sy * 3 + 1] << 8) | spr[sy * 3 + 2]
        for cx in range(12):
            v = (bits >> (22 - 2 * cx)) & 3
            if v and 0 <= yy < H:
                for dx in (0, 1):
                    xx = lx + 8 + cx * 2 + dx
                    if 0 <= xx < W:
                        px[xx, yy] = MC[v]
    return im.resize((W * SCALE, H * SCALE), Image.NEAREST)

imgs = [render(*fr[:6]) for fr in frames[::3]]
imgs[0].save(os.path.join(HERE, "preview_goldtwin.gif"), save_all=True,
             append_images=imgs[1:], duration=50, loop=0)
picks = (0, 100, 170, 216, 217, 218)
sheet = Image.new("RGB", (W * SCALE * 3, H * SCALE * 2))
for i, n in enumerate(picks):
    sheet.paste(render(*frames[n][:6]), ((i % 3) * W * SCALE, (i // 3) * H * SCALE))
sheet.save(os.path.join(HERE, "preview_goldtwin.png"))
print("wrote preview_goldtwin.gif, preview_goldtwin.png")
sys.exit(0 if ok else 1)
