; =============================================================================
;  PART 1 -- the intro film for the C64 (PAL): ghost-byte swatches, plain raster code
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
        .include "part1p.inc"

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
LINEBUF    = $0400              ; the screen is never shown; 64 bytes of padding either side

        .import p_sin, p_sk, p_azs, p_sb, p_se, p_sc, p_risel, p_riseh, p_zbfl, p_zbfh
        .import p_kyl, p_kyh, p_tt, p_dx, p_dimt, p_full, p_foffl, p_foffh, p_sqlo, p_sqhi

; =============================================================================
.segment "ZEROPAGE"
rp:      .res 2
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

; the film starts (again): frame 0, phase, stream
restart:
        lda #0
        sta fcl
        sta fch
        sta pa
        lda #>PH0
        sta pa+1
        lda #<scene
        sta rp
        lda #>scene
        sta rp+1
        rts

dly:    .repeat 14
        nop
        .endrep
        rts

; -----------------------------------------------------------------------------
;  8 x 8 multiply by quarter squares: mda * mrr -> A (high) : mrr (low)
; -----------------------------------------------------------------------------
mul8:   lda mda
        sec
        sbc mrr
        bcs @d
        eor #$ff
        adc #1
@d:     tay                     ; |a - b|
        lda mda
        clc
        adc mrr
        bcs @big
        tax                     ; a + b < 256
        lda p_sqlo,x
        sec
        sbc p_sqlo,y
        sta mrr
        lda p_sqhi,x
        sbc p_sqhi,y
        rts
@big:   tax                     ; a + b = 256 + x
        lda p_sqlo+256,x
        sec
        sbc p_sqlo,y
        sta mrr
        lda p_sqhi+256,x
        sbc p_sqhi,y
        rts

; -----------------------------------------------------------------------------
;  lerp: la = la + (lb - la) * lw / 255, exact at lw = 0 (la) and 255 (lb); sign-magnitude, as part1_proc.lerp8
; -----------------------------------------------------------------------------
lerp:   lda lw
        beq @ret
        cmp #255
        bne @m
        lda lb
        sta la
        lda lb+1
        sta la+1
@ret:   rts
@m:     lda lw                  ; w' = w + (w >> 7)
        bpl @w1
        clc
        adc #1
@w1:    sta l2                 ; the multiplier
        sec                     ; d = lb - la
        lda lb
        sbc la
        sta dl
        lda lb+1
        sbc la+1
        sta dh
        sta sg                  ; the sign (bit 7)
        bpl @abs
        sec                     ; |d|
        lda #0
        sbc dl
        sta dl
        lda #0
        sbc dh
        sta dh
@abs:   lda dl                  ; (|d| * w') >> 8 = dh * w' + ((dl * w') >> 8)
        sta mda
        lda l2
        sta mrr
        jsr mul8                ; A = high of dl*w'
        sta l1
        lda dh
        sta mda
        lda l2
        sta mrr
        jsr mul8                ; A:mrr = dh*w'
        clc
        adc #0                  ; (high byte stays)
        sta dh
        lda mrr
        clc
        adc l1
        sta dl
        bcc @nc
        inc dh
@nc:    lda sg
        bmi @neg
        clc                     ; la += m
        lda la
        adc dl
        sta la
        lda la+1
        adc dh
        sta la+1
        rts
@neg:   sec                     ; la -= m
        lda la
        sbc dl
        sta la
        lda la+1
        sbc dh
        sta la+1
        rts

; -----------------------------------------------------------------------------
;  clamp la (16 bits, signed) to ZMIN .. ZMAX
; -----------------------------------------------------------------------------
clampz: lda la+1
        bmi @min
        cmp #2                  ; ZMAX = 511: a high byte of 2 or more is too far
        bcs @max
        cmp #1
        beq @ok                 ; 256 .. 511
        lda la                  ; < 256: at least ZMIN
        cmp #ZMIN
        bcs @ok
@min:   lda #<ZMIN
        sta la
        lda #>ZMIN
        sta la+1
        rts
@max:   lda #<ZMAX
        sta la
        lda #>ZMAX
        sta la+1
@ok:    rts

; -----------------------------------------------------------------------------
;  pbars: the three bars of frame (fcl, fch) -> bt / by / bk, and ordr (far first)
; -----------------------------------------------------------------------------
.proc pbars
        ; --- s: smoothstep of (t - T_B0) over NB frames
        sec
        lda fcl
        sbc #<T_B0
        sta dl
        lda fch
        sbc #>T_B0
        sta dh
        bmi @s0
        lda dh
        bne @s255
        lda dl
        cmp #NB
        bcs @s255
        tax
        lda p_sb,x
        jmp @ss
@s0:    lda #0
        beq @ss
@s255:  lda #255
@ss:    sta sv
        ; --- zb: the circle's centre distance (1/64 m)
        sec
        lda fcl
        sbc #<ZB0
        sta dl
        lda fch
        sbc #>ZB0
        sta dh
        bmi @zdef
        lda dh
        beq @zlo
        cmp #>NZB
        bne @zdef
        lda dl
        cmp #<NZB
        bcs @zdef
        tax
        lda p_zbfl+256,x
        sta zbl
        lda p_zbfh+256,x
        sta zbh
        jmp @zok
@zlo:   ldx dl
        lda p_zbfl,x
        sta zbl
        lda p_zbfh,x
        sta zbh
        jmp @zok
@zdef:  lda #<ZC0
        sta zbl
        lda #>ZC0
        sta zbh
@zok:   lda #0
        sta kk
; ---- one bar
@bar:   ldx kk
        lda pa+1
        clc
        adc phk,x
        sta pk
        tax
        lda p_azs,x             ; zc = zb + azs[pk], sign-extended
        sta t1
        ldy #0
        bpl @pos
        dey
@pos:   clc
        lda zbl
        adc t1
        sta lb
        tya
        adc zbh
        sta lb+1
        lda #<Z_EQ              ; z = lerp(Z_EQ, zc, s)
        sta la
        lda #>Z_EQ
        sta la+1
        lda sv
        sta lw
        jsr lerp
        jsr clampz
        ; c = cos(pk): sign in sg, |c| in t2
        lda pk
        clc
        adc #64
        tax
        lda p_sin,x
        sta sg
        bpl @cp
        eor #$ff
        clc
        adc #1
@cp:    sta t2
        ; KY[z] -> kl in mrr, kh in t1
        ldx la
        lda la+1
        bne @kyhi
        lda p_kyl,x
        sta mrr
        lda p_kyh,x
        jmp @ky
@kyhi:  lda p_kyl+256,x
        sta mrr
        lda p_kyh+256,x
@ky:    sta t1
        lda la                  ; keep z in zl/zh across the multiply
        sta zl
        lda la+1
        sta zh
        lda t2
        sta mda
        jsr mul8                ; A:mrr = |c| * kl
        sta t3                  ; hi
        lda #0                  ; off = 2*hi + (lo >> 7)  (+ 2*|c| if kh)
        sta oh
        lda t3
        asl
        sta ol
        rol oh
        asl mrr                 ; carry = lo >> 7
        lda ol
        adc #0
        sta ol
        bcc @o1
        inc oh
@o1:    lda t1
        beq @o2
        asl t2                  ; + 2*|c|
        lda #0
        rol
        sta t3
        clc
        lda ol
        adc t2
        sta ol
        lda oh
        adc t3
        sta oh
@o2:    lda #100                ; yc = 100 - off (c >= 0) or 100 + off
        sta yl
        lda #0
        sta yh
        lda sg
        bmi @cn
        sec
        lda yl
        sbc ol
        sta yl
        lda yh
        sbc oh
        sta yh
        jmp @yc
@cn:    clc
        lda yl
        adc ol
        sta yl
        lda yh
        adc oh
        sta yh
@yc:    ldx kk
        lda la                  ; z
        sta zl
        lda la+1
        sta zh
        ; rise: d = t - T_ENTER[k]; <= 0: 260, >= NE: 0, else RISE[d]
        sec
        lda fcl
        sbc entl,x
        sta dl
        lda fch
        sbc enth,x
        sta dh
        bmi @r260
        lda dh
        bne @r0
        lda dl
        beq @r260
        cmp #NE
        bcs @r0
        tax
        lda p_risel,x
        sta t1
        lda p_riseh,x
        sta t2
        jmp @radd
@r260:  lda #<260
        sta t1
        lda #>260
        sta t2
        jmp @radd
@r0:    lda #0
        sta t1
        sta t2
@radd:  clc
        lda yl
        adc t1
        sta yl
        lda yh
        adc t2
        sta yh
        ; z clamped, T = TT[z]
        lda zl
        sta la
        lda zh
        sta la+1
        jsr clampz
        ldx la
        lda la+1
        bne @tthi
        lda p_tt,x
        jmp @tt
@tthi:  lda p_tt+256,x
@tt:    ldx kk
        sta bt,x
        lsr                     ; y0 = yc - (T >> 1)
        sta t1
        sec
        lda yl
        sbc t1
        sta byl,x
        lda yh
        sbc #0
        sta byh,x
        ; key = 4 * z - sk[pk] (sk signed)
        lda la
        sta t1
        lda la+1
        sta t2
        asl t1
        rol t2
        asl t1
        rol t2
        ldy pk
        lda p_sk,y
        sta t3
        ldy #0
        lda t3
        bpl @kp
        dey
@kp:    sec
        lda t1
        sbc t3
        sta bkl,x
        lda t2
        sty t3
        sbc t3
        sta bkh,x
        inc kk
        lda kk
        cmp #3
        beq @sort
        jmp @bar
; ---- order, far first = larger key first (stable bubble sort, like the model's sort)
@sort:  lda #0
        sta ordr
        lda #1
        sta ordr+1
        lda #2
        sta ordr+2
        ldx #0
        jsr @cswap
        ldx #1
        jsr @cswap
        ldx #0
        jsr @cswap
        rts
@cswap: ldy ordr,x              ; a
        lda ordr+1,x
        sta t1                  ; b
        stx t2                  ; i
        ldx t1
        sec                     ; swap if key[a] < key[b] (signed 16 bits)
        lda bkl,y
        sbc bkl,x
        lda bkh,y
        sbc bkh,x
        bvc @nv
        eor #$80
@nv:    bpl @keep
        ldx t2
        lda ordr+1,x
        sta t3
        lda ordr,x
        sta ordr+1,x
        lda t3
        sta ordr,x
@keep:  rts
phk:    .byte 0, PHK1, PHK2
slotl:  .byte <SLOT0, <SLOT1, <SLOT2
sloth:  .byte >SLOT0, >SLOT1, >SLOT2
entl:   .byte <T_ENTER0, <T_ENTER1, <T_ENTER2
enth:   .byte >T_ENTER0, >T_ENTER1, >T_ENTER2
.endproc

; -----------------------------------------------------------------------------
;  pdraw: the three bars, far to near, into LINEBUF (no clipping: the buffer has padding)
;    per row:  level = FULL[T][r];  map (the dimming) -> level;  | 32 if the bar's first line is odd
; -----------------------------------------------------------------------------
.proc pdraw
        ; the dimming map for this frame: p_dimt + di * 64
        lda #0
        sta di
        sec
        lda fcl
        sbc #<DIM0
        sta dl
        lda fch
        sbc #>DIM0
        sta dh
        bmi @nodim
        lda dh
        bne @nodim
        lda dl
        cmp #NDIM
        bcs @nodim
        tax
        lda p_dx,x
        sta di
@nodim: lda di                  ; di * 64
        lsr
        lsr
        sta t2                  ; di >> 2
        lda di
        and #3
        lsr
        ror
        ror
        sta t1                  ; (di & 3) << 6
        clc
        lda t1
        adc #<p_dimt
        sta @mp + 1
        lda t2
        adc #>p_dimt
        sta @mp + 2
        ldx #0
@next:  stx kk
        ldy ordr,x
        lda bt,y
        sta t3                  ; T
        lda byl,y
        sta yl
        lda byh,y
        sta yh
        bmi @neg                ; y0 < 0: visible only if y0 + T > 0
        bne @skip               ; y0 >= 256
        lda yl
        cmp #200
        bcs @skip
        bcc @draw
@neg:   clc
        lda yl
        adc t3
        sta t1
        lda yh
        adc #0
        bmi @skip               ; y0 + T < 0
        ora t1
        beq @skip               ; = 0
@draw:  ldx t3                  ; FULL + foff[T]
        clc
        lda p_foffl,x
        adc #<p_full
        sta @ld + 1
        lda p_foffh,x
        adc #>p_full
        sta @ld + 2
        clc                     ; dst = LINEBUF + y0
        lda yl
        adc #<LINEBUF
        sta @st + 1
        lda yh
        adc #>LINEBUF
        sta @st + 2
        lda yl                  ; | 32 if y0 is odd
        and #1
        beq @ev
        lda #$20
@ev:    sta @or + 1
        ldx t3                  ; the rows, from the last to the first
        dex
@ld:    lda $ffff,x
        tay
@mp:    lda $ffff,y
@or:    ora #0
@st:    sta $ffff,x
        dex
        bpl @ld
@skip:  ldx kk
        inx
        cpx #3
        bne @next
        rts
.endproc

; -----------------------------------------------------------------------------
;  update: the next frame's buffer of swatch indices, and which row set shows it
; -----------------------------------------------------------------------------
.proc update
        lda #0
        .repeat ::ROWS, N
        sta LINEBUF + N         ; clear: 4 cycles a line
        .endrep
        lda fch
        cmp #>T_PROC
        bcc @proc
        bne @stream
        lda fcl
        cmp #<T_PROC
        bcs @stream
@proc:  jsr pbars
        jsr pdraw
        clc                     ; the phase moves on
        lda pa
        adc #<PINC
        sta pa
        lda pa+1
        adc #>PINC
        sta pa+1
        jmp @done
@stream:
        ldy #0
        lda (rp),y
        cmp #$ff
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
@ld:    lda $ffff,y             ; the bar array's swatch index (+ 32 for an odd first line)
@st:    sta LINEBUF,y
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
        jsr restart             ; the film loops
@ret:   rts
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
prof:   .incbin "part1p_prof.bin"

.segment "SCENE"
scene:  .incbin "part1p_rec.bin"
