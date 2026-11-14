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
NTSC = int(os.environ.get("GOLD_NTSC", 0))            # 1: the NTSC build (goldlight_ntsc.prg: 65-cycle rows, 263 lines)
NAME = "goldlight_ntsc" if NTSC else "goldlight"
ROWS, SEGS, SEGSIZE, ROWSIZE = 29, 5, 8, 47 + NTSC
SEGW = 80                       # pixels per segment (10 cycles)
DENLINE = 44
TOP, BOTTOM = 50, 250           # raster lines shown in the preview
SPRITE = 0x3F00

PAL = [0x000000, 0xFFFFFF, 0x894036, 0x7ABFC7, 0x8A46AE, 0x68A941, 0x3E31A2,
       0xD0DC71, 0x905F25, 0x5C4700, 0xBB776D, 0x555555, 0x808080, 0xACEA88,
       0x7C70DA, 0xABABAB]
RGB = [((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in PAL]

labels = {}
for ln in open(os.path.join(HERE, NAME + ".lbl")):
    _, addr, name = ln.split()
    labels[name.lstrip(".")] = int(addr, 16)

prg = open(os.path.join(HERE, NAME + ".prg"), "rb").read()
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
    ok &= (mpu.processorCycles - start == 63 + 2 * NTSC)
print(f"speedcode: {ROWS} rows, {mpu.processorCycles - c0} cycles "
      f"({'every row ' + str(63 + 2 * NTSC) if ok else 'ROW TIMING WRONG'})")

# --- 2. update() frame by frame ------------------------------------------------
TRAMP = 0xC000
upd = labels["update"]
mem[TRAMP:TRAMP + 4] = [0x20, upd & 255, upd >> 8, 0x00]

BALL = labels["ballready"]
def run_update():
    """update's cycles, and the cycles to the point where the sprite registers are set (ballready)"""
    mpu.pc, mpu.sp = TRAMP, 0xFF
    c, ball = mpu.processorCycles, None
    while mpu.pc != TRAMP + 3:
        if mpu.pc == BALL and ball is None:
            ball = mpu.processorCycles - c
        mpu.step()
    return mpu.processorCycles - c, ball

# The frame's timeline (the update runs in the main loop since the bar's IRQ, the top IRQ cuts in):
# the sprite part must be ready before the top IRQ, the whole update before the bar's IRQ, and the tune (MUSIC cycles,
# NTSC cartridge) after it before the next bar has been drawn.  LINES / LINEC: PAL 312 / 63, NTSC 263 / 65.
LINES, LINEC, MUSIC = int(os.environ.get("LINES", 263 if NTSC else 312)), int(os.environ.get("LINEC", 65 if NTSC else 63)), int(os.environ.get("MUSIC", 0))
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

# initial phases, e.g. GOLD_INIT="orbit=178,tilt=178,lxa=196" (the hand-over from goldtilt: its last frame's phase - 1; frame 0 is the second update)
for kv in filter(None, os.environ.get("GOLD_INIT", "").split(",")):
    k, v = kv.split("="); mem[labels[k]] = int(v)
run_update()
frames, worst, clear = [], 0, True
worstw = {"sprite": 0, "bar": 0, "tune": 0}
for f in range(FRAMES):
    y_cur = mem[Y0]
    cyc, cball = run_update()
    y, ly, lx = mem[Y0], mem[LY], mem[LX4] * 4
    a_end = y_cur + ROWS + 2
    blocked = [(LINES + DENLINE, LINES + DENLINE + IRQTOP_LINES), (LINES + y - 2, LINES + y + ROWS + 2)]
    t_ball, t_all = advance(a_end, cball, blocked), advance(a_end, cyc, blocked)
    t_mus = advance(t_all, MUSIC, blocked) if MUSIC else t_all
    for k, t, dl in (("sprite", t_ball, LINES + DENLINE), ("bar", t_all, LINES + y - 2), ("tune", t_mus, LINES + y + ROWS + 2)):
        worstw[k] = max(worstw[k], 100 * (t - a_end) / (dl - a_end))
        ok &= t <= dl
    worst = max(worstw.values())
    # sprite lines (ly+1 .. ly+21) must end above the IRQ line y-2
    clear &= ly + 22 < y - 2
    grid = [[mem[block + r * ROWSIZE + k * SEGSIZE + 1] for k in range(SEGS)]
            for r in range(ROWS)]
    p = mem[0x07F8]                  # the sprite pointer update() set: a stage of the grow-in or the full ball (block $FC)
    spr = ball if p == SPRITE // 64 else mem[labels["grow"] + (p - labels["growptr"] * 0 - 0xF5) * 64:][:63]
    frames.append((y, grid, ly, lx, cyc, spr))
ok &= clear
print(f"update(): {min(fr[4] for fr in frames)}-{max(fr[4] for fr in frames)} cycles; worst use of each deadline window"
      f" ({LINES} lines of {LINEC} cycles, tune {MUSIC}): sprite before the top IRQ {worstw['sprite']:.0f}%, the update before the bar {worstw['bar']:.0f}%,"
      f" the tune after it {worstw['tune']:.0f}%")
print("sprite never shares a line with the bar:", clear)

# --- 3. render ---------------------------------------------------------------------
W, H, SCALE = SEGS * SEGW, BOTTOM - TOP, 2
MC = {1: RGB[8], 2: RGB[7], 3: RGB[1]}  # %01 orange, %10 yellow, %11 white

def render(y, grid, ly, lx, spr=None):
    ball_ = ball if spr is None else spr
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
        bits = (ball_[sy * 3] << 16) | (ball_[sy * 3 + 1] << 8) | ball_[sy * 3 + 2]
        for cx in range(12):
            v = (bits >> (22 - 2 * cx)) & 3
            if v and 0 <= yy < H:
                for dx in (0, 1):
                    xx = lx + 8 + cx * 2 + dx
                    if 0 <= xx < W:
                        px[xx, yy] = MC[v]
    return im.resize((W * SCALE, H * SCALE), Image.NEAREST)

imgs = [render(*fr[:4], spr=fr[5]) for fr in frames[::2]]
imgs[0].save(os.path.join(HERE, "preview_goldlight.gif"), save_all=True,
             append_images=imgs[1:], duration=40, loop=0)
sheet = Image.new("RGB", (W * SCALE * 3, H * SCALE))
for i, n in enumerate((20, 100, 200)):
    sheet.paste(render(*frames[n][:4], spr=frames[n][5]), (i * W * SCALE, 0))
sheet.save(os.path.join(HERE, "preview_goldlight.png"))
print("wrote preview_goldlight.gif, preview_goldlight.png")
sys.exit(0 if ok else 1)
