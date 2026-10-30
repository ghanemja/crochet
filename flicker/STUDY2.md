# Flicker study 2: what changes on "still" yarn (dc frames 300–311, 16 samples / 220 fibres)

The metric is the same as in README.md (raw frames, before encoding). The "masks" column says which render's
optical flow chooses the still and moving pixels.
- Camera-frozen runs move differently on screen, so they are scored on their own masks.
- s16f220 scored on its own masks is 5.99 / 4.90.

| run | s/frame | masks | still | moving |
|---|---:|---|---:|---:|
| 16 / 220 (default) | 61.6 | own | 5.99 | 4.90 |
| determinism: frames 300 and 305 rendered again | 60 | – | mean pixel diff 0.0014 and 0.0017 (max 2 and 4 of 255) | |
| adaptive sampling off (ADAPTIVE=0) | 59.5 | s16f220 | 5.99 | 4.90 |
| pixel filter width 2.0 (FILTER_W=2.0) | 59.6 | s16f220 | 6.46 | 5.26 |
| fabric strand 3 frozen at frame 300 beyond 8R (4–8R blend) | ~60 | own | 6.80 | 4.86 |
| **camera frozen at frame 300** | ~60 | own | **2.22** | 5.61 |
| camera and fabric frozen | ~60 | camera-frozen | 2.26 | 6.99 |

Findings:
1. **The renderer is deterministic.** The same frame rendered twice gives about 0 difference. Adaptive sampling at 16 samples never stops early, so the frames are identical to the default to within 0.0008 mean.
2. **The fabric does creep.** On the a3a9830 paths, strand 3 (the row being worked into the working yarn) moves every vertex every frame. The median per frame is 0.03R within 4R of the working yarn or hook, 0.021R at 4–8R, 0.008R at 8–16R and 0.001R beyond. It comes from the per-frame relax in choreo `yarn_clear`.
   - Freezing it gave no measurable gain: 2.22 vs 2.26 with the camera frozen, and worse on its own (blend seam).
   - Strands 0–2 are already bit-identical.
3. **The cause is the camera.** This stretch is in the middle of a shot's zoom: the camera dollies from 29.2 to 24.2 units over frames 290–320, with a constant turn. That is an intended shot zoom, not drift.
   - Every sub-pixel fibre (about 0.5 px wide) is rescaled every frame, so its aliasing changes even where the on-screen motion is under 0.25 px.
   - Freezing the camera cuts still-yarn flicker by 63% (5.99 to 2.22).
   - The camera moves in 85% of the take: 103 of 711 frames have a static camera, and the median move is 0.10 units per frame.
4. **A wider pixel filter makes it worse here** (6.46).

What would help, per these numbers:
- **Fewer, slower camera moves.** Hold the camera still while stitches are being made, and zoom or turn between actions. It is the only lever bigger than about 20%.
- **More samples and fibres** (16/220 over 6/70).
- **MCFILTER=12:1 at encode** for moving yarn.

Branch `fabric-freeze` (297dc54) has the choreo fix anyway (FABRIC_FREEZE=4:8; 0:0 turns it off). On current main, dc's first 330 frames go from 67% to 82% of the worked row bit-identical. It is not the flicker fix.

Clip: dolly_vs_frozen_dc300.mp4 shows 16/220 as published (left) and with the camera frozen (right), 12 frames looped 6 times.
