"""Prove the obsidian-cli write backend (spec 0014 behavior 9): mutations
raise `ObsidianNotRunning` when the app cannot be reached, every generated
invocation names `file=` or `path=`, multi-line content stages through a real
temp file and round-trips losslessly, and the CLI maps the exception to a
distinct exit code. Reads must keep working headless regardless -- unit
tests here never invoke the real `obsidian-cli` binary; the subprocess
boundary is always mocked.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from llmos_vault import mutations, obsidian_cli
from llmos_vault.notes import Note, read_note
from llmos_vault.obsidian_cli import EXIT_OBSIDIAN_NOT_RUNNING, ObsidianNotRunning, run

VAULT = Path("/vault/llmOS")
FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"


def ok(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def failed(stderr: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def capture_argv(store: dict) -> Callable:
    def fake_run(argv, **kwargs):
        store["argv"] = argv
        return ok()

    return fake_run


def capture_call(store: dict) -> Callable:
    def fake_call(*args, **kwargs):
        store["args"] = args
        store["kwargs"] = kwargs
        return "ok"

    return fake_call


def note_with_authors(authors: list[str]) -> Note:
    return Note(path=VAULT / "alpha.md", name="alpha", properties={"authors": authors}, body="")


# -- invocation construction --------------------------------------------


def test_run_names_vault_verb_and_file_target(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return ok("done\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    run(VAULT, "move", file="alpha", params={"to": "archive/alpha.md"})

    assert captured["argv"] == [
        "obsidian-cli",
        "vault=llmOS",
        "move",
        "file=alpha",
        "to=archive/alpha.md",
    ]


def test_run_names_path_target(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", capture_argv(captured))

    run(VAULT, "create", path="notes/new.md")

    assert "path=notes/new.md" in captured["argv"]


def test_run_requires_file_or_path():
    with pytest.raises(ValueError, match="file=|path="):
        run(VAULT, "read")


def test_run_rejects_both_file_and_path():
    with pytest.raises(ValueError, match="exactly one"):
        run(VAULT, "read", file="alpha", path="notes/alpha.md")


# -- content staging (single-line vs. temp-file) -------------------------


def test_single_line_content_is_not_staged_via_temp_file(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: ok())

    def boom(*args, **kwargs):
        raise AssertionError("single-line content must not be staged through a temp file")

    monkeypatch.setattr(obsidian_cli.tempfile, "NamedTemporaryFile", boom)

    run(VAULT, "append", file="alpha", content="one line")


def test_multiline_content_round_trips_losslessly_through_temp_file(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", capture_argv(captured))

    content = 'Line one\nLine "two" with [[Wikilink]]\nLine three\ttabbed'

    run(VAULT, "append", file="alpha", content=content)

    assert f"content={content}" in captured["argv"]


def test_multiline_content_temp_file_is_cleaned_up(monkeypatch):
    written_paths = []
    real_named_temp_file = obsidian_cli.tempfile.NamedTemporaryFile

    def spy_named_temp_file(*args, **kwargs):
        tmp = real_named_temp_file(*args, **kwargs)
        written_paths.append(Path(tmp.name))
        return tmp

    monkeypatch.setattr(obsidian_cli.tempfile, "NamedTemporaryFile", spy_named_temp_file)
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: ok())

    run(VAULT, "append", file="alpha", content="line one\nline two")

    assert written_paths
    assert not written_paths[0].exists()


# -- ObsidianNotRunning: loud, named failure -----------------------------


def test_missing_binary_raises_obsidian_not_running(monkeypatch):
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("obsidian-cli")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ObsidianNotRunning):
        run(VAULT, "read", file="alpha")


@pytest.mark.parametrize(
    "stderr",
    [
        "Error: connection refused",
        "Error: Obsidian is not running",
        "Error: could not connect to Obsidian",
    ],
)
def test_connection_failure_raises_obsidian_not_running(monkeypatch, stderr):
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: failed(stderr))

    with pytest.raises(ObsidianNotRunning):
        run(VAULT, "read", file="alpha")


def test_other_cli_failures_raise_plain_error_not_obsidian_not_running(monkeypatch):
    message = 'Error: File "ghost" not found.'
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: failed(message))

    with pytest.raises(RuntimeError) as exc_info:
        run(VAULT, "read", file="ghost")

    assert not isinstance(exc_info.value, ObsidianNotRunning)


def test_successful_call_returns_stdout(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: ok("Moved: a.md -> b.md\n"))

    result = run(VAULT, "move", file="alpha", params={"to": "b.md"})

    assert result == "Moved: a.md -> b.md\n"


def test_reads_stay_headless_even_when_obsidian_is_unreachable(monkeypatch):
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("obsidian-cli")

    monkeypatch.setattr(subprocess, "run", fake_run)

    note = read_note(FIXTURE_VAULT, "alpha")

    assert note.name == "alpha"


# -- mutation verbs -------------------------------------------------------


def test_create_note_targets_path_and_appends_md_suffix(monkeypatch):
    captured = {}
    monkeypatch.setattr(mutations, "run", capture_call(captured))

    mutations.create_note(VAULT, "projects/new-note", template="project")

    assert captured["kwargs"]["path"] == "projects/new-note.md"
    assert captured["kwargs"]["params"] == {"template": "project"}


def test_move_note_targets_file_and_destination(monkeypatch):
    captured = {}
    monkeypatch.setattr(mutations, "run", capture_call(captured))

    mutations.move_note(VAULT, "alpha", "archive/alpha.md")

    assert captured["kwargs"]["file"] == "alpha"
    assert captured["kwargs"]["params"] == {"to": "archive/alpha.md"}


def test_append_note_targets_file_and_content(monkeypatch):
    captured = {}
    monkeypatch.setattr(mutations, "run", capture_call(captured))

    mutations.append_note(VAULT, "alpha", "more content")

    assert captured["kwargs"]["file"] == "alpha"
    assert captured["kwargs"]["content"] == "more content"


def test_set_property_targets_file_name_and_value(monkeypatch):
    captured = {}
    monkeypatch.setattr(mutations, "run", capture_call(captured))

    mutations.set_property(VAULT, "alpha", "status", "active")

    assert captured["kwargs"]["file"] == "alpha"
    assert captured["kwargs"]["params"] == {"name": "status", "value": "active"}


def test_set_property_refuses_created(monkeypatch):
    monkeypatch.setattr(mutations, "run", lambda *a, **kw: pytest.fail("run must not be called"))

    with pytest.raises(ValueError, match="immutable"):
        mutations.set_property(VAULT, "alpha", "created", "2026-01-01")


def test_set_property_merges_authors_instead_of_overwriting(monkeypatch):
    captured = {}
    monkeypatch.setattr(mutations, "run", capture_call(captured))
    monkeypatch.setattr(mutations, "read_note", lambda root, note: note_with_authors(["claude"]))

    mutations.set_property(VAULT, "alpha", "authors", "codex")

    expected = {"name": "authors", "value": "claude,codex", "type": "list"}
    assert captured["kwargs"]["params"] == expected


def test_set_property_authors_is_idempotent(monkeypatch):
    captured = {}
    monkeypatch.setattr(mutations, "run", capture_call(captured))
    monkeypatch.setattr(mutations, "read_note", lambda root, note: note_with_authors(["claude"]))

    mutations.set_property(VAULT, "alpha", "authors", "claude")

    assert captured["kwargs"]["params"]["value"] == "claude"


def test_remove_property_targets_file_and_name(monkeypatch):
    captured = {}
    monkeypatch.setattr(mutations, "run", capture_call(captured))

    mutations.remove_property(VAULT, "alpha", "status")

    assert captured["kwargs"]["file"] == "alpha"
    assert captured["kwargs"]["params"] == {"name": "status"}


def test_remove_property_refuses_created(monkeypatch):
    monkeypatch.setattr(mutations, "run", lambda *a, **kw: pytest.fail("run must not be called"))

    with pytest.raises(ValueError, match="immutable"):
        mutations.remove_property(VAULT, "alpha", "created")


# -- CLI exit code mapping ------------------------------------------------


def test_cli_maps_obsidian_not_running_to_distinct_exit_code(monkeypatch, capsys):
    from llmos_vault import cli

    def raise_not_running(*args, **kwargs):
        message = "obsidian-cli could not reach a running Obsidian app: connection refused"
        raise ObsidianNotRunning(message)

    monkeypatch.setattr(cli, "app", raise_not_running)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == EXIT_OBSIDIAN_NOT_RUNNING
    assert exc_info.value.code != 0
    assert "connection refused" in capsys.readouterr().err


def test_obsidian_not_running_exit_code_is_distinct_from_success_and_generic_error():
    assert EXIT_OBSIDIAN_NOT_RUNNING not in (0, 1)
