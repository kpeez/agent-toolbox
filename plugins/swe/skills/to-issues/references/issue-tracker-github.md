# Issue tracker: GitHub

Issues for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove triage labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`. Create missing labels with `gh label create` before applying.
- **Parent/sub-issues**: GitHub supports native sub-issues — link each child to the parent via the sub-issues REST API or the GitHub MCP `sub_issue_write` tool; don't hand-maintain a `- [ ]` task list in the parent body. Each task's body still links back to the parent.
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v` — `gh` does this automatically when run inside a clone.

## swe-loop integration

The conductor invokes the installed `tracker.py` script for workable queries.
It passes the resolved tracker, parent issue, and integration branch; this
reference defines the GitHub conventions rather than a command string.

## Container identity

A spec records its parent issue in its own YAML frontmatter (`tracker: github`,
`tracker_container: <issue number>`). Read it from the spec; if absent, create
the parent issue and record it there. Never write a machine-parsed token into
an issue body — a plain `Spec: <specPath>` line for humans is fine.

## State transitions

- task picked up: `gh issue edit <number> --add-label in-progress`
- task merged into the integration branch: `gh issue edit <number> --remove-label in-progress --add-label in-review`
- end of run: nothing to reconcile — GitHub has no project-level status here

Create missing labels with `gh label create` first. Never close an issue: the
run ends at a draft PR. A failed label write is logged and the run continues.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.
