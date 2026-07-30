# Issue tracker: Local Markdown

Issues for this repo live as markdown files under `docs/agents/specs/`, beside the
spec they implement. `docs/agents/` is a gitignored symlink into the shared llmOS
vault, so issue files and their statuses are private and never committed.

## Conventions

- Implementation issues for spec `docs/agents/specs/NNNN-<slug>.md` are
  `docs/agents/specs/NNNN-<slug>-issue-<NN>-<issue-slug>.md`, numbered from `01`
- The parent issue is the spec itself — `NNNN-<slug>.md`'s goal/scope header; do not
  duplicate it as an issue file
- Triage state is a `Status:` line near the top of each issue file, using the
  triage label strings from `SKILL.md`; done is `Status: done`
- "Blocked by" references other issue files by relative path
- Comments and progress notes append to the bottom of the file under a
  `## Comments` heading

## swe-loop frontier

The loop's frontier query — the workable slices in a spec's container — is the
spec's `NNNN-<slug>-issue-*.md` files, minus:

- files whose `Status:` is `done`, `wontfix`, or `ready-for-human`
- files with a "Blocked by" reference whose target is not yet `Status: done`

Report each as `{id, identifier, title}` with the file path as `id`, the
`issue-<NN>-<issue-slug>` filename segment as `identifier`, and the file's
first heading as `title`. An unreadable or missing spec directory is a query
failure, never an empty frontier.

Reading or posting an issue's "tracker comments" means its `## Comments`
section; the loop's "container comment" (run summary) appends under a
`## Comments` heading at the bottom of the spec file itself.

## When a skill says "publish to the issue tracker"

Create a new file `docs/agents/specs/NNNN-<slug>-issue-<NN>-<issue-slug>.md` next to the spec.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the
issue number directly.
