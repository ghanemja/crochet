# Hookpath

A browser tool for planning a crochet hook's motion in 3D, for the offline tutorial
renders. No install: open `index.html` (or the GitHub Pages copy at
`/tools/hookpath/`).

- Drag the hook (Move / Rotate) — each change becomes a keyframe at the playhead.
- Per keyframe: a step name, a camera shot ("Use current view") and a callout
  (caption + a circle placed by clicking the scene).
- Play back with the free camera or the planned shots; export the plan as JSON.

Plan format (`hookpath/1`), in the renderer's space — Z up, X along the row
(worked right to left), −Y toward the viewer, 1 unit = one yarn radius:

```json
{ "format": "hookpath/1", "stitch": "sc", "duration": 13,
  "keys": [ { "t": 0, "tip": [x, y, z], "quat": [x, y, z, w],
              "label": "Insert hook",
              "camera": { "pos": [..], "target": [..], "fov": 22 } | null,
              "callout": { "text": "..", "target": [x, y, z], "hold": 2.2 } | null } ] }
```

`quat` orients the hook: local +Y runs up the shaft from the tip, local +X is the
throat. The sample is the single crochet from `tools/choreo_sc.py`.

## Rendering a plan

```bash
python3 tools/choreo_sc.py build/paths/sc_plan.json --plan my-plan.json --cues build/sc_plan.cues.json [--hands]
blender -b -P tools/render_tutorial.py -- build/paths/sc_plan.json build/frames/sc_plan --angle 0
```

The hook follows the plan (same interpolation as the planner); keyframes with a step
name mark where each step of the stitch starts, which tells the yarn what phase it is
in; camera shots drive the guided camera; callouts become the freeze-frames.
