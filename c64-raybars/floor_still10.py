"""10 s (600 frames) of part 1's last frame, flicker phases running, to show the static floor."""
import sys, numpy as np
import part1 as p
def main(path, n=600):
    v = p.iv.Video(path, p.W * 3, p.H * 3)
    col = p.gp.film_lines(p.frame_list(p.T_END - 1))
    for i in range(n):
        f = p.T_END + i
        img = np.array([p.gp.draw([c] * p.gp.SEGS, y, f) for y, c in enumerate(col)])
        v.add(p.lv.crt_look(p.fb.C64RGB[img].astype(np.uint8), 3))
    v.close(); print("wrote", path, n, "frames")
if __name__ == "__main__":
    main(sys.argv[1])
