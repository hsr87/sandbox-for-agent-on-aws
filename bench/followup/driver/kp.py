"""Karpenter on the gVisor path: from zero nodes, scale-down, and a real arrival trace."""
import argparse, concurrent.futures as cf, math, os, random, statistics, sys, threading, time, uuid
os.environ.setdefault("RESULTS", "/work/x/results")
sys.path.insert(0, "/work/bench")
import backends as B
from backends import now, NS
from common import emit
GROUP = "kp-gvisor"


class Pod(B.EksCold):
    """Same sandbox object, optionally marked so that Karpenter does not move it."""
    def __init__(self, image, keep=False):
        super().__init__("kp", image, GROUP, "gvisor")
        self.keep = keep

    def create(self):
        n = "k-" + uuid.uuid4().hex[:12]
        t0 = now()
        meta = {"labels": {"bench": "kp"}}
        if self.keep:
            meta["annotations"] = {"karpenter.sh/do-not-disrupt": "true"}
        body = {"apiVersion": "agents.x-k8s.io/v1beta1", "kind": "Sandbox", "metadata": {"name": n, "labels": {"bench": "kp"}}, "spec": {"podTemplate": {"metadata": meta, "spec": B.pod_spec(self.image, self.group, self.rc)}}}
        self.co.create_namespaced_custom_object("agents.x-k8s.io", "v1beta1", NS, "sandboxes", body)
        h = B.Handle(n=n, t0=t0, ip=None)
        h.marks["api_return"] = now() - t0
        return h


def nodes(core):
    return core.list_node(label_selector=f"bench/group={GROUP}").items


def ready(n):
    return any(c.type == "Ready" and c.status == "True" for c in n.status.conditions or [])


def wait_zero(core, deadline=1500):
    t = now()
    while nodes(core):
        if now() - t > deadline:
            raise TimeoutError("kp nodes still present")
        time.sleep(3)
    return now() - t


def one_start(b):
    h = b.create()
    b.wait_usable(h)
    return h


def cmd_scale(a):
    b = Pod(a.image)
    b.poll = 0.25
    core = b.core
    for rep in range(a.n):
        for size in [int(x) for x in a.sizes.split(",")]:
            wait_zero(core)
            time.sleep(20)
            t0 = now()
            first_seen = {}
            stop = threading.Event()

            def watch():
                while not stop.is_set():
                    for n in nodes(core):
                        if ready(n) and n.metadata.name not in first_seen:
                            first_seen[n.metadata.name] = now() - t0
                    time.sleep(0.5)
            threading.Thread(target=watch, daemon=True).start()
            with cf.ThreadPoolExecutor(size) as ex:
                hs = list(ex.map(lambda _: _try(b), range(size)))
            stop.set()
            ok = [h for h in hs if h and "first_ok" in h.marks]
            lat = sorted(h.marks["first_ok"] for h in ok)
            rec = {"rep": rep, "size": size, "ok": len(ok), "p50": statistics.median(lat) if lat else None, "max": lat[-1] if lat else None, "lat": [round(x, 2) for x in lat], "node_ready_s": sorted(first_seen.values()), "wall_s": now() - t0}
            for h in hs:
                if h:
                    try:
                        b.destroy(h)
                    except Exception:
                        pass
            t = now()
            rec["gone_s"] = wait_zero(core)
            emit("x_kp_scale", rec, a.round)
            print(rec, flush=True)


def _try(b):
    try:
        return one_start(b)
    except Exception as e:
        print("start failed", e, flush=True)
        return None


def cmd_trace(a):
    b = Pod(a.image, keep=a.keep)
    b.poll = 0.5
    core = b.core
    wait_zero(core)
    T = a.minutes * 60
    conc = lambda t: 10 + 95 * math.sin(math.pi * t / T) ** 4
    stop = threading.Event()
    live = [0]
    lk = threading.Lock()

    def sampler():
        t0 = now()
        while not stop.is_set():
            ns = nodes(core)
            pods = core.list_namespaced_pod(NS, label_selector="bench=kp").items
            emit("x_kp_nodes", {"t": now() - t0, "nodes": len(ns), "ready": sum(ready(n) for n in ns), "pods": len(pods), "pending": sum(p.status.phase == "Pending" for p in pods), "live": live[0], "target": conc(now() - t0), "keep": a.keep}, a.round)
            stop.wait(10)
    threading.Thread(target=sampler, daemon=True).start()

    def session(i, at):
        rec = {"i": i, "at": at, "keep": a.keep}
        h = None
        with lk:
            live[0] += 1
        try:
            h = one_start(b)
            rec["start_s"] = h.marks["first_ok"]
            time.sleep(random.uniform(0.8, 1.2) * a.session)
            try:
                b.call(h, {"op": "echo"}, timeout=10)
                rec["survived"] = True
            except Exception as e:
                rec["survived"] = False
                rec["lost"] = type(e).__name__
            ip = core.read_namespaced_pod(h.n, NS).status.pod_ip
            rec["same_ip"] = ip == h.ip
        except Exception as e:
            rec["error"] = f"{type(e).__name__} {str(e)[:150]}"
        if h:
            try:
                b.destroy(h)
            except Exception:
                pass
        with lk:
            live[0] -= 1
        emit("x_kp_session", rec, a.round)

    t0 = now()
    ex = cf.ThreadPoolExecutor(400)
    i = 0
    while now() - t0 < T:
        t = now() - t0
        rate = conc(t) / a.session
        time.sleep(random.expovariate(rate))
        ex.submit(session, i, t)
        i += 1
    ex.shutdown(wait=True)
    t = now()
    wait_zero(core)
    emit("x_kp_trace", {"sessions": i, "drain_s": now() - t, "keep": a.keep}, a.round)
    stop.set()
    print("TRACE DONE", i, a.round, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd")
    p.add_argument("--image")
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--sizes", default="1,20,50")
    p.add_argument("--round", default="kp")
    p.add_argument("--minutes", type=float, default=90)
    p.add_argument("--session", type=float, default=600)
    p.add_argument("--keep", action="store_true")
    a = p.parse_args()
    globals()["cmd_" + a.cmd](a)
