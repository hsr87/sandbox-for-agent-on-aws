"""Workloads that run inside each sandbox. Every op returns plain JSON with seconds."""
import hashlib, json, multiprocessing as mp, os, platform, shutil, socket, ssl, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

CORPUS = Path("/opt/corpus")
WORK = Path(os.environ.get("BENCH_WORKDIR", "/tmp"))


def _timed(fn):
    t = time.perf_counter()
    extra = fn() or {}
    return {"seconds": time.perf_counter() - t, **extra}


def _hash_worker(mb):
    data = b"\0" * (1024 * 1024)
    h = hashlib.sha256()
    for _ in range(mb):
        h.update(data)


def cpu_python(_):
    def f():
        s = 0
        for i in range(3_000_000):
            s += i * i
    return _timed(f)


def cpu_sha256(_):
    return _timed(lambda: _hash_worker(512))


def cpu_parallel(args):
    n = args.get("procs", 2)
    def f():
        ps = [mp.Process(target=_hash_worker, args=(256,)) for _ in range(n)]
        [p.start() for p in ps]
        [p.join() for p in ps]
    return {**_timed(f), "procs": n}


def syscalls(_):
    out = subprocess.run(["/usr/local/bin/syscall_bench"], capture_output=True, text=True, timeout=600)
    return json.loads(out.stdout.strip())


def files_small(_):
    d = Path(tempfile.mkdtemp(dir=WORK))
    def f():
        for i in range(2000):
            p = d / f"f{i}"
            p.write_bytes(b"x" * 512)
            p.stat()
        for i in range(2000):
            (d / f"f{i}").unlink()
    r = _timed(f)
    shutil.rmtree(d, ignore_errors=True)
    return r


def disk_seq(_):
    p = WORK / f"seq-{os.getpid()}"
    size = 512
    block = os.urandom(1024 * 1024)
    t = time.perf_counter()
    fd = os.open(p, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
    for _i in range(size):
        os.write(fd, block)
    os.fsync(fd)
    os.close(fd)
    w = time.perf_counter() - t
    fd = os.open(p, os.O_RDONLY)
    try:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    except OSError:
        pass
    t = time.perf_counter()
    while os.read(fd, 1024 * 1024):
        pass
    r = time.perf_counter() - t
    os.close(fd)
    p.unlink()
    return {"write_MBps": size / w, "read_MBps": size / r, "write_seconds": w, "read_seconds": r}


def mem_touch(args):
    mb = args.get("mb", 1024)
    def f():
        b = bytearray(mb * 1024 * 1024)
        for i in range(0, len(b), 4096):
            b[i] = 1
    return {**_timed(f), "mb": mb}


def compile_stdlib(_):
    d = Path(tempfile.mkdtemp(dir=WORK))
    t = time.perf_counter()
    subprocess.run(["tar", "xzf", str(CORPUS / "stdlib.tar.gz"), "-C", str(d)], check=True)
    x = time.perf_counter() - t
    t = time.perf_counter()
    subprocess.run([sys.executable, "-m", "compileall", "-q", "-j", "2", str(d)], check=False, capture_output=True)
    c = time.perf_counter() - t
    shutil.rmtree(d, ignore_errors=True)
    return {"extract_seconds": x, "compile_seconds": c, "seconds": x + c}


def pytest_project(_):
    d = Path(tempfile.mkdtemp(dir=WORK))
    shutil.copytree(CORPUS / "project", d / "p")
    def f():
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(d / "p")], capture_output=True, text=True)
        return {"rc": r.returncode}
    res = _timed(f)
    shutil.rmtree(d, ignore_errors=True)
    return res


def pip_install(_):
    d = tempfile.mkdtemp(dir=WORK)
    def f():
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", "--target", d, "requests==2.32.3", "rich==13.9.4"], capture_output=True, text=True)
        return {"rc": r.returncode, "err": r.stderr[-300:] if r.returncode else ""}
    res = _timed(f)
    shutil.rmtree(d, ignore_errors=True)
    return res


def git_clone(_):
    d = tempfile.mkdtemp(dir=WORK)
    def f():
        r = subprocess.run(["git", "clone", "-q", "--depth", "1", "https://github.com/pallets/flask", d + "/r"], capture_output=True, text=True)
        return {"rc": r.returncode, "err": r.stderr[-300:] if r.returncode else ""}
    res = _timed(f)
    shutil.rmtree(d, ignore_errors=True)
    return res


def claude_cli_start(_):
    """Starts the Claude Code CLI bundled in the Agent SDK. This cost is paid once per agent query."""
    from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport  # noqa
    import claude_agent_sdk
    cli = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
    times = []
    for _i in range(5):
        t = time.perf_counter()
        r = subprocess.run([str(cli), "--version"], capture_output=True, text=True)
        times.append(time.perf_counter() - t)
    return {"seconds": sorted(times)[2], "all": times, "version": r.stdout.strip(), "rc": r.returncode}


def tls_connect(args):
    host = args.get("host", "bedrock-runtime.us-east-1.amazonaws.com")
    ctx = ssl.create_default_context()
    ts = []
    for _i in range(20):
        t = time.perf_counter()
        with socket.create_connection((host, 443), timeout=10) as s:
            with ctx.wrap_socket(s, server_hostname=host):
                pass
        ts.append(time.perf_counter() - t)
    ts.sort()
    return {"seconds": ts[len(ts) // 2], "p90": ts[int(len(ts) * 0.9)]}


def net_download(args):
    url = args["url"]
    t = time.perf_counter()
    n = 0
    with urllib.request.urlopen(url, timeout=120) as r:
        while True:
            b = r.read(1024 * 1024)
            if not b:
                break
            n += len(b)
    s = time.perf_counter() - t
    return {"seconds": s, "bytes": n, "MBps": n / 1e6 / s}


def sysinfo(_):
    def rd(p):
        try:
            return Path(p).read_text().strip()
        except Exception as e:
            return f"ERR {type(e).__name__}"
    mem = {l.split(":")[0]: l.split(":")[1].strip() for l in rd("/proc/meminfo").splitlines() if l.startswith(("MemTotal", "MemAvailable"))}
    cpuinfo = rd("/proc/cpuinfo")
    models = [l.split(":", 1)[1].strip() for l in cpuinfo.splitlines() if l.lower().startswith(("model name", "cpu part", "bogomips"))]
    du = shutil.disk_usage(str(WORK))
    return {
        "uname": platform.uname()._asdict(),
        "python": sys.version.split()[0],
        "nproc_online": os.cpu_count(),
        "sched_affinity": len(os.sched_getaffinity(0)),
        "cgroup_cpu_max": rd("/sys/fs/cgroup/cpu.max"),
        "cgroup_mem_max": rd("/sys/fs/cgroup/memory.max"),
        "mem": mem,
        "cpu_models": sorted(set(models))[:4],
        "disk_total_GB": round(du.total / 1e9, 1),
        "disk_free_GB": round(du.free / 1e9, 1),
        "clocksource": rd("/sys/devices/system/clocksource/clocksource0/current_clocksource"),
        "uptime_seconds": rd("/proc/uptime").split()[0] if rd("/proc/uptime") else None,
        "user": os.getuid(),
    }


OPS = {f.__name__: f for f in [cpu_python, cpu_sha256, cpu_parallel, syscalls, files_small, disk_seq, mem_touch, compile_stdlib, pytest_project, pip_install, git_clone, claude_cli_start, tls_connect, net_download, sysinfo]}
