# Motion-compensated temporal smoothing of rendered frames (flicker idea 5), for the shimmer on things that move:
#   python3 tools/queue/mcfilter.py <frames dir> <out dir> [tau] [window]
# Each neighbour is warped onto the frame by optical flow (DIS), then averaged in only where the warped picture
# agrees with the frame (within tau, on the blurred difference): moving yarn is smoothed along its motion, and
# where the flow is wrong (occlusions, the yarn sliding through a loop) the frame is left as it is.
import sys, os, glob
import numpy as np
import cv2

src, dst = sys.argv[1], sys.argv[2]
tau = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0
WIN = int(sys.argv[4]) if len(sys.argv) > 4 else 2
os.makedirs(dst, exist_ok=True)
files = sorted(glob.glob(os.path.join(src, "f_*.png")))
dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)

cache = {}
def get(i):
    if i not in cache:
        im = cv2.imread(files[i], cv2.IMREAD_UNCHANGED).astype(np.float32)
        if im.shape[2] == 3: im = np.dstack([im, np.full(im.shape[:2], 255, np.float32)])
        cache[i] = (im, cv2.cvtColor(im[..., :3].astype(np.uint8), cv2.COLOR_BGR2GRAY))
    for k in [k for k in cache if k < i - WIN]: del cache[k]
    return cache[i]

def warp_onto(cur_g, nb, nb_g):
    """nb warped onto the current frame: for each pixel of the current frame, where it was in nb"""
    flow = dis.calc(cur_g, nb_g, None)
    h, w = cur_g.shape; gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(nb, gx + flow[..., 0], gy + flow[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

for i, f in enumerate(files):
    out = os.path.join(dst, os.path.basename(f))
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(f): continue
    cur, cur_g = get(i)
    acc, wsum = cur.copy(), np.ones(cur.shape[:2], np.float32)
    for j in sorted((j for j in range(i - WIN, i + WIN + 1) if j != i and 0 <= j < len(files)), key=lambda j: abs(j - i)):
        nb, nb_g = get(j); wn = warp_onto(cur_g, nb, nb_g)
        d = cv2.GaussianBlur(np.abs(wn[..., :3] - cur[..., :3]).mean(2), (0, 0), 2.0)
        wt = np.clip((tau - d) / tau, 0, 1) / abs(j - i)
        acc += wn * wt[..., None]; wsum += wt
    res = acc / wsum[..., None]; res[..., 3] = cur[..., 3]
    cv2.imwrite(out, np.clip(res + 0.5, 0, 255).astype(np.uint8))
