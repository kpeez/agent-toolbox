---
name: execute-spec
description: Execute or resume an approved spec across tracked tasks. Not for drafting specs, status checks, or isolated edits.
---

# Execute an approved spec

The spec owns approved intent and acceptance criteria. The selected tracker
owns tasks, dependencies, assignments, blockers, and progress. Read both and
inspect the workspace before acting. Reuse existing tasks and preserve
unrelated work.

Proceed only when the user has requested execution and the spec records
`approved: true` or the conversation explicitly approves it. Discovering an
approved spec is not an instruction to execute it. Material scope changes need
approval. Implementation approval does not grant permission to commit, push,
publish, deploy, or write to an external tracker; use only authority already given.

## Execute and finish

- Respect dependencies, human holds, and assignments. Give each task one owner
  for authorized tracker updates. Keep task state and useful project notes
  concise and evidence-backed; do not duplicate the tracker in the spec.
- Follow [implement](../implement/SKILL.md) for individual changes, including
  simplification before final verification. Use
  [orchestrate](../orchestrate/SKILL.md) when delegation or independent review
  helps; a full spec run need not use multiple agents for every task.
- Verify the assembled work against the approved acceptance criteria and
  applicable repository checks. Obtain independent review for substantive
  changes, following the orchestration guidance.
- Continue authorized work through applicable verification. A failed required
  check blocks completion or publication, while an in-scope correction may
  continue when the task authorizes it.
- Publish only when authorized, using [ship-pr](../ship-pr/SKILL.md) when that
  authority covers its commit, push, and pull-request workflow. Otherwise
  finish verified local work.

Choose the sequence to fit the work, not a fixed pipeline. Report completed
tasks, checks and review results, unresolved concerns, and actual tracker and
delivery state. Distinguish failed or unrun checks and unsuccessful updates
from verified outcomes.

## Resume and handle blockers

Reconcile the spec and tracker with current files, diffs, commits, reviews, and
delivery evidence. Inspect unfinished work before reassigning it. A branch
name, tracker label, or prior report alone proves neither completion nor
abandonment. An unavailable tracker is not an empty backlog; continue only
work whose ownership, dependencies, and authority can be established.

Report blockers and ask for direction when progress requires a material scope
decision, missing authority or capability, destructive action, or resolution
of contradictory requirements. Preserve useful evidence for resumption.
