; =============================================================================
;  ANIMSPLIT -- STAGE 2: the floor's strings tilt in a wave, with raster splits
;  python3 anim_gen.py && python3 wave_gen.py
;  cl65 -g -t none -C anim2.cfg -Ln animsplit.lbl -o animsplit.prg animsplit.s
;  python3 sim_animsplit.py
; =============================================================================
;
;  The same blanked screen and $d020 bars as anim0, but a line can now carry
;  6 colours (64 pixels each: 6 x 8 cycles = 384 pixels).  Two kinds of row,
;  each exactly 63 cycles and each ending in a JMP to the next row:
;    plain  P_s[n]  lda STILL_s+n / sta $d020 / jsr dly / jmp        (12 bytes)
;    split  X[n]    6 x (lda SEGBUF_k+32+n / sta $d020) / 6 nops / jmp (45 bytes)
;  The still floor (STILL_0/1: the 23 strings at rest, one set of colours per
;  frame parity) is shown by plain rows P_0 / P_1 (their own code, so no copy);
;  only the BAND of lines that the moving strings touch uses split rows.  The
;  band is entered and left by patching two JMP operands (and the entry
;  jump): one frame's update undoes the last patches and makes the new ones.
;
;  UPDATE for a frame with a band: the 6 segment buffers' band lines are
;  cleared and every string overlapping the band is blitted into each of
;  them, far to near, shifted by its own shift table (segment k, frame u of
;  its tilt) -- the staircase.  The parity of the line a string lands on
;  picks the colour set (the flicker pair's phase), as in anim0.
;
;  TIMING: see sim_animsplit.py.  The rows are cycle-exact; the update is
;  NOT yet fast enough for the frames with a wide band (it measures what
;  there is).
; =============================================================================

        .setcpu "6502"
        .include "wave.inc"

ROWS      = 200
PROW      = 12                  ; plain row: lda abs, sta abs, jsr, jmp
XROW      = 45                  ; split row: 6 x 6 + 6 nops + jmp
FIRST_LINE = 51
IRQLINE   = FIRST_LINE - 2
HTUNE     = 0

VIC_CTRL1  = $d011
VIC_RASTER = $d012
VIC_SPREN  = $d015
VIC_IRQ    = $d019
VIC_IRQEN  = $d01a
VIC_BORDER = $d020
VIC_BG     = $d021
CIA1_ICR   = $dc0d
CIA2_ICR   = $dd0d

B0 = $0200                      ; segment buffers, 256 bytes each: line n at +PAD+n
B1 = $0300
B2 = $0400
B3 = $0500
B4 = $0600
B5 = $0700

; =============================================================================
.segment "ZEROPAGE"
tw:      .res 1                 ; wave frame
fpar:    .res 1                 ; frame parity of the frame being built
wrp:     .res 2                 ; its band record
bt:      .res 1                 ; band: first line, last line, strings
bb:      .res 1
slo:     .res 1
shi:     .res 1
obt:     .res 1                 ; the patches made for the frame on screen
obb:     .res 1
ofp:     .res 1
oband:   .res 1
si:      .res 1
u:       .res 1
ik6:     .res 1
moving:  .res 1
sh:      .res 1
fam2:    .res 1
ptr:     .res 2
save_a:  .res 1
save_x:  .res 1
save_y:  .res 1

; =============================================================================
.segment "LOADADDR"
        .word $0801

.segment "EXEHDR"
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
        lda #$35
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
        lda #<wrec
        sta wrp
        lda #>wrec
        sta wrp+1
        lda #$0b
        sta VIC_CTRL1
        lda #IRQLINE
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQEN
        sta VIC_IRQ
        jsr update
        cli
@idle:  jmp @idle

nmi:    rti

dly:    .repeat 20              ; 20 nops + rts: with jsr 52 cycles
        nop
        .endrepeat
        rts

; one string into segment buffer K (macro: unrolled per segment)
.macro SEG K
        .local noshift, haves, ld, st
        lda moving
        beq noshift
        lda ik6
        clc
        adc #K
        tax
        lda opt_lo,x
        sta ptr
        lda opt_hi,x
        sta ptr+1
        ldy u
        lda (ptr),y             ; the shift (<= 0)
        jmp haves
noshift:
        lda #0
haves:  sta sh
        ldx si
        clc
        adc sy0,x               ; first line of the string in the buffer
        sta st + 1
        lda sh                  ; colour set: frame parity, parity of the line it lands on
        and #1
        eor syp,x
        ora fam2
        tay
        lda f32,y
        ora si
        tax
        lda splo,x
        sta ld + 1
        lda sphi,x
        sta ld + 2
        ldx si
        ldy sn,x
ld:     lda $ffff,y
st:     sta .ident(.sprintf("B%d", K)),y
        dey
        bpl ld
.endmacro

; patch the operand of a row's jmp: PATCH jlo, jhi, row (X), tlo, thi, trow (Y)
.macro PATCH jlo, jhi, tlo, thi
        lda jlo,x
        sta ptr
        lda jhi,x
        sta ptr+1
        ldx #0                  ; (callers put the target row in Y)
        lda tlo,y
        sta (ptr,x)
        inc ptr
        bne :+
        inc ptr+1
:       lda thi,y
        sta (ptr,x)
.endmacro

; -----------------------------------------------------------------------------
;  update: build the next frame (tw, fpar) and its jump patches
; -----------------------------------------------------------------------------
.proc update
        ; ---- undo the last frame's patches ----------------------------------
        lda oband
        beq L_undone
        lda ofp                 ; P_s[obt-1].jmp -> P_s[obt] (its default)
        bne L_u1
        lda obt
        beq L_ux
        ldx obt
        dex
        ldy obt
        PATCH pj0lo, pj0hi, p0lo, p0hi
        jmp L_ux
L_u1:    lda obt
        beq L_ux
        ldx obt
        dex
        ldy obt
        PATCH pj1lo, pj1hi, p1lo, p1hi
L_ux:    ldx obb                 ; X[obb].jmp -> X[obb+1]
        ldy obb
        iny
        PATCH xjlo, xjhi, xlo, xhi
L_undone:
        ; ---- this frame's band ----------------------------------------------
        ldy #0
        lda (wrp),y
        sta bt
        iny
        lda (wrp),y
        sta bb
        iny
        lda (wrp),y
        sta slo
        iny
        lda (wrp),y
        sta shi
        lda bt
        cmp #255
        bne L_band
        lda #0                  ; no band: plain floor
        sta oband
        ldy #0
        ldx fpar
        bne L_e1
        lda p0lo
        sta entry+1
        lda p0hi
        sta entry+2
        jmp L_adv
L_e1:    lda p1lo
        sta entry+1
        lda p1hi
        sta entry+2
        jmp L_adv

        ; ---- clear the band lines of the 6 buffers ---------------------------
L_band:  lda fpar
        asl
        sta fam2
        lda bt
        clc
        adc #PAD
        tax                     ; X = bt + PAD
        lda bb
        clc
        adc #PAD+1
        sta ptr                 ; end index
        lda #0
L_clr:   sta B0,x
        sta B1,x
        sta B2,x
        sta B3,x
        sta B4,x
        sta B5,x
        inx
        cpx ptr
        bne L_clr
        ; ---- blit every string of the band, far to near ---------------------
        ldx shi
L_str:   stx si
        lda tw
        sec
        sbc sust,x
        sta u
        lda #0
        sta moving
        lda u
        bmi L_still              ; u < 0: not started
        beq L_still
        cmp #TILT
        bcs L_still              ; finished
        inc moving
L_still: lda si                  ; ik6 = 6 * si
        asl
        adc si
        asl
        sta ik6
        .repeat 6, K
        SEG K
        .endrep
        ldx si
        cpx slo
        beq L_blitted
        dex
        jmp L_str
L_blitted:
        ; ---- patch the jumps into and out of the band -----------------------
        lda #1
        sta oband
        lda bt
        sta obt
        lda bb
        sta obb
        lda fpar
        sta ofp
        ldx bb                  ; X[bb].jmp -> P_s[bb+1] (blockend after row 199)
        ldy bb
        iny
        lda fpar
        bne L_o1
        PATCH xjlo, xjhi, p0lo, p0hi
        jmp L_ent
L_o1:    PATCH xjlo, xjhi, p1lo, p1hi
L_ent:   lda bt                  ; into the band: entry or P_s[bt-1].jmp -> X[bt]
        bne L_inrow
        lda xlo
        sta entry+1
        lda xhi
        sta entry+2
        jmp L_adv
L_inrow: lda fpar
        bne L_i1
        lda p0lo
        sta entry+1
        lda p0hi
        sta entry+2
        ldx bt
        dex
        ldy bt
        PATCH pj0lo, pj0hi, xlo, xhi
        jmp L_adv
L_i1:    lda p1lo
        sta entry+1
        lda p1hi
        sta entry+2
        ldx bt
        dex
        ldy bt
        PATCH pj1lo, pj1hi, xlo, xhi
        ; ---- next frame ------------------------------------------------------
L_adv:   lda fpar
        eor #1
        sta fpar
        clc
        lda wrp
        adc #4
        sta wrp
        bcc :+
        inc wrp+1
:       inc tw
        lda tw
        cmp #W_LEN
        bne L_ret
        lda #0
        sta tw
        lda #<wrec
        sta wrp
        lda #>wrec
        sta wrp+1
L_ret:   rts
.endproc


; =============================================================================
;  Stable raster (double IRQ), then the 200 rows (plain and split), 63 cycles each.
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
entry:  jmp P0                  ; patched: P0, P1 or X (3 cycles, before row 0)

blockend:
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
.segment "PROWS"
P0:     .repeat ROWS, N         ; plain rows, frame parity 0
        lda still0 + N          ; 4
        sta VIC_BORDER          ; 4
        jsr dly                 ; 52
        .if N < ROWS - 1
        jmp P0 + PROW * (N + 1) ; 3 = 63
        .else
        jmp blockend
        .endif
        .endrep
P1:     .repeat ROWS, N
        lda still1 + N
        sta VIC_BORDER
        jsr dly
        .if N < ROWS - 1
        jmp P1 + PROW * (N + 1)
        .else
        jmp blockend
        .endif
        .endrep
        .assert * - P0 = 2 * ROWS * PROW, error, "plain row size"

.segment "XROWS"
xrow:  .repeat ROWS, N         ; split rows: 6 colours a line
        lda B0 + PAD + N
        sta VIC_BORDER
        lda B1 + PAD + N
        sta VIC_BORDER
        lda B2 + PAD + N
        sta VIC_BORDER
        lda B3 + PAD + N
        sta VIC_BORDER
        lda B4 + PAD + N
        sta VIC_BORDER
        lda B5 + PAD + N
        sta VIC_BORDER
        .repeat 6
        nop
        .endrep
        .if N < ROWS - 1
        jmp xrow + XROW * (N + 1)
        .else
        jmp blockend
        .endif
        .endrep
        .assert * - xrow = ROWS * XROW, error, "split row size"

; =============================================================================
.segment "TABLES"
f32:    .byte 0, 32, 64, 96
        ; row start addresses (index 200 = blockend) and the addresses of each
        ; row's jmp operand
p0lo:   .repeat ROWS + 1, N
        .if N < ROWS
        .byte <(P0 + PROW * N)
        .else
        .byte <blockend
        .endif
        .endrep
p0hi:   .repeat ROWS + 1, N
        .if N < ROWS
        .byte >(P0 + PROW * N)
        .else
        .byte >blockend
        .endif
        .endrep
p1lo:   .repeat ROWS + 1, N
        .if N < ROWS
        .byte <(P1 + PROW * N)
        .else
        .byte <blockend
        .endif
        .endrep
p1hi:   .repeat ROWS + 1, N
        .if N < ROWS
        .byte >(P1 + PROW * N)
        .else
        .byte >blockend
        .endif
        .endrep
xlo:    .repeat ROWS + 1, N
        .if N < ROWS
        .byte <(xrow + XROW * N)
        .else
        .byte <blockend
        .endif
        .endrep
xhi:    .repeat ROWS + 1, N
        .if N < ROWS
        .byte >(xrow + XROW * N)
        .else
        .byte >blockend
        .endif
        .endrep
pj0lo:  .repeat ROWS, N
        .byte <(P0 + PROW * N + 10)
        .endrep
pj0hi:  .repeat ROWS, N
        .byte >(P0 + PROW * N + 10)
        .endrep
pj1lo:  .repeat ROWS, N
        .byte <(P1 + PROW * N + 10)
        .endrep
pj1hi:  .repeat ROWS, N
        .byte >(P1 + PROW * N + 10)
        .endrep
xjlo:   .repeat ROWS, N
        .byte <(xrow + XROW * N + 43)
        .endrep
xjhi:   .repeat ROWS, N
        .byte >(xrow + XROW * N + 43)
        .endrep
        WTABLES

.segment "PROF"
prof:   .incbin "anim_prof.bin"

.segment "DATA"
still0: .incbin "wave_still.bin", 0, 200
still1: .incbin "wave_still.bin", 200, 200
woff:   .incbin "wave_off.bin"
wrec:   .incbin "wave_rec.bin"
