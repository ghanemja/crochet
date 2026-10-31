# Resumable path generation: choreo.py's own frame loop run over chunks of frames, each written as it completes
# (a container restart only loses the chunk in progress; several workers share the cores). Output is identical to
# choreo.py's. tools/queue/chunks.sh runs the workers and merges.
#   CHUNK=24 WORKER=w WORKERS=n python3 tools/queue/chunkgen.py <key>  -> build/chunks/<key>_<start>.json (frames only)
#   CHUNK=24 python3 tools/queue/chunkgen.py <key> merge <out.json> <cues.json>      -> the full paths file and cues, as choreo.py writes them
import sys, os, json
src = open("tools/choreo.py").read()
c_loop = src.index("cache = {}; frames = []"); c_cues = src.index("# ---------------------------------------------------------------- callouts")
c_tail = src.index('json.dump({"key": KEY')
key = sys.argv[1]; merge = len(sys.argv) > 2 and sys.argv[2] == "merge"
out = sys.argv[3] if merge else "/dev/null"; cues = sys.argv[4] if merge else ""
sys.argv = ["choreo.py", key, out, "--hands"] + (["--cues", cues] if cues else [])
g = {"__file__": os.path.abspath("tools/choreo.py"), "__name__": "choreo_chunk"}
exec(compile(src[:c_loop], "choreo_head", "exec"), g)
D = "build/chunks"; os.makedirs(D, exist_ok=True); n = g["n"]
if not merge:
    size, w, W = int(os.environ["CHUNK"]), int(os.environ["WORKER"]), int(os.environ["WORKERS"])
    body = src[c_loop:c_cues].replace("for i in range(min(n, A.max_frames) if A.max_frames else n):", "for i in RANGE:")
    for ci, s in enumerate(range(0, n, size)):
        if ci % W != w: continue
        p = os.path.join(D, "%s_%05d.json" % (key, s))
        if os.path.exists(p): continue
        g["RANGE"] = range(s, min(n, s + size)); exec(compile(body, "choreo_frames", "exec"), g)
        json.dump(g["frames"], open(p + ".tmp", "w")); os.replace(p + ".tmp", p); print("chunk", s, flush=True)
    if all(os.path.exists(os.path.join(D, "%s_%05d.json" % (key, s_))) for s_ in range(0, n, size)):
        open(os.path.join(D, key + ".complete"), "w").close()          # chunks.sh merges it and starts no more workers for it
    print("worker done", w)
else:
    frames = []
    for s in range(0, n, int(os.environ["CHUNK"])):
        frames += json.load(open(os.path.join(D, "%s_%05d.json" % (key, s))))
    assert len(frames) == n, (len(frames), n)
    g["frames"] = frames; g["cache"] = {}
    exec(compile(src[c_cues:c_tail], "choreo_cues", "exec"), g)
    exec(compile(src[c_tail:], "choreo_out", "exec"), g)
