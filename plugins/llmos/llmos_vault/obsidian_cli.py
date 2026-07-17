"""The obsidian-cli write backend (ADR-0004): every vault mutation shells out
to a running Obsidian instance so `alwaysUpdateLinks` rewrites backlinks --
this module never reimplements rename or link-rewrite semantics itself. Reads
stay in `notes.py`/`graph.py`, parsing files directly; `run` is the one place
in the library allowed to call `subprocess`.

Invocation shape matches obsidian-cli's own convention: `vault=<name>` first
(the registered vault's directory basename, e.g. "llmOS" for
`/Users/kyle/code/llmOS` -- confirmed against a live `obsidian-cli` install),
then the verb, then `file=`/`path=` targeting, then remaining `key=value`
params -- always an argv list passed straight to `subprocess.run`, never a
shell string, so no value needs shell-quoting regardless of length or
content.

Multi-line `content` values are staged through a real temp file, read back,
and passed as the `content=` argv element -- a temp-file hop that catches
encoding mistakes early and gives tests a concrete round-trip point, even
though argv-list subprocess calls need no shell-escaping either way.
Single-line content skips the temp-file hop.

A closed Obsidian app is a loud, named failure (`ObsidianNotRunning`) rather
than a swallowed non-zero exit. obsidian-cli's exact closed-app stderr text
is not publicly documented (checked against `obsidian-cli --help` only, not a
live app quit, to avoid killing a real running session) -- `_NOT_RUNNING_SIGNALS`
is a best-effort substring match, to be confirmed by a manual smoke test
(quit Obsidian, run a mutation verb, check the message and exit code).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

EXIT_OBSIDIAN_NOT_RUNNING = 3

_NOT_RUNNING_SIGNALS = (
    # The message a real closed app produces, confirmed by live smoke test
    # (2026-07-17): "The CLI is unable to find Obsidian. Please make sure
    # Obsidian is running and try again."
    "unable to find obsidian",
    "not running",
    "connection refused",
    "econnrefused",
    "could not connect",
    "unable to connect",
    "no vault is open",
)


class ObsidianNotRunning(RuntimeError):
    """Raised when a mutation cannot reach a running Obsidian instance."""


def _target_args(file: str | None, path: str | None) -> list[str]:
    if bool(file) == bool(path):
        raise ValueError("pass exactly one of file= or path= to target a note")
    return [f"file={file}"] if file else [f"path={path}"]


def _stage_content(content: str) -> tuple[str, Path | None]:
    if "\n" not in content:
        return content, None
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    try:
        tmp.write(content)
    finally:
        tmp.close()
    tmp_path = Path(tmp.name)
    return tmp_path.read_text(), tmp_path


def run(
    vault_root: Path,
    verb: str,
    *,
    file: str | None = None,
    path: str | None = None,
    params: dict[str, str] | None = None,
    content: str | None = None,
) -> str:
    """Invoke obsidian-cli against the live app and return its stdout.

    Use when a mutation verb (`create_note`, `move_note`, ...) needs to shell
    out to obsidian-cli -- it is the only function in the library allowed to
    call `subprocess`, so vault targeting, `file=`/`path=` enforcement, and
    multi-line content staging happen in exactly one place.
    Do NOT use when reading -- `notes.read_note`/`graph.get_neighbors` parse
    the vault directly and stay headless-safe; shelling out for a read would
    needlessly require the app to be open.

    Example output:
        'Moved: notes/alpha.md -> archive/alpha.md\\n'

    Example invocation:
        run(vault_root, "move", file="alpha", params={"to": "archive"})

    Args:
        vault_root: Root directory of the vault to target.
        verb: obsidian-cli command name, e.g. "move" or "property:set".
        file: Note name (wikilink-style resolution). Exactly one of `file`/
            `path` is required -- the backend refuses to build a targetless
            invocation.
        path: Exact vault-relative path. Exactly one of `file`/`path` is
            required.
        params: Extra `key=value` arguments (e.g. `{"to": "archive"}`).
        content: Content value; multi-line content is staged through a temp
            file rather than shell-quoted inline.

    Raises:
        ObsidianNotRunning: obsidian-cli could not reach a running app.
    """
    target = _target_args(file, path)
    argv = ["obsidian-cli", f"vault={vault_root.name}", verb, *target]
    for key, value in (params or {}).items():
        argv.append(f"{key}={value}")

    tmp_path: Path | None = None
    if content is not None:
        staged, tmp_path = _stage_content(content)
        argv.append(f"content={staged}")

    try:
        result = subprocess.run(argv, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise ObsidianNotRunning(
            "obsidian-cli is not on PATH -- is Obsidian installed and running?"
        ) from exc
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if any(signal in stderr.lower() for signal in _NOT_RUNNING_SIGNALS):
            raise ObsidianNotRunning(
                f"obsidian-cli could not reach a running Obsidian app: {stderr}"
            )
        raise RuntimeError(f"obsidian-cli {verb} failed: {stderr}")
    return result.stdout
