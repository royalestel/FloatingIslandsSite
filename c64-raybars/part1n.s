; =============================================================================
;  PART 1 -- NTSC 60 Hz version (part1n_gen.py): every frame from the stream of CHANGED rows
;  (runs copied into the persistent LINEBUF; no clear, no procedural part).  Derived from the PAL part1p.s.
;  -- the intro film for the C64: ghost-byte swatches, plain raster code
;  python3 part1p_gen.py
;  ca65/ld65 via cl65 -g -t none -C part1p.cfg -Ln part1p.lbl -o part1p.prg part1p.s
; =============================================================================
;
;  The screen is ON, in the idle state: no badlines (DEN is held low across line $30, then raised), so the
;  320 x 200 window shows the colour $d021 where the idle byte at $3fff has 0 bits and black where it has 1
;  bits.  Every line writes both (the swatch's ghost byte and colour, by swatch, line parity and frame
;  parity): one row of code (63 cycles) per line, in two copies of the 200 rows, one per frame parity.
;
;      ldx LINEBUF+n  /  lda ght_fp_rp,x / sta $3fff  /  lda colt_fp_rp,x / sta $d021
;
;  The tables hold two blocks of 32 swatches for each (frame parity, line parity); the second block has the line
;  parities swapped.  A bar whose first line is odd writes its swatch indices +32, so a swatch's look follows
;  the row's parity INSIDE its bar: a bar has two looks (frame parity), however it moves.
;
;  Each frame, in the blank, `update` clears the 200-byte buffer and draws the bars far to near (index 0 =
;  black = not drawn):  frames 0 .. T_STACK-1 PROCEDURALLY (sine / smoothstep / reciprocal tables and 8-bit
;  arithmetic: part1_proc.py is the exact model), later frames from the precalculated stream.
; =============================================================================

        .setcpu "6502"
        .include "part1n.inc"

ROWS      = 200
FIRST_LINE = 51
IRQ0LINE  = 46                  ; DEN low across line $30 (48)
IRQLINE   = FIRST_LINE - 2      ; the stable double IRQ
.ifndef HTUNE
HTUNE     = 1
.endif
.ifndef WAITX
WAITX     = 5                   ; tuned in VICE: the rows start the same cycle on every line
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
.ifndef BASE
BASE = 1
.endif
STREAM_BANK0 = BASE + IMGBANKS
LINEBUF    = $0400              ; the screen is never shown; 64 bytes of padding either side


; =============================================================================
.segment "ZEROPAGE"
rp:      .res 2
cur:     .res 2
lastp:   .res 2
lastn:   .res 1
nbars:   .res 1
bank:    .res 1
ri:      .res 1
cnt:     .res 1
fcl:     .res 1
fch:     .res 1
save_a:  .res 1
save_x:  .res 1
save_y:  .res 1
; --- procedural beginning
pa:      .res 2                 ; phase accumulator (16 bits), the phase is its high byte
sv:      .res 1                 ; s: the slide becomes the circle (0..255)
zbl:     .res 1                 ; the circle's centre distance (1/64 m)
zbh:     .res 1
dl:      .res 1
dh:      .res 1
la:      .res 2                 ; lerp operands / result, 16 bits signed
lb:      .res 2
lw:      .res 1
mda:     .res 1                 ; 8 x 8 multiply
mrr:     .res 1
sg:      .res 1
kk:      .res 1
pk:      .res 1
zl:      .res 1
zh:      .res 1
yl:      .res 1
yh:      .res 1
l1:      .res 1
l2:      .res 1
t1:      .res 1
t2:      .res 1
t3:      .res 1
ol:      .res 1
oh:      .res 1
bt:      .res 3                 ; the three bars: thickness, first line (16 bits), draw key (16 bits)
byl:     .res 3
byh:     .res 3
bkl:     .res 3
bkh:     .res 3
ordr:    .res 3
dst:     .res 2
di:      .res 1

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
        lda #$2f                ; processor port: bits 0-2 outputs
        sta $00
        lda #$35                ; RAM + I/O
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
        ldx #$7d
@zp:    sta $02,x
        dex
        bpl @zp
        jsr restart
        lda #0                  ; the line buffer persists from frame to frame (delta stream): start black
        ldx #0
@clr:   sta LINEBUF,x
        inx
        cpx #200
        bne @clr
        lda #$c8                ; 40 columns (the VIC resets to 38)
        sta $d016
        lda #$0b                ; DEN low (the irq0/irq1 pair raises it every frame)
        sta VIC_CTRL1
        lda #IRQ0LINE
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQEN
        sta VIC_IRQ
        jsr update              ; frame 0
        cli
@idle:  .repeat 100
        nop                     ; 2-cycle ops: the stable raster sees only a 1-cycle jitter
        .endrep
        jmp @idle

nmi:    rti

; the film starts (again): frame 0, phase, stream
restart:
        lda #0
        sta fcl
        sta fch
        lda #<$8000
        sta rp
        lda #>$8000
        sta rp+1
        lda #STREAM_BANK0
        sta bank
        rts

dly:    .repeat 15                ; NTSC: 65-cycle rows
        nop
        .endrep
        rts

; -----------------------------------------------------------------------------
;  update: the next frame's buffer of swatch indices, and which row set shows it
; -----------------------------------------------------------------------------
.proc update
        lda #$37                ; the stream is in ROM (cartridge banks at $8000-$BFFF) while we read it
        sta $01
        lda bank
        sta $de00
        ldy #0
        lda (rp),y
        cmp #$fe                ; the record is in the next bank
        bne @rec
        inc bank
        lda bank
        sta $de00
        lda #<$8000
        sta rp
        lda #>$8000
        sta rp+1
        lda (rp),y
@rec:   sta nbars
        inc rp
        bne @go
        inc rp+1
@go:    lda nbars
        beq @done
@run:   ldy #0
        lda (rp),y              ; source address (in RAM), first line, rows - 1
        sta @ld + 1
        iny
        lda (rp),y
        sta @ld + 2
        iny
        lda (rp),y
        sta @st + 1
        iny
        lda (rp),y
        tay
@ld:    lda $ffff,y             ; the bar array's swatch index (+ 32 for an odd first line), or zeros
@st:    sta LINEBUF,y
        dey
        bpl @ld
        clc
        lda rp
        adc #4
        sta rp
        bcc @n
        inc rp+1
@n:     dec nbars
        bne @run
@done:  lda fcl                 ; the row set for this frame: parity of the frame number
        and #1
        beq @even
        lda #<rows1
        sta entry + 1
        lda #>rows1
        sta entry + 2
        jmp @adv
@even:  lda #<rows0
        sta entry + 1
        lda #>rows0
        sta entry + 2
@adv:   inc fcl
        bne @c
        inc fch
@c:     lda fcl
        cmp #<T_END
        bne @ret
        lda fch
        cmp #>T_END
        bne @ret
        jmp $0200               ; the chain: the next part is loaded
@ret:   lda #$35
        sta $01
        rts
.endproc

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
        bit $00
        lda VIC_RASTER
        cmp VIC_RASTER
        beq @stable
@stable:
        .repeat HTUNE
        nop
        .endrep
entry:  jmp rows0               ; patched by update: rows0 / rows1 (3 cycles, before row 0)

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
;  The 200 rows, twice (one set for each frame parity), 63 cycles each:
;  ldx 4, lda abs,x 4, sta 4, lda abs,x 4, sta 4, bit zp 3, jsr dly 6 + 28 + 6
; =============================================================================
.macro ROWSET FP, LAB
LAB:
        .repeat ROWS, N
        ldx LINEBUF + N
        lda ght + 64 * (FP * 2 + (N .mod 2)), x
        sta IDLE
        lda colt + 64 * (FP * 2 + (N .mod 2)), x
        sta VIC_BG
        bit $ea
        jsr dly
        .endrep
        jmp blockend
.endmacro


.segment "ROWS0"
        ROWSET 0, rows0

.segment "ROWS1"
        ROWSET 1, rows1

; =============================================================================
.segment "TABLES"
colt:   COLT
ght:    GHT

.segment "PROF"
prof:   .incbin "part1n_prof0.bin"

.segment "PROF2"
prof2:  .incbin "part1n_prof1.bin"


