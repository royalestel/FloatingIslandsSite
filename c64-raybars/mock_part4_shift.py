#!/usr/bin/env python3
"""MOCK (python only): part 4 (mock_part4_wave: the delayed copies) with every SPLIT moving up and down as a whole, each at its own rate.
  amplitude AMP lines (16: up to 16 up and 16 down), a sine per split (own period and phase), whole lines (on the C64: the low byte of the column's page operand);
  eased IN from the moment the split's bars are all moving, eased OUT so that it is back at rest when the matchups are done; each split keeps its own delay.
  Rows below 184 are cut (the C64 loop ends there).     python3 mock_part4_shift.py out.mp4 [last_frame]"""
import os, sys, math, pickle
os.environ["SPLITS"] = "6"
import numpy as np
import mock_part4_wave as mw
ms = mw.ms; g4 = ms.g4
AMP = 16
PERIOD = [110, 86, 134, 98, 72, 124]                       # frames a split takes for one up-and-down (a different rate each)
PHASE = [0.0, 1.9, 3.6, 0.8, 2.7, 4.9]
IN0, IN_LEN = ms.T_MOVING, 60                              # every bar of the split is moving from T_MOVING (+ its delay); ease in over 60 frames
OUT_END, OUT_LEN = int(ms.T_LAST), 90                      # eased out to rest over the 90 frames before the last matchup (+ delay)
LAST_ROW = 184
ss = lambda u: (lambda x: x * x * (3 - 2 * x))(min(1.0, max(0.0, u)))

def envelope(k, t):
    d = mw.D[k]
    return ss((t - (IN0 + d)) / IN_LEN) * (1.0 - ss((t - (OUT_END + d - OUT_LEN)) / OUT_LEN))

def shift(k, t):
    return int(round(AMP * envelope(k, t) * math.sin(2 * math.pi * t / PERIOD[k] + PHASE[k])))

def frame_tokens(TOK, t):
    out = np.zeros((6, 200), int)
    for k in range(6):
        d = shift(k, t)
        src = TOK[t, k]
        if d >= 0: out[k, d:] = src[:200 - d] if d else src
        else: out[k, :200 + d] = src[-d:]
    if t < ms.T_SWEEP0: out[:, LAST_ROW + 1:] = 0
    return out

def load_tokens():
    p = "/tmp/p4d_tokens.pkl"
    if os.path.exists(p):
        TOK = pickle.load(open(p, "rb"))
        if TOK.shape[0] == mw.T_END: return TOK
    TOK = np.array([ms.tokens(t) for t in range(mw.T_END)]); pickle.dump(TOK, open(p, "wb")); return TOK

if __name__ == "__main__":
    out = sys.argv[1]; last = int(sys.argv[2]) if len(sys.argv) > 2 else mw.T_END
    TOK = load_tokens()
    from PIL import Image
    v = ms.iv.Video(out, ms.m.W * 3, ms.H * 3, fps=60)
    for f in range(last):
        seg = frame_tokens(TOK, f); img = []
        for y in range(ms.H):
            line, _ = g4.fix_line([int(seg[k, y]) for k in range(6)], y, f)
            img.append(g4.draw(line, y, f))
        rgb = ms.fb.C64RGB[np.array(img)].astype(np.uint8)
        v.add(Image.fromarray(np.repeat(np.repeat(rgb, 3, axis=0), 3, axis=1)))
    v.close(); print("wrote", out, last, "frames; shifts at frame 450:", [shift(k, 450) for k in range(6)])
