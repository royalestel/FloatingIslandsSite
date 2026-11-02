#!/usr/bin/env python3
"""COSMIC STRINGS drawn with the swatch set: loop_video's flight (the ship's
loop-the-loop through the slab of glowing bars, chase camera, near clip,
gentler growth of distant bars) with every bar line drawn from the 29
swatches of swatches_video.py -- flicker pairs, single colours, and single
colours under a ghost-byte pattern (blue 1/4 on/off, blue 1/4 inverting,
half-brightness inverting checkerboards) -- matched by the colour the eye
sees: the two frames blended 50%.

Distance no longer picks a pattern (loop_video's PAT_BANDS): a bar's glow
ramp fades toward dark blue (loop_video.fade) and its light is scaled down
smoothly (dimming), and the swatch nearest that target is drawn, so the
light falls without a step at a band edge and the far bars stay visible.
Small bars: nearest swatch with error diffusion down the bar.  Bars BIG
lines and taller (the near ones): ordered dither (Bayer over 4 lines)
between the two swatches bracketing the target's brightness, so the many
lines of a close bar walk through the whole set.  Pairs two brightness
levels apart only on big bars, as before.

    python3 swatch_loop_video.py crt.mp4 sharp.mp4
"""
import math, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import glow_video as gv
import ideas_video as iv
import interlace as il
import loop_video as lv
import swatches_video as sw
import ship_aa, big_ship

LW = np.array([0.2126, 0.7152, 0.0722])
# The scene, bigger than loop_video's: thicker bars, spaced further apart,
# drawn from further away, and clipped closer to the camera.  (Cosmic
# strings needs no raster splits, so the row loop has cycles for a ghost
# byte per line.)
lv.R_BAR = 0.2                    # bar radius, metres (loop_video: 0.12)
lv.FAR = 28.0                     # bars drawn from 28 m (loop_video: 12)
lv.NEAR = 0.15                    # near clip (loop_video: 0.4)
SPACING = 1.4                     # metres between bars along the flight (0.28)
HOLD = 20.0                       # beyond this a bar is all blue 1/4 on/off
DIM_FROM, DIM_FAR = 6.0, 0.30     # light scaled 1 -> DIM_FAR from 6 m to HOLD

def world(seed=21):
    rng = np.random.default_rng(seed)
    return [(rng.uniform(-8, 8), z) for z in np.arange(-20.0, 120.0, SPACING)]

def fade(d):
    """loop_video.fade, reaching its far end (dark blue) at HOLD."""
    if d <= lv.REF + 0.25:
        return 1.0
    return 1.0 - (1.0 - lv.FADE_FAR) * min(1.0, (d - lv.REF - 0.25) / (HOLD - lv.REF - 0.25))

def _pattern(name):
    if name == "full":
        return lambda r, p: 0
    for pn, _, f in sw.BLUE_PATTERNS:
        if name.endswith(pn):
            return f
    raise KeyError(name)

def palette():
    """The swatches: (a, b, ghost byte f(line, parity), blended sRGB,
    blended luminance, luma levels apart, name)."""
    out = []
    for t in sw.chosen():
        _, a, b, name, frames = t
        out.append((a, b, _pattern(name), sw.blended(frames), sw.brightness(frames),
                    abs(fl.LUMA[a] - fl.LUMA[b]), name))
    return out

PAL = palette()
HELD = [i for i, p in enumerate(PAL) if p[6] == "blue 1/4 on/off"][0]
COL = np.array([p[3] for p in PAL])
LUM = np.array([p[4] for p in PAL])
WIDE = np.array([p[5] for p in PAL])

def dimming(d):
    if d <= DIM_FROM:
        return 1.0
    return 1.0 - (1.0 - DIM_FAR) * min(1.0, (d - DIM_FROM) / (HOLD - DIM_FROM))

def choose(tgt, who, big, held):
    """Per line: index into PAL (-1 for no bar)."""
    out = np.full(fb.H, -1)
    err = np.zeros(3)
    for y in range(fb.H):
        if held[y]:
            out[y] = HELD
            continue
        if who[y] < 0:
            err[:] = 0
            continue
        if y and who[y - 1] != who[y]:
            err[:] = 0
        ok = WIDE <= (2 if big[y] else 1)
        if big[y]:
            t = np.clip(tgt[y], 0, 1)
            cost = np.where(ok, il.redmean(COL, fl.srgb(t)), np.inf)
            near = np.argsort(cost)[:6]
            lt = float(t @ LW)
            lo = [k for k in near if LUM[k] <= lt and ok[k]]
            hi = [k for k in near if LUM[k] >= lt and ok[k]]
            if not lo or not hi:
                out[y] = near[0]
                continue
            kl = max(lo, key=lambda k: (LUM[k], -cost[k]))
            kh = min(hi, key=lambda k: (LUM[k], cost[k]))
            f = 0 if LUM[kh] - LUM[kl] < 1e-6 else (lt - LUM[kl]) / (LUM[kh] - LUM[kl])
            out[y] = kh if f > lv.BAYER4[y % 4] else kl
            err[:] = 0
            continue
        want = np.clip(tgt[y] + 0.7 * err, 0, 1)
        cost = np.where(ok, il.redmean(COL, fl.srgb(want)), np.inf)
        k = int(np.argmin(cost))
        out[y] = k
        err = np.clip(want - fl.lin(COL[k]), -0.05, 0.05)
    return out

def frame(vis, p):
    tgt = np.zeros((fb.H, 3))
    who = np.full(fb.H, -1)
    depth = np.full(fb.H, np.inf)
    big = np.zeros(fb.H, bool)
    held = np.zeros(fb.H, bool)
    for i, (top, h, d) in enumerate(vis):
        fc, dm = fade(d), dimming(d)
        for j in range(h):
            r = top + j
            if lv.WTOP <= r <= lv.WBOT and d < depth[r]:
                depth[r], who[r], big[r], held[r] = d, i, h >= lv.BIG, d >= HOLD
                g = gv.glow(fc * (1 - abs(2 * (j + 0.5) / h - 1)) ** 0.9)
                tgt[r] = fl.lin(g) * dm
    ks = choose(tgt, who, big, held)
    img = np.zeros((fb.H, fb.W), int)
    x = np.arange(fb.W)
    for r in range(fb.H):
        if ks[r] < 0:
            continue
        a, b, pat = PAL[ks[r]][:3]
        img[r] = a if (r + p) % 2 == 0 else b
        byte = pat(r, p)
        if byte:
            img[r, ((byte >> (7 - x % 8)) & 1) == 1] = 0
    return img

# the ship's colours: none, %01 shadow, %10 lit hull, %11 the exhaust glow --
# the glow register ($D025) written each frame, white and cyan in turn, so
# the engines shimmer
SHIP_COLS = [(0, 4, 14, 1), (0, 4, 14, 3)]

def render(f, sy, sz, phi, looping, state):
    vis = lv.view(state["bars"], sy, sz, phi)
    rgb = fb.C64RGB[frame(vis, f & 1)].astype(np.uint8)
    dphi = (phi - state["prev"]) % (2 * math.pi)
    state["prev"] = phi
    vy = int(min(64, dphi / (2 * math.pi / 200) * 40)) if looping else 0
    pi = ship_aa.pitch_index((vy + 64) >> 3)
    if pi not in state["ships"]:
        state["ships"][pi] = big_ship.pair(0, ship_aa.PITCHES[pi])
    fr = state["ships"][pi][f & 1]
    for r in range(fr.shape[0]):
        for c in range(fr.shape[1]):
            if fr[r, c]:
                y, xx = fb.CY - 10 + r, fb.W // 2 - fr.shape[1] + 2 * c
                rgb[y, xx:xx + 2] = fb.C64RGB[SHIP_COLS[f & 1][fr[r, c]]]
    return rgb, vis

def main(out_crt, out_sharp):
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    vids = [iv.Video(out_crt, W + 32, H + 60), iv.Video(out_sharp, W + 32, H + 60)]
    state = {"bars": world(), "prev": 0.0, "ships": {}}
    for f, sy, sz, phi, looping in lv.path():
        rgb, vis = render(f, sy, sz, phi, looping, state)
        for v, crt in zip(vids, (True, False)):
            canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
            dr = ImageDraw.Draw(canvas)
            dr.text((16, 8), f"{'loop' if looping else 'straight'}   pitch "
                    f"{math.degrees(phi) % 360:5.1f} deg   bars in view {len(vis)}   "
                    f"{len(PAL)} swatches   {'CRT' if crt else 'sharp pixels'}",
                    fill=(170, 176, 210), font=small)
            look = lv.crt_look(rgb, Z) if crt else \
                Image.fromarray(rgb).resize((W, H), Image.NEAREST)
            canvas.paste(look, (16, 40))
            v.add(canvas)
        if f % 150 == 0:
            print(f"frame {f}", flush=True)
    for v in vids:
        v.close()
    print("wrote", out_crt, out_sharp)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
