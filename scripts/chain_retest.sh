#!/bin/sh
# Added after review. Keepalive runs separate a NAT idle timeout from a service limit. The traffic runs measure
# SDK readiness while V1's reused environments are exhausted, which the low-rate agent runs did not cover.
cd /work/bench
export RESULTS=/work/results
for s in 360 600 840 960 1200; do TCP_KEEPALIVE=1 python run.py long_request --backends ac-v1,ac-v2 --seconds $s --round ka & done
python run.py sustained --backends ac-v1-probe,ac-v2-probe --sizes 3 --seconds 600 --settle 5 --round traffic &
L=$!
sleep 60
python run.py agent_e2e --backends ac-v1-probe,ac-v2-probe --n 10 --round traffic
python run.py first_touch --backends ac-v1-probe,ac-v2-probe --n 5 --round traffic
kill $L 2>/dev/null
wait
echo "== CHAIN DONE retest"
