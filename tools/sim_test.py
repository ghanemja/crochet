import bpy, bmesh, numpy as np, os
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc=bpy.context.scene; sc.frame_start=1; sc.frame_end=60
    sc.gravity=(0,0,-9.8)
reset()
sc=bpy.context.scene
# --- hook: a vertical-ish cylinder as a collision object ---
bpy.ops.mesh.primitive_cylinder_add(radius=0.42, depth=10, location=(0,0,3))
hook=bpy.context.active_object; hook.name="Hook"
hook.modifiers.new("col","COLLISION")
hook.collision.thickness_outer=0.1
# --- yarn: a long thin subdivided cylinder lying horizontally ABOVE the hook ---
bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=14, location=(0,0,1.2), rotation=(0,1.5708,0))
yarn=bpy.context.active_object; yarn.name="Yarn"
# subdivide along length for flexibility
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
for _ in range(4): bpy.ops.mesh.subdivide()
bpy.ops.object.mode_set(mode='OBJECT')
# pin the two ends: vertex group "pin"
vg=yarn.vertex_groups.new(name="pin")
ends=[i for i,v in enumerate(yarn.data.vertices) if abs(v.co.x)>6.5]
vg.add(ends,1.0,'REPLACE')
# cloth physics (good for yarn drape)
cl=yarn.modifiers.new("cloth","CLOTH").settings
cl.vertex_group_mass="pin"   # pinned group
cl.mass=0.2; cl.tension_stiffness=15; cl.bending_stiffness=2
yarn.modifiers["cloth"].collision_settings.distance_min=0.05
# --- bake the sim to shape keys (flipbook) so glTF can carry it ---
dg=bpy.context.evaluated_depsgraph_get()
yarn.shape_key_add(name="Basis", from_mix=False)  # frame-independent basis
nframes=list(range(1,61,3))
for fr in nframes:
    sc.frame_set(fr)
    dg=bpy.context.evaluated_depsgraph_get()
    ev=yarn.evaluated_get(dg); me=ev.to_mesh()
    kb=yarn.shape_key_add(name=f"f{fr}", from_mix=False)
    for i,v in enumerate(me.vertices): kb.data[i].co=v.co.copy()
    ev.to_mesh_clear()
# animate shape keys as a flipbook (each key peaks on its frame)
keys=yarn.data.shape_keys.key_blocks
for idx,fr in enumerate(nframes):
    kb=keys[idx+1]
    for jdx,fr2 in enumerate(nframes):
        kb.value=1.0 if jdx==idx else 0.0
        kb.keyframe_insert("value", frame=fr2)
# report displacement of a middle vertex between first and last key
mid=len(yarn.data.vertices)//2
d=(np.array(keys[-1].data[mid].co)-np.array(keys[1].data[mid].co))
print("mid-vertex drop over sim:", round(float(np.linalg.norm(d)),3))
out="/home/user/crochet/assets/baked/drape_test.glb"
# remove cloth modifier before export (we baked to shape keys)
yarn.modifiers.remove(yarn.modifiers["cloth"])
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_animations=True, export_morph=True, use_selection=False)
print("exported", os.path.getsize(out), "bytes ; shape keys:", len(keys))
