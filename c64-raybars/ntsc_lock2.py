import sys, itertools, collections; sys.path.insert(0, "/tmp"); sys.path.insert(0, ".")
sys.path.insert(0, "/tmp")
import importlib.util
spec = importlib.util.spec_from_file_location("d7", "/tmp/d7.py"); d7 = importlib.util.module_from_spec(spec); spec.loader.exec_module(d7)
for w, pre, o in itertools.product((4, 5, 6), (0, 1, 2), (0, 1)):
    kw = dict(WAITX=w, PRE=pre)
    kw["ODD"] = o
    res = [d7.test(501, **kw) for _ in range(5)]
    print(f"WAITX={w} PRE={pre} ODD={o}: {res}", flush=True)
