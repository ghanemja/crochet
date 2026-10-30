# Flicker study: dc frames 300–311 (a3a9830 paths, Guided view, 800×500)

Metric: `tools/queue/flicker_metric.py` (main 05dc4ab). It measures the mean luma change from one frame to the next, on a 0–255 scale. Lower is steadier.
- **still:** pixels whose optical flow in the 16/220 reference is under 0.25 px.
- **moving:** pixels whose flow is over 1 px, after the previous frame is warped onto the current one.
The masks come from the 16/220 raw frames, so every row is scored on the same pixels.

"Encoded" means decoded from the VP9 output of `tools/encode_views.sh`. Its default is tfilter idea 7, crf 24; the MC rows use `MCFILTER=12:1` instead.
Cost is Blender 4.2.3 Cycles CPU time in this container, averaged over the 12 frames.

| config | s/frame | still raw | moving raw | still enc | moving enc | MC still | MC moving |
|---|---:|---:|---:|---:|---:|---:|---:|
| published (6 samples / 70 fibres, decoded from dc.views.webm) | 21 | – | – | 4.86 | 4.04 | – | – |
| 6 / 70 (re-rendered; identical to the published frames) | 21.4 | 6.88 | 5.25 | 4.89 | 4.08 | 5.09 | 3.72 |
| 8 / 100 | 29.3 | 6.69 | 5.29 | 4.48 | 4.14 | 4.83 | 3.74 |
| 16 / 220 (reference) | 61.6 | 5.99 | 4.90 | 4.02 | 4.09 | 4.05 | **3.30** |
| 64 / 220, no denoiser | 203.9 | 19.44 | 14.21 | 18.10 | 13.46 | – | – |
| 16 / 150, FIBRE_K=1.4 (~0.7 px fibres) | 63.3 | 8.30 | 6.35 | 6.37 | 5.53 | – | – |
| 16 / 220, FUZZ_K=2 | 61.3 | 6.47 | 5.07 | 4.54 | 4.27 | – | – |

Findings:
1. **Base settings:** these cause part of the flicker. After the encode, 6/70 has 22% more still flicker than 16/220, and 8/100 has 11% more. 8/100 is the cheapest setting near 10%, at 0.48× the cost of 16/220.
2. **Denoiser:** it is not the cause. Turning it off and using 64 samples gives 4× the flicker at 3.3× the cost. OIDN output is far steadier than raw path tracing at these sample counts.
3. **Fibre aliasing:** thicker fibres (FIBRE_K=1.4) and FUZZ_K=2 both made the flicker worse here. Caveat: their geometry differs from the reference that the masks come from. Even so, no gain is visible.
4. **MCFILTER=12:1:** on moving yarn it cuts the flicker by about 20% for 16/220 and about 10% for 6/70 and 8/100. On still yarn it is neutral or slightly worse than tfilter.
   - Best combination overall: 16/220 with MCFILTER=12:1.
   - Cheaper option: 8/100 with MCFILTER=12:1, which is 13% worse still and 9% better moving than 16/220 with tfilter.

Clip: `flicker_study_dc300.mp4` shows the 12 frames looped 6 times. Left to right:
- the published 6/70;
- 8/100 with tfilter;
- 16/220 with MCFILTER=12:1.
