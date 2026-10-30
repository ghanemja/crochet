# Every stitch, choreographed for the offline render (tools/render_tutorial.py) — the general
# form of choreo_sc.py, driven by a stitch spec instead of a hand-written single crochet.
#
#   python3 tools/choreo.py dc build/paths/dc.json --cues assets/tutorials/dc.cues.json --hands [--fps 24]
#
# A stitch is a program of hook operations grouped into the app's steps (STITCH_STEPS in
# index.html):
#   yo_free        yarn over with the hook in front of the work (hdc / dc / tr before inserting)
#   insert h       into the stitch at x = h, under both top loops, tip out the back
#   yo_catch       yarn over with the hook inserted: the yarn lands in the throat
#   pull_up h      draw the caught yarn back through stitch h: a new loop on the shaft
#   pull_keep h    the same, but the yarn stays in the throat to go on through (slip stitch)
#   yo_front       yarn over with the hook in front
#   through n      draw the caught yarn through the n loops nearest the tip
# The state — loops on the hook in yarn order, the post growing under the hook, the stitches
# made so far — is simulated op by op, and the yarn is rebuilt from it every frame as one
# continuous path: fabric -> loops on the hook -> working yarn -> over the left index finger.
# Loops that come off the hook morph into the finished geometry (segment by segment, the
# far end lagging, so they slide off before they settle). Each op also eases in from the
# previous op's last frame, so nothing pops at the joins.
#
# The magic ring works in a straight "row space" bent into a circle (warp): the ring strand
# is the row below, every stitch goes into it, and closing the ring shrinks the circle.
#
# Design space as choreo_sc.py: Z up, X along the row (worked right to left), -Y toward the
# camera, yarn radius R = 1; exported in the app's frame (Y up) at the app's yarn radius.
import json, math, sys, os, argparse
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("key"); ap.add_argument("out"); ap.add_argument("--fps", type=int, default=24)
ap.add_argument("--hands", action="store_true")
ap.add_argument("--cues", default="")
ap.add_argument("--max-frames", type=int, default=0)      # tests: stop after this many frames
A = ap.parse_args()
KEY = A.key

STEP_DUR = 2.6
R, RH = 1.0, 1.15
P, H, B = 4.6, 4.4, 1.45
APP_R = 0.36
TUTORIAL_FABRIC, TUTORIAL_WORKING = "#4f7fc4", "#f0862a"
SHADE_OLD, SHADE_CURRENT = 0.68, 1.22
MOVE_SHARE = 0.78
D_B, SPACING = 4.4, 2.6            # nearest-the-tip loop sits D_B up the shaft, the others SPACING apart

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
def over_top(a):
    """the held working yarn's way over the top edge of the work, behind it, from where it leaves the
    work (a) on its way to the left index: it never crosses the front of the stitches"""
    if RING: return a + v(-1.0, 1.5, 4.5)   # the ring: the middle finger is behind it to the left
    return a + v(-3.5, 1.2, 4.5)      # up and along toward the finger, not straight up over the hook's head

# ---------------------------------------------------------------- hands (as choreo_sc.py)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hand_rig
UNIT = APP_R / 100
_HJ = os.path.join(HERE, "..", "build", "hands", "hands.json")
HAND_PTS = json.load(open(_HJ)) if os.path.exists(_HJ) else None
HAND_SCALE = 0.62
def local_pt(rig, name, lift=0.0, side=None):
    p = np.array(HAND_PTS[side][name] if HAND_PTS and side else rig[4][name]) * HAND_SCALE / UNIT
    return p + np.array([0, 0, lift])
def frame_from(yh, zh):
    yh = nrm(yh); zh = nrm(zh - yh * (zh @ yh)); return np.stack([np.cross(yh, zh), yh, zh], 1)
LEFT_RIG = hand_rig.skeleton(hand_rig.LEFT_HOLD, "L")
SPEC_ZT = {"hdc": 0.5 * H, "dc": 1.0 * H, "tr": 1.75 * H}.get(KEY, 0.0)   # top of the new row (SPECS below)
# The left hand holds the work the way a crocheter does: it comes in from the left, fingers
# pointing along the row (and a little down), thumb in front of the fabric and middle finger
# behind it pinching just below the stitches being worked into, index raised to carry the yarn.
def _env_vec(name, default):
    e = os.environ.get(name); return v(*map(float, e.split(","))) if e else default
# per stitch (pinch point, finger direction, middle fingertip -> thumb): the chain is pinched where
# it hangs down, the hand turned a little so the raised index stands in front of the chain; the
# magic ring on its strand up and left of the work (MR_C and MR_R0 below)
_PINCH = {"ch": (v(0.5 * P + 3.0, 0.0, -6.0), v(0.0, 0.0, 1.0), v(-0.5, -0.866, 0.0)),
          "mr": (v(-4.6 + 5.125 * math.cos(math.radians(130)), 0.0, -9.225 + 5.125 * math.sin(math.radians(130))), v(0.5, 0.0, 0.866), v(0, -1, 0))}.get(KEY, (v(-12.0, 0.0, -6.5), v(0.55, 0.45, 0.7), v(0, -1, 0)))
L_PINCH = _env_vec("L_PINCH", _PINCH[0])                       # midway between thumb tip and middle fingertip
L_FINGERS = nrm(_env_vec("L_FINGERS", _PINCH[1]))              # where the fingers point: up and in, the forearm toward the viewer
L_AXIS = nrm(_env_vec("L_AXIS", _PINCH[2]))                     # from the middle fingertip to the thumb: through the work
L_VARIANT = os.environ.get("L_VARIANT", {"mr": "Lc"}.get(KEY, "L"))   # make_hands_mpfb.py: Lc pinches a single strand
def _rot_onto(a1, a2, b1, b2):
    """rotation taking a1 to b1, and a2 (as far as it is perpendicular to a1) to b2"""
    def basis(x, y):
        x = nrm(x); y = nrm(y - x * (x @ y)); return np.stack([x, y, np.cross(x, y)], 1)
    return basis(b1, b2) @ basis(a1, a2).T
# ---------------------------------------------------------------- hook (as choreo_sc.py)
def hook_profile(y):
    r = RH
    if y < 0.9 * r:   return 0.12 * r, r * 0.93 * math.sqrt(max(0.0, 1 - (1 - y / (0.9 * r)) ** 2)) + 0.02
    if y < 1.55 * r:  return 0.12 * r, 0.93 * r
    if y < 1.95 * r:  t = (y - 1.55 * r) / (0.4 * r); return lerp(0.12 * r, -0.42 * r, t), lerp(0.93 * r, 0.5 * r, t)
    if y < 3.0 * r:   return -0.42 * r, 0.5 * r
    if y < 5.2 * r:   t = ease((y - 3.0 * r) / (2.2 * r)); return lerp(-0.42 * r, 0.0, t), lerp(0.5 * r, r, t)
    return 0.0, r
THROAT_D = 2.45 * RH

def thumb_rest():
    """(along the shaft, angle round it in the hook's frame) of the right thumb's pad, with the hook's
    throat facing down: the hook's flat thumb rest is put under it"""
    if not HAND_PTS or GRIP is None: return None
    hk = Hook(v(0, 0, 0), v(1, 0, 0), v(0, 0, -1)); pos, rot = right_hand(hk)
    J = {k: np.array(x) * HAND_SCALE / UNIT for k, x in HAND_PTS["R"].items() if not k.startswith("_")}
    th = pos + rot @ (0.4 * J["thumb_dip"] + 0.6 * J["thumb_tip"]); d = th @ hk.u; w = th - hk.u * d
    return d, math.atan2(w @ hk.z, w @ hk.t)
def hook_mesh():
    ys = np.concatenate([np.linspace(0, 5.6 * RH, 70), np.linspace(5.8 * RH, 70, 12)])
    tr = thumb_rest()
    if tr: ys = np.unique(np.concatenate([ys, np.linspace(tr[0] - 9, tr[0] + 9, 37)]))
    nseg = 28; ang = np.linspace(0, 2 * math.pi, nseg, endpoint=False)
    def flat(x, y, z):                                           # the thumb rest: the shaft flattened under the thumb
        if not tr: return x, z
        w = ease(1 - (abs(y - tr[0]) - 5.5) / 2.5) if abs(y - tr[0]) > 5.5 else 1.0   # the length of the thumb's last joint
        nx, nz = math.cos(tr[1]), math.sin(tr[1]); pr = x * nx + z * nz; cut = max(0.0, pr - 0.55 * RH) * w
        return x - nx * cut, z - nz * cut
    rings = [[(lambda x, z: (x, y, z))(*flat(cx + r * math.cos(a), y, r * math.sin(a))) for a in ang] for y in ys for cx, r in [hook_profile(y)]]
    tris = []
    for i in range(len(rings) - 1):
        for j in range(nseg):
            a, b = rings[i][j], rings[i][(j + 1) % nseg]; c, d = rings[i + 1][j], rings[i + 1][(j + 1) % nseg]
            tris += [a, c, b, b, c, d]
    tip = (hook_profile(0)[0], 0.0, 0.0)
    for j in range(nseg): tris += [tip, rings[0][j], rings[0][(j + 1) % nseg]]
    end = (0.0, float(ys[-1]), 0.0)                              # the far end closed (it showed as a black hole)
    for j in range(nseg): tris += [end, rings[-1][(j + 1) % nseg], rings[-1][j]]
    return [{"metal": True, "color": "#c9ced6", "pos": [round(c / R * APP_R, 5) for p in tris for c in p]}]

TO_APP = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
def mat_to_quat(m):
    t = m.trace()
    if t > 0:
        s = math.sqrt(t + 1) * 2; return [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s]
    i = int(np.argmax([m[0, 0], m[1, 1], m[2, 2]])); j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1 + m[i, i] - m[j, j] - m[k, k]) * 2; q = [0, 0, 0, 0]
    q[i] = 0.25 * s; q[j] = (m[j, i] + m[i, j]) / s; q[k] = (m[k, i] + m[i, k]) / s; q[3] = (m[k, j] - m[j, k]) / s
    return q

class Hook:
    def __init__(s, tip, u, throat):
        s.tip, s.u = np.asarray(tip, float), nrm(u)
        s.t = nrm(throat - s.u * (throat @ s.u)); s.z = np.cross(s.t, s.u)
        dn, fr = s.basis(); s.roll = math.degrees(math.atan2(s.t @ fr, s.t @ dn))
    def at(s, d): return s.tip + s.u * d
    def basis(s):
        dn = v(0, 0, -1) - s.u * s.u[2]; dn = nrm(dn) if np.linalg.norm(dn) > 1e-3 else nrm(np.cross(s.u, v(1, 0, 0)))
        fr = v(0, -1, 0); fr = fr - s.u * (fr @ s.u) - dn * (fr @ dn); fr = nrm(fr) if np.linalg.norm(fr) > 1e-3 else np.cross(s.u, dn)
        return dn, fr
    def axis_centre(s, d):
        cx, _ = hook_profile(d); return s.at(d) + s.t * cx
    def quat_app(s):
        return mat_to_quat(TO_APP @ np.stack([s.t, s.u, s.z], 1))
def rolled(tip, u, theta):
    """a hook whose throat is turned theta degrees about the shaft from facing down, through the front"""
    h = Hook(tip, u, v(0, 0, -1)); dn, fr = h.basis(); a = math.radians(theta)
    h = Hook(tip, u, math.cos(a) * dn + math.sin(a) * fr); h.roll = theta; return h

def wrap(hk, d, a_in, a_out, n=None):
    """yarn round the hook at height d, from angle a_in to a_out (degrees; 0 = under the shaft,
    90 = toward the camera, 180 = over the top); a flat helix so the legs pass beside each other."""
    dn, fr = hk.basis(); c = hk.axis_centre(d); r = hook_profile(d)[1] + 0.92 * R
    n = n or max(6, int(abs(a_out - a_in) / 12))
    a = np.radians(np.linspace(a_in, a_out, n))
    lift = np.linspace(-0.55, 0.55, n)[:, None] * R * min(1.0, abs(a_out - a_in) / 300)
    return list(c + r * (np.cos(a)[:, None] * dn + np.sin(a)[:, None] * fr) + lift * hk.u)

THROAT_R = hook_profile(THROAT_D)[1] + 0.92 * R
def contact(hk, A, B, caught=False):
    """(a_in, a_out) where the working yarn, held straight from A to B (behind the work -> the left
    index), lies round the throat; None where it doesn't touch. It bends over the top of the shaft
    only where the hook pushes into it; once caught, the throat carries it round as the hook rolls
    back down (the throat's roll is hk.roll: 200 facing up and back, 0 facing down)."""
    c = hk.axis_centre(THROAT_D); dn, fr = hk.basis()
    def p2(X):
        w = X - c; return np.array([w @ dn, w @ fr])
    a2, b2 = p2(A), p2(B); d = b2 - a2
    if np.linalg.norm(a2) < 1.3 * THROAT_R:                     # caught right where it leaves the work (a hook in a stitch):
        depth = np.clip((1.3 * THROAT_R - np.linalg.norm(a2)) / (0.6 * THROAT_R), 0, 1)   # it bends over the throat as far as the hook pushes in
        a_in, a_out = 250.0, 250.0 - (20 + 60 * depth)
        return (a_in, min(a_out, hk.roll - 50)) if caught else (a_in, a_out)
    q = a2 + d * np.clip(-(a2 @ d) / (d @ d + 1e-12), 0, 1)
    if np.linalg.norm(q) >= THROAT_R and not caught: return None
    def tangent(x):                                              # the tangent point nearer the top (180)
        rho = np.linalg.norm(x); al = math.degrees(math.atan2(x[1], x[0])); be = math.degrees(math.acos(min(1.0, THROAT_R / max(rho, 1e-6))))
        return min((180 + ((al + sg * be - 180 + 180) % 360) - 180 for sg in (-1, 1)), key=lambda t: abs(t - 180))
    a_in, a_out = tangent(a2), tangent(b2)
    if a_in <= a_out:
        if not caught: return None
        a_out = a_in - 5
    if caught: a_out = min(a_out, hk.roll - 50)
    return a_in, a_out

def push_out(c, hk):
    rel = c - hk.tip; d = rel @ hk.u
    out = c.copy()
    for i in np.where((d > -1.2 * RH) & (d < 70))[0]:
        dd = max(0.0, d[i]); cx, r = hook_profile(dd); axis = hk.tip + hk.u * dd + hk.t * cx
        w = c[i] - axis; w -= hk.u * (w @ hk.u) if d[i] >= 0 else 0
        L = np.linalg.norm(w); need = r + 0.9 * R
        if L < need: out[i] = axis + (w / (L + 1e-9) if L > 1e-6 else hk.z) * need
    return out

# ---------------------------------------------------------------- curves
def spline(points, step=0.18 * R):
    p = [points[0]]
    for q in points[1:]:
        if np.linalg.norm(q - p[-1]) > 0.05 * R: p.append(q)
    if len(p) < 2: return np.array([p[0], p[0] + 1e-3])
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
    c = np.asarray(c, float)
    if len(c) < 2: c = np.vstack([c, c + 1e-4])
    seg = np.linalg.norm(np.diff(c, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)])
    n = n or max(4, int(s[-1] / step) + 1); si = np.linspace(0, s[-1], n)
    if s[-1] < 1e-9: return np.repeat(c[:1], n, 0)
    return np.stack([np.interp(si, s, c[:, k]) for k in range(3)], 1)

MARKS = ("e", "a0", "a1", "new", "hand")
# e: where the morphing part starts (the end of the fabric before the op); a0..a1: the first loop
# on the hook; new: where the yarn that becomes the newest loop starts; hand: the left hand.
class Path:
    """the active yarn as way-points plus named way-point indices (marks), the fabric/working
    colour split and own_e (this state's end of fabric); .curve() splines it and maps them."""
    def __init__(s, pts, marks, split, own_e):
        s.pts, s.marks, s.split, s.own_e = pts, marks, split, own_e
    def curve(s):
        pts = s.pts
        if WARP["x0"] is not None:                               # the ring: bend the way-points, not the hand's
            h = s.marks["hand"]; pts = list(warp_pts(pts[:h])) + list(pts[h:])
        elif CHAIN:                                              # the older chain hangs down from the hook
            h = s.marks["hand"]; pts = list(droop(pts[:h])) + list(pts[h:])
        c = spline(pts); idx = {}; lo = 0
        P_ = np.asarray(pts, float); arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P_, axis=0), axis=1))])
        def near(i, lo):
            """the curve index of way-point i: nearest point within a window round where its arc
            length puts it (the ring's ends meet, so a plain nearest point is ambiguous)"""
            i = min(max(i, 0), len(pts) - 1); est = int(arc[i] / max(arc[-1], 1e-9) * (len(c) - 1)); wdw = max(40, len(c) // 12)
            a, b = max(lo, est - wdw), max(lo + 1, min(len(c), est + wdw + 1))
            return a + int(np.argmin(np.linalg.norm(c[a:b] - P_[i], axis=1)))
        for m in MARKS:
            idx[m] = near(s.marks[m], lo); lo = idx[m]
        return Curve(c, idx, near(s.split, 0), near(s.own_e, 0))

class Curve:
    def __init__(s, c, idx, split, own_e): s.c, s.idx, s.split, s.own_e = c, idx, split, own_e

def morph(ca, cb, e, lag=0.35):
    """segment-by-segment blend of two curves (marks matched) from mark e on; with lag the far end
    follows later. The fabric before e comes from cb (it is the same in both)."""
    ba = [ca.idx[m] for m in MARKS] + [len(ca.c) - 1]
    bb = [cb.idx[m] for m in MARKS] + [len(cb.c) - 1]
    pa, pb, sizes = [], [], []
    for k in range(len(ba) - 1):
        last = k == len(ba) - 2
        sa = ca.c[ba[k]:ba[k + 1] + 1]; sb = cb.c[bb[k]:bb[k + 1] + 1]
        n = max(2, len(sa), len(sb)); sizes.append(n)
        pa.append(resample(sa, n=n)[: None if last else -1]); pb.append(resample(sb, n=n)[: None if last else -1])
    a, b = np.vstack(pa), np.vstack(pb); n = len(a)
    w = np.clip(e * (1 + lag) - np.linspace(0, lag, n), 0, 1)[:, None]; w = w * w * (3 - 2 * w)
    head = cb.c[:bb[0]]
    out = np.vstack([head, lerp(a, b, w)]) if len(head) else lerp(a, b, w)
    def remap(bounds, i):
        """an index of a source curve -> the blended curve's"""
        if i <= bounds[0]: return len(head) - (bounds[0] - i) if i >= bounds[0] - len(head) else max(0, i)
        off = len(head)
        for k in range(len(bounds) - 1):
            seg = bounds[k + 1] - bounds[k]; m = sizes[k] - 1
            if i <= bounds[k + 1] or k == len(bounds) - 2:
                return off + int(round((i - bounds[k]) / max(1, seg) * m))
            off += m
        return off
    sp = int(round(lerp(remap(ba, ca.split), remap(bb, cb.split), ease(e))))
    offs = len(head) + np.cumsum([0] + [s_ - 1 for s_ in sizes]); idx = {m: int(offs[k]) for k, m in enumerate(MARKS)}
    # the end of the fabric stays where it was until the close is done: the loops coming off and the yarn through them
    # are still working yarn (kept off each other and the fabric) while they settle, not finished fabric yet
    own = remap(ba, ca.own_e) if CLOSE_OWN and e < 1.0 else remap(bb, cb.own_e)
    return Curve(out, idx, min(len(out) - 1, max(0, sp)), min(len(out) - 1, own))

def blend(ca, cb, w):
    """plain arc-length blend of two nearly equal curves from each one's end of fabric (op joins);
    the yarn round the left hand is the same in both and stays put"""
    ta, tb = ca.c[ca.own_e:ca.idx["hand"] + 1], cb.c[cb.own_e:cb.idx["hand"] + 1]; n = max(len(ta), len(tb), 2)
    mid = lerp(resample(ta, n=n), resample(tb, n=n), w)
    out = np.vstack([cb.c[:cb.own_e], mid, cb.c[cb.idx["hand"] + 1:]])
    hand_at = cb.own_e + n - 1
    fa = (ca.split - ca.own_e) / max(1, len(ta) - 1); fb = (cb.split - cb.own_e) / max(1, len(tb) - 1)
    sp = cb.own_e + int(round(lerp(fa, fb, w) * (n - 1))) if min(fa, fb) >= 0 else cb.split
    idx = {m: (i if i <= cb.own_e else cb.own_e + int(round((i - cb.own_e) / max(1, len(tb) - 1) * (n - 1)))) for m, i in cb.idx.items()}
    idx["hand"] = hand_at
    return Curve(out, idx, min(len(out) - 1, max(0, sp)), cb.own_e)

# ---------------------------------------------------------------- fabric geometry
def bar(xc, zj):
    """a yarn over that came off the hook: a wrap round the post"""
    return [v(xc + 0.4 * P, -1.25, zj + 0.9), v(xc - 0.35 * P, -1.35, zj - 0.3), v(xc - 0.45 * P, 0.6, zj - 0.6), v(xc + 0.1 * P, 1.3, zj - 0.2)]

def bar_heights(zt, zh, nb):
    lo, hi = zh + 1.8, zt - 1.6
    return [lo + (hi - lo) * (j + 1) / (nb + 1) for j in range(nb)]    # bottom to top

TOP_W = 0.95                                                   # half-width of a stitch's top across the row (was B)
LEGS_REAL = os.environ.get("LEGS", "") == "real"               # (prototype) the finished stitch threaded the way it was made
def stitch_static(x, zt, holes, nb=0, zh=-H, hole_dz=-1.3):
    """way-points of a finished stitch whose top V is centred at (x, ., zt), entered from its right
    neighbour and leaving to the left; legs into the hole(s) under the V of the row below at x = h
    (two holes for a decrease), wrapped by nb bars (the yarn overs of hdc / dc / tr). hole_dz: how far
    below the row under it the legs pass through (under its V; into a chain, through the link)."""
    # the top: a flat chain link along the row, front and back loops close together and pinched to a
    # point where they meet the next stitch, so the tops read as a row of V's from above
    pts = [v(x + 0.5 * P, -0.1, zt + 0.05),
           v(x + 0.24 * P, -TOP_W, zt + 0.3), v(x - 0.2 * P, -0.85 * TOP_W, zt + 0.32),
           v(x - 0.5 * P, 0.05, zt + 0.22),
           v(x - 0.2 * P, TOP_W, zt + 0.2), v(x + 0.24 * P, 0.8 * TOP_W, zt - 0.25)]
    L = zt - zh
    for k, hx in enumerate(holes):
        xa = lambda f: lerp(x, hx, f)
        if L < 3.2:      # a slip stitch: the V sits low, its legs go straight in
            pts += [v(xa(0.6) + 0.15 * P, -0.8, zh + 0.7), v(hx + 0.05 * P, 0.0, zh - 1.3), v(hx - 0.05 * P, 1.25, zh - 0.9), v(xa(0.6) - 0.2 * P, 0.8, zh + 0.8)]
            continue
        if nb == 0 and LEGS_REAL:
            # threaded as it was made: from the top down behind the work, the pulled-up loop out through the
            # hole to the front, up (its top closes round the yarn over, the next stitch's start), down the front,
            # back in through the hole and up behind to where the next stitch starts
            top = zt - 0.75 if k == len(holes) - 1 else zt - 2.0
            pts += [v(xa(0.3) + 0.3 * P, 1.25, zt - 1.2), v(hx + 0.12 * P, 1.35, zh + hole_dz + 0.3), v(hx + 0.1 * P, 0.15, zh + hole_dz),
                    v(xa(0.8) + 0.14 * P, -1.0, zh + 1.5), v(xa(0.15) + 0.2 * P, -1.05, top + 0.2),
                    v(xa(0.15) - 0.2 * P, -1.05, top + 0.2), v(xa(0.8) - 0.14 * P, -1.0, zh + 1.5),
                    v(hx - 0.1 * P, 0.15, zh + hole_dz), v(hx - 0.12 * P, 1.35, zh + hole_dz + 0.3), v(xa(0.3) - 0.35 * P, 1.2, zt - 1.0)]
            continue
        if nb == 0:      # the pulled-up loop's two legs make the V on the front: down from the top right into
            # the hole under the row below's V, round behind it, back out of the same hole and up to the top left
            top = zt - 0.75 if k == len(holes) - 1 else zt - 2.0
            pts += [v(xa(0.15) + 0.36 * P, -0.9, zt - 0.75), v(xa(0.8) + 0.14 * P, -1.0, zh + 1.5),
                    v(hx + 0.1 * P, 0.15, zh + hole_dz), v(hx, 1.35, zh + hole_dz + 0.3), v(hx - 0.1 * P, 0.15, zh + hole_dz),
                    v(xa(0.8) - 0.14 * P, -1.0, zh + 1.5), v(xa(0.15) - 0.36 * P, -0.9, top)]
            continue
        pts += [v(xa(0.1) + 0.18 * P, 0.7, zt - 1.6)]
        for zj in reversed(bar_heights(zt, zh, nb)):
            pts += bar(xa(1 - (zj - zh) / L), zj)
        pts += [v(xa(0.75) + 0.12 * P, -0.95, zh + 1.8), v(hx + 0.05 * P, 0.0, zh + hole_dz), v(hx - 0.05 * P, 1.25, zh + hole_dz + 0.4), v(xa(0.75) - 0.15 * P, 1.0, zh + 2.2)]
        if L > 6: pts += [v(xa(0.4) - 0.28 * P, 0.95, zh + 0.55 * L)]
        pts += [v(xa(0.1) - 0.3 * P, -0.95, zt - 1.4 if k == len(holes) - 1 else zt - 2.4)]
    return pts + [v(x - 0.5 * P, -0.25, zt + 0.15)]

def chain_link(x, z):
    """a chain: a flat link along the row, its two strands pinched to a V where it meets the next"""
    return [v(x + 0.5 * P, -0.1, z + 0.05), v(x + 0.22 * P, -TOP_W, z + 0.3), v(x - 0.22 * P, -0.8 * TOP_W, z + 0.32),
            v(x - 0.45 * P, 0.25, z + 0.2), v(x - 0.15 * P, 0.85 * TOP_W, z - 0.1), v(x - 0.5 * P, -0.1, z + 0.05)]

def chain(xs, z):
    pts = []
    for x in xs: pts += chain_link(x, z)[:-1]
    return pts + [chain_link(xs[-1], z)[-1]]

def row_of(xs, zt, nb=0, zh=-H, hole_dz=-1.3):
    pts = []
    for x in xs: pts += stitch_static(x, zt, [x], nb, zh, hole_dz)[:-1]
    return pts + [stitch_static(xs[-1], zt, [xs[-1]], nb, zh, hole_dz)[-1]]

def post_partial(hx, zt_hook, nb_done, zt, nb, zh=-H):
    """the post under the hook after a 'yarn over, through 2' (dc / tr): down the front through the
    bars made so far, into the hole and back up the back"""
    pts = [v(hx + 0.2 * P, -1.0, zt_hook - 0.8)]
    hs = bar_heights(zt, zh, nb)[:nb_done]
    for zj in reversed(hs): pts += bar(hx, min(zj, zt_hook - 2.0))
    return pts + [v(hx + 0.12 * P, -0.95, zh + 1.8), v(hx + 0.05 * P, 0.0, zh - 1.3), v(hx - 0.05 * P, 1.25, zh - 0.9),
                  v(hx - 0.15 * P, 1.0, zh + 2.2), v(hx - 0.3 * P, -0.95, zt_hook - 1.2)]

# ---------------------------------------------------------------- stitch specs
# height of the new row's top above the row below (sc = 1 row), bars on the post, the step
# texts (STITCH_STEPS in index.html — keep in sync) with their ops, the callouts.
X1 = -P                                                         # the stitch the hook goes into ("stitch 2")
INC_D = float(os.environ.get("INC_D", "0"))       # (study) an increase: its two stitches in the same stitch below, their legs side by side in its hole (0: on top of each other)
SPECS = {
    "sc":  dict(zt=0.0, nb=0, steps=[["insert"], ["yo_catch"], ["pull_up"], ["yo_front"], ["through"]]),
    "sl":  dict(zt=-0.48 * H, nb=0, steps=[["insert"], ["yo_catch"], ["pull_keep", "through"]]),
    "hdc": dict(zt=0.5 * H, nb=1, steps=[["yo_free"], ["insert"], ["yo_catch", "pull_up"], ["yo_front"], ["through"]]),
    "dc":  dict(zt=1.0 * H, nb=1, steps=[["yo_free"], ["insert"], ["yo_catch", "pull_up"], ["yo_front", "through2"], ["yo_front", "through"]]),
    "tr":  dict(zt=1.75 * H, nb=2, steps=[["yo_free", "yo_free"], ["insert"], ["yo_catch", "pull_up"], ["yo_front", "through2"], ["yo_front", "through2"], ["yo_front", "through"]]),
    "inc": dict(zt=0.0, nb=0, steps=[["insert", "yo_catch", "pull_up", "yo_front", "through"],
                                      ["insert", "yo_catch", "pull_up", "yo_front", "through"], ["hold"]], xs=[-P, -2 * P], holes=[[-P + INC_D], [-P - INC_D]]),
    "dec": dict(zt=0.0, nb=0, steps=[["insert", "yo_catch", "pull_up"], ["insert", "yo_catch", "pull_up"], ["yo_front", "through"]],
                xs=[-1.5 * P], holes=[[-P, -2 * P]]),
    "ch":  dict(zt=0.0, nb=0, chain=True, steps=[["yo_front"], ["through"]]),
    "mr":  dict(zt=0.0, nb=0, ring=True, steps=[["mr_loop"], ["insert", "yo_catch", "pull_up", "yo_front", "through"] + ["insert", "yo_catch", "pull_up", "yo_front", "through"] * 6, ["mr_close"]]),
}
STITCH_STEPS = {
    "ch":  ["Yarn over", "Pull through loop"],
    "sl":  ["Insert hook", "Yarn over", "Pull through stitch & loop"],
    "sc":  ["Insert hook", "Yarn over", "Pull up a loop (2 on hook)", "Yarn over", "Pull through both loops"],
    "hdc": ["Yarn over first", "Insert hook", "Yarn over, pull up loop (3 on hook)", "Yarn over", "Pull through all 3 loops"],
    "dc":  ["Yarn over first", "Insert hook", "Pull up a loop (3 on hook)", "Yarn over, pull through 2", "Yarn over, pull through 2"],
    "tr":  ["Yarn over twice", "Insert hook", "Pull up a loop (4 on hook)", "Yarn over, through 2", "Yarn over, through 2", "Yarn over, through 2"],
    "inc": ["Work 1 stitch", "Work a 2nd in the same stitch", "Two stitches made"],
    "dec": ["Pull up loop in st 1", "Pull up loop in st 2", "Yarn over, pull through all"],
    "mr":  ["Loop the yarn", "Work stitches into ring", "Pull tail to close"],
}
SPEC = SPECS[KEY]; STEPS = STITCH_STEPS[KEY]
ZT, NB = SPEC["zt"], SPEC["nb"]
CHAIN, RING = SPEC.get("chain", False), SPEC.get("ring", False)

# ---------------------------------------------------------------- magic ring: row space -> circle
MR_N = 7                                                        # ch 1 + 6 sc fill the ring
MR_R0 = MR_N * P / (2 * math.pi)                                # ring radius while working
MR_R1 = 1.1                                                     # ...once the tail is pulled
ZR = -H + 0.3                                                   # the ring strand's height in row space
MR_C = v(-P, 0.0, ZR - MR_R0)                                   # ring centre (world)
MR_XS = 0.0                                                     # row-space x where the ring crosses itself
WARP = {"x0": None, "r": MR_R0}                                 # set per frame for the ring
MR_BTZ = float(os.environ.get("MR_BTZ", "-2.4"))                # where the working yarn leaves the ring (row space)
def warp_pts(pts):
    if WARP["x0"] is None: return np.asarray(pts, float)
    p = np.asarray(pts, float); x0, rr = WARP["x0"], WARP["r"]
    phi = math.pi / 2 + (x0 - p[:, 0]) / MR_R0
    dz = p[:, 2] - ZR
    r = np.where(dz >= 0, rr + dz, rr * np.exp(dz / rr))
    return np.stack([MR_C[0] + r * np.cos(phi), p[:, 1], MR_C[2] + r * np.sin(phi)], 1)
def warp_hook(hk):
    if WARP["x0"] is None: return hk
    tip = warp_pts([hk.tip])[0]; a = (WARP["x0"] - hk.tip[0]) / MR_R0       # local rotation about +Y
    c, s = math.cos(a), math.sin(a)
    rot = lambda d: v(c * d[0] - s * d[2], d[1], s * d[0] + c * d[2])
    return Hook(tip, rot(hk.u), rot(hk.t))

# ---------------------------------------------------------------- the chain: older links hang down
DROOP_X, DROOP_R = 0.5 * P, 3.0                                # where the chain bends down, and how tightly
def droop(pts):
    """the chain right of DROOP_X bent down round a quarter circle, then straight down (x, z only)"""
    p = np.array(pts, float); s_ = p[:, 0] - DROOP_X; dz = p[:, 2]; out = p.copy()
    arc = DROOP_R * math.pi / 2
    bend = (s_ > 0) & (s_ <= arc); down = s_ > arc
    ph = s_[bend] / DROOP_R; rr = DROOP_R + dz[bend]
    out[bend, 0] = DROOP_X + rr * np.sin(ph); out[bend, 2] = -DROOP_R + rr * np.cos(ph)
    out[down, 0] = DROOP_X + DROOP_R + dz[down]; out[down, 2] = -DROOP_R - (s_[down] - arc)
    return out

# ---------------------------------------------------------------- scene layout
ROW_XS = [3 * P, 2 * P, P, 0, -P, -2 * P, -3 * P]
CUR_XS = [3 * P, 2 * P, P, 0]
if CHAIN:
    FABRIC0 = chain(CUR_XS, 0.0)
    STATIC = []
elif RING:
    FABRIC0 = [v(MR_XS + 2 * math.pi * MR_R0 - x, 0.0, ZR) for x in np.linspace(0, 2 * math.pi * MR_R0, 36)]  # the ring
    STATIC = []
else:
    FABRIC0 = row_of(CUR_XS, ZT, NB)
    # the rows below, each one's legs down into the one under it, the first into the foundation chain
    CHAIN_DZ = float(os.environ.get("CHAIN_DZ", "-0.5"))
    STATIC = [(row_of(ROW_XS, -H, zh=-2 * H), 1.0), (row_of(ROW_XS, -2 * H, zh=-3 * H, hole_dz=CHAIN_DZ), SHADE_OLD), (chain(ROW_XS, -3 * H), SHADE_OLD)]
E0 = FABRIC0[-1]

# ---------------------------------------------------------------- the left hand on the work
def skin_clearance(pts, sk, sn):
    """for each point: (signed distance to the nearest skin vertex along its normal, that vertex's index)"""
    out_d = np.empty(len(pts)); out_i = np.empty(len(pts), int)
    for k in range(0, len(pts), 256):
        q = pts[k:k + 256]; d2 = ((q[:, None, :] - sk[None, :, :]) ** 2).sum(-1); j = d2.argmin(1)
        out_i[k:k + 256] = j; out_d[k:k + 256] = ((q - sk[j]) * sn[j]).sum(-1)
    return out_d, out_i
if HAND_PTS:
    # the thumb pad on the front face of the work and the middle fingertip's pad on the back: the
    # pads' axis goes straight through the work (-Y), the fingers point L_FINGERS as far as that
    # allows, and the hand slides through the work until thumb and middle touch it equally
    _HL = HAND_PTS[L_VARIANT]
    _J = {k: np.array(x) * HAND_SCALE / UNIT for k, x in _HL.items() if not k.startswith("_")}
    SKIN_L = np.array(_HL["_verts"]) * HAND_SCALE / UNIT; SKIN_LN = np.array(_HL["_normals"])
    _gap = _J["thumb_pad"] - _J["middle_pad"]
    L_ROT = _rot_onto(_gap, v(0, 1, 0), L_AXIS, L_FINGERS)
    L_POS = v(L_PINCH[0], 0.0, L_PINCH[2]) - L_ROT @ ((_J["thumb_pad"] + _J["middle_pad"]) / 2)
    _f0 = droop(FABRIC0) if CHAIN else FABRIC0
    if RING:                                                    # the ring as it sits for the first stitch
        WARP["x0"] = MR_XS - 0.5 * P; _f0 = warp_pts(FABRIC0); WARP["x0"] = None
    _fab = np.vstack([spline(s) for s, _ in STATIC] + [spline(_f0)])
    _thumb = np.linalg.norm(SKIN_L - _J["thumb_tip"], axis=1) < np.linalg.norm(SKIN_L - _J["middle_tip"], axis=1)
    for _ in range(4):
        sk = L_POS + SKIN_L @ L_ROT.T; sn = SKIN_LN @ L_ROT.T
        lo, hi = sk.min(0) - 3, sk.max(0) + 3; f = _fab[np.all((_fab > lo) & (_fab < hi), axis=1)]
        d, j = skin_clearance(f, sk, sn); d -= R
        cf = d[_thumb[j]].min() if _thumb[j].any() else 9.0; cb = d[~_thumb[j]].min() if (~_thumb[j]).any() else 9.0
        L_POS = L_POS - L_AXIS * (cf - cb) / 2
    L_SLACK = (cf + cb) / 2                                   # > 0: air between the pads and the work; < 0: in it
    print("left hand: thumb %.2f, fingers %.2f clear of the work (yarn radii)" % (cf, cb), file=sys.stderr)
else:
    L_ROT = frame_from(v(0.42, 0.1, 1.0), v(-0.25, -1.0, 0.35)); L_POS = v(-3.6 * P, 6.0, 13.0); L_SLACK = 0.0
FINGER_R = {"index": 0.0085, "middle": 0.0088, "ring": 0.0082, "pinky": 0.0072}
YARN_M = R * UNIT
def on_skin(c, d, f):
    """the yarn's centre where it lies on finger f's skin, going out from c on its axis along d (design units, hand frame)"""
    if not HAND_PTS or "_verts" not in HAND_PTS["L"]: return c + d * (FINGER_R[f] * HAND_SCALE / UNIT + R + 0.1)
    q = SKIN_L - c; t = q @ d; perp = np.linalg.norm(q - t[:, None] * d, axis=1)
    rf = FINGER_R[f] * HAND_SCALE / UNIT
    ok = (t > 0) & (perp < 0.45)                  # the first skin the ray meets is this finger's own
    p = c + d * ((t[ok].min() if ok.any() else rf) + 1.06 * R)
    for _ in range(3):                            # then settle onto the skin along its normal
        j = np.argmin(((SKIN_L - p) ** 2).sum(1)); p = SKIN_L[j] + SKIN_LN[j] * 1.06 * R
    return p
def hand_route_local():
    """the working yarn round the left fingers, in the hand frame (design units): over the index,
    under the middle and ring fingers, once round the pinky; every point laid on the skin"""
    if not HAND_PTS: return [np.array([0.0, 0.17, 0.0]) / UNIT]
    J = _J
    across = nrm(J["pinky_knuckle"] - J["index_knuckle"]); back = np.array([0.0, 0.0, 1.0])
    def ring(f, t, angles, slide=0.0):
        k, pip = J[f + "_knuckle"], J[f + "_pip"]; ax = nrm(pip - k); c = k + (pip - k) * t
        zf = nrm(back - ax * (back @ ax)); df = nrm(np.cross(ax, zf)); df = df if df @ across > 0 else -df
        out = []
        for i, a in enumerate(angles):
            d = math.cos(math.radians(a)) * zf + math.sin(math.radians(a)) * df
            out.append(on_skin(c + ax * slide / UNIT * (i / max(1, len(angles) - 1)), d, f))
        return out
    pts = ring("index", 0.6, [-115, -90, -60, -30, 0, 30, 60, 90, 120, 145])   # the yarn comes up from the hook on the thumb side
    pts += ring("middle", 0.45, [180]) + ring("ring", 0.4, [180])
    pts += ring("pinky", 0.45, [210, 180, 150, 120, 90, 60, 30, 0, -30, -60, -90, -120, -150, -180, -210], slide=-0.008)
    pts += [J["pinky_knuckle"] + np.array([-0.01, -0.035, -0.02]) / UNIT]
    # settled together with the yarn's way up from the back of the work (BT below), so the stretch
    # where it meets the index lies on the skin too; it starts where it first touches the hand
    bt = v(X1 + 0.6 * P, 1.6, 1.5) if CHAIN else v(X1 + 0.25 * P, 2.2, -3.0 + 0.1 * max(0.0, SPEC_ZT))       # BT() below
    if RING:                                                     # where it sits once the ring is bent round
        WARP["x0"] = MR_XS - 0.5 * P; bt = warp_pts([v(MR_XS - 0.25 * P, 2.2, MR_BTZ)])[0]; WARP["x0"] = None
    bt = L_ROT.T @ (bt - L_POS)
    c = settle([over_top(bt)] + pts)
    near = np.array([np.sqrt(((SKIN_L - q) ** 2).sum(1).min()) for q in c]) < 1.5 * R
    return c[int(np.argmax(near)):]
def settle(pts, clear=1.06 * R, its=8):
    """the route as a dense line, pushed out of the skin wherever the curve between way-points dips
    into it, and lightly smoothed (the ends stay put)"""
    return list(settle_on(spline(pts, 0.3 * R), SKIN_L, SKIN_LN, clear, its))
def settle_on(c, sk, sn, clear=1.06 * R, its=8):
    c = np.array(c, float)
    lo, hi = c.min(0) - 3, c.max(0) + 3; m = np.all((sk > lo) & (sk < hi), axis=1); sk, sn = sk[m], sn[m]
    def push(c):
        for k in range(0, len(c), 128):
            q = c[k:k + 128]; j = ((q[:, None, :] - sk[None]) ** 2).sum(-1).argmin(1)
            d = ((q - sk[j]) * sn[j]).sum(-1); c[k:k + 128] = q + sn[j] * np.maximum(0.0, clear - d)[:, None]
    for _ in range(its):
        push(c); c[1:-1] = 0.5 * c[1:-1] + 0.25 * (c[:-2] + c[2:])
    for _ in range(3): push(c)                                   # (ending on the smoothing left it in the creases between fingers)
    return c
_route = hand_route_local()
YARN_HAND = [L_POS + L_ROT @ p for p in _route]
YARN_HAND = YARN_HAND + [YARN_HAND[-1] + v(-6.0, 8.0, -20.0)]

# ---------------------------------------------------------------- the left hand at work
# It isn't a fixed clamp: the index presents the yarn for each yarn over (Ly: lifted, turned toward the head,
# dipping as the hook catches), goes forward and down to give yarn as a loop is pulled up or through (Lf),
# the pinch eases and moves along to the new stitch once one is made (Le, and the hand slides along the row),
# and the hand turns a little toward the hook as it goes in and pulls up (about the line through thumb and
# middle pads, so they stay where they hold the work). The poses are baked on L's mesh (make_hands_mpfb.py)
# and blended by weight; the renderer does the same with shape keys (hand_mix.py), so the yarn round the
# fingers moves with them. Sources: Lion Brand (the index wraps the yarn), Vogue Knitting (the thumb and
# middle hold the work just below the hook and move up every few stitches; the index feeds the yarn).
WORK_POSES = ("Ly", "Lf", "Le")
HAND_ACTIVE = os.environ.get("HAND_ACTIVE", "1") == "1" and bool(HAND_PTS) and all(k in HAND_PTS for k in WORK_POSES)
LY_W, LF_W, LE_W = 0.85, 0.7, 0.6                               # how far into each pose (1 = the baked pose)
WRIST_DEG = float(os.environ.get("WRIST_DEG", "-11"))             # the hand's turn toward the hook (sign checked below)
CREEP = float(os.environ.get("CREEP", "0.5")) * P               # how far the pinch moves along the row per stitch made
HAND_NOW = {"mix": {}, "Rw": np.eye(3), "t": np.zeros(3)}
_PIVOT = L_POS + L_ROT @ ((_J["thumb_pad"] + _J["middle_pad"]) / 2) if HAND_PTS else L_PINCH
_D_SKIN, _D_ROUTE, _D_J, _N_SKIN = {}, {}, {}, {}
if HAND_ACTIVE:
    _hl0 = np.array(HAND_PTS["L"]["_verts"]) * HAND_SCALE / UNIT
    _keep = (SKIN_L, SKIN_LN, dict(_J))
    _NR = max(len(_route), int(np.linalg.norm(np.diff(np.asarray(_route), axis=0), axis=1).sum() / (0.4 * R)) + 1)   # (fine enough to keep off the fingers)
    for _k in WORK_POSES:
        _D_SKIN[_k] = np.array(HAND_PTS[_k]["_verts"]) * HAND_SCALE / UNIT - _hl0      # the pose's change from L
        _jk = {k: np.array(x) * HAND_SCALE / UNIT for k, x in HAND_PTS[_k].items() if not k.startswith("_")}
        _j0 = {k: np.array(x) * HAND_SCALE / UNIT for k, x in HAND_PTS["L"].items() if not k.startswith("_")}
        _D_J[_k] = {k: _jk[k] - _j0[k] for k in _jk if k in _j0}
        SKIN_L = _keep[0] + _D_SKIN[_k]; SKIN_LN = np.array(HAND_PTS[_k]["_normals"]); _N_SKIN[_k] = SKIN_LN - _keep[1]
        _J = {k: _keep[2][k] + (_jk[k] - _j0[k]) if k in _jk else x for k, x in _keep[2].items()}
        _rk = hand_route_local()
        _D_ROUTE[_k] = resample(np.asarray(_rk), n=_NR) - resample(np.asarray(_route), n=_NR)
    SKIN_L, SKIN_LN, _J = _keep
    _route = resample(np.asarray(_route), n=_NR)

# the index and middle fingers as capsules (bone to bone, the skin's median distance round each), so yarn found
# inside a finger is pushed out sideways from its bone: the nearest skin point doesn't say which way is out
# from deep inside a fingertip
_SEGS = [(f + "_" + a, f + "_" + b) for f in ("index", "middle") for a, b in (("knuckle", "pip"), ("pip", "dip"), ("dip", "tip"))]
def _seg_d(q, a, b):
    ab = b - a; t = np.clip(((q - a) @ ab) / (ab @ ab), 0.0, 1.0); f = a + t[:, None] * ab; return q - f, t
_SEG_R = {}
if HAND_PTS:
    _all = [(f + "_" + a, f + "_" + b) for f in ("thumb", "index", "middle", "ring", "pinky") for a, b in (("knuckle", "pip"), ("pip", "dip"), ("dip", "tip"))]
    _dd = np.stack([np.linalg.norm(_seg_d(SKIN_L, _J[a], _J[b])[0], axis=1) for a, b in _all], 1); _own = _dd.argmin(1)
    for _i, (a, b) in enumerate(_all):
        if (a, b) in _SEGS:
            _m = (_own == _i) & (_dd[:, _i] < 4.0); _SEG_R[(a, b)] = float(np.median(_dd[_m, _i])) if _m.sum() > 20 else 0.0
def joints_now(hs=None):
    hs = hs or HAND_NOW; Rh, ph = hand_xform(hs); out = {}
    for k in {k for ab in _SEGS for k in ab}:
        loc = _J[k] + sum((w * _D_J[p][k] for p, w in hs["mix"].items() if k in _D_J.get(p, {})), np.zeros(3))
        out[k] = ph + Rh @ loc
    return out
def off_fingers(q):
    if not _SEG_R: return q
    jn = joints_now()
    for (a, b), r in _SEG_R.items():
        if r <= 0: continue
        d, _ = _seg_d(q, jn[a], jn[b]); n = np.linalg.norm(d, axis=1); need = r + 1.06 * R
        m = n < need
        if m.any(): q = q.copy(); q[m] = q[m] + d[m] / np.maximum(n[m], 1e-6)[:, None] * (need - n[m])[:, None]
    return q

def hand_samples(n=24):
    """the left hand's states over the take (with its offset), for what must clear it wherever it goes"""
    if not HAND_ACTIVE: return []
    out = []
    for ta in np.linspace(0.0, TOTAL_ACT, n):
        out.append(hand_state(ta))
    return out
def _bell(p, a, b):
    x = min(1.0, max(0.0, (p - a) / (b - a))); return math.sin(math.pi * x) ** 2
def hand_state(ta):
    """the left hand at action time ta: its pose mix, its turn (about the pads' line) and its slide along the row"""
    if not HAND_ACTIVE: return {"mix": {}, "Rw": np.eye(3), "t": np.zeros(3)}
    op, p = op_at(ta); n = op.name; mix = {}
    if n in ("yo_catch", "yo_front", "yo_free"):
        q = p / 0.55 if n == "yo_free" else p                    # (yo_free: the yarn over is its first part)
        mix["Ly"] = LY_W * (_bell(q, 0.0, 1.0) - 0.3 * _bell(q, 0.5, 0.85))   # lifted toward the head; dips as it catches
        mix["Lf"] = 0.25 * _bell(q, 0.5, 0.85)
    elif n in ("pull_up", "pull_keep", "through2"):
        mix["Lf"] = LF_W * _bell(p, 0.1, 0.95)                   # forward and down: giving yarn as the loop comes up
    elif n == "through":
        mix["Lf"] = LF_W * _bell(p, 0.05, 0.7)
        mix["Le"] = LE_W * _bell(p, 0.65, 1.0)                   # the stitch made: the pinch eases, moves along, holds again
    w = {"insert": lambda q: ease(q), "yo_catch": lambda q: 1.0, "pull_up": lambda q: 1.0 - ease(q),
         "pull_keep": lambda q: 1.0 - ease(q)}.get(n, lambda q: 0.0)(p)
    Rw = _rot(L_AXIS, math.radians(WRIST_DEG) * w) if WRIST_DEG else np.eye(3)
    made = sum(1 for o in OPLIST if o.name == "through" and o.t0 + o.dur * MOVE_SHARE <= ta)
    cur = ease((p - 0.7) / 0.3) if n == "through" and p < 1.0 else 0.0
    t = v(-CREEP, 0, 0) * (made + cur) if not (RING or CHAIN) else np.zeros(3)
    return {"mix": {k: round(float(x), 4) for k, x in mix.items() if x > 1e-4}, "Rw": Rw, "t": t}
def hand_xform(hs=None):
    """(rotation, position) of the left hand's frame now"""
    hs = hs or HAND_NOW; Rw = hs["Rw"]
    return Rw @ L_ROT, _PIVOT + Rw @ (L_POS - _PIVOT) + hs["t"] + L_OFF[0]
def skin_now(hs=None):
    """the left hand's skin (row space) and its normals, as it is now"""
    hs = hs or HAND_NOW; Rh, ph = hand_xform(hs); loc = SKIN_L; nl = SKIN_LN
    for k, w in hs["mix"].items(): loc = loc + w * _D_SKIN[k]; nl = nl + w * _N_SKIN[k]
    if hs["mix"]: nl = nl / np.linalg.norm(nl, axis=1, keepdims=True)
    return ph + loc @ Rh.T, nl @ Rh.T
def route_now(hs=None):
    """the working yarn's way round the left fingers (row space), moving with them"""
    if not HAND_ACTIVE: return [q + L_OFF[0] for q in YARN_HAND]
    hs = hs or HAND_NOW; Rh, ph = hand_xform(hs); loc = _route
    end = loc[-1] + L_ROT.T @ v(-6.0, 8.0, -20.0)
    loc = np.vstack([loc] + [lerp(loc[-1], end, f)[None] for f in np.linspace(0, 1, 25)[1:]])   # (on to the ball, in steps)
    key = tuple(sorted(hs["mix"].items()))
    if key in _ROUTE_C: loc = _ROUTE_C[key]
    elif hs["mix"]:
        # blended between the poses' routes, then settled on the blended skin as the baked routes are (the
        # blend alone can cut a finger where the poses' routes differ)
        sk, sn = SKIN_L, SKIN_LN
        for k, w in hs["mix"].items():
            loc = loc + w * np.vstack([_D_ROUTE[k], np.repeat(_D_ROUTE[k][-1:], 24, 0)]); sk = sk + w * _D_SKIN[k]; sn = sn + w * _N_SKIN[k]
        sn = sn / np.linalg.norm(sn, axis=1, keepdims=True)
        loc = _ROUTE_C[key] = settle_on(loc, sk, sn)
        if len(_ROUTE_C) > 64: _ROUTE_C.pop(next(iter(_ROUTE_C)))
    return list(ph + loc @ Rh.T)
_ROUTE_C = {}

DOWN = v(0, 0, -1)
U_REST, U_IN, U_UP = v(1.0, -0.55, 0.8), v(0.8, -1.35, 0.45), v(0.95, -0.9, 0.85)   # U_IN flatter: the tip comes up behind the work
U_PULL = v(*map(float, os.environ.get("U_PULL", "1.0,-0.5,0.6").split(",")))          # after pulling up a loop: ~40 degrees off the guided view's line, the hand beside the head, not over it
def HOLE(hx): return v(hx, 0.0, -H - 1.3)
def T_IN(hx): return v(hx - 0.2, 4.2, -H - 1.6) - nrm(U_IN) * 4.5     # well out the back, along the shaft
def T_UP(hx, lift): return v(hx + 0.5, -2.6, -H + 4.0 + lift)
def REST(E): return E + v(0, -2.05, 1.35)
def ANCHOR(E): return E + v(0.3 * P, -0.25, 0.85)
def BT(x):
    """where the working yarn comes over the top of the work, behind it (low enough for a hook in a
    stitch to reach); a chain has nothing behind it: just behind and above the loop on the hook"""
    return v(x + 0.6 * P, 1.6, 1.5) if CHAIN else v(x + 0.25 * P, 2.2, (MR_BTZ if RING else -3.0) + 0.1 * max(0.0, ZT))
NTHR = sum(1 for s in SPEC["steps"] for o in s if o in ("through2",)) + 1
def lift_for(k): return max(0.0, ZT) * (0.3 + 0.55 * k / max(1, NTHR))

# ---------------------------------------------------------------- state
class Loop:
    def __init__(s, kind, hole=None): s.kind, s.hole = kind, hole
class State:
    def __init__(s): pass
    def copy(s):
        o = State(); o.__dict__ = dict(s.__dict__); o.loops = list(s.loops); o.prefix = list(s.prefix); return o

_FAB_PTS = []
def live_clear_d(S, hk, d0, lo):
    """the shaft position nearest d0 where the live loop (a ring round the shaft) clears the fabric by a yarn's
    width: with the hook in a stitch, the shaft in front of it can run along the face of the row below"""
    if not _FAB_PTS: _FAB_PTS.append(np.vstack([spline(s_) for s_, _ in STATIC]) if STATIC else np.zeros((0, 3)))
    pre = np.asarray(S.prefix); pre = pre[np.linalg.norm(pre - S.E, axis=1) > 3.0 * R]
    F = np.vstack([_FAB_PTS[0], pre]) if len(pre) else _FAB_PTS[0]
    ds_ = np.arange(lo, lo + 14.0, 0.25); ax_ = hk.tip[None] + ds_[:, None] * hk.u[None]
    near_ = F[np.all((F > ax_.min(0) - 6) & (F < ax_.max(0) + 6), axis=1)]
    if not len(near_): return d0
    clr = np.array([np.linalg.norm(near_ - q, axis=1).min() for q in ax_])
    need = np.array([hook_profile(x)[1] for x in ds_]) + 3.0 * R          # the ring round the shaft, then a yarn's width
    ok = clr >= need
    if not ok.any(): return float(ds_[np.argmax(clr - need)])
    return float(ds_[ok][np.argmin(np.abs(ds_[ok] - d0))])

def loop_ds(S, hk):
    """shaft positions of the loops (yarn order): the newest nearest the tip; the live loop held
    back by the fabric where it can be"""
    n = len(S.loops); ds = []
    for i, L in enumerate(S.loops):
        rank = n - 1 - i; d = D_B + rank * SPACING
        if L.kind == "live":
            lo = d; d = max(lo, min(max(14.0, lo), (ANCHOR(S.E) - hk.tip) @ hk.u))
            if not (CHAIN or RING) and hk.tip[1] > 0 and hk.u[1] < -0.05:   # a hook through the work: the loop sits where it clears it
                d = live_clear_d(S, hk, d, lo)
        ds.append(d)
    return ds

def yarn_leaves(S):
    """where the held yarn leaves the work on its way to the left index: low behind it while the hook is in a
    stitch (so the hook can reach it there); once a loop is pulled up and the hook is out, over the top edge
    behind the loops (the yarn over is taken there, above the work, not through it)"""
    last_pulled = bool(S.loops) and S.loops[-1].kind == "pulled"
    A = BT(S.xw) + v(-1.2, 0.3, 0) if last_pulled else BT(S.xw)
    if last_pulled and S.inserted is None and not (CHAIN or RING) and YARN_TOP:
        pre = np.asarray(S.prefix); near_ = pre[np.abs(pre[:, 0] - A[0]) < P]
        top = near_[:, 2].max() if len(near_) else ZT
        A = v(A[0], 1.3, max(A[2], top + 1.6 * R))
    elif PRE_TOP and NB > 0 and S.inserted is None and S.hole_i == 0 and not (CHAIN or RING):
        # a taller stitch's yarn overs before the hook goes in: the hook is in front of the work, so the yarn from
        # its loops goes back over the top edge (low behind it, it ran through the work to them)
        pre = np.asarray(S.prefix); near_ = pre[np.abs(pre[:, 0] - A[0]) < P]
        top = near_[:, 2].max() if len(near_) else ZT
        A = v(A[0], 1.3, max(A[2], top + 1.6 * R))
    return A
PRE_TOP = os.environ.get("PRE_TOP", "1") == "1"            # (hdc/dc/tr) see yarn_leaves; 0: as before
CLOSE_LAG = float(os.environ.get("CLOSE_LAG", "0.35"))
CLOSE_OWN = os.environ.get("CLOSE_OWN", "1") == "1"           # (0: the new stitch counts as fabric from the start of the close, as before)
SL_THRU = os.environ.get("SL_THRU", "1") == "1"               # after a slip stitch the yarn goes on down through it, the way the yarn over came (0: over the top)
YARN_TOP = os.environ.get("YARN_TOP", "1") == "1"

def legs_in(hx, s, w0):
    h1 = HOLE(hx) + v(0.55, 0, 0)
    return [BT(hx), lerp(w0, h1 + v(0, 1.4, 0.1), s), lerp(w0, h1, s), lerp(w0, h1 + v(0, -1.4, 0.4), s)]
def legs_out(hx, s, w1):
    h2 = HOLE(hx) + v(-0.55, 0, 0)
    return [lerp(w1, h2 + v(0, -1.4, 0.4), s), lerp(w1, h2, s), lerp(w1, h2 + v(0, 1.4, 0.1), s)]

def assemble(S, hk, ds=None, form=None, throat=None, keep=None, tail=None, rings=None, thread=None):
    """the active yarn from E0 to the ball, for state S and hook hk.
    ds: shaft position per loop (default loop_ds); form: {loop index: (angles, legs blend)} for a
    loop being formed (angles, legs blend[, way-points before it]); throat: "touch" -> the working
    yarn bends over the hook where the throat pushes into it, "caught" -> it lies in the throat and
    goes round with the hook's roll (contact); keep: hole x of yarn held in the throat and pulled
    through that stitch (slip stitch); tail: way-points that replace the working yarn up to the hand;
    rings: {loop index: points} for loops off the shaft; thread: centres of those loops, farthest
    first, that the caught yarn's two strands run back through on either side of the throat"""
    ds = ds if ds is not None else loop_ds(S, hk); form = form or {}
    pts = list(S.prefix); marks = {"e": len(S.prefix) - 1}
    pts.append(S.E + v(0, -0.6, 1.2))
    split = len(S.prefix) - 1
    for i, L in enumerate(S.loops):
        f = form.get(i, ((25, -295), 1.0)); (ain, aout), s = f[0], f[1]
        r = rings[i] if rings and i in rings else wrap(hk, ds[i], ain, aout)
        if L.kind == "drawn" and S.post is not None:
            pts += post_partial(*S.post)
        if len(f) > 2: pts += f[2]
        marks["ring%d" % i] = len(pts)
        if i == 0: marks["a0"] = len(pts)
        if L.kind == "pulled":
            pts += legs_in(L.hole, s, r[0])
            if i == 0: marks["a0"] = len(pts); split = len(pts) + len(r) // 2
            pts += r + legs_out(L.hole, s, r[-1])
        else:
            if i == 0: split = len(pts) + len(r) // 2
            pts += r
        if i == 0: marks["a1"] = len(pts)
    if not S.loops: marks["a0"] = marks["a1"] = len(pts) - 1
    marks["new"] = len(pts)
    last_pulled = bool(S.loops) and S.loops[-1].kind == "pulled"
    xw = S.xw
    A = yarn_leaves(S)                                           # the yarn leaves the work here, straight up to the hand
    if tail is not None:
        pts += tail
    elif keep is not None:                                       # slip stitch: the caught yarn, still in the throat, through the stitch
        r = wrap(hk, THROAT_D, 250, min(200.0, hk.roll - 50))
        pts += legs_in(keep, S.keep_s, r[0]) + r + legs_out(keep, S.keep_s, r[-1]) + [BT(keep) + v(-1.2, 0.3, 0)]
    else:
        if not (CHAIN or RING or throat):
            # from the loops on the hook the yarn goes back over the top of the work, then down behind it
            # to where the hook can reach it, not through the stitches between (not while the hook has it)
            pre = np.asarray(S.prefix); near_ = pre[np.abs(pre[:, 0] - A[0]) < P]
            if getattr(S, "thru", None) is not None:           # after a slip stitch: down through it, the way the yarn over came
                pts += legs_out(S.thru, 1.0, pts[-1])          # (over the top, its pull-through crossed the stitch under it)
            elif len(near_): pts += [v(A[0], A[1], max(A[2], near_[:, 2].max() + 1.6 * R))]
        pts += [A]
        side = hk.z * SIDE_OFF * R                                    # the caught yarn's two strands, side by side (a yarn's width apart, not through each other)
        tin = [c + side for c in thread] if thread else []; tout = [c - side for c in reversed(thread)] if thread else []
        ang = contact(hk, tin[-1] if tin else A, tout[0] if tout else over_top(A), throat == "caught") if throat else None
        pts += tin
        if ang: pts += wrap(hk, THROAT_D, *ang)
        pts += tout + [over_top(A)]
    rt = route_now()
    if HAND_ACTIVE:                                              # the way up to the index in steps: it is kept off the fingers as they move
        n_ = int(np.linalg.norm(rt[0] - pts[-1]) / (0.4 * R))
        pts += [lerp(pts[-1], rt[0], f) for f in np.linspace(0, 1, n_ + 2)[1:-1]]
    marks["hand"] = len(pts)
    pts += rt
    return Path(pts, marks, split, len(S.prefix) - 1)

# ---------------------------------------------------------------- ops
OPS = []          # (step index, op name, arg) in order
for si, ops in enumerate(SPEC["steps"]):
    for o in ops: OPS.append([si, o])
# hole / new-stitch bookkeeping: which stitch each insert goes into
XS = SPEC.get("xs"); HOLES = SPEC.get("holes")
if RING:
    XS = [MR_XS - 0.5 * P - k * P for k in range(MR_N)]; HOLES = [[x] for x in XS]
if not XS: XS, HOLES = [X1], [[X1]]
# action clock: each step lasts STEP_DUR, its ops share it
for si in range(len(STEPS)):
    mine = [o for o in OPS if o[0] == si]
    for k, o in enumerate(mine):
        o += [(si + k / len(mine)) * STEP_DUR, STEP_DUR / len(mine)]
TOTAL_ACT = len(STEPS) * STEP_DUR

S = State()
S.prefix = list(FABRIC0); S.E = E0; S.loops = [] if RING else [Loop("live")]
S.post = None; S.xw = XS[0]; S.inserted = None; S.caught = False; S.keep_s = 0.0; S.thru = None
S.stitch = 0; S.hole_i = 0; S.nthr = 0; S.x0 = XS[0] if RING else None; S.ring_r = MR_R0
S.hk = (Hook(REST(E0), U_REST, DOWN) if not RING else Hook(REST(v(MR_XS, -0.25, 0.15)), U_REST, DOWN))
S.ring_on = not RING

class Op:
    pass

def make_ops():
    out = []; st = S
    for si, name, t0, dur in OPS:
        op = Op(); op.step, op.name, op.t0, op.dur = si, name, t0, dur; op.S = st
        e = st.copy()
        hx = HOLES[st.stitch][min(st.hole_i, len(HOLES[st.stitch]) - 1)] if st.stitch < len(HOLES) else None
        op.hx = hx
        if name == "insert":
            e.inserted = hx; e.xw = hx; e.thru = None
        elif name == "yo_catch" or name == "yo_front":
            e.caught = True
        elif name == "yo_free":
            e.loops = st.loops + [Loop("wrap")]
        elif name == "pull_up":
            e.loops = st.loops + [Loop("pulled", hx)]; e.caught = False; e.inserted = None; e.hole_i = st.hole_i + 1
        elif name == "pull_keep":
            e.caught = True; e.inserted = None; e.keep = hx; e.keep_s = 1.0
        elif name in ("through", "through2"):
            n = 2 if name == "through2" else len(st.loops)
            e.caught = False; e.keep = None; e.thru = getattr(st, "keep", None) if SL_THRU else None
            if name == "through2":
                # the two loops nearest the tip come off into the post; the caught yarn is a new loop
                e.loops = st.loops[:-2] + [Loop("drawn")]; e.nthr = st.nthr + 1
                e.post = (st.xw, T_UP(st.xw, lift_for(e.nthr))[2], e.nthr, ZT, NB)
            else:
                x = XS[st.stitch]; holes = HOLES[st.stitch]
                if CHAIN: piece = chain_link(x, 0.0)
                elif RING and st.stitch == 0:     # pull up + ch 1: the turning chain standing on the ring
                    piece = stitch_static(x, ZT, holes, 0)
                else: piece = stitch_static(x, ZT, holes, NB)
                e.prefix = st.prefix + piece[1:]; e.E = piece[-1]
                e.loops = [Loop("live")]; e.post = None; e.nthr = 0
                e.stitch = st.stitch + 1; e.hole_i = 0
                e.xw = XS[e.stitch] if e.stitch < len(XS) else x - P
                e.x0 = e.xw if RING else None
        elif name == "mr_loop":
            e.ring_on = True
        elif name == "mr_close":
            e.ring_r = MR_R1
        op.E = e; out.append(op); st = e
    return out
OPLIST = make_ops()

# the left hand lets go of the magic ring before the finished stitches turn round into its pinch:
# it backs off outward, away from the ring's centre, as the sixth stitch is pulled through (and stays off)
L_OFF = [np.zeros(3)]                                           # set per frame (frame_strands)
L_RELEASE = None
if RING and HAND_PTS:
    _op = next(o for o in OPLIST if o.name == "through" and o.S.stitch == 5)
    L_RELEASE = (_op.t0 + 0.15 * _op.dur * MOVE_SHARE, _op.t0 + 0.5 * _op.dur * MOVE_SHARE, 7.0 * nrm((L_PINCH - MR_C) * v(1, 0, 1)))
def l_off(ta):
    if L_RELEASE is None: return np.zeros(3)
    a0, a1, off = L_RELEASE; return off * ease((ta - a0) / (a1 - a0))

LIVE_CLEAR = float(os.environ.get("LIVE_CLEAR", "2.6"))   # the live loop on a hook through the work: this far in front of where the shaft goes in
YO_FRONT_DZ = float(os.environ.get("YO_FRONT_DZ", "1.5"))  # a yarn over with the hook out of the stitch: caught this high over the row's top
YO_CATCH_Z = -H + float(os.environ.get("YO_CATCH_DZ", "2.5"))   # how high (above the tops of the row the hook is in) a hook in a stitch catches the yarn
YO_ROLL = 180.0                     # the throat turned to face straight up while the yarn is laid over the shaft (degrees from facing down)
PU_OUT = float(os.environ.get("PU_OUT", "2.0"))     # pulling up: the head backs straight out to this far in front of the work, then lifts
PU_LIFT = float(os.environ.get("PU_LIFT", "3.0"))
ROLL_SHOW = float(os.environ.get("ROLL_SHOW", "150"))                   # pulling up a loop: the throat up and toward the viewer, the caught yarn in it in view
ROLL_PULL = 70.0                    # ...and where it faces while it drags the yarn through: toward the pull
def _rot(axis, a):
    k = nrm(axis); K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K
def yo_plan(op):
    """where a yarn over goes: the point Q of the held yarn (straight from where it leaves the work to
    the left index) nearest the throat, the throat's down direction there, and for a hook that is in
    a stitch, how far it backs out and tips up about the stitch to get under the yarn"""
    if hasattr(op, "plan"): return op.plan
    S0 = op.S; h0 = S0.hk; c0 = h0.axis_centre(THROAT_D); dn, _ = h0.basis()
    last_pulled = bool(S0.loops) and S0.loops[-1].kind == "pulled"
    A = yarn_leaves(S0); B = over_top(A)
    d = B - A; Q = A + d * np.clip((c0 - A) @ d / (d @ d), 0, 0.6)       # on its way up behind the work
    if op.name == "yo_front" and ZT >= 0 and not (RING or CHAIN):   # catch it above the row's top (where it runs over to the finger), not behind the work: the hook would go through the stitches
        Q = A + d * np.clip((ZT + YO_FRONT_DZ - A[2]) / d[2], 0, 0.9)
    if op.name == "yo_catch" and not RING:                       # a hook in a stitch: catch it up clear of the row it is in, in view
        Q = A + v(0, 0.8, 0) + d * np.clip((YO_CATCH_Z - A[2]) / d[2], 0, 0.6)   # drawn back a little: the throat well out the back
    ub = U_UP if op.name == "yo_front" and not (CHAIN or RING) else h0.u     # (a loop just pulled up ends turned aside, U_PULL: not this)
    if CHAIN: ub = v(1.0, -0.2, 0.0)                             # the chain: the shaft across the view, the head and throat side on (not foreshortened behind the loop)
    plan = dict(c0=c0, Q=Q, dn=dn, dip=Q + dn * (THROAT_R + 1.0), catch=Q + dn * (THROAT_R - 1.3),
                u_yo=nrm(v(ub[0], ub[1], -0.25 * np.hypot(ub[0], ub[1]))))    # shaft falling toward the hand: the head higher
    if op.name == "yo_catch":                                    # in the stitch: back out a little, tip up about it
        hole = HOLE(S0.xw)
        # back out only as far as the throat must come in to reach the yarn (the head stays well out the back)
        k = 2.5 if RING else float(np.clip(np.linalg.norm(c0 - hole) - np.linalg.norm(plan["catch"] - hole), -1.0, 2.5))
        cr = c0 + h0.u * k
        ax = np.cross(cr - hole, plan["catch"] - hole)
        phi = min(math.radians(50 if RING else 65), math.acos(np.clip(nrm(cr - hole) @ nrm(plan["catch"] - hole), -1, 1)))
        plan.update(hole=hole, k=k, ax=ax, phi=phi)
    op.plan = plan; return plan

def yo_roll(r0, p):
    """the throat during a yarn over: round through the front to face straight up while the yarn is
    laid over the shaft, then (once it is there) on over the top to face the pull, hooking it in"""
    if p < 0.6: return r0 + (YO_ROLL - r0) * ease((p - 0.1) / 0.4)
    return YO_ROLL + (ROLL_PULL - YO_ROLL) * ease((p - 0.6) / 0.35)
def yo_pose(op, p, theta):
    """the hook doing a yarn over: under the held yarn, up into it so it lies over the shaft, and back a
    little with it caught; the throat turned theta"""
    h0 = op.S.hk; pl = yo_plan(op)
    if "hole" in pl:
        f = ease(p / 0.6) - 0.25 * ease((p - 0.7) / 0.3)
        Rm = _rot(pl["ax"], pl["phi"] * f) if np.linalg.norm(pl["ax"]) > 1e-6 else np.eye(3)
        u = Rm @ h0.u; tip = pl["hole"] + Rm @ (h0.tip + h0.u * pl["k"] * ease(p / 0.6) - pl["hole"])
        return rolled(tip, u, theta)
    c0, dip, cat = pl["c0"], pl["dip"], pl["catch"]
    u = slerp_dir(h0.u, pl["u_yo"], ease(p / 0.45))             # the head tilts up, above the yarn
    if p < 0.45: c = bez(c0, c0 + pl["dn"] * 1.5, dip + pl["dn"] * 1.0, dip, ease(p / 0.45))     # under the yarn
    elif p < 0.7: c = lerp(dip, cat, ease((p - 0.45) / 0.25))                                    # up into it
    else: c = lerp(cat, lerp(cat, c0, 0.35), ease((p - 0.7) / 0.3))                              # back, with it caught
    h = rolled(v(0, 0, 0), u, theta)
    return rolled(c - u * THROAT_D - h.t * hook_profile(THROAT_D)[0], u, theta)

def op_pose(op, p):
    """hook pose (row space) for op at progress p (0..1 of its move), kept out of the left hand"""
    return off_left_hook(_op_pose(op, p))
def off_left_hook(hk):
    """the hook's head slid out of the left hand where a move would take it into the fingers"""
    if not HAND_PTS or RING and WARP["x0"] is None: return hk   # the ring: only once it is bent round for the frame
    ds = np.linspace(0.0, 20.0, 21)
    need = np.array([hook_profile(d)[1] for d in ds]) + 2.1 * R      # room for the yarn lying on the fingers
    sk, sn = skin_now()
    for _ in range(4):                                               # a push off one finger can land on the next
        axis = hk.tip + ds[:, None] * hk.u
        if RING: axis = warp_pts(axis) if WARP["x0"] is not None else axis
        near = np.all((sk > axis.min(0) - 6) & (sk < axis.max(0) + 6), axis=1)
        if not near.any(): return hk
        d, j = skin_clearance(axis, sk[near], sn[near]); short = need - d
        if short.max() <= 0: return hk
        i = int(np.argmax(short)); push = sn[near][j[i]] * (short[i] + 0.05)
        if RING and WARP["x0"] is not None:                          # the ring bends row space round: push back in row space
            a = (WARP["x0"] - hk.tip[0]) / MR_R0; c, s_ = math.cos(a), math.sin(a)
            push = v(c * push[0] + s_ * push[2], push[1], -s_ * push[0] + c * push[2])
        h = Hook(hk.tip + push, hk.u, hk.t); h.roll = hk.roll; hk = h
    return hk
def _op_pose(op, p):
    S0 = op.S; h0 = S0.hk; e = ease(p); hx = op.hx
    def back(hold):
        """after a yarn over the throat turns back round to face the pull (ROLL_PULL) and drags the
        yarn so; once the loop is made (from progress hold) it turns on down"""
        if h0.roll <= 1.0: return 0.0
        r = ROLL_PULL + (h0.roll - ROLL_PULL) * (1 - ease(min(1.0, p / 0.35)))
        return r * (1 - ease((p - hold) / 0.25))
    if op.name == "insert":
        # come down in front of the stitch already turned to the insert angle, then slide straight
        # in along the shaft (the tip leads; nothing moves sideways through the fabric)
        tip = bez(h0.tip, v(hx + 0.3, -4.0, -H + 1.0), T_IN(hx) + nrm(U_IN) * 7.5, T_IN(hx), e)
        return rolled(tip, slerp_dir(h0.u, U_IN, ease(min(1.0, p / 0.55))), back(0.0))
    if op.name in ("yo_catch", "yo_front"):
        return yo_pose(op, p, yo_roll(h0.roll, p))
    if op.name == "yo_free":                                     # caught in the first half, then the wrap slides up the shaft
        if p < 0.55: return yo_pose(op, p / 0.55, yo_roll(h0.roll, p / 0.55))
        h1 = yo_pose(op, 1.0, YO_ROLL); q = ease((p - 0.55) / 0.45)
        return rolled(lerp(h1.tip, h0.tip, q), h0.u, YO_ROLL * (1 - q))
    if op.name in ("pull_up", "pull_keep"):
        k = 0.55 if op.name == "pull_keep" else 1.0
        # back out the way it went in (along the shaft) before lifting the loop up in front
        dst = T_UP(hx, lift_for(0)) + (v(0, -0.6, PU_LIFT) if not RING else 0) if k == 1 else v(hx + 0.4, -2.8, -H + 2.0)   # the head up clear of the work, against the backdrop
        tip = bez(h0.tip, h0.tip + h0.u * 7.5, v(hx + 0.3, -3.5, -H), dst, e)
        if not RING and h0.tip[1] > 0 and h0.u[1] < -0.05:
            # straight back out along the shaft (the way it went in, back through the hole under the V, not up
            # through the V) until the head is in front of the work, then up
            L_out = (h0.tip[1] + PU_OUT) / -h0.u[1]; out = h0.tip + h0.u * L_out
            tip = h0.tip + h0.u * L_out * ease(e / 0.4) if e < 0.4 else bez(out, out + h0.u * 2.0, dst + v(0.5, -1.0, -1.0), dst, (e - 0.4) / 0.6)
        if k == 1 and not RING:                                      # (the ring's brisk stitches keep the plain pull)
            # the head comes out to the front with the caught yarn in view: the throat turns up and toward the
            # viewer (ROLL_SHOW) and stays so, the shaft ends turned aside (U_PULL) so the hand is not in front
            # of the head
            r = h0.roll + (ROLL_SHOW - h0.roll) * ease(p / 0.3)
            return rolled(tip, slerp_dir(h0.u, U_PULL, ease(max(0.0, (p - 0.35) / 0.65))), r)
        # the slip stitch's pull through the stitch: the shaft ends turned aside too, the hand beside the head
        return rolled(tip, slerp_dir(h0.u, U_PULL if not RING else U_UP, ease(max(0.0, (p - 0.35) / 0.65))), back(0.75))
    if op.name in ("through", "through2"):
        # the loops crowd up to the head, then the hook draws back along its shaft through them, the
        # caught yarn in the throat: each loop passes off over the head (raw_path: through_loops)
        T_OUT = h0.tip + h0.u * slide_back(op, 1.0) + v(0, 0, 0.6)
        if p < PULL_SPLIT:
            qq = p / PULL_SPLIT
            return rolled(h0.tip + h0.u * slide_back(op, qq) + v(0, 0, 0.6) * ease(qq), h0.u, back(PULL_SPLIT))
        q = ease((p - PULL_SPLIT) / (1 - PULL_SPLIT))
        if op.name == "through2":
            dst, ud = T_UP(S0.xw, lift_for(op.E.nthr)), U_UP
        else:
            dst, ud = REST(op.E.E), U_REST
        return rolled(bez(T_OUT, T_OUT + v(0.2, -0.6, 1.2), dst + v(0.8, -1.0, 1.0), dst, q), slerp_dir(h0.u, ud, q), back(PULL_SPLIT))
    return h0
PULL_SPLIT = 0.55
RIDE = 0.4                                   # share of the pull-through spent crowding the loops up to the head
def n_through(op): return 2 if op.name == "through2" else len(op.S.loops)
def slide_back(op, qq):
    """how far the hook has drawn back along its shaft at pull-through progress qq (0..1 of PULL_SPLIT):
    a little while the loops crowd to the head, then enough for the last of them to pass off it"""
    off = D_B + SPACING * (n_through(op) - 1) + 2.6
    return 1.2 * ease(qq / RIDE) + off * ease((qq - RIDE) / (1 - RIDE))

# end poses, chained: every op starts where the previous one left the hook
for i, op in enumerate(OPLIST):
    op.i = i; op.E.hk = op_pose(op, 1.0)

def raw_path(op, p):
    """the op's own yarn (row space) at progress p, as a Curve"""
    S0 = op.S; hk = op_pose(op, p); e = ease(p); n = len(S0.loops)
    if op.name in ("insert", "hold", "mr_close"):
        return assemble(S0, hk).curve()
    if op.name in ("yo_catch", "yo_front"):
        # the held yarn stays where it is until the hook pushes into it; caught once the throat faces it
        return assemble(S0, hk, throat="caught" if p >= 0.6 else "touch").curve()
    if op.name == "yo_free":
        # caught in the throat as above, then (rolling back down) the wrap slides up the shaft into
        # its place; the same way-points throughout so the halves join: [.. loops, BT, wrap, hand]
        bt = BT(S0.xw)
        if p < 0.55: return assemble(S0, hk, throat="caught" if p / 0.55 >= 0.6 else "touch").curve()
        q = ease((p - 0.55) / 0.45); S1 = op.E
        ds1 = loop_ds(S1, hk); ds0 = loop_ds(S0, hk)
        ds = [lerp(ds0[i], ds1[i], q) for i in range(n)] + [lerp(THROAT_D, ds1[-1], q)]
        a0 = contact(hk, bt, over_top(bt), True)
        ang = (lerp(a0[0], 25, q), lerp(a0[1], -295, q))
        w = wrap(hk, ds[-1], *ang)
        prev_end = wrap(hk, ds[n - 1], 25, -295)[-1] if n else S0.E
        pre = [lerp(bt, lerp(prev_end, w[0], 0.5), q)]
        return assemble(S1, hk, ds=ds, form={n: (ang, 1.0, pre)}, tail=[lerp(w[-1], bt, q)]).curve()
    if op.name in ("pull_up", "pull_keep"):
        s = ease((1.2 - hk.tip[1]) / 2.0)
        if op.name == "pull_keep":
            S1 = S0.copy(); S1.keep_s = s; return assemble(S1, hk, keep=op.hx).curve()
        # the caught yarn stays a bight in the throat, its two strands back through the stitch, until the head
        # is out in front; only then does it open into the new loop and slide up the shaft
        S1 = op.E; ds1 = loop_ds(S1, hk); ds0 = loop_ds(S0, hk); q = ease((p - 0.8) / 0.2)
        up = ease(p / 0.25) * (1 - q)                                   # meanwhile the loops already on it stay well up the shaft
        ds0 = [max(d, lerp(d, 8.5 + (n - 1 - i) * SPACING, up)) for i, d in enumerate(ds0)]
        ds = [lerp(ds0[i], ds1[i], q) for i in range(n)] + [lerp(THROAT_D, ds1[-1], q)]
        a0 = contact(hk, BT(op.hx), over_top(BT(op.hx)), True)          # the caught yarn, carried round by the throat
        f = ease((p - 0.72) / 0.28); ang = (lerp(a0[0], 25, f), lerp(a0[1], -295, f))
        return assemble(S1, hk, ds=ds, form={n: (ang, s)}).curve()
    if op.name in ("through", "through2"):
        if p < PULL_SPLIT: return through_loops(op, hk, p / PULL_SPLIT)
        hk0 = op_pose(op, PULL_SPLIT)
        return morph(through_loops(op, hk0, 1.0), post_path(op, hk).curve(), ease((p - PULL_SPLIT) / (1 - PULL_SPLIT)), lag=CLOSE_LAG)
    if op.name == "mr_loop":
        return assemble(op.E, hk).curve()
    raise ValueError(op.name)

def through_loops(op, hk_, qq):
    """the pull-through at progress qq (0..1 of PULL_SPLIT): the loops being pulled through slide up
    to the head, then stay where the fabric holds them while the hook draws back; each passes off over
    the head and closes round the caught yarn, whose two strands run back through it"""
    S0 = op.S; n = len(S0.loops); k = n_through(op); keep = getattr(S0, "keep", None)
    ds = loop_ds(S0, hk_); near = {n - 1 - j: D_B + SPACING * j for j in range(k)}     # spaced up the shaft, nearest the tip first
    if qq <= RIDE or keep is not None:
        f = ease(min(1.0, qq / RIDE))
        for i, d in near.items(): ds[i] = lerp(ds[i], d, f)
        return assemble(S0, hk_, ds=ds, throat=None if keep is not None else "caught", keep=keep).curve()
    hb = op_pose(op, RIDE * PULL_SPLIT)                          # where the loops were let go of
    rings, thread = {}, []
    for i, d in sorted(near.items(), key=lambda t: t[1]):
        c = hb.axis_centre(d); dd = (c - hk_.tip) @ hk_.u
        if dd > 0.25: ds[i] = dd; continue                       # still on the shaft
        cen = hk_.tip + hk_.u * dd                               # off the head: round the caught yarn
        dn, fr = hk_.basis()
        # the ring's open side (between its two ends) turns to face the yarn coming into it (from the fabric for the
        # first loop, from the hole for a pulled-up one), so that yarn doesn't cut across the ring to reach its start
        L_ = S0.loops[i]; src = (HOLE(L_.hole) + v(0.55, -1.4, 0.4)) if L_.kind == "pulled" else S0.E + v(0, -0.6, 1.2)
        w_ = src - cen; phi = math.degrees(math.atan2(w_ @ fr, w_ @ dn)); sh = ((phi - 45.0 + 180.0) % 360.0 - 180.0) * ease(-dd / 3.0) * RING_TURN
        a = np.radians(np.linspace(25, -295, 26) + sh); lift = np.linspace(-0.4, 0.4, 26)[:, None] * R
        ro = lerp(hook_profile(D_B)[1] + 0.92 * R, RING_OFF * R, ease(-dd / 5.0))       # open as it leaves the head, closing round the strands
        rings[i] = list(cen + ro * (np.cos(a)[:, None] * dn + np.sin(a)[:, None] * fr) + lift * hk_.u)
        thread.append(cen)
    return assemble(S0, hk_, ds=ds, throat="caught", rings=rings, thread=thread or None).curve()

def post_path(op, hk):
    """the yarn after a pull-through, marked to match the yarn before it: the first loop on the hook
    becomes the new stitch's V (or stays on the hook, after a 'through 2'), and the caught yarn
    becomes the newest loop"""
    S0, S1 = op.S, op.E; pth = assemble(S1, hk)
    if op.name == "through":
        e = len(S0.prefix) - 1
        pth.marks.update(e=e, a0=e + 1, a1=e + (5 if CHAIN else 6), new=pth.marks["ring0"])
    else:
        pth.marks["new"] = pth.marks["ring%d" % (len(S1.loops) - 1)]
    return pth

BLEND_IN = 0.18
END_CURVES = {}
def op_curve(op, p):
    c = raw_path(op, p)
    i = op.i
    if i > 0 and p < BLEND_IN:                                  # ease in from the last frame of the op before
        if i - 1 not in END_CURVES: END_CURVES[i - 1] = raw_path(OPLIST[i - 1], 1.0)
        c = blend(END_CURVES[i - 1], c, ease(p / BLEND_IN))
    return c

def op_at(ta):
    for op in OPLIST:
        if ta < op.t0 + op.dur: return op, min(1.0, max(0.0, (ta - op.t0) / op.dur) / MOVE_SHARE)
    return OPLIST[-1], 1.0

# ---------------------------------------------------------------- the magic ring's own pieces
MR_TAIL = 16.0
def ring_setup(op, p):
    """warp parameters for the ring at this moment"""
    S0 = op.S
    x0 = S0.x0 if S0.x0 is not None else XS[0]
    if op.name == "through" and op.E.x0 is not None and p > PULL_SPLIT:
        x0 = lerp(x0, op.E.x0, ease((p - PULL_SPLIT) / (1 - PULL_SPLIT)))
    rr = MR_R0 if op.name != "mr_close" else lerp(MR_R0, MR_R1, ease(p))
    WARP["x0"], WARP["r"] = x0, rr
def ring_tail():
    """the tail, from the crossing down and away (world)"""
    cross = warp_pts([v(MR_XS + 2 * math.pi * MR_R0, 0.0, ZR)])[0]
    out = nrm(cross - MR_C) + v(0, 0, -1.2); out = nrm(out)
    extra = 2 * math.pi * (MR_R0 - WARP["r"])
    L = MR_TAIL + extra
    return [cross + out * L + v(0, -0.6, 0), cross + out * (L * 0.5) + v(0, -0.5, 0), cross + out * 1.8 + v(0, -1.2, 0), cross + v(0, -1.0, 0)]

# ---------------------------------------------------------------- frames
def app(c):
    c = np.asarray(c) @ TO_APP.T * (APP_R / R)
    return [[round(float(x), 4) for x in p] for p in c]

def left_skin(off=None):
    """the left hand's skin points (row space), for keeping yarn off it"""
    if not HAND_PTS: return np.zeros((0, 3))
    if off is None: return skin_now()[0]
    return L_POS + off + SKIN_L @ L_ROT.T

def off_left_hand(c, iters=3, fingers=True):
    """the working yarn kept on the left hand's skin, never in it (its way up from the hook to the
    index changes every frame)"""
    if not HAND_PTS: return c
    sk, sn = skin_now()
    m = np.all((c > sk.min(0) - 2) & (c < sk.max(0) + 2), axis=1)
    if not m.any(): return c
    c = c.copy(); q = c[m]
    near = np.all((sk > q.min(0) - 3) & (sk < q.max(0) + 3), axis=1); sk, sn = sk[near], sn[near]
    if HAND_ACTIVE and fingers:                                  # (not on the route round them: it lies between the fingers)
        for _ in range(2): q = off_fingers(q)
    for _ in range(iters):
        d, j = skin_clearance(q, sk, sn); q = q + sn[j] * np.maximum(0.0, 1.06 * R - d)[:, None]
    c[m] = q; return c

# ---------------------------------------------------------------- yarn out of yarn (tools/yarn_relax.py)
# The stitch shapes are drawn tighter than the yarn is thick (a V's loops ~1.9 R apart, the legs through the hole
# under it ~0.9 R apart), and the working yarn's loops pass through the fabric's. The fabric is relaxed once so
# no two stretches of yarn that aren't neighbours along it come closer than 2 R; the finished part of the row
# being worked once per shape against it; and every frame the working yarn against both and itself.
import yarn_relax
_STATIC_RX = []
RING_TURN = float(os.environ.get("RING_TURN", "1"))
RING_OFF = float(os.environ.get("RING_OFF", "1.6")); SIDE_OFF = float(os.environ.get("SIDE_OFF", "0.9"))   # loops off the head close round the caught yarn's two strands
WORK_ITERS = int(os.environ.get("WORK_ITERS", "40"))           # the working yarn's relax, every frame
FABRIC_SELF = os.environ.get("FABRIC_SELF", "0") == "1"   # the fabric gives way to the working yarn and hand, not to itself (its V's touch on purpose)
RELAX_ANCHOR = float(os.environ.get("RELAX_ANCHOR", "0.1"))    # the finished fabric keeps its designed shape (0: relaxed freely, which bent the V's out of shape)
def static_relaxed():
    if not _STATIC_RX and STATIC:
        # held to their designed shape (anchor), giving way only where yarn meets yarn, and kept off the yarn
        # on its way round the left hand, which passes behind the work's left edge; the rows' cut ends there
        # stop short of it
        hy = spline(YARN_HAND); hy = np.vstack([hy] + ([hy + L_RELEASE[2]] if L_RELEASE is not None else []))
        HSAMP = hand_samples()                                   # the hand at work: wherever it and its yarn go
        if HSAMP: hy = np.vstack([hy] + [spline(route_now(h_)) for h_ in HSAMP[::3]])
        # the stitches below spread round the legs pulled through them (the pulled-up loop's, then the new
        # stitch's), as they do: there isn't room between their posts for two strands of yarn otherwise
        legs = [spline(stitch_static(XS[min(i_, len(XS) - 1)], ZT, hs, NB)) for i_, hs in enumerate(HOLES)]
        holes_ = np.array([HOLE(hx) for hs in HOLES for hx in hs])
        for op_ in OPLIST:                                       # wherever the working yarn passes them over the take
            if op_.name not in ("pull_up", "pull_keep", "yo_front", "through", "through2"): continue
            for p_ in np.linspace(0.0, 1.0, 13):
                cv_ = raw_path(op_, p_); q = cv_.c[cv_.own_e + 1:cv_.idx["hand"]]
                near_ = np.linalg.norm(q[:, None] - holes_[None], axis=2).min(1) < 3.5
                if near_.any(): legs.append(q[near_])
        obst = np.vstack([hy] + legs) if not CHAIN else hy
        # and off the left hand's pads, which hold it (the hand was placed against the work as designed)
        sk_ = np.vstack([left_skin(np.zeros(3))] + ([left_skin(L_RELEASE[2])] if L_RELEASE is not None else [])
                        + [skin_now(h_)[0] for h_ in HSAMP[::4]])
        fb = np.vstack([spline(s) for s, _ in STATIC]); sk_ = sk_[np.all((sk_ > fb.min(0) - 3) & (sk_ < fb.max(0) + 3), axis=1)]
        rx = yarn_relax.relax([spline(s) for s, _ in STATIC], fixed=(np.vstack([obst, sk_]), np.concatenate([np.full(len(obst), 2.0 * R), np.full(len(sk_), 1.06 * R)])),
                              R=R, iters=120, anchor=RELAX_ANCHOR, self_pairs=FABRIC_SELF)
        for q in rx:
            n = len(q)
            while n > 10 and np.linalg.norm(hy - q[n - 1], axis=1).min() < 2.1 * R: n -= 1
            _STATIC_RX.append(q[:n])
    return _STATIC_RX if STATIC else []
_PREFIX_RX = {}
_PASSES = []
def working_passes():
    """where the working yarn passes the end of the row being made over the take (not counting its first
    stretch out of the fabric, which is the same yarn going on): the finished stitches give way round it"""
    if not _PASSES and not RING:
        for op_ in OPLIST:
            for p_ in np.linspace(0.0, 1.0, 13):
                cv_ = raw_path(op_, p_); q = cv_.c[cv_.own_e + 25:cv_.idx["hand"]]
                near_ = np.linalg.norm(q - op_.S.E, axis=1) < 4.0
                if near_.any(): _PASSES.append(q[near_])
        _PASSES.append(np.zeros((0, 3)))
    return np.vstack(_PASSES) if _PASSES else np.zeros((0, 3))
def yarn_clear(c, e, h, hk):
    """c (the yarn of the row being worked, then the working yarn) cleared of the fabric and itself: c[:e] is the
    finished fabric (relaxed once, cached), c[e:h] the working yarn up to the hand (relaxed every frame)"""
    c = c.copy(); fab = static_relaxed(); F = np.vstack(fab) if fab else np.zeros((0, 3))
    if e > 2:
        key = (e, round(float(c[:e + 1].sum()), 3))
        if key not in _PREFIX_RX:
            W = working_passes(); Fx = np.vstack([F, W]) if len(W) else F
            _PREFIX_RX[key] = yarn_relax.relax([c[:e + 1]], fixed=Fx, R=R, iters=120, anchor=RELAX_ANCHOR, self_pairs=FABRIC_SELF)[0]
        moved = _PREFIX_RX[key][-1] - c[e]
        c[:e + 1] = _PREFIX_RX[key]
        k = min(len(c) - e - 1, 24)                                # carry the join along, fading
        if k > 0: c[e + 1:e + 1 + k] += moved * np.linspace(1, 0, k + 1)[1:, None]
    if h - e > 2:
        lo, hi = c[e:h].min(0) - 3 * R, c[e:h].max(0) + 3 * R
        Fn = F[np.all((F > lo) & (F < hi), axis=1)] if len(F) else F
        # the hook as obstacles too, so its loops and the yarn caught in it are kept off it and off each other
        # in one go (pushing them onto the hook afterwards put the two sides of the caught yarn back together)
        ds = np.arange(0.0, 40.0, 0.3); prof = [hook_profile(d_) for d_ in ds]
        hax = np.array([hk.tip + hk.u * d_ + hk.t * cx for d_, (cx, _) in zip(ds, prof)])
        hneed = np.array([r_ + 0.9 * R for _, r_ in prof])
        mask = np.zeros(h, bool); mask[e + 1:h - 1] = True
        sk = left_skin(); sk = sk[np.all((sk > lo) & (sk < hi), axis=1)]          # and the left hand
        c[:h] = yarn_relax.relax([c[:h]], movable=[mask], fixed=(np.vstack([Fn, hax, sk]), np.concatenate([np.full(len(Fn), 2.0 * R), hneed, np.full(len(sk), 1.06 * R)])), R=R, iters=WORK_ITERS)[0]
    return c

def frame_strands(ta):
    op, p = op_at(ta); L_OFF[0] = l_off(ta); HAND_NOW.update(hand_state(ta))
    if RING: ring_setup(op, p)
    hk_row = op_pose(op, p)
    cv = op_curve(op, p)
    c = cv.c; hk = warp_hook(hk_row)
    out = [{"visible": True, "closed": False, "radius": APP_R, "accent": False, "shade": sh, "pts": app(q)} for q, (_, sh) in zip(static_relaxed(), STATIC)]
    sp = cv.split
    if RING:
        tail = ring_tail()
        if op.name == "mr_loop":                                 # the ring forms out of a straight run of yarn
            e = ease(p); straight = straight_run(c, tail)
            c = lerp(straight, c, e)
        ts = spline(tail + [c[0]]); c = np.vstack([ts, c[1:]]); sp += len(ts) - 1
    c = push_out(c, hk)
    h = min(len(c), cv.idx["hand"] + (len(ts) - 1 if RING else 0) + 1)    # the route round the fingers is settled already
    if h > sp: c[sp:h] = off_left_hand(c[sp:h])
    off = (len(ts) - 1) if RING else 0
    c = yarn_clear(c, cv.own_e + off if not RING else 0, h, hk)
    if HAND_ACTIVE and h > sp:                                   # (the relax can pull a little of it back into the moving fingers)
        c[sp:h] = off_left_hand(c[sp:h])
    segs = [(c[:sp + 1], False), (c[sp:], True)]
    for s, acc in segs:
        if len(s) < 2: continue
        st = {"visible": True, "closed": False, "radius": APP_R, "accent": acc, "shade": 1.0 if acc else (SHADE_CURRENT if not RING else 1.0), "pts": app(s)}
        if acc:   # for the renderer: the yarn from "hold" on (leaving the work, to the hand and the ball) is held and
                  # fed from the ball; it slides through the loops on the hook ("slide" to "hold")
            st["slide"] = int(max(0, cv.idx["a0"] + off - sp)); st["hold"] = int(max(st["slide"], cv.idx["new"] + off - sp))
        out.append(st)
    WARP["x0"] = None
    return hk, out

def straight_run(c, tail):
    """the ring's yarn before it is looped: the same points laid along a gentle line from the tail's
    top to the yarn's first point past the ring"""
    n_ring = len(spline(FABRIC0))
    a = np.asarray(tail[-1]); b = c[min(len(c) - 1, n_ring + 30)]
    out = c.copy()
    m = min(len(c), n_ring + 30)
    for i in range(m):
        f = i / max(1, m - 1); out[i] = lerp(a, b, f) + v(0, -1.5, 0) * math.sin(math.pi * f)
    return out

# ---------------------------------------------------------------- cameras
FOV = 13.69; DIST = 84 * R * (1 + 0.1 * max(0.0, ZT) / H)
if RING: look = MR_C + v(0, 0, 0.55 * MR_R0)
elif KEY in ("inc", "dec"): look = v(-1.3 * P, 0.0, -0.4 * H)
else: look = v(-0.8 * P, 0.0, -0.4 * H + 0.5 * max(0.0, ZT))
FRONT, SIDE, BACK = v(0.3, -1.0, 0.8), v(-1.0, -0.3, 0.55), v(0.15, 1.0, 0.65)
OVER = v(0.1, -0.5, 1.0)
QUARTER = v(-0.55, -1.0, 0.75)
TOP = v(0.0, -0.22, 1.0)
BEHIND_OVER = v(-0.35, 0.45, 1.0)       # over the top from behind-left: the head out the back, the yarn over it
FRONT_LOW = v(0.3, -1.0, 0.25)          # nearly level: the head pulled up in front shows above the work, against the backdrop
if RING: OVER, TOP = v(0.1, -0.75, 0.75), v(0.05, -0.55, 0.9)   # the ring stands up: look in less steeply
def turn_of(d):
    """the guided view never changes its angle: to show another side the whole work (fabric, yarn, hook, hands)
    turns in front of it. That is the same picture as the camera, with its lights and backdrop, swung by the
    least rotation taking FRONT to d — this one — with its roll swung too (so nothing flips over the top)"""
    a, b = nrm(FRONT), nrm(d); ax = np.cross(a, b); s_, c_ = np.linalg.norm(ax), float(a @ b)
    if s_ < 1e-9: return np.eye(3)
    return _rot(ax, math.atan2(s_, c_))
def cam(d, tgt=None, zoom=1.0, turn=False):
    tgt = look if tgt is None else tgt
    c = {"pos": app([tgt + nrm(d) * DIST * zoom])[0], "target": app([tgt])[0], "fov": FOV, "aspect": 1.6}
    if turn: c["turn"] = [round(float(x), 6) for x in mat_to_quat(TO_APP @ turn_of(d) @ TO_APP.T)]
    return c

# ---------------------------------------------------------------- the guided take
# Shots per op: (seconds, op progress from, to, camera to, zoom to, callout or None). Callouts
# (kind, text) show at the end of their shot, like choreo_sc.py.
WORDS = {2: "2", 3: "3", 4: "4"}
SHOTS = []           # (dur, action from, action to, cam dir, zoom (z0, z1), cue (kind, step, text) or None)
def shot(dur, a0, a1, cdir, zoom, cue=None):
    z0 = SHOTS[-1][4][1] if SHOTS else zoom
    c0 = SHOTS[-1][3] if SHOTS else cdir
    SHOTS.append((dur, a0, a1, cdir, (z0, zoom), cue, c0))

def act(op, f): return op.t0 + op.dur * MOVE_SHARE * f if f <= 1.0 else op.t0 + op.dur
END_TEXT = {
    "sc": "Your new stitch — sitting on top of stitch 2",
    "sl": "A slip stitch — it lies flat and adds almost no height",
    "hdc": "Your half double crochet — taller than a single, with a bar at the back",
    "dc": "Your double crochet — a tall post on stitch 2",
    "tr": "Your treble — the tallest post, wrapped twice",
    "inc": "Two stitches in one — that's an increase",
    "dec": "Two stitches joined at the top — that's a decrease",
    "ch": "A new chain — the loop on your hook starts the next one",
    "mr": "Pull the tail — the ring closes into a tight circle",
}
# the guided view keeps one angle (the user: "keep the camera angle the same, and only rotate the hands/
# piece if trying to show a different angle"): every shot looks from FRONT but the turn to show the back
QUARTER = OVER = TOP = FRONT
def build_shots():
    first = OPLIST[0]; t_start = 0.0
    shot(1.6, t_start, t_start, FRONT, 2.6)
    if CHAIN:
        shot(1.4, 0.0, 0.0, FRONT, 1.0, ("link", None, "This loop on your hook makes the next chain"))
    elif RING:
        shot(1.0, 0.0, 0.0, FRONT, 1.3)
    elif first.name == "insert":
        shot(1.4, 0.0, 0.0, FRONT, 1.0, ("stitch", 0, "Go into stitch 2 — under both top loops"))
    else:
        shot(1.0, 0.0, 0.0, FRONT, 1.0)
    n_yo_free = 0; n_ins = 0; n_thr = 0
    for i, op in enumerate(OPLIST):
        S0, S1 = op.S, op.E; si = op.step; nm = op.name
        fast = (KEY == "inc" and S0.stitch == 1) or (RING and S0.stitch >= 2)
        if RING and S0.stitch >= 2 and nm != "mr_close":          # the rest of the ring's stitches: brisk, no stops
            span = {"insert": 0.4, "yo_catch": 0.25, "pull_up": 0.3, "yo_front": 0.25, "through": 0.4}[nm]
            shot(span, act(op, 0), act(op, 1.01), FRONT, 1.25)
            continue
        quiet = fast or (RING and S0.stitch == 1)                 # the ring's first sc: same moves as the ch, fewer stops
        k = 0.72 if quiet else 1.0
        if RING: k = {0: 0.85, 1: 0.6}.get(S0.stitch, k)
        if nm == "mr_loop":
            shot(3.2, act(op, 0), act(op, 1), FRONT, 1.0, ("ring", si, "Loop the yarn into a ring — the tail crosses behind"))
        elif nm == "yo_free":
            n_yo_free += 1
            txt = "Wrap the yarn over your hook first — back to front" if n_yo_free == 1 else "And once more — %d loops on your hook" % len(S1.loops)
            if n_yo_free == 1 and len([o for o in OPLIST if o.name == "yo_free"]) == 1: txt = "Wrap the yarn over your hook first — back to front"
            shot(3.0, act(op, 0), act(op, 1), QUARTER, 0.8, ("loops", si, txt))
            if OPLIST[i + 1].name == "insert":
                shot(1.6, act(op, 1), act(op, 1), FRONT, 1.0, ("stitch", OPLIST[i + 1].step, "Now go into stitch 2 — under both top loops"))
        elif nm == "insert":
            n_ins += 1
            if KEY == "dec" and n_ins == 2:
                shot(1.2, act(op, 0), act(op, 0), FRONT, 1.0, ("stitch", si, "Leave it on the hook and go into stitch 2"))
            if KEY == "inc" and n_ins == 2:
                shot(1.0, act(op, 0), act(op, 0), FRONT, 1.0, ("stitch", si, "Back into the same stitch"))
            if RING and n_ins == 1:
                shot(1.0, act(op, 0), act(op, 0), FRONT, 1.0, ("stitch", si, "Go into the middle of the ring"))
            if RING and n_ins == 2:
                shot(0.9, act(op, 0), act(op, 0), FRONT, 1.0, ("stitch", si, "Now a single crochet — into the ring again"))
            shot(2.0 * k, act(op, 0), act(op, 1), FRONT, 1.0)
            tip_txt = "The hook pokes out the back" if not RING else "The hook goes through the ring and out the back"
            if RING: shot(1.6 * k, act(op, 1), act(op, 1.01), OVER, 1.0, ("tip", si, tip_txt) if not quiet else None)
            else:
                shot(0.8 * k, act(op, 1), act(op, 1), BEHIND_OVER, 1.0)  # the work turns to show its back (turn_of);
                shot(0.8 * k, act(op, 1), act(op, 1.01), BEHIND_OVER, 1.0, ("tip", si, tip_txt) if not quiet else None)   # same 1.6 s: the cues keep their times
        elif nm == "yo_catch":
            shot(2.8 * k, act(op, 0), act(op, 1), TOP if RING else BEHIND_OVER, 0.72, ("throat", si, "Wrap the yarn over your hook — back to front") if not quiet else None)
        elif nm in ("pull_up", "pull_keep"):
            if nm == "pull_keep":
                shot(2.0, act(op, 0), act(op, 1), QUARTER, 1.0)
            else:
                m = len(S1.loops)
                txt = "Pull it back through — %s loops on your hook" % WORDS.get(m, m) if m > 1 else "Pull up a loop — it's the only one on your hook"
                if OPLIST[i - 1].name == "yo_catch" and not RING:      # coming back round from behind the work
                    shot(0.8 * k, act(op, 0), act(op, 0.15), FRONT_LOW, 1.0)  # and turns back, on round to nearly level for the pull (same 2.6 s in all)
                    shot(1.8 * k, act(op, 0.15), act(op, 1), FRONT_LOW, 1.0, ("loops", si, txt) if not quiet else None)
                else: shot(2.6 * k, act(op, 0), act(op, 1), QUARTER, 1.0, ("loops", si, txt) if not quiet else None)
        elif nm == "yo_front":
            again = any(o.name in ("yo_catch", "yo_front", "yo_free") for o in OPLIST[:i])
            txt = "Wrap the yarn over again — back to front" if again else "Wrap the yarn over your hook — back to front"
            if CHAIN: txt = "Wrap the yarn over your hook — back to front"
            shot((2.6 if n_thr else 3.0) * k, act(op, 0), act(op, 1), QUARTER, 0.75, ("throat", si, txt) if not quiet or KEY == "inc" else None)
        elif nm == "through2":
            n_thr += 1; m = len(S1.loops)
            shot(2.6, act(op, 0), act(op, 1.01), QUARTER, 0.95, ("loops", si, "Pull through 2 — %s loops left on your hook" % WORDS.get(m, m)))
        elif nm == "through":
            n = len(S0.loops)
            if CHAIN: txt = "Pull it through the loop on your hook"
            elif getattr(S0, "keep", None) is not None: txt = "Pull through the stitch and the loop — in one go"
            elif RING and S0.stitch == 0: txt = "Pull through — that's the chain 1"
            elif n == 2: txt = "Pull through both loops"
            else: txt = "Pull through all %d loops" % n
            last = i == len(OPLIST) - 1 or OPLIST[i + 1].name in ("hold", "mr_close")
            if KEY == "inc" and S0.stitch == 0: txt = "That's one — stay in the same stitch"
            if RING and S0.stitch == 1: txt = "Pull through both — now 5 more the same way"
            shot(2.8 * k, act(op, 0), act(op, 1.01), FRONT, 1.0, ("done", si, txt) if (not fast or KEY == "inc") or (RING and S0.stitch == 1) else None)
        elif nm == "hold":
            pass
        elif nm == "mr_close":
            shot(3.4, act(op, 0), act(op, 1), FRONT, 1.0)
    end = TOTAL_ACT
    shot(1.8, end, end, FRONT, 1.0 if not RING else 1.0, ("new", None, END_TEXT[KEY]))
    shot(0.6, end, end, FRONT, 1.0)
build_shots()

def _at_shots(tv):
    """(action time, camera dir, zoom) at video time tv as the shots lay them out: the camera eases from shot
    to shot over each whole shot (the held camera below keeps the action and replaces the camera)"""
    t0 = 0.0
    for i, (dur, a0, a1, c1, (z0, z1), cue, c0) in enumerate(SHOTS):
        if tv <= t0 + dur or i == len(SHOTS) - 1:
            qa = min(1.0, max(0.0, (tv - t0) / dur))
            return lerp(a0, a1, qa), slerp_dir(c0, c1, ease(qa)), lerp(z0, z1, ease(qa))
        t0 += dur
total = sum(s[0] for s in SHOTS)
n = int(round(total * A.fps)) + 1

def hook_world(ta):
    op, p = op_at(ta)
    if RING: ring_setup(op, p)
    hk = warp_hook(op_pose(op, p)); WARP["x0"] = None; return hk
def action_focus(ta):
    hk = hook_world(ta); return lerp(look, hk.at(2.0), 0.5)
def _target_free(tv):
    ts = np.linspace(tv - 0.5, tv + 0.5, 9)
    return np.mean([action_focus(_at_shots(min(max(0.0, x), total))[0]) for x in ts], axis=0)

# ---------------------------------------------------------------- the held camera
# The camera never moves during an action: every frame it moved (a slow dolly, the target following the hook)
# rescaled the yarn's sub-pixel fibres and they shimmered (flicker study: 63% less with the camera still). Shots
# next to each other seen from the same side are one framing (their zooms averaged); between framings the camera
# (its distance, target, and the work's turn) eases over CAM_T s, placed in the stillest stretch of the hook near
# the change and never over a callout. CAM_HOLD=0: the camera as the shots lay it out.
CAM_HOLD = os.environ.get("CAM_HOLD", "1") == "1"
CAM_T = float(os.environ.get("CAM_T", "0.4"))              # s, a change of distance / target (a turn: up to +0.2 s)
CAM_MERGE = float(os.environ.get("CAM_MERGE", "0.4"))      # zooms within this ratio of each other, same side: one framing
CAM_MARGIN = float(os.environ.get("CAM_MARGIN", "0.12"))    # the hook's head stays this far (frame fraction) in from the edges
def _ang(a, b): return math.degrees(math.acos(max(-1.0, min(1.0, float(nrm(a) @ nrm(b))))))
def build_track():
    fr, t0 = [], 0.0                                              # framings: [start, end, dir, zoom]
    for dur, a0, a1, c1, (z0, z1), cue, c0 in SHOTS:
        if fr and _ang(fr[-1][2], c1) < 1.0 and max(fr[-1][3], z1) / min(fr[-1][3], z1) <= 1 + CAM_MERGE:
            w0 = fr[-1][1] - fr[-1][0]; fr[-1][3] = (fr[-1][3] * w0 + z1 * dur) / (w0 + dur); fr[-1][1] = t0 + dur
        else: fr.append([t0, t0 + dur, nrm(c1), z1])
        t0 += dur
    dt = 1.0 / A.fps; ts = np.arange(0.0, total + dt, dt)
    tips = np.array([hook_world(_at_shots(t)[0]).tip for t in ts]); speed = np.r_[0.0, np.linalg.norm(np.diff(tips, axis=0), axis=1)]
    tgts = []
    for f_ in fr:                                                 # aim between the extremes of the action, then back
        smp = np.arange(f_[0], f_[1], 0.1)                        # off until the hook's head keeps CAM_MARGIN of the frame
        foc = np.array([action_focus(_at_shots(t)[0]) for t in smp]); tg = (foc.min(0) + foc.max(0)) / 2
        hks = [hook_world(_at_shots(t)[0]) for t in smp]; pts = [h_.tip for h_ in hks] + [h_.at(2.5) for h_ in hks]
        for _ in range(12):
            eye = tg + f_[2] * DIST * f_[3]; fw = nrm(tg - eye); Rt = turn_of(f_[2])
            f0 = -nrm(FRONT); r0 = nrm(np.cross(f0, v(0, 0, 1))); rr, uu = Rt @ r0, Rt @ np.cross(r0, f0)
            th = math.tan(math.radians(FOV) / 2)
            m = min(min(0.5 - abs((q - eye) @ rr / ((q - eye) @ fw) / th / 1.6 / 2), 0.5 - abs((q - eye) @ uu / ((q - eye) @ fw) / th / 2)) for q in pts)
            if m >= CAM_MARGIN: break
            f_[3] *= 1.06
        tgts.append(tg)
    cue_ts, t0 = [], 0.0
    for dur, *_, cue, _c0 in SHOTS:
        t0 += dur
        if cue: cue_ts.append(t0 - 0.5 / A.fps)
    moves = []                                                    # (start, length, framing before)
    for k in range(len(fr) - 1):
        tb = fr[k][1]; T = CAM_T + 0.2 * min(1.0, _ang(fr[k][2], fr[k + 1][2]) / 90.0)
        lo, hi = max(fr[k][0] + 0.1, tb - T - 0.7), min(fr[k + 1][1] - T - 0.1, tb + 0.7)
        best = None
        for s0 in np.arange(lo, hi + 1e-9, dt):
            if any(s0 - 2 * dt <= c <= s0 + T + 2 * dt for c in cue_ts): continue
            if moves and s0 < moves[-1][0] + moves[-1][1] + 0.1: continue
            i0, i1 = int(round(s0 / dt)), int(round((s0 + T) / dt))
            cost = speed[i0:i1 + 1].sum() + 0.02 * abs(s0 + T / 2 - tb)    # still hook first, then near the change
            if best is None or cost < best[0]: best = (cost, s0)
        moves.append((best[1] if best else max(tb - T / 2, moves[-1][0] + moves[-1][1] if moves else 0.0), T, k))
    return fr, tgts, moves
if CAM_HOLD: TRACK = build_track()
def _cam_at(tv):
    fr, tgts, moves = TRACK
    for s0, T, k in moves:
        if s0 <= tv <= s0 + T:
            e = ease((tv - s0) / T)
            return slerp_dir(fr[k][2], fr[k + 1][2], e), lerp(fr[k][3], fr[k + 1][3], e), lerp(tgts[k], tgts[k + 1], e)
    k = sum(1 for s0, T, _ in moves if tv > s0 + T)               # framings fully moved into
    return fr[k][2], fr[k][3], tgts[k]
def at_video(tv):
    ta, cdir, zoom = _at_shots(tv)
    if not CAM_HOLD: return ta, cdir, zoom
    cdir, zoom, _ = _cam_at(tv); return ta, cdir, zoom
def guided_target(tv):
    return _cam_at(tv)[2] if CAM_HOLD else _target_free(tv)

RIGHT_RIG = hand_rig.skeleton(hand_rig.RIGHT_GRIP, "R")
D_GRIP = 22.0 * R                     # the fingertips hold the shaft this far up from the tip
WRIST_SHARE = 0.4
GRIP_ROLL = float(os.environ.get("GRIP_ROLL", "-1.0"))    # the hand turned about the shaft (radians): the thumb on the rest, facing the viewer
def right_hand(hk):
    """tripod (pencil) grip: the shaft runs between the thumb pad and the index and middle
    fingertips and back through the web between thumb and index; turns with the hook (the wrist)"""
    pt = lambda k: local_pt(RIGHT_RIG, k, side="R")
    if not HAND_PTS:
        rot = frame_from(-hk.u, -hk.t * math.cos(0.5) + hk.z * math.sin(0.5))
        q = (pt("index_pip") + pt("index_dip")) / 2 - np.array([0, 0, 0.009 * HAND_SCALE / UNIT + RH])
        return hk.at(28.0 * R) - rot @ q, rot
    if GRIP is None:
        grip = (pt("thumb_tip") + pt("index_dip") + pt("middle_dip")) / 3
        web = (pt("thumb_knuckle") + pt("index_knuckle")) / 2
        rot = _rot_onto(web - grip, v(0, 0, 1), hk.u, -hk.t * math.cos(0.5) + hk.z * math.sin(0.5))
        return hk.at(D_GRIP) - rot @ grip, rot
    o, d = GRIP                                   # the shaft's own line through the hand (grip_fit.py)
    hw = rolled(hk.tip, hk.u, WRIST_SHARE * hk.roll)   # the wrist turns part of the hook's roll; the fingers roll the shaft the rest
    rot = _rot_onto(d, v(0, 0, 1), hk.u, -hw.t * math.cos(GRIP_ROLL) + hw.z * math.sin(GRIP_ROLL))
    return hk.at(D_GRIP) - rot @ o, rot
def load_grip():
    """the shaft's line in the right hand, fitted once per hands bake (cached beside hands.json)"""
    if not HAND_PTS or "_verts" not in HAND_PTS["R"]: return None
    cp = os.path.join(os.path.dirname(_HJ), "grip.json"); stamp = os.path.getmtime(_HJ)
    if os.path.exists(cp):
        c = json.load(open(cp))
        if c.get("stamp") == stamp and c.get("r") == RH: return np.array(c["o"]), np.array(c["d"])
    import grip_fit
    Pj = {k: np.array(x) * HAND_SCALE / UNIT for k, x in HAND_PTS["R"].items() if not k.startswith("_")}
    o, d, gaps = grip_fit.fit(Pj, np.array(HAND_PTS["R"]["_verts"]) * HAND_SCALE / UNIT, RH)
    print("right hand on the shaft, gaps (yarn radii):", gaps, file=sys.stderr)
    json.dump({"stamp": stamp, "r": RH, "o": list(o), "d": list(d), "gaps": gaps}, open(cp, "w"))
    return o, d
GRIP = load_grip()

FIXED = [("Front", FRONT), ("Side", SIDE), ("Behind", BACK)]
cache = {}; frames = []
for i in range(min(n, A.max_frames) if A.max_frames else n):
    tv = i / A.fps
    ta, cdir, zoom = at_video(tv); key = round(ta, 4)
    if key not in cache: cache[key] = frame_strands(ta)
    hk, strands = cache[key]
    rpos, rrot = right_hand(hk)
    L_OFF[0] = l_off(ta); lhs = hand_state(ta); lrot, lpos = hand_xform(lhs)
    hands = [{"side": "R", "pose": "RIGHT_GRIP", "scale": HAND_SCALE, "pos": [round(float(x) * UNIT, 5) for x in rpos], "rot": [round(float(x), 5) for x in rrot.ravel()]},
             {"side": "L", "pose": "LEFT_HOLD", "obj": "Hand" + L_VARIANT, "scale": HAND_SCALE, "pos": [round(float(x) * UNIT, 5) for x in lpos], "rot": [round(float(x), 5) for x in lrot.ravel()], "mix": lhs["mix"]}]
    frames.append({"t": round(tv, 4), "a": key, "cam": cam(cdir, guided_target(tv), zoom, turn=True), "hands": hands if A.hands else None,
                   "hook": {"pos": app([hk.tip])[0], "quat": [round(q, 6) for q in hk.quat_app()]}, "strands": strands})

# ---------------------------------------------------------------- callouts
def project(d, tgt, pts, zoom=1.0, turn=False):
    eye = tgt + nrm(d) * DIST * zoom; f = nrm(tgt - eye); r = nrm(np.cross(f, v(0, 0, 1))); u = np.cross(r, f)
    if turn:                                                      # the guided view: FRONT's frame, turned (turn_of)
        Rt = turn_of(d); f0 = -nrm(FRONT); r0 = nrm(np.cross(f0, v(0, 0, 1))); r, u = Rt @ r0, Rt @ np.cross(r0, f0)
    th = math.tan(math.radians(FOV) / 2); out = []
    for p in pts:
        q = p - eye; z = q @ f
        out.append([round(0.5 + (q @ r) / z / th / 1.6 / 2, 4), round(0.5 - (q @ u) / z / th / 2, 4)])
    return out, DIST * zoom * th
def V_of(x, z=-H): return list(spline(stitch_static(x, z, [x])[:6], 0.4 * R))
def cue_target(kind, ta):
    """(centre, radius, trace, arrow) in world space"""
    op, p = op_at(ta)
    if RING: ring_setup(op, p)
    hk_r = op_pose(op, p); hk = warp_hook(hk_r); S0 = op.S
    W = lambda pts: list(warp_pts(pts)) if pts is not None else None
    nxt = next((o for o in OPLIST[OPLIST.index(op):] if o.name == "insert"), op)
    hx = nxt.hx if nxt.hx is not None else X1
    res = None
    if kind == "link":
        d = loop_ds(S0, hk_r)[0] if S0.loops else D_B; res = (hk.at(d), 2.4, None, None)
    elif kind == "stitch":
        path = [op_pose(nxt, k / 11).tip for k in range(12)]
        trace = None if RING else V_of(hx)
        res = (W([HOLE(hx) + v(0, 0, 0.9)])[0], 3.0, W(trace), W(path[4:]))
    elif kind == "tip": res = (hk.at(1.0), 2.2, None if RING else W(V_of(hx)), None)
    elif kind == "throat":
        dn, fr = hk.basis(); c = hk.axis_centre(THROAT_D); rr = hook_profile(THROAT_D)[1] + 2.6 * R
        arc = [c + rr * (math.cos(a) * dn + math.sin(a) * fr) for a in np.radians(np.linspace(265, -20, 14))]
        res = (c, 2.4, wrap(hk, THROAT_D, 250, -50), arc)
    elif kind == "loops":
        St = op.E if p >= 1.0 else S0; ds = loop_ds(St, hk_r) if St.loops else [D_B]
        lo, hi = min(ds + [THROAT_D]), max(ds); res = (hk.at((lo + hi) / 2), (hi - lo) / 2 + 2.4, None, None)
    elif kind == "done":
        ds = loop_ds(op.E, hk_r); res = (hk.at(ds[-1]), 2.4, None, None)
    elif kind == "ring":
        res = (W([v(MR_XS - 1.5 * P, 0, ZR)])[0] * 0 + MR_C, MR_R0 + 1.5, None, None)
    elif kind == "new":
        if RING:
            res = (MR_C + v(0, 0, 0.5 * WARP["r"]), WARP["r"] + 4.5, None, None)
        else:
            xs = XS[:op.E.stitch] if op.E.stitch else XS[:1]
            tr = []
            for x in xs: tr += V_of(x, ZT)
            cx = float(np.mean(xs)); res = (v(cx, -0.6, ZT + 0.2), 3.0 + 1.5 * (len(xs) - 1), tr if len(xs) == 1 else V_of(xs[0], ZT) + V_of(xs[-1], ZT), None)
    WARP["x0"] = None
    return res
cues, t0, timeline = [], 0.0, [[0.0, 0.0]]
for dur, a0, a1, c1, zz, cue, c0 in SHOTS:
    t0 += dur; timeline.append([round(t0, 3), round(a1, 3)])
    if not cue: continue
    tc = t0 - 0.5 / A.fps; ta, cdir, zoom = at_video(tc); c, rad, trace, arrow = cue_target(cue[0], ta)
    views = []
    for d, tgt, z, tu in [(cdir, guided_target(tc), zoom, True)] + [(d, look, 1.0, False) for _, d in FIXED]:
        (xy,), half = project(d, tgt, [c], z, tu)
        views.append({"x": xy[0], "y": xy[1], "r": round(rad / half / 2, 4),
                      "trace": project(d, tgt, trace, z, tu)[0] if trace is not None else None,
                      "arrow": project(d, tgt, arrow, z, tu)[0] if arrow else None,
                      "link": None})
    cues.append({"t": round(tc, 3), "step": cue[1], "text": cue[2], "views": views})

# stitch numbers on the row being worked into (not for the chain or the ring)
labels = None
if not CHAIN and not RING:
    if KEY == "dec": LXS, LT, LTXT = [0.0, -P, -2 * P, -3 * P], 1, ["", "1", "2", ""]
    else: LXS, LT, LTXT = [0.0, -P, -2 * P, -3 * P], 1, ["1", "2", "3", "4"]
    LPTS = [v(x, 0.0, -H - 1.3) for x in LXS]
    tips = [c["t"] for c in cues if c["text"].startswith("The hook pokes")]
    label_until = (tips[-1] if tips else 3.0) + 0.2
    track = []
    for tv in np.arange(0.0, label_until + 0.1, 0.1):
        ta, cdir, zoom = at_video(tv)
        track.append([round(float(tv), 2)] + [c for xy in project(cdir, guided_target(tv), LPTS, zoom, True)[0] for c in xy])
    keep = [i for i, t in enumerate(LTXT) if t]
    labels = {"until": round(label_until, 2), "target": keep.index(LT),
              "stitches": [{"text": LTXT[i]} for i in keep],
              "track": [[r[0]] + [r[1 + 2 * i + k] for i in keep for k in (0, 1)] for r in track],
              "fixed": [[c for i, xy in enumerate(project(d, look, LPTS)[0]) if i in keep for c in xy] for _, d in FIXED]}

if A.cues:
    out = {"key": KEY, "hold": 2.4, "steps": len(STEPS), "stepDur": STEP_DUR, "timeline": timeline, "cues": cues}
    if labels: out["labels"] = labels
    json.dump(out, open(A.cues, "w"), indent=1)
    print("wrote", A.cues, len(cues), "callouts")

json.dump({"key": KEY, "fps": A.fps, "stepDur": STEP_DUR, "steps": STEPS, "total": total,
           "yarn": TUTORIAL_FABRIC, "accent": TUTORIAL_WORKING, "type": "wool",
           "camera": cam(FRONT), "views": [dict(cam(FRONT), name="Guided", moving=True, hands=A.hands)] + [dict(cam(d), name=nm) for nm, d in FIXED],
           "ball": None, "ground": -40, "hookMesh": hook_mesh(), "frames": frames}, open(A.out, "w"))
print("wrote", A.out, n, "frames, %.1f s, %d poses" % (total, len(cache)))
