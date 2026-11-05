#!/bin/zsh
# Operator side: after chain_same, V2 and MicroVM repeat the concurrent test from the same dedicated driver the others used.
set -u
cd "$(dirname "$0")/.."
K=(kubectl --context sbx-bench)
until $K -n bench exec driver -- grep -q "CHAIN DONE same" /work/chain_same.log 2>/dev/null; do sleep 60; done
$K -n bench exec driver2 -- sh -c 'cd /work/bench && python run.py agent_concurrent --backends ac-v2-np,lm --sizes 5,20 --n 2 --settle 30 --round conc4 > /work/conc5.log 2>&1'
: > /dev/null
for f in agent_concurrent agent_concurrent_node; do
  $K -n bench exec driver2 -- sh -c "grep -E '\"backend\": \"(ac-v2-np|lm)\"' /work/results/$f.jsonl" | $K -n bench exec -i driver -- sh -c "cat >> /work/results/$f.jsonl"
done
echo "== SAME DONE"
