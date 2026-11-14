; bgzp.inc -- the background loader's zero page (bgload.s)
NIRQ    = $ef           ; the line the next raster IRQ is set for (every chained routine keeps it)
JOB     = $f0           ; 2: the record being copied ($8000 + 8 x its index)
DONE    = $f2           ; 2: bytes of it copied
SRC     = $f4           ; 2
DST     = $f6           ; 2
NOTICK  = $ed           ; != 0: bgswitch does not call the tune (the old routine did, this frame)
rec     = $e7           ; 7: the record being copied
n       = $ee           ; bytes this chunk
