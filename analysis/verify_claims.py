#!/usr/bin/env python3
"""Checks that every comparative claim still holds in the data.
A claim that the data does not support fails this script, including across rounds."""
import json
from pathlib import Path

F = json.loads((Path(__file__).resolve().parent.parent / "results" / "facts.json").read_text())
fails = []
checked = 0


def claim(text, ok):
    global checked
    checked += 1
    print(("PASS " if ok else "FAIL ") + text)
    if not ok:
        fails.append(text)


def every_round(a, b):
    """a < b in every round, so that a single lucky round cannot carry a claim."""
    ra, rb = F[a], F[b]
    return all(ra[r] < rb[r] for r in ra if r in rb)


# Cold start
claim("Low-rate: V1 is faster than V2 in every round", every_round("cold.v1.rounds", "cold.v2.rounds"))
claim("Low-rate: gVisor is faster than Kata in every round", every_round("cold.gv.rounds", "cold.kt.rounds"))
claim("Warm pool allocation is under 200 ms at p50", F["cold.gvw.p50"] < 0.2 and F["cold.ktw.p50"] < 0.2)
claim("Metal Kata starts faster than nested Kata", F["cold.ktm.p50"] < F["cold.kt.p50"])
claim("Fresh runtime: V2 beats V1", F["fresh.V2.base.first"] < F["fresh.V1.base.first"] and F["fresh.V2.large.first"] < F["fresh.V1.large.first"])
claim("Fresh runtime V1 is in AWS's published 5.4 to 30 s range", 5.4 <= F["fresh.V1.base.first"] <= 30 and 5.4 <= F["fresh.V1.large.first"] <= 30)
claim("Fresh runtime V2 is about 2 s", F["fresh.V2.base.first"] < 3 and F["fresh.V2.large.first"] < 3)
for r in ("1", "5", "10"):
    claim(f"Sustained {r}/s: V2 beats V1", F[f"sus.v2.{r}.p50"] < F[f"sus.v1.{r}.p50"])
claim("Sustained: V2 stays under 2.5 s at 10/s including large image", F["sus.v2.10.p50"] < 2.5 and F["sus.v2large.10.p50"] < 2.5)
claim("Sustained: MicroVM at quota rate is comparable with V2", abs(F["sus.lm.5.p50"] - F["sus.v2.5.p50"]) < 0.5)
claim("Burst: no failed sandbox on any platform at any size", all(v == 0 for k, v in F.items() if k.startswith("burst.") and k.endswith(".fail")))
claim("Heavy init: snapshot platforms absorb the 10 s", F["cold.v2.heavy.p50"] < 4 and F["cold.lm.heavy.p50"] < 4)
claim("Heavy init: EKS pays it on every start", F["cold.gv.heavy.p50"] > 10 and F["cold.kt.heavy.p50"] > 10)
# Agent readiness
claim("Low rate, SDK first message: V2 is slower than V1", F["agent.v2.first.p50"] > 5 * F["agent.v1.first.p50"])
claim("Low rate, SDK first message: MicroVM is slower than V1", F["agent.lm.first.p50"] > 3 * F["agent.v1.first.p50"])
claim("At low rate, the whole request is shorter on V1 than on V2 and MicroVM", F["agent.v1.total_p50"] < F["agent.v2.total_p50"] and F["agent.v1.total_p50"] < F["agent.lm.total_p50"])
claim("Under 3/s, V1 sessions are truly cold at p50", F["agent.v1t.cold_p50"] > 5)
claim("Under 3/s, gVisor stays near its low-rate whole request time", F["agent.gvt.total_p50"] < 1.2 * F["agent.gv.total_p50"])
claim("Under 3/s, Kata stays near its low-rate whole request time", F["agent.ktt.total_p50"] < 1.2 * F["agent.kt.total_p50"])
claim("SDK first message: EKS has no first-run delay", F["agent.gv.first.p50"] < 4 and F["agent.kt.first.p50"] < 4)
claim("Task wall time: gVisor, Kata and V1 are within 30 percent", max(F["agent.gv.wall.p50"], F["agent.kt.wall.p50"], F["agent.v1.wall.p50"]) < 1.3 * min(F["agent.gv.wall.p50"], F["agent.kt.wall.p50"], F["agent.v1.wall.p50"]))
claim("Model call time is similar everywhere (not the cause)", max(F[f"agent.{k}.api_ms"] for k in ("v1", "v2", "lm", "gv", "kt")) < 1.5 * min(F[f"agent.{k}.api_ms"] for k in ("v1", "v2", "lm", "gv", "kt")))
claim("First read of the CLI is at least 100x the second on V2", F["touch.v2.read_cli_binary.first"] > 100 * F["touch.v2.read_cli_binary.second"])
claim("First read of the CLI is at least 100x the second on MicroVM", F["touch.lm.read_cli_binary.first"] > 100 * F["touch.lm.read_cli_binary.second"])
claim("First read of the CLI is under 2 s on V1, gVisor and Kata", all(F[f"touch.{k}.read_cli_binary.first"] < 2 for k in ("v1", "gv", "kt")))
claim("Repeat SDK start in the same sandbox is under 1 s on V2 and MicroVM", F["repeat.v2.1"] < 1 and F["repeat.lm.1"] < 1)
claim("Prewarm lowers p50 on V2 and MicroVM", F["agent.v2pw.first.p50"] < F["agent.v2.first.p50"] and F["agent.lmpw.first.p50"] < F["agent.lm.first.p50"])
claim("Prewarm does not remove slow sessions (p90 stays high)", F["agent.v2pw.first.p90"] > 10)
# Isolation cost
claim("getppid: gVisor is at least 10x runc on x86", F["sys.gv.getppid_ns"] > 10 * F["sys.rc.getppid_ns"])
claim("getppid: Kata is not slower than runc", F["sys.kt.getppid_ns"] <= F["sys.rc.getppid_ns"])
claim("open/close: Kata is at least 10x runc, on metal too", F["sys.kt.open_close_ns"] > 10 * F["sys.rc.open_close_ns"] and F["sys.ktm.open_close_ns"] > 10 * F["sys.rc.open_close_ns"])
claim("fork+exec: nesting adds cost on Kata", F["sys.kt.fork_exec_ns"] > F["sys.ktm.fork_exec_ns"])
claim("Compile: runc < gVisor < nested Kata on x86", F["suite.rc.compile_stdlib.seconds"] < F["suite.gv.compile_stdlib.seconds"] < F["suite.kt.compile_stdlib.seconds"])
claim("Memory per idle sandbox: runc < gVisor < Kata", F["density.rc.mb"] < F["density.gv.mb"] < F["density.kt.mb"])
# Fleet
claim("AgentCore mixes Graviton2 and Graviton3", all(F.get(f"census.{k}.{c}.n", 0) > 5 for k in ("v1", "v2") for c in ("Graviton2", "Graviton3")))
claim("MicroVM mixes Graviton3 and Graviton4", all(F.get(f"census.lm.{c}.n", 0) > 5 for c in ("Graviton3", "Graviton4")))
claim("Graviton2 sessions are slower for pure Python than Graviton3", F["census.v1.Graviton2.cpu_python"] > 1.3 * F["census.v1.Graviton3.cpu_python"])
# Lifecycle
claim("V2 with 60 s idle: alive at 60 s, gone by 70 s", F["idle.v2np"]["60"]["alive"] == F["idle.v2np"]["60"]["n"] and F["idle.v2np"]["70"]["alive"] == 0)
claim("Explicit stop wipes memory and disk on V1 and V2", all(F["wipe"][b]["memory_survived"] == 0 and F["wipe"][b]["disk_survived"] == 0 for b in ("ac-v1", "ac-v2")))
claim("MicroVM keeps memory and disk across every resume", all(F[f"susp.{m}.{t}.memkept"] == F[f"susp.{m}.{t}.n"] == F[f"susp.{m}.{t}.diskkept"] for m in ("0MB", "512MB", "2048MB") for t in ("api", "traffic")))
claim("MicroVM API resume is at least 10x faster than traffic resume", F["susp.0MB.traffic.resume_p50"] > 10 * F["susp.0MB.api.resume_p50"])
L = F["long"]
def lr(b, s):
    return [x for x in L if x["backend"] == b and x["requested_s"] == s and (x.get("mode") or "sleep") == "sleep"]
claim("20 min silent request completes on EKS", all(x["ok"] for b in ("eks-x86-gvisor", "eks-x86-kata") for x in lr(b, 1200)) and lr("eks-x86-gvisor", 1200))
claim("MicroVM silent request returns 502 near 900 s", all(not x["ok"] and 890 < x["wall_s"] < 910 for x in lr("lm", 1200) + lr("lm", 960)))
claim("14 min silent request completes on MicroVM", all(x["ok"] for x in lr("lm", 840)) and lr("lm", 840))
claim("AgentCore silent requests of 120 s and 300 s complete", all(x["ok"] for b in ("ac-v1", "ac-v2") for s in (120, 300) for x in lr(b, s)))
def ka(b, s):
    return [x for x in L if x["backend"] == b and x["requested_s"] == s and x.get("mode") == "sleep_keepalive"]
claim("With TCP keepalive, AgentCore silent requests complete up to 840 s", all(ka(b, s) and all(x["ok"] for x in ka(b, s)) for b in ("ac-v1", "ac-v2") for s in (360, 600, 840)))
claim("AgentCore silent requests past 15 minutes fail near 900 s", all(ka(b, s) and all((not x["ok"]) and 880 < x["wall_s"] < 910 for x in ka(b, s)) for b in ("ac-v1", "ac-v2") for s in (960, 1200)))
hb = [x for x in L if x.get("mode") == "stream_sleep"]
claim("15 s heartbeat: 1500 s request completes on V1, V2 and MicroVM", len(hb) >= 3 and all(x["ok"] for x in hb))
# Cost
A = "agent_task_then_5min_idle"
claim("Real agent session: V2 bills less GB-h than V1", F[f"usage.{A}.v2.gbh"] < F[f"usage.{A}.v1.gbh"])
claim("Real agent session: V2 costs less than V1", F[f"usage.{A}.v2.cost"] < F[f"usage.{A}.v1.cost"])
c = F["cost"]["scenarios"]
# Security, as observed in default settings
S = F["security"]
claim("EKS without enforced policy: peer sandbox reachable", all(S[f"{b}/default"]["peer_sandbox_tcp"] == "open" for b in ("eks-x86-gvisor", "eks-x86-kata")))
claim("AgentCore default container has CAP_SYS_ADMIN, others do not", all(int(S[f"{b}/default"]["cap_eff"], 16) & (1 << 21) for b in ("ac-v1", "ac-v2")) and not any(int(S[f"{b}/default"]["cap_eff"], 16) & (1 << 21) for b in ("lm", "eks-x86-gvisor", "eks-x86-kata")))
claim("Only EKS mounts a service account token", S["eks-x86-gvisor/default"]["k8s_sa_token_mounted"] and not S["ac-v2/default"]["k8s_sa_token_mounted"])
claim("gVisor has no io_uring", S["eks-x86-gvisor/default"]["io_uring_setup"]["errno"] == "ENOSYS")
NP = {k: S[f"{k}/np-enforced"] for k in ("eks-x86-gvisor-warm", "eks-x86-kata-warm")}
claim("With network policy on, warm pool sandboxes cannot reach each other or the Kubernetes API", all(v["peer_sandbox_tcp"] != "open" and v["k8s_api_tcp"] != "open" for v in NP.values()))
claim("With network policy on, the managed policy keeps the internet open", all(v["egress_internet_https"] == "open" for v in NP.values()))
claim("With network policy on, the managed policy also blocks Pod Identity, so credentials fail", all(v["extra"]["pod_identity_169_254_170_23"] != "open" for v in NP.values()) and len(F["np_creds"]) == 2 and all("fail" in x for x in F["np_creds"]))
claim("A Sandbox created without a template gets no policy", S["eks-x86-gvisor/np-enabled-no-policy"]["peer_sandbox_tcp"] == "open")

# Added by the fairness audit
A, CS = F["fair"]["agent"], F["fair"]["concurrent_scaled"]
claim("V1 with the documented /ping is gone by 90 s", F["idle.v1np"]["90"]["alive"] == 0 and F["idle.v1np"]["60"]["alive"] == F["idle.v1np"]["60"]["n"])
claim("V1 is two-peaked at low rate: p90 over 5x p50", F["cold.v1np.p90"] > 5 * F["cold.v1np.p50"])
claim("V1 container is above 7 s from 1 per second", F["sus.v1np.1.p50"] > 7 and F["sus.v1np.5.p50"] > 7)
claim("V1 direct code and V2 stay under 4 s at 5 per second", F["sus.v1zip.5.p50"] < 4 and F["sus.v2.5.p50"] < 4 and F["sus.v2zip.5.p50"] < 4)
claim("VPC mode: V1 above 7 s, V2 under 2.5 s", F["cold.v1vpc.p50"] > 7 and F["cold.v2vpc.p50"] < 2.5)
claim("Burst 100: V2 beats gVisor, V1 and Kata with enough capacity", F["burst.v2.100.p50"] < min(F["burst.gv.100.p50"], F["burst.v1.100.p50"], F["burst.kt.100.p50"]))
claim("Burst 10: V1 and gVisor are under 2 s", F["burst.v1.10.p50"] < 2 and F["burst.gv.10.p50"] < 2)
claim("Bursts removed for the MicroVM quota are not reported", "burst.lm.50.p50" not in F and "burst.lm.100.p50" not in F and "sus.lm.10.p50" not in F)
claim("Final EKS bursts ran 3 rounds", all(F[f"burst.{k}.{n}.runs"] == 3 for k in ("gv", "kt") for n in ("10", "50", "100")))
claim("New V2 runtimes: first message is slow in over a third of runs, with no failures", A["ac-v2|crossed"]["slow_share"] > 0.33 and A["ac-v2|crossed"]["failed"] == 0)
claim("New MicroVM images are faster to first message than new V2 runtimes", A["lm|crossed"]["first_p50"] < A["ac-v2|crossed"]["first_p50"])
claim("Load does not lower V2 whole request (CIs overlap)", A["ac-v2|load"]["total_ci"][0] < A["ac-v2|noload"]["total_ci"][1] and A["ac-v2|noload"]["total_ci"][0] < A["ac-v2|load"]["total_ci"][1])
claim("V2 whole request falls with run order", A["ac-v2|run1_4"]["total_p50"] > A["ac-v2|run5_8"]["total_p50"] > A["ac-v2|run9_12"]["total_p50"])
D = F["fair"]["diag"]["ac-v2-diag"]
claim("Slow V2 runs show the same logs and about the same faults as fast ones", D["slow"]["log_lines"] == D["fast"]["log_lines"] and abs(D["slow"]["majflt"] - D["fast"]["majflt"]) < 0.1 * D["fast"]["majflt"])
SA, SR = F["fair"]["same"]["agent"], F["fair"]["same"]["agent_by_round"]
claim("Same period: every option has 20 of 20 runs", all(SA[k]["n"] == 20 and SA[k]["failed"] == 0 for k in ("gv", "g3gv", "kt", "v1", "v2", "lm")))
claim("Same period: gVisor and V1 intervals overlap, so they are not ranked", SA["gv"]["total_ci"][0] < SA["v1"]["total_ci"][1] and SA["v1"]["total_ci"][0] < SA["gv"]["total_ci"][1])
claim("Same period: gVisor and V1 beat Kata, in both rounds", all(SR[f"{k}|{r}"]["total_p50"] < SR[f"kt|{r}"]["total_p50"] for k in ("gv", "v1") for r in ("same1", "same2")))
claim("Same period: V2 has the slowest whole request in both rounds", all(SR[f"v2|{r}"]["total_p50"] > max(SR[f"{k}|{r}"]["total_p50"] for k in ("gv", "g3gv", "kt", "v1", "lm")) for r in ("same1", "same2")))
claim("Same period: only V2 and MicroVM have runs over 20 s to first message", SA["v2"]["slow_share"] > 0 and SA["lm"]["slow_share"] > 0 and all(SA[k]["slow_share"] == 0 for k in ("gv", "g3gv", "kt", "v1")))
QA = lambda k: A[f"{k}|quiet2"]
claim("Quiet hour: V2 is slow in most runs, MicroVM in few, none failed", QA("ac-v2-q2")["slow_share"] > .5 and QA("lm-q2")["slow_share"] < .2 and QA("ac-v2-q2")["failed"] == 0 and QA("lm-q2")["failed"] == 0)
claim("Quiet hour: V2 first message falls by the last run", F["fair"]["quiet_order"]["ac-v2-q2"][-1] < 5 < F["fair"]["quiet_order"]["ac-v2-q2"][0])
claim("Quiet hour: holding the CLI in memory leaves no run over 20 s", QA("ac-v2-pinq2")["slow_share"] == 0 and QA("lm-pinq2")["slow_share"] == 0)
claim("MicroVM whole-request intervals with and without CLI file mapping overlap", QA("lm-pinq2")["total_ci"][1] > QA("lm-q2")["total_ci"][0])
claim("Run order does not explain everything: long-used ac-v2 still has a slow first message", A["ac-v2|consecutive"]["first_p50"] > 20)
claim("Dropped page cache: first CLI read stays under 2 s on EKS", all(v < 2 for v in F["fair"]["drop_touch"].values()))
CS = F["fair"]["concurrent_scaled"]
claim("Concurrent rerun: V2 and MicroVM have no failed runs", all(CS[f"{b}|{n}"]["failed"] == 0 for b in ("ac-v2-np", "lm") for n in (5, 20)))
claim("Holding the CLI in memory removes runs over 20 s on V2", A["ac-v2-pin|pin"]["slow_share"] == 0)
claim("Startup warm-up leaves slow runs on V2", A["ac-v2-warm|pkg"]["slow_share"] > 0.2)
claim("EKS warm pods with the task run first reach first message under 1 s", A["eks-x86-gvisor-warm-init|init"]["first_p50"] < 1 and A["eks-x86-kata-warm-init|init"]["first_p50"] < 1)
claim("With enough nodes, gVisor at 20 concurrent agents stays within 20 percent of 5", CS["eks-x86-gvisor|20"]["total_p50"] < 1.2 * CS["eks-x86-gvisor|5"]["total_p50"])
claim("With enough nodes, Kata at 20 concurrent agents stays within 20 percent of 5", CS["eks-x86-kata|20"]["total_p50"] < 1.2 * CS["eks-x86-kata|5"]["total_p50"])
claim("No failed agent in any scaled concurrent batch", all(v["failed"] == 0 for v in CS.values()))
claim("Build task: nested Kata is slower than gVisor x86, V1 and MicroVM", A["eks-x86-kata|heavy"]["total_ci"][0] > max(A["eks-x86-gvisor|heavy"]["total_p50"], A["ac-v1-np|heavy"]["total_p50"], A["lm-fa|heavy"]["total_p50"]))
claim("Build task: metal Kata beats nested Kata", A["eks-metal-kata|heavy"]["total_p50"] < A["eks-x86-kata|heavy"]["total_p50"])
claim("Cost formulas reproduce the AWS examples within 1 percent", abs(F["cost"]["aws_example_check"]["agentcore_v2_support_monthly_1m"] / 6703 - 1) < .01 and abs(F["cost"]["aws_example_check"]["microvm_ci_monthly_10k"] / 1124.03 - 1) < .01)
c = F["cost"]["scenarios"]
claim("Steady scenario: gVisor is cheaper than V1 and V2, MicroVM is highest", c["steady"]["eks_gvisor_autoscaled"] < min(c["steady"]["agentcore_v1"], c["steady"]["agentcore_v2"]) < max(c["steady"]["agentcore_v1"], c["steady"]["agentcore_v2"]) < c["steady"]["microvm_always_running"])
claim("MicroVM is the highest in every scenario at the tested size", all(v["microvm_tested_size"] == max(v["microvm_tested_size"], v["agentcore_v1"], v["agentcore_v2"], v["eks_gvisor_autoscaled"], v["eks_kata_autoscaled"]) for v in c.values()))
A5 = "agent_task_then_5min_idle"
claim("With the documented /ping, V2 bills less memory than V1 in every session shape", all(F[f"usage.{k}.v2np.gbh"] < F[f"usage.{k}.v1np.gbh"] for k in (A5, "idle_only_5min", "idle_only_30min")))
# Definitions and the mitigation table
claim("First message comes before the first model stream event in every agent run", F["fair"]["first_before_stream"]["min"] > 0)
C8 = F["fair"]["crossed_first8"]
claim("The first 8 crossed runs are slower on V2 than the pooled 12", C8["ac-v2"]["first_p50"] > F["fair"]["agent"]["ac-v2|crossed"]["first_p50"])
Q = F["fair"]["agent"]
claim("V2 mapping: no run over 20 s after a quiet hour, 5 of 8 without", Q["ac-v2-pinq2|quiet2"]["slow_share"] == 0 and round(Q["ac-v2-q2|quiet2"]["slow_share"] * 8) == 5)
claim("MicroVM mapping: first message p50 intervals overlap after a quiet hour", Q["lm-pinq2|quiet2"]["first_ci"][1] >= Q["lm-q2|quiet2"]["first_ci"][0])
PR = F["fair"]["prewarm_rounds"]
claim("Running the CLI before the snapshot is faster than none in each shuffled round", all(PR[f"{t}|{r}"]["prewarm"] < PR[f"{t}|{r}"]["plain"] for t in ("ac-v2", "lm") for r in ("r1", "r2", "r3")))

print(f"\n{checked - len(fails)}/{checked} claims hold")
raise SystemExit(1 if fails else 0)
