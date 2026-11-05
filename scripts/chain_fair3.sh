#!/bin/sh
# Balance after the audit, which had tuned the managed options more than EKS.
# 1. An agent task with real build work, where isolation cost and CPU generation can show.
# 2. EKS warm pods that ran one agent task before they became ready, the counterpart of warming before a snapshot.
# 3. AgentCore in VPC mode, the setup many customers need, next to EKS in private subnets.
cd /work/bench
until grep -q "CHAIN DONE pkg" /work/chain_pkg.log && grep -q "CHAIN DONE np2" /work/chain_np2.log; do sleep 20; done
python deploy.py --which balance > /work/deploy-balance.log 2>&1

pool() { python -c "
from kubernetes import client, config
config.load_incluster_config()
client.CustomObjectsApi().patch_namespaced_custom_object('extensions.agents.x-k8s.io', 'v1beta1', 'sandboxes', 'sandboxwarmpools', '$1', {'spec': {'replicas': $2}})"; }

eks_group() { # cold backend, warm pool, warm backend
  python run.py agent_spaced --backends $1 --n 8 --gap 10 --task heavy --round heavy
  pool $2 3; sleep 120
  python run.py agent_spaced --backends $3 --n 10 --gap 30 --round init
  pool $2 0
}
(eks_group eks-x86-gvisor wpi-x86-gvisor eks-x86-gvisor-warm-init) &
(eks_group eks-x86-kata wpi-x86-kata eks-x86-kata-warm-init) &
for b in eks-g3-gvisor ac-v1-np ac-v2-fa lm-fa; do python run.py agent_spaced --backends $b --n 8 --gap 10 --task heavy --round heavy & done

python run.py cold_start --backends ac-v1-vpc,ac-v2-vpc --n 30 --round vpc &
python run.py sustained --backends ac-v1-vpc,ac-v2-vpc --sizes 1,5 --seconds 180 --settle 30 --round vpc &
python run.py burst --backends ac-v1-vpc,ac-v2-vpc --sizes 10,100 --settle 60 --round vpc &
python run.py agent_spaced --backends ac-v1-vpc --n 8 --gap 60 --round vpc &
python run.py agent_spaced --backends ac-v2-vpc --n 8 --gap 60 --round vpc &
wait
echo "== CHAIN DONE fair3"
