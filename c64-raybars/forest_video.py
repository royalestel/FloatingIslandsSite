#!/usr/bin/env python3
"""A forest of bars, as a 60 fps video: what GOLDSHIP could look like with
no limit on the number of bars (the C64 can't build this many yet).

About 15 bars in flight (a new one every 16 frames), at constant thickness
and dimming steeply with distance (railshooter_video's "constant" style):
most scattered across the whole view, low and high, some crowding the
ship's height; about 40% with a gap (3 sections) somewhere along them.
The autopilot wanders, banking now and then (the gaps drift sideways); on
a collision course it banks for a gap it can reach, else climbs or dives
away.  Far bars rebuilt every other frame, the scene pitching with the
climb speed.

    python3 forest_video.py out.mp4
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import ideas_video as iv
import jitter_video as jv
import mockup as mk
import railshooter_video as rs
import ship_aa
import flicker as fl

rs.STYLE, rs.DIMPOW = "constant", 1.8
EVERY = 16                      # frames between spawns: about 15 bars in flight
LENGTH = 1320

_lines_off = rs.lines_off
def lines_off(b, z, px, sx, h0):
    return 0 if b.x0 is None else _lines_off(b, z, px, sx, h0)
rs.lines_off = lines_off        # bars without a gap: never off

def in_gap_at(b, x):
    return b.x0 is not None and rs.in_gap(int(math.floor((x - b.x0) / rs.W_S)))

def run(seed=11):
    rng = np.random.default_rng(seed)
    shipx, shipy, vy, roll, cam = 0.0, 0.0, 0, 0, 0.0
    bars, events, spawn_i = [], [], 0
    wander, wander_t = 0, 0
    for f in range(LENGTH + 240):
        if f % EVERY == 0:
            r = rng.random()
            # heights: a third near the ship's, the rest across the view (at
            # spawn, 12 m away, 1000 units is about 83 lines off centre)
            dy = rng.uniform(-90, 90) if r < 0.33 else rng.uniform(-1000, 1000)
            b = rs.Bar(shipy + dy, spawn_i % 4, None, "forest")
            if rng.random() < 0.4:
                b.x0 = shipx + rng.uniform(-14, 14) - rs.gap_u() * rs.W_S
            bars.append(b)
            spawn_i += 1
        # wandering: a bank now and then
        if wander_t <= 0:
            wander = rng.choice([0, 0, 4, 8])
            wander_t = int(rng.integers(30, 90))
        wander_t -= 1
        stick = wander
        threat = [b for b in bars if not b.done and b.st > 120 and abs(b.y - shipy) < mk.HITR + 8]
        if threat:
            b = max(threat, key=lambda b: b.st)
            left = fb.FLYD - 2 - b.st
            reach = left * rs.VXF * 0.45
            best = None
            if b.x0 is not None:
                for s in range(-60, 61):
                    x = shipx + s * rs.W_S / 3
                    if abs(x - shipx) <= reach and in_gap_at(b, x) and \
                            (best is None or abs(x - shipx) < abs(best - shipx)):
                        best = x
            if best is not None:
                stick = (8 if best > shipx else 4) if abs(best - shipx) > rs.W_S * 0.25 else 0
            else:
                # climb or dive: away from the bar, toward the emptier side
                above = sum(1 for o in bars if o.st > 100 and 0 < o.y - shipy < 120)
                below = sum(1 for o in bars if o.st > 100 and 0 < shipy - o.y < 120)
                up = b.y < shipy if abs(b.y - shipy) > 6 else above <= below
                stick = 2 if up else 1
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
        shipx += roll / 8 * rs.VXF
        cam += (vy / 64 * rs.PITCH_LINES - cam) * rs.PITCH_LAG
        for b in bars:
            if b.st == fb.FLYD - 2 and not b.done:
                b.done = True
                if abs(b.y - shipy) < mk.HITR:
                    events.append((f, "through a gap" if in_gap_at(b, shipx) else "HIT"))
            if b.shown is None or fb.zof(b.st) < rs.FAR or f % 2 == 0:
                b.shown = (b.st, b.y - shipy, shipx)
        if f >= 240:                                    # once the forest has filled
            last = events[-1] if events and f - events[-1][0] < 70 else None
            yield list(bars), shipx, shipy, roll, vy, cam, last, events
        for b in bars:
            b.st += 1
        bars = [b for b in bars if b.st < fb.FLYD]

def main(path):
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    v = iv.Video(path, W + 32, H + 76)
    for k, (bars, shipx, shipy, roll, vy, cam, last, events) in enumerate(run()):
        img = jv.frame_image(rs.frame_cols(bars, roll, k & 1, cam), k,
                             iv.ship_pair(pairs, roll, vy, k), None, None)
        canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 6), "A forest of bars", fill=(225, 222, 240), font=font)
        shown = sum(1 for b in bars if b.shown and
                    mk.WTOP <= fb.CY + cam - b.shown[1] / fb.zof(b.shown[0]) <= mk.WBOT)
        gaps = sum(1 for e in events if e[1] == "through a gap")
        hits = sum(1 for e in events if e[1] == "HIT")
        dr.text((16, 30), f"bars in flight {len(bars)}, on screen {shown}   roll {roll:+d}   "
                f"scene pitch {cam:+5.1f} lines   through gaps {gaps}, hits {hits}",
                fill=(150, 146, 170), font=small)
        if last:
            dr.text((W - 220, 6), last[1], fill=(255, 110, 100) if last[1] == "HIT"
                    else (208, 220, 113), font=font)
        canvas.paste(Image.fromarray(iv.tv(img)).resize((W, H), Image.BILINEAR), (16, 56))
        v.add(canvas)
        if k % 200 == 0:
            print(f"frame {k}/{LENGTH}", flush=True)
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    main(sys.argv[1])
