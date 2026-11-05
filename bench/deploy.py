"""Deploys the managed backends and writes deployment.json. Deployment durations are themselves a result."""
import argparse, io, json, os, time, zipfile
import boto3
from common import emit

REGION = "us-east-1"
TF = json.load(open(os.environ.get("TF_OUTPUT", "/work/tf.json")))
ECR = TF["ecr"]
ctl = boto3.client("bedrock-agentcore-control", region_name=REGION)
mv = boto3.client("lambda-microvms", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


def agentcore(name, tag, version, idle=None, deploy_round="d1", network=None):
    kw = dict(agentRuntimeName=name, roleArn=TF["agentcore_exec_role"], agentRuntimeArtifact={"containerConfiguration": {"containerUri": f"{ECR}:{tag}"}}, networkConfiguration=network or {"networkMode": "PUBLIC"}, protocolConfiguration={"serverProtocol": "HTTP"}, platformVersion=version, tags={"project": "sandbox-bench"})
    if idle:
        kw["lifecycleConfiguration"] = {"idleRuntimeSessionTimeout": idle, "maxLifetime": 28800}
    t = time.perf_counter()
    r = ctl.create_agent_runtime(**kw)
    rid = r["agentRuntimeId"]
    while True:
        g = ctl.get_agent_runtime(agentRuntimeId=rid)
        if g["status"] in ("READY", "CREATE_FAILED"):
            break
        time.sleep(2)
    emit("deploy_time", {"backend": name, "kind": "agentcore", "platform": version, "image": tag, "seconds": time.perf_counter() - t, "status": g["status"], "reason": g.get("failureReason")}, deploy_round)
    print(name, g["status"], round(time.perf_counter() - t), g.get("failureReason"), flush=True)
    return {"kind": "agentcore", "arn": r["agentRuntimeArn"], "id": rid, "platform": version, "image": tag}


def agentcore_zip(name, version, deploy_round="d1"):
    """The same app as a direct code deployment. A container sets these variables in the image; here they go on the runtime."""
    env = dict(IS_SANDBOX="1", CLAUDE_CODE_USE_BEDROCK="1", AWS_REGION=REGION, ANTHROPIC_MODEL="us.anthropic.claude-opus-5-5", DISABLE_TELEMETRY="1", DISABLE_AUTOUPDATER="1", PING_NO_TIMESTAMP="1", PYTHONUNBUFFERED="1")
    t = time.perf_counter()
    r = ctl.create_agent_runtime(agentRuntimeName=name, roleArn=TF["agentcore_exec_role"], agentRuntimeArtifact={"codeConfiguration": {"code": {"s3": {"bucket": TF["bucket"], "prefix": "agentcore/deployment.zip"}}, "runtime": "PYTHON_3_13", "entryPoint": ["main.py"]}}, networkConfiguration={"networkMode": "PUBLIC"}, protocolConfiguration={"serverProtocol": "HTTP"}, platformVersion=version, environmentVariables=env, tags={"project": "sandbox-bench"})
    rid = r["agentRuntimeId"]
    while True:
        g = ctl.get_agent_runtime(agentRuntimeId=rid)
        if g["status"] in ("READY", "CREATE_FAILED"):
            break
        time.sleep(2)
    emit("deploy_time", {"backend": name, "kind": "agentcore-zip", "platform": version, "image": "zip", "seconds": time.perf_counter() - t, "status": g["status"], "reason": g.get("failureReason")}, deploy_round)
    print(name, g["status"], round(time.perf_counter() - t), g.get("failureReason"), flush=True)
    return {"kind": "agentcore", "arn": r["agentRuntimeArn"], "id": rid, "platform": version, "image": "zip"}


def microvm(name, tag, env=None, deploy_round="d1"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Dockerfile", f"FROM {ECR}:{tag}\n")
    key = f"microvm/{name}.zip"
    s3.put_object(Bucket=TF["bucket"], Key=key, Body=buf.getvalue())
    t = time.perf_counter()
    arn = next((i["imageArn"] for i in mv.list_microvm_images()["items"] if i.get("imageName") == name or i["imageArn"].endswith(":" + name)), None)
    if not arn:
        arn = mv.create_microvm_image(name=name, baseImageArn=f"arn:aws:lambda:{REGION}:aws:microvm-image:al2023-1", buildRoleArn=TF["microvm_build_role"], codeArtifact={"uri": f"s3://{TF['bucket']}/{key}"}, resources=[{"minimumMemoryInMiB": 4096}], tags={"project": "sandbox-bench"})["imageArn"]
    while True:
        g = mv.get_microvm_image(imageIdentifier=arn)
        if g["state"] in ("CREATED", "CREATE_FAILED"):
            break
        time.sleep(5)
    # createdAt/updatedAt come from the service, so a resumed wait still reports the true build time.
    secs = (g["updatedAt"] - g["createdAt"]).total_seconds()
    emit("deploy_time", {"backend": name, "kind": "microvm", "image": tag, "seconds": secs, "status": g["state"], "reason": g.get("stateReason")}, deploy_round)
    print(name, g["state"], round(secs), g.get("stateReason"), flush=True)
    return {"kind": "microvm", "image": arn, "tag": tag}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--which", default="all")
    a = p.parse_args()
    path = os.environ.get("DEPLOYMENT", "/work/deployment.json")
    dep = json.load(open(path)) if os.path.exists(path) else {"backends": {}}
    dep.update(bucket=TF["bucket"], microvm_exec_role=TF["microvm_exec_role"])
    bk = dep["backends"]
    # EKS backends need no deployment step beyond the cluster; the pod spec is built per request.
    for arch, grp_rt in (("amd64", [("x86-runc", None, "runc"), ("x86-gvisor", "gvisor", "gvisor"), ("x86-kata", "kata-qemu-runtime-rs", "kata")]), ("arm64", [("arm-runc", None, "runc"), ("arm-gvisor", "gvisor", "gvisor"), ("g3-runc", None, "runc"), ("g3-gvisor", "gvisor", "gvisor")])):
        for grp, rc, _ in grp_rt:
            for v in ("base", "large", "heavy"):
                nm = f"eks-{grp}" + ("" if v == "base" else f"-{v}")
                bk[nm] = {"kind": "eks_cold", "image": f"{ECR}:{v}-{arch}", "group": grp, "runtime_class": rc}
    for w, g, rc, arch in [("g3-gvisor", "g3-gvisor", "gvisor", "arm64"), ("x86-gvisor", "x86-gvisor", "gvisor", "amd64"), ("x86-kata", "x86-kata", "kata-qemu-runtime-rs", "amd64")]:
        bk[f"eks-{w}-probe"] = {"kind": "eks_cold", "image": f"{ECR}:probe-{arch}", "group": g, "runtime_class": rc}
    bk["eks-metal-kata"] = {"kind": "eks_cold", "image": f"{ECR}:base-amd64", "group": "metal-kata", "runtime_class": "kata-qemu-runtime-rs"}
    bk["eks-x86-kata-go"] = {"kind": "eks_cold", "image": f"{ECR}:base-amd64", "group": "x86-kata", "runtime_class": "kata-qemu"}
    for w, pl in [("x86-runc", "wp-x86-runc"), ("x86-gvisor", "wp-x86-gvisor"), ("x86-kata", "wp-x86-kata"), ("arm-gvisor", "wp-arm-gvisor")]:
        bk[f"eks-{w}-warm"] = {"kind": "eks_warm", "pool": pl}
    for w, pl in [("x86-gvisor", "wpa-x86-gvisor"), ("x86-kata", "wpa-x86-kata")]:
        bk[f"eks-{w}-warm-agent"] = {"kind": "eks_warm", "pool": pl}
    if a.which == "balance":
        # AgentCore in VPC mode: the private subnets and security group the cluster uses, reaching AWS through the same NAT.
        vpc = {"networkMode": "VPC", "networkModeConfig": json.loads(os.environ["AC_VPC"])}
        for nm, ver in [("ac_v1_vpc", "V1"), ("ac_v2_vpc", "V2")]:
            if nm.replace("_", "-") not in bk:
                bk[nm.replace("_", "-")] = agentcore("sbx" + nm, "noping-arm64", ver, network=vpc)
                json.dump(dep, open(path, "w"), indent=1)
        for w, pl in [("x86-gvisor", "wpi-x86-gvisor"), ("x86-kata", "wpi-x86-kata")]:
            bk[f"eks-{w}-warm-init"] = {"kind": "eks_warm", "pool": pl}
        json.dump(dep, open(path, "w"), indent=1)
        return
    if a.which == "pkg":
        # Deployment mode and image size, each compared with the base image results.
        for nm, tag, ver in [("ac_v1_tiny", "tiny-arm64", "V1"), ("ac_v2_warm", "warm-arm64", "V2")]:
            if nm.replace("_", "-") not in bk:
                bk[nm.replace("_", "-")] = agentcore("sbx" + nm, tag, ver)
                json.dump(dep, open(path, "w"), indent=1)
        for nm, ver in [("ac_v1_zip", "V1"), ("ac_v2_zip", "V2")]:
            if nm.replace("_", "-") not in bk:
                bk[nm.replace("_", "-")] = agentcore_zip("sbx" + nm, ver)
                json.dump(dep, open(path, "w"), indent=1)
        if "lm-warm" not in bk:
            bk["lm-warm"] = microvm("sbx-lm-warm", "warm-arm64")
            json.dump(dep, open(path, "w"), indent=1)
        dp = boto3.client("bedrock-agentcore", region_name=REGION)
        import uuid
        for rep in range(3):
            for ver in ("V1", "V2"):
                for kind in ("zip", "tiny"):
                    nm = f"sbxfresh_{ver}_{kind}_{rep}_{uuid.uuid4().hex[:6]}"
                    d = agentcore_zip(nm, ver, "fresh") if kind == "zip" else agentcore(nm, "tiny-arm64", ver, deploy_round="fresh")
                    for i in range(3):
                        sid = "bench-" + uuid.uuid4().hex + uuid.uuid4().hex[:8]
                        t = time.perf_counter()
                        r = dp.invoke_agent_runtime(agentRuntimeArn=d["arn"], runtimeSessionId=sid, payload=b'{"op":"echo"}', contentType="application/json", accept="application/json")
                        o = json.loads(r["response"].read())
                        emit("fresh_runtime", {"platform": ver, "image": kind, "rep": rep, "i": i, "cold_s": time.perf_counter() - t, "uptime": o["now"] - o["process_start"]}, "fresh")
                        dp.stop_runtime_session(agentRuntimeArn=d["arn"], runtimeSessionId=sid)
                    ctl.delete_agent_runtime(agentRuntimeId=d["id"])
        return
    if a.which == "fresh":
        # First sessions on a brand new runtime: no warm environment can exist yet.
        dp = boto3.client("bedrock-agentcore", region_name=REGION)
        import uuid
        for rep in range(3):
            for ver in ("V1", "V2"):
                for tag in ("base-arm64", "large-arm64"):
                    nm = f"sbxfresh_{ver}_{tag.split('-')[0]}_{rep}_{uuid.uuid4().hex[:6]}"
                    d = agentcore(nm, tag, ver, deploy_round="fresh")
                    for i in range(3):
                        sid = "bench-" + uuid.uuid4().hex + uuid.uuid4().hex[:8]
                        t = time.perf_counter()
                        r = dp.invoke_agent_runtime(agentRuntimeArn=d["arn"], runtimeSessionId=sid, payload=b'{"op":"echo"}', contentType="application/json", accept="application/json")
                        o = json.loads(r["response"].read())
                        emit("fresh_runtime", {"platform": ver, "image": tag, "rep": rep, "i": i, "cold_s": time.perf_counter() - t, "uptime": o["now"] - o["process_start"]}, "fresh")
                        dp.stop_runtime_session(agentRuntimeArn=d["arn"], runtimeSessionId=sid)
                    ctl.delete_agent_runtime(agentRuntimeId=d["id"])
        return
    if a.which in ("all", "agentcore"):
        for nm, tag, ver, idle in [("ac_v1", "base-arm64", "V1", None), ("ac_v2", "base-arm64", "V2", None), ("ac_v1_large", "large-arm64", "V1", None), ("ac_v2_large", "large-arm64", "V2", None), ("ac_v1_heavy", "heavy-arm64", "V1", None), ("ac_v2_heavy", "heavy-arm64", "V2", None), ("ac_v1_idle60", "base-arm64", "V1", 60), ("ac_v2_idle60", "base-arm64", "V2", 60), ("ac_v2_prewarm", "prewarm-arm64", "V2", None), ("ac_v1_probe", "probe-arm64", "V1", None), ("ac_v2_probe", "probe-arm64", "V2", None), ("ac_v1_probe2", "probe2-arm64", "V1", None), ("ac_v2_probe2", "probe2-arm64", "V2", None), ("ac_v1_probe3", "probe3-arm64", "V1", None), ("ac_v2_probe3", "probe3-arm64", "V2", None), ("ac_v2_pin", "pin-arm64", "V2", None), ("ac_v1_np", "noping-arm64", "V1", None), ("ac_v2_np", "noping-arm64", "V2", None), ("ac_v1_np_idle60", "noping-arm64", "V1", 60), ("ac_v2_np_idle60", "noping-arm64", "V2", 60), ("ac_v2_fa", "base-arm64", "V2", None), ("ac_v2_fb", "base-arm64", "V2", None), ("ac_v2_fc", "base-arm64", "V2", None), ("ac_v2_fd", "base-arm64", "V2", None), ("ac_v2_diag", "diag-arm64", "V2", None), ("ac_v2_q", "base-arm64", "V2", None), ("ac_v2_pinq", "pin-arm64", "V2", None), ("ac_v2_q2", "base-arm64", "V2", None), ("ac_v2_pinq2", "pin-arm64", "V2", None), ("ac_v1_s1", "noping-arm64", "V1", None), ("ac_v2_s1", "noping-arm64", "V2", None), ("ac_v1_s2", "noping-arm64", "V1", None), ("ac_v2_s2", "noping-arm64", "V2", None)]:
            if nm.replace("_", "-") in bk:
                continue
            bk[nm.replace("_", "-")] = agentcore("sbx" + nm, tag, ver, idle)
            json.dump(dep, open(path, "w"), indent=1)
    if a.which in ("all", "microvm"):
        for nm, tag in [("lm", "base-arm64"), ("lm-large", "large-arm64"), ("lm-heavy", "heavy-arm64"), ("lm-prewarm", "prewarm-arm64"), ("lm-probe", "probe-arm64"), ("lm-probe2", "probe2-arm64"), ("lm-probe3", "probe3-arm64"), ("lm-pin", "pin-arm64"), ("lm-fa", "base-arm64"), ("lm-fb", "base-arm64"), ("lm-fc", "base-arm64"), ("lm-fd", "base-arm64"), ("lm-diag", "diag-arm64"), ("lm-q", "base-arm64"), ("lm-pinq", "pin-arm64"), ("lm-q2", "base-arm64"), ("lm-pinq2", "pin-arm64"), ("lm-s1", "base-arm64"), ("lm-s2", "base-arm64")]:
            if nm in bk:
                continue
            bk[nm] = microvm("sbx-" + nm, tag)
            json.dump(dep, open(path, "w"), indent=1)
    json.dump(dep, open(path, "w"), indent=1)


if __name__ == "__main__":
    main()
