#!/usr/bin/env python3
"""Part 2 with a shaken start and a new ending (ghost_part2 + these changes).

  start   the floor shakes (150 frames, before the first wave):
            1  the whole floor, a line up and down;
            2  then more (3 lines);
            3  then each raster-split column on its own: all the bars of a column
               move together, a few lines up and down, the columns out of step.
  waves   anim1, anim2, anim3 as in ghost_part2.
  end     anim4 is rebuilt: the right-end wave runs front to back in blue with no
          colour change; as it reaches the back row, the LEFT edge of the bars
          lifts, starting at the back and coming forward.  At each bar's peak it
          turns white, then fades to the red ramp as it comes back down.
          Ghost-byte rules as before (ghost_part2: split lines keep ghost swatches
          only where the segments agree on the idle byte).

    python3 ghost_part3.py out.mp4
"""
import sys, math
import numpy as np
import flyby3d as fb
import ideas_video as iv
import loop_video as lv
import ghost_part2 as gp2

STR, NS, W, H, SEGS, EDGES = gp2.STR, gp2.NS, gp2.W, gp2.H, gp2.SEGS, gp2.EDGES
RED, TOP_R, PROF_R, gp, rr = gp2.RED, gp2.TOP_R, gp2.PROF_R, gp2.gp, gp2.rr

SHAKE = 150
LIFT_STAG, LIFT_LEN = 3, 32
ANIM4 = dict(name="anim4", TILT=32, STAG=4, amp=lambda i, T0, T: 28, near_first=True, lift=True, red=False)

def shake_offsets(t):
    """(whole-floor shift, per-column shifts) at shake frame t."""
    if t < 30:
        return round(1.0 * math.sin(2 * math.pi * t / 10)), [0] * SEGS
    if t < 80:
        return round(3.0 * math.sin(2 * math.pi * t / 16)), [0] * SEGS
    if t < 130:
        u = t - 80
        return 0, [round(2.0 * math.sin(2 * math.pi * u / 12 + 0.9 * k)) for k in range(SEGS)]
    return 0, [0] * SEGS

def shift_rows(a, o):
    out = np.zeros_like(a)
    if o >= 0:
        out[:, o:] = a[:, :H - o] if o else a
    else:
        out[:, :H + o] = a[:, -o:]
    return out

def segments(A, tw):
    """Red-or-blue tokens (SEGS x H) at wave frame tw (tw < 0: the still floor)."""
    if not A.get("lift"):
        return gp2.segments(A, tw)
    T0 = STR[0][1]
    TILT = A["TILT"]
    T_hit = (NS - 1) * A["STAG"] + TILT // 2                      # the back row is reached
    out = np.zeros((SEGS, H), int)
    for i in range(NS - 1, -1, -1):                                # far first
        y0, T = STR[i]
        u = tw - i * A["STAG"]
        a = A["amp"](i, T0, T) * math.sin(math.pi * u / TILT) if 0 < u < TILT else 0.0
        ul = (tw - (T_hit + (NS - 1 - i) * LIFT_STAG)) / LIFT_LEN   # left lift: back first
        b = A["amp"](i, T0, T) * math.sin(math.pi * ul) if 0 < ul < 1 else 0.0
        for k in range(SEGS):
            c = (k + 0.5) / SEGS
            s = -int(round(a * c + b * (1 - c)))                  # right up, left up
            for r in range(T):
                if ul < 0.5:
                    tok = gp.PROF[T][r]                           # blue, no change
                else:
                    kr = PROF_R[T][r]
                    if not kr:
                        continue
                    f_ = max(0.0, 1 - (min(ul, 1.0) - 0.5) / 0.5)  # white at the peak, red at rest
                    tok = RED + kr + int(round((TOP_R - kr) * f_))
                if not tok:
                    continue
                if 0 <= y0 + s + r < H:
                    out[k, y0 + s + r] = tok
    return out

def main(path):
    Z = 3
    v = iv.Video(path, W * Z, H * Z)
    f = 0
    anims = [gp2.ANIMS[0], gp2.ANIMS[1], gp2.ANIMS[2], ANIM4]
    for n_i, A in enumerate(anims):
        pre = SHAKE if n_i == 0 else 60
        wave = (NS - 1) * A["STAG"] + A["TILT"] + (LIFT_STAG * (NS - 1) + LIFT_LEN + 16 if A.get("lift") else 0)
        n = pre + wave + 60
        fixed = total = 0
        for t in range(n):
            tw = t - pre
            seg = segments(A, tw) if tw >= 0 else gp2.segments(A, -1)
            if n_i == 0 and t < SHAKE:
                dy, dk = shake_offsets(t)
                seg = np.stack([shift_rows(seg[k:k + 1], dy + dk[k])[0] for k in range(SEGS)])
            img = []
            for y in range(H):
                toks = [int(seg[k, y]) for k in range(SEGS)]
                line, ch = gp2.fix_line(toks, y, f)
                fixed += ch
                total += any(gp2.ghost(x, y, f) for x in toks if not gp2.is_black(x))
                img.append(gp2.draw(line, y, f))
            v.add(lv.crt_look(fb.C64RGB[np.array(img)].astype(np.uint8), Z))
            f += 1
        print(f"{A['name']}: {n} frames, ghost lines made flat {fixed} of {total}")
    v.close()
    print("wrote", path, f, "frames")

if __name__ == "__main__":
    main(sys.argv[1])
