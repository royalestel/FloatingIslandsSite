; =============================================================================
;  GOLDFLY -- raster bars flying out of the distance past a central light
;  cl65 -t none -C raybars.cfg -o goldfly.prg goldfly.s
; =============================================================================
;
;  The light is a ball sprite fixed at the centre of the screen.  Three
;  bars at a time fly toward the camera from the distance, alternating
;  above / below the light.  Each new bar draws one of 53 tilts
;  (staircases, neighbouring segments up to 2 lines apart) that has not
;  been shown for at least 40 bars.  It takes the next entry of
;  two shuffled cycles (fly.inc) for its distance from the centre line (15
;  values: some start right next to the light, some well out) and palette
;  (gold, a second 24-colour one, and two 12-colour ones dithered up to
;  24).  The tilt never changes in flight.  In perspective they start small near the middle, grow
;  and fly out through the top or bottom edge.  They dim with distance and
;  reflect the light: thickest nearest it, and riding to the bar's edge once
;  a bar is nearer the camera than the light.
;
;  DISPLAY: POINTER-READ SPEEDCODE
;  Each bar's display code is a 63-cycle loop over its rows:
;       5 x (lda (pK),y / sta $d021)  =  5 x 9 cycles  (72-pixel segments)
;  pK points into segment K's colour column for this bar, offset by the
;  segment's tilt.  Nothing is patched per frame: the main loop only builds
;  the columns and the pointers.  The bars live inside the display window
;  (opened without badlines, see goldlight.s), so only $d021 is written;
;  the side borders stay black.  Each column is one page, so (pK),y never
;  crosses a page (that would cost a cycle).
;
;  FRAME PIPELINE
;  The main loop builds frame N+1 (columns into the back buffer, pointers
;  and the IRQ schedule into "next" copies) while frame N is shown.  The
;  top IRQ swaps them in when ready.  Bars never reach the light's sprite
;  lines (no DMA steal to allow for).
;
;  OVERLAPS
;  Two bars on the same side can cross.  Bars too close for an IRQ each are
;  merged: the nearer bar's block grows to cover both lines ranges and the
;  farther bar's colours are copied into the nearer bar's padding, around
;  its own rows -- so the nearer bar is drawn in front.
; =============================================================================

        .setcpu "6502"

        .include "fly.inc"      ; FLYD, flight tables, spawn cycles, dimmed palettes

NSLOT     = 3           ; bars in flight
SEGS      = 5
PAD       = 8           ; black rows above / below a bar's rows (>= max slant)
BASE      = 72          ; a bar's first row in its column; the rest of the
                        ; page is room for a merged bar above or below
BARH      = 24          ; source rows per palette
CENTRE    = 150         ; centre line of the screen: the light
WTOP      = 62          ; bars are drawn on lines WTOP..WBOT
WBOT      = 250
DENLINE   = 44
HTUNE     = 0
HLTHR     = 3           ; highlight: white from spec level 3 (+ segment drop)
VICBANK   = $8000
SPRBUF    = VICBANK + $0000
SPRPTR    = VICBANK + $0400 + $03f8
IDLEBYTE  = VICBANK + $3fff
SPRX      = 184 - 12    ; ball centred on the screen
SPRY      = CENTRE - 11

VIC_SPR0X  = $d000
VIC_SPR0Y  = $d001
VIC_SPRXHI = $d010
VIC_CTRL1  = $d011
VIC_RASTER = $d012
VIC_SPREN  = $d015
VIC_SPRDH  = $d017
VIC_SPRMC  = $d01c
VIC_SPRDW  = $d01d
VIC_IRQ    = $d019
VIC_IRQEN  = $d01a
VIC_BORDER = $d020
VIC_BG     = $d021
VIC_SPRMC0 = $d025
VIC_SPRMC1 = $d026
VIC_SPR0C  = $d027
CIA1_ICR   = $dc0d
CIA2_PRA   = $dd00
CIA2_ICR   = $dd0d

theta2    = theta2_12

; =============================================================================
.segment "ZEROPAGE"
ptr:     .res NSLOT*SEGS*2      ; live column pointers (read by the bars)
frameflag: .res 1               ; top IRQ: start building the next frame
ready:   .res 1                 ; main loop: next frame is built
buf:     .res 1                 ; column buffer being built (0/1)
spawn:   .res 1                 ; bars spawned so far
thead:   .res 1                 ; tilt ring: oldest entry
tr:      .res 1
tlast:   .res 1                 ; the last tilt drawn
seed:    .res 1                 ; random bytes
yi:      .res 1                 ; spawn cycle positions: distance,
pali:    .res 1                 ;   palette
sidx:    .res 1                 ; schedule entry being shown
curn:    .res 1                 ; rows / first row / code of the next bar
cury:    .res 1
curvec:  .res 2
st:      .res NSLOT             ; per slot: flight time
spal:    .res NSLOT             ;           palette
stilt:   .res NSLOT             ;           tilt (staircase)
sY:      .res NSLOT             ;           lateral distance
sydy:    .res NSLOT             ;           its dy toward the light
sside:   .res NSLOT             ;           0 = above the light, 1 = below
s:       .res 1                 ; slot being built
h:       .res 1                 ; its height, distance level, offset
lev:     .res 1
off:     .res 1
dy:      .res 1                 ; atan2 inputs
dz:      .res 1
sb:      .res 1
acc:     .res 1
kb:      .res SEGS              ; tilt: column start per segment
top:     .res 1                 ; first line shown, end line
bend:    .res 1
m1:      .res 1                 ; multiplier
n:       .res 1
ys:      .res 1
hh:      .res 1
lb:      .res 1         ; highlight brightness base
rsp:     .res 2         ; rowstart row for this bar height
si:      .res 1         ; source row
rend:    .res 1
hidx:    .res 1         ; hltab row
save_a:  .res 1
save_x:  .res 1
save_y:  .res 1

; =============================================================================
.segment "LOADADDR"
        .word $0801

.segment "EXEHDR"               ; 10 SYS2061
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
        lda CIA2_PRA            ; VIC bank 2: $8000-$bfff
        and #$fc
        ora #$01
        sta CIA2_PRA
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #<irqtop
        sta $fffe
        lda #>irqtop
        sta $ffff

        lda #0
        sta VIC_BORDER
        sta VIC_BG
        sta IDLEBYTE
        ldx #$7d
@zp:    sta $02,x
        dex
        bpl @zp
        sta ptr                 ; clear all columns (2 buffers)
        tay
        lda #>cols
        sta ptr+1
        ldx #2*NSLOT*SEGS
        tya
@col:   sta (ptr),y
        iny
        bne @col
        inc ptr+1
        dex
        bne @col
        lda #$a5                ; random seed
        sta seed
        ldx #NTILT-1            ; the tilt ring, in a shuffled order
@bag:   lda tbag0,x
        sta tbag,x
        dex
        bpl @bag
        lda #$80
        sta tlast
        ldx #NSLOT-1            ; stagger the bars along their flight
@stg:   lda stagger,x
        sta st,x
        jsr respawn
        lda #0
        sta dirty,x
        sta dirty+NSLOT,x
        dex
        bpl @stg

        ldx #62                 ; the light: the largest ball, centred
@spr:   lda balls + 7*64,x
        sta SPRBUF,x
        dex
        bpl @spr
        lda #<((SPRBUF - VICBANK)/64)
        sta SPRPTR
        lda #1
        sta VIC_SPREN
        sta VIC_SPRMC
        lda #0
        sta VIC_SPRDW
        sta VIC_SPRDH
        lda #<SPRX
        sta VIC_SPR0X
        lda #>SPRX
        sta VIC_SPRXHI
        lda #SPRY
        sta VIC_SPR0Y
        lda #7
        sta VIC_SPR0C
        lda #8
        sta VIC_SPRMC0
        lda #1
        sta VIC_SPRMC1

        lda #$0b
        sta VIC_CTRL1
        lda #DENLINE
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQEN
        sta VIC_IRQ
        jsr build               ; first frame
        cli

main:   lda frameflag           ; the top IRQ has swapped in the last frame
        beq main
        lda #0
        sta frameflag
        jsr build
        jmp main

nmi:    rti

; -----------------------------------------------------------------------------
;  respawn slot x: a tilt from the bag, the next distance and palette from
;  the cycles; sides alternate spawn by spawn.
; -----------------------------------------------------------------------------
.proc respawn
        jsr drawtilt
        sta stilt,x
        ldy yi
        lda ycyc,y
        sta sY,x
        lda ydy,y
        sta sydy,x
        iny
        cpy #NYC
        bcc :+
        ldy #0
:       sty yi
        ldy pali
        lda palcyc,y
        sta spal,x
        iny
        cpy #NPALC
        bcc :+
        ldy #0
:       sty pali
        lda spawn
        and #1
        sta sside,x
        inc spawn
        rts
.endproc

; -----------------------------------------------------------------------------
;  drawtilt: A = a tilt not shown for at least 40 bars.  tbag is a ring of
;  all 53 tilts in the order they were last shown; the TAV oldest (from
;  thead on) are available.  A random one of those is taken and moved to
;  the back.  If it looks too much like the last one (TSIM: indices are
;  ordered by slope), the one half the window away is taken instead.
; -----------------------------------------------------------------------------
TAV  = 13
TSIM = 6
.proc drawtilt
        stx save_t
        lda #TAV
        sta acc
        jsr rand
        jsr mul8                ; A = random * TAV / 256: 0 .. TAV-1
        sta tr
        jsr at
        lda tbag,y
        sec
        sbc tlast
        bcs :+
        eor #$ff
        adc #1
:       cmp #TSIM
        bcs take
        lda tr                  ; too alike: half the window away instead
        clc
        adc #TAV/2
        cmp #TAV
        bcc :+
        sbc #TAV
:       jsr at
take:   ldx thead               ; swap it with the oldest, then step past it:
        lda tbag,y              ; it is now the newest, at the back
        pha
        lda tbag,x
        sta tbag,y
        pla
        sta tbag,x
        sta tlast
        inx
        cpx #NTILT
        bcc :+
        ldx #0
:       stx thead
        ldx save_t
        rts

at:     clc                     ; y = (thead + A) mod NTILT
        adc thead
        cmp #NTILT
        bcc :+
        sbc #NTILT
:       tay
        rts
.endproc

; rand: A = next byte of an 8-bit LFSR (never 0)
.proc rand
        lda seed
        asl
        bcc :+
        eor #$1d
:       sta seed
        rts
.endproc

; -----------------------------------------------------------------------------
;  mulhi: A = round(A * acc / 256).  mul8: A:m1 = A * acc.  Both use X.
; -----------------------------------------------------------------------------
.proc mulhi
        jsr mul8
        asl m1                  ; round
        adc #0
        rts
.endproc

.proc mul8
        sta m1
        lda #0
        ldx #8
        lsr m1
l:      bcc :+
        clc
        adc acc
:       ror
        ror m1
        dex
        bne l
        rts
.endproc

; -----------------------------------------------------------------------------
;  atan2: A = angle of (dy, dz) in brads, all four quadrants.
; -----------------------------------------------------------------------------
.proc atan2
        lda dz
        bpl zpos
        eor #$ff
        clc
        adc #1
zpos:   tay
        lda dy
        bpl ypos
        eor #$ff
        clc
        adc #1
ypos:   tax
        lda log2tab,x
        sec
        sbc log2tab,y
        bcc small
        tax
        lda atanhi,x
        jmp quad
small:  eor #$ff
        adc #1
        tax
        lda atanlo,x
quad:   bit dz
        bpl front
        eor #$ff
        sec
        adc #128
front:  bit dy
        bpl done
        eor #$ff
        clc
        adc #1
done:   rts
.endproc

; write segment K's highlight colour into its column at row x
.macro hlrow K, opname
        .local skip
        lda hltab + K,y         ; this segment's colour (0 = none)
        beq skip
opname = * + 1
        sta $ff00,x
skip:
.endmacro

; =============================================================================
;  build: the next frame -- every bar's columns, pointers, and the schedule
; =============================================================================
.proc build
        ldx #NSLOT-1
slot:   stx s
        jsr doslot
        ldx s
        dex
        bpl slot
        jsr compose
        lda buf                 ; built into this buffer: show it next
        sta nbuf
        lda #1
        sta ready
        rts
.endproc

; -----------------------------------------------------------------------------
;  doslot: one bar
; -----------------------------------------------------------------------------
.proc doslot
        ; ---- fly; respawn at the end of the flight -------------------------
        ldx s
        inc st,x
        lda st,x
        cmp #FLYD
        bcc alive
        lda #0
        sta st,x
        jsr respawn
alive:

        ; ---- this slot's columns in the back buffer: patch the stores -------
        ; column page = >cols + buf*15 + s*5 + k
        lda buf
        beq :+
        lda #15
:       sta acc
        txa
        asl
        asl
        adc s                   ; s*5
        tay
        adc acc
        adc #>cols
        .repeat ::SEGS, K
        sta .ident(.sprintf("zt%d", K))+1
        sta .ident(.sprintf("ex%d", K))+1
        sta .ident(.sprintf("ov%d", K))+1
        sta .ident(.sprintf("zc%d", K))+1
        sta vcp+K,y             ; for compose
        adc #1
        .endrep

        ; ---- flight state --------------------------------------------------
        ldx s
        ldy st,x
        lda fh,y
        sta h
        lda flev,y
        sta lev
        lda fdz,y
        sta dz
        lda finvz,y             ; offset from the centre line = Y / Z
        sta acc
        lda sY,x
        jsr mulhi
        sta off

        ; ---- where it goes on screen: lines top .. bend-1 ------------------
        lda h
        lsr
        clc
        adc #PAD/2
        sta hh                  ; half the block
        lda h
        clc
        adc #PAD
        sta n                   ; block rows
        lda #0
        sta ys                  ; block rows clipped at the top
        ldx s
        lda sside,x
        bne lower
        ; above the light: block top = CENTRE - (off + hh)
        lda off
        clc
        adc hh                  ; u <= 205
        cmp #CENTRE - WTOP + 1
        bcc notclip
        sbc #CENTRE - WTOP      ; rows above WTOP
        sta ys
        cmp n
        bcs hidden              ; all clipped
        lda #WTOP
        sta top
        jmp aend
notclip: eor #$ff
        sec
        adc #CENTRE             ; CENTRE - u
        sta top
aend:   clc
        adc n
        sec
        sbc ys
        sta bend
        jmp visible
lower:  ; below the light: block top = CENTRE + off - hh (off - hh >= 13)
        lda off
        sec
        sbc hh
        clc
        adc #CENTRE
        bcs hidden              ; past line 255
        cmp #WBOT
        bcs hidden
        sta top
        clc
        adc n
        bcs clipb
        cmp #WBOT + 1
        bcc :+
clipb:  lda #WBOT + 1           ; clip at the bottom of the window
:       sta bend
        jmp visible
hidden: ldx s
        lda #0
        sta vis,x
        rts
visible:

        ; ---- tilt -----------------------------------------------------------------
        ldy stilt,x
        .repeat ::SEGS, K
        lda .ident(.sprintf("tilt%d", K)),y
        sta kb+K
        .endrep

        ; ---- the light seen from this bar ---------------------------------------
        lda sydy,x              ; lateral distance, toward the centre
        ldy sside,x
        bne below
        sta dy                  ; bar above: the light is below it (+)
        jmp sdy
below:  eor #$ff
        clc
        adc #1
        sta dy                  ; bar below: the light is above it (-)
sdy:    jsr atan2
        eor #$ff
        clc
        adc #1
        sta spe_op

        ; ---- the bar's palette at this distance: one of 16 tables ----------
        ldx s
        lda spal,x
        asl
        asl
        adc lev
        tax
        lda pdl,x
        sta src_op
        lda pdh,x
        sta src_op+1

        ; ---- 8 black rows before the bar: only stale after a merge -------
        lda buf
        beq :+
        lda #NSLOT
:       clc
        adc s
        tax
        lda dirty,x
        beq clean
        lda #0
        sta dirty,x
        ldx #BASE - PAD
ztop:
zt0 = * + 1
        sta $ff00,x
zt1 = * + 1
        sta $ff00,x
zt2 = * + 1
        sta $ff00,x
zt3 = * + 1
        sta $ff00,x
zt4 = * + 1
        sta $ff00,x
        inx
        cpx #BASE
        bne ztop
clean:

        ; ---- nearest-neighbour expansion into all 5 columns ----------------
        ; nnmap gives each expanded row's cache index (source row, parity)
        ldx h
        lda nnml,x
        sta rsp
        lda nnmh,x
        sta rsp+1
        stx endy_op
        ldy #0
exl:    lda (rsp),y
        tax
src_op = * + 1
        lda $ffff,x
ex0 = * + 1
        sta $ff00 + BASE,y
ex1 = * + 1
        sta $ff00 + BASE,y
ex2 = * + 1
        sta $ff00 + BASE,y
ex3 = * + 1
        sta $ff00 + BASE,y
ex4 = * + 1
        sta $ff00 + BASE,y
        iny
endy_op = * + 1
        cpy #0
        bne exl
        lda #0                  ; 8 black rows after the bar
        ldx #PAD
z8:
zc0 = * + 1
        sta $ff00 + BASE,y
zc1 = * + 1
        sta $ff00 + BASE,y
zc2 = * + 1
        sta $ff00 + BASE,y
zc3 = * + 1
        sta $ff00 + BASE,y
zc4 = * + 1
        sta $ff00 + BASE,y
        iny
        dex
        bne z8

        ; ---- the highlight, per segment ------------------------------------
        ; Only lit source rows are visited; rowstart gives the expanded rows
        ; each one covers.  Colour per segment: hlcol[min(e, 2) + 3 - level],
        ; e = how far the row's spec level exceeds the segment's threshold
        ; (thickest nearest the light, never darker than medium grey).
        ldx lev                 ; highlight table base for this distance
        lda lev45,x
        sta lb
        ldx h
        lda rsl,x
        sta rsp
        lda rsh,x
        sta rsp+1
        ldy #BARH-1
ovi:    ldx theta2,y            ; this source row's spec level
spe_op = * + 1
        lda spectab,x
        cmp #HLTHR
        bcc ovskip
        sty si
        tax
        lda mul5,x
        clc
        adc lb
        sta hidx                ; hltab row for this spec level
        lda (rsp),y             ; rows rowstart[i] .. rowstart[i+1]-1
        clc
        adc #BASE
        tax
        iny
        lda (rsp),y
        clc
        adc #BASE
        sta rend
        cpx rend
        beq ovnext
        ldy hidx
rowl:   hlrow 0, ov0
        hlrow 1, ov1
        hlrow 2, ov2
        hlrow 3, ov3
        hlrow 4, ov4
        inx
        cpx rend
        bne rowl
ovnext: ldy si
ovskip: dey
        bpl ovi

        ; ---- for compose: lines, height, column index of the first line shown
        ; pl_K = BASE - off_K + ys (kb_K = PAD - off_K)
        ldx s
        lda #1
        sta vis,x
        lda top
        sta vD,x
        lda bend
        sta vE,x
        lda h
        sta vh,x
        txa
        asl
        asl
        adc s
        tax
        .repeat ::SEGS, K
        lda kb+K
        clc
        adc ys
        adc #BASE - PAD
        sta vpl+K,x
        .endrep
        rts
.endproc

; -----------------------------------------------------------------------------
;  compose: the next frame's pointers and IRQ schedule from the visible bars,
;  in screen order.  Bars too close for an IRQ each (fewer than 4 lines
;  apart) are merged: the block of the nearer one (further along its flight)
;  grows to cover both, and the farther bar's colours are copied into its
;  column around its own rows.  A third bar on the same lines would be
;  dropped (two bars at most share a side, so it never happens).
; -----------------------------------------------------------------------------
.proc compose
        ldx #0
        ldy #0
gath:   lda vis,y
        beq :+
        tya
        sta ord,x
        inx
:       iny
        cpy #NSLOT
        bne gath
        stx cnt
        lda #0
        sta ncount
        cpx #0
        bne :+
        rts
:       cpx #2                  ; sort by first line (3-element network)
        bcc sorted
        ldx #0
        jsr oswap
        lda cnt
        cmp #3
        bcc sorted
        ldx #1
        jsr oswap
        ldx #0
        jsr oswap
sorted: ldx ord
        jsr begin
        lda #1
        sta oi
nxt:    ldx oi
        cpx cnt
        bcs fin
        ldy ord,x               ; the next bar down
        lda cE
        clc
        adc #4                  ; room for its IRQ?
        bcs close
        cmp vD,y
        bcc apart
        beq apart
close:  lda fr
        bpl adv                 ; already merged: drop a third bar
        ldx nr
        lda st,y                ; nearer = further along its flight
        cmp st,x
        bcc yfar
        sty nr
        stx fr
        jmp grow
yfar:   sty fr
grow:   lda vE,y
        cmp cE
        bcc adv
        sta cE
        jmp adv
apart:  tya
        pha
        jsr emit
        pla
        tax
        jsr begin
adv:    inc oi
        jmp nxt
fin:    ; the last block

; emit: schedule block nr (lines cD .. cE-1), merging bar fr into it
emit:   ldx ncount
        lda cD
        sec
        sbc #2
        sta nline,x
        lda nr
        sta nslot,x
        lda cE
        sec
        sbc cD
        sta nnrows,x
        lda #0
        sta nystart,x
        inc ncount
        ldx nr                  ; near pointers: pl_K - (D - cD)
        lda vD,x
        sec
        sbc cD
        sta dn
        txa
        asl
        asl
        adc nr
        sta ni
        asl
        tax
        ldy ni
        lda #SEGS
        sta k
ptrs:   lda vpl,y
        sec
        sbc dn
        sta nptr,x
        lda vcp,y
        sta nptr+1,x
        inx
        inx
        iny
        dec k
        bne ptrs
        lda fr
        bpl merge
        rts

merge:  ; the far bar's lines, relative to cD: df .. ef-1
        tax
        lda vD,x
        sec
        sbc cD
        sta df
        lda vE,x
        sec
        sbc cD
        sta ef
        txa
        asl
        asl
        adc fr
        sta fi
        ldx nr                  ; near bar rows (kept): BASE .. nbe-1
        lda vh,x
        clc
        adc #BASE
        sta nbe
        lda vE,x                ; near lines: dn .. en-1
        sec
        sbc cD
        sta en
        lda #0                  ; lines in neither block: g0 .. g1-1
        sta g0
        sta g1
        lda en
        cmp df
        bcs :+
        sta g0                  ; near above far
        lda df
        sta g1
:       lda ef
        cmp dn
        bcs :+
        sta g0                  ; far above near
        lda dn
        sta g1
:       lda buf                 ; its top pad needs clearing next time
        beq :+
        lda #NSLOT
:       clc
        adc nr
        tax
        lda #1
        sta dirty,x
        lda #0
        sta k
seg:    lda ni                  ; near column index of line cD
        clc
        adc k
        tax
        lda vpl,x
        sec
        sbc dn
        sta pn
        lda vcp,x
        sta cpd+1
        sta zd+1
        lda fi                  ; far column, read with the near index
        clc
        adc k
        tax
        lda vpl,x
        sec
        sbc df                  ; far index of line cD
        sec
        sbc pn
        sta cps
        lda vcp,x
        sbc #0
        sta cps+1
        lda pn                  ; far lines as near indices: ca .. cb-1
        clc
        adc df
        sta ca
        lda pn
        clc
        adc ef
        sta cb
        ldy ca                  ; copy above the near bar's rows
        cmp #BASE
        bcc :+
        lda #BASE
:       jsr copy
        ldy ca                  ; ... and below them
        cpy nbe
        bcs :+
        ldy nbe
:       lda cb
        jsr copy
        lda pn                  ; black in the gap
        clc
        adc g0
        tay
        lda pn
        clc
        adc g1
        jsr zero
        inc k
        lda k
        cmp #SEGS
        beq :+
        jmp seg
:       rts

copy:   sta ce                  ; copy rows y .. A-1
        cpy ce
        bcs cdone
cl:
cps = * + 1
        lda $ffff,y
cpd = * + 1
        sta $ff00,y
        iny
        cpy ce
        bne cl
cdone:  rts

zero:   sta ce                  ; zero rows y .. A-1
        cpy ce
        bcs zdone
        lda #0
zl:
zd = * + 1
        sta $ff00,y
        iny
        cpy ce
        bne zl
zdone:  rts

begin:  stx nr                  ; a new block: bar x
        lda vD,x
        sta cD
        lda vE,x
        sta cE
        lda #$ff
        sta fr
        rts

oswap:  ldy ord+1,x             ; swap ord x, x+1 if out of order
        lda vD,y
        ldy ord,x
        cmp vD,y
        bcs :+
        lda ord,x
        pha
        lda ord+1,x
        sta ord,x
        pla
        sta ord+1,x
:       rts
.endproc

; =============================================================================
;  Top IRQ: the badline trick; swap in the next frame if it is ready.
; =============================================================================
irqtop: sta save_a
        stx save_x
        sty save_y
        lda #$0b                ; DEN=0 across line $30
        sta VIC_CTRL1
:       lda VIC_RASTER
        cmp #$31
        bcc :-
        lda #$1b                ; DEN=1: window opens at line $33
        sta VIC_CTRL1

        lda ready
        beq noswap
        ldx #NSLOT*SEGS*2-1     ; pointers
:       lda nptr,x
        sta ptr,x
        dex
        bpl :-
        lda ncount              ; schedule
        sta scount
        ldx #NSLOT-1
:       lda nline,x
        sta sline,x
        lda nslot,x
        sta sslot,x
        lda nnrows,x
        sta snrows,x
        lda nystart,x
        sta systart,x
        dex
        bpl :-
        lda nbuf                ; build into the other buffer next
        eor #1
        sta buf
        lda #0
        sta ready
        lda #1
        sta frameflag
noswap:
        lda #0
        sta sidx
        lda scount
        beq notbar
        jsr nextbar
        jmp out
notbar: lda #DENLINE
        sta VIC_RASTER
out:    asl VIC_IRQ
        lda save_a
        ldx save_x
        ldy save_y
        rti

; set up the IRQ for schedule entry sidx
nextbar:
        ldx sidx
        lda sline,x
        sta VIC_RASTER
        lda snrows,x
        sta curn
        lda systart,x
        sta cury
        ldy sslot,x
        lda blkvlo,y
        sta curvec
        lda blkvhi,y
        sta curvec+1
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff
        rts

; =============================================================================
;  Bars: stable raster (double IRQ), then the bar's 63-cycle row loop
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
        ldx curn                ; rows
        ldy cury                ; first row (rows clipped at the top skipped)
        jmp (curvec)

; One row loop per slot (each reads its own pointers): exactly 63 cycles
;   5 x (lda (p),y 5 + sta $d021 4) = 45, iny 2, padding 11, dex 2, bne 3
        .repeat NSLOT, SL
.ident(.sprintf("blk%d", SL)):
:         .repeat SEGS, K
        lda (ptr + (SL*SEGS + K)*2),y
        sta VIC_BG
          .endrep
        iny
        bit $ea
        nop
        nop
        nop
        nop
        dex
        bne :-
        .assert >.ident(.sprintf("blk%d", SL)) = >*, error, "bar loop branch crosses a page"
        jmp bexit
        .endrep

bexit:  lda #0
        sta VIC_BG
        asl VIC_IRQ
        inc sidx
        lda sidx
        cmp scount
        bcs last
        jsr nextbar
        jmp bout
last:   lda #<irqtop
        sta $fffe
        lda #>irqtop
        sta $ffff
        lda #DENLINE
        sta VIC_RASTER
bout:   lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
.segment "TABLES"
        .include "tables.inc"   ; spectab, theta2_12, log2/atan
        .include "orbit.inc"    ; balls
        .assert <spectab = 0, error, "spectab must be page aligned"

stagger: .byte 0, FLYD/3, 2*FLYD/3

; per-segment highlight drop: segment centres at sprite x 50/112/184/256/318,
; light at 184: |a| / 32
DROP0 = 4
DROP1 = 2
DROP2 = 0
DROP3 = 2
DROP4 = 4
lev45:  .byte 0, 45, 90, 135     ; hltab: (lev*9 + spec)*5 + segment
mul5:   .byte 0, 5, 10, 15, 20, 25, 30, 35, 40

rsl:    .repeat 49, HH
        .byte <(rowstart + HH*25)
        .endrep
rsh:    .repeat 49, HH
        .byte >(rowstart + HH*25)
        .endrep
pdl:    .repeat 16, P               ; palette * 4 + level
        .byte <(pdim + P*2*BARH)
        .endrep
pdh:    .repeat 16, P
        .byte >(pdim + P*2*BARH)
        .endrep
nnml:   .byte 0
        .repeat 48, HH
        .byte <(nnmap + (HH + 1)*HH/2)
        .endrep
nnmh:   .byte 0
        .repeat 48, HH
        .byte >(nnmap + (HH + 1)*HH/2)
        .endrep
blkvlo: .lobytes blk0, blk1, blk2
blkvhi: .hibytes blk0, blk1, blk2

; =============================================================================
.segment "BSS"
tbag:   .res NTILT              ; tilt ring, oldest shown first
save_t: .res 1
dirty:  .res 2*NSLOT            ; per buffer and slot: merged into, pad stale
nbuf:   .res 1
nptr:   .res NSLOT*SEGS*2
ncount: .res 1
nline:  .res NSLOT
nslot:  .res NSLOT
nnrows: .res NSLOT
nystart: .res NSLOT
scount: .res 1
sline:  .res NSLOT
sslot:  .res NSLOT
snrows: .res NSLOT
systart: .res NSLOT
vis:    .res NSLOT              ; per slot, from doslot: shown?
vD:     .res NSLOT              ;   first line, end line, bar height
vE:     .res NSLOT
vh:     .res NSLOT
vpl:    .res NSLOT*SEGS         ;   column index of the first line, per segment
vcp:    .res NSLOT*SEGS         ;   column page, per segment
ord:    .res NSLOT              ; compose: visible slots in screen order
cnt:    .res 1
oi:     .res 1
nr:     .res 1                  ; block's (nearer) bar, merged far bar ($ff: none)
fr:     .res 1
cD:     .res 1                  ; block lines
cE:     .res 1
dn:     .res 1                  ; merge: near / far lines relative to cD
en:     .res 1
df:     .res 1
ef:     .res 1
ni:     .res 1                  ; near / far slot * 5
fi:     .res 1
nbe:    .res 1
g0:     .res 1
g1:     .res 1
k:      .res 1
pn:     .res 1
ca:     .res 1
cb:     .res 1
ce:     .res 1

.segment "RAMPS"
cols:   .res 2*NSLOT*SEGS*256   ; a page per column, 2 buffers
        .assert <cols = 0, error, "cols must be page aligned"
        .assert * <= VICBANK, error, "program runs into the VIC bank"
