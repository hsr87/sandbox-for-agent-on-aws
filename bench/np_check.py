"""Runs after VPC CNI network policy is enabled. The managed warm pool policy blocks the driver's ingress,
so checks run inside each pod through exec. Also records whether the policy leaves the agent able to work."""
import json, sys, time
from kubernetes import client, config
from kubernetes.stream import stream
import backends as B
from common import emit

config.load_incluster_config()
core = client.CoreV1Api()
NS = "sandboxes"
INNER = r'''
import json, os, socket, sys, urllib.request
sys.path.insert(0, "/app")
import security_probe as p
peer = sys.argv[1]
r = p.probe({"peer_ip": peer})
def tcp(h, port):
    try:
        with socket.create_connection((h, port), timeout=3):
            return "open"
    except Exception as e:
        return type(e).__name__
r["extra"] = {"public_ip_443": tcp("1.1.1.1", 443), "pod_identity_169_254_170_23": tcp("169.254.170.23", 80)}
try:
    socket.gethostbyname("bedrock-runtime.us-east-1.amazonaws.com")
    r["extra"]["dns_bedrock"] = "ok"
except Exception as e:
    r["extra"]["dns_bedrock"] = type(e).__name__
print("JSON" + json.dumps(r))
'''


def in_pod(pod, peer):
    out = stream(core.connect_get_namespaced_pod_exec, pod, NS, command=["python", "-c", INNER, peer], container="agent", stderr=True, stdin=False, stdout=True, tty=False, _request_timeout=120)
    i = out.find("JSON{")
    if i < 0:
        return {"error": out[-400:]}
    # kubernetes stream can return single-quoted text for dict-like output
    return json.loads(out[i + 4:].strip().splitlines()[0])


def driver_reach(ip):
    import requests
    try:
        r = requests.get(f"http://{ip}:8080/ping", timeout=4)
        return f"http {r.status_code}"
    except Exception as e:
        return type(e).__name__


for group, prefix, name in (("x86-gvisor", "wp-x86-gvisor", "eks-x86-gvisor-warm"), ("x86-kata", "wp-x86-kata", "eks-x86-kata-warm")):
    pods = [p for p in core.list_namespaced_pod(NS).items if p.metadata.name.startswith(prefix) and p.status.phase == "Running"]
    a, b = pods[0], pods[1]
    res = in_pod(a.metadata.name, b.status.pod_ip)
    res["driver_to_sandbox"] = driver_reach(a.status.pod_ip)
    emit("security", {"backend": name, "label": "np-enforced", "result": res}, "np")
    print(name, json.dumps({k: res.get(k) for k in ("peer_sandbox_tcp", "k8s_api_tcp", "egress_internet_https", "egress_dns", "extra", "driver_to_sandbox", "error")}), flush=True)

# A Sandbox created directly, with no SandboxTemplate, gets no managed policy.
dep = B.load_registry()
b = B.make("eks-x86-gvisor", dep)
h1, h2 = b.create(), b.create()
b.wait_usable(h1)
b.wait_usable(h2)
d = b.call(h1, {"op": "probe", "peer_ip": h2.ip})
emit("security", {"backend": "eks-x86-gvisor", "label": "np-enabled-no-policy", "result": d.get("result")}, "np")
print("direct Sandbox", d["result"]["peer_sandbox_tcp"], d["result"]["k8s_api_tcp"], d["result"]["egress_internet_https"], flush=True)
b.destroy(h1)
b.destroy(h2)
print("DONE np_check")
