#!/usr/bin/env python3
"""Summarizes the follow-up experiments in results/raw/followup/ into results/followup.json.
p50 with a bootstrap 95% interval, as in analyze.py. Failed runs are counted, never dropped silently."""
import collections
import json
import math
import random
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "results" / "raw" / "followup"


def L(name):
    p = D / f"{name}.jsonl"
    return [json.loads(x) for x in p.open()] if p.exists() else []


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


def ci(v):
    random.seed(1)
    b = sorted(st.median(random.choices(v, k=len(v))) for _ in range(2000))
    return [b[50], b[1949]]


def summ(v):
    return {"n": len(v), "p50": st.median(v), "p90": q(v, .9), "max": max(v), "ci": ci(v), "over20": sum(x > 20 for x in v)}


def whole(r):
    return r["cold_s"] + r["wall_s"]


def group(rows, key):
    g = collections.defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    return g


def agent_block(rows):
    ok = [r for r in rows if r.get("ok") and r["result"].get("first_message") is not None]
    out = {"runs": len(rows), "failed": len(rows) - len(ok), "pytest_failed": sum((r["result"].get("verify_pytest_rc") or 0) != 0 for r in ok)}
    if ok:
        out["first"] = summ([r["result"]["first_message"] for r in ok])
        out["whole"] = summ([whole(r) for r in ok])
        out["agent"] = st.median(r["result"]["agent_s"] for r in ok)
        out["model"] = st.median(r["result"]["duration_api_ms"] / 1000 for r in ok if r["result"].get("duration_api_ms"))
        out["after_first"] = summ([r["result"]["agent_s"] - r["result"]["first_message"] for r in ok])
        out["cold"] = summ([r["cold_s"] for r in ok])
    return out


def build():
    f = {}
    # Strands Agents and the Claude Agent SDK on every platform. Ready = SDK import + first model stream event.
    sdk = {}
    for (p, s), R in group([r for r in L("sdk_compare") if r.get("ok")], lambda r: (r["platform"], r["sdk"])).items():
        ready = [r["result"]["import_s"] + r["result"]["first_stream_event"] for r in R]
        sdk[f"{p}|{s}"] = {"ready": summ(ready), "whole": summ([whole(r) for r in R]), "pytest_failed": sum(r["result"].get("verify_pytest_rc") not in (0, None) for r in R)}
    f["sdk"] = sdk
    f["sdk_runs"] = len(L("sdk_compare"))
    f["sdk_failed"] = sum(not r.get("ok") for r in L("sdk_compare"))
    # First read of one file by size, Strands app, new session each time.
    size = {}
    for (p, mb), R in group([r for r in L("file_size") if r.get("ok")], lambda r: (r["platform"], r["mb"])).items():
        size[f"{p}|{mb}"] = summ([r["result"]["asset_first"]["s"] for r in R])
        size[f"{p}|{mb}"]["second_p50"] = st.median(r["result"]["asset_second"]["s"] for r in R)
    f["size"] = size
    # Session storage: CLI from the image, from S3 into /tmp, from S3 into session storage, then resume.
    store = {}
    for k, R in group([r for r in L("session_storage") if r.get("ok")], lambda r: f"{r['arm']}|{r.get('phase', 'run')}").items():
        b = agent_block(R)
        fe = [r["result"]["fetch_s"] for r in R if r["result"].get("fetch_s")]
        if fe:
            b["fetch"] = summ(fe)
        store[k] = b
    f["store"] = store
    cyc = [r for r in L("session_storage_cycle") if r.get("ok")]
    res = [r["result"] for r in cyc if r["phase"] == "resume"]
    f["store_cycle"] = {"cycles": len(res), "new_vm": sum(not x["marker_in_tmp"] for x in res), "file_kept": sum(x["exists"] for x in res),
                        "first_read": summ([x["first"]["s"] for x in res]), "after_drop": summ([x["after_drop"]["s"] for x in res]),
                        "fetch": summ([r["result"]["fetch_s"] for r in cyc if r["phase"] == "fetch"])}
    # Does warming carry across runtimes? Same 331 MB file in every arm, 8 probe slots 16 minutes apart.
    iso = {}
    for a, R in group([r for r in L("warming_isolation_probe") if r.get("ok")], lambda r: r["arm"]).items():
        iso[a] = summ([r["result"]["first"]["s"] for r in R])
    f["iso"] = iso
    # Mitigations, all arms in one period, 2 runtimes each, 8 probes 16 minutes apart.
    mit = {}
    for a, R in group(L("mitigation_probe"), lambda r: r["arm"]).items():
        mit[a] = agent_block(R)
    ticks = collections.defaultdict(list)
    for r in L("mitigation_tick"):
        ticks[r["arm"]].append(r)
    span_h = (max(r["ts"] for r in L("mitigation_probe")) - min(r["ts"] for r in L("mitigation_tick"))) / 3600
    usage = {r["runtime"]: r for r in L("usage_by_runtime")}
    for a in mit:
        u = [v for k, v in usage.items() if k.startswith(f"xm_{a}_")]
        if u:
            mit[a]["usage"] = {"gb_hours": sum(x["gb_hours"] for x in u) / len(u), "vcpu_hours": sum(x["vcpu_hours"] for x in u) / len(u), "runtimes": len(u)}
        if a in ticks:
            mit[a]["ticks_per_runtime"] = len(ticks[a]) / 2
            mit[a]["tick_s_per_runtime"] = sum(r["wall_s"] for r in ticks[a]) / 2
    # Extra billed usage of a warmed runtime over a runtime with no mitigation, per hour, at the V2 price.
    pr = json.loads((ROOT / "results" / "cost_model.json").read_text())["prices"]["agentcore_v2"]
    base = mit["v2_none"]["usage"]
    for a in ("v2_w5k1", "v2_w10k4", "v2_map", "v2_s3", "v2_pre"):
        u = mit[a]["usage"]
        gb, cpu = (u["gb_hours"] - base["gb_hours"]) / span_h, (u["vcpu_hours"] - base["vcpu_hours"]) / span_h
        u["extra_gb_per_h"], u["extra_vcpu_per_h"], u["extra_usd_per_h"] = gb, cpu, gb * pr["gb_h"] + cpu * pr["vcpu_h"]
        u["gb_hours_per_probe_session"] = u["gb_hours"] / 8
    base["gb_hours_per_probe_session"] = base["gb_hours"] / 8
    f["mitigation"] = mit
    f["mitigation_span_h"] = span_h
    # Older warming round, kept for the warm-up interval comparison (5 min, 4 at once).
    f["warming_1"] = {a: agent_block(R) for a, R in group(L("warming_probe_1"), lambda r: r["arm"]).items()}
    # Network mode, build task and concurrency, shuffled in one period.
    f["network"] = {a: agent_block(R) for a, R in group(L("network_mode_agent"), lambda r: r["arm"]).items()}
    f["network_usage"] = {k: usage[k] for k in ("xm_v_v1", "xm_v_v2", "xm_p_v1", "xm_p_v2") if k in usage}
    f["build"] = {a: agent_block(R) for a, R in group(L("build_task"), lambda r: r["arm"]).items()}
    f["build_cpu"] = {a: sorted({c for r in R for c in r["result"].get("cpu", [])}) for a, R in group(L("build_task"), lambda r: r["arm"]).items()}
    f["conc"] = {f"{a}|{n}": agent_block(R) for (a, n), R in group(L("concurrent_agents"), lambda r: (r["arm"], r["size"])).items()}
    # Karpenter: scale from zero, then a 100 minute trace with and without do-not-disrupt.
    kp = {}
    for n, R in group(L("karpenter_scale"), lambda r: r["size"]).items():
        kp[str(n)] = {"reps": len(R), "p50": st.median(r["p50"] for r in R), "all_ready": st.median(r["max"] for r in R), "node_ready": st.median(r["node_ready_s"][0] for r in R), "ok": all(r["ok"] == n for r in R)}
    f["kp_scale"] = kp
    tr = {}
    for rnd, keep in (("kpa", False), ("kpb", True)):
        S = [x for x in L("karpenter_trace_sessions") if x["round"] == rnd]
        N = [x for x in L("karpenter_trace_nodes") if x["round"] == rnd]
        s_ = [x["start_s"] for x in S if "start_s" in x]
        dt = 10
        node_h = sum(x["nodes"] for x in N) * dt / 3600
        pod_h = sum(x["pods"] for x in N) * dt / 3600
        tr["keep" if keep else "default"] = {"sessions": len(S), "lost": sum(x.get("survived") is False for x in S), "errors": sum("error" in x for x in S),
                                             "start": summ(s_), "node_h": node_h, "pod_h": pod_h, "node_h_per_pod_h": node_h / pod_h, "hours": len(N) * dt / 3600}
    f["kp_trace"] = tr
    kk = L("karpenter_kata")
    f["kp_kata"] = {"usable": [r["usable_s"] for r in kk], "helm": [r["helm_s"] for r in kk], "node_ready": [r["node_ready_s"] for r in kk]}
    # Tokyo.
    tk = {"cold": {}, "sus5": {}, "burst": {}, "agent": {}, "first_read": {}}
    for b, R in group([r for r in L("tokyo/cold_start") if r.get("ok")], lambda r: r["backend"].replace("tk-", "")).items():
        tk["cold"][b] = summ([r["cold_s"] for r in R])
    for b, R in group(L("tokyo/sustained"), lambda r: r["backend"].replace("tk-", "")).items():
        tk["sus5"][b] = summ([r["cold_s"] for r in R if r.get("ok")])
        tk["sus5"][b]["failed"] = sum(not r.get("ok") for r in R)
    for (b, n), R in group(L("tokyo/burst"), lambda r: (r["backend"].replace("tk-", ""), r["size"])).items():
        p = [st.median([x["s"] for x in r["results"] if x.get("ok")]) for r in R]
        tk["burst"][f"{b}|{n}"] = {"rounds": len(R), "min": min(p), "max": max(p), "failed": sum(not x.get("ok") for r in R for x in r["results"])}
    for a, R in group(L("tokyo/agent"), lambda r: r["arm"]).items():
        tk["agent"][a] = agent_block(R)
    for a, R in group([r for r in L("tokyo/first_read") if r.get("ok")], lambda r: r["arm"]).items():
        tk["first_read"][a] = [r["result"]["read"]["s"] for r in R]
    f["tokyo"] = tk
    f["new"] = new_options()
    return f


def new_options():
    """EKS Fargate (fg), Nitro Sandboxes (nt) and their same-period anchors (na: gVisor and Kata in the main cluster).
    Reuses the main analysis functions on each folder so that the numbers are computed the same way."""
    import analyze as A
    out = {}
    for sub in ("fg", "nt", "na"):
        d = D / sub
        if not d.exists():
            continue
        A.RAW = d
        o = {"cold": A.cold(), "suite": A.suite(), "census": A.census(), "first_touch": A.first_touch(), "burst": A.burst(), "sustained": A.sustained(),
             "security": {r["backend"]: r["result"] for r in A.load("security") if r.get("result")}}
        for name in ("agent", "heavy", "conc"):
            rows = A.load(f"x_{sub}_{name}")
            if rows:
                key = (lambda r: f"{r['arm']}|{r['size']}") if name == "conc" else (lambda r: r["arm"])
                o[name] = {a: agent_block(R) for a, R in group(rows, key).items()}
        o["cpu_models"] = {b: sorted({r["cpu"][1] for r in R if r.get("cpu")}) for b, R in group(A.load("hw_census"), lambda r: r["backend"]).items()}
        ni = A.load("nodeinfo")
        if ni:
            o["nodeinfo"] = ni[-1]
        pr = A.load("nitro_pause_resume")
        if pr:
            ok = [r for r in pr if r.get("ok")]
            o["pause_resume"] = {"cycles": len(pr), "failed": len(pr) - len(ok), "create": summ([r["create_s"] for r in ok]), "suspend": summ([r["suspend_s"] for r in ok]), "resume": summ([r["resume_s"] for r in ok]),
                                 "disk_kept": sum(r["after"]["disk_ok"] for r in ok), "memory_kept": sum(r["after"]["memory_ok"] for r in ok), "new_instance": sum(r["after"]["new_instance"] for r in ok), "same_node": sum(r["before"]["node"] == r["after"]["node"] for r in ok)}
        out[sub] = o
    A.RAW = ROOT / "results" / "raw"
    return out


if __name__ == "__main__":
    f = build()
    (ROOT / "results" / "followup.json").write_text(json.dumps(f, indent=1))
    print(json.dumps({k: (v if not isinstance(v, dict) else list(v)[:12]) for k, v in f.items()}, indent=0)[:3000])
