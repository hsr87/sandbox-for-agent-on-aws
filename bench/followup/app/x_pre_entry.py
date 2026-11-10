"""Variant entry. X_PRE=map runs the CLI and maps every page before the snapshot. X_PRE=exec only runs the CLI. Empty does nothing."""
import importlib.util, mmap, os, pathlib, runpy, subprocess
MODE = os.environ.get("X_PRE", "")
held = None
if MODE:
    cli = pathlib.Path(importlib.util.find_spec("claude_agent_sdk").origin).parent / "_bundled" / "claude"
    subprocess.run([str(cli), "--version"], capture_output=True)
    if MODE == "map":
        import claude_agent_sdk
        f = open(cli, "rb")
        held = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ)
        sum(held[i] for i in range(0, len(held), 4096))
runpy.run_path("/app/x_entry.py", run_name="__main__")
