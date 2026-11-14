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
BALL = labels["ballready"]
def run_update():
    """update's cycles, and the cycles to the point where the sprite is ready (ballready)"""
    mpu.pc, mpu.sp = TRAMP, 0xFF
    c, ball = mpu.processorCycles, None
    while mpu.pc != TRAMP + 3:
        if mpu.pc == BALL and ball is None:
            ball = mpu.processorCycles - c
        mpu.step()
    return mpu.processorCycles - c, ball

# The frame's timeline (the update runs in the main loop since the bar's IRQ, the top IRQ cuts in):
# the sprite part must be ready before the top IRQ (it reads y0, ly, lx4, lptr), the whole update before the bar's IRQ,
# and the tune (MUSIC cycles, NTSC cartridge) after it before the next bar has been drawn.  LINES / LINEC: PAL 312 / 63, NTSC 263 / 65.
LINES, LINEC, MUSIC = int(os.environ.get("LINES", 312)), int(os.environ.get("LINEC", 63)), int(os.environ.get("MUSIC", 0))
IRQTOP_LINES = 6
def advance(line, cycles, blocked):
    lines = (cycles + 150) / LINEC
    while lines > 0:
        for lo, hi in blocked:
            if lo <= line < hi:
                line = hi
                break
        step = min(lines, 1)
        line += step
        lines -= step
    return line

# initial phases, e.g. GOLD_INIT="orbit=90,tilt=26,lxa=45,lya=250,q=254" (the hand-over from goldlight; frame 0 is the second update: initial + 2)
for kv in filter(None, os.environ.get("GOLD_INIT", "").split(",")):
    k, v = kv.split("="); mem[labels[k]] = int(v)
run_update()
frames, worst, inwin, rowsok, behind_frames = [], 0, True, True, 0
worstw = {"sprite": 0, "bar": 0, "tune": 0}
for f in range(FRAMES):
    y_cur = mem[Z["y0"]]
    cyc, cball = run_update()
    y, ly, lx = mem[Z["y0"]], mem[Z["ly"]], mem[Z["lx4"]] * 4
    a_end = y_cur + ROWS + 2
    blocked = [(LINES + DENLINE, LINES + DENLINE + IRQTOP_LINES), (LINES + y - 2, LINES + y + ROWS + 2)]
    t_ball, t_all = advance(a_end, cball, blocked), advance(a_end, cyc, blocked)
    t_mus = advance(t_all, MUSIC, blocked) if MUSIC else t_all
    for k, t, dl in (("sprite", t_ball, LINES + DENLINE), ("bar", t_all, LINES + y - 2), ("tune", t_mus, LINES + y + ROWS + 2)):
        worstw[k] = max(worstw[k], 100 * (t - a_end) / (dl - a_end))
        ok &= t <= dl
    worst = max(worstw.values())
    dz = mem[Z["dz"]] - 256 * (mem[Z["dz"]] > 127)
    behind_frames += dz < 0
    inwin &= ly + 1 >= 51 and ly + 21 <= 250
    patched = [mem[block + r * ROWSIZE + SEGS * SEGSIZE] == OP_BCC for r in range(ROWS)]
    rowsok &= patched == [0 <= y + r - ly < 21 for r in range(ROWS)]
    grid = [[mem[block + r * ROWSIZE + k * SEGSIZE + 1] for k in range(SEGS)]
            for r in range(ROWS)]
    spr = list(mem[mem[Z["lptr"]] * 64: mem[Z["lptr"]] * 64 + 63])
    frames.append((y, grid, ly, lx, spr, sum(patched), cyc, dz))
ok &= inwin and rowsok
print(f"update(): {min(fr[6] for fr in frames)}-{max(fr[6] for fr in frames)} cycles; worst use of each deadline window"
      f" ({LINES} lines of {LINEC} cycles, tune {MUSIC}): sprite before the top IRQ {worstw['sprite']:.0f}%, the update before the bar {worstw['bar']:.0f}%,"
      f" the tune after it {worstw['tune']:.0f}%")
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
