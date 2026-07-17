#!/usr/bin/env python3
"""Behavioral checks for ext-subagent: timeout kill-tree, empty-answer guard, role expansion, auto selection, arg validation."""
import importlib.util
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Load the module via importlib (filename has a hyphen)
spec = importlib.util.spec_from_file_location(
    "ext_subagent",
    str(Path(__file__).parent / "ext-subagent.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Track results for summary at the end
passed = []
failed = []


def test_timeout_kill_tree():
    """Timeout kills the whole process group, returns 124, and doesn't hang."""
    start = time.monotonic()
    proc = mod.run_process(["bash", "-c", "sleep 30 & sleep 30"], timeout=1)
    elapsed = time.monotonic() - start
    assert proc.returncode == mod.TIMEOUT_RETURNCODE, f"Expected 124, got {proc.returncode}"
    assert elapsed < 5, f"took {elapsed:.1f}s, expected < 5s"
    assert "killed after --timeout 1s" in proc.stderr
    leftover = subprocess.run(["pgrep", "-f", "sleep 30"], capture_output=True, text=True)
    assert leftover.stdout.strip() == "", f"orphaned children: {leftover.stdout}"
    print("✓ timeout kill-tree OK")
    passed.append("timeout_kill_tree")


def test_timeout_zero_disables():
    """--timeout 0 disables the timeout limit."""
    proc = mod.run_process(["echo", "hi"], timeout=0)
    assert proc.returncode == 0 and proc.stdout.strip() == "hi"
    print("✓ timeout=0 OK")
    passed.append("timeout_zero_disables")


def test_empty_answer_guard():
    """Empty-answer guard: exit-0 + empty answer becomes a failure and consumes retries."""
    calls = []

    def fake_runner(prompt, model, effort, timeout):
        calls.append(1)
        return mod.Result(0, "", "provider log")

    mod.RUNNERS["codex"] = fake_runner
    res = mod.dispatch("codex", "p", None, None, 60, 2, 0)
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}"
    assert "empty answer" in res.log
    assert len(calls) == 3, f"Expected 3 attempts (1 initial + 2 retries), got {len(calls)}"
    print("✓ empty-answer guard OK")
    passed.append("empty_answer_guard")


def test_codex_roles_table():
    """CODEX_ROLES table matches the delegate tiers."""
    assert mod.CODEX_ROLES == {
        "explorer": ("gpt-5.6-luna", "medium"),
        "doer": ("gpt-5.6-luna", "xhigh"),
        "planner": ("gpt-5.6-sol", "high"),
    }
    print("✓ role table OK")
    passed.append("codex_roles_table")


def test_role_with_model_error():
    """--role combined with --model must error."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "ext-subagent.py"),
         "codex", "test", "--role", "doer", "--model", "gpt-5.0-turbo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "Expected non-zero exit"
    assert "--role already sets" in result.stderr or "combine it" in result.stderr, \
        f"Expected error about --role and --model, got: {result.stderr}"
    print("✓ --role with --model error OK")
    passed.append("role_with_model_error")


def test_role_with_reasoning_effort_error():
    """--role combined with --reasoning-effort must error."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "ext-subagent.py"),
         "codex", "test", "--role", "doer", "--reasoning-effort", "high"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "Expected non-zero exit"
    assert "--role already sets" in result.stderr or "combine it" in result.stderr, \
        f"Expected error about --role and --reasoning-effort, got: {result.stderr}"
    print("✓ --role with --reasoning-effort error OK")
    passed.append("role_with_reasoning_effort_error")


def test_role_on_non_codex_error():
    """--role on a non-codex provider must error."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "ext-subagent.py"),
         "copilot", "test", "--role", "doer"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "Expected non-zero exit"
    assert "--role is codex-only" in result.stderr, \
        f"Expected '--role is codex-only' error, got: {result.stderr}"
    print("✓ --role on non-codex error OK")
    passed.append("role_on_non_codex_error")


def test_reasoning_effort_on_non_codex_error():
    """--reasoning-effort on a non-codex provider must error."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "ext-subagent.py"),
         "copilot", "test", "--reasoning-effort", "high"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "Expected non-zero exit"
    assert "--reasoning-effort is codex-only" in result.stderr, \
        f"Expected '--reasoning-effort is codex-only' error, got: {result.stderr}"
    print("✓ --reasoning-effort on non-codex error OK")
    passed.append("reasoning_effort_on_non_codex_error")


def test_negative_timeout_error():
    """--timeout negative must error."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "ext-subagent.py"),
         "codex", "test", "--timeout", "-1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "Expected non-zero exit"
    assert "--timeout must be" in result.stderr, \
        f"Expected '--timeout must be' error, got: {result.stderr}"
    print("✓ --timeout negative error OK")
    passed.append("negative_timeout_error")


def _with_probes(copilot, agy, codex, fn):
    """Stub the quota probes for one call, then put them back.

    pick_agent is a module, so a stub assigned here outlives the test and leaks
    into test_pick_agent when both run in one process.
    """
    pa = mod.pick_agent
    saved = (pa.probe_copilot, pa.probe_agy, pa.probe_codex)
    pa.probe_copilot, pa.probe_agy, pa.probe_codex = copilot, agy, codex
    try:
        return fn()
    finally:
        pa.probe_copilot, pa.probe_agy, pa.probe_codex = saved


def _run(*argv):
    return subprocess.run(
        [sys.executable, str(Path(__file__).parent / "ext-subagent.py"), *argv],
        capture_output=True,
        text=True,
    )


def test_auto_name_map_covers_the_whole_chain():
    """pick_agent prints commands; this table speaks provider names.

    Two names for one thing is a drift seam, so pin it: every provider the chain
    can yield must map, and every mapping must land on a real runner. Add a
    provider to the chain without touching the table and this fires.
    """
    pa = mod.pick_agent
    chain_names = _with_probes(
        lambda: pa.Absent(),
        lambda: pa.Absent(),
        lambda now: pa.Absent(),
        lambda: {n for n, _ in pa.probe_chain(datetime.now(timezone.utc))},
    )
    assert chain_names == set(mod.SELECTOR_TO_PROVIDER), \
        f"name map {set(mod.SELECTOR_TO_PROVIDER)} drifted from chain {chain_names}"
    assert set(mod.SELECTOR_TO_PROVIDER.values()) <= set(mod.RUNNERS), \
        "auto could select a provider with no runner"
    assert mod.SELECTOR_TO_PROVIDER["agy"] == "antigravity"
    print("✓ auto name map covers the chain OK")
    passed.append("auto_name_map")


def test_auto_optimistic_picks_the_unmeasurable_provider():
    """agy has no quota interface; optimistic presumes it available."""
    pa = mod.pick_agent
    winner = _with_probes(
        lambda: pa.Known(0.0, "monthly"),
        lambda: pa.Unknown("no quota interface"),
        lambda now: pa.Known(0.0, "weekly"),
        lambda: mod.resolve_auto("optimistic"),
    )
    assert winner == "antigravity", winner
    print("✓ auto optimistic -> antigravity OK")
    passed.append("auto_optimistic")


def test_auto_strict_skips_the_unmeasurable_provider():
    """strict wants a measured provider; today that leaves nothing."""
    pa = mod.pick_agent
    spent = _with_probes(
        lambda: pa.Known(0.0, "monthly"),
        lambda: pa.Unknown("no quota interface"),
        lambda now: pa.Known(0.0, "weekly"),
        lambda: mod.resolve_auto("strict"),
    )
    assert spent is None, spent
    healthy = _with_probes(
        lambda: pa.Known(0.0, "monthly"),
        lambda: pa.Unknown("no quota interface"),
        lambda now: pa.Known(80.0, "weekly"),
        lambda: mod.resolve_auto("strict"),
    )
    assert healthy == "codex", healthy
    print("✓ auto strict OK")
    passed.append("auto_strict")


def test_policy_without_auto_errors():
    """--policy is meaningless when the caller already named the provider."""
    result = _run("codex", "test", "--policy", "strict")
    assert result.returncode != 0, "Expected non-zero exit"
    assert "--policy applies to auto only" in result.stderr, result.stderr
    print("✓ --policy without auto error OK")
    passed.append("policy_without_auto_error")


def test_model_with_auto_errors():
    """A model literal cannot survive a provider chosen at runtime."""
    result = _run("auto", "test", "--model", "gpt-5.6-luna")
    assert result.returncode != 0, "Expected non-zero exit"
    assert "need an explicit provider" in result.stderr, result.stderr
    print("✓ --model with auto error OK")
    passed.append("model_with_auto_error")


def test_workers_stdin_is_closed():
    """`codex exec` blocks on an inherited idle stdin even with a prompt argument.

    Reading stdin here at all means a background caller hangs until --timeout.
    """
    proc = mod.run_process([sys.executable, "-c", "import sys; sys.stdin.read()"], timeout=10)
    assert proc.returncode == 0, f"worker blocked on stdin: rc={proc.returncode}"
    print("✓ worker stdin closed OK")
    passed.append("worker_stdin_closed")


def main():
    """Run all tests."""
    print("Running ext-subagent tests...\n")

    # Run tests
    test_timeout_kill_tree()
    test_timeout_zero_disables()
    test_empty_answer_guard()
    test_codex_roles_table()
    test_role_with_model_error()
    test_role_with_reasoning_effort_error()
    test_role_on_non_codex_error()
    test_reasoning_effort_on_non_codex_error()
    test_negative_timeout_error()
    test_auto_name_map_covers_the_whole_chain()
    test_auto_optimistic_picks_the_unmeasurable_provider()
    test_auto_strict_skips_the_unmeasurable_provider()
    test_policy_without_auto_errors()
    test_model_with_auto_errors()
    test_workers_stdin_is_closed()

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"Tests passed: {len(passed)}/{len(passed) + len(failed)}")
    if failed:
        print(f"Tests failed: {len(failed)}")
        for test_name in failed:
            print(f"  - {test_name}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
