#!/usr/bin/env python3
"""Part 3's waves on the C64 (6 columns) as CHANGE STREAMS on part2c's engine.

The raster loop reads 7 byte patterns a line (6 columns + the idle byte), a page each, for the frame's parity:
two sets of 7 pages, S0 for even frames, S1 for odd ones (the flicker pairs make the colour bytes depend on the
frame parity).  Frame t shows S[t&1], which holds frame t-2 until the changes are applied: runs of changed bytes
(page, first line, length, bytes), found by comparing frame t with frame t-2.  S[t&1] is free during the two
blanks before frame t (frame t-2 has been drawn, frame t-1 shows the other set), so the runs of a frame are shared
between the two: the peak frames (about 290 changed bytes) cost more than one blank holds.

  part4c_tab.s   the initial pages (frames N-2 and N-1: the loop wraps) and the page address table
  part4c_str.bin the stream, 8 KB ROML banks, each blank = a record: [n runs] n x ([page][line][len] bytes); $ff = next bank
  part4c.inc     constants

    SPLITS=6 python3 part4c_gen.py
"""
import os, pickle, sys
os.environ.setdefault("SPLITS", "6")
import numpy as np
import wavesched as ws

H = 200
BUDGET = 3000 if os.environ.get("PLATFORM", "NTSC") == "NTSC" else 6700            # cycles of delta work in one blank: the blank holds about 7.4 k with the loop on lines 4..184; update itself takes ~600
C_BYTE, C_RUN = 14, 81   # cost model (measured in the simulator): cycles a byte, cycles a run

def load():
    frames, gh = pickle.load(open(os.environ.get("FRAMES", "/tmp/part4_frames.pkl"), "rb"))
    N = len(frames)
    img = []
    for t in range(N):
        cols = frames[t]                                    # 200 x 6
        idle = np.array(gh[t], dtype=np.uint8)              # 200
        img.append(np.concatenate([cols, idle[:, None]], axis=1).astype(np.uint8))   # 200 x 7
    return img

MAXRUN = 120             # a run is at most 120 bytes: the copy loop counts down with bpl
GAP = 8                  # runs closer than this are merged (a run costs more than a few bytes)

def runs_between(a, b, parity):
    """runs of bytes where b differs from a: (page id, line, bytes); gaps of up to GAP equal bytes are copied too."""
    out = []
    for k in range(7):
        d = a[:, k] != b[:, k]
        y = 0
        while y < H:
            if d[y]:
                y1 = y + 1
                while y1 < H:
                    nxt = y1
                    while nxt < H and not d[nxt] and nxt - y1 < GAP: nxt += 1
                    if nxt < H and d[nxt]: y1 = nxt + 1
                    else: break
                for s0 in range(y, y1, MAXRUN):
                    e0 = min(y1, s0 + MAXRUN)
                    out.append((parity * 7 + k, s0, bytes(b[s0:e0, k].tolist())))
                y = y1
            else:
                y += 1
    return out

HOLD = (270, 730) if os.environ.get("HOLD2") else None     # busy stretch: held frames (picture and flicker) in pairs (HS+2k, HS+2k+1)

def page_sets(N):
    """the set (0/1) each frame is shown from: alternate, except the odd frame of a held pair keeps its partner's set"""
    S = [0] * N
    for t in range(1, N):
        held = HOLD is not None and HOLD[0] < t < HOLD[1] and t % 2 == 1
        S[t] = S[t - 1] if held else S[t - 1] ^ 1
    return S

def main():
    img = load(); N = len(img)
    assert N % 2 == 0
    S = page_sets(N)
    NOTOG = [S[x] == S[x - 1] for x in range(N)]           # NOTOG[0]: S[-1] = S[N-1]
    assert S[N - 1] == 1, "the sets must alternate across the wrap"
    # The schedule: the pages are simulated.  Blank b_x (before frame x+1) must bring the set of frame x+1 up to date
    # (priority: the frame is imminent) and may start on the set of frame x+2 (free now): runs = bytes that differ from
    # the frame's image, applied while the blank's budget lasts; whatever is left is found again in the next blank.
    state = {0: img[0].copy(), 1: img[1].copy()}   # the chain starts each part on its own first frames
    # (the first blanks of the loop start from the same state: images N-2 and N-1 are in the pages)
    blanks, load_, stale, capacity, Fs, shown = [], [], [], [], [], []
    for x in range(N):                                       # record x = the blank before frame x: prepares frame x, may start on x+1
        t1 = x % N; t2 = (x + 1) % N
        cand = [(r, 0) for r in runs_between(state[S[t1]], img[t1], S[t1])] + [(r, 1) for r in runs_between(state[S[t2]], img[t2], S[t2])]
        Fx = min(ws.F_of(img[t1]), 127)                           # bit 7 of the record's F = hold                                        # the first active line of the frame shown after this blank
        a_cap, b_cap = ws.budgets(Fx)                                # group A: before line 49; group B: after the DEN write, until line 49 + Fx
        A, B, ua, ub = [], [], 0, 0
        for pri in (0, 1):
            for r, _ in sorted([c for c in cand if c[1] == pri], key=lambda c: -len(c[0][2])):
                cost = C_BYTE * len(r[2]) + C_RUN
                if ua + cost <= a_cap or (pri == 0 and ua == 0 and not A): A.append(r); ua += cost
                elif ub + cost <= b_cap: B.append(r); ub += cost
                else: continue
                page, line, data = r
                state[page // 7][line:line + len(data), page % 7] = np.frombuffer(data, dtype=np.uint8)
        chosen, used = A + B, ua + ub
        capacity.append(a_cap + b_cap); Fs.append(Fx)
        blanks.append((Fx | (0x80 if NOTOG[x] else 0), A, B)); load_.append(used)
        stale.append(int((state[S[t1]] != img[t1]).any(axis=1).sum()))      # lines of frame x+1 that are not exact
        shown.append(state[S[t1]].copy())                                    # what frame x really shows (stale lines included)
    # the loop: record x for x in 0..N-1 are the ones in the stream; the lead-in blanks N-2, N-1 are the last two
    blanks = blanks[:N]; load_ = load_[:N]
    late = [x for x in range(N) if stale[x]]
    print(f"frames with a stale line: {len(late)} of {N}; stale lines mean {np.mean([stale[x] for x in late] or [0]):.1f}, max {max(stale)}")
    print("stale lines per frame: median %d, 90%% %d, frames over 64 lines: %d, over 100: %d" % (np.median(stale), np.percentile(stale, 90), sum(s > 64 for s in stale), sum(s > 100 for s in stale)))
    open("part4c_late.txt", "w").write(" ".join(str(x) for x in late))   # frames shown with stale lines
    worst = max(load_)
    print(f"{N} frames; worst blank {worst} cycles, mean {int(np.mean(load_))}; capacity per blank (runs only) mean {int(np.mean(capacity))}, min {min(capacity)}, max {max(capacity)}; first active line F: mean {np.mean(Fs):.0f}, frames with F = 0: {sum(1 for f in Fs if f == 0)}")
    # the stream: 8 KB banks, records never straddle
    banks, cur = [], bytearray()
    start = {}
    for x in range(N):
        rec = bytearray(ws.record(*blanks[x]))
        assert len(blanks[x][1]) < 250 and len(blanks[x][2]) < 250
        if len(cur) + len(rec) > 0x4000 - 1:
            cur.append(0xFF); banks.append(bytes(cur).ljust(0x4000, b"\xff")); cur = bytearray()
        start[x] = (len(banks), len(cur))
        cur += rec
    banks.append(bytes(cur).ljust(0x4000, b"\xff"))
    open("part4c_str.bin", "wb").write(b"".join(banks))
    # the initial pages: S0 = frame N-2, S1 = frame N-1 (the first two blanks bring them to frames 0 and 1)
    with open("part4c_tab.s", "w") as f:
        f.write("; generated by part4c_gen.py -- do not edit\n.segment \"PAGES\"\n.export pages\n.align 256\npages:\n")
        for par, fr in ((0, 0), (1, 1)):
            for k in range(7):
                b = img[fr][:, k].tolist() + [0] * 56
                for i in range(0, 256, 16):
                    f.write("        .byte " + ",".join(str(v) for v in b[i:i + 16]) + "\n")
    pickle.dump(shown[:N], open("/tmp/part4c_shown.pkl", "wb"))
    open("part4c.inc", "w").write(f"; generated by part4c_gen.py\nIMGBANKS = 1\nNF = {N}\nNBANKS = {len(banks)}\n")
    print(f"stream: {len(banks)} bank(s) of 8 KB")

if __name__ == "__main__":
    main()
