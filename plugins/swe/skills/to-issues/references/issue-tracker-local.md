# Issue tracker: local Markdown

Store tasks beside their spec as
`NNNN-<slug>-issue-<NN>-<issue-slug>.md`. The spec is the container; do not
duplicate its intent in a parent issue file.

## Task files

Use YAML frontmatter for machine-readable status. Follow established local
states when present; otherwise use `ready-for-agent`, `ready-for-human`,
`in-progress`, `blocked`, `in-review`, and `done`. Record native local
dependencies as relative paths. Append only concise, useful resume information
under `## Comments` or `## Resume`; do not create a repetitive journal.

Use the issue path as its stable identifier and the first heading as its title.
An unreadable spec directory or malformed issue is a query failure, never an
empty workable set. Reuse existing issue files.

## State and resume

Give one task owner responsibility for status updates. Record meaningful
transitions while work proceeds. Preserve human holds and assignments.

Before changing state on resume, compare the file with current checkout,
worktree, diff, commit, review, pull-request, and delivery evidence. A filename,
branch name, or frontmatter value alone does not prove completion or
abandonment. Do not mark `done` merely because work is verified locally,
integrated, or in a draft or ready pull request; use the project's delivery
condition.

When a skill says to publish a local task, create the sibling issue file only
within the authorized workspace. When it says to fetch a ticket, read the
referenced path and its latest useful resume note.
