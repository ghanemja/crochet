# How the yarn and the hands touch: for one frame of a paths file, the signed clearance between
# every strand (and the hook) and each hand's skin, and where along the hand it is worst.
#
#   blender -b -P tools/hand_contact.py -- build/paths/sc.json [frame] [--json out.json]
#
# Clearance = distance from the yarn's centre line to the skin minus the yarn radius: < 0 means the
# yarn is inside the finger. The point is reported with the nearest named joint (hands.json).
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
OUTJ = None
if "--json" in argv: i = argv.index("--json"); OUTJ = argv[i + 1]; del argv[i:i + 2]
D = json.load(open(argv[0])); FA = (argv[1] if len(argv) > 1 else "0").split(":")
FRAMES = range(int(FA[0]), int(FA[1]) + 1 if len(FA) > 1 else int(FA[0]) + 1, int(FA[2]) if len(FA) > 2 else 1)
HERE = os.path.dirname(os.path.abspath(__file__))
HB = os.path.join(HERE, "..", "build", "hands", "hands.blend")
PTS = json.load(open(os.path.join(HERE, "..", "build", "hands", "hands.json")))
S = 0.01
def to_bl_np(a): a = np.asarray(a, float); return np.stack([a[:, 0], -a[:, 2], a[:, 1]], 1) * S

for o in list(bpy.data.objects): bpy.data.objects.remove(o)
with bpy.data.libraries.load(HB) as (src, dst): dst.objects = ["HandR", "HandL"]
for o in dst.objects: bpy.context.scene.collection.objects.link(o); o.modifiers["Sub"].levels = 2
def check(fr):
    dg = bpy.context.evaluated_depsgraph_get()
    hands = {}
    for h in fr["hands"] or []:
        ob = bpy.data.objects["Hand" + h["side"]]; r = h["rot"]; p = h["pos"]
        M = Matrix(((r[0], r[1], r[2], p[0]), (r[3], r[4], r[5], p[1]), (r[6], r[7], r[8], p[2]), (0, 0, 0, 1))) @ Matrix.Scale(h["scale"], 4)
        me = ob.evaluated_get(dg).to_mesh()
        vs = [M @ v.co for v in me.vertices]; fs = [tuple(pl.vertices) for pl in me.polygons]
        joints = {k: M @ Vector(x) for k, x in PTS[h["side"]].items() if not k.startswith("_") and not k.endswith("_n")}
        hands[h["side"]] = (BVHTree.FromPolygons(vs, fs), joints)

    def resample(c, step):
        seg = np.linalg.norm(np.diff(c, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)])
        n = max(2, int(s[-1] / step) + 1); si = np.linspace(0, s[-1], n)
        return np.stack([np.interp(si, s, c[:, k]) for k in range(3)], 1)

    def clearance(tree, p):
        loc, nor, idx, d = tree.find_nearest(Vector(p))
        if loc is None: return 1e9, None
        sgn = 1.0 if (Vector(p) - loc).dot(nor) >= 0 else -1.0
        return sgn * d, loc

    report = {}
    yr = None
    for si, st in enumerate(fr["strands"]):
        if not st.get("visible"): continue
        c = resample(to_bl_np(st["pts"]), 0.0005); yr = st["radius"] * S
        name = "working" if st.get("accent") else ("fabric%d" % si)
        for side, (tree, joints) in hands.items():
            cl = []
            for p in c:
                d, loc = clearance(tree, p)
                if d < 0.02: cl.append((d - yr, p))
            if not cl: continue
            worst = min(cl, key=lambda x: x[0])
            bad = [x for x in cl if x[0] < -0.0005]
            near = min(joints, key=lambda k: (joints[k] - Vector(worst[1])).length)
            key = "%s/%s" % (name, side)
            report[key] = {"min_mm": round(worst[0] * 1000, 2), "inside_pts": len(bad), "near": near,
                           "touch_pts": len([x for x in cl if abs(x[0]) < 0.0008])}
            bj = {}
            for d, p in bad:
                j = min(joints, key=lambda k: (joints[k] - Vector(p)).length); bj[j] = min(bj.get(j, 0), round(d * 1000, 1))
            report[key]["inside_by_joint"] = bj
            if os.environ.get("VERBOSE"):
                for d, p in bad[::4]: print("  inside %.1f mm at %s (design %s)" % (d * 1000, min(joints, key=lambda k: (joints[k] - Vector(p)).length), np.round(np.array([p[0], p[1], p[2]]) / 0.0036, 1)))
    return report

allrep = {}
for fi in FRAMES:
    if fi >= len(D["frames"]): break
    rep = check(D["frames"][fi]); allrep[fi] = rep
    for k, x in sorted(rep.items()):
        if len(FRAMES) == 1 or x["inside_pts"]: print("CONTACT", fi, k, json.dumps(x))
print("CHECKED", len(allrep), "frames")
if OUTJ: json.dump(allrep, open(OUTJ, "w"), indent=1)
