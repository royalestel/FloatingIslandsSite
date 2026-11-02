#!/usr/bin/env python3
"""The ship flies a loop-the-loop through a slab of glowing bars, then
straightens out: a look study (60 fps video, one C64 frame per video frame,
through interlace.py's PAL CRT model).

The bars are fixed in space (horizontal, across the view, at random
heights through a slab), and a chase camera ZS metres behind the ship turns
with it, so the bars stay horizontal on screen as the loop sweeps the view
through them.  Bars are glow_video's white-to-blue raster bars, full
brightness up close until the near clip takes them all at once (no shadow
past the ship), dimming with distance beyond the ship.

Distance shown by the idle byte, which can change every line: a bar line
takes the sparsest pattern that still carries its brightness, and its
colours are chosen that much brighter --
    $00  every pixel        (near)
    $55  1 pixel of 2
    $77  1 pixel of 4
    $7f  1 pixel of 8       (farthest)
so distant bars keep their hue instead of sinking into dark colours.

    python3 loop_video.py out.mp4
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flight_video as fv
import glow_video as gv
import interlace as il
import ideas_video as iv
import ship_aa
import flicker as fl

F, R_BAR = fb.F, fb.R          # focal length (lines), bar radius (metres)
ZS, NEAR, FAR = fb.ZS, fb.Z1, fb.Z0
V = (fb.Z0 - fb.Z1) / (fb.FLYD - 1)     # forward speed, metres a frame (the game's)
LOOP_R = 1.8                   # loop radius, metres
PATTERNS = [(1.0, 0x00), (0.5, 0x55), (0.25, 0x77), (0.125, 0x7f)]   # (coverage, idle byte)
WTOP, WBOT = 11, 199           # the bars' window lines (mockup.py)

def brightness(z):
    """1 up to just beyond the ship, then dimming with distance (no shadow)."""
    if z <= ZS + 0.25:
        return 1.0
    return max(0.0, 1.0 - 0.75 * (z - ZS - 0.25) / (FAR - ZS - 0.25)) ** gv.DIMPOW

def pattern(b):
    """The sparsest pattern whose coverage still carries brightness b."""
    for cov, byte in reversed(PATTERNS):
        if cov >= b:
            return cov, byte
    return 1.0, 0x00

def world(seed=21):
    """Bars fixed in space: (height, distance along the flight), one every
    0.28 m forward, heights through a slab 16 m deep."""
    rng = np.random.default_rng(seed)
    zs = np.arange(-20.0, 60.0, 0.28)
    return [(rng.uniform(-8, 8), z) for z in zs]

def path(straight1=150, straight2=210):
    """Per frame: ship position (y, z) and pitch phi (radians): straight,
    a loop of LOOP_R, straight."""
    y, z, phi = 0.0, 0.0, 0.0
    loop = int(round(2 * math.pi * LOOP_R / V))
    for f in range(straight1 + loop + straight2):
        if straight1 <= f < straight1 + loop:
            t = (f - straight1 + 1) / loop
            phi = 2 * math.pi * (t - math.sin(2 * math.pi * t) / (2 * math.pi))  # eased
        else:
            phi = 0.0
        y += V * math.sin(phi)
        z += V * math.cos(phi)
        yield f, y, z, phi, straight1 <= f < straight1 + loop

def view(bars, sy, sz, phi):
    """Bars as the chase camera sees them: (top line, height, distance)."""
    fwd = (math.sin(phi), math.cos(phi))        # (y, z)
    up = (math.cos(phi), -math.sin(phi))
    cy, cz = sy - ZS * fwd[0], sz - ZS * fwd[1]
    out = []
    for by, bz in bars:
        ry, rz = by - cy, bz - cz
        d = ry * fwd[0] + rz * fwd[1]           # distance along the view
        if not NEAR <= d <= FAR:
            continue                            # clipped all at once
        u = ry * up[0] + rz * up[1]
        h = max(2, int(round(2 * R_BAR * F / d)))
        top = int(round(fb.CY - F * u / d - h / 2))
        if top + h <= WTOP or top > WBOT:
            continue
        out.append((top, h, d))
    return out

def frame(vis, p):
    """The window (H x W C64 colour indices) on frame parity p."""
    tgt = np.zeros((fb.H, 3))
    who = np.full(fb.H, -1)
    depth = np.full(fb.H, np.inf)
    byte = np.zeros(fb.H, int)
    for i, (top, h, d) in enumerate(vis):
        b = brightness(d)
        cov, pat = pattern(b)
        for j in range(h):
            r = top + j
            if WTOP <= r <= WBOT and d < depth[r]:
                depth[r], who[r], byte[r] = d, i, pat
                g = gv.glow((1 - abs(2 * (j + 0.5) / h - 1)) ** 0.9) * min(1.0, b / cov)
                tgt[r] = fv.fl_lin(g)
    cols, _ = il.choose_column(tgt, who, [False] * len(vis), "full", allowed=gv.BLUES)
    img = np.repeat(cols[:, p][:, None], fb.W, axis=1)
    x = np.arange(fb.W)
    for r in range(fb.H):
        if byte[r]:
            # idle-byte bits set show black; bit 7 is the leftmost pixel
            black = (byte[r] >> (7 - (x % 8))) & 1
            img[r, black == 1] = 0
    return img

def main(path_out):
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    bars = world()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    v = iv.Video(path_out, W + 32, H + 60)
    prev_phi = 0.0
    for f, sy, sz, phi, looping in path():
        vis = view(bars, sy, sz, phi)
        idx = frame(vis, f & 1)
        rgb = fb.C64RGB[idx].astype(np.uint8)
        # the ship: nose up while the loop turns it
        dphi = (phi - prev_phi) % (2 * math.pi)
        prev_phi = phi
        vy = int(min(64, dphi / (2 * math.pi / 200) * 40)) if looping else 0
        pair = iv.ship_pair(pairs, 0, vy, f)
        for r, line in enumerate(pair):
            for c, val in enumerate(line):
                if val:
                    y, x = fb.CY - 10 + r, fb.W // 2 - 12 + 2 * c
                    rgb[y, x:x + 2] = jv_ship(val)
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        deg = math.degrees(phi) % 360
        n = {k: 0 for k in (0x00, 0x55, 0x77, 0x7f)}
        for top, h, d in vis:
            n[pattern(brightness(d))[1]] += 1
        dr.text((16, 8), f"{'loop' if looping else 'straight'}   pitch {deg:5.1f} deg   bars in view "
                f"{len(vis)}: full {n[0]}, 1/2 {n[0x55]}, 1/4 {n[0x77]}, 1/8 {n[0x7f]}",
                fill=(170, 176, 210), font=small)
        canvas.paste(Image.fromarray(iv.tv(rgb)).resize((W, H), Image.BILINEAR), (16, 40))
        v.add(canvas)
        if f % 150 == 0:
            print(f"frame {f}", flush=True)
    v.close()
    print("wrote", path_out)

def jv_ship(val):
    return fb.C64RGB[(0, 4, 14, 1)[val]]

if __name__ == "__main__":
    main(sys.argv[1])
