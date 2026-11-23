#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fail when a tracked file holds an absolute home-folder path.

A path such as /Users/<name>/ or /home/<name>/ leaks a private account name
into the public repo. The scan reads every file that `git ls-files` lists.
"""

import re
import subprocess
import sys

HOME_PATH = re.compile(r"/(Users|home)/([A-Za-z0-9._-]+)/")
SYNTHETIC_USERS = {"demo", "you"}


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True, text=True
    ).stdout
    return [path for path in out.split("\0") if path]


def main() -> int:
    errors = []
    for path in tracked_files():
        try:
            with open(path, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(lines, 1):
            for match in HOME_PATH.finditer(line):
                if match.group(2) in SYNTHETIC_USERS:
                    continue
                errors.append(
                    f"{path}:{number} has a home-folder path /{match.group(1)}/<name>/...; "
                    "use a repo-relative or synthetic path such as /home/demo/ "
                    "(the users demo and you are allowed)"
                )
    print("\n".join(errors) or "ok: no home-folder paths")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
