"""A posable hand skeleton, life size (metres), shared by the choreography (to know
where the fingers are — e.g. the left index finger the working yarn runs over) and
by render_tutorial.py (which skins it into a smooth hand each frame: Blender's Skin
modifier + Subdivision Surface).

Hand frame: wrist at the origin, fingers along +Y, back of the hand +Z, thumb on +X
for a right hand (side="L" mirrors X). Curls bend a finger toward the palm (-Z).

Pure Python (no bpy), so it can be imported anywhere.
"""
import math

# finger: knuckle x, knuckle y, phalanx lengths, joint radii (knuckle, pip, dip, tip)
FINGERS = {
    "index":  (0.028, 0.093, (0.043, 0.025, 0.020), (0.0122, 0.0110, 0.0099, 0.0086)),
    "middle": (0.009, 0.096, (0.047, 0.028, 0.021), (0.0125, 0.0113, 0.0101, 0.0088)),
    "ring":   (-0.010, 0.093, (0.044, 0.026, 0.020), (0.0118, 0.0106, 0.0095, 0.0082)),
    "pinky":  (-0.027, 0.086, (0.034, 0.020, 0.017), (0.0104, 0.0095, 0.0085, 0.0073)),
}
REST = {"index": (8, 12, 8), "middle": (10, 14, 10), "ring": (12, 16, 10), "pinky": (14, 18, 12),
        "spread": {"index": 4, "middle": 0, "ring": -4, "pinky": -9},
        "thumb": (40, 20, 10, 10)}       # (swing toward the palm, lift off it, mcp curl, ip curl)

def _add(v, a, s=1.0): return (v[0] + a[0] * s, v[1] + a[1] * s, v[2] + a[2] * s)
def _rot_x(p, a):
    c, s = math.cos(a), math.sin(a); return (p[0], p[1] * c - p[2] * s, p[1] * s + p[2] * c)

def skeleton(pose=None, side="R"):
    """-> (verts, edges, radii, roots, named points)"""
    P = dict(REST); P.update(pose or {})
    spread = dict(REST["spread"]); spread.update((pose or {}).get("spread", {}))
    V, E, Rd, Ro, named = [], [], [], [], {}
    def add(p, r, parent=None, root=False, name=None):
        i = len(V); V.append(p); Rd.append(r); Ro.append(root)
        if parent is not None: E.append((parent, i))
        if name: named[name] = p
        return i
    arm = add((0.0, -0.09, -0.004), 0.029, root=True, name="forearm")  # leaves the frame, so no stump shows
    wrist = add((0.0, 0.0, 0.0), 0.025, arm, name="wrist")
    heel = add((0.0, 0.03, -0.003), 0.029, wrist)                        # heel of the palm
    palm = add((0.003, 0.06, 0.0), 0.031, heel, name="palm")
    # knuckles linked in a row (a chain skins cleanly; a star of branches creases)
    kid = {}
    for f in ("middle", "index", "ring", "pinky"):
        kx, ky, lens, rads = FINGERS[f]
        parent = palm if f == "middle" else kid["middle" if f in ("index", "ring") else "ring"]
        kid[f] = add((kx, ky - 0.008, 0.0), rads[0] * 1.55, parent)
    for f, (kx, ky, lens, rads) in FINGERS.items():
        k = add((kx, ky, 0.002), rads[0], kid[f], name=f + "_knuckle")
        sp = math.radians(spread[f]); curls = P[f]
        p, prev, cum = V[k], k, 0.0
        for j in range(3):
            cum += math.radians(curls[j])
            d = (math.sin(sp) * math.cos(cum), math.cos(sp) * math.cos(cum), -math.sin(cum))
            p = _add(p, d, lens[j])
            prev = add(p, rads[j + 1], prev, name=f + ("_pip", "_dip", "_tip")[j])
    # thumb: from the base of the palm on the radial side, swinging across the palm
    sw, lift, c1, c2 = (math.radians(a) for a in P["thumb"])
    base = add((0.021, 0.022, -0.010), 0.017, heel, name="thumb_base")
    d0 = (math.cos(sw) * 0.75, 0.62, -0.25 - math.sin(sw) * 0.45)      # metacarpal direction
    n = math.sqrt(sum(x * x for x in d0)); d0 = tuple(x / n for x in d0)
    d0 = _rot_x(d0, -lift)
    p = _add(V[base], d0, 0.042); mcp = add(p, 0.0118, base, name="thumb_mcp")
    def bend(d, a):            # curl the thumb toward the palm centre
        to = (-0.6, 0.5, -0.6); n = math.sqrt(sum(x * x for x in to)); to = tuple(x / n for x in to)
        b = tuple(d[i] * math.cos(a) + to[i] * math.sin(a) for i in range(3)); n = math.sqrt(sum(x * x for x in b))
        return tuple(x / n for x in b)
    d1 = bend(d0, c1); p = _add(p, d1, 0.032); ip = add(p, 0.0104, mcp, name="thumb_ip")
    d2 = bend(d1, c2); p = _add(p, d2, 0.026); add(p, 0.0088, ip, name="thumb_tip")
    if side == "L":
        V = [(-x, y, z) for x, y, z in V]; named = {k: (-x, y, z) for k, (x, y, z) in named.items()}
    return V, E, Rd, Ro, named

# poses for crochet
RIGHT_GRIP = {   # pencil grip: index along the shaft, middle under it, ring and pinky tucked
    "index": (18, 22, 14), "middle": (42, 58, 30), "ring": (62, 78, 40), "pinky": (70, 80, 40),
    "spread": {"index": 2, "middle": -2, "ring": -6, "pinky": -10},
    "thumb": (55, 10, 18, 22)}
LEFT_HOLD = {    # holding the work: index raised to carry the yarn, middle and thumb pinch below
    "index": (-12, 18, 12), "middle": (38, 50, 26), "ring": (55, 68, 34), "pinky": (62, 72, 34),
    "spread": {"index": 10, "middle": 0, "ring": -5, "pinky": -11},
    "thumb": (62, 6, 14, 14)}
