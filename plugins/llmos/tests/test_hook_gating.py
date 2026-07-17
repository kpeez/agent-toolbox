"""Prove the SessionStart/PreToolUse hook gates on path, not on intent, and
never reads provider memory (ADR-0003).

The hook is exercised as a real subprocess -- stdin JSON in, stdout out --
because that is exactly how both harnesses invoke it. `HOME` is redirected
into `tmp_path` so `vault_root.py`'s `~/.config/llmos/config.json` fallback
can never see the real machine's config.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "hooks" / "llmos_hook.py"

MEMORY_SENTINEL = "MEMORY-SENTINEL-DO-NOT-LEAK"
SCHEMA_SENTINEL = "SCHEMA-CONTRACT-SENTINEL"


def make_vault(root: Path) -> Path:
    """Build a minimal fake vault, plus the fixtures gating tests need."""
    (root / ".obsidian").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# fake vault\n")
    references = root / "agents" / "references"
    references.mkdir(parents=True)
    (references / "schema.md").write_text(SCHEMA_SENTINEL + "\n")
    memory_dir = root / "agents" / "claude"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text(MEMORY_SENTINEL + "\n")
    return root


def run_hook(
    event: str,
    payload: dict,
    tmp_path: Path,
    llmos_root: Path | None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    if llmos_root is not None:
        env["LLMOS_ROOT"] = str(llmos_root)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH), event],
        input=json.dumps(payload),
        env=env,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=10,
    )


def apply_patch_payload(*envelope_lines: str) -> dict:
    """A real Codex `apply_patch` call: targets live only inside the envelope."""
    body = "\n".join(("*** Begin Patch", *envelope_lines, "*** End Patch"))
    return {"tool_name": "apply_patch", "tool_input": {"command": body}}


def test_session_start_silent_outside_vault(tmp_path):
    vault = make_vault(tmp_path / "vault")
    outside = tmp_path / "elsewhere"
    outside.mkdir()

    result = run_hook("session-start", {"cwd": str(outside)}, tmp_path, vault)

    assert result.stdout == ""
    assert result.returncode == 0


def test_session_start_injects_inside_vault(tmp_path):
    vault = make_vault(tmp_path / "vault")

    result = run_hook("session-start", {"cwd": str(vault)}, tmp_path, vault)

    assert str(vault) in result.stdout
    assert "branch" in result.stdout.lower()
    assert "thoughts" in result.stdout.lower()
    assert result.returncode == 0


def test_session_start_names_daily_note_by_absolute_path(tmp_path):
    """The daily note must arrive as a full path, not a vault-relative one.

    A relative `reviews/daily/<today>.md` reads against the session's cwd, and
    a model handed one paraphrases it into a path that does not exist. Pin the
    whole absolute path so only a resolvable pointer passes.
    """
    vault = make_vault(tmp_path / "vault")
    daily_note = vault / "reviews" / "daily" / f"{date.today().isoformat()}.md"

    result = run_hook("session-start", {"cwd": str(vault)}, tmp_path, vault)

    assert str(daily_note) in result.stdout
    assert result.returncode == 0


def test_session_start_injects_no_memory(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")

    # 1. Subprocess check: verifying the hook still prints correct output
    # and has the sentinel not present in output.
    result = run_hook("session-start", {"cwd": str(vault)}, tmp_path, vault)

    assert str(vault) in result.stdout
    assert MEMORY_SENTINEL not in result.stdout
    assert result.returncode == 0

    # 2. Behavioral spy check: prove no MEMORY.md file is read by monkeypatching
    # Path.read_text, Path.open, and builtins.open to verify they are never
    # invoked on any file ending in MEMORY.md during session_start execution.
    import importlib.util
    import builtins

    spec = importlib.util.spec_from_file_location("llmos_hook", HOOK_PATH)
    llmos_hook = importlib.util.module_from_spec(spec)
    # Ensure vault_root is importable by updating sys.path via monkeypatch
    monkeypatch.syspath_prepend(str(HOOK_PATH.parent.parent / "scripts"))
    spec.loader.exec_module(llmos_hook)

    monkeypatch.setenv("LLMOS_ROOT", str(vault))

    accessed_files = []

    original_read_text = Path.read_text

    def mock_read_text(self, *args, **kwargs):
        accessed_files.append(self)
        return original_read_text(self, *args, **kwargs)

    original_open = Path.open

    def mock_path_open(self, *args, **kwargs):
        accessed_files.append(self)
        return original_open(self, *args, **kwargs)

    original_builtins_open = builtins.open

    def mock_builtins_open(file, *args, **kwargs):
        accessed_files.append(Path(file))
        return original_builtins_open(file, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", mock_read_text)
    monkeypatch.setattr(Path, "open", mock_path_open)
    monkeypatch.setattr(builtins, "open", mock_builtins_open)

    output = llmos_hook.session_start({"cwd": str(vault)})
    assert output is not None
    assert str(vault) in output

    for path in accessed_files:
        assert path.name != "MEMORY.md", f"MEMORY.md was read: {path}"


def test_pre_write_injects_for_symlinked_spec(tmp_path):
    vault = make_vault(tmp_path / "vault")
    project_docs = vault / "projects" / "testproj"
    (project_docs / "specs").mkdir(parents=True)
    spec = project_docs / "specs" / "foo.md"
    spec.write_text("# spec\n")

    # Mirrors the real topology: agent-toolbox/docs/agents is a symlink
    # pointing *out* of the repo, into the vault's project docs.
    repo = tmp_path / "agent-toolbox"
    repo.mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "docs" / "agents").symlink_to(project_docs, target_is_directory=True)
    symlinked_spec = repo / "docs" / "agents" / "specs" / "foo.md"

    result = run_hook(
        "pre-tool-use",
        {"tool_input": {"file_path": str(symlinked_spec)}},
        tmp_path,
        vault,
    )

    assert SCHEMA_SENTINEL in result.stdout
    assert result.returncode == 0


def test_pre_write_silent_for_non_vault_target(tmp_path):
    vault = make_vault(tmp_path / "vault")
    other_repo_file = tmp_path / "other-repo" / "src" / "main.py"
    other_repo_file.parent.mkdir(parents=True)
    other_repo_file.write_text("print('hi')\n")

    result = run_hook(
        "pre-tool-use",
        {"tool_input": {"file_path": str(other_repo_file)}},
        tmp_path,
        vault,
    )

    assert result.stdout == ""
    assert result.returncode == 0


def test_pre_write_silent_for_non_note_inside_vault(tmp_path):
    vault = make_vault(tmp_path / "vault")
    script = vault / "scripts" / "audit_metadata.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('x')\n")

    result = run_hook(
        "pre-tool-use",
        {"tool_input": {"file_path": str(script)}},
        tmp_path,
        vault,
    )

    assert result.stdout == ""
    assert result.returncode == 0


def make_spec(vault: Path, name: str) -> Path:
    spec = vault / "projects" / "testproj" / "specs" / name
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# spec\n")
    return spec


def test_pre_write_injects_for_codex_apply_patch(tmp_path):
    vault = make_vault(tmp_path / "vault")
    spec = make_spec(vault, "foo.md")

    result = run_hook(
        "pre-tool-use",
        apply_patch_payload(f"*** Update File: {spec}", "@@", "-a", "+b"),
        tmp_path,
        vault,
    )

    assert SCHEMA_SENTINEL in result.stdout
    assert result.returncode == 0


def test_pre_write_silent_for_codex_apply_patch_outside_vault(tmp_path):
    vault = make_vault(tmp_path / "vault")
    other_repo_file = tmp_path / "other-repo" / "README.md"
    other_repo_file.parent.mkdir(parents=True)
    other_repo_file.write_text("# hi\n")

    result = run_hook(
        "pre-tool-use",
        apply_patch_payload(f"*** Update File: {other_repo_file}", "@@", "-a", "+b"),
        tmp_path,
        vault,
    )

    assert result.stdout == ""
    assert result.returncode == 0


def test_pre_write_injects_once_when_codex_patch_touches_many_files(tmp_path):
    vault = make_vault(tmp_path / "vault")
    spec = make_spec(vault, "foo.md")
    outside = tmp_path / "other-repo" / "src" / "main.py"
    outside.parent.mkdir(parents=True)
    outside.write_text("print('hi')\n")

    result = run_hook(
        "pre-tool-use",
        apply_patch_payload(
            f"*** Update File: {outside}",
            "@@",
            "-a",
            "+b",
            f"*** Update File: {spec}",
            "@@",
            "-c",
            "+d",
        ),
        tmp_path,
        vault,
    )

    assert result.stdout.count(SCHEMA_SENTINEL) == 1
    assert result.returncode == 0


def test_pre_write_injects_for_codex_add_file(tmp_path):
    vault = make_vault(tmp_path / "vault")
    new_spec = vault / "projects" / "testproj" / "specs" / "0001-new.md"
    new_spec.parent.mkdir(parents=True)

    result = run_hook(
        "pre-tool-use",
        apply_patch_payload(f"*** Add File: {new_spec}", "+# new spec"),
        tmp_path,
        vault,
    )

    assert SCHEMA_SENTINEL in result.stdout
    assert result.returncode == 0


def test_pre_write_injects_for_codex_relative_patch_path(tmp_path):
    # Codex names patch targets relative to the session's working directory.
    vault = make_vault(tmp_path / "vault")
    make_spec(vault, "foo.md")
    cwd = vault / "projects" / "testproj"

    result = run_hook(
        "pre-tool-use",
        apply_patch_payload("*** Update File: specs/foo.md", "@@", "-a", "+b"),
        tmp_path,
        vault,
        cwd=cwd,
    )

    assert SCHEMA_SENTINEL in result.stdout
    assert result.returncode == 0


def test_pre_write_injects_on_the_only_channel_the_model_reads(tmp_path):
    """PreToolUse must inject via JSON; its plain stdout never reaches a model.

    Both harnesses drop a PreToolUse hook's bare stdout into the transcript and
    hand the model nothing. `hookSpecificOutput.additionalContext` is the sole
    supported injection point. Every other test here asserts the schema merely
    *appears in stdout*, which stayed true for months while the contract in fact
    reached no one -- so this is the assertion that has to pin the envelope.
    """
    vault = make_vault(tmp_path / "vault")
    spec = make_spec(vault, "foo.md")

    result = run_hook(
        "pre-tool-use",
        {"tool_input": {"file_path": str(spec)}},
        tmp_path,
        vault,
    )

    specific = json.loads(result.stdout)["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert SCHEMA_SENTINEL in specific["additionalContext"]
    assert result.returncode == 0


def test_session_start_injects_as_bare_stdout(tmp_path):
    """SessionStart is the one event whose bare stdout is added to context.

    Wrapping it in the PreToolUse envelope would show the model the JSON rather
    than the message, so the two events must not converge on one shape.
    """
    vault = make_vault(tmp_path / "vault")

    result = run_hook("session-start", {"cwd": str(vault)}, tmp_path, vault)

    assert "hookSpecificOutput" not in result.stdout
    assert str(vault) in result.stdout
    assert result.returncode == 0


def test_pre_write_non_blocking_when_vault_unconfigured(tmp_path):
    # No LLMOS_ROOT and no ~/.config/llmos/config.json (HOME is redirected
    # into tmp_path): vault_root() sys.exits internally. The hook must
    # swallow that and stay a no-op, never a blocked tool call.
    target = tmp_path / "some-other-repo" / "src" / "main.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hi')\n")

    result = run_hook(
        "pre-tool-use",
        {"tool_input": {"file_path": str(target)}},
        tmp_path,
        None,
    )

    assert result.returncode == 0
    assert result.stdout == ""
