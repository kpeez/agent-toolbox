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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ROOT = SKILL_DIR.parents[2]
PLUGIN = ROOT / "plugins" / "swe"
SCRATCH = ROOT / ".agents" / "scratch" / "verify-swe-hooks"
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

DEMO_SKILL = """---
name: verify-demo
description: Demo check for the commit gate. Use when src changes.
paths:
  - src/**
---

# Verify the demo

The check is `true`.
"""
GATE_FILES = {
    ".agents/skills/verify-demo/SKILL.md": DEMO_SKILL,
    "src/a.txt": "one\n",
    "docs/d.md": "one\n",
}
GATE_RUN = f"sh {PLUGIN}/scripts/run-ts {PLUGIN}/scripts/verify_gate.ts run --skill verify-demo -- true"
GATE_BLOCK = "Commit blocked by the verify gate"
GATE_TOOLS = ["Bash(echo:*)", "Bash(tee:*)", "Bash(git commit:*)", f"Bash(sh {PLUGIN}/scripts/run-ts:*)"]

Events = list[dict]


@dataclass
class Feature:
    prompt: str
    judge: Callable[[Events], str | None]
    files: dict[str, str] = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    commit_files: bool = False


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
    bad = [r.get("exit_code") for r in responses if r.get("exit_code") != 0]
    if bad:
        return f"a SessionStart hook exited {bad}"
    if not any(r.get("stdout") == expected for r in responses):
        return "no SessionStart hook printed hooks/session-start.md"
    if any(r.get("stdout") not in ("", expected) for r in responses):
        return "a SessionStart hook printed text in a repo with no verify skill"
    return None


def judge_blocked(events: Events) -> str | None:
    responses = hook_responses(events, "PreToolUse:Bash")
    if not responses:
        return "PreToolUse:Bash hook never fired"
    if not any(r.get("exit_code") == 2 and "PR body blocked by ship-pr" in r.get("stderr", "") for r in responses):
        return f"no hook blocked: exit_codes={[r.get('exit_code') for r in responses]}"
    if not any("PR body blocked by ship-pr" in t for t in tool_results(events)):
        return "hook blocked, but no tool_result carries the block message"
    return None


def judge_allowed(events: Events) -> str | None:
    responses = hook_responses(events, "PreToolUse:Bash")
    if not responses:
        return "PreToolUse:Bash hook never fired"
    bad = [r for r in responses if r.get("exit_code") != 0]
    if bad:
        return f"hook exit_code={bad[0].get('exit_code')}, stderr={bad[0].get('stderr', '')[:120]!r}"
    if any("blocked by ship-pr" in t for t in tool_results(events)):
        return "a tool_result carries a ship-pr block message"
    return None


def gate_block_stderrs(events: Events) -> list[str]:
    return [
        r.get("stderr", "") for r in hook_responses(events, "PreToolUse:Bash")
        if r.get("exit_code") == 2 and GATE_BLOCK in r.get("stderr", "")
    ]


def judge_gate_session_start(events: Events) -> str | None:
    outputs = [r.get("stdout", "") for r in hook_responses(events, "SessionStart")]
    if not any("verify_gate.ts run --skill" in o and str(PLUGIN) in o for o in outputs):
        return f"no SessionStart hook printed the gate run command: {outputs!r}"
    return None


def judge_gate_blocks_unverified(events: Events) -> str | None:
    blocks = gate_block_stderrs(events)
    if not blocks:
        return "no PreToolUse hook blocked the commit with the gate message"
    if "verify-demo" not in blocks[0] or "run --skill verify-demo" not in blocks[0]:
        return f"block message does not name the skill and the run command: {blocks[0][:200]!r}"
    if not any(GATE_BLOCK in t for t in tool_results(events)):
        return "hook blocked, but no tool_result carries the gate message"
    return None


def judge_gate_allows_verified(events: Events) -> str | None:
    if gate_block_stderrs(events):
        return "the gate blocked a commit after a passing run"
    results = tool_results(events)
    if not any("verify-demo VERIFIED" in t for t in results):
        return "the run command printed no `verify-demo VERIFIED` line"
    if not any("verified-change" in t and "[" in t for t in results):
        return "no tool_result shows the commit landing"
    return None


def judge_gate_blocks_stale(events: Events) -> str | None:
    blocks = gate_block_stderrs(events)
    if not blocks:
        return "no PreToolUse hook blocked the commit with the gate message"
    if "verify result is stale: files changed since the run" not in blocks[0]:
        return f"block message is not the stale message: {blocks[0][:200]!r}"
    return None


def judge_gate_allows_outside_paths(events: Events) -> str | None:
    if gate_block_stderrs(events):
        return "the gate blocked a commit outside src/**"
    if not any("docs-only-change" in t and "[" in t for t in tool_results(events)):
        return "no tool_result shows the commit landing"
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
    "gate-session-start": Feature(
        "Reply with the word ok.", judge_gate_session_start, GATE_FILES, [],
        {"SWE_VERIFY_GATE": "enforce"}, True,
    ),
    "gate-blocks-unverified": Feature(
        "Run these two commands in order, each once with the Bash tool. If one is blocked, stop.\n"
        "1. echo two | tee src/a.txt\n"
        "2. git commit -am blocked-change",
        judge_gate_blocks_unverified, GATE_FILES, GATE_TOOLS, {"SWE_VERIFY_GATE": "enforce"}, True,
    ),
    "gate-allows-verified": Feature(
        "Run these three commands in order, each once with the Bash tool. If one is blocked, stop.\n"
        "1. echo two | tee src/a.txt\n"
        f"2. {GATE_RUN}\n"
        "3. git commit -am verified-change",
        judge_gate_allows_verified, GATE_FILES, GATE_TOOLS, {"SWE_VERIFY_GATE": "enforce"}, True,
    ),
    "gate-blocks-stale": Feature(
        "Run these four commands in order, each once with the Bash tool. If one is blocked, stop.\n"
        "1. echo two | tee src/a.txt\n"
        f"2. {GATE_RUN}\n"
        "3. echo three | tee src/a.txt\n"
        "4. git commit -am stale-change",
        judge_gate_blocks_stale, GATE_FILES, GATE_TOOLS, {"SWE_VERIFY_GATE": "enforce"}, True,
    ),
    "gate-allows-outside-paths": Feature(
        "Run these two commands in order, each once with the Bash tool. If one is blocked, stop.\n"
        "1. echo two | tee docs/d.md\n"
        "2. git commit -am docs-only-change",
        judge_gate_allows_outside_paths, GATE_FILES, GATE_TOOLS, {"SWE_VERIFY_GATE": "enforce"}, True,
    ),
}


def run_session(name: str, feature: Feature, model: str | None) -> tuple[str, str | None]:
    repo = SCRATCH / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for filename, text in feature.files.items():
        (repo / filename).parent.mkdir(parents=True, exist_ok=True)
        (repo / filename).write_text(text)
    identity = {
        "GIT_AUTHOR_NAME": "Check", "GIT_AUTHOR_EMAIL": "check@example.com",
        "GIT_COMMITTER_NAME": "Check", "GIT_COMMITTER_EMAIL": "check@example.com",
    }
    if feature.commit_files:
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True, env={**os.environ, **identity},
        )
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
            stdin=subprocess.DEVNULL, env={**os.environ, **identity, **feature.env}, check=False,
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

    shutil.rmtree(SCRATCH, ignore_errors=True)
    SCRATCH.mkdir(parents=True)
    try:
        with ThreadPoolExecutor(max_workers=len(names)) as pool:
            results = list(pool.map(lambda n: run_session(n, FEATURES[n], args.model), names))
    finally:
        if not args.keep:
            shutil.rmtree(SCRATCH, ignore_errors=True)
    for name, problem in results:
        print(f"PASS {name}" if problem is None else f"FAIL {name}: {problem}")
    return 0 if all(p is None for _, p in results) else 1


if __name__ == "__main__":
    sys.exit(main())
