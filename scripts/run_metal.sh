#!/bin/zsh
# Kata without nested virtualization, so its agent results are not only those of the slower path. Runs after run_final.sh.
set -u
cd "$(dirname "$0")/.."
K=(kubectl --context sbx-bench)
S=$1
until grep -q "FINAL DONE" "$S"; do sleep 30; done
aws eks update-nodegroup-config --cluster-name sbx-bench --nodegroup-name metal-kata --scaling-config desiredSize=1,minSize=0,maxSize=1 >/dev/null
until [ "$($K get nodes -l bench/group=metal-kata --no-headers 2>/dev/null | grep -c ' Ready ')" = 1 ]; do sleep 15; done
helm --kube-context sbx-bench upgrade kata-deploy oci://ghcr.io/kata-containers/kata-deploy-charts/kata-deploy --version 4.3.1 --namespace kube-system --reuse-values --wait --timeout 15m
$K -n bench exec driver -- sh -c 'cd /work/bench; python run.py cold_start --backends eks-metal-kata --n 1 --round metalwarmup; python run.py cold_start --backends eks-metal-kata --n 30 --round metal; python run.py agent_spaced --backends eks-metal-kata --n 10 --gap 10 --round metal; python run.py agent_spaced --backends eks-metal-kata --n 8 --gap 10 --task heavy --round heavy'
aws eks update-nodegroup-config --cluster-name sbx-bench --nodegroup-name metal-kata --scaling-config desiredSize=0,minSize=0,maxSize=1 >/dev/null
echo "== METAL DONE"
