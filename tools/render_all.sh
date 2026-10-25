#!/bin/sh
# Route B batch: export paths (needs the app served on :8765), render in Cycles,
# encode. Resumable — already-rendered frames are skipped.
#   BLENDER=/path/to/blender tools/render_all.sh "sc:30 dc:30 ch:15 ..."
# key:fps — 15 fps renders every other exported (30 fps) frame.
set -e
BLENDER=${BLENDER:-blender}
for kf in ${1:-sc:30 dc:30 hdc:15 tr:15 ch:15 sl:15 inc:15 dec:15 mr:15}; do
  KEY=${kf%%:*}; FPS=${kf##*:}; STEP=$(( 30 / FPS ))
  [ -f build/paths/$KEY.json ] || node tools/export_paths.mjs $KEY
  nice -n 10 "$BLENDER" -b -P tools/render_tutorial.py -- build/paths/$KEY.json build/frames/$KEY \
      --frames 0:-1:$STEP --skip-existing 2>&1 | grep --line-buffered -E "^frame|Error|Traceback"
  tools/encode_tutorial.sh build/frames/$KEY $KEY $FPS
done
