# Source: Linear and GitHub Issues

The tracker often holds the product or business reason: "customer X asked",
"this is for the compliance work", a label such as `incident-followup`, or a
parent issue that names an initiative.

## Search Linear

Use the Linear MCP tools.

1. Fetch each ticket ID from the anchor with `get_issue`, and read its
   comments with `list_comments`.
2. Search with `list_issues` and `query`: the feature name, a key symbol, a
   user-visible term. Try several phrasings.
3. Walk up the tree: fetch the parent of a sub-issue. The parent often holds
   the reason.
4. For an issue in a project, read the project with `get_project` and its
   documents with `list_documents` and `get_document`.
5. Note labels, milestones, and dates. A deadline often reveals the motive.

## Search GitHub Issues

```bash
gh issue view <number> --comments
gh search issues '<term>' --repo <owner>/<repo> --include-prs
```

## Read with care

- A ticket can close and reopen with a new scope. Read its whole history.
- Template text such as "improve user experience" is not a reason.
- An old ticket can describe a plan that later changed. Compare its date with
  the code's merge date.
- Follow "duplicate of" links to the main ticket.
- An issue you cannot open is a gap. Record it.

## Return

For each relevant ticket: its ID and title, the reason quoted verbatim, its
labels, parent, and project, its author, created and closed dates, and its
link.
