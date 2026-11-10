#!/usr/bin/env python3
"""Monthly compute cost under declared scenarios.

Measured inputs, read from results/summary.json:
  AgentCore memory and idle vCPU per second (USAGE_LOGS), EKS memory per idle sandbox (host memory delta).
Published inputs: prices below. Assumptions: everything in SCENARIOS, plus the MicroVM suspend share.
AgentCore sessions are assumed to be stopped explicitly at the end; *_no_stop adds the default 15 minute idle tail.
Excluded on every platform: LLM tokens, data transfer and NAT per-GB charges, logs, MicroVM snapshot storage, engineer time.
EKS includes what the tested setup runs beyond worker nodes: control plane, 2 system nodes, gp3 volumes as configured, one NAT Gateway.
Unmeasured and shown as ranges: agent memory on EKS (0.3 GB assumed, V2's billed idle memory as the high case),
and the MicroVM size (1 vCPU/2 GB as the smallest setting, 2 vCPU/4 GB as tested).
"""
import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRICES = {
    "as_of": "2026-11-03", "region": "us-east-1",
    "agentcore_v1": {"vcpu_h": 0.0895, "gb_h": 0.00945, "source": "aws.amazon.com/bedrock/agentcore/pricing"},
    "agentcore_v2": {"vcpu_h": 0.1276, "gb_h": 0.0169, "source": "aws.amazon.com/bedrock/agentcore/pricing, consumption rate"},
    "microvm_arm": {"vcpu_s": 0.0000276944, "gb_s": 0.0000036667, "snap_read_gb": 0.0015467699, "snap_write_gb": 0.0037977138, "snap_storage_gb_month": 0.08, "source": "AWS Pricing API, aws.amazon.com/lambda/pricing"},
    "ec2": {"m8i.2xlarge": 0.42336, "m7g.2xlarge": 0.3264, "m7i.large": 0.1008, "source": "AWS Pricing API, on-demand"},
    "fargate_x86": {"vcpu_h": 0.04048, "gb_h": 0.004445, "source": "AWS Pricing API, USE1-Fargate-vCPU-Hours:perCPU and USE1-Fargate-GB-Hours"},
    "eks_auto_m8i.2xlarge_h": 0.0508,  # AWS Pricing API, EKS-Auto:m8i.2xlarge-management-hours
    "eks_cluster_h": 0.10,
    "nat_h": 0.045,
    "public_ipv4_h": 0.005,
    "gp3_node_month": 100 * 0.08 + (6000 - 3000) * 0.005 + (400 - 125) * 0.04,  # 100 GB, 6000 IOPS, 400 MB/s as in infra/terraform/eks.tf
}
HOURS = 730
DAYS = 30.4
NODE_CPU, NODE_GB = 7.9, 29.0  # allocatable on m8i.2xlarge after kubelet and system reservation
SCENARIOS = {
    "interactive": {"label": "Interactive assistant", "sessions_per_day": 5000, "minutes": 10, "cpu_active": 0.05, "extra_gb": 0.3, "peak_to_avg": 3, "running_share": 0.3},
    "code_exec": {"label": "Short code execution", "sessions_per_day": 50000, "minutes": 0.5, "cpu_active": 0.5, "extra_gb": 0.3, "peak_to_avg": 3, "running_share": 1.0},
    "coding": {"label": "Coding agent with builds", "sessions_per_day": 500, "minutes": 60, "cpu_active": 0.3, "extra_gb": 2.0, "peak_to_avg": 3, "running_share": 0.6},
    "build_heavy": {"label": "Build-heavy agents, mostly on CPU", "sessions_per_day": 500, "minutes": 60, "cpu_active": 1.5, "extra_gb": 2.0, "peak_to_avg": 3, "running_share": 0.8},
    "steady": {"label": "Steady high concurrency", "sessions_per_day": 288000, "minutes": 1, "cpu_active": 0.2, "extra_gb": 0.3, "peak_to_avg": 1.3, "running_share": 1.0},
}


def concurrency(s):
    return s["sessions_per_day"] * s["minutes"] / 1440


def measured_agentcore(summary, b):
    """Billed memory falls during a session, so the average is taken over the session's length from the 1 s series. Runs with the documented /ping.
    The long idle runs last about 15 minutes, because AgentCore reclaims at its default idle timeout."""
    rate = lambda u: {"idle_gb": u["gb_hours_p50"] * 3600 / u["seconds_p50"], "idle_vcpu": u["vcpu_hours_p50"] * 3600 / u["seconds_p50"]}
    series = [json.loads(l) for l in (ROOT / "results" / "raw" / "usage_logs.jsonl").open()]
    series = [r["series_gb"] for r in series if r["backend"] == b and r["alloc_mb"] == 0 and r["idle_s"] == 1800]
    med = lambda xs: sorted(xs)[len(xs) // 2]
    return {"short": rate(summary["usage"]["idle_only_5min"][b]), "long": rate(summary["usage"]["idle_only_30min"][b]), "series": series,
            "tail_gb": med([sum(x[-60:]) / len(x[-60:]) for x in series])}


def _avg_gb(m, seconds):
    return sorted(sum(x[:int(seconds)]) / len(x[:int(seconds)]) for x in m["series"])[len(m["series"]) // 2]


def agentcore(s, ver, m):
    p = PRICES[f"agentcore_{ver}"]
    h = s["minutes"] / 60
    gb = _avg_gb(m, min(s["minutes"], 15) * 60)
    r = m["long"] if s["minutes"] >= 15 else m["short"]
    return h * ((s["cpu_active"] + r["idle_vcpu"]) * p["vcpu_h"] + (gb + s["extra_gb"]) * p["gb_h"]) * s["sessions_per_day"] * DAYS


def agentcore_no_stop(s, ver, m):
    """The same session when the app never calls stop: it also bills the default 15 minute idle tail at the measured tail memory."""
    p = PRICES[f"agentcore_{ver}"]
    tail = 0.25 * (m["long"]["idle_vcpu"] * p["vcpu_h"] + (m["tail_gb"] + s["extra_gb"]) * p["gb_h"]) * s["sessions_per_day"] * DAYS
    return agentcore(s, ver, m) + tail


def microvm(s, running_share=1.0, launch_read_gb=1.0, min_gb=2.0):
    p = PRICES["microvm_arm"]
    base_gb = max(min_gb, 2 * math.ceil((s["extra_gb"] + 0.5) / 2))  # configured baseline, billed in full while RUNNING
    base_cpu = base_gb / 2
    sec = s["minutes"] * 60 * running_share
    # About 1 GB read per launch matches our bill for the base image. A suspend writes and a resume reads the baseline memory,
    # as in the AWS worked examples, and the suspended state is stored at the snapshot storage rate.
    per = sec * (base_cpu * p["vcpu_s"] + base_gb * p["gb_s"]) + launch_read_gb * p["snap_read_gb"]
    if running_share < 1:
        per += base_gb * (p["snap_write_gb"] + p["snap_read_gb"]) * 3  # assumes 3 suspend and resume cycles per session
        per += base_gb * s["minutes"] * 60 * (1 - running_share) / (720 * 3600) * p["snap_storage_gb_month"]
    return per * s["sessions_per_day"] * DAYS


def eks(s, overhead_gb, cpu_overhead, autoscaled, base_gb=0.3, warm_pods=0, instance="m8i.2xlarge", existing_cluster=False):
    target = concurrency(s) * (1.25 if autoscaled else s["peak_to_avg"]) + warm_pods
    per_cpu = max(0.25, s["cpu_active"]) + cpu_overhead  # 0.25 vCPU request as used in the tests, Kata adds its pod overhead
    per_gb = s["extra_gb"] + base_gb + overhead_gb
    per_node = min(NODE_CPU / per_cpu, NODE_GB / per_gb)
    nodes = max(2, math.ceil(target / per_node))
    fixed_h = PRICES["eks_cluster_h"] + PRICES["nat_h"] + PRICES["public_ipv4_h"] + 2 * PRICES["ec2"]["m7i.large"]
    disks = (nodes + 2) * PRICES["gp3_node_month"]
    if existing_cluster:  # a customer who already runs EKS adds worker nodes only
        return nodes * (PRICES["ec2"][instance] * HOURS + PRICES["gp3_node_month"]), nodes, per_node
    return (nodes * PRICES["ec2"][instance] + fixed_h) * HOURS + disks, nodes, per_node


FARGATE_SIZES = [(0.25, [0.5, 1, 2])] + [(0.5, [1, 2, 3, 4])] + [(1, list(range(2, 9)))] + [(2, list(range(4, 17)))] + [(4, list(range(8, 31)))]


def fargate(s, startup_s, size=None):
    """EKS Fargate: one microVM per sandbox pod, sized from the pod requests plus 256 MiB, billed per second
    from the image pull until the pod ends, with a one minute minimum. The cluster's fixed costs are as for EKS."""
    p = PRICES["fargate_x86"]
    cpu_need, gb_need = max(0.25, s["cpu_active"]), s["extra_gb"] + 0.3 + 0.25
    cpu, gb = size or next((c, m) for c, ms in FARGATE_SIZES for m in ms if c >= cpu_need and m >= gb_need)
    sec = max(60, s["minutes"] * 60 + startup_s)
    per = sec / 3600 * (cpu * p["vcpu_h"] + gb * p["gb_h"])
    fixed_h = PRICES["eks_cluster_h"] + PRICES["nat_h"] + PRICES["public_ipv4_h"] + 2 * PRICES["ec2"]["m7i.large"]
    return per * s["sessions_per_day"] * DAYS + fixed_h * HOURS + 2 * PRICES["gp3_node_month"], (cpu, gb)


def nitro(s, auto_mode=True, autoscaled=True):
    """Nitro Sandboxes on EC2 nodes: the VM gets its requests, and memory is reserved in full, plus the
    256 MiB pod overhead that the isolated-sandbox RuntimeClass declares. Auto Mode adds its per-node fee."""
    cost, nodes, per_node = eks(s, 0.25, 0, autoscaled)
    if auto_mode:
        cost += nodes * PRICES["eks_auto_m8i.2xlarge_h"] * HOURS
    return cost, nodes, per_node


def check_against_aws_examples():
    """Reproduces the worked examples on the public pricing pages, so a formula error cannot pass unnoticed."""
    c, m = PRICES["agentcore_v2"]["vcpu_h"], PRICES["agentcore_v2"]["gb_h"]
    support = 60 * 1 * c / 3600 + (300 * 1 + 150 * 2 + 150 * 2.5) * m / 3600
    p = PRICES["microvm_arm"]
    job = 60 * (16 * p["vcpu_s"] + 32 * p["gb_s"]) + 540 * (4 * p["vcpu_s"] + 8 * p["gb_s"])
    job_month = 10000 * job + 10000 * 2 * p["snap_read_gb"] + 2 * p["snap_storage_gb_month"]
    return {"agentcore_v2_support_monthly_1m": 1e6 * support, "aws_says_agentcore_v2": 6703, "microvm_ci_monthly_10k": job_month, "aws_says_microvm_ci": 1124.03}


def main():
    sm = json.loads((ROOT / "results" / "summary.json").read_text())
    fu = json.loads((ROOT / "results" / "followup.json").read_text()).get("new", {})
    fg_start = fu["fg"]["cold"]["fg-fs"]["p50"] if "fg" in fu else 57.0
    dens = sm["density"]
    def ov(b):
        return [d["used_delta_mb_per_sandbox"] for d in dens[b] if d.get("used_delta_mb_per_sandbox")][-1] / 1024
    gv, kt = ov("eks-x86-gvisor"), ov("eks-x86-kata")
    m1, m2 = measured_agentcore(sm, "ac-v1-np"), measured_agentcore(sm, "ac-v2-np")
    out = {"prices": PRICES, "measured_inputs": {"ac_v1": {k: v for k, v in m1.items() if k != "series"}, "ac_v2": {k: v for k, v in m2.items() if k != "series"}, "gvisor_overhead_gb": gv, "kata_overhead_gb": kt}, "assumptions": "Scenario values are illustrations, not measurements. EKS autoscaled means 25% headroom over average; peak means sized for peak at all times.", "scenarios": {}}
    for k, s in SCENARIOS.items():
        ga, n1, pn1 = eks(s, gv, 0, True)
        gp, n2, _ = eks(s, gv, 0, False)
        ka, n3, pn3 = eks(s, kt, 0.25, True)
        kp, n4, _ = eks(s, kt, 0.25, False)
        high = m2["short"]["idle_gb"]
        extra = {
            "microvm_tested_size": microvm(s, min_gb=4.0),
            "agentcore_v1_no_stop": agentcore_no_stop(s, "v1", m1),
            "agentcore_v2_no_stop": agentcore_no_stop(s, "v2", m2),
            "eks_gvisor_autoscaled_warm30": eks(s, gv, 0, True, warm_pods=30)[0],
            "eks_gvisor_autoscaled_mem_high": eks(s, gv, 0, True, base_gb=high)[0],
            "eks_gvisor_autoscaled_graviton3": eks(s, gv, 0, True, instance="m7g.2xlarge")[0],
            "eks_gvisor_autoscaled_existing_cluster": eks(s, gv, 0, True, existing_cluster=True)[0],
            "eks_kata_autoscaled_existing_cluster": eks(s, kt, 0.25, True, existing_cluster=True)[0],
            "eks_kata_autoscaled_mem_high": eks(s, kt, 0.25, True, base_gb=high)[0],
            "fargate": fargate(s, fg_start)[0],
            "fargate_size": fargate(s, fg_start)[1],
            "fargate_tested_size": fargate(s, fg_start, (2, 8))[0],  # 2 vCPU / 8 GB as tested: Fargate cannot burst past its size
            "nitro_auto_autoscaled": nitro(s)[0],
            "nitro_auto_peak": nitro(s, autoscaled=False)[0],
            "nitro_custom_ami_autoscaled": nitro(s, auto_mode=False)[0],
            "nitro_auto_autoscaled_existing_cluster": nitro(s)[0] - (PRICES["eks_cluster_h"] + PRICES["nat_h"] + PRICES["public_ipv4_h"] + 2 * PRICES["ec2"]["m7i.large"]) * HOURS - 2 * PRICES["gp3_node_month"],
            "fargate_existing_cluster": fargate(s, fg_start)[0] - (PRICES["eks_cluster_h"] + PRICES["nat_h"] + PRICES["public_ipv4_h"] + 2 * PRICES["ec2"]["m7i.large"]) * HOURS - 2 * PRICES["gp3_node_month"],
        }
        out["scenarios"][k] = {**s, **extra, "avg_concurrency": concurrency(s), "agentcore_v1": agentcore(s, "v1", m1), "agentcore_v2": agentcore(s, "v2", m2), "microvm_always_running": microvm(s), "microvm_with_suspend": microvm(s, s["running_share"]), "eks_gvisor_autoscaled": ga, "eks_gvisor_peak": gp, "eks_kata_autoscaled": ka, "eks_kata_peak": kp, "nodes": {"gvisor_autoscaled": n1, "gvisor_peak": n2, "kata_autoscaled": n3, "kata_peak": n4}, "sandboxes_per_node": {"gvisor": pn1, "kata": pn3}}
    # Break-even: concurrent sessions where autoscaled gVisor on EKS equals AgentCore V2, for the interactive shape.
    s = dict(SCENARIOS["interactive"])
    be = be_peak = be_warm = None
    for conc in range(1, 20000):
        s["sessions_per_day"] = conc * 1440 / s["minutes"]
        v2 = agentcore(s, "v2", m2)
        if be is None and eks(s, gv, 0, True)[0] < v2:
            be = conc
        if be_peak is None and eks(s, gv, 0, False)[0] < v2:
            be_peak = conc
        if be_warm is None and eks(s, gv, 0, True, warm_pods=30)[0] < v2:
            be_warm = conc
        if be and be_peak and be_warm:
            break
    # Node counts step, so a first crossing can flip back. Also record where the cheaper side stops changing.
    last = last_warm = 0
    for conc in range(1, 500):
        s["sessions_per_day"] = conc * 1440 / s["minutes"]
        v2 = agentcore(s, "v2", m2)
        if eks(s, gv, 0, True)[0] >= v2:
            last = conc
        if eks(s, gv, 0, True, warm_pods=30)[0] >= v2:
            last_warm = conc
    out["gvisor_stays_cheaper_from"] = last + 1
    out["gvisor_warm30_stays_cheaper_from"] = last_warm + 1
    out["break_even_concurrency_interactive_gvisor_vs_v2"] = be
    out["break_even_concurrency_interactive_gvisor_peak_vs_v2"] = be_peak
    out["break_even_concurrency_interactive_gvisor_warm30_vs_v2"] = be_warm
    out["aws_example_check"] = check_against_aws_examples()
    out["suspend_breakeven_idle_s_smallest"] = 2 * (PRICES["microvm_arm"]["snap_write_gb"] + PRICES["microvm_arm"]["snap_read_gb"]) / (PRICES["microvm_arm"]["vcpu_s"] + 2 * PRICES["microvm_arm"]["gb_s"])
    (ROOT / "results" / "cost_model.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["measured_inputs"]))
    for k, v in out["scenarios"].items():
        print(k, f"conc={v['avg_concurrency']:.0f}", *(f"{m.replace('agentcore_','ac_').replace('microvm_','mv_').replace('eks_','')}={v[m]:,.0f}" for m in ("agentcore_v1", "agentcore_v2", "microvm_always_running", "microvm_with_suspend", "eks_gvisor_autoscaled", "eks_kata_autoscaled", "eks_gvisor_peak", "fargate", "nitro_auto_autoscaled")))
    print("break-even", be, be_peak, be_warm)


if __name__ == "__main__":
    main()
