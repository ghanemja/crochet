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
composites onto the cream stage and encodes (two-pass VP9 aimed at ~1.35 MB — `encode_views.sh` holds quality instead, since the fibres smear in motion at that size,
H.264 MP4 for Safari, poster at 80%). Defaults (800×500, 16 samples +
OpenImageDenoise, no subsurface) take ~13 s/frame on 4 CPU cores; `key:15`
renders every other frame. Rendering is resumable (`--skip-existing`).

### Single crochet, choreographed (multi-angle)

`choreo_sc.py` authors the single crochet around a modelled hook (loops snug on
the shaft, yarn overs in the throat, pull-ups through the hole under the V) in
blue fabric / orange working yarn, with four camera angles. Each angle renders
separately and `encode_views.sh` packs them into one 2×2 grid video so they stay
frame-locked; list the stitch in `assets/tutorials/manifest.json` and the Learn
modal shows one tile at a time (drag sideways, arrow keys or the view buttons to
turn).

```bash
python3 tools/choreo_sc.py build/paths/sc_v2.json
for i in 0 1 2 3; do
  blender -b -P tools/render_tutorial.py -- build/paths/sc_v2.json build/frames/sc_v$i --angle $i
done
tools/encode_views.sh sc 30 build/frames/sc_v0 build/frames/sc_v1 build/frames/sc_v2 build/frames/sc_v3
echo '{"sc":{"views":["Front","Left side","Behind","Above"]}}' > assets/tutorials/manifest.json
```

### Hands (guided take)

Realistic hands come from a MakeHuman body: install the MPFB2 extension in Blender
(extensions.blender.org/add-ons/mpfb, CC0 assets) and the CC0
`makehuman_system_assets_cc0.zip` (for a skin texture), then

```bash
blender -b -P tools/make_hands_mpfb.py -- build/hands /path/to/skins/<skin>/<skin>_diffuse.png
python3 tools/choreo_sc.py build/paths/sc_v2.json --cues build/sc.cues.json --hands
```

`make_hands_mpfb.py` poses the right hand in a pencil grip and the left hand holding
the work with its index raised, cuts them out and writes `build/hands/hands.blend` +
`hands.json` (named points such as `index_dip`, which the working yarn runs over).
Without them, `tools/hand_rig.py` (a simple skinned skeleton) stands in.

### Every other stitch (`choreo.py`)

`choreo.py` is the general form of `choreo_sc.py`: a stitch is a spec (`SPECS`) — the new row's
height, the bars a tall stitch wraps round its post, and a program of hook operations grouped
into the app's steps (`STITCH_STEPS` in `index.html`, mirrored here — keep the texts in sync):
`yo_free` (yarn over in front, before inserting), `insert`, `yo_catch`, `pull_up`, `pull_keep`
(slip stitch: the yarn stays in the throat), `yo_front`, `through2`, `through` (all loops). The
state (loops on the hook in yarn order, the post growing under it, stitches made) is simulated op
by op and the yarn rebuilt from it each frame as one path; loops that come off morph segment by
segment into the finished geometry. The guided camera, callouts and stitch numbers are generated
per op in the same style as the single crochet. The magic ring works in a straight "row space"
bent into a circle (the ring strand is the row below; pulling the tail shrinks the circle).

```bash
python3 tools/choreo.py dc build/paths/dc.json --cues assets/tutorials/dc.cues.json --hands   # 24 fps
python3 tools/preview_paths.py build/paths/dc.json build/preview/dc.png --every 24          # line-drawing contact sheet, no Blender
blender -b -P tools/render_tutorial.py -- build/paths/dc.json build/frames/dc_v0 --angle 0 --skip-existing
tools/encode_views.sh dc 24 build/frames/dc_v0          # one view -> 1x1 dc.views.*; four -> the 2x2 grid
```

The studio's live hook in `index.html` runs the same op programs (`STITCH_OPS`, posed with the same
keypoints in `choreoAt`), so a change to `SPECS` belongs there too.

Then list it in `assets/tutorials/manifest.json`, e.g. `"dc": {"views": ["Guided"], "grid": [1, 1], "cues": true}`.
The paths JSON carries all four cameras, so the fixed angles can be rendered later (`--angle 1..3`)
and the stitch re-encoded as a 2×2 grid without re-running the choreography. The renderer copies a
frame instead of rendering it when the pose and camera match the previous one (holds).
