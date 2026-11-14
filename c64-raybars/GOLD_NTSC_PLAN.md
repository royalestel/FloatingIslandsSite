# Gold sequence on the NTSC cartridge: plan (background loading)

Sequence: part4d (cut at its wipe, frame 1076) -> blue bar move + fade (90 frames) -> goldtilt (180) -> goldlight (360) -> goldorbit (360)
-> goldtwin (360 + 296 fly-out) -> goldfly (360) -> the cart loader (`jmp $0200`) loops to part 1.
Each routine is loaded from the cartridge IN THE BACKGROUND while the one before it runs, and started on the frame after the last
frame of the one before it (no gap).  The tune (Alpha, $1000-$2A33) plays throughout: every part calls it 5 frames in 6.

## Memory map (NTSC, all banks RAM with $01 = $35 while running)
| area | contents |
|---|---|
| $0002-$006F | each routine's zero page (cleared by its start) |
| $00F0-$00F5 | background loader state (never cleared) |
| $00FE-$00FF | the tune |
| $0200-$02FF | cart loader (`jmp $0200` = load the next part, the old way) |
| $0300-$03FF | background loader (`bgstep`) + the shared tune counter `mc` |
| $0400-$07F7 | goldtilt's tables (tilt.inc), loaded during part4d (VIC never shows the screen: DEN trick) |
| $07F8-$07FF | sprite pointers (VIC bank 0: goldlight, goldorbit) |
| $0800-$0FFF | part4d's code |
| $1000-$2AFF | the tune |
| $2B00-$B3FF | part4d's pages; afterwards: goldlight $2B00-$3D3F, then goldtwin's tables + BSS $2B00-$3D3F |
| $3D40-$3FFF | VIC bank 0 sprites (goldlight $3D40-$3FFF, goldorbit $3E00-$3FFF), idle byte $3FFF |
| $4000-$7FFF | goldorbit, then goldfly (code, tables, its 30 column pages) |
| $8000-$87FF | VIC bank 2: sprites $8000-$80FF, screen $8400 (goldtwin, goldfly) |
| $8800-$B3FF | goldtwin's code + raster code |
| $B400-$BFFE | goldtilt's code + raster code (+ the blue bar move/fade), loaded during part4d; $BFFF = bank 2 idle byte |
| $C000-$CFFF | hlrun.inc (4 KB, resident from goldlight on) -- or goldtilt's extra if hlrun moves to $4000 |
| $E000-$FFF9 | tables.inc + light.inc + orbit.inc (7.1 KB, resident from goldtilt to goldfly) |

Loads: during part4d: goldtilt + tilt.inc + shared tables (+ hlrun) ~15 KB; during goldtilt: goldlight 5.2 KB (+ hlrun);
during goldlight: goldorbit 4.7 KB; during goldorbit: goldtwin 16.4 KB; during goldtwin: goldfly 7.7 KB + 7.7 KB of zeroed pages.

## Background copy
In the main loop's idle time (after the frame's update + tune): copy a chunk (32 bytes, ~9 lines) from the ROML bank with $01 = $37,
interrupts off, ONLY if the next raster IRQ is more than ~12 lines away (each routine keeps `nirq` = the line its next IRQ is set for,
written next to every `sta $d012`).  Reading the cart needs HIRAM = 1, so the IRQ vector would come from the KERNAL ROM: no IRQ may
fire while a chunk is copied.

## Switch-over
At the end of its frame count the running routine jumps (from its main loop, after its last update) to the next routine's `start`,
which sets its phases (the GOLD_INIT values of mock_gold_seq.py), VIC bank, sprites, IRQ chain, builds its first frame and arms its
top IRQ before line 44.
