#!/bin/sh
# publish one stitch: tools/queue/publish.sh <key> <fps> <dir0> [dir1 dir2 dir3]
cd /home/user/crochet
KEY=$1; FPS=$2; shift 2; NV=$#
# yarn through yarn: the working yarn kept off everything else (build/queue/gate_except_<key>: "a:b" frames not gated)
# (SKIP_YARN_GATE=1: a stitch rendered from paths made before the gate existed, published as a base version)
EXC=$(cat build/queue/gate_except_$KEY 2>/dev/null); G=$(python3 tools/queue/yarn_gate.py build/paths/$KEY.json 6 0.65 ${EXC:+--except $EXC})
GS=$?; [ "$SKIP_YARN_GATE" = 1 ] && GS=0 && G="$G (gate skipped: base version)"; echo "$(date) $KEY $G" | tr '\n' ' ' >> build/queue/log.txt; echo >> build/queue/log.txt
[ $GS -eq 0 ] || { echo "$(date) GATEFAIL $KEY" >> build/queue/log.txt; exit 1; }
tools/encode_views.sh $KEY $FPS "$@" || exit 1
cp build/paths/$KEY.cues.json assets/tutorials/$KEY.cues.json
python3 - "$KEY" "$NV" <<'PY'
import json, sys, os
k, nv = sys.argv[1], int(sys.argv[2]); p = "assets/tutorials/manifest.json"
m = json.load(open(p)) if os.path.exists(p) else {}
m[k] = {"views": ["Guided", "Front", "Side", "Behind"], "grid": [2, 2], "cues": True} if nv == 4 else {"views": ["Guided"], "grid": [1, 1], "cues": True}
order = "ch sl sc hdc dc tr inc dec mr".split()
json.dump({x: m[x] for x in sorted(m, key=order.index)}, open(p, "w"), indent=1); open(p, "a").write("\n")
PY
git add assets/tutorials/$KEY.views.webm assets/tutorials/$KEY.views.mp4 assets/tutorials/$KEY.views.jpg assets/tutorials/$KEY.cues.json assets/tutorials/manifest.json
V=$([ $NV -eq 4 ] && echo "four angles (Guided, Front, Side, Behind)" || echo "the Guided view")
git commit -q -m "Tutorial: $KEY rendered, $V

Cycles render of tools/choreo*.py at ${FPS} fps, with freeze-frame callouts.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RFXApAbCj3oAniAKo1gr3k" || exit 1
for d in 2 4 8 16 32; do git pull -q --rebase --autostash origin main && git push -q -u origin main && { echo "$(date) PUBLISHED $KEY $NV" >> build/queue/log.txt; exit 0; }; sleep $d; done
echo "$(date) PUSHFAIL $KEY" >> build/queue/log.txt; exit 1
