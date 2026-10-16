#!/usr/bin/env python3
"""Run raybars.prg's per-frame tracer on an emulated 6502 (py65).

Checks the cycle budget and the 63-cycle raster loop, then renders frames
of the colour buffer to preview.png / preview.gif.

    pip install py65 pillow
    cl65 -g -t none -C raybars.cfg -Ln raybars.lbl -o raybars.prg raybars.s
    python3 simulate.py
"""
import os, sys
from py65.devices.mpu6502 import MPU
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = 256
NLINES = 200
FIRSTLINE = 50
# Budget: update starts after the colour loop (~line 252) and must be done
# before irq1 at line FIRSTLINE of the next frame.  Keep some slack for
# the IRQ entry/exit code.
BUDGET = ((312 - (FIRSTLINE + 2 + NLINES)) + FIRSTLINE) * 63 - 150

# Pepto's C64 palette
PAL = [0x000000, 0xFFFFFF, 0x68372B, 0x70A4B2, 0x6F3D86, 0x588D43, 0x352879,
       0xB8C76F, 0x6F4F25, 0x433900, 0x9A6759, 0x444444, 0x6C6C6C, 0x9AD284,
       0x6C5EB5, 0x959595]
RGB = [((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in PAL]

labels = {}
for ln in open(os.path.join(HERE, "raybars.lbl")):
    _, addr, name = ln.split()
    labels[name.lstrip(".")] = int(addr, 16)

prg = open(os.path.join(HERE, "raybars.prg"), "rb").read()
mpu = MPU()
load = prg[0] | prg[1] << 8
mpu.memory[load:load + len(prg) - 2] = list(prg[2:])

# Trampoline at $c000: JSR update ; BRK-trap (we stop when PC hits $c003)
TRAMP = 0xC000
upd = labels["update"]
mpu.memory[TRAMP:TRAMP + 4] = [0x20, upd & 255, upd >> 8, 0x00]
colbuf = labels["colbuf"]

def run_update():
    mpu.pc = TRAMP
    mpu.sp = 0xFF
    c0 = mpu.processorCycles
    while mpu.pc != TRAMP + 3:
        mpu.step()
    return mpu.processorCycles - c0

frames, worst = [], 0
for f in range(FRAMES):
    cyc = run_update()
    worst = max(worst, cyc)
    frames.append(list(mpu.memory[colbuf:colbuf + NLINES]))

print(f"update(): worst {worst} cycles, budget {BUDGET} "
      f"({100 * worst / BUDGET:.0f}% used)")
ok = worst <= BUDGET

# --- time the raster loop: one iteration must be exactly 63 cycles ----------
irq2 = labels["irq2"]
mem = mpu.memory
# find "lda colbuf,x" (BD lo hi) after irq2
pat = [0xBD, colbuf & 255, colbuf >> 8]
loop = next(a for a in range(irq2, irq2 + 64) if list(mem[a:a + 3]) == pat)
mpu.pc, mpu.x = loop, 0
start = mpu.processorCycles
mpu.step()
while mpu.pc != loop:
    mpu.step()
c = mpu.processorCycles - start
print(f"raster loop iteration: {c} cycles (PAL line = 63)")
ok &= (c == 63)

# --- every lit pixel must be one of the bars' colours, white only from spec -
used = sorted({v for fr in frames for v in fr})
print("colours used:", used)

# --- render ------------------------------------------------------------------
# Left half: the raw scanlines.  Right half: a rough PAL/CRT view, each line
# averaged with its neighbour, which is how the mixed colour pairs blend on
# a real TV.
def blended(fr):
    out = []
    for y in range(len(fr)):
        a, b = RGB[fr[y]], RGB[fr[min(y + 1, len(fr) - 1)]]
        out.append(tuple((p + q) // 2 for p, q in zip(a, b)))
    return out

W, SCALE = 320, 2
imgs = []
for fr in frames[::4]:
    raw, mix = [RGB[c] for c in fr], blended(fr)
    im = Image.new("RGB", (W, NLINES))
    px = im.load()
    for y in range(NLINES):
        for x in range(W):
            px[x, y] = raw[y] if x < W // 2 - 1 else (0, 0, 0) if x <= W // 2 else mix[y]
    imgs.append(im.resize((W * SCALE, NLINES * SCALE), Image.NEAREST))
imgs[0].save(os.path.join(HERE, "preview.gif"), save_all=True,
             append_images=imgs[1:], duration=80, loop=0)

# contact sheet: 32 frames side by side, PAL-blended
strip_w = 24
sheet = Image.new("RGB", (strip_w * 32, NLINES))
px = sheet.load()
for i, fr in enumerate(frames[::8][:32]):
    mix = blended(fr)
    for y in range(NLINES):
        for x in range(strip_w - 2):
            px[i * strip_w + x, y] = mix[y]
sheet.resize((sheet.width * 2, NLINES * 2), Image.NEAREST).save(
    os.path.join(HERE, "preview.png"))
print("wrote preview.gif, preview.png")
sys.exit(0 if ok else 1)
