#!/usr/bin/env python3
"""Tables for cosmicstrings.s (COSMIC STRINGS on the C64): writes
cosmic.inc.

* Ramps: for every bar height h = 2..255 lines, the swatch index of each of
  its rows (swatch_loop_video's colours: the 29 swatches, the glow ramp
  faded and dimmed for the distance that height means, nearest swatch with
  error diffusion on small bars, Bayer dither on big ones, all blue 1/4
  on/off at h <= 10).  Stored bottom row first, two ramps a page (h and
  255 - h at page offsets 1..255) so the display's lda (src),y never
  crosses a page.
* Swatch tables: colour and idle byte per swatch, by row parity and frame
  parity.
* World: 256 bar heights; quarter sine; rows to visit per view angle.
* Maths: log2 mantissa and exp tables (1/128 octave).
* The ship: 9 pitches x 2 frames x 2 sprites (big_ship.py).

    python3 gen_cosmic.py
"""
import math
import numpy as np
import flicker as fl
import glow_video as gv
import loop_video as lv
import swatch_loop_video as sv
import big_ship, ship_aa

OUT = "cosmic.inc"
UNIT = 1 / 16                      # world unit, metres
ROWSP = 22                         # rows of bars every 22 units (1.375 m)
DUNIT = 1 / 4096                   # depth / height after rotation, metres
F = 200
WTOPR, NLINES = 62, 189            # bar window: raster lines 62..250
CYL = 88                           # screen centre, window line (row 99)
SPRY = 139                         # ship sprites: display rows 140..160
BAND0, BAND1 = SPRY - WTOPR, SPRY - WTOPR + 21   # window lines with sprite DMA
HMAX = 255
HHELD = 10                         # h <= 10: beyond HOLD, blue 1/4 on/off
EXPOFF, EXPN = 256, 1400
R_BAR = sv.lv.R_BAR

def bar_lines(d):
    return lv.bar_lines(d)

def d_of_h(h):
    """The distance a bar h lines tall stands for (inverse of bar_lines)."""
    k = 2 * R_BAR * F
    if h >= k / lv.REF:
        return k / h
    return lv.REF * (k / lv.REF / h) ** (1 / lv.GROW)

def ramp(h):
    """Swatch indices of a bar h lines tall, top row first."""
    d = d_of_h(h)
    if h <= HHELD:
        return [sv.HELD] * h
    fc, dm = sv.fade(d), sv.dimming(d)
    tgt = np.array([fl.lin(gv.glow(fc * (1 - abs(2 * (j + 0.5) / h - 1)) ** 0.9)) * dm
                    for j in range(h)])
    big = h >= lv.BIG
    out, err = [], np.zeros(3)
    ok = sv.WIDE <= (2 if big else 1)
    for j in range(h):
        if big:
            t = np.clip(tgt[j], 0, 1)
            cost = np.where(ok, sv.il.redmean(sv.COL, fl.srgb(t)), np.inf)
            near = np.argsort(cost)[:6]
            lt = float(t @ sv.LW)
            lo = [k for k in near if sv.LUM[k] <= lt and ok[k]]
            hi = [k for k in near if sv.LUM[k] >= lt and ok[k]]
            if not lo or not hi:
                out.append(int(near[0]))
                continue
            kl = max(lo, key=lambda k: (sv.LUM[k], -cost[k]))
            kh = min(hi, key=lambda k: (sv.LUM[k], cost[k]))
            f = 0 if sv.LUM[kh] - sv.LUM[kl] < 1e-6 else (lt - sv.LUM[kl]) / (sv.LUM[kh] - sv.LUM[kl])
            out.append(int(kh if f > lv.BAYER4[j % 4] else kl))
            continue
        want = np.clip(tgt[j] + 0.7 * err, 0, 1)
        cost = np.where(ok, sv.il.redmean(sv.COL, fl.srgb(want)), np.inf)
        k = int(np.argmin(cost))
        out.append(k)
        err = np.clip(want - fl.lin(sv.COL[k]), -0.05, 0.05)
    return out

def pack_ramps():
    """Pages of ramps, stored bottom row first: [(page bytes, {h: offset})]."""
    pages = []
    for h in range(2, 128):
        pages.append((h, 255 - h))
    pages += [(254,), (255,)]
    out = []
    for hs in pages:
        b = bytearray(256)
        offs, o = {}, 1
        for h in hs:
            r = ramp(h)[::-1]
            b[o:o + h] = bytes(r)
            offs[h] = o
            o += h
        assert o <= 256
        out.append((bytes(b), offs))
    return out

def swatch_tables():
    """Two pages (frame parity p): colour by row parity (E: even mock row,
    O: odd) at +0 / +32, idle byte at +64 / +96."""
    pages = []
    for p in (0, 1):
        b = bytearray(256)
        for k, (a, bb, pat, *_r) in enumerate(sv.PAL):
            for r in (0, 1):
                b[32 * r + k] = a if (r + p) % 2 == 0 else bb
                b[64 + 32 * r + k] = pat(r, p) & 255
        pages.append(bytes(b))
    return pages

# ---- maths ------------------------------------------------------------------
def LMF(m):
    return min(128, round(128 * math.log2(1 + (m + 0.5) / 256)))

def LG(x):
    """The C64's log: 128 * log2(x) from the top 9 bits (x >= 1)."""
    x = int(x)
    if x <= 0:
        return 0
    pos = x.bit_length() - 1
    m = ((x << 8) >> pos) & 255 if pos < 8 else (x >> (pos - 8)) & 255
    return pos * 128 + LMF(m)

def EXPT(i):
    return min(65535, round(2 ** ((i - EXPOFF) / 128)))

def quarter_sine():
    return [min(255, round(256 * math.sin(i / 1024 * math.pi / 2))) for i in range(1025)]

def row_ranges():
    """Per view angle (angle's high byte): first row offset from the camera's
    row and the number of rows to visit, covering the view cone (with each
    bar's half height) out to FAR, from the near clip."""
    kmin, nrow = [], []
    for a in range(256):
        zs = []
        for sub in np.linspace(0, 1, 9):
            phi = (a + sub) / 256 * 2 * math.pi
            s, c = math.sin(phi), math.cos(phi)
            for d in np.linspace(0.25, sv.lv.FAR, 120):
                h = min(HMAX, bar_lines(d))
                um = (100 + h / 2 + 4) / F * d
                for u in (-um, um):
                    zs.append(d * c - u * s)
        zmin, zmax = min(zs), max(zs)
        sp = ROWSP * UNIT
        k0 = math.floor(zmin / sp) - 1
        k1 = math.ceil(zmax / sp) + 1
        kmin.append(k0 & 255)
        nrow.append(k1 - k0 + 1)
    return kmin, nrow

def sprites():
    """36 blocks: pitch * 4 + frame * 2 + side (left, right)."""
    out = bytearray()
    for pi in range(9):
        fr = big_ship.pair(0, ship_aa.PITCHES[pi])
        for f in fr:
            for side in (0, 1):
                blk = bytearray(64)
                for r in range(21):
                    bits = 0
                    for c in range(12):
                        bits = bits << 2 | int(f[r, side * 12 + c])
                    blk[3 * r:3 * r + 3] = bits.to_bytes(3, "big")
                out += blk
    return bytes(out)

def byte_lines(name, data, per=16):
    out = [f"{name}:"] if name else []
    for i in range(0, len(data), per):
        out.append("        .byte " + ",".join(f"${b:02x}" for b in data[i:i + per]))
    return out

def main():
    rng = np.random.default_rng(21)
    hy = bytes(int(v) for v in rng.integers(0, 256, 256))
    pages = pack_ramps()
    L = ["; generated by gen_cosmic.py -- do not edit", ""]
    D3 = round(3 / DUNIT)
    consts = dict(WTOPR=WTOPR, NLINES=NLINES, CYL2=2 * CYL, SPRY=SPRY, BAND0=BAND0,
                  BAND1=BAND1, ROWSP=ROWSP, EXPOFF=EXPOFF, EXPN=EXPN, NSW=len(sv.PAL),
                  LG400=round(128 * math.log2(2 * F)),
                  LGHN=round(128 * math.log2(2 * R_BAR * F / DUNIT)),
                  LGHF=round(128 * math.log2(2 * R_BAR * F / lv.REF)),
                  LG3=round(128 * math.log2(D3)), D3=D3,
                  DNEAR=math.ceil(2 * R_BAR * F / (HMAX + 0.45) / DUNIT),
                  DFAR=round(sv.lv.FAR / DUNIT), HELDSW=sv.HELD)
    for k, v in consts.items():
        L.append(f"{k:8s} = {v}")
    L += ["", '.segment "RAMPS1"']
    split = 107                                # pages in RAMPS1 ($1500-$7fff)
    ptr = {}
    for i, (b, offs) in enumerate(pages):
        if i == split:
            L += ['', '.segment "RAMPS2"']
        lab = f"rpage{i}"
        L += byte_lines(lab, b)
        for h, o in offs.items():
            ptr[h] = (lab, o)
    L += ['', '.segment "TABLES"', '        .align 256']
    L += byte_lines("zeros", bytes(256))
    swt = swatch_tables()
    L += byte_lines("swtab", swt[0] + swt[1])
    L.append("rampl:")
    L += ["        .byte " + ",".join(f"<({ptr[h][0]}+{ptr[h][1]})" if h in ptr else "0"
                                     for h in range(i, i + 8)) for i in range(0, 256, 8)]
    L.append("ramph:")
    L += ["        .byte " + ",".join(f">({ptr[h][0]}+{ptr[h][1]})" if h in ptr else "0"
                                     for h in range(i, i + 8)) for i in range(0, 256, 8)]
    L += byte_lines("hy", hy)
    L += byte_lines("lmf", bytes(LMF(m) for m in range(256)))
    kmin, nrow = row_ranges()
    L += byte_lines("kmin", bytes(kmin))
    L += byte_lines("nrow", bytes(nrow))
    qs = quarter_sine()
    L += byte_lines("sinq", bytes(qs))
    L += ['        .align 256']
    ex = [EXPT(i) for i in range(EXPN)]
    L += byte_lines("expl", bytes(v & 255 for v in ex))
    L += ['        .align 256']
    L += byte_lines("exph", bytes(v >> 8 for v in ex))
    L += ['', '.segment "SPRITES"']
    L += byte_lines("shipspr", sprites())
    open(OUT, "w").write("\n".join(L) + "\n")
    print("wrote", OUT, "max rows", max(nrow), "ramp pages", len(pages))

if __name__ == "__main__":
    main()
