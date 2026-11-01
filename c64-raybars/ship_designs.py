"""Ship design variations for GOLDSHIP, each without central fins in the
tail view: A-E (arrow, twin boom, gull, forward swept, tip fins) and the
gull's variations C1-C5 (C1 became ship3d.model()).  Same conventions as
ship3d.py: x right, y up, z forward.  Rendered by ship_hires.py."""
from ship3d import loft, octagon, slab, fin, sphere

def lozenge(w, h, cy=0.0):
    a, b = w / 2, h / 2
    return [(-a * 0.55, cy + b), (a * 0.55, cy + b), (a, cy + b * 0.2), (a, cy - b * 0.2),
            (a * 0.55, cy - b), (-a * 0.55, cy - b), (-a, cy - b * 0.2), (-a, cy + b * 0.2)]

def nose_light(z):
    return sphere(0, 0, z, 1.4, "glow")

def arrow():
    """A: a flying wing.  A flat body, a broad delta, engine slots in the tail,
    small downturned winglets."""
    f = loft([(-7, lozenge(6.0, 2.6)), (-2, lozenge(7.0, 3.0)), (5, lozenge(4.0, 2.2)),
              (10, lozenge(1.2, 0.9))])
    f += nose_light(10.6)
    for s in (-1, 1):
        f += slab([(s * 3.0, 0, 6.0), (s * 11.6, 0, -5.0), (s * 11.6, 0, -7.0),
                   (s * 3.0, 0, -7.0)], 1.4)
        f += fin([(s * 11.8, 0.6, -7.0), (s * 11.8, -2.6, -7.4), (s * 11.8, -2.6, -6.0),
                  (s * 11.8, 0.6, -4.6)], 1.6, "trim")
        f += loft([(-7.6, lozenge(2.4, 1.4)), (-3, lozenge(2.4, 1.4))], "trim",
                  dx=s * 1.6)
    return f

def twinboom():
    """B: a flat pod, straight wings and two booms, each with its own small
    fin out at the side."""
    f = loft([(-4, lozenge(4.6, 2.8)), (2, lozenge(5.0, 3.2)), (7, lozenge(3.0, 2.2)),
              (10, lozenge(1.2, 1.0))])
    f += nose_light(10.6)
    for s in (-1, 1):
        f += slab([(s * 2.2, 0, 3.0), (s * 11.8, 0, 1.5), (s * 11.8, 0, -1.5),
                   (s * 2.2, 0, -2.0)], 1.2)
        f += loft([(-8, octagon(2.4, 2.4)), (-1, octagon(2.6, 2.6)), (4, octagon(1.6, 1.6))],
                  "trim", dx=s * 6.4)
        f += fin([(s * 6.4, 1.0, -8.0), (s * 6.4, 4.6, -8.4), (s * 6.4, 4.6, -7.0),
                  (s * 6.4, 1.0, -4.5)], 1.4)
        f += slab([(s * 5.2, 0.2, -6.0), (s * 7.6, 0.2, -6.0), (s * 7.6, 0.2, -8.2),
                   (s * 5.2, 0.2, -8.2)], 0.8)
    return f

def gull():
    """C: gull wings rising from the body and kinking down to the tips, with
    the engines at the kinks."""
    f = loft([(-6, lozenge(4.4, 2.8)), (-1, lozenge(5.0, 3.2)), (6, lozenge(3.0, 2.2)),
              (10, lozenge(1.2, 1.0))])
    f += nose_light(10.6)
    for s in (-1, 1):
        f += slab([(s * 2.2, 0, 4.0), (s * 5.2, 1.8, 1.0), (s * 5.2, 1.8, -6.0),
                   (s * 2.2, 0, -6.0)], 1.2)
        f += slab([(s * 5.2, 1.8, 1.0), (s * 11.8, -1.6, -4.0), (s * 11.8, -1.6, -6.0),
                   (s * 5.2, 1.8, -6.0)], 1.1)
        f += loft([(-7.5, octagon(2.4, 2.4, 1.8)), (0, octagon(2.4, 2.4, 1.8)),
                   (2, octagon(1.0, 1.0, 1.8))], "trim", dx=s * 5.2)
    return f

def forward():
    """D: forward-swept wings and small canards, engines beside the body."""
    f = loft([(-7, lozenge(4.4, 3.0)), (-2, lozenge(5.2, 3.2)), (6, lozenge(3.0, 2.2)),
              (10, lozenge(1.2, 1.0))])
    f += nose_light(10.6)
    for s in (-1, 1):
        f += slab([(s * 2.4, 0, 0.0), (s * 11.8, 0, 3.0), (s * 11.8, 0, 1.0),
                   (s * 2.4, 0, -6.0)], 1.2)
        f += slab([(s * 2.0, 0.4, 7.0), (s * 5.0, 0.4, 5.6), (s * 5.0, 0.4, 4.6),
                   (s * 2.0, 0.4, 4.6)], 0.8, "trim")
        f += loft([(-8, octagon(2.2, 2.2)), (-1, octagon(2.2, 2.2)), (1, octagon(1.0, 1.0))],
                  "trim", dx=s * 3.2)
    return f

def tipfins():
    """E: the current ship without its central fins: flat delta wings, tip
    fins above and below, engine pods through the wing roots."""
    f = loft([(-7, octagon(4.6, 3.8)), (-3, octagon(7.4, 6.2)),
              (5, octagon(4.6, 3.8)), (10, octagon(1.6, 1.4))])
    f += nose_light(10.6)
    for s in (-1, 1):
        f += slab([(s * 3.0, 0.0, 4.0), (s * 11.2, 0.0, -4.0), (s * 11.2, 0.0, -6.2),
                   (s * 3.0, 0.0, -6.2)], 1.6)
        f += fin([(s * 11.4, -3.3, -6.6), (s * 11.4, 3.3, -6.6), (s * 11.4, 3.3, -4.0),
                  (s * 11.4, -3.3, -4.0)], 2.2, "trim")
        f += loft([(-8, octagon(2.8, 3.2)), (-1, octagon(2.8, 3.2)),
                   (1, octagon(1.2, 1.2))], "trim", caps=("trim", "trim"), dx=s * 4.6)
    return f

DESIGNS = [("A  Arrow", arrow), ("B  Twin boom", twinboom), ("C  Gull", gull),
           ("D  Forward swept", forward), ("E  Tip fins", tipfins)]

# ---- variations of C (gull) ---------------------------------------------------
def wing_path(pts, z_front, z_back, thick, kind="hull", sweep=None):
    """A wing following the tail-view path pts [(x, y), ...] from the root out,
    with chord z_front(x) .. z_back(x)."""
    f = []
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        f += slab([(xa, ya, z_front(xa)), (xb, yb, z_front(xb)), (xb, yb, z_back(xb)),
                   (xa, ya, z_back(xa))], thick, kind)
    return f

def gull_body():
    f = loft([(-6, lozenge(4.4, 3.0)), (-1, lozenge(5.0, 3.4)), (6, lozenge(3.0, 2.2)),
              (10, lozenge(1.2, 1.0))])
    return f + nose_light(10.6)

def both(fn):
    return fn(1) + fn(-1)

def c1():
    """C1: the gull, with thicker panels."""
    f = gull_body()
    zf = lambda x: 4.0 - abs(x) * 0.75
    zb = lambda x: -6.0
    f += both(lambda s: wing_path([(s * 2.2, 0), (s * 5.2, 1.8), (s * 11.8, -1.6)], zf, zb, 1.8))
    f += both(lambda s: loft([(-7.5, octagon(2.6, 2.6, 1.8)), (0, octagon(2.6, 2.6, 1.8)),
                              (2, octagon(1.0, 1.0, 1.8))], "trim", dx=s * 5.2))
    return f

def c2():
    """C2: inverted gull: the wings dip down from the body, then rise to the
    tips; engines at the low kinks."""
    f = gull_body()
    zf = lambda x: 4.0 - abs(x) * 0.75
    zb = lambda x: -6.0
    f += both(lambda s: wing_path([(s * 2.2, 0), (s * 5.4, -2.0), (s * 11.8, 1.4)], zf, zb, 1.8))
    f += both(lambda s: loft([(-7.5, octagon(2.6, 2.6, -2.0)), (0, octagon(2.6, 2.6, -2.0)),
                              (2, octagon(1.0, 1.0, -2.0))], "trim", dx=s * 5.4))
    return f

def c3():
    """C3: a smooth arched gull: three panels on an arc, engines at the
    first joint."""
    f = gull_body()
    zf = lambda x: 4.0 - abs(x) * 0.75
    zb = lambda x: -6.0 + abs(x) * 0.08
    f += both(lambda s: wing_path([(s * 2.2, 0), (s * 4.6, 1.6), (s * 8.0, 1.2), (s * 11.8, -1.6)],
                                  zf, zb, 1.8))
    f += both(lambda s: loft([(-7.5, octagon(2.4, 2.4, 1.6)), (0, octagon(2.4, 2.4, 1.6)),
                              (2, octagon(1.0, 1.0, 1.6))], "trim", dx=s * 4.6))
    return f

def c4():
    """C4: gull with downturned winglets; the engines hang under the kinks."""
    f = gull_body()
    zf = lambda x: 4.0 - abs(x) * 0.75
    zb = lambda x: -6.0
    f += both(lambda s: wing_path([(s * 2.2, 0), (s * 5.2, 1.6), (s * 10.6, -1.0)], zf, zb, 1.8))
    f += both(lambda s: fin([(s * 11.0, -0.6, -6.6), (s * 11.0, -3.8, -7.0), (s * 11.0, -3.8, -5.4),
                             (s * 11.0, -0.6, -2.8)], 1.8, "trim"))
    f += both(lambda s: loft([(-7.5, octagon(2.4, 2.4, -0.4)), (0, octagon(2.4, 2.4, -0.4)),
                              (2, octagon(1.0, 1.0, -0.4))], "trim", dx=s * 5.2))
    return f

def c5():
    """C5: a clean gull: swept-back tips, engines inside the body (two glowing
    slots in the tail)."""
    f = loft([(-7, lozenge(5.6, 3.2)), (-1, lozenge(5.6, 3.4)), (6, lozenge(3.0, 2.2)),
              (10, lozenge(1.2, 1.0))])
    f += nose_light(10.6)
    zf = lambda x: 5.0 - abs(x) * 0.95
    zb = lambda x: -5.0 - abs(x) * 0.25
    f += both(lambda s: wing_path([(s * 2.6, 0), (s * 5.6, 1.8), (s * 11.8, -1.4)], zf, zb, 1.8))
    f += both(lambda s: loft([(-7.6, lozenge(2.0, 1.6)), (-3, lozenge(2.0, 1.6))], "trim",
                             dx=s * 1.4))
    return f

GULLS = [("C1  Gull, fixed", c1), ("C2  Inverted gull", c2), ("C3  Arched gull", c3),
         ("C4  Gull, winglets", c4), ("C5  Clean gull", c5)]
