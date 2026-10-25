# Bake the two crochet hands for the guided take from a MakeHuman body (MPFB2, CC0 assets):
# the right hand in a pencil grip, the left hand holding the work with its index finger raised
# to carry the yarn. Each is cut out with a little forearm and saved in its own hand frame.
#
#   blender -b -P tools/make_hands_mpfb.py -- build/hands [skin.png]
#
# Needs the MPFB2 extension (extensions.blender.org/add-ons/mpfb) installed in Blender, and a
# MakeHuman CC0 skin texture (makehuman_system_assets_cc0.zip, skins/*/..._diffuse.png).
# Writes <out>/hands.blend (objects HandR, HandL; metres) and <out>/hands.json (named points
# in each hand's frame: wrist at the origin, fingers along +Y, back of the hand +Z).
import bpy, bmesh, sys, os, json, math, shutil
from mathutils import Vector, Matrix
from bl_ext.user_default.mpfb.services.humanservice import HumanService

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "build/hands")
SKIN = argv[1] if len(argv) > 1 else "/opt/mh/sys/skins/young_caucasian_female/young_lightskinned_female_diffuse.png"
os.makedirs(OUT, exist_ok=True)

# finger1 = thumb ... finger5 = pinky; curls are rotations about each bone's X (toward the palm)
POSES = {
    "R": {  # pencil grip: index along the hook, middle under it, ring and pinky tucked, thumb across
        "finger2": (12, 18, 10), "finger3": (38, 55, 30), "finger4": (55, 70, 38), "finger5": (60, 72, 38),
        "finger1": (10, 20, 20)},
    "L": {  # holding the work: index raised for the yarn, middle and thumb pinch, the rest relaxed
        "finger2": (-8, 8, 6), "finger3": (30, 40, 22), "finger4": (42, 52, 28), "finger5": (48, 55, 28),
        "finger1": (8, 15, 12)},
}

for o in list(bpy.data.objects): bpy.data.objects.remove(o)
human = HumanService.create_human()
rig = HumanService.add_builtin_rig(human, "default")
pb = rig.pose.bones
for side, pose in POSES.items():
    for f, curls in pose.items():
        for j, a in enumerate(curls, 1):
            b = pb[f"{f}-{j}.{side}"]; b.rotation_mode = "XYZ"; b.rotation_euler = (math.radians(a), 0, 0)
bpy.context.view_layer.update()

def wpos(name, tail=False):
    b = pb[name]; return rig.matrix_world @ (b.tail if tail else b.head)

dg = bpy.context.evaluated_depsgraph_get()
posed = bpy.data.meshes.new_from_object(human.evaluated_get(dg))      # armature + mask applied
posed.transform(human.matrix_world)

# skin: MakeHuman diffuse map, subsurface scattering, fine pore/crease bump
skin_png = os.path.join(OUT, "skin.png"); shutil.copyfile(SKIN, skin_png)
mat = bpy.data.materials.new("HandSkin"); mat.use_nodes = True
n = mat.node_tree.nodes; l = mat.node_tree.links; bs = n["Principled BSDF"]
tex = n.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(skin_png); tex.image.pack()
hsv = n.new("ShaderNodeHueSaturation")          # studio light flattens it: a touch deeper and warmer
hsv.inputs["Saturation"].default_value = 1.25; hsv.inputs["Value"].default_value = 0.78; hsv.inputs["Hue"].default_value = 0.49
l.new(tex.outputs["Color"], hsv.inputs["Color"]); l.new(hsv.outputs["Color"], bs.inputs["Base Color"])
bs.inputs["Roughness"].default_value = 0.48
bs.inputs["Subsurface Weight"].default_value = 0.3; bs.inputs["Subsurface Radius"].default_value = (1.0, 0.4, 0.25)
bs.inputs["Subsurface Scale"].default_value = 0.003; bs.inputs["Specular IOR Level"].default_value = 0.45
noise = n.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 900; noise.inputs["Detail"].default_value = 6
bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.06; bump.inputs["Distance"].default_value = 0.0003
l.new(noise.outputs["Fac"], bump.inputs["Height"]); l.new(bump.outputs["Normal"], bs.inputs["Normal"])

points = {}
objs = []
for side in ("R", "L"):
    wrist = wpos(f"wrist.{side}")
    mid_k, idx_k, pnk_k = wpos(f"finger3-1.{side}"), wpos(f"finger2-1.{side}"), wpos(f"finger5-1.{side}")
    yh = (mid_k - wrist).normalized()
    nrm_ = yh.cross(idx_k - pnk_k).normalized()
    # the palm is the side the curled fingers bend toward: back of the hand is the other way
    ring_tip = wpos(f"finger4-3.{side}", tail=True)
    zh = -nrm_ if (ring_tip - mid_k).dot(nrm_) > 0 else nrm_
    zh = (zh - yh * zh.dot(yh)).normalized(); xh = yh.cross(zh)
    to_local = Matrix((xh, yh, zh)).to_4x4() @ Matrix.Translation(-wrist)
    # cut out the hand and ~16 cm of forearm (the cut stays out of frame)
    me = posed.copy(); me.name = "Hand" + side
    bm = bmesh.new(); bm.from_mesh(me)
    kill = [v for v in bm.verts if (v.co - wrist).length > 0.3 or (v.co - wrist).dot(yh) < -0.16]
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    # keep only the piece connected to this wrist (drops the other hand / body bits within range)
    bm.verts.ensure_lookup_table()
    seed = min(bm.verts, key=lambda v: (v.co - (wrist + yh * 0.03)).length)
    keep, stack = {seed}, [seed]
    while stack:
        v = stack.pop()
        for e in v.link_edges:
            o = e.other_vert(v)
            if o not in keep: keep.add(o); stack.append(o)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v not in keep], context="VERTS")
    bm.to_mesh(me); bm.free()
    me.transform(to_local); me.materials.clear(); me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new("Hand" + side, me); bpy.context.scene.collection.objects.link(ob)
    sub = ob.modifiers.new("Sub", "SUBSURF"); sub.levels = 1; sub.render_levels = 2
    objs.append(ob)
    L = lambda p: list(to_local @ p)
    points[side] = {"wrist": [0, 0, 0],
                    "index_knuckle": L(idx_k), "index_pip": L(wpos(f"finger2-2.{side}")), "index_dip": L(wpos(f"finger2-3.{side}")),
                    "index_tip": L(wpos(f"finger2-3.{side}", True)), "middle_tip": L(wpos(f"finger3-3.{side}", True)),
                    "thumb_tip": L(wpos(f"finger1-3.{side}", True)), "middle_pip": L(wpos(f"finger3-2.{side}"))}
    print("HAND", side, len(me.vertices), "verts")

bpy.data.libraries.write(os.path.join(OUT, "hands.blend"), set(objs), fake_user=True)
json.dump(points, open(os.path.join(OUT, "hands.json"), "w"), indent=1)
print("wrote", OUT)
