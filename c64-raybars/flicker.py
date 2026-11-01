#!/usr/bin/env python3
"""Flicker colours: two C64 colours shown on alternate frames, 50 times a
second, which the eye blends into a colour the C64 doesn't have.  A study
for GOLDSHIP's bars and ship, built on flyby3d.py's true-perspective
renders.

Colours.  The 16 colours sit on 9 brightness (luma) levels; a pair on the
same level barely flickers, a pair one level apart a little more.  Those
pairs give 7 + 28 mixes on top of the 16 colours: 51 in all.  A pair's
colour is the average of the two in linear light (a CRT's phosphor and the
eye add light, not sRGB values).  Neighbouring rows alternate in opposite
phase (row parity XOR frame parity), which halves the visible flicker.

Bars.  Each decimated pixel takes the nearest of the 51 colours (a pair one
level apart counts 15% farther, for its flicker).  In the game this costs
no cycles: the bars are rebuilt every frame, so the even and odd frames
would just copy different lists (twice the colour-table memory).

Ship.  Two sprite frames per attitude, alternated every frame (a sprite
pointer change): an edge pixel half covered by the hull is lit in one frame
only, so it shows at half strength; a pixel split between shadowed and lit
hull alternates purple and light blue.

    python3 flicker.py    # preview_flicker.png (swatches, bars, ship),
                          # preview_flicker.gif (the fly-by, as seen),
                          # preview_flicker_50hz.gif (the real alternation)
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import flyby3d as fb
import ship3d

HERE = os.path.dirname(os.path.abspath(__file__))
# brightness levels of the 16 colours (Pepto's measurements)
LUMA = [0, 8, 2, 6, 3, 5, 1, 7, 3, 1, 5, 2, 4, 6, 4, 7]
NAMES = ["black", "white", "red", "cyan", "purple", "green", "blue", "yellow", "orange",
         "brown", "light red", "dark grey", "grey", "light green", "light blue", "light grey"]
GAMMA = 2.2
ADJ_COST = 1.15                 # a pair one level apart: its flicker counts

def lin(rgb):
    return (np.asarray(rgb, float) / 255) ** GAMMA

def srgb(l):
    return np.clip(l, 0, 1) ** (1 / GAMMA) * 255

def mix(a, b):
    """The colour the eye sees from colours a and b on alternate frames."""
    return srgb((lin(fb.C64RGB[a]) + lin(fb.C64RGB[b])) / 2)

# the candidate colours: (a, b, perceived rgb, cost factor)
CANDS = [(c, c, fb.C64RGB[c], 1.0) for c in range(16)]
for a in range(16):
    for b in range(a + 1, 16):
        d = abs(LUMA[a] - LUMA[b])
        if d <= 1:
            CANDS.append((a, b, mix(a, b), 1.0 if d == 0 else ADJ_COST))
CA = np.array([c[0] for c in CANDS])
CB = np.array([c[1] for c in CANDS])
CRGB = np.array([c[2] for c in CANDS])
CCOST = np.array([c[3] for c in CANDS])

def nearest_pair(rgb):
    """Index into CANDS of the nearest candidate per pixel (redmean)."""
    r = np.asarray(rgb, float)[..., None, :]
    d = r - CRGB
    rm = (r[..., 0] + CRGB[:, 0]) / 2
    dist = (2 + rm / 256) * d[..., 0] ** 2 + 4 * d[..., 1] ** 2 + (2 + (255 - rm) / 256) * d[..., 2] ** 2
    return np.argmin(dist * CCOST ** 2, axis=-1)

def decimate_pairs(img):
    """Hi-res samples -> per pixel (colour on even frames, colour on odd
    frames), the two swapped on odd rows."""
    h, w = img.shape[0] // fb.SS, img.shape[1] // fb.SS
    avg = img.reshape(h, fb.SS, w, fb.SS, 3).mean(axis=(1, 3))
    k = nearest_pair(avg)
    a, b = CA[k], CB[k]
    odd = (np.arange(h) % 2 == 1)[:, None]
    return np.where(odd, b, a), np.where(odd, a, b)

# ---- the ship: two frames per attitude ----------------------------------------------
def ship_pair(roll, pitch):
    """Two 21 x 12 class frames whose alternation antialiases the ship."""
    counts = ship3d.sample_counts(roll, pitch)
    single = ship3d.render(roll, pitch)
    tot = ship3d.SX * ship3d.SY
    f0 = [[0] * 12 for _ in range(21)]
    f1 = [[0] * 12 for _ in range(21)]
    for r in range(21):
        for c in range(12):
            n0, n1, n2, n3 = counts[r][c]
            cov = (n1 + n2 + n3) / tot
            hull = n1 + n2
            col = 2 if n2 >= n1 else 1
            split = hull and min(n1, n2) >= 0.3 * hull
            if n3 * 5 >= tot:
                f0[r][c] = f1[r][c] = 3
            elif cov >= 0.7:
                f0[r][c], f1[r][c] = (1, 2) if split else (col, col)
                if n3 * 12 >= tot:                   # a touch of glow: half
                    f0[r][c] = 3
            elif cov >= 0.25 or single[r][c]:
                # half covered (or kept to bridge a gap): one frame of two,
                # in a checkerboard so each frame carries half the edge
                v = 3 if n3 > hull else col
                if (r + c) % 2:
                    f1[r][c] = v
                else:
                    f0[r][c] = v
    return f0, f1

SHIPPAL = {1: (0x8A, 0x46, 0xAE), 2: (0x7C, 0x70, 0xDA), 3: (0xFF, 0xFF, 0xFF)}

def draw_ship(rgb, frame):
    """Paint a 21 x 12 class frame at the window's centre."""
    for r, row in enumerate(frame):
        for c, v in enumerate(row):
            if v:
                y, x = fb.CY - 10 + r, fb.W // 2 - 12 + 2 * c
                rgb[y, x:x + 2] = SHIPPAL[v]

def perceived(frames):
    """Frames shown in turn -> the colour the eye sees (linear-light mean)."""
    return srgb(np.mean([lin(f) for f in frames], axis=0)).astype(np.uint8)

# ---- outputs ----------------------------------------------------------------------------
FLIGHTS = [(fb.GOLD, -0.30, 0), (fb.P2, 0.48, 80), (fb.P3, -0.66, 160)]

def scene(f):
    bars = [(yc, fb.zof((f + st) % fb.FLYD), fb.bands48(pal)) for pal, yc, st in FLIGHTS]
    return fb.frame(bars, with_ship=False)

def both_versions(img, ship_single, ship0, ship1):
    """The current single-colour picture, and the flicker version's two
    frames."""
    single = fb.C64RGB[fb.decimate(img)].astype(np.uint8)
    draw_ship(single, ship_single)
    e, o = decimate_pairs(img)
    fe = fb.C64RGB[e].astype(np.uint8)
    fo = fb.C64RGB[o].astype(np.uint8)
    draw_ship(fe, ship0)
    draw_ship(fo, ship1)
    return single, fe, fo

def label(img, text, font):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, 22], fill=(14, 14, 22))
    d.text((8, 3), text, fill=(220, 220, 230), font=font)
    return img

def fonts():
    try:
        return (ImageFont.truetype("DejaVuSans-Bold.ttf", 16),
                ImageFont.truetype("DejaVuSans.ttf", 13))
    except OSError:
        f = ImageFont.load_default()
        return f, f

def animations(path, path50, step=3):
    font, small = fonts()
    single_ship = ship3d.render(0, 0)
    s0, s1 = ship_pair(0, 0)
    out, keep = [], None
    for f in range(0, fb.FLYD, step):
        img = scene(f)
        single, fe, fo = both_versions(img, single_ship, s0, s1)
        W2, H2 = fb.W * 2, fb.H * 2
        a = label(Image.fromarray(single).resize((W2, H2), Image.NEAREST),
                  "now: 16 colours", small)
        b = label(Image.fromarray(perceived([fe, fo])).resize((W2, H2), Image.NEAREST),
                  "flicker colours, as seen", small)
        both = Image.new("RGB", (W2 * 2 + 8, H2), (20, 20, 28))
        both.paste(a, (0, 0))
        both.paste(b, (W2 + 8, 0))
        out.append(both)
        if f == 48:
            keep = (fe, fo)
    out[0].save(path, save_all=True, append_images=out[1:], duration=60, loop=0)
    # the real thing: the two frames alternating at 50 Hz (20 ms each)
    fe, fo = keep
    frames = [Image.fromarray(x).resize((fb.W * 2, fb.H * 2), Image.NEAREST) for x in (fe, fo)]
    frames[0].save(path50, save_all=True, append_images=frames[1:], duration=20, loop=0)

def sheet(path):
    font, small = fonts()
    SW = 34
    lv_groups = {}
    for i, (a, b, rgb, cost) in enumerate(CANDS):
        key = (LUMA[a] + LUMA[b]) / 2
        lv_groups.setdefault(key, []).append(i)
    rows = sorted(lv_groups)
    Wd = 1520
    y = 10
    im = Image.new("RGB", (Wd, 2400), (14, 14, 22))
    dr = ImageDraw.Draw(im)
    dr.text((10, y), f"The colours: 16 C64 colours + {len(CANDS) - 16} flicker pairs "
            f"({len(CANDS)} in all), by brightness level; a dot marks pairs one level apart",
            fill=(220, 220, 230), font=font)
    y += 30
    for key in rows:
        dr.text((10, y + 8), f"level {key:g}", fill=(160, 160, 180), font=small)
        x = 90
        for i in lv_groups[key]:
            a, b, rgb, cost = CANDS[i]
            dr.rectangle([x, y, x + SW - 1, y + SW - 1], fill=tuple(int(v) for v in rgb))
            if a != b and cost > 1:
                dr.ellipse([x + SW // 2 - 2, y + SW - 7, x + SW // 2 + 2, y + SW - 3],
                           fill=(20, 20, 20))
            x += SW + 6
        y += SW + 8
    y += 16
    # the bars' 48 bands: target, nearest single colour, nearest flicker colour
    dr.text((10, y), "The palettes' 48 bands, at full brightness and at half: "
            "target | 16 colours | flicker colours (as seen)", fill=(220, 220, 230), font=font)
    y += 30
    BW = 22
    for name, pal in fb.PALETTES:
        for bri in (1.0, 0.5):
            t = fb.bands48(pal) * bri
            single = fb.C64RGB[fb.to_c64(t)]
            fl = CRGB[nearest_pair(t)]
            dr.text((10, y + 18), f"{name} {int(bri * 100)}%", fill=(160, 160, 180), font=small)
            for row, cols in enumerate((t, single, fl)):
                for i, c in enumerate(cols):
                    x = 110 + i * BW
                    dr.rectangle([x, y + row * 16, x + BW - 1, y + row * 16 + 14],
                                 fill=tuple(int(v) for v in c))
            y += 3 * 16 + 12
    y += 16
    # the ship: single frame vs the flicker pair (as seen), 9 attitudes
    dr.text((10, y), "The ship: one frame (now) vs two alternating frames (as seen), "
            "at 6x", fill=(220, 220, 230), font=font)
    y += 30
    Z = 6
    for row, name in enumerate(("now", "flicker")):
        dr.text((10, y + 50), name, fill=(160, 160, 180), font=small)
        for k, (rr, pp) in enumerate(ship3d.ATT):
            if name == "now":
                fr = [ship3d.render(rr * ship3d.R, pp * ship3d.P)]
            else:
                fr = list(ship_pair(rr * ship3d.R, pp * ship3d.P))
            imgs = []
            for f in fr:
                a = np.zeros((21, 24, 3), np.uint8)
                for r, line in enumerate(f):
                    for c, v in enumerate(line):
                        if v:
                            a[r, 2 * c:2 * c + 2] = SHIPPAL[v]
                imgs.append(a)
            p = perceived(imgs)
            im.paste(Image.fromarray(p).resize((24 * Z, 21 * Z), Image.NEAREST),
                     (110 + k * (24 * Z + 10), y))
        y += 21 * Z + 14
    im.crop((0, 0, Wd, y + 10)).save(path)

if __name__ == "__main__":
    print(f"{len(CANDS)} colours: 16 + {sum(1 for c in CANDS if c[0] != c[1] and c[3] == 1)} "
          f"same-level pairs + {sum(1 for c in CANDS if c[3] > 1)} pairs one level apart")
    sheet(os.path.join(HERE, "preview_flicker.png"))
    print("wrote preview_flicker.png")
    animations(os.path.join(HERE, "preview_flicker.gif"), os.path.join(HERE, "preview_flicker_50hz.gif"))
    print("wrote preview_flicker.gif, preview_flicker_50hz.gif")
