; cosmicstage2.s -- the second stage of the switch into cosmicstrings (mk_gold_ntsc.py assembles it at $0800 with its tables).
; Most of cosmicstrings's RAM ($2B00-$7FFF, the tables in $E000..) is where goldfly runs, so it can only be copied once goldfly is over.  bgswitch has cleared
; the zero page and written the early registers; this copies whole pages from the cartridge (~14 cycles a byte: the screen is black meanwhile), calls the tune
; once a frame (it polls the raster for a wrap), then writes the VIC / CIA registers and the vectors and goes on at cosmicstrings's `resume`.
; Tables (the generator's): `tbl`: [bank][source page][destination page][pages] ... $ff; `late`: [address lo][address hi][value] ... [?][0].
        .setcpu "6502"
BGTICK  = $02AE                 ; bgload.s: the tune, 5 calls in 6
cnt     = $f8
last    = $f9
tix     = $fa
ptr     = $fb                   ; 2

s2:     lda #$7b                ; black, no interrupts (the register lists come at the end); goldfly's light stays: the display stays on
        sta $d011               ; (VICE shows no sprites with DEN off all frame) in an invalid mode (ECM + BMM: all black)
        lda #0
        sta $d01a
        sta $d020
        sta $d021
        lda #$0f
        sta $d019
        sta tix                 ; (0 below)
        jsr rast
        sta last
        lda #0
        sta tix
        lda #$37                ; the cartridge visible
        sta $01
@blk:   ldy tix
        lda tbl,y
        cmp #$ff
        beq @done
        sta $de00
        lda tbl+1,y
        sta @ld + 2
        lda tbl+2,y
        sta @st + 2
        lda tbl+3,y
        sta cnt
        iny
        iny
        iny
        iny
        sty tix
@pg:    ldx #0
@ld:    lda $ff00,x
@st:    sta $ff00,x
        inx
        bne @ld
        inc @ld + 2
        inc @st + 2
        jsr rast                ; the tune once a frame: the raster has wrapped since the last page
        cmp last
        sta last
        bcs @np
        jsr BGTICK
@np:    dec cnt
        bne @pg
        beq @blk
@done:  ldy #0
@r:     lda late,y
        sta ptr
        iny
        lda late,y
        beq @fin
        sta ptr + 1
        iny
        lda late,y
        iny
        ldx #0
        sta (ptr,x)
        jmp @r
@fin:   lda #$35
        sta $01
        jmp RESUME

rast:   lda $d011               ; the raster line, lines 256.. as 255 (their low byte would look like a wrap)
        bmi :+
        lda $d012
        rts
:       lda #$ff
        rts

        .include "cs2tab.inc"   ; tbl, late (generated)
