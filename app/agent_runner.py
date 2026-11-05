"""One fixed coding task run through the Claude Agent SDK."""
import asyncio, os, shutil, subprocess, sys, tempfile, time

TASK = """Create a small Python package in the current directory.
1. Write `calc.py` with functions add, sub, mul, div. div must raise ZeroDivisionError for a zero divisor.
2. Write `test_calc.py` with pytest tests covering all four functions and the zero divisor case.
3. Run `python -m pytest -q` with the Bash tool and fix anything that fails.
When the tests pass, reply with the single word DONE."""


def _diag_options(log):
    """Only in the diag image: keep the CLI's own log, to see whether a slow start hides an error or a retry."""
    if not os.environ.get("AGENT_DIAG"):
        return {}
    return {"stderr": lambda line: log.append((round(time.perf_counter(), 3), line[:300])), "extra_args": {"debug-to-stderr": None}}


def _diag_result(log):
    if not os.environ.get("AGENT_DIAG"):
        return {}
    import resource
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    words = ("error", "retry", "fail", "timeout", "throttl", "exception", "denied")
    part = next((l.split(":")[1].strip() for l in open("/proc/cpuinfo") if l.startswith("CPU part")), None)
    return {"diag": {"child_major_faults": ru.ru_majflt, "child_block_in": ru.ru_inblock, "child_user_s": ru.ru_utime, "child_sys_s": ru.ru_stime, "cpu_part": part, "log_lines": len(log), "log_first_at": log[0][0] if log else None, "suspect": [l for _, l in log if any(w in l.lower() for w in words)][:15], "head": [l for _, l in log[:8]]}}


async def _go(model, prompt, max_turns):
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
    d = tempfile.mkdtemp(prefix="agent-")
    t0 = time.perf_counter()
    marks = {"first_message": None, "first_stream_event": None}
    log = []
    result = {}
    opts = ClaudeAgentOptions(
        model=model,
        cwd=d,
        allowed_tools=["Read", "Write", "Edit", "Bash"],
        permission_mode="bypassPermissions",
        include_partial_messages=True,
        max_turns=max_turns,
        setting_sources=[],
        **_diag_options(log),
    )
    async for m in query(prompt=prompt, options=opts):
        now = time.perf_counter() - t0
        if marks["first_message"] is None:
            marks["first_message"] = now
        if type(m).__name__ == "StreamEvent" and marks["first_stream_event"] is None:
            marks["first_stream_event"] = now
        if isinstance(m, ResultMessage):
            u = m.usage or {}
            result = {
                "is_error": m.is_error,
                "num_turns": m.num_turns,
                "duration_ms": m.duration_ms,
                "duration_api_ms": m.duration_api_ms,
                "total_cost_usd": m.total_cost_usd,
                "input_tokens": u.get("input_tokens"),
                "output_tokens": u.get("output_tokens"),
                "cache_read_tokens": u.get("cache_read_input_tokens"),
                "cache_create_tokens": u.get("cache_creation_input_tokens"),
            }
    total = time.perf_counter() - t0
    v = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=d, capture_output=True, text=True)
    shutil.rmtree(d, ignore_errors=True)
    return {"seconds": total, **marks, **result, "verify_pytest_rc": v.returncode, **_diag_result(log)}


def run_agent(args):
    model = args.get("model") or os.environ.get("ANTHROPIC_MODEL", "us.anthropic.claude-opus-5-5")
    prompt = args.get("prompt", TASK)
    return asyncio.run(_go(model, prompt, args.get("max_turns", 15)))
