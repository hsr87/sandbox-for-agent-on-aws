#!/bin/sh
# The first traffic run put load only on V1, because sustained runs backends in sequence. This gives V2 the same load.
cd /work/bench
python run.py sustained --backends ac-v2-probe --sizes 3 --seconds 540 --settle 5 --round traffic2 &
L=$!
sleep 60
python run.py agent_e2e --backends ac-v2-probe --n 10 --round traffic2
python run.py first_touch --backends ac-v2-probe --n 5 --round traffic2
wait
echo "== CHAIN DONE retest2"
