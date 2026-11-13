#!/usr/bin/env python3
"""PART 4 on the C64 as DELAYED COPIES (the design of mock_part4_wave.py), 6 columns on part4c's raster loop.

Two movement sources feed the six columns: even columns show source A, odd columns source B, each delayed by 16 k frames (STEP, even: the flicker
phase of a source frame is the displayed frame's).  A source frame is ONE page of colour bytes (rows R0..184); the three columns of a source read
three frames of its ring of pages: the raster loop only needs its 7 page operands (hi bytes) patched per frame, from the record.  In the blank
the engine copies the NEWEST page of each source into a ring slot (runs, part4c's `doruns`) -- no change stream, nothing depends on how much
moves: a source page is the same size every frame.  Identical pages share a slot (nothing is copied while a source is at rest).

  busy frames (until every column is identical): ghost swatches are off (every token is replaced by its flat swatch, as the model does on every line
        where the columns disagree; the mock keeps the ghost swatches on the few lines where all six columns agree: counted below).  Idle byte page = zeros.
  uniform frames (from the first frame in which all six columns are identical: the rest, the hold and the wipe): ghost swatches as the mock draws
        them: colour page C and idle byte page G per frame parity, changed rows copied (preloaded before the first uniform frame).

  record = [F][hi of the 6 column pages][hi of the idle page][nA][runs A][nB][runs B];  a run = [first line][page hi][length] bytes
  RAM: ZERO page $2B, ring A $2C.., ring B, then Ce Co Ge Go.

    SPLITS=6 python3 part4d_gen.py     -> part4d_str.bin, part4d.inc, /tmp/part4d_shown.pkl (what each frame shows: 200 x 7 bytes)
"""
import os, sys, pickle, math
os.environ["SPLITS"] = "6"
import numpy as np
import mock_part4_wave as mw
import wavesched as ws

ms = mw.ms; g4 = ms.g4
H = 200
D = mw.D
R = 66                                           # slots per source (the pages of at most 65 frames are live)
ZERO_HI, U_HI0 = 0x2B, 0x2C                      # the idle byte pages (zero, Ge, Go) must be BELOW $8000: update reads row F's idle byte with the ROM window mapped
A_HI0 = U_HI0 + 4                                # Ce, Co (colour pages by frame parity), Ge, Go at U_HI0..+3
B_HI0 = A_HI0 + R
C_BYTE, C_RUN = float(os.environ.get("C_BYTE", 12.5)), float(os.environ.get("C_RUN", 123))        # the engine's `doruns` (fitted on the 6502 simulator)
MAXRUN = 120
LAST_ROW = 184

def flat_tok(tk, y, f):
    """the token a ghost swatch becomes where the line's columns disagree (ghost_part4.fix_line)"""
    if g4.is_black(tk) or not g4.ghost(tk, y, f): return tk
    if tk >= g4.P25: return g4.P25 + min(g4.FLAT25, key=lambda j: abs(g4.L25[j] - g4.L25[tk - g4.P25]))
    if tk < g4.RED: return min(g4.gp2.FLAT, key=lambda j: abs(g4.gp.RAMP_L[j] - g4.gp2.light(tk)))
    return g4.RED + min(g4.rr.FLAT, key=lambda j: abs(g4.rr.RAMP_L[j] - g4.gp2.light(tk)))

def page_bytes(tokrow, f):
    """the colour bytes of a source page (flat swatches) for displayed frame parity f"""
    out = np.zeros(H, np.uint8)
    for y in range(H):
        tk = int(tokrow[y])
        if tk: out[y] = g4.colour(flat_tok(tk, y, f), y, f)
    return out

def load_tokens():
    p = "/tmp/p4d_tokens.pkl"
    if os.path.exists(p) and not os.environ.get("RETOKEN"):
        TOK = pickle.load(open(p, "rb"))
        if TOK.shape[0] == mw.T_END: return TOK
    TOK = np.array([ms.tokens(t) for t in range(mw.T_END)])
    pickle.dump(TOK, open(p, "wb"))
    return TOK

class Ring:
    """R page slots of one source: content keys, last use, and what each slot holds (for the diff of the next copy)"""
    def __init__(self, hi0):
        self.hi0 = hi0
        self.slot_key = [None] * R; self.slot_rows = [None] * R; self.live = [-1] * R; self.cache = {}
    def find(self, key):
        return self.cache.get(key)
    def alloc(self, t):
        free = [s for s in range(R) if self.live[s] < t]
        assert free, "ring full"
        s = min(free, key=lambda s: self.live[s])
        if self.slot_key[s] is not None: self.cache.pop(self.slot_key[s], None)
        return s

def diff_runs(new, old, lo, hi, hi_byte):
    """runs (line, hi byte, bytes) covering the rows of [lo, hi] where new differs from old (old None: all)"""
    if old is None: d0, d1 = lo, hi
    else:
        d = np.where(new[lo:hi + 1] != old[lo:hi + 1])[0]
        if not len(d): return []
        d0, d1 = lo + int(d[0]), lo + int(d[-1])
    runs = []
    for s0 in range(d0, d1 + 1, MAXRUN):
        e0 = min(d1 + 1, s0 + MAXRUN)
        runs.append((s0, hi_byte, bytes(new[s0:e0].tolist())))
    return runs

def cost(r): return C_BYTE * len(r[2]) + C_RUN

def main():
    TOK = load_tokens(); N = TOK.shape[0]
    uni = [bool((TOK[t] == TOK[t][0]).all()) for t in range(N)]
    T_U = next(t for t in range(N) if all(uni[t:]))
    first = [int(np.where(TOK[t].any(axis=0))[0][0]) if TOK[t].any() else 150 for t in range(N)]
    R0 = min(first[:T_U])
    print(f"{N} frames; busy until {T_U - 1}, uniform from {T_U}; busy rows {R0}..{LAST_ROW}", flush=True)
    MC = None
    if not os.environ.get("NOTUNE"):
        import tunecost
        MC = tunecost.part4_costs(N)
    rings = {0: Ring(A_HI0), 1: Ring(B_HI0)}
    maxD = {0: max(D[k] for k in range(6) if k % 2 == 0), 1: max(D[k] for k in range(6) if k % 2 == 1)}
    pcache = {}
    records, shown, over = [], [], []
    # ---- the uniform frames: colour page C and idle page G per frame parity (ghost swatches as the mock draws them) ----
    def uniform_image(t):
        col = np.zeros(H, np.uint8); idl = np.zeros(H, np.uint8)
        for y in range(H):
            tk0 = int(TOK[t, 0, y])
            line, flat = g4.fix_line([tk0] * 6, y, t)
            tk = line[0]
            col[y] = g4.colour(tk, y, t) if tk else 0
            idl[y] = g4.ghost(tk, y, t) if (tk and not flat and not g4.is_black(tk)) else 0
        col[LAST_ROW + 1:] = 0; idl[LAST_ROW + 1:] = 0
        return col, idl
    UIMG = {t: uniform_image(t) for t in range(T_U, N)}
    uhi = lambda kind, par: U_HI0 + kind * 2 + par
    ucont = {}                                       # (kind, parity) -> the page's current rows (kind 0 colour, 1 idle)
    preload = []                                     # the first uniform frames' pages (both parities), copied in the blanks before T_U
    for t in (T_U, T_U + 1):
        par = t & 1; col, idl = UIMG[t]
        for kind, arr in ((0, col), (1, idl)):
            preload += diff_runs(arr, None, 0, LAST_ROW, uhi(kind, par)); ucont[kind, par] = arr.copy()
    PRE_FROM = T_U - 30
    pre_i = 0; maxload = 0
    for t in range(N):
        f = t & 1
        runs_A, runs_B, his = [], [], []
        if t < T_U:
            for k in range(6):
                s = k % 2; tau = min(max(0, t - D[k]), mw.NMAX)
                pk = (s, tau, f)
                if pk not in pcache: pcache[pk] = page_bytes(TOK[t, k], f)
                content = pcache[pk]
                rg = rings[s]
                key = content[R0:LAST_ROW + 1].tobytes()
                slot = rg.find(key)
                if slot is None:
                    slot = rg.alloc(t)
                    rr_ = diff_runs(content, rg.slot_rows[slot], R0, LAST_ROW, rg.hi0 + slot)
                    (runs_A if s == 0 else runs_B).extend(rr_)
                    rg.slot_key[slot] = key; rg.slot_rows[slot] = content; rg.cache[key] = slot
                rg.live[slot] = max(rg.live[slot], tau + maxD[s])        # read again until the slowest column of the source has left this frame
                his.append(rg.hi0 + slot)
            hiG = ZERO_HI
            cols = np.zeros((H, 7), np.uint8)
            for k in range(6): cols[:, k] = rings[k % 2].slot_rows[his[k] - rings[k % 2].hi0]
        else:
            par = t & 1; col, idl = UIMG[t]
            if t >= T_U + 2:
                for kind, arr in ((0, col), (1, idl)):
                    runs_A.extend(diff_runs(arr, ucont[kind, par], 0, LAST_ROW, uhi(kind, par))); ucont[kind, par] = arr.copy()
            his = [uhi(0, par)] * 6; hiG = uhi(1, par)
            cols = np.zeros((H, 7), np.uint8)
            for k in range(6): cols[:, k] = col
            cols[:, 6] = idl
        cols[LAST_ROW + 1:, :] = 0
        rows_any = np.where(cols.any(axis=1))[0]
        Fx = min(int(rows_any[0]), 127) if len(rows_any) else 127
        Fx = Fx if Fx >= 3 else 0
        if t < T_U: assert Fx == 0 or Fx >= R0, (t, Fx, R0)
        cols[:Fx, :] = 0
        shown.append(cols)
        a_cap, b_cap = ws.budgets(Fx, None if MC is None else MC[min(t, len(MC) - 1)])
        jobs = [r for r in runs_A] + [r for r in runs_B]
        A, B, ua, ub = [], [], 0, 0
        for r in sorted(jobs, key=lambda r: -len(r[2])):
            c = cost(r)
            if ua + c <= a_cap: A.append(r); ua += c
            elif ub + c <= b_cap: B.append(r); ub += c
            else: over.append((t, int(c), int(a_cap - ua), int(b_cap - ub))); A.append(r); ua += c
        if PRE_FROM <= t < T_U:                       # the uniform pages' first copies fill the spare capacity of the busy blanks
            while pre_i < len(preload):
                r = preload[pre_i]; c = cost(r)
                if ua + c <= a_cap: A.append(r); ua += c; pre_i += 1
                elif ub + c <= b_cap: B.append(r); ub += c; pre_i += 1
                else: break
        maxload = max(maxload, ua + ub)
        records.append((Fx, his, hiG, A, B))
    assert pre_i == len(preload), f"preload not finished: {pre_i}/{len(preload)}"
    print(f"frames over budget: {len(over)}" + (f"  first: {over[:6]}" if over else ""), "; heaviest frame's runs: %d cycles" % maxload)
    # ---- the stream ----
    banks, cur = [], bytearray()
    for (Fx, his, hiG, A, B) in records:
        rec = bytearray([Fx] + his + [hiG, len(A)])
        for line, hi, data in A: rec += bytes([line, hi, len(data)]) + data
        rec.append(len(B))
        for line, hi, data in B: rec += bytes([line, hi, len(data)]) + data
        assert len(A) < 250 and len(B) < 250
        if len(cur) + len(rec) > 0x4000 - 1:
            cur.append(0xFF); banks.append(bytes(cur).ljust(0x4000, b"\xff")); cur = bytearray()
        cur += rec
    banks.append(bytes(cur).ljust(0x4000, b"\xff"))
    open("part4d_str.bin", "wb").write(b"".join(banks))
    open("part4d.inc", "w").write(f"; generated by part4d_gen.py\nIMGBANKS = 1\nNF = {N}\nNBANKS = {len(banks)}\nZERO_HI = ${ZERO_HI:02x}\nRING_HI0 = ${U_HI0:02x}\nRING_PAGES = {B_HI0 + R - U_HI0}\n")
    pickle.dump(shown, open("/tmp/part4d_shown.pkl", "wb"))
    print(f"stream: {len(banks)} bank(s) of 16 KB ({sum(len(b) for b in banks)} bytes); ring {R} slots a source; RAM $%04x-$%04x" % (ZERO_HI << 8, (B_HI0 + R) << 8))
    # ---- how far from the mock?  (bytes per row: the six colour bytes and the idle byte, as the mock's fix_line gives them) ----
    dev = []
    for t in range(N):
        sh = shown[t]; cnt = 0
        for y in range(records[t][0], LAST_ROW + 1):
            toks = [int(TOK[t, k, y]) for k in range(6)]
            line, flat = g4.fix_line(toks, y, t)
            exp = [g4.colour(tk, y, t) if tk else 0 for tk in line]
            idl = g4.ghost(next((tk for tk in line if tk), 0), y, t) if (not flat and any(line)) else 0
            if list(sh[y, :6]) != exp or sh[y, 6] != idl: cnt += 1
        dev.append(cnt)
    print("rows (bytes) that differ from the mock: in %d of %d frames, %d rows in all, at most %d in one frame; uniform frames: %d rows" % (
        sum(1 for d in dev if d), N, sum(dev), max(dev), sum(dev[T_U:])))

if __name__ == "__main__":
    main()
