#!/usr/bin/env python3
"""Workflow adapters for Linear records and GitHub pull-request evidence.

Python standard library only. Three adapter surfaces are defined here:

* ``LinearAdapter``  - read/write Linear records through GraphQL.
* ``FakeAdapter``    - deterministic in-memory or JSON-file stand-in.
* ``GitHubEvidence`` - read-only GitHub pull-request evidence.

Transport contract (injected)
-----------------------------
``LinearAdapter(token, *, transport=None, timeout=15)`` accepts an optional
``transport(query: str, variables: dict) -> dict``. The callable receives the
GraphQL document plus variables and returns the decoded GraphQL envelope
(``{"data": ...}`` and/or ``{"errors": [...]}``). A transport must raise
``AdapterError`` for HTTP or network failures. The adapter raises
``AdapterError`` for GraphQL ``errors`` and malformed envelopes. The default
transport uses ``urllib`` against the fixed public endpoint
``https://api.linear.app/graphql``. Writes are never retried automatically.

``GitHubEvidence(token=None, *, transport=None, timeout=15)`` accepts an
optional ``transport(method: str, path: str) -> object``. ``method`` is always
``"GET"`` because the adapter is read-only. ``path`` is an API path including
any query string, for example ``/repos/o/r/pulls/7``. The callable returns the
decoded JSON payload (object or list) and must raise ``AdapterError`` for HTTP
or network failures. The default transport uses ``urllib`` against
``https://api.github.com``.

Identity contract
-----------------
``create(kind, resource_id, payload)`` requires the caller to allocate a UUID4
and durably persist it *before* the call. This adapter never generates ids; it
validates and injects the caller's id. SDK-verified inputs accept an explicit
``id`` for all five resources.

Security
--------
Error messages are constructed locally and never embed credentials or raw
remote response bodies. ``FakeAdapter`` output is never live data; its
``capabilities()`` result is labelled ``source: "fake"``.

Schema evidence
---------------
Field and mutation names were verified against the published Linear SDK type
definitions and generated GraphQL documents. The deprecated ``Project.state``
scalar is never used; ``Project.status`` is used instead.
"""

from __future__ import annotations

import copy
import json
import os
import re
import socket
import tempfile
import urllib.error
import urllib.request
import uuid

__all__ = [
    "AdapterError",
    "LinearAdapter",
    "FakeAdapter",
    "GitHubEvidence",
    "LINEAR_GRAPHQL_URL",
    "GITHUB_API_URL",
    "MAX_PAGES",
    "FAKE_STATE_TODO",
    "FAKE_STATE_IN_PROGRESS",
    "FAKE_STATE_IN_REVIEW",
    "FAKE_STATE_DONE",
]

LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"
GITHUB_API_URL = "https://api.github.com"
USER_AGENT = "agent-toolbox-workflow/1.0"

# Upper bound on any adapter-driven pagination loop. Exceeding it is reported
# as an incomplete read, never a silent truncation.
MAX_PAGES = 100

_KINDS = ("project", "document", "issue", "relation", "comment")

_FAKE_CREATED_AT = "2020-01-01T00:00:00.000Z"
_FAKE_UPDATED_AT = "2020-01-02T00:00:00.000Z"

# Plain synthetic ids so a fixture can name them without private identifiers.
FAKE_STATE_TODO = "00000000-0000-4000-8000-000000000001"
FAKE_STATE_IN_PROGRESS = "00000000-0000-4000-8000-000000000002"
FAKE_STATE_IN_REVIEW = "00000000-0000-4000-8000-000000000003"
FAKE_STATE_DONE = "00000000-0000-4000-8000-000000000004"

FAKE_PROJECT_STATUS_PLANNED = "00000000-0000-4000-8000-000000000101"
FAKE_PROJECT_STATUS_STARTED = "00000000-0000-4000-8000-000000000102"
FAKE_PROJECT_STATUS_COMPLETED = "00000000-0000-4000-8000-000000000103"

_FAKE_STATE_MAP = {
    FAKE_STATE_TODO: ("Todo", "unstarted"),
    FAKE_STATE_IN_PROGRESS: ("In Progress", "started"),
    FAKE_STATE_IN_REVIEW: ("In Review", "started"),
    FAKE_STATE_DONE: ("Done", "completed"),
}

_FAKE_PROJECT_STATUS_MAP = {
    FAKE_PROJECT_STATUS_PLANNED: ("Planned", "planned"),
    FAKE_PROJECT_STATUS_STARTED: ("Started", "started"),
    FAKE_PROJECT_STATUS_COMPLETED: ("Completed", "completed"),
}


class AdapterError(Exception):
    """Adapter failure with a stable ``code`` and a locally built ``message``.

    ``message`` never contains credentials or raw remote response bodies.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__("%s: %s" % (code, message))


# ---------------------------------------------------------------------------
# GraphQL documents
# ---------------------------------------------------------------------------

_GET_PROJECT = """
query WorkflowProject($id: String!) {
  project(id: $id) {
    id
    name
    description
    content
    url
    archivedAt
    updatedAt
    labelIds
    status { id name type }
    teams { nodes { id } }
  }
}
""".strip()

_GET_DOCUMENT = """
query WorkflowDocument($id: String!) {
  document(id: $id) {
    id
    title
    content
    url
    archivedAt
    updatedAt
    project { id }
    issue { id }
    team { id }
  }
}
""".strip()

_GET_ISSUE = """
query WorkflowIssue($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    description
    url
    archivedAt
    updatedAt
    project { id }
    team { id }
    state { id name type }
    assignee { id }
    labels(first: 100) {
      nodes { id }
      pageInfo { hasNextPage endCursor }
    }
  }
}
""".strip()

_GET_ISSUE_LABELS = """
query WorkflowIssueLabels($id: String!, $after: String) {
  issue(id: $id) {
    id
    labels(first: 100, after: $after) {
      nodes { id }
      pageInfo { hasNextPage endCursor }
    }
  }
}
""".strip()

_GET_RELATION = """
query WorkflowIssueRelation($id: String!) {
  issueRelation(id: $id) {
    id
    type
    archivedAt
    updatedAt
    issue { id }
    relatedIssue { id }
  }
}
""".strip()

_GET_COMMENT = """
query WorkflowComment($id: String!) {
  comment(id: $id) {
    id
    body
    url
    archivedAt
    updatedAt
    issueId
    projectId
    issue { id }
    project { id }
  }
}
""".strip()

_GET_QUERIES = {
    "project": _GET_PROJECT,
    "document": _GET_DOCUMENT,
    "issue": _GET_ISSUE,
    "relation": _GET_RELATION,
    "comment": _GET_COMMENT,
}

_GET_RESULT_KEYS = {
    "project": "project",
    "document": "document",
    "issue": "issue",
    "relation": "issueRelation",
    "comment": "comment",
}

_CREATE_PROJECT = """
mutation WorkflowCreateProject($input: ProjectCreateInput!) {
  projectCreate(input: $input) {
    success
    project {
      id
      name
      description
      content
      url
      archivedAt
      updatedAt
      labelIds
      status { id name type }
      teams { nodes { id } }
    }
  }
}
""".strip()

_CREATE_DOCUMENT = """
mutation WorkflowCreateDocument($input: DocumentCreateInput!) {
  documentCreate(input: $input) {
    success
    document {
      id
      title
      content
      url
      archivedAt
      updatedAt
      project { id }
      issue { id }
      team { id }
    }
  }
}
""".strip()

_CREATE_ISSUE = """
mutation WorkflowCreateIssue($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue {
      id
      identifier
      title
      description
      url
      archivedAt
      updatedAt
      project { id }
      team { id }
      state { id name type }
      assignee { id }
      labels(first: 100) {
        nodes { id }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
""".strip()

_CREATE_RELATION = """
mutation WorkflowCreateIssueRelation($input: IssueRelationCreateInput!) {
  issueRelationCreate(input: $input) {
    success
    issueRelation {
      id
      type
      archivedAt
      updatedAt
      issue { id }
      relatedIssue { id }
    }
  }
}
""".strip()

_CREATE_COMMENT = """
mutation WorkflowCreateComment($input: CommentCreateInput!) {
  commentCreate(input: $input) {
    success
    comment {
      id
      body
      url
      archivedAt
      updatedAt
      issueId
      projectId
      issue { id }
      project { id }
    }
  }
}
""".strip()

_CREATE_QUERIES = {
    "project": _CREATE_PROJECT,
    "document": _CREATE_DOCUMENT,
    "issue": _CREATE_ISSUE,
    "relation": _CREATE_RELATION,
    "comment": _CREATE_COMMENT,
}

_CREATE_MUTATION_KEYS = {
    "project": "projectCreate",
    "document": "documentCreate",
    "issue": "issueCreate",
    "relation": "issueRelationCreate",
    "comment": "commentCreate",
}

_CREATE_OBJECT_KEYS = {
    "project": "project",
    "document": "document",
    "issue": "issue",
    "relation": "issueRelation",
    "comment": "comment",
}


_CAPABILITIES_QUERY = """
query WorkflowCapabilities {
  project: __type(name: "Project") { name fields { name } }
  document: __type(name: "Document") { name fields { name } }
  issue: __type(name: "Issue") { name fields { name } }
  issueRelation: __type(name: "IssueRelation") { name fields { name } }
  comment: __type(name: "Comment") { name fields { name } }
  projectStatus: __type(name: "ProjectStatus") { name fields { name } }
  projectCreateInput: __type(name: "ProjectCreateInput") {
    name inputFields { name type { kind name } }
  }
  documentCreateInput: __type(name: "DocumentCreateInput") {
    name inputFields { name type { kind name } }
  }
  issueCreateInput: __type(name: "IssueCreateInput") {
    name inputFields { name type { kind name } }
  }
  commentCreateInput: __type(name: "CommentCreateInput") {
    name inputFields { name type { kind name } }
  }
  issueRelationCreateInput: __type(name: "IssueRelationCreateInput") {
    name inputFields { name type { kind name } }
  }

  mutationType: __type(name: "Mutation") { name fields { name } }
}
""".strip()

_CAPABILITY_TYPE_ALIASES = {
    "project": "Project",
    "document": "Document",
    "issue": "Issue",
    "issueRelation": "IssueRelation",
    "comment": "Comment",
    "projectStatus": "ProjectStatus",
}

_CAPABILITY_INPUT_ALIASES = {
    "projectCreateInput": "ProjectCreateInput",
    "documentCreateInput": "DocumentCreateInput",
    "issueCreateInput": "IssueCreateInput",
    "commentCreateInput": "CommentCreateInput",
    "issueRelationCreateInput": "IssueRelationCreateInput",
}

_CREATE_META = (
    ("project", "projectCreate", "ProjectCreateInput"),
    ("document", "documentCreate", "DocumentCreateInput"),
    ("issue", "issueCreate", "IssueCreateInput"),
    ("relation", "issueRelationCreate", "IssueRelationCreateInput"),
    ("comment", "commentCreate", "CommentCreateInput"),
)

# Keys are the wire values of ``extensions.type`` (the Linear SDK's errorMap),
# not its LinearErrorType enum names.
_GRAPHQL_ERROR_CODES = {
    "authentication error": "authentication_error",
    "forbidden": "permission_denied",
    "feature not accessible": "feature_not_accessible",
    "invalid input": "invalid_input",
    "ratelimited": "rate_limited",
    "network error": "network_error",
    "internal error": "internal_error",
    "graphql error": "graphql_error",
    "user error": "user_error",
}

_REPO_PART = re.compile(r"^[A-Za-z0-9_.-]+$")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _validate_uuid4(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise AdapterError("invalid_input", "%s must be a UUID4 string" % field)
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise AdapterError("invalid_input", "%s must be a UUID4 string" % field) from None
    if parsed.version != 4:
        raise AdapterError("invalid_input", "%s must be a UUID4 string" % field)
    return str(parsed)


def _require_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdapterError("invalid_input", "%s must be a non-empty string" % field)
    return value


def _stringify(value: object) -> str:
    if isinstance(value, str):
        return value
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return str(value)


def _linked_id(node: dict, key: str) -> object:
    value = node.get(key)
    if isinstance(value, dict):
        return value.get("id")
    return None


def _http_error(status: int, service: str) -> AdapterError:
    if status == 401:
        code = "authentication_error"
    elif status == 403:
        code = "permission_denied"
    elif status == 404:
        code = "not_found"
    elif status == 422:
        code = "invalid_input"
    elif status == 429:
        code = "rate_limited"
    elif 500 <= status <= 599:
        code = "server_error"
    else:
        code = "http_error"
    return AdapterError(code, "%s API HTTP %d" % (service, status))


def _normalize_conclusion(conclusion: object) -> str:
    if conclusion is None or conclusion == "":
        return "pending"
    value = str(conclusion).lower()
    if value == "success":
        return "success"
    if value in (
        "failure",
        "error",
        "timed_out",
        "timeout",
        "cancelled",
        "canceled",
        "action_required",
        "startup_failure",
        "stale",
    ):
        return "failure"
    return "pending"


def _validate_repo(repo: str) -> str:
    if not isinstance(repo, str) or repo.count("/") != 1:
        raise AdapterError("invalid_input", "repo must be owner/name")
    owner, name = repo.split("/", 1)
    for part in (owner, name):
        if not part or part in (".", "..") or not _REPO_PART.match(part):
            raise AdapterError("invalid_input", "repo must be owner/name")
    return "%s/%s" % (owner, name)


def _validate_number(number: object) -> int:
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        raise AdapterError("invalid_input", "pull request number must be a positive integer")
    return number


# ---------------------------------------------------------------------------
# Default urllib transports
# ---------------------------------------------------------------------------

def _make_linear_transport(token: str, timeout: int):
    def transport(query: str, variables: dict) -> dict:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        request = urllib.request.Request(
            LINEAR_GRAPHQL_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": token,
                "User-Agent": USER_AGENT,
            },
        )
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            code = int(exc.code)
            exc.close()
            raise _http_error(code, "Linear") from None
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, socket.timeout):
                raise AdapterError("timeout", "Linear API request timed out") from None
            raise AdapterError("network_error", "Linear API request failed") from None
        except socket.timeout:
            raise AdapterError("timeout", "Linear API request timed out") from None
        except OSError:
            raise AdapterError("network_error", "Linear API request failed") from None
        try:
            with response:
                raw = response.read()
                status = getattr(response, "status", 200)
        except OSError:
            raise AdapterError("network_error", "Linear API read failed") from None
        if not (200 <= int(status) < 300):
            raise _http_error(int(status), "Linear")
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise AdapterError("malformed_response", "Linear API returned non-JSON") from None
        return envelope

    return transport


def _make_github_transport(token, timeout: int):
    def transport(method: str, path: str) -> object:
        if method != "GET":
            raise AdapterError("unsupported_operation", "GitHubEvidence is read-only")
        url = GITHUB_API_URL + path
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }
        if token:
            headers["Authorization"] = "Bearer %s" % token
        request = urllib.request.Request(url, method="GET", headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            code = int(exc.code)
            exc.close()
            raise _http_error(code, "GitHub") from None
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, socket.timeout):
                raise AdapterError("timeout", "GitHub API request timed out") from None
            raise AdapterError("network_error", "GitHub API request failed") from None
        except socket.timeout:
            raise AdapterError("timeout", "GitHub API request timed out") from None
        except OSError:
            raise AdapterError("network_error", "GitHub API request failed") from None
        try:
            with response:
                raw = response.read()
                status = getattr(response, "status", 200)
        except OSError:
            raise AdapterError("network_error", "GitHub API read failed") from None
        if not (200 <= int(status) < 300):
            raise _http_error(int(status), "GitHub")
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise AdapterError("malformed_response", "GitHub API returned non-JSON") from None

    return transport


# ---------------------------------------------------------------------------
# Linear
# ---------------------------------------------------------------------------

class LinearAdapter:
    """Linear GraphQL adapter with an injectable transport."""

    def __init__(self, token: str, *, transport=None, timeout: int = 15) -> None:
        self._token = token
        self._timeout = timeout
        self._transport = transport if transport is not None else _make_linear_transport(token, timeout)

    # -- transport plumbing -------------------------------------------------

    def _call(self, query: str, variables: dict) -> dict:
        try:
            envelope = self._transport(query, variables)
        except AdapterError:
            raise
        except Exception as exc:  # transport contract violation
            raise AdapterError("network_error", "transport failed (%s)" % type(exc).__name__) from None
        if not isinstance(envelope, dict):
            raise AdapterError("malformed_response", "GraphQL envelope is not an object")
        errors = envelope.get("errors")
        if errors:
            raise self._classify_errors(errors)
        data = envelope.get("data")
        if not isinstance(data, dict):
            raise AdapterError("malformed_response", "GraphQL envelope has no data object")
        return data

    @staticmethod
    def _classify_errors(errors: object) -> AdapterError:
        if not isinstance(errors, list) or not errors:
            return AdapterError("graphql_error", "Linear GraphQL error")
        first = errors[0] if isinstance(errors[0], dict) else {}
        extensions = first.get("extensions")
        raw_type = extensions.get("type") if isinstance(extensions, dict) else None
        code = _GRAPHQL_ERROR_CODES.get(raw_type, "graphql_error")
        return AdapterError(code, "Linear GraphQL error (%s)" % (raw_type or "unknown"))

    @staticmethod
    def _check_kind(kind: str) -> str:
        if kind not in _KINDS:
            raise AdapterError("unsupported_kind", "unsupported resource kind")
        return kind

    # -- schema capabilities ------------------------------------------------

    def capabilities(self) -> dict:
        """Introspect read-only schema fields and available create inputs."""
        data = self._call(_CAPABILITIES_QUERY, {})
        types = {}
        for alias, type_name in _CAPABILITY_TYPE_ALIASES.items():
            node = data.get(alias)
            names = []
            if isinstance(node, dict):
                names = sorted(
                    field.get("name")
                    for field in (node.get("fields") or [])
                    if isinstance(field, dict) and field.get("name")
                )
            types[type_name] = names

        inputs = {}
        for alias, input_name in _CAPABILITY_INPUT_ALIASES.items():
            node = data.get(alias)
            fields = []
            required = []
            if isinstance(node, dict):
                for field in node.get("inputFields") or []:
                    if not isinstance(field, dict) or not field.get("name"):
                        continue
                    fields.append(field["name"])
                    field_type = field.get("type") or {}
                    if isinstance(field_type, dict) and field_type.get("kind") == "NON_NULL":
                        required.append(field["name"])
            inputs[input_name] = {"fields": sorted(fields), "required": sorted(required)}

        mutation_node = data.get("mutationType")
        mutation_fields = set()
        if isinstance(mutation_node, dict):
            mutation_fields = {
                field.get("name")
                for field in (mutation_node.get("fields") or [])
                if isinstance(field, dict) and field.get("name")
            }

        creates = {}
        for kind, mutation_name, input_name in _CREATE_META:
            info = inputs.get(input_name, {"fields": [], "required": []})
            creates[kind] = {
                "supported": (
                    mutation_name in mutation_fields
                    and input_name in inputs
                    and "id" in info["fields"]
                ),
                "mutation": mutation_name,
                "input_type": input_name,
                "id_supported": "id" in info["fields"],
                "required_fields": list(info["required"]),
            }

        return {
            "endpoint": LINEAR_GRAPHQL_URL,
            "read_only": True,
            "source": "live_schema",
            "types": types,
            "input_fields": inputs,
            "creates": creates,
            "project_status_field": "status" in types.get("Project", []),
        }

    # -- reads --------------------------------------------------------------

    def get(self, kind: str, resource_id: str):
        """Return a normalized record, or ``None`` only for definite not-found.

        GraphQL or transport errors raise ``AdapterError`` and are never folded
        into a missing result. Archived records are returned by id with
        ``archived`` set.
        """
        kind = self._check_kind(kind)
        rid = _require_id(resource_id, "resource_id")
        data = self._call(_GET_QUERIES[kind], {"id": rid})
        if _GET_RESULT_KEYS[kind] not in data:
            raise AdapterError("malformed_response", "record field missing from GraphQL data")
        node = data[_GET_RESULT_KEYS[kind]]
        if node is None:
            return None
        if not isinstance(node, dict):
            raise AdapterError("malformed_response", "record is not an object")
        return self._normalize(kind, node)

    def _collect_issue_labels(self, issue_node: dict) -> list:
        labels = issue_node.get("labels")
        if not isinstance(labels, dict):
            raise AdapterError("incomplete_pagination", "issue labels connection missing")
        nodes = labels.get("nodes")
        if not isinstance(nodes, list):
            raise AdapterError("malformed_response", "issue labels nodes missing")
        label_ids = [node.get("id") for node in nodes if isinstance(node, dict)]
        page_info = labels.get("pageInfo")
        if not isinstance(page_info, dict):
            raise AdapterError("incomplete_pagination", "issue labels pageInfo missing")
        pages = 0
        while page_info.get("hasNextPage"):
            cursor = page_info.get("endCursor")
            if not cursor:
                raise AdapterError("incomplete_pagination", "labels page missing endCursor")
            pages += 1
            if pages > MAX_PAGES:
                raise AdapterError("incomplete_pagination", "labels pagination exceeded page bound")
            data = self._call(_GET_ISSUE_LABELS, {"id": issue_node.get("id"), "after": cursor})
            next_issue = data.get("issue")
            if not isinstance(next_issue, dict):
                raise AdapterError("incomplete_pagination", "labels page missing issue")
            labels = next_issue.get("labels")
            if not isinstance(labels, dict) or not isinstance(labels.get("nodes"), list):
                raise AdapterError("malformed_response", "labels page nodes missing")
            label_ids.extend(n.get("id") for n in labels["nodes"] if isinstance(n, dict))
            page_info = labels.get("pageInfo")
            if not isinstance(page_info, dict):
                raise AdapterError("incomplete_pagination", "labels page pageInfo missing")
        return label_ids

    def _normalize(self, kind: str, node: dict) -> dict:
        common = {
            "id": node.get("id"),
            "archived": node.get("archivedAt") is not None,
            "updated_at": node.get("updatedAt"),
        }
        if kind == "project":
            status = node.get("status") if isinstance(node.get("status"), dict) else {}
            teams = node.get("teams") if isinstance(node.get("teams"), dict) else {}
            common.update(
                {
                    "name": node.get("name"),
                    "description": node.get("description"),
                    "content": node.get("content"),
                    "url": node.get("url"),
                    "label_ids": list(node.get("labelIds") or []),
                    "team_ids": [
                        team.get("id")
                        for team in (teams.get("nodes") or [])
                        if isinstance(team, dict)
                    ],
                    "status_id": status.get("id"),
                    "status_name": status.get("name"),
                    "status_type": status.get("type"),
                }
            )
        elif kind == "document":
            common.update(
                {
                    "title": node.get("title"),
                    "content": node.get("content"),
                    "url": node.get("url"),
                    "project_id": _linked_id(node, "project"),
                    "issue_id": _linked_id(node, "issue"),
                    "team_id": _linked_id(node, "team"),
                }
            )
        elif kind == "issue":
            state = node.get("state") if isinstance(node.get("state"), dict) else {}
            common.update(
                {
                    "title": node.get("title"),
                    "description": node.get("description"),
                    "url": node.get("url"),
                    "identifier": node.get("identifier"),
                    "project_id": _linked_id(node, "project"),
                    "team_id": _linked_id(node, "team"),
                    "state_id": state.get("id"),
                    "state_name": state.get("name"),
                    "state_type": state.get("type"),
                    "assignee_id": _linked_id(node, "assignee"),
                    "label_ids": self._collect_issue_labels(node),
                }
            )
        elif kind == "relation":
            common.update(
                {
                    "issue_id": _linked_id(node, "issue"),
                    "related_issue_id": _linked_id(node, "relatedIssue"),
                    "relation_type": node.get("type"),
                }
            )
        elif kind == "comment":
            common.update(
                {
                    "body": node.get("body"),
                    "url": node.get("url"),
                    "issue_id": node.get("issueId") or _linked_id(node, "issue"),
                    "project_id": node.get("projectId") or _linked_id(node, "project"),
                }
            )
        return common

    # -- writes -------------------------------------------------------------

    def create(self, kind: str, resource_id: str, payload: dict) -> dict:
        """Create a record with a caller-supplied UUID4 id.

        The caller must allocate and durably persist ``resource_id`` before
        this call. The id is injected into the native GraphQL input as ``id``;
        all other payload keys are passed through as native GraphQL input
        field names. Required-field and enum enforcement come from the live
        schema (see ``capabilities()``) and from GraphQL errors, not from a
        hardcoded local schema copy. A write is attempted once; it is never
        retried automatically.
        """
        kind = self._check_kind(kind)
        rid = _validate_uuid4(resource_id, "resource_id")
        if not isinstance(payload, dict):
            raise AdapterError("invalid_input", "payload must be an object")
        native = dict(payload)
        supplied_id = native.get("id")
        if supplied_id is not None and _stringify(supplied_id) != rid:
            raise AdapterError("invalid_input", "payload id does not match resource_id")
        native["id"] = rid

        data = self._call(_CREATE_QUERIES[kind], {"input": native})
        node = data.get(_CREATE_MUTATION_KEYS[kind])
        if not isinstance(node, dict):
            raise AdapterError("malformed_response", "create response shape missing")
        if node.get("success") is not True:
            raise AdapterError("graphql_error", "Linear create reported success=false")
        created = node.get(_CREATE_OBJECT_KEYS[kind])
        if not isinstance(created, dict):
            raise AdapterError("malformed_response", "create response missing object")
        return self._normalize(kind, created)



# ---------------------------------------------------------------------------
# Fake adapter
# ---------------------------------------------------------------------------

class FakeAdapter:
    """Deterministic stand-in for ``LinearAdapter``.

    With ``path`` the store is a JSON file written atomically with mode 0600.
    Without ``path`` the store lives in memory. ``data`` is public so tests can
    mutate fixture state. All reads and writes return deep copies. Subclass and
    override a method to inject faults.

    ``create`` is idempotent by identity only: re-creating an existing
    ``kind``/``id`` returns the original record untouched so the caller can
    reconcile idempotency.
    """

    def __init__(self, path=None) -> None:
        self._path = path
        self.state_map = dict(_FAKE_STATE_MAP)
        self.project_status_map = dict(_FAKE_PROJECT_STATUS_MAP)
        self.data = self._load()

    def capabilities(self) -> dict:
        return {
            "endpoint": None,
            "read_only": True,
            "source": "fake",
            "creates": {
                kind: {"supported": True, "id_supported": True} for kind in _KINDS
            },
            "project_status_field": True,
        }

    def get(self, kind: str, resource_id: str):
        self._check_kind(kind)
        bucket = self.data.get(kind) or {}
        record = bucket.get(resource_id)
        return copy.deepcopy(record) if record is not None else None

    def create(self, kind: str, resource_id: str, payload: dict) -> dict:
        self._check_kind(kind)
        rid = _validate_uuid4(resource_id, "resource_id")
        if not isinstance(payload, dict):
            raise AdapterError("invalid_input", "payload must be an object")
        bucket = self.data.setdefault(kind, {})
        if rid in bucket:
            return copy.deepcopy(bucket[rid])
        record = self._build_record(kind, rid, payload)
        bucket[rid] = record
        self._persist()
        return copy.deepcopy(record)


    # -- internals ----------------------------------------------------------

    @staticmethod
    def _check_kind(kind: str) -> str:
        if kind not in _KINDS:
            raise AdapterError("unsupported_kind", "unsupported resource kind")
        return kind

    def _build_record(self, kind: str, rid: str, payload: dict) -> dict:
        record = {
            "id": rid,
            "archived": False,
            "updated_at": _FAKE_CREATED_AT,
            "payload": copy.deepcopy(payload),
        }
        if kind == "project":
            status_id = payload.get("statusId")
            name, status_type = self.project_status_map.get(status_id, (None, None))
            record.update(
                {
                    "name": payload.get("name"),
                    "description": payload.get("description"),
                    "content": payload.get("content"),
                    "label_ids": list(payload.get("labelIds") or []),
                    "team_ids": list(payload.get("teamIds") or []),
                    "status_id": status_id,
                    "status_name": name,
                    "status_type": status_type,
                }
            )
        elif kind == "document":
            record.update(
                {
                    "title": payload.get("title"),
                    "content": payload.get("content"),
                    "project_id": payload.get("projectId"),
                    "issue_id": payload.get("issueId"),
                    "team_id": payload.get("teamId"),
                }
            )
        elif kind == "issue":
            state_id = payload.get("stateId")
            name, state_type = self.state_map.get(state_id, (None, None))
            record.update(
                {
                    "title": payload.get("title"),
                    "description": payload.get("description"),
                    "project_id": payload.get("projectId"),
                    "team_id": payload.get("teamId"),
                    "state_id": state_id,
                    "state_name": name,
                    "state_type": state_type,
                    "label_ids": list(payload.get("labelIds") or []),
                    "assignee_id": payload.get("assigneeId"),
                }
            )
        elif kind == "relation":
            record.update(
                {
                    "issue_id": payload.get("issueId"),
                    "related_issue_id": payload.get("relatedIssueId"),
                    "relation_type": payload.get("type"),
                }
            )
        elif kind == "comment":
            record.update(
                {
                    "body": payload.get("body"),
                    "issue_id": payload.get("issueId"),
                    "project_id": payload.get("projectId"),
                }
            )
        return record

    def _load(self) -> dict:
        if not self._path or not os.path.exists(self._path):
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, ValueError):
            raise AdapterError("invalid_store", "fake adapter store is unreadable") from None
        if not isinstance(loaded, dict):
            raise AdapterError("invalid_store", "fake adapter store must be an object")
        return {kind: dict(bucket) for kind, bucket in loaded.items() if isinstance(bucket, dict)}

    def _persist(self) -> None:
        if not self._path:
            return
        directory = os.path.dirname(os.path.abspath(self._path))
        os.makedirs(directory, exist_ok=True)
        handle_fd, temp_path = tempfile.mkstemp(prefix=".fake-adapter-", dir=directory)
        try:
            with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, self._path)
        except BaseException:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise


# ---------------------------------------------------------------------------
# GitHub evidence
# ---------------------------------------------------------------------------

class GitHubEvidence:
    """Read-only GitHub REST evidence for one pull request.

    Every request is a ``GET``. The caller (core) decides merge contract,
    required checks, review roles, branch policy, and whether a review's
    ``commit_sha`` is fresh against ``head_sha``.
    """

    def __init__(self, token=None, *, transport=None, timeout: int = 15) -> None:
        self._token = token
        self._timeout = timeout
        self._transport = transport if transport is not None else _make_github_transport(token, timeout)

    def _get(self, path: str):
        try:
            return self._transport("GET", path)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError("network_error", "GitHub transport failed (%s)" % type(exc).__name__) from None

    def pull_request(self, repo: str, number: int) -> dict:
        full_repo = _validate_repo(repo)
        number = _validate_number(number)

        pr = self._get("/repos/%s/pulls/%d" % (full_repo, number))
        if not isinstance(pr, dict):
            raise AdapterError("malformed_response", "pull request payload is not an object")
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
        head_sha = head.get("sha")
        if not isinstance(head_sha, str) or not head_sha:
            raise AdapterError("malformed_response", "pull request head sha missing")
        base_branch = base.get("ref")
        if not isinstance(base_branch, str) or not base_branch:
            raise AdapterError("malformed_response", "pull request base branch missing")

        checks = []
        checks.extend(self._check_runs(full_repo, head_sha))
        checks.extend(self._commit_statuses(full_repo, head_sha))
        reviews = self._reviews(full_repo, number)
        latest = self._get("/repos/%s/pulls/%d" % (full_repo, number))
        fields = ("head", "base", "merged", "merge_commit_sha", "draft")
        if not isinstance(latest, dict) or any(latest.get(field) != pr.get(field) for field in fields):
            raise AdapterError("evidence_changed", "PR revision or delivery state changed during observation; inspect again")

        return {
            "repo": full_repo,
            "number": number,
            "base_branch": base_branch,
            "head_sha": head_sha,
            "merged": bool(pr.get("merged")),
            "merge_commit_sha": pr.get("merge_commit_sha"),
            "draft": bool(pr.get("draft")),
            "checks": checks,
            "reviews": reviews,
            "url": pr.get("html_url") or pr.get("url"),
        }

    def _check_runs(self, repo: str, head_sha: str) -> list:
        collected = []
        total_count = None
        page = 1
        while True:
            path = "/repos/%s/commits/%s/check-runs?per_page=100&page=%d" % (repo, head_sha, page)
            payload = self._get(path)
            if not isinstance(payload, dict):
                raise AdapterError("malformed_response", "check-runs payload is not an object")
            if total_count is None:
                total_count = payload.get("total_count")
                if not isinstance(total_count, int) or isinstance(total_count, bool) or total_count < 0:
                    raise AdapterError("malformed_response", "check-runs total_count missing")
            runs = payload.get("check_runs")
            if not isinstance(runs, list):
                raise AdapterError("malformed_response", "check-runs list missing")
            for run in runs:
                if not isinstance(run, dict):
                    continue
                sha = run.get("head_sha") or head_sha
                collected.append(
                    {
                        "name": run.get("name"),
                        "sha": sha,
                        "conclusion": _normalize_conclusion(run.get("conclusion")),
                    }
                )
            if len(collected) >= total_count:
                break
            if not runs:
                raise AdapterError("incomplete_pagination", "check-runs pagination ended early")
            page += 1
            if page > MAX_PAGES:
                raise AdapterError("incomplete_pagination", "check-runs pagination exceeded page bound")
        return collected

    def _commit_statuses(self, repo: str, head_sha: str) -> list:
        # GitHub's combined status endpoint is paginated. Read every context;
        # a first page is not evidence that all required checks were observed.
        records = []
        total = None
        for page in range(1, MAX_PAGES + 1):
            payload = self._get("/repos/%s/commits/%s/status?per_page=100&page=%d" % (repo, head_sha, page))
            if not isinstance(payload, dict) or not isinstance(payload.get("statuses"), list):
                raise AdapterError("malformed_response", "commit statuses missing")
            if total is None:
                total = payload.get("total_count")
                if type(total) is not int or total < 0:
                    raise AdapterError("incomplete_pagination", "combined status count missing")
            values = payload["statuses"]
            records.extend({"name": x.get("context"), "sha": head_sha,
                            "conclusion": _normalize_conclusion(x.get("state"))} for x in values)
            if len(records) >= total:
                return records
            if not values:
                raise AdapterError("incomplete_pagination", "commit status pagination ended early")
        raise AdapterError("incomplete_pagination", "commit status pagination exceeded bound")

    def _reviews(self, repo: str, number: int) -> list:
        reviews = []
        page = 1
        while True:
            path = "/repos/%s/pulls/%d/reviews?per_page=100&page=%d" % (repo, number, page)
            payload = self._get(path)
            if not isinstance(payload, list):
                raise AdapterError("malformed_response", "reviews payload is not a list")
            for review in payload:
                if not isinstance(review, dict):
                    continue
                user = review.get("user") if isinstance(review.get("user"), dict) else {}
                reviews.append(
                    {
                        "actor": user.get("login"),
                        "commit_sha": review.get("commit_id"),
                        "state": review.get("state"),
                    }
                )
            if len(payload) < 100:
                break
            page += 1
            if page > MAX_PAGES:
                raise AdapterError("incomplete_pagination", "reviews pagination exceeded page bound")
        return reviews
