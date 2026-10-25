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
ap.add_argument("--fstop", type=float, default=4.0)
ap.add_argument("--skip-existing", action="store_true")
ap.add_argument("--fibres", type=int, default=7)          # spun fibres per ply (0 = plies only)
ap.add_argument("--sss", type=float, default=0.0)          # subsurface doubles the frame time on CPU
ap.add_argument("--bounces", type=int, default=6)
ap.add_argument("--view", default="AgX")
ap.add_argument("--exposure", type=float, default=0.0)
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
sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = A.view
if A.view == "AgX": sc.view_settings.look = "AgX - Punchy"
sc.view_settings.exposure = A.exposure
sc.cycles_curves.shape = "THICK"
sc.cycles_curves.subdivisions = 2

world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
wn = world.node_tree.nodes; wl = world.node_tree.links
bg = wn["Background"]
if os.path.exists(A.hdri):
    env = wn.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(os.path.abspath(A.hdri))
    mp = wn.new("ShaderNodeMapping"); tc = wn.new("ShaderNodeTexCoord")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(110))
    wl.new(tc.outputs["Generated"], mp.inputs["Vector"]); wl.new(mp.outputs["Vector"], env.inputs["Vector"])
    wl.new(env.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 0.35
else:
    print("no HDRI at", A.hdri, "- using a flat warm environment")
    bg.inputs["Color"].default_value = (0.85, 0.8, 0.74, 1); bg.inputs["Strength"].default_value = 0.8

# key: big soft area light up and to the left (matches the app's key at (8,16,12) mirrored for the long lens)
key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "AREA")); sc.collection.objects.link(key)
key.data.shape = "DISK"; key.data.size = 0.35; key.data.energy = 6; key.data.color = (1.0, 0.95, 0.9)
key.location = to_bl((-14, 18, 16)); key.rotation_euler = (to_bl((0, 0, 0)) - key.location).to_track_quat("-Z", "Y").to_euler()
rim = bpy.data.objects.new("Rim", bpy.data.lights.new("Rim", "AREA")); sc.collection.objects.link(rim)
rim.data.size = 0.2; rim.data.energy = 3; rim.data.color = (1.0, 0.9, 0.8)
rim.location = to_bl((6, 10, -16)); rim.rotation_euler = (to_bl((0, 0, 0)) - rim.location).to_track_quat("-Z", "Y").to_euler()

# floor: shadow catcher. The app's ground (y=-3.4) only draws shadows, so the working
# yarn runs on below it to the ball; a catcher there would cut that strand off.
fm = bpy.data.meshes.new("Floor"); g = -10.0 * S; e = 3.0
fm.from_pydata([(-e, -e, g), (e, -e, g), (e, e, g), (-e, e, g)], [], [(0, 1, 2, 3)])
floor = bpy.data.objects.new("Floor", fm); sc.collection.objects.link(floor); floor.is_shadow_catcher = True

# camera: the app's framing, pulled back along the view line for a long lens
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cd = cam.data; cd.sensor_fit = "VERTICAL"; cd.sensor_height = 24; cd.sensor_width = 24 * W / H; cd.lens = A.lens
vf = 2 * math.atan(12 / A.lens)
P = Vector(D["camera"]["pos"]); T = Vector(D["camera"]["target"])
k = math.tan(math.radians(D["camera"]["fov"]) / 2) / math.tan(vf / 2)
cam.location = to_bl(T + (P - T) * k); tgt = to_bl(T)
cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
cd.dof.use_dof = True; cd.dof.aperture_fstop = A.fstop; cd.dof.aperture_blades = 7
cam_fwd = (tgt - cam.location).normalized()

# ---------------------------------------------------------------- materials
def yarn_mat(name, hexcol, fibre=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links; b = n["Principled BSDF"]
    base = srgb_lin(hexcol)
    hi = n.new("ShaderNodeHairInfo"); ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = [c * 0.78 for c in base[:3]] + [1]
    ramp.color_ramp.elements[1].color = [min(1, c * 1.12 + 0.01) for c in base[:3]] + [1]
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

MAT = {False: (yarn_mat("Yarn", D["yarn"]), yarn_mat("YarnFibre", D["yarn"], True), fuzz_mat("YarnFuzz", D["yarn"])),
       True: (yarn_mat("Accent", D["accent"]), yarn_mat("AccentFibre", D["accent"], True), fuzz_mat("AccentFuzz", D["accent"]))}

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

# ---------------------------------------------------------------- yarn as hair curves
PLIES = 3
def frames_rmf(c, closed):
    """rotation-minimising frames (n, b) along polyline c (N,3)."""
    N = len(c)
    if closed: t = np.roll(c, -1, 0) - np.roll(c, 1, 0)
    else:
        t = np.empty_like(c); t[1:-1] = c[2:] - c[:-2]; t[0] = c[1] - c[0]; t[-1] = c[-1] - c[-2]
    t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-12
    up = np.array([0.0, 1.0, 0.0]) if abs(t[0][1]) < 0.9 else np.array([1.0, 0.0, 0.0])
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

def resample(pts, closed, step):
    p = np.array(pts, float)
    if closed: p = np.vstack([p, p[:1]])
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1); s = np.concatenate([[0], np.cumsum(seg)]); L = s[-1]
    m = max(8, int(L / step) + 1); si = np.linspace(0, L, m)
    q = np.stack([np.interp(si, s, p[:, k]) for k in range(3)], 1)
    if closed: q, si = q[:-1], si[:-1]
    return q, si, L

def rng_at(seed, j):   # cheap deterministic hash -> [0,1)
    x = (seed * 0x9E3779B97F4A7C15 + j * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    x ^= x >> 31; x = (x * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF; x ^= x >> 29
    return (x & 0xFFFFFF) / float(0xFFFFFF)

def strand_curves(si_idx, st):
    """-> dict(kind -> list of (points (n,3) app units, radii (n,)))"""
    R = st["radius"]; closed = st["closed"]
    c, s, L = resample(st["pts"], closed, R * 0.09)
    n, b = frames_rmf(c, closed)
    twist = 2 * math.pi / (R * 4.2)                       # one ply turn per ~4 yarn radii
    if closed: twist = 2 * math.pi * max(1, round(L * twist / (2 * math.pi))) / L
    rp, rply = R * 0.5, R * 0.56
    out = {"ply": [], "fibre": [], "fuzz": []}
    # taper the free ends a touch so cut ends read as yarn, not pipes
    taper = np.ones(len(s)) if closed else np.clip(np.minimum(s, L - s) / (R * 0.8), 0.55, 1)
    F = A.fibres; rf = rply * 0.86; fr = rply * 0.3; ftw = -2 * math.pi / (R * 2.3)
    for k in range(PLIES):
        th = 2 * math.pi * k / PLIES + s * twist
        pc = c + rp * (np.cos(th)[:, None] * n + np.sin(th)[:, None] * b) * taper[:, None]
        out["ply"].append((pc, rply * 0.8 * taper))
        for j in range(F):
            ph = 2 * math.pi * j / F + s * ftw + th
            jit = 1 + 0.06 * np.sin(s / R * (3 + j) + k)
            pf = pc + rf * jit[:, None] * (np.cos(ph)[:, None] * n + np.sin(ph)[:, None] * b) * taper[:, None]
            out["fibre"].append((pf, fr * taper))
    # flyaways: anchored by absolute arc length so they don't swim between frames
    spacing = R * 0.35; seed = 1009 * (si_idx + 1)
    for j in range(int(L / spacing)):
        u = (j + rng_at(seed, j)) * spacing
        if u >= L: break
        r1, r2, r3 = rng_at(seed + 1, j), rng_at(seed + 2, j), rng_at(seed + 3, j)
        i = min(len(s) - 1, int(np.searchsorted(s, u)))
        a = r1 * 2 * math.pi; d = math.cos(a) * n[i] + math.sin(a) * b[i]
        t = c[(i + 1) % len(c)] - c[i - 1]; t /= np.linalg.norm(t) + 1e-12
        ln = R * (0.35 + 1.1 * r2 ** 2)
        lean = (r3 - 0.5) * 1.6
        base = c[i] + d * R * 0.92
        pts = np.array([base + (d * (0.35 + 0.65 * q) + t * lean * q + d * 0.0) * ln * q for q in np.linspace(0, 1, 5)])
        pts[:, :] += np.outer(np.linspace(0, 1, 5) ** 2, np.cross(t, d)) * ln * 0.25 * (r1 - 0.5)
        out["fuzz"].append((pts, np.linspace(R * 0.022, R * 0.008, 5)))
    return out

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

YOBJ = {}
def set_yarn(fr):
    groups = {}
    for i, st in enumerate(fr["strands"]):
        if not st.get("visible") or len(st.get("pts", [])) < 3: continue
        acc = bool(st.get("accent"))
        for kind, items in strand_curves(i, st).items():
            groups.setdefault((acc, kind), []).extend(items)
    for acc in (False, True):
        for ki, kind in enumerate(("ply", "fibre", "fuzz")):
            name = ("Acc_" if acc else "Yarn_") + kind
            old = YOBJ.get(name)
            data = build_curves(name, groups.get((acc, kind), []), MAT[acc][ki])
            if old is None:
                ob = bpy.data.objects.new(name, data); sc.collection.objects.link(ob); YOBJ[name] = ob
            else:
                od = old.data; old.data = data; bpy.data.hair_curves.remove(od)

# ---------------------------------------------------------------- frames
nF = len(D["frames"])
a, b_, st_ = (A.frames.split(":") + ["", "", ""])[:3]
f0 = int(a or 0); f1 = int(b_ or -1); f1 = nF if f1 < 0 else min(nF, f1 + 1); step = int(st_ or 1)
import time
for fi in range(f0, f1, step):
    path = os.path.join(A.out, "f_%04d.png" % fi)
    if A.skip_existing and os.path.exists(path): continue
    t0 = time.time(); fr = D["frames"][fi]
    hook.location = to_bl(fr["hook"]["pos"])
    qx, qy, qz, qw = fr["hook"]["quat"]
    hook.rotation_quaternion = CQ @ Quaternion((qw, qx, qy, qz)) @ CQ.inverted()
    set_yarn(fr); t1 = time.time()
    # focus on the hook head (the tip sits at the hook's origin)
    cd.dof.focus_distance = max(0.05, (hook.location - cam.location).dot(cam_fwd))
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("frame %d/%d  %.1fs (build %.1fs)" % (fi, nF - 1, time.time() - t0, t1 - t0), flush=True)
