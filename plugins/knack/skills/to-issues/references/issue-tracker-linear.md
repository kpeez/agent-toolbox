# Issue tracker: Linear

Issues for this repo live in Linear. Use the Linear MCP tools for all operations
(`save_issue`, `get_issue`, `list_issues`, `save_comment`, `list_comments`,
`create_issue_label`, `list_issue_statuses`).

## Conventions

- **Create an issue**: `save_issue` with team, title, and markdown body. Set
  `parentId` to publish a slice as a sub-issue of the spec's parent issue.
- **Read an issue**: `get_issue` plus `list_comments` — read both before acting;
  the latest progress comment is the handoff.
- **List issues**: `list_issues` filtered by team/project/label/state.
- **Comment**: `save_comment`. Comment progress on the active issue before you
  run out of context — what's done, what's next, the one gotcha.
- **Triage labels**: apply the label strings from `SKILL.md` via `save_issue`;
  create missing labels with `create_issue_label` first.
- **Status**: map gate semantics onto the workspace's closest states
  (`list_issue_statuses`): starting work → In Progress, PR up → In Review,
  merged → Done, stuck → comment the exact blocker and needed human input.
- **Blocked by**: use Linear's native blocked-by relations, not prose.
- **PRs**: attach the PR link to the issue when publishing branch work.

Escalate from parent issue + sub-issues to a Linear **project** only for large,
multi-milestone specs.

## When a skill says "publish to the issue tracker"

Create a Linear issue with `save_issue` (sub-issue of the parent when the work
came from a spec).

## When a skill says "fetch the relevant ticket"

`get_issue` + `list_comments` for the referenced ID (e.g. `ABC-123`).
