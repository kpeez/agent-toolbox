"""Prove the PreToolUse hook refuses to publish agent attribution.

The rule already exists in ship-pr's prose, and prose did not hold: session
URLs and "Generated with" footers kept reaching commits, where they cannot be
rewritten after a push. Every case runs the real hook against the real stdin
envelope the harness sends.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "swe"
    / "hooks"
    / "block-agent-attribution.sh"
)

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="jq is required")


def run_hook(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HOOK)],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True,
        text=True,
    )


CLEAN = [
    'git commit -m "Add wave stacking to the conductor"',
    "gh pr create --draft --title 'Stack the waves' --body 'Reviewer guide: ...'",
    # Not a publishing verb: the guard must not police every mention of the URL.
    "curl -s https://claude.ai/foo",
    "grep -rn claude.ai docs/",
]


@pytest.mark.parametrize("command", CLEAN)
def test_clean_publishing_commands_pass(command: str) -> None:
    assert run_hook(command).returncode == 0


BLOCKED = [
    pytest.param(
        'git commit -m "Fix auth\n\nSession: https://claude.ai/chat/abc-123"',
        id="session-url",
    ),
    pytest.param(
        'git commit -m "Fix auth\n\nCo-authored-by: Claude <noreply@anthropic.com>"',
        id="co-authored-by",
    ),
    pytest.param(
        "gh pr create --body 'Generated with Claude Code'",
        id="generated-with",
    ),
    pytest.param("gh pr edit 4 --body '🤖 done'", id="robot"),
    pytest.param(
        "gh stack link --base main a b --body 'see https://claude.com/x'",
        id="claude-com-url",
    ),
]


@pytest.mark.parametrize("command", BLOCKED)
def test_attribution_is_blocked(command: str) -> None:
    result = run_hook(command)
    # Exit 2 is what feeds the refusal back to the agent; anything else lets the
    # commit through.
    assert result.returncode == 2, result.stdout
    assert "agent attribution" in result.stderr


def test_a_body_file_is_inspected_too(tmp_path: Path) -> None:
    # The failure mode this covers: the body never appears in the command
    # string, so grepping the command alone would wave it through.
    body = tmp_path / "body.md"
    body.write_text("Nice change.\n\nGenerated with Claude Code\n")
    result = run_hook(f"gh pr create --draft --body-file {body}")
    assert result.returncode == 2, result.stdout


def test_a_non_bash_envelope_is_ignored() -> None:
    result = subprocess.run(
        [str(HOOK)],
        input=json.dumps({"tool_input": {"file_path": "/tmp/x.py"}}),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
