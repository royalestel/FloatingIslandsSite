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
grey).  Ordered up each column from the bottom left, darkest first.  Patches that look the same (the
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

P, GAP, ROWS = 8, 2, 8             # patch size, gap, patches a column
DARK = (0, 6, 11)                  # black, blue, dark grey: the patterned ones

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
                        byte = pbyte(r, p)
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
        v.add(canvas)
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    items = patches()
    video(sys.argv[1], items, True)
    video(sys.argv[2], items, False)
