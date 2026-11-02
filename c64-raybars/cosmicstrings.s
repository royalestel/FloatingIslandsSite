; =============================================================================
;  COSMIC STRINGS -- fly a ship through a slab of glowing raster bars
;  python3 gen_cosmic.py
;  cl65 -t none -C cosmic.cfg -o cosmicstrings.prg cosmicstrings.s
; =============================================================================
;
;  Space is full of horizontal glowing bars: one row of bars every 1.375 m
;  along z, each at its own height (256 heights, a 16 m slab that repeats
;  up and down).  The ship, two multicolour sprites side by side, is seen
;  from a chase camera that pitches with it.  Joystick in port 2: down
;  pulls the nose up, up pushes it down (hold it for a loop-the-loop); fire
;  boosts the speed up to 3x.
;
;  3D, EVERY FRAME (build)
;  The camera only pitches, so each bar is a point in the y-z plane:
;       d = ry sin + rz cos      (depth)       u = ry cos - rz sin
;  The rows are evenly spaced in z, so the rz terms step by a constant from
;  row to row (two 24-bit adds); ry = t + wofs - frac, t the bar's height
;  minus the camera's (8 bits, wrapping: the slab repeats), so each row
;  costs one 8 x 8 multiply for d (quarter squares) and one more for u if
;  d is in range.  Perspective by logs: the screen offset 400 u / d (half
;  lines) and the bar's height (80 / d lines near, 26.7 sqrt(3 / d) beyond
;  3 m) are exp(log - log) lookups, 1/128 octave.
;
;  OCCLUSION, SPANS AND BLOCKS
;  Bars are sorted near to far; each one's visible pieces are what the
;  union of the nearer ones leaves.  The pieces, in screen order, become
;  span records (source, length, the line code to enter) grouped into
;  blocks: lines with bars, gaps under GAPMIN lines filled with black.
;  Each block gets a raster IRQ; between blocks the screen is black and
;  the CPU is free.
;
;  DISPLAY: THE STACK FEEDS THE SPANS
;  A block's records are copied to page 1 in the vertical blank; its IRQ
;  points the stack at them.  Each line:  lda (src),y / tax / colour and
;  idle byte from the swatch tables / dey; when y reaches 0 the next span
;  comes off the stack (pla x 3, rts into its line code): 26 cycles that
;  fit the line's spare time.  So no per-line build: a bar's ramp (its
;  swatch per row, bottom row first, two ramps a page so (src),y never
;  crosses a page) is read straight from memory.
;  The swatch: a flicker pair (a / b on alternate frames, the phase swapped
;  on alternate lines) and an idle byte ($bfff: set bits show black, a
;  ghost-byte pattern), from 4 tables: row parity x frame parity (the top
;  IRQ patches the frame parity into the line code).
;  The ship's lines: the VIC takes 7 cycles of each for the two sprites,
;  so they have their own line code (56 cycles) and spans split there.
;
;  Untested on real hardware or VICE so far: line timing (HTUNE, STEAL)
;  is checked only in the simulator (sim_cosmic.py).
; =============================================================================
        .setcpu "6502X"         ; with the stable illegal opcodes
        .include "cosmic.inc"

GAPMIN    = 6           ; black gaps shorter than this stay inside a block
DENLINE   = 44
VBLLINE   = 253
HTUNE     = 0
RECMAX    = 224         ; page 1 bytes for span records ($0100-$01df)
NBMAX     = 32          ; bars kept per frame
NPMAX     = 48          ; pieces
NBLKMAX   = 24
NBUCK     = (NLINES + 7) / 8
NFMAX     = 16
NHMAX     = 16
SPDBASE   = 185         ; 0.72 units (0.045 m) a frame, 8.8
SPDMAX    = 555         ; fire: 3x
SPDACC    = 10
RMAX      = 66          ; pitch rate (x 4 angle units: a loop in ~250 frames)
RACC      = 3
SQL       = $c000       ; quarter squares floor(x*x/4), x = 0..511, lo / hi
SQH       = $c200
NSL       = $c400       ; floor((i-255)^2/4), i = 0..511
NSH       = $c600
SHL       = $e000       ; lg shift tables (made at start)
SHR       = $e800
NLZ       = $f000
BND       = $0500       ; per window line tables (made at start)
VARX      = $0600
SQSL      = $9800       ; signed squares (x^2)/4, x = -384..383 (made at start)
SQSH      = $9b00
SPRPTR    = $87f8
SPRBLK    = $20         ; $8800 / 64 in bank 2

; =============================================================================
.segment "ZEROPAGE"
src:     .res 2         ; display: span source
sav_a:   .res 1
sav_x:   .res 1
sav_y:   .res 1
sav_s:   .res 1
curs:    .res 1         ; display: the block's first record (stack pointer)
blk:     .res 1         ; display: block being shown, number of blocks
nblkd:   .res 1
shippd:  .res 1         ; display: ship pitch frame
fcount:  .res 1
ready:   .res 1         ; build done, waiting for the copy
copied:  .res 1         ; copy done: build the next one
psl:     .res 2         ; fixed multiplier S: (psl),y - (nsl),y = y * S
psh:     .res 2
nsl:     .res 2
nsh:     .res 2
pcl:     .res 2         ; fixed multiplier C
pch:     .res 2
ncl:     .res 2
nch:     .res 2
pgl:     .res 2         ; general multiplier
pgh:     .res 2
ngl:     .res 2
ngh:     .res 2
ma:      .res 1
mb:      .res 1
m0:      .res 1
m1:      .res 1
joy:     .res 1
rate:    .res 1         ; pitch rate (signed, x 4 angle units a frame)
angl:    .res 1         ; view angle (16 bits, 65536 a turn; 0 level)
angh:    .res 1
spdl:    .res 1         ; speed, units a frame (8.8)
spdh:    .res 1
cyff:    .res 1         ; camera height: units (wrapping: 16 m) . 16 bits
cyf:     .res 1
cyi:     .res 1
czff:    .res 1         ; camera z within its row: 0 <= cz < ROWSP
czf:     .res 1
czi:     .res 1
kc:      .res 1         ; camera's row (mod 256)
sv:      .res 1         ; |sin|, |cos| (x 256, max 255) and signs ($ff neg)
cv:      .res 1
sgns:    .res 1
sgnc:    .res 1
wofs:    .res 1         ; the height window's centre: 128 sin (signed)
ref:     .res 1         ; cyi + wofs
kd:      .res 3         ; row terms of d and u (1/4096 m), their steps
ku:      .res 3
sd:      .res 3
su:      .res 3
xv:      .res 3         ; mul24 in / out
rr:      .res 3
mm:      .res 1
neg:     .res 1
at:      .res 1         ; |t|, sign
at0:     .res 1
st:      .res 1
dd:      .res 3         ; d, u of the row
uu:      .res 3
usg:     .res 1
rows:    .res 1
krow:    .res 1
nb:      .res 1         ; bars this frame
v0:      .res 3         ; lg in
lgl:     .res 1         ; lg out
lgh:     .res 1
pos:     .res 1
lo:      .res 1
ldl:     .res 1         ; log d
ldh:     .res 1
il:      .res 1
ih:      .res 1
ep:      .res 2
q2l:     .res 1         ; 400 u / d, half lines
q2h:     .res 1
hh:      .res 1         ; bar height, lines
tl:      .res 1         ; bar top (signed 16)
th:      .res 1
t0:      .res 2
t1:      .res 2
cur:     .res 1
ee:      .res 1
aa:      .res 1
bb:      .res 1
j:       .res 1
nu:      .res 1
np:      .res 1
recp:    .res 1
nblk:    .res 1
inb:     .res 1
cend:    .res 1
ps0:     .res 1         ; span being emitted
ps1:     .res 1
pbar:    .res 1
rp:      .res 2         ; record source
shipp:   .res 1
sqv:     .res 3
sqx:     .res 2
sp:      .res 2
nxt:     .res 1
nact:    .res 1
own:     .res 1
okl:     .res 1
okh:     .res 1
stop:    .res 1
pbx:     .res 1
it1:     .res 1         ; IRQ scratch
lastfc:  .res 1
nsteps:  .res 1
ii:      .res 1
nearonly: .res 1
nfar:    .res 1
ext:     .res 1
ref2:    .res 1
nbe:     .res 1
t2:      .res 1
q0:      .res 1
q1:      .res 1
hcur:    .res 1
hlim:    .res 1
hp:      .res 1
nh:      .res 1
nfh:     .res 1
fangl:   .res 1
fangh:   .res 1
shift:   .res 1
spnl:    .res 1
spnh:    .res 1

; =============================================================================
.segment "BSS"
recbuf:  .res RECMAX
bkl:     .res NBMAX     ; per bar: sort key (d >> 8)
bkh:     .res NBMAX
bhh:     .res NBMAX     ;          height
ba:      .res NBMAX     ;          clipped start / end line
be:      .res NBMAX
bk:      .res NBMAX     ;          row (for the simulator)
bsl:     .res NBMAX     ;          span source base
bsh:     .res NBMAX
ord:     .res NBMAX     ; bars in screen order (by start line)
act:     .res NBMAX     ; sweep: bars covering the current line
head:    .res NBUCK     ; screen-order buckets (first line / 8)
nextb:   .res NBMAX
hs:      .res NHMAX     ; the far layer: sorted line intervals
he:      .res NHMAX
fhs:     .res NHMAX     ; ... kept from the last full build
fhe:     .res NHMAX
bline:   .res NBLKMAX   ; blocks being built: irq1 line, first record
bss:     .res NBLKMAX
dline:   .res NBLKMAX   ; blocks shown
dss:     .res NBLKMAX
nrec:    .res 1

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
        .assert * = 2062, error, "SYS 2061 must land on start"
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #$35
        sta $01
        lda $dd00               ; VIC bank 2: $8000-$bfff
        and #$fc
        ora #$01
        sta $dd00
        lda #$10                ; screen $8400: sprite pointers $87f8
        sta $d018
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #<irqtop
        sta $fffe
        lda #>irqtop
        sta $ffff
        ldx #$fe
        lda #0
@zp:    sta $01,x
        dex
        bne @zp
        sta $d020
        sta $d021
        sta $bfff
        sta $dc02               ; joystick port: inputs
        jsr gensqr
        jsr genshift
        jsr genlines
        jsr gensqs
        lda #<SPDBASE
        sta spdl
        lda #>SPDBASE
        sta spdh
        lda #4
        sta shipp
        sta shippd
        ; the ship: sprites 0 and 1, multicolour, side by side
        lda #3
        sta $d015
        sta $d01c
        lda #0
        sta $d017
        sta $d01d
        sta $d01b
        sta $d010
        lda #160
        sta $d000
        lda #184
        sta $d002
        lda #SPRY
        sta $d001
        sta $d003
        lda #4                  ; %01 purple
        sta $d025
        lda #1                  ; %11 the glow (white / cyan by frame)
        sta $d026
        lda #14                 ; %10 light blue
        sta $d027
        sta $d028
        lda #SPRBLK + 16
        sta SPRPTR
        lda #SPRBLK + 17
        sta SPRPTR+1
        lda #$0b
        sta $d011
        lda #DENLINE
        sta $d012
        lda #1
        sta $d01a
        sta $d019
        jsr build
        lda #1
        sta ready
        cli
main:   lda copied
        beq main
        lda #0
        sta copied
        jsr build
        lda #1
        sta ready
        jmp main

nmi:    rti

; -----------------------------------------------------------------------------
;  quarter squares: SQL/SQH[x] = x*x/4 (x 0..511), NSL/NSH[i] = (i-255)^2/4
gensqr: lda #0
        sta sqv
        sta sqv+1
        sta sqv+2
        sta sqx
        sta sqx+1
@lp:    lda sqv+1               ; (sqv >> 2) 16 bits
        sta t0+1
        lda sqv
        sta t0
        lda sqv+2
        lsr a
        ror t0+1
        ror t0
        lsr a
        ror t0+1
        ror t0
        lda #<SQL               ; store at x
        clc
        adc sqx
        sta sp
        lda #>SQL
        adc sqx+1
        sta sp+1
        ldy #0
        lda t0
        sta (sp),y
        lda sp+1
        clc
        adc #2                  ; SQH = SQL + $200
        sta sp+1
        lda t0+1
        sta (sp),y
        lda sqx                 ; sqv += 2x + 1
        asl a
        sta t1
        lda sqx+1
        rol a
        sta t1+1
        lda t1
        ora #1
        clc
        adc sqv
        sta sqv
        lda t1+1
        adc sqv+1
        sta sqv+1
        lda sqv+2
        adc #0
        sta sqv+2
        inc sqx
        bne @lp
        inc sqx+1
        lda sqx+1
        cmp #2
        bne @lp
        ; NSL/NSH[i] = SQL/SQH[|i - 255|]
        lda #0
        sta sqx
        sta sqx+1
@lp2:   lda sqx                 ; t0 = i - 255
        sec
        sbc #255
        sta t0
        lda sqx+1
        sbc #0
        sta t0+1
        bpl @pos
        lda #0                  ; negate
        sec
        sbc t0
        sta t0
        lda #0
        sbc t0+1
        sta t0+1
@pos:   lda #<SQL
        clc
        adc t0
        sta sp
        lda #>SQL
        adc t0+1
        sta sp+1
        ldy #0
        lda (sp),y
        pha
        lda sp+1
        clc
        adc #2
        sta sp+1
        lda (sp),y
        pha
        lda #<NSL
        clc
        adc sqx
        sta sp
        lda #>NSL
        adc sqx+1
        sta sp+1
        lda sp+1
        clc
        adc #2
        sta sp+1
        pla
        sta (sp),y              ; NSH
        lda sp+1
        sec
        sbc #2
        sta sp+1
        pla
        sta (sp),y              ; NSL
        inc sqx
        bne @lp2
        inc sqx+1
        lda sqx+1
        cmp #2
        bne @lp2
        rts

; general 8 x 8: ma * mb -> m0 m1
mul8:   lda mb
        sta pgl
        sta pgh
        lda #>SQL
        sta pgl+1
        lda #>SQH
        sta pgh+1
        lda #255
        sec
        sbc mb
        sta ngl
        sta ngh
        lda #>NSL
        sta ngl+1
        lda #>NSH
        sta ngh+1
        ldy ma
        lda (pgl),y
        sec
        sbc (ngl),y
        sta m0
        lda (pgh),y
        sbc (ngh),y
        sta m1
        rts

; ma * the multiplier whose pointers are in pg* -> m0 m1
mulg:   ldy ma
        lda (pgl),y
        sec
        sbc (ngl),y
        sta m0
        lda (pgh),y
        sbc (ngh),y
        sta m1
        rts

; the multiplier for mul24: S or C (their fixed pointers into pg*)
pgs:    ldx #7
:       lda psl,x
        sta pgl,x
        dex
        bpl :-
        rts
pgc:    ldx #7
:       lda pcl,x
        sta pgl,x
        dex
        bpl :-
        rts

; rr = (xv * S or C) >> 8, xv signed 24 bits (pgs / pgc first)
mul24:  lda xv+2
        sta neg
        bpl @p
        lda #0
        sec
        sbc xv
        sta xv
        lda #0
        sbc xv+1
        sta xv+1
        lda #0
        sbc xv+2
        sta xv+2
@p:     lda xv
        sta ma
        jsr mulg
        lda m1
        sta rr
        lda xv+1
        sta ma
        jsr mulg
        lda m0
        clc
        adc rr
        sta rr
        lda m1
        adc #0
        sta rr+1
        lda xv+2
        sta ma
        jsr mulg
        lda m0
        clc
        adc rr+1
        sta rr+1
        lda m1
        adc #0
        sta rr+2
        lda neg
        bpl mulx
negrr:  lda #0
        sec
        sbc rr
        sta rr
        lda #0
        sbc rr+1
        sta rr+1
        lda #0
        sbc rr+2
        sta rr+2
mulx:   rts

; set the fixed multipliers: S (psl..) and C (pcl..)
setmul: lda sv
        sta psl
        sta psh
        lda #>SQL
        sta psl+1
        lda #>SQH
        sta psh+1
        lda #255
        sec
        sbc sv
        sta nsl
        sta nsh
        lda #>NSL
        sta nsl+1
        lda #>NSH
        sta nsh+1
        lda cv
        sta pcl
        sta pch
        lda #>SQL
        sta pcl+1
        lda #>SQH
        sta pch+1
        lda #255
        sec
        sbc cv
        sta ncl
        sta nch
        lda #>NSL
        sta ncl+1
        lda #>NSH
        sta nch+1
        rts

; =============================================================================
;  build the next frame
; =============================================================================
build:  lda fcount               ; frames since the last build: move that far
        sec
        sbc lastfc
        bne :+
        lda #1
:       cmp #5
        bcc :+
        lda #4
:       sta nsteps
        lda fcount
        sta lastfc
        lda #0                  ; the distance: speed summed over the frames
        sta spnl
        sta spnh
@st:    jsr controls
        lda spnl
        clc
        adc spdl
        sta spnl
        lda spnh
        adc spdh
        sta spnh
        dec nsteps
        bne @st
        jsr sincos
        jsr move
        jsr setmul
        jsr frameconst
        lda nearonly            ; far bars on every other build
        eor #$ff
        sta nearonly
        bit nearonly            ; the far layer: kept, or made afresh
        bmi @keep
        lda #0
        sta nh
        jmp @rows
@keep:  lda angl                ; the scene turned since: shift the layer
        sec                     ; by 200 * (angle change), lines
        sbc fangl
        sta t0
        lda angh
        sbc fangh
        sta t0+1                ; dang (signed); * 5 / 256
        lda t0
        asl a
        sta t1
        lda t0+1
        rol a
        sta t1+1
        asl t1
        rol t1+1
        lda t1
        clc
        adc t0
        lda t1+1
        adc t0+1
        sta shift               ; (dang * 5) >> 8
        ldx #0
        ldy #0
@cp1:   cpx nfh
        bcs @cpd
        lda fhs,x
        jsr shl1
        sta hs,y
        lda fhe,x
        jsr shl1
        sta he,y
        cmp hs,y
        beq :+                  ; shifted out of the window
        iny
:       inx
        bne @cp1
@cpd:   sty nh
@rows:  jsr dorows
        bit nearonly
        bmi @done
        lda angl                ; full build: keep its far layer
        sta fangl
        lda angh
        sta fangh
        ldx nh
        stx nfh
        beq @done
@cp2:   lda hs-1,x
        sta fhs-1,x
        lda he-1,x
        sta fhe-1,x
        dex
        bne @cp2
@done:
        jmp sweep

; line A + shift, clipped to the window
shl1:   clc
        adc shift
        bit shift
        bmi @n
        bcs @hi                 ; past 255
        cmp #NLINES
        bcc @x
@hi:    lda #NLINES
@x:     rts
@n:     bcs :+                  ; below 0
        lda #0
:       cmp #NLINES
        bcs @hi
        rts

; joystick: pitch rate and speed, eased
controls:
        lda $dc00
        eor #$ff
        and #$1f
        sta joy
        ldx #0                  ; target rate
        lsr a                   ; bit 0 up: nose down
        bcc :+
        ldx #<(-RMAX)
:       lsr a                   ; bit 1 down: nose up
        bcc :+
        ldx #RMAX
:       stx t0
        lda t0                  ; ease toward the target (signed: biased)
        eor #$80
        sta t0+1
        lda rate
        eor #$80
        cmp t0+1
        beq @rok
        bcc @up
        sec
        sbc #RACC
        cmp t0+1
        bcs @rs
        lda t0+1
        jmp @rs
@up:    clc
        adc #RACC
        cmp t0+1
        bcc @rs
        lda t0+1
@rs:    eor #$80
        sta rate
@rok:   lda rate                ; angle += rate * 4
        ldx #0
        cmp #$80
        bcc :+
        dex
:       stx t1
        asl a
        rol t1
        asl a
        rol t1
        clc
        adc angl
        sta angl
        lda t1
        adc angh
        sta angh
        lda rate                ; the ship's pitch frame: (rate + 72) >> 4
        clc
        adc #72
        lsr a
        lsr a
        lsr a
        lsr a
        cmp #9
        bcc :+
        lda #8
:       sta shipp
        ; speed: fire boosts toward SPDMAX, else back to SPDBASE
        lda joy
        and #$10
        beq @base
        lda spdl
        clc
        adc #SPDACC
        sta spdl
        bcc :+
        inc spdh
:       lda spdl
        cmp #<SPDMAX
        lda spdh
        sbc #>SPDMAX
        bcc @sx
        lda #<SPDMAX
        sta spdl
        lda #>SPDMAX
        sta spdh
        rts
@base:  lda spdl
        cmp #<(SPDBASE+SPDACC)
        lda spdh
        sbc #>(SPDBASE+SPDACC)
        bcc @set
        lda spdl
        sec
        sbc #SPDACC
        sta spdl
        bcs @sx
        dec spdh
@sx:    rts
@set:   lda #<SPDBASE
        sta spdl
        lda #>SPDBASE
        sta spdh
        rts

; sin / cos of the view angle (12 bits): magnitude x 256 (max 255), sign
sincos: lda angh                ; i10 = angle bits 13..4
        and #$3f
        sta t0+1
        lda angl
        lsr t0+1
        ror a
        lsr t0+1
        ror a
        lsr t0+1
        ror a
        lsr t0+1
        ror a
        sta t0                  ; t0 = i10 (0..1023)
        clc                     ; a = sinq[i10]
        adc #<sinq
        sta sp
        lda t0+1
        adc #>sinq
        sta sp+1
        ldy #0
        lda (sp),y
        sta aa
        lda #<(sinq+1024)       ; b = sinq[1024 - i10]
        sec
        sbc t0
        sta sp
        lda #>(sinq+1024)
        sbc t0+1
        sta sp+1
        lda (sp),y
        sta bb
        lda angh                ; quadrant
        lsr a
        lsr a
        lsr a
        lsr a
        lsr a
        lsr a
        tax
        lda aa
        ldy bb
        cpx #1
        beq @q1
        cpx #2
        beq @q2
        cpx #3
        beq @q3
        sta sv                  ; q0: sin a, cos b
        sty cv
        lda #0
        sta sgns
        sta sgnc
        jmp @w
@q1:    sty sv                  ; q1: sin b, cos -a
        sta cv
        lda #0
        sta sgns
        lda #$ff
        sta sgnc
        jmp @w
@q2:    sta sv                  ; q2: sin -a, cos -b
        sty cv
        lda #$ff
        sta sgns
        sta sgnc
        jmp @w
@q3:    sty sv                  ; q3: sin -b, cos a
        sta cv
        lda #$ff
        sta sgns
        lda #0
        sta sgnc
@w:     lda sv                  ; wofs = 128 sin
        lsr a
        bit sgns
        bpl :+
        eor #$ff
        clc
        adc #1
:       sta wofs
        rts

; move the camera: cy += spd sin, cz += spd cos (24 bits, units . 16)
move:   lda sv
        sta mb
        jsr spdmul
        lda sgns
        bmi @ys
        lda cyff
        clc
        adc rr
        sta cyff
        lda cyf
        adc rr+1
        sta cyf
        lda cyi
        adc rr+2
        sta cyi
        jmp @z
@ys:    lda cyff
        sec
        sbc rr
        sta cyff
        lda cyf
        sbc rr+1
        sta cyf
        lda cyi
        sbc rr+2
        sta cyi
@z:     lda cv
        sta mb
        jsr spdmul
        lda sgnc
        bmi @zs
        lda czff
        clc
        adc rr
        sta czff
        lda czf
        adc rr+1
        sta czf
        lda czi
        adc rr+2
        sta czi
        jmp @n
@zs:    lda czff
        sec
        sbc rr
        sta czff
        lda czf
        sbc rr+1
        sta czf
        lda czi
        sbc rr+2
        sta czi
@n:     lda czi                 ; keep 0 <= cz < ROWSP: next / previous row
        bmi @back
        cmp #ROWSP
        bcc @x
        sbc #ROWSP
        sta czi
        inc kc
        rts
@back:  clc
        adc #ROWSP
        sta czi
        dec kc
@x:     rts

; rr = spd * mb (16 x 8 -> 24 bits)
spdmul: lda spnl
        sta ma
        jsr mul8
        lda m0
        sta rr
        lda m1
        sta rr+1
        lda spnh
        sta ma
        jsr mul8
        lda m0
        clc
        adc rr+1
        sta rr+1
        lda m1
        adc #0
        sta rr+2
        rts

; per frame: the rows to visit, the row terms of d and u and their steps
frameconst:
        ldx angh
        lda nrow,x
        sta rows
        lda kmin,x
        sta aa                  ; kmin (signed)
        clc
        adc kc
        sta krow
        ; rz0 = 22 kmin - cz  (16.8 signed) -> xv (as 24 bits: int16 . frac8)
        lda aa
        bpl :+
        eor #$ff
        clc
        adc #1
:       sta ma
        lda #ROWSP
        sta mb
        jsr mul8                ; |kmin| * 22
        lda aa
        bpl :+
        lda #0
        sec
        sbc m0
        sta m0
        lda #0
        sbc m1
        sta m1
:       lda #0                  ; - czi.czf
        sec
        sbc czf
        sta t1                  ; frac
        lda m0
        sbc czi
        sta t1+1
        lda m1
        sbc #0
        sta aa                  ; rz0 = aa:t1+1 . t1
        ; v = wofs - cy frac (8.8 signed) -> bb:t0 (sign ext in ee)
        lda #0
        sec
        sbc cyf
        sta t0
        lda wofs
        sbc #0
        sta t0+1
        lda wofs
        clc
        adc cyi
        sta ref
        ; kd = sgns * (v * S) + sgnc * (rz0 * C)
        jsr ldv
        jsr pgs
        jsr mul24
        lda sgns
        jsr sgnrr
        jsr rr2kd
        jsr ldrz
        jsr pgc
        jsr mul24
        lda sgnc
        jsr sgnrr
        jsr addrrkd
        ; ku = sgnc * (v * C) - sgns * (rz0 * S)
        jsr ldv
        jsr pgc
        jsr mul24
        lda sgnc
        jsr sgnrr
        jsr rr2ku
        jsr ldrz
        jsr pgs
        jsr mul24
        lda sgns
        eor #$ff
        jsr sgnrr
        jsr addrrku
        ; sd = sgnc * 22 C, su = -sgns * 22 S
        lda cv
        sta ma
        lda #ROWSP
        sta mb
        jsr mul8
        lda m0
        sta rr
        lda m1
        sta rr+1
        lda #0
        sta rr+2
        lda sgnc
        jsr sgnrr
        lda rr
        sta sd
        lda rr+1
        sta sd+1
        lda rr+2
        sta sd+2
        lda sv
        sta ma
        jsr mul8
        lda m0
        sta rr
        lda m1
        sta rr+1
        lda #0
        sta rr+2
        lda sgns
        eor #$ff
        jsr sgnrr
        lda rr
        sta su
        lda rr+1
        sta su+1
        lda rr+2
        sta su+2
        rts

ldv:    lda t0
        sta xv
        lda t0+1
        sta xv+1
        ldx #0
        cmp #$80
        bcc :+
        dex
:       stx xv+2
        rts
ldrz:   lda t1
        sta xv
        lda t1+1
        sta xv+1
        lda aa
        sta xv+2
        rts
sgnrr:  cmp #$80                ; A negative: rr = -rr
        bcc :+
        jmp negrr
:       rts
rr2kd:  lda rr
        sta kd
        lda rr+1
        sta kd+1
        lda rr+2
        sta kd+2
        rts
rr2ku:  lda rr
        sta ku
        lda rr+1
        sta ku+1
        lda rr+2
        sta ku+2
        rts
addrrkd:
        lda kd
        clc
        adc rr
        sta kd
        lda kd+1
        adc rr+1
        sta kd+1
        lda kd+2
        adc rr+2
        sta kd+2
        rts
addrrku:
        lda ku
        clc
        adc rr
        sta ku
        lda ku+1
        adc rr+1
        sta ku+1
        lda ku+2
        adc rr+2
        sta ku+2
        rts

; -----------------------------------------------------------------------------
;  the rows: d (cull), u, then project.  Split by the sign of t; each path's
;  add / subtract (of |t| S and |t| C) patched per frame from the signs of
;  sin and cos (setops).
.segment "CODE2"

; dst = base +/- (m0 m1): the opcodes at P, P+3, P+9, P+15 patched
.macro ACCUM P, base, dst
P:      clc
        lda base
        adc m0
        sta dst
        lda base+1
        adc m1
        sta dst+1
        lda base+2
        adc #0
        sta dst+2
.endmacro

; m0 m1 = y * S (or C) with the fixed quarter-square pointers
.macro MULS pl, ph, nl, nh
        lda (pl),y
        sec
        sbc (nl),y
        sta m0
        lda (ph),y
        sbc (nh),y
        sta m1
.endmacro

; d in range (after ACCUM, flags from d's top byte): DNEAR <= d < DFAR
.macro CULL skip
        .local hi, vis, no
        bmi no
        bne hi
        lda dd+1
        cmp #>DNEAR
        bcs vis
no:     jmp skip
hi:     cmp #^DFAR
        bne no
        lda dd+1
        cmp #>DFAR
        bcs no
vis:
.endmacro

; 128 log2 of a 24-bit value -> dl dh (7-bit mantissa, by shift tables)
.macro LGM xsrc, xdl, xdh
        .local n2, n1, go, sa, sb, zz, done
        ldx xsrc+2
        beq n2
        ldy xsrc+1
        lda #23
        bne go
n2:     ldx xsrc+1
        beq n1
        ldy xsrc
        lda #15
        bne go
n1:     ldx xsrc
        beq zz
        ldy #0
        lda #7
go:     sec
        sbc NLZ,x
        sta pos
        lda NLZ,x
        clc
        adc #>SHL
        sta sa+2
        adc #8
        sta sb+2
sa:     lda SHL,x
sb:     ora SHR,y
        asl a
        ora #1
        tax
        lda pos
        lsr a
        sta xdh
        lda #0
        ror a
        adc lmf,x
        sta xdl
        bcc done
        inc xdh
        bcs done
zz:     stx xdl
        stx xdh
done:
.endmacro

opadd:  .byte $18, $65, $65, $69        ; clc, adc zp, adc zp, adc #
opsub:  .byte $38, $e5, $e5, $e9        ; sec, sbc zp, sbc zp, sbc #
opoff:  .byte 0, 3, 9, 15

; patch the ACCUM at (t1) to add (A >= 0) or subtract (A < 0)
patch4: ldx #3
        cmp #$80
        bcs @s
@a:     ldy opoff,x
        lda opadd,x
        sta (t1),y
        dex
        bpl @a
        rts
@s:     ldy opoff,x
        lda opsub,x
        sta (t1),y
        dex
        bpl @s
        rts

.macro PATCH P, flag, inv
        lda #<P
        sta t1
        lda #>P
        sta t1+1
        lda flag
  .if inv
        eor #$ff
  .endif
        jsr patch4
.endmacro



; signed products t * S, t * C: (t + m)^2/4 - (t - m)^2/4 from the signed
; square tables, X = t + 128; the bases patched per frame (setsq)
.macro SPROD pl, ml, ph, mh
pl:     lda SQSL+256,x
        sec
ml:     sbc SQSL+256,x
        sta m0
ph:     lda SQSH+256,x
mh:     sbc SQSH+256,x
        sta m1
        asl a                   ; the sign, for the top byte
        lda #0
        adc #$ff
        eor #$ff
        sta ext
.endmacro

.macro ADD24 base, dst
        lda m0
        clc
        adc base
        sta dst
        lda m1
        adc base+1
        sta dst+1
        lda ext
        adc base+2
        sta dst+2
.endmacro

; patch the bases: +m at SQS + 256 + m, -m at SQS + 256 - m (m signed)
.macro SETBASE mag, sgn, pl, ml, ph, mh
        lda mag
        ldx #0
        bit sgn
        bpl :+
        eor #$ff
        clc
        adc #1
        ldx #$ff
        cmp #0
        bne :+
        inx                     ; -0
:       stx t0+1
        sta t0
        clc
        adc #<(SQSL+256)
        sta pl+1
        sta ph+1
        lda t0+1
        adc #>(SQSL+256)
        sta pl+2
        clc
        adc #>(SQSH-SQSL)
        sta ph+2
        lda #<(SQSL+256)
        sec
        sbc t0
        sta ml+1
        sta mh+1
        lda #>(SQSL+256)
        sbc t0+1
        sta ml+2
        clc
        adc #>(SQSH-SQSL)
        sta mh+2
.endmacro

dorows: lda #0
        sta nb
        SETBASE sv, sgns, dpl, dml, dph, dmh
        SETBASE cv, sgnc, upl, uml, uph, umh
        lda ref
        sec
        sbc #128
        sta ref2
        lda rows
        bne :+
        rts
:       ldy krow
drow:   lda hy,y                ; X = t + 128, t = height - (cy + wofs)
        sec
        sbc ref2
        tax
        SPROD dpl, dml, dph, dmh
        ADD24 kd, dd
        CULL dskip
        bit nearonly            ; near-only build: far rows keep last time's
        bpl :+
        lda dd+1
        cmp #<FARKEY
        lda dd+2
        sbc #>FARKEY
        bcc :+
        jmp dskip
:       SPROD upl, uml, uph, umh
        ADD24 ku, uu
        sty krow
        jsr project
        ldy krow
dskip:  lda kd                  ; next row
        clc
        adc sd
        sta kd
        lda kd+1
        adc sd+1
        sta kd+1
        lda kd+2
        adc sd+2
        sta kd+2
        lda ku
        clc
        adc su
        sta ku
        lda ku+1
        adc su+1
        sta ku+1
        lda ku+2
        adc su+2
        sta ku+2
        iny
        dec rows
        beq :+
        jmp drow
:       rts

; project row krow (d dd, u uu): height, top line, clip, sort in
project:
        LGM dd, ldl, ldh
        lda uu+2                ; |u|
        sta usg
        bpl :+
        lda #0
        sec
        sbc uu
        sta uu
        lda #0
        sbc uu+1
        sta uu+1
        lda #0
        sbc uu+2
        sta uu+2
:       lda dd+2                ; off the screen whatever its height:
        lsr a                   ; |u| > 1.25 d
        sta t0+1
        lda dd+1
        ror a
        sta t0
        lda dd
        ror a
        lsr t0+1
        ror t0
        ror a
        clc
        adc dd
        lda t0
        adc dd+1
        sta t0
        lda t0+1
        adc dd+2
        sta t0+1
        lda t0                  ; (1.25 d) >> 8 vs |u| >> 8
        cmp uu+1
        lda t0+1
        sbc uu+2
        bcs :+
        rts
:       LGM uu, lgl, lgh
        ; q2 = exp(lg u - lg d + LG400): 400 u / d, half lines
        lda lgl
        sec
        sbc ldl
        tay
        lda lgh
        sbc ldh
        tax
        tya
        clc
        adc #<(LG400+EXPOFF)
        sta ep
        txa
        adc #>(LG400+EXPOFF)
        bmi @q0
        cmp #>EXPN
        bcc @qok
        beq :+
@off:   rts                     ; far off the screen
:       lda ep
        cmp #<EXPN
        bcs @off
        lda #>EXPN
@qok:   clc
        adc #>expl
        sta ep+1
        ldy #0
        lda (ep),y
        sta q2l
        lda ep+1
        adc #>(exph-expl)
        sta ep+1
        lda (ep),y
        sta q2h
        jmp @h
@q0:    lda #0
        sta q2l
        sta q2h
@h:     lda ldl                 ; height: a table by log d
        sec
        sbc #<LDMIN
        sta ep
        lda ldh
        sbc #>LDMIN
        clc
        adc #>htab
        sta ep+1
        ldy #0
        lda (ep),y
        sta hh
        ; top = (CYL2 + 1 - h -/+ q2) >> 1
        lda #<(CYL2+1)
        sec
        sbc hh
        sta t0
        lda #>(CYL2+1)
        sbc #0
        sta t0+1
        lda usg
        bmi @bl
        lda t0
        sec
        sbc q2l
        sta t0
        lda t0+1
        sbc q2h
        jmp @sh
@bl:    lda t0
        clc
        adc q2l
        sta t0
        lda t0+1
        adc q2h
@sh:    cmp #$80
        ror a
        ror t0
        sta th
        lda t0
        sta tl
        lda th
        bmi @tneg
        bne @off2
        lda tl                  ; 0 <= top
        cmp #NLINES
        bcs @off2
        sta aa
        clc
        adc hh
        bcs @full
        cmp #NLINES
        bcc @eok
@full:  lda #NLINES
@eok:   sta ee
        jmp @store
@off2:  rts
@tneg:  lda tl                  ; top < 0: the end top + h must be > 0
        clc
        adc hh
        tay
        lda th
        adc #0
        bne @off2
        tya
        beq @off2
        cmp #NLINES
        bcc :+
        lda #NLINES
:       sta ee
        lda #0
        sta aa
@store: lda hh                  ; a far bar: into the held layer
        cmp #HHELD+1
        bcs :+
        jmp addheld
:       ldx nb                  ; the bar
        cpx #NBMAX
        bcc :+
        rts
:       lda dd+1                ; depth key (d >> 8)
        sta bkl,x
        lda dd+2
        sta bkh,x
        lda hh
        sta bhh,x
        tay
        lda aa
        sta ba,x
        sta t1+1
        lda ee
        sta be,x
        lda krow
        sta bk,x
        lda rbl,y               ; source base: ramp + h - 1 + top
        clc
        adc tl
        sta bsl,x
        lda rbh,y
        adc th
        sta bsh,x
        jmp insord
@x:     rts

; bar x (first line in t1+1) into screen order; nb + 1
insord: stx t1
        ldy nb
        beq @put
@ins:   lax ord-1,y
        lda ba,x
        cmp t1+1
        bcc @put
        beq @put
        txa
        sta ord,y
        dey
        bne @ins
@put:   lda t1
        sta ord,y
        inc nb
        rts

; far bars (d >= DHELD: all blue 1/4 on/off, under a line a frame) are
; projected on every other build; the builds between reuse them
FARKEY = DHELD >> 8


.segment "CODE"
; shift tables for lg: SHL page k = i << k, SHR page k = i >> (8 - k);
; NLZ = leading zeros
genshift:
        ldx #0
@i:     txa
        sta SHL,x
        asl a
        sta SHL+$100,x
        asl a
        sta SHL+$200,x
        asl a
        sta SHL+$300,x
        asl a
        sta SHL+$400,x
        asl a
        sta SHL+$500,x
        asl a
        sta SHL+$600,x
        asl a
        sta SHL+$700,x
        txa
        lsr a
        sta SHR+$700,x
        lsr a
        sta SHR+$600,x
        lsr a
        sta SHR+$500,x
        lsr a
        sta SHR+$400,x
        lsr a
        sta SHR+$300,x
        lsr a
        sta SHR+$200,x
        lsr a
        sta SHR+$100,x
        lda #0
        sta SHR,x
        txa
        ldy #0
        cmp #0
        beq @z
@c:     asl a
        bcs @z
        iny
        bne @c
@z:     tya
        sta NLZ,x
        inx
        bne @i
        rts

; -----------------------------------------------------------------------------
;  sweep: bars in screen order; on each stretch of lines the nearest of the
;  bars covering it (the active ones) is shown, until it ends or a nearer
;  one starts.  Each stretch becomes span records (emitpiece).
sweep:
        lda #0
        sta recp
        sta nblk
        sta inb
        sta cend
        sta nxt
        sta hp
        sta hcur
; bars in screen order; one that ends before the next starts is shown
; whole (the usual case), overlapping ones go through the cluster sweep
sw_top: ldy nxt
        cpy nb
        bcc :+
        jmp sw_done
:       lax ord,y
        lda be,x
        sta stop
        iny
        cpy nb
        bcs @fast
        stx t1
        lax ord,y               ; the next bar starts before this one ends?
        lda ba,x
        ldx t1
        cmp stop
        bcc @clus
@fast:  sty nxt
        lda ba,x
        sta ps0
        lda stop
        sta ps1
        jsr emitnear
        jmp sw_top
@clus:  ; the cluster: bars from nxt while they start before its end so far
@ce:    lax ord,y
        lda be,x
        cmp stop
        bcc :+
        sta stop
:       iny
        cpy nb
        bcs @cx
        lax ord,y
        lda ba,x
        cmp stop
        bcc @ce
@cx:    sty nbe
        lax nxt                 ; starts at its first bar
        lda ord,x
        tax
        lda ba,x
        sta cur
        lda #0
        sta nact
sw_loop:
@add:   ldy nxt                 ; bars starting at or above cur join
        cpy nbe
        bcs @addx
        ldx ord,y
        lda ba,x
        cmp cur
        beq :+
        bcs @addx
:       txa
        ldy nact
        sta act,y
        inc nact
        inc nxt
        jmp @add
@addx:  lda #$ff                ; the nearest active bar; drop ended ones
        sta own
        sta okl
        sta okh
        ldy #0
@scan:  cpy nact
        bcs @scx
        ldx act,y
        lda be,x
        cmp cur
        beq @drop
        bcc @drop
        lda bkl,x
        cmp okl
        lda bkh,x
        sbc okh
        bcs @nx
        stx own
        lda bkl,x
        sta okl
        lda bkh,x
        sta okh
@nx:    iny
        jmp @scan
@drop:  dec nact                ; the last one takes its place
        sty t0
        ldy nact
        lda act,y
        ldy t0
        sta act,y
        jmp @scan
@scx:   ldx own
        bpl @have
        ldy nxt                 ; none: skip to the next start, or done
        cpy nbe
        bcc :+
        jmp sw_top
:       ldx ord,y
        lda ba,x
        sta cur
        jmp sw_loop
@have:  lda be,x                ; until it ends, or a nearer bar starts
        sta stop
        ldy nxt
@up:    cpy nbe
        bcs @upx
        ldx ord,y
        lda ba,x
        cmp stop
        bcs @upx
        lda bkl,x
        cmp okl
        lda bkh,x
        sbc okh
        bcs @un
        lda ba,x
        sta stop
        jmp @upx
@un:    iny
        jmp @up
@upx:   lda cur
        sta ps0
        lda stop
        sta ps1
        ldx own
        jsr emitnear
        lda stop
        sta cur
        jmp sw_loop
sw_done:
        lda #NLINES             ; the far layer's lines after the last bar
        jsr heldto
        lda inb
        beq :+
        jsr close
:       lda recp
        sta nrec
        rts

; the far layer: [aa, ee) merged into the sorted intervals hs / he
addheld:
        ldy #0
@f:     cpy nh                  ; the first interval reaching aa
        bcs @ins
        lda he,y
        cmp aa
        bcs @ov
        iny
        bne @f
@ov:    lda hs,y                ; starts after ee: insert before it
        cmp ee
        beq @mg
        bcs @ins
@mg:    sty t0                  ; merge: absorb those starting <= ee
        cmp aa
        bcc :+
        lda aa
:       sta ps0
        lda ee
        sta ps1
@ab:    cpy nh
        bcs @ad
        lda hs,y
        cmp ee
        beq :+
        bcs @ad
:       lda he,y
        cmp ps1
        bcc :+
        sta ps1
:       iny
        bne @ab
@ad:    ldx t0                  ; [t0] = merged; shift the rest down
        lda ps0
        sta hs,x
        lda ps1
        sta he,x
        inx
@sl:    cpy nh
        bcs @sd
        lda hs,y
        sta hs,x
        lda he,y
        sta he,x
        iny
        inx
        bne @sl
@sd:    stx nh
        rts
@ins:   sty t0+1                ; insert at y
        ldx nh
        cpx #NHMAX
        bcs @x
@sr:    cpx t0+1
        beq @put
        lda hs-1,x
        sta hs,x
        lda he-1,x
        sta he,x
        dex
        jmp @sr
@put:   lda aa
        sta hs,x
        lda ee
        sta he,x
        inc nh
@x:     rts

; a near piece ps0..ps1 of bar x, the far layer's lines before it first
emitnear:
        stx t2
        lda ps0
        sta q0
        lda ps1
        sta q1
        lda q0
        jsr heldto
        lda q0
        sta ps0
        lda q1
        sta ps1
        ldx t2
        jsr emitpiece
        lda q1
        sta hcur
        rts

; the far layer's lines from hcur up to A
heldto: sta hlim
@l:     ldy hp
        cpy nh
        bcs @x
        lda he,y
        cmp hcur
        bcc @adv
        beq @adv
        lda hs,y
        cmp hlim
        bcs @x
        cmp hcur
        bcs :+
        lda hcur
:       sta ps0
        lda he,y
        cmp hlim
        bcc :+
        lda hlim
:       sta ps1
        ldx #$ff
        jsr emitpiece
        ldy hp
        lda he,y
        cmp hlim
        beq @adv
        bcs @x
@adv:   inc hp
        jmp @l
@x:     rts

; records for lines ps0..ps1 of bar x: black in between if the gap since
; the last piece is short, else a new block
emitpiece:
        stx pbx
        lda recp
        cmp #RECMAX-40
        bcc :+
        rts
:       lda inb
        beq @open
        lda ps0
        sec
        sbc cend
        beq @piece
        cmp #GAPMIN
        bcc @black
        jsr adjd
        sec
        sbc cend
        bcc @black
        cmp #GAPMIN
        bcc @black
        jsr close
        jmp @open
@black: lda cend
        sta aa
        jsr blackto
        jmp @piece
@open:  ldx nblk
        cpx #NBLKMAX
        bcc :+
        rts
:       jsr adjd
        sta aa
        clc
        adc #WTOPR-2            ; irq1 two lines before the block
        sta bline,x
        lda recp
        sec
        sbc #1
        sta bss,x
        inc nblk
        lda #1
        sta inb
        lda aa
        cmp ps0
        bcs @piece
        jsr blackto
@piece: ldx pbx
        bmi @held
        lda bsl,x               ; the bar's source base: ramp + h - 1 + top
        sta rp
        lda bsh,x
        sta rp+1
        lda #1
        bne @pb
@held:  lda #2                  ; the far bars' layer: one swatch
@pb:    sta pbar
        lda ps0
        sta aa
        lda ps1
        sta ee
        jsr spans
        lda ps1
        sta cend
@x:     rts

; a block's first line for a piece at ps0: not just below a sprite DMA line
; (irq2 would wait on one), so BAND0 < line <= BAND1 starts at BAND0
adjd:   lda ps0
        cmp #BAND0+1
        bcc :+
        cmp #BAND1+1
        bcs :+
        lda #BAND0
:       rts

; black from aa to ps0
blackto:
        lda #0
        sta pbar
        lda ps0
        sta ee
        jmp spans

; close the block: the exit record
close:  ldy recp
        lda #0
        sta recbuf,y
        sta recbuf+1,y
        lda #1
        sta recbuf+2,y
        lda #<(exit-1)
        sta recbuf+3,y
        lda #>(exit-1)
        sta recbuf+4,y
        tya
        clc
        adc #5
        sta recp
        lda #0
        sta inb
        rts

; records for lines aa..ee (pbar: 0 black, 1 the ramp rp / hh / top),
; split at the sprite DMA band
spans:  ldy recp
@lp:    lda aa
        cmp ee
        bcs @x
        tax
        lda BND,x               ; the line's region ends here (band edges)
        cmp ee
        bcc :+
        lda ee
:       sta bb
        lda VARX,x              ; its line code: normal / band, row parity
        tax
        lda pbar
        beq @blk
        cmp #2
        beq @hld
        lda rp                  ; src = base - end
        sec
        sbc bb
        sta recbuf,y
        lda rp+1
        sbc #0
        sta recbuf+1,y
        jmp @len
@blk:   lda #<zeros
        sta recbuf,y
        lda #>zeros
        sta recbuf+1,y
        jmp @len
@hld:   lda #<heldpg
        sta recbuf,y
        lda #>heldpg
        sta recbuf+1,y
@len:   lda bb
        sec
        sbc aa
        sta recbuf+2,y
        lda entl,x
        sta recbuf+3,y
        lda enth,x
        sta recbuf+4,y
        tya
        clc
        adc #5
        tay
        lda bb
        sta aa
        jmp @lp
@x:     sty recp
        rts

; signed squares: SQS[i] = SQ[|i - 384|], i = 0..767
gensqs: lda #0
        sta sqx
        sta sqx+1
@l:     lda sqx                 ; t0 = |i - 384|
        sec
        sbc #<384
        sta t0
        lda sqx+1
        sbc #>384
        sta t0+1
        bpl :+
        lda #0
        sec
        sbc t0
        sta t0
        lda #0
        sbc t0+1
        sta t0+1
:       lda #<SQL
        clc
        adc t0
        sta sp
        lda #>SQL
        adc t0+1
        sta sp+1
        lda #<SQSL
        clc
        adc sqx
        sta t1
        lda #>SQSL
        adc sqx+1
        sta t1+1
        ldy #0
        lda (sp),y
        sta (t1),y
        lda sp+1
        clc
        adc #>(SQH-SQL)
        sta sp+1
        lda t1+1
        clc
        adc #>(SQSH-SQSL)
        sta t1+1
        lda (sp),y
        sta (t1),y
        inc sqx
        bne :+
        inc sqx+1
:       lda sqx+1
        cmp #>768
        bne @l
        lda sqx
        cmp #<768
        bne @l
        rts

; per window line: where its region (above / on / below the ship's
; lines) ends, and its line code (0 NE, 1 NO, 2 BE, 3 BO)
genlines:
        ldx #0
@l:     lda #BAND0
        ldy #0
        cpx #BAND0
        bcc @p
        lda #BAND1
        ldy #2
        cpx #BAND1
        bcc @p
        lda #NLINES
        ldy #0
@p:     sta BND,x
        txa                     ; mock row x + 11 odd -> O
        and #1
        eor #1
        sty t0
        ora t0
        sta VARX,x
        inx
        cpx #NLINES
        bne @l
        rts

entl:   .byte <(l_ne-1), <(l_no-1), <(l_be-1), <(l_bo-1)
enth:   .byte >(l_ne-1), >(l_no-1), >(l_be-1), >(l_bo-1)

; =============================================================================
;  IRQs (in the screen's RAM, which the VIC never fetches: no badlines)
; =============================================================================
.segment "DISP"
irqtop: sta sav_a
        stx sav_x
        sty sav_y
        lda #$0b                ; DEN=0 across line $30: no badlines
        sta $d011
:       lda $d012
        cmp #$31
        bcc :-
        lda #$1b
        sta $d011
        inc fcount
        lda fcount
        and #1
        tax
        clc
        adc #>swtab             ; the line code's tables: this frame's parity
        sta c_ne+2
        sta g_ne+2
        sta c_no+2
        sta g_no+2
        sta c_be+2
        sta g_be+2
        sta c_bo+2
        sta g_bo+2
        lda glow,x
        sta $d026
        txa
        asl a
        sta it1
        lda shippd
        asl a
        asl a
        clc
        adc #SPRBLK
        adc it1
        sta SPRPTR
        adc #1
        sta SPRPTR+1
        lda #0
        sta blk
        lda nblkd
        beq @vbl
        ldx #0
        jsr setblk
        jmp irqout
@vbl:   jsr setvbl
irqout: asl $d019
        lda sav_a
        ldx sav_x
        ldy sav_y
        rti

glow:   .byte 1, 3              ; %11: white, cyan

setblk: lda dline,x
        sta $d012
        lda dss,x
        sta curs
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff
        rts
setvbl: lda #VBLLINE
        sta $d012
        lda #<irqvbl
        sta $fffe
        lda #>irqvbl
        sta $ffff
        rts

; vertical blank: take the built frame (records into page 1, blocks)
irqvbl: sta sav_a
        stx sav_x
        sty sav_y
        lda ready
        beq @no
        ldx nrec
        beq @nr
@cp:    lda recbuf-1,x
        sta a:$00ff,x
        dex
        bne @cp
@nr:    ldx nblk
        stx nblkd
        beq @nb
@cb:    lda bline-1,x
        sta dline-1,x
        lda bss-1,x
        sta dss-1,x
        dex
        bne @cb
@nb:    lda shipp
        sta shippd
        lda #0
        sta ready
        lda #1
        sta copied
@no:    lda #DENLINE
        sta $d012
        lda #<irqtop
        sta $fffe
        lda #>irqtop
        sta $ffff
        jmp irqout

; =============================================================================
;  Blocks: stable raster (double IRQ), then the spans off the stack
; =============================================================================

irq1:   sta sav_a
        stx sav_x
        sty sav_y
        lda #<irq2
        sta $fffe
        lda #>irq2
        sta $ffff
        inc $d012
        asl $d019
        tsx
        stx sav_s
        cli
        .repeat 14
        nop
        .endrep

irq2:   txs
        ldx #8
@w:     dex
        bne @w
        bit $00
        lda $d012
        cmp $d012
        beq @stable
@stable:
        .repeat HTUNE
        nop
        .endrep
        ldx curs                ; the block's records
        txs
blkgo:  pla
        sta src
        pla
        sta src+1
        pla
        tay
        rts                     ; into its first line

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

.macro beqnear T
        beq T
        .assert >* = >(T), error, "branch crosses a page"
.endmacro

; one line: the swatch at (src),y, its colour and idle byte by row parity
; (E: even mock row, O: odd) and frame parity (the tables' page, patched
; by irqtop).  27 cycles to the branch; padded to 63 (normal lines) or 56
; (the ship's lines: the VIC takes 7).  The span's last line branches to
; the next record (26 cycles, padded first: 63 / 56 in all).
        .align 256
l_ne:   lda (src),y             ; 5
        tax                     ; 7
c_ne:    lda swtab,x             ; 11
        sta $d021               ; 15
g_ne:   lda swtab+64,x          ; 19
        sta $bfff               ; 23
        dey                     ; 25
        beqnear nnext           ; 27 (28)
        fill 36                 ; 63
l_no:   lda (src),y
        tax
c_no:    lda swtab+32,x
        sta $d021
g_no:    lda swtab+96,x
        sta $bfff
        dey
        beqnear nnext
        fill 33
        jmp l_ne                ; 63
nnext:  fill 9                  ; 37
        pla                     ; 41
        sta src                 ; 44
        pla                     ; 48
        sta src+1               ; 51
        pla                     ; 55
        tay                     ; 57
        rts                     ; 63

l_be:   lda (src),y
        tax
c_be:    lda swtab,x
        sta $d021
g_be:    lda swtab+64,x
        sta $bfff
        dey
        beqnear bnext
        fill 29                 ; 56
l_bo:   lda (src),y
        tax
c_bo:    lda swtab+32,x
        sta $d021
g_bo:    lda swtab+96,x
        sta $bfff
        dey
        beqnear bnext
        fill 26
        jmp l_be                ; 56
bnext:  fill 2                  ; 30
        pla
        sta src
        pla
        sta src+1
        pla
        tay
        rts                     ; 56

; the block's end, reached like a line: black, then the next block's IRQ
exit:   fill 9
        lda #0
        sta $d021
        sta $bfff
exitd:  ldx sav_s
        txs
        inc blk
        ldx blk
        cpx nblkd
        bcs @last
        jsr setblk
        jmp irqout
@last:  jsr setvbl
        jmp irqout
