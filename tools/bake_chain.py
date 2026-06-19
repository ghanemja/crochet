import bpy, numpy as np, os, math
V=np.array

def plied_ring(center, ulong, ushort, rL, rS, baseR=0.135, plies=3, amp=0.26, twists=4, M=14, nseg=56):
    """Closed plied (twisted) yarn tube around a planar oval. Seam-matched twist."""
    center=V(center,float); ulong=V(ulong,float); ushort=V(ushort,float)
    pn=np.cross(ulong,ushort); pn/=np.linalg.norm(pn)+1e-12
    C=[]
    for i in range(nseg):
        a=2*math.pi*i/nseg
        C.append(center+rL*math.cos(a)*ulong+rS*math.sin(a)*ushort)
    C=np.array(C)
    # arclength
    s=np.zeros(nseg)
    for i in range(1,nseg): s[i]=s[i-1]+np.linalg.norm(C[i]-C[i-1])
    L=s[-1]+np.linalg.norm(C[0]-C[-1])
    twper=twists*2*math.pi/L
    verts=[]
    for i in range(nseg):
        t=C[(i+1)%nseg]-C[(i-1)%nseg]; t/=np.linalg.norm(t)+1e-12
        ax2=pn
        ax1=np.cross(t,pn); ax1/=np.linalg.norm(ax1)+1e-12
        for j in range(M):
            th=2*math.pi*j/M
            rad=baseR*(1.0+amp*math.cos(plies*th - twper*s[i]))
            p=C[i]+rad*(math.cos(th)*ax1+math.sin(th)*ax2)
            verts.append((float(p[0]),float(p[1]),float(p[2])))
    faces=[]
    for i in range(nseg):
        i2=(i+1)%nseg
        for j in range(M):
            j2=(j+1)%M
            faces.append((i*M+j, i*M+j2, i2*M+j2, i2*M+j))
    return verts,faces

def build_chain(nlinks=6, rL=0.6, rS=0.34, step=0.64, top=0.0):
    allv=[]; allf=[]
    Z=V([0,0,1.0]); X=V([1.0,0,0]); Y=V([0,1.0,0])
    for k in range(nlinks):
        cz=top-k*step
        ushort = X if k%2==0 else Y
        v,f=plied_ring((0,0,cz), Z, ushort, rL, rS)
        base=len(allv)
        allv+=v; allf+=[(a+base,b+base,c+base,d+base) for (a,b,c,d) in f]
    return allv,allf

def setup_render(sc):
    cam_d=bpy.data.cameras.new("Cam"); cam=bpy.data.objects.new("Cam",cam_d); sc.collection.objects.link(cam)
    cam.location=(0.0,-7.4,-1.8); cam.rotation_euler=(math.radians(90),0,0); cam_d.lens=60; sc.camera=cam
    ld=bpy.data.lights.new("Sun",'SUN'); ld.energy=4.2
    lo=bpy.data.objects.new("Sun",ld); sc.collection.objects.link(lo); lo.rotation_euler=(math.radians(55),math.radians(12),math.radians(35))
    w=bpy.data.worlds.new("W"); w.use_nodes=True; w.node_tree.nodes["Background"].inputs[1].default_value=0.35; sc.world=w
    sc.render.engine='CYCLES'; sc.cycles.samples=24; sc.cycles.device='CPU'
    sc.render.resolution_x=720; sc.render.resolution_y=720

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc=bpy.context.scene; sc.frame_start=1; sc.frame_end=80; sc.gravity=(0,0,-9.8)
    verts,faces=build_chain()
    me=bpy.data.meshes.new("Chain"); me.from_pydata(verts,[],faces); me.update()
    ob=bpy.data.objects.new("Chain",me); sc.collection.objects.link(ob)
    for f in me.polygons: f.use_smooth=True
    mat=bpy.data.materials.new("Yarn"); mat.use_nodes=True
    b=mat.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value=(0.93,0.55,0.66,1); b.inputs["Roughness"].default_value=0.85
    ob.data.materials.append(mat)
    mode=os.environ.get("CHAIN_MODE","static")
    if mode=="static":
        sub=ob.modifiers.new("sub","SUBSURF"); sub.levels=1; sub.render_levels=1
    setup_render(sc)
    if mode=="bake":
        # gentle pendulum sway of the whole chain (node anim, loops) + softbody
        # secondary jiggle baked to shape keys for natural lag.
        n=len(verts)//(14)            # rings; goal: top firm, bottom loose
        vg=ob.vertex_groups.new(name="goal"); M=14
        per=56  # nseg per ring
        # weight by height (z): higher = firmer
        zs=[verts[i][2] for i in range(len(verts))]
        zmin=min(zs); zmax=max(zs)
        for i in range(len(verts)):
            w=0.3+0.7*((verts[i][2]-zmin)/(zmax-zmin+1e-9))
            vg.add([i], float(w), 'REPLACE')
        md=ob.modifiers.new("soft","SOFT_BODY"); sb=md.settings
        sb.use_goal=True; sb.vertex_group_goal="goal"
        sb.goal_default=0.7; sb.goal_spring=0.9; sb.goal_friction=6
        sb.goal_min=0.25; sb.goal_max=1.0; sb.pull=0.9; sb.push=0.9; sb.bend=5; sb.mass=0.5
        # pendulum: rotate about the top (object origin at top link)
        sc.frame_start=1; sc.frame_end=72
        for fr,ang in [(1,0.0),(18,0.05),(36,0.0),(54,-0.05),(72,0.0)]:
            ob.rotation_euler=(0.0,ang,0.0); ob.keyframe_insert("rotation_euler",frame=fr)
        # bake softbody response to shape keys (flipbook morph)
        ob.shape_key_add(name="Basis",from_mix=False)
        frames=list(range(1,73,4))
        keys=[]
        for fr in frames:
            sc.frame_set(fr)
            dg=bpy.context.evaluated_depsgraph_get(); ev=ob.evaluated_get(dg); ms=ev.to_mesh()
            kb=ob.shape_key_add(name=f"f{fr}",from_mix=False)
            for i,v in enumerate(ms.vertices): kb.data[i].co=v.co.copy()
            keys.append(kb); ev.to_mesh_clear()
        for idx,fr in enumerate(frames):
            for jdx,fr2 in enumerate(frames):
                keys[idx].value=1.0 if idx==jdx else 0.0
                keys[idx].keyframe_insert("value",frame=fr2)
        ob.modifiers.remove(md)   # baked; drop sim modifier
        os.makedirs('/home/user/crochet/assets/baked',exist_ok=True)
        out='/home/user/crochet/assets/baked/chain.glb'
        bpy.ops.export_scene.gltf(filepath=out,export_format='GLB',export_animations=True,export_morph=True,use_selection=False)
        print("baked+exported",os.path.getsize(out),"bytes verts",len(verts))
    elif mode=="export":
        os.makedirs('/home/user/crochet/assets/baked',exist_ok=True)
        out='/home/user/crochet/assets/baked/chain.glb'
        bpy.ops.export_scene.gltf(filepath=out,export_format='GLB',export_animations=False,use_selection=False)
        print("exported",os.path.getsize(out),"bytes verts",len(verts))
    else:
        sc.frame_set(1); sc.render.filepath='/tmp/CH_static.png'
        bpy.ops.render.render(write_still=True)
        print("done verts",len(verts))

main()
