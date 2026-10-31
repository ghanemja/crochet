# The left hand at work: tools/make_hands_mpfb.py bakes working poses of the left hand (Ly, Lf, Le) on L's
# mesh; choreo.py gives each frame's hand a "mix" ({pose: weight}). Here (inside Blender) each pose becomes a
# shape key on the hand object (HandL, or HandLc: the same pose change applied to its own shape) and the mix
# sets the keys. Shared by render_tutorial.py and hand_contact.py.
import numpy as np

WORK_POSES = ("Ly", "Lf", "Le")

def _co(me):
    a = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", a); return a

def add_pose_keys(bpy, ob, blend_path):
    """shape keys on ob for the working poses (their change from HandL), if the hands file has them"""
    if not ob.name.startswith("HandL") or ob.data.shape_keys is not None: return
    want = ["HandL"] + ["Hand" + p for p in WORK_POSES]
    with bpy.data.libraries.load(blend_path) as (src, dst):
        have = set(src.objects); names = [n for n in want if n in have]; dst.objects = list(names)
    ref = {n: o for n, o in zip(names, dst.objects) if o is not None}   # (loaded copies may be renamed: HandL.001)
    if "HandL" not in ref: return
    base = _co(ref["HandL"].data); n = len(ob.data.vertices)
    if len(base) != n * 3: return
    ob.shape_key_add(name="Basis", from_mix=False); own = _co(ob.data)
    for p in WORK_POSES:
        r = ref.get("Hand" + p)
        if r is None or len(r.data.vertices) != n: continue
        k = ob.shape_key_add(name=p, from_mix=False); k.data.foreach_set("co", own + (_co(r.data) - base))
        k.slider_min, k.slider_max = 0.0, 1.0
    for o in ref.values():
        if o is not ob: bpy.data.objects.remove(o)

def set_mix(ob, mix):
    keys = ob.data.shape_keys
    if keys is None: return
    for p in WORK_POSES:
        if p in keys.key_blocks: keys.key_blocks[p].value = float((mix or {}).get(p, 0.0))
