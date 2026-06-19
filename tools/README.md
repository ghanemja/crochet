# tools

Both scripts generate `assets/hand-right.glb` — the organic right hand, posed in
a crochet grip, that `index.html` loads at runtime (`loadHandModel`). The grip is
baked into the mesh, so the model needs no armature and the app's bone-posing is
a harmless no-op. Placement on the hook is controlled by `HAND_CFG` in
`index.html` (the grip opens along the model's local +X; `rot.z = PI/2` lays the
hook shaft through it).

## make_hand.mjs  (used to build the committed asset)

Pure Node — no Blender required. Builds the hand as a marching-cubes isosurface
over metaball "capsules" laid along a finger skeleton.

```bash
npm install three          # creates ./node_modules (git-ignored)
node tools/make_hand.mjs   # writes assets/hand-right.glb (~25k tris)
```

Tune the hand by editing the skeleton near the top: `fingers` (x offset, length,
radius), `dAngs` (per-joint curl), the thumb block, and `SUB` (higher = fingers
stay more separate). Re-run, then re-check placement with `HAND_CFG`.

## make_hand_blender.py  (alternative)

If you'd rather sculpt in Blender, this builds an equivalent hand with the Skin +
Subdivision modifiers and exports the same `assets/hand-right.glb`:

```bash
blender --background --python tools/make_hand_blender.py
```

After regenerating with either script, commit `assets/hand-right.glb`.

## bake_chain.py / bake_row.py  (Blender-baked twisted yarn + cloth drape)

These produce the multi-ply (twisted) yarn fabric the Learn modal loads for
stitches: `assets/baked/chain.glb` (the chain) and `assets/baked/row_{sc,hdc,dc,tr}.glb`
(foundation row + completed posts per stitch). Yarn is a fluted/plied tube; a
goal-based softbody under a gently tilting gravity is baked to morph targets so
the fabric drapes/sways. The clip loops over one sine period; Three.js plays it
on an `AnimationMixer` (chain/row meshes need `material.morphTargets = true`).

Requires Blender as a Python module (no GUI): `pip install bpy` (Python 3.11).

```bash
CHAIN_MODE=render python3 tools/bake_chain.py   # Cycles preview -> /tmp/CH_static.png
CHAIN_MODE=bake   python3 tools/bake_chain.py   # writes assets/baked/chain.glb (drape)
ROW_MODE=render   python3 tools/bake_row.py     # Cycles previews -> /tmp/ROW_{dc,sc}.png
ROW_MODE=export   python3 tools/bake_row.py     # writes assets/baked/row_*.glb (all stitches)
```

The procedural Three.js yarn (working strand, live loops, current post) uses a
matching `pliedTubeGeometry` so everything reads as the same twisted yarn.
Commit the regenerated `assets/baked/*.glb`.
