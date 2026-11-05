"""Same HTTP app on every platform. It follows the AgentCore contract
(GET /ping, POST /invocations on 8080), which is also plain HTTP for EKS and Lambda MicroVMs."""
import json, os, threading, time, traceback

PROCESS_START = time.time()
# Optional simulated heavy start-up (model load, big imports) used by the "heavy-init" image variant.
_init = float(os.environ.get("INIT_SECONDS", "0"))
if _init:
    _end = time.perf_counter() + _init
    while time.perf_counter() < _end:
        pass

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

import bench_ops
import security_probe
import agent_runner  # the SDK itself is imported lazily; only the prewarm image loads it before a snapshot

INIT_DONE = time.time()
_busy = 0
_lock = threading.Lock()
_state = {}
_ballast = []
_first_req = None
_instance = None


async def ping(_: Request):
    body = {"status": "HealthyBusy" if _busy else "Healthy"}
    # The default build sends a fresh timestamp on every ping, which the AgentCore HTTP contract warns keeps idle sessions
    # from being reclaimed. Results were first measured with it; the noping image leaves it out, as the contract asks.
    if not os.environ.get("PING_NO_TIMESTAMP"):
        body["time_of_last_update"] = int(time.time())
    return JSONResponse(body)


def _dispatch(body):
    global _busy, _first_req, _instance
    op = body.get("op", "echo")
    if _instance is None:
        # Created per restored instance, never at start-up: a value made before a snapshot is shared by all clones.
        _instance = os.urandom(8).hex()
        _first_req = time.time()
    base = {"op": op, "instance": _instance, "process_start": PROCESS_START, "init_done": INIT_DONE, "first_request": _first_req, "now": time.time()}
    if op == "echo":
        return base
    if op == "state_set":
        _state[body["key"]] = body["value"]
        with open("/tmp/.state-" + body["key"], "w") as f:
            f.write(str(body["value"]))
        return base
    if op == "state_get":
        path = "/tmp/.state-" + body["key"]
        disk = open(path).read() if os.path.exists(path) else None
        return {**base, "memory": _state.get(body["key"]), "disk": disk}
    if op == "alloc":
        _ballast.append(bytearray(os.urandom(1024)) * (1024 * body["mb"]))
        return base
    if op == "free":
        _ballast.clear()
        import gc, ctypes
        gc.collect()
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass
        return base
    if op == "cpu_for":
        end = time.perf_counter() + body["seconds"]
        n = 0
        while time.perf_counter() < end:
            n += 1
        return {**base, "iters": n}
    if op == "sleep":
        time.sleep(body["seconds"])
        return base
    if op == "probe":
        return {**base, "result": security_probe.probe(body)}
    if op == "agent":
        return {**base, "result": agent_runner.run_agent(body)}
    if op in bench_ops.OPS:
        return {**base, "result": bench_ops.OPS[op](body)}
    return {**base, "error": f"unknown op {op}"}


async def invocations(req: Request):
    global _busy
    try:
        body = await req.json()
    except Exception:
        body = {}
    with _lock:
        _busy += 1
    try:
        # echo must not pick up thread-pool latency, so it stays on the event loop.
        if body.get("op", "echo") == "echo":
            return JSONResponse(_dispatch(body))
        return JSONResponse(await run_in_threadpool(_dispatch, body))
    except Exception as e:
        return JSONResponse({"error": repr(e), "trace": traceback.format_exc()[-1500:]}, status_code=500)
    finally:
        with _lock:
            _busy -= 1


app = Starlette(routes=[Route("/ping", ping), Route("/invocations", invocations, methods=["POST"]), Route("/", ping)])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning", access_log=False)
