#!/bin/sh
cd /work
export RESULTS=/work/x/results
python kp.py scale --image ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sbx-bench/agent:x1c-amd64 --n 5 --sizes 1,20,50 --round kp
python kp.py trace --image ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sbx-bench/agent:x1c-amd64 --minutes 90 --round kpa
python kp.py trace --image ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sbx-bench/agent:x1c-amd64 --minutes 90 --keep --round kpb
echo KP_DONE
