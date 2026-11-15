#!/usr/bin/env python3
"""Rows for vtest2.s: the tilted-bar row timing test (NTSC).  Writes vtest2_rows.inc.
Each row: 5 x (lda colK,y / sta $d021) at the segment edges, iny, the next row's segment 0 (lda / sta $d021,x in the right border),
the badline dodge (lda #Y / sta $d011), padding to the line: 65 cycles, or 65 - STEAL on the ship's sprite-DMA rows."""
import os
ROW0, NROWS, SPRY, STEAL = 70, 120, 120, 7
SR0 = int(os.environ.get("SR0", SPRY - ROW0))          # the first ship row (58 cycles): checked in VICE (SPRY - ROW0 - 1 or + 1: the band's rows jog by 7 cycles)
TILT = int(os.environ.get("TILT", 3))
L = []
def fill(n):
    assert n == 0 or n >= 2, n
    if n % 2: L.append("        bit $ea"); n -= 3
    L.extend(["        nop"] * (n // 2))
for r in range(NROWS):
    line = ROW0 + r
    ship = SR0 <= r < SR0 + 21
    L.append(f"r{r}:")
    for k in range(1, 6):
        L.append(f"        lda col + {TILT * k},y")
        L.append("        sta $d021")
    L.append("        iny")
    L.append("        lda col,y")
    L.append("        sta $d021,x")                   # 51
    wl = line + 1                                     # the row's dodge write lands in the next line (cycle ~13): Y for that line
    y = 0x18 + (((wl % 4) + 2) % 8)
    L.append(f"        lda #${y:02x}")
    if ship:
        L.append("        sta $d011,x")               # 58 = 65 - 7
    else:
        L.append("        sta $d011")                 # 57
        fill(65 - 57)
SEQ = [6, 14, 3, 1, 3, 14, 4, 2]
open("vtest2_col.inc", "w").write("".join(f"        .byte {SEQ[(i // 4) % 8]}\n" for i in range(256)))
open("vtest2_rows.inc", "w").write("\n".join(L) + "\n")
print("ship rows", SR0, "..", SR0 + 20, "tilt", TILT)
