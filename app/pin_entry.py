"""Mitigation variant: map the CLI binary and lock process memory before the snapshot, then serve as usual.
Tests whether pages held this way survive into restored sessions."""
import ctypes, mmap, pathlib, runpy, subprocess, sys
import claude_agent_sdk

cli = pathlib.Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
subprocess.run([str(cli), "--version"], capture_output=True)
f = open(cli, "rb")
m = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ)
libc = ctypes.CDLL(None, use_errno=True)
locked = libc.mlockall(1 | 2)  # MCL_CURRENT | MCL_FUTURE
touched = sum(m[i] for i in range(0, len(m), 4096))
print("mlockall", locked, "errno", ctypes.get_errno(), "touched", touched % 7, flush=True)
sys.argv = ["server.py"]
runpy.run_path("/app/server.py", run_name="__main__")
