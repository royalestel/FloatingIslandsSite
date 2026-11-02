#!/usr/bin/env python3
"""Glowing bars filling 3D space: a look study, not a game.

Bars of constant thickness at random heights fill the space ahead (a new
one every SPAWN frames); the ship only climbs and dives (no roll, no tilt)
while new bars come into view far away.  The bars are classic raster bars:
a white core through pale and light blue to deep blue edges, dimmed with
distance, drawn with the colour tricks: flicker pairs of C64 colours with
the phase swapped on alternate lines (for the PAL delay line), the ghost
byte on distant and dim bars, through interlace.py's PAL CRT model.  The
scene pitches with the climb speed (railshooter_video's lagging camera).

The profile estimates the C64's cost per frame: the display (every line of
an IRQ block costs the CPU the whole line, plus 4 lines per block for its
IRQs) and the build (2,600 cycles a frame plus per bar on screen 1,500 and
24 a row; bars beyond FAR m rebuilt every other frame), against the
18,500 cycles a frame has once the top IRQ and the sprite are paid for.

    python3 glow_video.py out.mp4 [spawn]  # the video (a bar every 10 frames)
    python3 glow_video.py --profile out.png  # the cost profile, 3 densities
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flight_video as fv
import interlace as il
import ideas_video as iv
import jitter_video as jv
import mockup as mk
import ship_aa
import flicker as fl

DIMPOW, FAR, SEP = 1.8, 6.0, 6
PITCH_LINES, PITCH_LAG = 32, 0.12
FRAME_FREE = 18495                      # cycles a frame for display + build
STOPS = [(0.0, (22, 18, 96)), (0.3, (62, 49, 162)), (0.55, (124, 112, 218)),
         (0.8, (176, 200, 245)), (1.0, (255, 255, 255))]

# the colours the bars' flicker pairs may use: black, blue, purple, light
# blue, cyan, the greys and white (no browns or greens in the dim ones)
BLUES = [0, 6, 4, 14, 3, 11, 12, 15, 1]

def glow(i):
    """The bar's colour (sRGB) at glow i, 0 at its edges .. 1 at its core."""
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if i <= b:
            t = (i - a) / (b - a)
            return np.array(ca, float) * (1 - t) + np.array(cb, float) * t
    return np.array(STOPS[-1][1], float)

def dim(z):
    return fb.bright(z) ** DIMPOW

class Bar:
    def __init__(self, y):
        self.y, self.st, self.shown = y, 0, None

def run(spawn, frames, seed=7, warmup=240):
    """Per frame: bars (with their shown state), ship height, climb speed,
    camera pitch.  The ship climbs and dives on a slow wave."""
    rng = np.random.default_rng(seed)
    shipy, cam, bars = 0.0, 0.0, []
    for f in range(warmup + frames):
        if f % spawn == 0:
            bars.append(Bar(shipy + rng.uniform(-1100, 1100)))
        g = f - warmup
        vy = int(64 * math.sin(2 * math.pi * g / 420) * (0.6 + 0.4 * math.sin(g / 97)))
        shipy += vy / 64
        cam += (vy / 64 * PITCH_LINES - cam) * PITCH_LAG
        for b in bars:
            if b.shown is None or fb.zof(b.st) < FAR or f % 2 == 0:
                b.shown = (b.st, b.y - shipy)
        if f >= warmup:
            yield list(bars), vy, cam
        for b in bars:
            b.st += 1
        bars = [b for b in bars if b.st < fb.FLYD]

def placed(bars, cam):
    """Each bar's (top line, height, depth, palette rows) as shown."""
    out = []
    for b in bars:
        st, yrel = b.shown
        z, h = fb.zof(st), mk.FLYH[st]
        top = int(round(fb.CY + cam - yrel / z - h / 2))
        if top + h <= mk.WTOP or top > mk.WBOT:
            continue
        d = dim(z)
        rows = [glow((1 - abs(2 * (j + 0.5) / h - 1)) ** 0.9) * d for j in range(h)]
        out.append((top, h, z, rows, d))
    return out

def column(bars, cam, p):
    """The window's colours (one column: no tilt, all segments alike) on
    frame parity p, ghost byte in bit 4."""
    pl = placed(bars, cam)
    tgt = np.zeros((fb.H, 3))
    who = np.full(fb.H, -1)
    depth = np.full(fb.H, np.inf)
    for i, (top, h, z, rows, d) in enumerate(pl):
        for j in range(h):
            r = top + j
            if mk.WTOP <= r <= mk.WBOT and z < depth[r]:
                depth[r], who[r] = z, i
                tgt[r] = fv.fl_lin(rows[j])
    cols, ghosted = il.choose_column(tgt, who, [d < il.GHOST_BELOW for *_, d in pl], "full",
                                     allowed=BLUES)
    return cols[:, p] | (ghosted.astype(np.uint8) << 4)

def cost(bars, cam):
    """The C64 estimate for one frame: (lines covered, blocks, display
    cycles, build cycles, bars on screen)."""
    pl = placed(bars, cam)
    cov = np.zeros(fb.H + 1, bool)
    for top, h, *_ in pl:
        cov[max(mk.WTOP, top):min(mk.WBOT + 1, top + h)] = True
    # blocks: covered runs closer than SEP black lines share one
    spans, start, last = [], None, None
    for r in range(mk.WTOP, mk.WBOT + 1):
        if cov[r]:
            if start is None:
                start = r
            elif r - last > SEP:
                spans.append((start, last))
                start = r
            last = r
    if start is not None:
        spans.append((start, last))
    display = sum(b - a + 1 + 4 for a, b in spans) * 63
    build = 2600
    for top, h, z, *_ in pl:
        c = 1500 + 24 * h
        build += c / 2 if z >= FAR else c
    return int(cov.sum()), len(spans), display, int(build), len(pl)

def profile(path, frames=900):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = []
    fig, axes = plt.subplots(3, 1, figsize=(10, 8.2), sharex=True, sharey=True)
    ink, muted, grid = "#2a2838", "#6e6a80", "#e6e4ee"
    for ax, spawn in zip(axes, (24, 16, 10)):
        data = [cost(b, c) for b, vy, c in run(spawn, frames)]
        lines, blocks, disp, build, on = map(np.array, zip(*data))
        need = disp + build
        x = np.arange(frames)
        ax.fill_between(x, 0, disp, color="#8fa8e8", lw=0, label="display (bar lines)")
        ax.fill_between(x, disp, need, color="#3b5bc4", lw=0, label="build")
        ax.axhline(FRAME_FREE, color=ink, lw=1.2, label="a PAL frame's free time (18,500)")
        over = (need > FRAME_FREE).mean() * 100
        ax.set_title(f"a bar every {spawn} frames: {240 // spawn} in flight, "
                     f"{on.mean():.1f} on screen on average, over the frame {over:.0f}% of the time",
                     loc="left", fontsize=10, color=ink)
        ax.set_ylim(0, 36000)
        ax.set_ylabel("cycles", color=muted, fontsize=9)
        ax.grid(axis="y", color=grid, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(grid)
        ax.tick_params(colors=muted, labelsize=8)
        rows.append((spawn, 240 // spawn, on.mean(), on.max(), lines.mean(), lines.max(),
                     blocks.mean(), disp.mean(), build.mean(), need.mean(), need.max(), over))
    axes[0].legend(loc="upper left", frameon=False, fontsize=9, ncol=3)
    axes[-1].set_xlabel("frame", color=muted, fontsize=9)
    fig.suptitle("Glowing bars filling space: estimated C64 cost per frame", x=0.06, ha="left",
                 fontsize=12, color=ink)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    print("spawn in-flight  on-screen(avg/max)  lines(avg/max)  blocks  display  build  "
          "total(avg/max)  over%")
    for r in rows:
        print("%5d %9d %10.1f / %-4d %8.0f / %-4d %7.1f %8.0f %6.0f %8.0f / %-6d %5.0f" % r)

def video(path, spawn=10, frames=900):
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    v = iv.Video(path, W + 32, H + 60)
    for k, (bars, vy, cam) in enumerate(run(spawn, frames)):
        col = column(bars, cam, k & 1)
        img = jv.frame_image(np.repeat(col[None, :], 6, axis=0), k,
                             iv.ship_pair(pairs, 0, vy, k), None, None)
        lines, blocks, disp, build, on = cost(bars, cam)
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), f"bars in flight {len(bars)}, on screen {on}   lines covered {lines}   "
                f"scene pitch {cam:+5.1f} lines   C64 estimate "
                f"{100 * (disp + build) / FRAME_FREE:4.0f}% of a frame",
                fill=(170, 176, 210), font=small)
        canvas.paste(Image.fromarray(iv.tv(img)).resize((W, H), Image.BILINEAR), (16, 40))
        v.add(canvas)
        if k % 200 == 0:
            print(f"frame {k}/{frames}", flush=True)
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    if sys.argv[1] == "--profile":
        profile(sys.argv[2])
    else:
        video(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10)
