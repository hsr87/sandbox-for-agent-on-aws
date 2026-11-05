#!/bin/sh
# New runtimes after an hour with no agent run anywhere in the account: is a first read fast because other sandboxes just read the same file?
cd /work/bench
until grep -q "CHAIN DONE fair3" /work/chain_fair3.log; do sleep 30; done
sleep 3600
python deploy.py --which all > /work/deploy-quiet.log 2>&1
for b in ac-v2-q lm-q ac-v2-pinq lm-pinq; do python run.py agent_spaced --backends $b --n 8 --gap 150 --round quiet & done
wait
echo "== CHAIN DONE quiet"
