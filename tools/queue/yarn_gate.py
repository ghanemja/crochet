# The publish gate for yarn through yarn: the working yarn (the accent strand) against everything else.
#   python3 tools/queue/yarn_gate.py <paths.json> [step] [limit R] [--except a:b]
# Prints the frames over the limit and the fabric-vs-fabric worst (logged, not gated); exit 1 if any frame is over.
# --except a:b: frames a..b are measured and printed but not gated (a known exception, e.g. sc's pull-through close).
import sys, json
import numpy as np
EXC = (1, 0)
if "--except" in sys.argv:
    i = sys.argv.index("--except"); EXC = tuple(int(x) for x in sys.argv[i + 1].split(":")); del sys.argv[i:i + 2]
D = json.load(open(sys.argv[1])); step = int(sys.argv[2]) if len(sys.argv) > 2 else 6
LIM = float(sys.argv[3]) if len(sys.argv) > 3 else 0.65
bad, exc, worst, fab = [], [], (0.0, 0), (0.0, 0)
for fi in range(0, len(D["frames"]), step):
    st = [s for s in D["frames"][fi]["strands"] if s.get("visible") and len(s.get("pts", [])) > 1]
    R = st[0]["radius"]; acc = [i for i, s in enumerate(st) if s.get("accent")]
    if not acc: continue
    acc = acc[0]; A = np.asarray(st[acc]["pts"]); best = 0.0
    for j, s in enumerate(st):
        if j == acc: continue
        B = np.asarray(s["pts"]); d = np.linalg.norm(A[:, None] - B[None], axis=2)
        if j == acc - 1: d[:40, -40:] = np.inf                   # where the working yarn carries on from the row
        best = max(best, 2 - d.min() / R)
    if best > worst[0]: worst = (best, fi)
    if best > LIM: (exc if EXC[0] <= fi <= EXC[1] else bad).append((fi, round(best, 2)))
    if fi % (step * 4) == 0:                                     # fabric strands against each other, for the log
        for i in range(len(st)):
            for j in range(i + 1, len(st)):
                if acc in (i, j): continue
                d = np.linalg.norm(np.asarray(st[i]["pts"])[:, None] - np.asarray(st[j]["pts"])[None], axis=2)
                if j == i + 1: d[-40:, :40] = np.inf
                if 2 - d.min() / R > fab[0]: fab = (2 - d.min() / R, fi)
print("GATE working yarn worst %.2fR at frame %d; %d frames over %.2fR %s" % (worst[0], worst[1], len(bad), LIM, bad))
if exc: print("EXCEPT frames %d-%d over %.2fR (not gated): %s" % (EXC[0], EXC[1], LIM, exc))
print("LOG fabric vs fabric worst %.2fR at frame %d (not gated)" % fab)
sys.exit(1 if bad else 0)
