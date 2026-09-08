---
name: start-loop
description: Run the workable tasks for an approved spec through implementation, integration, verification, and independent review. Use only when the user explicitly invokes /start-loop.
---

# /start-loop — execute an approved spec

The spec defines approved intent, scope, design, and acceptance criteria. The
selected tracker owns executable tasks, dependencies, assignments, blockers,
and progress. Read both before changing code. Do not create a second task list
in the spec or derive task state from branch names.

Use ordinary host subagents when delegation helps. If local CLI delegation to
an external provider is explicitly authorized, follow `/external-subagents`.

## Authority

Proceed when the spec records `approved: true` or the current conversation
contains explicit approval for that spec. Record approval only when it was
actually given. Material changes to approved intent need user approval;
routine implementation choices do not.

Approval to implement does not itself authorize commits, pushes, pull
requests, deployments, external tracker writes, or other external mutations.
Use authority already present in the user's request or approved execution
scope. If publication is not authorized, finish and verify the local work.

## Host roles

- A **standalone Codex task** is user-owned. Its brief includes the approved
  scope, canonical document links, authority limits, and coordinator task ID.
  It may use temporary subagents and reports consequential blockers through
  the host's task-messaging route.
- A **Claude Code session** may start fresh or resume in a fresh session. It
  reads the same spec, tracker, and project documents. Write a short handoff
  only for unfinished work or information that cannot be reconstructed
  cheaply.
- A **temporary worker** owns one bounded assignment and reports to its caller.
  It does not contact a standalone coordinator independently.

Compaction or a fresh session does not invalidate approved work.

## Run procedure

1. **Resolve intent and work.** Read the approved spec, its tracker selection,
   and its linked task container. Reuse existing tasks. Respect human holds,
   assignments, and native dependency relationships. If the configured
   tracker is unavailable, report that limitation; absence of a response is
   not an empty backlog. Continue only work whose ownership, dependencies, and
   authority can be established from available evidence.
2. **Inspect the workspace.** Check the current checkout, worktrees, dirty
   changes, relevant diffs and commits, and any linked delivery state. Preserve
   unrelated work. Follow repository and host branch conventions. Create a
   branch or worktree only when the run needs one and authority permits it.
3. **Claim workable tasks.** Give each task one owner for tracker updates.
   Write transitions only within existing tracker-write authority: started,
   blocked, verified, awaiting review, and delivered as supported. If that
   authority or capability is missing, report the limitation and continue only
   work whose ownership and dependencies are established. Keep updates concise
   and useful for resumption. A failed update does not erase observed work.
4. **Implement bounded assignments.** Work directly when the task is small or
   delegation would add no value. Otherwise delegate bounded exploration or
   implementation to an appropriately inexpensive available agent. Follow
   `/implement`, including its deletion and simplification step before final
   verification. Prompts
   carry the relevant approved requirements, useful paths, constraints,
   ownership, evidence expectations, and blocker route. See
   [references/delegation.md](references/delegation.md).
5. **Integrate and verify.** Keep concurrent writes isolated by worktree or
   disjoint ownership. Inspect completed diffs, resolve interactions, and run
   the repository's applicable checks plus behavior-specific evidence. Do not
   call failing or unrun required checks successful.
6. **Review independently.** After the assembled change is verifiable, use one
   reviewer who did not implement the reviewed change. Model-family diversity
   is optional. Ask for concrete correctness, requirement, verification, and
   unnecessary-complexity findings grounded in the diff and approved intent.
   Fix supported findings and re-review when changed risk justifies it. Stop a
   loop that produces no new evidence; escalate an unresolved consequential
   decision.
7. **Publish when authorized.** Invoke `/ship-pr` only when existing authority
   covers commits, push, and pull-request creation. Otherwise leave verified
   local work for review. A draft or ready pull request is not proof of
   delivery.
8. **Report.** State tasks completed, tracker transitions attempted, local and
   external state changed, verification results, review findings, unresolved
   concerns, and publication or delivery state.

## Resume

Reconcile the tracker with current evidence: checkout and worktree contents,
dirty diffs, commits, reviews, pull requests, and delivery state where
applicable. Inspect unfinished work before assigning it again. A branch name,
missing branch, tracker label, or prior self-report alone proves neither
completion nor abandonment.

## Escalation

Continue while new evidence supports a plausible in-scope next step. Diagnose
repeated failure before redispatching. Ask the user only when progress requires
a material scope or preference decision, unavailable authority or capability,
destructive action, or resolution of contradictory approved requirements.
Workers report these conditions to their caller rather than prompting the user
directly.
