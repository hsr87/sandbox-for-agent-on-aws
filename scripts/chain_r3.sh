#!/bin/sh
# Repeat round: same scripts, later time. Fleet backends get more fresh sandboxes because their CPU varies per session.
R=$1; cd /work/bench
step(){ echo "== $(date -u +%H:%M:%S) $*"; "$@" || echo "!! FAILED: $*"; }
step sh /work/scripts/run_round.sh $R
step python run.py bench_suite --backends ac-v1,ac-v2,lm --sandboxes 8 --round $R
step python run.py bench_suite --backends eks-x86-runc,eks-x86-gvisor,eks-x86-kata,eks-g3-runc,eks-g3-gvisor --round $R
step python run.py agent_e2e --backends ac-v1,ac-v2,ac-v2-prewarm,lm,lm-prewarm,eks-x86-gvisor,eks-x86-kata,eks-g3-gvisor --n 8 --round $R
# EKS runs on one node per runtime here, so only 10 fits. The 50 and 100 cases need the 4-node setup in chain_eks_burst.sh.
step python run.py burst --backends ac-v1,ac-v2,lm --sizes 10,50 --settle 60 --round $R
step python run.py burst --backends eks-x86-gvisor --sizes 10 --settle 30 --round $R
step python run.py sustained --backends ac-v1,ac-v2,lm --sizes 2 --seconds 60 --settle 30 --round $R
for n in 300 360; do python run.py long_request --backends ac-v1,ac-v2 --seconds $n --round $R & done
python run.py long_request --backends ac-v1-probe3,ac-v2-probe3,lm-probe3 --seconds 1500 --long-op stream_sleep --round $R &
wait
echo "== CHAIN DONE $R"
