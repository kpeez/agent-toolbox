#!/usr/bin/env python3
"""Deterministic Linear operations for the swe-loop.

Two verbs:

  workable  -- the issues in a container that can be picked up right now
  container -- resolve (or record) the Linear project a spec publishes into

Everything reaches Linear through the `linear` CLI, so this file holds policy
rather than transport: no GraphQL, no auth, no pagination of its own.

Why a slice counts as done is the subtle part. A slice the loop merged has not
changed state in Linear -- that only happens when the run's PR lands -- so
judging by tracker state alone strands every dependent slice and drains the
frontier after the first round of a chain. The authority is git: a slice whose
branch is merged into the integration branch is done, full stop. Tracker state
is the human-visible projection of that, never the thing correctness rests on.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CLOSED_STATE_TYPES = {"completed", "canceled"}
READY_FOR_HUMAN_LABEL = "ready-for-human"
BLOCKS_RELATION_TYPE = "blocks"
# `knack/slice/` is the pre-rename prefix; both are accepted so a run already
# in flight when this ships still has its branches recognised.
SLICE_BRANCH_RE = re.compile(r"^(?:knack/)?slice/(?P<identifier>.+)$")
# Written into a spec's YAML frontmatter. `project:` is already taken by the
# llmOS vault link, hence the tracker_ prefix.
CONTAINER_KEY = "tracker_container"
TRACKER_KEY = "tracker"
# The pre-frontmatter identity token, still in the body of containers created
# before this change. Read to migrate, never written.
LEGACY_MARKER_RE = re.compile(
    r"<!--\s*knack-spec:\s*(?P<repo>[^/\s]+)/(?P<slug>\S+?)\s*-->"
)

EXIT_OK = 0
EXIT_ERROR = 1
# Distinct on purpose: a broken link must never be read as "no container yet",
# because the caller may create a container on EXIT_NO_CONTAINER and conflating
# the two is exactly how a run creates a duplicate project.
EXIT_BROKEN_LINK = 2
EXIT_NO_CONTAINER = 3


class LinearError(Exception):
    """A failed `linear` invocation, or a response that could not be parsed."""


def run_linear(args: list[str]) -> str:
    """Run the `linear` CLI and return stdout, raising on a non-zero exit."""
    try:
        result = subprocess.run(
            ["linear", *args], capture_output=True, text=True, check=False
        )
    except FileNotFoundError as exc:
        raise LinearError(
            "the `linear` CLI is not installed or not on PATH "
            "(brew install schpet/tap/linear)"
        ) from exc
    if result.returncode != 0:
        raise LinearError(f"linear {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise LinearError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def load_json(payload: str, what: str) -> dict:
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise LinearError(f"{what} did not return JSON: {payload[:200]}") from exc


# ---- workable ---------------------------------------------------------------


def merged_slice_identifiers(base_branch: str, run_git_fn=run_git) -> set[str]:
    """Identifiers whose slice branch is already merged into `base_branch`."""
    output = run_git_fn(
        ["branch", "--merged", base_branch, "--format=%(refname:short)"]
    )
    identifiers = set()
    for line in output.splitlines():
        match = SLICE_BRANCH_RE.match(line.strip())
        if match:
            identifiers.add(match.group("identifier"))
    return identifiers


def fetch_container_issues(container_id: str, run_linear_fn=run_linear) -> list[dict]:
    payload = run_linear_fn(
        [
            "issue",
            "query",
            "--project",
            container_id,
            "--all-teams",
            "--json",
            "--no-pager",
        ]
    )
    data = load_json(payload, "linear issue query")
    return data["nodes"] if isinstance(data, dict) else data


def is_done(issue: dict, merged: set[str]) -> bool:
    if issue["state"]["type"] in CLOSED_STATE_TYPES:
        return True
    return issue.get("identifier") in merged


def workable_issues(
    container_id: str,
    base_branch: str | None = None,
    run_linear_fn=run_linear,
    run_git_fn=run_git,
) -> list[dict]:
    """Issues that are not done, not blocked, and not flagged for a human."""
    merged = merged_slice_identifiers(base_branch, run_git_fn) if base_branch else set()
    result = []
    for issue in fetch_container_issues(container_id, run_linear_fn):
        if is_done(issue, merged):
            continue
        labels = [node["name"] for node in (issue.get("labels") or {}).get("nodes", [])]
        if READY_FOR_HUMAN_LABEL in labels:
            continue
        blockers = [
            relation["issue"]
            for relation in (issue.get("inverseRelations") or {}).get("nodes", [])
            if relation["type"] == BLOCKS_RELATION_TYPE
        ]
        if not all(is_done(blocker, merged) for blocker in blockers):
            continue
        result.append(
            {
                "id": issue["id"],
                "identifier": issue["identifier"],
                "title": issue["title"],
                "labels": labels,
            }
        )
    return result


# ---- spec frontmatter -------------------------------------------------------


def frontmatter_bounds(lines: list[str]) -> tuple[int, int] | None:
    """Index of the opening and closing `---` of a spec's frontmatter block."""
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return 0, index
    return None


def read_frontmatter_value(text: str, key: str) -> str | None:
    lines = text.splitlines()
    bounds = frontmatter_bounds(lines)
    if bounds is None:
        return None
    _, close = bounds
    for line in lines[1:close]:
        name, separator, value = line.partition(":")
        if separator and name.strip() == key:
            return value.strip() or None
    return None


def write_frontmatter_value(text: str, key: str, value: str) -> str:
    """Set `key` in the frontmatter, editing lines rather than round-tripping.

    Specs carry nested YAML (authors, categories) that a naive dict round-trip
    would flatten and destroy, so the block is edited in place: replace the
    key's line when present, otherwise insert before the closing delimiter.
    """
    lines = text.splitlines()
    bounds = frontmatter_bounds(lines)
    if bounds is None:
        raise LinearError("spec has no YAML frontmatter block to write into")
    _, close = bounds
    for index in range(1, close):
        name, separator, _ = lines[index].partition(":")
        if separator and name.strip() == key:
            lines[index] = f"{key}: {value}"
            break
    else:
        lines.insert(close, f"{key}: {value}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


# ---- container --------------------------------------------------------------


def container_exists(container_id: str, run_linear_fn=run_linear) -> bool:
    """`project view` exits 0 for a real project and 1 for a missing one.

    Deliberately no --json: that flag does not exist on this subcommand and
    passing it exits 2 on every id, which reads every live container as
    missing and turns the whole sweep into broken-link reports.
    """
    try:
        run_linear_fn(["project", "view", container_id])
    except LinearError:
        return False
    return True


def find_legacy_containers(slug: str, run_linear_fn=run_linear) -> list[dict]:
    """Projects whose body still carries the pre-frontmatter identity token."""
    payload = run_linear_fn(
        [
            "api",
            "query { projects(first: 250) { nodes { id name description content } } }",
        ]
    )
    data = load_json(payload, "linear api")
    matches = []
    for node in data["data"]["projects"]["nodes"]:
        body = (node.get("description") or "") + (node.get("content") or "")
        if any(m.group("slug") == slug for m in LEGACY_MARKER_RE.finditer(body)):
            matches.append(node)
    return matches


def slug_for(spec_path: Path) -> str:
    """`0002-morphometric-baselines.md` -> `morphometric-baselines`."""
    numbered = re.match(r"^\d+-(?P<slug>.+)$", spec_path.stem)
    return numbered.group("slug") if numbered else spec_path.stem


def resolve_container(
    spec_path: Path, run_linear_fn=run_linear
) -> tuple[int, str | None, str]:
    """Resolve a spec's container. Returns (exit code, container id, message)."""
    recorded = read_frontmatter_value(spec_path.read_text(), CONTAINER_KEY)
    if recorded:
        if container_exists(recorded, run_linear_fn):
            return EXIT_OK, recorded, f"{spec_path.name}: {recorded} (frontmatter)"
        return (
            EXIT_BROKEN_LINK,
            None,
            f"{spec_path.name} names container {recorded}, which does not exist. "
            "Re-link with --set <id> or fix the spec; refusing to create a second container.",
        )

    slug = slug_for(spec_path)
    legacy = find_legacy_containers(slug, run_linear_fn)
    if len(legacy) > 1:
        names = ", ".join(f"{node['name']} ({node['id']})" for node in legacy)
        return (
            EXIT_BROKEN_LINK,
            None,
            f"{spec_path.name}: {len(legacy)} containers carry the legacy marker "
            f"for '{slug}' — {names}. Pick one with --set <id>.",
        )
    if len(legacy) == 1:
        return (
            EXIT_OK,
            legacy[0]["id"],
            f"{spec_path.name}: {legacy[0]['id']} (legacy marker, needs backfill)",
        )
    return EXIT_NO_CONTAINER, None, f"{spec_path.name}: no container"


def set_container(spec_path: Path, container_id: str, tracker: str = "linear") -> None:
    text = spec_path.read_text()
    text = write_frontmatter_value(text, TRACKER_KEY, tracker)
    text = write_frontmatter_value(text, CONTAINER_KEY, container_id)
    spec_path.write_text(text)


def backfill_all(
    specs_dir: Path, dry_run: bool, run_linear_fn=run_linear
) -> tuple[int, list[str]]:
    """Record the container of every spec that resolves through the legacy marker."""
    report = []
    linked = 0
    for spec_path in sorted(specs_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        # Already-linked specs are resolved too, not skipped on sight: a sweep
        # that reports "already linked" for a container that no longer exists
        # produces exactly the mapping it was run to make trustworthy.
        already_linked = read_frontmatter_value(spec_path.read_text(), CONTAINER_KEY)
        code, container_id, message = resolve_container(spec_path, run_linear_fn)
        if code == EXIT_BROKEN_LINK:
            report.append(f"STOP  {message}")
            continue
        if code == EXIT_NO_CONTAINER:
            report.append(f"skip  {message}")
            continue
        assert container_id is not None  # EXIT_OK always carries a resolved id
        if already_linked:
            report.append(f"skip  {spec_path.name}: already linked ({container_id})")
            continue
        verb = "would link" if dry_run else "link"
        report.append(f"{verb}  {spec_path.name} -> {container_id}")
        if not dry_run:
            set_container(spec_path, container_id)
        linked += 1
    return linked, report


# ---- sync -------------------------------------------------------------------

PROJECT_QUERY = (
    'query {{ project(id: "{container_id}") {{ id name status {{ type }} }} }}'
)
# Statuses that claim no work has begun. Any of these while issues are underway
# is the lie this verb exists to correct.
NOT_STARTED_STATUSES = {"backlog", "planned"}
STARTED_STATE_TYPES = {"started", "completed"}


def project_status(container_id: str, run_linear_fn=run_linear) -> tuple[str, str]:
    payload = run_linear_fn(["api", PROJECT_QUERY.format(container_id=container_id)])
    project = load_json(payload, "linear api")["data"]["project"]
    return project["name"], project["status"]["type"]


def sync_project(
    container_id: str, dry_run: bool = False, run_linear_fn=run_linear
) -> list[str]:
    """Promote a project whose issues are underway out of a not-started status.

    Promote-only, deliberately. A run ends at a draft PR, so "every issue is
    done" is not delivery and auto-completing a project would assert something
    the loop cannot know; that case is reported for a human instead.
    """
    name, status = project_status(container_id, run_linear_fn)
    issues = fetch_container_issues(container_id, run_linear_fn)
    if not issues:
        return [f"{name}: no issues, nothing to sync"]

    underway = [i for i in issues if i["state"]["type"] in STARTED_STATE_TYPES]
    unfinished = [i for i in issues if i["state"]["type"] not in CLOSED_STATE_TYPES]
    report = []
    if underway and status in NOT_STARTED_STATUSES:
        report.append(
            f"{name}: {len(underway)}/{len(issues)} issue(s) underway but project is "
            f"'{status}' — {'would set' if dry_run else 'setting'} it to 'started'"
        )
        if not dry_run:
            run_linear_fn(["project", "update", container_id, "--status", "started"])
    else:
        report.append(f"{name}: status '{status}' is consistent with its issues")
    if not unfinished and status != "completed":
        report.append(
            f"{name}: every issue is closed — consider completing the project "
            f"(not done automatically: the run ends at a draft PR, not a merge)"
        )
    return report


# ---- cli --------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(prog="linear_tracker")
    verbs = parser.add_subparsers(dest="verb", required=True)

    workable = verbs.add_parser("workable", help="issues that can be worked right now")
    workable.add_argument("--container", required=True, metavar="ID")
    workable.add_argument(
        "--merged-into",
        metavar="BRANCH",
        help="integration branch; slices already merged into it count as done",
    )

    container = verbs.add_parser(
        "container", help="resolve or record a spec's container"
    )
    container.add_argument("--spec", type=Path, metavar="PATH")
    container.add_argument("--set", dest="container_id", metavar="ID")
    container.add_argument("--backfill-all", type=Path, metavar="SPECS_DIR")
    container.add_argument("--dry-run", action="store_true")

    sync = verbs.add_parser("sync", help="reconcile a project's status with its issues")
    sync.add_argument("--container", required=True, metavar="ID")
    sync.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    try:
        if args.verb == "workable":
            print(json.dumps(workable_issues(args.container, args.merged_into)))
            return EXIT_OK

        if args.verb == "sync":
            for line in sync_project(args.container, args.dry_run):
                print(line)
            return EXIT_OK

        if args.backfill_all:
            linked, report = backfill_all(args.backfill_all, args.dry_run)
            for line in report:
                print(line)
            print(f"{linked} spec(s) {'would be ' if args.dry_run else ''}linked")
            return EXIT_OK
        if not args.spec:
            parser.error("container needs --spec or --backfill-all")
        if args.container_id:
            set_container(args.spec, args.container_id)
            print(args.container_id)
            return EXIT_OK
        code, container_id, message = resolve_container(args.spec)
        if code == EXIT_OK:
            print(container_id)
            return EXIT_OK
        print(message, file=sys.stderr)
        return code
    except LinearError as exc:
        print(f"linear_tracker: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
