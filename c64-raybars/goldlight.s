; =============================================================================
;  GOLDLIGHT -- a slanted gold raster bar lit by a visible sprite light
;  cl65 -t none -C raybars.cfg -o goldlight.prg goldlight.s
; =============================================================================
;
;  Like goldtilt.s (a staircase of horizontal segments reads as one slanted
;  bar), plus a glowing ball sprite: the point light.  It sweeps back and
;  forth above the bar, and the bar's white highlight is thickest in the
;  segment nearest the ball.
;
;  SHOWING A SPRITE WITHOUT BADLINES
;  With the screen blanked (DEN=0) the border covers everything, sprites
;  included.  But badlines are enabled once per frame: only if DEN is set
;  during raster line $30.  So DEN is cleared across line $30 and set again
;  before line $33, where the vertical border opens.  The display window
;  then opens with no badlines all frame (idle state: background colour
;  $d021 plus the byte at $3fff, which is 0).
;  So every split writes both registers: $d020 for the border, $d021 for
;  the window.  lda #c / sta $d020 / sta $d021 = 10 cycles = 80 pixels, so
;  5 segments span the visible line; the slant uses offsets 0..4.
;
;  SPRITE TIMING
;  A sprite steals CPU cycles only on the lines where it is drawn.  The
;  ball stays above the bar and never shares a raster line with the bar's
;  speedcode or its stabilising double IRQ, so every row stays 63 cycles.
;
;  THE HIGHLIGHT PER SEGMENT
;  For a cylinder along x, a point light at horizontal distance a from a
;  segment gives  spec = ((rho / sqrt(rho^2 + a^2)) * cos(2t - p))^n,
;  rho being the light's distance in the y/z plane: full strength under the
;  light, falling off sideways.  Here the falloff is approximated as
;  "subtract |a|/32 levels" from the 0..8 specular level of each line, so
;  the white is thickest under the ball and thins out segment by segment.
; =============================================================================

        .setcpu "6502"

ROWS      = 29          ; display rows: 24 bar lines + 4 lines of slant + 1
SEGS      = 5           ; horizontal segments per row
SEGSIZE   = 8           ; bytes per segment: lda #c (2) sta $d020 (3) sta $d021 (3)
ROWSIZE   = SEGS*SEGSIZE + 7    ; + bit $ea (2) + 5 nops = 47 bytes
BARH      = 24          ; gold lines
PAD       = 6           ; black rows above and below the gold
YBASE     = 170         ; raster line of the bar's top row when centred
LZ        = 100         ; light depth in front of the bar
LYREST    = 56          ; light sprite top, this many lines above the bar
DENLINE   = 44          ; top IRQ: clear DEN before raster line $30
HTUNE     = 0           ; extra NOPs to line the first split up with hblank
SPRITE    = $3f00       ; ball sprite data (outside the $1000 char ROM image)
SPRPTR    = $07f8       ; sprite 0 pointer (screen at $0400)

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
orbit:   .res 1         ; vertical bob angle
tilt:    .res 1         ; see-saw angle
lxa:     .res 1         ; light sweep angle
lya:     .res 1         ; light bob angle
y0:      .res 1         ; raster line of the bar's top row (next frame)
ly:      .res 1         ; light sprite top line
lx4:     .res 1         ; light sprite x / 4
dy:      .res 1         ; light - bar, vertical (signed)
dz:      .res 1         ; light - bar, depth
sb:      .res 1         ; this line's specular level
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
        ldx #63                 ; the ball sprite
@spr:   lda ball,x
        sta SPRITE,x
        dex
        bpl @spr
        lda #<(SPRITE/64)
        sta SPRPTR
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
;  atan2: A = atan(dy / dz) in brads, signed.  dz > 0 always.
; -----------------------------------------------------------------------------
.proc atan2
        lda dy
        beq done                ; light level with the bar
        bpl pos
        eor #$ff
        clc
        adc #1
pos:    tax
        lda log2tab,x
        ldx dz
        sec
        sbc log2tab,x           ; log2|dy| - log2 dz
        bcc small
        tax
        lda atanhi,x            ; |dy| >= dz : 32..64
        jmp sign
small:  eor #$ff                ; carry is clear, so this negates
        adc #1
        tax
        lda atanlo,x            ; |dy| <  dz : 0..32
sign:   bit dy
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
        inc orbit               ; bar bobs up and down
        inc tilt                ; and rocks
        inc lxa                 ; light sweeps back and forth
        lda lya
        clc
        adc #3                  ; and bobs a little
        sta lya

        ; ---- 2. the bar ---------------------------------------------------------
        ldy orbit
        lda lsin,y              ; +-44 lines
        clc
        adc #::YBASE
        sta y0
        ldy tilt
        .repeat ::SEGS, K
        lda .ident(.sprintf("lkbase%d", K)),y
        sta kb+K
        .endrep

        ; ---- 3. the light: sprite position -------------------------------------
        ldy lya
        lda y0
        sec
        sbc #::LYREST
        clc
        adc lyofftab,y          ; +-11
        sta ly
        sta VIC_SPR0Y
        ldy lxa
        lda lx4tab,y
        sta lx4
        asl
        asl                     ; x = 4 * lx4, carry = bit 8
        sta VIC_SPR0X
        lda #0
        rol
        sta VIC_SPRXHI

        ; ---- 4. the light seen from the bar: vertical angle ------------------
        ; light centre ly+10, bar centre about y0+20
        lda ly
        sec
        sbc y0
        sec
        sbc #10
        sta dy                  ; about -77..-55
        lda #::LZ
        sta dz
        jsr atan2
        eor #$ff
        clc
        adc #1                  ; -p
        sta spe_op

        ; ---- 5. per segment: how far from the light, so how much highlight ----
        ; segment k's centre is at sprite x 32 + 80k, i.e. x/4 = 8 + 20k.
        ; drop = |lx4 - segx4| / 8 levels (|a| / 32 pixels).
        ; Thresholds: white if s - drop >= 3 (solid) or >= 1 on every other
        ; screen line (light yellow).  col0 rows are screen lines of parity
        ; y0&1; even screen lines take the >=2 threshold.
        .repeat ::SEGS, K
        lda lx4
        sec
        sbc #8 + 20*K
        bcs :+
        eor #$ff
        adc #1                  ; carry clear: negate
:       lsr
        lsr
        lsr                     ; drop
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
        ;  row r, segment k = column_k[r + kb_k], kb_k = 6 - off_k
patch:
        .repeat ::SEGS, K
        ldx kb+K
          .repeat ::ROWS, RR
        lda cols + (2*K + (RR .mod 2))*36 + RR,x
        sta block + RR*::ROWSIZE + K*::SEGSIZE + 1
          .endrep
        .endrep
        rts
.endproc

; =============================================================================
;  Top IRQ: keep DEN clear across raster line $30 (no badlines this frame),
;  set it again before line $33 (the display window opens).
; =============================================================================
irqtop: pha
        lda #$0b                ; DEN=0
        sta VIC_CTRL1
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
;  row exactly 63 cycles with no branches.
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

block:                          ; ---- the slanted bar ---------------------
        .repeat ROWS
          .repeat SEGS
        lda #0                  ; 2   patched every frame
        sta VIC_BORDER          ; 4   border part of the line
        sta VIC_BG              ; 4   display-window part
          .endrep               ;     = 10 cycles = 80 pixels per segment
        bit $ea                 ; 3
        nop                     ; 10
        nop
        nop
        nop
        nop                     ; 5*10 + 3 + 10 = 63 cycles = 1 PAL line
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
        .include "light.inc"    ; lkbase0..4, lx4tab, lyofftab, ball
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
        .assert * <= SPRITE, error, "program overlaps the sprite data"
