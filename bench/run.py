"""Experiment runner. Usage: python run.py <experiment> --backends a,b --n 30 --round r1"""
import argparse, json, random, statistics, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import backends as B
from backends import now
from common import emit

_retry_throttle = (B.Throttled,)


def _b(args, dep):
    return [B.make(x, dep) for x in args.backends.split(",")]


def _err(e):
    return {"ok": False, "error": type(e).__name__, "detail": str(e)[:400]}


# Isolation and CPU generation hardly show in a task that mostly waits for the model, so a second task does real build work.
HEAVY_TASK = """Create a small Python package in the current directory.
1. Write `calc.py` with functions add, sub, mul, div. div must raise ZeroDivisionError for a zero divisor.
2. Write `test_calc.py` with pytest tests covering all four functions and the zero divisor case.
3. Run `python -m pytest -q test_calc.py` with the Bash tool and fix anything that fails.
4. Run this with the Bash tool: `mkdir b && tar xzf /opt/corpus/stdlib.tar.gz -C b && python -m compileall -q b`
5. Run this with the Bash tool: `git init -q r && cp -r b/stdlib r/ && git -C r add -A && git -C r -c user.email=a@b.c -c user.name=a commit -qm x && git -C r log --oneline | wc -l`
6. Run this with the Bash tool: `rm -rf b r && python -m pytest -q test_calc.py`
When all of these succeed, reply with the single word DONE."""


def _agent_once(b, rec, model, task=None):
    """One new sandbox, one agent task. Fills rec and always cleans up."""
    h = None
    t = now()
    try:
        for attempt in range(200):
            try:
                h = b.create()
                b.wait_usable(h)
                break
            except B.Throttled:
                rec["throttles"] = rec.get("throttles", 0) + 1
                time.sleep(random.uniform(0.2, 1.0))
        rec["cold_s"] = now() - t
        t = now()
        body = {"op": "agent", "model": model}
        if task == "heavy":
            body["prompt"] = HEAVY_TASK
        d = b.call(h, body)
        rec.update(ok="error" not in d, agent_wall_s=now() - t, result=d.get("result"), detail=d.get("error"))
    except Exception as e:
        rec.update(_err(e))
    if h is not None:
        _safe(b.destroy, h)
    return rec


# Agent runs separated by a fixed gap: the runtime's recent use is controlled separately from load on it.
def agent_spaced(args, dep):
    for b in _b(args, dep):
        for i in range(args.n):
            emit("agent_e2e", _agent_once(b, {"backend": b.name, "i": i, "gap_s": args.gap, "task": args.task}, args.model, args.task), args.round)
            time.sleep(args.gap)


# Host memory and load during a concurrent batch on one EKS node: the input the cost model otherwise has to assume.
def _node_load(b, size, rep, rnd, stop):
    group = {"eks-x86-gvisor": "x86-gvisor", "eks-x86-gvisor-warm-agent": "x86-gvisor", "eks-x86-kata": "x86-kata", "eks-x86-kata-warm-agent": "x86-kata"}.get(b.name)
    if not group:
        return
    from ops_experiments import host, nodes_of
    node = nodes_of(group)[0].metadata.name
    read = lambda: host(node, "grep MemAvailable /proc/meminfo; cat /proc/loadavg")
    parse = lambda o: (int(o.split()[1]), float(o.split()[3]))
    before = parse(read())
    low, load = before[0], before[1]
    while not stop.wait(3):
        try:
            m, l = parse(read())
        except Exception:
            continue
        low, load = min(low, m), max(load, l)
    emit("agent_concurrent_node", {"backend": b.name, "concurrent": size, "rep": rep, "avail_before_kb": before[0], "avail_min_kb": low, "load1_max": load, "per_sandbox_gb": (before[0] - low) / 1048576 / size}, rnd)


# Agents that run at the same moment, on a node or on a managed fleet.
def agent_concurrent(args, dep):
    for b in _b(args, dep):
        for size in [int(x) for x in args.sizes.split(",")]:
            for rep in range(args.n):
                if isinstance(b, B.EksWarm):
                    b.wait_pool(size)
                stop = threading.Event()
                sampler = threading.Thread(target=_node_load, args=(b, size, rep, args.round, stop))
                sampler.start()
                with ThreadPoolExecutor(size) as ex:
                    fs = [ex.submit(_agent_once, b, {"backend": b.name, "concurrent": size, "rep": rep, "i": i}, args.model) for i in range(size)]
                    for f in fs:
                        emit("agent_concurrent", f.result(), args.round)
                stop.set()
                sampler.join()
                time.sleep(args.settle)


# E1: cold start. Backends are interleaved so that no backend owns a time of day.
def cold_start(args, dep):
    bs = _b(args, dep)
    for b in bs:
        if isinstance(b, B.EksWarm):
            b.wait_pool(int(args.pool or 1))
    for i in range(args.n):
        order = bs[:]
        random.shuffle(order)
        for b in order:
            rec = {"backend": b.name, "i": i}
            h = None
            try:
                h = b.create()
                d = b.wait_usable(h)
                rec.update(ok=True, cold_s=h.marks["first_ok"], marks=h.marks, in_sandbox_uptime=d.get("now", 0) - d.get("process_start", 0))
                t = now()
                b.call(h, {"op": "echo"})
                rec["second_call_s"] = now() - t
            except Exception as e:
                rec.update(_err(e))
            if h is not None:
                t = now()
                try:
                    b.destroy(h)
                    rec["destroy_api_s"] = now() - t
                    if isinstance(b, B.EksCold) and not isinstance(b, B.EksWarm):
                        rec["pod_gone_s"] = b.wait_gone(h)
                except Exception as e:
                    rec["destroy_error"] = str(e)[:200]
            emit("cold_start", rec, args.round)
            if isinstance(b, B.EksWarm):
                t = now()
                b.wait_pool(int(args.pool or 1))
                emit("warm_replenish", {"backend": b.name, "i": i, "seconds": now() - t}, args.round)
        time.sleep(random.uniform(1, 3))


# E2: request latency on an open sandbox.
def warm_latency(args, dep):
    def one(b):
        h = b.create()
        b.wait_usable(h)
        for i in range(args.n):
            t = now()
            try:
                b.call(h, {"op": "echo"})
                emit("warm_latency", {"backend": b.name, "i": i, "ok": True, "seconds": now() - t}, args.round)
            except Exception as e:
                emit("warm_latency", {"backend": b.name, "i": i, **_err(e)}, args.round)
        b.destroy(h)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(one, _b(args, dep)))


# E3: identical workloads in each sandbox. 3 fresh sandboxes, each op repeated.
SUITE = [("cpu_python", 5), ("cpu_sha256", 5), ("cpu_parallel", 5), ("syscalls", 5), ("files_small", 5), ("disk_seq", 3), ("mem_touch", 5), ("compile_stdlib", 3), ("pytest_project", 5), ("claude_cli_start", 3)]
NET = [("tls_connect", 3), ("git_clone", 3), ("pip_install", 3)]


def _suite(b, ops, exp, args, extra=None):
    for s in range(args.sandboxes):
        h = None
        try:
            h = b.create()
            b.wait_usable(h)
            info = b.call(h, {"op": "sysinfo"})
            emit("sysinfo", {"backend": b.name, "sandbox": s, "result": info.get("result")}, args.round)
            for op, reps in ops:
                for r in range(reps):
                    t = now()
                    try:
                        d = b.call(h, {"op": op, **(extra or {}).get(op, {})})
                        ok = "error" not in d
                        emit(exp, {"backend": b.name, "sandbox": s, "op": op, "rep": r, "ok": ok, "wall_s": now() - t, "result": d.get("result"), "detail": d.get("error")}, args.round)
                    except Exception as e:
                        emit(exp, {"backend": b.name, "sandbox": s, "op": op, "rep": r, **_err(e)}, args.round)
        except Exception as e:
            emit(exp, {"backend": b.name, "sandbox": s, "op": "_sandbox", **_err(e)}, args.round)
        finally:
            if h is not None:
                try:
                    b.destroy(h)
                except Exception:
                    pass


def bench_suite(args, dep):
    with ThreadPoolExecutor(10) as ex:
        list(ex.map(lambda b: _suite(b, SUITE, "bench_suite", args), _b(args, dep)))


def net_suite(args, dep):
    """Sequential: all backends share one NAT gateway on the EKS side."""
    import boto3
    url = boto3.client("s3").generate_presigned_url("get_object", Params={"Bucket": dep["bucket"], "Key": "bench/256mb.bin"}, ExpiresIn=43200)
    bs = _b(args, dep)
    for b in bs:
        _suite(b, NET + [("net_download", 3)], "net_suite", args, {"net_download": {"url": url}})


# E4: the real thing, one coding task through the Claude Agent SDK from a cold sandbox.
def agent_e2e(args, dep):
    bs = _b(args, dep)
    for i in range(args.n):
        order = bs[:]
        random.shuffle(order)
        for b in order:
            rec = {"backend": b.name, "i": i}
            h = None
            try:
                t = now()
                h = b.create()
                b.wait_usable(h)
                rec["cold_s"] = now() - t
                t = now()
                d = b.call(h, {"op": "agent", "model": args.model})
                rec.update(ok="error" not in d, agent_wall_s=now() - t, result=d.get("result"), detail=d.get("error"))
            except Exception as e:
                rec.update(_err(e))
            if h is not None:
                try:
                    b.destroy(h)
                except Exception:
                    pass
            emit("agent_e2e", rec, args.round)


# E5: simultaneous sandboxes. A throttled create is retried and counted: it is what a real client would do.
def burst(args, dep):
    sizes = [int(x) for x in args.sizes.split(",")]
    for b in _b(args, dep):
        for size in sizes:
            hs, lock = [], threading.Lock()
            start = threading.Barrier(size)
            if isinstance(b, B.Microvm):
                b.poll = max(0.05, size / 80)  # stay under the GetMicrovm quota; adds up to this much timing error
            if isinstance(b, B.EksCold):
                b.poll = max(0.05, size / 200)  # the driver must not become the load on the API server

            def one(i):
                start.wait()
                t = now()
                throttles = 0
                while True:
                    try:
                        h = b.create()
                        h.t0 = t
                        break
                    except B.Throttled:
                        throttles += 1
                        time.sleep(random.uniform(0.2, 1.0))
                while True:
                    try:
                        b.wait_usable(h)
                        break
                    except B.Throttled:
                        throttles += 1
                        time.sleep(random.uniform(0.2, 1.0))
                with lock:
                    hs.append(h)
                return {"s": now() - t, "throttles": throttles}

            t0 = now()
            res = []
            with ThreadPoolExecutor(size) as ex:
                for f in as_completed([ex.submit(one, i) for i in range(size)]):
                    try:
                        res.append({"ok": True, **f.result()})
                    except Exception as e:
                        res.append(_err(e))
            emit("burst", {"backend": b.name, "size": size, "wall_s": now() - t0, "results": res}, args.round)
            with ThreadPoolExecutor(16) as ex:
                list(ex.map(lambda h: _safe(b.destroy, h), hs))
            time.sleep(args.settle)


def _safe(f, *a):
    try:
        return f(*a)
    except Exception as e:
        return e


# E6a: when does an idle session really disappear? Each probe uses its own session so that probing cannot reset the timer.
def idle_reclaim(args, dep):
    waits = [int(x) for x in args.waits.split(",")]

    def one(b, w, rep):
        h = b.create()
        d = b.wait_usable(h)
        b.call(h, {"op": "state_set", "key": "m", "value": "1"})
        time.sleep(w)
        rec = {"backend": b.name, "wait_s": w, "rep": rep}
        try:
            d2 = b.call(h, {"op": "state_get", "key": "m"})
            rec.update(ok=True, same_instance=d2["instance"] == d["instance"], memory=d2.get("memory"), disk=d2.get("disk"))
        except Exception as e:
            rec.update(_err(e))
        emit("idle_reclaim", rec, args.round)
        _safe(b.destroy, h)

    with ThreadPoolExecutor(64) as ex:
        fs = [ex.submit(one, b, w, r) for b in _b(args, dep) for w in waits for r in range(args.n)]
        for f in fs:
            f.result()


# E6b: explicit stop, then the same session id.
def state_wipe(args, dep):
    for b in _b(args, dep):
        for i in range(args.n):
            h = b.create()
            d = b.wait_usable(h)
            b.call(h, {"op": "state_set", "key": "m", "value": "1"})
            b.destroy(h)
            time.sleep(5)
            rec = {"backend": b.name, "i": i}
            try:
                d2 = b.call(h, {"op": "state_get", "key": "m"})
                rec.update(ok=True, same_instance=d2["instance"] == d["instance"], memory=d2.get("memory"), disk=d2.get("disk"))
                b.destroy(h)
            except Exception as e:
                rec.update(_err(e))
            emit("state_wipe", rec, args.round)


# E6c: Lambda MicroVMs suspend/resume with and without a large memory state.
def suspend_resume(args, dep):
    b = B.make(args.backends, dep)
    for mb in [int(x) for x in args.sizes.split(",")]:
        for i in range(args.n):
            rec = {"backend": b.name, "ballast_mb": mb, "i": i}
            h = None
            try:
                h = b.create()
                b.wait_usable(h)
                if mb:
                    b.call(h, {"op": "alloc", "mb": mb})
                b.call(h, {"op": "state_set", "key": "m", "value": "42"})
                inst = b.call(h, {"op": "echo"})["instance"]
                t = now()
                b.c.suspend_microvm(microvmIdentifier=h.id)
                rec["suspend_s"] = b.wait_state(h, "SUSPENDED") + (now() - t) * 0
                rec["suspend_total_s"] = now() - t
                t = now()
                mode = "api" if i % 2 == 0 else "traffic"
                rec["mode"] = mode
                if mode == "api":
                    b.c.resume_microvm(microvmIdentifier=h.id)
                while True:
                    try:
                        d = b.call(h, {"op": "state_get", "key": "m"}, timeout=30)
                        break
                    except Exception:
                        if now() - t > 300:
                            raise
                        time.sleep(0.02)
                rec.update(ok=True, resume_s=now() - t, memory=d.get("memory"), disk=d.get("disk"), same_instance=d["instance"] == inst)
            except Exception as e:
                rec.update(_err(e))
            if h:
                _safe(b.destroy, h)
            emit("suspend_resume", rec, args.round)
            time.sleep(0.5)


# E6d: idle policy: how long until SUSPENDED, then TERMINATED, without any API call that could disturb it.
def microvm_idle_policy(args, dep):
    b = B.Microvm(args.backends, dep["backends"][args.backends]["image"], dep["microvm_exec_role"], idle={"autoResumeEnabled": True, "maxIdleDurationSeconds": 60, "suspendedDurationSeconds": 120})

    def one(i):
        h = b.create()
        b.wait_usable(h)
        t = now()
        susp = b.wait_state(h, "SUSPENDED", deadline=900, poll=1)
        t2 = now()
        term = b.wait_state(h, "TERMINATED", deadline=900, poll=1)
        emit("microvm_idle_policy", {"backend": b.name, "i": i, "to_suspended_s": susp, "suspended_to_terminated_s": term, "configured": b.idle}, args.round)

    with ThreadPoolExecutor(args.n) as ex:
        list(ex.map(one, range(args.n)))


# E12: a single request that outlives a 15 minute idle timeout.
def long_request(args, dep):
    def one(b):
        h = b.create()
        b.wait_usable(h)
        t = now()
        import os
        mode = args.long_op + ("_keepalive" if os.environ.get("TCP_KEEPALIVE") else "")
        rec = {"backend": b.name, "requested_s": args.seconds, "mode": mode}
        try:
            d = b.call(h, {"op": args.long_op, "seconds": args.seconds})
            rec.update(ok=True, wall_s=now() - t, instance=d.get("instance"), process_start=d.get("process_start"))
        except Exception as e:
            rec.update(_err(e), wall_s=now() - t)
        emit("long_request", rec, args.round)
        _safe(b.destroy, h)
    with ThreadPoolExecutor(10) as ex:
        list(ex.map(one, _b(args, dep)))


# E7: real AgentCore billing inputs for a controlled session: allocate, compute, free, idle.
def usage_sessions(args, dep):
    def one(b, i):
        h = b.create()
        b.wait_usable(h)
        b.call(h, {"op": "alloc", "mb": args.alloc_mb})
        b.call(h, {"op": "cpu_for", "seconds": args.cpu_s})
        b.call(h, {"op": "free"})
        time.sleep(args.idle_s)
        # A pooled connection can go stale over a long idle wait. The usage log does not depend on this last call.
        try:
            last = b.call(h, {"op": "echo"})
        except Exception:
            last = {}
        _safe(b.destroy, h)
        emit("usage_sessions", {"backend": b.name, "i": i, "session": getattr(h, "sid", getattr(h, "id", None)), "alloc_mb": args.alloc_mb, "cpu_s": args.cpu_s, "idle_s": args.idle_s, "instance": last.get("instance")}, args.round)
    with ThreadPoolExecutor(32) as ex:
        fs = [ex.submit(one, b, i) for b in _b(args, dep) for i in range(args.n)]
        for f in fs:
            f.result()


# E7b: billing inputs for one real Claude Agent SDK task followed by idle time.
def usage_agent(args, dep):
    def one(b, i):
        h = b.create()
        b.wait_usable(h)
        d = b.call(h, {"op": "agent", "model": args.model})
        time.sleep(args.idle_s)
        b.call(h, {"op": "echo"})
        b.destroy(h)
        emit("usage_sessions", {"backend": b.name, "i": i, "session": h.sid, "alloc_mb": -1, "cpu_s": 0, "idle_s": args.idle_s, "agent_ok": "error" not in d}, args.round)
    with ThreadPoolExecutor(16) as ex:
        fs = [ex.submit(one, b, i) for b in _b(args, dep) for i in range(args.n)]
        for f in fs:
            f.result()


# E9: what a workload can reach by default. Peer IP comes from a second sandbox of the same backend.
def security(args, dep):
    for b in _b(args, dep):
        h = b.create()
        b.wait_usable(h)
        peer = None
        h2 = None
        if isinstance(b, B.EksCold):
            h2 = b.create()
            b.wait_usable(h2)
            peer = h2.ip
        d = b.call(h, {"op": "probe", "peer_ip": peer})
        emit("security", {"backend": b.name, "label": args.label, "result": d.get("result"), "detail": d.get("error")}, args.round)
        b.destroy(h)
        if h2:
            b.destroy(h2)


# E13: first versus repeat agent start in one sandbox. Separates page-in after restore from model latency.
def agent_first_vs_repeat(args, dep):
    bs = _b(args, dep)
    for i in range(args.n):
        for b in random.sample(bs, len(bs)):
            h = None
            try:
                h = b.create()
                b.wait_usable(h)
                for rep in range(3):
                    t = now()
                    d = b.call(h, {"op": "agent", "model": args.model, "prompt": "Reply with the single word OK.", "max_turns": 1})
                    emit("agent_first_vs_repeat", {"backend": b.name, "i": i, "rep": rep, "ok": "error" not in d, "wall_s": now() - t, "result": d.get("result"), "detail": d.get("error")}, args.round)
            except Exception as e:
                emit("agent_first_vs_repeat", {"backend": b.name, "i": i, **_err(e)}, args.round)
            if h is not None:
                _safe(b.destroy, h)


# E5c: open-loop arrivals. New sandboxes arrive at a fixed rate regardless of how fast earlier ones started.
def sustained(args, dep):
    for b in _b(args, dep):
        for rate in [float(x) for x in args.sizes.split(",")]:
            total = int(rate * args.seconds)
            if isinstance(b, B.Microvm):
                b.poll = max(0.05, rate * 5 / 80)
            if isinstance(b, B.EksCold):
                b.poll = max(0.05, rate * 6 / 200)
            lock, res = threading.Lock(), []

            def one(i):
                t = now()
                rec = {"backend": b.name, "rate": rate, "i": i}
                h = None
                try:
                    for attempt in range(200):
                        try:
                            h = b.create()
                            h.t0 = t
                            d = b.wait_usable(h)
                            break
                        except B.Throttled:
                            rec["throttles"] = rec.get("throttles", 0) + 1
                            time.sleep(random.uniform(0.2, 1.0))
                    rec.update(ok=True, cold_s=now() - t, preexisting=d.get("now", 0) - d.get("process_start", 0) > 30)
                except Exception as e:
                    rec.update(_err(e))
                if h is not None:
                    _safe(b.destroy, h)
                emit("sustained", rec, args.round)

            with ThreadPoolExecutor(int(rate * 120) + 8) as ex:
                start = now()
                fs = []
                for i in range(total):
                    wait = start + i / rate - now()
                    if wait > 0:
                        time.sleep(wait)
                    fs.append(ex.submit(one, i))
                for f in fs:
                    f.result()
            time.sleep(args.settle)


# E15: which CPU does a session land on? Each session is new, so this samples the fleet.
def hw_census(args, dep):
    def one(b, i):
        h = None
        try:
            h = b.create()
            b.wait_usable(h)
            r = b.call(h, {"op": "sysinfo"})["result"]
            c = b.call(h, {"op": "cpu_python"})["result"]["seconds"]
            s = b.call(h, {"op": "cpu_sha256"})["result"]["seconds"]
            emit("hw_census", {"backend": b.name, "i": i, "cpu": r["cpu_models"], "kernel": r["uname"]["release"], "cpu_python_s": c, "cpu_sha256_s": s, "mem": r["mem"]["MemTotal"], "nproc": r["nproc_online"]}, args.round)
        except Exception as e:
            emit("hw_census", {"backend": b.name, "i": i, **_err(e)}, args.round)
        if h is not None:
            _safe(b.destroy, h)
    for b in _b(args, dep):
        with ThreadPoolExecutor(4) as ex:
            list(ex.map(lambda i: one(b, i), range(args.n)))


# E16: can one session reach another over the network? Uses IPs the sessions report themselves.
def cross_session(args, dep):
    for b in _b(args, dep):
        for i in range(args.n):
            a, c = None, None
            try:
                a = b.create(); b.wait_usable(a)
                c = b.create(); b.wait_usable(c)
                ips = b.call(c, {"op": "netinfo"})["result"]
                res = {ip: b.call(a, {"op": "probe", "peer_ip": ip})["result"]["peer_sandbox_tcp"] for ip in ips["candidate_ips"]}
                emit("cross_session", {"backend": b.name, "i": i, "peer_ips": ips, "result": res}, args.round)
            except Exception as e:
                emit("cross_session", {"backend": b.name, "i": i, **_err(e)}, args.round)
            for h in (a, c):
                if h is not None:
                    _safe(b.destroy, h)


# E14: first-touch cost in fresh sandboxes.
def first_touch(args, dep):
    bs = _b(args, dep)
    for i in range(args.n):
        for b in random.sample(bs, len(bs)):
            h = None
            try:
                h = b.create()
                b.wait_usable(h)
                d = b.call(h, {"op": "first_touch"})
                emit("first_touch", {"backend": b.name, "i": i, "ok": "error" not in d, "result": d.get("result"), "detail": d.get("error")}, args.round)
            except Exception as e:
                emit("first_touch", {"backend": b.name, "i": i, **_err(e)}, args.round)
            if h is not None:
                _safe(b.destroy, h)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("exp")
    p.add_argument("--backends", default="")
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--round", default="r1")
    p.add_argument("--sandboxes", type=int, default=3)
    p.add_argument("--sizes", default="10,50,100")
    p.add_argument("--settle", type=float, default=60)
    p.add_argument("--waits", default="30,50,60,70,80,90,120")
    p.add_argument("--pool", default="")
    p.add_argument("--seconds", type=int, default=1200)
    p.add_argument("--gap", type=float, default=150)
    p.add_argument("--task", default="")
    p.add_argument("--model", default="us.anthropic.claude-opus-5-5")
    p.add_argument("--alloc-mb", type=int, default=1024)
    p.add_argument("--cpu-s", type=float, default=30)
    p.add_argument("--idle-s", type=float, default=300)
    p.add_argument("--label", default="default")
    p.add_argument("--long-op", default="sleep")
    a = p.parse_args()
    dep = B.load_registry()
    globals()[a.exp](a, dep)
    print("DONE", a.exp, a.round, flush=True)


if __name__ == "__main__":
    main()
