"""Adds a first-touch probe on top of the unchanged app: how long does each file or tool take the first
time a fresh sandbox uses it, and the second time? Separates lazy loading from everything else."""
import pathlib, runpy, subprocess, sys, time
sys.path.insert(0, "/app")
import bench_ops, claude_agent_sdk

CLI = pathlib.Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"


def _t(cmd):
    t = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True)
    return {"s": time.perf_counter() - t, "rc": r.returncode}


def _read(p):
    t = time.perf_counter()
    n = 0
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            n += len(b)
    s = time.perf_counter() - t
    return {"s": s, "MB": n / 1e6, "MBps": n / 1e6 / s}


def first_touch(_):
    out = {}
    py = sys.executable
    steps = [
        ("git_version", lambda: _t(["git", "--version"])),
        ("python_import_boto3", lambda: _t([py, "-c", "import boto3"])),
        ("pytest_version", lambda: _t([py, "-m", "pytest", "--version"])),
        ("read_cli_binary", lambda: _read(CLI)),
        ("claude_version", lambda: _t([str(CLI), "--version"])),
    ]
    for round_ in ("first", "second"):
        for name, fn in steps:
            out[f"{name}_{round_}"] = fn()
    return out


def netinfo(_):
    import socket
    ips = []
    for line in pathlib.Path("/proc/net/fib_trie").read_text().splitlines():
        line = line.strip()
        if line.startswith("|--"):
            ips.append(line.split()[1])
    return {"hostname": socket.gethostname(), "candidate_ips": sorted({i for i in ips if not i.startswith(("127.", "0.", "255.")) and not i.endswith((".0", ".255"))})}


bench_ops.OPS["first_touch"] = first_touch
bench_ops.OPS["netinfo"] = netinfo
# A long request that sends a whitespace heartbeat, as a streaming agent would, and then its JSON result.
import asyncio, json
import uvicorn
from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.routing import Route

g = runpy.run_path("/app/server.py", run_name="server")
plain = g["invocations"]


async def invocations(req: Request):
    body = await req.body()
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        data = {}
    if data.get("op") == "stream_sleep":
        async def gen():
            g["_busy"] += 1
            end = time.monotonic() + data["seconds"]
            try:
                while time.monotonic() < end:
                    yield b" "
                    await asyncio.sleep(min(15, max(0.1, end - time.monotonic())))
                yield json.dumps({"op": "stream_sleep", "ok": True}).encode()
            finally:
                g["_busy"] -= 1
        return StreamingResponse(gen(), media_type="application/json")

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    return await plain(Request(req.scope, receive))


g["app"].router.routes = [r for r in g["app"].router.routes if getattr(r, "path", "") != "/invocations"] + [Route("/invocations", invocations, methods=["POST"])]
uvicorn.run(g["app"], host="0.0.0.0", port=8080, log_level="warning", access_log=False)
