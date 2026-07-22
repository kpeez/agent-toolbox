#!/usr/bin/env python3
"""Write the machine-owned `## Projects` block of daily notes from GitHub activity.

Fetch -> hash -> one model call -> verify -> write.
Deterministic script, not an agent. Processes today and yesterday (local time).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from llmos_vault import frontmatter
from llmos_vault.root import vault_root

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
MODEL = "claude-sonnet-5"
MARKER_START = "<!-- llmos-activity:start"
MARKER_END = "<!-- llmos-activity:end -->"
DISALLOWED_TOOLS = "Bash,Read,Write,Edit,MultiEdit,Glob,Grep,Task,WebFetch,WebSearch,NotebookEdit"
SYSTEM_PROMPT = (
    "You are a deterministic text transformer inside a script. You receive JSON of one "
    "day's GitHub activity grouped by project and emit only GitHub-flavored markdown. "
    "No preamble, no code fences around the whole output, no tool use."
)


@dataclass(frozen=True)
class Project:
    slug: str
    title: str
    repos: tuple[str, ...]


class DigestError(RuntimeError):
    pass


def read_projects(root: Path) -> tuple[list[Project], list[Project]]:
    """Return (monitored, active_but_unseen) projects from projects/*/<slug>.md."""
    monitored: list[Project] = []
    unseen: list[Project] = []
    for note_path in sorted(root.glob("projects/*/*.md")):
        if note_path.stem != note_path.parent.name:
            continue
        props, body = frontmatter.parse(note_path.read_text(encoding="utf-8"))
        if props.get("status") != "active":
            continue
        repos_value = props.get("repositories") or []
        if isinstance(repos_value, str):
            repos_value = [repos_value] if repos_value else []
        title_match = re.search(r"^# (.+)$", body, flags=re.MULTILINE)
        title = title_match.group(1).strip() if title_match else note_path.stem
        project = Project(slug=note_path.stem, title=title, repos=tuple(repos_value))
        if project.repos:
            monitored.append(project)
        else:
            unseen.append(project)
    if not monitored:
        raise DigestError("no monitored projects found -- allowlist is empty")
    return monitored, unseen


def day_range(day: date) -> str:
    """UTC-offset-explicit local range for gh date qualifiers (handles PDT/PST)."""
    start = datetime.combine(day, time.min, tzinfo=LOCAL_TZ)
    end = datetime.combine(day, time(23, 59, 59), tzinfo=LOCAL_TZ)
    return f"{start.isoformat()}..{end.isoformat()}"


def run_gh(args: list[str]) -> list[dict]:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise DigestError(f"gh {' '.join(args[:3])} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def fetch_activity(day: date, repos: list[str], gh=run_gh) -> dict:
    """Four gh search calls. Every repo must be reachable; a 404 is a hard failure."""
    repo_flags: list[str] = []
    for repo in repos:
        repo_flags += ["--repo", repo]
    rng = day_range(day)
    pr_fields = "number,title,body,url,repository,state"
    merged = gh(
        ["search", "prs", *repo_flags, "--merged-at", rng, "--json", pr_fields, "--limit", "100"]
    )
    opened = gh(
        ["search", "prs", *repo_flags, "--created", rng, "--json", pr_fields, "--limit", "100"]
    )
    issues = gh(
        [
            "search", "issues", *repo_flags, "--updated", rng,
            "--json", "number,title,body,url,repository,state,createdAt,closedAt",
            "--limit", "100",
        ]
    )
    commits = gh(
        [
            "search", "commits", *repo_flags, "--author-date", rng,
            "--json", "sha,commit,repository,url", "--limit", "100",
        ]
    )

    def in_range(ts: str | None) -> bool:
        if not ts:
            return False
        try:
            # gh emits "0001-01-01T00:00:00Z" for closedAt on open issues;
            # converting year 1 to a western offset underflows date range.
            local = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(LOCAL_TZ)
        except OverflowError:
            return False
        return local.date() == day

    return {
        "merged_prs": merged,
        "opened_prs": [p for p in opened if p["number"] not in {m["number"] for m in merged}],
        "issues_created": [i for i in issues if in_range(i.get("createdAt"))],
        "issues_closed": [i for i in issues if in_range(i.get("closedAt"))],
        "commits": commits,
    }


def group_by_project(activity: dict, projects: list[Project]) -> dict[str, dict]:
    repo_to_project = {repo: p for p in projects for repo in p.repos}
    grouped: dict[str, dict] = {}
    for kind, items in activity.items():
        for item in items:
            repo_obj = item.get("repository", {})
            # gh search prs/issues -> nameWithOwner; gh search commits -> fullName
            repo = repo_obj.get("nameWithOwner") or repo_obj.get("fullName")
            project = repo_to_project.get(repo)
            if project is None:
                raise DigestError(f"activity in unmapped repo {repo!r}")
            bucket = grouped.setdefault(
                project.slug, {"title": project.title, "repos": {}}
            )
            bucket["repos"].setdefault(repo, {}).setdefault(kind, []).append(item)
    return grouped


def normalized_hash(grouped: dict) -> str:
    return hashlib.sha256(
        json.dumps(grouped, sort_keys=True, ensure_ascii=True).encode()
    ).hexdigest()


def expected_references(grouped: dict) -> set[str]:
    refs: set[str] = set()
    for bucket in grouped.values():
        for kinds in bucket["repos"].values():
            for kind, items in kinds.items():
                if kind == "commits":
                    continue
                refs.update(f"#{item['number']}" for item in items)
    return refs


def summarize(grouped: dict, day: date, claude_bin: str = "claude") -> str:
    required = ", ".join(sorted(expected_references(grouped)))
    prompt = (
        f"GitHub activity for {day.isoformat()}, grouped by project. Write one `### <Title>` "
        "section per project (use the `title` field), in the given order. Under each, write a "
        "markdown bullet list — one bullet per distinct piece of work, never one large "
        "paragraph. Cite every PR and issue inline as a markdown link, "
        f"e.g. [#12](url). Every one of these references MUST appear in your output: {required}. "
        "Summarize commits briefly; do not list every commit. Base the prose on the `body` "
        "fields, not just titles. Output only the sections.\n\n"
        + json.dumps(grouped, indent=1, sort_keys=True)
    )
    result = subprocess.run(
        [
            claude_bin, "-p", "--model", MODEL,
            "--system-prompt", SYSTEM_PROMPT,
            "--disallowedTools", DISALLOWED_TOOLS,
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise DigestError(f"claude -p failed: {result.stderr.strip()[:500]}")
    return result.stdout.strip()


def check_completeness(prose: str, expected: set[str]) -> None:
    missing = sorted(ref for ref in expected if ref not in prose)
    if missing:
        raise DigestError(f"summary omitted references: {', '.join(missing)}")


def build_block(prose: str, unseen: list[Project], digest_hash: str) -> str:
    lines = [f"{MARKER_START} hash={digest_hash} -->", "", prose, ""]
    if unseen:
        names = ", ".join(f"[[{p.slug}|{p.title}]]" for p in unseen)
        lines += [f"_Not monitored (active, no repository): {names}_", ""]
    lines.append(MARKER_END)
    return "\n".join(lines)


def existing_hash(text: str) -> str | None:
    match = re.search(rf"{re.escape(MARKER_START)} hash=([0-9a-f]{{64}}) -->", text)
    return match.group(1) if match else None


def replace_block(text: str, block: str) -> str:
    start = text.find(MARKER_START)
    end = text.find(MARKER_END)
    if start != -1 and end != -1:
        return text[:start] + block + text[end + len(MARKER_END):]
    if start != -1 or end != -1:
        raise DigestError("unpaired llmos-activity markers -- refusing to write")
    heading = "## Projects"
    if heading in text:
        idx = text.index(heading) + len(heading)
        return text[:idx] + "\n\n" + block + text[idx:]
    return text.rstrip("\n") + f"\n\n{heading}\n\n{block}\n"


def atomic_write(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def process_day(day: date, root: Path, gh=run_gh, claude_bin: str = "claude") -> str:
    monitored, unseen = read_projects(root)
    repos = [repo for p in monitored for repo in p.repos]
    grouped = group_by_project(fetch_activity(day, repos, gh=gh), monitored)
    note_path = root / "reviews" / "daily" / f"{day.isoformat()}.md"

    if not grouped:
        return "silent (no note created)" if not note_path.exists() else "silent (note untouched)"

    digest_hash = normalized_hash(grouped)
    text = note_path.read_text(encoding="utf-8") if note_path.exists() else ""
    if existing_hash(text) == digest_hash:
        return "unchanged (hash match, no model call)"

    prose = summarize(grouped, day, claude_bin=claude_bin)
    check_completeness(prose, expected_references(grouped))
    block = build_block(prose, unseen, digest_hash)
    if text:
        atomic_write(note_path, replace_block(text, block))
        return "updated"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(note_path, f"# {day.isoformat()}\n\n## Projects\n\n{block}\n\n## Thoughts\n")
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="Vault root override.")
    parser.add_argument(
        "--date", type=date.fromisoformat, default=None,
        help="Process only this date (default: today and yesterday, local time).",
    )
    args = parser.parse_args()
    root = args.root or vault_root()
    today = datetime.now(LOCAL_TZ).date()
    days = [args.date] if args.date else [today - timedelta(days=1), today]
    for day in days:
        outcome = process_day(day, root)
        print(f"{day.isoformat()}: {outcome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
