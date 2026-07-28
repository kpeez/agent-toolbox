# Issue tracker: Linear

Issues for this repo live in Linear. Use the Linear MCP tools for all operations
(`save_issue`, `get_issue`, `list_issues`, `save_comment`, `list_comments`,
`create_issue_label`, `list_issue_statuses`, `save_project`, `list_projects`,
`save_document`).

## Auth

If the environment carries a Linear token (`LINEAR_API_KEY` or an app-actor
OAuth token), prefer it over the interactive MCP connection: call the GraphQL
API directly (`https://api.linear.app/graphql`, token in the `Authorization`
header). Headless runs then work without interactive auth, and app-actor writes
are attributed to the agent identity rather than the user. Fall back to the
Linear MCP tools otherwise; never fall through to another tracker just because
the MCP is absent.

## Conventions

- **Spec container**: a spec publishes as a Linear **project** (`save_project`),
  under the initiative named in the repo's `Issue tracker:` extras when given.
  Put the `<!-- knack-spec: <repo>/<slug> -->` marker in the project
  description and mirror the spec as a project document (`save_document`) — the
  local spec file stays canonical; the project copy is for browsing. Slices are
  issues **in that project**, not sub-issues of a parent issue.
- **Create an issue**: `save_issue` with team, title, markdown body, and the
  spec's project.
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
  When Linear's GitHub integration is enabled and the branch name carries the
  issue id (see `/ship-pr`), the In Review and Done transitions happen
  automatically — verify rather than duplicate them.
- **Blocked by**: use Linear's native blocked-by relations, not prose.
- **PRs**: attach the PR link to the issue when publishing branch work, unless
  the GitHub integration already linked it.
- **No leakage to GitHub**: Linear is the private side. Never put Linear URLs,
  issue identifiers-as-links, or issue/spec content into GitHub-side text
  (PR bodies, commits, comments). The private side references the public side,
  never the reverse.

## When a skill says "publish to the issue tracker"

Create a Linear issue with `save_issue` inside the spec's project (standalone
when the work has no spec).

## When a skill says "fetch the relevant ticket"

`get_issue` + `list_comments` for the referenced ID (e.g. `ABC-123`).
