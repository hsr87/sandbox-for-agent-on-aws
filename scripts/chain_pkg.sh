#!/bin/sh
# Deployment mode. The AWS docs give different session rates for zip and container, and our V1 numbers are from a container.
# Also the V2 startup advice taken as far as it goes: one full agent task before the snapshot.
cd /work/bench
python deploy.py --which pkg > /work/deploy-pkg.log 2>&1
python run.py cold_start --backends ac-v1-zip,ac-v2-zip,ac-v1-tiny --n 30 --round pkg
python run.py sustained --backends ac-v1-zip,ac-v2-zip,ac-v1-tiny --sizes 1,5 --seconds 180 --settle 30 --round pkg
python run.py burst --backends ac-v1-zip,ac-v2-zip,ac-v1-tiny --sizes 10,50,100 --settle 60 --round pkg
for b in ac-v1-zip ac-v2-zip ac-v2-warm lm-warm; do python run.py agent_spaced --backends $b --n 10 --gap 150 --round pkg & done
wait
echo "== CHAIN DONE pkg"
