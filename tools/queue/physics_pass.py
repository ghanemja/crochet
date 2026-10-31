# The working yarn remade as a rod stepped in time (tools/yarn_xpbd.py), as a post-pass on choreo's paths: choreo relaxes the
# working yarn off the fabric, hook and hand from scratch every frame (yarn_clear), and that relax swings from frame to frame
# (the yarn's length jumps by up to ~1 R a frame and its fibres crawl). Here one rod carries from frame to frame: it can't
# stretch, is pulled softly toward choreo's design, is kept 2R off the fabric and itself, off the hook and the left hand, and
# each stretch of it (out of the fabric to the first loop, the loops on the hook, on to the hand) has the yarn the relax found
# that stretch needs (the design is drawn tighter than the yarn is thick), smoothed in time.
#   PHYS=1 python3 tools/choreo.py <key> build/paths/<key>.json ...     (or PHYS=1 tools/queue/chunks.sh <key>)
#   python3 tools/queue/physics_pass.py build/paths/<key>.json [out.json] [--keep-phys]
# Replaces the points of the current row's strand and the accent strand (same point counts, so slide/hold keep their meaning)
# in every frame that has choreo's "phys" record, then drops the records (--keep-phys: keeps them). Run it before matcoords.py.
# The rod restarts (on choreo's relaxed yarn of that frame) where the yarn's attachment to the fabric moves (a stitch closes).
# ROD="w_soft=20,..." overrides YarnRod's parameters; BUDGET (default 1) scales the per-stretch yarn, BUDGET_TAU its smoothing.
import sys, os, json, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import yarn_xpbd

src = sys.argv[1]; args = [a for a in sys.argv[2:] if not a.startswith("--")]
out_p = args[0] if args else src; KEEP = "--keep-phys" in sys.argv
D = json.load(open(src)); fps = D["fps"]
APP_R = D["frames"][0]["strands"][0]["radius"]; R = 1.0; K = APP_R / R
TO_APP = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
def des(a): return np.asarray(a, float) @ TO_APP / K           # app -> design space (choreo's R = 1)
def app(c): return [[round(float(x), 4) for x in p] for p in np.asarray(c) @ TO_APP.T * K]
KW = dict(x.split("=") for x in os.environ.get("ROD", "").split(",") if x)
BUDGET = float(os.environ.get("BUDGET", "1")); BTAU = float(os.environ.get("BUDGET_TAU", "0.3"))

# HOLD=1 (default): a frame that repeats the pose before it (the held camera: the same ta) keeps the yarn the rod gave that
# pose, so held frames stay identical (the renderer copies them) instead of the rod settling on through the hold
HOLD = os.environ.get("HOLD", "1") == "1"
rod, ext, last_e, n_done, resets, t0, held = None, None, None, 0, [], time.time(), None
for fi, fr in enumerate(D["frames"]):
    ph = fr.get("phys")
    if not ph or "hook" not in ph: rod = None; held = None; continue
    st = fr["strands"]; acc = [k for k, s in enumerate(st) if s.get("accent")][0]; cur = acc - 1
    if HOLD and held is not None and held[0] == fr.get("a"):
        st[cur]["pts"], st[acc]["pts"] = held[1], held[2]; n_done += 1; continue
    e, h, sp = ph["e"], ph["h"], ph["sp"]
    c = np.vstack([des(st[cur]["pts"]), des(st[acc]["pts"])[1:]])        # the yarn as choreo relaxed it: row, then working yarn
    assert len(c) >= h and np.allclose(des(st[cur]["pts"])[-1], des(st[acc]["pts"])[0], atol=1e-3), fi
    work = des(ph["work"])                                               # the working yarn as designed (c[e:h])
    old = c[e:h]
    if rod is None or abs(e - last_e) > 8:                              # a fresh start, or the attachment moved (choreo's own_e
                                                                         # index jitters by one point where the curve is re-splined)
        rod = yarn_xpbd.YarnRod(**{k: float(v) for k, v in KW.items()}); ext = None
        if last_e is not None: resets.append(fi)
    last_e = e
    # each stretch's yarn: as much more than designed as the relax made it, smoothed in time
    seg_d = np.linalg.norm(np.diff(work, axis=0), axis=1); seg_o = np.linalg.norm(np.diff(old, axis=0), axis=1)
    mk = [0, min(h - e - 1, max(0, sp + st[acc].get("slide", 0) - e)), min(h - e - 1, max(0, sp + st[acc].get("hold", 0) - e)), h - e - 1]
    mk = list(np.maximum.accumulate(mk))
    want = np.array([BUDGET * (seg_o[a:b].sum() - seg_d[a:b].sum()) for a, b in zip(mk[:-1], mk[1:])])
    ext = want if ext is None else ext + (want - ext) * (1 - np.exp(-1.0 / fps / BTAU))
    k = np.ones(len(seg_d))
    for (a, b), x in zip(zip(mk[:-1], mk[1:]), ext): k[a:b] = 1 + max(x, 0.0) / max(seg_d[a:b].sum(), 1e-6)
    mat = np.concatenate([[0.0], np.cumsum(seg_d * k)])
    if rod.x is None:                                                    # start on choreo's relaxed yarn, at the budget's places
        rod.s = rod._layout(mat[-1]); rod.x = yarn_xpbd.interp_curve(rod.s, mat, old); rod.v = np.zeros_like(rod.x)
    statics = [des(s["pts"]) for s in st[:cur] if s.get("visible") and len(s.get("pts", [])) > 1]
    fixed = np.vstack(statics + [c[:e]]) if e > 0 else (np.vstack(statics) if statics else None)
    lo, hi = work.min(0) - 6 * R, work.max(0) + 6 * R
    if fixed is not None: fixed = fixed[np.all((fixed > lo) & (fixed < hi), axis=1)]
    skin = des(ph["skin"]) if ph.get("skin") else None
    new = rod.step(work, 1.0 / fps, fixed=fixed, hook=des(ph["hook"]), hook_need=np.asarray(ph["need"]) * R, skin=skin, mat=mat)
    c[e:h] = new
    st[cur]["pts"] = app(c[:sp + 1]); st[acc]["pts"] = app(c[sp:]); n_done += 1
    held = (fr.get("a"), st[cur]["pts"], st[acc]["pts"])
if not KEEP:
    for fr in D["frames"]: fr.pop("phys", None)
json.dump(D, open(out_p, "w"))
lg = rod.log if rod else []
print("physics_pass: %d of %d frames remade, %d restarts %s, %.0f s -> %s" % (n_done, len(D["frames"]), len(resets), resets[:20], time.time() - t0, out_p))
