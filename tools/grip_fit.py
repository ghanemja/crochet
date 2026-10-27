# Where the hook's shaft lies in the right hand (tripod grip): the straight line, in the hand's
# frame, on which the thumb pad, the index pad, the side of the middle fingertip and the web
# between thumb and index all rest at the shaft's radius, with no skin inside the shaft.
# choreo.py calls fit() once per hands bake and caches the answer next to hands.json.
import numpy as np

def nrm(a): return a / np.linalg.norm(a)

def seg_d(p, a, b):
    t = np.clip(((p - a) @ (b - a)) / ((b - a) @ (b - a)), 0, 1)
    return np.linalg.norm(p - (a + t[:, None] * (b - a)), axis=1)

def nelder(f, x0, s=1.0, it=500):
    n = len(x0); X = [np.array(x0, float)] + [np.array(x0, float) + s * np.eye(n)[i] for i in range(n)]; F = [f(x) for x in X]
    for _ in range(it):
        o = np.argsort(F); X = [X[i] for i in o]; F = [F[i] for i in o]
        c = np.mean(X[:-1], 0); xr = c + (c - X[-1]); fr = f(xr)
        if fr < F[0]:
            xe = c + 2 * (c - X[-1]); fe = f(xe); X[-1], F[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < F[-2]: X[-1], F[-1] = xr, fr
        else:
            xc = c + 0.5 * (X[-1] - c); fc = f(xc)
            if fc < F[-1]: X[-1], F[-1] = xc, fc
            else: X = [X[0] + 0.5 * (x - X[0]) for x in X]; F = [f(x) for x in X]
    return X[0], F[0]

def fit(P, SK, r):
    """P: named joints, SK: skin vertices (hand frame, any unit), r: shaft radius (same unit).
    -> (point on the axis near the fingertips, unit direction toward the web), {part: gap}"""
    def group(f):
        d = seg_d(SK, P[f + "_dip"], P[f + "_tip"]); return d < 0.9 * d.min() + 3.0 * r / 1.15
    web = (P["thumb_knuckle"] + P["index_knuckle"]) / 2
    G = {"thumb": group("thumb"), "index": group("index"), "middle": group("middle"),
         "web": np.linalg.norm(SK - web, axis=1) < 4.0 * r / 1.15}
    grip0 = (P["thumb_tip"] + P["index_dip"] + P["middle_dip"]) / 3
    d0 = nrm(web - grip0); e1 = nrm(np.cross(d0, [0, 0, 1.0])); e2 = np.cross(d0, e1)
    q = SK - grip0; t = q @ d0
    near = (np.linalg.norm(q - t[:, None] * d0, axis=1) < 6 * r) & (t > -12 * r) & (t < 36 * r)
    SK = SK[near]; G = {g: m[near] for g, m in G.items()}
    def line(x): return grip0 + x[0] * e1 + x[1] * e2, nrm(d0 + x[2] * e1 + x[3] * e2)
    def gaps(x):
        o, d = line(x); q = SK - o; t = q @ d; dd = np.linalg.norm(q - t[:, None] * d, axis=1)
        return dd, t
    def cost(x):
        dd, t = gaps(x); seg = (t > -10 * r) & (t < 35 * r)
        c = 30 * (np.maximum(0, r - dd[seg]) ** 2).sum()
        return c + sum((dd[m].min() - r) ** 2 for m in G.values())
    best = min((nelder(cost, x0, s=r) for x0 in ([0, 0, 0, 0], [-r, -2.5 * r, 0.5, 0.6])), key=lambda b: b[1])
    o, d = line(best[0]); dd, _ = gaps(best[0])
    o = o + d * ((grip0 - o) @ d)
    if (web - o) @ d < 0: d = -d
    return o, d, {g: round(float(dd[m].min() - r), 3) for g, m in G.items()}
