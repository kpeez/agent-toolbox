---
name: ship-pr
description: Commit, push, and open a draft PR for authorized work. Use when asked to ship; finalize only on explicit request.
---

# /ship-pr — publish verified work

Commit, push, and create or update a pull request only when the current request
or established approved execution scope authorizes those actions. A user
invocation of `/ship-pr` authorizes its default commit, push, and draft-PR
workflow for the named work. Do not invoke this skill automatically at a green
checkpoint. If publication is not authorized, leave verified local work intact
and report its state.

Default and explicit finalize modes:

- `/ship-pr [spec or task]`: verify, group, commit, push, and ensure a draft
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
- Do not add agent attribution, generated-by footers, session links, or private
  tracker content to commits or public pull-request text.
- Run all applicable repository checks and runnable behavior-specific evidence
  before committing. Report failures as failures.
- A draft or ready pull request is awaiting review, not delivered. Update a task
  to delivered only when its repository or tracker delivery condition is met.

## Resolve context

Use the spec or task named by the caller. Otherwise use an explicit linkage in
the current task, tracker item, branch metadata, or established session context.
Do not select the most recently modified spec or infer a spec solely from the
default branch. Proceed without a spec when the work is clearly bounded by the
current request.

Read the approved intent, current task state, and actual diff. Confirm that
publication authority covers the changes present. Resolve the base branch and
any stack relationship from repository evidence or the caller's instruction.

## Workflow

1. **Inspect.** Compare the branch to its confirmed base and include authorized
   committed, uncommitted, and untracked work. Identify unrelated changes and
   leave them untouched.
2. **Verify.** Run repository-declared checks that exist and apply, plus the
   behavior-specific evidence named by the work. Do not invent a generic lint,
   type-check, or test stack. A required failure stops publication.
3. **Group and commit.** Build the smallest coherent commit groups. Stage and
   commit one group at a time, checking status between groups.
4. **Push.** Push the current branch without force. Confirm the intended remote
   and upstream when they are ambiguous.
5. **Draft pull request.** Reuse the branch's existing pull request. Otherwise
   create one draft against the confirmed base.
6. **Tracker.** When tracker writes are authorized, attach the public pull
   request from the private tracker side and mark affected tasks awaiting
   review. Preserve human holds and assignments. Report failed writes.
7. **Spec.** When a linked spec exists, set its lifecycle to `review` after the
   pull request exists. This does not replace task state or prove delivery.
8. **Report.** Give the branch, base, commits, pull-request URL and state,
   tracker/spec updates, checks run, behavior evidence, and known gaps.

## Pull-request description

Write for a reviewer without session context:

- **What and why:** the concrete problem, resulting behavior, and load-bearing
  approach.
- **Reviewer's guide, when useful:** the most important diff first, sensible
  reading order, and any mechanical sections.
- **Verification:** concise applicable lint, type, build, and test results plus
  behavior-specific evidence and known gaps. Distinguish recorded prior results
  from checks run in the current workspace.

Keep the text self-contained. A private tracker may link to the public pull
request; public text does not reveal private tracker URLs, issue content, or
internal workflow commentary.

## Secondary modes

Use [stacked pull requests](references/stacked.md) only when the user or
established task design calls for a dependent branch chain. Read the
[finalize workflow](references/finalize.md) only for an explicit
`/ship-pr finalize` request.

## Markdown artifact

Create a local PR markdown artifact only when the user requests one or the
authorized publication route is unavailable. Keep it under the project's
private agent-docs area, and include the proposed title, body, commit grouping,
and relevant diff references without leaking private tracker content.
