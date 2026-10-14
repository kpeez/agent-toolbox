#!/usr/bin/env python3
"""List this project's agent transcripts, newest first.

Claude Code keeps one JSONL file per session in
``~/.claude/projects/<slug>/<session-id>.jsonl``. The slug is the session's
working directory with every character that is not a letter or a digit
changed to ``-``. Subagent transcripts sit in
``<slug>/<session-id>/subagents/*.jsonl``.

Codex keeps one rollout file per session in
``~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl``. Its first line is a
``session_meta`` record that names the working directory.

The script matches only the working directories of this repository: the main
checkout and each linked worktree. It prints paths and modification times. It
never prints transcript content, and it never lists a transcript of another
project.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def project_dirs(cwd: Path) -> list[Path]:
    """Return the main checkout and every worktree of the repository at cwd."""
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "worktree", "list", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return [cwd.resolve()]
    dirs = [Path(line[len("worktree "):]) for line in out.splitlines() if line.startswith("worktree ")]
    return dirs or [cwd.resolve()]


def claude_slug(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def claude_transcripts(dirs: list[Path], subagents: bool) -> list[Path]:
    root = Path.home() / ".claude" / "projects"
    found: list[Path] = []
    for d in dirs:
        project = root / claude_slug(d)
        if not project.is_dir():
            continue
        found.extend(project.glob("*.jsonl"))
        if subagents:
            found.extend(project.glob("*/subagents/*.jsonl"))
    return found


def codex_cwd(path: Path) -> str | None:
    try:
        with path.open(encoding="utf-8") as handle:
            first = json.loads(handle.readline())
    except (OSError, ValueError):
        return None
    if not isinstance(first, dict):
        return None
    payload = first.get("payload") if first.get("type") == "session_meta" else first
    if isinstance(payload, dict) and isinstance(payload.get("cwd"), str):
        return payload["cwd"]
    return None


def codex_transcripts(dirs: list[Path], since: float) -> list[Path]:
    root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions"
    if not root.is_dir():
        return []
    wanted = {str(d) for d in dirs}
    found: list[Path] = []
    for path in root.rglob("*.jsonl"):
        if path.stat().st_mtime < since:
            continue
        cwd = codex_cwd(path)
        if cwd is None:
            continue
        if any(cwd == w or cwd.startswith(w + os.sep) for w in wanted):
            found.append(path)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=float, default=7, help="window in days (default 7; 0 for all)")
    parser.add_argument("--host", choices=["claude", "codex", "all"], default="all")
    parser.add_argument("--subagents", action="store_true", help="include Claude Code subagent transcripts")
    parser.add_argument("--exclude", action="append", default=[], help="session id to skip, such as the current one")
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="a directory in the repository (default: here)")
    args = parser.parse_args(argv)

    since = 0.0 if args.days <= 0 else time.time() - args.days * 86400
    dirs = project_dirs(args.cwd)
    paths: list[Path] = []
    if args.host in ("claude", "all"):
        paths.extend(claude_transcripts(dirs, args.subagents))
    if args.host in ("codex", "all"):
        paths.extend(codex_transcripts(dirs, since))

    rows = []
    for path in set(paths):
        mtime = path.stat().st_mtime
        if mtime < since or any(s and s in str(path) for s in args.exclude):
            continue
        rows.append((mtime, path))
    for mtime, path in sorted(rows, reverse=True):
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
        print(f"{stamp}\t{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
