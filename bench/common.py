import json, os, socket, threading, time
RESULTS = os.environ.get("RESULTS", "/work/results")
_lock = threading.Lock()


def emit(exp, record, round_id=None):
    """Append-only: a failed run is written too. Nothing is dropped at measurement time."""
    record = {"exp": exp, "round": round_id, "ts": time.time(), **record}
    p = os.path.join(RESULTS, f"{exp}.jsonl")
    with _lock:
        os.makedirs(RESULTS, exist_ok=True)
        with open(p, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
    return record
