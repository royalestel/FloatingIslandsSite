#!/usr/bin/env python3
"""The ship flying over a gold bar, the camera orbited YAW degrees round the
ship (default 45): the bar comes from far ahead, passes under the ship (its
top edge GAP lines below the ship's centre) and goes on past the camera.
Left: the true 3D render; right: the C64 version (6 raster splits a line,
sprite ship), CRT look.  60 fps, one C64 frame per video frame, the bar
moving 0.045 m a frame (the game's base speed).

    python3 orbit_video.py out.mp4 [yaw] [from_dz] [to_dz]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
import flyby3d as fb
import flicker as fl
import ideas_video as iv
import loop_video as lv
import orbit_shots as o

SPEED = 0.045

def main(path, yaw=45.0, dz0=7.0, dz1=-2.5):
    Z = 2
    W, H = fb.W * Z, fb.H * Z
    font, small = fl.fonts()
    v = iv.Video(path, 2 * W + 48, H + 70)
    n = int((dz0 - dz1) / SPEED)
    last = None
    for f in range(n):
        dz = dz0 - f * SPEED
        o.BARZ = o.ZS + dz                    # the bar's distance from the ship's plane
        true, c64, box = o.shot(yaw)
        rgb = fb.C64RGB[c64].astype(np.uint8)
        a = Image.fromarray(np.clip(true, 0, 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
        b = lv.crt_look(rgb, Z)
        canvas = Image.new("RGB", (v.w, v.h), (8, 8, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((16, 8), f"camera orbited {yaw:g} degrees round the ship; the bar passes under it   "
                f"{dz:+.2f} m", fill=(170, 176, 210), font=small)
        dr.text((16, 38), "3D render", fill=(200, 205, 230), font=small)
        dr.text((32 + W, 38), "C64: raster splits + sprites, CRT", fill=(200, 205, 230), font=small)
        canvas.paste(a, (16, 56))
        canvas.paste(b, (32 + W, 56))
        v.add(canvas)
        last = canvas
        if f % 40 == 0:
            print("frame", f, "of", n, flush=True)
    for _ in range(30):
        v.add(last)
    v.close()
    print("wrote", path, n, "frames")

if __name__ == "__main__":
    a = sys.argv
    main(a[1], float(a[2]) if len(a) > 2 else 45.0,
         float(a[3]) if len(a) > 3 else 7.0, float(a[4]) if len(a) > 4 else -2.5)
