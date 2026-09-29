#!/usr/bin/env python3
"""Keep Linear project statuses in step with their issues.

Linear moves issues (the GitHub integration closes them on merge) but never
moves the project that holds them. This reconciles every open project from its
issues' current states, so a missed run is repaired by the next one.

Behavioral rules:
- A Backlog or Planned project with a started or completed issue becomes the
  workspace's first started status (In Progress).
- A Backlog, Planned, or started project whose issues are all closed
  (completed, canceled, or duplicate), with at least one completed, becomes the
  first completed status.
- Paused, Completed, and Canceled projects are never touched, so a follow-up
  issue added to a completed project does not reopen it.
- ``hook`` (the SessionStart hook) never blocks and always exits 0. It is
  silent without a Linear API key, prints one ``systemMessage`` JSON line
  naming each project it moved or the failure, and stops starting new requests
  after HOOK_BUDGET seconds.
- Uses the same Linear API key as plan_sync.py. Statuses are chosen from the
  workspace-level project statuses.

Usage: python3 project_status.py {sync,hook} --help
"""

import argparse
import json
import sys
import time

from plan_sync import SyncError, api_key, graphql

HOOK_BUDGET = 8  # a request started at the deadline adds up to TIMEOUT (5s); hooks.json allows 15s

STATUSES = """{ projectStatuses { nodes { id name type position team { id } } } }"""
PROJECTS = """query($after: String) {
  projects(first: 50, after: $after, filter: {status: {type: {in: ["backlog", "planned", "started"]}}}) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id name url trashed status { name type }
      progressed: issues(first: 1, filter: {state: {type: {in: ["started", "completed"]}}}) { nodes { id } }
      done: issues(first: 1, filter: {state: {type: {eq: "completed"}}}) { nodes { id } }
      open: issues(first: 1, filter: {state: {type: {nin: ["completed", "canceled", "duplicate"]}}}) { nodes { id } }
    }
  }
}"""
UPDATE = """mutation($id: String!, $input: ProjectUpdateInput!) {
  projectUpdate(id: $id, input: $input) { success }
}"""


def target(status_type, progressed, done, open_issues):
    """Return the status type a project should move to, or None to leave it."""
    if done and not open_issues:
        return "completed"
    if status_type in ("backlog", "planned") and progressed:
        return "started"
    return None


def first_statuses():
    """Map status type to the workspace's lowest-position status of that type."""
    chosen = {}
    for status in graphql(STATUSES, {})["projectStatuses"]["nodes"]:
        if status.get("team"):
            continue
        current = chosen.get(status["type"])
        if current is None or status["position"] < current["position"]:
            chosen[status["type"]] = status
    return chosen


def open_projects(deadline=None):
    after = None
    while True:
        if deadline is not None and time.monotonic() > deadline:
            return
        page = graphql(PROJECTS, {"after": after})["projects"]
        yield from (project for project in page["nodes"] if not project.get("trashed"))
        if not page["pageInfo"]["hasNextPage"]:
            return
        after = page["pageInfo"]["endCursor"]


def sync(dry_run=False, deadline=None):
    """Move drifted projects; return (moves, failures) as lists of messages."""
    statuses = first_statuses()
    moves, failures = [], []
    for project in open_projects(deadline):
        wanted = target(project["status"]["type"], bool(project["progressed"]["nodes"]),
                        bool(project["done"]["nodes"]), bool(project["open"]["nodes"]))
        if wanted is None:
            continue
        status = statuses.get(wanted)
        line = f"{project['name']}: {project['status']['name']} -> {status['name'] if status else wanted}"
        if status is None:
            failures.append(f"{line} (no workspace project status of type {wanted})")
            continue
        if not dry_run:
            if deadline is not None and time.monotonic() > deadline:
                break
            try:
                if not graphql(UPDATE, {"id": project["id"], "input": {"statusId": status["id"]}})["projectUpdate"]["success"]:
                    raise SyncError("Linear did not apply the update")
            except SyncError as error:
                failures.append(f"{line} ({error})")
                continue
        moves.append(line)
    return moves, failures


def run_hook():
    """SessionStart hook: reconcile project statuses without ever blocking the agent."""
    if not api_key():
        return 0
    try:
        moves, failures = sync(deadline=time.monotonic() + HOOK_BUDGET)
    except Exception as error:  # a hook must not fail the session
        moves, failures = [], [str(error)]
    parts = [f"moved {line}" for line in moves] + [f"failed {line}" for line in failures]
    if parts:
        print(json.dumps({"systemMessage": "project-status: " + "; ".join(parts)}))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Keep Linear project statuses in step with their issues.")
    commands = parser.add_subparsers(dest="command", required=True)
    sync_parser = commands.add_parser("sync", help="move every drifted open project now")
    sync_parser.add_argument("--dry-run", action="store_true", help="print the moves without making them")
    commands.add_parser("hook", help="SessionStart-hook entry point")
    args = parser.parse_args(argv)

    if args.command == "hook":
        return run_hook()
    try:
        moves, failures = sync(dry_run=args.dry_run)
    except SyncError as error:
        print(f"project_status.py: {error}", file=sys.stderr)
        return 1
    for line in moves:
        print(f"{'would move' if args.dry_run else 'moved'} {line}")
    for line in failures:
        print(f"failed {line}", file=sys.stderr)
    if not moves and not failures:
        print("all open projects match their issues")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
