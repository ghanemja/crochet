# One frame of a paths file seen from fixed close-up cameras (hand checks):
#   python3 tools/queue/closeup.py in.json frame out.json "dx,dy,dz@tx,ty,tz@dist" [...]
# Directions and targets in the design space of choreo.py (Z up, -Y toward the camera, yarn
# radius 1); each spec becomes a view (render it with render_tutorial.py --angle i).
import json, sys
import numpy as np
D = json.load(open(sys.argv[1])); fr = D["frames"][int(sys.argv[2])]
APP_R = 0.36
def app(p): return [p[0] * APP_R, p[2] * APP_R, -p[1] * APP_R]
views = []
for spec in sys.argv[4:]:
    d, t, dist = spec.split("@"); d = np.array(list(map(float, d.split(",")))); t = np.array(list(map(float, t.split(","))))
    d /= np.linalg.norm(d); pos = t + d * float(dist)
    views.append({"pos": app(pos), "target": app(t), "fov": 13.69, "aspect": 1.6, "name": spec, "hands": True})
fr = dict(fr); fr.pop("cam", None)
D["views"] = views; D["frames"] = [fr]
json.dump(D, open(sys.argv[3], "w"))
