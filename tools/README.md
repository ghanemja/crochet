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

## Stitch tutorials (`assets/tutorials/<key>.webm|.mp4|.jpg`)

The **Learn this stitch** modal plays a pre-rendered video when one exists for
the stitch and the yarn is the default Rose wool (`TUTORIAL_YARN` in
`index.html`); otherwise — or if the file fails to load — it falls back to the
live three.js scene. The scrubber, step list and loop readout follow
`video.currentTime` (`learnSyncUI`, `learnReadoutAt`).

Both routes need the repo served on :8765 (`python3 -m http.server 8765`) and
Playwright's Chromium.

**Route A — capture the live scene** (fallback quality, ~2.5 s/frame on CPU):

```bash
node tools/capture_tutorials.mjs [keys...]    # 1280×800 @ 30 fps -> assets/tutorials/
```

**Route B — Cycles render** of the same choreography:

```bash
node tools/export_paths.mjs [keys...]         # build/paths/<key>.json (exportLearnPaths in index.html)
curl -o build/hdri/studio_small_09_2k.hdr \
  https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/studio_small_09_2k.hdr   # CC0, optional
BLENDER=/path/to/blender OUT=assets/tutorials tools/render_all.sh "sc:30 dc:30 ch:15 ..."
```

`render_tutorial.py` rebuilds every strand per frame as hair curves — three
twisted plies, spun fibres around each ply, flyaways anchored by arc length —
with an HDRI + area lights, a 100 mm lens with f/4 depth of field focused on
the hook, a shadow-catcher floor and transparent film; `encode_tutorial.sh`
composites onto the cream stage and encodes (two-pass VP9 aimed at ~1.35 MB,
H.264 MP4 for Safari, poster at 80%). Defaults (800×500, 16 samples +
OpenImageDenoise, no subsurface) take ~13 s/frame on 4 CPU cores; `key:15`
renders every other frame. Rendering is resumable (`--skip-existing`).
