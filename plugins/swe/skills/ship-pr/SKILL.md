---
name: ship-pr
description: Commit, push, and open a draft PR for authorized work. Use when asked to ship; not for planning or local-only edits. Finalize only on explicit request.
---

# /ship-pr — publish verified work

Commit, push, and create or update a pull request only when the current request
or established approved execution scope authorizes those actions. Respect any
existing local-only boundary and explicit publication permission; publication
authority does not authorize putting private identifiers or content into public
output. A user invocation of `/ship-pr` authorizes its default commit, push, and
draft-PR workflow for the named work. Do not invoke this skill automatically at
a green checkpoint. If publication is not authorized, leave verified local work
intact and report its state.

Default and explicit finalize modes:

- `/ship-pr [plan or issue]`: verify, group, commit, push, and ensure a draft
  pull request exists.
- `/ship-pr finalize`: re-verify and mark the existing draft ready. Read
  [finalize](references/finalize.md) for this explicit mode. Merging remains
  separate.

## Rules

- Preserve unrelated and user-owned changes. Stage intentional groups and
  inspect the full staged diff before every commit. If unrelated staged work
  would be included, stop for direction without altering its staged state.
- Write imperative, informative commit subjects. Each commit carries one
  coherent intent and leaves the branch in a usable state where practical.
- Follow repository and host branch conventions. Do not rename an established
  branch solely to impose this skill's preferred format.
- Resolve the base branch from confirmed repository configuration or remote
  metadata. If neither establishes it, stop and ask rather than guessing.
- Never force-push except through an explicitly requested stack operation whose
  documented workflow requires it.
- Draft pull requests are the default. Do not change an existing draft/ready
  state unless the user requested that transition.
- Never put private identifiers, URLs, or content into a public branch, commit,
  pull-request body, or bot output. The one exception is an issue key (such as
  `ABC-123`) in the branch name and a `Fixes ABC-123` line, which link the
  tracker; never add tracker URLs or issue content. Do not add agent
  attribution, generated-by footers, or session links.
- Before committing, confirm applicable repository checks and runnable
  behavior-specific evidence pass under the verification rule below. Report
  failures as failures.
- The authorized PR-publication task is complete when the new draft exists or
  the existing PR is updated, and its state is reported. A draft is not
  human-review-ready; product delivery and merge remain separate outcomes.

## Resolve context

Use the plan or issue named by the caller, otherwise the issue key in the
branch name or an explicit linkage in the session. Do not pick the most
recently modified plan. Proceed without a plan when the work is clearly bounded
by the current request.

Read the intended outcome and the actual diff. Confirm that
publication authority covers the changes present. Resolve the base branch and
any stack relationship from repository evidence or the caller's instruction.

## Workflow

1. **Inspect.** Compare the branch to its confirmed base and include authorized
   committed, uncommitted, and untracked work. Identify unrelated changes and
   leave them untouched.
2. **Verify.** Run repository-declared checks that exist and apply, plus the
   behavior-specific evidence named by the work. Reuse prior results only when
   the revision, relevant uncommitted content, environment, and coverage still
   match; identify them as recorded results, not checks rerun here. Do not
   invent a generic lint, type-check, or test stack. A required failure stops
   publication.
3. **Group and commit.** Check proposed public branch, commit, and PR text
   against the privacy rule above. Build the smallest coherent commit groups.
   Stage and commit one group at a time, checking status between groups.
4. **Push.** Push the current branch without force. Confirm the intended remote
   and upstream when they are ambiguous.
5. **Draft pull request.** Reuse the branch's existing pull request. Otherwise
   create one draft against the confirmed base.
6. **Issue link.** When the work has an issue, end the pull-request body with
   `Fixes ABC-123` (or `Fixes #123` on GitHub) so the tracker's GitHub
   integration moves the issue on merge. Use `Part of ABC-123` when this pull
   request does not finish the issue. Do not hand-edit status that git moves.
7. **Report.** Give the branch, base, commits, pull-request URL and state, the
   linked issue, checks run, behavior evidence, and known gaps.

## Pull-request description

Write for a reviewer without session context. Follow the
[pull-request body template](references/pr-body.md). Skip preambles, keep prose
brief, and use the project's domain terms:

- **Summary:** the concrete problem, resulting behavior, and load-bearing
  approach, shown with the smallest visual that makes the point.
- **Reviewer's guide, when useful:** the most important diff first, sensible
  reading order, and any mechanical sections.
- **Evidence:** a before and after for each behavior the PR claims. Never list
  lint, type-check, build, or test-suite runs as evidence. Every PR must pass
  them, so they prove nothing about this one. State known gaps and pre-existing
  failures, and distinguish recorded prior results from checks run in the
  current workspace.
- **Merge danger:** whether the change is a one-way or two-way door, and its
  blast radius.

Keep the text self-contained. Beyond the closing `Fixes` line, public text
does not reveal tracker URLs, issue or plan content, or internal workflow
commentary.

## Secondary modes

Use [stacked pull requests](references/stacked.md) only when the user or
established task design calls for a dependent branch chain. Read the
[finalize workflow](references/finalize.md) only for an explicit
`/ship-pr finalize` request.

## Markdown artifact

Create a local PR markdown artifact only when the user requests one or the
authorized publication route is unavailable. Follow
[plan storage](../write-plan/references/plan-storage.md) to find the plans
directory; resolve `../../scripts/plan_sync.py` from this skill's directory,
not the current working directory, when running `dir`. Use a name without an
issue key, such as `pr-<branch>.md`, so it stays local. Include the proposed
title, body, commit grouping, and relevant diff references. This skill's job is
verified delivery to a draft PR.
