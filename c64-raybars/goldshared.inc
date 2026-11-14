; goldshared.inc -- the tables every gold routine shares, in one fixed layout (the NTSC cartridge loads them once, at $E000)
.segment "SHARED"
        .include "tables.inc"   ; spectab, theta2, log2/atan ... (page aligned)
        .include "light.inc"    ; lkbase0..4, lx4tab, lyofftab, ball
        .include "orbit.inc"    ; orby, orbz, orbsize, balls
        .assert <spectab = 0, error, "spectab must be page aligned"
