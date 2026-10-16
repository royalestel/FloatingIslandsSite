#!/usr/bin/env python3
"""Run goldtilt.prg's per-frame code on an emulated 6502 (py65).

Checks that every speedcode row is exactly 63 cycles and that update()
fits in the time between the bar and the next frame's IRQ, then renders
frames to preview_goldtilt.gif / .png.

    cl65 -g -t none -C raybars.cfg -Ln goldtilt.lbl -o goldtilt.prg goldtilt.s
    python3 sim_goldtilt.py
"""
import os, sys
from py65.devices.mpu6502 import MPU
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = 256
ROWS, SEGS, SEGSIZE, ROWSIZE = 30, 6, 6, 44
SEGW = 64                       # pixels per segment (8 cycles)
TOP, BOTTOM = 40, 270           # raster lines shown in the preview

# VICE's default palette
PAL = [0x000000, 0xFFFFFF, 0x894036, 0x7ABFC7, 0x8A46AE, 0x68A941, 0x3E31A2,
       0xD0DC71, 0x905F25, 0x5C4700, 0xBB776D, 0x555555, 0x808080, 0xACEA88,
       0x7C70DA, 0xABABAB]
RGB = [((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in PAL]

labels = {}
for ln in open(os.path.join(HERE, "goldtilt.lbl")):
    _, addr, name = ln.split()
    labels[name.lstrip(".")] = int(addr, 16)

prg = open(os.path.join(HERE, "goldtilt.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])
mem = mpu.memory
block, y0addr = labels["block"], labels["y0"]

# --- 1. the speedcode: every row exactly 63 cycles --------------------------
mpu.pc = block
c0 = mpu.processorCycles
rows_ok = True
for r in range(ROWS):
    start = mpu.processorCycles
    while mpu.pc != block + (r + 1) * ROWSIZE:
        mpu.step()
    rows_ok &= (mpu.processorCycles - start == 63)
print(f"speedcode: {ROWS} rows, {mpu.processorCycles - c0} cycles "
      f"({'every row 63' if rows_ok else 'ROW TIMING WRONG'})")

# --- 2. run update() frame by frame -----------------------------------------
TRAMP = 0xC000
upd = labels["update"]
mem[TRAMP:TRAMP + 4] = [0x20, upd & 255, upd >> 8, 0x00]

def run_update():
    mpu.pc, mpu.sp = TRAMP, 0xFF
    c = mpu.processorCycles
    while mpu.pc != TRAMP + 3:
        mpu.step()
    return mpu.processorCycles - c

run_update()                    # the init call
frames, worst_pct, ok = [], 0, rows_ok
for f in range(FRAMES):
    y_cur = mem[y0addr]
    cyc = run_update()
    y_next = mem[y0addr]
    # starts after the bar (y_cur + ROWS + ~2), must end before y_next - 2
    budget = ((312 - (y_cur + ROWS + 2)) + (y_next - 2)) * 63 - 150
    worst_pct = max(worst_pct, 100 * cyc / budget)
    ok &= cyc <= budget
    grid = [[mem[block + r * ROWSIZE + k * SEGSIZE + 1] for k in range(SEGS)]
            for r in range(ROWS)]
    frames.append((y_next, grid, cyc))
print(f"update(): {min(c for _, _, c in frames)}-{max(c for _, _, c in frames)} "
      f"cycles, worst {worst_pct:.0f}% of the time before the next IRQ")

# --- 3. render ------------------------------------------------------------------
W, H, SCALE = SEGS * SEGW, BOTTOM - TOP, 2
def render(y, grid):
    im = Image.new("RGB", (W, H))
    px = im.load()
    for r, row in enumerate(grid):
        yy = y + r - TOP
        if 0 <= yy < H:
            for k, c in enumerate(row):
                for x in range(k * SEGW, (k + 1) * SEGW):
                    px[x, yy] = RGB[c]
    return im.resize((W * SCALE, H * SCALE), Image.NEAREST)

imgs = [render(y, g) for y, g, _ in frames[::2]]
imgs[0].save(os.path.join(HERE, "preview_goldtilt.gif"), save_all=True,
             append_images=imgs[1:], duration=40, loop=0)
sheet = Image.new("RGB", (W * SCALE * 3, H * SCALE))
for i, n in enumerate((0, 64, 192)):
    sheet.paste(render(frames[n][0], frames[n][1]), (i * W * SCALE, 0))
sheet.save(os.path.join(HERE, "preview_goldtilt.png"))
print("wrote preview_goldtilt.gif, preview_goldtilt.png")
sys.exit(0 if ok else 1)
