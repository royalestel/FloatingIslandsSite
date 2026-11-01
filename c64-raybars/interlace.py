#!/usr/bin/env python3
"""Flicker colours + alternating line colours + the ghost byte, judged
through a PAL CRT model.  A study for GOLDSHIP's bars, built on flicker.py
and flyby3d.py.

Three ways to show colours the C64 doesn't have:
  * flicker: two colours on alternate frames (flicker.py's 51 colours; the
    phase swaps on odd screen lines);
  * alternating lines: neighbouring lines in neighbouring colours, which a
    PAL TV's delay line blends (it averages each line's colour, not its
    brightness, with the line above);
  * the ghost byte: inside the display window the VIC draws its idle byte
    ($3fff in the bank) where there is no character data, pixels set in
    black.  $55 blacks every other pixel; composite video blurs that into a
    darker shade of the bar's colour.  One write per bar block (at IRQ
    set-up), for distant bars and bars in the shadow past the ship.

The PAL CRT model, per frame, in the signal (gamma) domain: luma blurred
along the line with taps HY, chroma with the wider HC (composite video's
limited bandwidth), then the delay line averages each line's chroma with
the line above.  The eye then averages the two frames in linear light.
HY and HC are estimates: calibrate them in VICE's CRT emulation, which has
PAL delay-line blending and blur.

The colours: each bar line picks one of the 51 flicker candidates, top to
bottom, knowing the line above (for the delay line) and whether its bar is
ghosted, by error diffusion in linear light (the error left on one line
carries to the next, capped at EMAX so it can't run away, so lines
alternate into in-between shades).  A
brightness jump of more than one level between lines is penalised: PAL
doesn't blend brightness, so it would show as stripes.

    python3 interlace.py [frames_dir]
        # preview_interlace.png (bands), preview_interlace.gif (fly-by, three
        # ways, as a PAL CRT shows them), and in frames_dir each moment's two
        # frames sharp and through the CRT model, for a live web page
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ship3d

HERE = os.path.dirname(os.path.abspath(__file__))
HY = np.array([0.2, 0.6, 0.2])                 # luma blur along the line
HC = np.array([0.1, 0.2, 0.4, 0.2, 0.1])       # chroma blur (wider)
GHOST_BELOW = 0.55                             # bars dimmer than this: ghost byte
KDIFF = 0.7                                    # error carried to the next line
EMAX = 0.05                                    # ... at most this (linear light),
                                               # so it nudges between shades
                                               # and can't run away
NC = len(fl.CANDS)
LUMA = np.array(fl.LUMA)

# ---- the PAL CRT model ------------------------------------------------------------------
def to_yuv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    return np.stack([y, 0.492 * (b - y), 0.877 * (r - y)], axis=-1)

def to_rgb(yuv):
    y, u, v = yuv[..., 0], yuv[..., 1], yuv[..., 2]
    r = y + v / 0.877
    b = y + u / 0.492
    g = (y - 0.299 * r - 0.114 * b) / 0.587
    return np.stack([r, g, b], axis=-1)

def hfilter(a, taps):
    """Filter along the line (axis -2), wrapping round (a period divides it)."""
    k = len(taps) // 2
    return sum(t * np.roll(a, i - k, axis=-2) for i, t in enumerate(taps))

def crt(frame):
    """One frame (H x W x 3 sRGB, 0..255) as a PAL CRT shows it (sRGB)."""
    yuv = to_yuv(frame / 255.0)
    y = hfilter(yuv[..., :1], HY)
    uv = hfilter(yuv[..., 1:], HC)
    uv[1:] = (uv[1:] + uv[:-1]) / 2                 # the delay line
    return np.clip(to_rgb(np.concatenate([y, uv], -1)), 0, 1) * 255

def seen(frames):
    """Frames shown in turn, through the CRT and the eye (sRGB uint8)."""
    return fl.perceived([crt(f.astype(float)) for f in frames])

# ---- choosing the colours, line by line ---------------------------------------------------
CA, CB = fl.CA, fl.CB
PX = 8                                           # pixels in the model's line patch
GHOSTMASK = (np.arange(PX) % 2 == 1)             # $55: odd pixels black

def patch_lin(cur, prev, ghost, pghost):
    """The light (linear, mean over a line patch) a line shows in one frame:
    cur (N x 3 sRGB) over prev (3 sRGB), each ghosted or not."""
    n = cur.shape[0]
    c = np.repeat(cur[:, None, :], PX, axis=1) / 255.0
    p = np.repeat(np.asarray(prev, float)[None, None, :], PX, axis=1) / 255.0
    if ghost:
        c[:, GHOSTMASK] = 0
    if pghost:
        p[:, GHOSTMASK] = 0
    cy, py = to_yuv(c), to_yuv(p)
    y = hfilter(cy[..., :1], HY)
    uv = (hfilter(cy[..., 1:], HC) + hfilter(py[..., 1:], HC)) / 2
    rgb = np.clip(to_rgb(np.concatenate([y, uv], -1)), 0, 1)
    return (rgb ** fl.GAMMA).mean(axis=1)         # N x 3 linear

def redmean(a, b):
    d = a - b
    rm = (a[..., 0] + b[..., 0]) / 2
    return (2 + rm / 256) * d[..., 0] ** 2 + 4 * d[..., 1] ** 2 + (2 + (255 - rm) / 256) * d[..., 2] ** 2

def choose_column(targets, bar, ghost_of, mode):
    """Per screen line: (colour on even frames, on odd frames).
    targets: H x 3 linear light; bar: H ints (-1: no bar);
    ghost_of: per bar, ghosted?  mode: 'single' (16 colours), 'flicker'
    (51, nearest each), 'full' (51 + lines + ghost, error-diffused)."""
    H = len(targets)
    out = np.zeros((H, 2), int)
    ghosted = np.zeros(H, bool)
    err = np.zeros(3)
    prev = [np.zeros(3), np.zeros(3)]                # sRGB shown on the line above
    pghost = False
    cands = np.arange(16) if mode == "single" else np.arange(NC)
    for y in range(H):
        if bar[y] < 0:
            out[y] = 0
            err[:] = 0
            prev = [np.zeros(3), np.zeros(3)]
            pghost = False
            continue
        g = mode == "full" and ghost_of[bar[y]]
        want = targets[y] + (KDIFF * err if mode == "full" else 0)
        sw = fl.srgb(np.clip(want, 0, 1))
        # each candidate's colours on this line in frames 0 and 1 (phase by line)
        a = np.where((y % 2) == 0, CA[cands], CB[cands])
        b = np.where((y % 2) == 0, CB[cands], CA[cands])
        if mode == "full":
            l0 = patch_lin(fb.C64RGB[a], prev[0], g, pghost)
            l1 = patch_lin(fb.C64RGB[b], prev[1], g, pghost)
            light = (l0 + l1) / 2
        else:
            light = (fl.lin(fb.C64RGB[a]) + fl.lin(fb.C64RGB[b])) / 2
        cost = redmean(fl.srgb(light), sw) * fl.CCOST[cands] ** 2
        if mode == "full" and y > 0 and bar[y - 1] == bar[y]:
            # brightness jumps between neighbouring lines show as stripes
            jump = np.maximum(np.abs(LUMA[a] - LUMA[out[y - 1, 0]]),
                              np.abs(LUMA[b] - LUMA[out[y - 1, 1]]))
            cost = cost * (1 + 0.6 * np.maximum(jump - 1, 0)) ** 2
        k = int(np.argmin(cost))
        out[y] = (a[k], b[k])
        ghosted[y] = g
        err = np.clip(want - light[k], -EMAX, EMAX)
        prev = [fb.C64RGB[a[k]], fb.C64RGB[b[k]]]
        pghost = g
    return out, ghosted

# ---- frames ----------------------------------------------------------------------------------
def line_targets(bars):
    """Per screen line of the middle column: target light (linear), the bar
    covering it (-1 none), and each bar's distance."""
    dx, dy = fb.rays(cols=[fb.W // 2])
    zb = np.full(dx.shape, np.inf)
    col = np.zeros(dx.shape + (3,))
    who = np.full(dx.shape, -1)
    for i, (yc, zc, colours) in enumerate(bars):
        z, c = fb.cylinder(dx, dy, yc, zc, colours, fb.bright(zc))
        m = z < zb
        zb[m], col[m], who[m] = z[m], c[m], i
    lin = fl.lin(col).reshape(fb.H, fb.SS, -1, 3).mean(axis=(1, 2))
    w = who.reshape(fb.H, -1)
    bar = np.array([np.bincount(r[r >= 0], minlength=1).argmax() if (r >= 0).mean() >= 0.5 else -1
                    for r in w])
    return lin, bar

def frames_for(bars, mode, ship0, ship1):
    """The two frames (sRGB uint8) a mode shows for these bars, ship on top."""
    lin, bar = line_targets(bars)
    ghost_of = [fb.bright(zc) < GHOST_BELOW for _, zc, _ in bars]
    cols, ghosted = choose_column(lin, bar, ghost_of, mode)
    out = []
    for f in range(2):
        img = np.repeat(fb.C64RGB[cols[:, f]][:, None, :], fb.W, axis=1).astype(np.uint8)
        gx = np.arange(fb.W) % 2 == 1
        img[np.ix_(ghosted, gx)] = 0                  # the ghost byte's black pixels
        fl.draw_ship(img, ship0 if f == 0 else ship1)
        out.append(img)
    return out

def scene_bars(f):
    return [(yc, fb.zof((f + st) % fb.FLYD), fb.bands48(pal)) for pal, yc, st in fl.FLIGHTS]

# ---- outputs ---------------------------------------------------------------------------------
def animation(path, frames_dir=None, step=3, dir_step=4):
    font, small = fl.fonts()
    single = ship3d.render(0, 0)
    s0, s1 = fl.ship_pair(0, 0)
    W2, H2 = fb.W * 2, fb.H * 2
    out = []
    if frames_dir:
        os.makedirs(frames_dir, exist_ok=True)
    for f in range(0, fb.FLYD, step):
        bars = scene_bars(f)
        panels = []
        for mode, sh, text in (("single", (single, single), "16 colours"),
                               ("flicker", (s0, s1), "flicker"),
                               ("full", (s0, s1), "flicker + lines + ghost byte")):
            fr = frames_for(bars, mode, *sh)
            im = Image.fromarray(seen(fr)).resize((W2, H2), Image.LANCZOS)
            panels.append(fl.label(im, text + " (PAL CRT, as seen)", small))
            if mode == "full" and frames_dir and f % dir_step == 0:
                k = f // dir_step
                for nm, img in (("e", fr[0]), ("o", fr[1])):
                    fl.save_png(img, os.path.join(frames_dir, f"s{nm}{k:03d}.png"))
                    fl.save_png(crt(img.astype(float)).astype(np.uint8),
                                os.path.join(frames_dir, f"c{nm}{k:03d}.png"))
        both = Image.new("RGB", (W2 * 3 + 16, H2), (20, 20, 28))
        for i, p in enumerate(panels):
            both.paste(p, (i * (W2 + 8), 0))
        out.append(both)
    out[0].save(path, save_all=True, append_images=out[1:], duration=60, loop=0)

def sheet(path):
    """Each palette's 48 bands at 100, 50 and 25% brightness: target, then
    the three ways as a PAL CRT shows them, then the sharp pixels of the
    combined way's two frames."""
    font, small = fl.fonts()
    RH = 8                         # screen lines per band
    rows = ["target", "16 colours", "flicker", "flicker + lines + ghost",
            "  its frame 0, sharp", "  its frame 1, sharp"]
    panels = []
    for name, pal in fb.PALETTES:
        for bri in (1.0, 0.5, 0.25):
            # a column of 48 * RH lines: each band RH lines tall
            tgt = fl.lin(np.repeat(fb.bands48(pal), RH, axis=0) * bri)
            bar = np.zeros(len(tgt), int)
            ghost_of = [bri < GHOST_BELOW]
            strips = [fl.srgb(tgt)]
            for mode in ("single", "flicker", "full"):
                cols, gh = choose_column(tgt, bar, ghost_of, mode)
                fr = []
                for f in range(2):
                    img = np.repeat(fb.C64RGB[cols[:, f]][:, None, :], 22, axis=1).astype(np.uint8)
                    img[np.ix_(gh, np.arange(22) % 2 == 1)] = 0
                    fr.append(img)
                strips.append(seen(fr).mean(axis=1))
                if mode == "full":
                    raw = fr
            strips += [raw[0], raw[1]]
            panels.append((f"{name} {int(bri * 100)}%", strips))
    # one row of panels (palette x brightness), each its 6 strips side by side
    SW, GAP, PG = 22, 3, 24
    pw = len(rows) * (SW + GAP) + PG
    Wd = 20 + len(panels) * pw
    top = 96
    im = Image.new("RGB", (Wd, top + 48 * RH + 20), (14, 14, 22))
    dr = ImageDraw.Draw(im)
    dr.text((10, 8), "48 bands per palette, top to bottom, as a PAL CRT shows them. In each panel, "
            "left to right:", fill=(220, 220, 230), font=font)
    dr.text((10, 32), "  1 target   2 16 colours   3 flicker   4 flicker + alternating lines + "
            "ghost byte   5-6 that one's two frames, sharp pixels (as an emulator shows them)",
            fill=(170, 170, 190), font=small)
    for n, (label_, strips) in enumerate(panels):
        x = 20 + n * pw
        dr.text((x, top - 26), label_, fill=(220, 220, 230), font=small)
        for i, st in enumerate(strips):
            x0 = x + i * (SW + GAP)
            if st.ndim == 3:                       # sharp frame: the real pixels
                im.paste(Image.fromarray(st[:, :SW]), (x0, top))
            else:
                for j, c in enumerate(st):
                    dr.line([x0, top + j, x0 + SW - 1, top + j], fill=tuple(int(v) for v in c))
    im.save(path)

if __name__ == "__main__":
    sheet(os.path.join(HERE, "preview_interlace.png"))
    print("wrote preview_interlace.png")
    animation(os.path.join(HERE, "preview_interlace.gif"),
              frames_dir=sys.argv[1] if len(sys.argv) > 1 else None)
    print("wrote preview_interlace.gif")
