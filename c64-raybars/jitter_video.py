#!/usr/bin/env python3
"""The split-jitter banking demo as a video file, for steady frame pacing
(a video player paces frames better than a web page).

One bar held at a fixed distance while the ship banks slowly left and right
(flight_video.bank), shown five ways, stacked:
  no jitter (rounded offsets);
  all lines, sawtooth 0-8-16-24 px and 0-8-16 px;
  top and bottom lines only (whole stair rows: lines where some segments
  show the bar and others black), sawtooth 0-8-16-24 px and 0-8-16 px.
A step of jitter delays a row's start one cycle: its five inner splits land
8 px further right.  One C64 frame per video frame, through interlace.py's
PAL CRT model.

    python3 jitter_video.py out.mp4 [fps]         # default 60
    python3 jitter_video.py out.mp4 60 extra      # the flickering extra line
    python3 jitter_video.py out.mp4 60 ghost      # ... ghosted
"""
import subprocess, sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flight_video as fv
import interlace as il
import mockup as mk
import ship_aa

SAW4, SAW3 = [0, 1, 2, 3], [0, 1, 2]
OPTIONS = [("No jitter: rounded offsets", None, None, None),
           ("All lines, sawtooth 0-8-16-24 px", SAW4, "all", None),
           ("All lines, sawtooth 0-8-16 px", SAW3, "all", None),
           ("Top and bottom lines only, sawtooth 0-8-16-24 px", SAW4, "rows", None),
           ("Top and bottom lines only, sawtooth 0-8-16 px", SAW3, "rows", None)]
# the flickering extra line: while the bar is tilted, each segment shows one
# more line of the bar's edge colour above its top (and below its bottom),
# on even frames only, so it shows at half strength
EXTRA = [("Rounded offsets, no extra line", None, None, None),
         ("Tilted: an extra line above each segment, on alternate frames", None, None, "above"),
         ("Tilted: extra lines above and below each segment, on alternate frames", None, None, "both")]

# the extra line ghosted (the idle byte $55: every other pixel black).  The
# idle byte is one byte for the whole line, so "segment" (the ghost on the
# extra line's own segment only) is the ideal; "line" ghosts the whole line
# where any segment's extra line falls, dimming the bar rows beside it too
# (what the program could do, writing $bfff between chunks of rows)
GHOST = [("Rounded offsets, no extra line", None, None, None),
         ("Extra lines above and below, ghosted, on alternate frames (ideal: own segment only)",
          None, None, dict(where="both", ghost="segment")),
         ("Extra lines above and below, ghosted, every frame (ideal: own segment only)",
          None, None, dict(where="both", ghost="segment", steady=True)),
         ("Extra lines above and below, ghosted, on alternate frames (practical: whole line)",
          None, None, dict(where="both", ghost="line")),
         ("Extra lines above and below, not ghosted, on alternate frames (last video)",
          None, None, dict(where="both"))]

def add_extra(cols, k, roll, extra):
    """The segment columns with the flickering extra line(s) added."""
    if isinstance(extra, str):
        extra = dict(where=extra)
    if not extra or roll == 0 or (k & 1 and not extra.get("steady")):
        return cols
    ghost = 16 if extra.get("ghost") else 0
    lines = set()
    out = cols.copy()
    on = (cols & 15) != 0
    for s in range(6):
        ys = np.flatnonzero(on[s])
        if not len(ys):
            continue
        # the bars' extents: lit lines, gaps under 3 lines (dark rows inside
        # a bar) bridged
        runs, a = [], ys[0]
        for p, q in zip(ys, ys[1:]):
            if q - p > 3:
                runs.append((a, p))
                a = q
        runs.append((a, ys[-1]))
        for a, b in runs:
            if a > 0:
                out[s, a - 1] = cols[s, a] | ghost          # above its top
                lines.add(a - 1)
            if extra["where"] == "both" and b + 1 < fb.H:
                out[s, b + 1] = cols[s, b] | ghost          # below its bottom
                lines.add(b + 1)
    if extra.get("ghost") == "line":
        for y in lines:
            out[:, y] |= 16
    return out
SHIPPAL = [fb.C64RGB[c] for c in (0, 4, 14, 1)]
Z = 3                                   # scale

def frame_image(cols, k, pair, seq, where):
    """One C64 frame of the window (sRGB, H x W): the six segments' colours
    per line, the ghost byte, the jitter, the ship."""
    W, H = fb.W, fb.H
    idx = np.zeros((H, W), int)
    on = (cols & 15) != 0
    d = 8 * seq[k % len(seq)] if seq else 0
    for y in range(H):
        stair = bool(on[:, y].any() and not on[:, y].all())
        sh = d if seq and (where == "all" or stair) else 0
        edges = [0] + [mk.SEGX[s] + sh for s in range(1, 6)] + [W]
        for s in range(6):
            v = cols[s, y]
            idx[y, edges[s]:edges[s + 1]] = v & 15
            if v & 16:                                  # the ghost byte
                idx[y, edges[s] + (1 - edges[s] % 2):edges[s + 1]:2] = 0
    img = fb.C64RGB[idx].astype(np.uint8)
    for r, line in enumerate(pair):
        for c, v in enumerate(line):
            if v:
                y, x = fb.CY - 10 + r, W // 2 - 12 + 2 * c
                img[y, x:x + 2] = SHIPPAL[v]
    return img

def main(path, fps=60, options=OPTIONS):
    recs, ship = fv.record(0, fv.bank(), ("notilt",))
    frames = [np.frombuffer(b, np.uint8).reshape(6, fb.H) for b in recs["notilt"]]
    pairs = ship_aa.pairs()
    top = int(fb.CY - 26 / fb.zof(fv.BANK_T)) - 14
    bot = fb.CY + 13
    sh_, sw_ = (bot - top) * Z, fb.W * Z
    lab = 26
    Wv, Hv = sw_ + 32, len(options) * (sh_ + lab) + 16
    Wv, Hv = Wv + Wv % 2, Hv + Hv % 2
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
                           "-pix_fmt", "rgb24", "-s", f"{Wv}x{Hv}", "-r", str(fps), "-i", "-",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "12",
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", path],
                          stdin=subprocess.PIPE)
    import flicker as fl
    font, small = fl.fonts()
    n = len(frames)
    for loop in range(2):
        for k in range(n):
            canvas = Image.new("RGB", (Wv, Hv), (11, 10, 18))
            dr = ImageDraw.Draw(canvas)
            pair = pairs[ship[k][0]][k & 1]
            for i, (text, seq, where, extra) in enumerate(options):
                cols = add_extra(frames[k], k, ship[k][3], extra)
                img = frame_image(cols, k, pair, seq, where)
                # (padded with black: the CRT model's blur wraps round)
                pad = np.pad(img[top - 1:bot], ((0, 0), (8, 8), (0, 0)))
                crop = il.crt(pad.astype(float))[1:, 8:-8].astype(np.uint8)
                y = 8 + i * (sh_ + lab)
                dr.text((16, y + 4), text, fill=(200, 196, 220), font=small)
                canvas.paste(Image.fromarray(crop).resize((sw_, sh_), Image.BILINEAR), (16, y + lab))
            ff.stdin.write(canvas.tobytes())
    ff.stdin.close()
    ff.wait()
    print(f"wrote {path}: {2 * n} frames at {fps} fps")

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 60,
         {"extra": EXTRA, "ghost": GHOST}.get(sys.argv[3] if len(sys.argv) > 3 else "", OPTIONS))
