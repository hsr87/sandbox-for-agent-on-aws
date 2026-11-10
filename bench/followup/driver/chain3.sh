#!/bin/sh
cd /work
export RESULTS=/work/x/results DEPLOYMENT=/work/x/deployment.json
python xrun.py deploy --spec xi_spec.json --par 13
python xrun.py cycle --backend xi-store --n 10 --pause 60 --gap 120 --key x1/claude-arm64-ok --round xj > /work/x/cycle.log 2>&1 &
python xrun.py iso --items xi_items.json --n 8 --gap 960 --lead 1200 --round xj
wait
echo CHAIN_DONE
