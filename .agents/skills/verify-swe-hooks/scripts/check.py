#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Drive each swe plugin hook in a real headless Claude Code session.

Prints `PASS <feature>` or `FAIL <feature>: <observed>` per feature.
Exits 0 only when every feature passes.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ROOT = SKILL_DIR.parents[2]
PLUGIN = ROOT / "plugins" / "swe"
SCRATCH = ROOT / ".agents" / "scratch"
TIMEOUT_SECONDS = 240

GOOD_BODY = """## Summary

Adds the verify skill.

## Evidence

The check printed PASS for each feature.

## Risk

**Reversible:** Yes, revert the commit.

**Blast Radius:** The repo-local skill folder only.
"""
BAD_BODY = GOOD_BODY.replace("Adds the verify skill.", "Requested by the user in chat.")

Events = list[dict]


@dataclass
class Feature:
    prompt: str
    judge: Callable[[Events], str | None]
    files: dict[str, str] = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)


def hook_responses(events: Events, hook_name: str) -> Events:
    return [
        e for e in events
        if e.get("subtype") == "hook_response" and e.get("hook_name", "").startswith(hook_name)
    ]


def tool_results(events: Events) -> list[str]:
    texts = []
    for e in events:
        if e.get("type") != "user":
            continue
        for block in e["message"]["content"]:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                texts.append(str(block.get("content")))
    return texts


def judge_session_start(events: Events) -> str | None:
    responses = hook_responses(events, "SessionStart")
    if not responses:
        return "no SessionStart hook_response event"
    expected = (PLUGIN / "hooks" / "session-start.md").read_text()
    got = responses[0].get("stdout")
    if responses[0].get("exit_code") != 0 or got != expected:
        return f"exit_code={responses[0].get('exit_code')}, stdout differs from hooks/session-start.md"
    return None


def judge_blocked(events: Events) -> str | None:
    responses = hook_responses(events, "PreToolUse:Bash")
    if not responses:
        return "PreToolUse:Bash hook never fired"
    r = responses[0]
    if r.get("exit_code") != 2 or "PR body blocked by ship-pr" not in r.get("stderr", ""):
        return f"hook exit_code={r.get('exit_code')}, stderr={r.get('stderr', '')[:120]!r}"
    if not any("PR body blocked by ship-pr" in t for t in tool_results(events)):
        return "hook blocked, but no tool_result carries the block message"
    return None


def judge_allowed(events: Events) -> str | None:
    responses = hook_responses(events, "PreToolUse:Bash")
    if not responses:
        return "PreToolUse:Bash hook never fired"
    r = responses[0]
    if r.get("exit_code") != 0:
        return f"hook exit_code={r.get('exit_code')}, stderr={r.get('stderr', '')[:120]!r}"
    if any("blocked by ship-pr" in t for t in tool_results(events)):
        return "a tool_result carries a ship-pr block message"
    return None


def run_only(command: str) -> str:
    return f"Run this exact command once with the Bash tool, change nothing, then stop: {command}"


FEATURES: dict[str, Feature] = {
    "session-start": Feature("Reply with the word ok.", judge_session_start),
    "pr-body-blocks-bad": Feature(
        run_only("gh pr create --title t --body-file bad.md"),
        judge_blocked,
        {"bad.md": BAD_BODY},
        ["Bash(gh pr create:*)"],
    ),
    "pr-body-allows-good": Feature(
        run_only("gh pr create --title t --body-file good.md"),
        judge_allowed,
        {"good.md": GOOD_BODY},
        ["Bash(gh pr create:*)"],
    ),
}


def run_session(run_dir: Path, name: str, feature: Feature, model: str | None) -> tuple[str, str | None]:
    repo = run_dir / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for filename, text in feature.files.items():
        (repo / filename).write_text(text)
    cmd = [
        "claude", "-p", feature.prompt,
        "--plugin-dir", str(PLUGIN),
        "--setting-sources", "project",
        "--permission-mode", "default",
        "--output-format", "stream-json", "--verbose", "--include-hook-events",
    ]
    for rule in feature.allowed_tools:
        cmd += ["--allowedTools", rule]
    if model:
        cmd += ["--model", model]
    try:
        proc = subprocess.run(
            cmd, cwd=repo, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL, env=os.environ, check=False,
        )
    except subprocess.TimeoutExpired:
        return name, f"claude -p timed out after {TIMEOUT_SECONDS}s"
    events = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]
    (repo / "stream.jsonl").write_text(proc.stdout)
    init = next((e for e in events if e.get("subtype") == "init"), None)
    if init is None:
        return name, f"no init event, exit {proc.returncode}, stderr={proc.stderr[:200]!r}"
    if not any(p.get("path") == str(PLUGIN) for p in init.get("plugins", [])):
        return name, f"plugin dir {PLUGIN} not loaded"
    return name, feature.judge(events)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="passed to claude --model")
    parser.add_argument("--keep", action="store_true", help="keep the throwaway repos and streams")
    parser.add_argument("features", nargs="*", help="default: all")
    args = parser.parse_args()
    names = args.features or list(FEATURES)
    unknown = [n for n in names if n not in FEATURES]
    if unknown:
        parser.error(f"unknown feature {unknown}; known: {list(FEATURES)}")

    SCRATCH.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="verify-swe-hooks-", dir=SCRATCH))
    try:
        with ThreadPoolExecutor(max_workers=len(names)) as pool:
            results = list(pool.map(lambda n: run_session(run_dir, n, FEATURES[n], args.model), names))
    finally:
        if args.keep:
            print(f"kept {run_dir}")
        else:
            shutil.rmtree(run_dir, ignore_errors=True)
    for name, problem in results:
        print(f"PASS {name}" if problem is None else f"FAIL {name}: {problem}")
    return 0 if all(p is None for _, p in results) else 1


if __name__ == "__main__":
    sys.exit(main())
