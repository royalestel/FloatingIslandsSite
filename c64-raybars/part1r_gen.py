#!/usr/bin/env python3
"""Part 1 for the C64, one design for NTSC (60 Hz, film time 5n/6) and PAL (50 Hz, film time n):

  1a-1c (film time < 1240): per frame a 7-byte record [dim level][(routine, x) x 3] in ROM banks; each bar is drawn by an
        UNROLLED ROUTINE per (thickness, start-line parity): lda #index / sta buf+i,x with the swatch indices baked in.
  1d    (film time >= 1240): the delta stream (runs of changed buffer rows copied from shape arrays), as part1n.
  dimming = a 128-byte MAP per dim level, applied in the raster rows (ldy buf / lda (dm),y / tax), one pointer per frame.
  The rotation of the stack is eased flatter (half linear, half smoothstep).

    PLATFORM=NTSC python3 part1r_gen.py     (or PAL)  ->  part1r.inc, part1r.cfg, part1r_rout.s, part1r_data.s, part1r_str.bin,
                                                          /tmp/part1r_model.pkl  (the frames as the C64 shows them)
"""
import os, math, pickle
import part1 as p1
import part1_proc as q
import part1p_gen as g
import preview_v10 as v10

PLAT = os.environ.get("PLATFORM", "NTSC")
NTSC = PLAT == "NTSC"
RATE = 5 / 6 if NTSC else 1.0
H, PAD, LBW = 200, 63, 0x0500
BUDGET = 3800 if NTSC else 6500
T_SPLIT = 1240                                   # film time where the routines end and the delta stream starts
NN = int((p1.T_END - 1) / RATE) + 1
NR = int(math.ceil(T_SPLIT / RATE))
tau = lambda n: n * RATE

# ---- the flatter rotation ------------------------------------------------------------
def my_stack(t):
    lin = min(max((t - p1.T_ROT0) / float(p1.T_ROT1 - p1.T_ROT0), 0.0), 1.0)
    p = 0.5 * lin + 0.5 * p1.smooth(lin)
    alpha = math.pi / 2 * p
    s = p1.S0 + (p1.S1 - p1.S0) * p
    yp = p1.YP0 + (p1.YP1 - p1.YP0) * p
    zp = p1.Z0 + (p1.ZP1 - p1.Z0) * p
    y0 = H / 2 + (p1.HORIZON - H / 2) * p
    out = []
    for m in range(p1.NSTACK):
        y = yp + m * s * math.cos(alpha)
        z = zp + m * s * math.sin(alpha)
        yc = y0 - p1.F * y / z
        w = p1.smooth((p - 0.6) / 0.4)
        yc = (1 - w) * yc + w * p1.floor_yc(z)
        d = math.hypot(z, y * p)
        if m < 3:
            yc += 260 * (1 - p1.smooth((t - p1.T_NEWB[2 - m]) / p1.NEW_LEN))
        elif m > 5:
            yc -= 600 * (1 - p1.smooth((t - p1.T_TOPB) / (p1.NEW_LEN + 10)))
        out.append((d, yc, d, m, p))
    return out
p1.stack = my_stack

# ---- dim maps: buffer value b = level | centre<<5 | parity<<6  ->  swatch index (level' | parity<<5) --------------
def dimmap(di):
    out = []
    for b in range(128):
        lvl, c, p = b & 31, (b >> 5) & 1, (b >> 6) & 1
        out.append(0 if lvl == 0 else q.DIMT[di][c][lvl] + 32 * p)
    return out
MAPS = [dimmap(di) for di in range(32)]
assert max(max(m) for m in MAPS) < 64

def dim_at(t):
    ti = int(round(t))
    return q.DX[ti - q.DIM0] if q.DIM0 <= ti < q.DIM0 + q.DIMN else 0

# ---- section 1: routines ----------------------------------------------------------------
rids = {}                                        # (T, parity) -> routine id
def rid_of(T, p):
    if (T, p) not in rids: rids[(T, p)] = len(rids)
    return rids[(T, p)]
def shape(T, p):
    return [(f & 31) | (((f >> 5) & 1) << 5) | (p << 6) for f in q.FULL[T]]

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

# ---- section 2: the delta stream (as part1n_gen) --------------------------------------------
def frame_bars2(n):
    t = tau(n); out = []
    for y0, T in p1.frame_list(t):
        if t < p1.T_STACK: base = [f & 31 for f in q.FULL[T]]
        else: base = list(p1.gp.PROF[T])
        out.append((y0, T, base))
    return out

def section2(prev):
    prof, off = bytearray(), {}
    def intern(a):
        k = bytes(a)
        if k not in off: off[k] = ("arr", len(off)); prof.extend(k)
        return k
    ZERO = bytes(H)
    runs_all, bufs, stale = [], [], []
    for n in range(NR, NN):
        buf, own = [0] * H, [None] * H
        for y0, T, base in frame_bars2(n):
            arr = bytes((k + 64 * (y0 & 1)) if k else 0 for k in base)
            for i, k in enumerate(arr):
                y = y0 + i
                if 0 <= y < H and k: buf[y] = k; own[y] = (arr, i)
        runs, y = [], 0
        while y < H:
            if buf[y] == prev[y]: y += 1; continue
            if own[y] is None:
                y1 = y
                while y1 < H and own[y1] is None and buf[y1] != prev[y1]: y1 += 1
                for s0 in range(y, y1, 128): runs.append((ZERO, 0, s0, min(y1, s0 + 128) - s0))
            else:
                arr, i0 = own[y]; y1 = y
                while (y1 < H and own[y1] is not None and own[y1][0] is arr and own[y1][1] == i0 + (y1 - y)
                       and buf[y1] != prev[y1] and y1 - y < 128): y1 += 1
                runs.append((arr, i0, y, y1 - y))
            y = y1
        chosen, used, state = [], 150, list(prev)
        for r in sorted(runs, key=lambda r: -r[3]):
            c = 14 * r[3] + 75
            if used + c <= BUDGET:
                chosen.append(r); used += c
                arr, i0, y, n_ = r; state[y:y + n_] = list(arr[i0:i0 + n_])
        chosen.sort(key=lambda r: r[2])
        stale.append(sum(state[y] != buf[y] for y in range(H)))
        runs_all.append(chosen); bufs.append(state); prev = state
        for arr, i0, y, n_ in chosen: intern(arr)
    return runs_all, bufs, stale

def main():
    recs, bufs1, dis, clipped = section1()
    runs_all, bufs2, stale = section2(bufs1[-1])
    arrays = {}
    for runs in runs_all:
        for arr, i0, y, n_ in runs: arrays[arr] = 1
    ar1_base = 0x1400
    if os.path.exists("part1r.lbl"):                     # the code's end from the last build: AR1 fills the rest of $0801-$1DFF
        lbl = {l.split()[2].lstrip("."): int(l.split()[1], 16) for l in open("part1r.lbl")}
        if "codeend" in lbl: ar1_base = (lbl["codeend"] + 0x1F) & ~0x1F
    # --- memory layout: routines in $8000-$BFFF (RAM under the cartridge window), arrays in $1000-$1DFF + $4400-$7FFF, maps $C000+
    sizes = {}
    for (T, p), r in rids.items():
        sh = shape(T, p)
        sizes[r] = 1 + sum(5 if i == 0 or v != sh[i - 1] else 3 for i, v in enumerate(sh))
    pools = {"ROUTA": [0x8000, 0x4000 - 0x200, 0], "AR1": [ar1_base, 0x1E00 - ar1_base, 0], "AR3": [0x3200, 0x0DFF, 0], "AR2": [0x5200, 0x2E00, 0]}   # base, size, used
    seg_of = {}
    for r in sorted(sizes):                                  # routines: ROUTA first, then AR2
        for k in ("ROUTA", "AR2"):
            if pools[k][2] + sizes[r] <= pools[k][1]:
                seg_of[r] = k; pools[k][2] += sizes[r]; break
        else: raise SystemExit("routines do not fit")
    regs = {k: bytearray() for k in ("AR1", "AR3", "AR2")}
    addr = {}
    for a_ in sorted(arrays, key=len, reverse=True):         # arrays: AR1, then what is left of AR2 (they follow that pool's routines)
        for k in ("AR1", "AR3", "AR2"):
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
    for runs in runs_all:
        assert len(runs) < 250
        r = bytearray([len(runs)])
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
        f.write('.segment "MAPS"\n.export dmlo, dmhi, map0\n.align 128\n')
        for di in range(32):
            f.write(f"map{di}:\n" + "".join("        .byte " + ",".join(str(v) for v in MAPS[di][i:i + 32]) + "\n" for i in range(0, 128, 32)))
        f.write('.segment "ROUTA"\n')
        f.write("dmlo:\n        .byte " + ",".join(f"<map{di}" for di in range(32)) + "\n")
        f.write("dmhi:\n        .byte " + ",".join(f">map{di}" for di in range(32)) + "\n")
    col, gh = g.swatch_tables()
    with open("part1r.inc", "w") as f:
        f.write("; generated by part1r_gen.py -- do not edit\n")
        if NTSC: f.write("NTSC = 1\n")
        f.write(f"NF = {NN}\nNR = {NR}\nIMGBANKS = 4\nPAD = {PAD}\nLBW = ${LBW:04x}\n")
        for name, tabs in (("colt", col), ("ght", gh)):
            f.write(f".macro {name.upper()}\n")
            for t_ in tabs: f.write("        .byte " + ",".join(str(v & 255) for v in t_) + "\n")
            f.write(".endmacro\n")
    open("part1r.cfg", "w").write(f"""# generated by part1r_gen.py
MEMORY {{
    ZP:       start = $0002, size = $00FE, type = rw;
    LOADADDR: start = $07FF, size = $0002, file = %O;
    MAIN:     start = $0801, size = $15FF, file = %O, fill = yes;
    TAB:      start = $1E00, size = $0200, file = %O, fill = yes;
    ROWS0:    start = $2000, size = $1200, file = %O, fill = yes;
    AR3:      start = $3200, size = $0E00, file = %O, fill = yes;   # ($3FFF = the idle byte: the pool stops one byte short)
    ROWS1:    start = $4000, size = $1200, file = %O, fill = yes;
    AR2:      start = $5200, size = $2E00, file = %O, fill = yes;
    ROUTA:    start = $8000, size = $4000, file = %O, fill = yes;
    MAPS:     start = $C000, size = $1000, file = %O, fill = yes;
}}
SEGMENTS {{
    ZEROPAGE: load = ZP,       type = zp;
    LOADADDR: load = LOADADDR, type = ro;
    EXEHDR:   load = MAIN,     type = ro;
    CODE:     load = MAIN,     type = rw;
    AR1:      load = MAIN,     type = ro, optional = yes, align = $20;
    TABLES:   load = TAB,      type = ro, align = $100;
    ROWS0:    load = ROWS0,    type = rw;
    AR3:      load = AR3,      type = ro, optional = yes;
    ROWS1:    load = ROWS1,    type = rw;
    AR2:      load = AR2,      type = ro, optional = yes;
    ROUTA:    load = ROUTA,    type = ro, optional = yes;
    MAPS:     load = MAPS,     type = ro, align = $80;
}}
""")
    model = dict(bufs=bufs1 + bufs2, dis=dis + [0] * (NN - NR), plat=PLAT, rate=RATE)
    pickle.dump(model, open("/tmp/part1r_model.pkl", "wb"))
    late = sum(1 for s in stale if s)
    print(f"{PLAT}: {NN} frames ({NR} routine frames, {NN - NR} delta); routines {len(rids)} = {sum(sizes.values())} B; "
          f"arrays {len(arrays)} = {sum(len(a) for a in arrays)} B; pools {({k: v[2] for k, v in pools.items()})}; stream {len(banks)} banks; clipped bars {clipped}; "
          f"stale frames {late} (max {max(stale) if stale else 0} lines)")

if __name__ == "__main__":
    main()
