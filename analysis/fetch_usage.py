#!/usr/bin/env python3
"""Downloads AgentCore USAGE_LOGS for the sessions in usage_sessions.jsonl. Run with AWS credentials."""
import json, time
from pathlib import Path
import boto3
ROOT = Path(__file__).resolve().parent.parent
logs = boto3.client("logs", region_name="us-east-1")
recs = [json.loads(l) for l in (ROOT / "results/raw/usage_sessions.jsonl").open()]
ts = min(r["ts"] for r in recs)
out = (ROOT / "results/raw/usage_logs.jsonl").open("w")
for r in recs:
    q = logs.start_query(logGroupName="/bench/agentcore-usage", startTime=int(ts - 900), endTime=int(max(x["ts"] for x in recs) + 900),
        queryString=f'fields @timestamp, `metrics.agent.runtime.memory.gb_hours.used` as mem, `metrics.agent.runtime.vcpu.hours.used` as cpu, attributes.time_elapsed_seconds as dt | filter attributes.session.id = "{r["session"]}" | sort @timestamp asc | limit 2000')["queryId"]
    while True:
        a = logs.get_query_results(queryId=q)
        if a["status"] in ("Complete", "Failed", "Cancelled"):
            break
        time.sleep(1)
    rows = [{f["field"]: f["value"] for f in row} for row in a["results"]]
    series = [{"t": x["@timestamp"], "gb": float(x["mem"]) * 3600 / float(x["dt"]), "vcpu": float(x["cpu"]) * 3600 / float(x["dt"]), "dt": float(x["dt"])} for x in rows]
    out.write(json.dumps({"backend": r["backend"], "i": r["i"], "alloc_mb": r["alloc_mb"], "cpu_s": r["cpu_s"], "idle_s": r["idle_s"], "seconds_logged": sum(s["dt"] for s in series), "gb_hours": sum(float(x["mem"]) for x in rows), "vcpu_hours": sum(float(x["cpu"]) for x in rows), "peak_gb": max((s["gb"] for s in series), default=None), "last60_gb": sum(s["gb"] for s in series[-60:]) / max(1, len(series[-60:])), "series_gb": [round(s["gb"], 3) for s in series]}) + "\n")
    out.flush()
