; goldboot.s -- the start of the gold sequence on a cartridge (the test cartridge: the first part; on the real one part4d does this):
; the background loader to $0300, then bgswitch runs the job list: the tune (loaded, then `tinit` starts it) and goldtilt.
        .import __BGLOAD_LOAD__, __BGLOAD_RUN__, __BGLOAD_SIZE__
        .export tinit
.segment "CODE"
start:  sei
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #$35
        sta $01
        lda #$0b                ; screen off
        sta $d011
        lda #0
        sta $d020
        sta $d021
        sta $d015
        ldx #0
:       lda __BGLOAD_LOAD__,x
        sta __BGLOAD_RUN__,x
        inx
        cpx #<__BGLOAD_SIZE__
        bne :-
        lda #0
        sta JOB                 ; the job list: bank 0, $8000
        sta DONE
        sta DONE+1
        lda #$80
        sta JOB+1
        lda #$ff                ; (no tune yet: bgswitch does not call it)
        sta MC
        jmp $0303               ; bgswitch: the tune, then tinit
tinit:  lda #0
        jsr $1000               ; the tune's init
        lda #0
        sta MC
        jmp $0303               ; bgswitch: goldtilt
        .include "bgload.s"
.segment "LOADADDR"
.word $0801
