#!/usr/bin/env python3
"""Every colour the tricks make from cosmic strings' colours (the blue family:
black, blue, purple, light blue, cyan, the greys, white; glow_video.BLUES),
as 8 x 8 pixel patches ordered dark to light, as 60 fps videos (one C64 frame per video frame, so the flicker is
real): with the CRT look, and without it (sharp pixels).

A patch: a pair of C64 colours, shown on alternate frames with the phase
swapped on alternate lines (a single colour when both are the same; pairs
up to two brightness levels apart, as cosmic strings' big bars use), under
one of loop_video's six idle-byte patterns (full, 1/2 checkerboard, 1/4,
1/4 on/off, 1/8, 1/8 on/off, staggered from line to line; the on/off ones
the whole pattern on one frame and black the next) --
the patterns only on pairs of the darkest three colours (black, blue, dark
grey).  Ordered up each column from the bottom left, darkest first, by the two
frames blended 50% (the flicker as the eye sees it).  Patches that look the same (the
same light, averaged over the patch and both frames) are shown once.

    python3 swatches_video.py crt.mp4 sharp.mp4
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import loop_video as lv
import ideas_video as iv
import glow_video as gv

P, GAP, ROWS = 8, 3, 4             # patch size, gap, patches a column
DARK = (0, 6, 11)
DROP = {(3, 15, "full")}           # cyan / light grey: too close to its neighbours                  # black, blue, dark grey: the patterned ones

def patch(a, b, name, light, pbyte):
    """One swatch: the pair a / b (phase swapped by line) under a pattern."""
    frames = []
    for p in (0, 1):
        img = np.zeros((P, P, 3))
        for r in range(P):
            c = fb.C64RGB[a if (r + p) % 2 == 0 else b]
            byte = pbyte(r, p, a != b)
            for x in range(P):
                img[r, x] = 0 if (byte >> (7 - x % 8)) & 1 else c
        frames.append(img)
    lin = np.mean([fl.lin(f) for f in frames], axis=(0, 1, 2))
    return (lin, a, b, name, frames)

def _byte(stride, shift):
    """An idle byte lighting 1 pixel in stride, the first at shift."""
    return sum(1 << (7 - x) for x in range(8) if (x - shift) % stride)

# blue alone under a pattern (no flicker pair, so nothing moves between
# lines): f(line, frame parity).  "on/off": the pattern on even frames,
# black on odd ones; "inverting": the pattern's other half on odd frames.
CHECK = lambda r: _byte(2, r % 2)                    # $55 / $aa by line
QUART = lambda r: _byte(4, 2 * (r % 2))              # $77 / $dd by line
EIGHT = lambda r: _byte(8, 4 * (r % 2))              # $7f / $f7 by line
BLUE_PATTERNS = [
    ("1/4 on/off", 0.125, lambda r, p: QUART(r) if p == 0 else 0xff),
    ("checker on/off", 0.25, lambda r, p: CHECK(r) if p == 0 else 0xff),
    ("1/4 inverting", 0.25, lambda r, p: QUART(r + p)),
    ("checker inverting", 0.5, lambda r, p: CHECK(r + p)),
]

def chosen():
    """The set to show: black; blue alone under each of BLUE_PATTERNS; every
    other colour alone under the inverting checkerboard (half brightness,
    each pixel lit every other frame); then every flicker pair and single
    colour unpatterned -- dark to light."""
    wrap = lambda f: lambda r, p, bp=False: f(r, p)
    items = [patch(6, 6, f"blue {n}", l, wrap(f)) for n, l, f in BLUE_PATTERNS]
    inv = [t for t in BLUE_PATTERNS if t[0] == "checker inverting"][0]
    items += [patch(c, c, f"{fl.NAMES[c]} checker inverting", inv[1], wrap(inv[2]))
              for c in gv.BLUES if c not in (0, 6)]
    items += [t for t in patches() if t[3] == "full"]
    items = dedupe(items)
    items = [t for t in items if (t[1], t[2], t[3]) not in DROP]
    items.sort(key=lambda t: (brightness(t[4]), t[1], t[2], t[3]))
    return items

def blended(frames):
    """The swatch's colour (sRGB) as the eye sees it: frames blended 50%,
    averaged over the patch."""
    return fl.srgb(np.mean(fl.lin((frames[0] + frames[1]) / 2), axis=(0, 1)))

def dedupe(items, tol=1.0):
    """Of swatches whose blended colour and brightness match, keep one:
    plain single colours first, then inverting patterns (steady, no
    boiling), then flicker pairs (which boil up and down a bar), then
    on/off patterns."""
    def order(t):
        if t[3] == "full":
            return 0 if t[1] == t[2] else 2
        return 3 if "on/off" in t[3] else 1
    kept = []
    for t in sorted(items, key=order):
        c = blended(t[4])
        if order(t) and any(np.abs(c - blended(k[4])).max() <= tol for k in kept):
            continue
        kept.append(t)
    return kept

def brightness(frames):
    """Brightness of a swatch as the eye sees its flicker: the two frames
    blended 50%, then the blend's mean luminance (linear light)."""
    blend = (frames[0] + frames[1]) / 2
    return float(np.mean(fl.lin(blend) @ [0.2126, 0.7152, 0.0722]))

def patches():
    out = []
    for i, a in enumerate(gv.BLUES):
        for b in gv.BLUES[i:]:
            if abs(fl.LUMA[a] - fl.LUMA[b]) > 2:
                continue
            # the patterns only on the darkest three colours' pairs
            pats = lv.PATTERNS if a in DARK and b in DARK else lv.PATTERNS[:1]
            for name, light, pbyte in pats:
                frames = []
                for p in (0, 1):
                    img = np.zeros((P, P, 3))
                    for r in range(P):
                        c = fb.C64RGB[a if (r + p) % 2 == 0 else b]
                        byte = pbyte(r, p, a != b)
                        for x in range(P):
                            img[r, x] = 0 if (byte >> (7 - x % 8)) & 1 else c
                    frames.append(img)
                lin = np.mean([fl.lin(f) for f in frames], axis=(0, 1, 2))
                out.append((lin, a, b, name, frames))
    # one of each look; then dark to light
    seen, uniq = [], []
    for item in sorted(out, key=lambda t: (t[0] @ [0.2126, 0.7152, 0.0722], t[1], t[2])):
        key = tuple(np.round(fl.srgb(item[0])).astype(int))
        if key in seen:
            continue
        seen.append(key)
        uniq.append(item)
    return uniq

def sheet(items, p):
    """Dark to light up each column from the bottom left, then the next
    column to the right."""
    cols = -(-len(items) // ROWS)
    W, H = GAP + cols * (P + GAP), GAP + ROWS * (P + GAP)
    img = np.zeros((H, W, 3), np.uint8)
    for i, (lin, a, b, name, frames) in enumerate(items):
        c, k = divmod(i, ROWS)
        r = ROWS - 1 - k
        y, x = GAP + r * (P + GAP), GAP + c * (P + GAP)
        img[y:y + P, x:x + P] = frames[p].astype(np.uint8)
    return img

def video(path, items, crt, seconds=8, Z=6):
    font, small = fl.fonts()
    sheets = [sheet(items, p) for p in (0, 1)]
    h, w, _ = sheets[0].shape
    looks = [lv.crt_look(s, Z) if crt else Image.fromarray(s).resize((w * Z, h * Z), Image.NEAREST)
             for s in sheets]
    v = iv.Video(path, max(w * Z + 32, 300), h * Z + 84)
    for k in range(int(seconds * 60)):
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        for i, t in enumerate([f"Cosmic strings: {len(items)} colours",
                               "dark to light, up from bottom left",
                               "CRT" if crt else "sharp pixels, 60 frames/s"]):
            dr.text((16, 6 + 18 * i), t, fill=(190, 195, 225), font=small)
        canvas.paste(looks[k & 1], (16, 64))
        for i in range(len(items)):
            c, kk = divmod(i, ROWS)
            r = ROWS - 1 - kk
            dr.text((16 + (GAP + c * (P + GAP)) * Z, 64 + (GAP + r * (P + GAP)) * Z - 15),
                    str(i + 1), fill=(150, 155, 185), font=small)
        v.add(canvas)
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    items = chosen()
    video(sys.argv[1], items, True)
    video(sys.argv[2], items, False)
