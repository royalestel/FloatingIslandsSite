NPARTS = 5
.macro PARTS_TABLE
        .byte 1, 200, <$080d, >$080d
        .byte 7, 22, <$880d, >$880d
        .byte 8, 22, <$880d, >$880d
        .byte 21, 22, <$880d, >$880d
        .byte 31, 22, <$080d, >$080d
.endmacro
