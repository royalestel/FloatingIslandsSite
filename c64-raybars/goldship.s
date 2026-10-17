; =============================================================================
;  GOLDSHIP -- fly a ship through a forest of ray-traced raster bars
;  cl65 -t none -C raybars.cfg -o goldship.prg goldship.s
; =============================================================================
;
;  The ship is a multicolour sprite seen from behind, fixed at the centre of
;  the screen, with the light on its nose.  Parallel bars come at it out of
;  the distance, three at a time: each new one appears near the screen
;  centre (some at the ship's height, most off it) and grows as it
;  approaches.  Joystick in port 2:
;  up / down pitch the ship (it climbs or dives, so the bars move down or
;  up), left / right roll it (the bars tilt the other way, up to 3 lines per
;  segment).  The ship's sprite leans in the 8 directions while pushed.
;  When a bar ahead is on a collision course (it covers the screen centre,
;  which in perspective means it is within half its thickness of the ship's
;  height, at any distance) the ship's palette turns from purple / light
;  blue / white to red / orange / yellow.  A bar that reaches the ship's
;  depth on a collision course flashes the border red.
;
;  Built on goldfly.s: the same bars, highlights, merging and the loops for
;  the sprite's DMA lines (see there).
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

        .include "fly.inc"      ; FLYD, flight tables, dimmed palettes
        .include "ship.inc"     ; ship sprites, roll tilts, spawn heights

NSLOT     = 3           ; bars in flight
SEGS      = 5
NCOL      = 3           ; columns per bar: centre, middle, outer.  All bars
                        ; share the tilt and the highlight is symmetric, so
                        ; segments 0 and 4 read one column, 1 and 3 another
                        ; (each at its own tilt offset)
PAD       = 12          ; black rows above / below a bar's rows (>= max slant)
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
PEXP      = VICBANK + $0800 ; pre-expanded colour lists (RAM the VIC doesn't use)
PCLIP     = PEXP + 16*PXBLK ;   and the near clip's
        .assert PCLIP + 16*CLIPH <= IDLEBYTE, error, "colour lists reach the idle byte"
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
CIA1_PRA   = $dc00
HITR      = 24          ; |height| below this: on a collision course
VMAX      = 64          ; climb speed: 1/64 units per frame
VACC      = 3
HITLEN    = 25          ; frames the border flashes after a hit
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
shipf:   .res 1                 ; ship height: fraction, integer (16 bits)
shipy:   .res 2
vy:      .res 1                 ; climb speed (signed, 1/64 units per frame)
roll:    .res 1                 ; -8 (left) .. 8 (right)
rolli:   .res 1                 ; roll + 8
joy:     .res 1                 ; joystick: 1 up, 2 down, 4 left, 8 right
fcount:  .res 1
red:     .res 1                 ; a bar ahead is on a collision course
hitfl:   .res 1                 ; border flash frames left
yl:      .res 1                 ; |height| of the bar being built
yh:      .res 1
t0:      .res 2
yi:      .res 1                 ; spawn cycle positions: height,
pali:    .res 1                 ;   palette
sidx:    .res 1                 ; schedule entry being shown
sbase:   .res 1                 ; schedule half being shown
curvec:  .res 2                 ; loop entry of the next bar
lp:      .res 2                 ; its slot's loops (nextbar patches them)
st:      .res NSLOT             ; per slot: flight time
spal:    .res NSLOT             ;           palette
swl:     .res NSLOT             ;           height (16 bits)
swh:     .res NSLOT
sY:      .res NSLOT             ;           |height - ship's|, this frame
sydy:    .res NSLOT             ;           its dy toward the light
sside:   .res NSLOT             ;           0 = above the ship, 1 = below
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
pxs:     .res 2                 ; preexp: palette-level colours
zp5:     .res 2*SEGS            ; merge: the nearest bar's five columns from
np:      .res 2*SEGS            ;   line cD / from their start, the farther
fp:      .res 2*SEGS            ;   bar's (offset to match)
bsx:     .res 1                 ; buffer * NSLOT + slot
phi:     .res 1                 ; spec offset (spe_op)
llo:     .res 1                 ; first lit row
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
        ldx #$fe                ; zero page $02-$ff
@zp:    sta $01,x
        dex
        bne @zp
        sta ptr                 ; clear all columns (2 buffers)
        tay
        lda #>cols
        sta ptr+1
        ldx #2*NSLOT*NCOL
        tya
@col:   sta (ptr),y
        iny
        bne @col
        inc ptr+1
        dex
        bne @col
        sta $dc02               ; CIA1 port A all inputs: the joystick only
        jsr preexp
        lda #8                  ; level
        sta rolli
        ldx #NSLOT-1            ; stagger the bars along their flight
@stg:   lda stagger,x
        sta st,x
        jsr respawn             ; (marks its pads stale: full first build)
        dex
        bpl @stg

        ldx #0                  ; the ship's 9 frames
@spr:   .repeat 3, P
        lda shipspr + P*256,x
        sta SPRBUF + P*256,x
        .endrep
        inx
        bne @spr
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
;  preexp: at start-up, every palette-level's colours expanded to every bar
;  height HMIN..HMAX (nnmap: source row and even / odd line per row), one
;  after the other from PEXP; then the near clip's lists (clipmap) at PCLIP.
; -----------------------------------------------------------------------------
.proc preexp
        lda #<PEXP
        sta t0
        lda #>PEXP
        sta t0+1
        lda #0
        sta acc                 ; palette * 4 + level
pl:     ldx acc
        lda pdl,x
        sta pxs
        lda pdh,x
        sta pxs+1
        lda #HMIN
        sta hh
hl:     ldx hh
        lda nnml,x
        sta rsp
        lda nnmh,x
        sta rsp+1
        jsr one
        inc hh
        lda hh
        cmp #HMAX + 1
        bne hl
        inc acc
        lda acc
        cmp #16
        bne pl
        lda #0                  ; the near clip's: same, with clipmap
        sta acc
cl:     ldx acc
        lda pdl,x
        sta pxs
        lda pdh,x
        sta pxs+1
        lda #<clipmap
        sta rsp
        lda #>clipmap
        sta rsp+1
        lda #CLIPH
        sta hh
        jsr one
        inc acc
        lda acc
        cmp #16
        bne cl
        rts
one:    ldy #0                  ; hh rows to t0, then t0 += hh
:       lda (rsp),y
        sty si
        tay
        lda (pxs),y
        ldy si
        sta (t0),y
        iny
        cpy hh
        bne :-
        tya
        clc
        adc t0
        sta t0
        bcc :+
        inc t0+1
:       rts
.endproc

; -----------------------------------------------------------------------------
;  respawn slot x: far away, at the ship's height plus the next spawn
;  offset (some at the centre, most off it), with the next palette.
; -----------------------------------------------------------------------------
.proc respawn
        ldy yi
        lda yspawnl,y
        clc
        adc shipy
        sta swl,x
        lda yspawnh,y
        adc shipy+1
        sta swh,x
        iny
        cpy #NYSPAWN
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
        lda #1                  ; its columns hold the last flight's rows
        sta dirty,x
        sta dirty+NSLOT,x
        rts
.endproc

; -----------------------------------------------------------------------------
;  pilot: once a frame -- the joystick, the ship's height and roll, its
;  sprite frame and palette, the border flash.
; -----------------------------------------------------------------------------
.proc pilot
        lda CIA1_PRA            ; port 2, active low
        eor #$ff
        and #$0f
        sta joy
        ; ---- pitch: the climb speed eases toward +-VMAX, or back to 0
        lsr                     ; up?
        bcc notup
        lda vy
        clc
        adc #VACC
        cmp #VMAX + 1
        bmi setv
        lda #VMAX
        jmp setv
notup:  lsr                     ; down?
        bcc coast
        lda vy
        sec
        sbc #VACC
        cmp #<(-VMAX)
        bpl setv
        bcs setv
        lda #<(-VMAX)
        jmp setv
coast:  lda vy
        beq setv
        bmi cup
        sec
        sbc #VACC
        bpl setv
        lda #0
        jmp setv
cup:    clc
        adc #VACC
        bmi setv
        lda #0
setv:   sta vy
        ; ---- height += vy / 64 (16.8 fixed point)
        sta t0
        ldx #0
        and #$80
        beq :+
        dex
:       stx t0+1
        asl t0
        rol t0+1
        asl t0
        rol t0+1                ; vy * 4 in 1/256 units
        lda shipf
        clc
        adc t0
        sta shipf
        lda shipy
        adc t0+1
        sta shipy
        txa
        adc shipy+1
        sta shipy+1
        ; ---- roll: one step every other frame toward the stick
        inc fcount
        lda fcount
        lsr
        bcs rdone
        lda joy
        and #4
        beq notl
        lda roll
        cmp #<(-8)
        beq rdone
        dec roll
        jmp rdone
notl:   lda joy
        and #8
        beq level
        lda roll
        cmp #8
        beq rdone
        inc roll
        jmp rdone
level:  lda roll
        beq rdone
        bmi :+
        dec roll
        jmp rdone
:       inc roll
rdone:  lda roll
        clc
        adc #8
        sta rolli
        ; ---- the ship leans with the stick
        ldx joy
        lda joyframe,x
        clc
        adc #<((SPRBUF - VICBANK)/64)
        sta SPRPTR
        ; ---- its palette: red / orange / yellow on a collision course
        ldx #0
        lda red
        beq :+
        ldx #3
:       lda shippal,x
        sta VIC_SPRMC0
        lda shippal+1,x
        sta VIC_SPR0C
        lda shippal+2,x
        sta VIC_SPRMC1
        lda #0
        sta red                 ; (this build finds it again)
        ; ---- border flash after a hit
        ldx #0
        lda hitfl
        beq :+
        dec hitfl
        ldx #2
:       stx VIC_BORDER
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
;  build: the next frame -- the ship, every bar's columns, pointers, and the
;  schedule
; =============================================================================
.proc build
        jsr pilot
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
        ; ---- height relative to the ship: side and |y|; collision course ----
        lda swl,x
        sec
        sbc shipy
        sta yl
        lda swh,x
        sbc shipy+1
        sta yh
        ldy #0                  ; side 0: above the ship
        bit yh
        bpl :+
        lda #0
        sec
        sbc yl
        sta yl
        lda #0
        sbc yh
        sta yh
        iny
:       tya
        sta sside,x
        lda yl
        sta sY,x
        lda yh                  ; |y| >= HITR: clear of the ship
        bne clear
        lda yl
        cmp #HITR
        bcs clear
        lda st,x
        cmp #NEARZ3
        bcc ahead
        bne clear               ; already past the ship
        lda #HITLEN             ; just reaching it: hit
        sta hitfl
        bne clear
ahead:  lda #1                  ; still ahead of it: collision course
        sta red
clear:

        ; ---- this slot's columns in the back buffer: patch the stores -------
        ; column page = >cols + buf*9 + s*3 + c (c: 0 centre, 1 middle,
        ; 2 outer); segment k reads column CLS(k)
        lda buf
        beq :+
        lda #9
:       sta acc
        txa
        asl
        adc s                   ; s*3
        adc acc
        adc #>cols
        .repeat ::NCOL, C
        sta .ident(.sprintf("ex%d", C))+1
        sta .ident(.sprintf("ov%d", C))+1
        sta .ident(.sprintf("zc%d", C))+1
        adc #1
        .endrep
        sbc #::NCOL - 1         ; (carry clear: back to the centre column)
        sta acc
        txa                     ; vcp per segment, for compose
        asl
        asl
        adc s
        tay
        lda acc
        .repeat ::SEGS, K
        .if K = 0 .or K = 4
        clc
        adc #2
        sta vcp+K,y
        sec
        sbc #2
        .elseif K = 1 .or K = 3
        clc
        adc #1
        sta vcp+K,y
        sec
        sbc #1
        .else
        sta vcp+K,y
        .endif
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
        lda yh                  ; 256+ units away: out of sight
        beq :+
        jmp hidden
:       lda finvz,y             ; offset from the centre line = Y / Z
        sta acc
        lda sY,x
        jsr mulhi
        sta off
        ldx s                   ; dy for the light: |y| / 10
        ldy sY,x
        lda ydiv10,y
        sta sydy,x

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
lower:  ; below the ship: block top = CENTRE + off - hh
        lda off
        clc
        adc #CENTRE
        bcs hidden              ; past line 255
        sec
        sbc hh
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
        ldy rolli               ; all bars parallel: the roll's tilt
        .repeat ::SEGS, K
        lda .ident(.sprintf("rtilt%d", K)),y
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
        sta phi

        ; ---- its colours, pre-expanded for this palette, level and height --
        ldx s
        lda spal,x
        asl
        asl
        adc lev
        tax                     ; palette * 4 + level
        lda fcl
        beq :+
        lda pclbl,x             ; near clip: the cut list
        sta exs_op
        lda pclbh,x
        sta exs_op+1
        jmp :++
:       ldy h
        lda pxbl,x
        clc
        adc hoffl,y
        sta exs_op
        lda pxbh,x
        adc hoffh,y
        sta exs_op+1
:

        ; ---- PAD black rows before the bar: only stale after a merge or a
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
        lda s                   ; patch the stores: this slot's columns
        asl
        asl
        adc s
        tay
        lda vcp+2,y             ; (segments 2, 1, 0: columns 0, 1, 2)
        sta zt0+1
        lda vcp+1,y
        sta zt1+1
        lda vcp+0,y
        sta zt2+1
        lda #0
        ldx #BASE - PAD
ztop:
zt0 = * + 1
        sta $ff00,x
zt1 = * + 1
        sta $ff00,x
zt2 = * + 1
        sta $ff00,x
        inx
        cpx #BASE
        bne ztop
clean:

        ; ---- the bar's rows into its 3 columns: a straight copy -----------
        ldy h
        dey
exl:
exs_op = * + 1
        lda $ffff,y
ex0 = * + 1
        sta $ff00 + BASE,y
ex1 = * + 1
        sta $ff00 + BASE,y
ex2 = * + 1
        sta $ff00 + BASE,y
        dey
        bpl exl
        ; ---- PAD black rows after the bar.  Within a flight a bar only
        ; grows, so only rows not black last time (in this buffer) need it:
        ; from max(h, last h + PAD); all of them after a merge or a respawn.
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
        iny
        cpy rend
        bne z8
zdone:  lda h
        sta lasth,x
        lda #0
        sta dirty,x

        ; ---- the highlight, per segment ------------------------------------
        ; Only lit source rows are visited (litlo/lithi: one run per light
        ; angle); rowstart gives the expanded rows
        ; each one covers.  Colour per segment: hlcol[min(e, 2) + 3 - level],
        ; e = how far the row's spec level exceeds the segment's threshold
        ; (thickest nearest the light, never darker than medium grey).
        lda fcl                 ; (none while near-clipping)
        beq :+
        jmp ovdone
:       ldx lev                 ; highlight table base for this distance
        lda lev45,x
        sta lb
        ldx h
        lda rsl,x
        sta rsp
        lda rsh,x
        sta rsp+1
        ldx phi                 ; only the run of lit rows
        lda litlo,x
        sta llo
        ldy lithi,x
        beq ovdone
        dey
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
rowl:   hlrow 2, ov0                ; (segment 2's colour: the centre column)
        hlrow 1, ov1
        hlrow 0, ov2
        inx
        cpx rend
        bne rowl
ovnext: ldy si
ovskip: cpy llo
        beq ovdone
        dey
        jmp ovi
ovdone:


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
        ldy ni                  ; the nearest bar's columns from line cD
        .repeat ::SEGS, K
        lda vpl+K,y
        sec
        sbc dn
        sta zp5 + K*2
        lda vcp+K,y
        sta zp5 + K*2 + 1
        .endrep
        lda zp5
        sta pnl                 ; (segment 0's index of line cD)
        ldy #0                  ; black outside its own lines, all five
        lda dn                  ; columns at once (all bars share the tilt,
        jsr zero5               ; so the same lines in each)
        ldy en
        lda span
        jsr zero5

        ldy ni                  ; copy targets: the nearest bar's columns
        lda #0                  ; from their start, y = column index
        .repeat ::NCOL, C
        sta np + C*2
        .endrep
        .repeat ::NCOL, C
        lda vcp+2-C,y           ; (segments 2, 1, 0: columns 0, 1, 2)
        sta np + C*2 + 1
        .endrep
        lda #::BASE             ; its rows: BASE .. nbe-1
        clc
        adc hn
        sta nbe
        ldx mcnt                ; the others, farthest first
        dex
        stx fj
far:    ldy mem,x
        ; All bars share the tilt, so a farther bar's rows sit at the same
        ; offset d from the nearest bar's in every column: copy them all
        ; five at a time, indexed by the nearest bar's column index.
        lda vD,y
        sec
        sbc cD
        sta flo
        lda vh,y
        sta hf
        sty acc
        tya
        asl
        asl
        adc acc
        tax                     ; its slot * 5
        lda vpl,x               ; its column index of line cD (segment 0)
        sec
        sbc flo
        sec
        sbc pnl                 ; minus the nearest bar's: d (16 bits)
        sta dlo
        lda #0
        sbc #0
        sta dhi
        .repeat ::NCOL, C       ; read pointers: its columns + d
        lda dlo
        sta fp + C*2
        lda vcp+2-C,x
        clc
        adc dhi
        sta fp + C*2 + 1
        .endrep
        lda #::BASE             ; its rows: BASE - d .. + its height - 1
        sec
        sbc dlo
        sta lo
        lda #0
        sbc dhi
        bmi neg
        bne nextf               ; past the column: none shown
        lda lo
        clc
        adc hf
        bcc :+
        lda #255
:       sta hi
        jmp rows
neg:    sta acc                 ; starts before the column: from 0
        lda lo
        clc
        adc hf
        tax
        lda acc
        adc #0
        bmi nextf               ; ends before it too
        bne nextf
        stx hi
        lda #0
        sta lo
rows:   ldy lo                  ; copy, skipping the nearest bar's rows
        lda hi
        cmp #::BASE
        bcc :+
        lda #::BASE
:       jsr copy5
        ldy lo
        cpy nbe
        bcs :+
        ldy nbe
:       lda hi
        jsr copy5
nextf:  dec fj
        ldx fj
        beq :+
        jmp far
:       rts

copy5:  sta ce                  ; rows y .. A-1 in all three columns
        cpy ce
        bcs c5done
c5:     .repeat ::NCOL, C
        lda (fp + C*2),y
        sta (np + C*2),y
        .endrep
        iny
        cpy ce
        bne c5
c5done: rts

zero5:  sta ce                  ; black rows y .. A-1 in all five columns
        cpy ce
        bcs z5done
        lda #0
z5:     sta (zp5),y
        sta (zp5+2),y
        sta (zp5+4),y
        sta (zp5+6),y
        sta (zp5+8),y
        iny
        cpy ce
        bne z5
z5done: rts



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
shippal: .byte 4, 14, 1, 2, 8, 7   ; hull, trim, light: normal, collision
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
pxbl:   .repeat 16, P               ; pre-expanded lists, per palette * 4 + level
        .byte <(PEXP + P*PXBLK)
        .endrep
pxbh:   .repeat 16, P
        .byte >(PEXP + P*PXBLK)
        .endrep
pclbl:  .repeat 16, P
        .byte <(PCLIP + P*CLIPH)
        .endrep
pclbh:  .repeat 16, P
        .byte >(PCLIP + P*CLIPH)
        .endrep
pdl:    .repeat 16, P               ; palette * 4 + level
        .byte <(pdim64 + P*64)
        .endrep
pdh:    .repeat 16, P
        .byte >(pdim64 + P*64)
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
pnl:    .res 1                  ; merge: nearest bar's index of line cD
nbe:    .res 1                  ;   end of its rows
dlo:    .res 1                  ;   a farther bar's offset from it
dhi:    .res 1
fj:     .res 1                  ; a farther bar: its lines, height, rows
flo:    .res 1
fhi:    .res 1
hf:     .res 1
lo:     .res 1
hi:     .res 1

.segment "RAMPS"
cols:   .res 2*NSLOT*NCOL*256   ; a page per column, 2 buffers
        .assert <cols = 0, error, "cols must be page aligned"
        .assert * <= VICBANK, error, "program runs into the VIC bank"
