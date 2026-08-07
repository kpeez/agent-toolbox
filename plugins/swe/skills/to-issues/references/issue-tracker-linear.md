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
  Record the project id in the spec's frontmatter (see Container identity) and
  mirror the spec as a project document (`save_document`) — the local spec file
  stays canonical; the project copy is for browsing. Slices are
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
- **Status**: see State transitions below — the loop writes these itself
  rather than relying on Linear's GitHub integration firing, which is what left
  a merged, shipped slice sitting in Backlog on an observed run.
- **Blocked by**: use Linear's native blocked-by relations, not prose.
- **PRs**: attach the PR link to the issue when publishing branch work, unless
  the GitHub integration already linked it.
- **No leakage to GitHub**: Linear is the private side. Never put Linear URLs,
  issue identifiers-as-links, or issue/spec content into GitHub-side text
  (PR bodies, commits, comments). The private side references the public side,
  never the reverse.

## swe-loop workable set

The loop's workable query is deterministic here. From the repo root run

    uv run <scriptsDir>/linear_tracker.py workable --container <containerId> --merged-into <baseBranch>

(the conductor's prompt supplies all three values). It prints a JSON array of
`{id, identifier, title, labels, batch}` and exits non-zero on a failed
`linear` call — report a non-zero exit as a query failure, never as an empty
result. `batch` is the slice's **project milestone** (`''` when it has none).
File every slice belonging to one reviewable story on one milestone: the loop
hands a whole batch to one implementer and publishes it as one pull request.

**The output is final.** The script applies the workability rules itself:
closed or already-merged issues are dropped, a merged issue counts as a
satisfied blocker, and `ready-for-human` is excluded. Consume the array as-is;
re-reading the tracker on top of it is wasted work.

"Already merged" is read from git — `git branch --merged <baseBranch>` over
`slice/<identifier>` branches — not from tracker state, which does not advance
until the run's PR lands.

## Container identity

A spec records its Linear project in its own YAML frontmatter
(`tracker: linear`, `tracker_container: <project id>`). Resolve it with

    uv run <scriptsDir>/linear_tracker.py container --spec <specPath>

Exit 0 prints the id; exit 2 means the spec names a project that no longer
exists (stop — never create a second one); exit 3 means no container exists yet
and the caller may create one, then record it with `--set <id>`. Containers
created before this convention carry a `<!-- knack-spec: ... -->` token in their
body; the resolver still reads it and backfills the frontmatter, but nothing
writes new ones. Give a new project a plain `Spec: <specPath>` line in its
description for humans — never a machine-parsed token.

## State transitions

The loop advances issue state as it works, so the tracker reflects reality
rather than the state work started in:

- slice picked up: `linear issue update <identifier> --state "In Progress"`
- slice merged into the integration branch: `linear issue update <identifier> --state "In Review"`
- end of run: `uv run <scriptsDir>/linear_tracker.py sync --container <containerId>`
  promotes a project still reading backlog/planned while its issues are underway

Never set an issue or project to a completed state: the run ends at a draft PR,
so nothing it touched is delivered yet. A failed state write is logged and the
run continues — git, not the tracker, decides what is merged.

## When a skill says "publish to the issue tracker"

Create a Linear issue with `save_issue` inside the spec's project (standalone
when the work has no spec).

## When a skill says "fetch the relevant ticket"

`get_issue` + `list_comments` for the referenced ID (e.g. `ABC-123`).
