"""Follow-up image entry. Adds ops to the same server. Nothing here runs before a snapshot except registration,
so neither SDK and no file under test is touched at start-up."""
import asyncio, os, pathlib, runpy, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, "/app")
import bench_ops

pc = time.perf_counter
TASK = """Create a small Python package in the current directory.
1. Write `calc.py` with functions add, sub, mul, div. div must raise ZeroDivisionError for a zero divisor.
2. Write `test_calc.py` with pytest tests covering all four functions and the zero divisor case.
3. Run `python -m pytest -q` with the Bash tool and fix anything that fails.
When the tests pass, reply with the single word DONE."""


def cpu():
    return sorted({l.split(":")[1].strip() for l in open("/proc/cpuinfo") if l.startswith("CPU part")})


def bundled_cli():
    import importlib.util
    return str(pathlib.Path(importlib.util.find_spec("claude_agent_sdk").origin).parent / "_bundled" / "claude")


def read_file(path, drop=False):
    fd = os.open(path, os.O_RDONLY)
    if drop:
        os.fsync(fd)
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    t = pc()
    n = 0
    while True:
        b = os.read(fd, 1 << 20)
        if not b:
            break
        n += len(b)
    s = pc() - t
    os.close(fd)
    return {"s": s, "bytes": n}


def x_cpu(_):
    return {"cpu": cpu()}


def x_read_asset(a):
    p = a.get("path", "/opt/asset.bin")
    r1 = read_file(p)
    r2 = read_file(p)
    return {"first": r1, "second": r2, "cpu": cpu()}


def x_warm_cli(_):
    """What a warming session does: starts the CLI once and reads the whole binary."""
    cli = bundled_cli()
    t = pc()
    subprocess.run([cli, "--version"], capture_output=True)
    v = pc() - t
    r = read_file(cli)
    return {"version_s": v, "read": r, "cpu": cpu()}


def x_strands(a):
    """The same task through the Strands Agents SDK, with the same three tools. An optional asset is read first."""
    t0 = pc()
    out = {"cpu": cpu()}
    if a.get("asset"):
        out["asset_first"] = read_file(a["asset"])
        out["asset_second"] = read_file(a["asset"])
    t = pc()
    from strands import Agent, tool
    from strands.models import BedrockModel
    out["import_s"] = pc() - t
    d = tempfile.mkdtemp(prefix="agent-")

    @tool
    def write_file(path: str, content: str) -> str:
        """Write a text file in the working directory."""
        pathlib.Path(d, path).write_text(content)
        return "ok"

    @tool
    def read_text(path: str) -> str:
        """Read a text file in the working directory."""
        return pathlib.Path(d, path).read_text()

    @tool
    def bash(command: str) -> str:
        """Run a shell command in the working directory and return its output."""
        r = subprocess.run(command, shell=True, cwd=d, capture_output=True, text=True, timeout=300)
        return (r.stdout + r.stderr)[-4000:]

    model = BedrockModel(model_id=a["model"], region_name=os.environ["AWS_REGION"], streaming=True, max_tokens=4096)
    agent = Agent(model=model, tools=[write_file, read_text, bash], callback_handler=None, system_prompt="You are a coding agent. Use the tools to do the task.")

    async def go():
        t1 = pc()
        first = None
        res = None
        async for ev in agent.stream_async(a.get("prompt", TASK)):
            if first is None and "event" in ev:
                first = pc() - t1
            if "result" in ev:
                res = ev["result"]
        return first, res
    t1 = pc()
    first, res = asyncio.run(go())
    out["agent_s"] = pc() - t1
    out["first_stream_event"] = first
    m = res.metrics.accumulated_metrics if res else {}
    out["model_ms"] = m.get("latencyMs")
    out["cycles"] = res.metrics.cycle_count if res else None
    out["total_in_app_s"] = pc() - t0
    v = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=d, capture_output=True, text=True)
    out["verify_pytest_rc"] = v.returncode
    shutil.rmtree(d, ignore_errors=True)
    return out


def x_claude(a):
    """The Claude SDK task with an optional other CLI path, and an optional S3 fetch of the CLI first."""
    out = {"cpu": cpu()}
    t0 = pc()
    cli = a.get("cli_path")
    if a.get("s3"):
        import boto3
        t = pc()
        os.makedirs(os.path.dirname(cli), exist_ok=True)
        boto3.client("s3").download_file(a["s3"]["bucket"], a["s3"]["key"], cli)
        os.chmod(cli, 0o755)
        out["fetch_s"] = pc() - t
        out["fetch_bytes"] = os.path.getsize(cli)
    if a.get("read_cold") and cli:
        out["cli_read"] = read_file(cli, drop=True)
    elif a.get("read_before") and cli:
        out["cli_read"] = read_file(cli)

    async def go():
        t = pc()
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
        out["import_s"] = pc() - t
        d = tempfile.mkdtemp(prefix="agent-")
        kw = {"cli_path": cli} if cli else {}
        opts = ClaudeAgentOptions(model=a["model"], cwd=d, allowed_tools=["Read", "Write", "Edit", "Bash"], permission_mode="bypassPermissions", include_partial_messages=True, max_turns=15, setting_sources=[], **kw)
        t1 = pc()
        fm = fs = None
        async for m in query(prompt=a.get("prompt", TASK), options=opts):
            now = pc() - t1
            if fm is None:
                fm = now
            if type(m).__name__ == "StreamEvent" and fs is None:
                fs = now
            if isinstance(m, ResultMessage):
                out["duration_api_ms"] = m.duration_api_ms
                out["is_error"] = m.is_error
        out["agent_s"] = pc() - t1
        out["first_message"] = fm
        out["first_stream_event"] = fs
        v = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=d, capture_output=True, text=True)
        out["verify_pytest_rc"] = v.returncode
        shutil.rmtree(d, ignore_errors=True)
    asyncio.run(go())
    out["total_in_app_s"] = pc() - t0
    return out


def x_cli_on_store(a):
    """Reads a CLI already on the mounted path. Used after a stop and resume with the same session id."""
    p = a["path"]
    return {"exists": os.path.exists(p), "size": os.path.getsize(p) if os.path.exists(p) else None, "cpu": cpu()}


def x_store_cycle(a):
    """Session storage check. fetch: download to the mount, leave a marker in /tmp. resume: is the marker gone, and how fast is the stored file with and without the page cache."""
    p = a["path"]
    mark = "/tmp/x_store_marker"
    out = {"cpu": cpu(), "boot_id": open("/proc/sys/kernel/random/boot_id").read().strip(), "marker_in_tmp": os.path.exists(mark), "exists": os.path.exists(p)}
    if a["phase"] == "fetch":
        import boto3
        t = pc()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        boto3.client("s3").download_file(a["s3"]["bucket"], a["s3"]["key"], p)
        out["fetch_s"] = pc() - t
        t = pc()
        fd = os.open(p, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
        out["fsync_s"] = pc() - t
        open(mark, "w").write("x")
    else:
        out["size"] = os.path.getsize(p)
        out["first"] = read_file(p)
        out["again"] = read_file(p)
        out["after_drop"] = read_file(p, drop=True)
        out["after_drop2"] = read_file(p, drop=True)
    return out


def _safe(f):
    def g(a):
        try:
            return f(a)
        except BaseException as e:
            import traceback
            return {"failed": repr(e)[:400], "trace": traceback.format_exc()[-1200:]}
    g.__name__ = f.__name__
    return g


bench_ops.OPS.update({f.__name__: _safe(f) for f in [x_cpu, x_read_asset, x_warm_cli, x_strands, x_claude, x_cli_on_store, x_store_cycle]})
sys.argv = ["server.py"]
runpy.run_path("/app/server.py", run_name="__main__")
