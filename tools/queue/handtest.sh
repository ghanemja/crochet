#!/bin/sh
# quick look at the hands: build/handtest.sh <name>  (env L_PINCH / L_FINGERS)
python3 tools/choreo.py sc build/paths/hand_$1.json --hands --max-frames 1 > /dev/null || exit 1
/opt/blender-dl/blender-4.2.3-linux-x64/blender -b -P tools/render_tutorial.py -- build/paths/hand_$1.json build/handtest/$1 --frames 0:0:1 --samples 8 --fibres 80 > /dev/null 2>&1
ffmpeg -y -loglevel error -i build/handtest/$1/f_0000.png -f lavfi -i color=c=0xf3ece3:s=800x500 -filter_complex "[1][0]overlay=format=auto:shortest=1" -frames:v 1 build/handtest/$1.jpg && echo build/handtest/$1.jpg
