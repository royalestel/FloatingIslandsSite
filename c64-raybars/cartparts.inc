NPARTS = 5
.macro PARTS_TABLE
        .byte 1, 200, <$080d, >$080d
        .byte 7, 21, <$880d, >$880d
        .byte 8, 22, <$880d, >$880d
        .byte 19, 22, <$880d, >$880d
        .byte 25, 22, <$080d, >$080d
.endmacro
