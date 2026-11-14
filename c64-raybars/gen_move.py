#!/usr/bin/env python3
"""move.inc: the blue bar of part 4's last frame becomes goldtilt's gold bar (mock_gold_seq.py's MOVE + FADE), as a stream goldtilt's update
plays for its first MOVEN frames.  Per frame: Y0 (the raster line of the block's first row), then 30 colours for the segments 0..4 of each row
(a flat bar: they are all the same), then 30 colours for the two borders (segments 0 and 6: black while the bar is as wide as part 4's window, the bar's
colour once it is full width, the two alternating by line and frame in between: a half-bright border).

  python3 gen_move.py [preview.mp4]          needs /tmp/part4d_shown.pkl (python3 part4d_gen.py) and the goldtilt sim frames (gold_frames.py)
"""
import os, sys, pickle
os.environ["SPLITS"] = "6"
import numpy as np
import mock_gold_seq as m
import gold_frames as gf

MOVE, FADE = m.MOVE, m.FADE
ROWS = 30                                   # goldtilt's speedcode rows
TOPPAD = 2                                  # black rows above the bar in the block
R0, WY = m.R0, m.WY
RGB = m.RGB
ss = lambda u: u * u * (3 - 2 * u)

def build():
    shown = pickle.load(open("/tmp/part4d_shown.pkl", "rb"))
    last = shown[m.P4_TO - 1]
    TILT_INIT = "orbit=228,tilt=164"
    tilt = gf.frames_of("goldtilt", 270, init=TILT_INIT); traw = gf.raw_of("goldtilt", 270, TILT_INIT)
    T0 = next(i for i, fr in enumerate(traw) if all(len(set(r)) == 1 for r in fr[1]))
    gc = m.gold_canvas(*tilt[T0])
    grows = [y for y in range(m.H) if gc[y].any()]
    g_top, g_bot = grows[0], grows[-1]
    gold = [int(gc[y, m.W // 2]) for y in range(g_top, g_bot + 1)]
    NG = len(gold)
    # part 4's last frame: the bar's lines (colour of the six equal columns, the idle byte's dither: its 1 bits are black)
    brow = [y for y in range(185) if int(last[y][0])]
    NB = len(brow)
    bcol = [int(last[y][0]) for y in brow]
    bgh = [bin(int(last[y][6])).count("1") / 8.0 for y in brow]
    bmean = [RGB[bcol[s]] * (1 - bgh[s]) for s in range(NB)]
    y_start = brow[0] + WY
    ytraj = [traw[T0 - MOVE + j][0] - traw[T0][0] for j in range(MOVE)]
    start = [bmean[min(NB - 1, int(i * NB / NG))] for i in range(NG)]
    prev = [None] * NG
    J0 = (MOVE - FADE) // 2
    frames, canvas = [], []
    for j in range(MOVE):
        t = m.P4_TO + j
        u = ss((j + 1) / MOVE)
        n = max(NG, int(round(NB + (NG - NB) * u)))
        top = (g_top + ytraj[j]) + (y_start - (g_top + ytraj[0])) * (1.0 - u)
        y0 = int(round(top))
        fade = ss(min(1.0, max(0.0, (j - J0) / float(FADE))))
        rowc = []                                                         # the bar's n lines: the colour (a flicker pair resolved for this line and frame)
        for i in range(n):
            y = y0 + i
            gi = min(NG - 1, int(i * NG / n))
            if fade <= 0.0:
                s = min(NB - 1, int(i * NB / n))
                if bgh[s] == 0: c = bcol[s]
                else:
                    p = m.best_pair(bmean[s], None); a, b = m.PAIRS[p]; c = a if ((y + t) & 1) == 0 else b
            elif fade >= 1.0:
                c = gold[gi]
            else:
                p = m.best_pair(start[gi] * (1 - fade) + RGB[gold[gi]] * fade, prev[gi]); prev[gi] = p
                a, b = m.PAIRS[p]; c = a if ((y + t) & 1) == 0 else b
            rowc.append(c)
        # the border: black (window width) -> alternating -> the bar's colour (full width), at a third and two thirds of the move
        stage = 0 if u < 1 / 3 else (1 if u < 2 / 3 else 2)
        Y0line = y0 + R0 - TOPPAD
        mrow = [0] * ROWS; brow_ = [0] * ROWS
        for i, c in enumerate(rowc):
            r = TOPPAD + i
            assert r < ROWS, (j, n)
            mrow[r] = c
            y = y0 + i
            brow_[r] = 0 if stage == 0 else (c if stage == 2 else (c if ((y + t) & 1) == 0 else 0))
        frames.append((Y0line, mrow, brow_))
        # the canvas as the C64 shows it: segment 0 (the left border), the window's five segments, segment 6 (the right border)
        cv = np.zeros((m.H, m.W), int)
        for r in range(ROWS):
            yy = Y0line + r - R0
            if 0 <= yy < m.H:
                cv[yy, 33:353] = mrow[r]
                cv[yy, 353:] = brow_[r]
                cv[yy, :33] = brow_[r]
        canvas.append(cv)
    return frames, canvas, T0, (g_top, NG, NB)

def main():
    frames, canvas, T0, info = build()
    NG = info[1]
    # the frames from MOVEX on are plain gold (the 24 gold lines, full width): only the position is stored
    gold_rows = None
    MOVEX = MOVE
    for j in range(MOVE - 1, -1, -1):
        Y0, mr, br = frames[j]
        ok = all(mr[TOPPAD + i] == mr[TOPPAD + i] for i in range(NG))
        if frames[j][1][TOPPAD:TOPPAD + NG] == frames[-1][1][TOPPAD:TOPPAD + NG] and frames[j][2] == frames[j][1] and not any(frames[j][1][:TOPPAD]) and not any(frames[j][1][TOPPAD + NG:]):
            MOVEX = j
        else:
            break
    print("plain gold from frame", MOVEX)
    out = []
    for j, (Y0, mr, br) in enumerate(frames):
        out.append([Y0])
        if j >= MOVEX: continue
        n = max(i + 1 for i in range(ROWS - TOPPAD) if mr[TOPPAD + i] or br[TOPPAD + i])
        cols = mr[TOPPAD:TOPPAD + n]
        # border mode: 0 black, 1 the bar's colour, 2 / 3 alternating (phase 0 / 1: the line i has the colour when (i + phase) is even)
        bd = br[TOPPAD:TOPPAD + n]
        if not any(bd): mode = 0
        elif bd == cols: mode = 1
        else:
            mode = None
            for ph in (0, 1):
                if all(bd[i] == (cols[i] if (i + ph) % 2 == 0 else 0) for i in range(n)): mode = 2 + ph
            assert mode is not None, (j, cols, bd)
        out[-1] += [n, mode] + cols
    flat = sum((len(o) for o in out))
    offs = [sum(len(o) for o in out[:j]) for j in range(MOVE)]
    pickle.dump(offs, open('/tmp/move_offs.pkl', 'wb'))
    with open("move.inc", "w") as f:
        f.write("; generated by gen_move.py: the blue bar of part 4's last frame -> goldtilt's gold bar.  Per frame: [Y0] [n, border mode, n colours] (the frames from MOVEX on: Y0 only, plain gold)\n")
        f.write(f"MOVEN = {MOVE}\nMOVEX = {MOVEX}\nmvdata:\n")
        for o in out:
            f.write("        .byte " + ", ".join(str(v) for v in o) + "\n")
        f.write("mvgold:                                  ; the plain gold frames' 24 lines (the highlight included: goldtilt's first flat frame)\n        .byte " + ", ".join(str(v) for v in frames[-1][1][TOPPAD:TOPPAD + NG]) + "\n")
    print("wrote move.inc,", flat, "bytes; gold rows:", [mr for mr in frames[-1][1][TOPPAD:TOPPAD + NG]])
    if len(sys.argv) > 1:
        import ideas_video as iv
        from PIL import Image
        v = iv.Video(sys.argv[1], m.W * 3, m.H * 3, fps=60)
        for c in canvas:
            v.add(Image.fromarray(np.repeat(np.repeat(RGB[c].astype(np.uint8), 3, axis=0), 3, axis=1)))
        v.close(); print("wrote", sys.argv[1])
    pickle.dump(canvas, open("/tmp/move_canvas.pkl", "wb"))

if __name__ == "__main__":
    main()
