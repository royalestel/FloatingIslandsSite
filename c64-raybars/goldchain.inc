; goldchain.inc -- what a routine of the NTSC gold sequence needs from the background loader (bgload.s, $0300)
.ifndef CHAIN
CHAIN     = 0           ; -Wa -DCHAIN=1: a link of the cartridge's gold sequence (bgstep in the idle loop, bgswitch at the end)
.endif
NIRQ      = $ef         ; the line the next raster IRQ is set for: bgstep copies only when it is far enough away
BGSTEP    = $0300
BGSWITCH  = $0303
BGTICK    = $0306       ; the tune, 5 calls in 6 frames
.macro SETIRQ           ; sta $d012, and keep NIRQ
        sta $d012
        .if ::CHAIN
        sta NIRQ
        .endif
.endmacro
