#!/bin/sh
# restart the render queue and publisher if they are not running (renders resume with --skip-existing)
cd /home/user/crochet
if ! pgrep -f '^/bin/sh tools/queue/run.sh' >/dev/null; then
  pkill -f '^/opt/blender-dl/'
  # the job that was running may have left a half-written last frame
  J=$(grep -vxF -f build/queue/done.txt build/queue/jobs.txt | head -1); d=$(echo "$J" | cut -d' ' -f2)
  f=$(ls $d/f_*.png 2>/dev/null | tail -1); [ -n "$f" ] && rm -f "$f"
  nohup setsid tools/queue/run.sh >/dev/null 2>&1 & echo "restarted run.sh"
fi
pgrep -f '^/bin/sh tools/queue/publisher.sh' >/dev/null || { nohup setsid tools/queue/publisher.sh >/dev/null 2>&1 & echo "restarted publisher.sh"; }
echo "queue: $(tail -1 build/queue/log.txt)"; grep "frame " build/queue/blender.log | tail -1
