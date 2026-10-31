# The yarn physics study: choreo's recorded frames (physics_rec.py) re-made with the working yarn as a rod stepped in
# time (tools/yarn_xpbd.py), against the frames as choreo makes them (the per-frame relax).
#   python3 tools/queue/physics_study.py <head.json> <out dir> <a:b measured> rec1.pkl [rec2.pkl ...]
# The rod starts on the design at the first recorded frame and is stepped through every recorded frame (the ones
# before a are its run-up). Writes <out>/old.json and <out>/new.json (the recorded frames, as paths files the
# renderer and yarn_gate.py read; frame k of them is video frame first + k) and prints the numbers.
import sys, os, json, pickle, time, copy
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import yarn_xpbd
from scipy.spatial import cKDTree

head_p, out_d, rng = sys.argv[1], sys.argv[2], sys.argv[3]
A0, B0 = (int(x) for x in rng.split(":"))
recs = []
for p in sys.argv[4:]: recs += pickle.load(open(p, "rb"))["recs"]
H0 = pickle.load(open(sys.argv[4], "rb"))["head"]
recs.sort(key=lambda r: r["i"]); R = H0["R"]; APP_R = H0["APP_R"]; fps = H0["fps"]
TO_APP = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
def app(c): return [[round(float(x), 4) for x in p] for p in np.asarray(c) @ TO_APP.T * (APP_R / R)]
KW = dict(x.split("=") for x in os.environ.get("ROD", "").split(",") if x)
rod = yarn_xpbd.YarnRod(**{k: float(v) for k, v in KW.items()})
prof = H0["hook_prof"]; hds = H0["hook_ds"]

def hook_pts(hk):
    hax = np.array([hk["tip"] + hk["u"] * d + hk["t"] * cx for d, (cx, _) in zip(hds, prof)])
    return hax, prof[:, 1] + 0.9 * R

def arc(p): return yarn_xpbd.arc(p)
# BUDGET=k: the rod gets the yarn the per-frame relax found each stretch needs (from where it leaves the fabric to the
# first loop, the loops on the hook, on to the hand), k x that, smoothed in time (BUDGET_TAU s), spread evenly along it
BUDGET = float(os.environ.get("BUDGET", "0")); BTAU = float(os.environ.get("BUDGET_TAU", "0.3")); ext = None
def marks(r):
    acc = [s for s in r["frame"]["strands"] if s.get("accent")][0]
    return [0, r["sp"] + acc["slide"] - r["e"], r["sp"] + acc["hold"] - r["e"], r["h"] - r["e"] - 1]
new_c, t0 = [], time.time()
for r in recs:
    e, h = r["e"], r["h"]; base = r["base"]
    des = base[e:h]                                              # (base: the fabric prefix relaxed, the working yarn as designed)
    pre = base[:e + 1]; sa = arc(pre[::-1])                      # the finished part of the row, minus its last 3R (the same yarn)
    fixed = np.vstack([r["F"], pre[::-1][sa > 3.0 * R]])
    lo, hi = des.min(0) - 6 * R, des.max(0) + 6 * R
    fixed = fixed[np.all((fixed > lo) & (fixed < hi), axis=1)]
    hax, hneed = hook_pts(r["hook"])
    mat = None
    if BUDGET:
        seg_d = np.linalg.norm(np.diff(des, axis=0), axis=1); seg_o = np.linalg.norm(np.diff(r["old_c"][e:h], axis=0), axis=1)
        mk = marks(r); want = np.array([BUDGET * (seg_o[a:b].sum() - seg_d[a:b].sum()) for a, b in zip(mk[:-1], mk[1:])])
        ext = want if ext is None else ext + (want - ext) * (1 - np.exp(-1.0 / fps / BTAU))
        k = np.ones(len(seg_d))
        for (a, b), x in zip(zip(mk[:-1], mk[1:]), ext): k[a:b] = 1 + max(x, 0.0) / max(seg_d[a:b].sum(), 1e-6)
        mat = np.concatenate([[0.0], np.cumsum(seg_d * k)])
    out = rod.step(des, 1.0 / fps, fixed=fixed, hook=hax, hook_need=hneed, skin=r["skin"] if len(r["skin"]) else None, mat=mat)
    c = base.copy(); c[e:h] = out; new_c.append(c)
print("rod: %d frames %.1f s" % (len(recs), time.time() - t0), file=sys.stderr)

# ---- paths files: the recorded frames, old (as choreo) and new (the rod), same header
H = json.load(open(head_p))
def frame_with(r, c):
    fr = copy.deepcopy(r["frame"]); sp = r["sp"]; st = fr["strands"]
    fr["a"] = fr["a"] + 1e-6 * r["i"]                           # the rod moves on in held poses: the renderer must not copy the frame before
    acc = [k for k, s in enumerate(st) if s.get("accent")][0]
    st[acc]["pts"] = app(c[sp:]); st[acc - 1]["pts"] = app(c[:sp + 1])
    return fr
os.makedirs(out_d, exist_ok=True)
for name, frames in (("old", [r["frame"] for r in recs]), ("new", [frame_with(r, c) for r, c in zip(recs, new_c)])):
    D = dict(H); D["frames"] = frames; D["first"] = recs[0]["i"]
    json.dump(D, open(os.path.join(out_d, name + ".json"), "w"))

# ---- numbers on the working yarn (from where it leaves the fabric to the hand), frames a..b
def disp_geo(p, q):
    """mean distance from each point of p to the curve q, both ways (shape motion, not sliding along itself)"""
    return 0.5 * (cKDTree(q).query(p)[0].mean() + cKDTree(p).query(q)[0].mean())
def disp_mat(p, q, step=0.25):
    """mean displacement of points at the same arc length from the fabric (what the renderer's fibres follow)"""
    sp_, sq = arc(p), arc(q); s = np.arange(0, min(sp_[-1], sq[-1]), step)
    return np.linalg.norm(yarn_xpbd.interp_curve(s, sp_, p) - yarn_xpbd.interp_curve(s, sq, q), axis=1).mean()
rows = []
for k in range(1, len(recs)):
    r0, r1 = recs[k - 1], recs[k]
    if not (A0 <= r1["i"] <= B0): continue
    W = lambda r, c: c[r["e"]:r["h"]]
    d0, d1 = W(r0, r0["design"]), W(r1, r1["design"])
    o0, o1 = W(r0, r0["old_c"]), W(r1, r1["old_c"])
    n0, n1 = W(r0, new_c[k - 1]), W(r1, new_c[k])
    rows.append([r1["i"]] + [f(a, b) for a, b in ((d0, d1), (o0, o1), (n0, n1)) for f in (disp_geo, disp_mat)]
                + [arc(b)[-1] - arc(a)[-1] for a, b in ((d0, d1), (o0, o1), (n0, n1))]
                + [arc(o1)[-1] - arc(d1)[-1], arc(n1)[-1] - arc(d1)[-1]])
X = np.array(rows)
np.savetxt(os.path.join(out_d, "per_frame.tsv"), X, fmt="%.4f", delimiter="\t",
           header="frame\tdes_geo\tdes_mat\told_geo\told_mat\tnew_geo\tnew_mat\tdL_des\tdL_old\tdL_new\textra_old\textra_new")
def q(v): return "%.3f / %.3f / %.3f" % (np.median(v), np.percentile(v, 90), np.max(v))
eps = 0.02
print("frames %d-%d (%d steps); median / p90 / max, in yarn radii" % (A0, B0, len(X)))
print("per-frame motion, geometric : design %s | old %s | new %s" % (q(X[:, 1]), q(X[:, 3]), q(X[:, 5])))
print("per-frame motion, material  : design %s | old %s | new %s" % (q(X[:, 2]), q(X[:, 4]), q(X[:, 6])))
print("ratio to design (geo, med/p90): old %.2f / %.2f | new %.2f / %.2f" % (
    np.median(X[:, 3] / (X[:, 1] + eps)), np.percentile(X[:, 3] / (X[:, 1] + eps), 90),
    np.median(X[:, 5] / (X[:, 1] + eps)), np.percentile(X[:, 5] / (X[:, 1] + eps), 90)))
print("ratio to design (mat, med/p90): old %.2f / %.2f | new %.2f / %.2f" % (
    np.median(X[:, 4] / (X[:, 2] + eps)), np.percentile(X[:, 4] / (X[:, 2] + eps), 90),
    np.median(X[:, 6] / (X[:, 2] + eps)), np.percentile(X[:, 6] / (X[:, 2] + eps), 90)))
print("|frame-to-frame length change|: design %s | old %s | new %s" % (q(np.abs(X[:, 7])), q(np.abs(X[:, 8])), q(np.abs(X[:, 9]))))
print("length over the design        : old %s | new %s" % (q(X[:, 10]), q(X[:, 11])))
lg = rod.log[-(len(recs)):]
print("rod: max stretch error %.4f R, slack max %.2f R, contacts/frame median %d" % (
    max(l["stretch"] for l in lg), max(l["slack"] for l in lg), np.median([l["contacts"] for l in lg])))
