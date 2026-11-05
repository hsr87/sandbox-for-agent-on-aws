# Multi-arch agent image. The same image digest runs on every platform under test.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm AS build
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends gcc libc6-dev >/dev/null
COPY syscall_bench.c /src/syscall_bench.c
RUN gcc -O2 -static -o /syscall_bench /src/syscall_bench.c

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends git util-linux ca-certificates >/dev/null \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -q claude-agent-sdk==0.2.177 starlette==0.47.2 "uvicorn==0.35.0" boto3 pytest==8.4.1
COPY --from=build /syscall_bench /usr/local/bin/syscall_bench
COPY server.py bench_ops.py security_probe.py agent_runner.py /app/
COPY corpus/project /opt/corpus/project
# stdlib tree used by the compile workload: a realistic mix of small files
RUN python - <<'PY'
import tarfile, sysconfig, pathlib
lib = pathlib.Path(sysconfig.get_paths()["stdlib"])
with tarfile.open("/opt/corpus/stdlib.tar.gz", "w:gz") as t:
    t.add(lib, arcname="stdlib", filter=lambda m: None if "site-packages" in m.name or "__pycache__" in m.name else m)
PY
WORKDIR /app
ENV PYTHONUNBUFFERED=1 IS_SANDBOX=1 CLAUDE_CODE_USE_BEDROCK=1 AWS_REGION=us-east-1 ANTHROPIC_MODEL=us.anthropic.claude-opus-5-5 DISABLE_TELEMETRY=1 DISABLE_AUTOUPDATER=1 HOME=/tmp
EXPOSE 8080
CMD ["python", "server.py"]
