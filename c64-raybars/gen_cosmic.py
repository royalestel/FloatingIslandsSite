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
HMAX = 191                         # tallest bar (nearest 0.42 m)
HHELD = 10                         # h <= 10: beyond HOLD, blue 1/4 on/off
EXPOFF, EXPN = 256, 1400
R_BAR = sv.lv.R_BAR

def bar_lines(d):
    return lv.bar_lines(d)

# ROUND: every bar keeps its round glow profile at all distances: the
# colours fade along the glow ramp and the light dims smoothly all the way
# to FAR, so far away the centre is a dim blue pattern and the edges the
# dimmest, and the centre grows denser and brighter as the bar comes in
ROUND = False                      # (onebar_video.py turns it on: a preview)
DIM_FAR_R = 0.11

def fade_r(d):
    if d <= lv.REF + 0.25:
        return 1.0
    return 1.0 - (1.0 - lv.FADE_FAR) * min(1.0, (d - lv.REF - 0.25) / (sv.lv.FAR - lv.REF - 0.25))

def dim_r(d):
    if d <= sv.DIM_FROM:
        return 1.0
    return 1.0 - (1.0 - DIM_FAR_R) * min(1.0, (d - sv.DIM_FROM) / (sv.lv.FAR - sv.DIM_FROM))

# the ladder: swatches in brightness order along the glow's hues (black,
# the blue patterns, blue, purple, light blue, cyan, white)
LADDER = [0, 1, 2, 3, 5, 6, 8, 10, 14, 18, 19, 22, 25, 27, 28]

# extra swatches for the far, dim end (preview): single colours under the
# 1/4 inverting pattern -- purple (L* 12) and light blue (L* 17) fill the
# gaps between blue checker inverting (10.5) and purple checker inverting
# (19.1).  Appended, so the 29 keep their numbers (the tables have 32 slots).
def _extra():
    import swatches_video as sw
    pat = [f for n, _, f in sw.BLUE_PATTERNS if n == "1/4 inverting"][0]
    for c, name in ((4, "purple 1/4 inverting"), (14, "light blue 1/4 inverting")):
        if any(p[6] == name for p in sv.PAL):
            continue
        t = sw.patch(c, c, name, 0, lambda r, p, bp=False: pat(r, p))
        sv.PAL.append((c, c, pat, sw.blended(t[4]), sw.brightness(t[4]), 0, name))
    sv.COL = np.array([p[3] for p in sv.PAL])
    sv.LUM = np.array([p[4] for p in sv.PAL])
    sv.WIDE = np.array([p[5] for p in sv.PAL])
_extra()
P14, LB14 = [i for i, p in enumerate(sv.PAL) if p[6] in ("purple 1/4 inverting",
                                                         "light blue 1/4 inverting")]
LADDER_P = [0, 1, 2, 3, P14, LB14, 5, 6, 8, 10, 14, 18, 19, 22, 25, 27, 28]

def centre_first(rows):
    """Rows never brighter than the row nearer the centre: a new, brighter
    step appears in the middle of the bar first and spreads outward."""
    pos = {k: i for i, k in enumerate(LADDER)}
    p = [pos.get(k, 0) for k in rows]
    h = len(p)
    c0, c1 = (h - 1) // 2, h // 2          # the middle row(s)
    m = max(p[c0], p[c1])
    p[c0] = p[c1] = m
    for j in range(c0 - 1, -1, -1):
        p[j] = min(p[j], p[j + 1])
    for j in range(c1 + 1, h):
        p[j] = min(p[j], p[j - 1])
    # evenly both ways: a row takes a step only when its mirror row does
    p = [min(p[j], p[h - 1 - j]) for j in range(h)]
    return [LADDER[i] for i in p]

CONTRAST_FULL = 14.0               # full round profile from here in;
                                   # flat at FAR (low contrast far away)

def contrast(d):
    t = min(1.0, max(0.0, (sv.lv.FAR - d) / (sv.lv.FAR - CONTRAST_FULL)))
    return t * t * (3 - 2 * t)

def ramp_round(h, d):
    """A round bar h lines tall at distance d: each row's light on the
    ladder, ordered-dithered between its two nearest steps (Bayer by row).
    The light: the glow ramp's core, faded and dimmed for d, shaded across
    the bar by the round profile -- with less contrast far away, so at the
    very end the bar is one flat dim blue pattern."""
    fc, dm = fade_r(d), dim_r(d)
    c = contrast(d)
    lum = np.array([sv.LUM[k] for k in LADDER])
    core = float(fl.lin(gv.glow(fc)) @ sv.LW) * dm
    out = []
    for j in range(h):
        prof = float(fl.lin(gv.glow(fc * (1 - abs(2 * (j + 0.5) / h - 1)) ** 0.9)) @ sv.LW) * dm
        lt = core + c * (prof - core)
        i = int(np.searchsorted(lum, lt)) - 1
        if i >= len(LADDER) - 1:
            out.append(LADDER[-1])
            continue
        i = max(i, 0)
        f = (lt - lum[i]) / (lum[i + 1] - lum[i])
        out.append(LADDER[i + 1] if f > lv.BAYER4[j % 4] else LADDER[i])
    return centre_first(out)

def ramp_smooth(h, d):
    """ramp_round, smoother up close: all 29 swatches by brightness (the
    greys and grey mixes fill the gaps), and the error carried from the
    centre row outward, mirrored top and bottom, so the pattern stays put
    as the bar grows."""
    fc, dm = fade_r(d), dim_r(d)
    c = contrast(d)
    lum = np.array(sv.LUM)
    core = float(fl.lin(gv.glow(fc)) @ sv.LW) * dm
    def light(j):
        prof = float(fl.lin(gv.glow(fc * (1 - abs(2 * (j + 0.5) / h - 1)) ** 0.9)) @ sv.LW) * dm
        return core + c * (prof - core)
    half = (h + 1) // 2
    lower = []                             # rows from the centre down
    err = 0.0
    for i in range(half):
        j = h - half + i                   # centre row first (odd h: the middle)
        want = light(j) + err
        k = int(np.argmin(np.abs(lum - want)))
        lower.append(k)
        err = 0.8 * (want - lum[k])
    upper = lower[::-1] if h % 2 == 0 else lower[:0:-1]
    return upper + lower

# v3 (preview): brightness planned in perceptual terms.  The core's
# lightness (L*) rises in a straight line against log distance, from the
# dimmest pattern at FAR to white at the near clip -- so it keeps rising
# all the way in; contrast across the bar fades in from flat at FAR to the
# full round profile at CONTRAST_FULL; rows take the nearest ladder step
# with the error carried from the centre outward, mirrored (no Bayer, and
# the pattern stays put as the bar grows)
LSTAR_FAR, EDGE = 3.0, 0.012          # core L* at FAR; deep blue edge light
V3_CURVE = 0.6                        # < 1: brighter sooner, still rising to the end

def _lin(lstar):
    return ((lstar + 16) / 116) ** 3 if lstar > 8 else lstar * 27 / 24389

# the core's lightness at a few distances, straight lines between them
# against log distance: a gentle climb through the dim patterns far out,
# brighter by mid distance, white at the near clip
V3_ANCHORS = [(28.0, 3.0), (20.0, 19.0), (5.0, 60.0), (0.42, 100.0)]

def core_v3(d):
    ds, ls = zip(*V3_ANCHORS[::-1])
    return _lin(float(np.interp(np.log(d), np.log(ds), ls)))

def row_v3(d, r):
    """Target light of the row at r (-1 top .. 1 bottom) of a bar at d."""
    c = contrast(d)
    core = core_v3(d)
    shape = max(0.0, 1 - r * r) ** 1.2
    return core * ((1 - c) + c * shape) + c * min(core, EDGE) * (1 - shape)

def ramp_v3(h, d, ladder=None):
    LADDER_ = ladder or LADDER
    lum = np.array([sv.LUM[k] for k in LADDER_])
    half = (h + 1) // 2
    lower, err, kmax = [], 0.0, len(LADDER_) - 1
    for i in range(half):
        j = h - half + i
        want = row_v3(d, 2 * (j + 0.5) / h - 1) + err
        k = min(int(np.argmin(np.abs(lum - want))), kmax)   # never above the row inside
        kmax = k
        lower.append(LADDER_[k])
        err = 0.8 * (want - lum[k])
    upper = lower[::-1] if h % 2 == 0 else lower[:0:-1]
    return upper + lower

# ---- v6 (preview): every swatch we have, in order of linear light (the two
# frames' light averaged, as the eye sums a 50 Hz flicker).  The light is
# planned twice over: by distance (the core's L* through V6_ANCHORS, against
# log distance) and from the centre of the bar to its edge (the round
# profile, its contrast fading in from flat at FAR).  Each row takes the
# nearest swatch with the error carried from the centre outward, mirrored,
# never brighter than the row inside it -- so a new, brighter swatch starts
# on the centre line and spreads evenly.  White comes in through cyan / white.
V6_ANCHORS = [(28.0, 6.5), (20.0, 22.0), (5.0, 62.0), (0.42, 100.0)]

def lum_linear(k):
    import swatches_video as sw
    a, b, pat, *_ = sv.PAL[k]
    t = sw.patch(a, b, "", 0, lambda r, p, bp=False: pat(r, p))
    return float(np.mean([fl.lin(f) @ sv.LW for f in t[4]]))

LUMLIN = np.array([lum_linear(k) for k in range(len(sv.PAL))])
ALL_L = sorted(range(len(sv.PAL)), key=lambda k: LUMLIN[k])

def row_v6(d, r):
    global V3_ANCHORS
    keep, V3_ANCHORS = V3_ANCHORS, V6_ANCHORS
    try:
        return row_v3(d, r)
    finally:
        V3_ANCHORS = keep

def ramp_v6(h, d):
    lum = LUMLIN[ALL_L]
    half = (h + 1) // 2
    lower, err, lmax = [], 0.0, 9.0
    for i in range(half):
        j = h - half + i
        want = row_v6(d, 2 * (j + 0.5) / h - 1) + err
        cost = np.where(lum <= lmax + 1e-9, np.abs(lum - want), np.inf)
        k = int(np.argmin(cost))
        lower.append(ALL_L[k])
        lmax = lum[k]
        err = 0.8 * (want - lum[k])
    upper = lower[::-1] if h % 2 == 0 else lower[:0:-1]
    return upper + lower

def d_of_h(h):
    """The distance a bar h lines tall stands for (inverse of bar_lines)."""
    k = 2 * R_BAR * F
    if h >= k / lv.REF:
        return k / h
    return lv.REF * (k / lv.REF / h) ** (1 / lv.GROW)

def ramp(h):
    """Swatch indices of a bar h lines tall, top row first."""
    d = d_of_h(h)
    if not ROUND:
        if h <= HHELD:
            return [sv.HELD] * h
        fc, dm = sv.fade(d), sv.dimming(d)
    else:
        return ramp_round(h, d)
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
    """Pages of ramps, stored bottom row first, first fit from the tallest,
    at page offsets 1..255: [(page bytes, {h: offset})]."""
    pages = []
    for h in range(HMAX, 1, -1):
        for pg in pages:
            if pg[2] + h <= 256:
                break
        else:
            pg = [bytearray(256), {}, 1]
            pages.append(pg)
        pg[0][pg[2]:pg[2] + h] = bytes(ramp(h)[::-1])
        pg[1][h] = pg[2]
        pg[2] += h
    return [(bytes(b), offs) for b, offs, _ in pages]

def swatch_tables():
    """Two pages (frame parity p): colour by row parity (E: even mock row,
    O: odd) at +0 / +32, idle byte at +64 / +96."""
    pages = []
    for p in (0, 1):
        b = bytearray(256)
        for k, (a, bb, pat, *_r) in enumerate(sv.PAL):
            for r in (0, 1):
                whole = "whole lines" in sv.PAL[k][6]       # the same on every line
                b[32 * r + k] = (a if p == 0 else bb) if whole else (a if (r + p) % 2 == 0 else bb)
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
                  DFAR=round(sv.lv.FAR / DUNIT), DHELD=round(d_of_h(HHELD + 0.5) / DUNIT), HELDSW=sv.HELD, HMAX=HMAX, HHELD=HHELD)
    for k, v in consts.items():
        L.append(f"{k:8s} = {v}")
    L += ["", '.segment "RAMPS1"']
    split = 999                                # all in RAMPS1
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
    L += ['', '.segment "TABLES2"', '        .align 256']
    L += byte_lines("heldpg", bytes([sv.HELD]) * 256)
    ldmin = math.floor(128 * math.log2(consts["DNEAR"])) - 4
    ldmax = math.ceil(128 * math.log2(consts["DFAR"])) + 4
    ht = []
    for ld in range(ldmin, ldmax + 1):
        d = 2 ** (ld / 128) * DUNIT
        ht.append(max(2, min(HMAX, bar_lines(d))))
    L.append(f"LDMIN    = {ldmin}")
    L += byte_lines("htab", bytes(ht))
    rb = [0] * 256
    for h in range(2, HMAX + 1):
        rb[h] = ptr[h]
    L.append("rbl:")
    L += ["        .byte " + ",".join(f"<({ptr[h][0]}+{ptr[h][1]}+{h-1})" if h in ptr else "0"
                                     for h in range(i, i + 8)) for i in range(0, 256, 8)]
    L.append("rbh:")
    L += ["        .byte " + ",".join(f">({ptr[h][0]}+{ptr[h][1]}+{h-1})" if h in ptr else "0"
                                     for h in range(i, i + 8)) for i in range(0, 256, 8)]
    L += ['', '.segment "TABLES"']
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
