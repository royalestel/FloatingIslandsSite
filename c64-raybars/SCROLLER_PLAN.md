# The band scroller (cosmicstrings, NTSC cartridge)

What the user wants (mock_greets.py is the reference mockup): the Xenon font (xenon_font.asm, 2x2 multicolour tiles) in the black band under
the bars, choreographed with the ship's banks, a half loop and a dive; the 81 GOLDship angles; GOLDship's six tilting bar segments.
Port notes to remember: GOLDship (goldship.s) is PAL timing (63-cycle lines, 312 lines, STEAL 5) and has no music call; its ship is one
sprite (cosmicstrings' is two); the 81 angles are 162 frames x 64 bytes = 10 KB of sprite data.

## The problem
Text needs the VIC's badlines (character fetches: ~40 CPU cycles stolen on every 8th line, wherever the text is) and cosmicstrings switches
the display off (DEN = 0 across line $30) so that no badline ever happens: its bar lines are cycle-exact, and it relies on the VIC being in
IDLE state (graphics = the idle byte at $3fff = $bfff, the ghost byte the line code writes every line).

## The method: badlines only in the band; everywhere above, DEN on and the yscroll dodges every line
* DEN = 1 at line $30 (48) latches the display on; a badline then happens on every line in $30..$f7 whose low 3 bits == YSCROLL (any cycle of
  the line: the condition is evaluated every cycle), and the VIC enters display state.  So from line 44 down to the band $d011's yscroll must
  never equal the current line's low bits at ANY cycle: each write must be safe for the rest of its line and the start of the next.
* In the bar line code (per line): Y(L) = ((L mod 4) + 2) & 7, written by `lda #$18+Y / sta $d011` after the ghost-byte write: safe for lines
  L and L+1 (and for an off-by-one in which line the write lands in).  4 phases x (normal, ship line) = 8 variants of the line code.
  Ship lines have no spare cycles on a span's last line: that path skips the ghost-byte write (one line of old dither).
* In the gaps between blocks (CPU free, main loop running): gap IRQs every <= 6 lines write Y(M) = (M-1)&7 (M read from $d012), which is safe
  for 7 lines (M..M+6).  The block's irq1 (S-3) must come within 6 lines of the last gap write: nextirq: d = S - c; d <= 6: the block's IRQ;
  else a gap IRQ at c + min(6, d - 5).  GAPMIN = 8 so that d >= 8 after an exit.  The exit code does the same write at its line.
* The band IRQ (just after the last bar line): VIC bank 0 (screen $0400, charset $0800, ROM font not used), MCM on, yscroll set to match the
  first text row's line; colours masked (black) above the band's top line T = 212 and restored by a second IRQ at T-1, so rows may start up to
  7 lines above T and be clipped there.  Bars end at T-8.  Text rows then follow the pitch by yscroll (0..7) plus whole-row shifts of the
  screen RAM; clipping at the bottom is the window's end (line 250).
* irqvbl moves to line 251 (after the band; it restores bank 2 / $d018 / $d016 first); the record copy + the tune must end before line 44
  (irqtop must come in time: with DEN on a late irqtop would let badlines in).

## Memory
* VIC bank 0 for the band: charset (inverted Xenon data, 1984 bytes) at $0800, screen $0400 (rows 0..4: 200 bytes), colour RAM $d800.
  Bank 0 offsets $1000..$1fff are the ROM font (the tune hides under them for the VIC, which is fine).
* The font colours: the CharPad data has strokes as %00/%01/%10 and the background as %11 (colour RAM black).  Inverted (NOT): background
  %00 = black ($d021 = 0), %01 = $d022 = dark grey (11), %10 = $d023 = light red (10), %11 = colour RAM 15 (MC + yellow).
* Stage 2 (cosmicstage2.s, 264 bytes) lives at $0800 now: it has to move (page $0700, <= 256 bytes) because the font takes $0800..$0fff and the
  stage-2 switch copies whole pages.  Colour RAM ($d800) is I/O space: written by code that runs after `resume`.

## Staging (each checked in VICE: cap2.sh screenshots at exact cycles)
1. engine: DEN on, line code dodge, gap IRQs, band IRQ with a static test text; bars must look as before (dither intact, no sync loss).
2. the Xenon font, masking at the band's top, the scroll (xscroll + column shifts), vertical follow.
3. the choreography state machine (banks from the flight, half loop, dive) + the ship's pitch/roll hooks.
4. the 81-angle ship, the tilting segments (timing test first: six writes a line + the dodge write + the ship's 7 stolen cycles).

## Status
* Stage 1 and the static part of stage 2 work in VICE (test cartridge: GOLD_SEQ=goldfly,cosmicstrings python3 mk_gold_ntsc.py /tmp/gc_test.crt):
  DEN on, the 8 line-code variants, the gap IRQs, the band IRQ in VIC bank 0 with the Xenon font ("XENON TEST" in the band), the bars' edges and dither
  unchanged.  vtest1.s is the standalone check of the dodge rule (a polling loop writing Y(L) a line: no badline; a constant yscroll: the whole screen
  in display state).  Pitfalls found: the cartridge hides the ROM font from the VIC (a RAM font is needed even for tests); a line-code variant must
  jump over the span-end path that follows it (first build ran into it: garbage rows from the third line of every block).
* Stage 2 moved to $0700 (255 bytes) to leave $0800-$0fff to the font.
* Garbage frames (found and fixed): a gap IRQ is set up by `nextirq` from the block `exit` code, whose handler takes ~155 cycles (from cycle 2 of the exit line);
  with d = 7 (last bar line 203, band at 211) the gap IRQ fell only 2 lines after the exit, the raster IRQ came while the handler was still running and
  its `asl $d019` acknowledged it: the IRQ chain was lost for a frame (no dodge writes: text garbage, bars black, the next frame's irqtop late too).
  Rule: after an exit the next IRQ must be >= 3 lines away (GAPMIN = 8 gives that between blocks); the bars now end at raster 202 (BANDL = 141) so the
  last exit is at line 203 and d >= 8 for the band too.  Found with the monitor: `watch store d011` + `r` per write (LIN/CYC) and `io d000`
  (VIC internal state: RC / Idle) per step, on frames synchronised by a trap.
* Tilted-row timing (stage 4's first test, vtest2.s / gen_vtest2.py, NTSC, VICE): GOLDship's row -- 5 x (lda colK,y / sta $d021),
  iny, the next row's segment 0 (lda / sta $d021,x in the right border) -- plus the dodge write (lda #Y / sta $d011) is 57 cycles: a normal
  row has 8 to spare (65), enough for a loop's cpy / beq / jmp.  On the ship's 21 sprite-DMA rows (two sprites: 7 cycles stolen) it is
  58 of 58 (sta $d011,x): no room for a loop test, so the ship band is straight-line code (or the dodge goes to every other row).
  Checked: 120 rows, no badline, every row's six segments at the same pixels (sprite x 56 + 64k) above, through and below the ship.
  Details that matter: the row's dodge write lands in the next raster line (cycle ~13), so it carries that line's Y; the first ship row
  is the one starting on the sprite's first line (SPRY - ROW0: one off either way and the band's rows jog 7 cycles); HTUNE 3.
* Flat colours for the tilted segments (flat_ladder.py, in gen_cosmic.py's swatch pages at +128 even rows / +160 odd rows, per frame
  parity, indexed by ladder position like the colour entries; flat_ladder.png: real swatch | flat, both frames averaged): each ladder
  step becomes one colour or a pair on alternate rows swapped every frame, chosen in CIELAB; flicker beyond the real swatch's own is
  penalised; no step dimmer than 0.8x (0.95x for the upper half: the bars' centres); the faintest steps (< 0.03) black + one colour.
  By eye (user): ladder steps 1, 2 (dark blue) and 4 (purple) are one coloured row and one black row, the coloured row always the one
  further from the bar's centre and flickering (on even frames): a quarter of the colour.  That needs the row's half of the bar, so the
  table is there twice: +128 / +160 the upper half, +192 / +224 the lower half (the compose step knows which half a row is in).
  19 of 25 steps match the real light exactly; step 1 2x, step 5 1.14x, two upper steps 1.2-1.4x (white for cyan|white).
* Next: top masking, the scroll (xscroll + column shifts), vertical follow, the choreography.
