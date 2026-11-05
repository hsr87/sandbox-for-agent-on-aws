"""Mitigation variant: exercise the Claude CLI before the snapshot is taken, then serve as usual."""
import pathlib, runpy, subprocess, sys
import claude_agent_sdk
cli = pathlib.Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
subprocess.run([str(cli), "--version"], capture_output=True)
with open(cli, "rb") as f:
    while f.read(1 << 20):
        pass
sys.argv = ["server.py"]
runpy.run_path("/app/server.py", run_name="__main__")
