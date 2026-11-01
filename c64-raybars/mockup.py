#!/usr/bin/env python3
"""A mockup of GOLDSHIP with the colour studies applied: flicker colours,
alternating line colours and the ghost byte on the bars, the antialiased
(two-frame) ship.  A Python re-creation of the game, not the 6502 engine:
the flight, spawn cycles, sizes, six segments, roll tilt, highlight maths and
ship frames follow the game's tables; the colours are chosen as interlace.py
chooses them, through its PAL CRT model.

The flight: three bars at a time, 80 frames apart, from depth 12 to 1.2,
each spawned at the ship's height plus the next spawn offset with the next
palette.  An autopilot climbs or dives away from bars on a collision course
and rolls fully left and right every 200 frames; the ship turns red /
orange / yellow while a bar ahead is on a collision course.

    python3 mockup.py frames_dir
        # preview_mockup.gif (as a PAL CRT shows it), and in frames_dir each
        # moment's two frames, sharp (s) and through the CRT model (c)
"""
import math, os, re, sys
import numpy as np
from PIL import Image
import flyby3d as fb
import flicker as fl
import interlace as il
import flyby_spec as fs
import ship3d

HERE = os.path.dirname(os.path.abspath(__file__))
WTOP, WBOT = 62 - 51, 250 - 51        # the bars' lines, as rows of the window
SEGX = [0, 32, 96, 160, 224, 288, 320]   # six segments (window x); the light at 160
SEGDX = [-144, -96, -32, 32, 96, 144]
DROP6 = [4, 3, 1, 1, 3, 4]
HITR = 24
PALSHIP = [{1: (0x8A, 0x46, 0xAE), 2: (0x7C, 0x70, 0xDA), 3: (0xFF, 0xFF, 0xFF)},
           {1: (0x89, 0x40, 0x36), 2: (0x90, 0x5F, 0x25), 3: (0xD0, 0xDC, 0x71)}]

def table(path, name):
    """A .byte table from one of the generated .inc files."""
    text = open(os.path.join(HERE, path)).read()
    m = re.search(rf"^{name}:\n((?:\s+\.byte.*\n)+)", text, re.M)
    return [int(v, 16) for v in re.findall(r"\$([0-9a-f]{2})", m.group(1))]

FLYH = table("flyprof.inc", "flyh")
SPAWN = [l | h << 8 for l, h in zip(table("ship.inc", "yspawnl"), table("ship.inc", "yspawnh"))]
SPAWN = [v - 65536 if v & 0x8000 else v for v in SPAWN]
PALC = table("fly.inc", "palcyc")
PALS = [fb.GOLD, fb.P2, fb.P3, fb.P4]
BANDS = [fb.bands48(p) for p in PALS]

class Bar:
    def __init__(self, y, pal, st):
        self.y, self.pal, self.st = y, pal, st

def tilt(r):
    """Per segment: lines below the bar's line at the light, for roll r."""
    m = -3 * r / 8
    return [int(math.floor(6 + d / 72 * m + 0.5)) - 6 for d in SEGDX]

def highlight(yrel, z, h, k):
    """The game's highlight on segment k: {bar row: C64 colour}."""
    dyv = min(255, int(round(abs(yrel) / 10)))
    dy = dyv if yrel >= 0 else -dyv
    dz = int(round((z - fb.ZS) * 10))
    phi = int(round(math.atan2(dy, dz) * 128 / math.pi)) & 255
    lev = fb.hl_level(z)
    rs = fs.rowstart(h)
    out = {}
    for i in range(24):
        e = fs.SPEC[(fs.TH2[i] - phi) & 255] - (fs.HLTHR + DROP6[k])
        if e >= 0:
            for j in range(rs[i], rs[i + 1]):
                out[j] = fs.HLCOL[min(e, 2) + 3 - lev]
    return out

def render(bars, shipy, roll, att, red):
    """The two frames (sharp, sRGB uint8) the mockup shows."""
    offs = tilt(roll)
    vis = []
    for b in bars:
        z = fb.zof(b.st)
        yrel = b.y - shipy
        vis.append((b, z, yrel, FLYH[b.st]))
    ghost_of = [fb.bright(z) < il.GHOST_BELOW for _, z, _, _ in vis]
    frames = [np.zeros((fb.H, fb.W, 3), np.uint8) for _ in range(2)]
    gx = np.arange(fb.W) % 2 == 1
    for k in range(6):
        tgt = np.zeros((fb.H, 3))
        who = np.full(fb.H, -1)
        depth = np.full(fb.H, np.inf)
        for i, (b, z, yrel, h) in enumerate(vis):
            top = int(round(fb.CY - yrel / z - h / 2)) + offs[k]
            hl = highlight(yrel, z, h, k)
            base = BANDS[b.pal] * fb.bright(z)
            for j in range(h):
                row = top + j
                if WTOP <= row <= WBOT and z < depth[row]:
                    depth[row] = z
                    who[row] = i
                    c = fb.C64RGB[hl[j]] if j in hl else base[j * 48 // h]
                    tgt[row] = fl.lin(c)
        cols, ghosted = il.choose_column(tgt, who, ghost_of, "full")
        x0, x1 = SEGX[k], SEGX[k + 1]
        for f in range(2):
            frames[f][:, x0:x1] = fb.C64RGB[cols[:, f]][:, None, :]
            g = np.ix_(ghosted, gx[x0:x1])
            sub = frames[f][:, x0:x1]
            sub[g] = 0
            frames[f][:, x0:x1] = sub
    pair = SHIPS[att]
    for f in range(2):
        for r, line in enumerate(pair[f]):
            for c, v in enumerate(line):
                if v:
                    y, x = fb.CY - 10 + r, fb.W // 2 - 12 + 2 * c
                    frames[f][y, x:x + 2] = PALSHIP[red][v]
    return frames

SHIPS = [fl.ship_pair(r * ship3d.R, p * ship3d.P) for r, p in ship3d.ATT]
ATTIDX = {(r, p): i for i, (r, p) in enumerate(ship3d.ATT)}

def fly(nframes, export_every=4, warmup=240):
    """Run the flight; yield (frame number, the two frames) every
    export_every frames after the warm-up."""
    spawn_i = pal_i = 0
    shipy, vy, roll = 0.0, 0.0, 0
    bars = []
    def respawn(st):
        nonlocal spawn_i, pal_i
        b = Bar(shipy + SPAWN[spawn_i % len(SPAWN)], PALC[pal_i % len(PALC)] & 3, st)
        spawn_i += 1
        pal_i += 1
        return b
    for st in (160, 80, 0):
        bars.append(respawn(st))
    for f in range(warmup + nframes):
        # the autopilot: away from the nearest bar on (or near) a collision course
        ahead = [b for b in bars if b.st < 200 and abs(b.y - shipy) < 34]
        vert = 0
        if ahead:
            b = max(ahead, key=lambda b: b.st)
            vert = -1 if b.y >= shipy else 1          # bar above: dive, else climb
        ph = f % 200
        side = -1 if 40 <= ph < 100 else 1 if 140 <= ph < 200 else 0
        vy = max(-1, min(1, vy + vert * 3 / 64)) if vert else vy * 0.9
        shipy += vy
        if f % 2 == 0:
            roll += (1 if side * 8 > roll else -1 if side * 8 < roll else 0)
        red = int(any(b.st < 200 and abs(b.y - shipy) < HITR for b in bars))
        att = ATTIDX[(side, vert)]
        if f >= warmup and (f - warmup) % export_every == 0:
            yield f, render(bars, shipy, roll, att, red)
        for i, b in enumerate(bars):
            b.st += 1
            if b.st >= fb.FLYD:
                bars[i] = respawn(0)

if __name__ == "__main__":
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    gif = []
    for k, (f, fr) in enumerate(fly(240)):
        for nm, img in (("e", fr[0]), ("o", fr[1])):
            fl.save_png(img, os.path.join(out_dir, f"s{nm}{k:03d}.png"))
            fl.save_png(il.crt(img.astype(float)).astype(np.uint8),
                        os.path.join(out_dir, f"c{nm}{k:03d}.png"))
        gif.append(Image.fromarray(il.seen(fr)).resize((fb.W * 2, fb.H * 2), Image.LANCZOS))
    gif[0].save(os.path.join(HERE, "preview_mockup.gif"), save_all=True,
                append_images=gif[1:], duration=80, loop=0)
    print(f"wrote preview_mockup.gif and {len(gif)} moments to {out_dir}")
