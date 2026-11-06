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
              The left bars come down as the red palette; the right bars settle
              into a multicolour gradient made from all 16 C64 colours, ordered
              by lightness (dark to light, one colour per step).

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

def colour(tok, y, f):
    if tok >= P16:
        return ORDER16[tok - P16]
    return gp2.colour(tok, y, f)

def ghost(tok, y, f):
    return 0 if tok >= P16 else gp2.ghost(tok, y, f)

def is_black(tok):
    return tok == 0 or tok == RED

def fix_line(toks, y, f):
    """The ghost rule of ghost_part2 (ghost swatches stay only where a line's segments agree)."""
    gb = {ghost(t, y, f) for t in toks if not is_black(t)}
    if len(gb) <= 1:
        return toks, False
    out = []
    for t in toks:
        if not is_black(t) and ghost(t, y, f):
            if t < RED:
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
            side, mode = ("L", A["modes"][0]) if i % 2 == 0 else ("R", A["modes"][1])
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
                    target = PROF16[T][r]
                    if not target:
                        continue
                    pr = target - P16
                    tok = P16 + pr + int(round((WPOS - pr) * f))
                if 0 <= y0 + s + r < H:
                    out[k, y0 + s + r] = tok
    return out

# ---- the start ------------------------------------------------------------------------
SHAKE = 820

def shake_offsets(t):
    """(whole-floor shift, per-column shifts):
       0-20     a little shake (1 line)
       20-140   pause (2 s)
       140-200  a bigger shake (2 lines, 1 s)
       200-320  pause (2 s)
       320-...  the split columns: 1 line (1 s), 2 lines (1 s), build to 3 (1 s),
                settle to 1 (1 s), 1 line (1 s), a beat (1/3 s), 1 line again (1 s),
                then a 2 s pause, and the waves."""
    if t < 20:
        return round(1.0 * math.sin(2 * math.pi * t / 10)), [0] * SEGS
    if t < 140:
        return 0, [0] * SEGS
    if t < 200:
        return round(2.0 * math.sin(2 * math.pi * (t - 140) / 10)), [0] * SEGS
    if t < 320:
        return 0, [0] * SEGS
    u = t - 320
    if u < 60:
        env = 1.0
    elif u < 120:
        env = 2.0
    elif u < 180:
        env = 2.0 + (u - 120) / 60.0                     # build to 3
    elif u < 240:
        env = 3.0 - 2.0 * (u - 180) / 60.0              # settle from 3 lines to 1
    elif u < 300:
        env = 1.0                                       # 1 line, one second
    elif u < 320:
        env = 0.0                                       # a beat
    elif u < 380:
        env = 1.0                                       # 1 line again
    else:
        env = 0.0                                       # still: the 2 s pause before the waves
    return 0, [round(env * math.sin(2 * math.pi * u / 10 + 0.9 * k)) for k in range(SEGS)]

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
