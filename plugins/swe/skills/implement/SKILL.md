---
name: implement
description: "Implement an authorized feature or fix through relevant verification. Use for scoped code changes; not for writing plans, creating issues, or PR delivery."
---

# Implement

Implement one authorized, scoped task through proportionate evidence and
verification. Read the task and relevant current state before acting. Preserve
unrelated work and the user's authority boundaries. This skill's job is the
smallest justified code change with evidence.

## Past decisions and current authority

Use relevant decision records to understand earlier trade-offs, not to veto
better solutions. Evaluate current evidence, constraints, and switching costs;
the old assumptions need not have changed. Verify any binding requirement at
its current source instead of treating an ADR's status as authority.

Within an authorized task, replace a past choice when justified and explain why
in the result; the ADR alone does not require another approval. Changes to an
explicit requirement or approved plan design, or work outside the task's scope,
still need the applicable approval. Preserve the earlier rationale and record
the replacement when project-document updates are in scope, using
[decision history](../sharpen/ADR-FORMAT.md).

## Contract

1. Make the smallest justified change. Challenge the result against the
   intended outcome and remove unnecessary code, abstractions, or special cases.
   A no-change result is valid when the requested behavior already holds.
2. Choose evidence by behavioral risk. Default to no new permanent test; a
   static check, reproducible demonstration, existing workflow, or explicit
   no-permanent-test decision is often enough. Before adding or rewriting a
   permanent test, or when behavior is uncertain or a probe is requested, use
   `/testing-code` and pass its admission gate.
3. Run relevant repository gates and behavior-specific checks. A failing
   required gate blocks completion and publication, but continue authorized
   diagnosis and correction when that can resolve the failure. Report unrelated
   baseline failures without silently fixing unrelated code.
4. Report the change, evidence, verification, and unresolved concerns.

## Plans and issues

- When the caller names a plan (for example `ABC-123-slug.md`), read it first
  and work to it. Follow [plan storage](../write-plan/references/plan-storage.md)
  to find plans in the main checkout; resolve `../../scripts/plan_sync.py` from
  this skill's directory, not the current working directory, when running `dir`.
  If a material design choice changes during the work, update the plan's
  Decisions section.
- For work with an issue, include its key when creating a branch; preserve an
  established branch name. Git and the pull request move the issue's status;
  comment on the issue only for a blocker or a decision that needs the user.
- For substantive changes, give an independent reviewer the actual diff,
  accepted requirements, and relevant verification evidence.

For substantial work with independently executable parts, use
[orchestrate](../orchestrate/SKILL.md) to delegate them before implementation.
Keep tightly coupled changes with one agent, and send a single independent
review directly to the reviewer. The lead remains responsible for decisions,
integration, and final verification. A bounded worker reports to its caller
rather than dispatching more agents unless its assignment authorizes that.
