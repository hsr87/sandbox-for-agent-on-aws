#!/bin/sh
# Clean repeat of chain_quiet: nothing else runs in the account during either wait, and base and pinned images never overlap.
cd /work/bench
sleep 3600
python deploy.py --which all > /work/deploy-quiet2.log 2>&1
for b in ac-v2-q2 lm-q2; do python run.py agent_spaced --backends $b --n 8 --gap 150 --round quiet2 & done
wait
echo "== BASE DONE"
sleep 3600
for b in ac-v2-pinq2 lm-pinq2; do python run.py agent_spaced --backends $b --n 8 --gap 150 --round quiet2 & done
wait
echo "== CHAIN DONE quiet2"
