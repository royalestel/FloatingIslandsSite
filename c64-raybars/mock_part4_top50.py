#!/usr/bin/env python3
"""MOCK (no C64 code): part 4 with the random movement kept below visible line 50 (nothing rises into the top 50 lines),
a wilder frenzy at the climax, and a slower clean-up (the matches).  Model only; the wipe at the end is unchanged.
    python3 mock_part4_top50.py [out.mp4]"""
import os, sys
os.environ["SPLITS"] = "6"
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "part4m.py")).read()

def sub(a, b):
    global src
    assert a in src, a
    src = src.replace(a, b, 1)

sub("SLIDE_AMP, CIRC_Y, CIRC_Z = 22.0, 14.0, 0.30",
    "SLIDE_AMP, CIRC_Y, CIRC_Z = 22.0, 14.0, 0.30\nCAPY = 50.0                   # no piece rises above visible line 50")
sub("EASE = 20 ", "EASE = 34 ")                                      # a matched element takes longer to join its neighbour
sub("SETTLE = 90 ", "SETTLE = 150 ")                                 # the motion eases out slower
sub("T_ALIGN = T_BLUE + 90", "T_ALIGN = T_BLUE + 200")               # the matches start later (the frenzy first)
sub("tt += max(0.4, 20 * 0.95 ** j)", "tt += max(1.5, 26 * 0.965 ** j)")   # slower matching, accelerating less
sub("smooth = lambda", """def FZ(t):
    \"\"\"the frenzy: 0 -> 1 around the climax (just before and while the matches begin), then easing off\"\"\"
    return smooth((t - (T_ALIGN - 150)) / 160.0) * (1.0 - smooth((t - (T_ALIGN + 330)) / 260.0))
smooth = lambda""")
# FZ uses smooth, defined on the next line: swap the order
sub("def FZ(t):", "smooth = lambda x: (lambda u: u * u * (3 - 2 * u))(min(max(x, 0.0), 1.0))\ndef FZ(t):")
sub("return smooth((t - T_CIRC) / float(T_LAST - T_CIRC))", "return smooth((t - T_CIRC) / float(T_ALIGN + 80 - T_CIRC))")
sub("a_ += 2 * math.pi / PERIOD[k] * (1 + 1.2 * chaos(t_))", "a_ += 2 * math.pi / PERIOD[k] * (1 + 1.2 * chaos(t_) + 1.6 * FZ(t_))")
sub("b_ += OMEGA[k] * (1 + 1.5 * chaos(t_))", "b_ += OMEGA[k] * (1 + 1.5 * chaos(t_) + 2.2 * FZ(t_))")
# excursions go up only as far as the cap
sub("dy += -(YC[i] + 12.0) * math.sin(2 * math.pi * u)             # up, off the top, back",
    "dy += -(YC[i] - CAPY - STR[i][1] / 2.0) * math.sin(2 * math.pi * u)   # up to the cap, back")
# columns take turns: more and more at once, all of them at the climax
sub("n = 1 if _s < T_CIRC + 400 else 2", "n = min(SEGS, (1 if _s < T_CIRC + 400 else 2) + int(round(4 * FZ(_s))))")
sub("_t += max(30, 80 - 40 * chaos(_t))", "_t += max(3.5, 80 - 40 * chaos(_t) - 80 * FZ(_t))")
sub("EXC[key].append((int(_t), 70))", "EXC[key].append((int(_t), int(70 - 25 * FZ(_t))))")
sub("while _t < T_LAST - 120:", "while _t < T_ALIGN + 600:")
sub("while _s < T_LAST + 60:", "while _s < T_ALIGN + 700:")
sub("slide = SLIDE_AMP * (1 + 1.7 * ch) * sa", "slide = SLIDE_AMP * (1 + 1.7 * ch + 1.0 * FZ(t)) * sa")
sub("rho = 1.0 + CIRC_Z * (1 + 0.8 * ch) * ca", "rho = 1.0 + CIRC_Z * (1 + 0.8 * ch + 0.5 * FZ(t)) * ca")
sub("- CIRC_Y * (1 + 1.5 * ch) * ca * math.cos(th) + exc,\n            STR[i][1] / max(rho, 0.35))",
    "- CIRC_Y * (1 + 1.5 * ch + 0.8 * FZ(t)) * ca * math.cos(th) + exc,\n            STR[i][1] / max(rho, 0.35))")
# soft floor under the whole motion: the top of a bar never goes above CAPY
sub("def pos(i, k, t):\n    y, T = traj(k, i, t)", """def _cap(y, T):
    lo = CAPY + T / 2.0
    d = y - lo
    return lo + (d if d >= 8.0 else 8.0 * math.exp((d - 8.0) / 8.0))

def pos(i, k, t):
    y, T = traj(k, i, t)
    y = _cap(y, T)""")
sub("        y, T = y + (y2 - y) * w, T + (T2 - T) * w\n    return y, T",
    "        y, T = y + (y2 - y) * w, T + (T2 - T) * w\n    return (_cap(y, T) if t < T_SWEEP0 else y), T")
sub("def main(path, a=0, b=None):", "def main(path, a=0, b=None):\n    print('frames', T_END, 'matches', int(T_ALIGN), '-', int(T_LAST), 'frenzy peak', T_ALIGN + 70)")
exec(compile(src, "part4m_top50", "exec"), {"__name__": "mock", "__file__": "part4m.py", "sys": sys, "OUT": sys.argv[1] if len(sys.argv) > 1 else "/tmp/mock_part4_top50.mp4"}) if False else None
ns = {"__name__": "part4m_top50", "__file__": os.path.abspath("part4m.py")}
exec(compile(src, "part4m_top50", "exec"), ns)
out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mock_part4_top50.mp4"
ns["main"](out)
