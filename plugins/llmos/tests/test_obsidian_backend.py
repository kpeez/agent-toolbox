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

from llmos_vault import mutations
from llmos_vault.notes import Note
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


# -- content staging (single-line vs. temp-file) -------------------------


def test_multiline_content_round_trips_losslessly_through_temp_file(monkeypatch):
    captured = {}
    monkeypatch.setattr(subprocess, "run", capture_argv(captured))

    content = 'Line one\nLine "two" with [[Wikilink]]\nLine three\ttabbed'

    run(VAULT, "append", file="alpha", content=content)

    assert f"content={content}" in captured["argv"]


# -- ObsidianNotRunning: loud, named failure -----------------------------


@pytest.mark.parametrize(
    "stderr",
    [
        "Error: connection refused",
        "Error: Obsidian is not running",
        "Error: could not connect to Obsidian",
        # The message a real closed app produces, confirmed by live smoke test
        # (2026-07-17, issue #25 checklist).
        "The CLI is unable to find Obsidian. Please make sure Obsidian is running and try again.",
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


# -- mutation verbs -------------------------------------------------------


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


def test_set_property_authors_rejects_comma_in_value(monkeypatch):
    """obsidian-cli property:set has no escape mechanism for commas in list
    values (checked against a live `obsidian-cli property:set --help`,
    read-only) -- ",".join would otherwise silently mis-split on write
    (SHOULD-FIX 7)."""
    monkeypatch.setattr(mutations, "run", lambda *a, **kw: pytest.fail("run must not be called"))
    monkeypatch.setattr(mutations, "read_note", lambda root, note: note_with_authors(["claude"]))

    with pytest.raises(ValueError, match="comma"):
        mutations.set_property(VAULT, "alpha", "authors", "co,dex")


def test_set_property_list_rejects_comma_in_value(monkeypatch):
    monkeypatch.setattr(mutations, "run", lambda *a, **kw: pytest.fail("run must not be called"))

    with pytest.raises(ValueError, match="comma"):
        mutations.set_property_list(VAULT, "alpha", "categories", ["[[Knowledge, Inc]]"])


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
