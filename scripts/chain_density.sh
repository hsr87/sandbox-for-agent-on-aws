#!/bin/sh
cd /work/bench
step(){ echo "== $(date -u +%H:%M:%S) $*"; "$@" || echo "!! FAILED: $*"; }
step python ops_experiments.py density --backends eks-x86-runc --steps 5,10,20,30 --round r1
step python ops_experiments.py density --backends eks-x86-gvisor --steps 5,10,20,30 --round r1
step python ops_experiments.py density --backends eks-x86-kata --steps 5,10,15 --round r1
step python ops_experiments.py uncached --backends eks-x86-runc,eks-x86-gvisor,eks-x86-kata --n 5 --round r1
step python ops_experiments.py uncached --backends eks-x86-gvisor-large,eks-x86-kata-large --n 3 --round r1
step python ops_experiments.py observability --round r1
echo "== CHAIN DONE density"
