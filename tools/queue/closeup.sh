#!/bin/sh
# close-ups of one frame from several cameras, tiled: tools/queue/closeup.sh <paths.json> <frame> <name> <quality: q|full> <spec>...
# (spec: see closeup.py). Writes build/closeup/<name>.jpg
P=$1; F=$2; N=$3; Q=$4; shift 4
B=/opt/blender-dl/blender-4.2.3-linux-x64/blender
mkdir -p build/closeup; rm -rf build/closeup/$N; mkdir -p build/closeup/$N
python3 tools/queue/closeup.py $P $F build/closeup/$N.json "$@" || exit 1
OPT="--samples 6 --fibres 60 --res 640x400"; [ "$Q" = full ] && OPT=""
i=0
for s in "$@"; do
  $B -b -P tools/render_tutorial.py -- build/closeup/$N.json build/closeup/$N/a$i --angle $i --zoom 1.0001 $OPT > build/closeup/$N.log 2>&1
  i=$((i + 1))
done
set -f
ffmpeg -y -loglevel error -pattern_type glob -i "build/closeup/$N/a*/f_0000.png" -filter_complex "tile=2x$(( (i + 1) / 2 ))" -frames:v 1 build/closeup/$N.jpg && echo build/closeup/$N.jpg
