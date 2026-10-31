#!/bin/sh
# paths for some stitches in resumable chunks (tools/queue/chunkgen.py): tools/queue/chunks.sh <key> [key ...]
# Starts WORKERS (default 4) background workers that go through the keys in order, unless they are running; a key
# whose chunks are all done (and no worker is on it) is merged into build/paths/<key>.json + <key>.cues.json.
# Idempotent: run it again after a container restart, or to merge. Remove build/chunks/<key>_* to regenerate a key.
cd /home/user/crochet; mkdir -p build/chunks; N=${WORKERS:-4}; C=${CHUNK:-24}
for w in $(seq 0 $((N - 1))); do
  pgrep -f "chunkworker $w\$" >/dev/null && continue
  nohup setsid sh -c "for k in $*; do CHUNK=$C WORKER=$w WORKERS=$N python3 tools/queue/chunkgen.py \$k; done # chunkworker $w" > build/chunks/w$w.log 2>&1 < /dev/null &
done
for k in "$@"; do
  [ -f build/paths/$k.json ] && [ build/paths/$k.json -nt build/chunks/w0.log ] && continue
  ps -eo args | grep -q "^python3 tools/queue/chunkgen.py $k\$" && continue
  CHUNK=$C python3 tools/queue/chunkgen.py $k merge build/paths/$k.json build/paths/$k.cues.json 2>&1 | tail -1
done
