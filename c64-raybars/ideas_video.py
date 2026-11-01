#!/usr/bin/env python3
"""Two GOLDSHIP ideas as 60 fps videos (one C64 frame per video frame,
through interlace.py's PAL CRT model), on flight_video.py's re-creation.

Tapered bars.  Instead of a cylinder of constant radius, a bar thins along
its length.  Each of the six segments shows the bar at its own height:
  spindle  thick in the middle, thin at both ends: segments 0/5, 1/4 and 2/3
           share heights, which fits goldship's 3 mirrored columns per bar;
  wedge    thick at the left end, thin at the right: six heights, so six
           columns per bar (twice the column memory and copying).
    python3 ideas_video.py taper out.mp4

Banking sets the difficulty.  Banking right shortens the time between
spawns and spawns bars closer to the ship's height; banking left lengthens
it and spreads them out.  Level: one bar every 80 frames (3 in flight, as
now); full right: every 48 (5 in flight); full left: every 120 (2).
    python3 ideas_video.py density out.mp4
"""
import math, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flight_video as fv
import interlace as il
import jitter_video as jv
import mockup as mk
import ship_aa
import flicker as fl

TAPERS = {"straight": [1, 1, 1, 1, 1, 1],
          "spindle": [0.4, 0.72, 1, 1, 0.72, 0.4],
          "wedge": [1, 0.88, 0.74, 0.6, 0.46, 0.32]}

def visible(bars, shipy):
    """The bars with their depth, height relative to the ship, profiled height."""
    vis = []
    for b in bars:
        z = fb.zof(b.st)
        vis.append((b, z, b.y - shipy, mk.FLYH[b.st]))
    return vis

def frame_cols(bars, shipy, roll, p, taper):
    """flight_video.columns for frame parity p, with a height factor per
    segment (the colour rows the bar's own, resampled to that height)."""
    vis = visible(bars, shipy)
    ghost_of = [fb.bright(z) < il.GHOST_BELOW for _, z, _, _ in vis]
    out = np.zeros((6, fb.H), np.uint8)
    offs = fv.offsets(roll, p, False)
    for k in range(6):
        tgt = np.zeros((fb.H, 3))
        who = np.full(fb.H, -1)
        depth = np.full(fb.H, np.inf)
        for i, (b, z, yrel, h0) in enumerate(vis):
            h = max(2, int(round(h0 * TAPERS[taper][k])))
            top = int(round(fb.CY - yrel / z - h / 2)) + offs[k]
            hl = mk.highlight(yrel, z, h, k)
            base = mk.BANDS[b.pal] * fb.bright(z)
            for j in range(h):
                row = top + j
                if mk.WTOP <= row <= mk.WBOT and z < depth[row]:
                    depth[row] = z
                    who[row] = i
                    tgt[row] = fv.fl_lin(fb.C64RGB[hl[j]] if j in hl else base[j * 48 // h])
        cols, ghosted = il.choose_column(tgt, who, ghost_of, "full")
        out[k] = cols[:, p] | (ghosted.astype(np.uint8) << 4)
    return out

def tv(img, top=0, bot=None):
    pad = np.pad(img[max(0, top - 1):bot], ((0, 0), (8, 8), (0, 0)))
    return il.crt(pad.astype(float))[1 if top else 0:, 8:-8].astype(np.uint8)

class Video:
    def __init__(self, path, w, h, fps=60):
        self.w, self.h = w + w % 2, h + h % 2
        self.p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
                                   "-pix_fmt", "rgb24", "-s", f"{self.w}x{self.h}", "-r", str(fps),
                                   "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "12",
                                   "-pix_fmt", "yuv420p", "-movflags", "+faststart", path],
                                  stdin=subprocess.PIPE)
    def add(self, im):
        self.p.stdin.write(im.crop((0, 0, self.w, self.h)).tobytes())
    def close(self):
        self.p.stdin.close()
        self.p.wait()

def ship_pair(pairs, roll, vy, k):
    return pairs[ship_aa.roll_index(roll) * 9 + ship_aa.pitch_index((vy + 64) >> 3)][k & 1]

# ---- tapered bars: the banking demo, three ways -------------------------------------
def taper_video(path):
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z, lab = 3, 26
    top = int(fb.CY - 26 / fb.zof(fv.BANK_T)) - 16
    bot = fb.CY + 13
    sh, sw = (bot - top) * Z, fb.W * Z
    opts = [("Straight: a cylinder (now)", "straight"),
            ("Spindle: thin at both ends (fits the 3 mirrored columns)", "spindle"),
            ("Wedge: thick at the left end, thin at the right (needs 6 columns)", "wedge")]
    v = Video(path, sw + 32, len(opts) * (sh + lab) + 16)
    seq = list(fv.bank())
    for loop in range(2):
        for k, (bars, shipy, roll, vy, red, hit) in enumerate(seq):
            canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
            dr = ImageDraw.Draw(canvas)
            for i, (text, taper) in enumerate(opts):
                img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, taper), k,
                                     ship_pair(pairs, roll, vy, k), None, None)
                y = 8 + i * (sh + lab)
                dr.text((16, y + 4), text, fill=(200, 196, 220), font=small)
                canvas.paste(Image.fromarray(tv(img, top, bot)).resize((sw, sh), Image.BILINEAR),
                             (16, y + lab))
            v.add(canvas)
    v.close()
    print("wrote", path)

# ---- banking sets the difficulty ------------------------------------------------------
# the autopilot holds the stick right for 6 s, centres, holds it left
# (the roll eases back to level whenever the stick is centred)
PLAN = [(8, 300), (0, 40), (4, 300), (0, 40)]

def interval(roll):
    """Frames between spawns: 80 level, 48 full right, 120 full left."""
    return int(round(80 * 0.6 ** (roll / 8))) if roll > 0 else int(round(80 * 1.5 ** (-roll / 8)))

def spread(roll):
    """Spawn offsets scaled: 1 level, 0.55 full right, 1.5 full left."""
    return 0.55 ** (roll / 8) if roll > 0 else 1.5 ** (-roll / 8)

def fly_density(nframes, warmup=200):
    shipy, vy, roll = 0.0, 0, 0
    bars, spawn_i, since = [], 0, 999
    plan = [b for b, n in PLAN for _ in range(n)]
    for f in range(warmup + nframes):
        if since >= interval(roll):
            bars.append(mk.Bar(shipy + mk.SPAWN[spawn_i % len(mk.SPAWN)] * spread(roll),
                               mk.PALC[spawn_i % len(mk.PALC)] & 3, 0))
            spawn_i += 1
            since = 0
        since += 1
        stick = plan[f % len(plan)]
        ahead = [b for b in bars if b.st > 110 and abs(b.y - shipy) < 34]
        if ahead:
            b = max(ahead, key=lambda b: b.st)
            stick = (stick & 12) | (1 if b.y >= shipy else 2)
        if stick & 2 and not stick & 1:
            vy = min(64, vy + 3)
        elif stick & 1 and not stick & 2:
            vy = max(-64, vy - 3)
        else:
            vy = max(0, vy - 3) if vy > 0 else min(0, vy + 3)
        shipy += vy / 64
        if f % 2 == 0:
            if stick & 4 and not stick & 8:
                roll = max(-8, roll - 1)
            elif stick & 8 and not stick & 4:
                roll = min(8, roll + 1)
            else:
                roll -= (roll > 0) - (roll < 0)
        if f >= warmup:
            yield list(bars), shipy, roll, vy
        for b in bars:
            b.st += 1
        bars = [b for b in bars if b.st < fb.FLYD]

def density_video(path, nframes=1200):
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    v = Video(path, W + 32, H + 60)
    for k, (bars, shipy, roll, vy) in enumerate(fly_density(nframes)):
        img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, "spindle"), k,
                             ship_pair(pairs, roll, vy, k), None, None)
        canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
        dr = ImageDraw.Draw(canvas)
        side = "right: harder" if roll > 0 else "left: easier" if roll < 0 else "level"
        dr.text((16, 10), f"Banking sets the difficulty -- roll {roll:+d} ({side})   "
                f"a bar every {interval(roll)} frames   bars in flight: {len(bars)}",
                fill=(200, 196, 220), font=small)
        dr.text((16, 30), "Spindle-tapered bars. More than 3 bars in flight needs the "
                "build optimisations.", fill=(140, 136, 160), font=small)
        canvas.paste(Image.fromarray(tv(img)).resize((W, H), Image.BILINEAR), (16, 52))
        v.add(canvas)
        if k % 200 == 0:
            print(f"frame {k}/{nframes}", flush=True)
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    {"taper": taper_video, "density": density_video}[sys.argv[1]](sys.argv[2])
