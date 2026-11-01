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

    python3 jitter_video.py out.mp4 [fps]     # default 60
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
OPTIONS = [("No jitter: rounded offsets", None, None),
           ("All lines, sawtooth 0-8-16-24 px", SAW4, "all"),
           ("All lines, sawtooth 0-8-16 px", SAW3, "all"),
           ("Top and bottom lines only, sawtooth 0-8-16-24 px", SAW4, "rows"),
           ("Top and bottom lines only, sawtooth 0-8-16 px", SAW3, "rows")]
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

def main(path, fps=60):
    recs, ship = fv.record(0, fv.bank(), ("notilt",))
    frames = [np.frombuffer(b, np.uint8).reshape(6, fb.H) for b in recs["notilt"]]
    pairs = ship_aa.pairs()
    top = int(fb.CY - 26 / fb.zof(fv.BANK_T)) - 14
    bot = fb.CY + 13
    sh_, sw_ = (bot - top) * Z, fb.W * Z
    lab = 26
    Wv, Hv = sw_ + 32, len(OPTIONS) * (sh_ + lab) + 16
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
            for i, (text, seq, where) in enumerate(OPTIONS):
                img = frame_image(frames[k], k, pair, seq, where)
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
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 60)
