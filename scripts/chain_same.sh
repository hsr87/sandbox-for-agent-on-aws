#!/bin/sh
# Same period, shuffled order, new managed runtimes, one arrival pattern for every option. This is the fair headline for agents and cold starts.
cd /work/bench
until grep -q "CHAIN DONE quiet2" /work/chain_quiet2.log; do sleep 30; done
python deploy.py --which all > /work/deploy-same.log 2>&1
python run.py agent_e2e --backends ac-v1-s1,ac-v2-s1,lm-s1,eks-x86-gvisor,eks-g3-gvisor,eks-x86-kata --n 10 --round same1
python run.py cold_start --backends ac-v1-s1,ac-v2-s1,lm-s1,eks-x86-gvisor,eks-g3-gvisor,eks-x86-kata --n 30 --round same1
python run.py agent_e2e --backends ac-v1-s2,ac-v2-s2,lm-s2,eks-x86-gvisor,eks-g3-gvisor,eks-x86-kata --n 10 --round same2
echo "== CHAIN DONE same"
