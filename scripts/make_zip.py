"""Packages the app and its installed dependencies as an AgentCore direct code deployment. Run inside the base-arm64 image."""
import os, stat, sys, zipfile

SITE = "/usr/local/lib/python3.13/site-packages"
out = sys.argv[1]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    def add(path, arc):
        info = zipfile.ZipInfo.from_file(path, arc)
        executable = os.stat(path).st_mode & stat.S_IXUSR or arc.endswith("_bundled/claude")
        info.external_attr = (0o755 if executable else 0o644) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        with open(path, "rb") as f:
            z.writestr(info, f.read())
    for root, dirs, files in os.walk(SITE):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for n in files:
            p = os.path.join(root, n)
            add(p, os.path.relpath(p, SITE))
    for n in os.listdir("/app"):
        if n.endswith(".py"):
            add(os.path.join("/app", n), n)
    add("/app/server.py", "main.py")
print(os.path.getsize(out) / 1e6, "MB compressed", sum(i.file_size for i in zipfile.ZipFile(out).infolist()) / 1e6, "MB uncompressed")
