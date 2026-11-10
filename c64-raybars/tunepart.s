; TEST PART (not in the routine): loads the tune at $1000 and starts it, then chains to the next part (so a single part can be run with the music on).
.segment "ZEROPAGE"
zpad:   .res 1
.segment "LOADADDR"
        .word $0801
.segment "EXEHDR"
        .word @next, 10
        .byte $9e, "2061", 0
@next:  .word 0
.segment "CODE"
start:  sei
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #$2f
        sta $00
        lda #$35
        sta $01
        lda #$0f
        sta $d418
        lda #0
        jsr $1000
        jmp $0200
