#!/usr/bin/env python3
"""GOLDSHIP's flight recorded frame by frame, with every trick on, for a live
page that plays it back one C64 frame per screen refresh (60 a second).

Built on mockup.py's re-creation of the game (flight, sizes, six segments,
highlights, interlace.py's colour choice: flicker colours, alternating line
colours, the ghost byte for distant and dim bars), plus:
  * the ship from ship_aa.py: 81 angles following the eased roll and climb
    speed, each a two-frame pair;
  * the tilt antialiased by flicker: each segment's exact line offset x is
    shown as floor(x + 0.75) on even frames and floor(x + 0.25) on odd
    ones, so a half-line offset alternates between its two neighbours and
    the bars bank in half-line steps (goldship's rtilt tables, by parity).

Three recordings of the same flight:
  all    every trick;
  notilt every trick but the tilt flicker (offsets rounded);
  plain  16 colours, rounded offsets, the ship's single frame.

Each frame is stored as, per segment and window line, its colour (bits 0-3)
and the ghost byte (bit 4), deflated, plus the ship's frame and palette and
the border colour.

    python3 flight_video.py page.html [frames]
"""
import base64, json, math, os, sys, zlib
import numpy as np
import flyby3d as fb
import interlace as il
import mockup as mk
import ship_aa
import ship3d

HERE = os.path.dirname(os.path.abspath(__file__))
SEGDX = mk.SEGDX

def offsets(roll, parity, aa):
    """Per segment: lines the bar sits lower than at the light."""
    out = []
    for d in SEGDX:
        x = d / 72 * (-3 * roll / 8)
        out.append(int(math.floor(x + (0.75 if parity == 0 else 0.25))) if aa
                   else int(math.floor(6 + x + 0.5)) - 6)
    return out

def columns(bars, shipy, offs, mode):
    """Per segment: (colour per window line in frames 0 / 1, ghosted lines)."""
    vis = []
    for b in bars:
        z = fb.zof(b.st)
        vis.append((b, z, b.y - shipy, mk.FLYH[b.st]))
    ghost_of = [fb.bright(z) < il.GHOST_BELOW for _, z, _, _ in vis]
    out = []
    for k in range(6):
        tgt = np.zeros((fb.H, 3))
        who = np.full(fb.H, -1)
        depth = np.full(fb.H, np.inf)
        for i, (b, z, yrel, h) in enumerate(vis):
            top = int(round(fb.CY - yrel / z - h / 2)) + offs[k]
            hl = mk.highlight(yrel, z, h, k)
            base = mk.BANDS[b.pal] * fb.bright(z)
            for j in range(h):
                row = top + j
                if mk.WTOP <= row <= mk.WBOT and z < depth[row]:
                    depth[row] = z
                    who[row] = i
                    tgt[row] = fl_lin(fb.C64RGB[hl[j]] if j in hl else base[j * 48 // h])
        cols, ghosted = il.choose_column(tgt, who, ghost_of, mode)
        if mode == "single":
            ghosted[:] = False
        out.append((cols, ghosted))
    return out

def fl_lin(c):
    return (np.asarray(c, float) / 255) ** 2.2

# the autopilot's stick: (bits, frames); 1 up = nose down, 2 down = nose up,
# 4 left, 8 right.  Short taps leave the roll part way: smooth banking.
PLAN = [(0, 40), (8, 10), (0, 50), (8, 8), (0, 40), (4, 34), (0, 40), (4, 30), (0, 30),
        (2, 30), (0, 40), (8, 34), (0, 20), (1, 25), (0, 40), (6, 24), (0, 50),
        (9, 30), (0, 40), (4, 12), (0, 30)]

def fly(nframes, warmup=240):
    """Yield per frame: (bars, shipy, roll, vy, red, hit) after the warm-up,
    with the game's easing (climb speed +-3 a frame up to 64 = 1 unit a
    frame, roll one step every other frame)."""
    spawn_i = pal_i = 0
    shipy, vy, roll, hit = 0.0, 0, 0, 0
    bars = []
    def respawn(st):
        nonlocal spawn_i, pal_i
        b = mk.Bar(shipy + mk.SPAWN[spawn_i % len(mk.SPAWN)], mk.PALC[pal_i % len(mk.PALC)] & 3, st)
        spawn_i += 1
        pal_i += 1
        return b
    for st in (160, 80, 0):
        bars.append(respawn(st))
    plan = [b for b, n in PLAN for _ in range(n)]
    for f in range(warmup + nframes):
        stick = plan[f % len(plan)]
        ahead = [b for b in bars if b.st > 120 and abs(b.y - shipy) < 34]
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
        red = any(abs(b.y - shipy) < mk.HITR for b in bars)
        for b in bars:
            if b.st == fb.FLYD - 2 and abs(b.y - shipy) < mk.HITR:
                hit = 25
        if f >= warmup:
            yield bars, shipy, roll, vy, red, hit
        hit = max(0, hit - 1)
        for i, b in enumerate(bars):
            b.st += 1
            if b.st >= fb.FLYD:
                bars[i] = respawn(0)

def record(nframes):
    recs = {"all": [], "notilt": [], "plain": []}
    ship = []
    for n, (bars, shipy, roll, vy, red, hit) in enumerate(fly(nframes)):
        p = n & 1
        for name, mode, aa in (("all", "full", True), ("notilt", "full", False),
                               ("plain", "single", False)):
            cols = columns(bars, shipy, offsets(roll, p, aa), mode)
            fr = np.zeros((6, fb.H), np.uint8)
            for k, (c, g) in enumerate(cols):
                fr[k] = c[:, p] | (g.astype(np.uint8) << 4)
            recs[name].append(fr.tobytes())
        k = ship_aa.roll_index(roll) * 9 + ship_aa.pitch_index((vy + 64) >> 3)
        ship.append([k, int(red), 2 if hit else 0, roll])
        if n % 100 == 0:
            print(f"frame {n}/{nframes}", flush=True)
    return recs, ship

def page(path, nframes):
    recs, ship = record(nframes)
    pairs = ship_aa.pairs()
    data = {"W": fb.W, "H": fb.H, "CY": fb.CY, "n": nframes,
            "segx": mk.SEGX,
            "pairs": [["".join(map(str, sum(f, []))) for f in (f0, f1, s)]
                      for f0, f1, s, *_ in pairs],
            "ship": ship,
            "rec": {k: base64.b64encode(zlib.compress(b"".join(v), 9)).decode()
                    for k, v in recs.items()}}
    tpl = open(os.path.join(HERE, "flight_page.html")).read()
    open(path, "w").write(tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"))))
    print("wrote", path, os.path.getsize(path) // 1024, "KB")

if __name__ == "__main__":
    page(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 900)
