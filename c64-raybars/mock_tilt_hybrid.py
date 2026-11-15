#!/usr/bin/env python3
"""Mockup: a real VICE bar (ghost byte) against its tilted six-segment flat version using the per-row hybrid rules:
every row is one colour or a pair swapped each frame, centre rows never dimmer than the bar, the rest by closest match.
python3 mock_tilt_hybrid.py frame.png rows_from rows_to out.png [lambda]"""
import sys
import numpy as np
from PIL import Image, ImageDraw
SRC, Y0, Y1, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
LAM = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
PAL = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in
    "000000 ffffff 813338 75cec8 8e3c97 56ac4d 2e2c9b edf171 8e5029 553800 c46c71 4a4a4a 7b7b7b a9ff9f 706deb b2b2b2".split()], float)
lin = lambda c: (np.asarray(c, float) / 255) ** 2.2
unl = lambda l: np.clip(l, 0, 1) ** (1 / 2.2) * 255
LW = np.array([0.2126, 0.7152, 0.0722]); LP = lin(PAL); LUM = LP @ LW
def load(p):                                   # (the ship's columns are filled from the left: they would pollute the rows)
    im = np.array(Image.open(p).convert("RGB")).astype(float); im[:, 150:230] = im[:, 70:150]; return im
FRAMES = [load(p) for p in SRC.split(",")]       # one frame, or two consecutive VICE frames (the ghost byte pattern flips with frame parity)
img = FRAMES[0]
X0, X1 = 40, 344
H = Y1 - Y0
target = np.array([np.mean([lin(f[y, X0:X1]).mean(axis=0) for f in FRAMES], axis=0) for y in range(Y0, Y1)])   # what the eye integrates
cand = [(a, b) for a in range(16) for b in range(a, 16)]
def pick(t, centre):
    lt = t @ LW; best, bc = None, 1e9
    for a, b in cand:
        v = (LP[a] + LP[b]) / 2
        if centre and v @ LW < 0.95 * lt: continue
        c = ((v - t) ** 2).sum() + LAM * (LUM[a] - LUM[b]) ** 2
        if c < bc: best, bc = (a, b), c
    return best or max(cand, key=lambda ab: (LP[ab[0]] + LP[ab[1]]).sum() )
c0, c1 = H // 2 - 1, H // 2 + 1
rows = [pick(t, c0 <= j <= c1) for j, t in enumerate(target)]
W, SEG, TILT = X1 - X0, 6, 2.6
def tilted(f):
    out = np.zeros((H + 24, W, 3))
    for s in range(SEG):
        xa, xb = s * W // SEG, (s + 1) * W // SEG
        off = int(round((s - (SEG - 1) / 2) * -TILT)) + 12
        for j in range(H):
            a, b = rows[j]
            out[off + j, xa:xb] = PAL[a if (j + f) % 2 == 0 else b]
    return out
def panel(f): r = np.zeros((H + 24, W, 3)); r[12:12 + H] = f[Y0:Y1, X0:X1]; return r
realA = panel(FRAMES[0]); realB = panel(FRAMES[-1]); real = realA
A, B = tilted(0), tilted(1); avg = unl((lin(A) + lin(B)) / 2)
LT = target @ LW                                         # (measured on the rows themselves: the tilt shifts each segment's rows)
LM = np.array([(LUM[a] + LUM[b]) / 2 for a, b in rows])
ce, ed = slice(c0, c1 + 1), np.r_[0:2, H - 2:H]
print("centre lum  real %.3f  mock %.3f | edge  real %.3f  mock %.3f | whole bar real %.3f mock %.3f" % (
    LT[ce].mean(), LM[ce].mean(), LT[ed].mean(), LM[ed].mean(), LT.mean(), LM.mean()))
print("centre pairs:", [(a, b) for a, b in rows[c0:c1 + 1]])
S = 3; ph, pad = (H + 24) * S, 16
panels = [("REAL VICE: straight and level, ghost-byte dither", real), ("MOCK hybrid: tilted, frame A", A),
          ("MOCK hybrid: tilted, frame B (pairs swapped)", B), ("MOCK hybrid: A + B averaged (what the eye integrates)", avg)]
canvas = Image.new("RGB", (W * S, len(panels) * (ph + pad)), (24, 24, 24)); d = ImageDraw.Draw(canvas)
for i, (name, a) in enumerate(panels):
    y = i * (ph + pad); d.text((4, y + 2), name, fill=(255, 255, 160))
    canvas.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((W * S, ph), Image.NEAREST), (0, y + pad))
canvas.save(OUT)
