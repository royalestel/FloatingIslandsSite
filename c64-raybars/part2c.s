; =============================================================================
;  PART 2's earthquake for the C64 (PAL), 6 raster-split columns (32 | 64 x 4 | 32 pixels)
;  SPLITS=6 python3 part2c_gen.py && cl65 -g -t none -C part2c.cfg -Ln part2c.lbl -o part2c.prg part2c.s part2c_tab.s
; =============================================================================
;
;  The screen is ON, idle (no badlines: DEN low across line $30), so the window shows $d021 where the idle byte
;  ($3fff) has 0 bits.  The 200 lines are ONE loop, 63 cycles a line, X = the line:
;
;      lda G,x / sta $3fff            the idle byte (ghost pattern)
;      lda P0,x / sta $d021           column 0 (before the window)
;      lda P1,x / sta $d021  ...      columns 1-5, one write every 8 cycles (64 pixels)
;      inx / cpx #200 / bne
;
;  Every column is a byte pattern of a page (the still floor's colour bytes, line n at offset C0 + n), and a
;  column shifted by d lines is the same pattern read at  pattern + C0 - d + x : the shake is 7 patched operand
;  bytes a frame, from a table of precomputed shifts (part2.shake_offsets).  While every column has the same shift
;  the patterns with ghost swatches and the idle-byte pattern are used; while the columns differ, the patterns
;  with flat swatches and a zero idle byte (the video's rule: ghost swatches only where all columns agree).
;  Patterns are page-aligned and read from offsets 0..255 only: no page crossings, every line 63 cycles.
; =============================================================================

        .setcpu "6502"
        .include "part2c.inc"

FIRST_LINE = 51
IRQ0LINE  = 46
IRQLINE   = FIRST_LINE - 2
.ifndef PRE
PRE       = 0
.endif
.ifndef HTUNE
HTUNE     = 0                   ; tuned in VICE (6567R8): column 1 starts at x = 33
.endif
.ifndef WAITX
WAITX     = 8                   ; the stable raster's compare falls on the line change (measured in VICE, 6567R8)
.endif
.ifndef NOHBIT
HBIT      = 1                   ; NTSC: one odd cycle (bit $ea) shifts column 1 to x = 33
.endif

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

        .import pat_g0, pat_g1, pat_f0, pat_f1, pat_h0, pat_h1, pat_z0, offs

.segment "ZEROPAGE"
fcl:     .res 1
sub:     .res 1
fch:     .res 1
op:      .res 2                 ; the frame's record in offs
t1:      .res 2
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
        sta sub                 ; (the first update below is frame 0; the next blank is skipped)
        jsr restart
        lda #$c8
        sta $d016
        lda #$0b
        sta VIC_CTRL1
        lda #IRQ0LINE
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQEN
        sta VIC_IRQ
        jsr update
        cli
@idle:  jmp @idle

nmi:    rti

restart:
.ifdef START                    ; test builds: begin at frame START
        lda #<START
        sta fcl
        lda #>START
        sta fch
        lda #<(offs + 7 * START)
        sta op
        lda #>(offs + 7 * START)
        sta op+1
.else
        lda #0
        sta fcl
        sta fch
        lda #<offs
        sta op
        lda #>offs
        sta op+1
.endif
        rts

; -----------------------------------------------------------------------------
;  update: patch the loop's 7 operands for the next frame
; -----------------------------------------------------------------------------
.proc update
        lda fcl                 ; the frame parity picks the patterns' page
        and #1
        tax
        ldy #6
        lda (op),y              ; mode: 1 = every column the same shift
        beq @flat
        lda pghi,x              ; ghost swatches + the idle byte pattern
        sta rP0 + 2
        sta rP1 + 2
        sta rP2 + 2
        sta rP3 + 2
        sta rP4 + 2
        sta rP5 + 2
        lda phhi,x
        sta rG + 2
        sta t1 + 1
        ldy #0
        lda (op),y              ; the idle byte pattern shifts with the columns
        sta t1
        clc
        adc #1
        sta rG + 1
        ldy #0
        lda (t1),y              ; line 0's idle byte, now (nothing writes $3fff before the first line)
        sta IDLE
        jmp @lo
@flat:  lda pfhi,x
        sta rP0 + 2
        sta rP1 + 2
        sta rP2 + 2
        sta rP3 + 2
        sta rP4 + 2
        sta rP5 + 2
        lda #>pat_z0
        sta rG + 2
        lda #C0
        sta rG + 1
        lda #0
        sta IDLE
@lo:    ldy #0
        lda (op),y
        sta rP0 + 1
        iny
        lda (op),y
        sta rP1 + 1
        iny
        lda (op),y
        sta rP2 + 1
        iny
        lda (op),y
        sta rP3 + 1
        iny
        lda (op),y
        sta rP4 + 1
        iny
        lda (op),y
        sta rP5 + 1
.ifdef FREEZE
        lda fcl                 ; test builds: stay on frame FREEZE
        cmp #<FREEZE
        bne @go
        lda fch
        cmp #>FREEZE
        bne @go
        rts
@go:
.endif
        clc                     ; next record
        lda op
        adc #7
        sta op
        bcc @n
        inc op+1
@n:     inc fcl
        bne @c
        inc fch
@c:     lda fcl
        cmp #<NF
        bne @r
        lda fch
        cmp #>NF
        bne @r
        jmp $0200               ; the chain: the next part is loaded
@r:     rts
.endproc

blank:  lda sub                 ; NTSC: every film frame is shown for 2 frames: update every second blank
        eor #1
        sta sub
        bne @skip
        jmp update
@skip:  rts

pghi:   .byte >pat_g0, >pat_g1
pfhi:   .byte >pat_f0, >pat_f1
phhi:   .byte >pat_h0, >pat_h1

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
        .repeat PRE
        nop
        .endrep
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
rows:   ldx #0                  ; (the first line's idle byte is written by update)
rloop:
rP0:    lda pat_g0 + C0,x
        sta VIC_BG
rP1:    lda pat_g0 + C0,x
        sta VIC_BG
rP2:    lda pat_g0 + C0,x
        sta VIC_BG
rP3:    lda pat_g0 + C0,x
        sta VIC_BG
rP4:    lda pat_g0 + C0,x
        sta VIC_BG
rP5:    lda pat_g0 + C0,x
        sta VIC_BG
rG:     lda pat_z0 + C0 + 1,x   ; the NEXT line's idle byte, written in the right border
        sta IDLE
        nop                     ; NTSC: 65 cycles a line
        inx
        cpx #200
        bne rloop
        jmp blockend

blockend:
        lda #<irq0
        sta $fffe
        lda #>irq0
        sta $ffff
        lda #IRQ0LINE
        sta VIC_RASTER
        asl VIC_IRQ
        jsr blank
        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
;  The 200 lines: one loop of 63 cycles (7 x (lda abs,x 4 + sta 4) + inx 2 + cpx 2 + bne 3)
; =============================================================================
