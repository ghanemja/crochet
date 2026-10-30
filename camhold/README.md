# cam-hold (main aa23a7b): the guided camera holds still through every action

## Static camera
Frames whose camera (position, target and turn) is unchanged from the previous frame:

| stitch | old camera | cam-hold |
|---|---:|---:|
| sc | 21.0% | 89.3% |
| dc | 14.5% | 93.0% |

The hook head stays at least 13% of the frame in from the edges. Every callout stays in frame, and none falls in a camera move.

## Flicker (sc frames 188–199, 16 samples / 220 fibres)
Same paths; only each frame's "cam" is swapped. In this stretch the old camera dollies about 0.2 units per frame.
Still-yarn flicker from `tools/queue/flicker_metric.py`, each render scored on its own masks; lower is steadier.

| | old camera | cam-hold | change |
|---|---:|---:|---:|
| raw frames | 5.47 | 2.20 | −60% |
| encoded (encode_views.sh default) | 3.79 | 1.00 | −74% |
| encoded, MCFILTER=12:1 | 3.71 | 1.24 | −67% |

The moving column can't be compared between the two: with the camera moving, the old render counts nearly the whole picture as moving.

- `camhold_sc188.mp4`: old camera (left) vs cam-hold (right), 12 frames looped 6 times, standard encode.
- `sc_cue_overlay.jpg`: all 7 sc callouts drawn over 8/100 renders of their cue frames, with the held camera. Every ring is on target.

The dc comparison will follow from the regenerated dc paths.
