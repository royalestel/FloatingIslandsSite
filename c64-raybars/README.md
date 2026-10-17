# RAYBARS: ray-traced raster bars for the C64

Three chrome cylinders orbit the screen's X axis. Each one is shaded every
frame with a diffuse term, a 1-D environment map and a Phong specular
highlight from a single point light. The CPU only has to write one
register per scanline, so almost all of its time goes to the shading maths.

![preview](preview.gif)

## Build and run

```sh
python3 gen_tables.py                                   # optional: tables.inc and ramps.inc are committed
cl65 -t none -C raybars.cfg -o raybars.prg raybars.s   # STYLE=2 (default) gold; --asm-define STYLE=0 or 1 for the shaded looks
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
     brightness step the chip has. These are three of the article's
     gradients, with their white end dropped:
     * Ocean: blue, dark grey, purple, light blue, cyan, light green
     * Forest: brown, dark grey, orange, green, light grey, light green
     * Dusk: blue, dark grey, purple, light red, cyan, yellow
   * **`STYLE=2` (default): the gold bar.** No shading of the bar colours
     at all. Each bar is 24 lines with a fixed hand-picked gold pattern, one
     colour per scanline, top to bottom:
     `9 8 12 7 7 0 9 8 15 7 7 1 7 1 7 0 0 0 9 12 10 12 8 9`.
     It works like a fixed environment map, so it doesn't shift as the bar
     moves. Only the white specular highlight is traced on top. Where the
     highlight is faint, white replaces gold on every other line
     (yellow/white alternating blends to light yellow). Where it is strong,
     it's solid white. The highlight covers every line, the black ones
     included. This style uses about 48% of the vblank.
   * **`STYLE=0`: dithering only where white used to be.** The
     bar's own colours are solid bands. Between the brightest bar colour
     and the white highlight, the two alternate on even and odd scanlines
     (the article's "Poor Man's Dithering"), which a PAL TV blends. The
     shading loop is unrolled by two, so even and odd lines read their own
     ramp table. `FLICKER=1` also swaps the pair every frame, which looks
     smoother on a sharp LCD or emulator but flickers.
   * **`STYLE=1`: the article's "scaled split".** Two lines of colour,
     then one black line, counted outwards from each bar's centre. The
     black lines belong to the bar, so they also cover the bars behind it.
   * **Correct widths.** The article notes that hand-made patterns never
     give each brightness its correct width. Here the widths come from the
     cosine shading, so the bars actually look round.
   * **Intensity** is diffuse (0..14) + env (0..2) + specular (0..8).
     Diffuse plus env tops out at 16, the brightest bar colour, so only the
     specular term reaches **white**.
8. **Bars are drawn back to front.** A 3-element sorting network orders them
   by depth, and the painter's algorithm handles the crossings.
9. **The screen is blanked (DEN=0).** With the display off there are no
   badlines, so after a double-IRQ stable raster the display is a plain
   63-cycle loop writing `$d020`, and the whole screen is border. The tracer
   uses about 5,000 of the roughly 6,800 vblank cycles (73%).

## GOLDTILT: one slanted gold bar

`goldtilt.s` is a separate program: one gold bar that bobs up and down and
rocks like a see-saw.

```sh
cl65 -t none -C raybars.cfg -o goldtilt.prg goldtilt.s
python3 sim_goldtilt.py      # needs -g -Ln goldtilt.lbl; renders preview_goldtilt.gif
```

* **Splitting each line.** A raster bar normally can't slant, because the
  colour only changes where the CPU writes `$d020`. Here every line of the
  bar is split into 6 segments. Each split is `lda #c / sta $d020 / nop`,
  8 cycles or 64 pixels, so 6 segments cover the whole 384-pixel visible
  line. The fastest possible split is 6 cycles (48 pixels), but six of
  those would only cover 288 pixels, leaving the last segment stretched.
* **The slant.** Segment *k* is drawn shifted down by `off_k` = 0..5
  lines, so the bar becomes a staircase that reads as one slanted bar. The
  slope follows `off_k = round(2.5 + (k - 2.5) * sin(tilt))`.
* **Black padding.** The gold column gets 6 black rows above and 6 below,
  so every segment is the same 36-entry column read at a different shift:
  `colour(row r, segment k) = column[r + 6 - off_k]`.
* **Speedcode.** The 30 display rows are unrolled code with no branches,
  exactly 63 cycles per row. Each frame, an unrolled patcher rewrites the
  180 `lda #` values in it.
* **The rest of the screen** is black, so the stable double IRQ simply
  fires 2 lines above wherever the bar is. The per-frame work uses at most
  about 16% of the time before the next IRQ.
* **The highlight** is traced exactly as in `STYLE=2`. Its dither follows
  each segment's own screen lines.
* **Horizontal position.** Where the splits land across the screen depends
  on exact cycle timing that only a real C64 or VICE shows. Use `HTUNE` to
  slide them so the first split falls in the horizontal blank.

## GOLDLIGHT: the slanted bar with a visible light

`goldlight.s` adds the light source as a glowing ball sprite that sweeps
back and forth above the bar. The bar's highlight is thickest in the
segment nearest the ball.

```sh
cl65 -t none -C raybars.cfg -o goldlight.prg goldlight.s
python3 sim_goldlight.py     # needs -g -Ln goldlight.lbl; renders preview_goldlight.gif
```

* **A sprite without badlines.** With DEN=0 the border covers everything,
  sprites included. But badlines are only enabled if DEN is set during
  raster line $30. So a small IRQ at line 44 clears DEN across line $30 and
  sets it again before line $33, where the display window opens. The window
  opens with no badlines all frame (idle state, `$3fff` = 0).
* **Two registers per split.** Inside the window the colour comes from
  `$d021`, so every split writes both registers:
  `lda #c / sta $d020 / sta $d021` = 10 cycles = 80 pixels. That gives 5
  segments with offsets 0..4.
* **Sprite timing.** A sprite only steals cycles on the lines where it's
  drawn. The ball stays above the bar and never shares a raster line with
  the speedcode or its stabilising IRQ (the simulator checks every frame),
  so every row stays exactly 63 cycles.
* **The highlight per segment.** For a cylinder along x lit by a point
  light at horizontal distance *a*,
  `spec = ((rho / sqrt(rho^2 + a^2)) * cos(2t - p))^n`, so it is strongest
  under the light and falls off sideways. That is approximated as
  "subtract |a|/32 levels" per segment. As the light sweeps, the white
  goes from about 7 lines under the ball down to the gold pattern's own 2.
* **The ball** is a multicolour sprite: white core, yellow, orange rim. It
  is copied to `$3F00`, because in VIC bank 0 the range `$1000`-`$1FFF`
  shows character ROM.
* **Cost.** The per-frame work uses at most about 59% of the time before
  the top IRQ.
* **Untested on hardware.** Exactly where the splits land relative to
  the sprite's x position depends on cycle timing that only VICE or real
  hardware shows. The code assumes segment *k* is centred at sprite x
  `32 + 80k`; adjust `HTUNE` and that constant if the highlight looks
  offset from the ball.

## GOLDORBIT: the light orbits the bar

`goldorbit.s` sends the light around the bar. It rises in front, slips
behind the bar at the top, sinks behind it, and comes back out in front at
the bottom, while drifting slowly sideways.

```sh
cl65 -t none -C raybars.cfg -o goldorbit.prg goldorbit.s   # --asm-define STEAL=6 to try 6
python3 sim_goldorbit.py     # needs -g -Ln goldorbit.lbl; renders preview_goldorbit.gif
```

* **Depth.** The ball is drawn at 8 pre-drawn sizes, radius 3..10 pixels,
  picked from the light's depth: small behind, big in front.
* **Occlusion.** While the light is behind, the sprite rows that fall on
  the bar's lines are blanked. It uses the line positions of the segment
  under the ball, so the cut follows the slant. The ball is drawn into two
  alternating buffers, switched at the top of the frame, so it never tears.
* **Light from behind.** `atan2` now covers all four quadrants. Once the
  light is behind the bar, the reflection angle passes 90 degrees and the
  front loses its highlight. With the light below, the highlight moves to
  the bar's bottom edge.
* **Timing on sprite lines.** On every line where the sprite is drawn,
  the VIC stops the CPU for a few cycles to fetch its data, whether the
  ball is in front or masked behind. Each speedcode row's padding starts
  with a branch whose opcode is patched every frame. With the carry clear,
  `bcs` is never taken and costs 2 cycles; `bcc` is always taken, costs 3,
  and skips an `inc $ea`, making the row `STEAL` cycles shorter. Rows on
  the sprite's lines get the short version, and the simulator checks they
  are exactly the right rows. How many cycles the VIC really takes depends
  on what the CPU is doing at that moment, so `STEAL` (4 or 6) needs tuning
  in VICE. The stable double IRQ can also lose a cycle when the ball sits
  right above the bar.
* **Cost.** The per-frame work uses at most about 54% of the time before
  the top IRQ.

## GOLDTWIN: a second bar from the distance

`goldtwin.s` keeps the orbiting light and its bar, and adds a second gold
bar low on the screen that comes from the distance, brightens, grows to
twice the size, and near-clips away. Then it comes again.

```sh
cl65 -t none -C raybars.cfg -o goldtwin.prg goldtwin.s
python3 sim_goldtwin.py      # needs -g -Ln goldtwin.lbl; renders preview_goldtwin.gif
```

* **Perspective.** The bar's depth z goes linearly from 6 to 1, and its
  height on screen is 48/z. It appears 8 lines tall, speeds up as it
  nears, and reaches 48 lines.
* **Nearest-neighbour rows.** Screen row *j* shows source row
  `floor(j * 24 / H)` of the gold pattern. The 24 source lines are coloured
  first; then a 30-cycle-per-row loop expands them with an 8.8 fixed-point
  step (no division).
* **Brightness by distance.** There are 4 colour remaps:
  * farthest: yellow is brown and white is dark grey
  * then yellow becomes orange and white becomes grey
  * then yellow orange and white light grey
  * full colour from about the top bar's size (22 lines)

  The traced highlight is dimmed the same way.
* **Near-clip.** At the camera it near-clips in two frames: the middle 32
  of its 48 rows (the nearest part) vanish, then the rest. Then there's a
  short black pause.
* **Shared motion and light.** It tilts with the top bar and reflects the
  same orbiting light. Its scene depth runs from 90 behind the light's orbit
  plane to 75 in front of it. Once bar B is nearer the camera than the
  light, the light shines from behind and above, and the highlight rides up
  to the very top rows. In the simulator, the highlight's average centre
  moves from 0.44 of the bar height to 0.21.
* **Thickest nearest the light.** The plain dimmed gold is expanded once.
  Then the highlight is laid on per segment, each with its own
  distance-from-the-light threshold. The expansion records which source
  line feeds each row, and only lit rows are visited. The white is written
  straight into bar B's speedcode through a table of row addresses.
* **Main loop instead of IRQs.** The interrupts only draw: the badline
  trick at line 44, bar A, and bar B from line 229. The main loop starts
  the next sprite and bar A as soon as bar A has been drawn (bar B's IRQ
  cuts in), and the next bar B once bar B has been drawn. Worst cases are
  18% (sprite, before line 44), 56% (bar A, before its IRQ) and 74% (bar B,
  before line 227) of each deadline window.
* **No timing patch for bar B.** The ball never goes below line 226, so it
  never steals cycles inside bar B.
* **VIC bank 2.** The program outgrew VIC bank 0's free space, so the VIC
  uses bank 2 ($8000-$BFFF): sprites at $8000 and $8040, screen at $8400,
  idle byte at $BFFF.

## Tuning notes

* PAL only: the loop is 63 cycles per line, and an NTSC frame has too little vblank.
* `HTUNE` adds NOPs after the stable-raster code. If you see a step where
  the colour changes partway across a line, adjust it until the switch
  falls inside horizontal blank.
* Everything else (`R`, the orbit amplitudes, the light depth, the Phong
  exponent and the env map) is in `gen_tables.py` and at the top of `raybars.s`.
  Keep `R` in sync between the two files.
