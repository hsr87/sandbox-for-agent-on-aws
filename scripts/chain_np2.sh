#!/bin/sh
# V1 under the documented /ping behavior, for the numbers that go in the main tables.
cd /work/bench
python run.py cold_start --backends ac-v1,ac-v1-np --n 30 --round nplow &
python run.py sustained --backends ac-v1-np --sizes 1,5 --seconds 180 --settle 30 --round np2 &
python run.py usage_agent --backends ac-v1-np,ac-v2-np --n 5 --idle-s 300 --round usagenp &
python run.py agent_spaced --backends ac-v1-np --n 10 --gap 150 --round np2 &
wait
echo "== CHAIN DONE np2"
