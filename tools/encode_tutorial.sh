#!/bin/sh
# Encode rendered frames (RGBA PNGs from render_tutorial.py, or opaque PNGs from
# capture) into assets/tutorials/<key>.webm|.mp4|.jpg, over the app's cream stage.
#   tools/encode_tutorial.sh <frames_dir> <key> [fps=30]
# WebM is two-pass VP9 aimed at ~1.35 MB whatever the length.
set -e
DIR=$1; KEY=$2; FPS=${3:-30}; OUT=${OUT:-assets/tutorials}; mkdir -p "$OUT"
N=$(ls "$DIR"/f_*.png | wc -l)
SIZE=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$(ls "$DIR"/f_*.png | head -1)")
KBPS=$(( 1350000 * 8 / 1000 * FPS / N )); [ $KBPS -gt 1500 ] && KBPS=1500
IN="-framerate $FPS -pattern_type glob -i $DIR/f_*.png"
BG="-f lavfi -i color=c=0xf3ece3:s=$SIZE:r=$FPS"
FLT="[1][0]overlay=format=auto:shortest=1,format=yuv420p"
LOG=$(mktemp -d)/vp9
ffmpeg -y -loglevel error $IN $BG -filter_complex "$FLT" -c:v libvpx-vp9 -b:v ${KBPS}k -row-mt 1 -pass 1 -passlogfile $LOG -an -f null /dev/null
ffmpeg -y -loglevel error $IN $BG -filter_complex "$FLT" -c:v libvpx-vp9 -b:v ${KBPS}k -row-mt 1 -pass 2 -passlogfile $LOG "$OUT/$KEY.webm"
ffmpeg -y -loglevel error $IN $BG -filter_complex "$FLT" -c:v libx264 -crf 23 -preset slow -movflags +faststart "$OUT/$KEY.mp4"
P=$(ls "$DIR"/f_*.png | sed -n "$(( N * 8 / 10 + 1 ))p")
ffmpeg -y -loglevel error -i "$P" $BG -filter_complex "[0][1]overlay=format=auto:shortest=1" -frames:v 1 -q:v 4 "$OUT/$KEY.jpg"
echo "$KEY: $N frames @ ${FPS}fps, webm $(stat -c%s "$OUT/$KEY.webm") B (${KBPS}k), mp4 $(stat -c%s "$OUT/$KEY.mp4") B"
