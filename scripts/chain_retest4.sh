#!/bin/sh
# Controls for the speed-up seen under traffic. ac-v2 has had no heavy traffic: is it still slow, or did something else change?
# ac-v2-probe had heavy traffic: is it still fast after 45 idle minutes?
cd /work/bench
python run.py agent_e2e --backends ac-v2 --n 6 --round control
sleep 2700
python run.py agent_e2e --backends ac-v2-probe --n 6 --round idle45
echo "== CHAIN DONE retest4"
