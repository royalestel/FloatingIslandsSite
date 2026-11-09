NPARTS = 2
.macro PARTS_TABLE
        .byte 1, 35, <$080d, >$080d
        .byte 2, 22, <$880d, >$880d
.endmacro
