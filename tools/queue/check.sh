#!/bin/sh
# quick low-quality Cycles frames of a paths file: build/check.sh <key> <frames a:b:step> [angle]
K=$1; F=$2; AN=${3:-0}
B=/opt/blender-dl/blender-4.2.3-linux-x64/blender
rm -rf build/check/$K; mkdir -p build/check/$K
$B -b -P tools/render_tutorial.py -- build/paths/t_$K.json build/check/$K --angle $AN --frames $F --samples 6 --fibres 60 --res 480x300 > build/check/$K.log 2>&1
ffmpeg -y -loglevel error -pattern_type glob -i "build/check/$K/f_*.png" -f lavfi -i color=c=0xf3ece3:s=480x300 -filter_complex "[1][0]overlay=shortest=1,tile=4x$(( ($(ls build/check/$K/f_*.png | wc -l) + 3) / 4 ))" -frames:v 1 build/check/$K.jpg
echo done $K
