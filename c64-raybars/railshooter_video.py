#!/usr/bin/env python3
"""A GOLDSHIP rail-shooter mockup as a 60 fps video (one C64 frame per video
frame, through interlace.py's PAL CRT model), on the re-creation in
flight_video.py / ideas_video.py.

  * Bars that thin 3 lines a section to gaps (ideas_video.gap_thin), the
    dim colours excised; banking drifts the ship sideways (the fast scroll).
  * Up to 5 bars in flight, in scripted waves at a fixed rate (banking
    doesn't change the density): a single bar, a doorway (one above, one
    below), a wall (three stacked, gaps lined up: bank or hit), a corridor
    (three in a row, gaps lined up), a slalom (gaps left, right, left ...).
  * Distant bars (beyond FAR m) are rebuilt every other frame only, as the
    program would to save time: between rebuilds they show the last state.
  * The scene pitches: a camera pitch that follows the climb speed with a
    lag shifts every bar the same number of lines (the vanishing point
    moves), on top of the parallax of rising and sinking.

    python3 railshooter_video.py out.mp4             # thinning to gaps
    python3 railshooter_video.py out.mp4 constant    # constant thickness,
                                                     # plain gaps, far bars dimmer
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

STEP = 3
FAR = 6.0                      # metres: bars farther than this rebuild every other frame
PITCH_LINES = 32               # scene shift at full climb speed (about 9 degrees)
PITCH_LAG = 0.12               # the camera eases this fraction of the way each frame
VXF = iv.VX * 3                # sideways drift at full bank, metres a frame
W_S = 64 * fb.ZS / fb.F        # a section's width at the ship's distance, metres
T, PERIOD = iv.gap_layout(STEP)
# STYLE "thin": bars thin 3 lines a section to their gaps; "constant": full
# thickness, broken by gaps GAPW sections wide at the same places.  DIMPOW
# steepens the dimming with distance (brightness ** DIMPOW).
STYLE, GAPW, DIMPOW = "thin", 3, 1.0

def gap_u():
    """A gap's centre, in sections from x0."""
    return T + iv.GM + T + iv.GG / 2 if STYLE == "thin" else PERIOD - GAPW / 2

def mid_u():
    """The full middle's centre."""
    return T + iv.GM / 2 if STYLE == "thin" else (PERIOD - GAPW) / 2

def in_gap(u):
    return iv.gap_e(STEP, u) is None if STYLE == "thin" else u % PERIOD >= PERIOD - GAPW

def lines_off(b, z, px, sx, h0):
    """Lines off a bar of h0 lines at screen x px (h0 or more: a gap)."""
    if STYLE == "thin":
        return iv.gap_thin(b, z, px, sx, STEP, h0)
    w = 64 * z / fb.F
    return h0 if in_gap(int(math.floor((sx - b.x0) / w + px / 64))) else 0

def dim(z):
    return fb.bright(z) ** DIMPOW

class Bar:
    def __init__(self, y, pal, x0, wave):
        self.y, self.pal, self.x0, self.st, self.wave = y, pal, x0, 0, wave
        self.done = False
        self.shown = None          # (st, yrel, shipx) at the last rebuild

def gap_bar(lane_y, dy, x_gap, pal, wave):
    """A bar dy above the lane with a gap centred at world x x_gap."""
    return Bar(lane_y + dy, pal, x_gap - gap_u() * W_S, wave)

def full_bar(lane_y, dy, x_mid, pal, wave):
    """A bar dy above the lane with its full middle at world x x_mid."""
    return Bar(lane_y + dy, pal, x_mid - mid_u() * W_S, wave)

# the waves: (frame, name, [(kind, dy, x offset from the ship at spawn, palette)])
WAVES = []
def wave(at, name, bars, step=0):
    for i, b in enumerate(bars):
        WAVES.append((at + i * step, name, [b]))
def stack(at, name, bars):
    WAVES.append((at, name, bars))
wave(0, "single bar: a gap to the right", [("gap", 0, 5.0, 0)])
stack(90, "doorway: one above, one below", [("full", 62, 0, 1), ("full", -62, 0, 1)])
stack(240, "wall: three stacked, gaps lined up -- bank!",
      [("gap", 48, -7.0, 2), ("gap", 0, -7.0, 2), ("gap", -48, -7.0, 2)])
wave(400, "corridor: gaps lined up", [("gap", 0, 0.0, 3)] * 3, step=48)
wave(640, "slalom", [("gap", 0, 6.0, 0), ("gap", 0, 0.0, 1), ("gap", 0, 6.0, 2),
                     ("gap", 0, 0.0, 3)], step=48)
stack(930, "wall again, gaps to the right",
      [("gap", 48, 8.0, 1), ("gap", 0, 8.0, 1), ("gap", -48, 8.0, 1)])
stack(1040, "doorway", [("full", 62, 0, 2), ("full", -62, 0, 2)])
# (at most 5 bars in flight: a bar flies 240 frames)
# pitch wobbles, to show the scene pitch: climb, dive twice as long, climb
# (or the reverse), ending at the same height: (frame, frames, stick)
MOVES = []
for at, first, n in [(30, 2, 18), (150, 1, 18), (300, 2, 16), (560, 1, 18), (800, 2, 18),
                     (1000, 1, 18), (1190, 2, 18)]:
    other = 3 - first
    MOVES += [(at, n, first), (at + n, 2 * n, other), (at + 3 * n, n, first)]
LENGTH = 1300

def run():
    """Yield per frame: (bars with their shown state, shipx, shipy, roll,
    vy, camera pitch offset in lines, wave name, last event)."""
    shipx, shipy, vy, roll, cam = 0.0, 0.0, 0, 0, 0.0
    bars, events, name = [], [], ""
    moves = {}
    for at, n, s in MOVES:
        for f in range(at, at + n):
            moves[f] = s
    pending = sorted(WAVES, key=lambda w: w[0])
    for f in range(LENGTH):
        while pending and pending[0][0] <= f:
            _, name, spec = pending.pop(0)
            for kind, dy, dx, pal in spec:
                mk_ = gap_bar if kind == "gap" else full_bar
                bars.append(mk_(shipy, dy, shipx + dx, pal, name))
        # the autopilot: bank for a gap in the nearest bar on a collision
        # course (the stick's sideways part), climb / dive on the script
        stick = moves.get(f, 0)
        threat = [b for b in bars if not b.done and abs(b.y - shipy) < mk.HITR + 6]
        if threat:
            b = max(threat, key=lambda b: b.st)
            best = None
            for s in range(-60, 61):
                x = shipx + s * W_S / 3
                u = int(math.floor((x - b.x0) / W_S))
                if in_gap(u) and (best is None or abs(x - shipx) < abs(best - shipx)):
                    best = x
            if best is not None and abs(best - shipx) > W_S * 0.25:
                # aim to arrive: bank harder the farther and the sooner
                stick |= 8 if best > shipx else 4
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
        shipx += roll / 8 * VXF
        cam += (vy / 64 * PITCH_LINES - cam) * PITCH_LAG
        outcome = []
        for b in bars:
            if b.st == fb.FLYD - 2 and not b.done:
                b.done = True
                if abs(b.y - shipy) >= mk.HITR:
                    outcome.append("clear")
                elif lines_off(b, fb.ZS, 0, shipx, iv.HREF) >= iv.HREF:
                    outcome.append("through a gap")
                else:
                    outcome.append("HIT")
        if outcome:                     # a wave's bars arrive together: the worst
            events.append((f, "HIT" if "HIT" in outcome else
                           "through a gap" if "through a gap" in outcome else "clear"))
        for b in bars:          # rebuild: near bars every frame, far ones every other
            if b.shown is None or fb.zof(b.st) < FAR or f % 2 == 0:
                b.shown = (b.st, b.y - shipy, shipx)
        last = events[-1] if events and f - events[-1][0] < 80 else None
        yield [b for b in bars], shipx, shipy, roll, vy, cam, name, last
        for b in bars:
            b.st += 1
        bars = [b for b in bars if b.st < fb.FLYD]

def frame_cols(bars, roll, p, cam):
    """Per segment and window line: the colour on frame parity p (bits 0-3)
    and the ghost byte (bit 4), every bar drawn from its shown state."""
    vis = []
    for b in bars:
        st, yrel, sx = b.shown
        vis.append((b, fb.zof(st), yrel, mk.FLYH[st], sx))
    ghost_of = [dim(z) < il.GHOST_BELOW for _, z, _, _, _ in vis]
    offs = fv.offsets(roll, p, False)
    out = np.zeros((6, fb.H), np.uint8)
    for k in range(6):
        tgt = np.zeros((fb.H, 3))
        who = np.full(fb.H, -1)
        depth = np.full(fb.H, np.inf)
        for i, (b, z, yrel, h0, sx) in enumerate(vis):
            d = lines_off(b, z, iv.SEGC[k], sx, h0)
            if d >= h0:
                continue                                    # a gap
            top = int(round(fb.CY + cam - yrel / z - h0 / 2)) + offs[k] + d // 2
            hl = mk.highlight(yrel, z, h0, k)
            base = mk.BANDS[b.pal] * dim(z)
            rows = [fb.C64RGB[hl[j]] if j in hl else base[j * 48 // h0] for j in range(h0)]
            for jj, j in enumerate(iv.excise(rows, d)):
                row = top + jj
                if mk.WTOP <= row <= mk.WBOT and z < depth[row]:
                    depth[row] = z
                    who[row] = i
                    tgt[row] = fv.fl_lin(rows[j])
        cols, ghosted = il.choose_column(tgt, who, ghost_of, "full")
        out[k] = cols[:, p] | (ghosted.astype(np.uint8) << 4)
    return out

def main(path):
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    v = iv.Video(path, W + 32, H + 76)
    for k, (bars, shipx, shipy, roll, vy, cam, name, last) in enumerate(run()):
        img = jv.frame_image(frame_cols(bars, roll, k & 1, cam), k,
                             iv.ship_pair(pairs, roll, vy, k), None, None)
        canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 6), f"wave: {name}", fill=(225, 222, 240), font=font)
        far = sum(1 for b in bars if fb.zof(b.st) >= FAR)
        dr.text((16, 30), f"bars in flight {len(bars)} ({far} far, rebuilt every other frame)   "
                f"roll {roll:+d}   scene pitch {cam:+5.1f} lines", fill=(150, 146, 170), font=small)
        if last:
            dr.text((W - 220, 6), f"last bar: {last[1]}",
                    fill=(255, 110, 100) if last[1] == "HIT" else (208, 220, 113), font=font)
        canvas.paste(Image.fromarray(iv.tv(img)).resize((W, H), Image.BILINEAR), (16, 56))
        v.add(canvas)
        if k % 200 == 0:
            print(f"frame {k}/{LENGTH}", flush=True)
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "constant":
        STYLE, DIMPOW = "constant", 1.8
    main(sys.argv[1])
