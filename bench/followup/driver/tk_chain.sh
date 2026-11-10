#!/bin/sh
# Tokyo: the core tables. Runs on driver2, the dedicated 8 vCPU node.
cd /work/bench
export RESULTS=/work/x/results DEPLOYMENT=/work/x/deployment.json TF_OUTPUT=/work/tf.json
cd /work && python xrun.py deploy --spec tk_spec.json --par 6
cd /work/bench
# Warm the two echo runtimes the same way as the main table: 10 agent runs first.
python run.py agent_spaced --backends tk-v1,tk-v2 --n 10 --gap 30 --round tk0 --model jp.anthropic.claude-opus-5-5
python run.py cold_start --backends tk-gv,tk-kt,tk-v1,tk-v2 --n 30 --round tk
python run.py sustained --backends tk-v1,tk-v2,tk-gv,tk-kt --sizes 5 --seconds 120 --settle 60 --round tk
for r in 1 2 3; do python run.py burst --backends tk-gv,tk-kt,tk-v1-b,tk-v2-b --sizes 10,50,100 --settle 60 --round tkb$r; done
cd /work && python xrun.py agent --items tk_items.json --n 10 --gap 150 --round tk --exp x_agent
python xrun.py agent --items tk_touch.json --n 10 --gap 150 --round tk --exp x_touch
echo TK_DONE
