"""Prove the Bash guard's Rule B: `mv`/`git mv`/`rm` whose resolved target is a
`.md` file under any known vault root are denied (spec 0014, behavior 2).

Known vault roots = the llmOS root (`$LLMOS_ROOT`) plus every vault in
Obsidian's own registry (llmOS + xbrain). Both are redirected into `tmp_path`
fixtures -- `HOME` for the registry file, `LLMOS_ROOT` for the configured
root -- so this suite never touches the operator's real vaults.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "hooks" / "guard_bash.py"


def make_vault(root: Path) -> Path:
    (root / ".obsidian").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# fake vault\n")
    return root


def write_registry(home: Path, vaults: dict[str, Path]) -> None:
    registry_dir = home / "Library" / "Application Support" / "obsidian"
    registry_dir.mkdir(parents=True)
    registry = {
        "vaults": {
            key: {"path": str(path), "ts": i}
            for i, (key, path) in enumerate(vaults.items())
        }
    }
    (registry_dir / "obsidian.json").write_text(json.dumps(registry))


def run_guard(
    command: str,
    tmp_path: Path,
    home: Path,
    llmos_root: Path | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    if llmos_root is not None:
        env["LLMOS_ROOT"] = str(llmos_root)
    payload = {"tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )


def test_mv_note_out_of_llmos_root_denied(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text("# note\n")

    result = run_guard(f"mv {note} /tmp/dest/", tmp_path, home, llmos_root=vault)

    assert result.returncode == 2
    assert "obsidian-cli move" in result.stderr


def test_git_mv_inside_vault_denied(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    src = vault / "a.md"
    src.write_text("# a\n")

    result = run_guard(
        f"git mv {src} {vault / 'b.md'}", tmp_path, home, llmos_root=vault
    )

    assert result.returncode == 2
    assert "obsidian-cli move" in result.stderr or "obsidian-cli rename" in result.stderr


def test_rm_vault_note_denied(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text("# note\n")

    result = run_guard(f"rm {note}", tmp_path, home, llmos_root=vault)

    assert result.returncode == 2
    assert str(note) in result.stderr


def test_mv_outside_every_vault_root_allowed(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    outside = tmp_path / "other" / "note.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("# note\n")

    result = run_guard(
        f"mv {outside} /tmp/dest/", tmp_path, home, llmos_root=vault
    )

    assert result.returncode == 0
    assert result.stderr == ""


def test_rm_outside_every_vault_root_allowed(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    outside = tmp_path / "other" / "note.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("# note\n")

    result = run_guard(f"rm {outside}", tmp_path, home, llmos_root=vault)

    assert result.returncode == 0
    assert result.stderr == ""


def test_mv_non_markdown_file_in_vault_allowed(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    asset = vault / "image.png"
    asset.write_text("binary-ish\n")

    result = run_guard(f"mv {asset} /tmp/dest/", tmp_path, home, llmos_root=vault)

    assert result.returncode == 0
    assert result.stderr == ""


def test_registry_only_vault_denied(tmp_path):
    """A vault known only via Obsidian's registry (e.g. xbrain) is still guarded."""
    home = tmp_path / "home"
    home.mkdir()
    xbrain = make_vault(tmp_path / "xbrain")
    write_registry(home, {"xbrain-id": xbrain})
    note = xbrain / "note.md"
    note.write_text("# note\n")

    result = run_guard(f"rm {note}", tmp_path, home)

    assert result.returncode == 2
    assert str(note) in result.stderr


def test_compound_command_catches_offending_mv(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text("# note\n")

    result = run_guard(
        f"cd /tmp && rm {note}", tmp_path, home, llmos_root=vault
    )

    assert result.returncode == 2
    assert str(note) in result.stderr


def test_relative_path_resolved_against_cwd(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text("# note\n")

    result = run_guard(
        "mv note.md /tmp/dest/", tmp_path, home, llmos_root=vault, cwd=vault
    )

    assert result.returncode == 2
    assert "obsidian-cli move" in result.stderr


def test_fails_open_when_no_vault_configured(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    outside_vault_but_md = tmp_path / "somewhere" / "note.md"
    outside_vault_but_md.parent.mkdir(parents=True)
    outside_vault_but_md.write_text("# note\n")

    result = run_guard(f"rm {outside_vault_but_md}", tmp_path, home)

    assert result.returncode == 0
    assert result.stderr == ""


def test_ordinary_mv_and_rm_calls_unaffected(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    src = tmp_path / "build" / "output.txt"
    src.parent.mkdir(parents=True)
    src.write_text("data\n")

    result = run_guard(f"mv {src} {tmp_path / 'dest.txt'}", tmp_path, home, llmos_root=vault)

    assert result.returncode == 0
    assert result.stderr == ""


def test_redirect_into_vault_md_allowed(tmp_path):
    """A shell redirection operand is not an mv/rm target -- only mv/rm's own
    positional args are (spec 0014 Risks: guard false positives)."""
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    old = tmp_path / "old.txt"
    old.write_text("data\n")

    result = run_guard(
        f"mv {old} {tmp_path / 'new.txt'} > {vault / 'notes' / 'log.md'}",
        tmp_path,
        home,
        llmos_root=vault,
    )

    assert result.returncode == 0
    assert result.stderr == ""


def test_real_mv_target_denied_even_with_trailing_redirect(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text("# note\n")

    result = run_guard(
        f"mv {note} /tmp/dest.md > {tmp_path / 'log.txt'}",
        tmp_path,
        home,
        llmos_root=vault,
    )

    assert result.returncode == 2
    assert str(note) in result.stderr


def test_glued_double_ampersand_catches_offending_rm(tmp_path):
    """shlex glues `hi&&rm` into one token without whitespace around `&&`;
    the guard must still split it and catch the `rm` (spec 0014 Risks)."""
    home = tmp_path / "home"
    home.mkdir()
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text("# note\n")

    result = run_guard(f"echo hi&&rm {note}", tmp_path, home, llmos_root=vault)

    assert result.returncode == 2
    assert str(note) in result.stderr


def test_no_vault_filesystem_access_on_fast_path(tmp_path, monkeypatch):
    """Ordinary commands must never touch vault_root/registered_vaults at all."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("guard_bash", HOOK_PATH)
    guard_bash = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(HOOK_PATH.parent.parent))
    spec.loader.exec_module(guard_bash)

    def _boom():
        raise AssertionError("vault I/O touched on the fast path")

    monkeypatch.setattr(guard_bash, "vault_root", _boom)
    monkeypatch.setattr(guard_bash, "registered_vaults", _boom)

    for command in ("git status", "uv run pytest", "ls -la", "npm install"):
        assert guard_bash.check_command(command, ".") is None
