# RAYBARS: ray-traced raster bars for the C64

Four chrome cylinders orbit the screen's X axis. Each one is shaded every
frame with a diffuse term, a 1-D environment map and a Phong specular
highlight from a single point light. The CPU only has to write one
register per scanline, so almost all of its time goes to the shading maths.

![preview](preview.gif)

## Build and run

```sh
python3 gen_tables.py                                   # optional: tables.inc and ramps.inc are committed
cl65 -t none -C raybars.cfg -o raybars.prg raybars.s   # add --asm-define STYLE=0 for the dithered look
x64sc raybars.prg                                        # VICE, PAL machine
```

`simulate.py` runs the real binary's per-frame tracer on an emulated 6502
(`pip install py65 pillow`, and build with `-g -Ln raybars.lbl`). It checks
the cycle budget and the 63-cycle raster loop, and renders `preview.gif` and
`preview.png`. The GIF's left half shows the raw scanlines. The right half
roughly approximates how a PAL TV blends neighbouring lines. The preview
uses VICE's default palette, the one the article uses.

## How it works, step by step

1. **A raster bar is a cylinder seen side-on.** In the y/z plane each scanline
   `i` of a bar with radius `R` is a point on a circle, and its normal is at
   angle `t_i` where `sin t_i = (i + 0.5 - R) / R`. That depends only on `i`,
   so the normals of every bar make up one constant 32-byte table.
2. **The camera is at infinity (orthographic).** The view vector is always
   `(0,0,1)`, so there is no perspective divide and V never needs computing.
3. **Angles are stored in brads** (256 to a circle). Sums of angles wrap
   naturally in 8 bits, and every trig function is a 256-byte table.
4. **The lighting reduces to sums of angles.** With the light at angle `p`:
   * diffuse: `N·L = cos(t − p)`
   * specular: the reflected light, dotted with V, raised to the power n, which is `cos(2t − p)^n`
   * environment: the reflected view ray points at angle `2t`, so the lookup is `env[2t + spin]`
5. **The light uses a log-table atan2.** There is one light, at fixed depth
   `LZ = 100`. The bars orbit with |y| ≤ 64 and |z| ≤ 40, and the light bobs
   ±44, so `dy` always fits in a signed byte and `dz` is always 60..140. Then
   `atan(dy/dz) = atan(2^(log2 dy − log2 dz))`, which turns the division into
   a subtraction. It is evaluated once per bar, at the bar's axis, which
   works because R = 16 is small next to the light distance.
6. **Indexing uses doubled, page-aligned tables.** The tables are 512 bytes
   each, so `table[t − p]` becomes `lda table+(−p),x`, with `−p` patched into
   the operand once per bar. The inner loop takes about 39 cycles per
   scanline.
7. **Colour uses a stretched palette.** This follows Daniel Krajzewicz's
   [Stretching the c64 Palette](https://www.krajzewicz.de/blog/stretching-the-c64-palette.php).
   * **Multichrome ramps.** Each ramp takes one colour from each of the
     VIC-II's brightness levels, whatever its hue, so it gets every
     brightness step the chip has. These are the article's four
     multichrome gradients, with their white end dropped:
     * Fire: black, brown, red, orange, light red, light grey, yellow
     * Ocean: black, blue, dark grey, purple, light blue, cyan, light green
     * Forest: black, brown, dark grey, orange, green, light grey, light green
     * Dusk: black, blue, dark grey, purple, light red, cyan, yellow
   * **`STYLE=1` (default), the article's "scaled split".** Two lines of
     colour, then one black line, counted outwards from each bar's centre.
     The black lines belong to the bar, so they also cover the bars
     behind it.
   * **`STYLE=0`, the article's "Poor Man's Dithering" at scale 2.**
     Between neighbouring colours there is a mixed step: the two colours on
     alternating scanlines, which a PAL TV blends, so 7 colours give 13
     steps. The shading loop is unrolled by two, so even and odd lines read
     their own ramp table. `FLICKER=1` also swaps each pair every frame,
     which looks smoother on a sharp LCD or emulator but flickers.
   * **Correct widths.** The article notes that hand-made patterns never
     give each brightness its correct width. Here the widths come from the
     cosine shading, so the bars actually look round.
   * **Intensity** is diffuse (0..10) + env (0..2) + specular (0..6).
     Diffuse plus env tops out at 12, the brightest bar colour, so only the
     specular term reaches **white**.
8. **Bars are drawn back to front.** A 4-element sorting network orders them
   by depth, and the painter's algorithm handles the crossings.
9. **The screen is blanked (DEN=0).** With the display off there are no
   badlines, so after a double-IRQ stable raster the display is a plain
   63-cycle loop writing `$d020`, and the whole screen is border. The display
   is 184 lines tall. The tracer uses about 6,800 of the roughly 7,800
   vblank cycles (87%).

## Tuning notes

* PAL only: the loop is 63 cycles per line, and an NTSC frame has too little vblank.
* `HTUNE` adds NOPs after the stable-raster code. If you see a step where
  the colour changes partway across a line, adjust it until the switch
  falls inside horizontal blank.
* Everything else (`R`, the orbit amplitudes, the light depth, the Phong
  exponent and the env map) is in `gen_tables.py` and at the top of `raybars.s`.
  Keep `R` in sync between the two files.
