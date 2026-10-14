#!/usr/bin/env python3
"""Find handoff files, and get a stale one rewritten before the session goes cold.

A handoff file holds the current state of one piece of work, so a new session
can continue it. It lives in ``<main checkout>/.agents/plans/``, shared by every
worktree of the repository and kept out of git by the directory's own
``.gitignore``. Its name is the branch name with ``/`` changed to ``-``. On
``main``, ``master``, or a detached HEAD it is ``<date>-<session id prefix>.md``.

The session model writes the file with the ``handoff`` skill. ``hook`` is the
automatic path. A file is stale when the session's newest Edit or Write is less
than RECENT_EDIT seconds old and later than the file's modification time, or
the file does not exist. The age limit skips an old session that is only
opened and closed again. For a stale file:

- Notification ``idle_prompt`` (an ``asyncRewake`` hook): exit 2 with a
  reminder, which wakes the session so its model runs the skill on a warm
  cache. It reminds once per newest edit.
- SessionEnd: start a detached ``write`` process that summarizes the
  transcript with ``claude -p --model haiku`` and replaces the file.

Otherwise ``hook`` exits 0 and prints nothing. It never fails the session.

Usage: python3 handoff.py {dir,path,hook} --help
"""

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
DEFAULT_BRANCHES = {"main", "master"}
CHILD_ENV = "SWE_HANDOFF_CHILD"
MAX_TRANSCRIPT_CHARS = 150_000
WRITE_TIMEOUT = 300
RECENT_EDIT = 3600

PROMPT = """\
Write a handoff file for a coding session, so that a new agent session can
continue the work. Use only facts from the transcript and the current file.

Output only the file's Markdown, with no preamble and no code fence. Use these
sections, in this order:

# <Title of the work>

## Goal
## Done
## Decisions
## Next
## Open questions
## Branch and PR

Keep the Goal and Decisions of the current file unless the transcript changes
them. Keep any other section of the current file, such as Non-goals, Approach,
or Verification, after Decisions. Name files, commands, and branch names exactly. Write "None" in an empty
section.
"""


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


def entries(transcript):
    with open(transcript, encoding="utf-8") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") in ("user", "assistant") and not entry.get("isSidechain"):
                yield entry


def blocks(entry):
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content if isinstance(content, list) else []


def last_edit_time(transcript):
    """Return the POSIX time of the newest Edit or Write in the transcript, or None."""
    newest = None
    for entry in entries(transcript):
        if any(b.get("type") == "tool_use" and b.get("name") in EDIT_TOOLS for b in blocks(entry)):
            try:
                stamp = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).timestamp()
            except (KeyError, AttributeError, ValueError):
                continue
            newest = stamp if newest is None else max(newest, stamp)
    return newest


def is_stale(path, transcript):
    edited = last_edit_time(transcript)
    if edited is None or time.time() - edited > RECENT_EDIT:
        return False
    try:
        return path.stat().st_mtime < edited
    except FileNotFoundError:
        return True


def digest(transcript):
    """Return the conversation text and tool calls, newest MAX_TRANSCRIPT_CHARS kept."""
    lines = []
    for entry in entries(transcript):
        role = entry["type"]
        for block in blocks(entry):
            if block.get("type") == "text" and block.get("text", "").strip():
                lines.append(f"[{role}] {block['text'].strip()}")
            elif block.get("type") == "tool_use":
                arguments = json.dumps(block.get("input", {}), ensure_ascii=False)[:300]
                lines.append(f"[tool] {block.get('name')} {arguments}")
    return "\n".join(lines)[-MAX_TRANSCRIPT_CHARS:]


def write(path, transcript):
    """Summarize the transcript with Haiku and replace the handoff file."""
    def mtime():
        try:
            return path.stat().st_mtime
        except FileNotFoundError:
            return None

    started = mtime()
    try:
        current = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        current = "(none)"
    prompt = (f"{PROMPT}\n<current-file>\n{current}\n</current-file>\n\n"
              f"<transcript>\n{digest(transcript)}\n</transcript>\n")
    result = subprocess.run(
        ["claude", "-p", "--model", "haiku", "--tools", "", "--no-session-persistence"],
        input=prompt, capture_output=True, text=True, timeout=WRITE_TIMEOUT,
        env={**os.environ, CHILD_ENV: "1"})
    text = result.stdout.strip()
    # The skill or another writer changed the file during the call: keep theirs.
    if result.returncode != 0 or not text.startswith("#") or mtime() != started:
        return 1
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp",
                                     delete=False, encoding="utf-8") as handle:
        handle.write(text + "\n")
    os.chmod(handle.name, 0o644)
    os.replace(handle.name, path)
    return 0


def remind(path, session_id, edited):
    """Return 2 with a reminder on stderr, once per newest edit; else 0."""
    marker = path.parent / f".reminded-{session_id[:8] or 'session'}"
    try:
        if float(marker.read_text(encoding="utf-8")) >= edited:
            return 0
    except (OSError, ValueError):
        pass
    marker.write_text(str(edited), encoding="utf-8")
    print(f"The handoff file {path} is missing or older than this session's last edit. "
          "Run the swe:handoff skill to update it, then stop.", file=sys.stderr)
    return 2


def run_hook():
    """Remind the idle session, or start a detached Haiku write at session end."""
    if os.environ.get(CHILD_ENV):
        return 0
    try:
        event = json.load(sys.stdin)
        cwd, transcript = event["cwd"], event["transcript_path"]
        session_id = event.get("session_id", "")
        path = handoff_path(cwd, session_id)
        if path is None or not is_stale(path, transcript):
            return 0
        ensure_dir(cwd)
        if event.get("hook_event_name") == "Notification":
            return remind(path, session_id, last_edit_time(transcript))
        subprocess.Popen(
            [sys.executable, __file__, "write", "--path", str(path), "--transcript", transcript],
            cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception:  # noqa: BLE001 - a hook must never fail the session
        pass
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True, metavar="{dir,path,hook}")
    commands.add_parser("dir", help="create and print the plans directory")
    path_cmd = commands.add_parser("path", help="create the plans directory and print this work's handoff file")
    path_cmd.add_argument("--session", default="", help="session id, used on a default branch")
    commands.add_parser("hook", help="Notification idle_prompt and SessionEnd hook; reads the hook event on stdin")
    write_cmd = commands.add_parser("write", help="internal: summarize a transcript into a handoff file")
    write_cmd.add_argument("--path", required=True, type=Path)
    write_cmd.add_argument("--transcript", required=True)
    args = parser.parse_args(argv)

    if args.command == "hook":
        return run_hook()
    if args.command == "write":
        return write(args.path, args.transcript)
    directory = ensure_dir(Path.cwd())
    if directory is None:
        print("not inside a git work tree", file=sys.stderr)
        return 1
    print(directory if args.command == "dir" else directory / handoff_name(Path.cwd(), args.session))
    return 0


if __name__ == "__main__":
    sys.exit(main())
