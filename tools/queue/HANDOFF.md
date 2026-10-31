# Stitch tutorial renders — handoff

You're rendering the pre-made 3D stitch tutorials in this repo. Commit and push to `main` as each
stitch finishes (`git pull --rebase origin main` first). Another session redesigns the app UI in
`index.html` at the same time: **don't edit `index.html`**. Touch only `assets/tutorials/`,
`tools/` and `.gitignore`.

## Goal
For every stitch key `ch sl sc hdc dc tr inc dec mr`, `assets/tutorials/` gets
`<key>.views.webm|.mp4|.jpg` + `<key>.cues.json`, listed in `assets/tutorials/manifest.json`:
```json
{ "sc": { "views": ["Guided", "Front", "Side", "Behind"], "grid": [2, 2], "cues": true } }
```
A single-angle video is `"views": ["Guided"], "grid": [1, 1]`. Only list stitches whose files are
committed. Plan: sc gets all 4 angles; the others the Guided view only, at 24 fps.
`tools/queue/publish.sh` writes the files and the manifest entry for you.

## Where things stand (2026-10-28 15:00 UTC)
- **Rendering now**: sc Side/Behind (`sc_v2..3`), then sc Guided (`sc_v0`) from scratch with the
  second-pass nails (item 11), then ch sl hdc dc tr inc dec mr (Guided, 24 fps). sc Front (`sc_v1`)
  is done (rendered with the paths from before item 10: its hook's thumb-rest flat differs slightly). The sc Guided video on main (`e4e04c5`) is an older take; the publisher replaces it.
- User feedback reaches this session relayed by the session the user follows
  (`session_01Ay6331HA75Zgi2RxDMTWXS`); send it the commit, frame numbers and close-up specs and it
  renders and shows them. Files sent from here don't reach the user.
- **All paths and cues are final** in `build/paths/<key>.json` + `<key>.cues.json` (git-ignored;
  regenerate with the Setup loop in a fresh container). Don't change choreo/hands without
  restarting the affected renders (see the queue section).
- Measured speed: ~45–60 s/frame for the Guided view with hands (close-ups), less for the fixed
  views.
- Settings approved by the user (all in git): opaque cream stage, no shadow-catcher floor, matte
  flyaways, constant-quality encoding, tripod right-hand grip, a hook that turns before the stitch,
  slides in and out along its shaft and goes well out the back, less waxy skin.

## Done in this session (the two issues the user raised, and what came out of checking them)
1. **Left hand physics.** `make_hands_mpfb.py` now exports the pinch pads and the whole rendered
   skin (`_verts`/`_normals` in `hands.json`). `choreo.py` places the left hand by its pads on the
   work's two faces along `L_AXIS`, then slides it until thumb and fingers touch equally
   (`skin_clearance`); the yarn route round the fingers is laid on the skin (`on_skin`, `settle`),
   and every frame the hook-to-hand stretch is pushed off the skin (`off_left_hand`). Op blends keep
   the hand's yarn fixed (it used to slide through the index).
2. **Rows joined.** Every static row has legs into the row below; the first row's go through the
   foundation chain's links (`row_of(..., zh, hole_dz)`, `CHAIN_DZ`).
3. **Right hand.** It didn't hold the hook (the shaft ran through the palm). `tools/grip_fit.py`
   fits the shaft's line so thumb pad, index pad, middle fingertip and web rest on it (cached in
   `build/hands/grip.json`); the index/middle curls changed to make that possible. Hook end capped.
4. **ch**: the older chain hangs down from the hook (`droop`) and the hand pinches it there, turned
   so the raised index stands in front of the chain. **mr**: a tighter pinch variant (`HandLc`)
   rests on the ring strand and backs off (`L_RELEASE`) before the finished stitches turn into it.
   Per-stitch placement lives in `_PINCH` / `L_VARIANT` in `choreo.py`.
6. **Yarn overs** (user, relayed: "not rotating the hook enough"; "the yarn moves by itself"): the
   working yarn is held straight from where it leaves the work (`BT`, lowered to be within reach)
   to the left index and bends only where the hook pushes into it (`contact`). A yarn over dips the
   hook under it and lifts it in (`yo_plan`/`yo_pose`; a hook in a stitch backs out 2.5 and tips
   up ≤50° about it), rolling the throat `YO_ROLL` = 200° round through the front; the roll back
   happens in the next op (`back` in `op_pose`), the throat carrying the yarn round. The right wrist
   takes `WRIST_SHARE` of the roll. `off_left_hook` slides the hook's head out of the left hand
   (leaving room for the yarn on the fingers); ch's yarn exit sits by the hook (no work behind a
   chain); the ring's is `MR_BTZ` = -2.4. Checked with close-ups and `hand_contact.py`: every
   stitch ≤ 0.64 mm (tr's tucked right pinky brushes the post for two frames; mr's thumb at the
   ring as it forms).
7. **Yarn over must read as hooked** (user, relayed: "it should clearly go over the yarn … otherwise
   it looks like magic"; and the held yarn crossed the front of the stitches): the held yarn now
   runs up behind the work and over the top edge (`over_top`, offset toward the finger so it never
   passes over the hook's head); the hook catches it on that stretch, so it drapes over the shaft
   into the throat with the head in view from the guided camera; after the catch the throat turns
   back only to face the pull (`ROLL_PULL` = 70°) while it drags, and down once the loop is made.
   A low-res clip of frames 150–440 was sent to the user before the restart.
8. **Stitches read as V's** (user, relayed): each finished stitch's top is a chain-like V lying on the
   row (`TOP_W`, the 6-point top in `row_of`), its legs going down into the row below.
9. **Pull-through** (user: "the yarn spawns"): loops on the hook ride with it (`through_loops`,
   `RIDE`), then stay put while the hook slides back through them (`slide_back`), each one leaving
   the head as a ring round the shaft; nothing appears out of nowhere.
10. **Grip and nails** (user, relayed: thumb not visibly on the thumb rest; nails "white flakes"):
   `grip_fit.py` now keeps every part `margin` clear and fits the thumb against the flat of the thumb
   rest (the shaft cut to 0.55·r, ±5.5 along it); `GRIP_ROLL` = −1.0 turns the hand so the thumb on
   the rest faces the camera. Nails: each fingertip owns only its own skin; the back of the last
   joint is the hand's side axis × the joint (thumb: away from its base) — the bones' twist axes
   point sideways on some fingers; the angle is measured round the finger's cross-section, not the
   bone (which runs ~3 mm under the nail and gave a strip); linear colours close to the skin; ring
   and pinky curled less and the pinky spread (their tips sank into the palm and each other).
11. **Nails, second pass** (user: "the nails look weird" — flat pale stickers): the plate is
   translucent (the bed is the skin's own texture colour × a pinker, cooler tint), glossy with a
   smooth plate (no pores), a thin ivory free edge only at the tip, the outline feathered (soft
   sides, soft cuticle, rounded free edge) and narrower than the fingertip. A comment had swallowed
   the owner/radius gates of the mask; they apply again.
12. **Nails, third pass** (user: "it's missing" — the thumb's nail vanished into the skin — and a
   reference photo of natural manicured nails): wide (covering most of the back of the fingertip),
   rounded-square just past the tip, a U-shaped cuticle line; a milky pale pink (88% its own colour,
   the skin only showing through a little), very glossy (full clear coat).
13. **Nail placement** (user: "shifted to the wrong place on the finger"): the back of each last joint
   is the short axis of the fingertip's cross-section, on the side where the bone lies nearer the
   skin — from the mesh, so the thumb is right too; the free edge at the measured tip, the cuticle
   halfway down the joint, ~75% of the width; the mask smoothed over the mesh (jagged outlines).
   The thumb (user: "the thumb is the problem" — a pale cap round its end, a red fold down its side):
   the model's thumb is turned ~100 degrees about its axis from a real grip (its modelled/painted nail faces
   the side). Untwisting it broke the approved grip, so instead: the thumb's back faces straight away from
   the shaft (`grip_fit` in `nails()`; left hand: away from the middle fingertip), the plate is capped at the
   fingertip, and the thumb tip's own painted nail is covered — the skin there takes the colour of the other
   side of the fingertip (`skincol`/`skinfix`, per vertex: copying UVs left seams; the texture's pixels are
   sRGB) and the modelled nail groove is smoothed out of the mesh.
   Free edges (user: "a stubby thumb"): `free_edges()` builds a slim plate (`NAIL_FREE` = 2 mm past the
   fingertip, 0.3 mm thick, rounded) on each nail's front edge but the index's, into the hand mesh; they
   are left out of `hands.json`'s `_verts` (`n_skin`), or choreo's skin tests push the hook and hands about.
14. **First yarn over in view** (user: "5–9 seconds still doesn't hook right"; only the tip's ball showed
   over the top edge): a hook in a stitch no longer backs out; it tips its head up about the stitch to
   catch the held yarn `YO_CATCH_Z` above the row it is in, drawn back 0.8 (the throat ~4 out the back).
15. **One camera angle** (user: "keep the camera angle the same, and only rotate the hands/piece if trying
   to show a different angle"): every guided shot looks from FRONT; to show the back for "pokes out the
   back" and the yarn over, the whole work turns in front of it (eased, 1 s each way). Done as the camera
   swung by `turn_of(d)` (the least rotation FRONT→d) *with its roll, lights, HDRI and floor* — the same
   picture; choreo writes it per frame as `cam.turn` and `project()` uses it for the cues. The turns fit
   inside the old shot lengths, so every cue keeps its time (sc: 20.2 s, cues at the published times).
   `tools/queue/cue_overlay.py` draws the cues' rings/traces/arrows over renders of the cue frames.
5. Verified with `tools/hand_contact.py` (BVH; prints only frames where something is >0.5 mm inside
   a hand): sc every 3rd frame, the others every 12th–30th frame — all clean. Full-quality
   close-ups of both fixes were sent to the user before the long run.

16. **Yarn flicker in motion** (user: "the yarn is moving weird when there is motion"): choreo splits one yarn
   into colours at a point that moves every frame, and the renderer keyed each strand's twist, fibres and
   flyaways (and its frame) to its own start, so they crawled along the working yarn. A strand that starts
   where the previous ended now carries on its length (`s0`), seed and frame; open strands are sampled at
   fixed places along the yarn; the joins don't taper. The focus distance is the hook's averaged over a second.
   Then (user: "still see it a bit"): the working yarn is held from where it leaves the work to the ball and
   fed from the ball, so the renderer counts that stretch back from its end (choreo exports `slide`/`hold`
   on the accent strand; `yarn_coords`) and the loops on the hook take up the difference. Encoding at VP9
   crf 24 (grid 27) instead of 30/32: the encoder's error changed frame to frame on the fibres. Tried and
   rejected: thicker fibres/fewer flyaways (`FIBRE_K`, `FUZZ_K`: more flicker), 32 samples (barely helps).
   A blue line on the nails: the free-edge plate stood off the skin (you saw through the gap); now set into it.
   Later (relayed: "keep improving that flicker"): idea 7 is the default in `encode_views.sh` — the temporal filter
   averages ±2 frames where still and stays 4 px off motion (still shimmer 0.32 -> 0.24). Idea 6 (1.5x supersample)
   rejected: no gain at 2.25x cost. Idea 5, motion-compensated (`tools/queue/mcfilter.py`, needs
   `pip install opencv-python-headless`): shimmer on moving yarn -20% but the moving plies soften (the user's first
   complaint was "blurry in motion"), so it is off; `MCFILTER=12:1` switches it on if the user picks it.
17. **Yarn through yarn** (user: "the two yarns wouldn't mix like that, they're going through" — the orange
   working yarn through the blue): detector `tools/yarn_contact.py`; the publish gate is `tools/queue/yarn_gate.py`
   (working yarn vs everything else ≤ 0.65R on every 6th frame; fabric vs fabric only logged — the designed V
   pinches touch on purpose; `build/queue/gate_except_<key>` holds an "a:b" range not gated; sc: `384:408`, the
   pull-through close). `publish.sh` runs it before encoding. sc went from 1.97R in every frame to 0 frames over
   0.65R outside the close. What it took, in choreo:
   - the held yarn leaves the work over its top edge once a loop is pulled up (`yarn_leaves`), so the yarn over
     is taken above the work, not by reaching through it; from the loops it goes over the top, not through the
     new stitch;
   - the live loop sits on the shaft where it clears the fabric (`live_clear_d`), not inside it;
   - pulling up backs the head straight out through the hole before lifting (`PU_OUT`), not up through the V;
   - loops off the head turn their open side to the yarn coming into them (`RING_TURN`);
   - relaxation (`tools/yarn_relax.py`): crossing strands part along their common normal; the fabric gives way only
     to the working yarn's passes, the hand's yarn and the left hand's skin (not to itself: `FABRIC_SELF=0`,
     anchored `RELAX_ANCHOR`), so the V tops keep their designed shape; the working yarn also keeps off the skin.
   Open: the pull-through close (sc 390–402, 1.3–1.9R): the pulled-up loop's legs thread through the live loop's
   ring as they leave the head (the finished stitch is threaded the other way round; `LEGS=real` is a prototype
   of the stitch threaded as made). It reads as loops chained round the head, not as a colour glitch. choreo now
   takes ~45 min per stitch (the per-frame relax). Previews for the user go to branch `previews`, via the relay.
18. **The left hand at work** (user: "you are never moving the left hand ... it just looks like the yarn is
   magically sliding"; then "it should actually move MORE"): `make_hands_mpfb.py` bakes working poses on L's mesh:
   Ly (index lifted and swung toward the head, `LY_SWING`), Lf (index forward and down, giving yarn), Le (pinch
   eased). choreo's `hand_state(ta)` mixes them per op (Ly at each yarn over, dipping as the hook catches; Lf
   through the pull-ups and pull-throughs; Le after each stitch), turns the hand toward the hook about the pads'
   line (`WRIST_DEG` -11) and slides the pinch along the row per stitch made (`CREEP`); the frame's left hand
   carries `"mix"`, which the renderer and hand_contact set as shape keys (`tools/hand_mix.py`). `HAND_ACTIVE=0`:
   the still hand. **After pulling, rebuild `build/hands`** (`make_hands_mpfb.py`, ~20 s) before regenerating
   paths, or the renderer shows the still hand. The yarn round the fingers is the poses' routes blended, then
   settled on the blended skin (`settle_on`); the runs up to the index and on to the ball are in steps; index and
   middle are capsules (`off_fingers`) for yarn found deep in a fingertip. sc: gate 0 frames over 0.65R;
   hand_contact ≤ 3 mm in 17/81 frames, all in the crease between the index and middle knuckles (palm side, the
   gap narrower than the yarn when the index swings in; hidden behind the fingers). choreo ~65 min for sc.
19. **The pull-through close** (the orange knot / blue fabric through orange loops at every stitch's last
   pull-through: sc 390–402, sl 306–312, hdc ~492, dec ~648): the close morphs the loops on the hook into the new
   stitch (`morph`), and its curve took the *new* stitch's end of fabric (`own_e`) from the first frame, so the
   loops still coming off the hook and the yarn through them were relaxed as finished fabric: frozen, not kept
   off each other or the fabric. `CLOSE_OWN=1` (default) keeps the old end of fabric until the close is done.
   sc (single frames): 390/396/402 from 1.78/1.90/1.02R to 0.39/0.39/0.06R, the rest unchanged. Slip stitch:
   `SL_THRU=1` also takes the yarn on from the new loop down through the stitch (as the yarn over came) instead of
   over its top, which the close otherwise dragged through the stitch below: sl 303–315 from up to 1.93R to
   ≤0.41R. Left over in sl, ~0.7–0.8R: 270, 294, 318–324, and 240 (1.16R, the caught yarn drawn through the
   stitch, as before). Not fixed by this: inc's second sc shares the first's hole (legs on top of each other),
   hdc/dec's mid-stitch stretches (hdc 72–102, 348–366; dec 348–426). Tools: scratchpad-style single-frame gate =
   exec choreo.py up to the frame loop, then `frame_strands(at_video(f/24)[0])` (~4 min setup, seconds a frame).
   Further yarn-through-fabric fixes (single-frame gate): `PRE_TOP` (hdc/dc/tr: yarn overs before the insert, the
   hook in front of the work, take the yarn back over the top edge; hdc 72–102 from 1.55R to ≤0.45R); `WRAP_TOP`
   (hdc/dc/tr: a pulled-up loop after a yarn over takes its yarn over the row below's top at the hole,
   `over_edge`; hdc 360–366 from 1.5R to 0.34R); `PULLED_FRONT` 2.5 (dec: a pulled-up loop stays on the shaft
   in front of the work while the hook is in the next stitch; 348–402 from ~1.1R to ~0.8R, 500 up from 0.76R to
   1.06R). `INC_D` (off): inc's two stitches side by side in the shared hole, only partly helps (the second
   stitch's loop and legs go through the first's V and legs, 582–684 ~1.6R; needs a fan-out redesign).
   Still open: hdc 348–354 (the loops on the hook brush the row below's front as it backs out, ~1.1R).
## Checking tools
- `python3 tools/queue/cue_overlay.py build/paths/<key>.cues.json <frames dir> out.jpg [view]` — the callouts
  drawn over the rendered cue frames (render them first at `round(t * 24)`).
- `blender -b -P tools/hand_contact.py -- build/paths/<key>.json a:b:step` — yarn/fabric/hook vs hands.
- `tools/queue/closeup.sh <paths> <frame> <name> q|full "dx,dy,dz@tx,ty,tz@dist" ...` — close-ups
  from any camera (design space: Z up, -Y toward the camera), tiled into `build/closeup/<name>.jpg`.
- Env overrides in `choreo.py`: `L_PINCH`, `L_FINGERS`, `L_AXIS`, `L_VARIANT`, `CHAIN_DZ`;
  `HAND_POSE_<R|L|Lc>` in `make_hands_mpfb.py`.

## Setup (nothing in build/ is in git; a fresh container needs all of it)
- Blender 4.2.3: `mkdir -p /opt/blender-dl && curl -sSL https://download.blender.org/release/Blender4.2/blender-4.2.3-linux-x64.tar.xz | tar xJ -C /opt/blender-dl`
- HDRI: `mkdir -p build/hdri && curl -o build/hdri/studio_small_09_2k.hdr https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/studio_small_09_2k.hdr`
- MPFB2: `curl -sSL -o build/dl/mpfb.zip "https://extensions.blender.org/download/sha256:c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad/add-on-mpfb-v2.0.18.zip"`, then
  `blender -b --command extension install-file -r user_default -e build/dl/mpfb.zip` (no `--factory-startup` with it).
- MPFB2 is a user extension and is lost if the container's home is reset — reinstall it before
  re-baking hands (rendering only needs `build/hands/`).
- MakeHuman CC0 assets: `https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip`,
  unzip into `build/dl/mh/x`. Then `blender -b -P tools/make_hands_mpfb.py -- build/hands build/dl/mh/x/skins/young_caucasian_female/young_lightskinned_female_diffuse.png`
- `pip install matplotlib` (for `tools/preview_paths.py`).
- Paths: `for k in sc ch sl hdc dc tr inc dec mr; do python3 tools/choreo.py $k build/paths/$k.json --cues build/paths/$k.cues.json --hands; done`

## The render queue (`tools/queue/`)
- State lives in `build/queue/` (git-ignored): `jobs.txt` (lines `<paths.json> <frames dir> <angle>`),
  `done.txt`, `publish.txt` (lines `<key> 24 <dir> [dir dir dir]`), `published.txt`, `log.txt`.
  Start from `cp tools/queue/jobs.example.txt build/queue/jobs.txt; cp tools/queue/publish.example.txt build/queue/publish.txt`
  (order: sc_v0, sc_v1..3, then ch sl hdc dc tr inc dec mr).
- `tools/queue/ensure.sh` starts `run.sh` (renders jobs in order, resumable with `--skip-existing`) and
  `publisher.sh` (encodes + commits + pushes each stitch once its dirs are done) if not running.
  It's idempotent; run it from the repo root.
- After any change to choreo/renderer/hands: stop everything (`pkill -f '^/bin/sh tools/queue/'; pkill -f '^/opt/blender-dl/'`),
  `rm -rf build/frames/*`, empty `done.txt` and `published.txt`, regenerate the paths, then `ensure.sh`.
- `tools/queue/check.sh <key> <a:b:step>` renders quick low-quality frames of `build/paths/t_<key>.json`
  as a contact sheet. `tools/queue/handtest.sh <name>` renders one frame of the hands.

## Pitfalls already hit
- **The container/worker restarts and the renders die** (four times so far; files in `build/`
  survived each time, processes didn't). After any restart run `sh tools/queue/ensure.sh` (it
  resumes with `--skip-existing`). Keep a `run_in_background` Bash watcher alive (max timeout 2 h):
  an until-loop running `ensure.sh` every minute that exits when something publishes; re-arm it.
  The user declined further `send_later` check-ins at 20:50 — don't schedule them.
- Heavy checks (hand_contact sweeps, choreo runs) share the 4 cores and slow the render 2–3×.
- ffmpeg reads stdin: inside a `while read` loop, give it `< /dev/null` (it ate the job list).
- This shell is bash: a `-pattern_type glob -i dir/f_*.png` in a variable gets expanded unless you
  `set -f` first.
- `pgrep -f`/`pkill -f` patterns that also appear in your own command match your shell — anchor them (`^/opt/blender...`).
- EEVEE needs a GPU: Cycles only. Subsurface on the yarn doubles render time — keep `--sss 0` (the default).
- AgX Punchy shifts every colour: the stage values in `render_tutorial.py --stage` were solved by
  test renders to come out as the app's cream `#f3ece3` (242,235,227).
- Python's `http.server` has no HTTP Range support (video seeking breaks locally); GitHub Pages is fine.
- `tools/__pycache__` and `build/` are git-ignored — never commit them.

## Budget
4 CPU cores, CPU-only Cycles at 800×500, 16 samples + OIDN: ~45–60 s/frame Guided with hands. sc
486 frames × 4 angles, the others ~5,400 frames → ~60–70 h in total. Commit each stitch as soon as it's encoded. Finish with a
short summary of which stitches/angles were rendered and anything cut.

## Base versions of hdc, dc, dec, tr (session_01RFXAp9cSMRVMFfJmhJ5amD, 2026-10-30)
Guided only, 24 fps, 800×500, rendered with `--samples 6 --fibres 70` (+ OIDN, tfilter in the encode):
~4× faster than 16 samples / 220 fibres and close to it at the site's size. Paths from main at `a3a9830`
(yarn relax). Full-quality renders from the main queue should overwrite them.
Known issue (not fixed here, it's shared choreo): **the left hand is placed against the un-relaxed fabric**
(`_fab` in the left-hand placement uses `spline(s)` of STATIC, not `static_relaxed()`), so after the yarn relax
puffs the fabric out the left middle fingertip sits ~2 mm inside it (hand_contact: `fabric1/L middle_pad -2.0`
on every frame of hdc/dc/dec). On dec the working yarn also runs ~2 mm into the left middle finger in the
last third (frames 480–720). Mostly behind the work in the Guided view. Fix: place the hand against
`static_relaxed()` (move `import yarn_relax`/`static_relaxed` above the placement) and re-run hand_contact.

## ch, sl, inc, mr (session_01RFXApCsFfy8t6C1NjXPFtF, 2026-10-30)
Base renders: Guided, 24 fps, 800×500, `--samples 8 --fibres 100` (+ OIDN, tfilter): ~20 s/frame, looks the same
as 16/220 at the site's size (`run.sh` takes renderer flags after the frames field of a jobs line).
- **ch** (`9c0f3f4`, re-encoded `333c219`) and **sl** (`8094f73`, re-encoded `f3d22bb`) are on the site from the
  a3a9830 paths. **sl has the V-top fault** (the current row's tops read as separate curls: a3a9830 relaxed the
  fabric against itself); sl regenerated on 23f305f has connected V tops again (stills on branch `previews`,
  `vtops/`). ch has no row and is fine. **inc**'s render on a3a9830 paths was stopped and not published.
- Plan: when the left-hand choreo lands, regenerate sl and inc on it, check the V tops on the last frame against
  old sc `9bc0185`'s last frame, render, publish (replacing sl).
- **mr is unpublished.** Its finished round reads as a rosette of loose loops, not a compact disc with a rim of
  V's. Branch `mr-vtops`: `daece6d` turns the work for the close and the end so the rim is seen from above
  (`RIM`, via `turn_of`; cue times unchanged; yarn_gate 0.73R at 636/840, hand_contact clean). Still needed (being
  remodelled on that branch): the ring's stitches are the row sc bent round (7 of them, the ch 1 a full post);
  they need their own shape (`ring_piece`): compact wedge posts that share sides, top links flat on the rim, a small
  ch 1, so the closed round is a firm flat disc. Single frames build in ~10 s by running choreo.py up to its frame
  loop and only the wanted frames (keep paths in `build/`; see the session's scratchpad `oneframe.py` idea).
- **Paths in chunks** (`tools/queue/chunks.sh <key> ...`): choreo.py's own frame loop run by `chunkgen.py` over
  24-frame ranges, each written to `build/chunks/` as it completes, 4 workers. A full choreo run (1.5–2 h with the
  left hand) kept dying in container restarts; this resumes (rerun the script) and uses all cores (sl ~20 min).
  Output is identical to choreo.py's (checked frame by frame). Rerun it once the workers are done to merge each key
  into `build/paths/<key>.json` + `.cues.json`; delete `build/chunks/<key>_*` before regenerating a key.
- **Final renders on the left hand + held camera** (Guided, 24 fps, `--samples 8 --fibres 100`, default encode; paths from
  42fcc47's close fix + the ring commits, generated with `chunks.sh`). Logged yarn_gate exceptions (working yarn > 0.65R):
  - **sl** (`3fb1038`): 240:324, worst 1.18R at 240 (the pull through the stitch and loop; 0.69–0.82R after 240).
  - **inc** (`020d9e3`, paths from 42fcc47 without TOP_FLAT): 534:684, worst 1.66R (the second sc's legs share the
    first's hole and run through its V and legs; 534 at 0.71R). Its pull-throughs (390:402, 468:516) pass.
