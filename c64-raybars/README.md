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

* **Steeper tilt.** Neighbouring segments can be up to 2 lines apart:
  `off_k = round(4 + (k - 2) * 2 * sin(tilt))`, 0..8 across the 5
  segments. The padding grows to 8 black rows, bar A to 33 display rows
  and bar B to 56. Bar B starts at line 231 so the ball, now reaching line
  228, still never touches it. Bar B's last row is line 286, at the bottom
  edge of PAL's visible area.
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

  The traced highlight is never darker than medium grey. Its strongest
  rows brighten first, grey to light grey to white, so as the bar nears,
  the thick core of the highlight turns white before its thin edges.
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
  trick at line 44, bar A, and bar B from line 231. The main loop starts
  the next sprite and bar A as soon as bar A has been drawn (bar B's IRQ
  cuts in), and the next bar B once bar B has been drawn. Worst cases are
  18% (sprite, before line 44), 60% (bar A, before its IRQ) and 81% (bar B,
  before line 229) of each deadline window.
* **No timing patch for bar B.** The ball never goes below line 226, so it
  never steals cycles inside bar B.
* **VIC bank 2.** The program outgrew VIC bank 0's free space, so the VIC
  uses bank 2 ($8000-$BFFF): sprites at $8000 and $8040, screen at $8400,
  idle byte at $BFFF.

## GOLDFLY: bars flying out of the distance

`goldfly.s` puts the light, a ball sprite, at the centre of the screen.
Three bars at a time fly toward the camera out of the distance and past it,
through the top or bottom of the window.

```sh
cl65 -t none -C raybars.cfg -o goldfly.prg goldfly.s
python3 sim_goldfly.py       # needs -g -Ln goldfly.lbl; renders preview_goldfly.gif
```

* **Tilts that don't repeat.** A tilt is a staircase across the 5
  segments. Each segment can only move by whole lines, so the 32 angles
  used before only made 13 different-looking tilts. Varying where the
  steps fall as well as the slope gives 53 distinct staircases, with
  neighbouring segments up to 2 lines apart (`tilt0..4` in `fly.inc`).
  * The tilts sit in a ring, in the order they were last shown. A new bar
    picks at random among the 13 that have waited longest, and that tilt
    moves to the back of the ring. So no tilt comes back within 40 bars,
    and every one keeps coming round.
  * If the pick looks too much like the previous bar's tilt, the one half
    the window away is taken instead.
  * The simulator calls `drawtilt` 3000 times: all 53 are used, and the
    closest repeat is 41 bars apart.
* **Spawn cycles.** Each bar keeps its tilt for the whole flight. It takes
  the next entry of two shuffled tables in `fly.inc`:
  * a distance from the centre line: 15 values from 76 to 244. Far away,
    that puts a bar 6 to 20 lines from the centre, right by the light.
  * a palette: 13 entries, never the same one twice running.

  Sides alternate above and below the light.
* **Perspective.** A bar flies at constant speed from depth 12 to 1.2
  over 240 frames. It is `48/Z` lines tall and `Y/Z` from the centre,
  where the asm multiplies Y by a `256/Z` table. So it starts 4 lines tall
  beside the light, stays small there for about 3 seconds, then swells to
  40 lines and rushes out through the top or bottom edge.
  * A bar still on screen at the end near-clips at the camera: in one
    frame its middle rows go, then the rest.
  * It dims with distance and reflects the light, thickest nearest it. The
    highlight rides to the bar's edge once the bar is nearer the camera
    than the light (depth 3).
* **Palettes:** the gold one; `8 12 7 8 11 8 15 7 1 7 1 7 7 15 8 11 9 9 11 8
  12 10 12 8`; and two 12-colour lists, `6 11 14 15 1 0 9 11 8 12 10 15`
  and `8 10 7 10 10 15 10 8 2 9 9 11`, dithered up to 24 rows. Each colour
  is followed by a row of (this colour, next colour) on alternating lines,
  so scaling up gives poor man's dithering between them.
* **Pointer-read speedcode.** Each bar row is 5 x `lda (pK),y / sta $d021`
  (9 cycles, 72-pixel segments), then `iny` and loop control. `pK` points
  into segment K's column, offset by the tilt. The bars are drawn inside
  the display window (badline trick as in goldlight), so the side borders
  stay black. Each column is one page, so `(pK),y` never crosses a page.
* **Bars behind the light.** Far bars pass right behind the light's
  sprite, and on the 21 lines where the sprite is fetched the VIC halts
  the CPU for cycles 55-59.
  * Rows on those lines run `63 - STEAL` cycles instead of 63. Each slot
    has three loops: normal rows above the light, rows on its lines, and
    normal rows below.
  * The loops are chained by jumps that `nextbar` patches for each block,
    and their entries are padded so every row keeps its exact length.
  * The stable-raster IRQ's delay is one turn (5 cycles) shorter when its
    line has the DMA.
  * The sprite is drawn over the bar's colour, so it covers bars behind
    it. Bars nearer than the light keep off its lines (Y >= 76).
  * `STEAL` (5, because the loop's tail only reads) and the band lines
    `BAND0`/`BAND1` are worked out from the VIC's timing, not measured.
    The simulator can't emulate sprite DMA, so they need checking in VICE.
* **Pipeline.** The main loop builds frame N+1 into back buffers (columns,
  pointers, the IRQ schedule) while frame N is shown. The top IRQ swaps
  them in. If a build ever ran late, the swap would simply wait a frame.
* **Overlaps.** Bars closer than 6 lines can't each have their own IRQ.
  Far bars above and below the light meet at the centre, and bars on one
  side can cross. Such bars share one block, up to all three:
  * The nearest bar (furthest along its flight) draws the block, which
    grows to cover them all.
  * Its column is blacked outside its own lines. Then the other bars' rows
    are copied in around its own rows, farthest first, so nearer bars
    cover farther ones, segment by segment, tilt and all.

  Its bar rows sit at row 96 of a 256-byte column, which leaves room for
  merged bars above and below.
* **Speed tricks.**
  * Palettes come pre-dimmed: 4 palettes x 4 distance levels, 48 bytes
    each.
  * A row map per bar height gives each expanded row's palette entry, so
    there is no stepping in the loop.
  * The spec level is computed inside the highlight loop, which only does
    work for lit rows. A row-start table gives each lit row's expanded
    rows, and a static table gives each segment's highlight colour.
  * Bars only grow within a flight, so each frame only blacks the rows
    newly exposed below a bar. The 8 rows above, and all 8 below, are only
    re-blacked after a merge or a respawn.
  * The merge loops copy and black two rows at a time.

  The simulator runs the program's own display code for every block of
  every frame. Over 4000 frames it found:
  * Every row takes 63 cycles, or 58 on the light's lines.
  * Every displayed cell shows the nearest bar covering it.
  * Blocks leave room for the next IRQ.
  * The worst frame uses 97% of the free time. Its budget allows 4 lines
    of IRQ work per block and the sprite's own DMA.

## GOLDSHIP: fly through a forest of raster bars

`goldship.s` turns goldfly into a game. You fly a ship, seen from behind,
through parallel bars that come at it out of the distance. Joystick in
port 2.

```sh
cl65 -t none -C raybars.cfg -o goldship.prg goldship.s
python3 sim_goldship.py      # needs -g -Ln goldship.lbl; renders preview_goldship.gif
```

* **The ship** is one multicolour sprite at the centre of the screen.
  Its 9 frames are renders of a small 3D model (`ship3d.py`, called by
  `gen_tables.py` into `ship.inc`). With the stick centred you see the
  tail view; otherwise it leans that way, rolled 25 degrees and pitched
  30. `python3 ship3d.py frames.png` previews them
  (`preview_ship3d.png`).
  * The model is a gull, picked from colour-rendered design variations.
    It has a flat body with the light on its nose, wings that rise to a
    kink and fall to the tips, and an engine pod at each kink.
  * In the tail view it is an "M" across the full sprite width, with no
    central fins. Its climbing and diving frames mirror each other: the
    nose light shows above when climbing and below when diving.
  * Each frame is rendered with a z-buffer at 8 x 4 samples per
    multicolour pixel and flat-shaded into the sprite's three colours:
    shadowed hull, lit hull and trim (the engine pods), and white,
    kept for the light on the nose alone.
  * When a thin slanted part leaves a one-pixel gap between two filled
    pixels, the conversion fills it, so the roll frames stay whole.
  * Looking straight at the tail, the nose is hidden behind the body, so
    the level frame has no white.
* **Pitch** (up / down) eases the ship's climb speed toward ±1 unit per
  frame, so pushing up makes the bars sink. Each bar's height is relative
  to the ship's: it is `Y/Z` lines from the centre, above or below.
* **Roll** (left / right) tilts every bar the other way, one step every
  other frame. Neighbouring segments can be up to 3 lines apart, so at
  full roll a bar drops 12 lines from one edge to the other. Letting go
  levels out again.
  * All bars are parallel, so the tilt comes from one 17-entry table per
    segment (`rtilt0..4`).
  * Each bar has 12 black padding rows above and below it (`PAD`), one
    for each line of the steepest slant.
* **New bars** appear far away at your current height, plus the next of
  16 shuffled offsets (16-bit): 5 near the ship, on a collision course at
  the screen centre, and 11 off the centre line, up to 200 units away
  (17 lines out when they appear). Bars above and below make a forest to
  fly through.
* **Bar sizes and colours come from a true-perspective profile**
  (`flyby3d.py`, below, writes `flyprof.inc`):
  * Each bar's height per flight frame is its decimated height in a
    true-perspective render (`flyh`).
  * Its colours per flight frame are the decimated render's rows, one
    list per palette per frame: 430 distinct lists, 6.5 KB. Each list
    includes the dimming: dim far away, full just in front of the ship,
    then quickly into shadow past it.
  * The 12-colour palettes get true in-between colours instead of line
    dithering.
  * The raster-split highlight is drawn on top as before. Its brightness
    level follows the same brightness curve (`flylev`), so a bar in the
    ship's shadow gets a dim highlight.
* **Collision course.** A bar covers the screen centre exactly when its
  height is within half its thickness (24 units) of the ship's, at any
  distance. While any bar ahead does, the ship's palette changes:

  | | hull | trim and light ring | light core |
  |---|---|---|---|
  | normal | purple | light blue | white |
  | collision course | red | orange | yellow |

  A bar that reaches the ship's depth on a collision course flashes the
  border red.
* **The engine** is goldfly's. Bars sit close together near the centre,
  so almost every frame merges bars, often all three. Three things keep
  that inside the frame:
  * A light-angle table bounds the highlight loop to the lit rows.
  * Colours come ready-made: the profiled list for the bar's palette and
    flight frame is a straight copy (`lda list,y`, 3 stores, `dey / bpl`).
  * Only 3 columns per bar. All bars share the tilt and the highlight is
    symmetric, so segments 0 and 4 read one column and 1 and 3 another,
    each at its own tilt offset. Expansion, highlight and merge copies
    write 3 columns instead of 5. A row costs 24 cycles instead of 43.
  * The near clip has its own profiled lists, with the cut rows black, so
    it costs nothing extra.
  * All bars share one tilt, so a farther bar's rows sit at the same
    offset in every column. Copying them and blacking around the nearest
    bar both handle all five columns at once.
  * This program banks out the ROMs, so its zero page can run past $7F
    (the shared `raybars.cfg` now allows up to $FF).
* **Simulator.** `sim_goldship.py` flies with an autopilot on `$dc00`. It
  dives or climbs away from the nearest bar on a collision course. Every
  200 frames it also rolls fully left, levels out, and rolls fully right.
  The preview's still frames are at full roll. It runs the program's own
  display code for every block, and over 3000 frames found:
  * Every row takes 63 cycles, or 58 on the sprite's lines.
  * Every displayed cell shows the nearest bar covering it.
  * The worst frame uses 79% of the free time, leaving at least 2,600
    cycles (about 42 raster lines) of each frame spare.
  * Every bar row holds its profiled colour, or a highlight drawn over it.

  As in goldfly, the sprite DMA timing (`STEAL`, `BAND0/1`) needs checking
  in VICE.

## FLYBY3D: profiling the bars in true perspective

`flyby3d.py` renders GOLDSHIP's scene for real and decimates it to the C64.
The profile it takes is what the game's bar sizes and colours are built
from.

```sh
python3 flyby3d.py     # preview_flyby.gif, preview_flyby_profile.png,
                       # flyby_sizes.txt, flyprof.inc
python3 flyby_spec.py  # preview_flyby_spec*.png / .gif: the highlight
```

* **The scene.** The camera's focal length is 200 lines, which makes the
  game's `48/Z` and `Y/Z` exact: bars are 0.24 m thick and Y units are
  1/200 m.
  * The ship (`ship3d.py`'s model) sits at Z = 3, its wingspan 24
    pixels.
  * Cylinders of radius 0.12 m fly from Z = 12 (4 rows tall) to 1.2 over
    240 frames.
  * Each cylinder is painted in 48 bands: its palette's colours with
    in-between colours mixed in RGB.
  * Brightness depends on distance only: 25% far away, full just in front
    of the ship, 30% within 0.8 m past it.
* **Rendering.** Each frame is rendered at 4 x 4 samples per C64 pixel
  (ray-cylinder intersections, the ship z-buffered), then averaged and
  matched to the nearest C64 colour.
* **The profile.** For each palette and flight frame, the decimated rows
  of a bar on the screen's middle column. A bar's row count depends on
  where it sits within a line, so each frame is sampled at 8 sub-line
  positions and the heights averaged.
  * `flyby_sizes.txt` counts the frames a bar spends at each height,
    against the game's old `round(48/Z)`. True perspective leaves 4 rows
    sooner (16 frames instead of 30), and above 8 rows the counts agree
    within one frame.
* **The highlight** (`flyby_spec.py`) is compared with a ground truth:
  the bars as perfect mirrors of the light on the nose, plus a modest
  bloom.
  * The game's highlight sits where the true one does.
  * The true one shows on the C64 only in the last stretch before the
    ship.

## Tuning notes

* PAL only: the loop is 63 cycles per line, and an NTSC frame has too little vblank.
* `HTUNE` adds NOPs after the stable-raster code. If you see a step where
  the colour changes partway across a line, adjust it until the switch
  falls inside horizontal blank.
* Everything else (`R`, the orbit amplitudes, the light depth, the Phong
  exponent and the env map) is in `gen_tables.py` and at the top of `raybars.s`.
  Keep `R` in sync between the two files.
