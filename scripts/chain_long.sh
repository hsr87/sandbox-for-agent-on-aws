#!/bin/sh
cd /work/bench
python deploy.py --which all
for s in 120 300 360 600; do python run.py long_request --backends ac-v1,ac-v2 --seconds $s --round r1d & done
python run.py long_request --backends ac-v1-probe3,ac-v2-probe3,lm-probe3 --seconds 1500 --long-op stream_sleep --round r1d &
wait
echo "== CHAIN DONE long"
