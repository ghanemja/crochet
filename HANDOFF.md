# HANDOFF — pre-rendered stitch tutorials

Goal: replace the live WebGL animation in the **Learn this stitch** modal with
pre-rendered videos (one per stitch) so the tutorials can have offline-render
quality — the look of the "Houdini-Level Yarn in Blender 3D" tutorial: bevelled
strands twisted together, hair fibres, HDRI lighting, long lens with shallow
depth of field. The live 3D scene stays as the fallback.

Deliver **Route A first** (safety net, ~20 min of compute), then **Route B**
(the real goal, hours of CPU render — run it in the background).

---

## Repo orientation

- Single-page app, everything in `index.html` (~4100 lines, one `<script>`).
  three.js r128 is vendored in `vendor/three/`. No build step; serve with any
  static server (`python3 -m http.server 8765`).
- Deploys: GitHub Pages from `main` via `.github/workflows/pages.yml`.
  Branch `claude/crochet-pattern-animator-LoKad` is kept identical to `main`;
  push to both (`git push origin HEAD:claude/crochet-pattern-animator-LoKad HEAD:main`).
- `assets/yarn/` — CC0 rope PBR maps (ambientCG Rope001). `assets/hand-right.glb` — hand model.
- `tools/` — Blender/Node scripts already used to generate assets
  (`make_hand_blender.py` shows how we drive `bpy` headless; `README.md` there).
- `.gitignore` ignores `node_modules/`, `/package.json`, `_*.mjs` (a puppeteer
  harness convention: name your local capture script `_capture.mjs` or commit it
  under `tools/` instead).

### Learn scene internals (all in `index.html`)

| What | Where |
|---|---|
| Modal markup: `#learnModal`, `#learnCanvas`, `#learnReadout`, `#learnScrub`, `#learnSteps` | ~line 888 |
| Step text per stitch: `STITCH_STEPS` (ch, sl, sc, hdc, dc, tr, inc, dec, mr) | ~977 |
| Seconds per written step: `STEP_DUR = 2.6` | ~2671 |
| Scene setup: `initLearn3D()`, `buildLearnScene(key)` | ~2674, ~2909 |
| Per-frame choreography: `animateLearn3D()` — reads `Learn.t` (seconds), sets hook pose and rebuilds every strand | ~3000 |
| Step → hand acts: `stepActs(text)`, loop-stack simulation `simulateActs(acts, upto)` | ~2961, ~2977 |
| Strand builders: `setTube(mesh, pts, closed, radius)` (yarn from a point list), `chainPts`, `postPts`, `postWraps`, `ringPts` | ~2890–2995 |
| Yarn geometry/material: `yarnGeometry` (plies + fibres), `yarnMesh`, `makeYarnMaterial` | ~1677–1940 |
| Open / play: `openLearn(key)`, `learnLoop(ts)`, `setLearnPlaying(on)`, `learnTotal()` | ~3143–3330 |

Key facts for capture/export:
- Total tutorial length = `STITCH_STEPS[key].length * STEP_DUR` seconds (sc = 13 s, dc = 13 s, tr = 15.6 s, ch = 5.2 s).
- The animation is a pure function of `Learn.t`: set `Learn.t = x; animateLearn3D(); L3.renderer.render(L3.scene, L3.camera);` renders that instant. No simulation state to warm up.
- Working strand and loops made from it render in an accent colour (`L3.newMat`, hue +0.45 from the yarn colour); existing fabric in the yarn colour (`L3.yarnMat`). Keep this two-colour convention in the renders — it's what makes the motion readable.
- Default yarn: colour `#e0608a` (Rose), type `wool`. Render in these defaults.
- Every strand is a `THREE.Mesh` in `L3.scene` built from a point list through `setTube`. For Route B, export those point lists per frame (see below) rather than the mesh.
- `YR = 0.36` is the yarn radius in the Learn scene; hook shaft radius `HOOK_HALF = 0.42`; camera is a 24° lens set in `buildLearnScene` (position depends on stitch height `tall`).

Studio performance notes (not needed for the tutorials, but don't regress them):
`STUDIO_TRI_BUDGET` (~1565) adapts via a frame-rate probe and persists in
`localStorage["yf_tri_budget"]`. The browser pane used for testing reported a
phone-class GPU; measure with GPU sync (`gl.readPixels` after render), not
`performance.now()` around `render()`.

---

## Route A — capture the live scene (fast fallback)

1. `npm install puppeteer` (local, git-ignored). Serve the repo on a port.
2. Script (`tools/capture_tutorials.mjs`): for each key in `ch sl sc hdc dc tr inc dec mr`:
   - open `http://localhost:8765/`, wait for `YarnTex.ready === true`.
   - set the canvas to 1280×800 CSS px with `devicePixelRatio = 2` (`page.setViewport` + `deviceScaleFactor`).
   - `openLearn(key); setLearnPlaying(false);`
   - override detail for quality: in `learnMkMesh` the strands use `fibres: 6`; before building, you may bump by redefining `learnMkMesh` to pass `{fibres: 9, radial: 14}` and call `buildLearnScene(key)` again.
   - for `t` in `0 … learnTotal()` step `1/30`: `Learn.t = t; animateLearn3D(); L3.renderer.render(L3.scene, L3.camera);` then `page.screenshot({clip: canvasRect})` or `canvas.toDataURL()` (Learn renderer is created with `alpha:true` and no `preserveDrawingBuffer`; render and read in the same evaluate call, or recreate the renderer with `preserveDrawingBuffer:true`).
3. Encode with ffmpeg: `-framerate 30 -i f_%04d.png -c:v libvpx-vp9 -b:v 0 -crf 32 -pix_fmt yuv420p out.webm` and an H.264 MP4 (`-c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart`). Poster = frame at `t = 0.8 × total`.
4. Output to `assets/tutorials/<key>.webm|.mp4|.jpg`. The `.jpg` is also the stitch's thumbnail in the studio's "Watch it up close" card and on the Learn stitches page; `tr`, `inc`, `dec` and `mr` have small 320×200 stand-in posters until their videos exist (keep the 16:10 aspect). Target ≤ 1.5 MB per WebM. Do **not** ship GIFs as the primary format (10–30 MB each); if a GIF is wanted for sharing, make a 480-px-wide 15 fps one with a palette (`palettegen`/`paletteuse`) and keep it out of the app.

## Route B — Cycles render (the real goal)

### 1. Export strand paths from the app
Add (and commit) an export helper in `index.html`, e.g. `exportLearnPaths(key, fps=30)`:
- `openLearn(key); setLearnPlaying(false);`
- for each frame: `Learn.t = i/fps; animateLearn3D();` then walk `L3.scene` and, for every mesh built by `setTube`, record the point list that produced it. Easiest: have `setTube` stash `mesh.userData.pts = pts.map(v => [v.x, v.y, v.z]); mesh.userData.closed = closed; mesh.userData.radius = radius; mesh.userData.accent = (mesh.material === L3.newMat);` and read that back. Also record the hook: `L3.hook.position`, `L3.hook.quaternion`, and the camera (`L3.camera.position`, `L3.controls.target`, fov).
- JSON per stitch: `{ key, fps, frames: [ { t, hook: {pos, quat}, strands: [ {pts, closed, radius, accent} ] } ], camera: {...}, steps: STITCH_STEPS[key], stepDur: STEP_DUR }`.
- Strand identity is stable by index within `L3.rings` / `L3.fabric` / `L3.work`, so a Blender curve can be updated per frame rather than recreated.

### 2. Blender scene (`tools/render_tutorial.py`, run with `blender -b -P … -- stitch.json out_dir`)
Follow the tutorial's recipe with the exported paths as the driving curves:
- For each strand: a Bezier/poly curve from `pts` (closed if `closed`), `bevel_depth = radius`, caps on, resolution high; **three duplicated, offset copies twisted together** (Simple Deform Twist ≈ 5000° per the tutorial, or build the twist directly in the curve data) — this is the "yarn" instead of a smooth tube. Convert to mesh per frame, or keep as curves and animate control points with keyframes from the JSON.
- Particle hair on the yarn mesh (short, sparse, a little clumping/roughness) for flyaways.
- Material: Principled with sheen, subsurface or translucent mix for the fibre glow; per-strand slight hue offset via a ColorRamp (yarn `#e0608a`; accent = same hue +0.45). 
- Lighting: an HDRI environment (any CC0 studio HDRI from Poly Haven, 2K is enough) plus one area light off to the side; cream background matching the app (`#f3ece3`), or a high-roughness glass plane behind the subject for the soft-background trick.
- Camera: match the app's camera from the JSON, long lens (85–135 mm equivalent), low f-stop DOF focused on the hook head.
- Hook: a simple cylinder + hooked head is fine (see `makeCrochetHook` for proportions: shaft radius 0.42, length ~14 units, head lip 0.6 × shaft radius).

### 3. Render settings for CPU in the cloud
- Cycles, CPU, 720p (1280×720), 64–96 samples, OpenImageDenoise on, motion blur off, hair as curves.
- Expect 10–20 s/frame → 9 stitches × ~400 frames ≈ 3–6 h. Run in the background; render `sc` and `dc` first (most used) and check a single frame before committing to the batch.
- EEVEE needs a GPU/OpenGL context and will not work headless in the cloud container; don't try.

### 4. Encode
Same ffmpeg settings as Route A; same output paths `assets/tutorials/<key>.{webm,mp4,jpg}`.

---

## App integration (either route)

In the Learn modal:
- If `assets/tutorials/<key>.webm` (or `.mp4`) exists (preload with `fetch(..., {method:"HEAD"})` on hover of "Learn this stitch", or just attempt and fall back on error), show a `<video>` in place of `#learnCanvas`, same size/aspect (16:10), `playsinline muted loop`.
- Drive the existing UI from the video: `#learnScrub` ↔ `video.currentTime / video.duration`; `#learnSteps` highlight = `Math.floor(video.currentTime / STEP_DUR)`; `#learnReadout` from `stepActs`/`simulateActs` as today (compute from `t = video.currentTime`).
- Keep the live 3D path: if the video fails to load, or the user's yarn colour is not Rose (videos are rendered in one colour), fall back to `buildLearnScene` + `learnLoop` exactly as now. Optional: render a second colourway later.
- Keep `openLearn` / `closeLearn` signatures; other code calls them (`learnNowBtn`, glossary).

## Acceptance

- `sc` and `dc` tutorials play as video in the modal, scrubber and step list stay in sync, falls back to live 3D when the file is missing.
- All 9 stitches rendered (Route A at minimum), each WebM ≤ 1.5 MB, MP4 present for Safari, poster JPG present.
- No console errors; the studio (non-tutorial) still builds and the perf probe still works.
- Commit assets + code to the branch and `main`; Pages deploys from `main`.

## Pitfalls seen so far

- The Claude browser pane caches `index.html` aggressively — append `?v=N` when reloading.
- The Learn renderer is only sized when the modal opens (`fitLearn3D`); set viewport before `openLearn`.
- `animateLearn3D` recreates strand geometry every frame (fine for capture, slow if you also leave the studio animating — pause the studio with `pause()` first).
- Hook pivots about the live loop (`anchor`) each frame; the hook's rest direction is `HOOK_DIR`. Export the hook pose, don't recompute it.
