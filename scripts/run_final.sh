#!/bin/zsh
# Operator side of chain_fair4: adds nodes, starts a dedicated driver, merges its results, then returns the nodes.
set -u
cd "$(dirname "$0")/.."
K=(kubectl --context sbx-bench)
ACC=$(aws sts get-caller-identity --query Account --output text)
until $K -n bench exec driver -- grep -q "CHAIN DONE fair3" /work/chain_fair3.log 2>/dev/null; do sleep 30; done
aws eks update-nodegroup-config --cluster-name sbx-bench --nodegroup-name x86-gvisor --scaling-config desiredSize=4,minSize=0,maxSize=8 >/dev/null
aws eks update-nodegroup-config --cluster-name sbx-bench --nodegroup-name x86-kata --scaling-config desiredSize=8,minSize=0,maxSize=8 >/dev/null
until [ "$($K get nodes -l bench/group=x86-gvisor --no-headers 2>/dev/null | grep -c ' Ready ')" = 4 ] && [ "$($K get nodes -l bench/group=x86-kata --no-headers 2>/dev/null | grep -c ' Ready ')" = 8 ]; do sleep 15; done
helm --kube-context sbx-bench upgrade kata-deploy oci://ghcr.io/kata-containers/kata-deploy-charts/kata-deploy --version 4.3.1 --namespace kube-system --reuse-values --wait --timeout 15m
sed "s/ACCOUNT_ID/$ACC/g" infra/k8s/prepull.yaml | $K apply -f -
$K -n bench rollout status ds/prepull --timeout=900s
cat <<Y | $K apply -f -
apiVersion: v1
kind: Pod
metadata: { name: driver2, namespace: bench }
spec:
  serviceAccountName: driver
  nodeSelector: { bench/group: x86-runc }
  containers:
  - name: driver
    image: $ACC.dkr.ecr.us-east-1.amazonaws.com/sbx-bench/agent:driver
    command: ["sleep", "infinity"]  # no result sync here: it would overwrite the main driver's files in S3
    resources: { requests: { cpu: "4", memory: 8Gi } }
Y
$K -n bench wait --for=condition=Ready pod/driver2 --timeout=300s
$K -n bench exec driver -- tar cf - -C /work bench scripts tf.json deployment.json | $K -n bench exec -i driver2 -- sh -c 'mkdir -p /work && tar xf - -C /work'
$K cp scripts/chain_fair4.sh bench/driver2:/work/scripts/chain_fair4.sh
$K -n bench exec driver2 -- sh -c 'nohup sh /work/scripts/chain_fair4.sh > /work/chain_fair4.log 2>&1 < /dev/null &'
until $K -n bench exec driver2 -- grep -q "CHAIN DONE fair4" /work/chain_fair4.log 2>/dev/null; do sleep 30; done
for f in burst agent_concurrent agent_concurrent_node; do
  $K -n bench exec driver2 -- cat /work/results/$f.jsonl | $K -n bench exec -i driver -- sh -c "cat >> /work/results/$f.jsonl"
done
$K -n bench delete ds prepull
aws eks update-nodegroup-config --cluster-name sbx-bench --nodegroup-name x86-gvisor --scaling-config desiredSize=1,minSize=0,maxSize=8 >/dev/null
aws eks update-nodegroup-config --cluster-name sbx-bench --nodegroup-name x86-kata --scaling-config desiredSize=1,minSize=0,maxSize=8 >/dev/null
echo "== FINAL DONE"
