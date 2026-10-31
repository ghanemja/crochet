# The working yarn as a rod stepped in time (XPBD, small steps: Macklin et al. 2019), instead of re-relaxed from
# scratch every frame (yarn_relax.py). One state carries from frame to frame:
#   - inextensible: the chain's distance constraints solved directly every iteration (tridiagonal, as Bender's direct
#     solver for rods), so no stretch is left (<1e-4 R); bending set from a bending length against the pull (see
#     __init__); no twist: the renderer lays the plies' twist out along the arc, so the centreline is all it needs;
#   - material coordinates: particle i sits at a fixed arc length s_i = i * ds from where the yarn leaves the fabric
#     (pinned there); yarn is fed in and taken back at the other end, where it runs over the left index (pinned to
#     choreo's hand point), so the yarn between them slides through the hand instead of changing length; the hand
#     lets more through (smoothly) when the contacts want the yarn longer than the design, and takes it back;
#   - pulled softly toward choreo's designed path at the same material place (a zero-length spring per particle,
#     stiffer where the design has it round the hook: the loops ride the shaft), so the choreography and the
#     crochet topology are kept and the physics only decides how it settles and moves;
#   - kept 2R off the fabric and off itself (2R between centrelines: the surfaces touch), off the hook's shaft
#     (its profile + 0.9R, as yarn_clear) and the left hand's skin (1.06R), with Coulomb-like position friction.
# Units: lengths in yarn radii (choreo's design space, R = 1), time in seconds, mass in kg.
import numpy as np
from scipy.spatial import cKDTree
from scipy.linalg import solve_banded

R_M = 1.8e-3                 # the yarn radius in metres (the renderer's yarn is 3.6 mm thick)
TEX = 5e-4                   # linear density, kg/m (worsted ~ 200 m / 100 g)

def arc(p):
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])

def interp_curve(s_q, s, p):
    return np.stack([np.interp(s_q, s, p[:, k]) for k in range(3)], 1)

class YarnRod:
    # defaults from the sc 280-340 study (tools/queue/physics_study.py): w_soft 20 Hz (10: more yarn through yarn,
    # 30+: the pull holds it in the fabric), 10 iterations x 60 substeps a frame (40 x 8: sc gate 0.61R, hdc 0.96R; 60 x 10: 0.24R, 0.71R), feed gain 1 (0.5: yarn through the row at sc 318; 2: the length swings)
    def __init__(s, ds=0.5, substeps=60, iters=10, ei=0.0, lb=1.0, tex=TEX, w_soft=20.0, w_hook=20.0, zeta=1.0,
                 mu=0.4, feed_tau=0.5, gravity=0.0, fade=4.0, feed_gain=1.0, slack_tau=0.5, contact_last=0, R=1.0):
        s.ds, s.n_sub, s.iters, s.R = ds, int(substeps), int(iters), R
        s.m = tex * ds * R_M                                    # kg per particle
        s.w_soft, s.w_hook = 2 * np.pi * w_soft, 2 * np.pi * w_hook   # the pull toward the design, as frequencies
        # bending: energy EI/2 kappa^2 ds with kappa ~ |x[i-1] - 2 x[i] + x[i+1]| / ds^2. A real yarn under the hands'
        # tension T only rounds off what is shorter than its bending length sqrt(EI / T) (~0.5-1 R for EI ~ 3e-7 N m^2,
        # T ~ 0.3 N), and the pull toward the design stands in for that tension; so the rod's EI is set from the
        # bending length lb against the pull, EI = lambda omega^2 lb^4 (ei > 0: a given EI in N m^2 instead)
        lam = tex * R_M                                          # kg per yarn radius
        ei_u = ei / R_M ** 3 if ei > 0 else lam * s.w_soft ** 2 * lb ** 4
        s.k_bend = ei_u / ds ** 3
        s.damping = 2.0 * zeta * s.w_soft                        # critically damped toward the design (yarn has next to no inertia: contact
                                                                 # friction and the hands' grip, not the air, take its energy)
        s.mu, s.feed_tau, s.fade, s.feed_gain, s.slack_tau = mu, feed_tau, fade, feed_gain, slack_tau
        s.contact_last = bool(contact_last)
        s.g = np.array([0.0, 0.0, -9.81 / R_M]) * gravity
        s.x = None; s.slack = 0.0; s.slack_s = 0.0; s.prev = None; s.log = []

    # ------------------------------------------------------------------ material layout
    def _layout(s, L):
        n_int = max(2, int(np.floor(L / s.ds - 0.3)))
        return np.concatenate([np.arange(n_int + 1) * s.ds, [L]])

    def _relayout(s, L):
        """material length now L: particles at the same material places stay; the end (the hand) moves on, yarn
        fed in appears along the last segment, yarn taken back disappears into the hand"""
        sn = s._layout(L)
        if s.x is None: return sn
        so, xo, vo = s.s, s.x, s.v
        xn = interp_curve(sn, so, xo); vn = interp_curve(sn, so, vo)
        k = min(len(sn), len(so)) - 1                            # interior particles kept exactly
        xn[:k] = xo[:k]; vn[:k] = vo[:k]
        s.x, s.v = xn, vn
        return sn

    # ------------------------------------------------------------------ one video frame
    def step(s, design, dt, fixed=None, fixed_need=None, hook=None, hook_need=None, skin=None, skin_need=1.06, mat=None):
        """design: (M, 3) choreo's working yarn this frame, from where it leaves the fabric to the hand (both ends
        pinned); fixed: (K, 3) yarn it keeps 2R off (fixed_need per point); hook: (H, 3) the shaft's axis points
        (hook_need per point); skin: (S, 3); mat: (M,) the material place of each design point (default its arc
        length): more yarn than the design's own length where the design is drawn tighter than the yarn is thick.
        -> (M, 3) the rod at the design's points' material places"""
        R = s.R; sD = arc(design) if mat is None else np.asarray(mat, float); Ld = sD[-1]
        if s.x is None:                                          # start at rest on the design
            s.slack = 0.0; s.s = s._layout(Ld); s.x = interp_curve(s.s, sD, design); s.v = np.zeros_like(s.x)
        Lm = Ld + s.slack_s
        s.s = s._relayout(Lm); N = len(s.s)
        rest = np.diff(s.s)
        tgt1 = interp_curve(s.s * (Ld / Lm), sD, design)
        if s.prev is None: tgt0, hook0 = tgt1, hook
        else:
            pd, ph, sp = s.prev; tgt0 = interp_curve(s.s / s.s[-1] * sp[-1], sp, pd)
            hook0 = ph if ph is not None and hook is not None and len(ph) == len(hook) else hook
        s.prev = (design.copy(), None if hook is None else hook.copy(), sD.copy())
        # stiff where the design has the yarn round the hook (the loops riding the shaft)
        om = np.full(N, s.w_soft)
        if hook is not None:
            d_h, j_h = cKDTree(hook).query(tgt1)
            om[d_h < hook_need[j_h] + 1.5 * R] = s.w_hook
        w = np.full(N, 1.0 / s.m); w[0] = w[-1] = 0.0
        # colliders: the fabric (static) and the skin in one tree, each point its own clearance
        pts, need = [], []
        if fixed is not None and len(fixed): pts.append(fixed); need.append(np.full(len(fixed), 2.0 * R) if fixed_need is None else fixed_need)
        if skin is not None and len(skin): pts.append(skin); need.append(np.full(len(skin), skin_need * R))
        FP = np.vstack(pts) if pts else np.zeros((0, 3)); FN = np.concatenate(need) if need else np.zeros(0)
        ftree = cKDTree(FP) if len(FP) else None; fmax = FN.max() if len(FN) else 0.0
        h = dt / s.n_sub; nb = s.k_bend * h * h
        excess = 0.0; ncont = 0
        for sub in range(s.n_sub):
            a = (sub + 1) / s.n_sub
            T = tgt0 + (tgt1 - tgt0) * a
            HK = None if hook is None else hook0 + (hook - hook0) * a
            xp = s.x.copy()
            s.x = s.x + s.v * h + s.g * h * h * (w > 0)[:, None]
            s.x[0], s.x[-1] = T[0], T[-1]
            for it in range(s.iters):
                # the pull toward the design (XPBD zero-length spring, compliance 1 / (m omega^2))
                c = (om * h) ** 2; s.x[1:-1] += (T[1:-1] - s.x[1:-1]) * (c / (1 + c))[1:-1, None]
                # bending: d = x[i-1] - 2 x[i] + x[i+1] -> 0, three colours
                for col in range(3):
                    i = np.arange(1 + col, N - 1, 3)
                    d = s.x[i - 1] - 2 * s.x[i] + s.x[i + 1]; C = np.linalg.norm(d, axis=1) + 1e-12; n = d / C[:, None]
                    dl = -C / ((w[i - 1] + 4 * w[i] + w[i + 1]) + 1.0 / nb)
                    s.x[i - 1] += (w[i - 1] * dl)[:, None] * n; s.x[i] += (-2 * w[i] * dl)[:, None] * n; s.x[i + 1] += (w[i + 1] * dl)[:, None] * n
                # contacts with the fixed yarn, skin and hook
                ncont = s._contacts(ftree, FP, FN, fmax, HK, hook_need, xp, w)
                s._self(xp, w)
                if sub == s.n_sub - 1 and it == s.iters - 1:   # how much longer the contacts want it: the pull on the hand
                    want = arc(s.x)[-1] - s.s[-1]
                s._inextensible(rest, w)
            if s.contact_last:                                   # contacts have the last word (a hair of stretch, no yarn through yarn)
                s._contacts(ftree, FP, FN, fmax, HK, hook_need, xp, w); s._self(xp, w)
            s.v = (s.x - xp) / h * np.exp(-s.damping * h)
            s.v[0] = s.v[-1] = 0.0
        L_now = arc(s.x)[-1]; excess = s.feed_gain * want
        # the yarn slides through the left index: pulled taut beyond the hold, the hand gives yarn (capstan
        # friction lets it slip at once); slack drifts back to the design's length as the hand takes it in
        s.slack = max(0.0, s.slack * np.exp(-dt / s.feed_tau) + max(0.0, excess))
        s.slack_s += (s.slack - s.slack_s) * (1 - np.exp(-dt / s.slack_tau))   # the hand lets yarn through smoothly
        s.log.append(dict(L_des=Ld, L_mat=Lm, L_rod=L_now, slack=s.slack, contacts=ncont,
                          stretch=float(np.abs(np.linalg.norm(np.diff(s.x, axis=0), axis=1) - rest).max())))
        return interp_curve(sD * (Lm / Ld), s.s, s.x)

    def _inextensible(s, rest, w, newton=3):
        """every edge back to its rest length at once: the chain's distance constraints linearised are tridiagonal in
        their multipliers (J W J^T dl = -C), solved directly (Newton steps), so no stretch is left over however long"""
        for _ in range(newton):
            d = np.diff(s.x, axis=0); L = np.linalg.norm(d, axis=1) + 1e-12; n = d / L[:, None]; C = L - rest
            if np.abs(C).max() < 1e-4: break
            M = len(C); ab = np.zeros((3, M))
            ab[1] = w[:-1] + w[1:]
            off = -w[1:-1] * np.einsum("ij,ij->i", n[:-1], n[1:])
            ab[0, 1:] = off; ab[2, :-1] = off
            ab[1] = np.maximum(ab[1], 1e-30)
            lam = solve_banded((1, 1), ab, -C)
            f = n * lam[:, None]
            dx = np.zeros_like(s.x); dx[:-1] -= f; dx[1:] += f
            s.x += w[:, None] * dx

    def _contacts(s, ftree, FP, FN, fmax, HK, hook_need, xp, w):
        x = s.x; R = s.R; corr = np.zeros_like(x); cnt = np.zeros(len(x)); dep = np.zeros(len(x))
        # the yarn comes out of the fabric where it is pinned: its contacts fade in over its first FADE radii
        fade = np.clip(s.s / s.fade, 0.0, 1.0) if s.fade > 0 else np.ones(len(x))
        for tree, P, NEED, mx in ((ftree, FP, FN, fmax), (cKDTree(HK) if HK is not None else None, HK, hook_need, None)):
            if tree is None: continue
            mx = NEED.max() if mx is None else mx
            dd, jj = tree.query(x, k=6, distance_upper_bound=mx)
            for k in range(dd.shape[1]):
                m = np.isfinite(dd[:, k]) & (w > 0)
                if not m.any(): continue
                j = jj[m, k]; q = x[m] - P[j]; L = np.linalg.norm(q, axis=1) + 1e-12
                short = NEED[j] * fade[m] - L; hit = short > 0
                if not hit.any(): continue
                idx = np.nonzero(m)[0][hit]
                corr[idx] += q[hit] / L[hit, None] * short[hit, None]; cnt[idx] += 1
                dep[idx] = np.maximum(dep[idx], short[hit])
        c = cnt > 0
        if c.any():
            x[c] += corr[c] / cnt[c, None]
            # friction: the slip along the contact this substep is cancelled while under mu x the push
            nrm = corr[c] / (np.linalg.norm(corr[c], axis=1, keepdims=True) + 1e-12)
            mv = x[c] - xp[c]; tan = mv - (mv * nrm).sum(1, keepdims=True) * nrm; tl = np.linalg.norm(tan, axis=1) + 1e-12
            lim = s.mu * dep[c]; f = np.minimum(1.0, lim / tl)
            x[c] -= tan * f[:, None]
        return int(c.sum())

    def _self(s, xp, w):
        x = s.x; R = s.R
        pr = cKDTree(x).query_pairs(2.0 * R, output_type="ndarray")
        if not len(pr): return
        a, b = pr[:, 0], pr[:, 1]
        k = np.abs(s.s[a] - s.s[b]) > 3.0 * R
        a, b = a[k], b[k]
        if not len(a): return
        d = x[b] - x[a]; L = np.linalg.norm(d, axis=1) + 1e-12; short = 2.0 * R - L
        wa, wb = w[a], w[b]; ws = np.maximum(wa + wb, 1e-30)
        push = d / L[:, None] * short[:, None]
        corr = np.zeros_like(x); cnt = np.zeros(len(x))
        np.add.at(corr, a, -push * (wa / ws)[:, None]); np.add.at(cnt, a, 1)
        np.add.at(corr, b, push * (wb / ws)[:, None]); np.add.at(cnt, b, 1)
        c = cnt > 0; x[c] += corr[c] / cnt[c, None]
