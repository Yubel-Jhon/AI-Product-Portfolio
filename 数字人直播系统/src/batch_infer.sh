#!/bin/bash
# 远端批量跑 SadTalker，串行生成 4 个 demo 视频
cd /root/autodl-tmp/SadTalker
LOG=/root/autodl-tmp/batch.log
for i in 0 1 2 3; do
  echo "===== demo_$i START $(date '+%H:%M:%S') =====" >> "$LOG"
  /root/miniconda3/bin/python inference.py \
    --driven_audio "/root/autodl-tmp/demo_$i.mp3" \
    --source_image /root/autodl-tmp/face.png \
    --result_dir /root/autodl-tmp/results_demo \
    --still --preprocess full --size 256 \
    >> "$LOG" 2>&1
  latest=$(ls -t /root/autodl-tmp/results_demo/*.mp4 2>/dev/null | head -1)
  cp "$latest" "/root/autodl-tmp/demo_$i.mp4"
  echo "===== demo_$i DONE -> $latest =====" >> "$LOG"
done
echo "ALL DONE $(date '+%H:%M:%S')" >> "$LOG"
