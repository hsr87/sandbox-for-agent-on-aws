#!/bin/sh
# Fairness follow-ups.
# A: empty host page cache on EKS, so that "first run" means the same as on a restored session.
# B: the base V2 runtime, no load, consecutive runs: does repeated use alone speed it up?
# C: the runtime that sped up earlier: is it still fast hours later?
# D: V2 and MicroVM with the CLI locked in memory before the snapshot, spaced apart like the low-rate rounds.
cd /work/bench
python deploy.py --which all > /work/deploy-pin.log 2>&1
python ops_experiments.py dropcache --backends eks-x86-gvisor,eks-x86-kata,eks-g3-gvisor --n 8 --round fair &
python run.py agent_e2e --backends ac-v2-probe --n 6 --round laterdec &
(python run.py agent_e2e --backends lm-probe --n 6 --round later; python run.py agent_e2e --backends ac-v2 --n 12 --round consecutive) &
for i in 1 2 3 4 5 6 7 8; do python run.py agent_e2e --backends ac-v2-pin,lm-pin --n 1 --round pin; sleep 150; done &
wait
echo "== CHAIN DONE fair"
