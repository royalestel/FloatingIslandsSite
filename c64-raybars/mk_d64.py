#!/usr/bin/env python3
"""Write a .d64 disk image holding the given PRG files (standard 35-track, 683 sectors),
and read it back to check it.

    python3 mk_d64.py disk.d64 "DISKNAME" part1.prg=PART1 [more.prg=NAME ...]
"""
import sys

SPT = [21] * 17 + [19] * 7 + [18] * 6 + [17] * 5          # sectors per track, tracks 1-35
OFFS = [sum(SPT[:t]) for t in range(35)]

def off(t, s):
    return (OFFS[t - 1] + s) * 256

def build(files, name="DISK", did="01"):
    img = bytearray(683 * 256)
    free = {t: [True] * SPT[t - 1] for t in range(1, 36)}
    def take(t, s):
        free[t][s] = False
    for s in range(SPT[17]):                                # track 18: BAM + directory
        take(18, s)
    entries = []
    for fname, data in files:
        nblk = (len(data) + 253) // 254
        t, s, chain = 1, 0, []
        for _ in range(nblk):
            while t == 18 or not any(free[t]):
                t = t + 1 if t < 35 else 1
                s = 0
            while not free[t][s]:
                s = (s + 1) % SPT[t - 1]
            take(t, s)
            chain.append((t, s))
            s = (s + 10) % SPT[t - 1]
        for i, (tt, ss) in enumerate(chain):
            blk = data[i * 254:(i + 1) * 254]
            o = off(tt, ss)
            if i + 1 < len(chain):
                img[o], img[o + 1] = chain[i + 1]
            else:
                img[o], img[o + 1] = 0, len(blk) + 1
            img[o + 2:o + 2 + len(blk)] = blk
        entries.append((fname, chain[0], nblk))
    # BAM
    o = off(18, 0)
    img[o], img[o + 1], img[o + 2] = 18, 1, 0x41
    for t in range(1, 36):
        bits = 0
        for s in range(SPT[t - 1]):
            if free[t][s]:
                bits |= 1 << s
        n = sum(free[t])
        img[o + 4 * t:o + 4 * t + 4] = bytes([n, bits & 255, (bits >> 8) & 255, (bits >> 16) & 255])
    img[o + 0x90:o + 0xA0] = name.encode("ascii").upper().ljust(16, b"\xa0")[:16]
    img[o + 0xA0:o + 0xA2] = b"\xa0\xa0"
    img[o + 0xA2:o + 0xA4] = did.encode("ascii")
    img[o + 0xA4] = 0xA0
    img[o + 0xA5:o + 0xA7] = b"2A"
    img[o + 0xA7:o + 0xAB] = b"\xa0" * 4
    # directory
    d = off(18, 1)
    img[d], img[d + 1] = 0, 0xFF
    for i, (fname, (t, s), nblk) in enumerate(entries):
        e = d + 32 * i
        img[e + 2] = 0x82                                  # PRG, closed
        img[e + 3], img[e + 4] = t, s
        img[e + 5:e + 21] = fname.encode("ascii").upper().ljust(16, b"\xa0")[:16]
        img[e + 30], img[e + 31] = nblk & 255, nblk >> 8
    return bytes(img)

def read_back(img):
    """[(name, bytes)] following the directory and the sector chains."""
    out = []
    d = off(18, 1)
    for i in range(8):
        e = d + 32 * i
        if img[e + 2] != 0x82:
            continue
        name = bytes(img[e + 5:e + 21]).rstrip(b"\xa0").decode("ascii")
        t, s = img[e + 3], img[e + 4]
        data = bytearray()
        while True:
            o = off(t, s)
            nt, ns = img[o], img[o + 1]
            if nt == 0:
                data += img[o + 2:o + 2 + ns - 1]
                break
            data += img[o + 2:o + 256]
            t, s = nt, ns
        out.append((name, bytes(data)))
    return out

if __name__ == "__main__":
    path, dname, *args = sys.argv[1:]
    files = []
    for a in args:
        f, n = a.split("=")
        files.append((n, open(f, "rb").read()))
    img = build(files, dname)
    open(path, "wb").write(img)
    back = dict(read_back(img))
    ok = all(back[n] == data for n, data in files)
    free = sum(img[off(18, 0) + 4 * t] for t in range(1, 36) if t != 18)
    print(f"wrote {path}: {len(files)} file(s), {free} blocks free, read back identical: {ok}")
    sys.exit(0 if ok else 1)
