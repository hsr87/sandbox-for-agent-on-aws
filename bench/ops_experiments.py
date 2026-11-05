"""Experiments on the EKS side that need node-level access, and the observability audit."""
import argparse, json, os, subprocess, time
import boto3
from kubernetes import client, config
from kubernetes.stream import stream
import backends as B
from common import emit

now = time.perf_counter
config.load_incluster_config()
core = client.CoreV1Api()
co = client.CustomObjectsApi()
eks = boto3.client("eks", region_name="us-east-1")
ec2 = boto3.client("ec2", region_name="us-east-1")
CLUSTER = "sbx-bench"


def hostops_on(node):
    for p in core.list_namespaced_pod("bench", label_selector="app=hostops").items:
        if p.spec.node_name == node:
            return p.metadata.name
    raise RuntimeError("no hostops on " + node)


def host(node, cmd):
    return stream(core.connect_get_namespaced_pod_exec, hostops_on(node), "bench", command=["nsenter", "-t", "1", "-m", "-u", "-n", "-i", "sh", "-c", cmd], stderr=True, stdin=False, stdout=True, tty=False, _request_timeout=300)


def nodes_of(group):
    return [n for n in core.list_node(label_selector=f"bench/group={group}").items]


def is_ready(n):
    return any(c.type == "Ready" and c.status == "True" for c in n.status.conditions)


def set_pool(pool, replicas):
    co.patch_namespaced_custom_object("extensions.agents.x-k8s.io", "v1beta1", "sandboxes", "sandboxwarmpools", pool, {"spec": {"replicas": replicas}})


# E1c: cold start when the node has never seen the image.
def uncached(a, dep):
    for name in a.backends.split(","):
        b = B.make(name, dep)
        node = nodes_of(b.group)[0].metadata.name
        for i in range(a.n):
            r = host(node, f"ctr -n k8s.io images ls -q | grep -F '{b.image.split(':')[-1]}' | xargs -r ctr -n k8s.io images rm >/dev/null 2>&1; ctr -n k8s.io content prune references >/dev/null 2>&1; ctr -n k8s.io images ls -q | grep -cF '{b.image.split(':')[-1]}'")
            h = b.create()
            rec = {"backend": name, "i": i, "images_left_before": r.strip()[-3:]}
            try:
                b.wait_usable(h)
                rec.update(ok=True, cold_s=h.marks["first_ok"], marks=h.marks)
            except Exception as e:
                rec.update(ok=False, error=str(e)[:300])
            b.destroy(h)
            b.wait_gone(h)
            emit("cold_uncached", rec, a.round)
            time.sleep(5)


# E5b: memory and CPU per idle sandbox, read from the host.
def density(a, dep):
    for name in a.backends.split(","):
        b = B.make(name, dep)
        node = nodes_of(b.group)[0].metadata.name
        def mem():
            o = host(node, "grep -E 'MemTotal|MemAvailable' /proc/meminfo; cat /proc/loadavg")
            d = {l.split(":")[0]: int(l.split()[1]) for l in o.splitlines() if ":" in l}
            return d
        time.sleep(a.settle)
        base = mem()
        hs = []
        emit("density", {"backend": name, "sandboxes": 0, "mem_avail_kb": base["MemAvailable"], "mem_total_kb": base["MemTotal"]}, a.round)
        try:
            for step in [int(x) for x in a.steps.split(",")]:
                while len(hs) < step:
                    batch = [b.create() for _ in range(min(5, step - len(hs)))]
                    hs += batch
                    for h in batch:
                        b.wait_usable(h, deadline=180)
                time.sleep(a.settle)
                m = mem()
                emit("density", {"backend": name, "sandboxes": step, "mem_avail_kb": m["MemAvailable"], "mem_total_kb": m["MemTotal"], "used_delta_mb_per_sandbox": (base["MemAvailable"] - m["MemAvailable"]) / 1024 / step}, a.round)
        except TimeoutError as e:
            emit("density", {"backend": name, "sandboxes": len(hs), "capacity_limit": True, "detail": str(e)[:200]}, a.round)
        finally:
            for h in hs:
                b.destroy(h)
            for h in hs:
                b.wait_gone(h)


# E6e: capacity changes. New node to first usable sandbox, then back down until the instance is gone.
def node_scale(a, dep):
    for name in a.backends.split(","):
        b = B.make(name, dep)
        g = b.group
        for i in range(a.n):
            before = {n.metadata.name for n in nodes_of(g)}
            d0 = len(before)
            t0 = now()
            eks.update_nodegroup_config(clusterName=CLUSTER, nodegroupName=g, scalingConfig={"desiredSize": d0 + 1, "minSize": 0, "maxSize": 6})
            new = None
            while new is None:
                for n in nodes_of(g):
                    if n.metadata.name not in before and is_ready(n):
                        new = n.metadata.name
                time.sleep(1)
            ready = now() - t0
            if "kata" in g:
                # In job mode kata-deploy only sees new nodes on helm upgrade; the time of that step is reported separately.
                pass
            # Cordon the old nodes so that the first sandbox must land on the new one.
            for o in before:
                core.patch_node(o, {"spec": {"unschedulable": True}})
            t = now()
            h = b.create()
            rec = {"backend": name, "i": i, "node_ready_s": ready}
            try:
                b.wait_usable(h, deadline=600)
                rec.update(ok=True, first_sandbox_on_new_node_s=now() - t, node_to_sandbox_total_s=now() - t0, node=core.read_namespaced_pod(h.n, "sandboxes").spec.node_name == new)
            except Exception as e:
                rec.update(ok=False, error=str(e)[:300])
            b.destroy(h)
            b.wait_gone(h)
            for o in before:
                core.patch_node(o, {"spec": {"unschedulable": False}})
            # Scale back down with an explicit instance. Managed node groups choose the victim, so wait until any instance is gone.
            t = now()
            eks.update_nodegroup_config(clusterName=CLUSTER, nodegroupName=g, scalingConfig={"desiredSize": d0, "minSize": 0, "maxSize": 6})
            while len(nodes_of(g)) > d0:
                time.sleep(2)
            rec["node_removed_s"] = now() - t
            emit("node_scale", rec, a.round)
            time.sleep(30)


# E17: first run on a node with an empty host page cache. Without this, EKS sandboxes can inherit pages left by earlier
# sandboxes on the node, which a restored managed session cannot.
def dropcache(a, dep):
    for name in a.backends.split(","):
        b = B.make(name, dep)
        # The scheduler picks the node, so every node in the group is emptied.
        group_nodes = [n.metadata.name for n in nodes_of(b.group)]

        def drop():
            for node in group_nodes:
                host(node, "sync; echo 3 > /proc/sys/vm/drop_caches")
            time.sleep(2)

        for i in range(a.n):
            drop()
            h = b.create()
            rec = {"backend": name, "i": i}
            try:
                b.wait_usable(h)
                rec["cold_s"] = h.marks["first_ok"]
                t = now()
                d = b.call(h, {"op": "agent", "model": "us.anthropic.claude-opus-5-5"})
                rec.update(ok="error" not in d, agent_wall_s=now() - t, result=d.get("result"), detail=d.get("error"))
            except Exception as e:
                rec.update(ok=False, error=str(e)[:300])
            b.destroy(h)
            b.wait_gone(h)
            emit("agent_dropcache", rec, a.round)
        p = B.make(name + "-probe", dep) if name + "-probe" in dep["backends"] else None
        if p:
            for i in range(5):
                drop()
                h = p.create()
                p.wait_usable(h)
                d = p.call(h, {"op": "first_touch"})
                emit("first_touch_dropcache", {"backend": name, "i": i, "result": d.get("result")}, a.round)
                p.destroy(h)
                p.wait_gone(h)


# E8: what exists after one invocation with zero extra configuration.
def observability(a, dep):
    logs = boto3.client("logs", region_name="us-east-1")
    cw = boto3.client("cloudwatch", region_name="us-east-1")
    xray = boto3.client("xray", region_name="us-east-1")
    ctl = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
    out = {}

    def groups(prefix):
        return [g["logGroupName"] for p in logs.get_paginator("describe_log_groups").paginate(logGroupNamePrefix=prefix) for g in p["logGroups"]]

    def stream_counts(g):
        try:
            s = logs.describe_log_streams(logGroupName=g, limit=5, orderBy="LastEventTime", descending=True)["logStreams"]
            ev = logs.get_log_events(logGroupName=g, logStreamName=s[0]["logStreamName"], limit=5)["events"] if s else []
            return {"streams_sampled": len(s), "sample_events": len(ev), "sample": [e["message"][:160] for e in ev[:2]]}
        except Exception as e:
            return {"error": str(e)[:200]}

    def metric_names(ns, dim=None):
        names = set()
        kw = {"Namespace": ns}
        for p in cw.get_paginator("list_metrics").paginate(**kw):
            for m in p["Metrics"]:
                names.add(m["MetricName"])
        return sorted(names)

    out["agentcore"] = {
        "log_groups": groups("/aws/bedrock-agentcore/runtimes/sbxac_v1-") + groups("/aws/bedrock-agentcore/runtimes/sbxac_v2-"),
        "metrics_bedrock_agentcore": metric_names("Bedrock-AgentCore"),
        "metrics_aws_bedrock_agentcore": metric_names("AWS/Bedrock-AgentCore"),
        "logs": {g: stream_counts(g) for g in groups("/aws/bedrock-agentcore/runtimes/sbxac_v2-")[:1]},
    }
    out["microvm"] = {
        "log_groups": groups("/aws/lambda-microvms/"),
        "logs": {g: stream_counts(g) for g in groups("/aws/lambda-microvms/")[:2]},
        "metrics_aws_lambda_microvm": [m for m in metric_names("AWS/Lambda") if "icro" in m.lower()],
        "metrics_aws_lambda_microvms_ns": metric_names("AWS/LambdaMicroVMs") + metric_names("AWS/Lambda/MicroVMs") + metric_names("AWS/Lambda-MicroVMs"),
    }
    d = eks.describe_cluster(name=CLUSTER)["cluster"]
    addons = eks.list_addons(clusterName=CLUSTER)["addons"]
    out["eks"] = {
        "control_plane_logging": d.get("logging"),
        "addons": addons,
        "log_groups": groups(f"/aws/eks/{CLUSTER}") + groups("/aws/containerinsights/" + CLUSTER),
        "container_insights_metrics": metric_names("ContainerInsights"),
        "metrics_server_installed": any(i.metadata.name == "metrics-server" for i in client.AppsV1Api().list_deployment_for_all_namespaces().items),
    }
    emit("observability", {"result": out}, a.round)
    print(json.dumps(out, indent=1, default=str)[:6000])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("exp")
    p.add_argument("--backends", default="")
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--round", default="r1")
    p.add_argument("--steps", default="5,10,20")
    p.add_argument("--settle", type=float, default=60)
    a = p.parse_args()
    dep = B.load_registry()
    globals()[a.exp](a, dep)
    print("DONE", a.exp, flush=True)
