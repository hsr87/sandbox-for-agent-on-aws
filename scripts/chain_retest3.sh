#!/bin/sh
# Same load for MicroVM (3 per second is under its default quota of 5). Then V2 after 15 idle minutes with no load:
# if the speed-up came from recent use, the first run should slow down again.
cd /work/bench
python run.py sustained --backends lm-probe --sizes 3 --seconds 540 --settle 5 --round traffic3 &
L=$!
sleep 60
python run.py agent_e2e --backends lm-probe --n 10 --round traffic3
python run.py first_touch --backends lm-probe --n 5 --round traffic3
wait
sleep 300
python run.py agent_e2e --backends ac-v2-probe --n 6 --round idleafter
echo "== CHAIN DONE retest3"
