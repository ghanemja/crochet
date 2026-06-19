// Generates assets/hand-right.glb: an organic right hand posed in a crochet
// grip. The hand is an isosurface (marching cubes) over metaball "capsules"
// laid along a finger skeleton, so it comes out smooth and watertight with the
// grip baked into the mesh (no rig / bone names needed).
//
//   npm install three      # once, anywhere on NODE's path
//   node tools/make_hand.mjs
//
// The grip opens along the model's local +X; index.html lays the hook shaft
// through it via HAND_CFG (rot.z = PI/2). Tris ~25k.
import { Blob } from 'buffer';
// GLTFExporter's binary path expects a browser FileReader; shim it for Node.
globalThis.FileReader = class { readAsArrayBuffer(b){ b.arrayBuffer().then(r=>{ this.result=r; this.onloadend&&this.onloadend(); }); } };
import * as THREE from 'three';
import { MarchingCubes } from 'three/examples/jsm/objects/MarchingCubes.js';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';
import { writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
const OUT = fileURLToPath(new URL('../assets/hand-right.glb', import.meta.url));

const RES=140, ISO=80, SUB=55;          // high subtract => each ball stays local
const balls=[];
const addBall=(x,y,z,R)=>balls.push({x,y,z,R});
function capsule(a,b,ra,rb,n){ for(let i=0;i<=n;i++){const t=i/n;
  addBall(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t, ra+(rb-ra)*t);} }

// ---- palm: flat slab (one main sheet + thin back) ----
for(let xi=-3;xi<=3;xi++) for(let yi=0;yi<=3;yi++){
  const x=0.5+xi*0.030, y=0.40+yi*0.032;
  addBall(x,y,0.50,0.050);
  addBall(x,y,0.47,0.040);
}
capsule([0.5,0.305,0.49],[0.5,0.37,0.49],0.066,0.058,3); // heel/wrist

// ---- fingers: extend, then curl ~135 deg toward palm ----
const fingers=[[0.655,1.00,0.034],[0.580,1.10,0.035],[0.505,1.02,0.034],[0.430,0.84,0.030]];
const dAngs=[0.12,0.40,0.55,0.55,0.45];   // straighter at base, curl toward tip
for(const [fx,ls,br] of fingers){
  let p=[fx,0.53,0.50], dir=[0,1,0], r=br;
  addBall(p[0],p[1],p[2], r*1.15);                  // knuckle
  for(let i=0;i<dAngs.length;i++){
    const a=dAngs[i];
    const ny=dir[1]*Math.cos(a)-dir[2]*Math.sin(a);
    const nz=dir[1]*Math.sin(a)+dir[2]*Math.cos(a);
    dir=[0,ny,nz];
    const ds=0.050*ls;
    const np=[p[0],p[1]+dir[1]*ds,p[2]+dir[2]*ds];
    const r2=br*(1-0.30*(i+1)/dAngs.length);
    capsule(p,np,r,r2,2); p=np; r=r2;
  }
}

// ---- thumb: radial side, angled across to meet fingers ----
{
  let p=[0.665,0.40,0.50], dir=[-0.20,0.78,0.55];
  let L=Math.hypot(...dir); dir=dir.map(d=>d/L);
  let r=0.040; const ds=0.052;
  const tA=[0.10,0.45,0.55,0.45];
  addBall(p[0],p[1],p[2], r*1.15);
  for(let i=0;i<tA.length;i++){
    const a=tA[i];
    const nx=dir[0]*Math.cos(a)-dir[1]*Math.sin(a);
    const ny=dir[0]*Math.sin(a)+dir[1]*Math.cos(a);
    dir=[nx,ny,dir[2]]; const dl=Math.hypot(...dir)||1; dir=dir.map(d=>d/dl);
    const np=[p[0]+dir[0]*ds,p[1]+dir[1]*ds,p[2]+dir[2]*ds*0.5];
    const r2=0.040*(1-0.28*(i+1)/tA.length);
    capsule(p,np,r,r2,2); p=np; r=r2;
  }
}

const mc=new MarchingCubes(RES,new THREE.MeshStandardMaterial(),true,false,300000);
mc.isolation=ISO; mc.init(RES); mc.reset();
for(const b of balls){ const s=(ISO+SUB)*b.R*b.R; mc.addBall(b.x,b.y,b.z,s,SUB); }
mc.update();

const n=mc.count, src=mc.geometry.attributes.position.array;
const pos=new Float32Array(n*3); pos.set(src.subarray(0,n*3));
const geo=new THREE.BufferGeometry();
geo.setAttribute('position',new THREE.BufferAttribute(pos,3));
geo.computeVertexNormals();
geo.computeBoundingBox(); const bb=geo.boundingBox, c=new THREE.Vector3(); bb.getCenter(c);
geo.translate(-c.x,-c.y,-c.z);
const sz=new THREE.Vector3(); bb.getSize(sz);
geo.scale(0.19/Math.max(sz.x,sz.y,sz.z)+0,0.19/Math.max(sz.x,sz.y,sz.z),0.19/Math.max(sz.x,sz.y,sz.z));

const scene=new THREE.Scene();
scene.add(new THREE.Mesh(geo,new THREE.MeshStandardMaterial({color:0xc98a5c,roughness:0.62,metalness:0})));
console.log('balls',balls.length,'tris',(n/3)|0,'size',sz.x.toFixed(3),sz.y.toFixed(3),sz.z.toFixed(3));
new GLTFExporter().parse(scene,g=>{writeFileSync(OUT,Buffer.from(g));console.log('WROTE',OUT,g.byteLength);},
  e=>{console.error(e);process.exit(1);},{binary:true});
