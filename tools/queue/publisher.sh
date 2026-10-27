#!/bin/sh
# lines of publish.txt: "<key> <fps> <dir...>"; published when every dir's render job is done
mkdir -p /home/user/crochet/build/queue; touch /home/user/crochet/build/queue/done.txt /home/user/crochet/build/queue/published.txt /home/user/crochet/build/queue/log.txt
cd /home/user/crochet
while true; do
  while read -r L; do
    [ -z "$L" ] && continue
    grep -qxF "$L" build/queue/published.txt 2>/dev/null && continue
    set -- $L; ok=1
    for d in $(echo "$L" | cut -d' ' -f3-); do grep -q " $d " build/queue/done.txt || ok=0; done
    [ $ok -eq 1 ] && tools/queue/publish.sh $L < /dev/null >> build/queue/publish.log 2>&1 && echo "$L" >> build/queue/published.txt
  done < build/queue/publish.txt
  sleep 60
done
