; =============================================================================
;  GOLDORBIT -- the slanted gold bar with a light that orbits it
;  cl65 -t none -C raybars.cfg -o goldorbit.prg goldorbit.s
; =============================================================================
;
;  Built on goldlight.s (slanted bar from 5 horizontal segments, ball
;  sprite as the point light, display window opened with no badlines).
;  Here the light circles the bar in the y/z plane: it rises in front of
;  the bar, slips behind it at the top, sinks behind it and comes back out
;  in front at the bottom, while drifting slowly from side to side.
;
;   * Depth: 8 pre-drawn ball sizes (radius 3..10 pixels) picked from the
;     light's z, so it shrinks behind the bar and grows in front.
;   * Occlusion: while the light is behind, the sprite rows that fall on
;     the bar's lines (for the segment under the ball) are blanked.  The
;     sprite is drawn into two alternating buffers so it never tears.
;   * Lighting: atan2 now covers all four quadrants.  With the light
;     behind the bar, the reflection angle passes 90 degrees and the front
;     surface loses its highlight, straight from the maths.
;   * Timing: on raster lines where the sprite is drawn, the VIC stops the
;     CPU for a few cycles to fetch its data, in front of the bar or
;     masked behind it.  Each speedcode row's padding starts with a branch
;     whose opcode is patched every frame: with the carry clear, bcs
;     (never taken) costs 2 cycles; bcc (always taken) costs 3 and skips
;     an "inc $ea" -- STEAL cycles shorter.  Rows where the sprite steals
;     cycles get the short version.  The real number of stolen cycles
;     depends on what the CPU is doing at that moment, so STEAL is a
;     constant to tune in VICE.
; =============================================================================

        .setcpu "6502"

ROWS      = 29          ; display rows: 24 bar lines + 4 lines of slant + 1
SEGS      = 5           ; horizontal segments per row
SEGSIZE   = 8           ; bytes per segment: lda #c (2) sta $d020 (3) sta $d021 (3)
PADSIZE   = 7           ; bytes of padding per row (see below)
ROWSIZE   = SEGS*SEGSIZE + PADSIZE  ; 47 bytes
BARH      = 24          ; gold lines
PAD       = 6           ; black rows above and below the gold
YBASE     = 140         ; raster line of the bar's top row when centred
BARMID    = 14          ; bar centre, in rows below the top row
LZ        = 100         ; (unused here: the light's depth comes from the orbit)
DENLINE   = 44          ; top IRQ: clear DEN before raster line $30
HTUNE     = 0           ; extra NOPs to line the first split up with hblank
.ifndef STEAL
STEAL     = 4           ; cycles a row is shortened by on sprite lines: 4 or 6
.endif
SPRBUF0   = $3e00       ; sprite double buffer (pointers $f8 / $fc)
SPRBUF1   = $3f00
SPRPTR    = $07f8       ; sprite 0 pointer (screen at $0400)

; padding: [bcs/bcc +SKIP] [inc $ea] [nop nop nop]
;   bcs, not taken: 2 + 5 + 6     = 13 cycles   (5*10 + 13 = 63)
;   bcc, taken:     3 + (skip)    = 13 - STEAL
.if STEAL = 4
SKIP      = 2           ; skip inc $ea:            3 + 6 = 9  cycles
.elseif STEAL = 6
SKIP      = 3           ; skip inc $ea and a nop:  3 + 4 = 7  cycles
.else
.error "STEAL must be 4 or 6"
.endif
OP_BCS    = $b0
OP_BCC    = $90

VIC_SPR0X  = $d000
VIC_SPR0Y  = $d001
VIC_SPRXHI = $d010
VIC_CTRL1  = $d011
VIC_RASTER = $d012
VIC_SPREN  = $d015
VIC_SPRDH  = $d017
VIC_SPRMC  = $d01c
VIC_SPRDW  = $d01d
VIC_IRQ    = $d019
VIC_IRQEN  = $d01a
VIC_BORDER = $d020
VIC_BG     = $d021
VIC_SPRMC0 = $d025
VIC_SPRMC1 = $d026
VIC_SPR0C  = $d027
CIA1_ICR   = $dc0d
CIA2_ICR   = $dd0d

theta2    = theta2_12   ; per-line reflection angle of a 24-line bar

; =============================================================================
.segment "ZEROPAGE"
orbit:   .res 1         ; bar bob angle
tilt:    .res 1         ; see-saw angle
lxa:     .res 1         ; light sideways drift angle
q:       .res 1         ; light orbit angle
fcount:  .res 1         ; frame counter
y0:      .res 1         ; raster line of the bar's top row (next frame)
ly:      .res 1         ; sprite Y register (next frame)
lx4:     .res 1         ; sprite X register / 4 (next frame)
lptr:    .res 1         ; sprite pointer (next frame)
dy:      .res 1         ; light - bar, vertical (signed)
dz:      .res 1         ; light - bar, depth (signed, + = toward camera)
neg:     .res 1         ; atan2 scratch
sb:      .res 1         ; this line's specular level
jstart:  .res 1         ; first sprite row hidden behind the bar
src:     .res 2         ; ball frame being copied
dst:     .res 2         ; sprite buffer being written
kb:      .res SEGS      ; start index into the column for each segment
thr0:    .res SEGS      ; white on even display rows if sb >= thr0
thr1:    .res SEGS      ; white on odd display rows if sb >= thr1
save_a:  .res 1
save_x:  .res 1
save_y:  .res 1

; =============================================================================
.segment "LOADADDR"
        .word $0801

.segment "EXEHDR"               ; 10 SYS2061
        .word @next, 10
        .byte $9e, "2061", 0
@next:  .word 0

; =============================================================================
.segment "CODE"

start:  sei
        lda #$7f                ; silence the CIA timer interrupts
        sta CIA1_ICR
        sta CIA2_ICR
        lda CIA1_ICR
        lda CIA2_ICR
        lda #$35                ; RAM + I/O, no BASIC/KERNAL ROM
        sta $01
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #<irqtop
        sta $fffe
        lda #>irqtop
        sta $ffff

        lda #0
        sta VIC_BORDER
        sta VIC_BG
        sta $3fff               ; idle-state graphics byte: all background
        ldx #$7d                ; clear our zero page ($02-$7f)
@zp:    sta $02,x
        dex
        bpl @zp
        ldx #(2*PAD+BARH)*SEGS-1        ; clear all columns (black padding)
@col:   sta cols,x
        dex
        bpl @col
        lda #1
        sta VIC_SPREN
        sta VIC_SPRMC           ; multicolour
        lda #0
        sta VIC_SPRDW
        sta VIC_SPRDH
        lda #7                  ; %10: yellow
        sta VIC_SPR0C
        lda #8                  ; %01: orange rim
        sta VIC_SPRMC0
        lda #1                  ; %11: white core
        sta VIC_SPRMC1

        lda #$0b                ; DEN=0 for now; bit 7 = 0
        sta VIC_CTRL1
        lda #DENLINE
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQEN           ; raster IRQ only
        sta VIC_IRQ
        jsr update              ; first frame
        cli
@idle:  jmp @idle               ; everything happens in the IRQs

nmi:    rti                     ; RESTORE key does nothing

; -----------------------------------------------------------------------------
;  atan2: A = angle of (dy, dz) in brads, all four quadrants:
;  0 = toward the camera, +64 = straight down, 128 = straight behind.
; -----------------------------------------------------------------------------
.proc atan2
        lda dz
        bpl zpos
        eor #$ff
        clc
        adc #1
zpos:   tay                     ; |dz|
        lda dy
        bpl ypos
        eor #$ff
        clc
        adc #1
ypos:   tax                     ; |dy|
        lda log2tab,x
        sec
        sbc log2tab,y           ; log2|dy| - log2|dz|
        bcc small
        tax
        lda atanhi,x            ; |dy| >= |dz| : 32..64
        jmp quad
small:  eor #$ff                ; carry is clear, so this negates
        adc #1
        tax
        lda atanlo,x            ; |dy| <  |dz| : 0..32
quad:   bit dz
        bpl front
        eor #$ff                ; behind: 128 - m
        sec
        adc #128
front:  bit dy
        bpl done
        eor #$ff
        clc
        adc #1
done:   rts
.endproc

; =============================================================================
;  update: build the next frame.  Runs after the bar has been drawn and
;  must be done before line DENLINE.
; =============================================================================
.proc update
        ; ---- 1. animate ------------------------------------------------------
        inc fcount
        inc orbit               ; bar bobs up and down
        inc tilt                ; and rocks
        inc q                   ; light orbits the bar
        lda fcount
        and #1
        bne :+
        inc lxa                 ; and drifts sideways at half speed
:

        ; ---- 2. the bar ---------------------------------------------------------
        ldy orbit
        lda lsin,y              ; +-44 ...
        cmp #$80
        ror                     ; ... /2 = +-22 lines
        clc
        adc #::YBASE
        sta y0
        ldy tilt
        .repeat ::SEGS, K
        lda .ident(.sprintf("lkbase%d", K)),y
        sta kb+K
        .endrep

        ; ---- 3. the light: where it is, how big --------------------------------
        ldy q
        lda orby,y
        sta dy                  ; light - bar centre, vertical: +-40
        lda orbz,y
        sta dz                  ; light depth: +-40, + = in front
        lda y0
        clc
        adc #::BARMID - 11      ; sprite centre row is 10, shown from Y+1
        clc
        adc dy
        sta ly
        ldy lxa
        lda lx4tab,y
        sta lx4

        ; ---- 4. the highlight angle ----------------------------------------------
        jsr atan2
        eor #$ff
        clc
        adc #1                  ; -p
        sta spe_op

        ; ---- 5. per segment: distance from the light -> highlight threshold ----
        ; ball centre x/4 = lx4 + 3; segment k centre x/4 = 8 + 20k.
        .repeat ::SEGS, K
        lda lx4
        sec
        sbc #5 + 20*K
        bcs :+
        eor #$ff
        adc #1                  ; carry clear: negate
:       lsr
        lsr
        lsr                     ; drop = |a| / 32 pixels
        clc
        adc #1
        sta thr0+K
        adc #2
        sta thr1+K
        .endrep
        lda y0
        and #1
        beq evenrows            ; col0 rows are even screen lines: as set
        .repeat ::SEGS, K       ; otherwise swap the thresholds
        lda thr0+K
        ldx thr1+K
        sta thr1+K
        stx thr0+K
        .endrep
evenrows:

        ; ---- 6. the columns: gold + traced highlight per segment ---------------
        ldy #::BARH-1
line:   ldx theta2,y
spe_op = * + 1
        lda spectab,x           ; specular 0..8
        cmp #1
        bcc dark
        jmp lit
dark:   lda gold,y              ; no highlight anywhere on this line
        .repeat ::SEGS, K
        sta cols + (2*K)*36 + ::PAD,y
        sta cols + (2*K+1)*36 + ::PAD,y
        .endrep
        dey
        bmi :+
        jmp line
:       jmp patch
lit:    sta sb
        .repeat ::SEGS, K
        lda sb
        cmp thr0+K
        lda #1                  ; white (flags from cmp kept)
        bcs :+
        lda gold,y
:       sta cols + (2*K)*36 + ::PAD,y
        lda sb
        cmp thr1+K
        lda #1
        bcs :+
        lda gold,y
:       sta cols + (2*K+1)*36 + ::PAD,y
        .endrep
        dey
        bmi patch
        jmp line

        ; ---- 7. patch the 145 colours into the speedcode ---------------------
patch:
        .repeat ::SEGS, K
        ldx kb+K
          .repeat ::ROWS, RR
        lda cols + (2*K + (RR .mod 2))*36 + RR,x
        sta block + RR*::ROWSIZE + K*::SEGSIZE + 1
          .endrep
        .endrep

        ; ---- 8. shorten the rows where the sprite steals cycles ---------------
        ; The VIC fetches sprite data for line L at the end of line L-1, and
        ; the sprite is drawn on lines ly+1 .. ly+21.  Row r is on line
        ; y0 + r, so it loses cycles if 0 <= y0 + r - ly < 21.
        lda y0
        sec
        sbc ly
        tax                     ; y0 - ly
        .repeat ::ROWS, RR
        txa
        clc
        adc #RR
        cmp #21
        lda #OP_BCS             ; normal row (flags from cmp kept)
        bcs :+
        lda #OP_BCC             ; sprite row: STEAL cycles shorter
:       sta block + RR*::ROWSIZE + ::SEGS*::SEGSIZE
        .endrep

        ; ---- 9. the ball: pick its size, hide what is behind the bar -----------
        ; frame = balls + 64 * size; draw into the buffer not on screen now
        ldy q
        lda orbsize,y
        lsr
        lsr                     ; size * 64 = (size >> 2) * 256 + (size & 3) * 64
        clc
        adc #>balls
        sta src+1
        lda orbsize,y
        and #3
        lsr
        ror
        ror                     ; (size & 3) * 64
        clc
        adc #<balls
        sta src
        bcc :+
        inc src+1
:       lda lptr
        cmp #<(SPRBUF0/64)
        beq use1
        lda #<(SPRBUF0/64)      ; shown now: buffer 1 -> draw into buffer 0
        sta lptr
        lda #>SPRBUF0
        bne setdst
use1:   lda #<(SPRBUF1/64)
        sta lptr
        lda #>SPRBUF1
setdst: sta dst+1
        lda #0
        sta dst

        ; rows hidden: only when behind (dz < 0).  The bar's lines for the
        ; segment under the ball are y0 + off .. y0 + off + 23; sprite row j
        ; is on line ly + 1 + j.  Hidden if 0 <= j - jstart < 24 with
        ; jstart = y0 + off - ly - 1.
        lda #$80                ; in front: jstart far away, nothing hidden
        bit dz
        bpl front
        lda lx4                 ; segment under the ball: (lx4 + 5) / 20
        clc
        adc #5
        ldx #0
:       cmp #20
        bcc :+
        sbc #20
        inx
        cpx #::SEGS-1
        bne :-
:       lda #6
        sec
        sbc kb,x                ; off = 6 - kb
        clc
        adc y0
        sec
        sbc ly
        sec
        sbc #1
front:  sta jstart

        ldx #0                  ; sprite row j
        ldy #0                  ; byte offset 3j
row:    txa
        sec
        sbc jstart
        cmp #24
        bcc hide
        lda (src),y
        sta (dst),y
        iny
        lda (src),y
        sta (dst),y
        iny
        lda (src),y
        sta (dst),y
        iny
        jmp nextrow
hide:   lda #0
        sta (dst),y
        iny
        sta (dst),y
        iny
        sta (dst),y
        iny
nextrow:
        inx
        cpx #21
        bne row
        rts
.endproc

; =============================================================================
;  Top IRQ: keep DEN clear across raster line $30 (no badlines this frame),
;  set it again before line $33 (the display window opens).  The sprite
;  registers are set here, before it is displayed.
; =============================================================================
irqtop: pha
        lda #$0b                ; DEN=0
        sta VIC_CTRL1
        lda ly
        sta VIC_SPR0Y
        lda lptr
        sta SPRPTR
        lda lx4
        asl
        asl                     ; x = 4 * lx4, carry = bit 8
        sta VIC_SPR0X
        lda #0
        rol
        sta VIC_SPRXHI
:       lda VIC_RASTER
        cmp #$31                ; until line $30 is completely over
        bne :-
        lda #$1b                ; DEN=1: window opens at line $33
        sta VIC_CTRL1
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff
        lda y0
        sec
        sbc #2                  ; 2 lines above the bar
        sta VIC_RASTER
        asl VIC_IRQ
        pla
        rti

; =============================================================================
;  Stable raster (double IRQ), then the bar: 29 rows of speedcode, each
;  row exactly 63 cycles, or 63 - STEAL on lines where the sprite steals.
; =============================================================================
.segment "RASTER"

irq1:   sta save_a
        stx save_x
        sty save_y
        lda #<irq2
        sta $fffe
        lda #>irq2
        sta $ffff
        inc VIC_RASTER          ; second IRQ on the very next line
        asl VIC_IRQ
        tsx
        cli
        .repeat 14              ; irq2 lands inside these: 0-1 cycle jitter
        nop
        .endrep

irq2:   txs                     ; throw away irq2's stack frame
        ldx #8
@w:     dex
        bne @w
        bit $00
        lda VIC_RASTER
        cmp VIC_RASTER          ; still the same line?
        beq @stable             ; +1 cycle if so: last cycle of jitter gone
@stable:
        .repeat HTUNE
        nop
        .endrep
        clc                     ; the row branches rely on carry clear

block:                          ; ---- the slanted bar ---------------------
        .repeat ROWS, RR
          .repeat SEGS
        lda #0                  ; 2   patched every frame
        sta VIC_BORDER          ; 4   border part of the line
        sta VIC_BG              ; 4   display-window part
          .endrep               ;     = 10 cycles = 80 pixels per segment
        .byte OP_BCS, SKIP      ; 2   (bcc: 3, skipping ahead)
        inc $ea                 ; 5
        nop                     ; 6
        nop
        nop                     ; 5*10 + 13 = 63 cycles = 1 PAL line
        .assert >(block + RR*ROWSIZE + SEGS*SEGSIZE + 2) = >(block + RR*ROWSIZE + SEGS*SEGSIZE + 2 + SKIP), error, "row branch crosses a page"
        .endrep
blockend:
        .assert blockend - block = ROWS*ROWSIZE, error, "row size mismatch"
        lda #0
        sta VIC_BORDER
        sta VIC_BG

        lda #<irqtop
        sta $fffe
        lda #>irqtop
        sta $ffff
        lda #DENLINE
        sta VIC_RASTER
        asl VIC_IRQ

        jsr update              ; build the next frame

        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
.segment "TABLES"

        .include "tables.inc"   ; spectab etc. (page aligned, see gen_tables)
        .include "light.inc"    ; lkbase0..4, lx4tab
        .include "orbit.inc"    ; orby, orbz, orbsize, balls
        .assert <spectab = 0, error, "spectab must be page aligned"

.segment "RAMPS"
; The gold bar, top to bottom, one C64 colour per scanline (24 lines).
gold:   .byte 9,8,12,7,7,0,9,8,15,7,7,1,7,1,7,0,0,0,9,12,10,12,8,9
        .assert * - gold = BARH, error, "gold must have one colour per line"

; =============================================================================
.segment "BSS"
; 2 columns per segment (even / odd display rows), 36 entries each:
; 6 black, 24 gold-or-white, 6 black.
cols:   .res 2*SEGS*(2*PAD+BARH)
        .assert * <= SPRBUF0, error, "program overlaps the sprite buffers"
