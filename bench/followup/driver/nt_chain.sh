#!/bin/sh
# Nitro Sandboxes (EKS Auto Mode cluster, isolated-sandbox), run from the driver in that cluster.
# nt-c: 250m/512Mi requests, so a 1 vCPU VM, for echo start, bursts and arrivals.
# nt-b: 2 vCPU / 8 GB requests, the same size as the other sandboxes, for agent, build and workload runs.
# nt-w: claim from a 3-replica SandboxWarmPool.
set -e
cd /work
export RESULTS=/work/x/results DEPLOYMENT=/work/x/dep_nt.json
python - <<P
import json; p="/work/x/dep_nt.json"; d=json.load(open(p)); d["backends"]["nt-w"]={"kind":"eks_warm","pool":"wp-x86-nitro"}; json.dump(d,open(p,"w"))
P
cd /work/bench
python run.py cold_start --backends nt-c,nt-w --n 20 --round nt
cd /work
python xrun.py mix --items nt_items.json --n 12 --gap 30 --exp x_nt_agent --round nt
python xrun.py mix --items nt_items.json --n 12 --gap 0 --task heavy --exp x_nt_heavy --round nt
python nt_pause.py 5 nt
cd /work/bench
for r in 1 2 3; do python run.py burst --backends nt-c --sizes 10,50,100 --settle 90 --round nt-b$r; done
python run.py sustained --backends nt-c --sizes 1,5 --seconds 120 --settle 90 --round nt
python run.py bench_suite --backends nt-b --sandboxes 3 --round nt
python run.py first_touch --backends nt-b --n 5 --round nt
python run.py hw_census --backends nt-b --n 10 --round nt
python run.py security --backends nt-b --round nt
cd /work
python xrun.py conc --items nt_conc_items.json --n 4 --gap 30 --sizes 5,20 --exp x_nt_conc --round nt
echo NT_DONE
