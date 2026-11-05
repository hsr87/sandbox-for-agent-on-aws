import json, pathlib, subprocess, sys
import pytest

@pytest.mark.parametrize("n", range(60))
def test_files(tmp_path, n):
    p = tmp_path / f"{n}.json"
    p.write_text(json.dumps({"n": n, "items": list(range(200))}))
    assert json.loads(p.read_text())["n"] == n

@pytest.mark.parametrize("n", range(10))
def test_subprocess(n):
    r = subprocess.run([sys.executable, "-c", f"print({n})"], capture_output=True, text=True)
    assert r.stdout.strip() == str(n)
