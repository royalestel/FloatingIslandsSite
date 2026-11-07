; =============================================================================
;  cartboot.s -- the EasyFlash boot (bank 0, ROMH): copies the program from the ROML banks into RAM
;  and starts it.  The scene stream stays in ROM (banks SCENE_BANK..) and is read in place.
;
;  At reset the cartridge is in Ultimax mode: RAM only at $0000-$0FFF, ROMH at $E000.  So the code
;  copies a small routine to $0200, switches the cartridge to 8 KB mode ($de02 = $06: ROML at
;  $8000, the machine's normal memory otherwise) and copies IMG_PAGES pages from the ROML banks
;  1.. (8 KB each) to $0801...  Then RAM + I/O ($01 = $35) and a jump to the program's start.
; =============================================================================
        .include "cartboot.inc"          ; IMG_PAGES, PROG_START

        .import __TRAMP_LOAD__
src = $fb
dst = $fd
pgs = $fa

.segment "CODE"
reset:  sei
        cld
        ldx #$ff
        txs
        ldx #(tramp_end - tramp) - 1
@c:     lda __TRAMP_LOAD__,x
        sta $0200,x
        dex
        bpl @c
        jmp $0200

.segment "TRAMP"
tramp:  lda #$2f                         ; the KERNAL normally sets the processor port's direction
        sta $00
        lda #$06                         ; EasyFlash: 8 KB mode (EXROM low, GAME high)
        sta $de02
        lda #$37
        sta $01
        lda #1
        sta $de00                        ; ROML bank 1
        ldx #1
        lda #<$8000
        sta src
        lda #>$8000
        sta src+1
        lda #<$0801
        sta dst
        lda #>$0801
        sta dst+1
        lda #IMG_PAGES
        sta pgs
@page:  ldy #0
@b:     lda (src),y
        sta (dst),y
        iny
        bne @b
        inc src+1
        inc dst+1
        lda src+1
        cmp #$a0
        bne @np
        lda #$80
        sta src+1
        inx
        stx $de00                        ; the next ROML bank
@np:    dec pgs
        bne @page
        lda #$35                         ; RAM + I/O
        sta $01
        jmp PROG_START
tramp_end:

.segment "VECTORS"
        .word reset, reset, reset        ; NMI, RESET, IRQ
