#!/usr/bin/env python3
"""COSMIC STRINGS: the ship flies a loop-the-loop through a slab of glowing
bars, then straightens out: a look study (60 fps video, one C64 frame per video frame,
through interlace.py's PAL CRT model).

The bars are fixed in space (horizontal, across the view, at random
heights through a slab), and a chase camera ZS metres behind the ship turns
with it, so the bars stay horizontal on screen as the loop sweeps the view
through them.  Bars are glow_video's white-to-blue raster bars, full
brightness up close until the near clip (0.4 m from the camera) takes them
all at once (no shadow past the ship), dimming with distance beyond the
ship.  The video shows each frame as a CRT would: the PAL signal model,
then scanlines, beam spot and glow (crt_look).

Distance shown by the idle byte, which can change every line, by distance
band (pattern_at, PAT_BANDS): full up to 7 m, then --
    $00  every pixel        (near)
    $55|$aa  1 pixel of 2, a checkerboard (the byte alternating by line)
    $77|$dd  1 pixel of 4, staggered
    $77|$dd / $ff  the same on even frames, black on odd ones
    $7f|$f7  1 pixel of 8, shifted by 4 every other line (a dither)
    $7f|$f7 / $ff  the same on even frames, black on odd ones (the dimmest)
The chase camera is 2 m behind the ship, so the ship is drawn 1.5 times
larger, across two sprites side by side (big_ship.py).
on top of the colours fading with distance (fade): the white core gives
way to light blue, then the whole bar to dark blue far away.  The
colours themselves are flicker pairs from the blue family (greys included)
with the phase swapped on alternate lines: one level apart and error
diffused on small bars; on bars BIG lines and taller also two levels apart
(bridging cyan and purple with greys) and ordered-dithered line by line.
Distant bars grow more gently than true perspective (bar_lines).

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
import big_ship
import flicker as fl

F, R_BAR = fb.F, fb.R          # focal length (lines), bar radius (metres)
ZS, NEAR, FAR = 2.0, 0.4, fb.Z0   # the chase camera 2 m behind the ship; bars
                                  # clip 0.4 m from the camera
REF = fb.ZS                       # 3 m: where the fade and the gentler growth start
V = (fb.Z0 - fb.Z1) / (fb.FLYD - 1)     # forward speed, metres a frame (the game's)
LOOP_R = 1.8                   # loop radius, metres
# The idle-byte patterns: (name, light, byte(line, frame parity)).  Bits set
# show black.  The byte alternates from line to line so the lit pixels
# stagger (a checkerboard for 1 of 2) instead of lining up in vertical
# stripes.  The on/off ones show the whole pattern on even frames and black
# ($ff) on odd ones: nothing moves vertically between frames.
def _onoff(pat):
    return lambda r, p: pat(r) if p % 2 == 0 else 0xff

def _stagger(stride, seq):
    """An idle byte lighting 1 pixel in stride, offset by seq[line % 4]:
    the offsets cycle over 4 lines so that neither every line nor every
    other line (a flicker pair's colour) lines its pixels up."""
    def byte(r):
        sh = seq[r % 4]
        return sum(1 << (7 - x) for x in range(8) if (x - sh) % stride)
    return byte
_HALF = _stagger(2, (0, 1, 1, 0))       # 1 x 2 checkerboard cells
_QUARTER = _stagger(4, (0, 2, 1, 3))
_EIGHTH = _stagger(8, (0, 4, 0, 4))       # 10000000, 00001000 (lit) by line
PATTERNS = [("full", 1.0, lambda r, p: 0x00),
            ("1/2", 0.5, lambda r, p: _HALF(r)),
            ("1/4", 0.25, lambda r, p: _QUARTER(r)),
            ("1/4 on/off", 0.125, _onoff(_QUARTER)),
            ("1/8", 0.125, lambda r, p: _EIGHTH(r)),
            ("1/8 on/off", 0.0625, _onoff(_EIGHTH))]
WTOP, WBOT = 11, 199           # the bars' window lines (mockup.py)

def brightness(z):
    """1 up to just beyond the ship, then dimming with distance (no shadow)."""
    if z <= REF + 0.25:
        return 1.0
    return max(0.0, 1.0 - 0.75 * (z - REF - 0.25) / (FAR - REF - 0.25)) ** gv.DIMPOW

def fade(d):
    """Distance fades a bar's colours along its own glow ramp: 1 (the full
    white-to-blue ramp) up to just beyond the ship, down to FADE_FAR at the
    far end, where even the core is dark blue (glow(0.15))."""
    if d <= REF + 0.25:
        return 1.0
    return 1.0 - (1.0 - FADE_FAR) * min(1.0, (d - REF - 0.25) / (FAR - REF - 0.25))

FADE_FAR = 0.15
# the idle-byte pattern by distance: full, 1 of 2, 1 of 4, and 1 of 4 on
# alternate frames (alternate lines) for the dimmest
PAT_BANDS = [(7.0, 0), (8.5, 1), (9.5, 2), (10.5, 3), (11.25, 4), (99.0, 5)]

def pattern_at(d):
    for edge, k in PAT_BANDS:
        if d < edge:
            return PATTERNS[k]

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

GROW = 0.5          # beyond the ship's distance a bar's height goes as d ** -GROW

def bar_lines(d):
    """A bar's height in lines: true perspective (48 / d) up to the ship's
    distance, then a gentler curve, so distant bars cover more lines and
    grow more slowly as they come in (8 lines at 12 m instead of 4)."""
    h = 2 * R_BAR * F / d if d <= REF else 2 * R_BAR * F / REF * (REF / d) ** GROW
    return max(2, int(round(h)))

# ---- the colours: flicker pairs, with wider pairs and stronger line dither for
# big bars.  C64 brightness levels (Pepto): cyan is 6, light blue and grey 4,
# purple 3 -- nothing at 5, so pairs one level apart can't bridge cyan and
# purple.  Rows of bars BIG lines or taller also take pairs two levels apart
# (cyan + grey, cyan + light blue, grey + purple ...) and carry more error to
# the next line (poor man's dithering); small bars keep the gentle pairs.
BIG = 24
LUMA = np.array(fl.LUMA)
def _cands(maxd):
    out = []
    for i, a in enumerate(gv.BLUES):
        for b in gv.BLUES[i:]:
            dl = abs(LUMA[a] - LUMA[b])
            if dl <= maxd:
                out.append((a, b, (1.0, 1.15, 1.5)[dl]))
    a, b, c = map(np.array, zip(*out))
    lin = (fl.lin(fb.C64RGB[a]) + fl.lin(fb.C64RGB[b])) / 2
    return a, b, c, lin
CANDS = {1: _cands(1), 2: _cands(2)}

def choose(tgt, who, big):
    """Per line: (colour on even frames, on odd frames), the pair's phase
    swapped on odd lines; error diffusion down each bar (stronger on big
    bars), brightness jumps of more than a level between lines penalised."""
    out = np.zeros((fb.H, 2), int)
    err = np.zeros(3)
    prev = None
    for y in range(fb.H):
        if who[y] < 0:
            err[:] = 0
            prev = None
            continue
        if prev is not None and who[y - 1] != who[y]:
            err[:] = 0
        a, b, c, lin = CANDS[2 if big[y] else 1]
        if big[y]:
            k = ordered(tgt[y], y, a, b, c, lin)
            pair = (a[k], b[k]) if y % 2 == 0 else (b[k], a[k])
            out[y] = pair
            prev = (a[k], b[k])
            err[:] = 0
            continue
        kd, emax = 0.7, 0.05
        want = np.clip(tgt[y] + kd * err, 0, 1)
        sw = fl.srgb(want)
        cost = il.redmean(fl.srgb(lin), sw) * c ** 2
        if prev is not None:
            jump = np.maximum(np.abs(LUMA[a] - LUMA[prev[0]]), np.abs(LUMA[b] - LUMA[prev[1]]))
            cost = cost * (1 + 0.4 * np.maximum(jump - (2 if big[y] else 1), 0)) ** 2
        k = int(np.argmin(cost))
        pair = (a[k], b[k]) if y % 2 == 0 else (b[k], a[k])
        out[y] = pair
        prev = (a[k], b[k])
        err = np.clip(want - lin[k], -emax, emax)
    return out

BAYER4 = [0.125, 0.625, 0.375, 0.875]          # line thresholds, repeating

def ordered(t, y, a, b, c, lin):
    """Ordered dither for big bars: among the candidates nearest the target
    in colour, the two that bracket its brightness; the brighter on lines
    whose threshold the target's position between them passes."""
    sw = fl.srgb(np.clip(t, 0, 1))
    cost = il.redmean(fl.srgb(lin), sw) * c ** 2
    near = np.argsort(cost)[:6]
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    lt = float(np.clip(t, 0, 1) @ np.array([0.2126, 0.7152, 0.0722]))
    lo = [k for k in near if lum[k] <= lt]
    hi = [k for k in near if lum[k] >= lt]
    if not lo or not hi:
        return int(near[0])
    kl = max(lo, key=lambda k: (lum[k], -cost[k]))
    kh = min(hi, key=lambda k: (lum[k], cost[k]))
    if lum[kh] - lum[kl] < 1e-6:
        return int(kl)
    f = (lt - lum[kl]) / (lum[kh] - lum[kl])
    return int(kh if f > BAYER4[y % 4] else kl)

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
        h = bar_lines(d)
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
    big = np.zeros(fb.H, bool)
    for i, (top, h, d) in enumerate(vis):
        fc = fade(d)
        pname, light, pbyte = pattern_at(d)
        for j in range(h):
            r = top + j
            if WTOP <= r <= WBOT and d < depth[r]:
                depth[r], who[r], big[r] = d, i, h >= BIG
                byte[r] = pbyte(r, p)
                g = gv.glow(fc * (1 - abs(2 * (j + 0.5) / h - 1)) ** 0.9)
                tgt[r] = fv.fl_lin(g)
    cols = choose(tgt, who, big)
    img = np.repeat(cols[:, p][:, None], fb.W, axis=1)
    x = np.arange(fb.W)
    for r in range(fb.H):
        if byte[r]:
            # idle-byte bits set show black; bit 7 is the leftmost pixel
            black = (byte[r] >> (7 - (x % 8))) & 1
            img[r, black == 1] = 0
    return img

def crt_look(rgb, z=3):
    """A frame as a CRT screen shows it, z times the size: the signal through
    interlace.py's PAL model (composite blur, delay line), then the tube: each
    line a beam of z rows, brighter lines blooming wider (visible scanlines
    between dark ones), a soft beam spot along the line, and a glow around
    bright areas.  Light is added in linear space."""
    from PIL import ImageFilter
    sig = iv.tv(rgb).astype(float) / 255
    lin = sig ** 2.2
    h, w, _ = lin.shape
    wide = np.repeat(lin, z, axis=1)                         # along the line
    lum = (0.3 * lin[..., 0] + 0.59 * lin[..., 1] + 0.11 * lin[..., 2])[..., None]
    out = np.zeros((h * z, w * z, 3))
    off = np.arange(z) - (z - 1) / 2                         # row offsets in a line
    for i, d in enumerate(off):
        sigma = 0.22 + 0.45 * np.repeat(lum, z, axis=1)      # beam width, lines
        wgt = np.exp(-0.5 * (d / z / sigma) ** 2)
        out[i::z] = wide * wgt
    def blur(a, r):
        im = Image.fromarray(np.clip(a ** (1 / 2.2) * 255, 0, 255).astype(np.uint8))
        return (np.asarray(im.filter(ImageFilter.GaussianBlur(r)), float) / 255) ** 2.2
    k = np.exp(-0.5 * (np.arange(-4, 5) / 1.4) ** 2)        # the beam spot, along
    k /= k.sum()                                             # the line only
    spot = sum(w_ * np.roll(out, i - 4, axis=1) for i, w_ in enumerate(k))
    glow = blur(out, 7)                                      # halation / bloom
    res = spot * 1.15 + glow * 0.35
    return Image.fromarray((np.clip(res, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))

def main(path_out):
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    bars = world()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    v = iv.Video(path_out, W + 32, H + 60)
    prev_phi = 0.0
    ships = {}
    for f, sy, sz, phi, looping in path():
        vis = view(bars, sy, sz, phi)
        idx = frame(vis, f & 1)
        rgb = fb.C64RGB[idx].astype(np.uint8)
        # the ship: nose up while the loop turns it
        dphi = (phi - prev_phi) % (2 * math.pi)
        prev_phi = phi
        vy = int(min(64, dphi / (2 * math.pi / 200) * 40)) if looping else 0
        # the ship, 2 m away: two sprites side by side (big_ship.py)
        pi = ship_aa.pitch_index((vy + 64) >> 3)
        if pi not in ships:
            ships[pi] = big_ship.pair(0, ship_aa.PITCHES[pi])
        fr = ships[pi][f & 1]
        for r in range(fr.shape[0]):
            for c in range(fr.shape[1]):
                if fr[r, c]:
                    y, x = fb.CY - 10 + r, fb.W // 2 - fr.shape[1] + 2 * c
                    rgb[y, x:x + 2] = jv_ship(fr[r, c])
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        deg = math.degrees(phi) % 360
        n = {name: 0 for name, _, _ in PATTERNS}
        for top, h, d in vis:
            n[pattern_at(d)[0]] += 1
        dr.text((16, 8), f"{'loop' if looping else 'straight'}   pitch {deg:5.1f} deg   bars in view "
                f"{len(vis)}: " + ", ".join(f"{k} {c}" for k, c in n.items()),
                fill=(170, 176, 210), font=small)
        canvas.paste(crt_look(rgb, Z), (16, 40))
        v.add(canvas)
        if f % 150 == 0:
            print(f"frame {f}", flush=True)
    v.close()
    print("wrote", path_out)

def jv_ship(val):
    return fb.C64RGB[(0, 4, 14, 1)[val]]

if __name__ == "__main__":
    main(sys.argv[1])
