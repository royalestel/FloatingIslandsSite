; =============================================================================
;  bgload.s -- the gold sequence's background loader, resident at $0300-$03FE
;  (MC, the tune's frame counter, is $03FF).  See GOLD_NTSC_PLAN.md.
;
;  The job list lives in the cartridge, bank 0 ROML ($8000-), 8 bytes a record:
;     bank, src lo, src hi, dst lo, dst hi, len lo, len hi, 0    copy len bytes (src in $8000-$BFFF of that bank)
;     $FD                                                         the switch-time records follow (bgstep stops here)
;     $FF, start lo, start hi                                     the next routine's swstart (bgswitch jumps there)
;
;  bgstep   ($0300, jsr): from a routine's idle loop.  Copies 32 bytes of the
;           next routine's image if the next raster IRQ (NIRQ) is at least 13
;           lines away; with interrupts off, $01 = $37 (the cartridge visible).
;  bgswitch ($0303, jmp): at a routine's end, interrupts off: copies whatever
;           is left up to the barrier (the switch-time records: zero page,
;           shared sprite bytes), calls the tune once (the old routine skipped
;           this frame's call) and jumps to the next routine's swstart.
;  tick     ($0306, jsr): the tune, 5 calls in 6 frames (the counter MC).
; =============================================================================
NIRQ    = $ef           ; the line the next raster IRQ is set for (every chained routine keeps it)
JOB     = $f0           ; record being copied
DONE    = $f1           ; 2: bytes of it copied
SRC     = $f3           ; 2
DST     = $f5           ; 2
MC      = $03ff
MUSIC_PLAY = $1003
CHUNK   = 32            ; bytes per bgstep: 32 x 16 cycles + ~170 = ~11 lines
MINLINES = 13

.segment "BGLOAD"
bgstep:   jmp step
bgswitch: jmp switch
tick:     inc MC
        lda MC
        cmp #6
        bne :+
        lda #0
        sta MC
        rts
:       jmp MUSIC_PLAY

step:   php
        sei
        lda $d011
        bmi @go                 ; raster >= 256: the next IRQ (always < 256) is next frame
        lda NIRQ
        sec
        sbc $d012
        bcc @go                 ; it has passed: next frame
        cmp #MINLINES
        bcs @go
        plp
        rts
@go:    jsr chunk
        plp
        rts

switch: sei
        ldx #$ff
        txs
@l:     jsr chunk
        bcc @l
        lda rec
        cmp #$ff
        beq @start
        inc JOB                 ; the $FD marker: on
        jmp @l
@start: inc JOB
        jsr tick
        jmp (rec+1)

; chunk: C = 1 (nothing copied) at a marker, else up to CHUNK bytes of record JOB
chunk:  lda #0                  ; the record: bank 0, $8000 + 8 * JOB
        sta $de00
        lda JOB
        asl
        asl
        asl
        sta @fs+1
        lda JOB
        lsr
        lsr
        lsr
        lsr
        lsr
        ora #$80
        sta @fs+2
        lda #$37
        sta $01
        ldx #6
@fs:    lda $8000,x
        sta rec,x
        dex
        bpl @fs
        lda #$35
        sta $01
        lda rec
        cmp #$fd
        bcc @copy
        rts                     ; (C = 1)
@copy:  lda rec+1
        clc
        adc DONE
        sta SRC
        lda rec+2
        adc DONE+1
        sta SRC+1
        lda rec+3
        clc
        adc DONE
        sta DST
        lda rec+4
        adc DONE+1
        sta DST+1
        lda rec+5               ; n = min(CHUNK, len - done)
        sec
        sbc DONE
        tax
        lda rec+6
        sbc DONE+1
        bne @full
        cpx #CHUNK
        bcc @part
@full:  ldx #CHUNK
@part:  stx n
        lda rec
        sta $de00
        lda #$37
        sta $01
        ldy #0
@b:     lda (SRC),y
        sta (DST),y
        iny
        dex
        bne @b
        lda #$35
        sta $01
        lda DONE
        clc
        adc n
        sta DONE
        bcc :+
        inc DONE+1
:       cmp rec+5
        bne @more
        lda DONE+1
        cmp rec+6
        bne @more
        inc JOB                 ; record done
        lda #0
        sta DONE
        sta DONE+1
@more:  clc
        rts

rec:    .res 7
n:      .res 1
        .assert * <= $03ff, error, "bgload runs into MC ($03ff)"
