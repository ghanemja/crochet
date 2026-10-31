# Temporal numbers on the working yarn (where it leaves the fabric to the left hand) of paths made with PHYS=1 (choreo keeps the
# design in each frame's "phys"): per-frame motion against the design's, and frame-to-frame length change.
#   python3 tools/queue/physics_metrics.py <paths.json> [<other paths.json> ...] [--range a:b]
# The first file's "phys" gives the design and the e/h indices for all of them (the post-pass keeps point counts).
import sys, json
import numpy as np
from scipy.spatial import cKDTree
rng = (0, 10 ** 9)
if "--range" in sys.argv: i = sys.argv.index("--range"); rng = tuple(int(x) for x in sys.argv[i + 1].split(":")); del sys.argv[i:i + 2]
TO_APP = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
def arc(p): return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
def work(fr, ph, K):
    st = fr["strands"]; acc = [k for k, s in enumerate(st) if s.get("accent")][0]
    c = np.vstack([np.asarray(st[acc - 1]["pts"]), np.asarray(st[acc]["pts"])[1:]]) @ TO_APP / K
    return c[ph["e"]:ph["h"]]
def mat(p, q, step=0.25):
    sp, sq = arc(p), arc(q); s = np.arange(0, min(sp[-1], sq[-1]), step)
    ip = lambda s_, a, c: np.stack([np.interp(s_, a, c[:, k]) for k in range(3)], 1)
    return np.linalg.norm(ip(s, sp, p) - ip(s, sq, q), axis=1).mean()
def geo(p, q): return 0.5 * (cKDTree(q).query(p)[0].mean() + cKDTree(p).query(q)[0].mean())
Ds = [json.load(open(p)) for p in sys.argv[1:]]; F0 = Ds[0]["frames"]; K = F0[0]["strands"][0]["radius"]
cols = {"design": []}; cols.update({p: [] for p in sys.argv[1:]})
for i in range(max(1, rng[0]), min(len(F0), rng[1] + 1)):
    a, b = F0[i - 1].get("phys"), F0[i].get("phys")
    if not a or not b or a["e"] != b["e"]: continue
    da, db = np.asarray(a["work"]) @ TO_APP / K, np.asarray(b["work"]) @ TO_APP / K
    rows = {"design": (da, db)}
    for p, D in zip(sys.argv[1:], Ds): rows[p] = (work(D["frames"][i - 1], a, K), work(D["frames"][i], b, K))
    for k, (x, y) in rows.items(): cols[k].append((geo(x, y), mat(x, y), arc(y)[-1] - arc(x)[-1], arc(y)[-1] - arc(db)[-1]))
d = np.array(cols["design"]); eps = 0.02
print("%d frame steps; median / p90" % len(d))
for k, v in cols.items():
    v = np.array(v)
    print("%-28s shape %.3f/%.3f (x%.2f/%.2f)  crawl %.3f/%.3f (x%.2f/%.2f)  |dL| %.2f/%.2f max %.1f  over design %+.1f" % (
        k[-28:], np.median(v[:, 0]), np.percentile(v[:, 0], 90), np.median(v[:, 0] / (d[:, 0] + eps)), np.percentile(v[:, 0] / (d[:, 0] + eps), 90),
        np.median(v[:, 1]), np.percentile(v[:, 1], 90), np.median(v[:, 1] / (d[:, 1] + eps)), np.percentile(v[:, 1] / (d[:, 1] + eps), 90),
        np.median(np.abs(v[:, 2])), np.percentile(np.abs(v[:, 2]), 90), np.abs(v[:, 2]).max(), np.median(v[:, 3])))
