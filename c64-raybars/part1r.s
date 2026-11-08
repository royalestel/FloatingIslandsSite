; =============================================================================
;  PART 1 for the C64 -- NTSC (60 Hz) and PAL (50 Hz) from one source (part1r_gen.py writes part1r.inc, the routines, the data)
;
;  The screen is ON in the idle state (no badlines: DEN is held low across line $30, then raised), the 200 rows are plain raster code, 65
;  (NTSC) or 63 (PAL) cycles each, in two copies (one per frame parity: the flicker palettes).  A row writes the swatch's ghost byte to
;  $3fff and its colour to $d021; the swatch comes from a 200-byte buffer through a DIM MAP:   ldy buf+n / lda (dm),y / tax.
;
;  Each frame in the blank:  film time < 1240 (1a-1c): clear the buffer, draw the 3 bars with their UNROLLED ROUTINES (one per thickness and
;  start-line parity, lda #index / sta buf+i,x) from a 7-byte record [dim level][routine, x] x 3;  later (1d): the delta stream = runs of
;  changed rows copied from shape arrays into the persistent buffer.
; =============================================================================
        .setcpu "6502"
        .include "part1r.inc"

ROWS      = 200
FIRST_LINE = 51
IRQ0LINE  = 46
IRQLINE   = FIRST_LINE - 2
.ifdef NTSC
HTUNE     = 1
WAITX     = 5                   ; NTSC (6567R8), tuned in VICE with `bit $00`
DLYN      = 11                  ; filler nops: row = 65 cycles
DLYL      = 15
.else
HTUNE     = 0
WAITX     = 6                   ; PAL (6569), as part1p
DLYN      = 10                  ; row = 63 cycles
DLYL      = 14
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
MUSIC_INIT = $1000                ; Alpha.sid (LukHash): PSID load address $1000, init $1000, play $1003 (uses zero page $fe/$ff only)
MUSIC_PLAY = $1003

        .import rtlo, rthi, dmlo, dmhi, map0

.segment "ZEROPAGE"
rp:      .res 2                 ; the stream pointer (ROM window)
bank:    .res 1
nruns:   .res 1
fcl:     .res 1
fch:     .res 1
dm:      .res 2                 ; the dim map in use
rec:     .res 7                 ; a copy of the record (1a-1c)
save_a:  .res 1
save_x:  .res 1
save_y:  .res 1
mc:      .res 1                 ; the play-call counter (NTSC: the tune is called 5 times in 6 frames)

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
        ldx #$7d
@zp:    sta $02,x
        dex
        bpl @zp
        lda #<$8000
        sta rp
        lda #>$8000
        sta rp+1
        lda #STREAM_BANK0
        sta bank
        lda #<map0
        sta dm
        lda #>map0
        sta dm+1
        jsr clrbuf
        lda #$c8
        sta $d016
        lda #$0b
        sta VIC_CTRL1
        lda #IRQ0LINE
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQEN
        sta VIC_IRQ
        lda #0
        sta mc
        jsr MUSIC_INIT          ; tune 0
        jsr update              ; frame 0
        cli
@idle:  .repeat 100
        nop                     ; 2-cycle ops: the stable raster sees only a 1-cycle jitter
        .endrep
        jmp @idle

nmi:    rti


; -----------------------------------------------------------------------------
; the tune's play routine, once a frame (PAL) or 5 frames in 6 (NTSC: the tune was written for 50 Hz)
musicplay:
.ifdef NTSC
        inc mc
        lda mc
        cmp #6
        bne @go
        lda #0
        sta mc
        rts
@go:
.endif
        jmp MUSIC_PLAY

clrbuf: lda #0
        .repeat ROWS, N
        sta LBW + N
        .endrep
        rts

dly:    .repeat DLYN
        nop
        .endrep
        rts
dlyl:   .repeat DLYL
        nop
        .endrep
        rts

; -----------------------------------------------------------------------------
;  update (in the blank, interrupts off): the buffer and the dim map of the next frame, and the row set that shows it
; -----------------------------------------------------------------------------
.macro DRAWBAR K
        .local j, skip
        lda rec + 1 + 2 * K
        cmp #$ff
        beq skip
        tax
        lda rtlo,x
        sta j + 1
        lda rthi,x
        sta j + 2
        ldx rec + 2 + 2 * K
j:      jsr $ffff
skip:
.endmacro

.proc update
        lda #$37                ; ROM window visible: the stream
        sta $01
        lda bank
        sta $de00
        ldy #0
        lda (rp),y
        cmp #$fe                ; the record is in the next bank
        bne u_rec
        inc bank
        lda bank
        sta $de00
        lda #<$8000
        sta rp
        lda #>$8000
        sta rp+1
        lda (rp),y
u_rec:   lda fch                 ; section 1 (1a-1c) while the frame number < NR
        cmp #>NR
        bcc u_sec1
        bne u_sec2
        lda fcl
        cmp #<NR
        bcs u_sec2
u_sec1:  ldy #6                  ; copy the 7-byte record, then RAM everywhere (the routines live under the ROM window)
u_cp:    lda (rp),y
        sta rec,y
        dey
        bpl u_cp
        lda #$35
        sta $01
        clc
        lda rp
        adc #7
        sta rp
        bcc u_n1
        inc rp+1
u_n1:    ldy rec                 ; the dim map
        lda dmlo,y
        sta dm
        lda dmhi,y
        sta dm+1
        jsr clrbuf
        DRAWBAR 0
        DRAWBAR 1
        DRAWBAR 2
        jmp u_adv
u_sec2:  lda #<map0              ; identity map
        sta dm
        lda #>map0
        sta dm+1
        ldy #0
        lda (rp),y
        sta nruns
        inc rp
        bne u_g
        inc rp+1
u_g:     lda nruns
        beq u_d2
u_run:   ldy #0
        lda (rp),y              ; source address, first line, rows - 1
        sta u_ld + 1
        iny
        lda (rp),y
        sta u_ld + 2
        iny
        lda (rp),y
        sta u_st + 1
        iny
        lda (rp),y
        tay
u_ld:    lda $ffff,y
u_st:    sta LBW,y
        dey
        bpl u_ld
        clc
        lda rp
        adc #4
        sta rp
        bcc u_n2
        inc rp+1
u_n2:    dec nruns
        bne u_run
u_d2:    lda #$35
        sta $01
u_adv:   lda fcl                 ; the row set: parity of the frame number
        and #1
        beq u_even
        lda #<rows1
        sta entry + 1
        lda #>rows1
        sta entry + 2
        jmp u_inc
u_even:  lda #<rows0
        sta entry + 1
        lda #>rows0
        sta entry + 2
u_inc:   inc fcl
        bne u_c
        inc fch
u_c:     lda fcl
        cmp #<NF
        bne u_ret
        lda fch
        cmp #>NF
        bne u_ret
        lda #0                  ; silence the SID: the next part overwrites the tune
        sta $d404
        sta $d40b
        sta $d412
        sta $d418
        jmp $0200               ; the chain: the next part is loaded
u_ret:   rts
.endproc

; -----------------------------------------------------------------------------
;  irq0 (line 46): DEN low.  irq1 (line 49): DEN high and the stable double IRQ; irq2 falls into the 200 rows.
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
        lda #$1b
        sta VIC_CTRL1
        lda #<irq2
        sta $fffe
        lda #>irq2
        sta $ffff
        ldy LBW                 ; row 0's swatch through the dim map (Y survives the stable raster)
        lda (dm),y
        tay
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
entry:  jmp rows0               ; patched by update: rows0 / rows1

blockend:
        lda #<irq0
        sta $fffe
        lda #>irq0
        sta $ffff
        lda #IRQ0LINE
        sta VIC_RASTER
        asl VIC_IRQ
        jsr musicplay
        jsr update
        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
;  The 200 rows, twice (one set for each frame parity).  Row n:  nop nop (4) / lda ght,x / sta $3fff / lda colt,x / sta $d021 (16, the writes
;  at the same cycles as before the map stage) / ldy buf+n+1, lda (dm),y, tax (11: the NEXT row's index) / jsr dly: 65 (NTSC) or 63 (PAL).
;  Row 0 takes its index from Y (irq1 computed it).
; =============================================================================
.macro ROWSET FP, LAB
LAB:
        .repeat ROWS, N
        nop
        nop
        .if N = 0
        lda ght + 64 * (FP * 2 + (N .mod 2)),y
        sta IDLE
        lda colt + 64 * (FP * 2 + (N .mod 2)),y
        .else
        lda ght + 64 * (FP * 2 + (N .mod 2)),x
        sta IDLE
        lda colt + 64 * (FP * 2 + (N .mod 2)),x
        .endif
        sta VIC_BG
        .if N < ROWS - 1
        ldy LBW + N + 1
        lda (dm),y
        tax
        jsr dly
        .else
        bit $ea
        jsr dlyl
        .endif
        .endrep
        jmp blockend
.endmacro

.segment "ROWS0"
        ROWSET 0, rows0

.segment "ROWS1"
        ROWSET 1, rows1

.segment "TABLES"
colt:   COLT
ght:    GHT

.segment "CODE"
codeend:
