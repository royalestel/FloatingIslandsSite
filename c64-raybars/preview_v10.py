#!/usr/bin/env python3
"""Preview v10: v9's bar (steady thickness, white centre near in) built from
the hand-ordered swatch ramp (swatch_ramp_video.ladder(): 25 swatches in the
order chosen by eye on the CRT, light blue 1/4 inverting shifted a pixel,
the stripes' rows swapped).  The eye's order is taken as the brightness
order: each step gets the measured light values sorted into that order, so
every step up the ladder is a step brighter.  Each pattern also keeps its
overall light close to the last one's, so the bar brightens in small even
steps as it comes in.  Side by side with v9, CRT.

    python3 preview_v10.py video.mp4
"""
import sys
import numpy as np
import swatch_ramp_video as sr
import preview_v7 as v7
import preview_v8 as v8
import preview_v9 as v9

LAD, _lums = sr.ladder()
EYE = dict(zip(LAD, sorted(_lums[k] for k in LAD)))   # light by the eye's order
LUM = np.array([EYE[k] for k in LAD])
W_WIDTH, W_PREV, W_STEP = 6.0, 10.0, 4.0
_last = {"w": None, "m": None, "d": None}

# the ramp's two tweaks, applied wherever these swatches are drawn
_colour, _ghost = v7.colour, v7.ghost
def colour(k, rp, p):
    return _colour(k, rp ^ (k in sr.SWAP_ROWS), p)
def ghost(k, rp, p):
    g = _ghost(k, rp ^ (k in sr.SWAP_ROWS), p)
    if k in sr.SHIFT:
        g = (g >> 1) | ((g & 1) << 7)
    return g
v7.colour, v7.ghost = colour, ghost

def candidate(tgt, shift, carry):
    h = len(tgt)
    half = (h + 1) // 2
    lower, err, kmax = [], 0.0, len(LAD) - 1
    for i in range(half):
        want = tgt[h - half + i] + err
        idx = np.searchsorted(LUM, want)
        lo, hi = max(0, min(idx - 1, len(LAD) - 1)), min(idx, len(LAD) - 1)
        if hi == lo:
            k = lo
        else:
            f = (want - LUM[lo]) / max(LUM[hi] - LUM[lo], 1e-9)
            k = hi if f > 0.5 + shift else lo
        k = min(k, kmax)
        kmax = k
        lower.append(LAD[k])
        err = carry * (want - LUM[k])
    upper = lower[::-1] if h % 2 == 0 else lower[:0:-1]
    return upper + lower

def ramp_v10(h, d):
    if _last["d"] is not None and d > _last["d"] + 1.0:
        _last["w"] = _last["m"] = None
    tgt = v9.target_profile(h, d)
    w0, m0 = v9.rms_width(tgt), tgt.mean()
    best, bc, bw, bm = None, np.inf, None, None
    for s in v9.SHIFTS:
        for c in v9.CARRY:
            r = candidate(tgt, s, c)
            l = np.array([EYE[k] for k in r])
            w, m = v9.rms_width(l), l.mean()
            cost = abs(m - m0) / max(m0, 1e-6) + W_WIDTH * abs(w - w0)
            if _last["w"] is not None:
                cost += W_PREV * abs(w - _last["w"])
                if m < _last["m"]:                       # never dimmer as it nears
                    cost += W_STEP * (_last["m"] - m) / max(m0, 1e-6) * 4
                cost += W_STEP * abs(m - max(m0, _last["m"])) / max(m0, 1e-6)
            if cost < bc:
                best, bc, bw, bm = r, cost, w, m
    _last["w"], _last["m"], _last["d"] = bw, bm, d
    return best

if __name__ == "__main__":
    v8.main(sys.argv[1], v9.ramp_v9, ramp_v10, ("v9", "v10"), "the hand-ordered ramp")
