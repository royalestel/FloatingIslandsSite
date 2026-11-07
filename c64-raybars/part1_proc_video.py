"""Preview of the procedural beginning of part 1 (part1_proc.py): frames 0 .. T_STACK as the CRT-look film.
    python3 part1_proc_video.py out.mp4 [first last]"""
import sys, numpy as np
import part1 as p1
import part1_proc as q

def main(path, a=0, b=None):
    v = p1.iv.Video(path, p1.W * 3, p1.H * 3)
    for f in range(a, q.p1.T_END if b is None else b):
        col, par = q.film_buf(f)           # swatch parity = the row's parity in its bar
        img = np.array([p1.gp.draw([c] * p1.gp.SEGS, (y & ~1) | par[y], f) for y, c in enumerate(col)])
        v.add(p1.lv.crt_look(p1.fb.C64RGB[img].astype(np.uint8), 3))
    v.close(); print("wrote", path, (q.p1.T_END if b is None else b) - a, "frames")

if __name__ == "__main__":
    a = sys.argv[2:]
    main(sys.argv[1], int(a[0]) if a else 0, int(a[1]) if len(a) > 1 else None)
