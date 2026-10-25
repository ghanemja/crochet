#!/bin/sh
# Encode several camera angles of one tutorial take into a single 2×2 grid video,
# so the angles stay frame-locked; the app shows one tile at a time.
#   tools/encode_views.sh <key> <fps> <frames_dir_view0> <view1> <view2> <view3>
# -> assets/tutorials/<key>.views.webm|.mp4|.jpg  (WebM two-pass VP9 aimed at ~2.8 MB)
set -e
KEY=$1; FPS=$2; shift 2; OUT=${OUT:-assets/tutorials}; mkdir -p "$OUT"
N=$(ls "$1"/f_*.png | wc -l)
SIZE=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$(ls "$1"/f_*.png | head -1)")
IN=""; for d in "$@"; do IN="$IN -framerate $FPS -pattern_type glob -i $d/f_*.png"; done
BG="-f lavfi -i color=c=0xf3ece3:s=$SIZE:r=$FPS"
# each tile is placed over its own copy of the background: split it four ways
FLT="[4]split=4[g0][g1][g2][g3];[g0][0]overlay=format=auto:shortest=1[a];[g1][1]overlay=format=auto:shortest=1[b];[g2][2]overlay=format=auto:shortest=1[c];[g3][3]overlay=format=auto:shortest=1[d];[a][b][c][d]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0,format=yuv420p"
KBPS=$(( 2800000 * 8 / 1000 * FPS / N )); [ $KBPS -gt 3000 ] && KBPS=3000
LOG=$(mktemp -d)/vp9
ffmpeg -y -loglevel error $IN $BG -filter_complex "$FLT" -c:v libvpx-vp9 -b:v ${KBPS}k -row-mt 1 -pass 1 -passlogfile $LOG -an -f null /dev/null
ffmpeg -y -loglevel error $IN $BG -filter_complex "$FLT" -c:v libvpx-vp9 -b:v ${KBPS}k -row-mt 1 -pass 2 -passlogfile $LOG "$OUT/$KEY.views.webm"
ffmpeg -y -loglevel error $IN $BG -filter_complex "$FLT" -c:v libx264 -crf 24 -preset slow -movflags +faststart "$OUT/$KEY.views.mp4"
ffmpeg -y -loglevel error -sseof -3 -i "$OUT/$KEY.views.mp4" -frames:v 1 -q:v 4 "$OUT/$KEY.views.jpg"
echo "$KEY: $N frames x 4 views @ ${FPS}fps, webm $(stat -c%s "$OUT/$KEY.views.webm") B, mp4 $(stat -c%s "$OUT/$KEY.views.mp4") B"
