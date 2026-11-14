# Gold sequence on the NTSC cartridge: plan (background loading)

Sequence: part4d (cut at its wipe, frame 1076) -> blue bar move + fade (90 frames) -> goldtilt (180) -> goldlight (360) -> goldorbit (360)
-> goldtwin (360 + 296 fly-out) -> goldfly (360) -> the cart loader (`jmp $0200`) loops to part 1.
Each routine is loaded from the cartridge IN THE BACKGROUND while the one before it runs, and started on the frame after the last
frame of the one before it (no gap).  The tune (Alpha, $1000-$2A33) plays throughout: every part calls it 5 frames in 6.

## Memory map (NTSC, all banks RAM with $01 = $35 while running)
| area | contents |
|---|---|
| $0002-$007F | the running routine's zero page (restored from its image at the switch) |
| $00F0-$00F6 | background loader state; $00EF `nirq`: the line the next raster IRQ is set for (every routine keeps it) |
| $00FE-$00FF | the tune |
| $0200-$02FF | cart loader (`jmp $0200` = load the next part, the old way) |
| $0300-$03FF | background loader (`bgstep`), the switch (`bgswitch`), the job list, the tune counter `mc` ($03FF) |
| $1000-$2A33 | the tune |
| $E000-$FFF9 | shared: tables.inc + light.inc + orbit.inc, loaded once (during part4d) |
| $4000-$4FFF | shared: hlrun.inc, loaded once (during goldtilt) |

| running | its memory | loads in the background |
|---|---|---|
| part4d | $0800-$0FFF, $2B00-$B3FF, bank 0 idle byte | goldtilt ($B400-$CFFF), the shared tables ($E000) |
| goldtilt (+ the blue bar move/fade) | $B400-$CFFF | goldlight ($0400-$0FFF, $2B00-$3FFF; VIC bank 0), hlrun ($4000) |
| goldlight | $0400-$0FFF, $2B00-$3FFF | goldorbit ($5000-$7FFF; VIC bank 0: sprites $3E00-$3FFF) |
| goldorbit | $5000-$7FFF, $3E00-$3FFF, $07F8 | goldtwin ($8800-$BFFE, $2B00-$3DFF, $0400-$0FFF; VIC bank 2: $8000-$87FF) |
| goldtwin | $8000-$BFFF, $2B00-$3DFF, $0400-$0FFF | goldfly ($5000-$7FFF, $C000-$CFFF; VIC bank 2) |

## Images are snapshots
Each routine's image is taken on the 6502 simulator after its own `start` has run up to `resume` (zero page, cleared columns, tables,
sprites, the raster code patched for its first frame, built with the sequence's start phases).  Loading the image loads the first frame:
the switch only sets the hardware up (`swstart`: VIC bank, sprites, vectors, `$d011`, the IRQ line from `nirq`), restores the zero page,
copies the few bytes the old routine was still showing (shared sprite buffers), calls the tune once and enters the main loop.  No clearing
at the switch, so it fits between the old routine's last bar and the new one's top IRQ.

## Background copy
In the main loop's idle time (waiting for the next frame): if the next raster IRQ (`nirq`) is more than 11 lines away, `bgstep` copies 32
bytes from the cart (ROML/ROMH, `$01` = $37, interrupts off: the IRQ vector would come from the KERNAL ROM).  The job list (4 bytes a
record: bank, source page, destination page, pages) runs to a barrier per routine; deferred bytes (zero page, shared sprite buffers) are
staged and copied at the switch.  Part4d copies at the end of its update.
