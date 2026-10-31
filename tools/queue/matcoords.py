# Material coordinates for a paths file: each strand gets "m", per point, the yarn's own coordinate along it, carried
# from frame to frame. The renderer lays the twist, fibres and flyaways out along m (render_tutorial.py, yarn_coords);
# without it m comes from each frame's arc length, and choreo rebuilds the yarn every frame (assemble + relax) with a
# length that jumps by up to ~1 R between frames, so every fibre slid along the yarn on its own: the fibres crawled
# while the yarn as a whole stood still.
#   python3 tools/queue/matcoords.py <paths.json> [out.json]       (in place without out)
# Each point inherits m from the nearest point of the same yarn in the frame before (within REACH, and within WIN of
# what arc length would give it); where nothing is near (the yarn moved) the offset is carried over from its
# neighbours along the strand. m never runs backwards along a strand.
import sys, json
import numpy as np

REACH, WIN, SMOOTH = 0.8, 4.0, 9          # in yarn radii; SMOOTH: points in the offset's running median

def arc(p):
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])

def chains(fr):
    """the yarns of a frame as lists of strand indices (one yarn split into colours = consecutive strands that join)"""
    out, prev = [], None
    for i, st in enumerate(fr["strands"]):
        if not st.get("visible") or len(st.get("pts", [])) < 3 or st.get("closed"): prev = None; continue
        p = np.asarray(st["pts"], float)
        if prev is not None and np.linalg.norm(p[0] - prev) < 1e-6: out[-1].append(i)
        else: out.append([i])
        prev = p[-1]
    return out

def held_lengths(D):
    """as render_tutorial.py: per yarn, the median length to the far end of its held ("hold") strand"""
    acc = {}
    for fr in D["frames"]:
        for ch in chains(fr):
            m = 0.0
            for i in ch:
                st = fr["strands"][i]; m += arc(np.asarray(st["pts"], float))[-1]
                if "hold" in st: acc.setdefault(ch[0], []).append(m)
    return {k: float(np.median(v)) for k, v in acc.items()}

def base_m(st, m_start, m_hold):
    """render_tutorial.py's yarn_coords, per point: arc length on from m_start; a held strand counts back from m_hold"""
    a = arc(np.asarray(st["pts"], float)); L = a[-1]
    if "hold" not in st or m_hold is None: return m_start + a
    sa, sh = a[min(st["slide"], len(a) - 1)], a[min(st["hold"], len(a) - 1)]
    W = max(sh - sa, 1e-6); mh = m_hold
    if (m_start + L) - mh > 0.7 * W: mh = m_start + L - 0.7 * W
    w = np.clip((a - sa) / W, 0, 1)
    return (m_start + a) * (1 - w) + (mh - (L - a)) * w

def running_median(x, k):
    if len(x) < 3: return x
    h = k // 2; xp = np.pad(x, h, mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(xp, k), axis=1)

def main():
    src = sys.argv[1]; dst = sys.argv[2] if len(sys.argv) > 2 else src
    D = json.load(open(src)); HELD = held_lengths(D)
    prev = {}; stats = [0, 0]                       # per yarn (its first strand's index): (points, m) in the frame before
    for fr in D["frames"]:
        cur = {}
        for ch in chains(fr):
            P = [np.asarray(fr["strands"][i]["pts"], float) for i in ch]; R = fr["strands"][ch[0]]["radius"]
            mb, m0 = [], 0.0
            for i, p in zip(ch, P):
                b = base_m(fr["strands"][i], m0, HELD.get(ch[0])); mb.append(b); m0 = b[-1]
            X = np.vstack(P); B = np.concatenate(mb); off = np.full(len(X), np.nan)
            if ch[0] in prev:
                prev_pts, prev_m = prev[ch[0]]
                for c0 in range(0, len(X), 512):
                    d = np.linalg.norm(X[c0:c0 + 512, None, :] - prev_pts[None, :, :], axis=2)
                    d[np.abs(prev_m[None, :] - B[c0:c0 + 512, None]) > WIN * R] = np.inf
                    j = d.argmin(1); ok = d[np.arange(len(j)), j] < REACH * R
                    off[c0:c0 + 512][ok] = prev_m[j[ok]] - B[c0:c0 + 512][ok]
            have = ~np.isnan(off); stats[0] += have.sum(); stats[1] += len(off)
            if have.any():
                idx = np.arange(len(off)); off = np.interp(idx, idx[have], off[have])   # carried over where the yarn moved
                off = running_median(off, SMOOTH)
            else:
                off = np.zeros(len(X))
            M = B + off
            M = np.maximum.accumulate(M)                                           # never runs backwards (locally; no re-integration)
            k = 0
            for i, p in zip(ch, P):
                fr["strands"][i]["m"] = [round(float(x), 4) for x in M[k:k + len(p)]]; k += len(p)
            cur[ch[0]] = (X, M)
        prev = cur
    json.dump(D, open(dst, "w"))
    print("matcoords: %s -> %s, %d frames, %.0f%% of points inherited m from the frame before"
          % (src, dst, len(D["frames"]), 100.0 * stats[0] / max(1, stats[1])))

if __name__ == "__main__":
    main()
