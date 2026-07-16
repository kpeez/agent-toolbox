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
    event: str, payload: dict, tmp_path: Path, llmos_root: Path | None
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
        text=True,
        capture_output=True,
        timeout=10,
    )


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
    assert "receipt" in result.stdout.lower()
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
    project_docs = vault / "projects" / "testproj" / "docs"
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
