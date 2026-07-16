#!/usr/bin/env python3
"""Manage the cascading llmOS branch model without discarding work.

    main
    YYYY-MM-DD                     daily catch-all, branched off main
    <agent>/YYYY-MM-DD/<spec>      per-spec working branch, off the daily branch

Per-spec branches merge into the day's catch-all; only the catch-all merges to
main. `start` puts the session on today's catch-all; `spec` cuts a per-spec
branch off it.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from datetime import date
from pathlib import Path

from vault_root import vault_root

DAILY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SPEC = re.compile(r"^[^/]+/(\d{4}-\d{2}-\d{2})/.+$")


def git(
    root: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=check,
        text=True,
        capture_output=True,
    )


def current_branch(root: Path) -> str:
    return git(root, "branch", "--show-current").stdout.strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise SystemExit(f"cannot slugify: {value!r}")
    return slug


def switch_or_create(root: Path, branch: str) -> None:
    """Switch to a branch, creating it if it does not exist."""
    exists = (
        git(
            root, "show-ref", "--verify", f"refs/heads/{branch}", check=False
        ).returncode
        == 0
    )
    if exists:
        git(root, "switch", branch)
    else:
        git(root, "switch", "-c", branch)


def start(root: Path) -> None:
    """Ensure the session sits on today's catch-all branch, off main."""
    today = date.today().isoformat()
    current = current_branch(root)

    if current == today:
        print(today)
        return
    spec_match = SPEC.match(current)
    if spec_match and spec_match.group(1) == today:
        print(current)  # already on a per-spec branch for today; leave it
        return
    if DAILY.match(current) or spec_match:
        raise SystemExit(f"stale branch still active: {current}")
    if current != "main":
        raise SystemExit(f"refusing to replace non-daily branch: {current}")

    switch_or_create(root, today)
    print(today)


def spec(root: Path, agent: str, name: str) -> None:
    """Cut (or switch to) a per-spec branch off today's catch-all branch."""
    today = date.today().isoformat()
    if current_branch(root) != today:
        raise SystemExit(
            f"run `start` first: per-spec branches fork today's catch-all ({today})"
        )
    branch = f"{agent}/{today}/{slugify(name)}"
    switch_or_create(root, branch)
    print(branch)


def main() -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Vault root; resolved via the shared resolver when omitted.",
    )
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("start", parents=[common])
    spec_parser = sub.add_parser("spec", parents=[common])
    spec_parser.add_argument("--agent", required=True)
    spec_parser.add_argument("--name", required=True)
    args = parser.parse_args()
    root = args.root.expanduser().resolve() if args.root else vault_root()

    if git(root, "rev-parse", "--verify", "HEAD", check=False).returncode != 0:
        print("initial commit does not exist; branch start deferred")
        return

    if args.command == "start":
        start(root)
    elif args.command == "spec":
        spec(root, slugify(args.agent), args.name)


if __name__ == "__main__":
    main()
