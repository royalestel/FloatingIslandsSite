#!/usr/bin/env python3
"""Part 1 for the C64, one design for NTSC (60 Hz) and PAL (50 Hz), drawing what mock_part1_flicker.py (the owner's reference) draws:
the three circling bars, three more between them from frame 960, the red bars (from the beat at 1218) with their transparency (a red bar over a
blue bar shows the blue bar's swatch from the RED ramp; alone it is a flat red swatch by depth; two red bars on a line: solid red), the stack,
the pause and the straight move to part 2's floor, and the 2 s hold (film time < T_JOIN = part1.T_JOIN).

  1a-1b (film time < T_SPLIT = 960): per frame a 7-byte record [dim level][(routine, x) x 3] in ROM banks; each bar is drawn by an UNROLLED
        ROUTINE per (thickness, start-line parity): lda #code / sta buf+i,x with the buffer codes baked in.
  1c-1d (film time >= 960): a STREAM of runs of changed buffer rows copied from shape arrays into the persistent buffer; each frame's record is
        [dim level][number of runs][(array address, first line, rows - 1) x n].  The generator composes the frame exactly like the mock
        (blue layer, red layer, tint, solid overlaps) and covers the changed rows with runs of bar arrays (blue / red-tinted) or constants.

  BUFFER CODE (8 bits):  level 1..24 | centre << 5 | blk << 6 | red << 7.   blk = the swatch table block: the wanted row parity (the row's place in
  its bar, counted from the nearer edge: min(i, T-1-i); on the finished floor the screen row's parity, as part 2) XOR the screen row's parity.
  red = 1 with level 1..24: the blue swatch of that level, drawn from the red ramp (the tint);  red = 1 with level 25..29: a flat red swatch
  (alone / solid) that the dimming never touches.
  A DIM MAP (256 bytes, 16 dim levels) turns a code into a swatch index  64 * red + 32 * blk + level'  (7 bits) in the raster rows
  (ldy buf / lda (dm),y / tax); the swatch tables (colour, ghost byte) have 128 entries for each (frame parity, row parity).

    PLATFORM=NTSC python3 part1r_gen.py   ->  part1r.inc, part1r.cfg, part1r_rout.s, part1r_data.s, part1r_str.bin,
                                              /tmp/part1r_model.pkl  (the frames as the C64 shows them)
"""
import os, math, pickle
os.environ.setdefault("SPLITS", "6")
import part1 as p1
import part1_proc as q
import preview_v10 as v10
import mock_part1_flicker as mk                    # patches p1.bars_all: the three extra bars (from frame 960); the red rules
import ghost_preview as gp
import red_ramp_saved as rr

PLAT = os.environ.get("PLATFORM", "NTSC")
NTSC = PLAT == "NTSC"
RATE = 1.0                                        # one film frame per displayed frame (NTSC: the 60 fps mock-up's timing, the one the music was timed to)
H, PAD, LBW = 200, 63, 0x0500
BUDGET = 3700 if NTSC else 6500
PLAYCOST = 1650                  # cycles of the tune's play routine (max 1577) + the call: taken off the blank's budget when it is called
plays = (lambda n: n != 0 and n % 6 != 0) if NTSC else (lambda n: n != 0)
T_SPLIT = mk.T0                                   # film time where the routines end (the extra bars start) and the stream begins
T_FLOOR = p1.T_BLEND0 + p1.BLEND_LEN              # from here the floor is finished: screen-row parity, as part 2
NN = int((p1.T_JOIN - 1) / RATE) + 1
NR = int(math.ceil(T_SPLIT / RATE))
tau = lambda n: n * RATE
NDIM = 16                                         # dim maps (the 32 levels of the mock-up, every second one)
RF = {25: 1, 26: 2, 27: 3, 28: 4, 29: mk.SOLID_RED}    # flat red codes (level) -> red ramp swatch
RFCODE = {v: k for k, v in RF.items()}

# ---- buffer codes, parity, shapes ---------------------------------------------------------------------------------
def blk_of(y, i, T, floor):
    """table block of row i (screen row y) of a bar of thickness T: wanted row parity XOR the screen row's parity"""
    par = (y & 1) if floor else (min(i, T - 1 - i) & 1)
    return par ^ (y & 1)

def levels(T, full):
    """swatch levels of the rows of a bar.  full = a circling bar (plain thickness): its levels plus the centre bit (the middle 4 rows of a bar of 8 rows
    or more keep lighter while dimmed); a stack bar (BT) has its own profile."""
    prof = list(gp.PROF[T]); T = int(T); mid = (T - 1) // 2
    if full and T >= 8:
        prof = [(k | 32) if (k and mid - 1 <= r <= mid + 2) else k for r, k in enumerate(prof)]
    return prof

def code_array(T, y0, full, red, floor):
    """the buffer codes of every row of a bar whose first row is on line y0"""
    out = []
    for i, k in enumerate(levels(T, full)):
        out.append(0 if not k else ((k & 63) | (blk_of(y0 + i, i, int(T), floor) << 6) | (128 if red else 0)))
    return bytes(out)

# ---- dim maps and swatch tables -------------------------------------------------------------------------------------
def dimmap(di):
    """256 entries: buffer code -> swatch index (7 bits).  di 0..NDIM-1 (the mock-up's 31-level dimming, every second level)."""
    d31 = int(round(di * 31.0 / (NDIM - 1)))
    out = [0] * 256
    for b in range(256):
        lvl, c, p, red = b & 31, (b >> 5) & 1, (b >> 6) & 1, b >> 7
        if red and lvl >= 25:                                         # flat red, alone or solid: not dimmed
            out[b] = 64 + 32 * p + RF[lvl] if lvl in RF else 0
        elif lvl == 0 or lvl > 24:
            out[b] = 0
        else:
            x = q.DIMT[d31][c][lvl] + 32 * p                          # the dimmed blue swatch (level' + block)
            out[b] = x + (64 if red else 0)                           # tint: the same number from the red ramp
    return out
MAPS = [dimmap(di) for di in range(NDIM)]
assert max(max(m) for m in MAPS) < 128

def dim_at(t):
    ti = int(round(t))
    d = q.DX[ti - q.DIM0] if q.DIM0 <= ti < q.DIM0 + q.DIMN else 0
    return int(round(d * (NDIM - 1) / 31.0))

def tables():
    """colour and ghost-byte tables: per (frame parity, screen row parity) 128 entries = blue block 0 / 1 (32 each), red block 0 / 1;
    block b uses the row parity (screen parity XOR b)"""
    col, gh = [], []
    for fp in (0, 1):
        for rp in (0, 1):
            c, g_ = [], []
            for red in (0, 1):
                for blk in (0, 1):
                    r = rp ^ blk
                    if red:
                        cc = [0] + [rr.colour(k, r, fp) for k in range(1, len(rr.RAMP_L))]
                        gg = [0] + [rr.ghost(k, r, fp) for k in range(1, len(rr.RAMP_L))]
                    else:
                        cc = [v10.colour(k, r, fp) for k in gp.LAD]
                        gg = [v10.ghost(k, r, fp) for k in gp.LAD]
                    c += (cc + [0] * 32)[:32]; g_ += (gg + [0] * 32)[:32]
            col.append(c); gh.append(g_)
    return col, gh
COL, GH = tables()

# ---- section 1: routines (frames < T_SPLIT) -----------------------------------------------------------------------------
rids = {}                                        # (T, parity) -> routine id
def rid_of(T, p):
    if (T, p) not in rids: rids[(T, p)] = len(rids)
    return rids[(T, p)]
def shape(T, p):
    return list(code_array(T, p, True, False, False))

def section1():
    recs, bufs, dis, clipped = [], [], [], 0
    for n in range(NR):
        t = tau(n); di = dim_at(t)
        buf, rec = [0] * H, [di]
        bars = []
        for y0, T in p1.frame_list(t):
            if y0 >= H or y0 + T <= 0: continue
            if y0 + PAD > 255: clipped += 1; continue
            bars.append((y0, T))
        assert len(bars) <= 3, (n, bars)
        for y0, T in bars:
            r = rid_of(T, y0 & 1)
            rec += [r, y0 + PAD]
            for i, v in enumerate(shape(T, y0 & 1)):
                if 0 <= y0 + i < H: buf[y0 + i] = v
        while len(rec) < 7: rec += [255, 0]
        recs.append(bytes(rec)); bufs.append(buf); dis.append(di)
    return recs, bufs, dis, clipped

def routines_text(seg_of):
    lines = []
    for (T, p), r in sorted(rids.items(), key=lambda kv: kv[1]):
        lines.append(f'.segment "{seg_of[r]}"\nrt{r}:')
        prev = None
        for i, v in enumerate(shape(T, p)):
            if v != prev: lines.append(f"        lda #{v}")
            lines.append(f"        sta {LBW - PAD + i},x")
            prev = v
        lines.append("        rts")
    return "\n".join(lines) + "\n"

# ---- section 2: the composed frames and their runs ----------------------------------------------------------------------
ARRS = {}                                         # content -> the one bytes object (identity = "the same array")
def arr_of(T, y0, full, red, floor):
    a = code_array(T, y0, full, red, floor)
    return ARRS.setdefault(a, a)
CONST = {}
def const_of(code):
    if code not in CONST: CONST[code] = bytes([code]) * 64
    return CONST[code]
ZERO = bytes(128)

def compose(t):
    """frame t >= T_SPLIT as mock_part1_flicker draws it: (buffer codes, sources).  sources[y] = (array, index) or (const array, None) or None."""
    bars = p1.bars_all(t)
    floor = t >= T_FLOOR
    chosen = {i for i, b in enumerate(bars) if mk.red_state(t, i, b)}
    blue = [None] * H                              # (array, i) of the nearest blue bar's row
    redn = [0] * H; redk = [mk.RED_SWATCH] * H; rblk = [0] * H
    blue_t = [None] * H                            # (T, y0, full) to build the tinted variant
    for idx in sorted(range(len(bars)), key=lambda i: -bars[i][2]):                   # far first
        b = bars[idx]
        z, yc = max(b[0], 0.6), b[1]
        T = max(1, min(p1.TMAX, int(round(2 * p1.F * p1.R / z))))
        full = len(b) <= 3
        if len(b) > 3:
            e_i = b[5] if len(b) > 5 else b[3]
            T = gp.BT(T, gp.edge_level(e_i), e_i, b[4])
        y0 = int(round(yc - T / 2))
        if y0 >= H or y0 + T <= 0 or not any(gp.PROF[T][max(0, -y0):H - y0]): continue
        prof = gp.PROF[T]
        for i in range(int(T)):
            y = y0 + i
            if not 0 <= y < H: continue
            if idx in chosen:
                redn[y] += 1; redk[y] = mk.red_swatch_for(z); rblk[y] = blk_of(y, i, int(T), floor)
            elif prof[i]:
                blue[y] = (arr_of(T, y0, full, False, floor), i); blue_t[y] = (T, y0, full)
    buf, own = [0] * H, [None] * H
    for y in range(H):
        if redn[y] >= 2:
            code = RFCODE[mk.SOLID_RED] | (rblk[y] << 6) | 128; own[y] = (const_of(code), None); buf[y] = code
        elif redn[y] and blue[y]:
            T, y0, full = blue_t[y]; a = arr_of(T, y0, full, True, floor); i = blue[y][1]
            own[y] = (a, i); buf[y] = a[i]
        elif redn[y]:
            code = RFCODE[redk[y]] | (rblk[y] << 6) | 128; own[y] = (const_of(code), None); buf[y] = code
        elif blue[y]:
            own[y] = blue[y]; buf[y] = blue[y][0][blue[y][1]]
    return buf, own

def src_ok(own, y, arr, i0, y0):
    """row y continues the run that started at y0 from array arr at index i0"""
    o = own[y]
    return o is not None and o[0] is arr and (i0 is None or o[1] == i0 + (y - y0))

def build_runs(buf, own, prev):
    """runs (array, first index, first line, rows) that cover every row whose code differs from the buffer; gaps of up to 4 unchanged rows are bridged"""
    runs, y = [], 0
    while y < H:
        if buf[y] == prev[y]: y += 1; continue
        if own[y] is None:
            y1 = y
            while y1 < H and own[y1] is None and buf[y1] != prev[y1] and y1 - y < 128: y1 += 1
            runs.append((ZERO, 0, y, y1 - y)); y = y1
            continue
        arr, i0 = own[y]; y1 = y + 1
        lim = 64 if i0 is None else 128
        while y1 < H and y1 - y < lim:
            if src_ok(own, y1, arr, i0, y) and (i0 is not None or True):
                y1 += 1
            else: break
            # (rows are copied while the source continues; trimmed back to the last changed row below)
        last = y
        for k in range(y, y1):
            if buf[k] != prev[k]: last = k
        # bridge only small gaps: cut the run at the first gap of more than 4 unchanged rows
        end, gap = y, 0
        for k in range(y, last + 1):
            if buf[k] != prev[k]: end = k + 1; gap = 0
            else:
                gap += 1
                if gap > 4: break
        runs.append((arr, i0 if i0 is not None else 0, y, end - y)); y = end
    return runs

def section2(prev):
    runs_all, bufs, stale = [], [], []
    dis = []
    for n in range(NR, NN):
        t = tau(n)
        buf, own = compose(t)
        runs = build_runs(buf, own, prev)
        chosen, used, state = [], 150, list(prev)
        for r in sorted(runs, key=lambda r: -r[3]):
            c = 14 * r[3] + 75
            if used + c <= BUDGET - PLAY[n]:
                chosen.append(r); used += c
                arr, i0, y, n_ = r; state[y:y + n_] = list(arr[i0:i0 + n_])
        chosen.sort(key=lambda r: r[2])
        stale.append(sum(state[y] != buf[y] for y in range(H)))
        runs_all.append(chosen); bufs.append(state); prev = state; dis.append(dim_at(t))
    return runs_all, bufs, dis, stale

def play_costs():
    """cycles of the tune's play call in the blank before frame n (0 = not called), by running the tune on the 6502 simulator"""
    from c64cpu import MPU
    data = open("music/Alpha.dat", "rb").read()
    mpu = MPU(); mem = mpu.memory
    for i, b in enumerate(data): mem[0x1000 + i] = b
    def call(addr, a=0):
        for i, v in enumerate([0x20, addr & 255, addr >> 8, 0]): mem[0x0334 + i] = v
        mpu.pc, mpu.sp, mpu.a, mpu.x, mpu.y = 0x0334, 0xFF, a, 0, 0
        c = mpu.processorCycles
        while mpu.pc != 0x0337: mpu.step()
        return mpu.processorCycles - c
    call(0x1000, 0)
    return [(call(0x1003) + 40) if plays(n) else 0 for n in range(NN)]
PLAY = None

def main():
    global PLAY
    PLAY = play_costs()
    recs, bufs1, dis1, clipped = section1()
    runs_all, bufs2, dis2, stale = section2(bufs1[-1])
    arrays = {}
    for runs in runs_all:
        for arr, i0, y, n_ in runs: arrays[arr] = 1
    ar1_base = 0x1400
    if os.path.exists("part1r.lbl"):                     # the code's end from the last build: AR1 fills the rest of $0801-$0FFF
        lbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open("part1r.lbl")}
        if "codeend" in lbl: ar1_base = (lbl["codeend"] + 0x1F) & ~0x1F
    # --- memory layout: routines in $8000-$BFFF (RAM under the cartridge window), arrays in $0D00-$0FFF, $3D00-$3EFF, $3F00 and $5600-$7FFF, tables $5200, maps $C000+
    sizes = {}
    for (T, p), r in rids.items():
        sh = shape(T, p)
        sizes[r] = 1 + sum(5 if i == 0 or v != sh[i - 1] else 3 for i, v in enumerate(sh))
    pools = {"ROUTA": [0x8000, 0x4000 - 0x200, 0], "AR1": [ar1_base, 0x1000 - ar1_base - int(os.environ.get("AR1_MARGIN", 0x40)), 0], "AR3": [0x3F00, 0x00FF, 0], "AR4": [0x3D00, 0x0200, 0],
             "AR2": [0x5600, 0x2A00, 0]}   # base, size, used
    seg_of = {}
    for r in sorted(sizes):                                  # routines: ROUTA first, then AR2
        for k in ("ROUTA", "AR2"):
            if pools[k][2] + sizes[r] <= pools[k][1]:
                seg_of[r] = k; pools[k][2] += sizes[r]; break
        else: raise SystemExit("routines do not fit")
    regs = {k: bytearray() for k in ("AR1", "AR3", "AR4", "AR2")}
    addr = {}
    for a_ in sorted(arrays, key=len, reverse=True):         # arrays: AR1, AR3, AR4, then what is left of AR2 (they follow that pool's routines)
        for k in ("AR1", "AR3", "AR4", "AR2"):
            base, size, used_ = pools[k]
            if used_ + len(regs[k]) + len(a_) <= size:
                addr[a_] = base + used_ + len(regs[k]); regs[k] += a_; break
        else: raise SystemExit("arrays do not fit")
    # --- the stream: section 1 records then section 2 records, in 16 KB banks
    banks, cur = [], bytearray()
    def put(r):
        nonlocal cur
        if len(cur) + len(r) > 0x4000 - 1:
            cur.append(0xFE); banks.append(bytes(cur).ljust(0x4000, b"\xff")); cur = bytearray()
        cur += r
    for r in recs: put(r)
    for di, runs in zip(dis2, runs_all):
        assert len(runs) < 250
        r = bytearray([di, len(runs)])
        for arr, i0, y, n_ in runs:
            ptr = addr[arr] + i0
            r += bytes([ptr & 255, ptr >> 8, y, n_ - 1])
        put(bytes(r))
    banks.append(bytes(cur).ljust(0x4000, b"\xff"))
    open("part1r_str.bin", "wb").write(b"".join(banks))
    # --- source files
    with open("part1r_rout.s", "w") as f:
        f.write("; generated by part1r_gen.py -- do not edit\n" + routines_text(seg_of))
        f.write('.segment "ROUTA"\n.export rtlo, rthi\nrtlo:\n')
        n_ = len(rids); f.write("        .byte " + ",".join(f"<rt{i}" for i in range(n_)) + "\n")
        f.write("rthi:\n        .byte " + ",".join(f">rt{i}" for i in range(n_)) + "\n")
    with open("part1r_data.s", "w") as f:
        f.write("; generated by part1r_gen.py -- do not edit\n")
        for k, buf in regs.items():
            f.write(f'.segment "{k}"\n' + "".join("        .byte " + ",".join(str(v) for v in buf[i:i + 32]) + "\n" for i in range(0, len(buf), 32)))
        f.write('.segment "MAPS"\n.export dmlo, dmhi, map0\n.align 256\n')
        for di in range(NDIM):
            f.write(f"map{di}:\n" + "".join("        .byte " + ",".join(str(v) for v in MAPS[di][i:i + 32]) + "\n" for i in range(0, 256, 32)))
        f.write('.segment "ROUTA"\n')
        f.write("dmlo:\n        .byte " + ",".join(f"<map{di}" for di in range(NDIM)) + "\n")
        f.write("dmhi:\n        .byte " + ",".join(f">map{di}" for di in range(NDIM)) + "\n")
    with open("part1r.inc", "w") as f:
        f.write("; generated by part1r_gen.py -- do not edit\n")
        if NTSC: f.write("NTSC = 1\n")
        f.write(f"NF = {NN}\nNR = {NR}\nIMGBANKS = 4\nPAD = {PAD}\nLBW = ${LBW:04x}\n")
        for name, tabs in (("colt", COL), ("ght", GH)):
            f.write(f".macro {name.upper()}\n")
            for t_ in tabs: f.write("        .byte " + ",".join(str(v & 255) for v in t_) + "\n")
            f.write(".endmacro\n")
    open("part1r.cfg", "w").write(f"""# generated by part1r_gen.py   $1000-$2A33 = Alpha.sid (LukHash), the rows after it; $3FFF is the VIC's idle byte (nothing may use it)
MEMORY {{
    ZP:       start = $0002, size = $00FE, type = rw;
    LOADADDR: start = $07FF, size = $0002, file = %O;
    MAIN:     start = $0801, size = $07FF, file = %O, fill = yes;
    MUSIC:    start = $1000, size = $1B00, file = %O, fill = yes;
    ROWS0:    start = $2B00, size = $1200, file = %O, fill = yes;
    AR4:      start = $3D00, size = $0200, file = %O, fill = yes;
    AR3:      start = $3F00, size = $0100, file = %O, fill = yes;
    ROWS1:    start = $4000, size = $1200, file = %O, fill = yes;
    TAB:      start = $5200, size = $0400, file = %O, fill = yes;
    AR2:      start = $5600, size = $2A00, file = %O, fill = yes;
    ROUTA:    start = $8000, size = $4000, file = %O, fill = yes;
    MAPS:     start = $C000, size = $1000, file = %O, fill = yes;
}}
SEGMENTS {{
    ZEROPAGE: load = ZP,       type = zp;
    LOADADDR: load = LOADADDR, type = ro;
    EXEHDR:   load = MAIN,     type = ro;
    CODE:     load = MAIN,     type = rw;
    AR1:      load = MAIN,     type = ro, optional = yes, align = $20;
    MUSIC:    load = MUSIC,    type = ro;
    ROWS0:    load = ROWS0,    type = rw;
    AR4:      load = AR4,      type = ro, optional = yes;
    AR3:      load = AR3,      type = ro, optional = yes;
    ROWS1:    load = ROWS1,    type = rw;
    TABLES:   load = TAB,      type = ro, align = $100;
    AR2:      load = AR2,      type = ro, optional = yes;
    ROUTA:    load = ROUTA,    type = ro, optional = yes;
    MAPS:     load = MAPS,     type = ro, align = $100;
}}
""")
    model = dict(bufs=bufs1 + bufs2, dis=dis1 + dis2, plat=PLAT, rate=RATE, col=COL, gh=GH, maps=MAPS)
    pickle.dump(model, open("/tmp/part1r_model.pkl", "wb"))
    late = sum(1 for s in stale if s)
    print(f"{PLAT}: {NN} frames ({NR} routine frames, {NN - NR} stream); routines {len(rids)} = {sum(sizes.values())} B; "
          f"arrays {len(arrays)} = {sum(len(a) for a in arrays)} B; pools {({k: v[2] + len(regs.get(k, b'')) for k, v in pools.items()})}; stream {len(banks)} banks "
          f"({sum(len(b) for b in banks)} B); clipped bars {clipped}; stale frames {late} of {len(stale)} (mean {sum(stale) / max(1, late):.1f} lines, max {max(stale) if stale else 0})")

if __name__ == "__main__":
    main()
