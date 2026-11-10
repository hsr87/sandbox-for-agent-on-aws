"""Follow-up driver. python xrun.py deploy <spec.json> | agent ... Runs next to the benchmark code and keeps its own results."""
import argparse, concurrent.futures as cf, json, os, random, sys, threading, time, uuid
os.environ.setdefault("RESULTS", "/work/x/results")
os.environ.setdefault("DEPLOYMENT", "/work/x/deployment.json")
sys.path.insert(0, "/work/bench")
import boto3
import backends as B
from backends import now
from common import emit

REGION = os.environ.get("AWS_REGION", "us-east-1")
TF = json.load(open(os.environ.get("TF_OUTPUT", "/work/tf.json")))
LOCK = threading.Lock()
DEP = os.environ["DEPLOYMENT"]


def dep_load():
    return json.load(open(DEP)) if os.path.exists(DEP) else {"backends": {}, "bucket": TF["bucket"], "microvm_exec_role": TF["microvm_exec_role"]}


def dep_put(k, v):
    with LOCK:
        d = dep_load()
        d["backends"][k] = v
        tmp = DEP + ".tmp"
        json.dump(d, open(tmp, "w"), indent=1)
        os.replace(tmp, DEP)


def deploy_one(s):
    k = s["name"]
    if k in dep_load()["backends"]:
        return
    t = time.perf_counter()
    if s["kind"] == "agentcore":
        ctl = boto3.client("bedrock-agentcore-control", region_name=REGION)
        kw = dict(agentRuntimeName="sbxx_" + k.replace("-", "_"), roleArn=TF["agentcore_exec_role"], agentRuntimeArtifact={"containerConfiguration": {"containerUri": f"{TF['ecr']}:{s['tag']}"}}, networkConfiguration=s.get("network") or {"networkMode": "PUBLIC"}, protocolConfiguration={"serverProtocol": "HTTP"}, platformVersion=s["ver"], tags={"project": "sandbox-bench"})
        if s.get("storage"):
            kw["filesystemConfigurations"] = [{"sessionStorage": {"mountPath": "/mnt/workspace"}}]
        for a in range(30):
            try:
                r = ctl.create_agent_runtime(**kw)
                break
            except Exception as e:
                if "Throttl" not in str(e) and "TooMany" not in str(e):
                    raise
                time.sleep(10)
        rid = r["agentRuntimeId"]
        while True:
            try:
                g = ctl.get_agent_runtime(agentRuntimeId=rid)
            except Exception:
                time.sleep(5)
                continue
            if g["status"] in ("READY", "CREATE_FAILED"):
                break
            time.sleep(5)
        emit("x_deploy", {"backend": k, "spec": s, "seconds": time.perf_counter() - t, "status": g["status"], "reason": g.get("failureReason")}, s.get("round"))
        print(k, g["status"], round(time.perf_counter() - t), g.get("failureReason"), flush=True)
        if g["status"] == "READY":
            dep_put(k, {"kind": "agentcore", "arn": r["agentRuntimeArn"], "id": rid, "platform": s["ver"], "image": s["tag"]})
    elif s["kind"] == "microvm":
        import io, zipfile
        mv = boto3.client("lambda-microvms", region_name=REGION)
        s3 = boto3.client("s3", region_name=REGION)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("Dockerfile", f"FROM {TF['ecr']}:{s['tag']}\n")
        key = f"microvm/x-{k}.zip"
        s3.put_object(Bucket=TF["bucket"], Key=key, Body=buf.getvalue())
        arn = mv.create_microvm_image(name="sbxx-" + k, baseImageArn=f"arn:aws:lambda:{REGION}:aws:microvm-image:al2023-1", buildRoleArn=TF["microvm_build_role"], codeArtifact={"uri": f"s3://{TF['bucket']}/{key}"}, resources=[{"minimumMemoryInMiB": 4096}], tags={"project": "sandbox-bench"})["imageArn"]
        while True:
            g = mv.get_microvm_image(imageIdentifier=arn)
            if g["state"] in ("CREATED", "CREATE_FAILED"):
                break
            time.sleep(10)
        emit("x_deploy", {"backend": k, "spec": s, "seconds": (g["updatedAt"] - g["createdAt"]).total_seconds(), "status": g["state"], "reason": g.get("stateReason")}, s.get("round"))
        print(k, g["state"], g.get("stateReason"), flush=True)
        if g["state"] == "CREATED":
            dep_put(k, {"kind": "microvm", "image": arn, "tag": s["tag"]})
    elif s["kind"] == "eks_cold":
        dep_put(k, {"kind": "eks_cold", "image": f"{TF['ecr']}:{s['tag']}", "group": s["group"], "runtime_class": s.get("runtime_class"), "size": s.get("size")})
    elif s["kind"] == "eks_fargate":
        dep_put(k, {"kind": "eks_fargate", "image": f"{TF['ecr']}:{s['tag']}", "cpu": s["cpu"], "memory": s["memory"]})


def cmd_deploy(a):
    specs = json.load(open(a.spec))
    with cf.ThreadPoolExecutor(a.par) as ex:
        for f in cf.as_completed([ex.submit(deploy_one, s) for s in specs]):
            f.result()
    print("DEPLOYED", flush=True)


def once(b, rec, body, sid=None):
    h = None
    t = now()
    try:
        for attempt in range(200):
            try:
                h = b.create()
                if sid:
                    h.sid = sid
                b.wait_usable(h)
                break
            except B.Throttled:
                rec["throttles"] = rec.get("throttles", 0) + 1
                time.sleep(random.uniform(0.2, 1.0))
        rec["cold_s"] = now() - t
        t = now()
        d = b.call(h, body)
        rec.update(ok="error" not in d, wall_s=now() - t, result=d.get("result"), detail=d.get("error"))
    except Exception as e:
        rec.update(ok=False, error=type(e).__name__, detail=str(e)[:400])
    if h is not None:
        try:
            b.destroy(h)
        except Exception as e:
            rec["destroy_error"] = str(e)[:200]
    return rec


def cmd_agent(a):
    """Spaced runs on each backend, in parallel across backends. items: name=op-json."""
    d = B.load_registry(DEP)
    items = json.load(open(a.items))

    def loop(it):
        b = B.make(it["backend"], d)
        for i in range(a.n):
            rec = {"backend": it["backend"], "arm": it.get("arm"), "i": i, **{k: v for k, v in it.items() if k in ("sdk", "mb", "platform")}}
            emit(a.exp, once(b, rec, it["body"]), a.round)
            time.sleep(a.gap)
    time.sleep(random.uniform(0, 1))
    with cf.ThreadPoolExecutor(len(items)) as ex:
        for f in [ex.submit(loop, it) for it in items]:
            f.result()
    print("AGENT DONE", a.round, flush=True)


def cmd_warm(a):
    """Warming ticks plus probes on each arm. arm: backend, period_s (0 = none), k sessions per tick."""
    d = B.load_registry(DEP)
    items = json.load(open(a.items))
    stop = threading.Event()
    threads = []

    def tick(b, arm, tick_i, k):
        # A new client per call: with retries off, a connection reused after a long gap fails before reaching the service.
        b = B.make(b.name, d)
        rec = {"backend": b.name, "arm": arm, "tick": tick_i, "k": k}
        emit("x_warm_tick", once(b, rec, {"op": "x_warm_cli"}), a.round)

    def warmer(it):
        b = B.make(it["backend"], d)
        i = 0
        while not stop.is_set():
            ts = [threading.Thread(target=tick, args=(b, it["arm"], i, it["k"])) for _ in range(it["k"])]
            [t.start() for t in ts]
            i += 1
            stop.wait(it["period_s"])
            [t.join() for t in ts]

    for it in items:
        if it["period_s"]:
            t = threading.Thread(target=warmer, args=(it,), daemon=True)
            t.start()
            threads.append(t)
    time.sleep(a.lead)

    def probes(it):
        b = B.make(it["backend"], d)
        time.sleep(random.uniform(0, 240))
        for i in range(a.n):
            b = B.make(it["backend"], d)
            rec = {"backend": it["backend"], "arm": it["arm"], "i": i, "period_s": it["period_s"], "k": it["k"]}
            emit("x_warm_probe", once(b, rec, {"op": "x_claude", "model": a.model, **it.get("body", {})}), a.round)
            if i < a.n - 1:
                time.sleep(a.gap)
    with cf.ThreadPoolExecutor(len(items)) as ex:
        for f in [ex.submit(probes, it) for it in items]:
            f.result()
    stop.set()
    [t.join(timeout=300) for t in threads]
    print("WARM DONE", a.round, flush=True)


def cmd_store(a):
    """Session storage: fetch the CLI to a path, run the task. Then stop, resume with the same id, and run from the stored copy."""
    d = B.load_registry(DEP)
    bucket = dep_load()["bucket"]
    items = json.load(open(a.items))

    def loop(it):
        b = B.make(it["backend"], d)
        for i in range(a.n):
            rec = {"backend": it["backend"], "arm": it["arm"], "i": i}
            arm = it["arm"]
            if arm == "image":
                emit("x_store", once(b, rec, {"op": "x_claude", "model": a.model}), a.round)
            else:
                path = it["path"]
                body = {"op": "x_claude", "model": a.model, "cli_path": path, "s3": {"bucket": bucket, "key": a.key}}
                sid = "bench-" + uuid.uuid4().hex + uuid.uuid4().hex[:8]
                emit("x_store", once(b, {**rec, "phase": "fetch"}, body, sid=sid), a.round)
                if it.get("resume"):
                    time.sleep(a.pause)
                    r2 = {**rec, "phase": "resume", "pause_s": a.pause}
                    emit("x_store", once(b, r2, {"op": "x_claude", "model": a.model, "cli_path": path, "read_before": i % 2 == 1}, sid=sid), a.round)
            time.sleep(a.gap)
    with cf.ThreadPoolExecutor(len(items)) as ex:
        for f in [ex.submit(loop, it) for it in items]:
            f.result()
    print("STORE DONE", a.round, flush=True)


HEAVY = """Create a small Python package in the current directory.
1. Write `calc.py` with functions add, sub, mul, div. div must raise ZeroDivisionError for a zero divisor.
2. Write `test_calc.py` with pytest tests covering all four functions and the zero divisor case.
3. Run `python -m pytest -q test_calc.py` with the Bash tool and fix anything that fails.
4. Run this with the Bash tool: `mkdir b && tar xzf /opt/corpus/stdlib.tar.gz -C b && python -m compileall -q b`
5. Run this with the Bash tool: `git init -q r && cp -r b/stdlib r/ && git -C r add -A && git -C r -c user.email=a@b.c -c user.name=a commit -qm x && git -C r log --oneline | wc -l`
6. Run this with the Bash tool: `rm -rf b r && python -m pytest -q test_calc.py`
When all of these succeed, reply with the single word DONE."""


def cmd_mix(a):
    """Every backend once per cycle in a new random order, so that no backend owns a time of day."""
    d = B.load_registry(DEP)
    items = json.load(open(a.items))
    for i in range(a.n):
        order = items[:]
        random.shuffle(order)
        for it in order:
            b = B.make(it["backend"], d)
            body = {"op": "x_claude", "model": a.model}
            if a.task == "heavy":
                body["prompt"] = HEAVY
            emit(a.exp, once(b, {"backend": it["backend"], "arm": it.get("arm"), "i": i, "task": a.task}, body), a.round)
        time.sleep(a.gap)
    print("MIX DONE", a.round, flush=True)


def cmd_conc(a):
    """Agents started together. Sizes and backends in a new random order per repeat."""
    d = B.load_registry(DEP)
    items = json.load(open(a.items))
    sizes = [int(x) for x in a.sizes.split(",")]
    for rep in range(a.n):
        pairs = [(it, s) for it in items for s in sizes]
        random.shuffle(pairs)
        for it, size in pairs:
            b = B.make(it["backend"], d)
            with cf.ThreadPoolExecutor(size) as ex:
                fs = [ex.submit(once, B.make(it["backend"], d), {"backend": it["backend"], "arm": it.get("arm"), "size": size, "rep": rep, "n": j}, {"op": "x_claude", "model": a.model}) for j in range(size)]
                for f in fs:
                    emit(a.exp, f.result(), a.round)
            time.sleep(a.gap)
    print("CONC DONE", a.round, flush=True)


def cmd_iso(a):
    """First reads of a unique asset per group. Arms warm their own runtime, share its image, share its bytes, or stand alone."""
    d = B.load_registry(DEP)
    items = json.load(open(a.items))
    stop = threading.Event()
    threads = []

    def rec_of(it, **kw):
        return {"backend": it["backend"], "arm": it["arm"], "group": it.get("group"), **kw}

    def body(it):
        return {"op": "x_read_asset", "path": it["path"]}

    def tick(it, i):
        b = B.make(it["backend"], d)
        emit("x_iso_tick", once(b, rec_of(it, tick=i), body(it)), a.round)

    def warmer(it):
        i = 0
        while not stop.is_set():
            ts = [threading.Thread(target=tick, args=(it, i)) for _ in range(it["k"])]
            [t.start() for t in ts]
            i += 1
            stop.wait(it["period_s"])
            [t.join() for t in ts]

    for it in items:
        if it.get("period_s"):
            t = threading.Thread(target=warmer, args=(it,), daemon=True)
            t.start()
            threads.append(t)
    time.sleep(a.lead)

    def probes(it):
        time.sleep(random.uniform(0, 240))
        for i in range(a.n):
            if it.get("only_last") and i < a.n - 1:
                time.sleep(a.gap)
                continue
            b = B.make(it["backend"], d)
            emit("x_iso_probe", once(b, rec_of(it, i=i), body(it)), a.round)
            if i < a.n - 1:
                time.sleep(a.gap)
    with cf.ThreadPoolExecutor(len(items)) as ex:
        for f in [ex.submit(probes, it) for it in items]:
            f.result()
    stop.set()
    [t.join(timeout=300) for t in threads]
    print("ISO DONE", a.round, flush=True)


def cmd_cycle(a):
    """Fetch to the mount, stop, resume with the same session id on the stored file."""
    d = B.load_registry(DEP)
    bucket = dep_load()["bucket"]
    for i in range(a.n):
        b = B.make(a.backend, d)
        sid = "bench-" + uuid.uuid4().hex + uuid.uuid4().hex[:8]
        emit("x_cycle", once(b, {"backend": a.backend, "i": i, "phase": "fetch"}, {"op": "x_store_cycle", "phase": "fetch", "path": a.path, "s3": {"bucket": bucket, "key": a.key}}, sid=sid), a.round)
        time.sleep(a.pause)
        b = B.make(a.backend, d)
        emit("x_cycle", once(b, {"backend": a.backend, "i": i, "phase": "resume", "pause_s": a.pause}, {"op": "x_store_cycle", "phase": "resume", "path": a.path}, sid=sid), a.round)
        time.sleep(a.gap)
    print("CYCLE DONE", a.round, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd")
    p.add_argument("--spec")
    p.add_argument("--items")
    p.add_argument("--par", type=int, default=4)
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--gap", type=float, default=150)
    p.add_argument("--lead", type=float, default=1200)
    p.add_argument("--pause", type=float, default=30)
    p.add_argument("--round", default="x")
    p.add_argument("--exp", default="x_agent")
    p.add_argument("--key", default="x1/claude-arm64")
    p.add_argument("--backend")
    p.add_argument("--task", default="")
    p.add_argument("--sizes", default="5,20")
    p.add_argument("--path", default="/mnt/workspace/asset.bin")
    p.add_argument("--model", default=os.environ.get("MODEL", "us.anthropic.claude-opus-5-5"))
    a = p.parse_args()
    globals()["cmd_" + a.cmd](a)
