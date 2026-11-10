#!/bin/sh
# EKS Fargate as a sixth option, with gVisor and a new V1 runtime in the same period as anchors.
# fg-fs: 0.25 vCPU pod, the same requests as the EC2 sandbox pods, for echo start, bursts and arrivals.
# fg-fb: 2 vCPU, 8 GB Fargate size, the same limit as the other sandboxes, for agent, build and workload runs.
set -e
cd /work
export RESULTS=/work/x/results DEPLOYMENT=/work/x/dep_fg.json
python xrun.py deploy --spec fg_spec.json --par 4
cd /work/bench
python run.py cold_start --backends fg-fs,fg-fb --n 2 --round fg-smoke
python run.py agent_e2e --backends fg-fb --n 1 --round fg-smoke
echo SMOKE_OK
python run.py cold_start --backends fg-gv,fg-v1,fg-fs,fg-fb --n 20 --round fg
cd /work
python xrun.py mix --items fg_items.json --n 12 --gap 30 --exp x_fg_agent --round fg
python xrun.py mix --items fg_items.json --n 12 --gap 0 --task heavy --exp x_fg_heavy --round fg
cd /work/bench
for r in 1 2 3; do python run.py burst --backends fg-fs --sizes 10,50,100 --settle 90 --round fg-b$r; done
python run.py sustained --backends fg-fs --sizes 1,5 --seconds 120 --settle 90 --round fg
python run.py bench_suite --backends fg-fb --sandboxes 3 --round fg
python run.py first_touch --backends fg-fb --n 5 --round fg
python run.py hw_census --backends fg-fb --n 10 --round fg
python run.py security --backends fg-fb --round fg
cd /work
python xrun.py conc --items fg_conc_items.json --n 4 --gap 30 --sizes 5,20 --exp x_fg_conc --round fg
echo FG_DONE
