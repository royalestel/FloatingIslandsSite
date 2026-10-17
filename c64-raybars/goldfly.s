; =============================================================================
;  GOLDFLY -- raster bars flying out of the distance past a central light
;  cl65 -t none -C raybars.cfg -o goldfly.prg goldfly.s
; =============================================================================
;
;  The light is a ball sprite fixed at the centre of the screen.  Three
;  bars at a time fly toward the camera from far away (depth 12 to 1.2 at
;  constant speed), alternating above / below the light.  They start as
;  thin, dim lines right by the light -- behind it -- linger there, then
;  swell and rush out through the top or bottom edge, or near-clip at the
;  camera (the middle rows go first).  Each new bar draws one of 53 tilts
;  (staircases, neighbouring segments up to 2 lines apart) that has not
;  been shown for at least 40 bars, and keeps it.  It takes the next entry
;  of two shuffled cycles (fly.inc) for its distance from the centre line
;  (15 values) and palette (gold, a second 24-colour one, and two
;  12-colour ones dithered up to 24).  Bars dim with distance and reflect
;  the light: thickest nearest it, and riding to the bar's edge once a bar
;  is nearer the camera than the light.
;
;  DISPLAY: POINTER-READ SPEEDCODE
;  Each bar's display code is a loop over its rows:
;       5 x (lda (pK),y / sta $d021)  =  5 x 9 cycles  (72-pixel segments)
;  pK points into segment K's colour column for this bar, offset by the
;  segment's tilt.  The main loop only builds the columns and the
;  pointers.  The bars live inside the display window (opened without
;  badlines, see goldlight.s), so only $d021 is written; the side borders
;  stay black.  Each column is one page, so (pK),y never crosses a page.
;
;  THE LIGHT'S LINES
;  On the 21 lines where the light's sprite is fetched the VIC halts the
;  CPU for cycles 55-59, so a bar row there must be STEAL cycles shorter.
;  Each slot has three loops -- normal rows above the light, rows on its
;  lines, normal rows below -- chained by patched jumps with padded
;  entries, and irq2's stabilising delay is shortened when its line is one
;  of them.  STEAL (5: the loop's tail only reads) and BAND0/1 need
;  checking in VICE; the simulator can't emulate sprite DMA.  The sprite
;  covers bars behind it; bars nearer than the light keep off its lines.
;
;  FRAME PIPELINE
;  The main loop builds frame N+1 (columns into the back buffer, pointers
;  and the IRQ schedule into the other half) while frame N is shown.  The
;  top IRQ swaps them in when ready.
;
;  OVERLAPS
;  Bars closer than SEP lines can't each have an IRQ (above and below the
;  light they meet at the centre; on one side they can cross).  They share
;  one block, drawn by the nearest bar: its column is blacked outside its
;  own lines and the others' bar rows are copied in around its own rows,
;  farthest first -- so nearer bars cover farther ones.
; =============================================================================

        .setcpu "6502"


NSLOT     = 3           ; bars in flight
SEGS      = 5
PAD       = 8           ; black rows above / below a bar's rows (>= max slant)
BASE      = 96          ; a bar's first row in its column; the rest of the
                        ; page is room for a merged bar above or below
BARH      = 24          ; source rows per palette
CENTRE    = 150         ; centre line of the screen: the light
WTOP      = 62          ; bars are drawn on lines WTOP..WBOT
WBOT      = 250
DENLINE   = 44
HTUNE     = 0
STEAL     = 5           ; cycles the light's sprite DMA takes from a bar row
BAND0     = SPRY        ; lines with the light's sprite DMA (its display
BAND1     = SPRY + 21   ;   lines are one later)
SEP       = 6           ; bars closer than this (lines) share one IRQ block
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
sbase:   .res 1                 ; schedule half being shown
curvec:  .res 2                 ; loop entry of the next bar
lp:      .res 2                 ; its slot's loops (nextbar patches them)
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
pnp:     .res 2                 ; merge: nearest / farther column pointers
pfp:     .res 2
fcl:     .res 1                 ; near-clip rows
bsx:     .res 1                 ; buffer * NSLOT + slot
ce:      .res 1                 ; merge: copy / black end
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
        .assert * = 2062, error, "SYS 2061 must land on start"
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
        jsr respawn             ; (marks its pads stale: full first build)
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
        lda #1                  ; its columns hold the last flight's rows
        sta dirty,x
        sta dirty+NSLOT,x
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
        sta .ident(.sprintf("zm%d", K))+1
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
        lda fclip,y             ; near clip: rows cut each side of the middle
        sta fcl
        cmp #255
        bne :+
        jmp hidden              ; last frame: gone
:
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

        ; ---- 8 black rows before the bar: only stale after a merge or a
        ; respawn ---------------------------------------------------------
        lda buf
        beq :+
        lda #NSLOT
:       clc
        adc s
        sta bsx                 ; this buffer's copy of the slot
        tax
        lda dirty,x
        beq clean
        lda #0
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
        ; ---- 8 black rows after the bar.  Within a flight a bar only
        ; grows, so only rows not black last time (in this buffer) need it:
        ; from max(h, last h + 8); all 8 after a merge or a respawn.
        ldx bsx
        lda dirty,x
        bne zfull
        lda lasth,x
        clc
        adc #PAD
        cmp h
        bcc zfull
        tay
        jmp zgo
zfull:  ldy h
zgo:    lda h
        clc
        adc #PAD
        sta rend
        cpy rend
        bcs zdone
        lda #0
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
        cpy rend
        bne z8
zdone:  lda h
        sta lasth,x
        lda #0
        sta dirty,x

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

        ; ---- near clip: the middle rows go first ---------------------------
        lda fcl
        beq noclip
        lda h
        lsr
        sta acc
        sec
        sbc fcl
        tay                     ; rows h/2 - c .. h/2 + c - 1
        lda acc
        clc
        adc fcl
        sta rend
        lda #0
clipl:
zm0 = * + 1
        sta $ff00 + BASE,y
zm1 = * + 1
        sta $ff00 + BASE,y
zm2 = * + 1
        sta $ff00 + BASE,y
zm3 = * + 1
        sta $ff00 + BASE,y
zm4 = * + 1
        sta $ff00 + BASE,y
        iny
        cpy rend
        bne clipl
noclip:

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
;  in screen order.  Bars closer than SEP lines can't each have an IRQ: they
;  share a block, drawn by the nearest one (furthest along its flight).  Its
;  block grows to cover them all; its column is blacked outside its own
;  lines, then the others' bar rows are copied in around its own rows,
;  farthest first -- so nearer bars cover farther ones.
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
        lda buf                 ; schedule half to write
        beq :+
        lda #NSLOT
:       sta wb
        lda #0
        sta ncount
        cpx #2                  ; sort by first line (3-element network)
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
sorted: lda #0
        sta oi
blk:    ldx oi                  ; a new block
        cpx cnt
        bcc :+
        rts
:       ldy ord,x
        sty mem
        lda #1
        sta mcnt
        lda vD,y
        sta cD
        lda vE,y
        sta cE
        inx
grow:   cpx cnt                 ; take in the bars too close below it
        bcs bdone
        ldy ord,x
        lda cE
        clc
        adc #::SEP
        bcs join
        cmp vD,y
        bcc bdone
        beq bdone
join:   tya
        ldy mcnt
        sta mem,y
        inc mcnt
        tay
        lda vE,y
        cmp cE
        bcc :+
        sta cE
:       inx
        jmp grow
bdone:  stx oi
        jsr emit
        jmp blk

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

mswap:  ldy mem+1,x             ; swap mem x, x+1 if x+1 is further along
        lda st,y
        ldy mem,x
        cmp st,y
        bcc :+
        lda mem,x
        pha
        lda mem+1,x
        sta mem,x
        pla
        sta mem+1,x
:       rts

; emit: schedule block mem[0..mcnt) on lines cD .. cE-1
emit:   lda mcnt                ; nearest first
        cmp #2
        bcc single
        ldx #0
        jsr mswap
        lda mcnt
        cmp #3
        bcc single
        ldx #1
        jsr mswap
        ldx #0
        jsr mswap
single: ldx mem                 ; the nearest draws the block
        stx nr
        lda vD,x
        sec
        sbc cD
        sta dn                  ; its lines, relative to cD: dn .. en-1
        lda vE,x
        sec
        sbc cD
        sta en
        lda vh,x
        sta hn
        lda cE
        sec
        sbc cD
        sta span

        ; ---- schedule entry: line, slot, loop entry, chunks ---------------
        lda ncount
        clc
        adc wb
        tax
        inc ncount
        lda cD
        sec
        sbc #2
        sta sline,x
        ldy nr
        tya
        sta soff,x
        lda #::BAND0            ; band rows: rb0 .. rb1-1 (clamped to 0..span)
        jsr bandrow
        sta rb0
        lda #::BAND1
        jsr bandrow
        sta rb1
        lda span                ; defaults: every chunk runs to the end,
        sta sc1,x               ; every jump exits
        sta sc2,x
        sta sc3,x
        lda #<bexit
        sta sj1lo,x
        sta sj2lo,x
        lda #>bexit
        sta sj1hi,x
        sta sj2hi,x
        lda rb0
        cmp rb1
        bne band
        lda n2lo,y              ; no light rows: n2 only
        sta sentlo,x
        lda n2hi,y
        sta senthi,x
        jmp chunks
band:   lda rb1                 ; light rows end at rb1, then n2 (if any)
        sta sc2,x
        cmp span
        bcs :+
        lda n2elo,y
        sta sj2lo,x
        lda n2ehi,y
        sta sj2hi,x
:       lda rb0
        bne above
        lda blo,y               ; starts on the light's lines
        sta sentlo,x
        lda bhi,y
        sta senthi,x
        jmp chunks
above:  sta sc1,x               ; n1 up to the light's lines
        lda n1lo,y
        sta sentlo,x
        lda n1hi,y
        sta senthi,x
        lda belo,y
        sta sj1lo,x
        lda behi,y
        sta sj1hi,x
chunks: lda #8                  ; irq2's delay: one turn less if its line
        ldy cD                  ; (cD - 1) has the sprite's DMA
        dey
        cpy #::BAND0
        bcc :+
        cpy #::BAND1
        bcs :+
        lda #7
:       sta sdel,x

        ; ---- the nearest bar's pointers: pl_K - dn ------------------------
        lda nr
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
        lda mcnt
        cmp #2
        bcs merge
        rts

merge:  lda buf                 ; its top pad needs re-blacking next time
        beq :+
        lda #NSLOT
:       clc
        adc nr
        tax
        lda #1
        sta dirty,x
        lda #0
        sta k
seg:    lda ni                  ; nearest bar's column: index of line cD
        clc
        adc k
        tax
        lda vpl,x
        sec
        sbc dn
        sta pnp
        lda vcp,x
        sta pnp+1
        lda #::BASE             ; its bar rows: y = nlo .. nhi-1
        sec
        sbc pnp
        bcs :+
        lda #0
:       sta nlo
        lda #::BASE
        clc
        adc hn
        sec
        sbc pnp
        bcs :+
        lda #0
:       sta nhi
        ldy #0                  ; black outside its own lines
        lda dn
        jsr zero
        ldy en
        lda span
        jsr zero
        ldx mcnt                ; the others, farthest first
        dex
        stx fj
far:    ldy mem,x
        lda vD,y                ; its lines: flo .. fhi-1
        sec
        sbc cD
        sta flo
        lda vE,y
        sec
        sbc cD
        sta fhi
        lda vh,y
        sta hf
        sty acc                 ; its column: index of line cD
        tya
        asl
        asl
        adc acc
        adc k
        tax
        lda vpl,x
        sec
        sbc flo
        sta pfp
        lda vcp,x
        sta pfp+1
        lda #::BASE             ; its bar rows within its lines: lo .. hi-1
        sec
        sbc pfp
        bcs :+
        lda #0
:       cmp flo
        bcs :+
        lda flo
:       sta lo
        lda #::BASE
        clc
        adc hf
        sec
        sbc pfp
        bcs :+
        lda #0
:       cmp fhi
        bcc :+
        lda fhi
:       sta hi
        ldy lo                  ; copy, skipping the nearest bar's rows
        lda hi
        cmp nlo
        bcc :+
        lda nlo
:       jsr copy
        ldy lo
        cpy nhi
        bcs :+
        ldy nhi
:       lda hi
        jsr copy
        dec fj
        ldx fj
        beq :+
        jmp far
:       inc k
        lda k
        cmp #SEGS
        beq :+
        jmp seg
:       rts

copy:   sta ce                  ; rows y .. A-1, two at a time
        cpy ce
        bcs cdone
        tya                     ; odd count?
        eor ce
        lsr
        bcc cl
        lda (pfp),y             ; odd: one first
        sta (pnp),y
        iny
        cpy ce
        beq cdone
cl:     lda (pfp),y
        sta (pnp),y
        iny
        lda (pfp),y
        sta (pnp),y
        iny
        cpy ce
        bne cl
cdone:  rts

zero:   sta ce                  ; black rows y .. A-1, two at a time
        cpy ce
        bcs zdone
        tya                     ; odd count?
        eor ce
        lsr
        lda #0
        bcc zl
        sta (pnp),y             ; odd: one first
        iny
        cpy ce
        beq zdone
zl:     sta (pnp),y
        iny
        sta (pnp),y
        iny
        cpy ce
        bne zl
zdone:  rts

; A = the row of the block on line A (0 .. span)
bandrow:
        sec
        sbc cD
        bcs :+
        lda #0
:       cmp span
        bcc :+
        lda span
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
        lda ncount              ; schedule: the half just built
        sta scount
        lda nbuf
        beq :+
        lda #NSLOT
:       sta sbase
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

; set up the IRQ for schedule entry sidx: its line, its loop entry, the
; chunk ends and chunk jumps in its slot's loops, irq2's delay
nextbar:
        lda sidx
        clc
        adc sbase
        tax
        lda sline,x
        sta VIC_RASTER
        lda sentlo,x
        sta curvec
        lda senthi,x
        sta curvec+1
        lda sdel,x
        sta dly_op
        ldy soff,x              ; the slot's loops
        lda n1lo,y
        sta lp
        lda n1hi,y
        sta lp+1
        ldy #n1c_0 - n1_0
        lda sc1,x
        sta (lp),y
        ldy #bc_0 - n1_0
        lda sc2,x
        sta (lp),y
        ldy #n2c_0 - n1_0
        lda sc3,x
        sta (lp),y
        ldy #n1j_0 - n1_0
        lda sj1lo,x
        sta (lp),y
        iny
        lda sj1hi,x
        sta (lp),y
        ldy #bj_0 - n1_0
        lda sj2lo,x
        sta (lp),y
        iny
        lda sj2hi,x
        sta (lp),y
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff
        rts

; =============================================================================
;  Bars: stable raster (double IRQ), then the bar's row loops
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

; On a line where the light's sprite is fetched (BAND0..BAND1-1) the VIC
; halts the CPU for cycles 55-59: 5 cycles in the middle of this delay
; (all reads), so the delay loop runs one turn less (dly_op = 7).
irq2:   txs
dly_op = * + 1
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
        ldy #0                  ; first row
        nop
        nop
        jmp (curvec)

; N cycles of padding (N = 0 or N >= 2)
.macro fill N
  .assert (N) = 0 .or (N) >= 2, error, "can't pad 1 cycle"
  .if (N) .mod 2 = 1
        bit $ea
    .repeat ((N) - 3)/2
        nop
    .endrep
  .else
    .repeat (N)/2
        nop
    .endrep
  .endif
.endmacro

; one row: 5 x (lda (pK),y / sta $d021) = 45 cycles, iny: 47
.macro row SL
  .repeat SEGS, K
        lda (ptr + (SL*SEGS + K)*2),y
        sta VIC_BG
  .endrep
        iny
.endmacro

; Three loops per slot, rows in screen order: normal rows above the light
; (n1), rows on the light's DMA lines (b), normal rows below it (n2).  A
; normal row is 63 cycles; a light row 63 - STEAL, the VIC taking the rest
; in the loop's tail (reads only, so cycles 55-59 of the line all go).
; Each loop ends when y reaches its chunk end (n1c / bc / n2c), then
; jumps on (n1j / bj), arriving 55 cycles into the row: the next loop's
; entry pads the row out (be: 8 cycles, n2e: 8 - STEAL).  All patched by
; nextbar; the slots' loops are laid out alike, LOOPSZ bytes apart.
        .repeat NSLOT, SL
.ident(.sprintf("n1_%d", SL)):
:       row SL                  ; 47
.ident(.sprintf("n1c_%d", SL)) = * + 1
        cpy #0                  ; 49
        beq :+                  ; 51 (52 taken)
        fill 9                  ; 60
        jmp :-                  ; 63
:
.ident(.sprintf("n1j_%d", SL)) = * + 1
        jmp bexit               ; 55: band entry or bexit
.ident(.sprintf("be_%d", SL)):
        fill 8                  ; the last n1 row: 63
.ident(.sprintf("b_%d", SL)):
:       row SL
.ident(.sprintf("bc_%d", SL)) = * + 1
        cpy #0
        beq :+
        fill 9 - STEAL          ; 63 - STEAL
        jmp :-
:
.ident(.sprintf("bj_%d", SL)) = * + 1
        jmp bexit               ; 55: n2 entry or bexit
.ident(.sprintf("n2e_%d", SL)):
        fill 8 - STEAL          ; the last band row: 63 - STEAL
.ident(.sprintf("n2_%d", SL)):
:       row SL
.ident(.sprintf("n2c_%d", SL)) = * + 1
        cpy #0
        beq :+
        fill 9
        jmp :-
:       jmp bexit
        .endrep
LOOPSZ = n1_1 - n1_0
        .assert n1_2 - n1_1 = LOOPSZ, error, "slot loops must be laid out alike"

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
        .include "fly.inc"      ; FLYD, flight tables, spawn cycles, dimmed palettes
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
; per slot: its loops' entries
n1lo:   .lobytes n1_0, n1_1, n1_2
n1hi:   .hibytes n1_0, n1_1, n1_2
blo:    .lobytes b_0, b_1, b_2
bhi:    .hibytes b_0, b_1, b_2
belo:   .lobytes be_0, be_1, be_2
behi:   .hibytes be_0, be_1, be_2
n2lo:   .lobytes n2_0, n2_1, n2_2
n2hi:   .hibytes n2_0, n2_1, n2_2
n2elo:  .lobytes n2e_0, n2e_1, n2e_2
n2ehi:  .hibytes n2e_0, n2e_1, n2e_2

; =============================================================================
.segment "BSS"
tbag:   .res NTILT              ; tilt ring, oldest shown first
save_t: .res 1
dirty:  .res 2*NSLOT            ; per buffer and slot: pads stale (merge, respawn)
lasth:  .res 2*NSLOT            ;   bar height when last built
nbuf:   .res 1
nptr:   .res NSLOT*SEGS*2
ncount: .res 1
; IRQ schedule, two halves (built / shown), per entry: raster line, slot's
; slot, loop entry, chunk ends, chunk jumps, irq2's delay
sline:  .res 2*NSLOT
soff:   .res 2*NSLOT
sentlo: .res 2*NSLOT
senthi: .res 2*NSLOT
sc1:    .res 2*NSLOT
sc2:    .res 2*NSLOT
sc3:    .res 2*NSLOT
sj1lo:  .res 2*NSLOT
sj1hi:  .res 2*NSLOT
sj2lo:  .res 2*NSLOT
sj2hi:  .res 2*NSLOT
sdel:   .res 2*NSLOT
scount: .res 1
vis:    .res NSLOT              ; per slot, from doslot: shown?
vD:     .res NSLOT              ;   first line, end line, bar height
vE:     .res NSLOT
vh:     .res NSLOT
vpl:    .res NSLOT*SEGS         ;   column index of the first line, per segment
vcp:    .res NSLOT*SEGS         ;   column page, per segment
ord:    .res NSLOT              ; compose: visible slots in screen order
cnt:    .res 1
oi:     .res 1
wb:     .res 1                  ; schedule half being written
mem:    .res NSLOT              ; block's bars, nearest first
mcnt:   .res 1
nr:     .res 1                  ; the nearest
cD:     .res 1                  ; block lines
cE:     .res 1
span:   .res 1
dn:     .res 1                  ; nearest bar's lines relative to cD
en:     .res 1
hn:     .res 1
ni:     .res 1                  ; nearest slot * 5
rb0:    .res 1                  ; block rows on the light's lines
rb1:    .res 1
k:      .res 1
nlo:    .res 1                  ; merge: nearest bar's rows, y-space
nhi:    .res 1
fj:     .res 1                  ; a farther bar: its lines, height, rows
flo:    .res 1
fhi:    .res 1
hf:     .res 1
lo:     .res 1
hi:     .res 1

.segment "RAMPS"
cols:   .res 2*NSLOT*SEGS*256   ; a page per column, 2 buffers
        .assert <cols = 0, error, "cols must be page aligned"
        .assert * <= VICBANK, error, "program runs into the VIC bank"
