"""Benign checks of what a workload can see and do from inside its own sandbox.
No probe attempts to break out. Each one reports reachability or capability only;
credential values are never read into the result."""
import ctypes, errno, json, os, socket, subprocess, urllib.error, urllib.request
from pathlib import Path


def _tcp(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return "open"
    except socket.timeout:
        return "timeout"
    except OSError as e:
        return f"closed:{errno.errorcode.get(e.errno, e.errno)}"


def _imds():
    r = {"tcp80": _tcp("169.254.169.254", 80, 1.5), "v2_token": False, "role_listed": False, "instance_identity": False}
    if r["tcp80"] != "open":
        return r
    try:
        q = urllib.request.Request("http://169.254.169.254/latest/api/token", method="PUT", headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"})
        tok = urllib.request.urlopen(q, timeout=2).read().decode()
        r["v2_token"] = True
        h = {"X-aws-ec2-metadata-token": tok}
    except Exception as e:
        r["v2_error"] = type(e).__name__
        h = {}
    for key, path in [("role_listed", "/latest/meta-data/iam/security-credentials/"), ("instance_identity", "/latest/dynamic/instance-identity/document")]:
        try:
            body = urllib.request.urlopen(urllib.request.Request("http://169.254.169.254" + path, headers=h), timeout=2).read()
            r[key] = bool(body)
        except Exception as e:
            r[key + "_error"] = type(e).__name__
    return r


def _syscall(nr_by_arch, *args):
    import platform
    nr = nr_by_arch[platform.machine()]
    libc = ctypes.CDLL(None, use_errno=True)
    rc = libc.syscall(nr, *args)
    return {"rc": rc, "errno": errno.errorcode.get(ctypes.get_errno(), ctypes.get_errno()) if rc < 0 else None}


def _caps():
    for l in Path("/proc/self/status").read_text().splitlines():
        if l.startswith("CapEff"):
            return l.split()[1]
        


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return {"rc": r.returncode, "err": r.stderr.strip()[-160:]}
    except Exception as e:
        return {"rc": None, "err": f"{type(e).__name__}"}


def probe(args):
    peer = args.get("peer_ip")
    res = {
        "imds": _imds(),
        "ecs_eks_cred_endpoint_env": any(k in os.environ for k in ("AWS_CONTAINER_CREDENTIALS_FULL_URI", "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")),
        "aws_env_creds_present": "AWS_SECRET_ACCESS_KEY" in os.environ,
        "k8s_sa_token_mounted": Path("/var/run/secrets/kubernetes.io/serviceaccount/token").exists(),
        "k8s_api_env": "KUBERNETES_SERVICE_HOST" in os.environ,
        "k8s_api_tcp": _tcp(os.environ["KUBERNETES_SERVICE_HOST"], 443) if "KUBERNETES_SERVICE_HOST" in os.environ else "no-env",
        "peer_sandbox_tcp": _tcp(peer, 8080) if peer else "not-tested",
        "egress_internet_https": _tcp("example.com", 443, 3),
        "egress_dns": _dns(),
        "cap_eff": _caps(),
        "dev_kvm": Path("/dev/kvm").exists(),
        "dev_fuse": Path("/dev/fuse").exists(),
        "dev_list_count": len(os.listdir("/dev")),
        "seccomp": _status_field("Seccomp"),
        "no_new_privs": _status_field("NoNewPrivs"),
        "io_uring_setup": _syscall({"x86_64": 425, "aarch64": 425}, 0, 0),
        "bpf": _syscall({"x86_64": 321, "aarch64": 280}, 0, 0, 0),
        "perf_event_open": _syscall({"x86_64": 298, "aarch64": 241}, 0, 0, -1, -1, 0),
        "unshare_user": _run(["unshare", "-U", "true"]),
        "unshare_net": _run(["unshare", "-n", "true"]),
        "mount_tmpfs": _mount(),
        "ptrace_child": _ptrace(),
        "dmesg_readable": _run(["dmesg"])["rc"] == 0,
        "proc_cmdline": _read("/proc/cmdline")[:300],
        "proc_version": _read("/proc/version")[:200],
        "dmi_vendor": _read("/sys/class/dmi/id/sys_vendor")[:60],
        "cpu_hypervisor_flag": "hypervisor" in _read("/proc/cpuinfo"),
        "shared_host_kernel_hint": _read("/proc/sys/kernel/hostname")[:40],
    }
    return res


def _read(p):
    try:
        return Path(p).read_text()
    except Exception as e:
        return f"ERR:{type(e).__name__}"


def _status_field(name):
    for l in Path("/proc/self/status").read_text().splitlines():
        if l.startswith(name + ":"):
            return l.split()[1]
    return None


def _dns():
    try:
        socket.gethostbyname("example.com")
        return "ok"
    except Exception as e:
        return type(e).__name__


def _mount():
    d = "/tmp/.mnt-probe"
    os.makedirs(d, exist_ok=True)
    r = _run(["mount", "-t", "tmpfs", "tmpfs", d])
    if r["rc"] == 0:
        _run(["umount", d])
    return r


def _ptrace():
    code = "import ctypes,os,signal,time\npid=os.fork()\nif pid==0:\n time.sleep(2);os._exit(0)\nl=ctypes.CDLL(None,use_errno=True)\nrc=l.ptrace(16,pid,0,0)\nprint(rc,ctypes.get_errno())\nos.kill(pid,signal.SIGKILL)\n"
    try:
        r = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception as e:
        return type(e).__name__
