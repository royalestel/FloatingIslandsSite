NPARTS = 5
.macro PARTS_TABLE
        .byte 1, 200, <$080d, >$080d
        .byte 7, 45, <$080d, >$080d
        .byte 8, 22, <$080d, >$080d
        .byte 21, 22, <$080d, >$080d
        .byte 28, 22, <$080d, >$080d
.endmacro
