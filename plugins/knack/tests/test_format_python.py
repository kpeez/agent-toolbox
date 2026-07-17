"""Prove the PostToolUse formatter runs on both harnesses' payload shapes.

The hook is exercised as a real subprocess -- stdin JSON in, exit code out --
against a real uv+ruff project on disk, because every previous claim about this
hook was true of our own config and false of the running system: the matcher
`Write|Edit|MultiEdit` does match Codex's `apply_patch`, so Codex dispatched the
hook faithfully for months while `.tool_input.file_path` came back empty and the
script exited 0 before ruff ever ran. A test that reads our JSON, or mocks ruff,
cannot fail when that happens. So these assert the only thing that distinguishes
"formatted" from "silently skipped": the bytes on disk afterwards.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "hooks" / "format-python.sh"

UNFORMATTED = "s = 'hello'\n"
FORMATTED = 's = "hello"\n'


def make_project(root: Path) -> Path:
    """A minimal git repo that opts into the hook's uv + ruff guards."""
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "probe"\nversion = "0.1.0"\nrequires-python = ">=3.9"\n\n[tool.ruff]\n'
    )
    return root


def run_hook(payload: dict, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(HOOK_PATH)],
        input=json.dumps(payload),
        env={**os.environ, "HOME": str(cwd)},
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=60,
    )


def apply_patch_payload(*envelope_lines: str) -> dict:
    """A real Codex `apply_patch` call: targets live only inside the envelope.

    Verbatim shape of what Codex sends. There is no `file_path` key anywhere --
    that absence is the whole bug, so it must not be papered over here.
    """
    body = "\n".join(("*** Begin Patch", *envelope_lines, "*** End Patch"))
    return {"tool_name": "apply_patch", "tool_input": {"command": body}}


def test_formats_codex_apply_patch_target(tmp_path):
    """The regression pin: a Codex patch envelope names the file, and only it."""
    project = make_project(tmp_path / "probe")
    target = project / "quotes.py"
    target.write_text(UNFORMATTED)

    result = run_hook(
        apply_patch_payload("*** Update File: quotes.py", "@@", "-x", "+y"),
        cwd=project,
    )

    assert target.read_text() == FORMATTED
    assert result.returncode == 0


def test_formats_codex_add_file(tmp_path):
    project = make_project(tmp_path / "probe")
    target = project / "hello2.py"
    target.write_text(UNFORMATTED)

    result = run_hook(
        apply_patch_payload("*** Add File: hello2.py", "+s = 'hello'"), cwd=project
    )

    assert target.read_text() == FORMATTED
    assert result.returncode == 0


def test_formats_every_file_one_codex_patch_names(tmp_path):
    """One apply_patch may touch several files; Claude's Write never does."""
    project = make_project(tmp_path / "probe")
    (project / "pkg").mkdir()
    first = project / "one.py"
    second = project / "pkg" / "two.py"
    first.write_text(UNFORMATTED)
    second.write_text(UNFORMATTED)

    result = run_hook(
        apply_patch_payload(
            "*** Update File: one.py",
            "@@",
            "-x",
            "+y",
            "*** Add File: pkg/two.py",
            "+s = 'hello'",
        ),
        cwd=project,
    )

    assert first.read_text() == FORMATTED
    assert second.read_text() == FORMATTED
    assert result.returncode == 0


def test_codex_patch_paths_resolve_against_cwd_not_repo_root(tmp_path):
    """Codex names targets relative to the session cwd, which need not be the
    repo root -- and the hook cd's to the root before invoking ruff."""
    project = make_project(tmp_path / "probe")
    nested = project / "pkg"
    nested.mkdir()
    target = nested / "deep.py"
    target.write_text(UNFORMATTED)

    result = run_hook(
        apply_patch_payload("*** Update File: deep.py", "@@", "-x", "+y"),
        cwd=nested,
    )

    assert target.read_text() == FORMATTED
    assert result.returncode == 0


def test_formats_claude_file_path_target(tmp_path):
    """Claude's shape must keep working: one absolute `file_path`, no envelope."""
    project = make_project(tmp_path / "probe")
    target = project / "quotes.py"
    target.write_text(UNFORMATTED)

    result = run_hook(
        {"tool_name": "Edit", "tool_input": {"file_path": str(target)}}, cwd=project
    )

    assert target.read_text() == FORMATTED
    assert result.returncode == 0


def test_lint_failure_from_codex_patch_exits_2(tmp_path):
    """exit 2 is how a lint failure reaches the model; formatting alone is mute."""
    project = make_project(tmp_path / "probe")
    target = project / "unused.py"
    target.write_text("import os\n")

    result = run_hook(
        apply_patch_payload("*** Add File: unused.py", "+import os"),
        cwd=project,
    )

    assert result.returncode == 2
    assert "F401" in result.stdout


def test_silent_for_non_python_codex_target(tmp_path):
    project = make_project(tmp_path / "probe")
    target = project / "README.md"
    target.write_text("#  hi\n")

    result = run_hook(
        apply_patch_payload("*** Update File: README.md", "@@", "-x", "+y"),
        cwd=project,
    )

    assert target.read_text() == "#  hi\n"
    assert result.returncode == 0


def test_silent_outside_a_ruff_project(tmp_path):
    """The opt-in guard: a git repo whose pyproject has no [tool.ruff]."""
    project = tmp_path / "plain"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "pyproject.toml").write_text(
        '[project]\nname = "plain"\nversion = "0.1.0"\n'
    )
    target = project / "quotes.py"
    target.write_text(UNFORMATTED)

    result = run_hook(
        apply_patch_payload("*** Update File: quotes.py", "@@", "-x", "+y"),
        cwd=project,
    )

    assert target.read_text() == UNFORMATTED
    assert result.returncode == 0
