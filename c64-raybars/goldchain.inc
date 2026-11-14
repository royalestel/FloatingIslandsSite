; goldchain.inc -- what a routine of the NTSC gold sequence needs from the background loader (bgload.s, $02A8)
.ifndef CHAIN
CHAIN     = 0           ; -Wa -DCHAIN=1: a link of the cartridge's gold sequence (bgstep in the idle loop, bgswitch at the end)
.endif
NIRQ      = $ef         ; the line the next raster IRQ is set for: bgstep copies only when it is far enough away
BGSTEP    = $02A8
BGSWITCH  = $02AB
BGTICK    = $02AE       ; the tune, 5 calls in 6 frames
.macro SETIRQ           ; sta $d012, and keep NIRQ
        sta $d012
        .if ::CHAIN
        sta NIRQ
        .endif
.endmacro
