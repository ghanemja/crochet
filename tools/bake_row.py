import bpy, numpy as np, os, math
V=np.array

def rmf(P):
    P=np.asarray(P,float); n=len(P)
    T=np.zeros_like(P)
    T[1:-1]=P[2:]-P[:-2]; T[0]=P[1]-P[0]; T[-1]=P[-1]-P[-2]
    T/=np.linalg.norm(T,axis=1,keepdims=True)+1e-12
    Nn=np.zeros_like(P); Bn=np.zeros_like(P)
    up=V([0,0,1.0]);
    if abs(float(T[0]@up))>0.9: up=V([1.0,0,0])
    Nn[0]=np.cross(up,T[0]); Nn[0]/=np.linalg.norm(Nn[0])+1e-12; Bn[0]=np.cross(T[0],Nn[0])
    for i in range(n-1):
        v1=P[i+1]-P[i]; c1=float(v1@v1)+1e-12
        rL=Nn[i]-(2/c1)*float(v1@Nn[i])*v1; tL=T[i]-(2/c1)*float(v1@T[i])*v1
        v2=T[i+1]-tL; c2=float(v2@v2)+1e-12
        Nn[i+1]=rL-(2/c2)*float(v2@rL)*v2; Nn[i+1]/=np.linalg.norm(Nn[i+1])+1e-12
        Bn[i+1]=np.cross(T[i+1],Nn[i+1])
    return T,Nn,Bn

def plied_ring(center, ulong, ushort, rL, rS, baseR=0.135, plies=3, amp=0.26, twists=3, M=10, nseg=36):
    center=V(center,float); ulong=V(ulong,float); ushort=V(ushort,float)
    pn=np.cross(ulong,ushort); pn/=np.linalg.norm(pn)+1e-12
    C=[center+rL*math.cos(2*math.pi*i/nseg)*ulong+rS*math.sin(2*math.pi*i/nseg)*ushort for i in range(nseg)]
    C=np.array(C); s=np.zeros(nseg)
    for i in range(1,nseg): s[i]=s[i-1]+np.linalg.norm(C[i]-C[i-1])
    L=s[-1]+np.linalg.norm(C[0]-C[-1]); twper=twists*2*math.pi/L
    verts=[]
    for i in range(nseg):
        t=C[(i+1)%nseg]-C[(i-1)%nseg]; t/=np.linalg.norm(t)+1e-12
        ax1=np.cross(t,pn); ax1/=np.linalg.norm(ax1)+1e-12
        for j in range(M):
            th=2*math.pi*j/M; rad=baseR*(1.0+amp*math.cos(plies*th-twper*s[i]))
            p=C[i]+rad*(math.cos(th)*ax1+math.sin(th)*pn); verts.append((float(p[0]),float(p[1]),float(p[2])))
    faces=[]
    for i in range(nseg):
        i2=(i+1)%nseg
        for j in range(M):
            j2=(j+1)%M; faces.append((i*M+j,i*M+j2,i2*M+j2,i2*M+j))
    return verts,faces

def plied_strand(P, baseR=0.135, plies=3, amp=0.26, twists=3, M=10):
    P=np.asarray(P,float); n=len(P); T,Nn,Bn=rmf(P)
    s=np.zeros(n); s[1:]=np.cumsum(np.linalg.norm(np.diff(P,axis=0),axis=1))
    L=s[-1]+1e-9; twper=twists*2*math.pi/L
    verts=[]
    for i in range(n):
        for j in range(M):
            th=2*math.pi*j/M; rad=baseR*(1.0+amp*math.cos(plies*th-twper*s[i]))
            p=P[i]+rad*(math.cos(th)*Nn[i]+math.sin(th)*Bn[i]); verts.append((float(p[0]),float(p[1]),float(p[2])))
    faces=[]
    for i in range(n-1):
        for j in range(M):
            j2=(j+1)%M; faces.append((i*M+j,i*M+j2,(i+1)*M+j2,(i+1)*M+j))
    return verts,faces

def add(allv,allf,v,f):
    base=len(allv); allv+=v; allf+=[tuple(x+base for x in fc) for fc in f]

def build_row(postH, nfound=7, foundStep=0.48, nposts=2, postStep=0.62, bars=0):
    allv=[]; allf=[]
    Z=V([0,0,1.]); X=V([1.,0,0]); Y=V([0,1.,0])
    # foundation row: interlocking chain links along X at z=0
    for k in range(nfound):
        cx=(k-(nfound-1)/2)*foundStep
        ushort = Z if k%2==0 else Y
        v,f=plied_ring((cx,0,0), X, ushort, foundStep*0.62, 0.20); add(allv,allf,v,f)
    # completed posts rising +Z, with a top V-loop (the stitch you insert into)
    for s in range(1,nposts+1):
        px=-s*postStep
        pts=[V([px,0,0.02]),V([px,0.12,postH*0.5]),V([px,0,postH])]
        v,f=plied_strand(pts); add(allv,allf,v,f)
        # bars (yarn-overs) for taller stitches
        for bsi in range(bars):
            bz=postH*(0.35+0.4*bsi/max(1,bars))
            v2,f2=plied_strand([V([px-0.12,0.06,bz]),V([px+0.12,0.06,bz])],baseR=0.1); add(allv,allf,v2,f2)
        # top loop: small oval lying flat (X-Y) at the top of the post
        v3,f3=plied_ring((px,0,postH+0.04), X, Y, 0.22, 0.13, baseR=0.115, twists=2); add(allv,allf,v3,f3)
    return allv,allf

def setup_render(sc, cx, cz):
    cam_d=bpy.data.cameras.new("Cam"); cam=bpy.data.objects.new("Cam",cam_d); sc.collection.objects.link(cam)
    cam.location=(cx,-6.0,cz); cam.rotation_euler=(math.radians(90),0,0); cam_d.lens=52; sc.camera=cam
    ld=bpy.data.lights.new("Sun",'SUN'); ld.energy=4.2
    lo=bpy.data.objects.new("Sun",ld); sc.collection.objects.link(lo); lo.rotation_euler=(math.radians(55),math.radians(12),math.radians(35))
    w=bpy.data.worlds.new("W"); w.use_nodes=True; w.node_tree.nodes["Background"].inputs[1].default_value=0.35; sc.world=w
    sc.render.engine='CYCLES'; sc.cycles.samples=20; sc.cycles.device='CPU'
    sc.render.resolution_x=760; sc.render.resolution_y=640

def make(key, h, bars):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc=bpy.context.scene; sc.frame_start=1; sc.frame_end=60; sc.gravity=(0,0,-9.8)
    postH=(h+1.7)/2.0
    verts,faces=build_row(postH,bars=bars)
    me=bpy.data.meshes.new("Row"); me.from_pydata(verts,[],faces); me.update()
    ob=bpy.data.objects.new("Row",me); sc.collection.objects.link(ob)
    for f in me.polygons: f.use_smooth=True
    mat=bpy.data.materials.new("Yarn"); mat.use_nodes=True
    b=mat.node_tree.nodes.get("Principled BSDF"); b.inputs["Base Color"].default_value=(0.93,0.55,0.66,1); b.inputs["Roughness"].default_value=0.85
    ob.data.materials.append(mat)
    mode=os.environ.get("ROW_MODE","render")
    if mode=="render":
        sc.frame_set(1); setup_render(sc,-0.3,postH*0.5); sc.render.filepath=f'/tmp/ROW_{key}.png'
        bpy.ops.render.render(write_still=True); print("rendered",key,"verts",len(verts)); return
    # ---- bake a gentle drape (softbody-goal + tilting gravity) to morph keys ----
    n=len(verts)
    vg=ob.vertex_groups.new(name="goal")
    zs=[verts[i][2] for i in range(n)]; zmin=min(zs); zmax=max(zs)
    for i in range(n):
        w=0.4+0.6*((verts[i][2]-zmin)/(zmax-zmin+1e-9))   # post tops firm, foundation looser
        vg.add([i], float(w), 'REPLACE')
    md=ob.modifiers.new("soft","SOFT_BODY"); sb=md.settings
    sb.use_goal=True; sb.vertex_group_goal="goal"
    sb.goal_default=0.6; sb.goal_spring=0.8; sb.goal_friction=6
    sb.goal_min=0.35; sb.goal_max=1.0; sb.mass=0.5; sb.bend=7; sb.pull=0.95; sb.push=0.95
    end=48; sc.frame_start=1; sc.frame_end=end
    cap=list(range(1,end+1,4)); poses=[]
    for fr in range(1,end+1):
        ang=0.10*math.sin(2*math.pi*(fr-1)/end)
        sc.gravity=(9.8*math.sin(ang),0.0,-9.8*math.cos(ang)); sc.frame_set(fr)
        if fr in cap:
            dg=bpy.context.evaluated_depsgraph_get(); ev=ob.evaluated_get(dg); ms=ev.to_mesh()
            poses.append([(v.co.x,v.co.y,v.co.z) for v in ms.vertices]); ev.to_mesh_clear()
    ob.modifiers.remove(md)
    ob.shape_key_add(name="Basis",from_mix=False); kbs=[]
    for idx,fr in enumerate(cap):
        kb=ob.shape_key_add(name=f"f{fr}",from_mix=False); P=poses[idx]
        for i in range(n): kb.data[i].co=P[i]
        kbs.append(kb)
    for idx,fr in enumerate(cap):
        for jdx,fr2 in enumerate(cap):
            kbs[idx].value=1.0 if idx==jdx else 0.0; kbs[idx].keyframe_insert("value",frame=fr2)
    sc.frame_start=cap[0]; sc.frame_end=cap[-1]
    os.makedirs('/home/user/crochet/assets/baked',exist_ok=True)
    out=f'/home/user/crochet/assets/baked/row_{key}.glb'
    bpy.ops.export_scene.gltf(filepath=out,export_format='GLB',export_animations=True,export_morph=True,use_selection=False)
    print("baked",key,os.path.getsize(out),"bytes verts",n)

ROW=os.environ.get("ROW_MODE","render")
if ROW=="render":
    make("dc",2.1,1)
    make("sc",1.0,0)
else:
    for key,h,bars in [("sc",1.0,0),("hdc",1.5,1),("dc",2.1,1),("tr",2.8,2)]:
        make(key,h,bars)
