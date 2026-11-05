#!/bin/sh
# Repeat round: same scripts, later time. Fleet backends get more fresh sandboxes because their CPU varies per session.
R=$1; cd /work/bench
step(){ echo "== $(date -u +%H:%M:%S) $*"; "$@" || echo "!! FAILED: $*"; }
step sh /work/scripts/run_round.sh $R
step python run.py bench_suite --backends ac-v1,ac-v2,lm --sandboxes 8 --round $R
step python run.py bench_suite --backends eks-x86-runc,eks-x86-gvisor,eks-x86-kata,eks-g3-runc,eks-g3-gvisor --round $R
step python run.py agent_e2e --backends ac-v1,ac-v2,ac-v2-prewarm,lm,lm-prewarm,eks-x86-gvisor,eks-x86-kata,eks-g3-gvisor --n 8 --round $R
step python run.py burst --backends ac-v1,ac-v2,lm,eks-x86-gvisor --sizes 10,50 --settle 60 --round $R
step python run.py sustained --backends ac-v1,ac-v2,lm --sizes 2 --seconds 60 --settle 30 --round $R
echo "== CHAIN DONE $R"
