# Handoff: the v10 colour ramp + raster splits

For a new chat that does "fun stuff" with the COSMIC STRINGS colour ramp and the
GOLD* raster-split technique. Repo `royalestel/FloatingIslandsSite`, directory
`c64-raybars/`, branch `claude/c64-raytraced-rasterbars-1iigat` (pull before
starting and before every push; no PRs unless asked).

## How the user works

* PAL C64, demoscene. Iterates visually and fast; short explanations.
* Wants **videos, not stills**: MP4, 60 fps, one C64 frame per video frame,
  **CRT look only** (`loop_video.crt_look`), sent with SendUserFile `display: attach`.
  Graphs: `display: render`.
* Judges by eye on the CRT render; when they reorder or drop swatches, do
  exactly that and re-render, no long explanation.

## The palette: the v10 ramp (25 swatches, darkest first, ordered by eye)

Source of truth: `swatch_ramp_video.ladder()` (order, drops, the shifted swatch),
`preview_v7.colour / ghost` (the two white swatches), `preview_v10.colour / ghost`
(applies the stripes row swap and the 1-pixel shift). Ramp video:
`python3 swatch_ramp_video.py preview_swatch_ramp_crt.mp4`.

Each swatch = colour and **idle (ghost) byte** by row parity r (screen line & 1)
and frame parity p. Idle state, no badlines: the display window shows `$d021`
with the idle byte (`$3fff`/`$bfff`) as black pixels; a set bit = black pixel.
Cells below: `colour:ghost` for p0r0 p0r1 p1r0 p1r1. Flicker pairs "a / b" show
a on one frame and b on the next, the phase swapped line to line (the PAL delay
line blends them). "L*" = CIE L* of the linear light averaged over both frames.

| # | swatch | p0r0 p0r1 p1r0 p1r1 | L* |
|---|---|---|---|
|  0 | black | 0:00 0:00 0:00 0:00 | 0 |
|  1 | blue 1/4 on/off | 6:77 6:DD 6:FF 6:FF | 6 |
|  2 | blue 1/4 inverting | 6:77 6:DD 6:DD 6:77 | 12 |
|  3 | blue checker inverting | 6:55 6:AA 6:AA 6:55 | 19 |
|  4 | purple 1/4 inverting | 4:77 4:DD 4:DD 4:77 | 21 |
|  5 | light blue 1/4 inverting (shifted 1 px right) | E:BB E:EE E:EE E:BB | 28 |
|  6 | purple checker inverting | 4:55 4:AA 4:AA 4:55 | 30 |
|  7 | light blue checker inverting | E:55 E:AA E:AA E:55 | 39 |
|  8 | blue | 6:00 6:00 6:00 6:00 | 28 |
|  9 | blue / dark grey | 6:00 B:00 B:00 6:00 | 32 |
| 10 | blue / purple | 6:00 4:00 4:00 6:00 | 36 |
| 11 | purple / dark grey | 4:00 B:00 B:00 4:00 | 39 |
| 12 | purple | 4:00 4:00 4:00 4:00 | 42 |
| 13 | light blue / dark grey | E:00 B:00 B:00 E:00 | 46 |
| 14 | purple / light blue | 4:00 E:00 E:00 4:00 | 48 |
| 15 | purple / grey | 4:00 C:00 C:00 4:00 | 49 |
| 16 | light blue | E:00 E:00 E:00 E:00 | 53 |
| 17 | light blue / grey | E:00 C:00 C:00 E:00 | 54 |
| 18 | light blue / cyan | E:00 3:00 3:00 E:00 | 65 |
| 19 | cyan / grey | 3:00 C:00 C:00 3:00 | 65 |
| 20 | cyan | 3:00 3:00 3:00 3:00 | 74 |
| 21 | cyan + white every other | 1:00 3:00 3:00 3:00 | 82 |
| 22 | cyan / white | 3:00 1:00 1:00 3:00 | 89 |
| 23 | cyan \| white stripes (rows swapped) | 3:00 1:00 3:00 1:00 | 89 |
| 24 | white | 1:00 1:00 1:00 1:00 | 100 |

The order is the user's, by eye on the CRT (several swatches measure brighter
than they look: the checker/1/4 patterns). Treat position as brightness;
`preview_v10.EYE` gives each step the measured values sorted into that order.
This is the program's swatch table: `gen_cosmic.v10_swatch_tables()` (32-slot
pages: colour at +0/+32, idle byte at +64/+96, per frame parity).

**Bar ramps (v10, kept):** `preview_v10.ramp_v10(h, d)` — round profile with a
white centre near in; candidates (v3's centre-out error diffusion, thresholds
shifted, error carried more or less) chosen for the round profile's rms width,
its brightness, staying close to the last pattern's width, and never getting
dimmer as the bar nears. Over a 28 m → 0.42 m flyby: no brightness drops, largest
step 2 L*. Side-by-side preview: `python3 preview_v10.py out.mp4`.
`cosmicstrings.prg` is built with it (`gen_cosmic.V10 = True`).

## The raster splits (GOLD* programs; README sections GOLDTILT..GOLDSHIP)

* A line's colour changes mid-line only where the CPU writes it. **Border**:
  `lda #c / sta $d020 / nop` = 8 cycles = 64 px, 6 segments across 384 px
  (fastest split 6 cycles = 48 px). **Inside the window** (idle state) the
  colour is `$d021`; writing both registers: `lda #c / sta $d020 / sta $d021`
  = 10 cycles = 80 px, 5 segments. GOLDSHIP: `lda col,y / sta $d021` = 8
  cycles, 6 segments split at sprite x 56, 120, 184, 248, 312 (inner 64 px,
  edges 32 px).
* **Slant / roll:** segment k is shifted by `off_k` lines, so a bar becomes a
  staircase read as one slanted bar (`off_k = round(2.5 + (k-2.5)·sin tilt)`;
  GOLDSHIP: one 17-entry tilt table per segment, `rtilt0..5`, 12 lines drop
  edge to edge at full roll). Black padding rows above/below each column so
  every segment reads the same column at a different shift:
  `colour(r, k) = column[r + PAD - off_k]`.
* **Speedcode:** unrolled display rows, no branches, every line exactly 63
  cycles (56 on sprite DMA lines: STEAL = 7 with the ship's sprites). A
  stabilising IRQ before the block; the first split lands in horizontal blank
  (`HTUNE` slides them; exact x only provable in VICE / hardware).
* **Highlight per segment:** GOLDLIGHT/GOLDORBIT trace a point light's
  specular per segment (cylinder lit at horizontal distance a), thickest in the
  segment nearest the light sprite.
* Simulators (`sim_gold*.py`, `sim_cosmic.py`) run the real 6502 code on
  `c64cpu.py`/py65 and check cycle counts, page crossings and what each line
  shows; use the same approach for new programs.

## Combining them — notes

* The ramp's ghost bytes are per line (one idle byte per line in COSMIC
  STRINGS); a split changes `$d021` per segment, the idle byte stays the
  line's unless also rewritten mid-line (another `sta $3fff`, 4 more cycles).
  So per-segment swatches are easiest from the flat (ghost 00) part of the
  ramp, #8..#24, or segments sharing one ghost pattern.
* Flicker pairs per segment just need the two frames' colour tables (frame
  parity p) and the row-parity swap, as in the swatch table.

## Files

`cosmicstrings.s / cosmic.cfg / gen_cosmic.py / sim_cosmic.py` (the program,
generator, 6502 sim), `goldship.s / goldfly.s / goldlight.s / goldorbit.s /
goldtilt.s / goldtwin.s` + `raybars.cfg` + `sim_gold*.py` (the split programs),
`swatch_ramp_video.py`, `preview_v7..v10.py`, `loop_video.py` (`crt_look`),
`flyby3d.py` (`C64RGB`), `ideas_video.Video` (MP4 writer), `README.md`.

Build: `python3 gen_cosmic.py && cl65 -g -t none -C cosmic.cfg -Ln cosmic.lbl -o cosmicstrings.prg cosmicstrings.s`;
gold programs: `cl65 -g -t none -C raybars.cfg -Ln goldship.lbl -o goldship.prg goldship.s`.
