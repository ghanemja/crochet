# Flicker metric: mean frame-to-frame change (luma, 0-255) on still areas, and on moving yarn after motion
# compensation (the previous frame warped onto the current one by DIS optical flow).
#   python3 tools/queue/flicker_metric.py <ref frames dir|video> <test frames dir|video> [...more tests]
# The still / moving masks come from the reference (so every test is measured on the same pixels): still = flow
# under 0.25 px, moving = flow over 1 px, both only on the work, hands and hook (not the empty stage), minus occlusions (where even the reference's warp misses by > 30).
# Lower is steadier. Frames: f_*.png (alpha composited over the stage colour) or any video ffmpeg can read.
import sys, os, glob, subprocess, tempfile
import numpy as np
import cv2

BG = np.array([227, 235, 243], np.float32)          # the stage #f3ece3, BGR

def load(src):
    if os.path.isdir(src):
        out = []
        for f in sorted(glob.glob(os.path.join(src, "f_*.png"))):
            im = cv2.imread(f, cv2.IMREAD_UNCHANGED).astype(np.float32)
            if im.shape[2] == 4: a = im[..., 3:] / 255.0; im = im[..., :3] * a + BG * (1 - a)
            out.append(cv2.cvtColor(im.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32))
        return out
    d = tempfile.mkdtemp()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", src, os.path.join(d, "f_%04d.png")], check=True)
    return load(d)

dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
def flow(a, b):
    """for each pixel of a, where it is in b"""
    return dis.calc(a.astype(np.uint8), b.astype(np.uint8), None)
def warp(img, fl):
    h, w = img.shape; gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(img, gx + fl[..., 0], gy + fl[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

ref = load(sys.argv[1]); masks = []
BGL = cv2.cvtColor(BG.reshape(1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2GRAY)[0, 0]
for t in range(1, len(ref)):
    fl = flow(ref[t], ref[t - 1]); mag = np.linalg.norm(fl, axis=2)
    occl = np.abs(warp(ref[t - 1], fl) - ref[t]) > 30
    obj = cv2.erode((np.abs(ref[t] - BGL) > 8).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0   # not the stage
    masks.append((fl, (mag < 0.25) & obj, (mag > 1.0) & ~occl & obj))

def score(fr):
    st, mv = [], []
    for t in range(1, min(len(fr), len(ref))):
        fl, still, moving = masks[t - 1]
        st.append(np.abs(fr[t] - fr[t - 1])[still].mean())
        if moving.any(): mv.append(np.abs(warp(fr[t - 1], fl) - fr[t])[moving].mean())
    return np.mean(st), (np.mean(mv) if mv else float("nan"))

print("%-40s %8s %8s" % ("", "still", "moving"))
for src in sys.argv[1:]:
    s, m = score(load(src) if src != sys.argv[1] else ref)
    print("%-40s %8.3f %8.3f" % (os.path.basename(src.rstrip("/")) or src, s, m))
