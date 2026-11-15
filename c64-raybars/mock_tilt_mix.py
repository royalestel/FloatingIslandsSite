#!/usr/bin/env python3
"""Mockup: a straight-and-level ghost-byte bar (a real VICE frame) against a tilted six-segment bar drawn with flat palette colours:
no ghost byte, two colours alternating by row, swapping every frame.   python3 mock_tilt_mix.py [vice_frame.png] [out.png]"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import os
SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/sa_19.png"
OUT = sys.argv[2] if len(sys.argv) > 2 else "mock_tilt_mix.png"
PICK = os.environ.get("PICK", "bright")          # bright: the brightest bar; dim: the dimmest bar (ghost-byte checker)
PAL = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in
    "000000 ffffff 813338 75cec8 8e3c97 56ac4d 2e2c9b edf171 8e5029 553800 c46c71 4a4a4a 7b7b7b a9ff9f 706deb b2b2b2".split()], float)
lin = lambda c: (np.asarray(c, float) / 255) ** 2.2
unl = lambda l: np.clip(l, 0, 1) ** (1 / 2.2) * 255
LP = lin(PAL)
img = np.array(Image.open(SRC).convert("RGB")).astype(float)
X0, X1 = 40, 344
# the brightest bar: the longest run of rows with light in them
keep = np.r_[40:150, 230:344]                          # (not the ship's columns)
row_l = lin(img[:, keep]).mean(axis=1) @ [0.2126, 0.7152, 0.0722]
on = row_l > (0.02 if PICK == "bright" else 0.004)
runs, run = [], None
for y in range(131):                       # (above the band)
    if on[y] and run is None: run = y
    if (not on[y] or y == 130) and run is not None:
        if y - run >= 6: runs.append((run, y, row_l[run:y].mean(), row_l[run:y].max()))
        run = None
if PICK == "bright":
    best = max((r for r in runs if r[3] > 0.2), key=lambda r: r[1] - r[0])[:2]
else:
    best = min(runs, key=lambda r: r[2])[:2]
print("runs", [(r[0], r[1], round(r[2], 3)) for r in runs])
y0, y1 = best
H = y1 - y0
print("bar rows", y0, y1, "H", H)
target = np.array([lin(img[y, X0:X1]).mean(axis=0) for y in range(y0, y1)])    # per row, linear light
# single flat colour per row; and a pair (A,B) whose mean is closest
single = [int(np.argmin(((LP - t) ** 2).sum(axis=1))) for t in target]
pair = []
BLACK = os.environ.get("BLACK", "0") == "1"      # dim rows: the pair is black + one colour (the ghost byte's own background is black there)
for t in target:
    c = ((LP[:, None, :] + LP[None, :, :]) / 2 - t) ** 2
    c = c.sum(axis=2)
    if BLACK: c[1:, :] = 1e9; c[0, 0] = c[0, 0]
    a, b = np.unravel_index(np.argmin(c), (16, 16))
    pair.append((int(a), int(b)))
W, SEG, TILT = X1 - X0, 6, 2.6
def tilted(colour_of, f):
    out = np.zeros((H + 24, W, 3))
    for s in range(SEG):
        xa, xb = s * W // SEG, (s + 1) * W // SEG
        off = int(round((s - (SEG - 1) / 2) * -TILT)) + 12
        for j in range(H):
            out[off + j, xa:xb] = PAL[colour_of(j, f)]
    return out
flat = lambda j, f: single[j]
mix = lambda j, f: pair[j][(j + f) & 1]
real = np.zeros((H + 24, W, 3)); real[12:12 + H] = img[y0:y1, X0:X1]
A, B = tilted(mix, 0), tilted(mix, 1)
avg = unl((lin(A) + lin(B)) / 2)
F = tilted(flat, 0)
def lum(a, rows):                          # mean linear luminance of the bar's rows
    return float(lin(a[rows]).mean(axis=(0, 1)) @ [0.2126, 0.7152, 0.0722])
rr = slice(12 + 4, 12 + H - 4)
print("level bar (real, VICE) lum %.3f  flat single %.3f  mix A+B %.3f" % (lum(real, rr), lum(F, rr), lum(avg, rr)))
S = 3
panels = [("REAL VICE: straight and level, ghost-byte dither", real),
          ("MOCK: tilted, one flat colour per row (no alternation)", F),
          ("MOCK: tilted, alternating rows, frame A", A),
          ("MOCK: tilted, alternating rows, frame B (swapped)", B),
          ("MOCK: A + B averaged (what the eye integrates)", avg)]
ph, pad = (H + 24) * S, 16
canvas = Image.new("RGB", (W * S, len(panels) * (ph + pad)), (24, 24, 24))
d = ImageDraw.Draw(canvas)
for i, (name, a) in enumerate(panels):
    y = i * (ph + pad)
    d.text((4, y + 2), name, fill=(255, 255, 160))
    canvas.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((W * S, ph), Image.NEAREST), (0, y + pad))
canvas.save(OUT)
