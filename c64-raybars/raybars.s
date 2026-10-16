; =============================================================================
;  RAYBARS -- real-time ray-traced raster bars for the Commodore 64 (PAL)
;  ca65 / cc65:   cl65 -t none -C raybars.cfg -o raybars.prg raybars.s
; =============================================================================
;
;  THE IDEA
;  A raster bar is a horizontal cylinder.  Seen from the side (the y/z plane)
;  every scanline of the bar is one point on a circle, and a single colour
;  register write per scanline draws it.  So the whole frame is just 200
;  bytes of colour, and almost all of the CPU is free to *compute* them.
;
;  THE OPTIMISATIONS THAT KEEP EVERYTHING 8-BIT
;   1. Camera at infinity (orthographic).  Every eye ray is (0,0,-1), so the
;      view vector is a constant and there is no perspective divide.
;   2. All angles are "brads": 256 = a full circle, so angle sums wrap for
;      free in an 8-bit register and every trig function is a 256-byte table.
;   3. A cylinder's normal at scanline i depends only on i:
;         sin(t_i) = (i + 0.5 - R) / R
;      so the normals of every bar are ONE constant 32-byte table.
;   4. With the normal at angle t and the light at angle p (both in the y/z
;      plane, x doesn't matter for an infinite cylinder):
;         diffuse   N.L           = cos(t - p)
;         specular  (refl(L).V)^n = cos(2t - p)^n
;         env map   refl(V)       = direction at angle 2t
;      i.e. three table lookups indexed by *sums of angles*.  No multiplies.
;   5. ONE point light at a fixed depth LZ.  Bars orbit within |z| <= 40 and
;      |dy| <= 108, so the light vector always fits in a byte, and its angle
;      atan(dy/dz) is done with logarithms: a subtraction, not a division.
;   6. Bar radius R = 16 << light distance (60..140), so the light direction
;      is computed once per bar (at its axis) instead of once per scanline.
;   7. Tables are stored twice (512 bytes) and page aligned, so "table[t-p]"
;      becomes "lda table+(-p),x" with -p patched into the operand once per
;      bar.  The inner loop is ~39 cycles per scanline, no adds for indexing.
;   8. The screen is blanked (DEN=0): no badlines, so the raster loop is a
;      plain 63-cycle loop writing $d020, and the border IS the canvas.
;
;  STRETCHED PALETTE  (after Daniel Krajzewicz, "Stretching the c64 Palette")
;  Each bar's ramp takes one colour from each VIC-II brightness level,
;  whatever its hue, so it gets every brightness step the chip has.
;  STYLE=1 (default): the article's "scaled split" -- two colour lines,
;  then one black line, counted outwards from each bar's centre.
;  STYLE=0: "Poor Man's Dithering" -- between neighbours, a mixed step with
;  colour A on even scanlines and B on odd ones, which a PAL TV blends:
;  7 colours -> 13 steps.  The shading loop is unrolled by two so even and
;  odd lines read their own ramp table at no extra cost per line.
;  FLICKER=1 also swaps the pair every frame (smoother on sharp screens,
;  but it flickers).
;
;  Intensity per scanline = diffuse(0..10) + env(0..2) + specular(0..6),
;  looked up in the ramp.  Diffuse+env tops out at 12, the brightest bar
;  colour, so only the specular term can reach WHITE.
;  The bars are depth-sorted and drawn back to front (painter's algorithm).
; =============================================================================

        .setcpu "6502"

; ---- tunables ---------------------------------------------------------------
FIRSTLINE = 50          ; raster line where irq1 fires
NLINES    = 184         ; scanlines of colour buffer shown (lines 52..235)
R         = 16          ; bar radius in scanlines
BARH      = 2*R         ; bar height (must match gen_tables.py)
NBARS     = 4
YMID      = 100         ; orbit axis, in colour-buffer lines
LZ        = 100         ; light depth: distance in front of the orbit axis
HTUNE     = 0           ; extra NOPs to slide the colour split into hblank
.ifndef STYLE           ; 1 = "scaled split": 2 colour lines, 1 black line
STYLE     = 1           ; 0 = dithered in-between steps (--asm-define STYLE=0)
.endif
.ifndef FLICKER         ; STYLE 0 only: also swap the mixed pairs every frame
FLICKER   = 0           ;     (cl65 ... --asm-define FLICKER=1)
.endif

; ---- hardware -------------------------------------------------------------
VIC_CTRL1  = $d011
VIC_RASTER = $d012
VIC_SPREN  = $d015
VIC_IRQ    = $d019
VIC_IRQEN  = $d01a
VIC_BORDER = $d020
VIC_BG     = $d021
CIA1_ICR   = $dc0d
CIA2_ICR   = $dd0d

; =============================================================================
.segment "ZEROPAGE"
orbit:   .res 1         ; orbit angle of bar 0
lang:    .res 1         ; light bob angle
scroll:  .res 1         ; environment map rotation
k:       .res 1         ; draw-order loop counter
bar:     .res 1         ; current bar number
dy:      .res 1         ; light - bar, vertical (signed)
dz:      .res 1         ; light - bar, depth    (unsigned)
lsv:     .res 1         ; light y offset this frame (signed)
yoff:    .res NBARS     ; bar y offset from YMID (signed)
bartop:  .res NBARS     ; first colour-buffer line of each bar
oldtop:  .res NBARS     ; ... and last frame's, for erasing
barz:    .res NBARS     ; bar depth (signed, + = toward camera)
zkey:    .res NBARS     ; depth ^ $80, for unsigned sorting
order:   .res NBARS     ; bar numbers, farthest first
tmp:     .res 1
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
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff

        lda #0
        sta VIC_BORDER
        sta VIC_BG
        sta VIC_SPREN           ; no sprites: they would steal raster cycles
        ldx #$7d                ; clear our zero page ($02-$7f)
@zp:    sta $02,x
        dex
        bpl @zp
        tax                     ; clear the colour buffer
@cb:    sta colbuf,x
        inx
        bne @cb

        lda #$0b                ; DEN=0: screen off, no badlines, bit 7 = 0
        sta VIC_CTRL1
        lda #FIRSTLINE
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQEN           ; raster IRQ only
        sta VIC_IRQ
        jsr update              ; trace the first frame
        cli
@idle:  jmp @idle               ; everything happens in the IRQ

nmi:    rti                     ; RESTORE key does nothing

; -----------------------------------------------------------------------------
;  shade: the per-scanline "ray tracer".  All operands marked *_op are
;  patched by update.  Carry stays clear: 10 + 2 + 6 never overflows.
; -----------------------------------------------------------------------------
.proc shade
        ldy #BARH-1             ; BARH is even: y alternates odd, even, ...
        clc
line:   ldx theta,y             ; ---- odd y ------------------------------
dif1 = * + 1
        lda difftab,x           ; diffuse   0..10
        ldx theta2,y
env1 = * + 1
        adc envtab,x            ; + env     0..2
spe1 = * + 1
        adc spectab,x           ; + specular 0..6
        tax
rampa = * + 1
        lda ramps,x             ; intensity -> colour (one parity's ramp)
dst1 = * + 1
        sta colbuf,y
        dey
        ldx theta,y             ; ---- even y -----------------------------
dif2 = * + 1
        lda difftab,x
        ldx theta2,y
env2 = * + 1
        adc envtab,x
spe2 = * + 1
        adc spectab,x
        tax
rampb = * + 1
        lda ramps,x             ; ... and the other parity's ramp
dst2 = * + 1
        sta colbuf,y
        dey
        bpl line
        rts
.endproc

; -----------------------------------------------------------------------------
;  atan2: A = atan(dy / dz) in brads, signed.  dz > 0 always.
;  atan(y/x) = atan(2^(log2 y - log2 x)): the division becomes a subtraction.
; -----------------------------------------------------------------------------
.proc atan2
        lda dy
        beq done                ; light level with the axis
        bpl pos
        eor #$ff
        clc
        adc #1
pos:    tax
        lda log2tab,x
        ldx dz
        sec
        sbc log2tab,x           ; log2|dy| - log2 dz
        bcc small
        tax
        lda atanhi,x            ; |dy| >= dz : 32..64
        jmp sign
small:  eor #$ff                ; carry is clear, so this negates
        adc #1
        tax
        lda atanlo,x            ; |dy| <  dz : 0..32
sign:   bit dy
        bpl done
        eor #$ff
        clc
        adc #1
done:   rts
.endproc

; compare-and-swap two entries of order[] by depth
.macro cswap i, j
        .local ok
        ldx order+i
        ldy order+j
        lda zkey,y
        cmp zkey,x
        bcs ok
        stx order+j
        sty order+i
ok:
.endmacro

; =============================================================================
;  update: trace one frame into colbuf.  Runs in the vertical blank,
;  ~5000 cycles of the ~6800 available (measured with simulate.py).
; =============================================================================
.proc update
        ; ---- 1. erase last frame's bars (unrolled, 5 cycles per line) ------
        lda #0
        ldx #NBARS-1
erase:  ldy oldtop,x
        .repeat ::BARH, I
        sta colbuf+I,y
        .endrep
        dex
        bpl erase

        ; ---- 2. animate ------------------------------------------------------
        inc orbit               ; bars orbit the x axis, 1 brad/frame
        lda lang
        clc
        adc #3                  ; light bobs at a different speed
        sta lang
        dec scroll              ; environment spins the other way

        ; ---- 3. place the bars on their orbit (120 degrees apart) -----------
        ldx #NBARS-1
place:  lda orbit
        clc
        adc phase,x
        tay
        lda ysin,y
        sta yoff,x
        clc
        adc #YMID-R
        sta bartop,x
        lda zcos,y
        sta barz,x
        eor #$80
        sta zkey,x
        dex
        bpl place

        ; ---- 4. depth sort, farthest first (4-element sorting network) ------
        ldx #NBARS-1
init:   txa
        sta order,x
        dex
        bpl init
        cswap 0, 1
        cswap 2, 3
        cswap 0, 2
        cswap 1, 3
        cswap 1, 2

        ; ---- 5. light position ---------------------------------------------
        ldy lang
        lda lsin,y
        sta lsv

        ; ---- 6. trace each bar, back to front ---------------------------------
        ldx #0
next:   stx k
        lda order,x
        sta bar
        tax
        lda lsv                 ; vector from the bar's axis to the light
        sec
        sbc yoff,x
        sta dy                  ; -108..108
        lda #LZ
        sec
        sbc barz,x
        sta dz                  ; 60..140
        jsr atan2               ; A = p, angle of the light seen from the bar

        eor #$ff                ; -p
        clc
        adc #1
        sta shade::dif1         ; patch: diffuse  table[t  - p]
        sta shade::dif2
        sta shade::spe1         ; patch: specular table[2t - p]
        sta shade::spe2
        lda scroll
        sta shade::env1         ; patch: env map  table[2t + scroll]
        sta shade::env2
        ldx bar
        lda bartop,x
        sta oldtop,x
        sta shade::dst1         ; patch: where in colbuf this bar lands
        sta shade::dst2

.if ::STYLE = 0
        ; Pick even/odd ramps so the mix pattern follows SCREEN lines, not
        ; bar lines: the first line shaded is top+BARH-1 (odd y).
        clc
        adc #1                  ; parity of top + odd y
.if ::FLICKER
        eor orbit               ; swap the pair every frame
.endif
        and #1
        lsr
        ror                     ; carry -> bit 7 ...
        lsr
        lsr                     ; ... -> bit 5: 0 or 32, even or odd table
        sta tmp
        txa
        lsr
        ror
        ror                     ; bar * 64 (bar < 4)
        ora tmp
        sta shade::rampa
        eor #32                 ; the other line uses the other table
        sta shade::rampb
        jsr shade
.else
        txa                     ; one ramp for every line
        lsr
        ror
        ror                     ; bar * 64 (bar < 4)
        sta shade::rampa
        sta shade::rampb
        jsr shade

        ; Black separators: every third line, counted outwards from the
        ; bar's centre so the pattern is symmetric (..cc0cc|cc0cc..).
        ; They are part of the bar, so they also hide what is behind it.
        ldx bar
        ldy bartop,x
        lda #0
        .repeat ::BARH, I
          .if I < ::BARH/2
            .if (::BARH/2 - 1 - I) .mod 3 = 2
        sta colbuf+I,y
            .endif
          .else
            .if (I - ::BARH/2) .mod 3 = 2
        sta colbuf+I,y
            .endif
          .endif
        .endrep
.endif

        ldx k
        inx
        cpx #NBARS
        bne next
        rts
.endproc

; =============================================================================
;  Stable raster (double IRQ) + the 63-cycle colour loop.  Lives in its own
;  page-aligned segment so no branch here ever crosses a page.
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

        ldx #0                  ; ---- one colour per scanline -----------
@line:  lda colbuf,x            ; 4
        sta VIC_BORDER          ; 4
        ldy #9                  ; 2
@dly:   dey                     ;
        bne @dly                ; 9*5-1 = 44
        nop                     ; 2
        inx                     ; 2
        cpx #NLINES             ; 2
        bne @line               ; 3     = 63 cycles = 1 PAL line
        .assert >@line = >*, error, "raster loop crosses a page"

        lda #0
        sta VIC_BORDER
        lda #<irq1
        sta $fffe
        lda #>irq1
        sta $ffff
        lda #FIRSTLINE
        sta VIC_RASTER
        asl VIC_IRQ

        jsr update              ; trace the next frame in the vblank

        lda save_a
        ldx save_x
        ldy save_y
        rti

; =============================================================================
.segment "TABLES"

        .include "tables.inc"   ; difftab/spectab/envtab first: page aligned

        .assert <difftab = 0, error, "difftab must be page aligned"
        .assert <spectab = 0, error, "spectab must be page aligned"
        .assert <envtab  = 0, error, "envtab must be page aligned"

phase:  .byte 0, 64, 128, 192    ; bars 90 degrees apart on the orbit

; Stretched colour ramps, 64 bytes per bar: even-line table, odd-line
; table, 32 entries each.  Generated from the 6-colour lists in gen_tables.py.
.segment "RAMPS"
ramps:
.if STYLE = 0
        .include "ramps_dither.inc"
.else
        .include "ramps_split.inc"
.endif
        .assert <ramps = 0, error, "ramps must be page aligned"

; =============================================================================
.segment "BSS"
colbuf: .res 256                ; one colour per scanline
        .assert <colbuf = 0, error, "colbuf must be page aligned"
