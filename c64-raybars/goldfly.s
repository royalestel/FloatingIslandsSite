; =============================================================================
;  GOLDFLY -- raster bars flying out of the distance past a central light
;  cl65 -t none -C raybars.cfg -o goldfly.prg goldfly.s
; =============================================================================
;
;  The light is a ball sprite fixed at the centre of the screen.  Three
;  bars at a time fly toward the camera from the distance, each with a
;  random palette (gold, a second 24-colour one, and two 12-colour ones
;  dithered up to 24), a random fixed tilt (neighbouring segments up to 2
;  lines apart), a random distance from the centre line, and alternating
;  above / below the light.  In perspective they start small near the
;  middle, grow and fly out through the top or bottom edge.  They dim with
;  distance and reflect the light: thickest nearest it, and riding to the
;  bar's edge once a bar is nearer the camera than the light.
;
;  DISPLAY: POINTER-READ SPEEDCODE
;  Each bar's display code is a 63-cycle loop over its rows:
;       5 x (lda (pK),y / sta $d021)  =  5 x 9 cycles  (72-pixel segments)
;  pK points into segment K's colour column for this bar, offset by the
;  segment's tilt.  Nothing is patched per frame: the main loop only builds
;  the columns and the pointers.  The bars live inside the display window
;  (opened without badlines, see goldlight.s), so only $d021 is written;
;  the side borders stay black.  The columns are 64-byte aligned, so
;  (pK),y never crosses a page (that would cost a cycle).
;
;  FRAME PIPELINE
;  The main loop builds frame N+1 (columns into the back buffer, pointers
;  and the IRQ schedule into "next" copies) while frame N is shown.  The
;  top IRQ swaps them in when ready.  Bars are placed so they never share
;  lines with each other (12+ lines apart) or with the light's sprite.
; =============================================================================

        .setcpu "6502"

        .include "fly.inc"      ; FLYD, flight tables, palettes, dims, rnd

NSLOT     = 3           ; bars in flight
SEGS      = 5
PAD       = 8           ; black rows above each bar's column (>= max slant)
COLSZ     = 64          ; one column; 64-aligned so (p),y never crosses a page
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
rndi:    .res 1                 ; random table index
sidx:    .res 1                 ; schedule entry being shown
curn:    .res 1                 ; rows / first row / code of the next bar
cury:    .res 1
curvec:  .res 2
st:      .res NSLOT             ; per slot: flight time
spal:    .res NSLOT             ;           palette
stilt:   .res NSLOT             ;           tilt angle
sycl:    .res NSLOT             ;           lateral distance class
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
top:     .res 1                 ; schedule entry being made
n:       .res 1
ys:      .res 1
hh:      .res 1
lb:      .res 1         ; highlight brightness base
sr:      .res 1         ; source row
lev16:   .res 1         ; distance level * 16
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
        ldx #0                  ; clear all columns (2 buffers)
@col:   .repeat 8, P
        sta cols + P*256,x
        .endrep
        inx
        bne @col
        ldx #NSLOT-1            ; stagger the bars along their flight
@stg:   lda stagger,x
        sta st,x
        txa
        sta sside,x             ; sides alternate
        and #1
        sta sside,x
        lda #$ff
        sta clev,x
        lda rnd,x
        and #3
        sta spal,x
        lda rnd+8,x
        sta stilt,x
        lda #1
        sta sycl,x
        dex
        bpl @stg
        lda #NSLOT
        sta spawn

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
        sta $ffff,x
skip:
.endmacro

; =============================================================================
;  build: the next frame -- every bar's columns, pointers, and the schedule
; =============================================================================
.proc build
        lda #0
        sta ncount
        ldx #NSLOT-1
slot:   stx s
        jsr doslot
        ldx s
        dex
        bpl slot
        jsr sortsched
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
        ldy rndi                ; random palette, tilt, lateral distance
        lda rnd,y
        and #3
        sta spal,x
        lda rnd+1,y
        sta stilt,x
        lda rnd+2,y
        and #3
        cmp #3
        bcc :+
        lda #1
:       sta sycl,x
        lda rndi
        clc
        adc #3
        sta rndi
        lda spawn               ; sides alternate spawn by spawn
        and #1
        sta sside,x
        inc spawn
        lda #$ff                ; new palette: recolour its rows
        sta clev,x
alive:

        ; ---- this slot's columns in the back buffer: patch the stores -------
        ; column index m = buf*15 + s*5 + k
        lda buf
        beq :+
        lda #15
:       sta acc
        txa
        asl
        asl
        adc s                   ; s*5
        adc acc
        tay                     ; m for k = 0
        .repeat ::SEGS, K
        lda collo+K,y
        sta .ident(.sprintf("ex%d", K))
        sta .ident(.sprintf("ov%d", K))
        sta .ident(.sprintf("zc%d", K))
        lda colhi+K,y
        sta .ident(.sprintf("ex%d", K))+1
        sta .ident(.sprintf("ov%d", K))+1
        sta .ident(.sprintf("zc%d", K))+1
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
        lda sycl,x
        beq c0
        cmp #1
        beq c1
        lda foff2,y
        jmp coff
c0:     lda foff0,y
        jmp coff
c1:     lda foff1,y
coff:   sta off

        ; ---- where it goes on screen ----------------------------------------
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
        sta ys
        ldx s
        lda sside,x
        bne lower
        ; above the light: centre = CENTRE - off (off <= 143: >= 7)
        lda #CENTRE
        sec
        sbc off
        sta top                 ; centre line
        lda #WTOP
        clc
        adc hh
        cmp top
        bcc nottop              ; centre - hh > WTOP: no clipping
        sec
        sbc top                 ; rows above WTOP
        sta ys
        cmp n
        bcs hidden                ; all clipped
        lda n
        sec
        sbc ys
        sta n
        lda #WTOP
        sta top
        jmp add
nottop: lda top
        sec
        sbc hh
        sta top
        jmp add
lower:  ; below the light: centre = CENTRE + off
        lda #CENTRE
        clc
        adc off
        bcs hidden                ; past line 255
        sec
        sbc hh
        cmp #WBOT
        bcs hidden
        sta top
        clc
        adc n
        bcs clipb
        cmp #WBOT + 1
        bcc add
clipb:
        lda #WBOT + 1           ; clip at the bottom of the window
        sec
        sbc top
        sta n
add:    jmp visible         ; on screen: build it, then enter it
hidden: rts
visible:

        ; ---- tilt -----------------------------------------------------------------
        ldy stilt,x
        .repeat ::SEGS, K
        lda .ident(.sprintf("tkbase%d", K)),y
        sta kb+K
        .endrep

        ; ---- the light seen from this bar ---------------------------------------
        ldy sycl,x
        lda fdy,y               ; lateral distance, toward the centre
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

        ; ---- 24 source rows: spec levels ---------------------------------------
        ldy #BARH-1
spl:    ldx theta2,y
spe_op = * + 1
        lda spectab,x
        sta specs,y
        dey
        bpl spl

        ; ---- the bar's dimmed palette rows: cached per slot ---------------------
        ldx s
        lda srcbe,x             ; this slot's cache: csrce/csrco + s*24
        sta se_op
        lda srcbo,x
        sta so_op
        lda lev
        cmp clev,x
        beq cached
        sta clev,x
        asl
        asl
        asl
        asl
        sta lev16
        lda spal,x              ; palette offset = pal * 24
        asl
        asl
        asl
        sta acc
        asl
        clc
        adc acc
        sta pal_op
        lda srcbe,x
        sta cw_op
        lda srcbo,x
        sta cwo_op
        ldy #BARH-1
srow:   sty acc
        tya
        clc
pal_op = * + 1
        adc #0
        tax                     ; palette * 24 + row
        lda pale,x
        clc
        adc lev16
        tay
        lda dims4,y             ; dimmed by distance
        ldy acc
cw_op = * + 1
        sta csrce,y
        lda palo,x
        clc
        adc lev16
        tay
        lda dims4,y
        ldy acc
cwo_op = * + 1
        sta csrco,y
        dey
        bpl srow
cached:

        ; ---- nearest-neighbour expansion into all 5 columns ----------------
        ldx h
        lda nnsteplo,x
        sta stl_op
        lda nnstephi,x
        sta sth_op
        lda #PAD
        clc
        adc h
        sta endx_op
        ldx #PAD
        lda #0
        sta acc
        tay                     ; source row
        clc
exl:    txa                     ; even or odd row of the bar
        lsr
        bcs odd
se_op = * + 1
        lda csrce,y
        jmp put
odd:
so_op = * + 1
        lda csrco,y
put:
ex0 = * + 1
        sta $ffff,x
ex1 = * + 1
        sta $ffff,x
ex2 = * + 1
        sta $ffff,x
ex3 = * + 1
        sta $ffff,x
ex4 = * + 1
        sta $ffff,x
        inx
        lda acc
        clc
stl_op = * + 1
        adc #0
        sta acc
        tya
sth_op = * + 1
        adc #0
        tay
endx_op = * + 1
        cpx #0
        bne exl
        lda #0                  ; 8 black rows after the bar (no clearing needed:
        ldy #PAD                ; rows further down are never read)
z8:
zc0 = * + 1
        sta $ffff,x
zc1 = * + 1
        sta $ffff,x
zc2 = * + 1
        sta $ffff,x
zc3 = * + 1
        sta $ffff,x
zc4 = * + 1
        sta $ffff,x
        inx
        dey
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
        lda #0
        sta si
ovi:    ldy si
        lda specs,y
        cmp #HLTHR
        bcs :+
        jmp ovskip
:       tax
        lda mul5,x
        clc
        adc lb
        sta hidx                ; hltab row for this spec level
        lda (rsp),y             ; rows rowstart[i] .. rowstart[i+1]-1
        clc
        adc #PAD
        tax
        iny
        lda (rsp),y
        clc
        adc #PAD
        sta rend
        cpx rend
        beq ovskip
        ldy hidx
rowl:   hlrow 0, ov0
        hlrow 1, ov1
        hlrow 2, ov2
        hlrow 3, ov3
        hlrow 4, ov4
        inx
        cpx rend
        bne rowl
ovskip: inc si
        lda si
        cmp #BARH
        beq :+
        jmp ovi
:

        ; ---- next pointers for this bar -------------------------------------
        ; pK = column K + kb_K (row r of the block reads column[r + kb_K])
        lda s
        asl
        asl
        clc
        adc s                   ; s*5
        asl                     ; *2: pointer pairs
        tax
        .repeat ::SEGS, K
        lda .ident(.sprintf("ex%d", K))
        clc
        adc kb+K
        sta nptr + K*2,x
        lda .ident(.sprintf("ex%d", K))+1
        adc #0
        sta nptr + K*2 + 1,x
        .endrep

        ldx ncount              ; schedule entry
        lda top
        sec
        sbc #2
        sta nline,x
        lda s
        sta nslot,x
        lda n
        sta nnrows,x
        lda ys
        sta nystart,x
        inc ncount
        rts
.endproc

; -----------------------------------------------------------------------------
;  sortsched: order the next schedule by line; drop a bar that would start
;  before the previous one has finished (never happens with these flights,
;  but it keeps the IRQ chain safe).
; -----------------------------------------------------------------------------
.proc sortsched
        ldx ncount
        cpx #2
        bcc check
        ; 3-element sort network on (nline, nslot, nnrows, nystart)
        ldx #0
        ldy #1
        jsr cswap
        ldx ncount
        cpx #3
        bcc check
        ldx #1
        ldy #2
        jsr cswap
        ldx #0
        ldy #1
        jsr cswap
check:  ldx #1
cl:     cpx ncount
        bcs done
        lda nline-1,x           ; previous end = line + 2 + rows
        clc
        adc #2
        clc
        adc nnrows-1,x
        clc
        adc #2                  ; room for the IRQ
        cmp nline,x
        bcc ok
        beq ok
        ; drop entry x: shift the rest down
        txa
        tay
dl:     iny
        cpy ncount
        bcs dropped
        lda nline,y
        sta nline-1,y
        lda nslot,y
        sta nslot-1,y
        lda nnrows,y
        sta nnrows-1,y
        lda nystart,y
        sta nystart-1,y
        jmp dl
dropped:
        dec ncount
        jmp cl
ok:     inx
        jmp cl
done:   rts

cswap:  lda nline,y             ; swap x/y if line[y] < line[x]
        cmp nline,x
        bcs :+
        .repeat 4, F
        .if F = 0
        lda nline,x
        pha
        lda nline,y
        sta nline,x
        pla
        sta nline,y
        .elseif F = 1
        lda nslot,x
        pha
        lda nslot,y
        sta nslot,x
        pla
        sta nslot,y
        .elseif F = 2
        lda nnrows,x
        pha
        lda nnrows,y
        sta nnrows,x
        pla
        sta nnrows,y
        .else
        lda nystart,x
        pha
        lda nystart,y
        sta nystart,x
        pla
        sta nystart,y
        .endif
        .endrep
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
        .include "twin.inc"     ; tkbase0..4, nnsteplo/hi
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

; column addresses: index m = buf*15 + slot*5 + segment
collo:  .repeat 2*NSLOT*SEGS, M
        .byte <(cols + M*COLSZ)
        .endrep
colhi:  .repeat 2*NSLOT*SEGS, M
        .byte >(cols + M*COLSZ)
        .endrep
rsl:    .repeat 49, HH
        .byte <(rowstart + HH*25)
        .endrep
rsh:    .repeat 49, HH
        .byte >(rowstart + HH*25)
        .endrep
srcbe:  .byte <csrce, <(csrce + BARH), <(csrce + 2*BARH)  ; per-slot colour caches
srcbo:  .byte <csrco, <(csrco + BARH), <(csrco + 2*BARH)
blkvlo: .lobytes blk0, blk1, blk2
blkvhi: .hibytes blk0, blk1, blk2

; =============================================================================
.segment "BSS"
csrce:  .res NSLOT*BARH         ; per slot: dimmed palette rows, even lines
csrco:  .res NSLOT*BARH         ;           ... odd lines (one page with csrce)
        .assert >csrce = >(csrco + NSLOT*BARH - 1), error, "colour caches must share a page"
specs:  .res BARH
clev:   .res NSLOT              ; cached distance level per slot ($ff: stale)
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

.segment "RAMPS"
; dims4 lives in fly.inc
cols:   .res 2*NSLOT*SEGS*COLSZ ; 1920 bytes of 64-aligned columns
        .assert <cols = 0, error, "cols must be page aligned"
        .assert * <= VICBANK, error, "program runs into the VIC bank"
