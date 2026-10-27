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

# finger1 = thumb ... finger5 = pinky; curls are rotations about each bone's X (toward the palm), or (x, y, z) Euler angles
POSES = {
    "R": {  # pencil grip: index along the hook, middle under it, ring and pinky tucked, thumb across
        # (index and middle chosen so thumb pad, index pad, middle fingertip and web all rest on one straight shaft)
        "finger2": (22, 30, 20), "finger3": (35, 50, 30), "finger4": (55, 70, 38), "finger5": (60, 72, 38),
        "finger1": (10, 20, 20)},
    "L": {  # holding the work: index raised for the yarn, middle and thumb pinch, the rest relaxed
        # (thumb and middle chosen so their pads face squarely, as far apart as the work is thick)
        "finger2": (-8, 8, 6), "finger3": (30, 60, 35), "finger4": (42, 52, 28), "finger5": ((30, 0, 15), 45, 25),   # pinky spread: room to wrap the yarn round it
        "finger1": ((18, 0, 10), 10, 30)},
}
for side in ("R", "L"):     # tests: HAND_POSE_L='{"finger1": [10, 20, 20]}'
    if os.environ.get("HAND_POSE_" + side): POSES[side].update(json.loads(os.environ["HAND_POSE_" + side]))

for o in list(bpy.data.objects): bpy.data.objects.remove(o)
human = HumanService.create_human()
rig = HumanService.add_builtin_rig(human, "default")
pb = rig.pose.bones
for side, pose in POSES.items():
    for f, curls in pose.items():
        for j, a in enumerate(curls, 1):
            b = pb[f"{f}-{j}.{side}"]; b.rotation_mode = "XYZ"
            b.rotation_euler = [math.radians(x) for x in (a if isinstance(a, (list, tuple)) else (a, 0, 0))]
bpy.context.view_layer.update()

def wpos(name, tail=False):
    b = pb[name]; return rig.matrix_world @ (b.tail if tail else b.head)

dg = bpy.context.evaluated_depsgraph_get()
posed = bpy.data.meshes.new_from_object(human.evaluated_get(dg))      # armature + mask applied
posed.transform(human.matrix_world)

# skin: MakeHuman diffuse map with subsurface scattering; creases and knuckles a little darker and
# redder (Cycles pointiness), roughness that varies over the surface, and pore-scale bump
skin_png = os.path.join(OUT, "skin.png"); shutil.copyfile(SKIN, skin_png)
mat = bpy.data.materials.new("HandSkin"); mat.use_nodes = True
n = mat.node_tree.nodes; l = mat.node_tree.links; bs = n["Principled BSDF"]
tex = n.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(skin_png); tex.image.pack()
hsv = n.new("ShaderNodeHueSaturation")          # studio light flattens it: deeper and warmer
hsv.inputs["Saturation"].default_value = 1.3; hsv.inputs["Value"].default_value = 0.64; hsv.inputs["Hue"].default_value = 0.49
l.new(tex.outputs["Color"], hsv.inputs["Color"])
geo = n.new("ShaderNodeNewGeometry")
cr = n.new("ShaderNodeValToRGB")                # pointiness: < 0.5 in creases, > 0.5 on knuckles and tips
cr.color_ramp.elements[0].position = 0.42; cr.color_ramp.elements[0].color = (0.55, 0.32, 0.30, 1)
cr.color_ramp.elements[1].position = 0.56; cr.color_ramp.elements[1].color = (1, 1, 1, 1)
l.new(geo.outputs["Pointiness"], cr.inputs["Fac"])
mul = n.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 0.8
l.new(hsv.outputs["Color"], mul.inputs[6]); l.new(cr.outputs["Color"], mul.inputs[7])

bs.inputs["Subsurface Weight"].default_value = 1.0; bs.inputs["Subsurface Radius"].default_value = (1.0, 0.38, 0.22)
bs.inputs["Subsurface Scale"].default_value = 0.0016; bs.inputs["Specular IOR Level"].default_value = 0.5
co = n.new("ShaderNodeTexCoord")
rn = n.new("ShaderNodeTexNoise"); rn.inputs["Scale"].default_value = 60; rn.inputs["Detail"].default_value = 4
l.new(co.outputs["Object"], rn.inputs["Vector"])
rr = n.new("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = 0.36; rr.inputs["To Max"].default_value = 0.56
l.new(rn.outputs["Fac"], rr.inputs["Value"]); l.new(rr.outputs["Result"], bs.inputs["Roughness"])
# blotchy redness: real skin is never one even tone
mot = n.new("ShaderNodeTexNoise"); mot.inputs["Scale"].default_value = 35; mot.inputs["Detail"].default_value = 3
mr = n.new("ShaderNodeValToRGB"); mr.color_ramp.elements[0].color = (1.0, 0.86, 0.84, 1); mr.color_ramp.elements[1].color = (1.0, 1.0, 0.97, 1)
mr.color_ramp.elements[0].position = 0.35; mr.color_ramp.elements[1].position = 0.65
l.new(co.outputs["Object"], mot.inputs["Vector"]); l.new(mot.outputs["Fac"], mr.inputs["Fac"])
mul2 = n.new("ShaderNodeMix"); mul2.data_type = "RGBA"; mul2.blend_type = "MULTIPLY"; mul2.inputs["Factor"].default_value = 1.0
l.new(mul.outputs[2], mul2.inputs[6]); l.new(mr.outputs["Color"], mul2.inputs[7])
l.new(mul2.outputs[2], bs.inputs["Base Color"])
pores = n.new("ShaderNodeTexVoronoi"); pores.inputs["Scale"].default_value = 2200
l.new(co.outputs["Object"], pores.inputs["Vector"])
fine = n.new("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = 700; fine.inputs["Detail"].default_value = 8
l.new(co.outputs["Object"], fine.inputs["Vector"])
hsum = n.new("ShaderNodeMath"); hsum.operation = "ADD"
l.new(pores.outputs["Distance"], hsum.inputs[0]); l.new(fine.outputs["Fac"], hsum.inputs[1])
bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35; bump.inputs["Distance"].default_value = 0.0004
l.new(hsum.outputs["Value"], bump.inputs["Height"]); l.new(bump.outputs["Normal"], bs.inputs["Normal"])

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
    # cut out the hand and ~28 cm of forearm (the cut stays out of frame)
    me = posed.copy(); me.name = "Hand" + side
    bm = bmesh.new(); bm.from_mesh(me)
    kill = [v for v in bm.verts if (v.co - wrist).length > 0.42 or (v.co - wrist).dot(yh) < -0.28]
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
    sub = ob.modifiers.new("Sub", "SUBSURF"); sub.levels = 1; sub.render_levels = 3
    objs.append(ob)
    L = lambda p: list(to_local @ p)
    points[side] = {"wrist": [0, 0, 0]}
    for fi, fname in enumerate(("thumb", "index", "middle", "ring", "pinky"), 1):   # every joint of every finger
        points[side].update({fname + "_knuckle": L(wpos(f"finger{fi}-1.{side}")), fname + "_pip": L(wpos(f"finger{fi}-2.{side}")),
                             fname + "_dip": L(wpos(f"finger{fi}-3.{side}")), fname + "_tip": L(wpos(f"finger{fi}-3.{side}", True))})
    sub.levels = 2; bpy.context.view_layer.update()                # the surface as rendered, near enough
    em = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    P_ = points[side]; V = [(Vector(x.co), Vector(x.normal)) for x in em.vertices]
    # the skin of the whole hand: choreo.py lays the working yarn on the left one and the hook in the right one
    P_["_verts"] = [[round(c, 5) for c in p] for p, _ in V]
    P_["_normals"] = [[round(c, 4) for c in nv] for _, nv in V]
    # the pinch pads (left hand): the skin points of the thumb and middle fingertips that face each
    # other, with their normals — choreo.py lays them on the two faces of the fabric
    if side == "L":
        def pad(f, other):
            a, b = Vector(P_[f + "_dip"]), Vector(P_[f + "_tip"]); o = Vector(P_[other + "_tip"])
            def seg_t(p): return (p - a).dot(b - a) / (b - a).length_squared
            near = [(p, nv) for p, nv in V if 0.25 < seg_t(p) < 1.05 and ((a + (b - a) * seg_t(p)) - p).length < 0.013]
            p, nv = max(near, key=lambda q: q[1].dot((o - q[0]).normalized()))
            return p, nv
        for f, other in (("thumb", "middle"), ("middle", "thumb")):
            p, nv = pad(f, other); P_[f + "_pad"] = list(p); P_[f + "_pad_n"] = list(nv)
        g = Vector(P_["thumb_pad"]) - Vector(P_["middle_pad"])
        print("PINCH gap %.1f mm, facing %.2f %.2f" % (g.length * 1000, Vector(P_["middle_pad_n"]).dot(g.normalized()), -Vector(P_["thumb_pad_n"]).dot(g.normalized())))
    ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear(); sub.levels = 1
    print("HAND", side, len(me.vertices), "verts")

bpy.data.libraries.write(os.path.join(OUT, "hands.blend"), set(objs), fake_user=True)
json.dump(points, open(os.path.join(OUT, "hands.json"), "w"), indent=1)
print("wrote", OUT)
