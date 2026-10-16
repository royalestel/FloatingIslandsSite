#!/usr/bin/env python3
"""Run goldlight.prg's per-frame code on an emulated 6502 (py65).

Checks that every speedcode row is exactly 63 cycles, that update() is
done before the top IRQ (the DEN trick at line DENLINE), and that the
light sprite never shares a raster line with the bar or its stabilising
IRQ.  Renders frames to preview_goldlight.gif / .png.

    cl65 -g -t none -C raybars.cfg -Ln goldlight.lbl -o goldlight.prg goldlight.s
    python3 sim_goldlight.py
"""
import os, sys
from py65.devices.mpu6502 import MPU
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = 256
ROWS, SEGS, SEGSIZE, ROWSIZE = 29, 5, 8, 47
SEGW = 80                       # pixels per segment (10 cycles)
DENLINE = 44
TOP, BOTTOM = 50, 250           # raster lines shown in the preview
SPRITE = 0x3F00

PAL = [0x000000, 0xFFFFFF, 0x894036, 0x7ABFC7, 0x8A46AE, 0x68A941, 0x3E31A2,
       0xD0DC71, 0x905F25, 0x5C4700, 0xBB776D, 0x555555, 0x808080, 0xACEA88,
       0x7C70DA, 0xABABAB]
RGB = [((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in PAL]

labels = {}
for ln in open(os.path.join(HERE, "goldlight.lbl")):
    _, addr, name = ln.split()
    labels[name.lstrip(".")] = int(addr, 16)

prg = open(os.path.join(HERE, "goldlight.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])
mem = mpu.memory
block = labels["block"]
Y0, LY, LX4 = labels["y0"], labels["ly"], labels["lx4"]
ball = mem[labels["ball"]:labels["ball"] + 63]

# --- 1. the speedcode: every row exactly 63 cycles --------------------------
mpu.pc = block
c0 = mpu.processorCycles
ok = True
for r in range(ROWS):
    start = mpu.processorCycles
    while mpu.pc != block + (r + 1) * ROWSIZE:
        mpu.step()
    ok &= (mpu.processorCycles - start == 63)
print(f"speedcode: {ROWS} rows, {mpu.processorCycles - c0} cycles "
      f"({'every row 63' if ok else 'ROW TIMING WRONG'})")

# --- 2. update() frame by frame ------------------------------------------------
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
frames, worst, clear = [], 0, True
for f in range(FRAMES):
    y_cur = mem[Y0]
    cyc = run_update()
    # starts after this frame's bar, must end before the next top IRQ
    budget = ((312 - (y_cur + ROWS + 2)) + DENLINE) * 63 - 150
    worst = max(worst, 100 * cyc / budget)
    ok &= cyc <= budget
    y, ly, lx = mem[Y0], mem[LY], mem[LX4] * 4
    # sprite lines (ly+1 .. ly+21) must end above the IRQ line y-2
    clear &= ly + 22 < y - 2
    grid = [[mem[block + r * ROWSIZE + k * SEGSIZE + 1] for k in range(SEGS)]
            for r in range(ROWS)]
    frames.append((y, grid, ly, lx, cyc))
ok &= clear
print(f"update(): {min(fr[4] for fr in frames)}-{max(fr[4] for fr in frames)} "
      f"cycles, worst {worst:.0f}% of the time before the top IRQ")
print("sprite never shares a line with the bar:", clear)

# --- 3. render ---------------------------------------------------------------------
W, H, SCALE = SEGS * SEGW, BOTTOM - TOP, 2
MC = {1: RGB[8], 2: RGB[7], 3: RGB[1]}  # %01 orange, %10 yellow, %11 white

def render(y, grid, ly, lx):
    im = Image.new("RGB", (W, H))
    px = im.load()
    for r, row in enumerate(grid):
        yy = y + r - TOP
        if 0 <= yy < H:
            for k, c in enumerate(row):
                for x in range(k * SEGW, (k + 1) * SEGW):
                    px[x, yy] = RGB[c]
    # sprite x -> canvas: segment 0 starts at sprite x -8
    for sy in range(21):
        yy = ly + 1 + sy - TOP
        bits = (ball[sy * 3] << 16) | (ball[sy * 3 + 1] << 8) | ball[sy * 3 + 2]
        for cx in range(12):
            v = (bits >> (22 - 2 * cx)) & 3
            if v and 0 <= yy < H:
                for dx in (0, 1):
                    xx = lx + 8 + cx * 2 + dx
                    if 0 <= xx < W:
                        px[xx, yy] = MC[v]
    return im.resize((W * SCALE, H * SCALE), Image.NEAREST)

imgs = [render(*fr[:4]) for fr in frames[::2]]
imgs[0].save(os.path.join(HERE, "preview_goldlight.gif"), save_all=True,
             append_images=imgs[1:], duration=40, loop=0)
sheet = Image.new("RGB", (W * SCALE * 3, H * SCALE))
for i, n in enumerate((20, 100, 200)):
    sheet.paste(render(*frames[n][:4]), (i * W * SCALE, 0))
sheet.save(os.path.join(HERE, "preview_goldlight.png"))
print("wrote preview_goldlight.gif, preview_goldlight.png")
sys.exit(0 if ok else 1)
