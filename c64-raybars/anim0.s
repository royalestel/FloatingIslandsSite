; =============================================================================
;  ANIM0 -- three blue raster bars slide, circle in depth, and become a floor
;  python3 anim_gen.py
;  cl65 -g -t none -C anim.cfg -Ln anim0.lbl -o anim0.prg anim0.s
;  python3 sim_anim0.py          (checks it on a simulated 6502, renders sim video)
; =============================================================================
;
;  STAGE 1 of the C64 version: plain raster code, one colour per line.
;
;  The picture is 200 lines (raster lines FIRST_LINE ...).  The screen is
;  blanked (DEN=0: no badlines, no DMA), so the whole line is border and one
;  "lda LINEBUF+n / sta $d020" per line is a bar.  Each frame:
;    update   (in the blank, after the last line): clear the 200-byte line
;             buffer, then draw the frame's bars far to near by copying each
;             one's colours from the profile table (a bar T lines thick has its
;             T colours stored, top row first, in four sets: frame parity x
;             parity of its top line, so the flicker pairs come out right);
;             colour 0 (black) is skipped, so black is just the background.
;             The frame's bars (top line, thickness) are read from the scene
;             stream anim_rec.bin: positions are precalculated by anim_gen.py.
;    display  stable raster (double IRQ) and 200 rows of speedcode, each row
;             exactly 63 cycles: lda LINEBUF+n / sta $d020 / 55 cycles of nops.
;
;  Not in this stage: splits (stage 2, animsplit.s) and the live tuning keys.
;  Everything to twiddle is in anim_params.py.
; =============================================================================

        .setcpu "6502"
        .include "anim.inc"

ROWS      = 200
ROWSIZE   = 3 + 3 + 2 + 26      ; lda abs, sta abs, bit $ea, 26 nops = 63 cycles
HTUNE     = 0                   ; extra NOPs to line the write up with hblank
IRQLINE   = FIRST_LINE - 2

VIC_CTRL1  = $d011
VIC_RASTER = $d012
VIC_SPREN  = $d015
VIC_IRQ    = $d019
VIC_IRQEN  = $d01a
VIC_BORDER = $d020
VIC_BG     = $d021
CIA1_ICR   = $dc0d
CIA2_ICR   = $dd0d

; =============================================================================
.segment "ZEROPAGE"
rp:      .res 2         ; scene stream: this frame's entry
cur:     .res 2         ; this frame's bar list (4 bytes a bar)
lastp:   .res 4         ; the last new list of each frame parity (lo, lo, hi, hi)
lastn:   .res 2
nbars:   .res 1
ri:      .res 1         ; index into cur
cnt:     .res 1
fcl:     .res 1         ; frame number
fch:     .res 1
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
        lda #$7f
        sta CIA1_ICR
        sta CIA2_ICR
        lda CIA1_ICR
        lda CIA2_ICR
        lda #$35                ; RAM + I/O
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
        sta VIC_SPREN
        ldx #$7d
@zp:    sta $02,x
        dex
        bpl @zp
        lda #<scene
        sta rp
        lda #>scene
        sta rp+1
        lda #$0b                ; DEN=0: screen off, no badlines
        sta VIC_CTRL1
        lda #IRQLINE
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQEN
        sta VIC_IRQ
        jsr update              ; frame 0
        cli
@idle:  jmp @idle

nmi:    rti

; -----------------------------------------------------------------------------
;  update: the next frame's line buffer
; -----------------------------------------------------------------------------
.proc update
        lda #0                  ; clear: 200 x 4 cycles
        .repeat ::ROWS, N
        sta linebuf + N
        .endrep
        ; ---- this frame's list: new (n, bars) or $ff = same as 2 frames ago ----
        lda fcl
        and #1
        tax                     ; X = frame parity: each keeps its own last list
        ldy #0
        lda (rp),y
        cmp #$ff
        bne @new
        lda lastp,x
        sta cur
        lda lastp+2,x
        sta cur+1
        lda lastn,x
        sta nbars
        inc rp                  ; the stream moves on by 1
        bne @go
        inc rp+1
        jmp @go
@new:   sta nbars
        sta lastn,x
        sec                     ; cur = rp + 1
        lda rp
        adc #0
        sta cur
        sta lastp,x
        lda rp+1
        adc #0
        sta cur+1
        sta lastp+2,x
        lda nbars               ; rp += 1 + 4 n
        asl
        asl
        sec
        adc rp
        sta rp
        bcc @go
        inc rp+1
        ; ---- the bars, far to near: a copy of n colours into the buffer ----
@go:    ldy #0
@bar:   lda nbars
        beq @done
        lda (cur),y             ; source address, first line, rows - 1
        sta @ld + 1
        iny
        lda (cur),y
        sta @ld + 2
        iny
        lda (cur),y
        sta @st + 1
        iny
        lda (cur),y
        iny
        sty ri
        tay
@ld:    lda $ffff,y             ; 4(+1)
@st:    sta linebuf,y           ; 5
        dey                     ; 2
        bpl @ld                 ; 3
        ldy ri
        dec nbars
        jmp @bar
@done:  inc fcl                 ; frame counter; the film loops
        bne @c
        inc fch
@c:     lda fcl
        cmp #<T_END
        bne @ret
        lda fch
        cmp #>T_END
        bne @ret
        lda #0
        sta fcl
        sta fch
        lda #<scene
        sta rp
        lda #>scene
        sta rp+1
@ret:   rts
.endproc

; =============================================================================
;  Stable raster (double IRQ), then 200 rows of speedcode, 63 cycles each.
; =============================================================================
.segment "RASTER"

irq1:   sta save_a
        stx save_x
        sty save_y
        lda #<irq2
        sta $fffe
        lda #>irq2
        sta $ffff
        inc VIC_RASTER
        asl VIC_IRQ
        tsx
        cli
        .repeat 14
        nop
        .endrep

irq2:   txs
        ldx #8
@w:     dex
        bne @w
        bit $00
        lda VIC_RASTER
        cmp VIC_RASTER
        beq @stable
@stable:
        .repeat HTUNE
        nop
        .endrep

block:
        .repeat ROWS, N
        lda linebuf + N         ; 4
        sta VIC_BORDER          ; 4
        bit $ea                 ; 3
        .repeat 26
        nop                     ; 52: 63 cycles in all
        .endrep
        .endrep
blockend:
        .assert blockend - block = ROWS*ROWSIZE, error, "row size mismatch"
        lda #0
        sta VIC_BORDER
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff
        lda #IRQLINE
        sta VIC_RASTER
        asl VIC_IRQ
        jsr update
        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
.segment "PROF"
prof:   .incbin "anim_prof.bin"         ; at $4000 (anim.cfg): anim_gen.py's pointers

.segment "SCENE"
scene:  .incbin "anim_rec.bin"

.segment "BSS"
linebuf: .res 256
