#!/usr/bin/env python3
"""Single source of truth. Reads results/raw/*.jsonl, writes results/summary.json.
README tables come from that file. Failures stay in the counts."""
import json, math, random, statistics as st, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "results" / "raw"
random.seed(7)


def load(name):
    out = []
    for p in sorted(RAW.glob(f"{name}.jsonl")):
        for l in p.open():
            l = l.strip()
            if l:
                out.append(json.loads(l))
    return out


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def ci(xs, q=0.5, n=1000):
    if len(xs) < 5:
        return (None, None)
    b = sorted(pct(random.choices(xs, k=len(xs)), q) for _ in range(n))
    return (b[int(n * 0.025)], b[int(n * 0.975)])


def dist(xs, fails=0):
    if not xs:
        return {"n": 0, "failed": fails}
    lo, hi = ci(xs)
    return {"n": len(xs), "failed": fails, "min": min(xs), "p50": pct(xs, .5), "p50_ci95": [lo, hi], "p90": pct(xs, .9), "p95": pct(xs, .95), "p99": pct(xs, .99), "max": max(xs), "mean": st.mean(xs), "stdev": st.pstdev(xs)}


def by(rs, *keys):
    d = defaultdict(list)
    for r in rs:
        d[tuple(r.get(k) for k in keys)].append(r)
    return d


def cold():
    rs = [r for r in load("cold_start") if r.get("round") not in ("nplow", "metalwarmup", "same1")]
    out = {}
    for (b,), g in by(rs, "backend").items():
        ok = [r["cold_s"] for r in g if r.get("ok")]
        byround = {}
        for (rd,), gg in by(g, "round").items():
            xs = [r["cold_s"] for r in gg if r.get("ok")]
            byround[rd] = {"n": len(xs), "p50": pct(xs, .5), "p90": pct(xs, .9)}
        destroy = [r["pod_gone_s"] for r in g if r.get("pod_gone_s")]
        uptimes = [r.get("in_sandbox_uptime") for r in g if r.get("ok")]
        out[b] = {**dist(ok, sum(1 for r in g if not r.get("ok"))), "by_round": byround, "pod_gone_p50": pct(destroy, .5), "errors": sorted({r.get("error", "") + ":" + str(r.get("detail", ""))[:120] for r in g if not r.get("ok")})[:5], "preexisting_process_share": sum(1 for u in uptimes if u and u > 30) / max(1, len(uptimes)), "second_call_p50": pct([r["second_call_s"] for r in g if r.get("second_call_s")], .5)}
    return out


def simple(name, field="seconds"):
    rs = load(name)
    return {b: dist([r[field] for r in g if r.get("ok", True) and field in r], sum(1 for r in g if r.get("ok") is False)) for (b,), g in by(rs, "backend").items()}


def suite():
    rs = load("bench_suite") + load("net_suite")
    out = defaultdict(dict)
    for (b, op), g in by(rs, "backend", "op").items():
        if op == "_sandbox":
            out[b]["_sandbox_errors"] = [r.get("detail") for r in g]
            continue
        good = [r for r in g if r.get("ok") and r.get("result")]
        fails = len(g) - len(good)
        res = {"n": len(good), "failed": fails}
        if good:
            for k, v in good[0]["result"].items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    res[k] = pct([r["result"][k] for r in good if k in r["result"]], .5)
            if op == "claude_cli_start":
                firsts = [r["result"]["all"][0] for r in good if r["rep"] == 0]
                res["first_run_p50"] = pct(firsts, .5)
                res["first_run_max"] = max(firsts) if firsts else None
        if fails:
            res["errors"] = sorted({str(r.get("detail") or r.get("error"))[:160] for r in g if not r.get("ok")})[:3]
        out[b][op] = res
    return dict(out)


def cpu_of(r):
    parts = [x for x in (r or {}).get("cpu_models", []) if x.startswith("0x") or "Xeon" in x]
    return parts[0] if parts else "unknown"


CPU_NAMES = {"0xd0c": "Graviton2", "0xd40": "Graviton3", "0xd4f": "Graviton4"}


def suite_by_cpu():
    """Managed fleets mix CPU generations, so a median across sessions compares fleets, not sandboxes."""
    cpu = {}
    for r in load("sysinfo"):
        cpu[(r["backend"], r["round"], r["sandbox"])] = cpu_of(r.get("result"))
    out = defaultdict(lambda: defaultdict(dict))
    groups = defaultdict(list)
    for r in load("bench_suite"):
        if r.get("ok") and r.get("result"):
            groups[(r["backend"], cpu.get((r["backend"], r["round"], r["sandbox"]), "unknown"), r["op"])].append(r)
    for (b, c, op), g in groups.items():
        res = {"n": len(g), "sandboxes": len({(r["round"], r["sandbox"]) for r in g})}
        for k, v in g[0]["result"].items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                res[k] = pct([r["result"][k] for r in g if k in r["result"]], .5)
        out[b][CPU_NAMES.get(c, c)][op] = res
    return {b: dict(v) for b, v in out.items()}


def census():
    out = defaultdict(lambda: defaultdict(list))
    for r in load("hw_census"):
        if r.get("cpu"):
            out[r["backend"]][CPU_NAMES.get(cpu_of({"cpu_models": r["cpu"]}), "unknown")].append(r)
    return {b: {c: {"n": len(g), "cpu_python_p50": pct([x["cpu_python_s"] for x in g], .5), "cpu_sha256_p50": pct([x["cpu_sha256_s"] for x in g], .5), "kernel": g[0]["kernel"], "nproc": g[0]["nproc"], "mem": g[0]["mem"]} for c, g in d.items()} for b, d in out.items()}


def first_touch():
    out = defaultdict(lambda: defaultdict(list))
    for r in load("first_touch"):
        if str(r.get("round")).startswith("traffic"):
            continue
        for k, v in (r.get("result") or {}).items():
            out[r["backend"]][k].append(v["s"])
    return {b: {k: {"n": len(v), "p50": pct(v, .5), "max": max(v)} for k, v in d.items()} for b, d in out.items()}


def first_touch_traffic():
    out = defaultdict(lambda: defaultdict(list))
    for r in load("first_touch"):
        if (r["backend"] == "ac-v1-probe" and r.get("round") == "traffic") or r.get("round") in ("traffic2", "traffic3"):
            for k, v in (r.get("result") or {}).items():
                out[r["backend"]][k].append(v["s"])
    return {b: {k: {"n": len(v), "p50": pct(v, .5)} for k, v in d.items()} for b, d in out.items()}


def usage():
    """Real AgentCore billing inputs from USAGE_LOGS, priced at the public rates in cost_model.py."""
    rate = {"ac-v1": (0.0895, 0.00945), "ac-v2": (0.1276, 0.0169), "ac-v1-np": (0.0895, 0.00945), "ac-v2-np": (0.1276, 0.0169)}
    out = defaultdict(lambda: defaultdict(list))
    for r in load("usage_logs"):
        kind = {-1: "agent_task_then_5min_idle", 0: "idle_only_5min"}.get(r["alloc_mb"], "alloc1gb_30s_cpu_5min_idle")
        if r.get("idle_s") == 1800:
            kind = "idle_only_30min"
        out[kind][r["backend"]].append(r)
    res = {}
    for kind, d in out.items():
        for b, g in d.items():
            c, m = rate[b]
            cost = [x["vcpu_hours"] * c + x["gb_hours"] * m for x in g]
            res.setdefault(kind, {})[b] = {"cost_min": min(cost), "cost_max": max(cost), "n": len(g), "seconds_p50": pct([x["seconds_logged"] for x in g], .5), "gb_hours_p50": pct([x["gb_hours"] for x in g], .5), "vcpu_hours_p50": pct([x["vcpu_hours"] for x in g], .5), "peak_gb_p50": pct([x["peak_gb"] for x in g if x["peak_gb"]], .5), "last60_gb_p50": pct([x["last60_gb"] for x in g], .5), "cost_usd_p50": pct(cost, .5)}
    return res


def sysinfo():
    out = {}
    for (b,), g in by(load("sysinfo"), "backend").items():
        r = g[-1]["result"] or {}
        out[b] = {k: r.get(k) for k in ("python", "nproc_online", "cgroup_cpu_max", "cgroup_mem_max", "mem", "cpu_models", "disk_total_GB", "clocksource", "user")}
        out[b]["kernel"] = r.get("uname", {}).get("release")
        out[b]["machine"] = r.get("uname", {}).get("machine")
    return out


FAIR_ROUNDS = ("laterdec", "later", "consecutive", "pin", "fa", "fb", "fc", "fd", "np", "pkg", "diag", "quiet", "quiet2", "same1", "same2", "np2", "heavy", "vpc", "init", "metal", "metalwarmup")


def _good(r):
    return r.get("ok") and r.get("result") and not r["result"].get("is_error") and r["result"].get("verify_pytest_rc") == 0


def _ci(xs, n=4000, seed=7):
    """Bootstrap 95% interval of the median."""
    import random
    if len(xs) < 3:
        return None
    rnd = random.Random(seed)
    m = sorted(pct(rnd.choices(xs, k=len(xs)), .5) for _ in range(n))
    return [m[int(n * .025)], m[int(n * .975)]]


def _agent_stats(g):
    """Failed runs are counted apart. A slow run that succeeded is a real wait for the user and stays in."""
    g = sorted(g, key=lambda r: r.get("ts", 0))
    ok = [r for r in g if _good(r)]
    first = [r["result"]["first_message"] for r in ok]
    total = [r["cold_s"] + r["agent_wall_s"] for r in ok]
    return {"n": len(ok), "tried": len(g), "failed": len(g) - len(ok), "first_p50": pct(first, .5), "first_p90": pct(first, .9), "first_max": max(first) if first else None,
            "slow_share": sum(x >= 20 for x in first) / len(first) if first else None, "total_p50": pct(total, .5), "total_p90": pct(total, .9), "total_ci": _ci(total), "first_ci": _ci(first),
            "cold_p50": pct([r["cold_s"] for r in ok], .5), "wall_p50": pct([r["agent_wall_s"] for r in ok], .5), "in_order_first": first}


def fair_followups():
    """Rounds added by the fairness audit. Each answers one question and stays out of the main tables."""
    e2e = load("agent_e2e")
    rs = [r for r in e2e if r.get("round") in FAIR_ROUNDS]
    out = {f"{b}|{rd}": _agent_stats(g) for (b, rd), g in by(rs, "backend", "round").items()}
    # Pooled: the four crossed cells are new runtimes with the base image, so together they are the fair "new runtime" number.
    for k in ("ac-v2", "lm"):
        g = [r for r in rs if r["backend"] in (f"{k}-fa", f"{k}-fb", f"{k}-fc", f"{k}-fd") and r.get("round") in ("fa", "fb", "fc", "fd")]
        out[f"{k}|crossed"] = _agent_stats(g)
        ordered = []
        for c in ("fa", "fb", "fc", "fd"):
            ordered.append(sorted([r for r in g if r["backend"] == f"{k}-{c}" and _good(r)], key=lambda r: r["ts"]))
        for name, slice_ in (("run1_4", slice(0, 4)), ("run5_8", slice(4, 8)), ("run9_12", slice(8, 12))):
            part = [r for o in ordered for r in o[slice_]]
            out[f"{k}|{name}"] = _agent_stats(part)
        out[f"{k}|load"] = _agent_stats([r for r in g if r["round"] in ("fc", "fd")])
        out[f"{k}|noload"] = _agent_stats([r for r in g if r["round"] in ("fa", "fb")])
        out[f"{k}|longgap"] = _agent_stats([r for r in g if r["round"] in ("fa", "fc")])
        out[f"{k}|shortgap"] = _agent_stats([r for r in g if r["round"] in ("fb", "fd")])
    conc, conc4 = {}, {}
    for (b, size, rd), g in by(load("agent_concurrent"), "backend", "concurrent", "round").items():
        st = _agent_stats(g)
        st.pop("in_order_first")
        st["api_ms_p50"] = pct([r["result"]["duration_api_ms"] for r in g if r.get("result")], .5)
        (conc4 if rd == "conc4" else conc)[f"{b}|{size}"] = st
    node = {}
    for (b, size), g in by([r for r in load("agent_concurrent_node") if r.get("round") == "conc"], "backend", "concurrent").items():
        node[f"{b}|{size}"] = {"gb_per_sandbox": pct([r["per_sandbox_gb"] for r in g], .5), "load1_max": max(r["load1_max"] for r in g)}
    drop = {b: _agent_stats(g) for (b,), g in by(load("agent_dropcache"), "backend").items()}
    diag = {}
    for b in ("ac-v2-diag", "lm-diag"):
        g = [r for r in rs if r["backend"] == b and r.get("round") == "diag" and _good(r)]
        if not g:
            continue
        mid = lambda part, f: pct([f(r["result"]["diag"]) for r in part], .5) if part else None
        slow = [r for r in g if r["result"]["first_message"] >= 20]
        fast = [r for r in g if r["result"]["first_message"] < 8]
        diag[b] = {"n": len(g), "slow_n": len(slow), "fast_n": len(fast)}
        for name, part in (("slow", slow), ("fast", fast)):
            diag[b][name] = {"majflt": mid(part, lambda d: d["child_major_faults"]), "block_in": mid(part, lambda d: d["child_block_in"]), "user_s": mid(part, lambda d: d["child_user_s"]), "log_lines": mid(part, lambda d: d["log_lines"]), "suspect": mid(part, lambda d: len(d["suspect"]))}
        diag[b]["slow_cpus"] = sorted({r["result"]["diag"]["cpu_part"] for r in slow})
        diag[b]["fast_cpus"] = sorted({r["result"]["diag"]["cpu_part"] for r in fast})
    ci = {}
    for key, b, keep in (("gv", "eks-x86-gvisor", ("r1", "r2", "r3")), ("g3gv", "eks-g3-gvisor", ("r1", "r2", "r3")), ("kt", "eks-x86-kata", ("r1", "r2", "r3")), ("v1", "ac-v1", ("r1", "r2", "r3"))):
        ci[key] = _agent_stats([r for r in e2e if r["backend"] == b and r.get("round") in keep])
        ci[key].pop("in_order_first")
    # Cluster bootstrap for the crossed cells: runs on one runtime are not independent, so resample runtimes first.
    import random as _r
    for k in ("ac-v2", "lm"):
        cells = [[r["cold_s"] + r["agent_wall_s"] for r in rs if r["backend"] == f"{k}-{c}" and r.get("round") == c and _good(r)] for c in ("fa", "fb", "fc", "fd")]
        rnd = _r.Random(7)
        ms = []
        for _ in range(4000):
            xs = []
            for cell in rnd.choices(cells, k=len(cells)):
                xs += rnd.choices(cell, k=len(cell))
            ms.append(sorted(xs)[len(xs) // 2])
        ms.sort()
        out[f"{k}|crossed"]["total_ci_cluster"] = [ms[100], ms[3899]]
    # Same period, shuffled, one arrival pattern for every option.
    same = {"agent": {}, "agent_by_round": {}, "cold": {}}
    names = {"ac-v1-s1": "v1", "ac-v1-s2": "v1", "ac-v2-s1": "v2", "ac-v2-s2": "v2", "lm-s1": "lm", "lm-s2": "lm", "eks-x86-gvisor": "gv", "eks-g3-gvisor": "g3gv", "eks-x86-kata": "kt"}
    sr = [r for r in e2e if r.get("round") in ("same1", "same2") and r["backend"] in names]
    for k in sorted(set(names.values())):
        g = [r for r in sr if names[r["backend"]] == k]
        if g:
            same["agent"][k] = _agent_stats(g)
            same["agent"][k].pop("in_order_first")
            for rd in ("same1", "same2"):
                gg = [r for r in g if r["round"] == rd]
                if gg:
                    same["agent_by_round"][f"{k}|{rd}"] = _agent_stats(gg)
    gap = {}
    for r in load("cold_start"):
        if r.get("round") == "same1" and r["backend"] in names:
            gap.setdefault(names[r["backend"]], []).append(r)
    for k, g in gap.items():
        xs = [r["cold_s"] for r in g if r.get("ok")]
        ts = sorted(r["ts"] for r in g)
        same["cold"][k] = {"n": len(xs), "tried": len(g), "p50": pct(xs, .5), "p90": pct(xs, .9), "ci": _ci(xs), "fast_share": sum(x < 3 for x in xs) / len(xs) if xs else None, "arrival_s": pct([b - a for a, b in zip(ts, ts[1:])], .5) if len(ts) > 1 else None}
    # Model time, per backend and round, so that "about the same" can be checked.
    mt = [pct([r["result"]["duration_api_ms"] for r in g if _good(r)], .5) / 1000 for (b, rd), g in by([r for r in e2e if not r.get("task")], "backend", "round").items() if any(_good(r) for r in g)]
    pw = sorted([r for r in e2e if r["backend"] == "ac-v2-prewarm" and _good(r)], key=lambda r: r["ts"])[:10]
    out["ac-v2-prewarm|first10"] = _agent_stats(pw)
    pw = sorted([r for r in e2e if r["backend"] == "lm-prewarm" and _good(r)], key=lambda r: r["ts"])[:10]
    out["lm-prewarm|first10"] = _agent_stats(pw)
    # Round "nplow" is not reported: its ac-v1-np calls ran while the sustained test was using up the same runtime's ready environments.
    quiet_order = {}
    for r in sorted((r for r in load("agent_e2e") if r.get("round") == "quiet2" and r.get("ok")), key=lambda r: r["ts"]):
        quiet_order.setdefault(r["backend"], []).append(r["result"]["first_message"])
    drop_touch = {b: pct([r["result"]["read_cli_binary_first"]["s"] for r in g], .5) for (b,), g in by(load("first_touch_dropcache"), "backend").items()}
    # Baseline for the mitigation table on the same footing as an 8-run row: the first 8 runs of each crossed runtime.
    first8 = {}
    for tag in ("ac-v2", "lm"):
        g8 = []
        for x in ("fa", "fb", "fc", "fd"):
            g8 += sorted([r for r in e2e if r.get("backend") == f"{tag}-{x}" and r.get("round") == x], key=lambda r: r["ts"])[:8]
        first8[tag] = _agent_stats(g8)
    # Run the CLI before the snapshot against no mitigation, in the same shuffled rounds.
    pre = {}
    for tag in ("ac-v2", "lm"):
        for rd in ("r1", "r2", "r3"):
            a = [r["result"]["first_message"] for r in e2e if r.get("backend") == tag and r.get("round") == rd and _good(r)]
            b = [r["result"]["first_message"] for r in e2e if r.get("backend") == f"{tag}-prewarm" and r.get("round") == rd and _good(r)]
            pre[f"{tag}|{rd}"] = {"plain": pct(a, .5), "prewarm": pct(b, .5)}
    # First message must precede the first model stream event for the README's definition to hold.
    before = [r["result"]["first_stream_event"] - r["result"]["first_message"] for r in e2e if _good(r) and r["result"].get("first_stream_event")]
    return {"crossed_first8": first8, "prewarm_rounds": pre, "first_before_stream": {"n": len(before), "min": min(before)}, "quiet_order": quiet_order, "drop_touch": drop_touch, "agent": out, "concurrent": conc, "concurrent_scaled": conc4, "node": node, "dropcache": drop, "diag": diag, "low_rate": ci, "same": same, "model_time_range": [min(mt), max(mt)]}


def agent():
    # Follow-up rounds answer a different question and stay out of the main table.
    # ac-v2-probe in round "traffic" ran with no load on it (sustained ran V1 first), so only "traffic2" counts for it.
    rs = [r for r in load("agent_e2e") if r.get("round") not in FAIR_ROUNDS and not (r["backend"] == "ac-v2-probe" and r.get("round") in ("traffic", "idleafter", "idle45")) and not (r["backend"] == "ac-v2" and r.get("round") == "control")]
    for r in rs:
        if r.get("round") == "traffic4":
            r["backend"] += "-traffic"
    out = {}
    cold_by = {}
    for (b,), g in by(rs, "backend").items():
        cold_by[b] = pct([r["cold_s"] for r in g if r.get("cold_s")], .5)
    for (b,), g in by(rs, "backend").items():
        good = [r for r in g if r.get("ok") and r.get("result") and not r["result"].get("is_error") and r["result"].get("verify_pytest_rc") == 0]
        f = lambda fn: [fn(r) for r in good]
        out[b] = {
            "n": len(good), "attempted": len(g), "cold_p50": cold_by.get(b),
            "wall": dist(f(lambda r: r["agent_wall_s"])),
            "first_message": dist(f(lambda r: r["result"]["first_message"])),
            "first_stream_event": dist(f(lambda r: r["result"]["first_stream_event"])),
            "sdk_duration_ms_p50": pct(f(lambda r: r["result"]["duration_ms"]), .5),
            "api_ms_p50": pct(f(lambda r: r["result"]["duration_api_ms"]), .5),
            "cold_plus_wall_p50": pct(f(lambda r: r["cold_s"] + r["agent_wall_s"]), .5),
            "cost_p50": pct(f(lambda r: r["result"]["total_cost_usd"]), .5),
            "errors": sorted({str(r.get("detail") or r.get("error") or (r.get("result") or {}).get("verify_pytest_rc"))[:120] for r in g if r not in good})[:3],
        }
    def checks(b, rd):
        g = [r for r in load("agent_e2e") if r["backend"] == b and r.get("round") == rd and r.get("result")]
        return {"n": len(g), "first_p50": pct([r["result"]["first_message"] for r in g], .5), "first": sorted(r["result"]["first_message"] for r in g), "wall_p50": pct([r["agent_wall_s"] for r in g], .5)}
    out["_v2_after_idle"] = checks("ac-v2-probe", "idleafter")
    out["_v2_after_idle45"] = checks("ac-v2-probe", "idle45")
    out["_v2_control"] = checks("ac-v2", "control")
    rep = load("agent_first_vs_repeat")
    repeat = {}
    for (b, k), g in by(rep, "backend", "rep").items():
        xs = [r["result"]["first_message"] for r in g if r.get("result")]
        repeat.setdefault(b, {})[f"run{k}"] = {"n": len(xs), "first_message_p50": pct(xs, .5), "p90": pct(xs, .9), "max": max(xs) if xs else None}
    return {"e2e": out, "first_vs_repeat": repeat}


def burst():
    out = {}
    for r in load("burst"):
        ok = [x["s"] for x in r["results"] if x.get("ok")]
        out.setdefault(r["backend"], {}).setdefault(str(r["size"]), []).append({"round": r.get("round"), "wall_s": r["wall_s"], "ok": len(ok), "failed": len(r["results"]) - len(ok), "p50": pct(ok, .5), "p95": pct(ok, .95), "max": max(ok) if ok else None, "throttles": sum(x.get("throttles", 0) for x in r["results"]), "errors": sorted({x.get("error", "") for x in r["results"] if not x.get("ok")})[:3]})
    return out


def lifecycle():
    idle = defaultdict(lambda: defaultdict(list))
    for r in load("idle_reclaim"):
        idle[r["backend"]][r["wait_s"]].append({"alive": r.get("same_instance"), "memory": r.get("memory"), "disk": r.get("disk"), "ok": r.get("ok"), "error": r.get("error")})
    susp = defaultdict(list)
    for r in load("suspend_resume"):
        susp[(r["ballast_mb"], r.get("mode"))].append(r)
    out_s = {}
    for (mb, mode), g in susp.items():
        ok = [r for r in g if r.get("ok")]
        out_s[f"{mb}MB/{mode}"] = {"n": len(ok), "failed": len(g) - len(ok), "suspend_p50": pct([r["suspend_total_s"] for r in ok], .5), "resume_p50": pct([r["resume_s"] for r in ok], .5), "resume_p90": pct([r["resume_s"] for r in ok], .9), "memory_kept": sum(1 for r in ok if r.get("memory") == "42"), "disk_kept": sum(1 for r in ok if r.get("disk") == "42"), "same_instance": sum(1 for r in ok if r.get("same_instance")), "errors": sorted({str(r.get("detail"))[:120] for r in g if not r.get("ok")})[:2]}
    return {
        "idle_reclaim": {b: {str(w): {"n": len(v), "alive": sum(1 for x in v if x["alive"]), "errors": sum(1 for x in v if not x["ok"])} for w, v in sorted(d.items())} for b, d in idle.items()},
        "state_wipe": {b: {"n": len(g), "same_instance": sum(1 for r in g if r.get("same_instance")), "memory_survived": sum(1 for r in g if r.get("memory")), "disk_survived": sum(1 for r in g if r.get("disk"))} for (b,), g in by(load("state_wipe"), "backend").items()},
        "suspend_resume": out_s,
        "microvm_idle_policy": dist([r["to_suspended_s"] for r in load("microvm_idle_policy")]) | {"suspended_to_terminated": dist([r["suspended_to_terminated_s"] for r in load("microvm_idle_policy")])},
        "long_request": [{k: r.get(k) for k in ("backend", "round", "mode", "ok", "wall_s", "requested_s", "error", "detail")} for r in load("long_request")],
        "deploy_time": {b: {"seconds": [r["seconds"] for r in g], "status": g[-1].get("status")} for (b,), g in by(load("deploy_time"), "backend").items()},
        "node_scale": {b: dist([r["node_ready_s"] for r in g]) | {"node_to_sandbox": dist([r["node_to_sandbox_total_s"] for r in g if r.get("node_to_sandbox_total_s")]), "removed": dist([r["node_removed_s"] for r in g if r.get("node_removed_s")])} for (b,), g in by(load("node_scale"), "backend").items()},
    }


def sustained():
    out = {}
    for (b, rate), g in by(load("sustained"), "backend", "rate").items():
        ok = [r["cold_s"] for r in g if r.get("ok")]
        out.setdefault(b, {})[str(rate)] = {**dist(ok, sum(1 for r in g if not r.get("ok"))), "preexisting_share": sum(1 for r in g if r.get("preexisting")) / max(1, len(ok)), "throttles": sum(r.get("throttles", 0) for r in g), "errors": sorted({str(r.get("error")) + ":" + str(r.get("detail"))[:100] for r in g if not r.get("ok")})[:3]}
    return out


def fresh():
    out = {}
    for (p, img, i), g in by(load("fresh_runtime"), "platform", "image", "i").items():
        out[f"{p}/{img}/call{i}"] = dist([r["cold_s"] for r in g]) | {"uptime_p50": pct([r["uptime"] for r in g], .5)}
    return out


def density():
    out = defaultdict(list)
    for r in load("density"):
        out[r["backend"]].append({k: r.get(k) for k in ("sandboxes", "used_delta_mb_per_sandbox", "mem_avail_kb", "round")})
    return dict(out)


def main():
    s = {
        "cold_start": cold(),
        # cold_uncached is excluded on purpose: warm pool pods kept the image on the node, so most runs were cached.
        # True first-pull data comes from new-node runs (node_scale, kata_scale) and the first run of each large image.
        "warm_latency": simple("warm_latency"),
        "warm_replenish": simple("warm_replenish"),
        "suite": suite(),
        "suite_by_cpu": suite_by_cpu(),
        "hw_census": census(),
        "first_touch": first_touch(),
        "first_touch_traffic": first_touch_traffic(),
        "fair": fair_followups(),
        "usage": usage(),
        "kata_scale": load("kata_scale"),
        "cross_session": [{k: r.get(k) for k in ("backend", "i", "peer_ips", "result")} for r in load("cross_session")],
        "sysinfo": sysinfo(),
        "agent": agent(),
        "burst": burst(),
        "sustained": sustained(),
        "fresh_runtime": fresh(),
        "lifecycle": lifecycle(),
        "density": density(),
        "security": {r["backend"] + "/" + r.get("label", ""): r["result"] for r in load("security") if r.get("result")},
        "observability": (load("observability") or [{}])[-1].get("result"),
        "observability_checks": load("observability_checks"),
    }
    (ROOT / "results" / "summary.json").write_text(json.dumps(s, indent=1, default=str))
    return s


if __name__ == "__main__":
    s = main()
    for b, d in sorted(s["cold_start"].items(), key=lambda x: x[1].get("p50") or 9e9):
        if d["n"]:
            print(f"{b:24s} n={d['n']:4d} fail={d['failed']} p50={d['p50']:.2f} p90={d['p90']:.2f} max={d['max']:.2f} pre-existing-process={d['preexisting_process_share']:.2f}")
