; =============================================================================
;  GOLDTILT -- one slanted, ray-lit gold raster bar for the C64 (PAL)
;  cl65 -t none -C raybars.cfg -o goldtilt.prg goldtilt.s
; =============================================================================
;
;  A raster bar can only change colour where the CPU writes $d020, so a
;  bar normally can't slant.  Here every scanline of the bar is split into
;  6 segments, 64 pixels wide (one "lda #c / sta $d020 / nop" = 8 cycles
;  each: 6 x 64 = 384 pixels, the whole visible line).  Segment k is drawn
;  shifted down by off_k = 0..5 lines, so the bar becomes a staircase that
;  reads as one slanted bar.
;
;  The bar is padded with 6 black rows above and 6 below, so every segment
;  is the same 36-entry column read at a different shift:
;       colour(row r, segment k) = column[r + 6 - off_k]
;  The 30 display rows are unrolled "speedcode" whose lda #immediates are
;  rewritten every frame (180 of them).  The offsets follow
;  off_k = round(2.5 + (k - 2.5) * sin(tilt)), so the bar rocks like a
;  see-saw from one slant, through flat, to the other.
;
;  The bar's 24 lines are the fixed gold pattern; only the white specular
;  highlight is traced (as in raybars.s STYLE=2): faint highlight puts
;  white on every other screen line, strong highlight is solid white, and
;  it covers every line of the bar.
;
;  The screen is blanked (DEN=0, no badlines) and black except for the
;  bar, so a stable double IRQ fires 2 lines above the bar each frame and
;  everything else is free time.
; =============================================================================

        .setcpu "6502"

ROWS      = 30          ; display rows: 24 bar lines + 5 lines of slant + 1
SEGS      = 6           ; horizontal segments per row
SEGSIZE   = 6           ; bytes per segment: lda #c (2) sta $d020 (3) nop (1)
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
ROWSIZE   = SEGS*SEGSIZE + 8 + NTSC ; + bit $ea (2) + 6 nops (+ 1 on NTSC) = 44 / 45 bytes
BARH      = 24          ; gold lines
PAD       = 6           ; black rows above and below the gold
YBASE     = 135         ; raster line of the bar's top row when centred
LZ        = 100         ; light depth in front of the bar
HTUNE     = 0           ; extra NOPs to line the first split up with hblank

VIC_CTRL1  = $d011
VIC_RASTER = $d012
VIC_SPREN  = $d015
VIC_IRQ    = $d019
VIC_IRQEN  = $d01a
VIC_BORDER = $d020
VIC_BG     = $d021
CIA1_ICR   = $dc0d
CIA2_ICR   = $dd0d

theta2    = theta2_12   ; per-line reflection angle of a 24-line bar

; =============================================================================
.segment "ZEROPAGE"
runf:    .res 2         ; CHAIN: frames shown
quit:    .res 1         ; CHAIN: ENDF reached, the idle loop switches
orbit:   .res 1         ; vertical bob angle
lang:    .res 1         ; light bob angle
tilt:    .res 1         ; see-saw angle
y0:      .res 1         ; raster line of the bar's top row (next frame)
dy:      .res 1         ; light - bar, vertical (signed)
dz:      .res 1         ; light - bar, depth
kb:      .res SEGS      ; start index into the column for each segment
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

start:  jsr hwinit
        ldx #$7d                ; clear our zero page ($02-$7f)
        lda #0
@zp:    sta $02,x
        dex
        bpl @zp
        ldx #2*PAD+BARH-1       ; clear both columns (black padding)
@col:   sta col0,x
        sta col1,x
        dex
        bpl @col
.ifdef PH_ORBIT                 ; start phases (-Wa -DPH_ORBIT=n ...: the hand-overs of the gold sequence, the VICE checks)
        lda #PH_ORBIT
        sta orbit
.endif
.ifdef PH_TILT
        lda #PH_TILT
        sta tilt
.endif
.ifdef PH_LANG
        lda #PH_LANG
        sta lang
.endif
        jsr update              ; first frame; also sets the IRQ line
resume:                         ; (CHAIN: the image is a snapshot taken here)
        cli
@idle:
.if CHAIN
        lda quit
        beq :+
        jmp BGSWITCH            ; shown ENDF frames: on to the next routine
:       jsr BGSTEP              ; idle: load the next routine
.endif
        jmp @idle               ; everything happens in the IRQ

hwinit: sei
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
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff

        lda #0
        sta VIC_BORDER
        sta VIC_BG
        sta VIC_SPREN           ; no sprites: they would steal raster cycles
        lda #$0b                ; DEN=0: screen off, no badlines, bit 7 = 0
        sta VIC_CTRL1
        lda #$01
        sta VIC_IRQEN           ; raster IRQ only
        lda #$0f
        sta VIC_IRQ             ; (acknowledge whatever is pending)
        rts

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
;  update: build the next frame.  Runs after the bar has been drawn.
; =============================================================================
.proc update
        ; ---- 1. animate ------------------------------------------------------
.ifndef FREEZE                  ; (-Wa -DFREEZE=1: a still picture, for the VICE checks)
        inc orbit               ; bob up and down
        lda lang
        clc
        adc #3                  ; light bobs at a different speed
        sta lang
        inc tilt                ; rock the slant
.endif

        ; ---- 2. where the bar is and how it slants ----------------------------
        ldy orbit
        lda ysin,y
        clc
        adc #YBASE
        sta y0
        ldy tilt
        .repeat ::SEGS, K
        lda .ident(.sprintf("kbase%d", K)),y
        sta kb+K
        .endrep

        ; ---- 3. the light, seen from the bar -----------------------------------
        ldy lang
        lda lsin,y
        ldy orbit
        sec
        sbc ysin,y
        sta dy                  ; -108..108
        lda #::LZ
        sta dz
        jsr atan2               ; A = p
        eor #$ff
        clc
        adc #1                  ; -p
        sta spe_op              ; patch: specular table[2t - p]

        ; ---- 4. the two columns: gold + traced highlight --------------------
        ; col0 is used on even display rows, col1 on odd ones.  They differ
        ; only in the highlight's dither, which follows SCREEN line parity.
        lda y0
        and #1
        asl
        asl
        asl
        asl                     ; 0 or 16: hilite table for even rows
        sta hl0_op
        eor #16
        sta hl1_op
        ldy #::BARH-1
line:   ldx theta2,y
spe_op = * + 1
        lda spectab,x           ; specular 0..8
        tax
hl0_op = * + 1
        lda hilite,x            ; white on an even row?
        bne :+
        lda gold,y
:       sta col0+::PAD,y
hl1_op = * + 1
        lda hilite,x            ; white on an odd row?
        bne :+
        lda gold,y
:       sta col1+::PAD,y
        dey
        bpl line

        ; ---- 5. patch the 180 colours into the speedcode ---------------------
        ;  row r, segment k = column[r + kb_k], kb_k = 6 - off_k
        .repeat ::SEGS, K
        ldx kb+K
          .repeat ::ROWS, RR
            .if RR .mod 2 = 0
        lda col0+RR,x
            .else
        lda col1+RR,x
            .endif
        sta block + RR*::ROWSIZE + K*::SEGSIZE + 1
          .endrep
        .endrep

        ; ---- 6. next frame's interrupt: 2 lines above the bar ----------------
        lda y0
        sec
        sbc #2
        SETIRQ
        rts
.endproc

; =============================================================================
;  Stable raster (double IRQ), then the bar: 30 rows of speedcode, each
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
        sta VIC_BORDER          ; 4
        nop                     ; 2   = 8 cycles = 64 pixels per segment
          .endrep
        bit $ea                 ; 3
        nop                     ; 12
        nop
        nop
        nop
        nop
        nop                     ; 6*8 + 3 + 12 = 63 cycles = 1 PAL line
        .if NTSC
        nop                     ; + 2 = 65 cycles = 1 NTSC line
        .endif
        .endrep
blockend:
        .assert blockend - block = ROWS*ROWSIZE, error, "row size mismatch"
        lda #0
        sta VIC_BORDER

        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff
        asl VIC_IRQ

        .if CHAIN && ENDF
        inc runf
        bne :+
        inc runf+1
:       lda runf
        cmp #<ENDF
        bne :+
        lda runf+1
        cmp #>ENDF
        bne :+
        inc quit                ; the idle loop switches (bgswitch calls the tune)
        jmp @out
:
        .endif
        jsr update              ; build the next frame
        .if MUSIC
        jsr musicplay           ; the tune, 5 frames in 6 (it was written for 50 Hz)
        .endif
@out:

        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
.segment "TABLES"
        .include "tilt.inc"     ; kbase0..5[tilt]
        .assert <spectab = 0, error, "spectab must be page aligned"

.segment "RAMPS"
; Highlight per specular level 0..8: 0 = keep the gold colour, 1 = white.
; Levels 2-3 make white on one screen-line parity only (blends with the
; yellow to light yellow), 4+ is solid white.
hilite: .byte 0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1   ; even screen lines
        .byte 0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1   ; odd screen lines
        .assert <hilite = 0, error, "hilite must be page aligned"

; The gold bar, top to bottom, one C64 colour per scanline (24 lines).
gold:   .byte 9,8,12,7,7,0,9,8,15,7,7,1,7,1,7,0,0,0,9,12,10,12,8,9
        .assert * - gold = BARH, error, "gold must have one colour per line"

; =============================================================================
.segment "BSS"
col0:   .res 2*PAD+BARH         ; the bar column for even display rows
col1:   .res 2*PAD+BARH         ; ... and for odd ones
        .include "goldshared.inc"
