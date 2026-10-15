---
name: implement
description: "Implement an authorized feature or fix through relevant verification. Use for scoped code changes."
---

# Implement

Implement one authorized, scoped task through proportionate evidence and
verification. Read the task and relevant current state before acting. Preserve
unrelated work and the user's authority boundaries. This skill's job is the
smallest justified code change with evidence.

## Past decisions

When the change replaces a past decision, supersede its record per the
[ADR format](../../references/ADR-FORMAT.md).

## Contract

1. Make the smallest justified change. Before you add code, a layer, or a
   special case, follow
   [subtract-before-you-add](../principle-subtract-before-you-add/SKILL.md).
   When the work has several steps, such as a sweep or a migration, follow
   [sequence-verifiable-units](../principle-sequence-verifiable-units/SKILL.md).
   When the change adds a migration, job, retry, or resume path, follow
   [make-operations-idempotent](../principle-make-operations-idempotent/SKILL.md).
2. For a reported defect, find the cause with
   [diagnose](../diagnose/SKILL.md) before you change code, and rerun its
   reproduction after the fix. Before you apply the fix, and after a fix
   fails, follow [fix-root-causes](../principle-fix-root-causes/SKILL.md).
3. Choose evidence by behavioral risk, and name the behavior check before
   writing code. A static check, reproducible demonstration, existing
   workflow, or explicit no-permanent-test decision is often enough. Before adding or rewriting a permanent test, or when behavior
   is uncertain or a probe is requested, pass the `testing-code` admission
   gate. Before claiming the change works, follow
   [prove-it-works](../principle-prove-it-works/SKILL.md).
4. Run relevant repository gates and behavior-specific checks. A failing
   required gate blocks completion and publication, but continue authorized
   diagnosis and correction when that can resolve the failure. When you find an
   issue outside the task, such as an unrelated baseline failure, follow
   [ancillary-fixes](../principle-ancillary-fixes/SKILL.md).
5. Report the change, evidence, verification, and unresolved concerns.

## Documentation completion

An authorized code or convention change includes updating documentation that
it makes obsolete; do not ask separately. Find and update affected guidance in
repository docs, READMEs, linked project or vault notes, tracker descriptions,
and agent instructions. Follow each destination's authoring and access rules;
for a README or a docs page, follow `writing`. Replace stale guidance with
the current behavior; earlier rationale stays in ADRs and the PR. Report any
affected documentation left stale and the reason.

## Plans and issues

- When the caller names a plan (for example `fix-login-redirect.md`), read it
  first and work to it. Follow [plan storage](../../references/plan-storage.md)
  to find plans in the main checkout; resolve `../../scripts/handoff.py` from
  this skill's directory, not the current working directory, when running `dir`.
  If a material design choice changes during the work, update the plan's
  Decisions section.
- For work with an issue, include its key when creating a branch; preserve an
  established branch name. Git and the pull request move the issue's status;
  comment on the issue only for a blocker or a decision that needs the user.
- For substantive changes, give an independent reviewer the actual diff,
  accepted requirements, and relevant verification evidence. Ask it to report
  only gaps in correctness or the stated requirements.

For substantial work with independently executable parts, use
[orchestrate](../orchestrate/SKILL.md) before implementation. The lead remains
responsible for decisions, integration, and final verification. A bounded
worker reports to its caller rather than dispatching more agents unless its
assignment authorizes that.
