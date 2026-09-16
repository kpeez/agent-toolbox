# Issue tracker: Linear

Use the installed Linear connection or another explicitly authorized Linear
route. Do not expose credentials in prompts or output. A missing connection is
a reported limitation; do not silently fall through to another tracker.

## Container and tasks

A spec records `tracker: linear` and `tracker_container: <project id>`. Verify
the recorded project. If it no longer exists, stop rather than creating a
duplicate. If none exists and creation is authorized, create a project, record
its stable id, and optionally mirror the spec as a project document while the
local spec remains canonical.

Create tasks as issues in the project. Reuse matching issues and native
blocked-by relationships. Follow the team's established statuses and labels.

## State and resume

Linear issues are the primary home for operational handoff and resume
information. Give one task owner responsibility for tracker updates. Record
meaningful transitions such as started, blocked, verified, awaiting review, and
delivered. Keep comments concise: current result, next action, and any
non-obvious blocker.

Publish handoff content into the private issue packet or a current-state comment
with dedupe rather than creating a new note per attempt. Notes record
`start`, `progress`, `handoff`, `review`, and `evidence` observations via
`record`; a note never changes status, assigns ownership, or clears a hold.
During an outage, a durable pending handoff is an operational outbox, not a
second tracker. Keep lasting decisions, investigations, and research
conclusions in project documents and link them selectively; do not duplicate
issue state there. Handoff carries current state, verified evidence, next
action, worktree and uncommitted work, running jobs, and what not to repeat;
durable docs keep reusable context and conclusions only.

Preserve human holds, assignments, and later changes to an approved task.

On resume, reconcile Linear with current checkout, worktree, diff, commit,
review, pull-request, and delivery evidence. A branch name, issue state, or
self-report alone is insufficient. A failed write is reported accurately and
retried only when useful; it does not rewrite observed code state.

Do not mark an issue delivered merely because work is verified locally,
integrated, or attached to a draft or ready pull request.

## Private tracker boundary

Linear may reference public GitHub work. Do not put Linear URLs, linked issue
content, or private identifiers into public pull-request bodies, commits, or
comments unless the user explicitly makes that information public.

## Publication boundary

Creating or updating projects, documents, issues, comments, relations, labels,
or statuses changes external state and requires existing authority. Reading
does not. When a skill says to publish or fetch a ticket, apply this reference
and the user's current authority.
