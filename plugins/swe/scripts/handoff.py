#!/usr/bin/env python3
"""Find handoff files, and save each compaction's summary into one.

A handoff file holds the current state of one piece of work, so a new session
can continue it. It lives in ``<main checkout>/.agents/plans/``, shared by every
worktree of the repository and kept out of git by the directory's own
``.gitignore``. Its name is the branch name with ``/`` changed to ``-``. On
``main``, ``master``, or a detached HEAD it is ``<date>-<session id prefix>.md``.

The session model writes the whole file with the ``handoff`` skill. ``hook``
runs on PostCompact (manual, auto, and idle compaction) and puts the event's
``compact_summary`` in the file's ``## Session summary`` section, replacing the
earlier one and keeping the rest of the file. It skips a default branch or
detached HEAD, never fails the session, and makes no model call.

``log`` appends one decision to the work's decision log, a JSON Lines file next
to the handoff file with the same stem and ``.decisions.jsonl``. Each line holds
``ts``, ``phase``, ``decision``, ``why``, ``evidence`` (a list of pointers), and
``result``. The ``log-decisions`` skill says when to write a row.

Usage: python3 handoff.py {dir,path,log,hook} --help
"""

import argparse
from datetime import date, datetime
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

DEFAULT_BRANCHES = {"main", "master"}

def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=5, check=True).stdout.strip()


def plans_dir(cwd):
    """Return the main checkout's plans directory, or None outside a git work tree.

    A linked worktree resolves to its main checkout, so every worktree shares one
    plans directory. Otherwise (including submodules and separate git dirs) the
    current work tree is the main checkout.
    """
    try:
        top, git_dir, common = git(cwd, "rev-parse", "--path-format=absolute", "--show-toplevel",
                                   "--absolute-git-dir", "--git-common-dir").splitlines()
        if Path(git_dir) != Path(common):
            listing = git(cwd, "worktree", "list", "--porcelain")
            top = next(line[len("worktree "):] for line in listing.splitlines() if line.startswith("worktree "))
    except (OSError, subprocess.SubprocessError, ValueError, StopIteration):
        return None
    return Path(top) / ".agents" / "plans"


def ensure_dir(cwd):
    """Create the plans directory and its ignore file; return it, or None outside git."""
    directory = plans_dir(cwd)
    if directory is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    ignore = directory / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    return directory


def handoff_name(cwd, session_id=""):
    try:
        branch = git(cwd, "branch", "--show-current")
    except (OSError, subprocess.SubprocessError):
        branch = ""
    if branch and branch not in DEFAULT_BRANCHES:
        return branch.replace("/", "-") + ".md"
    # An unexpanded ${CLAUDE_SESSION_ID} (a host without substitution) is no id.
    session = "" if "$" in session_id else session_id[:8]
    return f"{date.today().isoformat()}-{session or datetime.now().strftime('%H%M%S')}.md"


def handoff_path(cwd, session_id=""):
    directory = plans_dir(cwd)
    return None if directory is None else directory / handoff_name(cwd, session_id)


def log_path(cwd, session_id=""):
    directory = plans_dir(cwd)
    if directory is None:
        return None
    return directory / (Path(handoff_name(cwd, session_id)).stem + ".decisions.jsonl")


def append_decision(path, phase, decision, why, evidence, result):
    """Append one decision as a JSON line; return the row."""
    row = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"), "phase": phase,
           "decision": decision, "why": why, "evidence": list(evidence), "result": result}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


SUMMARY_HEADING = "## Session summary"


def summary_text(summary):
    """Return the <summary> part of a compact summary, without its <analysis> part."""
    match = re.search(r"<summary>(.*?)</summary>", summary, re.DOTALL)
    return match.group(1) if match else summary


def save_summary(path, summary, title):
    """Replace the file's Session summary section with this summary; keep the rest."""
    try:
        head = path.read_text(encoding="utf-8").split(f"\n{SUMMARY_HEADING}\n")[0].rstrip()
    except FileNotFoundError:
        head = f"# {title}"
    stamp = datetime.now().astimezone().isoformat(timespec="minutes")
    text = f"{head}\n\n{SUMMARY_HEADING}\n\nFrom compaction at {stamp}.\n\n{summary.strip()}\n"
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp",
                                     delete=False, encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(handle.name, 0o644)
    os.replace(handle.name, path)


def run_hook():
    """Save a PostCompact event's summary into the branch's handoff file."""
    try:
        event = json.load(sys.stdin)
        summary, cwd = summary_text(event.get("compact_summary") or ""), event["cwd"]
        branch = git(cwd, "branch", "--show-current")
        if not summary.strip() or not branch or branch in DEFAULT_BRANCHES:
            return 0
        directory = ensure_dir(cwd)
        save_summary(directory / handoff_name(cwd), summary, branch)
    except Exception:  # noqa: BLE001 - a hook must never fail the session
        pass
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True, metavar="{dir,path,log,hook}")
    commands.add_parser("dir", help="create and print the plans directory")
    path_cmd = commands.add_parser("path", help="create the plans directory and print this work's handoff file")
    path_cmd.add_argument("--session", default="", help="session id, used on a default branch")
    log_cmd = commands.add_parser("log", help="append one decision to this work's decision log and print its path")
    log_cmd.add_argument("--session", default="", help="session id, used on a default branch")
    log_cmd.add_argument("--phase", required=True, help="phase or workstream, or start for a new session's first row")
    log_cmd.add_argument("--decision", required=True, help="what was chosen or done, one line")
    log_cmd.add_argument("--why", required=True, help="the reason, in plain words")
    log_cmd.add_argument("--evidence", action="append", default=[],
                         help="a pointer: commit SHA, PR, file:line, or path; repeat for more")
    log_cmd.add_argument("--result", required=True, help="the outcome, such as reverted, tests pass, or open")
    commands.add_parser("hook", help="PostCompact hook; reads the hook event on stdin")
    args = parser.parse_args(argv)

    if args.command == "hook":
        return run_hook()
    directory = ensure_dir(Path.cwd())
    if directory is None:
        print("not inside a git work tree", file=sys.stderr)
        return 1
    if args.command == "log":
        path = log_path(Path.cwd(), args.session)
        append_decision(path, args.phase, args.decision, args.why, args.evidence, args.result)
        print(path)
        return 0
    print(directory if args.command == "dir" else directory / handoff_name(Path.cwd(), args.session))
    return 0


if __name__ == "__main__":
    sys.exit(main())
