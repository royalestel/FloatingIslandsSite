; cosmicstrings for the NTSC cartridge (6567R8: 65-cycle lines).  Test builds: -Wa -DSTEAL=n.
NTSC = 1
CART = 1                ; the cartridge layout (cosmicstrings_ntsc.cfg): code in $7300.., nothing over the tune
        .include "cosmicstrings.s"
