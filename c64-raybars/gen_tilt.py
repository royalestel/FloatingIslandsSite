#!/usr/bin/env python3
"""The tilted bars' row code for cosmicstrings (NTSC; SCROLLER_PLAN.md, "Tilted display design"): writes ctilt.inc.

Four copies (c = 2 * buffer + frame parity), each reading its own column page TCOLPG + c, indexed by window line (y) + MARG - off_k.
Per copy: loopN (4 phases, the end test), loopA (4 phases above the ship band, the band test on phase 0), the ship band (E, X, Y).
Shared: nine entry stubs (jmp (tvec + 2i)), the per-copy entry tables (copied into tvec by irqtop), the offset patch tables.

Cycles (row = one raster line, from cycle 21 of its line; vtest2.s):
  normal row: 5 x (lda col,y / sta $d021) = 40, iny, lda col,y / sta $d021,x (the next row's segment 0) = 51, dodge (lda # / sta) = 57
  loopN:  cpy src / bne + nop (63 + 2) or, the phase that wraps, cpy src / beq / jmp (62 + 3); equal: jmp texit
  loopA:  phase 0: cpy tb0v / bne (63) + nop; equal: jmp E (62 + 3); phases 1, 2: fill 8; phase 3: fill 5 + jmp
  band:   58 cycles (the VIC takes 7): segment 0 with sta $d021 (4): 50; E, X: + lda dodtab,y / sta $d011 = 58;
          Y: cpy tb1v / beq (55) + jmp X = 58; equal (56): nop -> loopN's first row (phase TB1 mod 4)
"""
WTOPR, TB0, TB1 = 62, 77, 98          # cosmic.inc: WTOPR, BAND0, BAND1
MARG = 8
TCOLPG = 0x8A
NCOPY = 4
L = []
def e(s): L.append(s)
def fill(n):
    assert n == 0 or n >= 2, n
    if n % 2: e("        bit $ea"); n -= 3
    for _ in range(n // 2): e("        nop")
def dod(w):
    """the dodge value written in the row for window line w: it lands in line w + 1 (cycle ~13): Y for that raster line"""
    M = WTOPR + w + 1
    return 0x18 + (((M % 4) + 2) % 8)
patch = {c: {k: [] for k in range(6)} for c in range(NCOPY)}
def stores(c, tag, band=False):
    page = TCOLPG + c
    for k in (1, 2, 3, 4, 5):
        lab = f"{tag}_o{k}"
        e(f"{lab} := * + 1"); patch[c][k].append(lab)
        e(f"        lda ${page:02x}00 + {MARG},y")
        e("        sta $d021")
    e("        iny")
    lab = f"{tag}_o0"
    e(f"{lab} := * + 1"); patch[c][0].append(lab)
    e(f"        lda ${page:02x}00 + {MARG},y")
    e("        sta $d021" if band else "        sta $d021,x")
assert (TB0 - 1) % 4 == 0, "the row above the ship band must be phase 0 (loopA's test)"
NFIRST = TB1 % 4                      # loopN starts with the phase the band hands on to
for c in range(NCOPY):
    e(f"; ---- copy {c}: buffer {c // 2}, frame parity {c % 2}, column page ${TCOLPG + c:02x}00")
    e(f"tcopy_{c}:")
    # the band: E, X, Y, then loopN (rotated: its first row is phase NFIRST)
    e(f"tE_{c}:")
    stores(c, f"tE_{c}", band=True)
    e("        lda dodtab,y"); e("        sta $d011")
    e(f"tX_{c}:")
    stores(c, f"tX_{c}", band=True)
    e("        lda dodtab,y"); e("        sta $d011")
    e(f"tY_{c}:")
    stores(c, f"tY_{c}", band=True)
    e("        cpy tb1v")
    e(f"        beqnear tYb_{c}")
    e(f"        jmp tX_{c}")
    e(f"tYb_{c}: nop")
    order = [(NFIRST + i) % 4 for i in range(4)]
    for i, m in enumerate(order):
        tag = f"tN_{c}_{m}"
        e(f"{tag}:")
        stores(c, tag)
        e(f"        lda #${dod(m):02x}           ; (phase {m}: window line mod 4)")
        e("        sta $d011")
        e("        cpy src")
        if i < 3:
            e(f"        bnenear {tag}_c")
            e("        jmp texit")
            e(f"{tag}_c: nop")
        else:
            e(f"        beqnear {tag}_x")
            e(f"        jmp tN_{c}_{order[0]}")
            e(f"{tag}_x: jmp texit")
    for m in (0, 1, 2, 3):
        tag = f"tA_{c}_{m}"
        e(f"{tag}:")
        stores(c, tag)
        e(f"        lda #${dod(m):02x}")
        e("        sta $d011")
        if m == 0:
            e("        cpy tb0v")
            e(f"        bnenear {tag}_c")
            e(f"        jmp tE_{c}")
            e(f"{tag}_c: nop")
        elif m < 3:
            fill(8)
        else:
            fill(5)
            e(f"        jmp tA_{c}_0")
# the entries, by entry i (loopN phases 0..3, loopA phases 0..3, the band), the four copies' side by side: stub i jumps through
# (tent + 8i + 2c); irqtop patches the stubs' low bytes for c = 2 * buffer + parity
e("        .align 256")
e("tent:")
for i in range(9):
    names = [f"tN_{c}_{i}" if i < 4 else (f"tA_{c}_{i - 4}" if i < 8 else f"tE_{c}") for c in range(NCOPY)]
    e("        .word " + ", ".join(names))
# the offset patch addresses: relative to the copy's start (the copies have the same layout), per segment
e("tcopyl: .byte " + ", ".join(f"<tcopy_{c}" for c in range(NCOPY)))
e("tcopyh: .byte " + ", ".join(f">tcopy_{c}" for c in range(NCOPY)))
e("trell:")
for k in range(6):
    e("        .byte " + ", ".join(f"<({a} - tcopy_0)" for a in patch[0][k]))
e("trelh:")
for k in range(6):
    e("        .byte " + ", ".join(f">({a} - tcopy_0)" for a in patch[0][k]))
for c in range(1, NCOPY):
    for k in range(6):
        for a0, ac in zip(patch[0][k], patch[c][k]):
            e(f"        .assert {ac} - tcopy_{c} = {a0} - tcopy_0, error, \"the copies differ\"")
# segment offsets by roll (0..8, 4 level): off_k = round((k - 2.5) * t), t = (roll - 4) * 0.75 lines a segment; stored MARG - off
import math
e("toff:")
for r in range(9):
    t = (r - 4) * 0.75
    offs = [int(math.floor((k - 2.5) * t + 0.5)) for k in range(6)]
    assert all(abs(o) <= MARG for o in offs)
    e("        .byte " + ", ".join(str(MARG - o) for o in offs) + f"     ; roll {r}: {offs}")
NP = len(patch[0][0])
e(f"TNPATCH = {NP}                ; patch addresses per segment per copy")
open("ctilt.inc", "w").write("\n".join(L) + "\n")
print("ctilt.inc:", len(L), "lines,", NP, "patch addresses per segment per copy")
