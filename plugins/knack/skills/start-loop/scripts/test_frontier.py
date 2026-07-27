"""Prove frontier.py finds exactly the workable issues in a Linear project and
fails loudly on auth/HTTP/GraphQL errors instead of silently.

The bug this guards: if an auth failure, HTTP error, or a GraphQL errors
payload were swallowed into an empty list, a graph round would read that as
"frontier is empty" and declare the run complete -- when it should escalate.
Every failure path here must raise/exit non-zero, never return [] on error.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from email.message import Message
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import frontier  # noqa: E402


def issue_node(id_, identifier, title, state_type, labels=None, relations=None):
    """`relations` is a list of (relation_type, blocker_state) pairs. Each node
    carries both `issue` (the blocker, with its own state) and `relatedIssue`
    (the current issue itself) -- matching the live Linear schema, where
    `relatedIssue` always resolves back to this issue, not the blocker.
    """
    return {
        "id": id_,
        "identifier": identifier,
        "title": title,
        "state": {"type": state_type},
        "labels": {"nodes": [{"name": name} for name in (labels or [])]},
        "inverseRelations": {
            "nodes": [
                {
                    "type": relation_type,
                    "issue": {"state": {"type": blocker_state}},
                    "relatedIssue": {"state": {"type": state_type}},
                }
                for relation_type, blocker_state in (relations or [])
            ]
        },
    }


def paged_response(nodes, has_next=False, end_cursor=None):
    return {
        "data": {
            "issues": {
                "nodes": nodes,
                "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor},
            }
        }
    }


def single_page_fetch(nodes):
    def fetch(query, variables):
        return paged_response(nodes)

    return fetch


def test_mixed_container_yields_exactly_the_workable_issues():
    nodes = [
        issue_node("1", "AB-1", "open unblocked", "started"),
        issue_node(
            "2",
            "AB-2",
            "open blocked by open",
            "started",
            relations=[("blocks", "started")],
        ),
        issue_node(
            "3",
            "AB-3",
            "open blocked by done",
            "started",
            relations=[("blocks", "completed")],
        ),
        issue_node("4", "AB-4", "done", "completed"),
        issue_node("5", "AB-5", "canceled", "canceled"),
        issue_node(
            "6", "AB-6", "ready for human", "started", labels=["ready-for-human"]
        ),
        issue_node(
            "7",
            "AB-7",
            "open with unrelated open relation",
            "started",
            relations=[("related", "started")],
        ),
    ]

    result = frontier.workable_issues("proj-1", single_page_fetch(nodes))

    assert [issue["identifier"] for issue in result] == ["AB-1", "AB-3", "AB-7"]
    assert result[0] == {
        "id": "1",
        "identifier": "AB-1",
        "title": "open unblocked",
        "labels": [],
    }


def test_empty_project_yields_empty_list():
    result = frontier.workable_issues("proj-empty", single_page_fetch([]))

    assert result == []


def test_paginated_response_is_fully_consumed():
    page1 = issue_node("1", "AB-1", "first page", "started")
    page2 = issue_node("2", "AB-2", "second page", "started")
    calls = []

    def fetch(query, variables):
        calls.append(variables)
        if variables["after"] is None:
            return paged_response([page1], has_next=True, end_cursor="cursor-1")
        assert variables["after"] == "cursor-1"
        return paged_response([page2], has_next=False)

    result = frontier.workable_issues("proj-1", fetch)

    assert [issue["identifier"] for issue in result] == ["AB-1", "AB-2"]
    assert len(calls) == 2


def test_graphql_errors_payload_raises():
    def fetch(query, variables):
        return {"errors": [{"message": "Argument Validation Error"}]}

    with pytest.raises(frontier.FrontierError, match="Argument Validation Error"):
        frontier.workable_issues("proj-1", fetch)


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)

    with pytest.raises(frontier.FrontierError, match="LINEAR_API_KEY"):
        frontier.fetch_graphql("query {}", {})


def test_http_error_raises(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "test-key")

    def raise_http_error(request):
        raise urllib.error.HTTPError(
            frontier.LINEAR_API_URL, 401, "Unauthorized", Message(), None
        )

    monkeypatch.setattr(frontier.urllib.request, "urlopen", raise_http_error)

    with pytest.raises(frontier.FrontierError, match="HTTP 401"):
        frontier.fetch_graphql("query {}", {})


def test_cli_missing_api_key_exits_nonzero(monkeypatch, capsys):
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["frontier", "--project", "proj-1"])

    exit_code = frontier.main()

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "LINEAR_API_KEY" in captured.err
    assert captured.out == ""


def test_cli_prints_json_array_and_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["frontier", "--project", "proj-1"])
    monkeypatch.setattr(frontier, "fetch_graphql", single_page_fetch([]))

    exit_code = frontier.main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
