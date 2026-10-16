#!/usr/bin/env python3
"""Run goldorbit.prg's per-frame code on an emulated 6502 (py65).

Checks row timing (63 cycles, or 63 - STEAL with the sprite branch
patched), that update() is done before the top IRQ, that the ball stays
inside the display window, and that the shortened rows are exactly the
ones where the sprite fetches data.  Renders preview_goldorbit.gif / .png
from the program's own sprite buffer, so the masking shown is the real one.

    cl65 -g -t none -C raybars.cfg -Ln goldorbit.lbl -o goldorbit.prg goldorbit.s
    python3 sim_goldorbit.py
"""
import os, sys
from py65.devices.mpu6502 import MPU
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = 512
ROWS, SEGS, SEGSIZE, ROWSIZE = 29, 5, 8, 47
SEGW, DENLINE, STEAL = 80, 44, 4
TOP, BOTTOM = 50, 250
OP_BCS, OP_BCC = 0xB0, 0x90

PAL = [0x000000, 0xFFFFFF, 0x894036, 0x7ABFC7, 0x8A46AE, 0x68A941, 0x3E31A2,
       0xD0DC71, 0x905F25, 0x5C4700, 0xBB776D, 0x555555, 0x808080, 0xACEA88,
       0x7C70DA, 0xABABAB]
RGB = [((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in PAL]

labels = {}
for ln in open(os.path.join(HERE, "goldorbit.lbl")):
    _, addr, name = ln.split()
    labels[name.lstrip(".")] = int(addr, 16)
prg = open(os.path.join(HERE, "goldorbit.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])
mem = mpu.memory
block = labels["block"]
Z = {n: labels[n] for n in ("y0", "ly", "lx4", "lptr", "dz")}

# --- 1. row timing, normal and shortened ----------------------------------------
def time_rows():
    mpu.pc = block
    out = []
    mpu.p &= ~1                         # carry clear, as irq2 leaves it
    for r in range(ROWS):
        s = mpu.processorCycles
        while mpu.pc != block + (r + 1) * ROWSIZE:
            mpu.step()
        out.append(mpu.processorCycles - s)
    return out
ok = all(c == 63 for c in time_rows())
for r in range(ROWS):
    mem[block + r * ROWSIZE + SEGS * SEGSIZE] = OP_BCC
short = time_rows()
ok &= all(c == 63 - STEAL for c in short)
for r in range(ROWS):
    mem[block + r * ROWSIZE + SEGS * SEGSIZE] = OP_BCS
print(f"rows: 63 cycles normal, {short[0]} with the sprite branch "
      f"({'OK' if ok else 'WRONG'})")

# --- 2. update() frame by frame ---------------------------------------------------
TRAMP = 0xC000
upd = labels["update"]
mem[TRAMP:TRAMP + 4] = [0x20, upd & 255, upd >> 8, 0x00]
def run_update():
    mpu.pc, mpu.sp = TRAMP, 0xFF
    c = mpu.processorCycles
    while mpu.pc != TRAMP + 3:
        mpu.step()
    return mpu.processorCycles - c

run_update()
frames, worst, inwin, rowsok, behind_frames = [], 0, True, True, 0
for f in range(FRAMES):
    y_cur = mem[Z["y0"]]
    cyc = run_update()
    budget = ((312 - (y_cur + ROWS + 2)) + DENLINE) * 63 - 150
    worst = max(worst, 100 * cyc / budget)
    ok &= cyc <= budget
    y, ly, lx = mem[Z["y0"]], mem[Z["ly"]], mem[Z["lx4"]] * 4
    dz = mem[Z["dz"]] - 256 * (mem[Z["dz"]] > 127)
    behind_frames += dz < 0
    inwin &= ly + 1 >= 51 and ly + 21 <= 250
    patched = [mem[block + r * ROWSIZE + SEGS * SEGSIZE] == OP_BCC for r in range(ROWS)]
    rowsok &= patched == [0 <= y + r - ly < 21 for r in range(ROWS)]
    grid = [[mem[block + r * ROWSIZE + k * SEGSIZE + 1] for k in range(SEGS)]
            for r in range(ROWS)]
    spr = list(mem[mem[Z["lptr"]] * 64: mem[Z["lptr"]] * 64 + 63])
    frames.append((y, grid, ly, lx, spr, sum(patched), cyc))
ok &= inwin and rowsok
print(f"update(): {min(fr[6] for fr in frames)}-{max(fr[6] for fr in frames)} cycles, "
      f"worst {worst:.0f}% of the time before the top IRQ")
print("ball inside the display window:", inwin)
print("shortened rows match the sprite's lines:", rowsok,
      f"(up to {max(fr[5] for fr in frames)} rows per frame)")
print(f"light behind the bar in {behind_frames} of {FRAMES} frames")

# --- 3. render ---------------------------------------------------------------------
W, H, SCALE = SEGS * SEGW, BOTTOM - TOP, 2
MC = {1: RGB[8], 2: RGB[7], 3: RGB[1]}
def render(y, grid, ly, lx, spr):
    im = Image.new("RGB", (W, H))
    px = im.load()
    for r, row in enumerate(grid):
        yy = y + r - TOP
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

imgs = [render(*fr[:5]) for fr in frames[::3]]
imgs[0].save(os.path.join(HERE, "preview_goldorbit.gif"), save_all=True,
             append_images=imgs[1:], duration=50, loop=0)
picks = (30, 64, 100, 140, 192, 230)
sheet = Image.new("RGB", (W * SCALE * 3, H * SCALE * 2))
for i, n in enumerate(picks):
    sheet.paste(render(*frames[n][:5]), ((i % 3) * W * SCALE, (i // 3) * H * SCALE))
sheet.save(os.path.join(HERE, "preview_goldorbit.png"))
print("wrote preview_goldorbit.gif, preview_goldorbit.png")
sys.exit(0 if ok else 1)
