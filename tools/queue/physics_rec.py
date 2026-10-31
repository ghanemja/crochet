# Record choreo's per-frame working-yarn inputs for the yarn physics study (tools/yarn_xpbd.py), next to the
# frames exactly as choreo makes them today (the per-frame relax, yarn_clear).
#   python3 tools/queue/physics_rec.py <key> <a:b> <out.pkl>
# Runs choreo.py up to its frame loop (as chunkgen.py does), then video frames a..b-1. Per frame it keeps: the frame
# as choreo writes it ("old"), and the yarn with the fabric prefix relaxed but the working yarn as designed (the same
# yarn_clear with no working-yarn iterations: "base"), its split/fabric/hand indices and the colliders the relax used.
import sys, os, json, pickle, time
import numpy as np
src = open("tools/choreo.py").read()
c_loop = src.index("cache = {}; frames = []")
key, rng, outp = sys.argv[1], sys.argv[2], sys.argv[3]
a, b = (int(x) for x in rng.split(":"))
sys.argv = ["choreo.py", key, "/dev/null", "--hands"]
g = {"__file__": os.path.abspath("tools/choreo.py"), "__name__": "choreo_rec"}
t0 = time.time()
exec(compile(src[:c_loop], "choreo_head", "exec"), g)
print("choreo head %.0f s" % (time.time() - t0), flush=True)

REC = {}
def clear_rec(c, e, h, hk):
    old = g["yarn_clear"](c, e, h, hk)
    w = g["WORK_ITERS"]; g["WORK_ITERS"] = 0
    base = g["yarn_clear"](c, e, h, hk)
    g["WORK_ITERS"] = w
    fab = g["static_relaxed"](); F = np.vstack(fab) if fab else np.zeros((0, 3))
    REC.update(e=e, h=h, design=c.copy(), base=base, old_c=old, F=F,
               hook=dict(tip=hk.tip.copy(), u=hk.u.copy(), t=hk.t.copy()), skin=g["left_skin"]())
    return old
fs = src[src.index("def frame_strands(ta):"):src.index("def straight_run(")]
fs = fs.replace("c = yarn_clear(c, cv.own_e", "c = CLEAR(c, cv.own_e").replace("segs = [(c[:sp + 1], False)", "REC.update(sp=sp, c_final=c.copy()); segs = [(c[:sp + 1], False)")
g["CLEAR"] = clear_rec; g["REC"] = REC
exec(compile(fs, "frame_strands_rec", "exec"), g)

body = src[c_loop:src.index("# ---------------------------------------------------------------- callouts")]
body = body.replace("for i in range(min(n, A.max_frames) if A.max_frames else n):", "for i in RANGE:")
body = body.replace("if key not in cache: cache[key] = frame_strands(ta)",
                    "if key not in cache: REC.clear(); cache[key] = frame_strands(ta); RECS[key] = dict(REC)")
g["RANGE"] = range(a, b); g["RECS"] = {}
exec(compile(body, "choreo_frames", "exec"), g)
recs = []
for i, fr in zip(range(a, b), g["frames"]):
    recs.append(dict(i=i, frame=fr, **g["RECS"][fr["a"]]))
hp = g["hook_profile"]; ds = np.arange(0.0, 40.0, 0.3)
head = {"key": key, "fps": g["A"].fps, "n": g["n"], "R": g["R"], "APP_R": g["APP_R"],
        "hook_prof": np.array([hp(d_) for d_ in ds]), "hook_ds": ds}
pickle.dump({"head": head, "recs": recs}, open(outp, "wb"))
print("recorded", len(recs), "frames %.0f s" % (time.time() - t0))
