#!/usr/bin/env python3
"""Mirror local plan files to Linear issue documents.

Plans live in ``<main checkout>/.agents/plans/``, shared by every worktree of
the repository and kept out of git by the directory's own ``.gitignore``. A file
named ``ABC-123-short-slug.md`` is mirrored one way to a "Plan: short-slug"
document on Linear issue ABC-123; files without an issue key stay local.

Behavioral rules:
- The local file is the source of truth. A Linear document edited since the
  last sync is reported and skipped unless ``sync --force <file>`` is given.
- Only plans whose content changed since their last sync are sent.
- ``hook`` (the Stop hook) never blocks and always exits 0. It prints nothing
  on success and one ``systemMessage`` JSON line when a sync fails, repeating a
  failure only after the plan changes or the failure changes. It stops starting
  new pushes after HOOK_BUDGET seconds; the rest retry on the next turn.
- Needs a Linear personal API key: ``LINEAR_API_KEY`` if set, otherwise the
  file ``$XDG_CONFIG_HOME/swe/linear-api-key`` (default ``~/.config``), so hooks
  find the key whatever shell or environment launched them. Sync state lives in
  one file per plan under ``.agents/plans/.sync/``, so concurrent sessions
  syncing different plans never overwrite each other's state.

Usage: python3 plan_sync.py {dir,status,sync,hook} --help
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

API_URL = "https://api.linear.app/graphql"
PLAN_NAME = re.compile(r"^([A-Z][A-Z0-9]*-[0-9]+)-(.+)\.md$")
STATE_DIR = ".sync"
NOTICE = "> Mirrored from a local plan file. Edits made here are not synced back.\n\n"
TIMEOUT = 5
HOOK_BUDGET = 20

ISSUE_QUERY = """query($id: String!, $title: String!) {
  issue(id: $id) { id documents(filter: {title: {eq: $title}}) { nodes { id } } }
}"""
DOCUMENT_QUERY = """query($id: String!) {
  document(id: $id) { id content trashed archivedAt }
}"""
CREATE = """mutation($input: DocumentCreateInput!) {
  documentCreate(input: $input) { success document { id url content } }
}"""
UPDATE = """mutation($id: String!, $input: DocumentUpdateInput!) {
  documentUpdate(id: $id, input: $input) { success document { id url content } }
}"""


class SyncError(Exception):
    pass


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


def ensure_ignored(directory):
    """Keep the plans directory out of git without relying on a global ignore."""
    ignore = directory / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_entry(directory, name):
    try:
        return json.loads((directory / STATE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_entry(directory, name, entry):
    state = directory / STATE_DIR
    state.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=state, prefix=f".{name}.", suffix=".tmp",
                                     delete=False, encoding="utf-8") as handle:
        json.dump(entry, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(handle.name, state / f"{name}.json")


def plans(directory):
    """Yield (path, issue key or None, slug) for each plan file."""
    for path in sorted(directory.glob("*.md")):
        match = PLAN_NAME.match(path.name)
        yield (path, match.group(1), match.group(2)) if match else (path, None, path.stem)


def key_file():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "swe" / "linear-api-key"


def api_key():
    """Return the Linear API key from LINEAR_API_KEY, else the key file, else ""."""
    key = os.environ.get("LINEAR_API_KEY", "").strip()
    if key:
        return key
    try:
        return key_file().read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def graphql(query, variables):
    key = api_key()
    if not key:
        raise SyncError(f"no Linear API key (set LINEAR_API_KEY or write it to {key_file()})")
    request = urllib.request.Request(
        API_URL, json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        {"Authorization": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:  # GraphQL errors can arrive with a 4xx status
        try:
            payload = json.load(error)
        except ValueError:
            raise SyncError(f"Linear returned HTTP {error.code}") from None
    except (OSError, ValueError) as error:
        raise SyncError(f"could not reach Linear ({error})") from None
    if payload.get("errors"):
        raise SyncError(payload["errors"][0].get("message", "Linear returned an error"))
    return payload["data"]


def live_document(document_id):
    """Return the document, or None when it was deleted, trashed, or archived."""
    try:
        document = graphql(DOCUMENT_QUERY, {"id": document_id})["document"]
    except SyncError as error:
        if "not found" in str(error).lower():
            return None
        raise
    return None if document.get("trashed") or document.get("archivedAt") else document


def push(name, key, slug, text, entry, force):
    """Create or update the plan's Linear document and return its new state entry."""
    title = f"Plan: {slug}"
    content = NOTICE + text
    document = live_document(entry["document_id"]) if entry.get("document_id") else None
    if document and not force and digest(document.get("content") or "") != entry.get("remote_sha"):
        raise SyncError("the Linear document was edited since the last sync; skipped "
                        f"(run `plan_sync.py sync --force {name}` to overwrite it)")
    if document is None:
        issue = graphql(ISSUE_QUERY, {"id": key, "title": title})["issue"]
        existing = issue["documents"]["nodes"]
        document = existing[0] if existing else None
    if document:
        result = graphql(UPDATE, {"id": document["id"], "input": {"title": title, "content": content}})
        saved = result["documentUpdate"]["document"]
    else:
        result = graphql(CREATE, {"input": {"issueId": issue["id"], "title": title, "content": content}})
        saved = result["documentCreate"]["document"]
    return {"issue": key, "document_id": saved["id"], "url": saved["url"],
            "local_sha": digest(text), "remote_sha": digest(saved.get("content") or "")}


def sync(directory, names=(), force=False, repeat_failures=True, deadline=None):
    """Sync changed linked plans; return (synced, failures) as lists of messages."""
    synced, failures = [], []
    for path, key, slug in plans(directory):
        if not key or (names and path.name not in names):
            continue
        if deadline is not None and time.monotonic() > deadline:
            break
        entry = load_entry(directory, path.name)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            text, problem = None, SyncError(f"cannot read the plan ({error})")
        else:
            if entry.get("local_sha") == digest(text) and not force:
                continue
            try:
                entry = push(path.name, key, slug, text, entry, force)
                save_entry(directory, path.name, entry)
                synced.append(f"{path.name} -> {entry['url']}")
                continue
            except SyncError as error:
                problem = error
        marker = f"{digest(text) if text is not None else 'unreadable'}:{problem}"
        if repeat_failures or entry.get("reported") != marker:
            failures.append(f"{path.name}: {problem}")
            save_entry(directory, path.name, {**entry, "reported": marker})
    return synced, failures


def status(directory):
    lines = [f"plans: {directory}"]
    for path, key, _ in plans(directory):
        entry = load_entry(directory, path.name)
        if not key:
            lines.append(f"  {path.name}: local only")
        elif not entry.get("url"):
            lines.append(f"  {path.name}: not synced yet ({key})")
        else:
            try:
                current = entry.get("local_sha") == digest(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                current = False
            lines.append(f"  {path.name}: {'in sync' if current else 'changed since last sync'} -> {entry['url']}")
    return "\n".join(lines)


def run_hook():
    """Stop hook: sync changed plans without ever blocking the agent."""
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    try:
        cwd = data.get("cwd") if isinstance(data, dict) else None
        directory = plans_dir(cwd or os.getcwd())
        if not directory or not directory.is_dir():
            return 0
        ensure_ignored(directory)
        _, failures = sync(directory, repeat_failures=False, deadline=time.monotonic() + HOOK_BUDGET)
    except Exception as error:  # a hook must not fail the turn
        failures = [f"unexpected error: {error}"]
    if failures:
        print(json.dumps({"systemMessage": "plan-sync: " + "; ".join(failures)}))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mirror local plan files to Linear issue documents.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("dir", help="create and print the plans directory for the current repository")
    commands.add_parser("status", help="list plans and their sync state")
    sync_parser = commands.add_parser("sync", help="sync changed linked plans now")
    sync_parser.add_argument("files", nargs="*", help="plan file names to sync (default: all changed)")
    sync_parser.add_argument("--force", action="store_true",
                             help="push even if unchanged, overwriting edits made in Linear")
    commands.add_parser("hook", help="Stop-hook entry point; reads the hook payload on stdin")
    args = parser.parse_args(argv)

    if args.command == "hook":
        return run_hook()
    directory = plans_dir(os.getcwd())
    if not directory:
        print("plan_sync.py: not inside a git work tree", file=sys.stderr)
        return 2
    if args.command == "dir":
        directory.mkdir(parents=True, exist_ok=True)
        ensure_ignored(directory)
        print(directory)
        return 0
    if not directory.is_dir():
        print(f"plans: {directory} (none yet)")
        return 0
    ensure_ignored(directory)
    if args.command == "status":
        print(status(directory))
        return 0
    synced, failures = sync(directory, {Path(name).name for name in args.files}, args.force)
    for line in synced:
        print(f"synced {line}")
    for line in failures:
        print(f"failed {line}", file=sys.stderr)
    if not synced and not failures:
        print("nothing to sync")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
