# Issue tracker: GitHub

Use host-native GitHub tools or `gh` for issue reads and writes. Follow the
repository's existing labels, project fields, and status conventions where they
exist; create workflow labels only when the approved scope calls for them.

## Container and tasks

A spec records `tracker: github` and `tracker_container: <issue number>`.
Verify a recorded parent issue before use. If no container exists and creation
is authorized, create one and record its number. Link task issues through
GitHub's native sub-issue relationship rather than a duplicated checklist.
Reuse matching existing tasks.

Issue bodies may include a plain `Spec: <specPath>` reference for humans. Do not
depend on hidden body tokens for identity.

## State and resume

Use repository-native states or labels to record meaningful transitions such
as started, blocked, awaiting review, and delivered. Give one task owner
responsibility for updates. Preserve human holds and assignments.

Before changing status on resume, compare the issue with current checkout,
worktree, diff, commit, review, and pull-request evidence. A branch name or
label alone does not prove completion. Report failed tracker writes accurately.

Do not close a task merely because code was verified locally or a pull request
was opened or marked ready. Close it when the repository's delivery condition
is met.

## Publication boundary

Creating issues, comments, labels, relationships, or status updates changes
external state and requires existing authority. Reading does not. When a skill
says to publish or fetch a ticket, apply this reference and the user's current
authority.
