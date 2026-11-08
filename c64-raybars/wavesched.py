"""Option 1 (NTSC): the update also works through the empty top lines of a frame.
   Timeline from the end of the last row (t = 0, line 51 + LINE1 + 1): the display-enable bit must be written in lines 49..50 (t = 4940..5070), the stable
   raster IRQ at line 49 + F (F = the first active line of the frame about to be shown) must find the CPU idle.
   A frame's runs are a group A (done before line 49) and a group B (after the DEN write, until line 49 + F); F = 0 (or < 3): one group, the old way."""
import os
import numpy as np
A_BUDGET = 4000                  # cycles of runs before line 49 (NTSC, 185 rows; the update's own ~600 not included)
def first_line(img_t):
    nz = np.where(img_t.any(axis=1))[0]
    return int(nz[0]) if len(nz) else 150
def F_of(img_t):
    f = first_line(img_t)
    return f if f >= 3 else 0
def budgets(F):
    if os.environ.get("NOOPT1"): return (A_BUDGET, 0)
    return (A_BUDGET, 65 * F - 450) if F else (A_BUDGET, 0)
def record(F, A, B):
    """[F][nA][runs A][nB][runs B]; a run = [page][line][len] bytes"""
    out = bytearray([F, len(A)])
    for page, line, data in A: out += bytes([page, line, len(data)]) + data
    out.append(len(B))
    for page, line, data in B: out += bytes([page, line, len(data)]) + data
    return bytes(out)
