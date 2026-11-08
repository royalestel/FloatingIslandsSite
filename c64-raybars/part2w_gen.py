#!/usr/bin/env python3
"""Part 3's waves on the C64 (6 columns) as CHANGE STREAMS on part2c's engine.

The raster loop reads 7 byte patterns a line (6 columns + the idle byte), a page each, for the frame's parity:
two sets of 7 pages, S0 for even frames, S1 for odd ones (the flicker pairs make the colour bytes depend on the
frame parity).  Frame t shows S[t&1], which holds frame t-2 until the changes are applied: runs of changed bytes
(page, first line, length, bytes), found by comparing frame t with frame t-2.  S[t&1] is free during the two
blanks before frame t (frame t-2 has been drawn, frame t-1 shows the other set), so the runs of a frame are shared
between the two: the peak frames (about 290 changed bytes) cost more than one blank holds.

  part2w_tab.s   the initial pages (frames N-2 and N-1: the loop wraps) and the page address table
  part2w_str.bin the stream, 8 KB ROML banks, each blank = a record: [n runs] n x ([page][line][len] bytes); $ff = next bank
  part2w.inc     constants

    SPLITS=6 python3 part2w_gen.py
"""
import os, pickle, sys
os.environ.setdefault("SPLITS", "6")
import numpy as np

H = 200
BUDGET = 6700            # cycles of delta work in one blank: the blank holds about 7.4 k with the loop on lines 4..184; update itself takes ~600
C_BYTE, C_RUN = 14, 81   # cost model (measured in the simulator): cycles a byte, cycles a run

def load():
    frames, gh = pickle.load(open("/tmp/part2w_frames.pkl", "rb"))
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

def main():
    img = load(); N = len(img)
    assert N % 2 == 0
    # The schedule: the pages are simulated.  Blank b_x (before frame x+1) must bring the set of frame x+1 up to date
    # (priority: the frame is imminent) and may start on the set of frame x+2 (free now): runs = bytes that differ from
    # the frame's image, applied while the blank's budget lasts; whatever is left is found again in the next blank.
    state = {0: img[N - 2].copy(), 1: img[N - 1].copy()}
    # (the first blanks of the loop start from the same state: images N-2 and N-1 are in the pages)
    blanks, load_, stale = [], [], []
    for x in range(N):                                       # record j = the blank before frame j: prepares frame j, may start on j+1
        t1 = x % N; t2 = (x + 1) % N
        cand = [(r, 0) for r in runs_between(state[t1 & 1], img[t1], t1 & 1)] + [(r, 1) for r in runs_between(state[t2 & 1], img[t2], t2 & 1)]
        chosen, used = [], 0
        for pri in (0, 1):
            for r, _ in sorted([c for c in cand if c[1] == pri], key=lambda c: -len(c[0][2])):
                cost = C_BYTE * len(r[2]) + C_RUN
                if used + cost <= BUDGET or (pri == 0 and used == 0):
                    chosen.append(r); used += cost
                    page, line, data = r
                    state[page // 7][line:line + len(data), page % 7] = np.frombuffer(data, dtype=np.uint8)
        blanks.append(chosen); load_.append(used)
        stale.append(int((state[t1 & 1] != img[t1]).any(axis=1).sum()))      # lines of frame x+1 that are not exact
    # the loop: record x for x in 0..N-1 are the ones in the stream; the lead-in blanks N-2, N-1 are the last two
    blanks = blanks[:N]; load_ = load_[:N]
    late = [x for x in range(N) if stale[x]]
    print(f"frames with a stale line: {len(late)} of {N}; stale lines mean {np.mean([stale[x] for x in late] or [0]):.1f}, max {max(stale[:N])}")
    open("part2w_late.txt", "w").write(" ".join(str(x) for x in late))   # frames shown with stale lines
    worst = max(load_)
    print(f"{N} frames; worst blank {worst} cycles (budget {BUDGET}), mean {int(np.mean(load_))}")
    # the stream: 8 KB banks, records never straddle
    banks, cur = [], bytearray()
    start = {}
    for x in range(N):
        rec = bytearray([len(blanks[x])])
        for page, line, data in blanks[x]:
            rec += bytes([page, line, len(data)]) + data
        assert len(blanks[x]) < 250
        if len(cur) + len(rec) > 0x2000 - 1:
            cur.append(0xFF); banks.append(bytes(cur).ljust(0x2000, b"\xff")); cur = bytearray()
        start[x] = (len(banks), len(cur))
        cur += rec
    banks.append(bytes(cur).ljust(0x2000, b"\xff"))
    open("part2w_str.bin", "wb").write(b"".join(banks))
    # the initial pages: S0 = frame N-2, S1 = frame N-1 (the first two blanks bring them to frames 0 and 1)
    with open("part2w_tab.s", "w") as f:
        f.write("; generated by part2w_gen.py -- do not edit\n.segment \"PAGES\"\n.export pages\n.align 256\npages:\n")
        for par, fr in ((0, N - 2), (1, N - 1)):
            for k in range(7):
                b = img[fr][:, k].tolist() + [0] * 56
                for i in range(0, 256, 16):
                    f.write("        .byte " + ",".join(str(v) for v in b[i:i + 16]) + "\n")
    open("part2w.inc", "w").write(f"; generated by part2w_gen.py\nIMGBANKS = 1\nNF = {N}\nNBANKS = {len(banks)}\n")
    print(f"stream: {len(banks)} bank(s) of 8 KB")

if __name__ == "__main__":
    main()
