"""Every number of the anim0 sequence that you may want to twiddle.  Change
a value, run `make -f anim.mk` (or: python3 anim_gen.py && the cl65 line in
anim0.s) and the .prg is rebuilt in seconds; the Python scene model, the
.inc the program includes and the simulator's reference all come from here.

Times are in frames (60 a second).  Lengths are in C64 raster lines, depths
in metres (focal length 200 lines, bar radius 0.12 m: a bar at d metres is
2 * 200 * 0.12 / d lines thick).
"""
P = dict(
    # -- the three bars: slide in, slide past each other, circle in depth
    T_ENTER   = [30, 150, 270],    # frame each of the first three bars starts to slide up: bar 1 on the first notes (0.5 s), bars 2 and 3 two seconds apart
    ENTER_LEN = 90,               # frames a bar takes to slide up
    TURN      = 240,              # frames per turn of the depth circle (and of the sliding)
    ZC        = 2.0,              # circle centre distance (m)
    AZ        = 1.2,              # circle radius in depth (m)
    AY        = 0.55,             # circle radius in height (m): the slide's amplitude
    Z_EQ      = 1.7,              # distance of the flat bars (m)
    GAP       = 3,                # black lines between bars in the stack
    T_B0      = 500,              # sliding at one distance ...
    T_B1      = 620,              # ... has become the circle
    T_C0      = 1100,             # circle ...
    T_C1      = 1230,             # ... has settled into the top three slots of the stack
    # -- three more bars slide up from the bottom
    T_NEW     = [1230, 1290, 1350],
    NEW_LEN   = 70,
    # -- the stack tilts into the distance and becomes a floor
    T_TILT0   = 1450,
    T_TILT1   = 1610,
    X_START   = 20,               # the other strings start this long after the tilt starts
    X_STAG    = 3,                # ... each this much later than the nearer one
    X_LEN     = 60,               # ... and slide in from the top in this many frames
    HOLD_END  = 120,              # frames the finished floor stays
    # -- C64 side
    TMAX      = 63,               # thickest bar (lines): 63 = 0.8 m from the camera
    FIRST_LINE = 51,              # raster line of the picture's first line
)

# The tilt wave on the finished floor (stage 2, raster splits): each string's right
# end rises and falls; the wave runs along the floor.
WAVE = dict(
    TILT_T   = 16,       # frames a string takes to rise and fall
    STAG     = 2,        # frames between one string and the next
    RISE     = 28,       # the nearest string's right-end rise (lines)
    RISE_EXP = 0.3,      # rise ~ (thickness / nearest thickness) ** RISE_EXP
    NEAR_FIRST = True,   # False: the wave starts at the farthest string
    HOLD     = 40,       # still frames after the wave
)
