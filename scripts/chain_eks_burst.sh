#!/bin/sh
# EKS capacity is provisioned before this runs: 4 nodes per runtime, see README. The first measurement of each size is kept.
cd /work/bench
step(){ echo "== $(date -u +%H:%M:%S) $*"; "$@" || echo "!! FAILED: $*"; }
step python run.py burst --backends eks-x86-runc,eks-x86-gvisor --sizes 10,50,100 --settle 30 --round r1
step python run.py burst --backends eks-x86-kata --sizes 10,50 --settle 30 --round r1
step python run.py sustained --backends eks-x86-gvisor,eks-x86-kata --sizes 1,5 --seconds 120 --settle 30 --round r1
echo "== CHAIN DONE eks burst"
