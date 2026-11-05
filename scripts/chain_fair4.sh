#!/bin/sh
# Final comparison runs, from a dedicated 8 vCPU driver with nothing else running on it.
# Bursts repeat 3 times with enough prepared nodes per runtime: gVisor 4, Kata 8. MicroVM stays within its default RunMicrovm quota.
cd /work/bench
pool() { python -c "
from kubernetes import client, config
config.load_incluster_config()
client.CustomObjectsApi().patch_namespaced_custom_object('extensions.agents.x-k8s.io', 'v1beta1', 'sandboxes', 'sandboxwarmpools', '$1', {'spec': {'replicas': $2}})"; }
for r in 1 2 3; do
  python run.py burst --backends ac-v1,ac-v2,ac-v1-np,ac-v2-np,ac-v1-zip,ac-v2-zip --sizes 10,50,100 --settle 60 --round final$r
  python run.py burst --backends eks-x86-gvisor,eks-x86-kata --sizes 10,50,100 --settle 30 --round final$r
  python run.py burst --backends lm --sizes 10 --settle 30 --round final$r
done
python run.py agent_concurrent --backends eks-x86-gvisor,eks-x86-kata --sizes 5,20 --n 2 --settle 30 --round conc4
pool wpa-x86-gvisor 20; pool wpa-x86-kata 20; sleep 90
python run.py agent_concurrent --backends eks-x86-gvisor-warm-agent,eks-x86-kata-warm-agent --sizes 5,20 --n 2 --settle 30 --round conc4
pool wpa-x86-gvisor 0; pool wpa-x86-kata 0
python run.py agent_concurrent --backends ac-v1-np --sizes 5,20 --n 2 --settle 30 --round conc4
echo "== CHAIN DONE fair4"
