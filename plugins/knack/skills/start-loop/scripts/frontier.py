#!/usr/bin/env python3
"""Print the workable Linear issues in a spec's project container, as JSON.

The query the knack-graph workflow runs each round to pick the next issues: an
issue is workable when its state isn't completed/canceled, nothing open still
blocks it, and it isn't labeled ready-for-human. Without a hard failure on
auth/HTTP/GraphQL errors, a round could silently treat an auth failure as an
empty frontier and declare the run complete -- this exits non-zero instead,
naming exactly what failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

LINEAR_API_URL = "https://api.linear.app/graphql"
CLOSED_STATE_TYPES = {"completed", "canceled"}
READY_FOR_HUMAN_LABEL = "ready-for-human"
BLOCKS_RELATION_TYPE = "blocks"

# labels and inverseRelations are bounded at 100 rather than paginated: an
# issue with more than 100 labels or blocking relations is not a realistic
# case for this tracker, so the bound stands in for full pagination.
ISSUES_QUERY = """
query WorkableIssues($projectId: ID!, $after: String) {
  issues(filter: { project: { id: { eq: $projectId } } }, after: $after, first: 50) {
    nodes {
      id
      identifier
      title
      state { type }
      labels(first: 100) { nodes { name } }
      inverseRelations(first: 100) {
        nodes {
          type
          issue { state { type } }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


class FrontierError(Exception):
    """Raised for a missing API key, an HTTP error, or a GraphQL errors payload."""


def fetch_graphql(query: str, variables: dict) -> dict:
    api_key = os.environ.get("LINEAR_API_KEY")
    if not api_key:
        raise FrontierError("LINEAR_API_KEY is not set in the environment")
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        LINEAR_API_URL,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise FrontierError(f"Linear API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise FrontierError(f"Linear API request failed: {exc.reason}") from exc


def is_open(state_type: str) -> bool:
    return state_type not in CLOSED_STATE_TYPES


def fetch_project_issues(project_id: str, fetch_graphql_fn) -> list[dict]:
    """Page through every issue in `project_id`, raising on a GraphQL errors payload."""
    issues: list[dict] = []
    cursor: str | None = None
    while True:
        response = fetch_graphql_fn(
            ISSUES_QUERY, {"projectId": project_id, "after": cursor}
        )
        if response.get("errors"):
            messages = "; ".join(e.get("message", str(e)) for e in response["errors"])
            raise FrontierError(f"Linear GraphQL error: {messages}")
        page = response["data"]["issues"]
        issues.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return issues
        cursor = page["pageInfo"]["endCursor"]


def workable_issues(project_id: str, fetch_graphql_fn) -> list[dict]:
    """Return the container's workable issues: open, unblocked, not ready-for-human."""
    result = []
    for issue in fetch_project_issues(project_id, fetch_graphql_fn):
        if not is_open(issue["state"]["type"]):
            continue
        labels = [node["name"] for node in issue["labels"]["nodes"]]
        if READY_FOR_HUMAN_LABEL in labels:
            continue
        blockers = (
            rel["issue"]
            for rel in issue["inverseRelations"]["nodes"]
            if rel["type"] == BLOCKS_RELATION_TYPE
        )
        if any(is_open(blocker["state"]["type"]) for blocker in blockers):
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


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="frontier",
        description="Print the workable Linear issues in a project, as a JSON array.",
    )
    parser.add_argument(
        "--project", required=True, metavar="ID", help="Linear project id"
    )
    args = parser.parse_args()
    try:
        issues = workable_issues(args.project, fetch_graphql)
    except FrontierError as exc:
        print(f"frontier: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(issues))
    return 0


if __name__ == "__main__":
    sys.exit(main())
