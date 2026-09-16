---
name: execute-spec
description: Execute or resume an approved spec across tracked tasks. Not for drafting specs, status checks, or isolated edits.
---

# Execute an approved spec

The spec owns approved intent and acceptance criteria. The selected tracker
owns tasks, dependencies, assignments, blockers, and progress. Read both and
inspect the workspace before acting. Reuse existing tasks and preserve
unrelated work. This skill's job is executing tracked tasks to verified handoff.

Proceed only when the user requested execution and approval evidence covers the
current spec revision and explicit scope. Treat `approved: true` as bookkeeping;
the model checks the real approval source. Discovering an approved spec is not
an instruction to execute it. Material scope changes need renewed approval.
Approval does not grant permission to commit, push, publish, deploy, or write
to an external tracker; use only authority already given.

## Execution checklist

- Confirm the current approved revision and explicit scope. For configured
  Linear work, compare the semantic digest; other tracker routes retain their
  existing explicit approval mechanism. Stop on stale or missing approval.
- Treat Todo status as readiness, separately from permission to execute.
- Respect holds, dependencies, and assignments; reconcile the tracker with the
  fresh checkout, diffs, commits, open PRs, and job observations.
- Use one supervised writer and one agreed task owner. Verify ownership before
  resuming; the pilot does not arbitrate concurrent workers.
- For configured Linear work, record `start`, `progress`, `handoff`, `review`, and `evidence` notes via
  `record` during the work (see [operations](../to-issues/references/workflow-operations.md)).
  No Stop message, PR, draft, or merge marks Done automatically.
- Obtain independent review before human review for substantive changes.
- Put handoff in the selected tracker issue (privately for Linear): current state, verified evidence,
  next action, worktree and uncommitted work, running jobs, and what not to
  repeat. Keep durable docs to reusable context and conclusions only.
- Continue to another eligible authorized task or explain the stop (blocking
  dependency, missing authority, ownership, or closure gate).

## Execute and finish

- Follow [implement](../implement/SKILL.md) for individual changes. Use
  [orchestrate](../orchestrate/SKILL.md) when delegation or independent review
  helps; a full run need not use multiple agents for every task.
- Keep code, research, condition, and sync work separate so each phase's
  evidence stays attributable.
- Verify assembled work against acceptance criteria and repository checks. A
  failed required check blocks completion; an in-scope correction may continue
  when the task authorizes it.
- Publish only when authorized, using [ship-pr](../ship-pr/SKILL.md) when that
  authority covers its workflow. Otherwise finish verified local work. A draft
  pull request is neither ready nor Done.
- Audits are read-only and propose repairs; performing a repair needs its own
  specific existing authority.

Report completed tasks, checks and review results, unresolved concerns, and
actual tracker and delivery state. Distinguish failed or unrun checks from
verified outcomes. Load only the selected tracker route.
