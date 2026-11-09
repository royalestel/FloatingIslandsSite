NPARTS = 5
.macro PARTS_TABLE
        .byte 1, 200, <$080d, >$080d
        .byte 7, 150, <$080d, >$080d
        .byte 8, 150, <$080d, >$080d
        .byte 21, 150, <$080d, >$080d
        .byte 31, 22, <$080d, >$080d
.endmacro
