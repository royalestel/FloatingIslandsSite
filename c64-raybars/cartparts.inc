NPARTS = 5
.macro PARTS_TABLE
        .byte 1, 193, <$080d, >$080d
        .byte 8, 45, <$080d, >$080d
        .byte 9, 22, <$080d, >$080d
        .byte 22, 22, <$080d, >$080d
        .byte 29, 22, <$080d, >$080d
.endmacro
