; =============================================================================
;  PART 1 -- the intro film for the C64 (PAL): ghost-byte swatches, plain raster code
;  python3 part1_gen.py
;  cl65 -g -t none -C part1.cfg -Ln part1.lbl -o part1.prg part1.s
;  python3 sim_part1.py           (checks it on a simulated 6502)
; =============================================================================
;
;  The screen is ON, in the idle state: no badlines (DEN is held low across line $30, then
;  raised), so the 320 x 200 window shows the colour $d021 where the idle byte at $3fff has
;  0 bits and black where it has 1 bits.  Every line writes both: the idle byte (the ghost
;  byte of the line's swatch) and $d021 (its colour), by swatch, line parity and frame parity:
;  one row of code (63 cycles) per line, in two copies of the 200 rows, one for each frame
;  parity, so the flicker pairs (phase swapped line to line) cost nothing.
;
;      ldx LINEBUF+n  /  lda ght_fp_rp,x / sta $3fff  /  lda colt_fp_rp,x / sta $d021
;
;  Each frame, in the blank: `update` clears the 200-byte buffer of swatch indices and
;  copies each bar's indices into it, far to near (index 0 = black = not drawn), from the
;  scene stream part1_gen.py precalculated.  Then the stable double IRQ and the 200 rows.
;
;  Untested on hardware or VICE: the exact cycle the writes land on (HTUNE) and the DEN trick
;  are only reasoned, not seen.
; =============================================================================

        .setcpu "6502"
        .include "part1.inc"

ROWS      = 200
FIRST_LINE = 51
IRQ0LINE  = 46                  ; DEN low across line $30 (48)
IRQLINE   = FIRST_LINE - 2      ; the stable double IRQ
.ifndef HTUNE
HTUNE     = 0
.endif
.ifndef WAITX
WAITX     = 6                   ; tuned in VICE: the rows start the same cycle on every line
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
LINEBUF    = $0400                ; the screen is never shown

; =============================================================================
.segment "ZEROPAGE"
rp:      .res 2
bank:    .res 1                 ; cartridge: the ROML bank the scene stream is in
cur:     .res 2
lastp:   .res 2
lastn:   .res 1
nbars:   .res 1
ri:      .res 1
cnt:     .res 1
fcl:     .res 1
fch:     .res 1
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
        lda #<scene
        sta rp
        lda #>scene
        sta rp+1
.ifdef CART
        lda #SCENE_BANK
        sta bank
.endif
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
@idle:  jmp @idle

nmi:    rti

dly:    .repeat 14
        nop
        .endrep
        rts

; -----------------------------------------------------------------------------
;  update: the next frame's buffer of swatch indices, and which row set shows it
; -----------------------------------------------------------------------------
.proc update
.ifdef CART
        lda #$37                ; BASIC/KERNAL/ROML visible while we read the scene (interrupts are off here)
        sta $01
        lda bank
        sta $de00
.endif
        lda #0
        .repeat ::ROWS, N
        sta LINEBUF + N         ; clear: 4 cycles a line
        .endrep
        ldy #0
        lda (rp),y
        cmp #$fe
        bne @nj
.ifdef CART
        inc bank                ; the stream goes on at the start of the next ROML bank
        lda bank
        sta $de00
        lda #<scene
        sta rp
        lda #>scene
        sta rp+1
.else
        lda #<scene1            ; the stream jumps over the I/O hole at $d000
        sta rp
        lda #>scene1
        sta rp+1
.endif
        lda (rp),y
@nj:    cmp #$ff
        bne @new
        lda lastp               ; same list as the last frame
        sta cur
        lda lastp+1
        sta cur+1
        lda lastn
        sta nbars
        inc rp
        bne @go
        inc rp+1
        jmp @go
@new:   sta nbars
        sta lastn
        sec                     ; cur = rp + 1
        lda rp
        adc #0
        sta cur
        sta lastp
        lda rp+1
        adc #0
        sta cur+1
        sta lastp+1
        lda nbars               ; rp += 1 + 4 n
        asl
        asl
        sec
        adc rp
        sta rp
        bcc @go
        inc rp+1
@go:    ldy #0
@bar:   lda nbars
        beq @done
        lda (cur),y             ; source address, first line, rows - 1
        sta @ld + 1
        iny
        lda (cur),y
        sta @ld + 2
        iny
        lda (cur),y
        sta @st + 1
        iny
        lda (cur),y
        iny
        sty ri
        tay
@ld:    lda $ffff,y             ; the profile's swatch index
@st:    sta LINEBUF,y           ; into the line buffer
        dey
        bpl @ld
        ldy ri
        dec nbars
        jmp @bar
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
        lda #0                  ; the film loops
        sta fcl
        sta fch
        lda #<scene
        sta rp
        lda #>scene
        sta rp+1
.ifdef CART
        lda #SCENE_BANK
        sta bank
.endif
@ret:
.ifdef CART
        lda #$35                ; RAM + I/O again for the rows and the IRQ vectors
        sta $01
.endif
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
        lda ght + 32 * (FP * 2 + (N .mod 2)), x
        sta IDLE
        lda colt + 32 * (FP * 2 + (N .mod 2)), x
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
prof:   .incbin "part1_prof.bin"

.ifdef CART
scene = $8000                   ; the scene stream is in ROML banks SCENE_BANK.. (mk_cart.py)
.else
.segment "SCENE"
scene:  .incbin "part1_rec0.bin"

.segment "SCENE1"
scene1: .incbin "part1_rec1.bin"
.endif
