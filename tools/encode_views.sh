#!/bin/sh
# Encode the camera angles of one tutorial take into a single video: four angles as a 2×2 grid
# (frame-locked; the app shows one tile at a time), or one angle on its own.
#   tools/encode_views.sh <key> <fps> <frames_dir_view0> [<view1> <view2> <view3>]
# -> assets/tutorials/<key>.views.webm|.mp4|.jpg  (constant-quality VP9 / H.264: the yarn's fibres
#    smear in motion at a fixed small size, so quality is held and the size follows — ~4 MB for a
#    20 s single view at crf 30; the fibres' encoding error changed frame to frame and read as crawl, so
#    crf 24 / 27 (grid): ~1.5x the size; QUALITY=<vp9 crf> overrides)
set -e
KEY=$1; FPS=$2; shift 2; OUT=${OUT:-assets/tutorials}; mkdir -p "$OUT"
NV=$#; [ $NV -eq 1 ] || [ $NV -eq 4 ] || { echo "need 1 or 4 frame dirs" >&2; exit 1; }
N=$(ls "$1"/f_*.png | wc -l)
SIZE=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$(ls "$1"/f_*.png | head -1)")
set -f   # keep the f_*.png patterns for ffmpeg, not the shell
IN=""; for d in "$@"; do IN="$IN -framerate $FPS -pattern_type glob -i $d/f_*.png"; done
BG="-f lavfi -i color=c=0xf3ece3:s=$SIZE:r=$FPS"
if [ $NV -eq 4 ]; then
  # each tile is placed over its own copy of the background: split it four ways
  FLT="[4]split=4[g0][g1][g2][g3];[g0][0]overlay=format=auto:shortest=1[a];[g1][1]overlay=format=auto:shortest=1[b];[g2][2]overlay=format=auto:shortest=1[c];[g3][3]overlay=format=auto:shortest=1[d];[a][b][c][d]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0,format=yuv420p"
  VCRF=${QUALITY:-27}; CRF=19
else
  FLT="[1][0]overlay=format=auto:shortest=1,format=yuv420p"
  VCRF=${QUALITY:-24}; CRF=18
fi
ffmpeg -y -loglevel error $IN $BG -filter_complex "$FLT" -c:v libvpx-vp9 -crf $VCRF -b:v 0 -row-mt 1 -deadline good -cpu-used 2 "$OUT/$KEY.views.webm"
ffmpeg -y -loglevel error $IN $BG -filter_complex "$FLT" -c:v libx264 -crf $CRF -preset slow -movflags +faststart "$OUT/$KEY.views.mp4"
ffmpeg -y -loglevel error -sseof -3 -i "$OUT/$KEY.views.mp4" -frames:v 1 -q:v 4 "$OUT/$KEY.views.jpg"
echo "$KEY: $N frames x $NV view(s) @ ${FPS}fps, webm $(stat -c%s "$OUT/$KEY.views.webm") B, mp4 $(stat -c%s "$OUT/$KEY.views.mp4") B"
