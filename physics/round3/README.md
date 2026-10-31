# Round 3: physics_pass post-pass, real hands, full sc + hdc

Code: branch `yarn-physics` (choreo `PHYS=1` opt-in export; `tools/queue/physics_pass.py`; `tools/yarn_xpbd.py` defaults
60 substeps × 10 iterations, feed gain 1; `tools/queue/physics_metrics.py`). Paths made with the baked hands from
`previews/hands/` (`chunks.sh`). Rod budget per stretch = choreo's own relax length for that stretch, smoothed over 0.3 s.

| | sc old | sc pass | hdc old | hdc pass |
|---|---|---|---|---|
| yarn_gate (every 6th frame), worst / frames > 0.65R | 0.80R / 2 (348, 378) | **0.24R / 0** | 1.21R / 2 (348, 354) | 0.71R / 4 (78, 84, 90, 414) |
| hand_contact, frames > 0.5 mm inside | 33/162, worst 3.0 mm | 33/162, same | 22/98, worst 3.0 mm | 22/98, same |
| fibre crawl per frame, median / p90 (R) | 0.34 / 1.89 | 0.15 / 0.84 | 0.49 / 2.16 | 0.25 / 0.95 |
| \|ΔL\| per frame, median / p90 / max (R) | 0.38 / 3.36 / 14.7 | 0.14 / 1.80 / 10.1 | 0.50 / 4.00 / 23.2 | 0.24 / 1.80 / 12.6 |
| shape motion ×design, median / p90 | 1.12 / 1.85 | 0.94 / 1.70 | 1.10 / 1.95 | 1.17 / 2.58 |
| flicker still / moving, own masks | 3.69 / 5.77 (280–340) | 3.71 / **5.37** | 3.91 / 5.77 (60–120) | **3.15 / 5.33** |
| flicker still / moving, old's masks | – | 4.10 / 9.95 | – | 3.92 / 9.48 |

The design's own crawl is 0.11/0.85 (sc) and 0.19/0.93 (hdc), so the pass is at the design's level.
hand_contact is identical to old: every frame over 0.5 mm is the documented crease between the index and middle knuckles,
on the route round the fingers, which the rod doesn't touch.
hdc gate frames over 0.65R: 78–90 (the yarn over behind the row, hidden behind the work in the Guided view) and 414
(the loops on the hook, readable). See `hdc_gate_frames_84_414_old_vs_pass.jpg`. Proposed logged exceptions:
`72:96`, `408:420`. More iterations (80 × 14) don't move them (0.70R): it's the design's geometry.
Look: the loops on the hook sit more bunched and draped than old's crisp loops (`sc_hands_stills_282_305_328.jpg`),
same size; the live loop is visible. Worth a look by the user.
Files: `sc_280_340_hands_old_vs_pass.mp4`, `hdc_60_120_hands_old_vs_pass.mp4`, the two stills.

## sl end of stitch (frames 330–396)

`sl_f360_old_vs_new.jpg`: Guided view, frame 360, choreo's relax (left) vs the pass (right), 8 samples / 100 fibres, 800×500.
The pass's yarn gate is 0.86R here (limit 0.65R). Choreo's design for the yarn on to the hand runs 0.23R through the
stitch just closed, and the rod is held taut on it. Logged as an exception: in the Guided view the overlap sits behind
the loop on the hook. Friction μ=0 brings it to 0.71R, but it costs sc, so the default stays μ=0.4.
