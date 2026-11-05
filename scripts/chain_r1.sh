#!/bin/sh
# Full measurement chain, run once inside the driver pod.
cd /work/bench
step(){ echo "== $(date -u +%H:%M:%S) $*"; "$@" || echo "!! FAILED: $*"; }
step sh /work/scripts/run_round.sh r1
C=ac-v1,ac-v2,lm,eks-x86-runc,eks-x86-gvisor,eks-x86-kata,eks-arm-runc,eks-arm-gvisor
step python run.py bench_suite --backends $C --round r1
step python run.py net_suite --backends $C --sandboxes 2 --round r1
A=ac-v1,ac-v2,ac-v2-prewarm,lm,lm-prewarm,eks-x86-gvisor,eks-x86-kata,eks-arm-gvisor
step python run.py agent_e2e --backends $A --n 12 --round r1
step python run.py agent_first_vs_repeat --backends $A --n 8 --round r1
step python run.py security --backends ac-v1,ac-v2,lm,eks-x86-runc,eks-x86-gvisor,eks-x86-kata,eks-arm-gvisor,eks-x86-gvisor-warm,eks-x86-kata-warm --label default --round r1
step python run.py state_wipe --backends ac-v1,ac-v2 --n 5 --round r1
step python run.py idle_reclaim --backends ac-v1-idle60,ac-v2-idle60 --n 3 --round r1
step python run.py suspend_resume --backends lm --sizes 0,512,2048 --n 12 --round r1
step python run.py microvm_idle_policy --backends lm --n 5 --round r1
step python run.py usage_sessions --backends ac-v1,ac-v2 --n 5 --round r1
step python run.py long_request --backends ac-v1,ac-v2,lm,eks-x86-gvisor,eks-x86-kata --seconds 1200 --round r1
echo "== CHAIN DONE $(date -u +%H:%M:%S)"
