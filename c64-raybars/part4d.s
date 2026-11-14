; =============================================================================
;  PART 4 for the C64 as DELAYED COPIES (part4d_gen.py), 6 raster-split columns on part4c's raster loop.
;  SPLITS=6 python3 part4d_gen.py ; python3 mk_cart_all.py out.crt part1r part2c part2w part3c part4d
; =============================================================================
;
;  The raster loop is part4c's (200 lines, 65 cycles each, X = the line, 6 column reads `lda page,x / sta $d021` and the next line's idle byte).
;  Every frame's record [F][hi of the 6 column pages][hi of the idle page][nA][runs A][nB][runs B] patches the loop's 7 page operands: the columns
;  read pages of a RING (two sources, each column a different frame of its source), `doruns` copies the newest source pages into ring slots.
;  Nothing is compared on the 6502: the generator decides which slot every column reads, frame by frame.  A column is moved up and down as a whole by
;  the LOW byte of its page operand (page row r sits at offset C0 + r, zero margins: C0 - shift + line never crosses a page).
; =============================================================================

        .setcpu "6502"
        .include "part4d.inc"

LINE0     = 0                   ; (a later start would not help: DEN must be high before line 51, so the stable IRQ stays at line 49)
LINE1     = 184
FIRST_LINE = 51 + LINE0
IRQ0LINE  = 46
IRQLINE   = FIRST_LINE - 2
.ifndef PRE
PRE       = 1
.endif
.ifndef HTUNE
HTUNE     = 0
.endif
.ifndef ODD
ODD       = 1
.endif
.ifndef WAITX
WAITX     = 8                   ; NTSC (6567R8): WAITX 8 + PRE 1 + bit $00 = the one compare window that
                                ; absorbs the 1-cycle jitter (VICE: 32/32 frames identical, column 1 at x = 33)
.endif
.ifndef BASE
BASE = 1
.endif
STREAM_BANK0 = BASE + IMGBANKS      ; the stream's first ROML bank (cartboot: bank 0 = boot, banks 1.. = the program image)

.ifndef CHAIN
CHAIN      = 0                  ; -Wa -DCHAIN=1 -Wa -DNFE=n: after NFE frames go on with the gold sequence (bgload.s, GOLD_NTSC_PLAN.md) instead of the cartridge loader
.endif
.if CHAIN
        .include "bgzp.inc"
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

.segment "ZEROPAGE"
fcl:     .res 1
fch:     .res 1
sp:      .res 2                 ; the stream pointer (in the ROML window)
bank:    .res 1
nruns:   .res 1
nt:      .res 1
nt1:     .res 1                 ; the stage-2 target line (nt + 1)
mc:      .res 1                 ; the music play-call counter
nf:      .res 1                 ; F: the first active line of the frame shown after this blank (0 = from row 0)
cnt:     .res 1
cnt3:    .res 1
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
        lda #0
        sta fch
        sta mc
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
        jsr clearpages
.if CHAIN
        ldx #0                  ; the background loader to $0300, its job list: bank 0 ROML, $8000
:       lda __BGLOAD_LOAD__,x
        sta __BGLOAD_RUN__,x
        inx
        cpx #<__BGLOAD_SIZE__
        bne :-
        lda #0
        sta JOB
        sta DONE
        sta DONE+1
        sta NOTICK
        lda #$80
        sta JOB+1
.endif
jsr update              ; frame 0
        cli
@idle:  .repeat 100
        nop                     ; 2-cycle ops only (a 3-cycle jmp adds a third jitter state to the first IRQ)
        .endrep
        jmp @idle

; clear the zero page (the idle byte page of the busy frames) and the margins of every ring / uniform page: RAM is not cleared and the copies only write
; rows R0..184 (page offsets C0 + R0 .. C0 + 184); a shifted column reads the margins.
clearpages:
        ldx #ZERO_HI
        stx @z0 + 2
        ldy #0
        tya
@z0:    sta $ff00,y
        iny
        bne @z0
@pg:    inx
        cpx #ZERO_HI + 1 + RING_PAGES
        beq @done
        stx @z1 + 2
        stx @z2 + 2
        ldy #C0 + R0 - 1        ; above the rows: offsets 0 .. C0 + R0 - 1
@z1:    sta $ff00,y
        dey
        bpl @z1
        ldy #255                ; below the rows: C0 + 185 .. 255
@z2:    sta $ff00,y
        dey
        cpy #C0 + 184
        bne @z2
        beq @pg
@done:  rts

nmi:    rti

; -----------------------------------------------------------------------------
;  update: apply this blank's record, then patch the loop for the next frame's parity
; -----------------------------------------------------------------------------
.proc update
.if ::CHAIN
        lda fcl                 ; the film is over (NFE frames shown): the gold sequence, at the start of the blank (it needs ~40 lines)
        cmp #<::NFE
        bne @go
        lda fch
        cmp #>::NFE
        bne @go
        lda mc                  ; the tune's cadence goes on (the blank's play call has been made)
        sta MC
        lda #1
        sta NOTICK
        jmp bgswitch
@go:
.endif
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
@rec:   sta nf                  ; F: the first active line of the frame shown after this blank
        inc sp
        bne @f0
        inc sp+1
@f0:    ldy #0                  ; the loop's 7 page operands (high bytes): the 6 columns' pages and the idle byte page; then the 6 columns' low bytes (the shift)
        lda (sp),y
        sta rP0 + 2
        iny
        lda (sp),y
        sta rP1 + 2
        iny
        lda (sp),y
        sta rP2 + 2
        iny
        lda (sp),y
        sta rP3 + 2
        iny
        lda (sp),y
        sta rP4 + 2
        iny
        lda (sp),y
        sta rP5 + 2
        iny
        lda (sp),y
        sta rG + 2
        sta @i0 + 2
        iny
        lda (sp),y
        sta rP0 + 1
        iny
        lda (sp),y
        sta rP1 + 1
        iny
        lda (sp),y
        sta rP2 + 1
        iny
        lda (sp),y
        sta rP3 + 1
        iny
        lda (sp),y
        sta rP4 + 1
        iny
        lda (sp),y
        sta rP5 + 1
        iny
        lda (sp),y              ; nA
        sta nruns
        clc
        lda sp
        adc #14
        sta sp
        bcc @f1
        inc sp+1
@f1:    jsr doruns              ; group A: before line 49
        lda nf
        beq @noden
@dw:    lda VIC_RASTER          ; wait for line 49 (also true when we are already in 49..98), then DEN high: the window opens at line 51
        sec
        sbc #49
        cmp #50
        bcc @den
.if ::CHAIN
        jsr bgslot              ; (the time we would spin away: a chunk of the next routine from the cartridge, when it fits before line 49)
.endif
        jmp @dw
@den:   lda #$1b
        sta VIC_CTRL1
@noden: ldy #0
        lda (sp),y              ; nB
        sta nruns
        inc sp
        bne @f2
        inc sp+1
@f2:    jsr doruns              ; group B: after the DEN write, until the stable IRQ at line 49 + F
@done:
        lda nf                  ; the loop starts at row F (the rows above are black anyway)
        sta rows + 1
        clc
        adc #C0
        sta @i0 + 1
@i0:    lda $ff00 + C0          ; (the first line's idle byte; the loop writes the NEXT line's after each line)
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
        jmp $0200               ; the chain: the next part is loaded
        lda #0                  ; (the film loops: the stream starts again)
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
        lda #<irq1              ; arm the stable raster IRQ (stage 1) for line 49 + F: 2 lines before the first row
        sta $fffe
        lda #>irq1
        sta $ffff
        lda nf
        clc
        adc #IRQLINE
        sta nt                  ; the target line
        clc
        adc #1
        sta nt1
@chk:   lda VIC_RASTER          ; never arm while the beam is within 3 lines before the target or on it: the IRQ would come late and
        sec                     ; the stable sync (stage 2) would miss; wait the line out (the IRQ then comes in the next frame)
        sbc nt
        clc
        adc #3
        cmp #4
        bcc @chk
        lda VIC_RASTER          ; missed this frame's target (the update ran past it)? the IRQ then comes in the next frame:
        cmp nt                  ; DEN must be low again before that frame's line 48, or badlines start (and break the sync)
        bcc @ok
        cmp #230                ; (lines >= 230: still the blank before this frame, not late)
        bcs @ok
        lda #$0b
        sta VIC_CTRL1
@ok:
        lda nt                  ; the new target FIRST, then the ack: a match of the OLD compare (last frame's stage 2 line)
        sta VIC_RASTER          ; while we were busy would otherwise stay latched and fire stage 1 at once
        asl VIC_IRQ
        lda #1
        sta $d01a
        rts
.endproc

.if CHAIN
; bgslot: one chunk (bgload.s: 24 bytes, ~600 cycles = 10 lines) if there are 12 lines or more to line 49.  The chunk leaves $01 and the ROML bank as it
; likes: the stream's again.
bgslot: lda #49
        sec
        sbc VIC_RASTER
        cmp #12
        bcc @no
        jsr chunk
        lda #$37
        sta $01
        lda bank
        sta $de00
@no:    rts
.endif

; the runs of a group: [page][line][len] bytes, copied into the pages (the stream is in the ROML window, $01 = $37)
.proc doruns
        lda nruns
        beq @dn
@run:   ldy #0                  ; run = [first line][page address high][length] bytes   (the generator writes the page's high byte: PAGES = $2B00)
        lda (sp),y
        sta @st + 1
        sta @s2 + 1
        iny
        lda (sp),y
        sta @st + 2
        sta @s2 + 2
        iny
        lda (sp),y
        sta cnt
        clc                     ; the bytes follow the 3 header bytes
        adc #3
        sta cnt3                ; the next run: sp + 3 + length
        lda sp
        adc #3                  ; (carry clear: the length is at most 120)
        sta @ld + 1
        sta @l2 + 1
        lda sp+1
        adc #0
        sta @ld + 2
        sta @l2 + 2
        ldy cnt
        dey
        lsr cnt                 ; odd length: start with the second half of the unrolled loop (one byte), then pairs
        bcs @l2
@ld:    lda $ffff,y             ; the copy loop, unrolled twice: 25 cycles for 2 bytes (the plain loop: 28)
@st:    sta $ffff,y
        dey
@l2:    lda $ffff,y
@s2:    sta $ffff,y
        dey
        bpl @ld
        clc                     ; sp += 3 + length
        lda sp
        adc cnt3
        sta sp
        bcc @a2
        inc sp+1
@a2:    dec nruns
        bne @run
@dn:    rts
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
        lda nt1                 ; (not inc: inc reads the CURRENT line, so a late stage 1 armed stage 2 a line too late)
        sta VIC_RASTER
        asl VIC_IRQ
        tsx
        cli
        .repeat 12
        nop
        .endrep
.ifdef SLEDPAD
        .repeat SLEDPAD         ; (build: keeps the row loop inside one page -- a page-crossing bne costs a cycle)
        nop
        .endrep
.endif

irq2:   txs
        .repeat PRE
        nop
        .endrep
        ldx #WAITX
@w:     dex
        bne @w
        .if ODD
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
rP0:    lda $ff00,x
        sta VIC_BG
rP1:    lda $ff00,x
        sta VIC_BG
rP2:    lda $ff00,x
        sta VIC_BG
rP3:    lda $ff00,x
        sta VIC_BG
rP4:    lda $ff00,x
        sta VIC_BG
rP5:    lda $ff00,x
        sta VIC_BG
rG:     lda $ff00 + C0 + 1,x   ; the NEXT line's idle byte, written in the right border
        sta IDLE
        nop                     ; NTSC: 65 cycles a line
        inx
        cpx #LINE1 + 1
        bne rloop
rend:
        lda #0                  ; black below the floor
        sta VIC_BG
        sta IDLE
        jmp blockend

; the tune's play routine (Alpha.sid stays resident at $1000-$2A33 from part 1; this part's pages sit above it at $2B00): 5 calls in 6 frames
; (NTSC: the tune was written for 50 Hz).  A call costs 280-1540 cycles; the generator takes each blank's real cost off the update's budget.
MUSIC_PLAY = $1003
musicplay:
        inc mc
        lda mc
        cmp #6
        bne @go
        lda #0
        sta mc
        rts
@go:    jmp MUSIC_PLAY

blockend:
        lda #$0b                ; DEN low: no badlines in the next frame (the update raises it in lines 49-50, or the stable IRQ does when F = 0)
        sta VIC_CTRL1
        sei                     ; (if the second sync interrupt ever misses, the I flag is still clear here)
        jsr musicplay
        lda #0
        sta $d01a               ; no raster IRQ source while the update runs ($01 = $37: the vector would come from ROM)
        jsr update
        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
;  The 200 lines: one loop of 63 cycles (7 x (lda abs,x 4 + sta 4) + inx 2 + cpx 2 + bne 3)
; =============================================================================

.if CHAIN
        .import __BGLOAD_LOAD__, __BGLOAD_RUN__, __BGLOAD_SIZE__
        .include "bgload.s"
.endif
