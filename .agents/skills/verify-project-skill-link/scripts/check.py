#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run the project-skill link script end to end in throwaway repositories.

Each scenario builds a repository with a remote, writes the skill
.agents/skills/demo, runs the script twice, commits with `git add -A`, pushes, and
checks a fresh clone and a teammate's pull. Prints `PASS <scenario>` or
`FAIL <scenario>: <check>, ...` per scenario. Exits 0 only when every scenario passes.
"""

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "plugins" / "swe" / "scripts" / "link_project_skill.py"
SKILL = "demo"


@dataclass(frozen=True)
class Scenario:
    name: str
    outcome: str
    gitignore: str | None = None
    exclude: str | None = None
    before: str | None = None


SCENARIOS = [
    Scenario("no-ignore-rules", "linked"),
    Scenario("claude-folder-ignored", "linked", gitignore=".claude/\n"),
    Scenario("claude-ignored-without-slash", "linked", gitignore=".claude\n"),
    Scenario("claude-children-ignored", "linked", gitignore=".claude/*\n"),
    Scenario("claude-tree-ignored", "linked", gitignore=".claude/**\n"),
    Scenario("claude-ignored-in-info-exclude", "linked", exclude=".claude/\n"),
    Scenario(
        "old-untracked-folder-link",
        "linked",
        gitignore="/.claude/skills\n",
        before="old-folder-link",
    ),
    Scenario(
        "team-skills-folder-claude-ignored",
        "linked",
        gitignore=".claude/\n",
        before="team-skills-folder",
    ),
    Scenario("team-skills-folder", "linked", before="team-skills-folder"),
    Scenario("committed-folder-link", "folder-link", before="committed-folder-link"),
    Scenario("agents-folder-ignored", "linked", gitignore=".agents/\n.claude/\n"),
    Scenario("agents-children-ignored", "linked", gitignore="/.agents/*\n"),
    Scenario("agents-ignored-in-info-exclude", "refused", exclude=".agents/\n"),
    Scenario("real-folder-at-link-path", "refused", before="real-folder-at-link-path"),
    Scenario(
        "committed-folder-link-elsewhere",
        "refused",
        before="committed-folder-link-elsewhere",
    ),
]

OLD_SETUP_LINE = (
    "mkdir -p .claude && if [ -L .claude/skills ] || [ ! -e .claude/skills ]; "
    "then ln -sfn ../.agents/skills .claude/skills; fi\n"
)


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=False, capture_output=True, text=True
    )


def must(cwd: Path, *args: str) -> str:
    result = git(cwd, *args)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def link(path: Path, target: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target)


def lay_out_before(work: Path, before: str | None) -> None:
    if before == "old-folder-link":
        write(work / "setup.sh", OLD_SETUP_LINE)
    elif before == "team-skills-folder":
        write(work / ".claude" / "skills" / "team" / "SKILL.md", "team\n")
        must(work, "add", "-f", ".claude/skills/team/SKILL.md")
    elif before == "committed-folder-link":
        write(work / ".agents" / "skills" / "other" / "SKILL.md", "other\n")
        link(work / ".claude" / "skills", "../.agents/skills")
        must(work, "add", "-f", ".agents", ".claude/skills")
    elif before == "committed-folder-link-elsewhere":
        write(work / "team-skills" / "other" / "SKILL.md", "other\n")
        link(work / ".claude" / "skills", "../team-skills")
        must(work, "add", "-f", "team-skills", ".claude/skills")
    elif before == "real-folder-at-link-path":
        write(work / ".claude" / "skills" / SKILL / "notes.md", "mine\n")
    must(work, "add", "-A")
    must(work, "commit", "-qm", "base")
    if before == "old-folder-link":
        (work / ".agents" / "skills").mkdir(parents=True)
        link(work / ".claude" / "skills", "../.agents/skills")


def snapshot(repo: Path) -> str:
    entries = [must(repo, "ls-files", "-s")]
    for path in sorted(repo.rglob("*")):
        if ".git" in path.relative_to(repo).parts:
            continue
        if path.is_symlink():
            entries.append(f"{path} -> {os.readlink(path)}")
        elif path.is_file():
            entries.append(f"{path} {hashlib.sha256(path.read_bytes()).hexdigest()}")
        else:
            entries.append(f"{path}/")
    return "\n".join(entries)


def resolves(repo: Path) -> bool:
    found = repo / ".claude" / "skills" / SKILL / "SKILL.md"
    return (
        found.is_file()
        and found.resolve()
        == (repo / ".agents" / "skills" / SKILL / "SKILL.md").resolve()
    )


def link_mode(repo: Path, outcome: str) -> str:
    path = ".claude/skills" if outcome == "folder-link" else f".claude/skills/{SKILL}"
    for line in must(repo, "ls-files", "-s", "--", path).splitlines():
        meta, name = line.split("\t", 1)
        if name == path:
            return meta.split()[0]
    return "untracked"


def run_scenario(base: Path, scenario: Scenario, script: Path) -> list[str]:
    remote, work, teammate, clone = (
        base / n for n in ("remote", "work", "mate", "clone")
    )
    must(base, "init", "-q", "--bare", "-b", "main", str(remote))
    must(base, "init", "-q", "-b", "main", str(work))
    if scenario.gitignore is not None:
        write(work / ".gitignore", scenario.gitignore)
    if scenario.exclude is not None:
        write(work / ".git" / "info" / "exclude", scenario.exclude)
    write(work / "README.md", "throwaway\n")
    lay_out_before(work, scenario.before)
    must(work, "remote", "add", "origin", str(remote))
    must(work, "push", "-q", "origin", "main")

    must(base, "clone", "-q", str(remote), str(teammate))
    if scenario.exclude is not None:
        write(teammate / ".git" / "info" / "exclude", scenario.exclude)
    personal = teammate / ".claude" / "skills" / "personal" / "SKILL.md"
    if scenario.before == "old-folder-link":
        (teammate / ".agents" / "skills").mkdir(parents=True)
        link(teammate / ".claude" / "skills", "../.agents/skills")
        personal = None
    elif scenario.before in {
        "committed-folder-link",
        "committed-folder-link-elsewhere",
    }:
        personal = None
    else:
        write(personal, "personal\n")

    write(work / ".agents" / "skills" / SKILL / "SKILL.md", "---\nname: demo\n---\n")
    write(work / ".agents" / "skills" / SKILL / "scripts" / "check.py", "print(1)\n")
    before = snapshot(work)
    first = subprocess.run(
        [str(script), SKILL], cwd=work, check=False, capture_output=True, text=True
    )
    failed = []
    if scenario.outcome == "refused":
        if first.returncode != 1:
            failed.append(f"exits-1 (got {first.returncode})")
        if snapshot(work) != before:
            failed.append("refusal-leaves-repo-unchanged")
        return failed
    if first.returncode != 0:
        return [f"exits-0 (got {first.returncode}: {first.stderr.strip()})"]
    after_first = snapshot(work)
    second = subprocess.run(
        [str(script), SKILL], cwd=work, check=False, capture_output=True, text=True
    )
    if second.returncode != 0 or snapshot(work) != after_first:
        failed.append("second-run-changes-nothing")

    must(work, "add", "-A")
    must(work, "commit", "-qm", "add the demo skill")
    if (work / ".agents" / "skills" / SKILL / SKILL).is_symlink():
        failed.append("no-stray-link-in-skill-folder")
    must(work, "push", "-q", "origin", "main")

    must(base, "clone", "-q", str(remote), str(clone))
    if not (clone / ".agents" / "skills" / SKILL / "scripts" / "check.py").is_file():
        failed.append("commit-holds-the-skill")
    if not resolves(clone) or link_mode(clone, scenario.outcome) != "120000":
        failed.append("fresh-clone-lists-the-skill")
    if (
        scenario.before == "team-skills-folder"
        and not (clone / ".claude" / "skills" / "team" / "SKILL.md").is_file()
    ):
        failed.append("team-skill-still-tracked")

    pulled = git(teammate, "pull", "-q", "--ff-only")
    if pulled.returncode != 0:
        failed.append(f"teammate-pull-succeeds ({pulled.stderr.strip()})")
    if personal is not None and not personal.is_file():
        failed.append("teammate-keeps-personal-skill")
    if not resolves(teammate):
        failed.append("teammate-lists-the-skill")
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--script",
        type=Path,
        default=SCRIPT,
        help="the link script to run (default: the swe plugin's copy)",
    )
    parser.add_argument("scenarios", nargs="*", help="run only these scenarios")
    args = parser.parse_args()
    chosen = [s for s in SCENARIOS if not args.scenarios or s.name in args.scenarios]
    script = args.script.resolve()

    with tempfile.TemporaryDirectory(prefix="project-skill-link-") as tmp:
        home = Path(tmp) / "xdg"
        home.mkdir()
        os.environ |= {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "XDG_CONFIG_HOME": str(home),
            "GIT_AUTHOR_NAME": "throwaway",
            "GIT_AUTHOR_EMAIL": "throwaway@example.invalid",
            "GIT_COMMITTER_NAME": "throwaway",
            "GIT_COMMITTER_EMAIL": "throwaway@example.invalid",
        }
        passed = 0
        for scenario in chosen:
            base = Path(tmp) / scenario.name
            base.mkdir()
            failed = run_scenario(base, scenario, script)
            if failed:
                print(f"FAIL {scenario.name}: {', '.join(failed)}")
            else:
                passed += 1
                print(f"PASS {scenario.name}")
    print(f"{passed}/{len(chosen)} scenarios pass")
    return 0 if passed == len(chosen) else 1


if __name__ == "__main__":
    sys.exit(main())
