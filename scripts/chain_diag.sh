#!/bin/sh
# Are slow starts on snapshot platforms errors? New runtimes, with the CLI debug log, faults and CPU part on every run.
cd /work/bench
# deploy.py rewrites deployment.json, so it waits for the other deployment to finish.
until grep -q "sbx-lm-warm" /work/deploy-pkg.log; do sleep 15; done
python - <<'PY'
# The runtime was created before the wait above was added: record it rather than create another.
import boto3, json, time
c = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
rid = next(r["agentRuntimeId"] for r in c.list_agent_runtimes(maxResults=100)["agentRuntimes"] if r["agentRuntimeName"] == "sbxac_v2_diag")
while c.get_agent_runtime(agentRuntimeId=rid)["status"] != "READY":
    time.sleep(5)
g = c.get_agent_runtime(agentRuntimeId=rid)
d = json.load(open("/work/deployment.json"))
d["backends"]["ac-v2-diag"] = {"kind": "agentcore", "arn": g["agentRuntimeArn"], "id": rid, "platform": "V2", "image": "diag-arm64"}
json.dump(d, open("/work/deployment.json", "w"), indent=1)
PY
python deploy.py --which all > /work/deploy-diag.log 2>&1
python run.py agent_spaced --backends ac-v2-diag --n 20 --gap 20 --round diag &
python run.py agent_spaced --backends lm-diag --n 20 --gap 20 --round diag &
wait
echo "== CHAIN DONE diag"
