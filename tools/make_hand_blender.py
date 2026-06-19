"""
Generate a high-fidelity right hand posed in a crochet grip and export it to
assets/hand-right.glb (the file index.html loads at runtime).

The hand is built from a vertex/edge skeleton + Blender's Skin modifier +
Subdivision Surface, which yields a smooth, organic, chunky hand. The grip is
baked directly into the mesh, so the model needs no armature and does not depend
on any bone names.

USAGE (run locally, where Blender is installed):

    blender --background --python tools/make_hand_blender.py

  Optional explicit output path (otherwise <repo>/assets/hand-right.glb):

    blender --background --python tools/make_hand_blender.py -- /abs/path/hand-right.glb

Tested against Blender 3.6 LTS and 4.x. After it runs, commit the resulting
assets/hand-right.glb and push.
"""

import bpy
import os
import sys
import math

# ---------------------------------------------------------------- output path
def resolve_out_path():
    argv = sys.argv
    if "--" in argv:
        extra = argv[argv.index("--") + 1:]
        if extra:
            return os.path.abspath(extra[0])
    # default: <repo root>/assets/hand-right.glb  (repo root = parent of tools/)
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    return os.path.join(repo, "assets", "hand-right.glb")

OUT = resolve_out_path()
os.makedirs(os.path.dirname(OUT), exist_ok=True)

# ---------------------------------------------------------------- clean scene
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for block in (bpy.data.meshes, bpy.data.materials):
    for b in list(block):
        if b.users == 0:
            block.remove(b)

# ---------------------------------------------------------------- skeleton
# Coordinate convention (metres, Blender Z-up):
#   +Y = direction the wrist points toward the fingers
#   +Z = back of hand;  fingers curl toward -Z then back toward the palm
# Everything is built at roughly life size (~0.19 m). The app rescales it.
verts = []     # list of (x,y,z)
edges = []     # list of (i,j)
radii = []     # per-vertex skin radius
roots = []     # per-vertex use_root flag

def add_v(p, r, root=False, parent=None):
    i = len(verts)
    verts.append(p)
    radii.append(r)
    roots.append(root)
    if parent is not None:
        edges.append((parent, i))
    return i

# wrist (root of the skin graph) -> palm
wrist = add_v((0.0, -0.02, 0.0), 0.040, root=True)
palm  = add_v((0.0,  0.055, 0.0), 0.047, parent=wrist)
# a second palm node spreads the knuckle ridge so the back of the hand reads full
palm2 = add_v((0.0,  0.085, 0.004), 0.043, parent=palm)

def dir_yz(angle_deg):
    """Unit direction in the Y-Z plane, angle measured from +Y toward -Z."""
    a = math.radians(angle_deg)
    return (0.0, math.cos(a), -math.sin(a))

# fingers: (name, x offset, length scale).  Middle longest, pinky shortest.
fingers = [
    ("index",  0.027, 1.00),
    ("middle", 0.009, 1.09),
    ("ring",  -0.009, 1.00),
    ("pinky", -0.027, 0.82),
]
# cumulative curl per joint (degrees from +Y, rotating down toward the palm)
curl_angles = [38.0, 78.0, 116.0]
seg_radii   = [0.012, 0.0105, 0.0080]   # proximal, intermediate, distal tip

for name, xoff, lscale in fingers:
    knuckle = add_v((xoff, 0.105, 0.002), 0.0135, parent=palm2)
    px, py, pz = verts[knuckle]
    prev = knuckle
    for j, ang in enumerate(curl_angles):
        dx, dy, dz = dir_yz(ang)
        seg = 0.032 * lscale * (1.0 - 0.12 * j)   # phalanges shorten toward tip
        px, py, pz = px + dx * seg, py + dy * seg, pz + dz * seg
        prev = add_v((xoff * (1.0 - 0.15 * j), py, pz), seg_radii[j], parent=prev)

# thumb: springs from the radial (+X) side of the palm and wraps inward
th0 = add_v((0.040, 0.030, 0.006), 0.018, parent=palm)
th1 = add_v((0.066, 0.062, 0.004), 0.015, parent=th0)
th2 = add_v((0.060, 0.092, -0.012), 0.0125, parent=th1)
th3 = add_v((0.040, 0.110, -0.024), 0.0095, parent=th2)  # tip closes the grip

# ---------------------------------------------------------------- build mesh
mesh = bpy.data.meshes.new("Hand")
mesh.from_pydata(verts, edges, [])
mesh.update()
obj = bpy.data.objects.new("Hand", mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

# ---------------------------------------------------------------- skin modifier
skin = obj.modifiers.new(name="Skin", type="SKIN")
skin.use_smooth_shade = True
sv = mesh.skin_vertices[0].data
for i, r in enumerate(radii):
    sv[i].radius = (r, r)
    sv[i].use_root = roots[i]

# subdivision for organic smoothness
sub = obj.modifiers.new(name="Subsurf", type="SUBSURF")
sub.levels = 2
sub.render_levels = 2

bpy.ops.object.shade_smooth()

# ---------------------------------------------------------------- skin material
mat = bpy.data.materials.new("Skin")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")

def setin(node, names, value):
    for n in names:
        if n in node.inputs:
            try:
                node.inputs[n].default_value = value
                return True
            except Exception:
                pass
    return False

if bsdf:
    setin(bsdf, ["Base Color"], (0.79, 0.54, 0.36, 1.0))
    setin(bsdf, ["Roughness"], 0.62)
    setin(bsdf, ["Metallic"], 0.0)
    # subsurface naming differs across Blender versions
    setin(bsdf, ["Subsurface Weight", "Subsurface"], 0.12)
    setin(bsdf, ["Subsurface Radius"], (0.10, 0.03, 0.02))
    setin(bsdf, ["Subsurface Color"], (0.80, 0.40, 0.30, 1.0))
obj.data.materials.append(mat)

# ---------------------------------------------------------------- export
print("[make_hand] exporting ->", OUT)
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format="GLB",
    use_selection=False,
    export_apply=True,        # bake Skin + Subsurf into the exported mesh
    export_yup=True,
)
print("[make_hand] done:", OUT)
