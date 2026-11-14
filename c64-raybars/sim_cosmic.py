#!/usr/bin/env python3
"""Fly cosmicstrings.prg on an emulated 6502 (py65), with an autopilot on
the joystick (straight, a loop-the-loop, a boost, a dive, another loop),
and render what it shows as 60 fps videos (one C64 frame per video frame):
with the CRT look and with sharp pixels.

Each frame runs the program's own IRQs and builder in order: the top IRQ,
every block (from its first record off the stack to the exit), the
vertical-blank copy, then build for the next frame.  Checks:
* every line of a block takes 63 cycles, 56 on the ship's sprite DMA lines;
* no lda (src),y crosses a page;
* each line shows the nearest bar covering it (the program's own bar list)
  at the right ramp row, black where no bar is;
* each bar's top and height match a floating-point projection of its row
  within 1.5 lines;
* the build fits the frame's free time (else that frame would repeat).

    cl65 -g -t none -C cosmic.cfg -Ln cosmicstrings.lbl -o cosmicstrings.prg cosmicstrings.s
    python3 sim_cosmic.py crt.mp4 sharp.mp4
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw
from c64cpu import MPU
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import swatch_loop_video as sv
import gen_cosmic as gc

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = int(os.environ.get("FRAMES", 700))
NTSC = int(os.environ.get("GOLD_NTSC", 0))          # 1: cosmicstrings_ntsc.prg (cl65 -Wa -DNTSC=1 ... -o cosmicstrings_ntsc.prg): 65-cycle lines, 263 lines
LINE, STEAL = 63 + 2 * NTSC, int(os.environ.get("STEAL", 7))
LINES = 263 if NTSC else 312
MUSIC = int(os.environ.get("MUSIC", 1500))      # the tune's cycles a frame, taken off the build's free time
WTOP = gc.WTOPR
BAND = range(gc.SPRY, gc.SPRY + 21)            # raster lines with sprite DMA

L = {}
for ln in open(os.path.join(HERE, "cosmicstrings_ntsc.lbl" if NTSC else "cosmicstrings.lbl")):
    _, a, nme = ln.split()
    L[nme.lstrip(".")] = int(a, 16)
prg = open(os.path.join(HERE, "cosmicstrings_ntsc.prg" if NTSC else "cosmicstrings.prg"), "rb").read()
mpu = MPU()
mem = mpu.memory
load = prg[0] | prg[1] << 8
mem[load:load + len(prg) - 2] = list(prg[2:])

TRAMP = 0x0400                                   # free RAM: a return target
def run_until(stop, limit=2_000_000):
    c = mpu.processorCycles
    while mpu.pc != stop:
        mpu.step()
        if mpu.processorCycles - c > limit:
            raise RuntimeError(f"runaway at {mpu.pc:04x}")
    return mpu.processorCycles - c

def push(v):
    mem[0x100 + mpu.sp] = v
    mpu.sp = (mpu.sp - 1) & 255

def irq(addr):
    """Enter an IRQ handler as the CPU would (frame pushed), run to its rti."""
    mpu.sp = 0xF0
    push(TRAMP >> 8); push(TRAMP & 255); push(0x20)
    mpu.pc = addr
    return run_until(TRAMP)

def call(addr):
    mpu.sp = 0xF0
    push((TRAMP - 1) >> 8); push((TRAMP - 1) & 255)
    mpu.pc = addr
    return run_until(TRAMP)

def joystick(f):
    """Autopilot: bits 1 up (nose down), 2 down (nose up), 16 fire.  A
    loop-the-loop (held long enough for one full turn), then on forward,
    weaving up and down between the bars."""
    j = 0
    if 60 <= f < 308:
        j |= 2                                   # the loop
    weave = [(340, 365, 2), (365, 415, 1), (415, 465, 2), (465, 515, 1), (515, 540, 2)]
    for a, b, bit in weave:
        if a <= f < b:
            j |= bit
    return j

# start-up: runs to the main loop (it built the first frame)
mpu.pc, mpu.sp = 2061, 0xFF
mem[0xDC00] = 0xFF
run_until(L["main"], 5_000_000)

ENTRY = {L["l_ne"]: (0, 0), L["l_no"]: (0, 1), L["l_be"]: (1, 0), L["l_bo"]: (1, 1)}
HY = [mem[L["hy"] + i] for i in range(256)]
HELDSW = int(open(os.path.join(HERE, 'cosmic.inc')).read().split('HELDSW   = ')[1].split()[0])
DHELD = int(open(os.path.join(HERE, 'cosmic.inc')).read().split('DHELD    = ')[1].split()[0])
def s8(v): return v - 256 if v & 128 else v
def s16(v): return v - 65536 if v & 0x8000 else v

stats = dict(badlen=0, cross=0, badcell=0, badpos=0, over=0, lines=0, worst=0.0,
             maxrec=0, maxbars=0, bars=0)
frames_rgb, info = [], []
def snapshot():
    out = []
    for i in range(mem[L["nb"]]):
        x = mem[L["ord"] + i]
        h = mem[L["bhh"] + x]
        rp = mem[L["rampl"] + h] | mem[L["ramph"] + h] << 8
        base = mem[L["bsl"] + x] | mem[L["bsh"] + x] << 8
        top = s16((base - (rp + h - 1)) & 0xFFFF)
        key = mem[L["bkl"] + x] | mem[L["bkh"] + x] << 8
        out.append((key, top, h, rp, mem[L["bk"] + x]))
    held = [(mem[L["hs"] + i], mem[L["he"] + i]) for i in range(mem[L["nh"]])]
    return [b[1:] for b in sorted(out, key=lambda b: b[0])], held   # nearest first
snap_built = snapshot()
irq(L["irqvbl"])                                 # take the first frame
snap_shown = snap_built
building, pending, updates = False, 0, 0
for f in range(FRAMES):
    # --- display frame f: top IRQ, the blocks
    mem[0xD012] = 0x31
    cyc_irq = irq(L["irqtop"])
    p = mem[L["fcount"]] & 1
    nblk = mem[L["nblkd"]]
    shown = np.zeros(gc.NLINES, int) - 1         # swatch per window line (-1 black)
    disp = 0
    for b in range(nblk):
        dline = mem[L["dline"] + b]
        D = dline + 2                            # the block's first raster line
        # irq1: frame pushed, S saved; irq2: S = the block's records
        mpu.sp = 0xF0
        push(TRAMP >> 8); push(TRAMP & 255); push(0x20)
        mem[L["sav_s"]] = mpu.sp
        mpu.sp = mem[L["curs"]]
        mpu.pc = L["blkgo"]
        c0 = mpu.processorCycles
        starts = []
        while mpu.pc != L["exitd"]:
            if mpu.pc in ENTRY or mpu.pc == L["exit"]:
                if mpu.pc == L["exit"] and starts and starts[-1][1] == "x":
                    pass
                else:
                    starts.append((mpu.processorCycles, mpu.pc))
                    if mpu.pc in ENTRY:
                        src = mem[L["src"]] | mem[L["src"] + 1] << 8
                        y = mpu.y
                        if (src & 255) + y > 255:
                            stats["cross"] += 1
                        ln = D + len(starts) - 1 - WTOP
                        if 0 <= ln < gc.NLINES:
                            shown[ln] = mem[src + y]
            mpu.step()
        for i in range(len(starts) - 1):
            ras = D + i
            want = LINE - STEAL if ras in BAND else LINE
            if starts[i + 1][0] - starts[i][0] != want:
                stats["badlen"] += 1
        stats["lines"] += len(starts) - 1
        disp += (len(starts) + 3) * LINE         # lines + IRQ entry and exit
        run_until(TRAMP)                         # the exit's rti
        cyc_irq += 0
    # what the program built for this frame (its bar list, still in memory
    # from the build before the copy): check the shown lines against it
    bars, held = snap_shown
    if f > 0:
        want = np.zeros(gc.NLINES, int) - 1
        done = np.zeros(gc.NLINES, bool)
        for top, h, rp, k in bars:               # nearest first
            for j in range(h):
                ln = top + j
                if 0 <= ln < gc.NLINES and not done[ln]:
                    done[ln] = True
                    want[ln] = mem[rp + h - 1 - j]
        for a_, e_ in held:                      # the far layer, behind
            for ln in range(a_, e_):
                if not done[ln]:
                    done[ln] = True
                    want[ln] = HELDSW
        bad = int(np.sum((shown != want) & ~((shown == 0) & (want == -1))))
        stats["badcell"] += bad
    # --- render the frame (window lines + the ship)
    col = mem[L["swtab"] + 256 * p: L["swtab"] + 256 * p + 128]
    img = np.zeros((fb.H, fb.W), int)
    x = np.arange(fb.W)
    for ln in range(gc.NLINES):
        k = shown[ln]
        if k <= 0:
            continue
        r = ln + 11                              # mock row
        c = col[32 * (r & 1) + k]
        g = col[64 + 32 * (r & 1) + k]
        img[r] = c
        if g:
            img[r, ((g >> (7 - x % 8)) & 1) == 1] = 0
    rgb = fb.C64RGB[img].astype(np.uint8)
    ptr0 = mem[0x87F8]
    mc = {1: mem[0xD025] & 15, 2: mem[0xD027] & 15, 3: mem[0xD026] & 15}
    for side in (0, 1):
        spr = mem[0x8000 + (ptr0 + side) * 64: 0x8000 + (ptr0 + side) * 64 + 63]
        for sy in range(21):
            bits = spr[3 * sy] << 16 | spr[3 * sy + 1] << 8 | spr[3 * sy + 2]
            for cx in range(12):
                v = (bits >> (22 - 2 * cx)) & 3
                if v:
                    yy = gc.SPRY + 1 + sy - 51
                    xx = 136 + side * 24 + 2 * cx
                    rgb[yy, xx:xx + 2] = fb.C64RGB[mc[v]]
    frames_rgb.append(rgb)
    # --- the build runs in the frame's free time: it is ready (and the
    # vertical blank takes it) once that has covered its cycles
    free = LINES * LINE - disp - cyc_irq - MUSIC - 21 * STEAL
    if building:
        pending -= free
        if pending <= 0:
            building = False
            mem[L["ready"]] = 1
    mem[0xDC00] = 0xFF ^ joystick(f)
    was = mem[L["ready"]]
    cyc_vbl = irq(L["irqvbl"])
    if was and not mem[L["ready"]]:
        snap_shown = snap_built
        updates += 1
    if mem[L["copied"]] and not building:
        mem[L["copied"]] = 0
        cyc = call(L["build"])
        pending, building = cyc, True
        snap_built = snapshot()
        stats["worst"] = max(stats["worst"], 100 * cyc / free)
        stats["over"] += cyc > free
        stats["maxrec"] = max(stats["maxrec"], mem[L["nrec"]])
        nb = mem[L["nb"]]
        stats["maxbars"] = max(stats["maxbars"], nb)
        stats["bars"] += nb
        # positions against a floating-point projection
        ang = (mem[L["angl"]] | mem[L["angh"]] << 8) / 65536 * 2 * math.pi
        s, c = math.sin(ang), math.cos(ang)
        cy = mem[L["cyi"]] + mem[L["cyf"]] / 256 + mem[L["cyff"]] / 65536
        cz = mem[L["czi"]] + mem[L["czf"]] / 256 + mem[L["czff"]] / 65536
        kc = mem[L["kc"]]
        wofs = s8(mem[L["wofs"]])
        far = gc_far = (mem[L["nearonly"]] & 0x80) != 0
        for i in range(nb):
            x_ = mem[L["ord"] + i]
            if far and (mem[L["bkl"] + x_] | mem[L["bkh"] + x_] << 8) >= (DHELD >> 8):
                continue                         # reused from the last full build
            k = mem[L["bk"] + x_]
            rz = (gc.ROWSP * s8((k - kc) & 255) - cz) * gc.UNIT
            t = s8((HY[k] - mem[L["cyi"]] - wofs) & 255)
            ry = (t + wofs - (cy - mem[L["cyi"]])) * gc.UNIT
            d = ry * s + rz * c
            u = ry * c - rz * s
            h = min(gc.HMAX, max(2, lv.bar_lines(d)))
            top = (2 * gc.CYL - 2 * gc.F * u / d - h) / 2
            hh_ = mem[L["bhh"] + x_]
            rp_ = mem[L["rampl"] + hh_] | mem[L["ramph"] + hh_] << 8
            ctop = s16(((mem[L["bsl"] + x_] | mem[L["bsh"] + x_] << 8) - (rp_ + hh_ - 1)) & 0xFFFF)
            if abs(ctop - top) > 1.5 or abs(mem[L["bhh"] + x_] - h) > 1.5:
                stats["badpos"] += 1
                if os.environ.get("DBG") and stats["badpos"] < 12:
                    print(f"f{f} ang {math.degrees(ang)%360:.1f} k {k} d {d:.2f} u {u:.2f} top {ctop} vs {top:.1f}  h {mem[L['bhh']+x_]} vs {h}")
        info.append((math.degrees(ang) % 360, (mem[L["spdl"]] | mem[L["spdh"]] << 8) / 185,
                     nb, nblk, 100 * cyc / free))
    else:
        info.append(info[-1] if info else (0, 1, 0, 0, 0))
    if f % 100 == 0:
        print(f"frame {f}: blocks {nblk}, bars {mem[L['nb']]}, build {info[-1][4]:.0f}% of free",
              flush=True)

ok = stats["badlen"] == 0 and stats["cross"] == 0 and stats["badcell"] == 0
print(f"lines shown {stats['lines']}, wrong length {stats['badlen']}, page crossings "
      f"{stats['cross']}, lines not showing the nearest bar {stats['badcell']}")
print(f"bars off the float projection by > 1.5 lines: {stats['badpos']} of {stats['bars']}")
print(f"build: worst {stats['worst']:.0f}% of a frame's free time; scene updates {updates} in "
      f"{FRAMES} frames ({50 * updates / FRAMES:.1f} a second at 50 Hz); most bars "
      f"{stats['maxbars']}, most record bytes {stats['maxrec']}")

def video(path, crt, Z=3):
    font, small = fl.fonts()
    W, H = fb.W * Z, fb.H * Z
    v = iv.Video(path, W + 32, H + 60)
    for f, rgb in enumerate(frames_rgb):
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        ang, spd, nb, nbk, load_ = info[f]
        dr.text((16, 8), f"cosmicstrings.prg (6502 sim)   pitch {ang:5.1f}   speed x{spd:.1f}   "
                f"bars {nb}   blocks {nbk}   build {load_:.0f}% of free   "
                f"{'CRT' if crt else 'sharp'}", fill=(170, 176, 210), font=small)
        look = lv.crt_look(rgb, Z) if crt else Image.fromarray(rgb).resize((W, H), Image.NEAREST)
        canvas.paste(look, (16, 40))
        v.add(canvas)
    v.close()
    print("wrote", path)

if len(sys.argv) > 2:
    video(sys.argv[1], True)
    video(sys.argv[2], False)
sys.exit(0 if ok else 1)
