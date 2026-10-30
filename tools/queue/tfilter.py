# Motion-masked temporal smoothing of rendered frames, before encoding:
#   python3 tools/queue/tfilter.py <frames dir> <out dir> [tau] [window] [dilate px]
# Each frame is averaged with its neighbours only where the picture barely changes between them (the still
# yarn's fibres, whose denoised noise shifts a little from frame to frame as the hook and hands move); where it
# changes more than tau (real motion: the hook, loops, hands) the frame is left as it is, so nothing ghosts.
import sys, os, glob
import numpy as np
from PIL import Image, ImageFilter

src, dst = sys.argv[1], sys.argv[2]
tau = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0          # 0..255, on the blurred luminance change
WIN = int(sys.argv[4]) if len(sys.argv) > 4 else 1                # neighbours each side (2: a 5-frame average where still)
DIL = int(sys.argv[5]) if len(sys.argv) > 5 else 0                # grow the moving region by this many px (no ghost at its edge)
os.makedirs(dst, exist_ok=True)
files = sorted(glob.glob(os.path.join(src, "f_*.png")))

def load(i):
    return np.asarray(Image.open(files[i]).convert("RGBA"), np.float32)

def change(a, b):
    """the frame-to-frame change, as blurred luminance (so a single fibre's flicker doesn't count as motion)"""
    d = np.abs(a[..., :3] - b[..., :3]).mean(2)
    return np.asarray(Image.fromarray(np.clip(d, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), np.float32)

cache = {}
def get(i):
    if i not in cache: cache[i] = load(i)
    for k in [k for k in cache if k < i - WIN]: del cache[k]
    return cache[i]

for i, f in enumerate(files):
    out = os.path.join(dst, os.path.basename(f))
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(f): continue
    cur = get(i); idx = [j for j in range(i - WIN, i + WIN + 1) if j != i and 0 <= j < len(files)]
    if not idx:
        Image.fromarray(cur.astype(np.uint8), "RGBA").save(out); continue
    acc, wsum = cur.copy(), np.ones(cur.shape[:2], np.float32)
    for j in sorted(idx, key=lambda j: abs(j - i)):
        n = get(j); ch = change(cur, n)
        if DIL: ch = np.asarray(Image.fromarray(np.clip(ch, 0, 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * DIL + 1)), np.float32)
        w = np.clip((tau - ch) / tau, 0, 1) / abs(j - i)        # 1 where still, 0 where moving; farther frames count less
        acc += n * w[..., None]; wsum += w
    res = acc / wsum[..., None]
    res[..., 3] = cur[..., 3]
    Image.fromarray(np.clip(res + 0.5, 0, 255).astype(np.uint8), "RGBA").save(out)
