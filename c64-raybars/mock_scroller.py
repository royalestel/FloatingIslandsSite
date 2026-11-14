#!/usr/bin/env python3
"""Mockup (Python, not the 6502 code): cosmicstrings' flight with goldship's ship and tilting bar segments, and a scroller in the
Xenon font (xenon_font.asm, 2x2 multicolour tiles) in the black band at the bottom (raster lines 212..250).

* The flight: cosmicstrings' world (a row of bars every 22 units along z, heights hy from cosmic.inc, a 256-unit slab that repeats), its
  autopilot (17 headings, 10 rows ahead, APSAFE 28) and its teardrop loop (ratetab: the pull-up rate by pitch angle).  The scene is
  rebuilt every 4 frames, as the C64 build runs at ~15 updates a second.
* goldship: its 162 ship frames (shipfr.inc: 9 rolls x 9 pitches, a pair each, alternating every frame), picked by the roll and the
  pitch rate; its six bar segments (split at sprite x 56, 120, 184, 248, 312) offset by its roll tilts (ship.inc rtilt0..5).  The roll
  follows a schedule (left, level, right), easing one step every other frame as goldship's pilot does.
* The bars' colours are an approximation (a glow ramp by distance), not the C64's flicker swatches.

    python3 mock_scroller.py [out.mp4] [seconds]
"""
import math, re, subprocess, sys
import numpy as np

OUT = sys.argv[1] if len(sys.argv) > 1 else "mock_scroller.mp4"
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 20
NF = int(SECS * 60)

PAL = [0x000000, 0xFFFFFF, 0x894036, 0x7ABFC7, 0x8A46AE, 0x68A941, 0x3E31A2, 0xD0DC71, 0x905F25, 0x5C4700, 0xBB776D,
       0x555555, 0x808080, 0xACEA88, 0x7C70DA, 0xABABAB]
RGB = np.array([((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in PAL], np.uint8)

def bytes_of(src, start, stop=None):
    i = src.index(start)
    j = src.index(stop, i) if stop else len(src)
    return [int(v, 16) for v in re.findall(r"\$([0-9A-Fa-f]{2})", src[i + len(start):j])]

# ---- the world (cosmic.inc) ------------------------------------------------------------------------------------------
cinc = open("cosmic.inc").read()
HY = bytes_of(cinc, "hy:", "\n\n")[:256]
RATETAB = bytes_of(cinc, "ratetab:", "heldpg:")[:256]
assert len(HY) == 256 and len(RATETAB) == 256
ROWSP, SPD, RMAX, RACC = 22, 185 / 256, 66, 3
APN, APSAFE = 10, 28
CANDS = [(k - 8) * 3 for k in range(17)]                     # target heading (high byte of the angle)
SLOPE = [round(math.tan(abs(c) * 256 * 2 * math.pi / 65536) * 256) for c in CANDS]
WTOP, CENTRE, BANDL = 62, 150, 212                           # bar window top, the horizon line, the band's first line

def wd(a):
    return ((a + 128) % 256) - 128

class Flight:
    def __init__(self):
        self.cy, self.cz, self.alpha, self.rate, self.tgt = 40.0, 0.0, 0, 0, 0
        self.looping = 0
    def plan(self):
        kc, czi = int(self.cz // ROWSP), self.cz % ROWSP
        sc = []
        for c, s in zip(CANDS, SLOPE):
            m = 999
            for j in range(APN):
                dz = ROWSP * (j + 1) - czi
                off = (s * dz) / 256 * (1 if c >= 0 else -1)
                m = min(m, abs(wd(HY[(kc + 1 + j) & 255] - (self.cy + off))))
            sc.append(m)
        angh = (self.alpha >> 8) & 255
        ci = min(range(17), key=lambda i: abs(wd(angh - CANDS[i] % 256)))
        if sc[ci] < APSAFE:
            ci = max(range(17), key=lambda i: sc[i])
        self.tgt = CANDS[ci]
    def step(self):
        angh = (self.alpha >> 8) & 255
        if self.looping:
            if self.looping == 1 and 128 <= angh < 192:
                self.looping = 2
            elif self.looping == 2 and (angh >= 252 or angh < 3):
                self.looping = 0
        if self.looping:
            rt = RATETAB[angh]
        else:
            err = ((self.tgt * 256 - self.alpha + 32768) % 65536) - 32768
            rt = max(-RMAX, min(RMAX, int(err / 32)))
        if self.rate < rt:
            self.rate = min(rt, self.rate + RACC)
        elif self.rate > rt:
            self.rate = max(rt, self.rate - RACC)
        self.alpha = (self.alpha + self.rate * 4) % 65536
        a = self.alpha * 2 * math.pi / 65536
        self.cy += SPD * math.sin(a)
        self.cz += SPD * math.cos(a)

# ---- goldship: ship frames, roll tilts ----------------------------------------------------------------------------------
sinc = open("ship.inc").read()
ROLLFR = bytes_of(sinc, "rollfr:", "pitchfr:")[:17]
PITCHFR = bytes_of(sinc, "pitchfr:", "rtilt0:")[:17]
RTILT = [bytes_of(sinc, f"rtilt{k}:", f"rtilt{k + 1}:" if k < 5 else None)[:17] for k in range(6)]
SHIPFR = bytes_of(open("shipfr.inc").read(), "shipfr:")[:162 * 64]
SHIPCOL = {1: 4, 2: 14, 3: 1}                                # %01 purple, %10 light blue, %11 white
SEGX = [32, 64, 128, 192, 256, 320, 352]                     # the six segments (screen x; sprite x 56.. = screen x 64..)
SPRX, SPRY = 184 - 12, CENTRE - 11

def ship_mask(f):
    """24 x 21 colour indices (-1 transparent) of frame f (multicolour: 12 pixel pairs a row)"""
    out = np.full((21, 24), -1, int)
    for r in range(21):
        bits = SHIPFR[f * 64 + 3 * r] << 16 | SHIPFR[f * 64 + 3 * r + 1] << 8 | SHIPFR[f * 64 + 3 * r + 2]
        for c in range(12):
            v = (bits >> (22 - 2 * c)) & 3
            if v:
                out[r, 2 * c:2 * c + 2] = SHIPCOL[v]
    return out
SHIPMASK = [ship_mask(f) for f in range(162)]

# ---- the Xenon font -----------------------------------------------------------------------------------------------------
finc = open("xenon_font.asm").read()
CHARSET = bytes_of(finc, "charset_data\n", "; CharSet Attribute")
assert len(CHARSET) == 248 * 8
FONTMC = [7, 10, 11, 0]                                      # %00 $d021 yellow, %01 $d022 light red, %10 $d023 dark grey, %11 black
def tile(t):
    out = np.zeros((16, 16), int)
    for cell in range(4):
        ch, cx, cyy = 4 * t + cell, (cell % 2) * 8, (cell // 2) * 8
        for r in range(8):
            b = CHARSET[ch * 8 + r]
            for p in range(4):
                out[cyy + r, cx + 2 * p:cx + 2 * p + 2] = FONTMC[(b >> (6 - 2 * p)) & 3]
    return out
CODE = {" ": 0x19, ".": 0x10, ",": 0x11, ";": 0x12, "?": 0x13, "!": 0x14, "(": 0x17, ")": 0x18, "-": 0x06, "+": 0x07,
        "'": 0x0F, '"': 0x0E, "&": 0x08, "/": 0x0A, ":": 0x01, "=": 0x02, "*": 0x04, "@": 0x0D, "$": 0x0C}
for i, ch in enumerate("ABCDEFGHIJKLM"):
    CODE[ch] = 0x1A + i
for ch, t in zip("NOPQRSTUVWXYZ", [0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x27, 0x31, 0x32, 0x33]):
    CODE[ch] = t
for i in range(10):
    CODE[str(i)] = 0x34 + i
TEXT = ("                    XEN0N      THIS IS A MOCKUP OF THE SCROLLER IN THE BLACK BAND UNDER THE COSMIC STRINGS ...  "
        "THE SHIP FLIES ON AUTOPILOT, ROLLS LEFT AND RIGHT, AND LOOPS THE LOOP!    MUSIC BY LUKHASH    0123456789    ")
STRIP = np.concatenate([tile(CODE.get(ch, 0x19)) for ch in TEXT], axis=1)    # 16 x (16 * len)
SCROLLY, SCROLLSPD = BANDL + (251 - BANDL - 16) // 2, 2

# ---- the bars: one build ------------------------------------------------------------------------------------------------
RAMP = [(0.10, 6), (0.25, 4), (0.42, 14), (0.62, 3), (0.82, 1)]    # blue, purple, light blue, cyan, white
def colour(v):
    c = 0
    for t, col in RAMP:
        if v >= t:
            c = col
    return c

R0, R1, W = 20, 263, 384                                    # canvas: raster lines R0..R1-1, 384 pixels
def build(fl, rolli):
    layer = np.zeros((R1 - R0, W), np.uint8)
    a = fl.alpha * 2 * math.pi / 65536
    s, c = math.sin(a), math.cos(a)
    kc = int(fl.cz // ROWSP)
    bars = []
    for k in range(kc - 24, kc + 26):
        rz = ROWSP * k - fl.cz
        for m in (-256, 0, 256):
            ry = wd(HY[k & 255] - fl.cy) + m
            d = ry * s + rz * c
            if not (1712 / 256 <= d < 448):
                continue
            u = ry * c - rz * s
            dm = d / 16
            h = 80 / dm if dm < 3 else 26.7 * math.sqrt(3 / dm)
            bars.append((d, CENTRE - 200 * u / d, max(1.0, h), dm))
    shifts = [6 - RTILT[k][rolli] for k in range(6)]
    for d, mid, h, dm in sorted(bars, reverse=True):          # far first: nearer bars cover them
        top = mid - h / 2
        n = int(round(h))
        y0 = int(round(top))
        bright = max(0.0, min(1.0, 1.15 - dm / 24)) ** 0.8
        cols = np.array([colour(bright * (0.3 + 0.7 * (1 - abs(2 * (j + 0.5) / n - 1)))) for j in range(n)], np.uint8)
        for sg in range(6):
            ya, yb = y0 + shifts[sg], y0 + shifts[sg] + n
            ca, cb = max(ya, WTOP), min(yb, BANDL)               # the window, above the black band
            if ca >= cb:
                continue
            seg = cols[ca - ya:cb - ya]
            keep = seg > 0                                     # (a black line of a bar's edge doesn't cover)
            blk = layer[ca - R0:cb - R0, SEGX[sg]:SEGX[sg + 1]]
            blk[keep] = seg[keep, None]
    return layer

# ---- the roll schedule (goldship's pilot: one step every other frame toward the stick) -----------------------------------
def stick(f):
    t = f % 420
    return 0 if t < 90 else (-8 if t < 180 else (0 if t < 240 else (8 if t < 330 else 0)))

def main():
    fl = Flight()
    for _ in range(240):                                       # (settle the autopilot before the clip starts)
        if _ % 4 == 0:
            fl.plan()
        fl.step()
    roll, layer = 0, None
    S = 3
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W * S}x{(R1 - R0) * S}",
                           "-r", "60", "-i", "-", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-crf", "18", OUT], stdin=subprocess.PIPE)
    for f in range(NF):
        if f == 360:
            fl.looping = 1                                     # the teardrop loop, 6 s in
        if f % 4 == 0 and not fl.looping:
            fl.plan()
        fl.step()
        if f % 2 == 0:                                         # the roll eases toward the stick, every other frame
            tgt = stick(f)
            roll += (tgt > roll) - (tgt < roll)
        rolli = roll + 8
        if f % 4 == 0:
            layer = build(fl, rolli)
        img = layer.copy()
        vy = max(-64, min(64, fl.rate))
        fr = ROLLFR[rolli] - 0x20 + PITCHFR[(vy + 64) >> 3] + (f & 1)
        m = SHIPMASK[fr]
        sub = img[SPRY + 1 - R0:SPRY + 22 - R0, SPRX:SPRX + 24]
        sub[m >= 0] = m[m >= 0]
        off = (f * SCROLLSPD) % (STRIP.shape[1] - 320)
        img[SCROLLY - R0:SCROLLY + 16 - R0, 32:352] = STRIP[:, off:off + 320]
        rgb = RGB[img]
        ff.stdin.write(np.repeat(np.repeat(rgb, S, axis=0), S, axis=1).tobytes())
        if f % 300 == 0:
            print("frame", f, "cy %.0f" % fl.cy, "angh", (fl.alpha >> 8) & 255, "roll", roll, flush=True)
    ff.stdin.close()
    ff.wait()
    print("wrote", OUT)

if __name__ == "__main__":
    main()
