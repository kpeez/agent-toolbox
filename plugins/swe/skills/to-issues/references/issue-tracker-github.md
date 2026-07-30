# Issue tracker: GitHub

Issues for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove triage labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`. Create missing labels with `gh label create` before applying.
- **Parent/sub-issues**: GitHub supports native sub-issues — link each child to the parent via the sub-issues REST API or the GitHub MCP `sub_issue_write` tool; don't hand-maintain a `- [ ]` task list in the parent body. Each slice's body still links back to the parent.
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v` — `gh` does this automatically when run inside a clone.

## swe-loop frontier

The loop's frontier query — the workable slices in a spec's container — is the
container parent issue's **open sub-issues**, minus:

- issues labeled `ready-for-human`
- issues whose `## Blocked by` section still references an open issue

Report each as `{id, identifier, title}` with the issue number as `id` and
`#<number>` as `identifier`. A failed `gh` call (auth, network, non-zero exit)
is a query failure, never an empty frontier.

The loop's "container comment" (run summary) is a comment on the parent issue.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.
