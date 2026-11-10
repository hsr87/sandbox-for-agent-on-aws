"""One interface over every sandbox under test.

Every timing starts just before the first control-plane or data-plane call that asks
for a sandbox and ends when the *agent app inside it* answers an echo request. That is
the moment a caller can actually use the sandbox, whichever platform it is on.
"""
import json, os, random, time, uuid

import boto3, requests
from botocore.config import Config

REGION = os.environ.get("AWS_REGION", "us-east-1")
NS = "sandboxes"
_cfg = Config(region_name=REGION, retries={"max_attempts": 0, "mode": "standard"}, read_timeout=1800, connect_timeout=10, max_pool_connections=300)
now = time.perf_counter


class Throttled(Exception):
    pass


class Handle:
    def __init__(self, **kw):
        self.marks = {}
        self.__dict__.update(kw)


# AgentCore Runtime ---------------------------------------------------------------------------
class AgentCore:
    def __init__(self, name, arn):
        self.name, self.arn = name, arn
        self.dp = boto3.client("bedrock-agentcore", config=_cfg)
        if os.environ.get("TCP_KEEPALIVE"):
            # A NAT gateway drops a silent flow after 350 s. Keepalive separates that from a service limit.
            import socket
            opts = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1), (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60), (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 30)]
            self.dp._endpoint.http_session._manager.connection_pool_kw["socket_options"] = opts

    def create(self):
        # A session is created by its first invoke, so create() only picks an id.
        return Handle(sid="bench-" + uuid.uuid4().hex + uuid.uuid4().hex[:8], t0=now())

    def call(self, h, payload, timeout=None):
        try:
            r = self.dp.invoke_agent_runtime(agentRuntimeArn=self.arn, runtimeSessionId=h.sid, payload=json.dumps(payload).encode(), contentType="application/json", accept="application/json")
        except self.dp.exceptions.ThrottlingException as e:
            raise Throttled(str(e))
        return json.loads(r["response"].read())

    def wait_usable(self, h):
        d = self.call(h, {"op": "echo"})
        h.marks["first_ok"] = now() - h.t0
        return d

    def destroy(self, h):
        self.dp.stop_runtime_session(agentRuntimeArn=self.arn, runtimeSessionId=h.sid)


# Lambda MicroVMs -----------------------------------------------------------------------------
class Microvm:
    CONN = "arn:aws:lambda:%s:aws:network-connector:aws-network-connector:%s"

    def __init__(self, name, image, exec_role, idle=None, version=None):
        self.name, self.image, self.role, self.version = name, image, exec_role, version
        self.idle = idle or {"autoResumeEnabled": True, "maxIdleDurationSeconds": 3600, "suspendedDurationSeconds": 300}
        self.c = boto3.client("lambda-microvms", config=_cfg)
        self.http = requests.Session()
        self.http.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=300))

    def create(self):
        t0 = now()
        kw = dict(imageIdentifier=self.image, ingressNetworkConnectors=[self.CONN % (REGION, "HTTP_INGRESS")], egressNetworkConnectors=[self.CONN % (REGION, "INTERNET_EGRESS")], executionRoleArn=self.role, idlePolicy=self.idle)
        if self.version:
            kw["imageVersion"] = self.version
        try:
            r = self.c.run_microvm(**kw)
        except self.c.exceptions.ClientError as e:
            if "Throttl" in str(e) or "TooMany" in str(e):
                raise Throttled(str(e))
            raise
        h = Handle(id=r["microvmId"], endpoint=r["endpoint"], t0=t0)
        h.marks["api_return"] = now() - t0
        return h

    def _token(self, h):
        t = self._retrying(self.c.create_microvm_auth_token, microvmIdentifier=h.id, expirationInMinutes=60, allowedPorts=[{"allPorts": {}}])
        # The API returns the header to send as a map, e.g. {"X-aws-proxy-auth": "<jwe>"}.
        h.auth = t["authToken"]

    def wait_usable(self, h, deadline=600):
        self.wait_state(h, "RUNNING", deadline)
        h.marks["running"] = now() - h.t0
        self._token(h)
        h.marks["token"] = now() - h.t0
        while True:
            try:
                d = self.call(h, {"op": "echo"}, timeout=15)
                h.marks["first_ok"] = now() - h.t0
                return d
            except (requests.ConnectionError, requests.Timeout):
                if now() - h.t0 > deadline:
                    raise
                time.sleep(0.02)

    poll = 0.05

    def _retrying(self, fn, **kw):
        # Control-plane reads are throttled at 100/s per account. A throttled read says nothing about the sandbox.
        while True:
            try:
                return fn(**kw)
            except Exception as e:
                if "Throttl" not in str(e) and "TooMany" not in str(e):
                    raise
                time.sleep(random.uniform(0.2, 1.0))

    def state(self, h):
        return self._retrying(self.c.get_microvm, microvmIdentifier=h.id)["state"]

    def wait_state(self, h, target, deadline=600, poll=None):
        poll = poll or self.poll
        t = now()
        while True:
            s = self.state(h)
            if s == target:
                return now() - t
            if s in ("TERMINATED", "FAILED") and target != s:
                raise RuntimeError(f"microvm {h.id} went {s}")
            if now() - t > deadline:
                raise TimeoutError(f"{h.id} stuck in {s}")
            time.sleep(poll)

    def call(self, h, payload, timeout=1800):
        r = self.http.post(f"https://{h.endpoint}/invocations", json=payload, headers=h.auth, timeout=timeout)
        if r.status_code >= 500 or r.status_code == 429:
            raise requests.ConnectionError(f"HTTP {r.status_code}: {r.text[:200]}")
        r.raise_for_status()
        return r.json()

    def destroy(self, h):
        self.c.terminate_microvm(microvmIdentifier=h.id)


# EKS + Agent Sandbox -------------------------------------------------------------------------
def _k8s():
    from kubernetes import client, config
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    c = client.Configuration.get_default_copy()
    c.connection_pool_maxsize = 300
    client.Configuration.set_default(c)
    return client


def pod_spec(image, group, runtime_class, env=None, fargate=None, size=None):
    """fargate: None for EC2 nodes, or {"cpu": ..., "memory": ...}. Fargate sizes the microVM from requests and ignores limits."""
    res = {"requests": {"cpu": "250m", "memory": "512Mi"}, "limits": {"cpu": "2", "memory": "8Gi"}}
    if fargate:
        res = {"requests": dict(fargate), "limits": dict(fargate)}
    if size:
        # Nitro Sandboxes also size the VM from requests, so requests equal limits here.
        res = {"requests": dict(size), "limits": dict(size)}
    spec = {
        "serviceAccountName": "sandbox-fargate" if fargate else "sandbox",
        "tolerations": [],
        "containers": [{
            "name": "agent", "image": image, "imagePullPolicy": "IfNotPresent",
            "ports": [{"containerPort": 8080}],
            "env": env or [],
            "resources": res,
            "readinessProbe": {"httpGet": {"path": "/ping", "port": 8080}, "periodSeconds": 1, "failureThreshold": 600},
        }],
    }
    if group:
        spec["nodeSelector"] = {"bench/group": group}
    if group == "x86-nitro":
        # Nitro Sandbox nodes on the Auto Mode cluster are tainted so that only sandbox pods land there.
        spec["tolerations"] = [{"key": "bench/nitro", "operator": "Exists", "effect": "NoSchedule"}]
    if runtime_class:
        spec["runtimeClassName"] = runtime_class
    return spec


class EksCold:
    """Creates a Sandbox object per request. Nothing is pre-warmed."""
    poll = 0.05

    def __init__(self, name, image, group, runtime_class, env=None, fargate=None, size=None):
        self.name, self.image, self.group, self.rc, self.env, self.fargate, self.size = name, image, group, runtime_class, env, fargate, size
        self.k = _k8s()
        self.co, self.core = self.k.CustomObjectsApi(), self.k.CoreV1Api()
        self.http = requests.Session()

    def create(self):
        n = "c-" + uuid.uuid4().hex[:12]
        t0 = now()
        body = {"apiVersion": "agents.x-k8s.io/v1beta1", "kind": "Sandbox", "metadata": {"name": n, "labels": {"bench": self.name}}, "spec": {"podTemplate": {"metadata": {"labels": {"bench": self.name, **({"bench/compute": "fargate"} if self.fargate else {})}}, "spec": pod_spec(self.image, self.group, self.rc, self.env, self.fargate, self.size)}}}
        self.co.create_namespaced_custom_object("agents.x-k8s.io", "v1beta1", NS, "sandboxes", body)
        h = Handle(n=n, t0=t0, ip=None)
        h.marks["api_return"] = now() - t0
        return h

    def wait_usable(self, h, deadline=900):
        while h.ip is None:
            try:
                p = self.core.read_namespaced_pod(h.n, NS)
                h.ip = p.status.pod_ip
            except self.k.ApiException as e:
                if e.status != 404:
                    raise
            if now() - h.t0 > deadline:
                raise TimeoutError(f"no pod ip for {h.n}")
            if h.ip is None:
                time.sleep(self.poll)
        h.marks["pod_ip"] = now() - h.t0
        return _poll_http(self, h, deadline)

    def call(self, h, payload, timeout=1800):
        r = self.http.post(f"http://{h.ip}:8080/invocations", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def destroy(self, h):
        self.co.delete_namespaced_custom_object("agents.x-k8s.io", "v1beta1", NS, "sandboxes", h.n)

    def wait_gone(self, h, deadline=300):
        t = now()
        while now() - t < deadline:
            try:
                self.core.read_namespaced_pod(h.n, NS)
            except self.k.ApiException as e:
                if e.status == 404:
                    return now() - t
            time.sleep(0.1)
        raise TimeoutError(f"pod {h.n} not removed")


def _poll_http(b, h, deadline):
    while True:
        try:
            r = b.http.post(f"http://{h.ip}:8080/invocations", json={"op": "echo"}, timeout=2)
            if r.status_code == 200:
                h.marks["first_ok"] = now() - h.t0
                return r.json()
        except requests.RequestException:
            pass
        if now() - h.t0 > deadline:
            raise TimeoutError(f"{h.ip} never answered")
        time.sleep(0.01)


class EksWarm(EksCold):
    """Binds a SandboxClaim to a pre-warmed pod from a SandboxWarmPool."""
    G = "extensions.agents.x-k8s.io"

    def __init__(self, name, pool):
        self.name, self.pool = name, pool
        self.k = _k8s()
        self.co, self.core = self.k.CustomObjectsApi(), self.k.CoreV1Api()
        self.http = requests.Session()

    def ready_replicas(self):
        d = self.co.get_namespaced_custom_object(self.G, "v1beta1", NS, "sandboxwarmpools", self.pool)
        return d.get("status", {}).get("readyReplicas", 0)

    def wait_pool(self, n, deadline=900):
        t = now()
        while self.ready_replicas() < n:
            if now() - t > deadline:
                raise TimeoutError(f"pool {self.pool} not at {n}")
            time.sleep(0.2)
        return now() - t

    def create(self):
        n = "w-" + uuid.uuid4().hex[:12]
        t0 = now()
        body = {"apiVersion": f"{self.G}/v1beta1", "kind": "SandboxClaim", "metadata": {"name": n}, "spec": {"warmPoolRef": {"name": self.pool}}}
        self.co.create_namespaced_custom_object(self.G, "v1beta1", NS, "sandboxclaims", body)
        h = Handle(n=n, t0=t0, ip=None)
        h.marks["api_return"] = now() - t0
        return h

    def wait_usable(self, h, deadline=900):
        while h.ip is None:
            d = self.co.get_namespaced_custom_object(self.G, "v1beta1", NS, "sandboxclaims", h.n)
            ips = d.get("status", {}).get("sandbox", {}).get("podIPs")
            if ips:
                h.ip = ips[0]
                h.pod = d["status"]["sandbox"].get("name")
            elif now() - h.t0 > deadline:
                raise TimeoutError(f"claim {h.n} unbound")
            else:
                time.sleep(self.poll)
        h.marks["bound"] = now() - h.t0
        return _poll_http(self, h, deadline)

    def destroy(self, h):
        self.co.delete_namespaced_custom_object(self.G, "v1beta1", NS, "sandboxclaims", h.n)

    def wait_gone(self, h, deadline=300):
        return None


# Registry ------------------------------------------------------------------------------------
def load_registry(path=None):
    """deployment.json is written by deploy scripts and maps a backend name to its resources."""
    path = path or os.environ.get("DEPLOYMENT", "/work/deployment.json")
    return json.load(open(path))


def make(name, dep):
    s = dep["backends"][name]
    k = s["kind"]
    if k == "agentcore":
        return AgentCore(name, s["arn"])
    if k == "microvm":
        return Microvm(name, s["image"], dep["microvm_exec_role"], idle=s.get("idle"))
    if k == "eks_cold":
        return EksCold(name, s["image"], s["group"], s.get("runtime_class"), s.get("env"), size=s.get("size"))
    if k == "eks_fargate":
        return EksCold(name, s["image"], None, None, s.get("env"), fargate={"cpu": s["cpu"], "memory": s["memory"]})
    if k == "eks_warm":
        return EksWarm(name, s["pool"])
    raise ValueError(k)
