#!/usr/bin/env python3
"""Adds one layer to an image in ECR without a local container engine. Used when the Finch VM disk is full."""
import argparse, gzip, hashlib, io, json, os, sys, tarfile, tempfile, zipfile
import boto3, urllib.request
ecr = boto3.client("ecr", region_name="us-east-1")
REPO = "sbx-bench/agent"
PART = 20 * 1024 * 1024


def manifest(tag):
    r = ecr.batch_get_image(repositoryName=REPO, imageIds=[{"imageTag": tag}], acceptedMediaTypes=["application/vnd.docker.distribution.manifest.v2+json", "application/vnd.oci.image.manifest.v1+json", "application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"])
    if not r["images"]:
        sys.exit(f"no image {tag}")
    return json.loads(r["images"][0]["imageManifest"])


def blob(digest):
    u = ecr.get_download_url_for_layer(repositoryName=REPO, layerDigest=digest)["downloadUrl"]
    return urllib.request.urlopen(u).read()


def upload(path_or_bytes):
    data = None
    if isinstance(path_or_bytes, bytes):
        data = io.BytesIO(path_or_bytes)
    else:
        data = open(path_or_bytes, "rb")
    h = hashlib.sha256()
    while True:
        b = data.read(1 << 20)
        if not b:
            break
        h.update(b)
    digest = "sha256:" + h.hexdigest()
    size = data.tell()
    if ecr.batch_check_layer_availability(repositoryName=REPO, layerDigests=[digest])["layers"][0:1] and ecr.batch_check_layer_availability(repositoryName=REPO, layerDigests=[digest])["layers"][0]["layerAvailability"] == "AVAILABLE":
        return digest, size
    uid = ecr.initiate_layer_upload(repositoryName=REPO)["uploadId"]
    data.seek(0)
    off = 0
    while True:
        b = data.read(PART)
        if not b:
            break
        ecr.upload_layer_part(repositoryName=REPO, uploadId=uid, partFirstByte=off, partLastByte=off + len(b) - 1, layerPartBlob=b)
        off += len(b)
    ecr.complete_layer_upload(repositoryName=REPO, uploadId=uid, layerDigests=[digest])
    return digest, size


def add(tar, arc, data=None, path=None, mode=0o644):
    ti = tarfile.TarInfo(arc.lstrip("/"))
    ti.mode = mode
    ti.mtime = 0
    if path:
        ti.size = os.path.getsize(path)
        with open(path, "rb") as f:
            tar.addfile(ti, f)
    else:
        ti.size = len(data)
        tar.addfile(ti, io.BytesIO(data))


def compose(base, tag, files, env=None, cmd=None):
    """files: list of (path in image, local path or bytes, mode)"""
    m = manifest(base)
    if "manifests" in m:
        sys.exit(f"{base} is an index")
    cfg = json.loads(blob(m["config"]["digest"]))
    with tempfile.TemporaryDirectory(dir=os.environ.get("COMPOSE_TMP")) as d:
        raw = os.path.join(d, "l.tar")
        with tarfile.open(raw, "w") as t:
            for arc, src, mode in files:
                if isinstance(src, bytes):
                    add(t, arc, data=src, mode=mode)
                else:
                    add(t, arc, path=src, mode=mode)
        h = hashlib.sha256()
        gz = raw + ".gz"
        with open(raw, "rb") as f, open(gz, "wb") as o, gzip.GzipFile(fileobj=o, mode="wb", compresslevel=1, mtime=0) as z:
            while True:
                b = f.read(1 << 20)
                if not b:
                    break
                h.update(b)
                z.write(b)
        diff = "sha256:" + h.hexdigest()
        digest, size = upload(gz)
    cfg["rootfs"]["diff_ids"].append(diff)
    cfg.setdefault("history", []).append({"created_by": "compose " + tag})
    c = cfg.setdefault("config", {})
    for k, v in (env or {}).items():
        c["Env"] = [e for e in c.get("Env", []) if not e.startswith(k + "=")] + [f"{k}={v}"]
    if cmd:
        c["Cmd"] = cmd
        c["Entrypoint"] = None
    cb = json.dumps(cfg).encode()
    cd, cs = upload(cb)
    m["config"]["digest"], m["config"]["size"] = cd, cs
    gztype = "application/vnd.oci.image.layer.v1.tar+gzip" if "oci" in m.get("mediaType", m["config"]["mediaType"]) else "application/vnd.docker.image.rootfs.diff.tar.gzip"
    m["layers"].append({"mediaType": gztype, "digest": digest, "size": size})
    try:
        ecr.put_image(repositoryName=REPO, imageManifest=json.dumps(m), imageManifestMediaType=m.get("mediaType", "application/vnd.oci.image.manifest.v1+json"), imageTag=tag)
    except ecr.exceptions.ImageAlreadyExistsException:
        pass
    print(tag, "layer", size, flush=True)


def wheel_files(whl, site):
    z = zipfile.ZipFile(whl)
    out = []
    for n in z.namelist():
        if n.endswith("/"):
            continue
        out.append((f"{site}/{n}", z.read(n), 0o755 if n.endswith("_bundled/claude") else 0o644))
    return out


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("job")
    a.add_argument("--work")
    x = a.parse_args()
    W = x.work
    os.environ["COMPOSE_TMP"] = W
    if x.job == "xi":
        compose("x1e-arm64", "xi-g2b-arm64", [("/opt/asset2.bin", f"{W}/g2/asset.bin", 0o644)])
        for u in range(1, 7):
            p = f"{W}/u{u}.bin"
            with open(p, "wb") as f:
                f.write(os.urandom(331212056))
            compose("x1e-arm64", f"xi-u{u}-arm64", [("/opt/asset.bin", p, 0o644)])
            os.remove(p)
        print("XI_IMAGES_DONE", flush=True)
    if x.job == "xm":
        app = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
        site = "/usr/local/lib/python3.13/site-packages"
        entry = open(f"{app}/x_entry.py", "rb").read()
        pre = open(f"{app}/x_pre_entry.py", "rb").read()
        cmd = ["python", "/app/x_pre_entry.py"]
        for arch, base in [("arm64", "noping-arm64"), ("amd64", "base-amd64")]:
            compose(base, f"x1f-{arch}", [("/app/x_entry.py", entry, 0o644), ("/app/x_pre_entry.py", pre, 0o644)], env={"PING_NO_TIMESTAMP": "1"}, cmd=cmd)
        for t, v, m in [("none176", "0.2.176", ""), ("map178", "0.2.178", "map"), ("pre173", "0.2.173", "exec"), ("w175", "0.2.175", ""), ("w174", "0.2.174", ""), ("none171", "0.2.171", ""), ("map168", "0.2.168", "map")]:
            import glob
            whl = glob.glob(f"{W}/../wh/v{v}/*.whl")[0]
            compose("x1f-arm64", f"xm-{t}-arm64", wheel_files(whl, site), env={"X_PRE": m})
        print("XM_IMAGES_DONE", flush=True)
