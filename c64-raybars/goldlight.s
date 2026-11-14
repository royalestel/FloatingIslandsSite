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
.ifndef NTSC
NTSC      = 0           ; -Wa -DNTSC=1: 6567R8, 65-cycle lines (one more nop a row, and in irq2's wait)
.endif
.ifndef MUSIC
MUSIC     = NTSC        ; call the tune (resident at $1000, play $1003) 5 frames in 6: the cartridge
.endif
MC        = $03ff       ; the tune's frame counter, shared by all the parts that play it
        .include "goldchain.inc"
.ifndef ENDF
ENDF      = 0           ; CHAIN: frames to show before the switch to the next routine (0: for ever)
.endif
MUSIC_PLAY = $1003
ROWSIZE   = SEGS*SEGSIZE + 7 + NTSC ; + bit $ea (2) + 5 nops (+ 1 on NTSC) = 47 / 48 bytes
BARH      = 24          ; gold lines
PAD       = 6           ; black rows above and below the gold
YBASE     = 135         ; raster line of the bar's top row when centred (goldtilt's: the bar moves on from it without a jump)
YOFFMAX   = 9           ; ... and settles this many lines lower over 16 * YOFFMAX frames: the light sprite needs the room above the bar's highest point
HSLACK   = 80          ; frames over which the highlight's falloff with distance from the light grows in
LYMIN     = 52          ; the light sprite is only seen inside the display window (from line 51): it never rises above this
LZ        = 100         ; light depth in front of the bar
LYREST    = 56          ; light sprite top, this many lines above the bar
DENLINE   = 44          ; top IRQ: clear DEN before raster line $30
HTUNE     = 0           ; extra NOPs to line the first split up with hblank
SPRITE    = $3f00       ; ball sprite data (outside the $1000 char ROM image)
GROWBASE  = $3d40       ; the 7 small sprites of the grow-in (448 bytes, 64-byte blocks below the full ball)
GROWN     = 21          ; frames of the grow-in (3 per stage)
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
runf:    .res 2         ; CHAIN: frames shown
orbit:   .res 1         ; vertical bob angle
frame:   .res 1         ; set by the bar's IRQ: time to build the next frame
hup:     .res 1         ; frames of the highlight's hand-over so far (up to HSLACK)
hsl:     .res 1         ; slack: the light's reach shrinks from everywhere (goldtilt's even highlight) to its own
gsz:     .res 1         ; frames of the light's grow-in so far (up to GROWN)
ycnt:    .res 1         ; frames since the start (up to 16 * YOFFMAX): the bob's slow settling
tilt:    .res 1         ; see-saw angle
lxa:     .res 1         ; light sweep angle
lya:     .res 1         ; light bob angle
y0:      .res 1         ; raster line of the bar's top row (next frame)
ly:      .res 1         ; light sprite top line
lx4:     .res 1         ; light sprite x / 4
dy:      .res 1         ; light - bar, vertical (signed)
dz:      .res 1         ; light - bar, depth
sb:      .res 1         ; this line's specular level
spe_op:  .res 1         ; the highlight operand q = -p (spectab + q + theta2[y])
hlinit:  .res 1         ; the columns have been filled with gold
nlo:     .res 1         ; this column's white run, lines nlo .. nhi-1
nhi:     .res 1
lim:     .res 1         ; (a run's end)
olo:     .res 2*SEGS    ; last frame's run per column
ohi:     .res 2*SEGS
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
        ldx #0                  ; the 7 small balls of the grow-in
@g0:    lda grow,x
        sta GROWBASE,x
        inx
        bne @g0
        ldx #191                ; (191 down to 0: X > 127, so not bpl)
@g1:    lda grow+256,x
        sta GROWBASE+256,x
        dex
        cpx #$ff
        bne @g1
        lda growptr             ; stage 0: a small yellow dot
        sta SPRPTR
        lda $dd02               ; VIC bank 0 ($0000-$3fff): the bank bits are outputs, both high
        ora #$03
        sta $dd02
        lda $dd00
        ora #$03
        sta $dd00
        lda #$15                ; screen at $0400 (sprite pointers at $07f8)
        sta $d018
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
        SETIRQ
        lda #$01
        sta VIC_IRQEN           ; raster IRQ only
        sta VIC_IRQ
.ifdef PH_ORBIT                 ; start phases (-Wa -DPH_ORBIT=n ...: the hand-overs of the gold sequence, the VICE checks)
        lda #PH_ORBIT
        sta orbit
.endif
.ifdef PH_TILT
        lda #PH_TILT
        sta tilt
.endif
.ifdef PH_LXA
        lda #PH_LXA
        sta lxa
.endif
.ifdef PH_LYA
        lda #PH_LYA
        sta lya
.endif
        jsr update              ; first frame
resume:                         ; (CHAIN: the image is a snapshot taken here)
        cli
main:   lda frame               ; the bar has been drawn: build the next frame
        bne @go
        .if CHAIN
        jsr BGSTEP              ; idle: load the next routine
        .endif
        jmp main
@go:
        .if CHAIN && ENDF
        inc runf                ; frames shown: on to the next routine after ENDF
        bne :+
        inc runf+1
:       lda runf
        cmp #<ENDF
        bne :+
        lda runf+1
        cmp #>ENDF
        bne :+
        jmp BGSWITCH            ; (it calls the tune)
:
        .endif
        lda #0
        sta frame
        jsr update
        .if MUSIC
        jsr musicplay           ; the tune, 5 frames in 6 (it was written for 50 Hz)
        .endif
        jmp main

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

; goldfill: the columns' bar lines all gold (once: the highlight runs are drawn over them)
.proc goldfill
        ldy #::BARH-1
:       lda gold,y
        .repeat 2*::SEGS, C
        sta cols + C*36 + ::PAD,y
        .endrep
        dey
        bpl :-
        rts
.endproc

.if MUSIC
musicplay:                      ; 5 calls in 6 frames (NTSC: the tune was written for 50 Hz)
        inc MC
        lda MC
        cmp #6
        bne :+
        lda #0
        sta MC
        rts
:       jmp MUSIC_PLAY
.endif

; =============================================================================
;  update: build the next frame.  Runs after the bar has been drawn and
;  must be done before line DENLINE.
; =============================================================================
.proc update
        ; ---- 1. animate ------------------------------------------------------
.ifndef FREEZE                  ; (-Wa -DFREEZE=1: a still picture, for the VICE checks)
        inc orbit               ; bar bobs up and down
        inc tilt                ; and rocks
        inc lxa                 ; light sweeps back and forth
.endif
        ldy gsz                 ; the light grows in: a small yellow dot to the full ball over GROWN frames
        lda growptr,y
        sta SPRPTR
        cpy #GROWN
        bcs @grown
        inc gsz
@grown:
        ldy hup                 ; the highlight: from goldtilt's even one to the light's own, as the light comes in
        lda #::HSLACK
        sec
        sbc hup
        sta hsl
        cpy #::HSLACK
        bcs @hdone
        inc hup
@hdone:
.ifndef FREEZE
        lda lya
        clc
        adc #3                  ; and bobs a little
        sta lya
.endif

        ; ---- 2. the bar ---------------------------------------------------------
        ldy orbit
        lda ysin,y              ; +-64 lines: goldtilt's bob (same table, same centre, one step a frame)
        clc
        adc #::YBASE
        sta y0
        lda ycnt                ; + 0 .. YOFFMAX lines, one more every 16 frames
        lsr
        lsr
        lsr
        lsr
        clc
        adc y0
        sta y0
        lda ycnt
        cmp #16 * ::YOFFMAX
        bcs @yo
        inc ycnt
@yo:
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
        cmp #::LYMIN
        bcs @lyok
        lda #::LYMIN            ; the bar is high: the light stays at the top of the window, just above it
@lyok:  sta ly
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

::ballready:                    ; the sprite registers and y0 (read by irqtop) are set; the rest only has to be done before the bar
        ; ---- 4. the light seen from the bar: vertical angle ------------------
        ; light centre ly+10, bar centre about y0+20
        lda ly
        sec
        sbc y0
        sec
        sbc #10
        clc
        ldy hsl
        adc hdytab,y            ; + what is left of the angle difference to goldtilt's highlight
        sta dy                  ; about -77..-55 (+ the hand-over)
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
:       sec
        sbc hsl                 ; within the slack the light's distance does not count yet
        bcs :+
        lda #0
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

        ; ---- 6. the columns: gold with the traced highlight as runs of white ------------
        ; A column with threshold t is white where the line's specular level spectab[q + theta2[y]] >= t (q = spe_op):
        ; always one run of lines, hlo_t[q] .. hhi_t[q]-1 (hlrun.inc).  The columns keep their gold between frames:
        ; each restores last frame's run to gold and paints this frame's white (nothing when the run is unchanged).
        lda hlinit
        bne :+
        jsr goldfill            ; (first frame: the columns all gold)
        inc hlinit
:
        .repeat 2*::SEGS, C
        .if (C .mod 2) = 0
        lda thr0 + C/2
        .else
        lda thr1 + C/2
        .endif
        cmp #9
        bcs :+                  ; (above 8: never white)
        adc #>hlo - 1           ; carry clear: table t
        sta .ident(.sprintf("hla%d", C)) + 2
        adc #(>hhi) - (>hlo)
        sta .ident(.sprintf("hlb%d", C)) + 2
        ldx spe_op
.ident(.sprintf("hla%d", C)):
        lda hlo,x
        sta nlo
.ident(.sprintf("hlb%d", C)):
        lda hhi,x
        jmp :++
:       lda #0
        sta nlo
:       sta nhi                 ; new run [nlo, nhi), old run [olo, ohi)
        cmp ohi + C
        bne :+
        lda nlo
        cmp olo + C
        bne :+
        jmp .ident(.sprintf("hlz%d", C))     ; unchanged
:       ; gold again: [olo, min(ohi, nlo)) and [max(olo, nhi), ohi)
        lda ohi + C
        cmp nlo
        bcc :+
        lda nlo
:       sta lim
        ldy olo + C
        cpy lim
        bcs :++
:       lda gold,y
        sta cols + C*36 + ::PAD,y
        iny
        cpy lim
        bcc :-
:       ldy nhi
        cpy olo + C
        bcs :+
        ldy olo + C
:       cpy ohi + C
        bcs :++
:       lda gold,y
        sta cols + C*36 + ::PAD,y
        iny
        cpy ohi + C
        bcc :-
:       ; white: [nlo, min(nhi, olo)) and [max(nlo, ohi), nhi)
        lda nhi
        cmp olo + C
        bcc :+
        lda olo + C
:       sta lim
        ldy nlo
        cpy lim
        bcs :++
        lda #1
:       sta cols + C*36 + ::PAD,y
        iny
        cpy lim
        bcc :-
:       ldy ohi + C
        cpy nlo
        bcs :+
        ldy nlo
:       cpy nhi
        bcs :++
        lda #1
:       sta cols + C*36 + ::PAD,y
        iny
        cpy nhi
        bcc :-
:       lda nlo
        sta olo + C
        lda nhi
        sta ohi + C
.ident(.sprintf("hlz%d", C)):
        .endrep

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
        SETIRQ
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
        .if NTSC
        nop                     ; (NTSC: the compare falls on the line change 2 cycles later)
        .endif
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
        .if NTSC
        nop                     ; + 2 = 65 cycles = 1 NTSC line
        .endif
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
        SETIRQ
        asl VIC_IRQ

        inc frame               ; main loop: build the next frame (irqtop may cut in)

        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
.segment "TABLES"
        .include "lightgrow.inc" ; grow, growptr: the light grows in (small yellow dot -> full ball)
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
        .assert CHAIN || (* <= GROWBASE), error, "program overlaps the sprite data"

.segment "HIGHTAB"               ; CPU-only: above the VIC bank
        .include "hlrun.inc"    ; hlo, hhi: the highlight runs
        .include "goldshared.inc"
