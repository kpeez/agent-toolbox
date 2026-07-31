# Issue tracker: Local Markdown

Issues for this repo live as markdown files under `docs/agents/specs/`, beside the
spec they implement. `docs/agents/` is a gitignored symlink into the shared llmOS
vault, so issue files and their statuses are private and never committed.

## Conventions

- Implementation issues for spec `docs/agents/specs/NNNN-<slug>.md` are
  `docs/agents/specs/NNNN-<slug>-issue-<NN>-<issue-slug>.md`, numbered from `01`
- The parent issue is the spec itself — `NNNN-<slug>.md`'s goal/scope header; do not
  duplicate it as an issue file
- Triage and workflow state live in the issue file's YAML frontmatter as
  `status:`, using the strings from `SKILL.md` plus `in-progress` and
  `in-review`; done is `status: done`. Frontmatter, not a prose line, so it is
  machine-readable without a model in the loop
- "Blocked by" references other issue files by relative path
- Comments and progress notes append to the bottom of the file under a
  `## Comments` heading

## swe-loop workable set

The container is the spec; its slices are the spec's `NNNN-<slug>-issue-*.md`
files. Report each as `{id, identifier, title}` with the file path as `id`, the
`issue-<NN>-<issue-slug>` filename segment as `identifier`, and the file's first
heading as `title`. An unreadable or missing spec directory is a query failure,
never an empty result.

Which of those are workable is the conductor's rule, not this file's — it states
what counts as done and blocked, including that a slice merged into the run's
integration branch is done whatever the file says. Do not re-derive it here.

"Blocked by" references other issue files by relative path. Reading or posting
an issue's "tracker comments" means its `## Comments` section; the loop's
container comment (run summary) appends under a `## Comments` heading at the
bottom of the spec file itself.

## Container identity

The spec is its own container, so no lookup is needed; a spec may still record
`tracker: local` in its frontmatter for symmetry with the other trackers.

## State transitions

Set the issue file's frontmatter `status:` as the loop works:

- slice picked up: `status: in-progress`
- slice merged into the integration branch: `status: in-review`
- end of run: nothing to reconcile — the spec has no separate status of its own
  beyond its own lifecycle field

Never write `status: done`: the run ends at a draft PR, so nothing is delivered
yet. A failed write is logged and the run continues.

## When a skill says "publish to the issue tracker"

Create a new file `docs/agents/specs/NNNN-<slug>-issue-<NN>-<issue-slug>.md` next to the spec.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the
issue number directly.
