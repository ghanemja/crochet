# Quick line-drawing preview of a tutorial paths JSON (no Blender): a contact sheet of frames.
#
#   python3 tools/preview_paths.py build/paths/dc.json build/preview/dc.png [--every 12] [--angle 0]
#
# Strands are drawn as thick depth-sorted segments in their colours (fabric blue, working yarn
# orange, rows by shade), the hook as a grey line, through each frame's camera. Enough to check
# a choreography's topology and timing before spending hours in Cycles.
import json, math, argparse
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

ap = argparse.ArgumentParser()
ap.add_argument("paths"); ap.add_argument("out")
ap.add_argument("--every", type=int, default=12); ap.add_argument("--angle", type=int, default=0)
ap.add_argument("--frames", default="")          # comma list overrides --every
ap.add_argument("--cols", type=int, default=6); ap.add_argument("--dpi", type=int, default=70)
A = ap.parse_args()
D = json.load(open(A.paths))
F = D["frames"]
idx = [int(x) for x in A.frames.split(",")] if A.frames else list(range(0, len(F), A.every)) + [len(F) - 1]

def hexrgb(h, k=1.0):
    h = h.lstrip("#"); return [min(1, int(h[i:i + 2], 16) / 255 * k) for i in (0, 2, 4)]

def proj(cam, pts):
    eye, tgt = np.array(cam["pos"]), np.array(cam["target"]); f = tgt - eye; f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, f); th = math.tan(math.radians(cam["fov"]) / 2)
    q = np.asarray(pts) - eye; z = q @ f
    return np.stack([(q @ r) / z / th / cam.get("aspect", 1.6), (q @ u) / z / th], 1), z

def hook_line(h):
    x, y, z, w = h["quat"]
    up = np.array([2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w)])
    p = np.array(h["pos"]); return np.array([p + up * s for s in np.linspace(0, 30, 16)])

rows = math.ceil(len(idx) / A.cols)
fig, axs = plt.subplots(rows, A.cols, figsize=(A.cols * 3.2, rows * 2.1))
for ax in np.ravel(axs): ax.axis("off")
for ax, fi in zip(np.ravel(axs), idx):
    fr = F[fi]
    cam = fr["cam"] if (A.angle == 0 and fr.get("cam")) else D["views"][A.angle]
    segs, cols, zs, lw = [], [], [], []
    scale = 1.0 / math.tan(math.radians(cam["fov"]) / 2)
    for st in fr["strands"]:
        if not st.get("visible"): continue
        c = hexrgb(D["accent"] if st.get("accent") else D["yarn"], st.get("shade", 1.0))
        xy, z = proj(cam, st["pts"])
        for i in range(len(xy) - 1):
            segs.append(xy[i:i + 2]); cols.append(c); zs.append((z[i] + z[i + 1]) / 2); lw.append(2 * st["radius"] / z[i] * scale * 60)
    xy, z = proj(cam, hook_line(fr["hook"]))
    for i in range(len(xy) - 1):
        segs.append(xy[i:i + 2]); cols.append([0.55, 0.57, 0.6]); zs.append((z[i] + z[i + 1]) / 2); lw.append(2 * 1.15 * 0.36 / z[i] * scale * 60)
    o = np.argsort(zs)[::-1]
    ax.add_collection(LineCollection([segs[i] for i in o], colors=[cols[i] for i in o], linewidths=[lw[i] for i in o], capstyle="round"))
    ax.set_xlim(-1, 1); ax.set_ylim(-1, 1); ax.set_aspect(1 / 1.6); ax.set_facecolor("#f3ece3"); ax.axis("on")
    ax.set_xticks([]); ax.set_yticks([]); ax.set_title("%d  t=%.2f" % (fi, fr["t"]), fontsize=7)
plt.tight_layout(); plt.savefig(A.out, dpi=A.dpi); print("wrote", A.out, len(idx), "frames")
