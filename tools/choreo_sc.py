# Single crochet, choreographed for the offline render (tools/render_tutorial.py).
#
#   python3 tools/choreo_sc.py build/paths/sc_v2.json [--fps 30]
#
# Writes the same JSON the app's exportLearnPaths() produces, but the motion is
# authored here around a real hook: loops sit snug on the shaft, every yarn over
# lands in the throat, the pull-ups go through the hole under the V of the
# stitch below, and the yarn is one continuous path fabric -> loops on the hook
# -> working yarn -> (off-screen) index finger. A last pass pushes any yarn
# point out of the hook so nothing passes through the metal.
#
# Design space: Z up, X along the row (worked right to left), -Y toward the
# camera, yarn radius R = 1. Exported in the app's frame (Y up) at the app's
# yarn radius, so the renderer needs no special case.
import json, math, sys, argparse
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--hands", action="store_true")   # draw hands in the guided take (work in progress)
ap.add_argument("--cues", default="")      # also write the freeze-frame callouts (assets/tutorials/<key>.cues.json)
A = ap.parse_args()

STEPS = ["Insert hook", "Yarn over", "Pull up a loop (2 on hook)", "Yarn over", "Pull through both loops"]
STEP_DUR = 2.6
R, RH = 1.0, 1.15                  # yarn radius, hook shaft radius
P, H, B = 4.6, 4.4, 1.45           # stitch pitch, row height, half-depth of a V
APP_R = 0.36                       # app yarn radius (export scale)
# teaching colours: blue fabric, orange working yarn — mid-tones that show the fibres,
# and a pair that stays distinct for every common colour-vision deficiency
TUTORIAL_FABRIC, TUTORIAL_WORKING = "#4f7fc4", "#f0862a"
F = np.array([-3.4 * P, 10.0, 16.0])   # the index finger the working yarn runs over (off-screen)

def v(*a): return np.array(a, float)
def nrm(a): return a / (np.linalg.norm(a) + 1e-12)
def ease(t): t = min(1, max(0, t)); return t * t * (3 - 2 * t)
def lerp(a, b, t): return a + (b - a) * t
def slerp_dir(a, b, t):
    a, b = nrm(a), nrm(b); d = np.clip(a @ b, -1, 1); w = math.acos(d)
    if w < 1e-5: return a
    return nrm((math.sin((1 - t) * w) * a + math.sin(t * w) * b) / math.sin(w))
def bez(p0, p1, p2, p3, t):
    s = 1 - t; return s**3 * p0 + 3 * s * s * t * p1 + 3 * s * t * t * p2 + t**3 * p3

# ---------------------------------------------------------------- hook
# local frame: tip at the origin, +Y up the shaft, throat (the notch the yarn sits in) on +X
def hook_profile(y):
    """(centre x, radius) of the hook's cross-section at height y above the tip."""
    r = RH
    if y < 0.9 * r:   return 0.12 * r, r * 0.93 * math.sqrt(max(0.0, 1 - (1 - y / (0.9 * r)) ** 2)) + 0.02
    if y < 1.55 * r:  return 0.12 * r, 0.93 * r                                  # head
    if y < 1.95 * r:  t = (y - 1.55 * r) / (0.4 * r); return lerp(0.12 * r, -0.42 * r, t), lerp(0.93 * r, 0.5 * r, t)  # under-cut of the lip
    if y < 3.0 * r:   return -0.42 * r, 0.5 * r                                   # throat
    if y < 5.2 * r:   t = ease((y - 3.0 * r) / (2.2 * r)); return lerp(-0.42 * r, 0.0, t), lerp(0.5 * r, r, t)
    return 0.0, r
THROAT_D = 2.45 * RH              # height of the throat above the tip

def hook_mesh():
    ys = np.concatenate([np.linspace(0, 5.6 * RH, 70), np.linspace(5.8 * RH, 70, 12)])
    nseg = 28; ang = np.linspace(0, 2 * math.pi, nseg, endpoint=False)
    rings = [[(cx + r * math.cos(a), y, r * math.sin(a)) for a in ang] for y in ys for cx, r in [hook_profile(y)]]
    tris = []
    for i in range(len(rings) - 1):
        for j in range(nseg):
            a, b = rings[i][j], rings[i][(j + 1) % nseg]; c, d = rings[i + 1][j], rings[i + 1][(j + 1) % nseg]
            tris += [a, c, b, b, c, d]
    tip = (hook_profile(0)[0], 0.0, 0.0)
    for j in range(nseg): tris += [tip, rings[0][j], rings[0][(j + 1) % nseg]]
    return [{"metal": True, "color": "#c9ced6", "pos": [round(c / R * APP_R, 5) for p in tris for c in p]}]

class Hook:
    def __init__(s, tip, u, throat):
        s.tip, s.u = tip, nrm(u)
        s.t = nrm(throat - s.u * (throat @ s.u)); s.z = np.cross(s.t, s.u)
    def at(s, d): return s.tip + s.u * d
    def basis(s):
        """(down, front) unit vectors perpendicular to the shaft, for wrapping yarn around it."""
        dn = v(0, 0, -1) - s.u * s.u[2]; dn = nrm(dn) if np.linalg.norm(dn) > 1e-3 else nrm(np.cross(s.u, v(1, 0, 0)))
        fr = v(0, -1, 0); fr = fr - s.u * (fr @ s.u) - dn * (fr @ dn); fr = nrm(fr) if np.linalg.norm(fr) > 1e-3 else np.cross(s.u, dn)
        return dn, fr
    def axis_centre(s, d):   # the shaft's cross-section centre, accounting for the throat offset
        cx, _ = hook_profile(d); return s.at(d) + s.t * cx
    def quat_app(s):
        # local (x=throat, y=shaft, z) -> design world; then design -> app frame
        M = np.stack([s.t, s.u, s.z], 1)
        M = TO_APP @ M
        return mat_to_quat(M)

TO_APP = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)   # design (x, y, z) -> app (x, z, -y)
def mat_to_quat(m):
    t = m.trace()
    if t > 0:
        s = math.sqrt(t + 1) * 2; return [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s]
    i = int(np.argmax([m[0, 0], m[1, 1], m[2, 2]])); j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1 + m[i, i] - m[j, j] - m[k, k]) * 2; q = [0, 0, 0, 0]
    q[i] = 0.25 * s; q[j] = (m[j, i] + m[i, j]) / s; q[k] = (m[k, i] + m[i, k]) / s; q[3] = (m[k, j] - m[j, k]) / s
    return q

def wrap(hk, d, a_in, a_out, rad=None, n=None):
    """yarn wrapped round the hook at height d, from angle a_in to a_out (degrees;
    0 = under the shaft, 90 = toward the camera, 180 = over the top)."""
    dn, fr = hk.basis(); c = hk.axis_centre(d); r = (rad or hook_profile(d)[1]) + 0.92 * R
    n = n or max(6, int(abs(a_out - a_in) / 12))
    a = np.radians(np.linspace(a_in, a_out, n))
    lift = np.linspace(-0.55, 0.55, n)[:, None] * R           # a loop is a flat helix: its legs pass beside each other
    return c + r * (np.cos(a)[:, None] * dn + np.sin(a)[:, None] * fr) + lift * hk.u

# ---------------------------------------------------------------- fabric
def sc_static(x, z, closed_left=True):
    """way-points of a finished single crochet whose top V is centred at (x, ., z),
    entered from its right-hand neighbour and leaving to the left (worked right to left)."""
    zb = z - H                         # top of the stitch below; its hole is just under that
    return [v(x + 0.5 * P, -0.25, z + 0.15),
            v(x + 0.22 * P, -B, z + 0.35), v(x - 0.22 * P, -B, z + 0.35),        # front loop of the V
            v(x - 0.48 * P, 0.0, z + 0.45),
            v(x - 0.2 * P, B, z + 0.3), v(x + 0.12 * P, B * 0.9, z - 0.2),       # back loop
            v(x + 0.18 * P, 0.7, z - 1.6), v(x + 0.12 * P, -0.95, z - 2.6),      # leg down the front
            v(x + 0.05 * P, 0.0, zb - 1.3), v(x - 0.05 * P, 1.25, zb - 0.9),     # through the stitch below
            v(x - 0.15 * P, 1.0, z - 2.2), v(x - 0.3 * P, -0.95, z - 1.4),       # second leg
            v(x - 0.5 * P, -0.25, z + 0.15)]

def chain(xs, z):
    """the foundation chain: a run of V's with nothing below, so the lowest legs end in something."""
    pts = []
    for x in xs:
        pts += [v(x + 0.5 * P, -0.25, z + 0.1), v(x + 0.2 * P, -B, z + 0.3), v(x - 0.25 * P, -B * 0.8, z + 0.35),
                v(x - 0.45 * P, 0.4, z + 0.2), v(x - 0.15 * P, B * 0.9, z - 0.1)]
    return pts + [v(xs[-1] - 0.5 * P, -0.25, z + 0.1)]

def row(xs, z):
    pts = []
    for x in xs: pts += sc_static(x, z)[:-1]
    return pts + [sc_static(xs[-1], z)[-1]]

# ---------------------------------------------------------------- paths
def spline(points, step=0.18 * R):
    """centripetal Catmull–Rom through the way-points, resampled by arc length."""
    p = [points[0]]
    for q in points[1:]:
        if np.linalg.norm(q - p[-1]) > 0.05 * R: p.append(q)
    p = np.array(p); p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        t0 = 0; t1 = t0 + np.linalg.norm(p1 - p0) ** 0.5 + 1e-6; t2 = t1 + np.linalg.norm(p2 - p1) ** 0.5 + 1e-6; t3 = t2 + np.linalg.norm(p3 - p2) ** 0.5 + 1e-6
        m = max(2, int(np.linalg.norm(p2 - p1) / (step * 0.5)))
        for t in np.linspace(t1, t2, m, endpoint=False):
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    out.append(p[-2]); return resample(np.array(out), step)

def resample(c, step=None, n=None):
    seg = np.linalg.norm(np.diff(c, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)])
    n = n or max(4, int(s[-1] / step) + 1); si = np.linspace(0, s[-1], n)
    return np.stack([np.interp(si, s, c[:, k]) for k in range(3)], 1)

def push_out(c, hk):
    """keep yarn outside the hook (capsule-ish test against the shaft profile)."""
    rel = c - hk.tip; d = rel @ hk.u
    out = c.copy()
    for i in np.where((d > -1.2 * RH) & (d < 70))[0]:
        dd = max(0.0, d[i]); cx, r = hook_profile(dd); axis = hk.tip + hk.u * dd + hk.t * cx
        w = c[i] - axis; w -= hk.u * (w @ hk.u) if d[i] >= 0 else 0
        L = np.linalg.norm(w); need = r + 0.9 * R
        if L < need: out[i] = axis + (w / (L + 1e-9) if L > 1e-6 else hk.z) * need
    return out

# ---------------------------------------------------------------- choreography
T_REST = v(-0.5 * P, -2.3, 1.5);  U_REST = v(1.0, -0.55, 0.8)
HOLE = v(-P, 0.0, -H - 1.3)                                    # under the V of the stitch we work into
T_IN = v(-P - 0.2, 4.2, -H - 1.6); U_IN = v(0.8, -1.35, 0.75)
T_UP = v(-P + 0.5, -2.6, -H + 4.0); U_UP = v(0.95, -0.9, 0.85)
DOWN = v(0, 0, -1)
ANCHOR = v(-0.2 * P, -0.5, 1.0)                                # where the fabric holds the live loop
E0 = v(-0.5 * P, -0.25, 0.15)                                  # end of the last finished stitch
BT = v(-0.75 * P, 2.2, -1.2)                                   # working yarn passes behind the work here

PULL_SPLIT = 0.55                                              # pull-through: loops ride off, then settle
MOVE_SHARE = 0.78                                              # share of each step spent moving (the rest is a hold)
D_B, D_A_MIN = 4.4, 7.0                                        # where the two loops sit on the shaft: clearly apart

LIFT = 0.0                                                     # opening lift (0..1), set per frame by the guided take
LIFT_VEC = v(0.8, -1.2, 3.4)                                   # raise the hook so the live loop stands up tall

def hook_pose(t):
    st, p = int(min(4, t // STEP_DUR)), (t % STEP_DUR) / STEP_DUR if t < 5 * STEP_DUR else 1.0
    p = min(1.0, p / MOVE_SHARE)                                 # move, then hold the pose
    e = ease(p)
    if st == 0:     # insert: arc in front of the work, dive under the V, out the back
        tip = bez(T_REST, v(-P + 0.3, -4.0, -H + 1.0), v(-P, -3.0, -H - 1.4), T_IN, e)
        u = slerp_dir(U_REST, U_IN, e); th = DOWN
    elif st == 1:   # yarn over: drop the throat under the yarn, rotate it up into it, settle
        tip = T_IN + v(0.25, 0.5, -0.35) * math.sin(math.pi * e)
        u = U_IN; th = slerp_dir(DOWN, v(0, 1, 0.4), math.sin(math.pi * e) * 0.8)
    elif st == 2:   # pull up a loop: back through the hole, then up in front
        tip = bez(T_IN, v(-P, -1.5, -H - 1.45), v(-P + 0.3, -3.5, -H), T_UP, e)
        u = slerp_dir(U_IN, U_UP, e); th = DOWN
    elif st == 3:
        tip = T_UP + v(-0.4, 0.6, 0.3) * math.sin(math.pi * e)
        u = U_UP; th = slerp_dir(DOWN, v(0, 1, 0.5), math.sin(math.pi * e) * 0.8)
    else:           # pull through both: draw the hook back along its shaft (the loops ride off the head),
                    # then carry the new live loop up to the next rest pose
        T_OUT = T_UP + nrm(U_UP) * 4.2 + v(0, 0, 0.6)
        if p < PULL_SPLIT:
            q = ease(p / PULL_SPLIT); tip = lerp(T_UP, T_OUT, q); u = U_UP
        else:
            q = ease((p - PULL_SPLIT) / (1 - PULL_SPLIT))
            tip = bez(T_OUT, T_OUT + v(0.2, -0.6, 1.2), T_REST - v(P, 0, 0) + v(0.8, -1.0, 1.0), T_REST - v(P, 0, 0), q)
            u = slerp_dir(U_UP, U_REST, q)
        th = DOWN
    return st, p, Hook(tip + LIFT * LIFT_VEC, u, th)

def loop_d(hk, anchor, lo):
    return max(lo, min(14.0, (anchor - hk.tip) @ hk.u))

def active_path(t, hk, st, p, dA=None, dB=D_B):
    """way-points from the end of the finished fabric to the finger; returns (points, index where the green yarn starts)."""
    e = ease(p)
    dA = loop_d(hk, ANCHOR, D_A_MIN) if dA is None else dA
    ringA = list(wrap(hk, dA, 25, -295))                         # the live loop, snug on the shaft
    pts = [E0, E0 + v(0, -0.6, 1.2)] + ringA[:len(ringA) // 2]; green = len(pts)
    pts += ringA[len(ringA) // 2:]
    behind = hk.tip[1] > 1.0                                     # hook tip is behind the work
    if st == 0:
        pts += [BT, BT + v(-1.5, 1.5, 3.5), F]
    elif st == 1:                                                # yarn over: wrap grows over the top into the throat
        wr = wrap(hk, THROAT_D, 250, 250 - 300 * e)
        pts += [BT] + list(wr) + [F]
    elif st == 2:                                                # pull up: the caught bight comes through the hole
        s = ease((1.2 - hk.tip[1]) / 2.0)                        # 0 while the tip is behind, 1 once in front
        dB = lerp(THROAT_D, D_B, ease((p - 0.55) / 0.45))
        ain, aout = lerp(250, 25, ease((p - 0.4) / 0.6)), lerp(-50, -295, ease((p - 0.4) / 0.6))
        wr = list(wrap(hk, dB, ain, aout))
        h1 = HOLE + v(0.55, 0, 0); h2 = HOLE + v(-0.55, 0, 0)
        pts += [BT, lerp(wr[0], h1 + v(0, 1.4, 0.1), s), lerp(wr[0], h1, s), lerp(wr[0], h1 + v(0, -1.4, 0.4), s)] + wr \
             + [lerp(wr[-1], h2 + v(0, -1.4, 0.4), s), lerp(wr[-1], h2, s), lerp(wr[-1], h2 + v(0, 1.4, 0.1), s), BT + v(-1.2, 0.3, 0), F]
    elif st == 3:
        ringB = list(wrap(hk, dB, 25, -295))
        wr = wrap(hk, THROAT_D, 250, 250 - 300 * e)
        h1 = HOLE + v(0.55, 0, 0); h2 = HOLE + v(-0.55, 0, 0)
        pts += [BT, h1 + v(0, 1.4, 0.1), h1, h1 + v(0, -1.4, 0.4)] + ringB + [h2 + v(0, -1.4, 0.4), h2, h2 + v(0, 1.4, 0.1), BT + v(-1.2, 0.3, 0)] + list(wr) + [F]
    return pts, green

ROW_XS = [3 * P, 2 * P, P, 0, -P, -2 * P, -3 * P]

def frame_strands(t):
    st, p, hk = hook_pose(t)
    static = [spline(row(ROW_XS, -H)), spline(row(ROW_XS, -2 * H)), spline(chain(ROW_XS, -3 * H))]
    fabric0 = row([3 * P, 2 * P, P, 0], 0.0)[:-1]                # finished part of the current row, up to E0
    if st < 4:
        pts, g = active_path(t, hk, st, p)
        allp = fabric0 + pts; gi = len(fabric0) + g
        c = spline(allp)
        # split where the live loop's second half starts (pink before, accent after)
        knot = allp[gi - 1]; k = int(np.argmin(np.linalg.norm(c - knot, axis=1)))
        segs = [(c[:k + 1], False), (c[k:], True)]
    else:
        # pull through: the two loops ride off over the head and settle into the new stitch,
        # while the yarn caught in the throat becomes the new live loop
        # phase 1: the hook draws back along its shaft; the loops, held by the fabric,
        # ride down over the throat (and the yarn caught in it) and off the head
        _, _, hk3 = hook_pose(4 * STEP_DUR - 1e-6)
        dA3 = loop_d(hk3, ANCHOR, D_A_MIN)
        def riding(hk_, q):
            return active_path(t, hk_, 3, 1.0, dA=lerp(dA3, 1.1, q), dB=lerp(D_B, 0.35, q))
        if p < PULL_SPLIT:
            pts, g = riding(hk, ease(p / PULL_SPLIT))
            allp = fabric0 + pts; c = spline(allp)
            knot = allp[len(fabric0) + g - 1]; k = int(np.argmin(np.linalg.norm(c - knot, axis=1)))
            return hk, finish(static, [(c[:k + 1], False), (c[k:], True)], hk)
        # phase 2: they tighten into the new stitch while the caught yarn becomes the new live loop
        e = ease((p - PULL_SPLIT) / (1 - PULL_SPLIT))
        _, _, hk0 = hook_pose(4 * STEP_DUR + PULL_SPLIT * STEP_DUR)
        pre, g = riding(hk0, 1.0)
        dC = loop_d(hk, ANCHOR - v(P, 0, 0), D_A_MIN)
        post = sc_static(-P, 0.0)[1:] + [E0 - v(P, 0, 0) + v(0, -0.6, 1.2)] + list(wrap(hk, dC, 25, -295)) + [BT - v(P, 0, 0), BT - v(P, 0, 0) + v(-1.5, 1.5, 3.5), F]
        a, b = spline(pre), spline(post)
        n = max(len(a), len(b)); a, b = resample(a, n=n), resample(b, n=n)
        # the loops slide toward the tip and off before the shape settles: delay the far end
        w = np.clip((e * 1.35 - np.linspace(0, 0.35, n)), 0, 1)[:, None]
        w = w * w * (3 - 2 * w)
        mid = lerp(a, b, w)
        c = spline(fabric0 + list(mid[::3]) + [mid[-1]])
        knot = mid[int(len(mid) * 0.22)]; k = int(np.argmin(np.linalg.norm(c - knot, axis=1)))
        segs = [(c[:k + 1], False), (c[k:], True)]
    return hk, finish(static, segs, hk)

def finish(static, segs, hk):
    out = [{"visible": True, "closed": False, "radius": APP_R, "accent": False, "pts": app(s)} for s in static]
    for s, acc in segs:
        s = push_out(s, hk)
        out.append({"visible": True, "closed": False, "radius": APP_R, "accent": acc, "pts": app(s)})
    return out

def app(c):
    c = np.asarray(c) @ TO_APP.T * (APP_R / R)
    return [[round(float(x), 4) for x in p] for p in c]

# ---------------------------------------------------------------- cameras
# 100 mm lens (13.7° vertical). The fixed angles aim at the stitch being made; the guided
# camera follows the action (a smoothed point between the stitch and the hook head) so
# nothing important leaves the frame.
FOV = 13.69; DIST = 84 * R
look = v(-0.8 * P, 0.0, -0.4 * H)
FRONT, SIDE, BACK = v(0.3, -1.0, 0.8), v(-1.0, -0.3, 0.55), v(0.15, 1.0, 0.65)
def cam(d, tgt=None, zoom=1.0):
    tgt = look if tgt is None else tgt
    return {"pos": app([tgt + nrm(d) * DIST * zoom])[0], "target": app([tgt])[0], "fov": FOV, "aspect": 1.6}

# ---------------------------------------------------------------- hands (guided take only)
# assets/hand-right.glb is posed in a crochet grip with its grip pocket at HAND_GRIP along its
# local x. Life size: about 25 yarn-widths long (scale 90 in app units).
HAND_GRIP, HAND_SCALE = np.array([0, 0.041, 0.017]), 90.0
def m_T(t): M = np.eye(4); M[:3, 3] = t; return M
def m_S(x, y, z): return np.diag([x, y, z, 1.0])
def m_R(axis, ang):
    c, s_ = math.cos(ang), math.sin(ang); M = np.eye(4)
    i, j = {"x": (1, 2), "y": (2, 0), "z": (0, 1)}[axis]
    M[i, i], M[i, j], M[j, i], M[j, j] = c, -s_, s_, c; return M
def hand_matrix(grip_at, rot, mirror=False):
    """app-frame matrix that puts the hand's grip pocket at grip_at, rotated by rot (4×4)."""
    M = rot @ m_S(-HAND_SCALE if mirror else HAND_SCALE, HAND_SCALE, HAND_SCALE)
    off = (M @ np.append(HAND_GRIP, 1))[:3]
    return m_T(np.asarray(grip_at) - off) @ M
# right hand: round the shaft ~34 yarn radii up from the tip (out of the close-ups) (hook-local app frame; shaft = +y)
RIGHT = hand_matrix([0, 34 * APP_R, 0], m_R("y", HAND_ROLL := math.radians(200)) @ m_R("z", -math.pi / 2))
# left hand: pinching the work to the left of the stitch, from behind, fingers over the top
LEFT_AT = v(-5.6 * P, 2.2, -1.7 * H)
LEFT = hand_matrix(app([LEFT_AT])[0], m_R("y", math.radians(-20)) @ m_R("z", math.pi / 2), mirror=True)
HANDS = [{"glb": "assets/hand-right.glb", "parent": "hook", "matrix": [round(x, 6) for x in RIGHT.ravel()]},
         {"glb": "assets/hand-right.glb", "parent": "world", "matrix": [round(x, 6) for x in LEFT.ravel()]}]

# ---------------------------------------------------------------- the guided take
# Filmed like a tutorial: show where the hook goes, do the move, swing the camera to where
# the result can be seen, freeze on it. Each shot: (seconds, action from, action to, camera
# from, camera to, callout at its end or None). Action time is the choreography's clock
# (steps of STEP_DUR, each moving for MOVE_SHARE then holding).
def mv(k): return k * STEP_DUR, k * STEP_DUR + STEP_DUR * MOVE_SHARE      # step k's move
SHOTS = [
    (1.6, 0.0, 0.0, FRONT, FRONT, None, (1.8, 1.8)),        # establishing: the hook, the work and the yarn
    # lift the hook so the live loop stands up, and link it to the stitch it came from
    (1.2, 0.0, 0.0, FRONT, FRONT, ("link", None, "This loop on your hook comes from stitch 1"), (1.8, 1.4), (0.0, 1.0)),
    (0.9, 0.0, 0.0, FRONT, FRONT, None, (1.4, 1.4), (1.0, 0.0)),
    (1.2, 0.0, 0.0, FRONT, FRONT, ("stitch", 0, "Now go into stitch 2 — under both top loops"), (1.4, 1.0)),
    (2.0, *mv(0), FRONT, FRONT, None),
    (1.8, mv(0)[1], STEP_DUR, FRONT, BACK, ("tip", 0, "The hook pokes out the back")),
    (2.0, *mv(1), BACK, BACK, ("throat", 1, "Wrap the yarn over your hook")),
    (2.6, mv(2)[0], mv(2)[1] + 0.3, BACK, SIDE, ("loops", 2, "Pull it back through — 2 loops on your hook")),
    (2.0, *mv(3), SIDE, SIDE, ("throat", 3, "Wrap the yarn over again")),
    (2.8, mv(4)[0], 5 * STEP_DUR, SIDE, FRONT, ("done", 4, "Pull through both loops — done!")),
    (0.8, 5 * STEP_DUR, 5 * STEP_DUR, FRONT, FRONT, None),
]
def at_video(tv):
    """video time -> (action time, camera direction, camera distance factor)"""
    t0 = 0.0
    for i, (dur, a0, a1, c0, c1, *rest) in enumerate(SHOTS):
        if tv <= t0 + dur or i == len(SHOTS) - 1:
            qa = min(1.0, max(0.0, (tv - t0) / dur)); z0, z1 = rest[1] if len(rest) > 1 else (1.0, 1.0)
            return lerp(a0, a1, qa), slerp_dir(c0, c1, ease(qa)), lerp(z0, z1, ease(qa))
        t0 += dur
def lift_at(tv):
    t0 = 0.0
    for dur, *rest in SHOTS:
        if tv <= t0 + dur:
            l0, l1 = rest[6] if len(rest) > 6 else (0.0, 0.0); return lerp(l0, l1, ease(min(1.0, max(0.0, (tv - t0) / dur))))
        t0 += dur
    return 0.0
def action_focus(ta):
    _, _, hk = hook_pose(ta); return lerp(look, hk.at(2.0), 0.5)
def guided_target(tv):
    """where the guided camera aims: the action focus averaged over ±0.5 s of video, so it glides."""
    ts = np.linspace(tv - 0.5, tv + 0.5, 9)
    return np.mean([action_focus(at_video(min(max(0.0, x), total))[0]) for x in ts], axis=0)
total = sum(sh[0] for sh in SHOTS)
n = int(round(total * A.fps)) + 1

FIXED = [("Front", FRONT), ("Side", SIDE), ("Behind", BACK)]   # the free-look angles (tiles 1–3)
cache = {}
frames = []
for i in range(n):
    tv = i / A.fps; ta, cdir, zoom = at_video(tv); LIFT = lift_at(tv); key = (round(ta, 4), round(LIFT, 3))
    if key not in cache: cache[key] = frame_strands(ta)
    LIFT = 0.0
    hk, strands = cache[key]
    frames.append({"t": round(tv, 4), "a": key[0] + key[1] * 1000, "cam": cam(cdir, guided_target(tv), zoom),
                   "hook": {"pos": app([hk.tip])[0], "quat": [round(q, 6) for q in hk.quat_app()]}, "strands": strands})

# ---------------------------------------------------------------- callouts
# At the end of each shot that has one, the app freezes for "hold" seconds and draws, over
# whichever tile is showing: a ring on what matters, the stitch to work into traced in a
# bright line, and an arrow along the hook's path. x, y, r are fractions of the frame
# (x of width, y and r of height).
def project(d, tgt, pts, zoom=1.0):
    eye = tgt + nrm(d) * DIST * zoom; f = nrm(tgt - eye); r = nrm(np.cross(f, v(0, 0, 1))); u = np.cross(r, f)
    th = math.tan(math.radians(FOV) / 2); out = []
    for p in pts:
        q = p - eye; z = q @ f
        out.append([round(0.5 + (q @ r) / z / th / 1.6 / 2, 4), round(0.5 - (q @ u) / z / th / 2, 4)])
    return out, DIST * zoom * th                                       # half the frame height in world units at the target
TARGET_V = spline(sc_static(-P, -H)[:6], 0.4 * R)              # the two top loops of the stitch we go into
INSERT_PATH = [hook_pose(STEP_DUR * MOVE_SHARE * k / 11)[2].tip for k in range(12)]
LABEL_XS = [0.0, -P, -2 * P, -3 * P]
LABEL_PTS = [v(x, -B - 0.7, -H - 2.2) for x in LABEL_XS]   # on the face of each stitch, under its top loops
def target(kind, ta):
    _, _, hk = hook_pose(ta)
    if kind == "link":
        dA = loop_d(hk, ANCHOR, D_A_MIN); return hk.at(dA), 2.4, None, None
    if kind == "stitch": return HOLE + v(0, 0, 0.9), 3.0, TARGET_V, INSERT_PATH[4:]
    if kind == "tip": return hk.at(1.0), 2.2, TARGET_V, None
    if kind == "throat": return hk.axis_centre(THROAT_D), 2.2, None, None
    if kind == "loops":
        dA = loop_d(hk, ANCHOR, D_A_MIN); return hk.at((dA + D_B) / 2), (dA - D_B) / 2 + 2.4, None, None
    dC = loop_d(hk, ANCHOR - v(P, 0, 0), D_A_MIN); return hk.at(dC), 2.4, None, None
cues, t0, timeline = [], 0.0, [[0.0, 0.0]]
for dur, a0, a1, c0, c1, cue, *_ in SHOTS:
    t0 += dur; timeline.append([round(t0, 3), round(a1, 3)])
    if not cue: continue
    tc = t0 - 0.5 / A.fps; ta, cdir, zoom = at_video(tc); LIFT = lift_at(tc); c, rad, trace, arrow = target(cue[0], ta); LIFT = 0.0
    views = []
    for d, tgt, z in [(cdir, guided_target(tc), zoom)] + [(d, look, 1.0) for _, d in FIXED]:
        (xy,), half = project(d, tgt, [c], z)
        views.append({"x": xy[0], "y": xy[1], "r": round(rad / half / 2, 4),
                      "trace": project(d, tgt, trace, z)[0] if trace is not None else None,
                      "arrow": project(d, tgt, arrow, z)[0] if arrow else None,
                      "link": project(d, tgt, [c, LABEL_PTS[0]], z)[0] if cue[0] == "link" else None})
    cues.append({"t": round(tc, 3), "step": cue[1], "text": cue[2], "views": views})
# stitch numbers: badges on the top of the stitches in the row being worked into, counted from
# the one just worked (1) to the one the hook goes into (2) and on; shown from the start until
# the hook is through. Guided view: positions sampled every 0.1 s; fixed views: static.
label_until = next(c["t"] for c in cues if "back" in c["text"]) + 0.2
track = []
for tv in np.arange(0.0, label_until + 0.1, 0.1):
    ta, cdir, zoom = at_video(tv)
    track.append([round(float(tv), 2)] + [c for xy in project(cdir, guided_target(tv), LABEL_PTS, zoom)[0] for c in xy])
labels = {"until": round(label_until, 2), "target": 1,
          "stitches": [{"text": str(i + 1)} for i in range(len(LABEL_XS))],
          "track": track,                                      # [t, x1, y1, x2, y2, ...] for the guided tile
          "fixed": [[c for xy in project(d, look, LABEL_PTS)[0] for c in xy] for _, d in FIXED]}

if A.cues:
    # timeline: [video time, action time] knots, so the app can follow the step list
    json.dump({"key": "sc", "hold": 2.4, "steps": len(STEPS), "stepDur": STEP_DUR, "timeline": timeline, "cues": cues, "labels": labels}, open(A.cues, "w"), indent=1)
    print("wrote", A.cues)

json.dump({"key": "sc", "fps": A.fps, "stepDur": STEP_DUR, "steps": STEPS, "total": total,
           "yarn": TUTORIAL_FABRIC, "accent": TUTORIAL_WORKING, "type": "wool",
           "camera": cam(FRONT), "hands": HANDS, "views": [dict(cam(FRONT), name="Guided", moving=True, hands=A.hands)] + [dict(cam(d), name=nm) for nm, d in FIXED],
           "ball": None, "ground": -40, "hookMesh": hook_mesh(), "frames": frames}, open(A.out, "w"))
print("wrote", A.out, n, "frames,", len(cache), "distinct poses")
