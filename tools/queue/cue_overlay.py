# Check the freeze-frame callouts against the render: draws each cue's ring, trace and arrow (as the app
# does: x, y in frame fractions, r in frame heights) over the rendered frame at the cue's time.
#   python3 tools/queue/cue_overlay.py <key>.cues.json <frames dir> <out.jpg> [view index]
import sys, json, glob, os
from PIL import Image, ImageDraw
cues, fdir, out = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
vi = int(sys.argv[4]) if len(sys.argv) > 4 else 0
fps = 24; tiles = []
for c in cues["cues"]:
    f = os.path.join(fdir, "f_%04d.png" % round(c["t"] * fps))
    if not os.path.exists(f): print("missing", f); continue
    im = Image.open(f).convert("RGB"); W, H = im.size; d = ImageDraw.Draw(im); w = c["views"][vi]
    for key, col in (("trace", (255, 220, 0)), ("arrow", (0, 200, 255))):
        if w.get(key): d.line([(x * W, y * H) for x, y in w[key]], fill=col, width=3)
    r = max(4 / 100, w["r"]) * H; d.ellipse([w["x"] * W - r, w["y"] * H - r, w["x"] * W + r, w["y"] * H + r], outline=(255, 0, 80), width=3)
    d.text((8, 8), "%.2fs  %s" % (c["t"], c["text"]), fill=(0, 0, 0)); tiles.append(im)
if tiles:
    W, H = tiles[0].size; cols = 2; rows = (len(tiles) + 1) // 2
    sheet = Image.new("RGB", (W * cols, H * rows), (255, 255, 255))
    for i, t in enumerate(tiles): sheet.paste(t, ((i % cols) * W, (i // cols) * H))
    sheet.save(out); print(out)
