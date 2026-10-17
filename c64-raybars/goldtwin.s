; =============================================================================
;  GOLDTWIN -- the orbiting light, its gold bar, and a second gold bar
;  approaching from the distance below it
;  cl65 -t none -C raybars.cfg -o goldtwin.prg goldtwin.s
; =============================================================================
;
;  Bar A, the light sprite and everything about them work as in
;  goldorbit.s.  New here is bar B, low on the screen:
;
;   * It comes from the distance: depth z goes 6 -> 1, so its height on
;     screen is H = 48/z, from 8 lines up to 48 (twice bar A), speeding up
;     as it nears.  Rows are scaled nearest-neighbour: screen row j of B
;     shows source row floor(j * 24 / H) of the gold pattern (an 8.8 fixed
;     point step per row, no division).
;   * It brightens as it nears: 4 levels of 16-entry colour remaps.  At
;     first, yellow shows as brown and white as dark grey; then yellow as
;     orange and white as light grey; full colour from about bar A's size.
;     The traced highlight is dimmed the same way.
;   * At the camera it near-clips: the near plane cuts it from the middle
;     outward (the nearest part first) until only black is left; then a
;     short pause and it comes again.
;   * It tilts with bar A and reflects the same orbiting light, seen from
;     its own depth.
;
;  ORGANISATION
;  The interrupts only draw: the top IRQ (the badline trick), bar A, bar B.
;  The main loop builds the next sprite and bar A as soon as bar A has
;  been drawn (bar B's IRQ cuts in), and the next bar B once bar B has been
;  drawn: the sprite is ready by line DENLINE, bar A before its IRQ, bar B
;  before line BTOP-2.  The sprite never comes below
;  line 226, so it never steals cycles inside bar B, which therefore needs
;  no timing patch.
;
;  MEMORY: the VIC uses bank 2 ($8000-$bfff, RAM here): sprites at $8000 /
;  $8040, screen (and sprite pointer) at $8400, idle byte $bfff = 0.
; =============================================================================

        .setcpu "6502"

ROWS      = 29          ; bar A display rows: 24 lines + 4 lines of slant + 1
ROWSB     = 52          ; bar B display rows: 48 lines + 4 lines of slant
SEGS      = 5           ; horizontal segments per row
SEGSIZE   = 8           ; bytes per segment: lda #c (2) sta $d020 (3) sta $d021 (3)
PADSIZE   = 7           ; bytes of padding per row
ROWSIZE   = SEGS*SEGSIZE + PADSIZE  ; 47 bytes, both bars
BARH      = 24          ; gold lines
BMAX      = 48          ; bar B's largest height
PAD       = 6           ; black rows above and below the gold
YBASE     = 140         ; raster line of bar A's top row when centred
BARMID    = 14          ; bar A centre, in rows below its top row
BTOP      = 229         ; raster line of bar B's first display row
BCENTRE   = BTOP + 2 + BMAX/2   ; bar B's centre line
DENLINE   = 44          ; top IRQ: clear DEN before raster line $30
HTUNE     = 0           ; extra NOPs to line the first split up with hblank
.ifndef STEAL
STEAL     = 4           ; bar A rows shortened on sprite lines: 4 or 6
.endif
VICBANK   = $8000       ; VIC bank 2
SPRBUF0   = VICBANK + $0000     ; sprite double buffer (pointers 0 / 1)
SPRBUF1   = VICBANK + $0040
SPRPTR    = VICBANK + $0400 + $03f8     ; sprite 0 pointer (screen at +$0400)
IDLEBYTE  = VICBANK + $3fff

.if STEAL = 4
SKIP      = 2
.elseif STEAL = 6
SKIP      = 3
.else
.error "STEAL must be 4 or 6"
.endif
OP_BCS    = $b0
OP_BCC    = $90

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

theta2    = theta2_12   ; per-line reflection angle of a 24-line bar

; =============================================================================
.segment "ZEROPAGE"
orbit:   .res 1         ; bar A bob angle
tilt:    .res 1         ; see-saw angle (both bars)
lxa:     .res 1         ; light sideways drift angle
q:       .res 1         ; light orbit angle
fcount:  .res 1         ; frame counter
frame:   .res 1         ; set by bar A's IRQ: time to build the next sprite + bar A
y0:      .res 1         ; raster line of bar A's top row (next frame)
ly:      .res 1         ; sprite Y register (next frame)
lx4:     .res 1         ; sprite X register / 4 (next frame)
lptr:    .res 1         ; sprite pointer (next frame)
ldy_:    .res 1         ; light - bar A centre, vertical (from the orbit)
ldz:     .res 1         ; light depth (+ = toward the camera)
dy:      .res 1         ; atan2 inputs
dz:      .res 1
sb:      .res 1         ; this line's specular level
jstart:  .res 1         ; first sprite row hidden behind bar A
src:     .res 2         ; ball frame being copied
dst:     .res 2         ; sprite buffer being written
kb:      .res SEGS      ; start index into the columns for each segment
thr0:    .res SEGS      ; white on even display rows if sb >= thr0
thr1:    .res SEGS      ; white on odd display rows if sb >= thr1
bt:      .res 1         ; bar B phase (0..255)
bh:      .res 1         ; bar B height on screen
bidx:    .res 1         ; bar B's first row in bcol
jlo:     .res 1         ; rows jlo..jhi-1 are near-clipped
jhi:     .res 1
acc:     .res 1         ; nearest-neighbour source row, fraction
bthr:    .res SEGS      ; bar B: white if the spec level >= bthr
minthr:  .res 1         ; the lowest of those
wcol:    .res 1         ; the highlight's white, dimmed for bar B's distance
clo:     .res 1         ; near-clip zone, in bcol positions
chi:     .res 1
frameb:  .res 1         ; set by bar B's IRQ: time to build bar B
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
        lda #$7f                ; silence the CIA timer interrupts
        sta CIA1_ICR
        sta CIA2_ICR
        lda CIA1_ICR
        lda CIA2_ICR
        lda #$35                ; RAM + I/O, no BASIC/KERNAL ROM
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
        sta IDLEBYTE            ; idle-state graphics byte: all background
        ldx #$7d                ; clear our zero page ($02-$7f)
@zp:    sta $02,x
        dex
        bpl @zp
        ldx #(2*PAD+BARH)*SEGS-1        ; clear bar A's columns
@col:   sta cols,x
        dex
        bpl @col
        ldx #BCOLSIZE-1                 ; and bar B's
@colb:  sta bcol,x
        dex
        bpl @colb
        lda #1
        sta VIC_SPREN
        sta VIC_SPRMC           ; multicolour
        lda #0
        sta VIC_SPRDW
        sta VIC_SPRDH
        lda #7                  ; %10: yellow
        sta VIC_SPR0C
        lda #8                  ; %01: orange rim
        sta VIC_SPRMC0
        lda #1                  ; %11: white core
        sta VIC_SPRMC1

        lda #$0b                ; DEN=0 for now; bit 7 = 0
        sta VIC_CTRL1
        lda #DENLINE
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQEN           ; raster IRQ only
        sta VIC_IRQ
        jsr update              ; first frame
        jsr updateb
        cli

main:   lda frame               ; bar A has been drawn: build the next
        beq main                ; sprite and bar A (bar B's IRQ may cut in)
        lda #0
        sta frame
        jsr update
:       lda frameb              ; bar B has been drawn: build the next bar B
        beq :-
        lda #0
        sta frameb
        jsr updateb
        jmp main

nmi:    rti                     ; RESTORE key does nothing

; -----------------------------------------------------------------------------
;  atan2: A = angle of (dy, dz) in brads, all four quadrants:
;  0 = toward the camera, +64 = straight down, 128 = straight behind.
; -----------------------------------------------------------------------------
.proc atan2
        lda dz
        bpl zpos
        eor #$ff
        clc
        adc #1
zpos:   tay                     ; |dz|
        lda dy
        bpl ypos
        eor #$ff
        clc
        adc #1
ypos:   tax                     ; |dy|
        lda log2tab,x
        sec
        sbc log2tab,y           ; log2|dy| - log2|dz|
        bcc small
        tax
        lda atanhi,x            ; |dy| >= |dz| : 32..64
        jmp quad
small:  eor #$ff                ; carry is clear, so this negates
        adc #1
        tax
        lda atanlo,x            ; |dy| <  |dz| : 0..32
quad:   bit dz
        bpl front
        eor #$ff                ; behind: 128 - m
        sec
        adc #128
front:  bit dy
        bpl done
        eor #$ff
        clc
        adc #1
done:   rts
.endproc

; =============================================================================
;  update: the sprite and bar A for the next frame
; =============================================================================
.proc update
        ; ---- 1. animate ------------------------------------------------------
        inc fcount
        inc orbit               ; bar A bobs up and down
        inc tilt                ; both bars rock
        inc q                   ; light orbits bar A
        lda fcount
        and #1
        bne :+
        inc lxa                 ; and drifts sideways at half speed
:

        ; ---- 2. bar A -----------------------------------------------------------
        ldy orbit
        lda lsin,y              ; +-44 ...
        cmp #$80
        ror                     ; ... /2 = +-22 lines
        clc
        adc #::YBASE
        sta y0
        ldy tilt
        .repeat ::SEGS, K
        lda .ident(.sprintf("lkbase%d", K)),y
        sta kb+K
        .endrep

        ; ---- 3. the light ---------------------------------------------------------
        ldy q
        lda orby,y
        sta ldy_                ; light - bar A centre, vertical: +-40
        lda orbz,y
        sta ldz                 ; light depth: +-40, + = in front
        lda y0
        clc
        adc #::BARMID - 11      ; sprite centre row is 10, shown from Y+1
        clc
        adc ldy_
        sta ly
        ldy lxa
        lda lx4tab,y
        sta lx4

        ; ---- 4. the ball: pick its size, hide what is behind bar A -------------
        jsr drawball
::ballready:                    ; (the simulator checks the time to here)

        ; ---- 5. bar A's highlight angle ------------------------------------------
        lda ldy_
        sta dy
        lda ldz
        sta dz
        jsr atan2
        eor #$ff
        clc
        adc #1                  ; -p
        sta spe_op

        ; ---- 6. per segment: distance from the light -> highlight threshold ----
        .repeat ::SEGS, K
        lda lx4
        sec
        sbc #5 + 20*K
        bcs :+
        eor #$ff
        adc #1                  ; carry clear: negate
:       lsr
        lsr
        lsr                     ; drop = |a| / 32 pixels
        clc
        adc #1
        sta thr0+K
        adc #2
        sta thr1+K
        sta bthr+K              ; bar B: solid white from drop + 3
        .endrep
        lda y0
        and #1
        beq evenrows
        .repeat ::SEGS, K       ; odd y0: swap the thresholds
        lda thr0+K
        ldx thr1+K
        sta thr1+K
        stx thr0+K
        .endrep
evenrows:

        ; ---- 7. bar A's columns: gold + traced highlight per segment -------------
        ldy #::BARH-1
line:   ldx theta2,y
spe_op = * + 1
        lda spectab,x           ; specular 0..8
        cmp #1
        bcc dark
        jmp lit
dark:   lda gold,y              ; no highlight anywhere on this line
        .repeat ::SEGS, K
        sta cols + (2*K)*36 + ::PAD,y
        sta cols + (2*K+1)*36 + ::PAD,y
        .endrep
        dey
        bmi :+
        jmp line
:       jmp patch
lit:    sta sb
        .repeat ::SEGS, K
        lda sb
        cmp thr0+K
        lda #1                  ; white (flags from cmp kept)
        bcs :+
        lda gold,y
:       sta cols + (2*K)*36 + ::PAD,y
        lda sb
        cmp thr1+K
        lda #1
        bcs :+
        lda gold,y
:       sta cols + (2*K+1)*36 + ::PAD,y
        .endrep
        dey
        bmi patch
        jmp line

        ; ---- 8. patch bar A's 145 colours -------------------------------------
patch:
        .repeat ::SEGS, K
        ldx kb+K
          .repeat ::ROWS, RR
        lda cols + (2*K + (RR .mod 2))*36 + RR,x
        sta block + RR*::ROWSIZE + K*::SEGSIZE + 1
          .endrep
        .endrep

        ; ---- 9. shorten bar A's rows where the sprite steals cycles -----------
        lda y0
        sec
        sbc ly
        tax                     ; y0 - ly
        .repeat ::ROWS, RR
        txa
        clc
        adc #RR
        cmp #21
        lda #OP_BCS             ; normal row (flags from cmp kept)
        bcs :+
        lda #OP_BCC             ; sprite row: STEAL cycles shorter
:       sta block + RR*::ROWSIZE + ::SEGS*::SEGSIZE
        .endrep
        rts
.endproc

; -----------------------------------------------------------------------------
;  drawball: the ball at its size into the back buffer, rows behind bar A
;  blanked while the light is behind it.
; -----------------------------------------------------------------------------
.proc drawball
        ldy q
        lda orbsize,y
        lsr
        lsr                     ; size * 64 = (size >> 2) * 256 + (size & 3) * 64
        clc
        adc #>balls
        sta src+1
        lda orbsize,y
        and #3
        lsr
        ror
        ror
        clc
        adc #<balls
        sta src
        bcc :+
        inc src+1
:       lda lptr
        bne use0
        lda #<((SPRBUF1 - VICBANK)/64)  ; shown now: buffer 0 -> draw into 1
        sta lptr
        lda #>SPRBUF1
        ldx #<SPRBUF1
        bne setdst
use0:   lda #<((SPRBUF0 - VICBANK)/64)
        sta lptr
        lda #>SPRBUF0
        ldx #<SPRBUF0
setdst: sta dst+1
        stx dst

        lda #$80                ; in front: nothing hidden
        bit ldz
        bpl front
        lda lx4                 ; segment under the ball: (lx4 + 5) / 20
        clc
        adc #5
        ldx #0
:       cmp #20
        bcc :+
        sbc #20
        inx
        cpx #::SEGS-1
        bne :-
:       lda #6
        sec
        sbc kb,x                ; off = 6 - kb
        clc
        adc y0
        sec
        sbc ly
        sec
        sbc #1
front:  sta jstart

        ldx #0                  ; sprite row j
        ldy #0                  ; byte offset 3j
row:    txa
        sec
        sbc jstart
        cmp #24
        bcc hide
        lda (src),y
        sta (dst),y
        iny
        lda (src),y
        sta (dst),y
        iny
        lda (src),y
        sta (dst),y
        iny
        jmp nextrow
hide:   lda #0
        sta (dst),y
        iny
        sta (dst),y
        iny
        sta (dst),y
        iny
nextrow:
        inx
        cpx #21
        bne row
        rts
.endproc

; =============================================================================
;  updateb: bar B for the next frame
; =============================================================================
.proc updateb
        inc bt
        ldy bt
        lda bhtab,y
        sta bh
        lda blevtab,y           ; brightness level 0..3 ...
        asl
        asl
        asl
        asl                     ; ... * 16: which remap table
        sta dim_op
        lda bh                  ; near-clip window, centred
        lsr
        sta jhi
        sec
        sbc bcliptab,y
        bcs :+
        lda #0
:       sta jlo
        lda jhi
        clc
        adc bcliptab,y
        sta jhi

        ; ---- clear the column (the bar changes size every frame) -------------
        lda #0
        ldx #::BMAX-1
:       sta bcol+::PAD,x
        dex
        bpl :-
        lda bh
        bne :+
        jmp patchb              ; nothing to draw
:

        ; ---- the light seen from bar B ----------------------------------------
        ; vertical: light centre line (y0 + BARMID + ldy_) - BCENTRE, clamped
        lda y0
        clc
        adc #::BARMID
        clc
        adc ldy_
        sta dy                  ; light centre line, 92..216
        lda #<::BCENTRE
        sec
        sbc dy                  ; distance above bar B, 39..163
        cmp #128
        bcc :+
        lda #127
:       eor #$ff
        clc
        adc #1
        sta dy                  ; light - bar B: negative (above)
        ; depth: light z - bar B z.  Bar B comes from 90 behind the light's
        ; orbit plane to 75 in front of it; once it is nearer the camera
        ; than the light, dz < 0 and the highlight rides to the top rows.
        lda ldz
        clc
        adc bzofftab,y
        bvc :+
        lda bzofftab,y          ; overflow: clamp toward the offset's sign
        bmi neg
        lda #127
        bne :+
neg:    lda #$81
:       sta dz
        jsr atan2
        eor #$ff
        clc
        adc #1
        sta bspe_op

        ; ---- the 24 source lines: specular level, dimmed gold ---------------
        ; (the highlight is laid on per segment afterwards, see overlay)
        ldy #::BARH-1
sl:     ldx theta2,y
bspe_op = * + 1
        lda spectab,x
        sta specb,y
        ldx gold,y
dim_op = * + 1
        lda dims,x              ; dimmed by distance
        sta srccol,y
        dey
        bpl sl
        lda dim_op              ; the highlight's white, dimmed the same way
        ora #1
        tax
        lda dims,x
        sta wcol

        ; ---- nearest-neighbour expand to bh rows ---------------------------
        ; row j shows source line acc.hi; acc += 24/bh (8.8) per row
        ldx bh
        lda nnsteplo,x
        sta steplo_op
        lda nnstephi,x
        sta stephi_op
        lda #::BMAX             ; first row: PAD + (BMAX - bh) / 2
        sec
        sbc bh
        lsr
        clc
        adc #::PAD
        sta bidx
        tax
        clc
        adc bh
        sta end_op
        lda #0
        sta acc
        tay                     ; Y = acc.hi = source line
        clc                     ; stays clear: acc.hi never passes 24
el:     lda srccol,y            ; 4
        sta bcol,x              ; 5
        tya                     ; 2
        sta rsrc,x              ; 5   which source line this row shows
        inx                     ; 2
        lda acc                 ; 3
steplo_op = * + 1
        adc #0                  ; 2
        sta acc                 ; 3
        tya                     ; 2
stephi_op = * + 1
        adc #0                  ; 2
        tay                     ; 2
end_op = * + 1
        cpx #0                  ; 2   (carry: x < end, so clear)
        bne el                  ; 3   = 37 cycles per row

        ; ---- near-clip: rows jlo..jhi-1 go black -------------------------------
        lda bidx                ; clip zone in bcol positions, for the overlay
        clc
        adc jlo
        sta clo
        lda bidx
        clc
        adc jhi
        sta chi
        lda jhi
        sec
        sbc jlo
        beq patchb
        tay                     ; how many
        ldx clo
        lda #0
:       sta bcol,x
        inx
        dey
        bne :-

        ; ---- patch bar B's 260 colours ------------------------------------------
patchb:
        .repeat ::SEGS, K
        ldx kb+K
          .repeat ::ROWSB, RR
        lda bcol + RR,x
        sta blockb + RR*::ROWSIZE + K*::SEGSIZE + 1
          .endrep
        .endrep
        lda bh
        bne :+
        rts
:

        ; ---- the highlight, per segment ------------------------------------------
        ; Segment k shows white where the row's specular level reaches its
        ; threshold bthr_k = drop_k + 3: thickest nearest the light.  Only
        ; rows where the lowest threshold is met are visited; the white goes
        ; straight into the speedcode (row r = bcol position - kb_k).
        lda bthr
        .repeat ::SEGS-1, K
        cmp bthr+K+1
        bcc :+
        lda bthr+K+1
:
        .endrep
        sta minthr
        ldx bidx
ov:     cpx clo                 ; near-clipped rows stay black
        bcc test
        cpx chi
        bcs test
        jmp next
test:   ldy rsrc,x
        lda specb,y
        cmp minthr
        bcs lit
        jmp next
lit:    sta sb
        .repeat ::SEGS, K
        lda sb
        cmp bthr+K
        bcc :+
        txa
        sec
        sbc kb+K                ; display row
        tay
        lda rowlo,y
        sta dst
        lda rowhi,y
        sta dst+1
        ldy #K*::SEGSIZE
        lda wcol
        sta (dst),y
:
        .endrep
next:   inx
        cpx end_op
        beq :+
        jmp ov
:       rts
.endproc

; =============================================================================
;  Top IRQ: keep DEN clear across raster line $30 (no badlines this frame),
;  set it again before line $33.  Sprite registers for this frame.
; =============================================================================
irqtop: pha
        lda #$0b                ; DEN=0
        sta VIC_CTRL1
        lda ly
        sta VIC_SPR0Y
        lda lptr
        sta SPRPTR
        lda lx4
        asl
        asl                     ; x = 4 * lx4, carry = bit 8
        sta VIC_SPR0X
        lda #0
        rol
        sta VIC_SPRXHI
:       lda VIC_RASTER
        cmp #$31                ; until line $30 is completely over
        bne :-
        lda #$1b                ; DEN=1: window opens at line $33
        sta VIC_CTRL1
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff
        lda y0
        sec
        sbc #2                  ; 2 lines above bar A
        sta VIC_RASTER
        asl VIC_IRQ
        pla
        rti

; =============================================================================
;  Bar A: stable raster (double IRQ), 29 rows of speedcode
; =============================================================================
.segment "RASTER"

irq1:   sta save_a
        stx save_x
        sty save_y
        lda #<irq2
        sta $fffe
        lda #>irq2
        sta $ffff
        inc VIC_RASTER          ; second IRQ on the very next line
        asl VIC_IRQ
        tsx
        cli
        .repeat 14              ; irq2 lands inside these: 0-1 cycle jitter
        nop
        .endrep

irq2:   txs                     ; throw away irq2's stack frame
        ldx #8
@w:     dex
        bne @w
        bit $00
        lda VIC_RASTER
        cmp VIC_RASTER          ; still the same line?
        beq @stable             ; +1 cycle if so: last cycle of jitter gone
@stable:
        .repeat HTUNE
        nop
        .endrep
        clc                     ; the row branches rely on carry clear

block:                          ; ---- bar A ---------------------------------
        .repeat ROWS, RR
          .repeat SEGS
        lda #0                  ; 2   patched every frame
        sta VIC_BORDER          ; 4   border part of the line
        sta VIC_BG              ; 4   display-window part
          .endrep               ;     = 10 cycles = 80 pixels per segment
        .byte OP_BCS, SKIP      ; 2   (bcc: 3, skipping ahead)
        inc $ea                 ; 5
        nop                     ; 6
        nop
        nop                     ; 5*10 + 13 = 63 cycles = 1 PAL line
        .assert >(block + RR*ROWSIZE + SEGS*SEGSIZE + 2) = >(block + RR*ROWSIZE + SEGS*SEGSIZE + 2 + SKIP), error, "row branch crosses a page"
        .endrep
blockend:
        .assert blockend - block = ROWS*ROWSIZE, error, "row size mismatch"
        lda #0
        sta VIC_BORDER
        sta VIC_BG
        lda #<irqb1             ; next: bar B
        sta $fffe
        lda #>irqb1
        sta $ffff
        lda #BTOP - 2
        sta VIC_RASTER
        asl VIC_IRQ
        inc frame               ; main loop: build the next sprite + bar A
        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
;  Bar B: stable raster (double IRQ), 52 rows of speedcode.  The sprite is
;  never on these lines, so every row is a plain 63 cycles.
; =============================================================================
irqb1:  sta save_a
        stx save_x
        sty save_y
        lda #<irqb2
        sta $fffe
        lda #>irqb2
        sta $ffff
        inc VIC_RASTER
        asl VIC_IRQ
        tsx
        cli
        .repeat 14
        nop
        .endrep

irqb2:  txs
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
        nop                     ; same 2 cycles as bar A's clc

blockb:                         ; ---- bar B ---------------------------------
        .repeat ROWSB
          .repeat SEGS
        lda #0                  ; 2   patched every frame
        sta VIC_BORDER          ; 4
        sta VIC_BG              ; 4
          .endrep
        bit $ea                 ; 3
        nop                     ; 10
        nop
        nop
        nop
        nop                     ; 5*10 + 13 = 63 cycles
        .endrep
blockbend:
        .assert blockbend - blockb = ROWSB*ROWSIZE, error, "bar B row size mismatch"
        lda #0
        sta VIC_BORDER
        sta VIC_BG
        lda #<irqtop            ; next: the top of the next frame
        sta $fffe
        lda #>irqtop
        sta $ffff
        lda #DENLINE
        sta VIC_RASTER
        asl VIC_IRQ
        inc frameb              ; main loop: build the next bar B
        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
.segment "TABLES"

        .include "tables.inc"   ; spectab etc. (page aligned, see gen_tables)
        .include "light.inc"    ; lkbase0..4, lx4tab
        .include "orbit.inc"    ; orby, orbz, orbsize, balls
        .include "twin.inc"     ; bar B: height, clip, brightness, depth, steps
        .assert <spectab = 0, error, "spectab must be page aligned"

.segment "RAMPS"
; Distance dimming for bar B: 4 levels x 16 colours (0 = full brightness).
; Gold colours used: 0 black, 1 white, 7 yellow, 8 orange, 9 brown,
; 10 light red, 12 grey, 15 light grey.
dims:   ;      0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
        .byte  0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,15   ; full
        .byte  0,15, 2, 3, 4, 5, 6, 8, 9, 9, 8,11,11,13,14,12   ; yellow -> orange, white -> light grey
        .byte  0,12, 2, 3, 4, 5, 6, 8, 9, 0, 9,11, 9,13,14,11   ; ... white -> grey, the rest darker
        .byte  0,11, 2, 3, 4, 5, 6, 9, 0, 0, 9,11, 0,13,14, 9   ; yellow -> brown, white -> dark grey
        .assert <dims = 0, error, "dims must be page aligned"
; The gold bar, top to bottom, one C64 colour per scanline (24 lines).
gold:   .byte 9,8,12,7,7,0,9,8,15,7,7,1,7,1,7,0,0,0,9,12,10,12,8,9
        .assert * - gold = BARH, error, "gold must have one colour per line"
; Bar B's display rows: address of each row's first lda #immediate
rowlo:  .repeat ROWSB, RR
        .byte <(blockb + RR*ROWSIZE + 1)
        .endrep
rowhi:  .repeat ROWSB, RR
        .byte >(blockb + RR*ROWSIZE + 1)
        .endrep

; =============================================================================
.segment "BSS"
; Bar A: 2 columns per segment (even / odd display rows), 36 entries each:
; 6 black, 24 gold-or-white, 6 black.
cols:   .res 2*SEGS*(2*PAD+BARH)
; Bar B: one column: 6 black, up to 48 bar rows, black after.
BCOLSIZE = PAD + ROWSB + 6
bcol:   .res BCOLSIZE
srccol: .res BARH               ; bar B's 24 source lines, dimmed
specb:  .res BARH               ; ... and their specular levels
rsrc:   .res BCOLSIZE           ; source line of each bcol position
        .assert * <= VICBANK, error, "program runs into the VIC bank"
