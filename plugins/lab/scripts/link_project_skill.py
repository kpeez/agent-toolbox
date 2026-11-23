#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Stage a project skill in .agents/skills/<name> and give Claude Code a committed link to it.

Run from inside the repository: link_project_skill.py <skill-name>

Exit 0: done, or already done. Exit 1: `refused:` changed nothing, `failed:` left the
changes it printed. Exit 2: bad arguments, no such skill, or not inside a Git repository.
"""

import os
import subprocess
import sys
from pathlib import Path

WHOLE_FOLDER_RULES = {".agents", ".agents/", "/.agents", "/.agents/"}
CHILDREN_RULES = {".agents/*", "/.agents/*"}
REINCLUDE = "!/.agents/skills/"


class Refusal(Exception):
    pass


class Failure(Exception):
    pass


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=False, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise Refusal(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def tracked_mode(root: Path, path: str) -> str | None:
    out = git(root, "ls-files", "-s", "--", path).stdout
    for line in out.splitlines():
        meta, name = line.split("\t", 1)
        if name == path:
            return meta.split()[0]
    return None


def ignore_rule(root: Path, path: str) -> tuple[str, int, str] | None:
    result = git(root, "check-ignore", "--no-index", "-v", "--", path, check=False)
    if result.returncode != 0 or not result.stdout:
        return None
    meta = result.stdout.split("\t", 1)[0]
    source, line, pattern = meta.split(":", 2)
    if pattern.startswith("!"):
        return None
    return source, int(line), pattern


def unignore_skills(root: Path, skill_file: str) -> str | None:
    rule = ignore_rule(root, skill_file)
    if rule is None:
        return None
    source, number, pattern = rule
    gitignore = root / ".gitignore"
    where = f"{source}:{number}: {pattern}"
    if (
        Path(source) != Path(".gitignore")
        or pattern not in WHOLE_FOLDER_RULES | CHILDREN_RULES
    ):
        raise Refusal(
            f"{where} hides {skill_file}, and only a root .gitignore rule for the whole "
            f".agents folder can be rewritten; change that rule so Git sees .agents/skills/"
        )
    original = gitignore.read_bytes()
    lines = original.decode().splitlines(keepends=True)
    eol = "\r\n" if lines[number - 1].endswith("\r\n") else "\n"
    kept = (
        "/.agents/*"
        if pattern in WHOLE_FOLDER_RULES
        else lines[number - 1].rstrip("\r\n")
    )
    lines[number - 1 : number] = [f"{kept}{eol}", f"{REINCLUDE}{eol}"]
    gitignore.write_bytes("".join(lines).encode())
    still = ignore_rule(root, skill_file)
    if still is not None:
        gitignore.write_bytes(original)
        raise Refusal(
            f"{still[0]}:{still[1]}: {still[2]} still hides {skill_file} after rewriting "
            f"{where}; .gitignore is restored; change that rule so Git sees .agents/skills/"
        )
    return f"rewrote {where} to /.agents/* and {REINCLUDE}"


def link_state(root: Path, name: str) -> str:
    folder = root / ".claude" / "skills"
    entry = folder / name
    skill_file = root / ".agents" / "skills" / name / "SKILL.md"
    if folder.is_symlink():
        if tracked_mode(root, ".claude/skills") == "120000":
            reaches = (entry / "SKILL.md").resolve() == skill_file.resolve()
            return "folder-link-reaches" if reaches else "folder-link-misses"
        if folder.resolve() == (root / ".agents" / "skills").resolve():
            return "old-folder-link"
        return "untracked-folder-link-elsewhere"
    if folder.exists() and not folder.is_dir():
        return "folder-is-file"
    if entry.is_symlink() or not entry.exists():
        return "link"
    return "entry-is-real"


REFUSALS = {
    "folder-link-misses": "the committed link .claude/skills does not reach .agents/skills/{name}; "
    "fix that link by hand",
    "untracked-folder-link-elsewhere": ".claude/skills is an untracked link that does not point "
    "to .agents/skills; move it away by hand",
    "folder-is-file": ".claude/skills is a file, not a folder; move it away by hand",
    "entry-is-real": ".claude/skills/{name} is a real file or folder and hides the skill; "
    "move it away by hand",
}


def old_setup_lines(root: Path, name: str) -> list[str]:
    patterns = [
        "ln -sfn ../.agents/skills .claude/skills",
        f"ln -sfn ../../.agents/skills/{name} .claude/skills/{name}",
    ]
    args = [arg for pattern in patterns for arg in ("-e", pattern)]
    out = git(root, "grep", "-n", "-F", *args, check=False).stdout.splitlines()
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        for number, line in enumerate(gitignore.read_text().splitlines(), 1):
            if line.strip() == f"/.claude/skills/{name}":
                out.append(f".gitignore:{number}:{line}")
    return out


def run(root: Path, name: str) -> None:
    state = link_state(root, name)
    if state in REFUSALS:
        raise Refusal(REFUSALS[state].format(name=name))
    rewrite = unignore_skills(root, f".agents/skills/{name}/SKILL.md")
    try:
        if rewrite:
            print(rewrite)
            git(root, "add", "--", ".gitignore")
        apply(root, state, name)
    except Refusal as failure:
        raise Failure(str(failure)) from None


def apply(root: Path, state: str, name: str) -> None:
    skill_dir = f".agents/skills/{name}"
    link = f".claude/skills/{name}"
    git(root, "add", "--", skill_dir)
    print(f"staged {skill_dir}")
    if state == "old-folder-link":
        (root / ".claude" / "skills").unlink()
        print("removed the untracked link .claude/skills from the old setup step")
    if state == "folder-link-reaches":
        print(f"the committed link .claude/skills already reaches {skill_dir}")
    else:
        entry = root / link
        entry.parent.mkdir(parents=True, exist_ok=True)
        if entry.is_symlink():
            entry.unlink()
        os.symlink(f"../../{skill_dir}", entry)
        git(root, "add", "-f", "--", link)
        print(f"linked and staged {link} -> ../../{skill_dir}")

    skill_file = f"{skill_dir}/SKILL.md"
    if tracked_mode(root, skill_file) is None:
        raise Refusal(f"Git does not record {skill_file}")
    recorded = ".claude/skills" if state == "folder-link-reaches" else link
    if tracked_mode(root, recorded) != "120000":
        raise Refusal(f"Git does not record {recorded} as a link (mode 120000)")
    if (root / link / "SKILL.md").resolve() != (root / skill_file).resolve():
        raise Refusal(f"{link}/SKILL.md does not resolve to {skill_file}")

    skipped = git(
        root, "ls-files", "--others", "--ignored", "--exclude-standard", "--", skill_dir
    )
    for path in skipped.stdout.split():
        print(f"note: an ignore rule keeps {path} out of Git")
    for line in old_setup_lines(root, name):
        print(f"note: remove the old setup line {line}")


def main(argv: list[str]) -> int:
    if (
        len(argv) != 1
        or argv[0] in {"", ".", ".."}
        or "/" in argv[0]
        or argv[0].startswith("-")
    ):
        print("usage: link_project_skill.py <skill-name>", file=sys.stderr)
        return 2
    name = argv[0]
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if top.returncode != 0:
        print("error: run this inside a Git repository", file=sys.stderr)
        return 2
    root = Path(top.stdout.strip())
    if not (root / ".agents" / "skills" / name / "SKILL.md").is_file():
        print(
            f"error: {root}/.agents/skills/{name}/SKILL.md does not exist",
            file=sys.stderr,
        )
        return 2
    try:
        run(root, name)
    except Failure as failure:
        print(f"failed: {failure}; the changes above stay in place", file=sys.stderr)
        return 1
    except Refusal as refusal:
        print(f"refused: {refusal}; nothing changed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
