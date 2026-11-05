#!/bin/sh
cd /work/bench
step(){ echo "== $(date -u +%H:%M:%S) $*"; "$@" || echo "!! FAILED: $*"; }
step python run.py idle_reclaim --backends ac-v1-idle60 --waits 180,240,300,420,600,900 --n 3 --round r1
step python run.py burst --backends ac-v1,ac-v2,lm,ac-v1-large,ac-v2-large,lm-large --sizes 10,50,100 --settle 60 --round r1
step python run.py sustained --backends ac-v1,ac-v2,lm,ac-v1-large,ac-v2-large --sizes 1,5,10 --seconds 120 --settle 60 --round r1
echo "== CHAIN DONE r1b"
step python run.py long_request --backends ac-v1,ac-v2,lm --seconds 840 --round r1b
step python run.py long_request --backends ac-v1,ac-v2,lm --seconds 960 --round r1b
echo "== CHAIN DONE r1b2"
