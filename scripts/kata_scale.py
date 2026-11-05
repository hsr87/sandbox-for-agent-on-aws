#!/usr/bin/env python3
"""New Kata node to first usable sandbox. kata-deploy in its default job mode only sees new nodes on helm upgrade,
so that step is part of the measured path and is reported separately. Run from an operator machine."""
import json, subprocess, sys, time

CTX = ["--context", "sbx-bench"]
OUT = "results/raw/kata_scale.jsonl"


def sh(*a, check=True):
    return subprocess.run(a, capture_output=True, text=True, check=check).stdout


def nodes():
    for attempt in range(30):
        try:
            return json.loads(sh("kubectl", *CTX, "get", "nodes", "-l", "bench/group=x86-kata", "-o", "json"))["items"]
        except subprocess.CalledProcessError:
            time.sleep(5)
    raise RuntimeError("kubectl unreachable")


def ready(n):
    return any(c["type"] == "Ready" and c["status"] == "True" for c in n["status"]["conditions"])


for rep in range(int(sys.argv[1])):
    before = {n["metadata"]["name"] for n in nodes()}
    d0 = len(before)
    t0 = time.time()
    sh("aws", "eks", "update-nodegroup-config", "--cluster-name", "sbx-bench", "--nodegroup-name", "x86-kata", "--scaling-config", f"desiredSize={d0 + 1},minSize=0,maxSize=6")
    new = None
    while not new:
        for n in nodes():
            if n["metadata"]["name"] not in before and ready(n):
                new = n["metadata"]["name"]
        time.sleep(2)
    t_ready = time.time() - t0
    t = time.time()
    sh("helm", "--kube-context", "sbx-bench", "upgrade", "kata-deploy", "oci://ghcr.io/kata-containers/kata-deploy-charts/kata-deploy", "--version", "4.3.1", "--namespace", "kube-system", "--reuse-values", "--wait=false")
    while True:
        lab = [n for n in nodes() if n["metadata"]["name"] == new][0]["metadata"].get("labels", {})
        if lab.get("katacontainers.io/kata-runtime") == "true":
            break
        time.sleep(2)
    t_kata = time.time() - t
    for o in before:
        sh("kubectl", *CTX, "cordon", o)
    code = ("import sys,json,time;sys.path.insert(0,'/work/bench');import backends as B;d=B.load_registry();b=B.make('eks-x86-kata',d);h=b.create();b.wait_usable(h,deadline=600);"
            "print(json.dumps({'first_ok':h.marks['first_ok'],'node':b.core.read_namespaced_pod(h.n,'sandboxes').spec.node_name}));b.destroy(h)")
    o = json.loads(sh("kubectl", *CTX, "-n", "bench", "exec", "driver", "--", "python", "-c", code).strip().splitlines()[-1])
    for x in before:
        sh("kubectl", *CTX, "uncordon", x)
    total = time.time() - t0
    t = time.time()
    sh("aws", "eks", "update-nodegroup-config", "--cluster-name", "sbx-bench", "--nodegroup-name", "x86-kata", "--scaling-config", f"desiredSize={d0},minSize=0,maxSize=6")
    while len(nodes()) > d0:
        time.sleep(5)
    rec = {"rep": rep, "node_ready_s": t_ready, "kata_install_s": t_kata, "first_sandbox_cold_s": o["first_ok"], "landed_on_new_node": o["node"] == new, "total_s": total, "node_removed_s": time.time() - t}
    open(OUT, "a").write(json.dumps(rec) + "\n")
    print(rec, flush=True)
    time.sleep(30)
