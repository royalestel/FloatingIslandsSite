NPARTS = 5
.macro PARTS_TABLE
        .byte 1, 200, <$080d, >$080d
        .byte 8, 21, <$880d, >$880d
        .byte 9, 22, <$880d, >$880d
        .byte 20, 22, <$880d, >$880d
        .byte 26, 22, <$080d, >$080d
.endmacro
