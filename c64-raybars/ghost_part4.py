#!/usr/bin/env python3
"""The floor film, part 2 as of ghost_part3, with these changes:

  start   a little shake, a long pause, a slightly bigger shake, a long pause,
          then the raster-split columns shake from small, build to full, and ease
          back to stillness; the first wave follows.
  waves   a beat of about a third of a second (20 frames) between waves.
          anim1-3 and anim4 (the back-to-front left lift) as in ghost_part3.
  new     W5  the right ends raise front to back, turn white at the peak, and
              fade to blue as they come down.
          W6  from the back, every other bar tilts on its left end and the rest on
              its right, both waves at once.  At each bar's peak it turns white.
              The red bars come down in the red palette; the multicolour bars settle
              into palette25 (7 base colours and in-betweens). The bars alternate
              along the floor: the nearest is multicolour (right tilt), the next red
              (left tilt), and so on.

    python3 ghost_part4.py out.mp4
"""
import sys, math
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import flicker as fl
import ghost_part2 as gp2
import ghost_part3 as gp3
import anim1_floor as fv
import palette25 as p25

STR, NS, W, H, SEGS, EDGES = gp2.STR, gp2.NS, gp2.W, gp2.H, gp2.SEGS, gp2.EDGES
RED, TOP_R, PROF_R, gp, rr = gp2.RED, gp2.TOP_R, gp2.PROF_R, gp2.gp, gp2.rr
LAD = gp2.LAD
TOPB = len(LAD) - 1                                  # the blue ramp's white (flat)
P16 = 300                                            # tokens P16 + position in the 16-colour order

M = np.array([0.2126, 0.7152, 0.0722])
def _L(c):
    y = float(((fb.C64RGB[c] / 255) ** 2.2) @ M)
    return float(116 * y ** (1 / 3) - 16) if y > 0.008856 else y * 903.3
ORDER16 = sorted(range(16), key=_L)                  # colour index by position, dark to light
POS16 = {c: i for i, c in enumerate(ORDER16)}
L16 = np.array([_L(c) for c in ORDER16])
WPOS = POS16[1]                                      # white's position (top)

def prof16(T):
    """Token per row of a bar T lines thick: its nearest C64 colour by lightness
    (0 = black: not drawn)."""
    d = 2 * fv.F * fv.R / T
    out = []
    for i in range(T):
        r = (i + (np.arange(8) + 0.5) / 8) * 2 / T - 1
        lit = sum(gp.gc.row_v3(d, v) for v in r) / 8
        Lr = float(fv.Lstar(np.array(lit)))
        pos = int(np.argmin(np.abs(L16 - Lr)))
        out.append(0 if pos == 0 else P16 + pos)
    return out
PROF16 = {T: prof16(T) for T in range(1, gp.TMAX + 1)}

P25 = 500                                            # tokens P25 + index of palette25's swatch (the multicolour ramp)
ENT25 = p25.build()
N25 = len(ENT25)
L25 = np.array([l for _, _, l in ENT25])
TOP25 = N25 - 1                                      # white
GHOST25 = [any(fn(rp, p, 0)[1] for rp in (0, 1) for p in (0, 1)) for _, fn, _ in ENT25]
FLAT25 = [i for i in range(N25) if not GHOST25[i]]

def prof25(T):
    d = 2 * fv.F * fv.R / T
    out = []
    for i in range(T):
        r = (i + (np.arange(8) + 0.5) / 8) * 2 / T - 1
        lit = sum(gp.gc.row_v3(d, v) for v in r) / 8
        Lr = float(fv.Lstar(np.array(lit)))
        j = int(np.argmin(np.abs(L25 - Lr)))
        out.append(0 if j == 0 else P25 + j)
    return out
PROF25 = gp.ProfDict({T: [P25 + j for j in gp.standard_profile(T, 23)]
                     for T in range(1, gp.TMAX + 1)},
                    lambda T, i: [P25 + j for j in gp.bar_profile(T, i, 23, lambda t: [max(0, x - P25) if x else 0 for x in prof25(t)])])

def colour(tok, y, f):
    if tok >= P25:
        return ENT25[tok - P25][1](y & 1, f & 1, y % 3)[0]
    if tok >= P16:
        return ORDER16[tok - P16]
    return gp2.colour(tok, y, f)

def ghost(tok, y, f):
    if tok >= P25:
        return ENT25[tok - P25][1](y & 1, f & 1, y % 3)[1]
    return 0 if tok >= P16 else gp2.ghost(tok, y, f)

def is_black(tok):
    return tok == 0 or tok == RED or tok == P25

def fix_line(toks, y, f):
    """The ghost rule of ghost_part2 (ghost swatches stay only where a line's segments agree)."""
    gb = {ghost(t, y, f) for t in toks if not is_black(t)}
    if len(gb) <= 1:
        return toks, False
    out = []
    for t in toks:
        if not is_black(t) and ghost(t, y, f):
            if t >= P25:
                t = P25 + min(FLAT25, key=lambda j: abs(L25[j] - L25[t - P25]))
            elif t < RED:
                t = min(gp2.FLAT, key=lambda j: abs(gp.RAMP_L[j] - gp2.light(t)))
            else:
                t = RED + min(rr.FLAT, key=lambda j: abs(rr.RAMP_L[j] - gp2.light(t)))
        out.append(t)
    return out, True

def draw(toks, y, f):
    row = np.zeros(W, int)
    g = 0
    for s in range(SEGS):
        row[EDGES[s]:EDGES[s + 1]] = colour(toks[s], y, f)
        if not is_black(toks[s]):
            g = ghost(toks[s], y, f) or g
    if g:
        x = np.arange(W)
        row[((g >> (7 - x % 8)) & 1) == 1] = 0
    return row

# ---- the new waves -----------------------------------------------------------------
W5 = dict(name="W5 right, blue", TILT=32, STAG=4, amp=28, start="front", side="R", modes=("blue", "blue"),
          base="red")                          # starts from the red floor: red, white at the apex, blue at rest
W6 = dict(name="W6 left/right from the back", TILT=32, STAG=4, amp=28, start="back", side="alt",
          modes=("red", "multi"))              # even bars: left wave (red), odd bars: right wave (multi)

def wave_tokens(A, tw):
    """SEGS x H tokens at frame tw of a W5/W6 wave."""
    out = np.zeros((SEGS, H), int)
    for i in range(NS - 1, -1, -1):                             # far first
        y0, T = STR[i]
        us = i * A["STAG"] if A["start"] == "front" else (NS - 1 - i) * A["STAG"]
        u = tw - us
        a = A["amp"] * math.sin(math.pi * u / A["TILT"]) if 0 < u < A["TILT"] else 0.0
        if A["side"] == "alt":
            side, mode = ("R", A["modes"][1]) if i % 2 == 0 else ("L", A["modes"][0])   # nearest: multicolour
        else:
            side, mode = A["side"], A["modes"][0]
        uu = u / A["TILT"]
        f = 1.0 - (min(uu, 1.0) - 0.5) / 0.5 if uu >= 0.5 else 0.0      # white at the peak, rest at 1
        for k in range(SEGS):
            c = (k + 0.5) / SEGS
            s = -int(round(a * c)) if side == "R" else -int(round(a * (1 - c)))
            for r in range(T):
                base = gp.PROF[T][r]                             # blue, before the peak
                if not base:
                    continue
                if uu < 0.5:
                    if A.get("base") == "red":
                        kr = PROF_R[T][r]
                        if not kr:
                            continue
                        tok = RED + kr
                    else:
                        tok = base
                elif mode == "blue":
                    tok = base + int(round((TOPB - base) * f))
                elif mode == "red":
                    kr = PROF_R[T][r]
                    if not kr:
                        continue
                    tok = RED + kr + int(round((TOP_R - kr) * f))
                else:                                            # multicolour
                    target = PROF25[T][r]
                    if not target:
                        continue
                    pr = target - P25
                    tok = P25 + pr + int(round((TOP25 - pr) * f))
                if 0 <= y0 + s + r < H:
                    out[k, y0 + s + r] = tok
    return out

# ---- the start ------------------------------------------------------------------------
SHAKE = 1064

# An earthquake: each position is a sum of sines at four unrelated frequencies
# (periods about 14, 7, 5 and 3 frames), each column with its own phases, under a slow
# envelope.  Rounded to whole lines it is that frame's offset.
QFREQ = (0.071, 0.137, 0.213, 0.327)
QWT = (1.0, 0.7, 0.45, 0.3)

def quake(t, k, env):
    x = sum(w * math.sin(2 * math.pi * f * t + 1.7 * k * (j + 1) + 0.9 * j + 0.4)
            for j, (f, w) in enumerate(zip(QFREQ, QWT))) / sum(QWT)
    return int(round(1.5 * env * x))

def interp(u, keys):
    """Envelope from (time, level) keys, eased between them."""
    if u <= keys[0][0]:
        return keys[0][1]
    for (t0, a), (t1, b) in zip(keys, keys[1:]):
        if u < t1:
            x = (u - t0) / (t1 - t0)
            x = x * x * (3 - 2 * x)
            return a + (b - a) * x
    return keys[-1][1]

SPLIT_KEYS = [(0, 0.5), (60, 1.0), (120, 2.0), (180, 4.0), (225, 6.0), (265, 4.0), (320, 2.0),
              (380, 1.0), (420, 0.0)]

def shake_offsets(t):
    """(whole-floor shift, per-column shifts):
       0-40      a little quake of the whole floor (1-2 lines)
       40-160    pause (2 s)
       160-260   a bigger quake (up to 3 lines)
       260-380   pause (2 s)
       380-800   the split columns, each shaking on its own, from small, getting bigger
                 to a peak of about 6 lines, and dying away
       800-920   a longer pause (2 s)
       920-944   a short tiny shake (1 line)
       944-1064  pause (2 s), then the waves."""
    if t < 40:
        return quake(t, 0, 1.5 * math.sin(math.pi * t / 40)), [0] * SEGS
    if t < 160:
        return 0, [0] * SEGS
    if t < 260:
        return quake(t, 0, 3.0 * math.sin(math.pi * (t - 160) / 100)), [0] * SEGS
    if t < 380:
        return 0, [0] * SEGS
    if t < 800:
        u = t - 380
        env = interp(u, SPLIT_KEYS)
        return 0, [quake(u, k + 1, env) for k in range(SEGS)]
    if t < 920:
        return 0, [0] * SEGS
    if t < 944:
        return quake(t, 0, 1.2 * math.sin(math.pi * (t - 920) / 24)), [0] * SEGS
    return 0, [0] * SEGS

def shift_rows(a, o):
    out = np.zeros_like(a)
    if o >= 0:
        out[:, o:] = a[:, :H - o] if o else a
    else:
        out[:, :H + o] = a[:, -o:]
    return out

def main(path):
    Z = 3
    v = iv.Video(path, W * Z, H * Z)
    f = 0
    # (name, segments(tw), wave length, pre, post)
    seq = [
        (gp2.ANIMS[0], lambda tw: gp2.segments(gp2.ANIMS[0], tw), (NS - 1) * 3 + 40),
        (gp2.ANIMS[1], lambda tw: gp2.segments(gp2.ANIMS[1], tw), (NS - 1) * 2 + 16),
        (gp2.ANIMS[2], lambda tw: gp2.segments(gp2.ANIMS[2], tw), (NS - 1) * 4 + 32),
        (gp3.ANIM4, lambda tw: gp3.segments(gp3.ANIM4, tw), (NS - 1) * 4 + 32 + 3 * (NS - 1) + 32),
        (W5, lambda tw: wave_tokens(W5, tw), (NS - 1) * 4 + 32),
        (W6, lambda tw: wave_tokens(W6, tw), (NS - 1) * 4 + 32),
    ]
    for n_i, (A, segs, wave) in enumerate(seq):
        pre = SHAKE if n_i == 0 else 10
        post = 10 if n_i < len(seq) - 1 else 60
        n = pre + wave + post
        for t in range(n):
            tw = t - pre
            seg = segs(tw)                                  # tw < 0: this wave's own starting floor
            if n_i == 0 and t < SHAKE:
                dy, dk = shake_offsets(t)
                seg = np.stack([shift_rows(seg[k:k + 1], dy + dk[k])[0] for k in range(SEGS)])
            img = []
            for y in range(H):
                toks = [int(seg[k, y]) for k in range(SEGS)]
                line, _ = fix_line(toks, y, f)
                img.append(draw(line, y, f))
            v.add(lv.crt_look(fb.C64RGB[np.array(img)].astype(np.uint8), Z))
            f += 1
        print(A["name"] if "name" in A else n_i, n, "frames")
    v.close()
    print("wrote", path, f, "frames")

if __name__ == "__main__":
    main(sys.argv[1])
