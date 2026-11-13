#!/usr/bin/env python3
"""MOCK (python only): the end of part 4 into the gold routines.

  part 4 (the C64's own frames, /tmp/part4d_shown.pkl) until the wipe has swept the other bars away (frame 1075);
  MOVE     the nearest (blue) bar does not leave the screen: it eases into goldtilt's own bobbing movement over MOVE frames (position and speed match at the
           hand-over), 26 lines become 24 and it widens to the full screen, and AT THE SAME TIME
  FADE     half a second (30 frames, in the middle of the move): every line of the bar fades from its blue swatch to its gold colour through flicker pairs of C64 colours
           (a pair = two colours alternating by line and by frame, as our swatches do), each step the pair nearest the line's colour on the way,
           with a penalty on the brightness difference of the two colours (less flicker);
  then 3 s each (180 frames at 60 fps, one update a frame): goldtilt (from the frame where its bar is flat), goldlight (from the frame where the light
  is at its leftmost and starts moving right: it sweeps in from the left), goldorbit, goldtwin, goldfly.  Where a routine's bar sits elsewhere than the
  last one left it, the picture glides there over GLIDE frames.  The gold routines' frames come from their simulators (the real 6502 code, PAL timing).
  The picture is the whole visible screen (384 x 240, raster lines 31..270): parts 1-4 only draw the 320 x 200 window, the gold routines the border too.
    python3 mock_gold_seq.py out.mp4"""
import os, sys, re, math, pickle
os.environ["SPLITS"] = "6"
import numpy as np
from PIL import Image
import flyby3d as fb, ideas_video as iv
import mock_part4_wave as mw
import vice_check_2c as v2
import gold_frames as gf
g4 = mw.ms.g4
RGB = np.array(fb.C64RGB, dtype=float)
W, H, R0 = 384, 250, 31                          # canvas: raster lines R0.., window row 0 = raster 51, x 32..351
WX, WY = 32, 51 - R0
P4_FROM, P4_TO = 880, 1076                      # part 4 frames shown (the wipe's sweep up ends at 1075)
MOVE, FADE, PART, GLIDE = 90, 30, 180, 30
LAM = 0.6                                        # weight of the flicker (brightness difference of a pair)

def gold_palette():
    src = open("sim_goldtilt.py").read()
    pal = eval(re.search(r"^PAL\s*=\s*(\[.*?\])", src, re.M | re.S).group(1))
    return {((c >> 16) & 255, (c >> 8) & 255, c & 255): i for i, c in enumerate(pal)}
GPAL = gold_palette()

def to_index(a):
    """RGB image from a gold simulator -> C64 colour indices"""
    out = np.zeros(a.shape[:2], int)
    for rgb, i in GPAL.items():
        out[(a[:, :, 0] == rgb[0]) & (a[:, :, 1] == rgb[1]) & (a[:, :, 2] == rgb[2])] = i
    return out

def gold_canvas(top, a, dy=0):
    idx = to_index(a)
    if idx.shape[1] > W: x0 = (idx.shape[1] - W) // 2; idx = idx[:, x0:x0 + W]
    c = np.zeros((H, W), int)
    for r in range(idx.shape[0]):
        y = top + r - R0 + dy
        if 0 <= y < H: c[y] = idx[r]
    return c

def window_canvas(rows320):
    c = np.zeros((H, W), int); c[WY:WY + 200, WX:WX + 320] = rows320; return c

X = np.arange(320)
def part4_rows(a):
    img = np.zeros((200, 320), int)
    for y in range(185):
        row = np.zeros(320, int)
        for k in range(6): row[v2.EDGES[k]:v2.EDGES[k + 1]] = a[y][k]
        if a[y][6]: row[((a[y][6] >> (7 - X % 8)) & 1) == 1] = 0
        img[y] = row
    return img

def token_row(tk, y, f):
    line, flat = g4.fix_line([tk] * 6, y, f)
    return g4.draw(line, y, f)

luma = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
PAIRS = [(a, b) for a in range(16) for b in range(a, 16)]
PMEAN = np.array([(RGB[a] + RGB[b]) / 2 for a, b in PAIRS]); PFL = np.array([abs(luma(RGB[a]) - luma(RGB[b])) for a, b in PAIRS])

def best_pair(target, prev=None):
    cost = ((PMEAN - target) ** 2).sum(1) + LAM * PFL ** 2
    if prev is not None: cost = cost - 40.0 * (np.arange(len(PAIRS)) == prev)      # a little hysteresis: keep the pair unless another is clearly better
    return int(np.argmin(cost))

def main(out):
    shown = pickle.load(open("/tmp/part4d_shown.pkl", "rb"))
    TOK = pickle.load(open("/tmp/p4d_tokens.pkl", "rb"))
    frames = []
    # 1. part 4 until the wipe has swept the others away
    for t in range(P4_FROM, P4_TO): frames.append(window_canvas(part4_rows(shown[t])))
    # the gold bar: goldtilt at its flat frame
    # goldtilt runs from phases chosen for this hand-over: the bob's orbit counter 204 (frame 0 shows 206: the bar near the top of its bob, about to descend, where the
    # blue bar joins it), tilt phase so that frame 90 (= T0) is flat; goldlight then continues the same bob and tilt from goldtilt's last frame
    # (goldtilt: orbit counter 228 -> frame 90 shows 64, the bottom of the bob, with the tilt flat; goldlight: the bob goes on, 6 s: it ends with the bar rising at
    #  orbit 91 and the light's bob at zero; goldtwin: bob, tilt and drift go on, the light's orbit starts at the top (q = 0), bar B starts far away)
    TILT_INIT, LIGHT_INIT, TWIN_INIT = "orbit=228,tilt=164", "orbit=242,tilt=178,lxa=196,lya=197", "orbit=90,tilt=26,lxa=45,lya=250,q=254,bt=254"
    tilt = gf.frames_of("goldtilt", 270, init=TILT_INIT); traw = gf.raw_of("goldtilt", 270, TILT_INIT)
    T0 = next(i for i, fr in enumerate(traw) if all(len(set(r)) == 1 for r in fr[1]))
    gc = gold_canvas(*tilt[T0])
    grows = [y for y in range(H) if gc[y].any()]
    g_top, g_bot = grows[0], grows[-1]                                    # canvas rows of the gold bar (black lines inside it included)
    gold = [int(gc[y, W // 2]) for y in range(g_top, g_bot + 1)]
    NG = len(gold)
    # 2. the blue bar joins goldtilt's own movement: it follows the bar's bobbing (goldtilt's y over the MOVE frames before its flat frame T0) plus an offset from
    #    where the wipe left it that is eased out (smoothstep: position AND speed match at the hand-over); at the same time it narrows from 26 to 24 lines, widens
    #    from the 320-pixel window to the full screen, and its colours FADE (FADE frames in the middle of the move) from the blue swatches to gold.
    col = TOK[P4_TO - 1, 0]; brow = [y for y in range(200) if col[y]]
    btok = [int(col[y]) for y in range(brow[0], brow[-1] + 1)]; NB = len(btok)
    y_start = brow[0] + WY
    ss = lambda u: u * u * (3 - 2 * u)
    ytraj = [traw[T0 - MOVE + j][0] - traw[T0][0] for j in range(MOVE)]          # goldtilt's block position relative to its position at T0, frame T0 - MOVE + j
    t0 = P4_TO
    start = []
    for i in range(NG):
        y = g_top + i - WY; tk = btok[min(NB - 1, int(i * NB / NG))]
        m = np.zeros(3)
        for f in (0, 1):
            line, flat = g4.fix_line([tk] * 6, y, f)
            gh = g4.ghost(line[0], y, f) if (not flat and not g4.is_black(line[0])) else 0
            m += RGB[g4.colour(line[0], y, f)] * (1 - bin(gh).count("1") / 8.0)
        start.append(m / 2)
    prev = [None] * NG
    J0 = (MOVE - FADE) // 2
    for j in range(MOVE):
        t = t0 + j; u = ss((j + 1) / MOVE)
        n = max(NG, int(round(NB + (NG - NB) * u)))
        top = (g_top + ytraj[j]) + (y_start - (g_top + ytraj[0])) * (1.0 - u)       # gold's y plus the eased-out offset (equal to gold's y at the end)
        y0 = int(round(top)); fade = ss(min(1.0, max(0.0, (j - J0) / float(FADE))))
        half = int(round(32 * u)); xa, xb = WX - half, WX + 320 + half
        c = np.zeros((H, W), int)
        for i in range(n):
            y = y0 + i
            if not 0 <= y < H: continue
            gi = min(NG - 1, int(i * NG / n))
            if fade <= 0.0:
                row = token_row(btok[min(NB - 1, int(i * NB / n))], y - WY, t)
                c[y, WX:WX + 320] = row; c[y, xa:WX] = row[0]; c[y, WX + 320:xb] = row[-1]
            elif fade >= 1.0: c[y, xa:xb] = gold[gi]
            else:
                p = best_pair(start[gi] * (1 - fade) + RGB[gold[gi]] * fade, prev[gi]); prev[gi] = p
                a, b = PAIRS[p]; c[y, xa:xb] = a if ((y + t) & 1) == 0 else b
        frames.append(c)
    # 4. the gold routines, 3 s each; a glide where a routine's bar starts elsewhere than the previous one ended
    def bar_rows(c):
        r = [y for y in range(H) if c[y, :W // 6].any() or c[y, W // 2].any()]
        return (r[0] + r[-1]) / 2.0 if r else None
    seq = []
    seq.append(("goldtilt", tilt, T0))
    light = gf.frames_of("goldlight", 420, init=LIGHT_INIT); lraw = gf.raw_of("goldlight", 420, LIGHT_INIT)
    L0 = 0                                                                   # (frame 0: the light at the left edge, moving right)
    seq.append(("goldlight", light, L0))
    twin = gf.frames_of("goldtwin", 420, init=TWIN_INIT)
    seq.append(("goldtwin", twin, 0))                                        # (goldorbit is not used: goldtwin has its orbiting light and bar A)
    fly = gf.frames_of("goldfly", 600)
    seq.append(("goldfly", fly, 100))
    RAW = {"goldtilt": traw, "goldlight": lraw}
    def centre(name, i):
        """raster line of the middle of the (first) bar, from the speedcode colours the simulator recorded"""
        fr = RAW[name][i]; grid = fr[1]
        rows = [r for r, row in enumerate(grid) if any(row)]
        return fr[0] + (rows[0] + rows[-1]) / 2.0
    prev_end = None; info = []
    for name, fr, s0 in seq:
        d0 = 0
        if prev_end is not None and name == "goldlight":
            print("goldtilt -> goldlight: bar centre %.1f -> %.1f raster lines (no glide: goldlight continues goldtilt's bob)" % (prev_end, centre(name, s0)))

        info.append((name, s0, d0))
        n = {"goldtilt": 180, "goldlight": 360, "goldtwin": 360}.get(name, PART)          # goldtilt 3 s, goldlight 6 s, goldtwin 6 s, goldfly 3 s
        for j in range(n):
            frames.append(gold_canvas(*fr[s0 + j]))
        prev_end = centre(name, s0 + n - 1) if name in RAW else None
    print("segments: part 4 %d-%d, move+fade %d (fade %d); " % (P4_FROM, P4_TO - 1, MOVE, FADE) + ", ".join(f"{n} from frame {s} (glide {d} lines)" for n, s, d in info))
    v = iv.Video(out, W * 3, H * 3, fps=60)
    for c in frames:
        rgb = RGB[c].astype(np.uint8)
        v.add(Image.fromarray(np.repeat(np.repeat(rgb, 3, axis=0), 3, axis=1)))
    v.close(); print("wrote", out, len(frames), "frames = %.1f s" % (len(frames) / 60.0))

if __name__ == "__main__":
    main(sys.argv[1])
