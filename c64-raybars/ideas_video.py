#!/usr/bin/env python3
"""Two GOLDSHIP ideas as 60 fps videos (one C64 frame per video frame,
through interlace.py's PAL CRT model), on flight_video.py's re-creation.

Tapered bars.  Instead of a cylinder of constant radius, a bar thins along
its length.  Each of the six segments shows the bar at its own height:
  spindle  thick in the middle, thin at both ends: segments 0/5, 1/4 and 2/3
           share heights, which fits goldship's 3 mirrored columns per bar;
  wedge    thick at the left end, thin at the right: six heights, so six
           columns per bar (twice the column memory and copying).
    python3 ideas_video.py taper out.mp4

Banking sets the difficulty.  Banking right shortens the time between
spawns and spawns bars closer to the ship's height; banking left lengthens
it and spreads them out.  Level: one bar every 80 frames (3 in flight, as
now); full right: every 48 (5 in flight); full left: every 120 (2).
    python3 ideas_video.py density out.mp4

Long, gently tapering bars.  A bar 38 m long (40 segments at the ship's
distance) whose thickness varies along it, gradually the whole way or with
a constant middle; banking drifts the ship sideways so different parts of
it pass by (fast on near bars, slowly on far ones).
    python3 ideas_video.py longbank out.mp4      # the banking demo
    python3 ideas_video.py longflight out.mp4    # a flight

Sections.  The same with the bar made of segment-wide sections, each 1 or
2 lines thinner than the next one in (rows trimmed), stepping a section at
a time as the ship drifts.
    python3 ideas_video.py sections out.mp4      # banking demo, then a flight
    python3 ideas_video.py steps out.mp4         # 4 / 6-line steps, excised
                                                 # middle colours, fast scroll
    python3 ideas_video.py gaps out.mp4          # 1-5 line steps to a gap,
                                                 # then a flight through gaps
"""
import math, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flight_video as fv
import interlace as il
import jitter_video as jv
import mockup as mk
import ship_aa
import flicker as fl

TAPERS = {"straight": [1, 1, 1, 1, 1, 1],
          "spindle": [0.4, 0.72, 1, 1, 0.72, 0.4],
          "wedge": [1, 0.88, 0.74, 0.6, 0.46, 0.32]}

def visible(bars, shipy):
    """The bars with their depth, height relative to the ship, profiled height."""
    vis = []
    for b in bars:
        z = fb.zof(b.st)
        vis.append((b, z, b.y - shipy, mk.FLYH[b.st]))
    return vis

def frame_cols(bars, shipy, roll, p, taper, shipx=0.0):
    """flight_video.columns for frame parity p, with a height factor per
    segment (the colour rows the bar's own, resampled to that height).
    taper: a TAPERS name, or a LONG profile name (the factor from where along
    the bar each segment looks, the ship shipx metres sideways)."""
    vis = visible(bars, shipy)
    ghost_of = [fb.bright(z) < il.GHOST_BELOW for _, z, _, _ in vis]
    out = np.zeros((6, fb.H), np.uint8)
    offs = fv.offsets(roll, p, False)
    for k in range(6):
        tgt = np.zeros((fb.H, 3))
        who = np.full(fb.H, -1)
        depth = np.full(fb.H, np.inf)
        for i, (b, z, yrel, h0) in enumerate(vis):
            skip = (0, 0)
            keep = None
            if isinstance(taper, dict) and taper.get("gap"):
                d = gap_thin(b, z, SEGC[k], shipx, taper["step"], h0)
                if d >= h0:
                    continue                        # thinned to nothing: a gap
                h, keep = h0, d
            elif isinstance(taper, dict):
                d = section_thin(b, z, k, shipx, taper["step"])
                if d is None:
                    continue
                d = min(d, h0 - 2)
                h = h0
                if taper["mode"] == "trim":
                    skip = (d // 2, d - d // 2)
                else:
                    keep = d
            elif taper == "sections":
                d = section_thin(b, z, k, shipx)
                if d is None:
                    continue
                d = min(d, h0 - 2)                  # at least 2 lines left
                skip = (d // 2, d - d // 2)         # rows trimmed: top, bottom
                h = h0
            elif taper in LONG:
                f = long_factor(taper, b, z, k, shipx)
                if f <= 0:
                    continue
                h = max(2, int(round(h0 * f)))
            else:
                h = max(2, int(round(h0 * TAPERS[taper][k])))
            top = int(round(fb.CY - yrel / z - h / 2)) + offs[k]
            hl = mk.highlight(yrel, z, h, k)
            base = mk.BANDS[b.pal] * fb.bright(z)
            src = list(range(skip[0], h - skip[1]))
            if keep:                                # excise keep rows, centred
                src = excise([fb.C64RGB[hl[j]] if j in hl else base[j * 48 // h]
                              for j in range(h)], keep)
                top += keep // 2
            for jj, j in enumerate(src):
                row = top + jj
                if mk.WTOP <= row <= mk.WBOT and z < depth[row]:
                    depth[row] = z
                    who[row] = i
                    tgt[row] = fv.fl_lin(fb.C64RGB[hl[j]] if j in hl else base[j * 48 // h])
        cols, ghosted = il.choose_column(tgt, who, ghost_of, "full")
        out[k] = cols[:, p] | (ghosted.astype(np.uint8) << 4)
    return out

# ---- long, gently tapering bars --------------------------------------------------
# A bar 38 m long (40 segments at the ship's distance), lying across the
# view; its thickness depends on where along it you look.  Banking drifts the
# ship sideways (VX metres a frame at full bank), so the profile scrolls
# past: fast on near bars, slowly on far ones.
BAR_L = 38.0
VX = 0.18
SEGC = [(a + b) / 2 - fb.W / 2 for a, b in zip(mk.SEGX, mk.SEGX[1:])]   # px from centre

def long_profile(name, u):
    """Thickness (0..1 of full) at u = 0 .. 1 along the bar; 0 beyond it."""
    if not 0 <= u <= 1:
        return 0.0
    if name == "gradual":                       # tapers the whole way
        return 0.2 + 0.8 * math.sin(math.pi * u)
    t = 0.32                                    # "plateau": tapers 12 m at each
    e = min(u, 1 - u) / t                       # end, constant in the middle
    return 1.0 if e >= 1 else 0.2 + 0.8 * (3 * e * e - 2 * e ** 3)

LONG = {"gradual": "Gradual taper the whole length (38 m)",
        "plateau": "Taper 12 m at each end, a constant 14 m middle"}

def long_factor(name, b, z, k, shipx):
    x = shipx - b.x0 + SEGC[k] * z / fb.F        # metres along the bar
    return long_profile(name, x / BAR_L + 0.5)

def profile_sketch(dr, x0, y0, w, name, shipx, b, z):
    """A side view of the bar's profile, the part on screen bracketed."""
    pts = [(x0 + i, y0 - 9 * long_profile(name, i / (w - 1))) for i in range(w)]
    dr.line(pts, fill=(200, 170, 90))
    dr.line([(x, y0 + (y0 - y)) for x, y in pts], fill=(200, 170, 90))
    half = fb.W / 2 * z / fb.F
    a = (shipx - b.x0 - half) / BAR_L + 0.5
    c = (shipx - b.x0 + half) / BAR_L + 0.5
    xa, xc = x0 + a * (w - 1), x0 + c * (w - 1)
    dr.rectangle([xa, y0 - 12, xc, y0 + 12], outline=(124, 112, 218))

# ---- sections, each 1 or 2 lines thinner than its neighbour ----------------------
# A bar of 40 sections, each one screen segment wide (64 px) at the bar's
# distance: a full-thickness middle of 20, and 10 at each end, each 1 or 2
# lines thinner than the next one in.  A section is thinned by trimming its
# outermost rows (the bar's own colours stay).  Banking right drifts the ship
# right, so the profile steps left a section at a time (near bars step
# sooner than far ones).
THIN = [0, 1, 2, 4, 5, 7, 8, 10, 11, 13]        # lines off, from the middle out
SECTIONS = THIN[::-1] + [0] * 20 + THIN         # 40 sections

def excise(rows, d):
    """Indices of the rows kept when d rows go.  The bars are drawn on black,
    so contrast is brightness: the dimmest rows go first (black reflection
    gaps, dull bands), a row repeating its neighbour's colour before a
    unique one, while the bright highlights stay; the top and bottom rows,
    the bar's outline, stay until only 3 rows are left."""
    lum = [(0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255
           for c in (np.asarray(r, float) for r in rows)]
    idx = list(range(len(rows)))
    for _ in range(d):
        if len(idx) <= 1:
            break
        def cost(i):
            j = idx[i]
            dup = any(0 <= n < len(idx) and np.allclose(rows[idx[n]], rows[j])
                      for n in (i - 1, i + 1))
            edge = len(idx) > 3 and i in (0, len(idx) - 1)
            return lum[j] - (0.1 if dup else 0) + (2 if edge else 0)
        idx.pop(min(range(len(idx)), key=cost))
    return idx

def section_index(b, z, k, shipx):
    w = 64 * z / fb.F                            # a section's width, metres
    return int(math.floor((shipx - b.x0) / w + SEGC[k] / 64 + len(SECTIONS) / 2))

def section_thin(b, z, k, shipx, step=None):
    """Lines off for the section under segment k: the profile above, or with
    step the end sections step lines thinner each, from the middle out."""
    i = section_index(b, z, k, shipx)
    if step is not None:                        # bars repeat end to end
        i %= len(SECTIONS)
    if not 0 <= i < len(SECTIONS):
        return None
    if step is None:
        return SECTIONS[i]
    e = max(0, 10 - i, i - 29)                  # sections into the tapering end
    return step * e

# ---- bars that thin to nothing: gaps to fly through ---------------------------------
# A bar: a full-thickness middle of GM sections, a taper at each end losing
# `step` lines a section (at the ship's distance; farther bars in proportion,
# so the gaps stay put in the world as the bar comes in) down to nothing,
# and a gap of GG sections before the next bar.
GM, GG = 14, 2
HREF = mk.FLYH[min(range(fb.FLYD), key=lambda t: abs(fb.zof(t) - fb.ZS))]

def gap_layout(step):
    t = -(-HREF // step)                         # taper sections: ceil(HREF/step)
    return t, t + GM + t + GG                    # taper, period

def gap_e(step, u):
    """Sections into the taper at position u of the period; None in the gap."""
    t, period = gap_layout(step)
    u %= period
    if u < t:
        return t - u
    if u < t + GM:
        return 0
    if u < t + GM + t:
        return u - (t + GM) + 1
    return None

def gap_thin(b, z, px, shipx, step, h0):
    """Lines off a bar of h0 lines at screen x px from the centre."""
    w = 64 * z / fb.F
    e = gap_e(step, int(math.floor((shipx - b.x0) / w + px / 64)))
    return h0 if e is None else min(h0, int(round(h0 * step * e / HREF)))

def gap_sketch(dr, x0, y0, b, z, shipx, step, cw=4):
    t, period = gap_layout(step)
    w = 64 * z / fb.F
    on = {int(math.floor((shipx - b.x0) / w + px / 64)) % period for px in SEGC}
    for i in range(period):
        e = gap_e(step, i)
        hh = 0 if e is None else max(0, HREF - step * e) * 9 / HREF
        col = (230, 225, 255) if i in on else (200, 170, 90)
        if hh:
            dr.rectangle([x0 + i * cw, y0 - hh, x0 + i * cw + cw - 2, y0 + hh], fill=col)
        elif i in on:
            dr.line([x0 + i * cw, y0, x0 + i * cw + cw - 2, y0], fill=col)

GAPSTEPS = [(f"{n} line{'s' if n > 1 else ''} thinner each step", n) for n in (1, 2, 3, 4, 5)]

def fly_gaps(nframes, step, warmup=240, seed=5):
    """A flight with gap bars: on a collision course the autopilot banks for
    the nearest gap it can reach in time, else climbs or dives."""
    rng = np.random.default_rng(seed)
    shipx, shipy, vy, roll = 0.0, 0.0, 0, 0
    vx = VX * 3
    bars, spawn_i, events = [], 0, []
    for f in range(warmup + nframes):
        if f % 80 == 0:
            b = mk.Bar(shipy + mk.SPAWN[spawn_i % len(mk.SPAWN)] * 0.5,
                       mk.PALC[spawn_i % len(mk.PALC)] & 3, 0)
            b.x0 = shipx + rng.uniform(-20, 20)
            b.done = False
            bars.append(b)
            spawn_i += 1
        stick = 0
        ahead = [b for b in bars if b.st > 90 and not b.done and abs(b.y - shipy) < 34]
        if ahead:
            b = max(ahead, key=lambda b: b.st)
            left = fb.FLYD - 2 - b.st
            reach = left * vx * 0.5
            w = 64 * fb.ZS / fb.F                # a section at the ship's depth
            best = None
            for s in range(-40, 41):
                x = shipx + s * w / 2
                if abs(x - shipx) <= reach and gap_e(step, int(math.floor((x - b.x0) / w))) is None:
                    if best is None or abs(x - shipx) < abs(best - shipx):
                        best = x
            if best is not None:
                if abs(best - shipx) > w * 0.2:
                    stick = 8 if best > shipx else 4
            else:
                stick = 1 if b.y >= shipy else 2
        if stick & 2 and not stick & 1:
            vy = min(64, vy + 3)
        elif stick & 1 and not stick & 2:
            vy = max(-64, vy - 3)
        else:
            vy = max(0, vy - 3) if vy > 0 else min(0, vy + 3)
        shipy += vy / 64
        if f % 2 == 0:
            if stick & 4 and not stick & 8:
                roll = max(-8, roll - 1)
            elif stick & 8 and not stick & 4:
                roll = min(8, roll + 1)
            else:
                roll -= (roll > 0) - (roll < 0)
        shipx += roll / 8 * vx
        for b in bars:
            if b.st == fb.FLYD - 2 and not b.done:   # the bar reaches the ship
                b.done = True
                if abs(b.y - shipy) >= mk.HITR:
                    events.append((f, "over / under"))
                elif gap_thin(b, fb.ZS, 0, shipx, step, HREF) >= HREF:
                    events.append((f, "through a gap"))
                else:
                    events.append((f, "HIT"))
        if f >= warmup:
            last = events[-1] if events and f - events[-1][0] < 90 else None
            yield list(bars), shipx, shipy, roll, vy, last
        for b in bars:
            b.st += 1
        bars = [b for b in bars if b.st < fb.FLYD]

def gaps_video(path, flight_frames=900, flight_step=3):
    """The banking demo with each step size, stacked, then a flight."""
    global VX
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z, lab = 3, 26
    top = int(fb.CY - 26 / fb.zof(fv.BANK_T)) - 16
    bot = fb.CY + 13
    sh, sw = (bot - top) * Z, fb.W * Z
    W, H = fb.W * Z, fb.H * Z
    v = Video(path, sw + 32, max(len(GAPSTEPS) * (sh + lab) + 16, H + 60))
    for loop in range(2):
        xs = [6.0] * len(GAPSTEPS)
        for k, (bars, shipy, roll, vy, red, hit) in enumerate(fv.bank()):
            b = bars[0]
            b.x0 = 0.0
            z = fb.zof(b.st)
            canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
            dr = ImageDraw.Draw(canvas)
            for i, (text, step) in enumerate(GAPSTEPS):
                opt = dict(step=step, gap=True)
                img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, opt, xs[i]), k,
                                     ship_pair(pairs, roll, vy, k), None, None)
                y = 8 + i * (sh + lab)
                dr.text((16, y + 5), f"{text}, thins to a gap   roll {roll:+d}",
                        fill=(200, 196, 220), font=small)
                gap_sketch(dr, sw - 250, y + 12, b, z, xs[i], step)
                canvas.paste(Image.fromarray(tv(img, top, bot)).resize((sw, sh), Image.BILINEAR),
                             (16, y + lab))
                xs[i] += roll / 8 * VX * 3
            v.add(canvas)
    opt = dict(step=flight_step, gap=True)
    for k, (bars, shipx, shipy, roll, vy, ev) in enumerate(fly_gaps(flight_frames, flight_step)):
        img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, opt, shipx), k,
                             ship_pair(pairs, roll, vy, k), None, None)
        canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), f"Flight: {flight_step}-line steps, gaps; the autopilot banks for a "
                f"gap it can reach, else climbs or dives.   roll {roll:+d}",
                fill=(200, 196, 220), font=small)
        if ev:
            dr.text((16, 28), f"last bar: {ev[1]}", fill=(208, 220, 113) if ev[1] != "HIT"
                    else (255, 110, 100), font=font)
        canvas.paste(Image.fromarray(tv(img)).resize((W, H), Image.BILINEAR), (16, 56))
        v.add(canvas)
    v.close()
    print("wrote", path)

STEPS = [("4-line steps, middle colours excised", dict(step=4, mode="excise", vx=1)),
         ("6-line steps, middle colours excised", dict(step=6, mode="excise", vx=1)),
         ("4-line steps, middle colours excised, 3x faster scroll", dict(step=4, mode="excise", vx=3)),
         ("4-line steps, edges trimmed (the colours lost)", dict(step=4, mode="trim", vx=1))]

def steps_sketch(dr, x0, y0, b, z, shipx, step, cw=5):
    on = {section_index(b, z, k, shipx) % len(SECTIONS) for k in range(6)}
    for i in range(len(SECTIONS)):
        hh = max(1, 9 - step * max(0, 10 - i, i - 29) // 3)
        col = (200, 170, 90) if i not in on else (230, 225, 255)
        dr.rectangle([x0 + i * cw, y0 - hh, x0 + i * cw + cw - 2, y0 + hh], fill=col)

def steps_video(path, flight_frames=720):
    """The banking demo, four ways stacked, then a flight (4-line steps,
    excised, fast scroll)."""
    global VX
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z, lab = 3, 30
    top = int(fb.CY - 26 / fb.zof(fv.BANK_T)) - 16
    bot = fb.CY + 13
    sh, sw = (bot - top) * Z, fb.W * Z
    W, H = fb.W * Z, fb.H * Z
    vw, vh = sw + 32, max(len(STEPS) * (sh + lab) + 16, H + 60)
    v = Video(path, vw, vh)
    xs = [10.0] * len(STEPS)
    for loop in range(2):
        xs = [10.0] * len(STEPS)
        for k, (bars, shipy, roll, vy, red, hit) in enumerate(fv.bank()):
            b = bars[0]
            b.x0 = 0.0
            z = fb.zof(b.st)
            canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
            dr = ImageDraw.Draw(canvas)
            for i, (text, opt) in enumerate(STEPS):
                img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, opt, xs[i]), k,
                                     ship_pair(pairs, roll, vy, k), None, None)
                y = 8 + i * (sh + lab)
                dr.text((16, y + 6), f"{text}   roll {roll:+d}", fill=(200, 196, 220), font=small)
                steps_sketch(dr, sw - 190, y + 14, b, z, xs[i], opt["step"])
                canvas.paste(Image.fromarray(tv(img, top, bot)).resize((sw, sh), Image.BILINEAR),
                             (16, y + lab))
                xs[i] += roll / 8 * VX * opt["vx"]
            v.add(canvas)
    opt = STEPS[2][1]
    vx0, VX = VX, VX * opt["vx"]
    try:
        for k, (bars, shipx, shipy, roll, vy) in enumerate(fly_long(flight_frames)):
            img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, opt, shipx), k,
                                 ship_pair(pairs, roll, vy, k), None, None)
            canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
            dr = ImageDraw.Draw(canvas)
            dr.text((16, 8), f"Flight: {STEPS[2][0]}   roll {roll:+d}", fill=(200, 196, 220),
                    font=small)
            canvas.paste(Image.fromarray(tv(img)).resize((W, H), Image.BILINEAR), (16, 34))
            v.add(canvas)
    finally:
        VX = vx0
    v.close()
    print("wrote", path)

def sections_sketch(dr, x0, y0, b, z, shipx, cw=6):
    """The 40 sections' thickness, the six on screen outlined."""
    on = {section_index(b, z, k, shipx) for k in range(6)}
    for i, d in enumerate(SECTIONS):
        hh = 13 - d
        col = (200, 170, 90) if i not in on else (230, 225, 255)
        dr.rectangle([x0 + i * cw, y0 - hh, x0 + i * cw + cw - 2, y0 + hh], fill=col)

def sections_video(path, flight_frames=720):
    """The banking demo (one bar at a fixed distance), then a flight."""
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    top = int(fb.CY - 26 / fb.zof(fv.BANK_T)) - 16
    bot = fb.CY + 13
    v = Video(path, W + 32, H + 72)
    note = ("Sections 1-2 lines thinner than the next one in; bank right and the thin "
            "sections step left")
    def frame(img, title, sketch):
        canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), title, fill=(200, 196, 220), font=small)
        dr.text((16, 28), note, fill=(140, 136, 160), font=small)
        if sketch:
            sketch(dr)
        canvas.paste(img, (16, 64))
        v.add(canvas)
    # 1. the banking demo, close up: one bar at a fixed distance
    shipx = 10.0
    for k, (bars, shipy, roll, vy, red, hit) in enumerate(fv.bank()):
        b = bars[0]
        b.x0 = 0.0
        z = fb.zof(b.st)
        img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, "sections", shipx), k,
                             ship_pair(pairs, roll, vy, k), None, None)
        frame(Image.fromarray(tv(img)).resize((W, H), Image.BILINEAR), f"One bar, banking: roll {roll:+d}, sideways {shipx:+5.1f} m",
              lambda dr: sections_sketch(dr, W - 230, 40, b, z, shipx))
        shipx += roll / 8 * VX
    # 2. a flight
    for k, (bars, shipx, shipy, roll, vy) in enumerate(fly_long(flight_frames)):
        img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, "sections", shipx), k,
                             ship_pair(pairs, roll, vy, k), None, None)
        frame(Image.fromarray(tv(img)).resize((W, H), Image.BILINEAR),
              f"Flight: roll {roll:+d}, sideways {shipx:+6.1f} m", None)
    v.close()
    print("wrote", path)

def tv(img, top=0, bot=None):
    pad = np.pad(img[max(0, top - 1):bot], ((0, 0), (8, 8), (0, 0)))
    return il.crt(pad.astype(float))[1 if top else 0:, 8:-8].astype(np.uint8)

class Video:
    def __init__(self, path, w, h, fps=60):
        self.w, self.h = w + w % 2, h + h % 2
        self.p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
                                   "-pix_fmt", "rgb24", "-s", f"{self.w}x{self.h}", "-r", str(fps),
                                   "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "12",
                                   "-pix_fmt", "yuv420p", "-movflags", "+faststart", path],
                                  stdin=subprocess.PIPE)
    def add(self, im):
        self.p.stdin.write(im.crop((0, 0, self.w, self.h)).tobytes())
    def close(self):
        self.p.stdin.close()
        self.p.wait()

def ship_pair(pairs, roll, vy, k):
    return pairs[ship_aa.roll_index(roll) * 9 + ship_aa.pitch_index((vy + 64) >> 3)][k & 1]

# ---- tapered bars: the banking demo, three ways -------------------------------------
def taper_video(path):
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z, lab = 3, 26
    top = int(fb.CY - 26 / fb.zof(fv.BANK_T)) - 16
    bot = fb.CY + 13
    sh, sw = (bot - top) * Z, fb.W * Z
    opts = [("Straight: a cylinder (now)", "straight"),
            ("Spindle: thin at both ends (fits the 3 mirrored columns)", "spindle"),
            ("Wedge: thick at the left end, thin at the right (needs 6 columns)", "wedge")]
    v = Video(path, sw + 32, len(opts) * (sh + lab) + 16)
    seq = list(fv.bank())
    for loop in range(2):
        for k, (bars, shipy, roll, vy, red, hit) in enumerate(seq):
            canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
            dr = ImageDraw.Draw(canvas)
            for i, (text, taper) in enumerate(opts):
                img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, taper), k,
                                     ship_pair(pairs, roll, vy, k), None, None)
                y = 8 + i * (sh + lab)
                dr.text((16, y + 4), text, fill=(200, 196, 220), font=small)
                canvas.paste(Image.fromarray(tv(img, top, bot)).resize((sw, sh), Image.BILINEAR),
                             (16, y + lab))
            v.add(canvas)
    v.close()
    print("wrote", path)

# ---- banking sets the difficulty ------------------------------------------------------
# the autopilot holds the stick right for 6 s, centres, holds it left
# (the roll eases back to level whenever the stick is centred)
PLAN = [(8, 300), (0, 40), (4, 300), (0, 40)]

def interval(roll):
    """Frames between spawns: 80 level, 48 full right, 120 full left."""
    return int(round(80 * 0.6 ** (roll / 8))) if roll > 0 else int(round(80 * 1.5 ** (-roll / 8)))

def spread(roll):
    """Spawn offsets scaled: 1 level, 0.55 full right, 1.5 full left."""
    return 0.55 ** (roll / 8) if roll > 0 else 1.5 ** (-roll / 8)

def fly_density(nframes, warmup=200):
    shipy, vy, roll = 0.0, 0, 0
    bars, spawn_i, since = [], 0, 999
    plan = [b for b, n in PLAN for _ in range(n)]
    for f in range(warmup + nframes):
        if since >= interval(roll):
            bars.append(mk.Bar(shipy + mk.SPAWN[spawn_i % len(mk.SPAWN)] * spread(roll),
                               mk.PALC[spawn_i % len(mk.PALC)] & 3, 0))
            spawn_i += 1
            since = 0
        since += 1
        stick = plan[f % len(plan)]
        ahead = [b for b in bars if b.st > 110 and abs(b.y - shipy) < 34]
        if ahead:
            b = max(ahead, key=lambda b: b.st)
            stick = (stick & 12) | (1 if b.y >= shipy else 2)
        if stick & 2 and not stick & 1:
            vy = min(64, vy + 3)
        elif stick & 1 and not stick & 2:
            vy = max(-64, vy - 3)
        else:
            vy = max(0, vy - 3) if vy > 0 else min(0, vy + 3)
        shipy += vy / 64
        if f % 2 == 0:
            if stick & 4 and not stick & 8:
                roll = max(-8, roll - 1)
            elif stick & 8 and not stick & 4:
                roll = min(8, roll + 1)
            else:
                roll -= (roll > 0) - (roll < 0)
        if f >= warmup:
            yield list(bars), shipy, roll, vy
        for b in bars:
            b.st += 1
        bars = [b for b in bars if b.st < fb.FLYD]

def density_video(path, nframes=1200):
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    v = Video(path, W + 32, H + 60)
    for k, (bars, shipy, roll, vy) in enumerate(fly_density(nframes)):
        img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, "spindle"), k,
                             ship_pair(pairs, roll, vy, k), None, None)
        canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
        dr = ImageDraw.Draw(canvas)
        side = "right: harder" if roll > 0 else "left: easier" if roll < 0 else "level"
        dr.text((16, 10), f"Banking sets the difficulty -- roll {roll:+d} ({side})   "
                f"a bar every {interval(roll)} frames   bars in flight: {len(bars)}",
                fill=(200, 196, 220), font=small)
        dr.text((16, 30), "Spindle-tapered bars. More than 3 bars in flight needs the "
                "build optimisations.", fill=(140, 136, 160), font=small)
        canvas.paste(Image.fromarray(tv(img)).resize((W, H), Image.BILINEAR), (16, 52))
        v.add(canvas)
        if k % 200 == 0:
            print(f"frame {k}/{nframes}", flush=True)
    v.close()
    print("wrote", path)

def long_bank_video(path):
    """The banking demo with long tapering bars: the ship drifts sideways as
    it banks, so a different part of the bar passes the screen."""
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z, lab = 3, 40
    top = int(fb.CY - 26 / fb.zof(fv.BANK_T)) - 16
    bot = fb.CY + 13
    sh, sw = (bot - top) * Z, fb.W * Z
    v = Video(path, sw + 32, len(LONG) * (sh + lab) + 16)
    seq = list(fv.bank())
    for loop in range(2):
        shipx = 12.0            # the bank drifts it to -12.5 m and back
        for k, (bars, shipy, roll, vy, red, hit) in enumerate(seq):
            bars[0].x0 = 0.0
            z = fb.zof(bars[0].st)
            canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
            dr = ImageDraw.Draw(canvas)
            for i, (name, text) in enumerate(LONG.items()):
                img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, name, shipx), k,
                                     ship_pair(pairs, roll, vy, k), None, None)
                y = 8 + i * (sh + lab)
                dr.text((16, y + 4), f"{text}   (sideways {shipx:+5.1f} m)", fill=(200, 196, 220),
                        font=small)
                profile_sketch(dr, sw - 230, y + 18, 240, name, shipx, bars[0], z)
                canvas.paste(Image.fromarray(tv(img, top, bot)).resize((sw, sh), Image.BILINEAR),
                             (16, y + lab))
            v.add(canvas)
            shipx += roll / 8 * VX
    v.close()
    print("wrote", path)

LONGPLAN = [(8, 110), (0, 50), (4, 220), (0, 50), (8, 140), (0, 80)]

def fly_long(nframes, warmup=240, seed=3):
    """A flight at today's density (a bar every 80 frames) with lateral
    drift; each bar spawns with its middle somewhere across the view."""
    rng = np.random.default_rng(seed)
    shipx, shipy, vy, roll = 0.0, 0.0, 0, 0
    bars, spawn_i = [], 0
    plan = [b for b, n in LONGPLAN for _ in range(n)]
    for f in range(warmup + nframes):
        if f % 80 == 0:
            b = mk.Bar(shipy + mk.SPAWN[spawn_i % len(mk.SPAWN)], mk.PALC[spawn_i % len(mk.PALC)] & 3, 0)
            b.x0 = shipx + rng.uniform(-0.4, 0.4) * BAR_L
            bars.append(b)
            spawn_i += 1
        stick = plan[f % len(plan)]
        ahead = [b for b in bars if b.st > 110 and abs(b.y - shipy) < 34]
        if ahead:
            b = max(ahead, key=lambda b: b.st)
            stick = (stick & 12) | (1 if b.y >= shipy else 2)
        if stick & 2 and not stick & 1:
            vy = min(64, vy + 3)
        elif stick & 1 and not stick & 2:
            vy = max(-64, vy - 3)
        else:
            vy = max(0, vy - 3) if vy > 0 else min(0, vy + 3)
        shipy += vy / 64
        if f % 2 == 0:
            if stick & 4 and not stick & 8:
                roll = max(-8, roll - 1)
            elif stick & 8 and not stick & 4:
                roll = min(8, roll + 1)
            else:
                roll -= (roll > 0) - (roll < 0)
        shipx += roll / 8 * VX
        if f >= warmup:
            yield list(bars), shipx, shipy, roll, vy
        for b in bars:
            b.st += 1
        bars = [b for b in bars if b.st < fb.FLYD]

def long_flight_video(path, name="plateau", nframes=900):
    pairs = ship_aa.pairs()
    font, small = fl.fonts()
    Z = 3
    W, H = fb.W * Z, fb.H * Z
    v = Video(path, W + 32, H + 40)
    for k, (bars, shipx, shipy, roll, vy) in enumerate(fly_long(nframes)):
        img = jv.frame_image(frame_cols(bars, shipy, roll, k & 1, name, shipx), k,
                             ship_pair(pairs, roll, vy, k), None, None)
        canvas = Image.new("RGB", (v.w, v.h), (11, 10, 18))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 10), f"{LONG[name]}.  Banking drifts the ship sideways: roll {roll:+d}, "
                f"sideways {shipx:+6.1f} m", fill=(200, 196, 220), font=small)
        canvas.paste(Image.fromarray(tv(img)).resize((W, H), Image.BILINEAR), (16, 32))
        v.add(canvas)
    v.close()
    print("wrote", path)

if __name__ == "__main__":
    {"taper": taper_video, "density": density_video, "longbank": long_bank_video,
     "longflight": long_flight_video, "sections": sections_video, "steps": steps_video, "gaps": gaps_video}[sys.argv[1]](sys.argv[2])
