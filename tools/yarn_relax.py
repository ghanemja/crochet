# Keep yarn out of yarn: push centrelines apart until no two stretches of yarn that aren't neighbours along
# the same yarn come closer than two yarn radii (the surfaces touch at 2R), smoothing as it goes so the yarn
# doesn't kink. Used by choreo.py: once for the fabric, then every frame for the working yarn against it.
import numpy as np

def _pairs(P, ids, arc, R, reach, A=None):
    """close pairs (i, j), i < j, among P (or between A and P if A is given), skipping neighbours along a yarn"""
    out = []
    Q = P if A is None else A
    for c0 in range(0, len(Q), 512):
        d = np.linalg.norm(Q[c0:c0 + 512, None, :] - P[None, :, :], axis=2)
        if A is None:
            ii = np.arange(c0, min(c0 + 512, len(Q)))[:, None]
            same = (ids[c0:c0 + 512][:, None] == ids[None, :]) & (np.abs(arc[c0:c0 + 512][:, None] - arc[None, :]) < 3 * R)
            d[same | (ii >= np.arange(len(P))[None, :])] = np.inf
        i, j = np.nonzero(d < reach)
        out.append(np.stack([i + c0, j], 1))
    return np.concatenate(out) if out else np.zeros((0, 2), int)

def relax(polys, movable=None, fixed=None, R=1.0, iters=30, smooth=0.25, anchor=0.0):
    """polys: list of (N_k, 3) centrelines (separate yarns, or the pieces of one marked with the same id:
    give (points, id) tuples); movable: per poly a bool mask (default all); fixed: (M, 3) points the movable
    yarn keeps 2R from (they don't move), or (points, clearances) to give each its own (e.g. the hook's axis,
    kept its radius + R off); anchor: each step, the share of the way back to where it started (keeps a
    designed shape, giving way only where yarn meets yarn). -> the relaxed polylines"""
    pts, ids, arc, mov = [], [], [], []
    for k, item in enumerate(polys):
        p, yid = item if isinstance(item, tuple) else (item, k)
        p = np.asarray(p, float); pts.append(p)
        ids.append(np.full(len(p), yid))
        a = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
        arc.append(a)
        mov.append(np.ones(len(p), bool) if movable is None or movable[k] is None else np.asarray(movable[k], bool))
    off = np.cumsum([0] + [len(p) for p in pts])
    # arcs continue across pieces of the same yarn (given in order)
    last = {}
    for k in range(len(pts)):
        yid = ids[k][0]
        if yid in last: arc[k] = arc[k] + last[yid]
        last[yid] = arc[k][-1]
    P = np.vstack(pts); I = np.concatenate(ids); S = np.concatenate(arc); M = np.concatenate(mov)
    P0 = P.copy()
    ends = np.zeros(len(P), bool); ends[off[:-1]] = True; ends[off[1:] - 1] = True
    Fneed = None
    if isinstance(fixed, tuple): fixed, Fneed = fixed
    F = None if fixed is None or len(fixed) == 0 else np.asarray(fixed, float)
    if F is not None: Fneed = np.full(len(F), 2.0 * R) if Fneed is None else np.asarray(Fneed, float)
    need = 2.0 * R; touched = np.zeros(len(P), bool)
    for it in range(iters):
        if it % 6 == 0:
            pr = _pairs(P, I, S, R, need * 1.6)
            fp = _pairs(F, None, None, R, max(need, Fneed.max()) * 1.4, A=P[M]) if F is not None else None
            midx = np.nonzero(M)[0]
        moved = np.zeros_like(P); cnt = np.zeros(len(P))
        if len(pr):
            T = np.zeros_like(P)                                     # tangents, within each piece
            for k0, k1 in zip(off[:-1], off[1:]):
                if k1 - k0 > 1: T[k0:k1] = np.gradient(P[k0:k1], axis=0)
            T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
            a, b = pr[:, 0], pr[:, 1]; d = P[b] - P[a]; L = np.linalg.norm(d, axis=1) + 1e-9
            # strands that cross part along their common normal: the gap between the nearest sample points
            # of two crossing centrelines points anywhere (it is the sampling), and pushing along it only
            # slides them along each other; strands side by side (parallel) part along the gap as before
            n = np.cross(T[a], T[b]); nn = np.linalg.norm(n, axis=1); cr = nn > 0.35
            n = n / (nn[:, None] + 1e-9); dn = np.einsum("ij,ij->i", d, n); sg = np.where(dn < 0, -1.0, 1.0)
            dirn = np.where(cr[:, None], n * sg[:, None], d / L[:, None]); sep = np.where(cr, np.abs(dn), L)
            short = np.maximum(0, need - sep) * (L < need); k = short > 0
            a, b, dirn, short = a[k], b[k], dirn[k], short[k]
            wa = M[a].astype(float); wb = M[b].astype(float); tot = np.maximum(wa + wb, 1e-9)
            push = dirn * short[:, None]
            np.add.at(moved, a, -push * (wa / tot)[:, None]); np.add.at(cnt, a, wa)
            np.add.at(moved, b, push * (wb / tot)[:, None]); np.add.at(cnt, b, wb)
        if fp is not None and len(fp):
            a = midx[fp[:, 0]]; d = P[a] - F[fp[:, 1]]; L = np.linalg.norm(d, axis=1) + 1e-9
            short = np.maximum(0, Fneed[fp[:, 1]] - L); k = short > 0
            np.add.at(moved, a[k], (d[k] / L[k][:, None]) * short[k][:, None]); np.add.at(cnt, a[k], 1)
        upd = cnt > 0
        P[upd] += moved[upd] / np.maximum(cnt[upd], 1)[:, None] * 0.8
        touched |= upd
        # smooth only round where the yarn was pushed (not its ends), so the pushes don't leave kinks; the
        # rest (loops on the hook, the way round the fingers) keeps its shape
        near = touched.copy()
        for _ in range(4): near[1:] |= near[:-1]; near[:-1] |= near[1:]
        lap = np.zeros_like(P); lap[1:-1] = P[:-2] + P[2:] - 2 * P[1:-1]
        sm = M & ~ends & near
        P[sm] += smooth * lap[sm]
        if anchor: P[M] += anchor * (P0[M] - P[M])
    return [P[off[k]:off[k + 1]] for k in range(len(pts))]
