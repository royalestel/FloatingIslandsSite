#!/usr/bin/env python3
"""NTSC pitch for Alpha.sid (LukHash): the tune's note table is tuned for the PAL SID clock (985248 Hz).  On an NTSC C64
(1022727 Hz) every note plays 3.8 % (65 cents) sharp.  This rewrites the 16-bit frequency table (hi bytes $1714.., lo bytes $177c..,
95 notes, read as lda $1713,y / lda $177b,y) in place, scaled by 985248/1022727: music/Alpha.dat -> music/Alpha_ntsc.dat.
The music files are not in the repository (.gitignore): run this once next to music/Alpha.dat (it is also run by mk_cart_all.py / c64build.py).
    python3 music_ntsc_patch.py"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC, DST = os.path.join(HERE, "music", "Alpha.dat"), os.path.join(HERE, "music", "Alpha_ntsc.dat")
BASE, HI, LO, N = 0x1000, 0x1714, 0x177c, 95
PAL, NTSC = 985248.0, 1022727.0

def patch(d):
    d = bytearray(d)
    for i in range(N):
        f = d[HI - BASE + i] * 256 + d[LO - BASE + i]
        g = min(0xFFFF, int(round(f * PAL / NTSC)))
        d[HI - BASE + i], d[LO - BASE + i] = g >> 8, g & 255
    return bytes(d)

def ensure():
    """build music/Alpha_ntsc.dat if it is missing or older than Alpha.dat (no-op without Alpha.dat)"""
    if not os.path.exists(SRC): return False
    if os.path.exists(DST) and os.path.getmtime(DST) >= os.path.getmtime(SRC): return True
    open(DST, "wb").write(patch(open(SRC, "rb").read()))
    return True

if __name__ == "__main__":
    src = open(SRC, "rb").read()
    new = patch(src)
    f = lambda d, i: d[HI - BASE + i] * 256 + d[LO - BASE + i]
    print("A-4 (note 57): PAL table %d = %.2f Hz at PAL clock; patched %d = %.2f Hz at NTSC clock" %
          (f(src, 57), f(src, 57) * PAL / 16777216, f(new, 57), f(new, 57) * NTSC / 16777216))
    assert all(1.045 < f(new, i + 1) / f(new, i) < 1.07 for i in range(8, N - 2)), "table no longer a clean semitone ladder"
    open(DST, "wb").write(new)
    print("wrote", DST)
