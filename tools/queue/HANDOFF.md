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

## Where things stand
- `tools/choreo.py` choreographs every stitch from a spec (`tools/README.md`, "Every other stitch").
  sc comes from it too now (`choreo_sc.py` is the older single-crochet original).
- `assets/tutorials/sc.views.*` on main is an **old** take: old hands, hook and transparent film.
  Everything has to be re-rendered once the two open issues below are fixed. Nothing is rendering.
- Settings approved by the user so far (all in git): an opaque cream stage (`render_tutorial.py
  --stage`, the default; the transparent film left speckled fibre edges), no shadow-catcher floor,
  matte flyaways, constant-quality encoding (`encode_views.sh`; low bitrates smeared the fibres in
  motion), the left hand placed by its pinch on the work (forearm toward the viewer, thumb in
  front, index raised carrying the yarn), a tripod right-hand grip, a hook that turns before it
  reaches the stitch, slides in and backs out along its shaft and goes well out the back, less waxy
  skin (`make_hands_mpfb.py`).

## Open issues (from the user, fix these first)
1. **How the left hand holds the yarn, physics-wise.** The fabric and yarn pass through the left
   fingers (see the close-ups at the start of the guided take). The thumb/middle pinch must sit on
   the fabric's surfaces, not inside it. The working yarn's route over the index, under
   middle/ring and round the pinky (`hand_route_local` in `choreo.py`) must lie on the skin. Check
   with full-quality close-up frames (`tools/queue/handtest.sh`, `L_PINCH` / `L_FINGERS` /
   `L_THUMB` env overrides in `choreo.py`). The finger poses are in `make_hands_mpfb.py` (`POSES`).
2. **The bottom row isn't connected to the row above.** The foundation chain (`chain(ROW_XS, -3*H)`
   in `choreo.py`) floats on its own: the legs of the row above (`row_of(ROW_XS, -2*H)`) must go
   down into the chain's V's, the way each row's legs go into the row below.

The user also cares that the hands look real (skin), and that the hook's direction makes sense in
every step. After fixing, render one full-quality frame per issue and show it before the long run.

## Setup (nothing in build/ is in git; a fresh container needs all of it)
- Blender 4.2.3: `mkdir -p /opt/blender-dl && curl -sSL https://download.blender.org/release/Blender4.2/blender-4.2.3-linux-x64.tar.xz | tar xJ -C /opt/blender-dl`
- HDRI: `mkdir -p build/hdri && curl -o build/hdri/studio_small_09_2k.hdr https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/studio_small_09_2k.hdr`
- MPFB2: `curl -sSL -o build/dl/mpfb.zip "https://extensions.blender.org/download/sha256:c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad/add-on-mpfb-v2.0.18.zip"`, then
  `blender -b --command extension install-file -r user_default -e build/dl/mpfb.zip` (no `--factory-startup` with it).
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
- **The container is recycled whenever the session is idle** and the renders die (twice, ~15 h
  lost). Keep a `run_in_background` Bash task running at all times (max timeout 2 h): an until-loop
  that runs `tools/queue/ensure.sh` every minute and exits when something publishes, then re-arm
  it. Also schedule a `send_later` check-in every ~30 min that re-runs `ensure.sh` and re-arms
  the watcher.
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
4 CPU cores, CPU-only Cycles: ~15–28 s/frame at 800×500, 16 samples + OIDN. sc 486 frames × 4
angles, the others ~5,400 frames → ~40 h. Commit each stitch as soon as it's encoded. Finish with a
short summary of which stitches/angles were rendered and anything cut.
