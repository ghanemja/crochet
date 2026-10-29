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
   The guided camera cuts (`shot(1e-3, …)`) to `BEHIND_OVER` for "pokes out the back" and the yarn over,
   and cuts back for the pull — a swing over the top flips the picture (the renderer's up is world Z).
5. Verified with `tools/hand_contact.py` (BVH; prints only frames where something is >0.5 mm inside
   a hand): sc every 3rd frame, the others every 12th–30th frame — all clean. Full-quality
   close-ups of both fixes were sent to the user before the long run.

## Checking tools
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
