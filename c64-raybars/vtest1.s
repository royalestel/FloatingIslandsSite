; VICE test of the badline dodge (NTSC): DEN on, one $d011 write a line, Y(L) = ((L mod 4) + 2) & 7 (or the constant: -DCONST=1).
; Any display state (a badline) shows the screen as text; none: black.
        .setcpu "6502"
.ifndef CONST
CONST = 0
.endif
.ifndef NOLOOP
NOLOOP = 0
.endif
.segment "LOADADDR"
        .word $0801
.segment "EXEHDR"
        .word @next, 10
        .byte $9e, "2061", 0
@next:  .word 0
.segment "CODE"
start:  sei
        lda #$35
        sta $01
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda $dd02
        ora #3
        sta $dd02
        lda $dd00
        ora #3                  ; VIC bank 0
        sta $dd00
        lda #$12                ; screen $0400, charset $0800 (RAM: char 1 = a solid block; the cartridge hides the ROM font)
        sta $d018
        ldx #7
        lda #$ff
:       sta $0808,x
        dex
        bpl :-
        lda #$c8
        sta $d016
        lda #0
        sta $d015
        sta $d020
        lda #2
        sta $d021
        ldx #0
:       lda #1
        sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $db00,x
        lda #1
        sta $0400,x
        sta $0500,x
        sta $0600,x
        sta $0700,x
        inx
        bne :-
        .if NOLOOP
        lda #$1b
        sta $d011
        jmp *
        .endif
frame:  lda $d011
        bpl frame
:       lda $d011
        bmi :-
        lda #$1b
        sta $d011
        ldx #44
wl:     cpx $d012
        bne wl
        lda ytab,x
        sta $d011
        inx
        cpx #252
        bne wl
        lda #$1b
        sta $d011
        jmp frame
ytab:
        .repeat 256, I
        .if CONST
        .byte $1b
        .else
        .byte $18 + (((I .mod 4) + 2) .mod 8)
        .endif
        .endrep
