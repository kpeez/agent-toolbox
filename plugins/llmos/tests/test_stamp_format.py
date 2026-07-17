"""Prove the PostToolUse stamp hook (spec 0014 behavior 3): normalizes vault
markdown, stamps `updated`, appends the provider to `authors` exactly once
(idempotent), and flags the qmd collection dirty. Non-vault writes and notes
without a frontmatter block are untouched. Exercised as a subprocess -- stdin
JSON in, mutated file on disk out -- the same way both harnesses invoke it.
`TMPDIR` is redirected into `tmp_path` so the dirty-flag scratch dir never
touches the operator's real temp directory.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "hooks" / "llmos_stamp_hook.py"

MESSY_NOTE = (
    "---\n"
    "created: 2026-07-01\n"
    "categories:\n"
    '  - "[[Knowledge]]"\n'
    "---\n"
    "# A note\n"
    "\n"
    "Body content, with a wikilink to [[Some Other Note]].\n"
)

NO_FRONTMATTER_NOTE = "# Just a note\n\nNo frontmatter here.\n"


def make_vault(root: Path) -> Path:
    (root / ".obsidian").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# fake vault\n")
    return root


def run_hook(
    payload: dict,
    tmp_path: Path,
    llmos_root: Path,
    provider_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "LLMOS_ROOT": str(llmos_root),
        "TMPDIR": str(scratch),
    }
    if provider_env:
        env.update(provider_env)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )


def dirty_flag(tmp_path: Path, session_id: str) -> Path:
    return tmp_path / "scratch" / "llmos-hooks" / session_id / "llmos.dirty"


def test_stamps_updated_and_appends_provider(tmp_path):
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text(MESSY_NOTE)

    result = run_hook(
        {"session_id": "sess-1", "tool_input": {"file_path": str(note)}},
        tmp_path,
        vault,
        provider_env={"CLAUDECODE": "1"},
    )

    assert result.returncode == 0
    text = note.read_text()
    assert f"updated: {date.today().isoformat()}" in text
    assert "  - claude" in text
    assert "created: 2026-07-01" in text


def test_authors_append_is_idempotent(tmp_path):
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text(MESSY_NOTE)
    payload = {"session_id": "sess-1", "tool_input": {"file_path": str(note)}}

    run_hook(payload, tmp_path, vault, provider_env={"CLAUDECODE": "1"})
    once = note.read_text()
    run_hook(payload, tmp_path, vault, provider_env={"CLAUDECODE": "1"})
    twice = note.read_text()

    assert once == twice
    assert once.count("claude") == 1


def test_normalizes_frontmatter(tmp_path):
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text(MESSY_NOTE)

    result = run_hook(
        {"session_id": "sess-1", "tool_input": {"file_path": str(note)}},
        tmp_path,
        vault,
    )

    assert result.returncode == 0
    text = note.read_text()
    assert "\n---\n\n#" in text
    for line in text.splitlines():
        assert line == line.rstrip()


def test_created_is_never_modified(tmp_path):
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text(MESSY_NOTE)

    run_hook(
        {"session_id": "sess-1", "tool_input": {"file_path": str(note)}},
        tmp_path,
        vault,
    )

    assert "created: 2026-07-01" in note.read_text()


def test_sets_dirty_flag_for_vault_write(tmp_path):
    vault = make_vault(tmp_path / "vault")
    note = vault / "note.md"
    note.write_text(MESSY_NOTE)

    run_hook(
        {"session_id": "sess-1", "tool_input": {"file_path": str(note)}},
        tmp_path,
        vault,
    )

    assert dirty_flag(tmp_path, "sess-1").exists()


def test_non_vault_write_untouched_and_sets_no_flag(tmp_path):
    vault = make_vault(tmp_path / "vault")
    outside = tmp_path / "other-repo" / "README.md"
    outside.parent.mkdir(parents=True)
    original = "# hello\n"
    outside.write_text(original)

    run_hook(
        {"session_id": "sess-1", "tool_input": {"file_path": str(outside)}},
        tmp_path,
        vault,
    )

    assert outside.read_text() == original
    assert not dirty_flag(tmp_path, "sess-1").exists()


def test_note_without_frontmatter_is_untouched(tmp_path):
    vault = make_vault(tmp_path / "vault")
    note = vault / "plain.md"
    note.write_text(NO_FRONTMATTER_NOTE)

    result = run_hook(
        {"session_id": "sess-1", "tool_input": {"file_path": str(note)}},
        tmp_path,
        vault,
    )

    assert result.returncode == 0
    assert note.read_text() == NO_FRONTMATTER_NOTE
    assert not dirty_flag(tmp_path, "sess-1").exists()


def test_non_blocking_when_vault_unconfigured(tmp_path):
    target = tmp_path / "some-repo" / "note.md"
    target.parent.mkdir(parents=True)
    target.write_text(MESSY_NOTE)
    home = tmp_path / "home"
    home.mkdir()
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "TMPDIR": str(tmp_path / "scratch"),
    }

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(
            {"session_id": "sess-1", "tool_input": {"file_path": str(target)}}
        ),
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert target.read_text() == MESSY_NOTE
