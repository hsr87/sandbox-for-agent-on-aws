#!/usr/bin/env python3
"""Turns results/summary.json into a flat dict of named facts.

README.md and README.ko.md read these names, so a number can only come from the data.
verify_claims.py checks every comparative claim in the docs against the same facts.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAT = {
    "gv": "eks-x86-gvisor", "kt": "eks-x86-kata", "v1": "ac-v1", "v2": "ac-v2", "lm": "lm",
    "rc": "eks-x86-runc", "ktgo": "eks-x86-kata-go", "ktm": "eks-metal-kata", "g3rc": "eks-g3-runc", "g3gv": "eks-g3-gvisor",
    "gvw": "eks-x86-gvisor-warm", "ktw": "eks-x86-kata-warm", "rcw": "eks-x86-runc-warm",
}


def load():
    return json.loads((ROOT / "results" / "summary.json").read_text()), json.loads((ROOT / "results" / "cost_model.json").read_text())


# RunMicrovm is limited to 5 per second by default. Above that the numbers show the quota and the driver's retries, not the platform.
QUOTA_LIMITED_BURST = {"lm": ("50", "100"), "lmlarge": ("50", "100")}
QUOTA_LIMITED_RATE = {"lm": ("10",), "lmlarge": ("10",)}


def build():
    s, c = load()
    f = {}
    cs = s["cold_start"]
    for k, b in PLAT.items():
        d = cs.get(b)
        if d and d.get("n"):
            f[f"cold.{k}.p50"], f[f"cold.{k}.p90"], f[f"cold.{k}.n"], f[f"cold.{k}.fail"] = d["p50"], d["p90"], d["n"], d["failed"]
            f[f"cold.{k}.max"] = d["max"]
            f[f"cold.{k}.warmshare"] = d["preexisting_process_share"]
            f[f"cold.{k}.rounds"] = {r: v["p50"] for r, v in d["by_round"].items()}
            if d.get("pod_gone_p50"):
                f[f"gone.{k}.p50"] = d["pod_gone_p50"]
    for v, suf in (("large", "large"), ("heavy", "heavy")):
        for k, b in (("v1", f"ac-v1-{suf}"), ("v2", f"ac-v2-{suf}"), ("lm", f"lm-{suf}"), ("gv", f"eks-x86-gvisor-{suf}"), ("kt", f"eks-x86-kata-{suf}")):
            d = cs.get(b)
            if d and d.get("n"):
                f[f"cold.{k}.{v}.p50"], f[f"cold.{k}.{v}.p90"], f[f"cold.{k}.{v}.n"], f[f"cold.{k}.{v}.max"] = d["p50"], d["p90"], d["n"], d["max"]
    fr = s["fresh_runtime"]
    for p in ("V1", "V2"):
        for img in ("base", "large"):
            f[f"fresh.{p}.{img}.first"] = fr[f"{p}/{img}-arm64/call0"]["p50"]
            f[f"fresh.{p}.{img}.third"] = fr[f"{p}/{img}-arm64/call2"]["p50"]
    for b, k in (("ac-v1", "v1"), ("ac-v2", "v2"), ("lm", "lm"), ("eks-x86-gvisor", "gv"), ("eks-x86-kata", "kt"), ("ac-v1-large", "v1large"), ("ac-v2-large", "v2large"), ("lm-large", "lmlarge"), ("eks-x86-gvisor-warm", "gvw"), ("eks-x86-kata-warm", "ktw"), ("eks-x86-runc", "rc")):
        for size, runs in s["burst"].get(b, {}).items():
            # The final rounds ran one at a time from a larger driver, with enough EKS nodes for the size. Earlier runs had neither.
            final = [x for x in runs if str(x.get("round", "")).startswith("final")]
            runs = final or runs
            if k in QUOTA_LIMITED_BURST and size in QUOTA_LIMITED_BURST[k]:
                continue
            ordered = sorted(runs, key=lambda x: x["p50"])
            r = ordered[len(ordered) // 2]
            f[f"burst.{k}.{size}.p50"], f[f"burst.{k}.{size}.p95"], f[f"burst.{k}.{size}.ok"], f[f"burst.{k}.{size}.fail"], f[f"burst.{k}.{size}.thr"] = r["p50"], r["p95"], r["ok"], r["failed"], r.get("throttles", 0)
            f[f"burst.{k}.{size}.wall"] = r["wall_s"]
            f[f"burst.{k}.{size}.runs"] = len(runs)
            if len(runs) > 1:
                f[f"burst.{k}.{size}.p50_all"] = [x["p50"] for x in runs]
        for rate, v in s["sustained"].get(b, {}).items():
            rk = str(int(float(rate)))
            if k in QUOTA_LIMITED_RATE and rk in QUOTA_LIMITED_RATE[k]:
                continue
            f[f"sus.{k}.{rk}.p50"], f[f"sus.{k}.{rk}.p95"], f[f"sus.{k}.{rk}.warm"], f[f"sus.{k}.{rk}.fail"], f[f"sus.{k}.{rk}.n"], f[f"sus.{k}.{rk}.thr"] = v["p50"], v["p95"], v["preexisting_share"], v["failed"], v["n"], v["throttles"]
    wl = s["warm_latency"]
    for k, b in PLAT.items():
        if b in wl and wl[b]["n"]:
            f[f"warm.{k}.p50ms"], f[f"warm.{k}.p99ms"] = wl[b]["p50"] * 1000, wl[b]["p99"] * 1000
    for b, k in (("ac-v1", "v1"), ("ac-v2", "v2"), ("ac-v2-prewarm", "v2pw"), ("ac-v1-probe", "v1t"), ("ac-v2-probe", "v2t"), ("lm-probe", "lmt"), ("eks-x86-gvisor-traffic", "gvt"), ("eks-x86-kata-traffic", "ktt"), ("lm", "lm"), ("lm-prewarm", "lmpw"), ("eks-x86-gvisor", "gv"), ("eks-x86-kata", "kt"), ("eks-g3-gvisor", "g3gv")):
        a = s["agent"]["e2e"].get(b)
        if a and a.get("attempted") and a["n"]:
            f[f"agent.{k}.n"], f[f"agent.{k}.tried"], f[f"agent.{k}.cold_p50"] = a["n"], a["attempted"], a["cold_p50"]
            f[f"agent.{k}.first.p50"], f[f"agent.{k}.first.p90"], f[f"agent.{k}.first.max"] = a["first_message"]["p50"], a["first_message"]["p90"], a["first_message"]["max"]
            f[f"agent.{k}.wall.p50"], f[f"agent.{k}.wall.p90"] = a["wall"]["p50"], a["wall"]["p90"]
            f[f"agent.{k}.api_ms"], f[f"agent.{k}.total_p50"] = a["api_ms_p50"], a["cold_plus_wall_p50"]
        r = s["agent"]["first_vs_repeat"].get(b)
        if r:
            for i in range(3):
                if f"run{i}" in r:
                    f[f"repeat.{k}.{i}"] = r[f"run{i}"]["first_message_p50"]
    t = s["first_touch"]
    for b, k in (("ac-v1-probe", "v1"), ("ac-v2-probe", "v2"), ("lm-probe", "lm"), ("eks-g3-gvisor-probe", "g3gv"), ("eks-x86-gvisor-probe", "gv"), ("eks-x86-kata-probe", "kt")):
        if b in t:
            for op in ("read_cli_binary", "python_import_boto3", "pytest_version", "git_version", "claude_version"):
                f[f"touch.{k}.{op}.first"], f[f"touch.{k}.{op}.second"] = t[b][f"{op}_first"]["p50"], t[b][f"{op}_second"]["p50"]
    sc = s["suite"]
    for k, b in PLAT.items():
        x = sc.get(b)
        if not x:
            continue
        for op, fld in (("cpu_python", "seconds"), ("cpu_sha256", "seconds"), ("files_small", "seconds"), ("mem_touch", "seconds"), ("compile_stdlib", "seconds"), ("pytest_project", "seconds"), ("disk_seq", "write_MBps"), ("disk_seq", "read_MBps"), ("net_download", "MBps"), ("git_clone", "seconds"), ("pip_install", "seconds"), ("tls_connect", "seconds")):
            if op in x and fld in x[op]:
                f[f"suite.{k}.{op}.{fld}"] = x[op][fld]
        for fld in ("getppid_ns", "open_close_ns", "page_fault_ns", "pipe_roundtrip_ns", "fork_exit_ns", "fork_exec_ns"):
            if "syscalls" in x and fld in x["syscalls"]:
                f[f"sys.{k}.{fld}"] = x["syscalls"][fld]
    for b, d in s.get("suite_by_cpu", {}).items():
        k = {"ac-v1": "v1", "ac-v2": "v2", "lm": "lm"}.get(b)
        if k:
            for cpu, ops in d.items():
                for op, fld in (("cpu_python", "seconds"), ("files_small", "seconds"), ("compile_stdlib", "seconds"), ("pytest_project", "seconds"), ("mem_touch", "seconds")):
                    if op in ops:
                        f[f"bycpu.{k}.{cpu}.{op}"] = ops[op].get(fld)
                if "syscalls" in ops:
                    for fld in ("getppid_ns", "open_close_ns", "fork_exec_ns"):
                        f[f"bycpu.{k}.{cpu}.{fld}"] = ops["syscalls"].get(fld)
                f[f"bycpu.{k}.{cpu}.sandboxes"] = next(iter(ops.values()))["sandboxes"]
    for b, k in (("ac-v1", "v1"), ("ac-v2", "v2"), ("lm", "lm")):
        for cpu, v in s["hw_census"].get(b, {}).items():
            f[f"census.{k}.{cpu}.n"], f[f"census.{k}.{cpu}.cpu_python"], f[f"census.{k}.nproc"], f[f"census.{k}.mem"], f[f"census.{k}.kernel"] = v["n"], v["cpu_python_p50"], v["nproc"], v["mem"], v["kernel"]
    li = s["lifecycle"]
    for b, k in (("ac-v1-idle60", "v1"), ("ac-v2-idle60", "v2")):
        f[f"idle.{k}"] = li["idle_reclaim"][b]
    f["wipe"] = li["state_wipe"]
    for key, v in li["suspend_resume"].items():
        mb, mode = key.split("/")
        f[f"susp.{mb}.{mode}.resume_p50"], f[f"susp.{mb}.{mode}.suspend_p50"], f[f"susp.{mb}.{mode}.n"], f[f"susp.{mb}.{mode}.memkept"], f[f"susp.{mb}.{mode}.diskkept"] = v["resume_p50"], v["suspend_p50"], v["n"], v["memory_kept"], v["disk_kept"]
    f["mvidle.suspend_p50"], f["mvidle.term_p50"] = li["microvm_idle_policy"]["p50"], li["microvm_idle_policy"]["suspended_to_terminated"]["p50"]
    f["long"] = li["long_request"]
    dp = li["deploy_time"]
    f["deploy.v1"], f["deploy.v2"], f["deploy.lm"] = dp["sbxac_v1"]["seconds"][0], dp["sbxac_v2"]["seconds"][0], dp["sbx-lm"]["seconds"][0]
    ns = li["node_scale"].get("eks-x86-gvisor")
    if ns:
        f["scale.gv.ready"], f["scale.gv.total"], f["scale.gv.removed"], f["scale.gv.n"] = ns["p50"], ns["node_to_sandbox"]["p50"], ns["removed"]["p50"], ns["n"]
    ks = s.get("kata_scale") or []
    if ks:
        k0 = ks[-1]
        f["scale.kt.ready"], f["scale.kt.install"], f["scale.kt.cold"], f["scale.kt.total"], f["scale.kt.removed"], f["scale.kt.n"] = k0["node_ready_s"], k0["kata_install_s"], k0["first_sandbox_cold_s"], k0["total_s"], k0["node_removed_s"], len(ks)
    for k, b in (("rc", "eks-x86-runc"), ("gv", "eks-x86-gvisor"), ("kt", "eks-x86-kata")):
        pts = [d["used_delta_mb_per_sandbox"] for d in s["density"].get(b, []) if d.get("used_delta_mb_per_sandbox")]
        if pts:
            f[f"density.{k}.mb"] = pts[-1]
    for kind, d in s["usage"].items():
        for b, v in d.items():
            k = {"ac-v1": "v1", "ac-v2": "v2", "ac-v1-np": "v1np", "ac-v2-np": "v2np"}[b]
            f[f"usage.{kind}.{k}.gbh"], f[f"usage.{kind}.{k}.vcpuh"], f[f"usage.{kind}.{k}.cost"], f[f"usage.{kind}.{k}.tail"], f[f"usage.{kind}.{k}.n"] = v["gb_hours_p50"], v["vcpu_hours_p50"], v["cost_usd_p50"], v["last60_gb_p50"], v["n"]
    f["agent.v2after"] = s["agent"]["e2e"].get("_v2_after_idle")
    f["agent.v2after45"] = s["agent"]["e2e"].get("_v2_after_idle45")
    f["agent.v2control"] = s["agent"]["e2e"].get("_v2_control")
    for b, k in (("ac-v1-probe", "v1"), ("ac-v2-probe", "v2"), ("lm-probe", "lm")):
        d = s["first_touch_traffic"].get(b)
        if d:
            f[f"touchT.{k}.read"] = d["read_cli_binary_first"]["p50"]
            f[f"touchT.{k}.read2"] = d["read_cli_binary_second"]["p50"]
    for kind, d in s["usage"].items():
        for b, v in d.items():
            k = {"ac-v1": "v1", "ac-v2": "v2", "ac-v1-np": "v1np", "ac-v2-np": "v2np"}[b]
            f[f"usage.{kind}.{k}.cost_min"], f[f"usage.{kind}.{k}.cost_max"] = v["cost_min"], v["cost_max"]
    f["fair"] = s["fair"]
    for k, b in (("v1np", "ac-v1-np-idle60"), ("v2np", "ac-v2-np-idle60")):
        f[f"idle.{k}"] = li["idle_reclaim"].get(b)
    for k, b in (("v1np", "ac-v1-np"), ("v2np", "ac-v2-np"), ("v1zip", "ac-v1-zip"), ("v2zip", "ac-v2-zip"), ("v1tiny", "ac-v1-tiny"), ("v1vpc", "ac-v1-vpc"), ("v2vpc", "ac-v2-vpc")):
        d = cs.get(b)
        if d and d.get("n"):
            f[f"cold.{k}.p50"], f[f"cold.{k}.p90"], f[f"cold.{k}.n"], f[f"cold.{k}.fail"], f[f"cold.{k}.warmshare"] = d["p50"], d["p90"], d["n"], d["failed"], d["preexisting_process_share"]
        for rate, v in s["sustained"].get(b, {}).items():
            rk = str(int(float(rate)))
            f[f"sus.{k}.{rk}.p50"], f[f"sus.{k}.{rk}.p90"], f[f"sus.{k}.{rk}.p95"], f[f"sus.{k}.{rk}.fail"], f[f"sus.{k}.{rk}.n"] = v["p50"], v.get("p90"), v["p95"], v["failed"], v["n"]
        for size, runs in s["burst"].get(b, {}).items():
            runs = [x for x in runs if str(x.get("round", "")).startswith("final")] or runs
            r = sorted(runs, key=lambda x: x["p50"])[len(runs) // 2]
            f[f"burst.{k}.{size}.p50"], f[f"burst.{k}.{size}.p95"], f[f"burst.{k}.{size}.fail"], f[f"burst.{k}.{size}.runs"] = r["p50"], r["p95"], r.get("failed", 0), len(runs)
    for p in ("V1", "V2"):
        for img in ("zip", "tiny"):
            d = fr.get(f"{p}/{img}/call0")
            if d:
                f[f"fresh.{p}.{img}.first"], f[f"fresh.{p}.{img}.third"] = d["p50"], fr[f"{p}/{img}/call2"]["p50"]
    for k, n in (("v1large", "sbxac_v1_large"), ("v1zip", "sbxac_v1_zip"), ("v2zip", "sbxac_v2_zip"), ("v1tiny", "sbxac_v1_tiny"), ("v1vpc", "sbxac_v1_vpc"), ("v2vpc", "sbxac_v2_vpc")):
        if n in dp:
            f[f"deploy.{k}"] = dp[n]["seconds"][0]
    # Small losses that the headline tables do not show.
    f["small"] = {"burst_failed": {b: sum(x.get("failed", 0) for x in runs) for b, d in s["burst"].items() for runs in d.values() if str(runs[0].get("round", "")).startswith("final") and any(x.get("failed") for x in runs)},
                  "sus_throttles": {b: {r: v["throttles"] for r, v in d.items() if v.get("throttles")} for b, d in s["sustained"].items() if b.startswith(("ac-")) and any(v.get("throttles") for v in d.values())},
                  "burst_final_throttles": sum(x.get("throttles", 0) for b, d in s["burst"].items() if b.startswith("ac-") for runs in d.values() for x in runs if str(x.get("round", "")).startswith("final"))}
    f["np_creds"] = [r["result"] for r in s.get("observability_checks", []) if r.get("check") == "aws_credentials_under_managed_network_policy"]
    f["security"] = s["security"]
    f["observability"] = s["observability"]
    f["cost"] = c
    f["sysinfo"] = s["sysinfo"]
    return f


if __name__ == "__main__":
    f = build()
    print(len(f), "facts")
    (ROOT / "results" / "facts.json").write_text(json.dumps(f, indent=0, default=str))
