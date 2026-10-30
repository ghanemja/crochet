# Yarn through yarn: where the working yarn's centreline comes closer than two yarn radii (the surfaces touch
# at 2R) to another strand, or to itself further along.
#   python3 tools/yarn_contact.py <paths.json> [a:b:step] [--all]
# Prints the worst frames (depth below 2R in yarn radii, and which strands), and a summary line. Strands that
# continue one another (one yarn split into colours) are one yarn: points on it closer than 3R along it are
# neighbours, not a contact. --all: static fabric strands against each other too.
import sys, json
import numpy as np

D = json.load(open(sys.argv[1]))
rng = sys.argv[2] if len(sys.argv) > 2 and ":" in sys.argv[2] else "0:100000:1"
a, b, st_ = (int(x) for x in rng.split(":")); ALL = "--all" in sys.argv
frames = D["frames"][a:b:st_]

def resample(p, step):
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)])
    n = max(2, int(s[-1] / step) + 1); si = np.linspace(0, s[-1], n)
    return np.stack([np.interp(si, s, p[:, k]) for k in range(3)], 1), si

def yarns(fr):
    """-> list of (points, arc along its yarn, yarn id, strand index, moving?)"""
    out, prev = [], None
    for i, st in enumerate(fr["strands"]):
        if not st.get("visible") or len(st.get("pts", [])) < 2: prev = None; continue
        p = np.asarray(st["pts"], float); R = st["radius"]
        q, s = resample(p, R * 0.5)
        cont = prev is not None and not st.get("closed") and np.linalg.norm(p[0] - prev[0]) < 1e-6
        yid, s0 = (prev[1], prev[2]) if cont else (i, 0.0)
        moving = bool(st.get("accent")) or "hold" in st or (prev is not None and cont and prev[3])
        out.append([q, s + s0, yid, i, moving, R])
        prev = (p[-1], yid, s0 + s[-1], moving)
    ids_moving = {y[2] for y in out if y[4]}                     # the whole yarn the working yarn belongs to
    for y in out: y[4] = y[2] in ids_moving
    return out

worst = []
for k, fr in enumerate(frames):
    fi = a + k * st_; Y = yarns(fr)
    best = (0.0, None)
    for ia, ya in enumerate(Y):
        if not ya[4] and not ALL: continue
        for ib, yb in enumerate(Y):
            if ib < ia and (yb[4] or ALL): continue              # each pair once
            if not ya[4] and not yb[4] and not ALL: continue
            R = ya[5]; pa, pb = ya[0], yb[0]
            for c0 in range(0, len(pa), 400):
                A = pa[c0:c0 + 400]
                d = np.linalg.norm(A[:, None, :] - pb[None, :, :], axis=2)
                if ya[2] == yb[2]:                               # the same yarn: skip neighbours along it
                    d[np.abs(ya[1][c0:c0 + 400][:, None] - yb[1][None, :]) < 3 * R] = np.inf
                m = d.min()
                if m < 2 * R:
                    dep = (2 * R - m) / R
                    if dep > best[0]: best = (dep, (ya[3], yb[3]))
    worst.append((best[0], fi, best[1]))
worst.sort(reverse=True)
for dep, fi, pair in worst[:8]:
    if dep > 0: print("YARN %d depth %.2fR strands %s" % (fi, dep, pair))
n_bad = sum(1 for w in worst if w[0] > 0.1)
print("SUMMARY worst %.2fR at frame %d; %d of %d frames deeper than 0.1R" % (worst[0][0], worst[0][1], n_bad, len(worst)))
