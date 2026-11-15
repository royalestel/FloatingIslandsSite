; VICE timing test (NTSC) for the tilted bar rows: six $d021 segments a row, the badline dodge each row (DEN on), the ship's two
; sprites stealing cycles on their DMA rows.  A row that is too long or too short shows as a slanted segment edge; a badline as
; white blocks (the screen is full of solid characters).   python3 gen_vtest2.py; build with vice_gold.cart("vtest2", [], out)
        .setcpu "6502"
ROW0  = 70
NROWS = 120
SPRY  = 120
.ifndef HTUNE
HTUNE = 3              ; (VICE: segment 1 starts at sprite x 56, as GOLDship)
.endif
.segment "LOADADDR"
        .word $0801
.segment "EXEHDR"
        .word @next, 10
        .byte $9e, "2061", 0
@next:  .word 0
.segment "ZEROPAGE"
sav_a:  .res 1
sav_x:  .res 1
sav_y:  .res 1
sav_s:  .res 1
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
        lda #$12                ; screen $0400, charset $0800 (char 1 = a solid block)
        sta $d018
        ldx #7
        lda #$ff
:       sta $0808,x
        dex
        bpl :-
        lda #0
        sta $3fff               ; the idle byte: none
        lda #$c8
        sta $d016
        lda #0
        sta $d020
        sta $d021
        ldx #0
:       lda #1
        sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $db00,x
        sta $0400,x
        sta $0500,x
        sta $0600,x
        sta $0700,x
        inx
        bne :-
        ldx #62                 ; the ship: two solid sprites side by side (as cosmicstrings: x 160 / 184, multicolour)
        lda #$ff
:       sta $0340,x
        dex
        bpl :-
        lda #13
        sta $07f8
        sta $07f9
        lda #3
        sta $d015
        sta $d01c
        lda #0
        sta $d017
        sta $d01d
        sta $d010
        lda #160
        sta $d000
        lda #184
        sta $d002
        lda #SPRY
        sta $d001
        sta $d003
        lda #7
        sta $d027
        sta $d028
        lda #1
        sta $d01a
        lda #40
        sta $d012
        lda #$1b
        sta $d011
        lda #<irqa
        sta $fffe
        lda #>irqa
        sta $ffff
        asl $d019
        cli
        jmp *

; line 40: the dodge by polling (one $d011 write a line) down to ROW0 - 3, then the rows' IRQ
irqa:   sta sav_a
        stx sav_x
        sty sav_y
        ldx #40
@wl:    cpx $d012
        bne @wl
        lda ytab,x
        sta $d011
        inx
        cpx #ROW0 - 2
        bne @wl
        lda #ROW0 - 2
        sta $d012
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff
        asl $d019
        lda sav_a
        ldx sav_x
        ldy sav_y
        rti

irq1:   sta sav_a
        stx sav_x
        sty sav_y
        lda #$18 + ((ROW0 + 3) .mod 8)  ; safe for lines ROW0 - 2 .. ROW0 + 2 (the first row's write lands in ROW0 + 1)
        sta $d011
        lda #<irq2
        sta $fffe
        lda #>irq2
        sta $ffff
        inc $d012
        asl $d019
        tsx
        stx sav_s
        cli
        .repeat 14
        nop
        .endrep
irq2:   txs
        nop                     ; (NTSC)
        ldx #8
@w:     dex
        bne @w
        bit $00
        lda $d012
        cmp $d012
        beq @st
@st:
        .repeat HTUNE
        nop
        .endrep
        ldy #0
        ldx #0
        .include "vtest2_rows.inc"
        lda #0
        sta $d021
        ldx sav_s
        txs
        ldx $d012               ; the dodge by polling to the window's end
@wl2:   cpx $d012
        bne @wl2
        lda ytab,x
        sta $d011
        inx
        cpx #250
        bne @wl2
        lda #40
        sta $d012
        lda #<irqa
        sta $fffe
        lda #>irqa
        sta $ffff
        asl $d019
        lda sav_a
        ldx sav_x
        ldy sav_y
        rti

.segment "TABLES"
col:                            ; colour bands, 4 rows each (gen_vtest2.py)
        .include "vtest2_col.inc"
ytab:
        .repeat 256, I
        .byte $18 + (((I .mod 4) + 2) .mod 8)
        .endrep
