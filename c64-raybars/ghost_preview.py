#!/usr/bin/env python3
"""Preview with the whole v10 ramp (25 swatches, the ghost-byte ones too).

 Part 1  the anim0 film (no splits): every line is one swatch, so the idle
         (ghost) byte of any swatch is free to use.
 Part 2  the wave on the finished floor, with the 6 split segments: a line
         has ONE idle byte ($3fff / $bfff), which darkens every segment of the
         line.  A split line can therefore keep ghost swatches only if all its
         segments agree on the byte (black segments don't care); wherever the
         animation moves a split across a ghost-byte row (segments then show
         different rows of the string) the ghost swatches on that line are
         replaced by the nearest flat swatch (no idle byte) by L*.
 The idle byte only shows in the display window, so lines are 320 px: the 6
 segments are 32 | 64 x 4 | 32 px (GOLDSHIP's $d021 splits).

    python3 ghost_preview.py out.mp4 [frames_of_film]
"""
import sys, math
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import preview_v10 as v10
import anim_params as ap
import anim_scene as sc
import gen_cosmic as gc
import anim1_floor as fv

P, WV = ap.P, ap.WAVE
sc.configure(P)
F, R, H, W = fv.F, fv.R, fv.H, fv.W
TMAX = P["TMAX"]
LAD = v10.LAD                                     # 25 swatches, darkest first
Lstar = fv.Lstar
RAMP_L = Lstar(np.array([v10.EYE[k] for k in LAD]))
FLAT = [i for i, k in enumerate(LAD) if all(v10.ghost(k, r, p) == 0 for r in (0, 1) for p in (0, 1))]
import os
# Split layout in the 320 px window.  6 segments: 32 | 64 x 4 | 32 (an 8-cycle write each:
# GOLDSHIP's layout).  7 segments (SPLITS=7): 40 | 48 x 5 | 40 -- a write every 6 cycles
# (lda #imm / sta), which the sprite-free 63-cycle line has room for.
if os.environ.get("SPLITS", "6") == "7":
    EDGES = [0, 40, 88, 136, 184, 232, 280, 320]
else:
    EDGES = [0, 32, 96, 160, 224, 288, 320]
SEGS = len(EDGES) - 1

def profile_idx(T):
    d = 2 * F * R / T
    out = []
    for i in range(T):
        r = (i + (np.arange(8) + 0.5) / 8) * 2 / T - 1
        lit = sum(gc.row_v3(d, v) for v in r) / 8
        out.append(int(np.argmin(np.abs(Lstar(np.array(lit)) - RAMP_L))))
    return out
def spread_profile(T, hi):
    """Every row of a thick bar a different swatch: T levels spread over 1..hi, dealt alternately to the
    rising (top) and falling (bottom) side, so the two sides never repeat a colour and the highlight
    sits just below the middle."""
    lev = [int(v) for v in np.round(np.linspace(1, hi, T))]
    up, down = lev[0:T - 1:2], lev[1:T - 1:2]
    return up + [lev[-1]] + down[::-1]
SPREAD_MIN = 20                                   # bars at least this thick get the spread profile
PROF = {T: (spread_profile(T, 23) if T >= SPREAD_MIN else profile_idx(T)) for T in range(1, TMAX + 1)}

def frame_list(t):
    out = []
    for z, yc, key in sorted(sc.bars(t), key=lambda b: -b[2]):
        z = max(z, 0.6)
        T = max(1, min(TMAX, int(round(2 * F * R / z))))
        y0 = int(round(yc - T / 2))
        if y0 >= H or y0 + T <= 0 or not any(PROF[T][max(0, -y0):H - y0]):
            continue
        out.append((y0, T))
    return out

# ---- rendering one line: segment swatches + the line's idle byte -------------
def draw(seg_idx, y, f):
    """(320 colours, idle byte) of line y: seg_idx = 6 ramp indices; the idle byte
    comes from the swatches (all agree, black ignored) -- caller guarantees it."""
    row = np.zeros(W, int)
    g = 0
    for s in range(SEGS):
        k = LAD[seg_idx[s]]
        row[EDGES[s]:EDGES[s + 1]] = v10.colour(k, y & 1, f & 1)
        gb = v10.ghost(k, y & 1, f & 1)
        if seg_idx[s]:
            g = gb or g
    if g:
        x = np.arange(W)
        row[((g >> (7 - x % 8)) & 1) == 1] = 0
    return row

def fix_line(seg_idx, y, f):
    """Ghost swatches only if every non-black segment has the same idle byte and
    none is flat next to a ghost one; otherwise the ghost ones become flat."""
    bytes_ = [v10.ghost(LAD[i], y & 1, f & 1) for i in seg_idx if i]
    if len(set(bytes_)) <= 1 and (not bytes_ or bytes_[0] != 0 or True):
        if len(set(bytes_)) <= 1:
            return seg_idx, False
    out = []
    for i in seg_idx:
        if i and v10.ghost(LAD[i], y & 1, f & 1):
            i = min(FLAT, key=lambda j: abs(RAMP_L[j] - RAMP_L[i]))
        out.append(i)
    return out, True

# ---- part 1: the film ---------------------------------------------------------
def film_lines(lst):
    col = np.zeros(H, int)
    for y0, T in lst:
        for i, k in enumerate(PROF[T]):
            if k and 0 <= y0 + i < H:
                col[y0 + i] = k
    return col

# ---- part 2: the wave -----------------------------------------------------------
STR = [(y0, T) for y0, T in reversed(frame_list(sc.T_END - 1))]          # nearest first
if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "floor20.json")):
    import json                                    # the 20-bar floor that part 1 ends on
    STR = [tuple(b) for b in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "floor20.json")))]
NS = len(STR)
TILT, STAG = WV["TILT_T"], WV["STAG"]
USTART = [i * STAG if WV["NEAR_FIRST"] else (NS - 1 - i) * STAG for i in range(NS)]
W_LEN = (NS - 1) * STAG + TILT + WV["HOLD"]

def shift(i, tw, k):
    u = tw - USTART[i]
    if not 0 < u < TILT:
        return 0
    a = WV["RISE"] * (STR[i][1] / STR[0][1]) ** WV["RISE_EXP"]
    return -int(round(a * math.sin(math.pi * u / TILT) * (k + 0.5) / SEGS))

def wave_segments(tw):
    out = np.zeros((SEGS, H), int)
    for k in range(SEGS):
        for i in range(NS - 1, -1, -1):
            y0, T = STR[i]
            s = shift(i, tw, k)
            for r, idx in enumerate(PROF[T]):
                if idx and 0 <= y0 + s + r < H:
                    out[k, y0 + s + r] = idx
    return out

def main(path, film_frames=None):
    Z = 3
    n_film = sc.T_END if film_frames is None else film_frames
    v = iv.Video(path, W * Z, H * Z)
    for f in range(n_film):
        col = film_lines(frame_list(f))
        img = np.array([draw([c] * SEGS, y, f) for y, c in enumerate(col)])
        v.add(lv.crt_look(fb.C64RGB[img].astype(np.uint8), Z))
    fixed = total = 0
    for tw in range(W_LEN):
        f = n_film + tw
        seg = wave_segments(tw)
        img = []
        for y in range(H):
            line, changed = fix_line([int(seg[k, y]) for k in range(SEGS)], y, f)
            fixed += changed
            total += any(seg[:, y]) and any(v10.ghost(LAD[i], y & 1, f & 1) for i in seg[:, y] if i)
            img.append(draw(line, y, f))
        v.add(lv.crt_look(fb.C64RGB[np.array(img)].astype(np.uint8), Z))
    v.close()
    print(f"wrote {path}: film {n_film} frames + wave {W_LEN} frames; "
          f"{NS} strings; ghost swatches replaced on {fixed} of {total} ghost lines in the wave")

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
