#!/bin/sh
cd /work/bench
step(){ echo "== $(date -u +%H:%M:%S) $*"; "$@" || echo "!! FAILED: $*"; }
step python run.py usage_sessions --backends ac-v1,ac-v2 --n 5 --alloc-mb 0 --cpu-s 0 --idle-s 300 --round r1c
step python run.py usage_agent --backends ac-v1,ac-v2 --n 5 --idle-s 300 --round r1c
step python run.py long_request --backends ac-v1,ac-v2,lm --seconds 840 --round r1b
step python run.py long_request --backends ac-v1,ac-v2,lm --seconds 960 --round r1b
echo "== CHAIN DONE r1c"
