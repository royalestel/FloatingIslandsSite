"""The anim0 scene as a model: bars(t) gives each bar's distance, centre line
and draw-order key at frame t.  All numbers come from anim_params.P via
configure() (so the generator, the Python preview and the simulator share
them).  Same maths as the frozen anim0.py.
"""
import numpy as np
import anim1_floor as fv

F, R, H, W = fv.F, fv.R, fv.H, fv.W

def configure(P):
    g = globals()
    g.update(P)
    g["T_NEW"] = list(P["T_NEW"])
    g["OMEGA"] = 2 * np.pi / P["TURN"]
    g["HALF_EQ"] = F * R / P["Z_EQ"]
    g["PITCH_PX"] = 2 * g["HALF_EQ"] + P["GAP"]
    g["T_X0"] = P["T_TILT0"] + P["X_START"]
    g["T_XSTAG"], g["T_XSLIDE"] = P["X_STAG"], P["X_LEN"]
    g["T_END"] = P["T_TILT1"] + P["HOLD_END"]
    g["FLOOR_Z"] = [fv.SPACING * (6 - j) for j in range(6)]
    g["YC_WALL"] = [H / 2 + (j - 2.5) * g["PITCH_PX"] for j in range(6)]
    g["D_FLOOR"] = [float(np.hypot(z, fv.CAM_H)) for z in g["FLOOR_Z"]]
    g["YC_FLOOR"] = [float(fv.screen_y(z)) for z in g["FLOOR_Z"]]
    ez = [fv.SPACING * k for k in range(7, int(fv.ZMAX / fv.SPACING) + 1)
          if fv.screen_y(fv.SPACING * k) > -4]
    g["EXTRA_D"] = [float(np.hypot(z, fv.CAM_H)) for z in ez]
    g["EXTRA_YC"] = [float(fv.screen_y(z)) for z in ez]

smooth = lambda x: (lambda u: u * u * (3 - 2 * u))(min(max(x, 0.0), 1.0))

def theta(t):
    """Angle of bar 0 (starts at 270 deg: centre height, nearest on the circle)."""
    return 1.5 * np.pi + OMEGA * t

# Optional: the circle's centre distance follows keyframes (time, distance), eased and
# interpolated in the logarithm of the distance (a steady shrink / grow); set FAR_KEYS.
FAR_KEYS = None

def _dz(t):
    if FAR_KEYS is None or t <= FAR_KEYS[0][0] or t >= FAR_KEYS[-1][0]:
        return 0.0
    for (t0, z0), (t1, z1) in zip(FAR_KEYS, FAR_KEYS[1:]):
        if t < t1:
            x = smooth((t - t0) / float(t1 - t0))
            return float(np.exp(np.log(z0) + (np.log(z1) - np.log(z0)) * x)) - ZC
    return 0.0

def bars(t):
    """(distance, centre line, draw-order key) of the six bars at frame t
    (bars not on screen yet are far below it)."""
    th = theta(t)
    s = smooth((t - T_B0) / (T_B1 - T_B0))              # 0 one distance .. 1 circle
    e = smooth((t - T_C0) / (T_C1 - T_C0))              # 0 circle .. 1 stack slots
    a = smooth((t - T_TILT0) / (T_TILT1 - T_TILT0))     # 0 wall .. 1 floor
    slots = np.argsort(np.argsort([-AY * np.cos(theta(T_C0) + 2 * np.pi * k / 3)
                                   for k in range(3)]))     # highest bar -> top slot
    out = []
    for k in range(6):
        if k < 3:
            ph = th + 2 * np.pi * k / 3
            zc = ZC + _dz(t) + AZ * np.sin(ph)          # circle: away, down, towards, up (and, if set, off into the distance and back)
            z = (1 - s) * Z_EQ + s * zc                 # sliding = the circle edge-on
            yc = H / 2 - F * AY * np.cos(ph) / z
            z = (1 - e) * z + e * Z_EQ
            yc = (1 - e) * yc + e * YC_WALL[slots[k]]
            key = z + 0.001 * (1 - e) * np.sin(ph)      # far (sin > 0) behind, also when sliding
            j = slots[k]
            rise = 200 * (1 - smooth((t - T_ENTER[k]) / ENTER_LEN))
        else:
            j = k                                       # slots 3, 4, 5: slide in from the bottom
            z, yc, key = Z_EQ, YC_WALL[j], Z_EQ
            rise = 200 * (1 - smooth((t - T_NEW[k - 3]) / NEW_LEN))
        z = (1 - a) * z + a * D_FLOOR[j]
        yc = (1 - a) * yc + a * YC_FLOOR[j]
        out.append((z, yc + rise * 1.3, key if a == 0 else z))
    for i, (d, y) in enumerate(zip(EXTRA_D, EXTRA_YC)):      # slide in from the top, nearest first
        u = smooth((t - T_X0 - T_XSTAG * i) / T_XSLIDE)
        out.append((d, y - 300 * (1 - u), d))
    return out

