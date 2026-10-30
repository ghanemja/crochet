# Route B: render a "Learn this stitch" tutorial in Cycles from the strand paths
# that index.html exports (tools/export_paths.mjs -> build/paths/<key>.json).
#
#   blender -b -P tools/render_tutorial.py -- build/paths/sc.json build/frames/sc \
#           [--samples 64] [--res 1280x800] [--frames 0:-1:1] [--hdri build/hdri/x.hdr]
#
# Each strand is rebuilt per frame as hair curves: three plies twisted together,
# spun fibres helixing the other way around each ply, and sparse flyaway hairs
# (all seeded by arc length, so they stay put from frame to frame). Writes
# RGBA PNGs (transparent film + shadow-catcher floor); tools/encode_tutorial.sh
# puts them on the app's cream background.
import bpy, sys, json, math, os, argparse
import numpy as np
from mathutils import Vector, Quaternion, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("paths"); ap.add_argument("out")
ap.add_argument("--samples", type=int, default=16)        # + OpenImageDenoise
ap.add_argument("--res", default="800x500")              # the modal shows ~520 css px
ap.add_argument("--frames", default="0:-1:1")
ap.add_argument("--hdri", default="build/hdri/studio_small_09_2k.hdr")
ap.add_argument("--lens", type=float, default=100.0)      # mm on a 24 mm-tall sensor (long lens)
ap.add_argument("--fstop", type=float, default=22.0)       # the scene is real size (yarn 3.6 mm thick): f/4 left a sliver in focus
ap.add_argument("--skip-existing", action="store_true")
ap.add_argument("--angle", type=int, default=0)              # which of the JSON's "views" (camera angles) to render
ap.add_argument("--lookdev", action="store_true")           # one strand in close-up (yarn look development)
ap.add_argument("--zoom", type=float, default=1.0)         # look-dev: >1 moves the camera in on the stitch, focus on the target
ap.add_argument("--fray", type=float, default=0.35)         # share of staple ends that lift out of the ply
ap.add_argument("--fibres", type=int, default=220)        # staple fibres per ply
ap.add_argument("--shape", default="RIBBONS")              # Cycles curve shape: RIBBONS (fast, tapered strips) | THICK
ap.add_argument("--sss", type=float, default=0.0)          # subsurface doubles the frame time on CPU
ap.add_argument("--bounces", type=int, default=6)
ap.add_argument("--view", default="AgX")
ap.add_argument("--exposure", type=float, default=0.0)
ap.add_argument("--fuzz-fix", type=int, default=1)
ap.add_argument("--floor", type=int, default=0)             # 1: the shadow-catcher floor (a shadow under the work)
# the app's cream #f3ece3 rendered opaque: these linear values come out as it through AgX Punchy
# (solved by test renders). A transparent film left the fibres' edges noisy — the denoiser skips alpha.
ap.add_argument("--stage", default="9.9249,7.3645,4.5288")   # "" for a transparent film          # 0: the old flyaway look (white glints at the edges)
A = ap.parse_args(argv)
D = json.load(open(A.paths))
os.makedirs(A.out, exist_ok=True)

S = 0.01                                                   # app units -> metres (yarn radius 3.6 mm)
C = Matrix.Rotation(math.pi / 2, 4, "X")                   # three.js Y-up -> Blender Z-up
CQ = C.to_quaternion()
def to_bl(p): return Vector((p[0] * S, -p[2] * S, p[1] * S))
def to_bl_np(a): return np.stack([a[:, 0], -a[:, 2], a[:, 1]], 1) * S

def srgb_lin(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]

# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
W, H = map(int, A.res.split("x"))
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = A.samples
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.max_bounces = A.bounces; sc.cycles.transparent_max_bounces = 8
if A.fuzz_fix:                                             # no fireflies off the fibres' highlights
    sc.cycles.blur_glossy = 1.0; sc.cycles.sample_clamp_indirect = 3.0
# flicker experiments (defaults = the settings in use): denoiser prefilter / quality, indirect clamp, min samples
if os.environ.get("DN_PREFILTER"): sc.cycles.denoising_prefilter = os.environ["DN_PREFILTER"]
if os.environ.get("DN_QUALITY"): sc.cycles.denoising_quality = os.environ["DN_QUALITY"]
if os.environ.get("CLAMP_IND"): sc.cycles.sample_clamp_indirect = float(os.environ["CLAMP_IND"])
if os.environ.get("ADAPT_MIN"): sc.cycles.adaptive_min_samples = int(os.environ["ADAPT_MIN"])
if os.environ.get("DENOISE") == "0": sc.cycles.use_denoising = False
sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = A.view
if A.view == "AgX": sc.view_settings.look = "AgX - Punchy"
sc.view_settings.exposure = A.exposure
sc.cycles_curves.shape = A.shape
sc.cycles_curves.subdivisions = 2

world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
wn = world.node_tree.nodes; wl = world.node_tree.links
bg = wn["Background"]
if os.path.exists(A.hdri):
    env = wn.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(os.path.abspath(A.hdri))
    mp = wn.new("ShaderNodeMapping"); tc = wn.new("ShaderNodeTexCoord")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(110))
    wl.new(tc.outputs["Generated"], mp.inputs["Vector"]); wl.new(mp.outputs["Vector"], env.inputs["Vector"])
    wl.new(env.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 0.18
else:
    print("no HDRI at", A.hdri, "- using a flat warm environment")
    bg.inputs["Color"].default_value = (0.85, 0.8, 0.74, 1); bg.inputs["Strength"].default_value = 0.8
if A.stage:
    # an opaque film: camera rays see the stage colour, everything else still sees the HDRI. With a
    # transparent film the denoiser leaves alpha noisy, and the loose fibres' edges came out as specks.
    sc.render.film_transparent = False
    lp = wn.new("ShaderNodeLightPath"); em = wn.new("ShaderNodeBackground"); mx = wn.new("ShaderNodeMixShader")
    em.inputs["Color"].default_value = [float(x) for x in A.stage.split(",")] + [1]; em.inputs["Strength"].default_value = 1.0
    wl.new(lp.outputs["Is Camera Ray"], mx.inputs["Fac"]); wl.new(bg.outputs["Background"], mx.inputs[1]); wl.new(em.outputs["Background"], mx.inputs[2])
    wl.new(mx.outputs["Shader"], wn["World Output"].inputs["Surface"])

# key: big soft area light up and to the left (matches the app's key at (8,16,12) mirrored for the long lens)
key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "AREA")); sc.collection.objects.link(key)
key.data.shape = "DISK"; key.data.size = 0.35; key.data.energy = 9; key.data.color = (1.0, 0.95, 0.9)
key.location = to_bl((-14, 18, 16)); key.rotation_euler = (to_bl((0, 0, 0)) - key.location).to_track_quat("-Z", "Y").to_euler()
rim = bpy.data.objects.new("Rim", bpy.data.lights.new("Rim", "AREA")); sc.collection.objects.link(rim)
rim.data.size = 0.25; rim.data.energy = 9; rim.data.color = (1.0, 0.9, 0.8)
rim.location = to_bl((6, 10, -16)); rim.rotation_euler = (to_bl((0, 0, 0)) - rim.location).to_track_quat("-Z", "Y").to_euler()

RIG = []          # set below: what turns with the guided camera (choreo.py turn_of)
# floor: shadow catcher. The app's ground (y=-3.4) only draws shadows, so the working
# yarn runs on below it to the ball; a catcher there would cut that strand off.
fm = bpy.data.meshes.new("Floor"); g = -10.0 * S; e = 3.0
fm.from_pydata([(-e, -e, g), (e, -e, g), (e, e, g), (-e, e, g)], [], [(0, 1, 2, 3)])
floor = bpy.data.objects.new("Floor", fm); sc.collection.objects.link(floor); floor.is_shadow_catcher = True
if not A.floor:   # its shadow showed through the stitches' holes as grey, speckled with noise; keep the light it bounces
    floor.is_shadow_catcher = False; floor.visible_camera = False; floor.visible_shadow = False
    fmat = bpy.data.materials.new("Floor"); fmat.use_nodes = True
    fmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.80, 0.74, 1)
    fm.materials.append(fmat)

RIG = [(o_, o_.location.copy(), o_.rotation_euler.to_quaternion()) for o_ in (key, rim, floor)]
ENV_MAP = mp if os.path.exists(A.hdri) else None
# camera: the app's framing, pulled back along the view line for a long lens
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cd = cam.data; cd.sensor_fit = "VERTICAL"; cd.sensor_height = 24; cd.sensor_width = 24 * W / H; cd.lens = A.lens
vf = 2 * math.atan(12 / A.lens)
CAM = D["views"][A.angle] if "views" in D else D["camera"]
P = Vector(CAM["pos"]); T = Vector(CAM["target"])
k = math.tan(math.radians(CAM["fov"]) / 2) / math.tan(vf / 2)
cam.location = to_bl(T + (P - T) * k / A.zoom); tgt = to_bl(T)
cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
cd.dof.use_dof = True; cd.dof.aperture_fstop = A.fstop; cd.dof.aperture_blades = 7
cam_fwd = (tgt - cam.location).normalized()

# ---------------------------------------------------------------- materials
def yarn_mat(name, hexcol, fibre=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links; b = n["Principled BSDF"]
    base = srgb_lin(hexcol)
    hi = n.new("ShaderNodeHairInfo"); ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = [c * 0.4 for c in base[:3]] + [1]   # ply core, seen only between fibres
    ramp.color_ramp.elements[1].color = [c * 0.6 for c in base[:3]] + [1]
    l.new(hi.outputs["Random"], ramp.inputs["Fac"])
    # darker toward the ply core (Intercept runs along the curve; use it lightly for streaks)
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.72 if fibre else 0.85
    b.inputs["Sheen Weight"].default_value = 0.7
    b.inputs["Sheen Roughness"].default_value = 0.35
    b.inputs["Sheen Tint"].default_value = [min(1, c * 1.15 + 0.04) for c in base[:3]] + [1]
    b.inputs["Subsurface Weight"].default_value = A.sss
    b.inputs["Subsurface Radius"].default_value = (base[0] * 2 + 0.2, base[1] * 2 + 0.2, base[2] * 2 + 0.2)
    b.inputs["Subsurface Scale"].default_value = 0.0015
    b.inputs["Specular IOR Level"].default_value = 0.3
    return m

def fuzz_mat(name, hexcol):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links
    n.remove(n["Principled BSDF"])
    h = n.new("ShaderNodeBsdfHairPrincipled"); h.parametrization = "COLOR"
    h.inputs["Color"].default_value = [min(1, c * 1.1 + 0.05) for c in srgb_lin(hexcol)[:3]] + [1]
    h.inputs["Roughness"].default_value = 0.4; h.inputs["Radial Roughness"].default_value = 0.6
    l.new(h.outputs["BSDF"], n["Material Output"].inputs["Surface"])
    return m

def fibre_mat(name, hexcol):
    """Principled Hair (Chiang) — the silky per-fibre highlights; per-fibre tone jitter via Random."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links
    n.remove(n["Principled BSDF"])
    h = n.new("ShaderNodeBsdfHairPrincipled"); h.parametrization = "COLOR"
    base = [c ** 1.7 for c in srgb_lin(hexcol)[:3]]          # hair scatters light many times: pre-darken so it lands on the yarn colour
    hi = n.new("ShaderNodeHairInfo"); ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = [c * 0.4 for c in base] + [1]
    ramp.color_ramp.elements[1].color = [min(1, c * 1.25) for c in base] + [1]
    l.new(hi.outputs["Random"], ramp.inputs["Fac"]); l.new(ramp.outputs["Color"], h.inputs["Color"])
    h.inputs["Roughness"].default_value = 0.22; h.inputs["Radial Roughness"].default_value = 0.4
    h.inputs["Coat"].default_value = 0.15; h.inputs["IOR"].default_value = 1.55
    l.new(h.outputs["BSDF"], n["Material Output"].inputs["Surface"])
    return m

def flyaway_mat(name, hexcol):
    """the loose fibres round the yarn: matte and yarn-coloured. As shiny hair they caught the rim
    light as white glints, and being thinner than a pixel they sparkled from frame to frame."""
    if not A.fuzz_fix: return fibre_mat(name, hexcol)
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links
    n.remove(n["Principled BSDF"])
    h = n.new("ShaderNodeBsdfHairPrincipled"); h.parametrization = "COLOR"
    h.inputs["Color"].default_value = [c ** 1.7 * 0.9 for c in srgb_lin(hexcol)[:3]] + [1]
    h.inputs["Roughness"].default_value = 0.6; h.inputs["Radial Roughness"].default_value = 0.9
    h.inputs["Coat"].default_value = 0.0; h.inputs["IOR"].default_value = 1.3
    l.new(h.outputs["BSDF"], n["Material Output"].inputs["Surface"])
    return m

MAT = {False: (yarn_mat("Yarn", D["yarn"]), fibre_mat("YarnFibre", D["yarn"]), flyaway_mat("YarnFuzz", D["yarn"])),
       True: (yarn_mat("Accent", D["accent"]), fibre_mat("AccentFibre", D["accent"]), flyaway_mat("AccentFuzz", D["accent"]))}

steel = bpy.data.materials.new("Steel"); steel.use_nodes = True
sb = steel.node_tree.nodes["Principled BSDF"]
sb.inputs["Base Color"].default_value = (0.78, 0.8, 0.84, 1); sb.inputs["Metallic"].default_value = 1.0; sb.inputs["Roughness"].default_value = 0.18
handle = bpy.data.materials.new("Handle"); handle.use_nodes = True
hb = handle.node_tree.nodes["Principled BSDF"]
hb.inputs["Base Color"].default_value = srgb_lin("#c06078"); hb.inputs["Roughness"].default_value = 0.5

# ---------------------------------------------------------------- hook (built once, posed per frame)
verts, faces, mats = [], [], []
for part in D["hookMesh"]:
    p = np.array(part["pos"]).reshape(-1, 3)
    b0 = len(verts)
    verts += [tuple((C @ Vector(v)) * S) for v in p]
    faces += [(b0 + i, b0 + i + 1, b0 + i + 2) for i in range(0, len(p), 3)]
    mats += [0 if part["metal"] else 1] * (len(p) // 3)
hm = bpy.data.meshes.new("Hook"); hm.from_pydata(verts, [], faces)
hm.materials.append(steel); hm.materials.append(handle)
hm.polygons.foreach_set("material_index", mats)
import bmesh
bm = bmesh.new(); bm.from_mesh(hm); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6); bm.to_mesh(hm); bm.free()
hm.shade_smooth()
try: hm.set_sharp_from_angle(angle=math.radians(50))
except Exception: pass
hook = bpy.data.objects.new("Hook", hm); sc.collection.objects.link(hook); hook.rotation_mode = "QUATERNION"

# ---------------------------------------------------------------- hands (only in views that ask for them)
# Frames carry {"side", "pose", "pos", "rot"} placements; the hand is a tools/hand_rig.py skeleton
# skinned with the Skin + Subdivision modifiers (metres, Blender axes).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hand_rig
skin = bpy.data.materials.new("Skin"); skin.use_nodes = True
kb = skin.node_tree.nodes["Principled BSDF"]
kb.inputs["Base Color"].default_value = (0.50, 0.25, 0.16, 1); kb.inputs["Roughness"].default_value = 0.5
kb.inputs["Subsurface Weight"].default_value = 0.4; kb.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
kb.inputs["Subsurface Scale"].default_value = 0.004; kb.inputs["Sheen Weight"].default_value = 0.1
HANDS_ON = bool((D["views"][A.angle] if "views" in D else {}).get("hands")) and not A.lookdev
HAND_OBJ = {}
HANDS_BLEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "hands", "hands.blend")
def hand_object(side, pose, obj=None):
    key = (side, pose, obj)
    if key not in HAND_OBJ and os.path.exists(HANDS_BLEND):   # realistic MakeHuman hands (tools/make_hands_mpfb.py)
        with bpy.data.libraries.load(HANDS_BLEND) as (src, dst): dst.objects = [obj or "Hand" + side]
        ob = dst.objects[0]; sc.collection.objects.link(ob); HAND_OBJ[key] = ob
    if key not in HAND_OBJ:
        V, E, Rd, Ro, _ = hand_rig.skeleton(getattr(hand_rig, pose), side)
        me = bpy.data.meshes.new("Hand" + side); me.from_pydata(V, E, [])
        ob = bpy.data.objects.new("Hand" + side, me); sc.collection.objects.link(ob)
        ob.modifiers.new("Skin", "SKIN"); sv = me.skin_vertices[0].data
        for i, r in enumerate(Rd): sv[i].radius = (r, r); sv[i].use_root = Ro[i]
        sub = ob.modifiers.new("Sub", "SUBSURF"); sub.levels = sub.render_levels = 3
        me.materials.append(skin)
        for poly in me.polygons: poly.use_smooth = True
        HAND_OBJ[key] = ob
    return HAND_OBJ[key]
def set_hands(fr):
    if not HANDS_ON or not fr.get("hands"): return
    for h in fr["hands"]:
        ob = hand_object(h["side"], h["pose"], h.get("obj")); r = h["rot"]
        ob.matrix_world = Matrix(((r[0], r[1], r[2], h["pos"][0]), (r[3], r[4], r[5], h["pos"][1]),
                                  (r[6], r[7], r[8], h["pos"][2]), (0, 0, 0, 1))) @ Matrix.Scale(h.get("scale", 1.0), 4)

# ---------------------------------------------------------------- yarn as hair curves
PLIES = 3
def frames_rmf(c, closed, n_start=None):
    """rotation-minimising frames (n, b) along polyline c (N,3); n_start continues a frame from before."""
    N = len(c)
    if closed: t = np.roll(c, -1, 0) - np.roll(c, 1, 0)
    else:
        t = np.empty_like(c); t[1:-1] = c[2:] - c[:-2]; t[0] = c[1] - c[0]; t[-1] = c[-1] - c[-2]
    t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-12
    up = n_start if n_start is not None else (np.array([0.0, 1.0, 0.0]) if abs(t[0][1]) < 0.9 else np.array([1.0, 0.0, 0.0]))
    n = np.empty_like(c); n0 = up - t[0] * up.dot(t[0]); n[0] = n0 / np.linalg.norm(n0)
    for i in range(1, N):
        v = n[i - 1] - t[i] * n[i - 1].dot(t[i]); L = np.linalg.norm(v)
        n[i] = v / L if L > 1e-9 else n[i - 1]
    b = np.cross(t, n)
    if closed:   # spread the holonomy so the frame closes on itself
        a = math.atan2(np.dot(np.cross(n[-1], n[0]), t[0]), np.dot(n[-1], n[0]))
        ang = np.linspace(0, a, N)[:, None]
        n, b = n * np.cos(ang) + b * np.sin(ang), -n * np.sin(ang) + b * np.cos(ang)
    return n, b

def resample(pts, closed, step, mat=None):
    """-> (points, s, L, m): points along the polyline every ~step; m = mat(s), the yarn's own (material)
    coordinate there. Open strands are sampled where m is on a fixed grid (plus their two ends), so the
    points stay on the same bits of yarn from frame to frame however the strand grows or slides."""
    p = np.array(pts, float)
    if closed: p = np.vstack([p, p[:1]])
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)]); L = s[-1]
    if closed or mat is None:
        m = max(8, int(L / step) + 1); si = np.linspace(0, L, m)
    else:
        sd = np.linspace(0, L, max(16, int(L / step * 4) + 1)); md = mat(sd)
        grid = np.arange(math.ceil(md[0] / step) * step, md[-1], step)
        si = np.unique(np.concatenate([[0.0], np.interp(grid, md, sd), [L]]))
        si = si[np.concatenate([[True], np.diff(si) > step * 0.05])]; si[-1] = L
        if len(si) < 8: si = np.linspace(0, L, 8)
    q = np.stack([np.interp(si, s, p[:, k]) for k in range(3)], 1)
    if closed: q, si = q[:-1], si[:-1]
    return q, si, L, (mat(si) if mat is not None and not closed else si)

def rng_at(seed, j):   # cheap deterministic hash -> [0,1)
    x = (seed * 0x9E3779B97F4A7C15 + j * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    x ^= x >> 31; x = (x * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF; x ^= x >> 29
    return (x & 0xFFFFFF) / float(0xFFFFFF)

def ply_fibres(seed, pc, n, b, m, th, rply, R):
    """A.fibres staple fibres following one ply: each sits at a random depth in the ply, twists with it,
    wanders a little (frizz) and, at the ends of its staple, frays out and lifts off the surface. Seeded
    and laid out along m, the yarn's own coordinate -> each fibre stays on the same bit of yarn."""
    NF = A.fibres
    if NF <= 0: return []
    rng = np.random.default_rng(seed)
    rho0 = rng.uniform(0.55, 1.0, NF) ** 0.5 * 0.98          # depth in the ply (0 = core)
    ph0 = rng.uniform(0, 2 * math.pi, NF)
    wob_f = rng.uniform(0.6, 1.6, NF) / R; wob_p = rng.uniform(0, 2 * math.pi, NF)
    ang = ph0[:, None] + th[None, :] * 1.08 + 0.12 * np.sin(m[None, :] * wob_f[:, None] + wob_p[:, None])
    rho = rho0[:, None] * (1 + 0.07 * np.sin(m[None, :] * wob_f[:, None] * 1.7 + wob_p[:, None] * 2))
    m0, m1 = m[0], m[-1]; out = []
    for f in range(NF):
        # staples 4–11 R long, laid end to end along the yarn from its start (m = 0)
        x = -rng.uniform(0, 11 * R); cuts = []
        while x < m1:
            ln = rng.uniform(4, 11) * R; c_ = (x, x + ln, rng.uniform(0.4, 1.6) if rng.uniform() < A.fray else 0.06, rng.uniform(-1, 1)); x += ln
            if c_[1] > m0: cuts.append(c_)
        for (x0, x1, amp, curl) in cuts:
            i0 = int(np.searchsorted(m, max(m0, x0))); i1 = int(np.searchsorted(m, min(m1, x1)))
            if i1 - i0 < 3: continue
            mm = m[i0:i1]
            # fray: within ~1 R of a staple end the fibre leaves the ply and curls outward (not where the strand
            # merely ends: the yarn goes on in the next one or is cut there, and those ends taper instead)
            e0 = np.clip(1 - (mm - x0) / (1.2 * R), 0, 1) ** 2 if x0 > m0 else 0 * mm
            e1 = np.clip(1 - (x1 - mm) / (1.2 * R), 0, 1) ** 2 if x1 < m1 else 0 * mm
            e = np.maximum(e0, e1); fr = e * amp
            r = rply[i0:i1] * (rho[f, i0:i1] + fr)
            a = ang[f, i0:i1] + fr * curl
            pts = pc[i0:i1] + r[:, None] * (np.cos(a)[:, None] * n[i0:i1] + np.sin(a)[:, None] * b[i0:i1])
            out.append((pts, R * 0.009 * FIBRE_K * (1 - 0.6 * e)))          # tapers toward the frayed tips
    return out

def strand_curves(si_idx, st, mat=None, n_start=None, taper_start=True, taper_end=True):
    """-> (dict(kind -> list of (points (n,3) app units, radii (n,))), m at the end, last normal).
    mat(s) -> m, the yarn's own coordinate along this strand (see yarn_coords): the twist, fibres and
    flyaways are laid out along m, so they stay on the same bits of yarn as the strand moves; n_start turns
    the frame on from the strand before (one yarn split into colours)"""
    R = st["radius"]; closed = st["closed"]
    c, s, L, m = resample(st["pts"], closed, R * 0.09, mat)
    n, b = frames_rmf(c, closed, n_start)
    twist = 2 * math.pi / (R * 4.2)                       # one ply turn per ~4 yarn radii
    if closed: twist = 2 * math.pi * max(1, round(L * twist / (2 * math.pi))) / L
    rp, rply = R * 0.52, R * 0.52
    out = {"ply": [], "fibre": [], "fuzz": []}
    # taper the free ends a touch so cut ends read as yarn, not pipes
    taper = np.ones(len(s)) if closed else np.clip(np.minimum(s if taper_start else np.inf, L - s if taper_end else np.inf) / (R * 0.8), 0.55, 1)
    for k in range(PLIES):
        th = 2 * math.pi * k / PLIES + m * twist
        pc = c + rp * (np.cos(th)[:, None] * n + np.sin(th)[:, None] * b) * taper[:, None]
        out["ply"].append((pc, rply * 0.72 * taper))           # solid core under the fibres
        out["fibre"] += ply_fibres(si_idx * 7 + k, pc, n, b, m, th, rply * taper, R)
    # flyaways: thin curly wisps, anchored along m so they don't swim between frames
    spacing = R * 0.12 * FUZZ_K; seed = 1009 * (si_idx + 1); q = np.linspace(0, 1, 14)[:, None]
    for j in range(int(math.floor(m[0] / spacing)), int(m[-1] / spacing) + 1):
        u = (j + rng_at(seed, j % 1000003)) * spacing
        if u < m[0]: continue
        if u >= m[-1]: break
        r1, r2, r3, r4 = (rng_at(seed + mm_, j % 1000003) for mm_ in (1, 2, 3, 4))
        i = min(len(s) - 1, int(np.searchsorted(m, u)))
        a = r1 * 2 * math.pi; d = math.cos(a) * n[i] + math.sin(a) * b[i]
        t = c[(i + 1) % len(c)] - c[i - 1]; t /= np.linalg.norm(t) + 1e-12
        w = np.cross(t, d)
        ln = R * (0.4 + 1.8 * r2 ** 3)                        # mostly short, a few long strays
        k = (2 + 5 * r3) * math.pi                             # curl
        out_ = d * (0.25 + 0.5 * r4) + t * (r3 - 0.5) * 1.2    # leaves the surface at a shallow angle
        pts = c[i] + d * R * 0.9 + (out_ * q + (np.cos(k * q) - 1) * d * 0.18 + np.sin(k * q) * w * 0.25) * ln
        out["fuzz"].append((pts, (R * 0.011 * FIBRE_K * (1 - 0.7 * q)).ravel()))
    return out, m[-1], n[-1]

FIBRE_K = float(os.environ.get("FIBRE_K", "1.0"))   # fibre and flyaway thickness (x R * 0.009 / 0.011)
FUZZ_K = float(os.environ.get("FUZZ_K", "1.0"))     # flyaway spacing (x R * 0.12)
def poly_len(pts):
    p = np.asarray(pts, float); return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) if len(p) > 1 else 0.0
def yarn_coords(st, m_start, m_hold):
    """mat(s) for a strand: from its start the yarn's coordinate counts on from m_start (the yarn is fixed in the
    fabric); a strand marked with "slide"/"hold" (the working yarn) is held from "hold" on — over the throat, to
    the hand and the ball, fed from the ball — so there it counts back from its end, m_hold being the yarn's
    length to the ball (constant over the take); between "slide" and "hold", the loops on the hook, the yarn
    slides and the two meet"""
    if "hold" not in st or m_hold is None: return lambda s_: m_start + s_
    p = np.asarray(st["pts"], float); seg = np.linalg.norm(np.diff(p, axis=0), axis=1); arc = np.concatenate([[0], np.cumsum(seg)]); L = arc[-1]
    sa, sh = arc[min(st["slide"], len(arc) - 1)], arc[min(st["hold"], len(arc) - 1)]
    W = max(sh - sa, 1e-6); mh = m_hold
    gap = (m_start + L) - mh                                  # how much longer the yarn is than the held length
    if gap > 0.7 * W: mh = m_start + L - 0.7 * W              # (keep m increasing: the held part gives a little)
    def mat(s_):
        front, back = m_start + s_, mh - (L - s_)
        w = np.clip((s_ - sa) / W, 0, 1)
        return front * (1 - w) + back * w
    return mat

def build_curves(name, items, mat):
    cv = bpy.data.hair_curves.new(name)
    if not items: return cv
    cv.add_curves([len(p) for p, _ in items])
    pos = to_bl_np(np.vstack([p for p, _ in items])).astype(np.float32)
    cv.position_data.foreach_set("vector", pos.ravel())
    rad = (np.concatenate([r for _, r in items]) * S).astype(np.float32)
    if "radius" not in cv.attributes: cv.attributes.new("radius", "FLOAT", "POINT")
    cv.attributes["radius"].data.foreach_set("value", rad)
    cv.materials.append(mat)
    return cv

def shade_hex(h, k):
    """lighten (k > 1, toward white) or darken (k < 1) an sRGB hex colour"""
    c = [int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    c = [x + (255 - x) * (k - 1) if k > 1 else x * k for x in c]
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, x))) for x in c)
MATS = {}
def mats_for(acc, shade):
    """(core, fibre, fuzz) materials for the yarn (or accent) colour at a shade"""
    if shade == 1.0: return MAT[acc]
    key = (acc, shade)
    if key not in MATS:
        hx = shade_hex(D["accent"] if acc else D["yarn"], shade); nm = ("Acc" if acc else "Yarn") + "%.2f" % shade
        MATS[key] = (yarn_mat(nm, hx), fibre_mat(nm + "Fibre", hx), flyaway_mat(nm + "Fuzz", hx))
    return MATS[key]
def held_lengths():
    """per yarn (its first strand's index): the median over the take of its whole length to the far end of its
    held ("hold") strand: the yarn there is counted back from this, so it stays put (yarn_coords)"""
    acc = {}
    for fr in D["frames"]:
        prev = None
        for i, st in enumerate(fr["strands"]):
            if not st.get("visible") or len(st.get("pts", [])) < 3 or st.get("closed"): prev = None; continue
            cont = prev is not None and np.linalg.norm(np.array(st["pts"][0]) - prev[0]) < 1e-6
            root, m0 = (prev[1], prev[2]) if cont else (i, 0.0)
            m1 = m0 + poly_len(st["pts"])
            if "hold" in st: acc.setdefault(root, []).append(m1)
            prev = (np.array(st["pts"][-1]), root, m1)
    return {k: float(np.median(v)) for k, v in acc.items()}
YOBJ, YOBJ_KEYS = {}, set()
def set_yarn(fr):
    groups = {}
    prev = None                                                   # (last point, root index, m so far, last normal)
    for i, st in enumerate(fr["strands"]):
        if not st.get("visible") or len(st.get("pts", [])) < 3: prev = None; continue
        acc = bool(st.get("accent")); shade = round(float(st.get("shade", 1.0)), 2)
        cont = (prev is not None and not st["closed"] and np.linalg.norm(np.array(st["pts"][0]) - prev[0]) < 1e-6)
        root, m0, n0 = (prev[1], prev[2], prev[3]) if cont else (i, 0.0, None)
        nx = fr["strands"][i + 1] if i + 1 < len(fr["strands"]) else None
        goes_on = (not st["closed"] and nx is not None and nx.get("visible") and len(nx.get("pts", [])) >= 3
                   and np.linalg.norm(np.array(nx["pts"][0]) - np.array(st["pts"][-1])) < 1e-6)
        mat = yarn_coords(st, m0, HELD_LEN.get(root)) if not st["closed"] else None
        curves, m_end, n_last = strand_curves(root, st, mat, n0, taper_start=not cont, taper_end=not goes_on)
        prev = None if st["closed"] else (np.array(st["pts"][-1]), root, m_end, n_last)
        for kind, items in curves.items():
            groups.setdefault((acc, shade, kind), []).extend(items)
    keys = sorted({(a, sh) for a, sh, _ in groups} | {(False, 1.0), (True, 1.0)} | {(a, sh) for a, sh in YOBJ_KEYS})
    for acc, shade in keys:
        YOBJ_KEYS.add((acc, shade))
        for ki, kind in enumerate(("ply", "fibre", "fuzz")):
            name = ("Acc_" if acc else "Yarn_") + kind + ("" if shade == 1.0 else "_%.2f" % shade)
            old = YOBJ.get(name)
            data = build_curves(name, groups.get((acc, shade, kind), []), mats_for(acc, shade)[ki])
            if old is None:
                ob = bpy.data.objects.new(name, data); sc.collection.objects.link(ob); YOBJ[name] = ob
            else:
                od = old.data; old.data = data; bpy.data.hair_curves.remove(od)

# ---------------------------------------------------------------- frames
if A.lookdev:   # a single lazy S of yarn across the frame, camera square on, focus on it
    R0 = 0.36; xs = np.linspace(-9, 9, 120)
    D["frames"] = [{"t": 0, "hook": {"pos": [0, 500, 0], "quat": [0, 0, 0, 1]},
                    "strands": [{"visible": True, "closed": False, "radius": R0, "accent": False,
                                 "pts": [[x, 0.9 * math.sin(x * 0.35), 0.6 * math.cos(x * 0.5)] for x in xs]}]}]
    cam.location = to_bl((1.5, 2.0, 11.0)); tgt = to_bl((1.5, 0.3, 0)); cd.lens = 100
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler(); cam_fwd = (tgt - cam.location).normalized()
    cd.dof.aperture_fstop = 32; hook.hide_render = True; A.zoom = 2
nF = len(D["frames"]); FPS_ = int(D.get("fps", 24))
HELD_LEN = held_lengths()                                       # the working yarn's held length (yarn_coords)
a, b_, st_ = (A.frames.split(":") + ["", "", ""])[:3]
f0 = int(a or 0); f1 = int(b_ or -1); f1 = nF if f1 < 0 else min(nF, f1 + 1); step = int(st_ or 1)
import time, shutil
MOVING = bool(CAM.get("moving")) and not A.lookdev          # the guided view: camera per frame
prev = None                                                 # (pose key, path) of the last frame rendered
for fi in range(f0, f1, step):
    path = os.path.join(A.out, "f_%04d.png" % fi)
    t0 = time.time(); fr = D["frames"][fi]
    akey = (fr.get("a"), json.dumps(fr["cam"]) if MOVING and "cam" in fr else None)   # pose + camera
    if A.skip_existing and os.path.exists(path): prev = (akey, path); continue
    if prev and "a" in fr and prev[0] == akey:
        shutil.copyfile(prev[1], path)                      # same pose seen from the same place: same picture
        print("frame %d/%d  copied" % (fi, nF - 1), flush=True); continue
    if MOVING and "cam" in fr:
        P = Vector(fr["cam"]["pos"]); T = Vector(fr["cam"]["target"])
        cam.location = to_bl(T + (P - T) * k); tgt = to_bl(T)
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler(); cam_fwd = (tgt - cam.location).normalized()
        if "turn" in fr["cam"]:
            # the guided view keeps its angle and the work turns in front of it (choreo.py turn_of): the same
            # picture as the camera, its roll, its lights, environment and floor all swung by that turn
            tx, ty, tz, tw = fr["cam"]["turn"]; Qb = CQ @ Quaternion((tw, tx, ty, tz)) @ CQ.inverted()
            d0 = Qb.inverted() @ (cam.location - tgt)
            cam.rotation_euler = (Qb @ (-d0).to_track_quat("-Z", "Y")).to_euler()
            for ob_, p0, q0 in RIG: ob_.location = Qb @ p0; ob_.rotation_euler = (Qb @ q0).to_euler()
            if ENV_MAP: ENV_MAP.inputs["Rotation"].default_value = (Matrix.Rotation(math.radians(110), 3, "Z") @ Qb.inverted().to_matrix()).to_euler("XYZ")
    hook.location = to_bl(fr["hook"]["pos"])
    qx, qy, qz, qw = fr["hook"]["quat"]
    hook.rotation_quaternion = CQ @ Quaternion((qw, qx, qy, qz)) @ CQ.inverted()
    set_yarn(fr); set_hands(fr); t1 = time.time()
    # focus on the hook head (the tip sits at the hook's origin)
    # focus: on the hook head, but averaged over a second around this frame. Following it frame by frame moved
    # the focus plane every frame, and the whole work's fibres sharpened and softened with it (a shimmer)
    hw = [to_bl(D["frames"][j]["hook"]["pos"]) for j in range(max(0, fi - FPS_ // 2), min(nF, fi + FPS_ // 2 + 1))]
    hk_avg = sum(hw, Vector()) / len(hw)
    cd.dof.focus_distance = max(0.05, ((hk_avg if A.zoom == 1 else tgt) - cam.location).dot(cam_fwd))
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    prev = (akey, path)
    print("frame %d/%d  %.1fs (build %.1fs)" % (fi, nF - 1, time.time() - t0, t1 - t0), flush=True)
