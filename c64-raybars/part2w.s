; =============================================================================
;  PART 3's waves for the C64 (PAL), 6 raster-split columns, as CHANGE STREAMS (cartridge)
;  SPLITS=6 python3 part2w_gen.py  (needs /tmp/part3_frames.pkl from the frame dump)
;  python3 mk_cart_p.py part2w part2w.crt  (banks: boot, program image, then the stream)
; =============================================================================
;
;  The raster loop is part2c's: 200 lines, 63 cycles each, X = the line, 6 column writes of `lda page,x / sta $d021`
;  8 cycles apart and the next line's idle byte; the 7 pages of the frame's parity (S0 even frames, S1 odd frames).
;  Frame t shows S[t & 1], which holds frame t-2: `update` (in the blank) applies the runs of changed bytes from the
;  stream in ROML banks -- records [n][n x ([page][line][len] bytes)], 120 bytes at most -- and patches the 7 page
;  operands for the next frame's parity.  A record holds runs for BOTH sets (the set of the frame after next may be
;  changed in two blanks): the generator splits the peak frames.
; =============================================================================

        .setcpu "6502"
        .include "part2w.inc"

LINE0     = 0                   ; (a later start would not help: DEN must be high before line 51, so the stable IRQ stays at line 49)
LINE1     = 184
FIRST_LINE = 51 + LINE0
IRQ0LINE  = 46
IRQLINE   = FIRST_LINE - 2
.ifndef HTUNE
HTUNE     = 0
.endif
.ifndef WAITX
WAITX     = 8
.endif
ODD       = 1
STREAM_BANK0 = 1 + IMGBANKS      ; the stream's first ROML bank (cartboot: bank 0 = boot, banks 1.. = the program image)

VIC_CTRL1  = $d011
VIC_RASTER = $d012
VIC_SPREN  = $d015
VIC_IRQ    = $d019
VIC_IRQEN  = $d01a
VIC_BORDER = $d020
VIC_BG     = $d021
CIA1_ICR   = $dc0d
CIA2_ICR   = $dd0d
IDLE       = $3fff

        .import pages

.segment "ZEROPAGE"
fcl:     .res 1
fch:     .res 1
sp:      .res 2                 ; the stream pointer (in the ROML window)
bank:    .res 1
nruns:   .res 1
cnt:     .res 1
save_a:  .res 1
save_x:  .res 1
save_y:  .res 1

.segment "LOADADDR"
        .word $0801

.segment "EXEHDR"
        .word @next, 10
        .byte $9e, "2061", 0
@next:  .word 0

.segment "CODE"
start:  sei
        lda #$7f
        sta CIA1_ICR
        sta CIA2_ICR
        lda CIA1_ICR
        lda CIA2_ICR
        lda #$2f
        sta $00
        lda #$35
        sta $01
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #<irq0
        sta $fffe
        lda #>irq0
        sta $ffff
        lda #0
        sta VIC_BORDER
        sta VIC_BG
        sta VIC_SPREN
        sta IDLE
        lda #0                  ; the pages hold frames N-2 and N-1; record j is the blank before frame j
        sta fcl
        sta fch
        lda #<$8000
        sta sp
        lda #>$8000
        sta sp+1
        lda #STREAM_BANK0
        sta bank
        lda #$c8
        sta $d016
        lda #$0b
        sta VIC_CTRL1
        lda #IRQ0LINE
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQEN
        sta VIC_IRQ
        jsr update              ; frame 0
        cli
@idle:  jmp @idle

nmi:    rti

; -----------------------------------------------------------------------------
;  update: apply this blank's record, then patch the loop for the next frame's parity
; -----------------------------------------------------------------------------
.proc update
        lda #$37                ; ROML visible while we read the stream (interrupts are off here)
        sta $01
        lda bank
        sta $de00
        ldy #0
        lda (sp),y
        cmp #$ff                ; the record is in the next bank
        bne @rec
        inc bank
        lda bank
        sta $de00
        lda #<$8000
        sta sp
        lda #>$8000
        sta sp+1
        lda (sp),y
@rec:   sta nruns
        inc sp
        bne @r0
        inc sp+1
@r0:    lda nruns
        beq @done
@run:   ldy #0
        lda (sp),y              ; page id
        tax
        iny
        lda (sp),y              ; first line
        sta @st + 1
        lda pghi,x
        sta @st + 2
        iny
        lda (sp),y              ; length
        sta cnt
        clc                     ; the bytes follow the 3 header bytes
        lda sp
        adc #3
        sta @ld + 1
        lda sp+1
        adc #0
        sta @ld + 2
        ldy cnt
        dey
@ld:    lda $ffff,y
@st:    sta $ffff,y
        dey
        bpl @ld
        clc                     ; sp += 3 + length
        lda sp
        adc cnt
        sta sp
        bcc @a1
        inc sp+1
@a1:    clc
        lda sp
        adc #3
        sta sp
        bcc @a2
        inc sp+1
@a2:    dec nruns
        bne @run
@done:
@nw:    lda fcl                 ; the next frame's parity: patch the loop's 7 page operands
        and #1
        beq @even
        lda #>pages + 7
        bne @pg
@even:  lda #>pages
@pg:    sta rP0 + 2
        clc
        adc #1
        sta rP1 + 2
        adc #1
        sta rP2 + 2
        adc #1
        sta rP3 + 2
        adc #1
        sta rP4 + 2
        adc #1
        sta rP5 + 2
        adc #1
        sta rG + 2
        sta @i0 + 2
@i0:    lda pages + LINE0       ; (the first line's idle byte; the loop writes the NEXT line's after each line)
        sta IDLE
        inc fcl
        bne @c
        inc fch
@c:     lda fcl
        cmp #<NF
        bne @r
        lda fch
        cmp #>NF
        bne @r
        lda #0                  ; the film loops: the stream starts again
        sta fcl
        sta fch
        lda #<$8000
        sta sp
        lda #>$8000
        sta sp+1
        lda #STREAM_BANK0
        sta bank
@r:     lda #$35                ; RAM + I/O again for the rows and the IRQ vectors
        sta $01
        rts
.endproc

pghi:   .repeat 14, I
        .byte >pages + I
        .endrep

; -----------------------------------------------------------------------------
;  irq0 (line 46): DEN low, so line $30 makes no badlines.  irq1 (line 49): DEN high again
;  and the stable double IRQ; irq2 (line 50) falls into the 200 rows.
; -----------------------------------------------------------------------------
irq0:   sta save_a
        lda #$0b
        sta VIC_CTRL1
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff
        lda #IRQLINE
        sta VIC_RASTER
        asl VIC_IRQ
        lda save_a
        rti

irq1:   sta save_a
        stx save_x
        sty save_y
        lda #$1b                ; DEN high: the window opens at line 51
        sta VIC_CTRL1
        lda #<irq2
        sta $fffe
        lda #>irq2
        sta $ffff
        inc VIC_RASTER
        asl VIC_IRQ
        tsx
        cli
        .repeat 12
        nop
        .endrep

irq2:   txs
        ldx #WAITX
@w:     dex
        bne @w
        .ifdef ODD
        bit $00
        .else
        nop
        .endif
        lda VIC_RASTER
        cmp VIC_RASTER
        beq @stable
@stable:
        .repeat HTUNE
        nop
        .endrep
.ifdef HBIT
        bit $ea                 ; one odd cycle (3)
.endif
entry:                          ; the loop follows at once (no jmp)
rows:   ldx #LINE0              ; (the first line's idle byte is written by update)
rloop:
rP0:    lda pages,x
        sta VIC_BG
rP1:    lda pages,x
        sta VIC_BG
rP2:    lda pages,x
        sta VIC_BG
rP3:    lda pages,x
        sta VIC_BG
rP4:    lda pages,x
        sta VIC_BG
rP5:    lda pages,x
        sta VIC_BG
rG:     lda pages + 1,x   ; the NEXT line's idle byte, written in the right border
        sta IDLE
        inx
        cpx #LINE1 + 1
        bne rloop
        lda #0                  ; black below the floor
        sta VIC_BG
        sta IDLE
        jmp blockend

blockend:
        lda #<irq0
        sta $fffe
        lda #>irq0
        sta $ffff
        lda #IRQ0LINE
        sta VIC_RASTER
        asl VIC_IRQ
        jsr update
        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
;  The 200 lines: one loop of 63 cycles (7 x (lda abs,x 4 + sta 4) + inx 2 + cpx 2 + bne 3)
; =============================================================================
