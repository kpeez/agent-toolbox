"""Prove the Bash guard's Rule A: obsidian-cli invocations of a note-operating
verb that name neither `file=` nor `path=` are denied (spec 0014, behavior 1).

Exercised as a real subprocess -- stdin JSON in, exit code + stderr out --
because that is exactly the PreToolUse deny contract: exit 2 with the message
on stderr blocks the tool call. `HOME` is redirected into `tmp_path` so this
suite never touches the operator's real vault config.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "hooks" / "guard_bash.py"


def run_guard(
    command: str, tmp_path: Path, cwd: str | None = None
) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    payload = {"tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = cwd
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )


def test_denies_read_with_no_target(tmp_path):
    result = run_guard("obsidian-cli read", tmp_path)

    assert result.returncode == 2
    assert "file=" in result.stderr
    assert "path=" in result.stderr


def test_allows_read_with_file_target(tmp_path):
    result = run_guard('obsidian-cli read file="My Note"', tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_allows_read_with_path_target(tmp_path):
    result = run_guard('obsidian-cli read path="notes/my-note.md"', tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


@pytest.mark.parametrize(
    "verb",
    [
        "read",
        "append",
        "prepend",
        "delete",
        "move",
        "rename",
        "backlinks",
        "links",
        "outline",
        "file",
        "wordcount",
        "property:read",
        "property:set",
        "property:remove",
        "diff",
        "history",
    ],
)
def test_denies_note_targeting_verbs_without_target(verb, tmp_path):
    result = run_guard(f"obsidian-cli {verb}", tmp_path)

    assert result.returncode == 2, verb
    assert "obsidian-cli" in result.stderr


@pytest.mark.parametrize(
    "verb",
    [
        "read",
        "append",
        "delete",
        "move",
        "rename",
        "backlinks",
        "property:set",
    ],
)
def test_allows_note_targeting_verbs_with_target(verb, tmp_path):
    result = run_guard(f'obsidian-cli {verb} file="My Note"', tmp_path)

    assert result.returncode == 0, verb
    assert result.stderr == ""


@pytest.mark.parametrize(
    "command",
    [
        "obsidian-cli vaults",
        "obsidian-cli daily:read",
        'obsidian-cli daily:append content="- [ ] task"',
        "obsidian-cli help",
        "obsidian-cli help read",
        "obsidian-cli dev:errors",
        "obsidian-cli dev:console",
        'obsidian-cli search query="term"',
        "obsidian-cli tasks",
        "obsidian-cli tags",
        "obsidian-cli properties",
        "obsidian-cli aliases",
        "obsidian-cli files",
        "obsidian-cli folders",
        "obsidian-cli vault",
        "obsidian-cli version",
        'obsidian-cli vault="llmOS" vaults',
    ],
)
def test_allows_targetless_by_design_commands(command, tmp_path):
    result = run_guard(command, tmp_path)

    assert result.returncode == 0, command
    assert result.stderr == ""


def test_vault_prefix_before_verb_still_denies(tmp_path):
    result = run_guard('obsidian-cli vault="llmOS" read', tmp_path)

    assert result.returncode == 2
    assert "file=" in result.stderr


def test_vault_prefix_before_verb_still_allows_with_target(tmp_path):
    result = run_guard('obsidian-cli vault="llmOS" read file="My Note"', tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_compound_command_catches_offending_invocation(tmp_path):
    result = run_guard("echo hi && obsidian-cli read", tmp_path)

    assert result.returncode == 2
    assert "file=" in result.stderr


def test_compound_command_with_target_allowed(tmp_path):
    result = run_guard('obsidian-cli read file="x" && echo done', tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "uv run pytest plugins/llmos/tests/",
        "ls -la",
        "git commit -m 'message'",
        "uv run ruff check .",
        "npm install",
    ],
)
def test_allows_ordinary_commands(command, tmp_path):
    result = run_guard(command, tmp_path)

    assert result.returncode == 0, command
    assert result.stderr == ""


def test_unparseable_command_fails_open(tmp_path):
    result = run_guard('obsidian-cli read file="unterminated', tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_malformed_stdin_fails_open(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not json",
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert result.stderr == ""


def test_no_command_in_tool_input_fails_open(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"tool_input": {}}),
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert result.stderr == ""
