"""Follows the AWS V2 optimization guide as far as the app allows: import, exercise and run everything once before the snapshot."""
import pathlib, runpy, subprocess, sys, threading
import claude_agent_sdk  # noqa: F401
import boto3

boto3.client("sts", region_name="us-east-1")
cli = pathlib.Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
subprocess.run([str(cli), "--version"], capture_output=True)
subprocess.run([sys.executable, "-m", "pytest", "--version"], capture_output=True)
sys.path.insert(0, "/app")
import agent_runner

done = threading.Event()
def warm():
    try:
        print("warm task", agent_runner.run_agent({}).get("verify_pytest_rc"), flush=True)
    except Exception as e:  # a build environment may have no credentials; the local steps above still ran
        print("warm task failed", type(e).__name__, flush=True)
    done.set()
threading.Thread(target=warm, daemon=True).start()
done.wait(70)
sys.argv = ["server.py"]
runpy.run_path("/app/server.py", run_name="__main__")
