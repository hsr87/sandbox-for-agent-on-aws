#!/bin/sh
# Second fairness round, after the audit.
# 1. /ping as the AgentCore contract asks: does idle reclaim, or anything else, change?
# 2. Four new runtimes per platform, crossing echo load with the gap between agent runs:
#    fa no load, long gap; fb no load, short gap; fc load, long gap; fd load, short gap.
# 3. Graviton3 gVisor at the same load as the x86 traffic run.
# 4. Agents running at the same moment: cold and warm pods on one node, and managed fleets.
cd /work/bench
until grep -q "CHAIN DONE fair" /work/chain_fair.log; do sleep 20; done
python deploy.py --which all > /work/deploy-fair2.log 2>&1

python run.py idle_reclaim --backends ac-v1-np-idle60,ac-v2-np-idle60 --n 3 --waits 30,60,70,90,120,180,300,600,900 --round np &
python run.py cold_start --backends ac-v1-np,ac-v2-np --n 30 --round np &
python run.py agent_e2e --backends ac-v1-np,ac-v2-np --n 6 --round np &

cell() { # backend round gap load_seconds
  if [ "$4" != 0 ]; then python run.py sustained --backends $1 --sizes 3 --seconds $4 --settle 5 --round $2 & sleep 300; fi
  python run.py agent_spaced --backends $1 --n 12 --gap $3 --round $2
  wait
}
(cell ac-v2-fa fa 150 0) &
(cell ac-v2-fb fb 5 0) &
(cell ac-v2-fc fc 150 2700) &
(cell ac-v2-fd fd 5 1000) &
(cell lm-fa fa 150 0) &
(cell lm-fb fb 5 0) &
(cell lm-fd fd 5 1000; cell lm-fc fc 150 2700) &

(python run.py sustained --backends eks-g3-gvisor --sizes 3 --seconds 540 --settle 5 --round traffic4 & sleep 60; python run.py agent_e2e --backends eks-g3-gvisor --n 10 --round traffic4; wait) &
wait

# Warm pods are scaled up only for their own batch: idle ones would take the capacity of the cold batch.
pool() { python -c "
from kubernetes import client, config
config.load_incluster_config()
client.CustomObjectsApi().patch_namespaced_custom_object('extensions.agents.x-k8s.io', 'v1beta1', 'sandboxes', 'sandboxwarmpools', '$1', {'spec': {'replicas': $2}})"; }
python run.py agent_concurrent --backends eks-x86-gvisor --sizes 5,20 --n 2 --settle 30 --round conc
pool wpa-x86-gvisor 20
python run.py agent_concurrent --backends eks-x86-gvisor-warm-agent --sizes 5,20 --n 2 --settle 30 --round conc
pool wpa-x86-gvisor 0
sleep 60
python run.py agent_concurrent --backends eks-x86-kata --sizes 5,10 --n 2 --settle 30 --round conc
pool wpa-x86-kata 10
python run.py agent_concurrent --backends eks-x86-kata-warm-agent --sizes 5,10 --n 2 --settle 30 --round conc
pool wpa-x86-kata 0
sleep 60
python run.py agent_concurrent --backends ac-v1,ac-v2,lm --sizes 5,20 --n 2 --settle 30 --round conc
echo "== CHAIN DONE fair2"
