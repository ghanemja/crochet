#!/bin/sh
# render queue: each line of jobs.txt is "<paths.json> <out_dir> <angle> [frames [renderer flags...]]"; done jobs are listed in done.txt.
mkdir -p /home/user/crochet/build/queue; touch /home/user/crochet/build/queue/done.txt /home/user/crochet/build/queue/published.txt /home/user/crochet/build/queue/log.txt
cd /home/user/crochet
B=/opt/blender-dl/blender-4.2.3-linux-x64/blender
while true; do
  J=$(grep -vxF -f build/queue/done.txt build/queue/jobs.txt 2>/dev/null | grep -v '^#' | head -1)
  [ -z "$J" ] && { sleep 60; continue; }
  set -- $J; P=$1 O=$2 AN=$3 FR=${4:-0:-1:1}; shift 3; [ $# -gt 0 ] && shift
  echo "$(date) START $J" >> build/queue/log.txt
  $B -b -P tools/render_tutorial.py -- $P $O --angle $AN --frames $FR --skip-existing "$@" > build/queue/blender.log 2>&1
  if [ $? -eq 0 ]; then echo "$J" >> build/queue/done.txt; echo "$(date) DONE $J" >> build/queue/log.txt
  else echo "$(date) FAIL $J" >> build/queue/log.txt; sleep 30; fi
done
