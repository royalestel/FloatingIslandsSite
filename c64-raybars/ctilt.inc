; ---- copy 0: buffer 0, frame parity 0, column page $8a00
tcopy_0:
tE_0:
tE_0_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tE_0_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tE_0_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tE_0_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tE_0_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tE_0_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021
        lda dodtab,y
        sta $d011
tX_0:
tX_0_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tX_0_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tX_0_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tX_0_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tX_0_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tX_0_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021
        lda dodtab,y
        sta $d011
tY_0:
tY_0_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tY_0_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tY_0_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tY_0_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tY_0_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tY_0_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021
        cpy tb1v
        beqnear tYb_0
        jmp tX_0
tYb_0: nop
tN_0_2:
tN_0_2_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_2_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_2_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_2_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_2_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tN_0_2_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021,x
        lda #$1b           ; (phase 2: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_0_2_c
        jmp texit
tN_0_2_c: nop
tN_0_3:
tN_0_3_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_3_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_3_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_3_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_3_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tN_0_3_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021,x
        lda #$1c           ; (phase 3: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_0_3_c
        jmp texit
tN_0_3_c: nop
tN_0_0:
tN_0_0_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_0_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_0_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_0_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_0_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tN_0_0_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021,x
        lda #$1d           ; (phase 0: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_0_0_c
        jmp texit
tN_0_0_c: nop
tN_0_1:
tN_0_1_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_1_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_1_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_1_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tN_0_1_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tN_0_1_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021,x
        lda #$1a           ; (phase 1: window line mod 4)
        sta $d011
        cpy src
        beqnear tN_0_1_x
        jmp tN_0_2
tN_0_1_x: jmp texit
tA_0_0:
tA_0_0_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_0_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_0_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_0_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_0_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tA_0_0_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021,x
        lda #$1d
        sta $d011
        cpy tb0v
        bnenear tA_0_0_c
        jmp tE_0
tA_0_0_c: nop
tA_0_1:
tA_0_1_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_1_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_1_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_1_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_1_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tA_0_1_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021,x
        lda #$1a
        sta $d011
        nop
        nop
        nop
        nop
tA_0_2:
tA_0_2_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_2_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_2_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_2_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_2_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tA_0_2_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021,x
        lda #$1b
        sta $d011
        nop
        nop
        nop
        nop
tA_0_3:
tA_0_3_o1 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_3_o2 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_3_o3 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_3_o4 := * + 1
        lda $8a00 + 8,y
        sta $d021
tA_0_3_o5 := * + 1
        lda $8a00 + 8,y
        sta $d021
        iny
tA_0_3_o0 := * + 1
        lda $8a00 + 8,y
        sta $d021,x
        lda #$1c
        sta $d011
        bit $ea
        nop
        jmp tA_0_0
; ---- copy 1: buffer 0, frame parity 1, column page $8b00
tcopy_1:
tE_1:
tE_1_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tE_1_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tE_1_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tE_1_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tE_1_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tE_1_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021
        lda dodtab,y
        sta $d011
tX_1:
tX_1_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tX_1_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tX_1_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tX_1_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tX_1_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tX_1_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021
        lda dodtab,y
        sta $d011
tY_1:
tY_1_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tY_1_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tY_1_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tY_1_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tY_1_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tY_1_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021
        cpy tb1v
        beqnear tYb_1
        jmp tX_1
tYb_1: nop
tN_1_2:
tN_1_2_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_2_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_2_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_2_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_2_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tN_1_2_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021,x
        lda #$1b           ; (phase 2: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_1_2_c
        jmp texit
tN_1_2_c: nop
tN_1_3:
tN_1_3_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_3_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_3_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_3_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_3_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tN_1_3_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021,x
        lda #$1c           ; (phase 3: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_1_3_c
        jmp texit
tN_1_3_c: nop
tN_1_0:
tN_1_0_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_0_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_0_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_0_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_0_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tN_1_0_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021,x
        lda #$1d           ; (phase 0: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_1_0_c
        jmp texit
tN_1_0_c: nop
tN_1_1:
tN_1_1_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_1_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_1_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_1_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tN_1_1_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tN_1_1_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021,x
        lda #$1a           ; (phase 1: window line mod 4)
        sta $d011
        cpy src
        beqnear tN_1_1_x
        jmp tN_1_2
tN_1_1_x: jmp texit
tA_1_0:
tA_1_0_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_0_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_0_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_0_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_0_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tA_1_0_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021,x
        lda #$1d
        sta $d011
        cpy tb0v
        bnenear tA_1_0_c
        jmp tE_1
tA_1_0_c: nop
tA_1_1:
tA_1_1_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_1_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_1_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_1_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_1_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tA_1_1_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021,x
        lda #$1a
        sta $d011
        nop
        nop
        nop
        nop
tA_1_2:
tA_1_2_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_2_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_2_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_2_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_2_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tA_1_2_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021,x
        lda #$1b
        sta $d011
        nop
        nop
        nop
        nop
tA_1_3:
tA_1_3_o1 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_3_o2 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_3_o3 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_3_o4 := * + 1
        lda $8b00 + 8,y
        sta $d021
tA_1_3_o5 := * + 1
        lda $8b00 + 8,y
        sta $d021
        iny
tA_1_3_o0 := * + 1
        lda $8b00 + 8,y
        sta $d021,x
        lda #$1c
        sta $d011
        bit $ea
        nop
        jmp tA_1_0
; ---- copy 2: buffer 1, frame parity 0, column page $8c00
tcopy_2:
tE_2:
tE_2_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tE_2_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tE_2_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tE_2_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tE_2_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tE_2_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021
        lda dodtab,y
        sta $d011
tX_2:
tX_2_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tX_2_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tX_2_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tX_2_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tX_2_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tX_2_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021
        lda dodtab,y
        sta $d011
tY_2:
tY_2_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tY_2_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tY_2_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tY_2_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tY_2_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tY_2_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021
        cpy tb1v
        beqnear tYb_2
        jmp tX_2
tYb_2: nop
tN_2_2:
tN_2_2_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_2_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_2_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_2_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_2_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tN_2_2_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021,x
        lda #$1b           ; (phase 2: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_2_2_c
        jmp texit
tN_2_2_c: nop
tN_2_3:
tN_2_3_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_3_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_3_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_3_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_3_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tN_2_3_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021,x
        lda #$1c           ; (phase 3: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_2_3_c
        jmp texit
tN_2_3_c: nop
tN_2_0:
tN_2_0_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_0_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_0_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_0_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_0_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tN_2_0_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021,x
        lda #$1d           ; (phase 0: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_2_0_c
        jmp texit
tN_2_0_c: nop
tN_2_1:
tN_2_1_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_1_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_1_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_1_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tN_2_1_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tN_2_1_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021,x
        lda #$1a           ; (phase 1: window line mod 4)
        sta $d011
        cpy src
        beqnear tN_2_1_x
        jmp tN_2_2
tN_2_1_x: jmp texit
tA_2_0:
tA_2_0_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_0_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_0_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_0_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_0_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tA_2_0_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021,x
        lda #$1d
        sta $d011
        cpy tb0v
        bnenear tA_2_0_c
        jmp tE_2
tA_2_0_c: nop
tA_2_1:
tA_2_1_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_1_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_1_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_1_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_1_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tA_2_1_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021,x
        lda #$1a
        sta $d011
        nop
        nop
        nop
        nop
tA_2_2:
tA_2_2_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_2_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_2_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_2_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_2_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tA_2_2_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021,x
        lda #$1b
        sta $d011
        nop
        nop
        nop
        nop
tA_2_3:
tA_2_3_o1 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_3_o2 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_3_o3 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_3_o4 := * + 1
        lda $8c00 + 8,y
        sta $d021
tA_2_3_o5 := * + 1
        lda $8c00 + 8,y
        sta $d021
        iny
tA_2_3_o0 := * + 1
        lda $8c00 + 8,y
        sta $d021,x
        lda #$1c
        sta $d011
        bit $ea
        nop
        jmp tA_2_0
; ---- copy 3: buffer 1, frame parity 1, column page $8d00
tcopy_3:
tE_3:
tE_3_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tE_3_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tE_3_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tE_3_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tE_3_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tE_3_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021
        lda dodtab,y
        sta $d011
tX_3:
tX_3_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tX_3_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tX_3_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tX_3_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tX_3_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tX_3_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021
        lda dodtab,y
        sta $d011
tY_3:
tY_3_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tY_3_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tY_3_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tY_3_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tY_3_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tY_3_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021
        cpy tb1v
        beqnear tYb_3
        jmp tX_3
tYb_3: nop
tN_3_2:
tN_3_2_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_2_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_2_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_2_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_2_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tN_3_2_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021,x
        lda #$1b           ; (phase 2: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_3_2_c
        jmp texit
tN_3_2_c: nop
tN_3_3:
tN_3_3_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_3_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_3_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_3_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_3_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tN_3_3_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021,x
        lda #$1c           ; (phase 3: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_3_3_c
        jmp texit
tN_3_3_c: nop
tN_3_0:
tN_3_0_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_0_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_0_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_0_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_0_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tN_3_0_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021,x
        lda #$1d           ; (phase 0: window line mod 4)
        sta $d011
        cpy src
        bnenear tN_3_0_c
        jmp texit
tN_3_0_c: nop
tN_3_1:
tN_3_1_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_1_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_1_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_1_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tN_3_1_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tN_3_1_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021,x
        lda #$1a           ; (phase 1: window line mod 4)
        sta $d011
        cpy src
        beqnear tN_3_1_x
        jmp tN_3_2
tN_3_1_x: jmp texit
tA_3_0:
tA_3_0_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_0_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_0_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_0_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_0_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tA_3_0_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021,x
        lda #$1d
        sta $d011
        cpy tb0v
        bnenear tA_3_0_c
        jmp tE_3
tA_3_0_c: nop
tA_3_1:
tA_3_1_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_1_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_1_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_1_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_1_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tA_3_1_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021,x
        lda #$1a
        sta $d011
        nop
        nop
        nop
        nop
tA_3_2:
tA_3_2_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_2_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_2_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_2_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_2_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tA_3_2_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021,x
        lda #$1b
        sta $d011
        nop
        nop
        nop
        nop
tA_3_3:
tA_3_3_o1 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_3_o2 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_3_o3 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_3_o4 := * + 1
        lda $8d00 + 8,y
        sta $d021
tA_3_3_o5 := * + 1
        lda $8d00 + 8,y
        sta $d021
        iny
tA_3_3_o0 := * + 1
        lda $8d00 + 8,y
        sta $d021,x
        lda #$1c
        sta $d011
        bit $ea
        nop
        jmp tA_3_0
        .align 256
tent:
        .word tN_0_0, tN_1_0, tN_2_0, tN_3_0
        .word tN_0_1, tN_1_1, tN_2_1, tN_3_1
        .word tN_0_2, tN_1_2, tN_2_2, tN_3_2
        .word tN_0_3, tN_1_3, tN_2_3, tN_3_3
        .word tA_0_0, tA_1_0, tA_2_0, tA_3_0
        .word tA_0_1, tA_1_1, tA_2_1, tA_3_1
        .word tA_0_2, tA_1_2, tA_2_2, tA_3_2
        .word tA_0_3, tA_1_3, tA_2_3, tA_3_3
        .word tE_0, tE_1, tE_2, tE_3
tcopyl: .byte <tcopy_0, <tcopy_1, <tcopy_2, <tcopy_3
tcopyh: .byte >tcopy_0, >tcopy_1, >tcopy_2, >tcopy_3
trell:
        .byte <(tE_0_o0 - tcopy_0), <(tX_0_o0 - tcopy_0), <(tY_0_o0 - tcopy_0), <(tN_0_2_o0 - tcopy_0), <(tN_0_3_o0 - tcopy_0), <(tN_0_0_o0 - tcopy_0), <(tN_0_1_o0 - tcopy_0), <(tA_0_0_o0 - tcopy_0), <(tA_0_1_o0 - tcopy_0), <(tA_0_2_o0 - tcopy_0), <(tA_0_3_o0 - tcopy_0)
        .byte <(tE_0_o1 - tcopy_0), <(tX_0_o1 - tcopy_0), <(tY_0_o1 - tcopy_0), <(tN_0_2_o1 - tcopy_0), <(tN_0_3_o1 - tcopy_0), <(tN_0_0_o1 - tcopy_0), <(tN_0_1_o1 - tcopy_0), <(tA_0_0_o1 - tcopy_0), <(tA_0_1_o1 - tcopy_0), <(tA_0_2_o1 - tcopy_0), <(tA_0_3_o1 - tcopy_0)
        .byte <(tE_0_o2 - tcopy_0), <(tX_0_o2 - tcopy_0), <(tY_0_o2 - tcopy_0), <(tN_0_2_o2 - tcopy_0), <(tN_0_3_o2 - tcopy_0), <(tN_0_0_o2 - tcopy_0), <(tN_0_1_o2 - tcopy_0), <(tA_0_0_o2 - tcopy_0), <(tA_0_1_o2 - tcopy_0), <(tA_0_2_o2 - tcopy_0), <(tA_0_3_o2 - tcopy_0)
        .byte <(tE_0_o3 - tcopy_0), <(tX_0_o3 - tcopy_0), <(tY_0_o3 - tcopy_0), <(tN_0_2_o3 - tcopy_0), <(tN_0_3_o3 - tcopy_0), <(tN_0_0_o3 - tcopy_0), <(tN_0_1_o3 - tcopy_0), <(tA_0_0_o3 - tcopy_0), <(tA_0_1_o3 - tcopy_0), <(tA_0_2_o3 - tcopy_0), <(tA_0_3_o3 - tcopy_0)
        .byte <(tE_0_o4 - tcopy_0), <(tX_0_o4 - tcopy_0), <(tY_0_o4 - tcopy_0), <(tN_0_2_o4 - tcopy_0), <(tN_0_3_o4 - tcopy_0), <(tN_0_0_o4 - tcopy_0), <(tN_0_1_o4 - tcopy_0), <(tA_0_0_o4 - tcopy_0), <(tA_0_1_o4 - tcopy_0), <(tA_0_2_o4 - tcopy_0), <(tA_0_3_o4 - tcopy_0)
        .byte <(tE_0_o5 - tcopy_0), <(tX_0_o5 - tcopy_0), <(tY_0_o5 - tcopy_0), <(tN_0_2_o5 - tcopy_0), <(tN_0_3_o5 - tcopy_0), <(tN_0_0_o5 - tcopy_0), <(tN_0_1_o5 - tcopy_0), <(tA_0_0_o5 - tcopy_0), <(tA_0_1_o5 - tcopy_0), <(tA_0_2_o5 - tcopy_0), <(tA_0_3_o5 - tcopy_0)
trelh:
        .byte >(tE_0_o0 - tcopy_0), >(tX_0_o0 - tcopy_0), >(tY_0_o0 - tcopy_0), >(tN_0_2_o0 - tcopy_0), >(tN_0_3_o0 - tcopy_0), >(tN_0_0_o0 - tcopy_0), >(tN_0_1_o0 - tcopy_0), >(tA_0_0_o0 - tcopy_0), >(tA_0_1_o0 - tcopy_0), >(tA_0_2_o0 - tcopy_0), >(tA_0_3_o0 - tcopy_0)
        .byte >(tE_0_o1 - tcopy_0), >(tX_0_o1 - tcopy_0), >(tY_0_o1 - tcopy_0), >(tN_0_2_o1 - tcopy_0), >(tN_0_3_o1 - tcopy_0), >(tN_0_0_o1 - tcopy_0), >(tN_0_1_o1 - tcopy_0), >(tA_0_0_o1 - tcopy_0), >(tA_0_1_o1 - tcopy_0), >(tA_0_2_o1 - tcopy_0), >(tA_0_3_o1 - tcopy_0)
        .byte >(tE_0_o2 - tcopy_0), >(tX_0_o2 - tcopy_0), >(tY_0_o2 - tcopy_0), >(tN_0_2_o2 - tcopy_0), >(tN_0_3_o2 - tcopy_0), >(tN_0_0_o2 - tcopy_0), >(tN_0_1_o2 - tcopy_0), >(tA_0_0_o2 - tcopy_0), >(tA_0_1_o2 - tcopy_0), >(tA_0_2_o2 - tcopy_0), >(tA_0_3_o2 - tcopy_0)
        .byte >(tE_0_o3 - tcopy_0), >(tX_0_o3 - tcopy_0), >(tY_0_o3 - tcopy_0), >(tN_0_2_o3 - tcopy_0), >(tN_0_3_o3 - tcopy_0), >(tN_0_0_o3 - tcopy_0), >(tN_0_1_o3 - tcopy_0), >(tA_0_0_o3 - tcopy_0), >(tA_0_1_o3 - tcopy_0), >(tA_0_2_o3 - tcopy_0), >(tA_0_3_o3 - tcopy_0)
        .byte >(tE_0_o4 - tcopy_0), >(tX_0_o4 - tcopy_0), >(tY_0_o4 - tcopy_0), >(tN_0_2_o4 - tcopy_0), >(tN_0_3_o4 - tcopy_0), >(tN_0_0_o4 - tcopy_0), >(tN_0_1_o4 - tcopy_0), >(tA_0_0_o4 - tcopy_0), >(tA_0_1_o4 - tcopy_0), >(tA_0_2_o4 - tcopy_0), >(tA_0_3_o4 - tcopy_0)
        .byte >(tE_0_o5 - tcopy_0), >(tX_0_o5 - tcopy_0), >(tY_0_o5 - tcopy_0), >(tN_0_2_o5 - tcopy_0), >(tN_0_3_o5 - tcopy_0), >(tN_0_0_o5 - tcopy_0), >(tN_0_1_o5 - tcopy_0), >(tA_0_0_o5 - tcopy_0), >(tA_0_1_o5 - tcopy_0), >(tA_0_2_o5 - tcopy_0), >(tA_0_3_o5 - tcopy_0)
        .assert tE_1_o0 - tcopy_1 = tE_0_o0 - tcopy_0, error, "the copies differ"
        .assert tX_1_o0 - tcopy_1 = tX_0_o0 - tcopy_0, error, "the copies differ"
        .assert tY_1_o0 - tcopy_1 = tY_0_o0 - tcopy_0, error, "the copies differ"
        .assert tN_1_2_o0 - tcopy_1 = tN_0_2_o0 - tcopy_0, error, "the copies differ"
        .assert tN_1_3_o0 - tcopy_1 = tN_0_3_o0 - tcopy_0, error, "the copies differ"
        .assert tN_1_0_o0 - tcopy_1 = tN_0_0_o0 - tcopy_0, error, "the copies differ"
        .assert tN_1_1_o0 - tcopy_1 = tN_0_1_o0 - tcopy_0, error, "the copies differ"
        .assert tA_1_0_o0 - tcopy_1 = tA_0_0_o0 - tcopy_0, error, "the copies differ"
        .assert tA_1_1_o0 - tcopy_1 = tA_0_1_o0 - tcopy_0, error, "the copies differ"
        .assert tA_1_2_o0 - tcopy_1 = tA_0_2_o0 - tcopy_0, error, "the copies differ"
        .assert tA_1_3_o0 - tcopy_1 = tA_0_3_o0 - tcopy_0, error, "the copies differ"
        .assert tE_1_o1 - tcopy_1 = tE_0_o1 - tcopy_0, error, "the copies differ"
        .assert tX_1_o1 - tcopy_1 = tX_0_o1 - tcopy_0, error, "the copies differ"
        .assert tY_1_o1 - tcopy_1 = tY_0_o1 - tcopy_0, error, "the copies differ"
        .assert tN_1_2_o1 - tcopy_1 = tN_0_2_o1 - tcopy_0, error, "the copies differ"
        .assert tN_1_3_o1 - tcopy_1 = tN_0_3_o1 - tcopy_0, error, "the copies differ"
        .assert tN_1_0_o1 - tcopy_1 = tN_0_0_o1 - tcopy_0, error, "the copies differ"
        .assert tN_1_1_o1 - tcopy_1 = tN_0_1_o1 - tcopy_0, error, "the copies differ"
        .assert tA_1_0_o1 - tcopy_1 = tA_0_0_o1 - tcopy_0, error, "the copies differ"
        .assert tA_1_1_o1 - tcopy_1 = tA_0_1_o1 - tcopy_0, error, "the copies differ"
        .assert tA_1_2_o1 - tcopy_1 = tA_0_2_o1 - tcopy_0, error, "the copies differ"
        .assert tA_1_3_o1 - tcopy_1 = tA_0_3_o1 - tcopy_0, error, "the copies differ"
        .assert tE_1_o2 - tcopy_1 = tE_0_o2 - tcopy_0, error, "the copies differ"
        .assert tX_1_o2 - tcopy_1 = tX_0_o2 - tcopy_0, error, "the copies differ"
        .assert tY_1_o2 - tcopy_1 = tY_0_o2 - tcopy_0, error, "the copies differ"
        .assert tN_1_2_o2 - tcopy_1 = tN_0_2_o2 - tcopy_0, error, "the copies differ"
        .assert tN_1_3_o2 - tcopy_1 = tN_0_3_o2 - tcopy_0, error, "the copies differ"
        .assert tN_1_0_o2 - tcopy_1 = tN_0_0_o2 - tcopy_0, error, "the copies differ"
        .assert tN_1_1_o2 - tcopy_1 = tN_0_1_o2 - tcopy_0, error, "the copies differ"
        .assert tA_1_0_o2 - tcopy_1 = tA_0_0_o2 - tcopy_0, error, "the copies differ"
        .assert tA_1_1_o2 - tcopy_1 = tA_0_1_o2 - tcopy_0, error, "the copies differ"
        .assert tA_1_2_o2 - tcopy_1 = tA_0_2_o2 - tcopy_0, error, "the copies differ"
        .assert tA_1_3_o2 - tcopy_1 = tA_0_3_o2 - tcopy_0, error, "the copies differ"
        .assert tE_1_o3 - tcopy_1 = tE_0_o3 - tcopy_0, error, "the copies differ"
        .assert tX_1_o3 - tcopy_1 = tX_0_o3 - tcopy_0, error, "the copies differ"
        .assert tY_1_o3 - tcopy_1 = tY_0_o3 - tcopy_0, error, "the copies differ"
        .assert tN_1_2_o3 - tcopy_1 = tN_0_2_o3 - tcopy_0, error, "the copies differ"
        .assert tN_1_3_o3 - tcopy_1 = tN_0_3_o3 - tcopy_0, error, "the copies differ"
        .assert tN_1_0_o3 - tcopy_1 = tN_0_0_o3 - tcopy_0, error, "the copies differ"
        .assert tN_1_1_o3 - tcopy_1 = tN_0_1_o3 - tcopy_0, error, "the copies differ"
        .assert tA_1_0_o3 - tcopy_1 = tA_0_0_o3 - tcopy_0, error, "the copies differ"
        .assert tA_1_1_o3 - tcopy_1 = tA_0_1_o3 - tcopy_0, error, "the copies differ"
        .assert tA_1_2_o3 - tcopy_1 = tA_0_2_o3 - tcopy_0, error, "the copies differ"
        .assert tA_1_3_o3 - tcopy_1 = tA_0_3_o3 - tcopy_0, error, "the copies differ"
        .assert tE_1_o4 - tcopy_1 = tE_0_o4 - tcopy_0, error, "the copies differ"
        .assert tX_1_o4 - tcopy_1 = tX_0_o4 - tcopy_0, error, "the copies differ"
        .assert tY_1_o4 - tcopy_1 = tY_0_o4 - tcopy_0, error, "the copies differ"
        .assert tN_1_2_o4 - tcopy_1 = tN_0_2_o4 - tcopy_0, error, "the copies differ"
        .assert tN_1_3_o4 - tcopy_1 = tN_0_3_o4 - tcopy_0, error, "the copies differ"
        .assert tN_1_0_o4 - tcopy_1 = tN_0_0_o4 - tcopy_0, error, "the copies differ"
        .assert tN_1_1_o4 - tcopy_1 = tN_0_1_o4 - tcopy_0, error, "the copies differ"
        .assert tA_1_0_o4 - tcopy_1 = tA_0_0_o4 - tcopy_0, error, "the copies differ"
        .assert tA_1_1_o4 - tcopy_1 = tA_0_1_o4 - tcopy_0, error, "the copies differ"
        .assert tA_1_2_o4 - tcopy_1 = tA_0_2_o4 - tcopy_0, error, "the copies differ"
        .assert tA_1_3_o4 - tcopy_1 = tA_0_3_o4 - tcopy_0, error, "the copies differ"
        .assert tE_1_o5 - tcopy_1 = tE_0_o5 - tcopy_0, error, "the copies differ"
        .assert tX_1_o5 - tcopy_1 = tX_0_o5 - tcopy_0, error, "the copies differ"
        .assert tY_1_o5 - tcopy_1 = tY_0_o5 - tcopy_0, error, "the copies differ"
        .assert tN_1_2_o5 - tcopy_1 = tN_0_2_o5 - tcopy_0, error, "the copies differ"
        .assert tN_1_3_o5 - tcopy_1 = tN_0_3_o5 - tcopy_0, error, "the copies differ"
        .assert tN_1_0_o5 - tcopy_1 = tN_0_0_o5 - tcopy_0, error, "the copies differ"
        .assert tN_1_1_o5 - tcopy_1 = tN_0_1_o5 - tcopy_0, error, "the copies differ"
        .assert tA_1_0_o5 - tcopy_1 = tA_0_0_o5 - tcopy_0, error, "the copies differ"
        .assert tA_1_1_o5 - tcopy_1 = tA_0_1_o5 - tcopy_0, error, "the copies differ"
        .assert tA_1_2_o5 - tcopy_1 = tA_0_2_o5 - tcopy_0, error, "the copies differ"
        .assert tA_1_3_o5 - tcopy_1 = tA_0_3_o5 - tcopy_0, error, "the copies differ"
        .assert tE_2_o0 - tcopy_2 = tE_0_o0 - tcopy_0, error, "the copies differ"
        .assert tX_2_o0 - tcopy_2 = tX_0_o0 - tcopy_0, error, "the copies differ"
        .assert tY_2_o0 - tcopy_2 = tY_0_o0 - tcopy_0, error, "the copies differ"
        .assert tN_2_2_o0 - tcopy_2 = tN_0_2_o0 - tcopy_0, error, "the copies differ"
        .assert tN_2_3_o0 - tcopy_2 = tN_0_3_o0 - tcopy_0, error, "the copies differ"
        .assert tN_2_0_o0 - tcopy_2 = tN_0_0_o0 - tcopy_0, error, "the copies differ"
        .assert tN_2_1_o0 - tcopy_2 = tN_0_1_o0 - tcopy_0, error, "the copies differ"
        .assert tA_2_0_o0 - tcopy_2 = tA_0_0_o0 - tcopy_0, error, "the copies differ"
        .assert tA_2_1_o0 - tcopy_2 = tA_0_1_o0 - tcopy_0, error, "the copies differ"
        .assert tA_2_2_o0 - tcopy_2 = tA_0_2_o0 - tcopy_0, error, "the copies differ"
        .assert tA_2_3_o0 - tcopy_2 = tA_0_3_o0 - tcopy_0, error, "the copies differ"
        .assert tE_2_o1 - tcopy_2 = tE_0_o1 - tcopy_0, error, "the copies differ"
        .assert tX_2_o1 - tcopy_2 = tX_0_o1 - tcopy_0, error, "the copies differ"
        .assert tY_2_o1 - tcopy_2 = tY_0_o1 - tcopy_0, error, "the copies differ"
        .assert tN_2_2_o1 - tcopy_2 = tN_0_2_o1 - tcopy_0, error, "the copies differ"
        .assert tN_2_3_o1 - tcopy_2 = tN_0_3_o1 - tcopy_0, error, "the copies differ"
        .assert tN_2_0_o1 - tcopy_2 = tN_0_0_o1 - tcopy_0, error, "the copies differ"
        .assert tN_2_1_o1 - tcopy_2 = tN_0_1_o1 - tcopy_0, error, "the copies differ"
        .assert tA_2_0_o1 - tcopy_2 = tA_0_0_o1 - tcopy_0, error, "the copies differ"
        .assert tA_2_1_o1 - tcopy_2 = tA_0_1_o1 - tcopy_0, error, "the copies differ"
        .assert tA_2_2_o1 - tcopy_2 = tA_0_2_o1 - tcopy_0, error, "the copies differ"
        .assert tA_2_3_o1 - tcopy_2 = tA_0_3_o1 - tcopy_0, error, "the copies differ"
        .assert tE_2_o2 - tcopy_2 = tE_0_o2 - tcopy_0, error, "the copies differ"
        .assert tX_2_o2 - tcopy_2 = tX_0_o2 - tcopy_0, error, "the copies differ"
        .assert tY_2_o2 - tcopy_2 = tY_0_o2 - tcopy_0, error, "the copies differ"
        .assert tN_2_2_o2 - tcopy_2 = tN_0_2_o2 - tcopy_0, error, "the copies differ"
        .assert tN_2_3_o2 - tcopy_2 = tN_0_3_o2 - tcopy_0, error, "the copies differ"
        .assert tN_2_0_o2 - tcopy_2 = tN_0_0_o2 - tcopy_0, error, "the copies differ"
        .assert tN_2_1_o2 - tcopy_2 = tN_0_1_o2 - tcopy_0, error, "the copies differ"
        .assert tA_2_0_o2 - tcopy_2 = tA_0_0_o2 - tcopy_0, error, "the copies differ"
        .assert tA_2_1_o2 - tcopy_2 = tA_0_1_o2 - tcopy_0, error, "the copies differ"
        .assert tA_2_2_o2 - tcopy_2 = tA_0_2_o2 - tcopy_0, error, "the copies differ"
        .assert tA_2_3_o2 - tcopy_2 = tA_0_3_o2 - tcopy_0, error, "the copies differ"
        .assert tE_2_o3 - tcopy_2 = tE_0_o3 - tcopy_0, error, "the copies differ"
        .assert tX_2_o3 - tcopy_2 = tX_0_o3 - tcopy_0, error, "the copies differ"
        .assert tY_2_o3 - tcopy_2 = tY_0_o3 - tcopy_0, error, "the copies differ"
        .assert tN_2_2_o3 - tcopy_2 = tN_0_2_o3 - tcopy_0, error, "the copies differ"
        .assert tN_2_3_o3 - tcopy_2 = tN_0_3_o3 - tcopy_0, error, "the copies differ"
        .assert tN_2_0_o3 - tcopy_2 = tN_0_0_o3 - tcopy_0, error, "the copies differ"
        .assert tN_2_1_o3 - tcopy_2 = tN_0_1_o3 - tcopy_0, error, "the copies differ"
        .assert tA_2_0_o3 - tcopy_2 = tA_0_0_o3 - tcopy_0, error, "the copies differ"
        .assert tA_2_1_o3 - tcopy_2 = tA_0_1_o3 - tcopy_0, error, "the copies differ"
        .assert tA_2_2_o3 - tcopy_2 = tA_0_2_o3 - tcopy_0, error, "the copies differ"
        .assert tA_2_3_o3 - tcopy_2 = tA_0_3_o3 - tcopy_0, error, "the copies differ"
        .assert tE_2_o4 - tcopy_2 = tE_0_o4 - tcopy_0, error, "the copies differ"
        .assert tX_2_o4 - tcopy_2 = tX_0_o4 - tcopy_0, error, "the copies differ"
        .assert tY_2_o4 - tcopy_2 = tY_0_o4 - tcopy_0, error, "the copies differ"
        .assert tN_2_2_o4 - tcopy_2 = tN_0_2_o4 - tcopy_0, error, "the copies differ"
        .assert tN_2_3_o4 - tcopy_2 = tN_0_3_o4 - tcopy_0, error, "the copies differ"
        .assert tN_2_0_o4 - tcopy_2 = tN_0_0_o4 - tcopy_0, error, "the copies differ"
        .assert tN_2_1_o4 - tcopy_2 = tN_0_1_o4 - tcopy_0, error, "the copies differ"
        .assert tA_2_0_o4 - tcopy_2 = tA_0_0_o4 - tcopy_0, error, "the copies differ"
        .assert tA_2_1_o4 - tcopy_2 = tA_0_1_o4 - tcopy_0, error, "the copies differ"
        .assert tA_2_2_o4 - tcopy_2 = tA_0_2_o4 - tcopy_0, error, "the copies differ"
        .assert tA_2_3_o4 - tcopy_2 = tA_0_3_o4 - tcopy_0, error, "the copies differ"
        .assert tE_2_o5 - tcopy_2 = tE_0_o5 - tcopy_0, error, "the copies differ"
        .assert tX_2_o5 - tcopy_2 = tX_0_o5 - tcopy_0, error, "the copies differ"
        .assert tY_2_o5 - tcopy_2 = tY_0_o5 - tcopy_0, error, "the copies differ"
        .assert tN_2_2_o5 - tcopy_2 = tN_0_2_o5 - tcopy_0, error, "the copies differ"
        .assert tN_2_3_o5 - tcopy_2 = tN_0_3_o5 - tcopy_0, error, "the copies differ"
        .assert tN_2_0_o5 - tcopy_2 = tN_0_0_o5 - tcopy_0, error, "the copies differ"
        .assert tN_2_1_o5 - tcopy_2 = tN_0_1_o5 - tcopy_0, error, "the copies differ"
        .assert tA_2_0_o5 - tcopy_2 = tA_0_0_o5 - tcopy_0, error, "the copies differ"
        .assert tA_2_1_o5 - tcopy_2 = tA_0_1_o5 - tcopy_0, error, "the copies differ"
        .assert tA_2_2_o5 - tcopy_2 = tA_0_2_o5 - tcopy_0, error, "the copies differ"
        .assert tA_2_3_o5 - tcopy_2 = tA_0_3_o5 - tcopy_0, error, "the copies differ"
        .assert tE_3_o0 - tcopy_3 = tE_0_o0 - tcopy_0, error, "the copies differ"
        .assert tX_3_o0 - tcopy_3 = tX_0_o0 - tcopy_0, error, "the copies differ"
        .assert tY_3_o0 - tcopy_3 = tY_0_o0 - tcopy_0, error, "the copies differ"
        .assert tN_3_2_o0 - tcopy_3 = tN_0_2_o0 - tcopy_0, error, "the copies differ"
        .assert tN_3_3_o0 - tcopy_3 = tN_0_3_o0 - tcopy_0, error, "the copies differ"
        .assert tN_3_0_o0 - tcopy_3 = tN_0_0_o0 - tcopy_0, error, "the copies differ"
        .assert tN_3_1_o0 - tcopy_3 = tN_0_1_o0 - tcopy_0, error, "the copies differ"
        .assert tA_3_0_o0 - tcopy_3 = tA_0_0_o0 - tcopy_0, error, "the copies differ"
        .assert tA_3_1_o0 - tcopy_3 = tA_0_1_o0 - tcopy_0, error, "the copies differ"
        .assert tA_3_2_o0 - tcopy_3 = tA_0_2_o0 - tcopy_0, error, "the copies differ"
        .assert tA_3_3_o0 - tcopy_3 = tA_0_3_o0 - tcopy_0, error, "the copies differ"
        .assert tE_3_o1 - tcopy_3 = tE_0_o1 - tcopy_0, error, "the copies differ"
        .assert tX_3_o1 - tcopy_3 = tX_0_o1 - tcopy_0, error, "the copies differ"
        .assert tY_3_o1 - tcopy_3 = tY_0_o1 - tcopy_0, error, "the copies differ"
        .assert tN_3_2_o1 - tcopy_3 = tN_0_2_o1 - tcopy_0, error, "the copies differ"
        .assert tN_3_3_o1 - tcopy_3 = tN_0_3_o1 - tcopy_0, error, "the copies differ"
        .assert tN_3_0_o1 - tcopy_3 = tN_0_0_o1 - tcopy_0, error, "the copies differ"
        .assert tN_3_1_o1 - tcopy_3 = tN_0_1_o1 - tcopy_0, error, "the copies differ"
        .assert tA_3_0_o1 - tcopy_3 = tA_0_0_o1 - tcopy_0, error, "the copies differ"
        .assert tA_3_1_o1 - tcopy_3 = tA_0_1_o1 - tcopy_0, error, "the copies differ"
        .assert tA_3_2_o1 - tcopy_3 = tA_0_2_o1 - tcopy_0, error, "the copies differ"
        .assert tA_3_3_o1 - tcopy_3 = tA_0_3_o1 - tcopy_0, error, "the copies differ"
        .assert tE_3_o2 - tcopy_3 = tE_0_o2 - tcopy_0, error, "the copies differ"
        .assert tX_3_o2 - tcopy_3 = tX_0_o2 - tcopy_0, error, "the copies differ"
        .assert tY_3_o2 - tcopy_3 = tY_0_o2 - tcopy_0, error, "the copies differ"
        .assert tN_3_2_o2 - tcopy_3 = tN_0_2_o2 - tcopy_0, error, "the copies differ"
        .assert tN_3_3_o2 - tcopy_3 = tN_0_3_o2 - tcopy_0, error, "the copies differ"
        .assert tN_3_0_o2 - tcopy_3 = tN_0_0_o2 - tcopy_0, error, "the copies differ"
        .assert tN_3_1_o2 - tcopy_3 = tN_0_1_o2 - tcopy_0, error, "the copies differ"
        .assert tA_3_0_o2 - tcopy_3 = tA_0_0_o2 - tcopy_0, error, "the copies differ"
        .assert tA_3_1_o2 - tcopy_3 = tA_0_1_o2 - tcopy_0, error, "the copies differ"
        .assert tA_3_2_o2 - tcopy_3 = tA_0_2_o2 - tcopy_0, error, "the copies differ"
        .assert tA_3_3_o2 - tcopy_3 = tA_0_3_o2 - tcopy_0, error, "the copies differ"
        .assert tE_3_o3 - tcopy_3 = tE_0_o3 - tcopy_0, error, "the copies differ"
        .assert tX_3_o3 - tcopy_3 = tX_0_o3 - tcopy_0, error, "the copies differ"
        .assert tY_3_o3 - tcopy_3 = tY_0_o3 - tcopy_0, error, "the copies differ"
        .assert tN_3_2_o3 - tcopy_3 = tN_0_2_o3 - tcopy_0, error, "the copies differ"
        .assert tN_3_3_o3 - tcopy_3 = tN_0_3_o3 - tcopy_0, error, "the copies differ"
        .assert tN_3_0_o3 - tcopy_3 = tN_0_0_o3 - tcopy_0, error, "the copies differ"
        .assert tN_3_1_o3 - tcopy_3 = tN_0_1_o3 - tcopy_0, error, "the copies differ"
        .assert tA_3_0_o3 - tcopy_3 = tA_0_0_o3 - tcopy_0, error, "the copies differ"
        .assert tA_3_1_o3 - tcopy_3 = tA_0_1_o3 - tcopy_0, error, "the copies differ"
        .assert tA_3_2_o3 - tcopy_3 = tA_0_2_o3 - tcopy_0, error, "the copies differ"
        .assert tA_3_3_o3 - tcopy_3 = tA_0_3_o3 - tcopy_0, error, "the copies differ"
        .assert tE_3_o4 - tcopy_3 = tE_0_o4 - tcopy_0, error, "the copies differ"
        .assert tX_3_o4 - tcopy_3 = tX_0_o4 - tcopy_0, error, "the copies differ"
        .assert tY_3_o4 - tcopy_3 = tY_0_o4 - tcopy_0, error, "the copies differ"
        .assert tN_3_2_o4 - tcopy_3 = tN_0_2_o4 - tcopy_0, error, "the copies differ"
        .assert tN_3_3_o4 - tcopy_3 = tN_0_3_o4 - tcopy_0, error, "the copies differ"
        .assert tN_3_0_o4 - tcopy_3 = tN_0_0_o4 - tcopy_0, error, "the copies differ"
        .assert tN_3_1_o4 - tcopy_3 = tN_0_1_o4 - tcopy_0, error, "the copies differ"
        .assert tA_3_0_o4 - tcopy_3 = tA_0_0_o4 - tcopy_0, error, "the copies differ"
        .assert tA_3_1_o4 - tcopy_3 = tA_0_1_o4 - tcopy_0, error, "the copies differ"
        .assert tA_3_2_o4 - tcopy_3 = tA_0_2_o4 - tcopy_0, error, "the copies differ"
        .assert tA_3_3_o4 - tcopy_3 = tA_0_3_o4 - tcopy_0, error, "the copies differ"
        .assert tE_3_o5 - tcopy_3 = tE_0_o5 - tcopy_0, error, "the copies differ"
        .assert tX_3_o5 - tcopy_3 = tX_0_o5 - tcopy_0, error, "the copies differ"
        .assert tY_3_o5 - tcopy_3 = tY_0_o5 - tcopy_0, error, "the copies differ"
        .assert tN_3_2_o5 - tcopy_3 = tN_0_2_o5 - tcopy_0, error, "the copies differ"
        .assert tN_3_3_o5 - tcopy_3 = tN_0_3_o5 - tcopy_0, error, "the copies differ"
        .assert tN_3_0_o5 - tcopy_3 = tN_0_0_o5 - tcopy_0, error, "the copies differ"
        .assert tN_3_1_o5 - tcopy_3 = tN_0_1_o5 - tcopy_0, error, "the copies differ"
        .assert tA_3_0_o5 - tcopy_3 = tA_0_0_o5 - tcopy_0, error, "the copies differ"
        .assert tA_3_1_o5 - tcopy_3 = tA_0_1_o5 - tcopy_0, error, "the copies differ"
        .assert tA_3_2_o5 - tcopy_3 = tA_0_2_o5 - tcopy_0, error, "the copies differ"
        .assert tA_3_3_o5 - tcopy_3 = tA_0_3_o5 - tcopy_0, error, "the copies differ"
toff:
        .byte 0, 3, 6, 9, 12, 15     ; roll 0: [8, 5, 2, -1, -4, -7]
        .byte 2, 5, 7, 9, 11, 14     ; roll 1: [6, 3, 1, -1, -3, -6]
        .byte 4, 6, 7, 9, 10, 12     ; roll 2: [4, 2, 1, -1, -2, -4]
        .byte 6, 7, 8, 8, 9, 10     ; roll 3: [2, 1, 0, 0, -1, -2]
        .byte 8, 8, 8, 8, 8, 8     ; roll 4: [0, 0, 0, 0, 0, 0]
        .byte 10, 9, 8, 8, 7, 6     ; roll 5: [-2, -1, 0, 0, 1, 2]
        .byte 12, 10, 9, 7, 6, 4     ; roll 6: [-4, -2, -1, 1, 2, 4]
        .byte 14, 11, 9, 7, 5, 2     ; roll 7: [-6, -3, -1, 1, 3, 6]
        .byte 15, 12, 9, 6, 3, 0     ; roll 8: [-7, -4, -1, 2, 5, 8]
TNPATCH = 11                ; patch addresses per segment per copy
