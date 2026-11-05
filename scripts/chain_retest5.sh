#!/bin/sh
# Same load as the managed traffic runs: 3 new sandboxes per second while 10 agent tasks run. EKS has 4 prepared nodes per runtime.
cd /work/bench
for b in eks-x86-gvisor eks-x86-kata; do
  python run.py sustained --backends $b --sizes 3 --seconds 540 --settle 5 --round traffic4 &
  sleep 60
  python run.py agent_e2e --backends $b --n 10 --round traffic4
  wait
  sleep 30
done
echo "== CHAIN DONE retest5"
