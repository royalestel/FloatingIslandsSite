; cartboot_all.s -- EasyFlash boot for the whole routine.  Bank 0 ROMH: reset copies the loader to $0200 and runs it.
; The loader ($0200, resident) loads part number [$02ff] (table: bank, pages, start lo, start hi) from the ROML banks to $0801,
; increments [$02ff] and jumps to the part.  Each part ends with `jmp $0200`, which loads the next one.
        .include "cartparts.inc"
        .import __TRAMP_LOAD__
src = $fb
dst = $fd
pgs = $fa
bk  = $f9
jv  = $f7
skp = $f6
PART = $02ff

.segment "CODE"
reset:  sei
        cld
        ldx #$ff
        txs
        ldx #0
@c:     lda __TRAMP_LOAD__,x
        sta $0200,x
        inx
        cpx #(tramp_end - tramp)
        bne @c
        lda #0
        sta PART
        jmp $0200

.segment "TRAMP"
tramp:  sei
        cld
        ldx #$ff
        txs
        lda #$2f
        sta $00
        lda #$07
        sta $de02
        lda #$37
        sta $01
        lda PART
        cmp #NPARTS
        bcc @ok
        lda #0
        sta PART
@ok:    lda PART
        asl
        asl
        tax
        lda ptab,x
        sta bk
        sta $de00
        lda ptab+1,x
        sta pgs
        lda ptab+2,x
        sta jv
        lda ptab+3,x
        sta jv+1
        and #$80                ; bit 7 of the start address: the part sits above the tune (the image bytes for $1000.. go to $2B00..)
        sta skp
        lda jv+1
        and #$7f
        sta jv+1
        inc PART
        lda #<$8000
        sta src
        lda #>$8000
        sta src+1
        lda #<$0800
        sta dst
        lda #>$0800
        sta dst+1
@page:  ldy #0
@b:     lda (src),y
        sta (dst),y
        iny
        bne @b
        inc src+1
        inc dst+1
        lda skp
        beq @nsk
        lda dst+1
        cmp #$10
        bne @nsk
        lda #$2b
        sta dst+1
        lda #0
        sta skp
@nsk:
        lda src+1
        cmp #$c0
        bne @np
        lda #$80
        sta src+1
        inc bk
        lda bk
        sta $de00
@np:    dec pgs
        bne @page
        lda #$35
        sta $01
        jmp (jv)
ptab:   PARTS_TABLE
tramp_end:

.segment "VECTORS"
        .word reset, reset, reset
