# Yarn physics spike: XPBD rod vs per-frame relax (sc 280–340, Guided)

Branch `yarn-physics` (`tools/yarn_xpbd.py`, `tools/queue/physics_rec.py`, `tools/queue/physics_study.py`).
**Caveat: hand-less paths.** This container couldn't install the MPFB extension (blocked), so `build/hands` doesn't exist.
Old and new are both made from choreo with `HAND_PTS=None`: no left-hand skin and no hands in the render.
The comparison is like for like, but the frames aren't main's published sc paths, and `hand_contact.py` couldn't run.

Rod: inextensible (direct tridiagonal chain solve each iteration, stretch < 1e-4 R). Material coordinates run
from the fabric end; the yarn is fed and taken back through the left-hand point (smoothed slack). It's pulled
toward choreo's design at 20 Hz, critically damped, with bending length 1R against the pull. Contacts at 2R with
fabric and self, the hook profile + 0.9R, friction μ 0.4. 40 substeps × 8 iterations: ~0.2 s/frame on CPU, numpy only.

| sc 280–340 (61 steps), yarn radii | design | old (yarn_clear) | new (rod) |
|---|---|---|---|
| per-frame motion, shape (median / p90) | 0.074 / 0.150 | 0.141 / 0.252 | 0.116 / 0.255 |
| ratio to design, shape (med / p90) | 1 | 1.35 / 2.09 | 1.53 / 2.35 |
| per-frame motion at fixed arc length from fabric (med / p90) | 0.42 / 1.44 | 1.27 / 2.76 | 0.43 / 1.43 |
| ratio to design, arc-length (med / p90) — fibre crawl | 1 | 2.39 / 15.3 | 0.96 / 1.80 |
| \|frame-to-frame length change\| (med / p90 / max) | 0.44 / 1.89 / 8.2 | 1.18 / 4.97 / 14.2 | 0.44 / 1.90 / 7.3 |
| length over the design (median) | 0 | +17.6 | +1.7 |
| yarn_gate, frames 280–340: worst / frames > 0.65R | — | 0.79R / 1 | 0.67R / 1 |
| flicker_metric still / moving, each self-referenced | — | 4.12 / 6.05 | 4.13 / 5.36 |
| flicker_metric still / moving, old as reference | — | 4.12 / 6.05 | 4.37 / 10.19 |
| hand_contact.py | — | n/a (no hands) | n/a |

The design's own length jumps by up to 8R at op joins (frames 255–258, 306, 327).

**Verdict: not a clear win.** The rod fixes what it set out to fix. Its length follows the design's frame to frame
(old swings the other way, e.g. frame 329: old −6.2R against the design's +1.3R). Material barely crawls (p90 1.8×
the design vs 15×), and the gate is as good as old or better. But the picture is worse: the design is drawn tighter
than the yarn is thick, and old resolves that by lengthening the yarn ~17R. An inextensible rod near the design's
length instead buckles, so the loops on the hook crumple into a blob and the live loop is buried (see the stills).
Feeding more yarn (gain 2) or holding the loops stiffer brings back length swings or yarn through the fabric
(gate fails on every frame). Flicker is a wash: better on moving yarn when self-referenced, worse cross-referenced.

Files: `sc_280_340_old_vs_new.mp4` (left old, right new), `cmp_grid.jpg` (frames 282 / 305 / 335),
`cmp_f328.jpg`, `sc_280_340_per_frame.tsv`.
