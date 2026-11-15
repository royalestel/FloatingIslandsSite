#!/usr/bin/env python3
"""cosmicstrings' ship at 81 attitudes (ship_aa's grid: 9 rolls -25..25 x 9 pitches -30..30), each big_ship.pair: two frames shown
on alternate frames, each two sprites side by side.  Angle a = roll * 9 + pitch, 256 bytes: frame * 128 + side * 64 (a sprite block).
Stored in the cartridge's ROML halves from bank SHIP81BANK, 32 angles a bank: ship81.bin (20736 bytes), streamed into the sprite
slots at run time (cosmicstrings.s: shipcopy).   python3 gen_ship81.py [preview.png]"""
import sys
import numpy as np
import big_ship, ship_aa

def block(f, side):
    blk = bytearray(64)
    for r in range(21):
        bits = 0
        for c in range(12):
            bits = bits << 2 | int(f[r, side * 12 + c])
        blk[3 * r:3 * r + 3] = bits.to_bytes(3, "big")
    return blk

def frames():
    return [big_ship.pair(r, p) for r in ship_aa.ROLLS for p in ship_aa.PITCHES]

def data():
    out = bytearray()
    for fr in frames():
        for f in fr:
            for side in (0, 1):
                out += block(f, side)
    assert len(out) == 81 * 256
    return bytes(out)

if __name__ == "__main__":
    d = data()
    open("ship81.bin", "wb").write(d)
    print("wrote ship81.bin", len(d))
    if len(sys.argv) > 1:
        from PIL import Image
        pal = np.array([(0, 0, 0), (0x8A, 0x46, 0xAE), (0x7C, 0x70, 0xDA), (0xFF, 0xFF, 0xFF)], np.uint8)
        S = 3
        img = np.zeros((9 * 25, 9 * 52, 3), np.uint8)
        for i, fr in enumerate(frames()):
            ri, pi = divmod(i, 9)
            a = (pal[fr[0]].astype(int) + pal[fr[1]].astype(int)) // 2            # the two frames as the eye blends them
            a = np.repeat(a, 2, axis=1).astype(np.uint8)                             # multicolour pixels are 2 wide
            img[pi * 25 + 2:pi * 25 + 23, ri * 52 + 2:ri * 52 + 50] = a
        Image.fromarray(img).resize((img.shape[1] * S, img.shape[0] * S), Image.NEAREST).save(sys.argv[1])
        print("wrote", sys.argv[1], "(columns: roll -25..25, rows: pitch -30..30)")
