#!/usr/bin/env python3
"""Mockup (Python): the greetings scroller in the black band, choreographed with the ship (mock_scroller.py's world, ship and font).

  after the teardrop loop:
    bank right   "GREETS TO" scrolls on from the right
    bank left    it leaves to the right, "DESIRE  MOONSHINE" comes on from the left
    bank right   that leaves to the left, "CREST  RAISTLIN" comes on from the right
    level        half a second, the text still
    bank left    that leaves to the right, "HAMMERFIST  T0M3000" comes on from the left
    half loop    the text scrolls down out of the band, "ANDY  SHINE" / "GUINEA PIG" (two rows, one black line
                 between them: one row is wider than the window)
                 scrolls down into it
    hard down    that scrolls up out of the band, gone at the band's top edge
  all the while: the side-scrolling text moves down as the ship pitches up and up as it pitches down, inside the band.

    python3 mock_greets.py [out.mp4]
"""
import math, subprocess, sys
import numpy as np
import mock_scroller as ms

OUT = sys.argv[1] if len(sys.argv) > 1 else "mock_greets.mp4"
BTOP, BBOT = ms.BANDL, ms.WTOP + 189                          # the black band: raster lines 212..250
XC = 32 + 160                                                 # the window's centre (screen x)
SPEED = 1                                                     # scroll: pixels a frame at full bank
LAG = 15                                                      # the scroll trails the bank by a quarter second

def brake():
    """pixels the text still travels after the bank starts to reverse (full bank, then easing to 0 a step every other frame)"""
    r, dist = [8] * LAG, 0.0
    roll = 8
    for f in range(200):
        if f % 2 == 0 and roll > 0:
            roll -= 1
        r.append(roll)
        u = r[-1 - LAG] / 8
        v = SPEED * u * u * (3 - 2 * u)
        if v == 0:
            break
        dist += v
    return dist
BRAKE = brake()
PMAX = (BBOT - BTOP - 16) // 2                                # the pitch's room for one text row: 11 lines each way

def strip(text):
    return np.concatenate([ms.tile(ms.CODE.get(ch, 0x19)) for ch in text.upper()], axis=1)

GAP = 1                                                       # black raster lines between the rows of a block

def block(*rows):
    s = [strip(r) for r in rows]
    w = max(x.shape[1] for x in s)
    out = np.zeros((16 * len(s) + GAP * (len(s) - 1), w), int)
    for i, x in enumerate(s):
        o = (w - x.shape[1]) // 2
        y = (16 + GAP) * i
        out[y:y + 16, o:o + x.shape[1]] = x
    return out

class Flight(ms.Flight):
    mode = "auto"                                             # auto (dodging), loop (teardrop), half (to inverted), down (hard, to level)
    def step(self):
        angh = (self.alpha >> 8) & 255
        if self.mode == "loop":
            if self.looping == 0:
                self.looping = 1
            ms.Flight.step(self)
            if self.looping == 0:
                self.mode = "auto"
            return
        if self.mode == "half":
            rt = ms.RATETAB[angh]
            if 128 <= angh < 200:
                self.mode, rt = "top", 0
        elif self.mode == "top":
            rt = 0
        elif self.mode == "down":
            rt = -ms.RMAX
            if angh < 4 or angh >= 252:
                self.mode, rt = "auto", 0
        else:
            err = ((self.tgt * 256 - self.alpha + 32768) % 65536) - 32768
            rt = max(-ms.RMAX, min(ms.RMAX, int(err / 32)))
        if self.rate < rt:
            self.rate = min(rt, self.rate + ms.RACC)
        elif self.rate > rt:
            self.rate = max(rt, self.rate - ms.RACC)
        if self.mode in ("top", "down") and abs(self.rate) < ms.RACC and rt == 0:
            self.rate = 0
        self.alpha = (self.alpha + self.rate * 4) % 65536
        a = self.alpha * 2 * math.pi / 65536
        self.cy += ms.SPD * math.sin(a)
        self.cz += ms.SPD * math.cos(a)

def main():
    fl = Flight()
    for i in range(240):
        if i % 4 == 0:
            fl.plan()
        fl.step()
    texts = {"greets": block("GREETS TO"), "dm": block("DESIRE  MOONSHINE"), "cr": block("CREST  RAISTLIN"),
             "ht": block("HAMMERFIST  T0M3000"), "asg": block("ANDY  SHINE", "GUINEA PIG")}
    H2 = texts["asg"].shape[0]                                # the two-row block: 16 + GAP + 16 lines
    # the horizontal phases: (roll target, direction the text moves: -1 left / +1 right, leaving text, arriving text)
    hphases = [(8, -1, None, "greets"), (-8, 1, "greets", "dm"), (8, -1, "dm", "cr"), ("hold", 0, "cr", None),
               (-8, 1, "cr", "ht")]
    blocks = {}                                               # visible text: name -> [x centre, top]
    roll, layer = 0, None
    S = 3
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                           f"{ms.W * S}x{(ms.R1 - ms.R0) * S}", "-r", "60", "-i", "-", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", OUT], stdin=subprocess.PIPE)
    phase, pf, prog, tail = "pre", 0, None, 0
    rolltgt = 0
    rollhist = []
    arriving = None
    f = 0
    while True:
        # ---- the script ----------------------------------------------------------------------------------------------------
        if phase == "pre" and f == 90:
            fl.mode, phase = "loop", "loop"
        elif phase == "loop" and fl.mode == "auto":
            phase, hi = "h", 0
            pf = 0
        # the side scroll trails the bank by LAG frames and eases with it: speed = SPEED * smoothstep(|roll| / 8), against the bank
        rh = rollhist[-1 - LAG] if len(rollhist) > LAG else 0
        u = abs(rh) / 8
        vx = -SPEED * (u * u * (3 - 2 * u)) * ((rh > 0) - (rh < 0))
        for b in blocks.values():
            b[0] += vx
        for nme in [n for n, b in blocks.items() if abs(b[0] - XC) > 160 + texts[n].shape[1] / 2 + 8 and (b[0] - XC) * vx > 0 and n != arriving]:
            del blocks[nme]                                 # (gone off the side, still moving away)
        if phase == "h":
            tgt, d, old, new = hphases[hi]
            if pf == 0:
                rolltgt = 0 if tgt == "hold" else tgt
                arriving = new
                if new:
                    wo = texts[old].shape[1] if old else 0
                    dist = 160 + max(wo, texts[new].shape[1]) // 2 + 8
                    blocks[new] = [XC - d * dist, None]
                still = 0
            pf += 1
            if tgt == "hold":
                still = still + 1 if vx == 0 else 0         # half a second with the text still
                done = still >= 30
            else:                                           # on to the next bank when the arriving text, slowing from here, stops at the centre
                done = (XC - blocks[new][0]) * d <= BRAKE
            if done:
                hi += 1
                pf = 0
                if hi == len(hphases):
                    phase, rolltgt = "half", 0
                    fl.mode = "half"
                    blocks["asg"] = [XC, BTOP - H2]
                    start_ht = blocks["ht"][1]
        elif phase == "half":
            angh = (fl.alpha >> 8) & 255
            sang = angh - 256 if angh >= 192 else angh          # (signed: a ship still pitched down at the start reads as < 0, not ~ a turn)
            p = min(1.0, max(0.0, sang / 128)) if fl.mode == "half" else 1.0
            blocks["ht"][1] = start_ht + p * (BBOT - start_ht)
            blocks["asg"][1] = (BTOP - H2) + p * ((BBOT - BTOP - H2) // 2 + H2)
            if fl.mode == "top":
                pf += 1
                if pf > 20:
                    del blocks["ht"]
                    phase, fl.mode, pf = "down", "down", 0
        elif phase == "down":
            angh = (fl.alpha >> 8) & 255
            q = 1.0 if fl.mode == "auto" else min(1.0, max(0.0, (128 - angh) / 128))
            top0 = BTOP + (BBOT - BTOP - H2) // 2
            blocks["asg"][1] = top0 + q * (BTOP - H2 - top0)
            if fl.mode == "auto":
                phase, tail = "tail", 0
        elif phase == "tail":
            blocks.pop("asg", None)
            tail += 1
            if tail > 120:
                break
        # ---- the flight ----------------------------------------------------------------------------------------------------
        if f % 4 == 0 and fl.mode == "auto":
            fl.plan()
        fl.step()
        if f % 2 == 0:
            roll += (rolltgt > roll) - (rolltgt < roll)
        rollhist.append(roll)
        rolli = roll + 8
        if f % 4 == 0:
            layer = ms.build(fl, rolli)
        img = layer.copy()
        vy = max(-64, min(64, fl.rate))
        fr = ms.ROLLFR[rolli] - 0x20 + ms.PITCHFR[(vy + 64) >> 3] + (f & 1)
        m = ms.SHIPMASK[fr]
        sub = img[ms.SPRY + 1 - ms.R0:ms.SPRY + 22 - ms.R0, ms.SPRX:ms.SPRX + 24]
        sub[m >= 0] = m[m >= 0]
        # ---- the text: pitch up moves the side-scrolling text down, pitch down moves it up ------------------------------------
        poff = int(round(max(-1.0, min(1.0, fl.rate / ms.RMAX)) * PMAX))
        for nme, b in blocks.items():
            t = texts[nme]
            h, w = t.shape
            if phase in ("pre", "loop", "h") or b[1] is None:
                b[1] = BTOP + (BBOT - BTOP - h) // 2 + (poff if h == 16 else 0)
            top = int(round(b[1]))
            x0 = int(round(b[0] - w / 2))
            ya, yb = max(top, BTOP), min(top + h, BBOT)
            xa, xb = max(x0, 32), min(x0 + w, 352)
            if ya < yb and xa < xb:
                src = t[ya - top:yb - top, xa - x0:xb - x0]
                dst = img[ya - ms.R0:yb - ms.R0, xa:xb]
                keep = src > 0
                dst[keep] = src[keep]
        ff.stdin.write(np.repeat(np.repeat(ms.RGB[img], S, axis=0), S, axis=1).tobytes())
        f += 1
        if phase == "h" and pf == 1 and hi < len(hphases):
            print("frame", f, "phase", hi, hphases[hi][3], flush=True)
        if f > 60 * 60:
            break
    ff.stdin.close()
    ff.wait()
    print("wrote", OUT, f, "frames")

if __name__ == "__main__":
    main()
