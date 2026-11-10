"""Nitro Sandbox pause and resume with an EBS volume, through agent-sandbox operatingMode.

Each cycle: create a Sandbox with a fresh gp3 volume mounted at /tmp, write a value through the
app (state_set writes /tmp/.state-<key> and also keeps it in process memory), suspend, resume,
then read it back. disk shows whether the file survived; memory shows whether process state did.
"""
import json, os, sys, time, uuid
sys.path.insert(0, "/work/bench")
import requests
import backends as B
from common import emit

NS = "sandboxes"
G, V = "agents.x-k8s.io", "v1beta1"
SC = "nitro-gp3"
k = B._k8s()
co, core, st = k.CustomObjectsApi(), k.CoreV1Api(), k.StorageV1Api()
http = requests.Session()
now = time.perf_counter


def ensure_sc():
    try:
        st.read_storage_class(SC)
    except k.ApiException:
        st.create_storage_class({"apiVersion": "storage.k8s.io/v1", "kind": "StorageClass", "metadata": {"name": SC},
                                 "provisioner": "ebs.csi.eks.amazonaws.com", "volumeBindingMode": "WaitForFirstConsumer",
                                 "parameters": {"type": "gp3", "encrypted": "true"}})


def pod_of(n):
    for p in core.list_namespaced_pod(NS, label_selector=f"bench={n}").items:
        if p.metadata.deletion_timestamp is None and p.status.pod_ip:
            return p
    return None


def wait_ok(n, t0, old_uid=None, deadline=600):
    while True:
        p = pod_of(n)
        if p is not None and p.metadata.uid != old_uid:
            try:
                r = http.post(f"http://{p.status.pod_ip}:8080/invocations", json={"op": "echo"}, timeout=2)
                if r.status_code == 200:
                    return now() - t0, p
            except requests.RequestException:
                pass
        if now() - t0 > deadline:
            raise TimeoutError(n)
        time.sleep(0.05)


def wait_no_pod(n, t0, deadline=600):
    while core.list_namespaced_pod(NS, label_selector=f"bench={n}").items:
        if now() - t0 > deadline:
            raise TimeoutError(n)
        time.sleep(0.1)
    return now() - t0


def call(p, body):
    return http.post(f"http://{p.status.pod_ip}:8080/invocations", json=body, timeout=30).json()


def cycle(i, image, rnd):
    n = "ps-" + uuid.uuid4().hex[:10]
    spec = B.pod_spec(image, "x86-nitro", "isolated-sandbox")
    spec["containers"][0]["volumeMounts"] = [{"name": "workspace", "mountPath": "/tmp"}]
    body = {"apiVersion": f"{G}/{V}", "kind": "Sandbox", "metadata": {"name": n},
            "spec": {"operatingMode": "Running",
                     "podTemplate": {"metadata": {"labels": {"bench": n}}, "spec": spec},
                     "volumeClaimTemplates": [{"metadata": {"name": "workspace"}, "spec": {"accessModes": ["ReadWriteOncePod"], "storageClassName": SC, "resources": {"requests": {"storage": "10Gi"}}}}]}}
    rec = {"i": i, "name": n}
    try:
        t0 = now()
        co.create_namespaced_custom_object(G, V, NS, "sandboxes", body)
        rec["create_s"], p = wait_ok(n, t0)
        value = uuid.uuid4().hex
        call(p, {"op": "state_set", "key": "w", "value": value})
        before = call(p, {"op": "state_get", "key": "w"})
        rec["before"] = {"memory_ok": before["memory"] == value, "disk_ok": before["disk"] == value, "instance": before["instance"], "uid": p.metadata.uid, "node": p.spec.node_name}
        t0 = now()
        co.patch_namespaced_custom_object(G, V, NS, "sandboxes", n, {"spec": {"operatingMode": "Suspended"}})
        rec["suspend_s"] = wait_no_pod(n, t0)
        pvcs = [c.metadata.name for c in core.list_namespaced_persistent_volume_claim(NS).items if n in c.metadata.name]
        rec["pvc_kept_while_suspended"] = bool(pvcs)
        time.sleep(5)
        t0 = now()
        co.patch_namespaced_custom_object(G, V, NS, "sandboxes", n, {"spec": {"operatingMode": "Running"}})
        rec["resume_s"], p2 = wait_ok(n, t0, old_uid=rec["before"]["uid"])
        after = call(p2, {"op": "state_get", "key": "w"})
        rec["after"] = {"memory_ok": after["memory"] == value, "disk_ok": after["disk"] == value, "new_instance": after["instance"] != before["instance"], "uid": p2.metadata.uid, "node": p2.spec.node_name}
        rec["ok"] = True
    except Exception as e:
        rec["ok"], rec["error"] = False, repr(e)[:400]
    finally:
        try:
            co.delete_namespaced_custom_object(G, V, NS, "sandboxes", n)
        except Exception:
            pass
    emit("nitro_pause_resume", rec, rnd)
    print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    ensure_sc()
    dep = B.load_registry()
    image = dep["backends"]["nt-c"]["image"]
    for i in range(int(sys.argv[1]) if len(sys.argv) > 1 else 5):
        cycle(i, image, sys.argv[2] if len(sys.argv) > 2 else "nt")
        time.sleep(10)
    print("PAUSE DONE", flush=True)
