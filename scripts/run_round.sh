#!/bin/sh
# Runs inside the driver pod. Usage: run_round.sh <round>. Output: /work/results/*.jsonl
R=$1; cd /work/bench
BASE=ac-v1,ac-v2,lm,eks-x86-runc,eks-x86-gvisor,eks-x86-kata,eks-x86-kata-go,eks-arm-runc,eks-arm-gvisor,eks-x86-runc-warm,eks-x86-gvisor-warm,eks-x86-kata-warm,eks-arm-gvisor-warm
python run.py cold_start --backends $BASE --n 30 --pool 3 --round $R
VAR=ac-v1-large,ac-v2-large,lm-large,eks-x86-gvisor-large,eks-x86-kata-large,ac-v1-heavy,ac-v2-heavy,lm-heavy,eks-x86-gvisor-heavy,eks-x86-kata-heavy
python run.py cold_start --backends $VAR --n 15 --round $R
python run.py warm_latency --backends ac-v1,ac-v2,lm,eks-x86-runc,eks-x86-gvisor,eks-x86-kata,eks-arm-runc,eks-arm-gvisor --n 200 --round $R
